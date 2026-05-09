import requests
import time
import math
from datetime import datetime

# ========== НАСТРОЙКИ TELEGRAM ==========
TELEGRAM_TOKEN = "8695713035:AAELPJ25J5SMbw2Ed6rEW1fiuAtRZ4L9Abc"
CHAT_ID = "694614387"

# ========== ОСНОВНЫЕ ПАРАМЕТРЫ (смягчённые для гарантии сигналов) ==========
CHECK_INTERVAL = 600            # 10 минут (для стабильности)
TOP_VOLATILE_COINS = 20         # топ-20 альткоинов
MIN_VOLUME_USDT = 2_000_000     # мин. объём $2M (раньше было 5M)
MIN_CHANGE_5M = 0.2             # мин. изменение за 5 минут 0.2% (раньше 0.4)
LEVERAGE = 3

# ========== ДИНАМИЧЕСКИЕ TP/SL (без изменений) ==========
ATR_PERIOD = 14
ATR_STOP_MULT = 1.2
ATR_TP_MULT_BASE = 2.0
ADX_STRONG = 25
STRONG_TREND_FACTOR = 1.3
WEAK_TREND_FACTOR = 0.7
USE_BB_LIMITS = True
BB_PERIOD = 20
BB_STD = 2

# ========== ИНДИКАТОРЫ ==========
MIN_AGREEMENT = 3               # 3 из 7 индикаторов (раньше 4)
RSI_PERIOD = 14
RSI_OVERSOLD = 30
RSI_OVERBOUGHT = 70
MACD_FAST = 12
MACD_SLOW = 26
EMA_SHORT = 9
EMA_LONG = 21
VOLUME_SURGE_FACTOR = 1.5
ADX_PERIOD = 14
SMA50_PERIOD = 50
# ==================================================

def send_telegram(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try:
        requests.post(url, json={"chat_id": CHAT_ID, "text": text, "parse_mode": "HTML"})
    except Exception as e:
        print("Ошибка отправки в Telegram:", e)

def get_top_volume_coins(limit=50):
    url = f"https://api.coingecko.com/api/v3/coins/markets?vs_currency=usd&order=volume_desc&per_page={limit}&page=1&sparkline=false"
    try:
        response = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
        data = response.json()
        exclude = ['BTC', 'ETH', 'USDT', 'USDC', 'DAI', 'BUSD', 'TUSD', 'USDP', 'FDUSD', 'PAXG', 'XAUT']
        top = []
        for coin in data:
            sym = coin['symbol'].upper()
            if sym in exclude:
                continue
            name = coin['name'].lower()
            if 'stable' in name or 'dollar' in name:
                continue
            top.append({'symbol': sym, 'volume': coin.get('total_volume', 0)})
        return top
    except Exception as e:
        print("Ошибка CoinGecko:", e)
        return []

def get_klines(symbol, interval='5m', limit=100):
    url = f"https://api.binance.com/api/v3/klines?symbol={symbol}USDT&interval={interval}&limit={limit}"
    try:
        response = requests.get(url, timeout=10)
        data = response.json()
        if not isinstance(data, list) or len(data) == 0:
            return [], [], [], []
        closes, highs, lows, volumes = [], [], [], []
        for candle in data:
            if len(candle) < 6:
                continue
            try:
                closes.append(float(candle[4]))
                highs.append(float(candle[2]))
                lows.append(float(candle[3]))
                volumes.append(float(candle[5]))
            except (ValueError, IndexError):
                continue
        return closes, highs, lows, volumes
    except Exception as e:
        # Не печатаем ошибку для каждой монеты, чтобы не засорять консоль
        return [], [], [], []

def calculate_rsi(closes, period=14):
    if len(closes) < period+1:
        return None
    gains, losses = [], []
    for i in range(1, len(closes)):
        diff = closes[i] - closes[i-1]
        gains.append(diff if diff>0 else 0)
        losses.append(-diff if diff<0 else 0)
    avg_gain = sum(gains[-period:])/period
    avg_loss = sum(losses[-period:])/period
    if avg_loss == 0:
        return 100
    return 100 - 100/(1+avg_gain/avg_loss)

def calculate_ema(closes, period):
    if len(closes) < period:
        return None
    mult = 2/(period+1)
    ema = closes[0]
    for p in closes[1:]:
        ema = (p-ema)*mult + ema
    return ema

def calculate_sma(closes, period):
    if len(closes) < period:
        return None
    return sum(closes[-period:]) / period

def calculate_bollinger_bands(closes, period=20, std=2):
    if len(closes) < period:
        return None, None, None
    last = closes[-period:]
    sma = sum(last)/period
    variance = sum((p-sma)**2 for p in last)/period
    stdev = math.sqrt(variance)
    return sma+std*stdev, sma-std*stdev, sma

def calculate_macd_diff(closes, fast=12, slow=26):
    ema_f = calculate_ema(closes, fast)
    ema_s = calculate_ema(closes, slow)
    return ema_f - ema_s if ema_f and ema_s else None

def calculate_adx(highs, lows, closes, period=14):
    if len(closes) < period+1:
        return None
    tr, plus_dm, minus_dm = [], [], []
    for i in range(1, len(closes)):
        hl = highs[i]-lows[i]
        hc = abs(highs[i]-closes[i-1])
        lc = abs(lows[i]-closes[i-1])
        tr.append(max(hl, hc, lc))
        high_diff = highs[i]-highs[i-1]
        low_diff = lows[i-1]-lows[i]
        plus_dm.append(high_diff if high_diff>low_diff and high_diff>0 else 0)
        minus_dm.append(low_diff if low_diff>high_diff and low_diff>0 else 0)
    if len(tr) < period:
        return None
    avg_tr = sum(tr[-period:])/period
    avg_plus = sum(plus_dm[-period:])/period
    avg_minus = sum(minus_dm[-period:])/period
    if avg_tr == 0:
        return None
    plus_di = avg_plus/avg_tr*100
    minus_di = avg_minus/avg_tr*100
    dx = abs(plus_di-minus_di)/(plus_di+minus_di)*100 if (plus_di+minus_di)!=0 else 0
    return round(dx,1)

def calculate_atr(highs, lows, closes, period=14):
    if len(closes) < period+1:
        return None
    tr = []
    for i in range(1, len(closes)):
        hl = highs[i]-lows[i]
        hc = abs(highs[i]-closes[i-1])
        lc = abs(lows[i]-closes[i-1])
        tr.append(max(hl, hc, lc))
    if len(tr) < period:
        return None
    atr_abs = sum(tr[-period:])/period
    return (atr_abs / closes[-1]) * 100 if closes[-1] != 0 else None

def dynamic_tp_sl(current_price, atr_percent, adx, bb_upper, bb_lower, direction):
    if atr_percent is None:
        atr_percent = 0.5
    if adx is not None and adx > ADX_STRONG:
        factor = STRONG_TREND_FACTOR
        trend_desc = "сильный тренд"
    elif adx is not None and adx < 20:
        factor = WEAK_TREND_FACTOR
        trend_desc = "слабый тренд (флет)"
    else:
        factor = 1.0
        trend_desc = "умеренный тренд"
    sl_mult = ATR_STOP_MULT * factor
    tp_mult = ATR_TP_MULT_BASE * factor
    sl_percent = atr_percent * sl_mult
    tp_percent = atr_percent * tp_mult
    bb_correction = ""
    if USE_BB_LIMITS and bb_upper and bb_lower:
        if direction == 'long':
            max_tp_price = bb_upper
            max_tp_percent = (max_tp_price/current_price - 1)*100
            if tp_percent > max_tp_percent and max_tp_percent > 0:
                tp_percent = max_tp_percent*0.9
                bb_correction = f" (скорректировано по верхней полосе {bb_upper:.2f})"
        else:
            min_tp_price = bb_lower
            min_tp_percent = (1 - min_tp_price/current_price)*100
            if tp_percent > min_tp_percent and min_tp_percent > 0:
                tp_percent = min_tp_percent*0.9
                bb_correction = f" (скорректировано по нижней полосе {bb_lower:.2f})"
    explanation = f"ATR={atr_percent:.2f}%, множители SL={sl_mult:.1f}×, TP={tp_mult:.1f}×. Тренд: {trend_desc}.{bb_correction}"
    return round(tp_percent,2), round(sl_percent,2), explanation

def detect_signal_and_levels(closes, highs, lows, volumes):
    if len(closes) < max(RSI_PERIOD, EMA_LONG, BB_PERIOD, MACD_SLOW, ADX_PERIOD, SMA50_PERIOD, 60):
        return None, {}
    curr_price = closes[-1]
    ind = {}
    desc = {}
    
    # RSI
    rsi = calculate_rsi(closes, RSI_PERIOD)
    if rsi:
        if rsi < RSI_OVERSOLD:
            ind['rsi'] = 'long'
            desc['rsi'] = f"RSI={rsi} (<{RSI_OVERSOLD}) – перепроданность"
        elif rsi > RSI_OVERBOUGHT:
            ind['rsi'] = 'short'
            desc['rsi'] = f"RSI={rsi} (>{RSI_OVERBOUGHT}) – перекупленность"
        else:
            desc['rsi'] = f"RSI={rsi} (нейтрально)"
    else:
        desc['rsi'] = "RSI нет данных"
    
    # EMA
    ema_s = calculate_ema(closes, EMA_SHORT)
    ema_l = calculate_ema(closes, EMA_LONG)
    if ema_s and ema_l:
        if ema_s > ema_l:
            ind['ema'] = 'long'
            desc['ema'] = f"EMA{EMA_SHORT}>{EMA_LONG} – восходящий тренд"
        else:
            ind['ema'] = 'short'
            desc['ema'] = f"EMA{EMA_SHORT}<{EMA_LONG} – нисходящий тренд"
    else:
        desc['ema'] = "EMA нет данных"
    
    # Боллинджер
    bb_up, bb_low, _ = calculate_bollinger_bands(closes, BB_PERIOD, BB_STD)
    if bb_up and bb_low:
        if curr_price < bb_low:
            ind['bb'] = 'long'
            desc['bb'] = f"Цена ниже нижней полосы ({bb_low:.2f})"
        elif curr_price > bb_up:
            ind['bb'] = 'short'
            desc['bb'] = f"Цена выше верхней полосы ({bb_up:.2f})"
        else:
            desc['bb'] = f"Цена внутри полос ({bb_low:.2f}–{bb_up:.2f})"
    else:
        desc['bb'] = "Боллинджер нет данных"
    
    # MACD
    macd = calculate_macd_diff(closes, MACD_FAST, MACD_SLOW)
    if macd is not None:
        if macd > 0:
            ind['macd'] = 'long'
            desc['macd'] = f"MACD положительный ({macd:.2f}) – бычий импульс"
        else:
            ind['macd'] = 'short'
            desc['macd'] = f"MACD отрицательный ({macd:.2f}) – медвежий импульс"
    else:
        desc['macd'] = "MACD нет данных"
    
    # Объём
    avg_vol = sum(volumes[-20:-1])/19 if len(volumes)>=20 else None
    if avg_vol and volumes[-1] > avg_vol * VOLUME_SURGE_FACTOR:
        if len(closes)>=2 and closes[-1] > closes[-2]:
            ind['volume'] = 'long'
            desc['volume'] = f"Всплеск объёма (x{volumes[-1]/avg_vol:.1f}) на росте"
        elif len(closes)>=2 and closes[-1] < closes[-2]:
            ind['volume'] = 'short'
            desc['volume'] = f"Всплеск объёма (x{volumes[-1]/avg_vol:.1f}) на падении"
        else:
            desc['volume'] = "Всплеск объёма, цена стабильна"
    else:
        desc['volume'] = "Объём в норме"
    
    # ADX
    adx = calculate_adx(highs, lows, closes, ADX_PERIOD)
    if adx and adx > ADX_STRONG:
        if ind.get('ema') == 'long':
            ind['adx'] = 'long'
            desc['adx'] = f"ADX={adx} (сильный тренд вверх)"
        elif ind.get('ema') == 'short':
            ind['adx'] = 'short'
            desc['adx'] = f"ADX={adx} (сильный тренд вниз)"
        else:
            desc['adx'] = f"ADX={adx} (сильный тренд, направление неясно)"
    else:
        desc['adx'] = f"ADX={adx if adx else '?'} (слабый тренд)"
    
    # SMA50
    sma50 = calculate_sma(closes, SMA50_PERIOD)
    if sma50 is not None:
        if curr_price > sma50:
            ind['sma50'] = 'long'
            desc['sma50'] = f"Цена выше SMA50 ({sma50:.4f}) – долгосрочный тренд вверх"
        else:
            ind['sma50'] = 'short'
            desc['sma50'] = f"Цена ниже SMA50 ({sma50:.4f}) – долгосрочный тренд вниз"
    else:
        desc['sma50'] = "SMA50 нет данных"
    
    # Подсчёт голосов (7 индикаторов)
    votes = []
    for k in ['rsi','ema','bb','macd','volume','adx','sma50']:
        if k in ind and ind[k] is not None:
            votes.append(ind[k])
    long_votes = votes.count('long')
    short_votes = votes.count('short')
    
    direction = None
    if long_votes >= MIN_AGREEMENT:
        direction = 'long'
    elif short_votes >= MIN_AGREEMENT:
        direction = 'short'
    
    atr_pct = calculate_atr(highs, lows, closes, ATR_PERIOD) or 0.5
    tp_pct, sl_pct, tp_sl_exp = (None, None, "")
    if direction:
        tp_pct, sl_pct, tp_sl_exp = dynamic_tp_sl(curr_price, atr_pct, adx, bb_up, bb_low, direction)
    
    details = {
        'long_votes': long_votes,
        'short_votes': short_votes,
        'descriptions': desc,
        'current_price': curr_price,
        'tp_percent': tp_pct,
        'sl_percent': sl_pct,
        'tp_sl_explanation': tp_sl_exp,
        'atr_percent': atr_pct,
        'adx': adx
    }
    return direction, details

def analyze_and_signal():
    coins = get_top_volume_coins(TOP_VOLATILE_COINS * 2)
    if not coins:
        send_telegram("⚠️ Не удалось получить список альткоинов с CoinGecko")
        return
    
    filtered = [c for c in coins if c['volume'] >= MIN_VOLUME_USDT][:TOP_VOLATILE_COINS]
    sig_count = 0
    for coin in filtered:
        symbol = coin['symbol']
        closes, highs, lows, volumes = get_klines(symbol, interval='5m', limit=100)
        time.sleep(0.3)   # задержка для API
        if len(closes) < 60:
            continue
        
        change_5m = (closes[-1] - closes[-2]) / closes[-2] * 100 if len(closes) >= 2 else 0
        if abs(change_5m) < MIN_CHANGE_5M:
            continue
        
        direction, det = detect_signal_and_levels(closes, highs, lows, volumes)
        if not direction:
            continue
        
        price = det['current_price']
        tp_pct = det['tp_percent']
        sl_pct = det['sl_percent']
        if tp_pct is None or sl_pct is None:
            continue
        
        if direction == 'long':
            tp = price * (1 + tp_pct / 100)
            sl = price * (1 - sl_pct / 100)
            msg = f"""
📢 <b>LONG СИГНАЛ ({symbol})</b> — {det['long_votes']}/7 индикаторов ЗА

💰 <b>Вход:</b> ${price:.6f}
🎯 <b>TP (динамический):</b> ${tp:.6f} (+{tp_pct}%)
🛑 <b>SL (динамический):</b> ${sl:.6f} (-{sl_pct}%)
⚙️ <b>Плечо:</b> {LEVERAGE}x

📊 <b>Индикаторы:</b>
• {det['descriptions'].get('rsi', '—')}
• {det['descriptions'].get('ema', '—')}
• {det['descriptions'].get('bb', '—')}
• {det['descriptions'].get('macd', '—')}
• {det['descriptions'].get('volume', '—')}
• {det['descriptions'].get('adx', '—')}
• {det['descriptions'].get('sma50', '—')}

🧮 <b>Расчёт TP/SL:</b> {det['tp_sl_explanation']}

💡 <b>Вывод:</b> Консенсус индикаторов — лонг.
⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
        else:
            tp = price * (1 - tp_pct / 100)
            sl = price * (1 + sl_pct / 100)
            msg = f"""
📢 <b>SHORT СИГНАЛ ({symbol})</b> — {det['short_votes']}/7 индикаторов ЗА

💰 <b>Вход:</b> ${price:.6f}
🎯 <b>TP (динамический):</b> ${tp:.6f} (падение {tp_pct}%)
🛑 <b>SL (динамический):</b> ${sl:.6f} (рост {sl_pct}%)
⚙️ <b>Плечо:</b> {LEVERAGE}x

📊 <b>Индикаторы:</b>
• {det['descriptions'].get('rsi', '—')}
• {det['descriptions'].get('ema', '—')}
• {det['descriptions'].get('bb', '—')}
• {det['descriptions'].get('macd', '—')}
• {det['descriptions'].get('volume', '—')}
• {det['descriptions'].get('adx', '—')}
• {det['descriptions'].get('sma50', '—')}

🧮 <b>Расчёт TP/SL:</b> {det['tp_sl_explanation']}

💡 <b>Вывод:</b> Консенсус индикаторов — шорт.
⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
        send_telegram(msg)
        sig_count += 1
        time.sleep(1)
    
    if sig_count == 0:
        print(f"{datetime.now()} - Сигналов нет (требуется {MIN_AGREEMENT}/7 согласия).")
        # Раз в час шлём "бот жив" (опционально)
        if datetime.now().minute < 1:
            send_telegram("🟢 Крипто-бот работает, но сигналов пока нет.")

# ========== ЗАПУСК С ТЕСТОВЫМ СООБЩЕНИЕМ ==========
send_telegram("🚀 Бот запущен и начинает анализ альткоинов (настройки: 3 из 7 индикаторов, мин. движение 0.2%)")
print("Бот с 7 индикаторами (RSI, EMA, Боллинджер, MACD, объём, ADX, SMA50) запущен.")
print(f"Проверка каждые {CHECK_INTERVAL//60} мин. Минимум согласия: {MIN_AGREEMENT}/7")

while True:
    try:
        analyze_and_signal()
        time.sleep(CHECK_INTERVAL)
    except Exception as e:
        print("Ошибка в основном цикле:", e)
        time.sleep(60)