import requests
import time
import math
from datetime import datetime

# ========== НАСТРОЙКИ TELEGRAM ==========
TELEGRAM_TOKEN = "8695713035:AAELPJ25J5SMbw2Ed6rEW1fiuAtRZ4L9Abc"
CHAT_ID = "694614387"

# ========== ОСНОВНЫЕ ПАРАМЕТРЫ ==========
CHECK_INTERVAL = 600
TOP_VOLATILE_COINS = 20
MIN_VOLUME_USDT = 2_000_000
MIN_CHANGE_5M = 0.2
LEVERAGE = 3

# ========== НАСТРОЙКИ ИНДИКАТОРОВ ==========
MIN_AGREEMENT = 4
RSI_PERIOD = 14; RSI_OVERSOLD = 30; RSI_OVERBOUGHT = 70
MACD_FAST = 12; MACD_SLOW = 26
EMA_SHORT = 9; EMA_LONG = 21
VOLUME_SURGE_FACTOR = 1.5
ADX_PERIOD = 14
SMA50_PERIOD = 50
BB_PERIOD = 20; BB_STD = 2
# ==========================================

def send_telegram(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try:
        requests.post(url, json={"chat_id": CHAT_ID, "text": text, "parse_mode": "HTML"})
    except:
        pass

def get_top_volume_coins(limit=50):
    url = f"https://api.coingecko.com/api/v3/coins/markets?vs_currency=usd&order=volume_desc&per_page={limit}&page=1&sparkline=false"
    try:
        response = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
        data = response.json()
        exclude = ['BTC', 'ETH', 'USDT', 'USDC', 'DAI', 'BUSD', 'TUSD', 'USDP', 'FDUSD', 'PAXG', 'XAUT']
        top = []
        for coin in data:
            sym = coin['symbol'].upper()
            if sym in exclude: continue
            name = coin['name'].lower()
            if 'stable' in name or 'dollar' in name: continue
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
        closes = [float(c[4]) for c in data]
        highs = [float(c[2]) for c in data]
        lows = [float(c[3]) for c in data]
        volumes = [float(c[5]) for c in data]
        return closes, highs, lows, volumes
    except:
        return [], [], [], []

def calculate_rsi(closes, period=14):
    if len(closes) < period+1: return None
    gains, losses = [], []
    for i in range(1, len(closes)):
        diff = closes[i] - closes[i-1]
        gains.append(diff if diff>0 else 0)
        losses.append(-diff if diff<0 else 0)
    avg_gain = sum(gains[-period:])/period
    avg_loss = sum(losses[-period:])/period
    if avg_loss == 0: return 100
    return 100 - 100/(1+avg_gain/avg_loss)

def calculate_ema(closes, period):
    if len(closes) < period: return None
    mult = 2/(period+1)
    ema = closes[0]
    for p in closes[1:]: ema = (p-ema)*mult + ema
    return ema

def calculate_sma(closes, period):
    if len(closes) < period: return None
    return sum(closes[-period:])/period

def calculate_bollinger_bands(closes, period=20, std=2):
    if len(closes) < period: return None, None, None
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
    if len(closes) < period+1: return None
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
    if len(tr) < period: return None
    avg_tr = sum(tr[-period:])/period
    avg_plus = sum(plus_dm[-period:])/period
    avg_minus = sum(minus_dm[-period:])/period
    if avg_tr == 0: return None
    plus_di = avg_plus/avg_tr*100
    minus_di = avg_minus/avg_tr*100
    dx = abs(plus_di-minus_di)/(plus_di+minus_di)*100 if (plus_di+minus_di)!=0 else 0
    return round(dx,1)

def calculate_atr(highs, lows, closes, period=14):
    if len(closes) < period+1: return None
    tr = []
    for i in range(1, len(closes)):
        hl = highs[i]-lows[i]
        hc = abs(highs[i]-closes[i-1])
        lc = abs(lows[i]-closes[i-1])
        tr.append(max(hl, hc, lc))
    if len(tr) < period: return None
    atr_abs = sum(tr[-period:])/period
    return (atr_abs / closes[-1]) * 100 if closes[-1] != 0 else None

def find_nearest_support_resistance(highs, lows, closes, current_price, direction):
    lookback = min(20, len(closes)-1)
    if direction == 'long':
        local_lows = []
        for i in range(-lookback, 0):
            if i+1 < 0 and i-1 >= -lookback:
                if lows[i] <= lows[i-1] and lows[i] <= lows[i+1]:
                    local_lows.append(lows[i])
        if local_lows:
            nearest = min(local_lows, key=lambda x: current_price - x if current_price > x else float('inf'))
            if current_price > nearest:
                return nearest
    else:
        local_highs = []
        for i in range(-lookback, 0):
            if i+1 < 0 and i-1 >= -lookback:
                if highs[i] >= highs[i-1] and highs[i] >= highs[i+1]:
                    local_highs.append(highs[i])
        if local_highs:
            nearest = max(local_highs, key=lambda x: x - current_price if x > current_price else -float('inf'))
            if current_price < nearest:
                return nearest
    return None

def auto_tp_sl(current_price, closes, highs, lows, adx, direction):
    atr_pct = calculate_atr(highs, lows, closes, 14) or 0.5
    bb_up, bb_low, bb_mid = calculate_bollinger_bands(closes, 20, 2)
    if adx and adx > 25:
        trend_factor = 1.5
        trend_desc = "сильный тренд"
    elif adx and adx < 20:
        trend_factor = 0.8
        trend_desc = "слабый тренд (флет)"
    else:
        trend_factor = 1.0
        trend_desc = "умеренный тренд"
    base_sl_percent = atr_pct * trend_factor
    base_sl_percent = max(0.5, min(3.0, base_sl_percent))
    nearest_level = find_nearest_support_resistance(highs, lows, closes, current_price, direction)
    if nearest_level:
        if direction == 'long':
            sl_by_level = (current_price - nearest_level) / current_price * 100
        else:
            sl_by_level = (nearest_level - current_price) / current_price * 100
        final_sl_percent = max(base_sl_percent, sl_by_level * 0.8)
        level_str = f"{nearest_level:.4f}"
    else:
        final_sl_percent = base_sl_percent
        level_str = "ATR"
    if atr_pct > 1.5:
        tp_mult = 1.5
    elif atr_pct > 0.8:
        tp_mult = 2.0
    else:
        tp_mult = 2.5
    if adx and adx > 30:
        tp_mult *= 1.3
    final_tp_percent = final_sl_percent * tp_mult
    final_tp_percent = min(5.0, final_tp_percent)
    tp_price = current_price * (1 + final_tp_percent/100) if direction == 'long' else current_price * (1 - final_tp_percent/100)
    sl_price = current_price * (1 - final_sl_percent/100) if direction == 'long' else current_price * (1 + final_sl_percent/100)
    explanation = (f"АТР={atr_pct:.2f}%, тренд: {trend_desc}, множитель {tp_mult:.1f}. "
                   f"Стоп {final_sl_percent:.2f}% (уровень: {level_str}), "
                   f"Тейк {final_tp_percent:.2f}%")
    return tp_price, sl_price, final_tp_percent, final_sl_percent, explanation

# ---------- Функции индикаторов и detect_signal_and_levels (сокращённо, но рабочие) ----------
# Для краткости я включу полную версию detect_signal_and_levels, иначе код будет неполным.
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
            ind['rsi'] = 'long'; desc['rsi'] = f"RSI={rsi} (<{RSI_OVERSOLD}) – перепроданность"
        elif rsi > RSI_OVERBOUGHT:
            ind['rsi'] = 'short'; desc['rsi'] = f"RSI={rsi} (>{RSI_OVERBOUGHT}) – перекупленность"
        else:
            desc['rsi'] = f"RSI={rsi} (нейтрально)"
    else:
        desc['rsi'] = "RSI нет данных"
    # EMA
    ema_s = calculate_ema(closes, EMA_SHORT)
    ema_l = calculate_ema(closes, EMA_LONG)
    if ema_s and ema_l:
        if ema_s > ema_l:
            ind['ema'] = 'long'; desc['ema'] = f"EMA{EMA_SHORT}>{EMA_LONG} – восходящий тренд"
        else:
            ind['ema'] = 'short'; desc['ema'] = f"EMA{EMA_SHORT}<{EMA_LONG} – нисходящий тренд"
    else:
        desc['ema'] = "EMA нет данных"
    # Боллинджер
    bb_up, bb_low, _ = calculate_bollinger_bands(closes, BB_PERIOD, BB_STD)
    if bb_up and bb_low:
        if curr_price < bb_low:
            ind['bb'] = 'long'; desc['bb'] = f"Цена ниже нижней полосы ({bb_low:.2f})"
        elif curr_price > bb_up:
            ind['bb'] = 'short'; desc['bb'] = f"Цена выше верхней полосы ({bb_up:.2f})"
        else:
            desc['bb'] = f"Цена внутри полос ({bb_low:.2f}–{bb_up:.2f})"
    else:
        desc['bb'] = "Боллинджер нет данных"
    # MACD
    macd = calculate_macd_diff(closes, MACD_FAST, MACD_SLOW)
    if macd is not None:
        if macd > 0:
            ind['macd'] = 'long'; desc['macd'] = f"MACD положительный ({macd:.2f}) – бычий импульс"
        else:
            ind['macd'] = 'short'; desc['macd'] = f"MACD отрицательный ({macd:.2f}) – медвежий импульс"
    else:
        desc['macd'] = "MACD нет данных"
    # Объём
    avg_vol = sum(volumes[-20:-1])/19 if len(volumes)>=20 else None
    if avg_vol and volumes[-1] > avg_vol * VOLUME_SURGE_FACTOR:
        if len(closes)>=2 and closes[-1] > closes[-2]:
            ind['volume'] = 'long'; desc['volume'] = f"Всплеск объёма (x{volumes[-1]/avg_vol:.1f}) на росте"
        elif len(closes)>=2 and closes[-1] < closes[-2]:
            ind['volume'] = 'short'; desc['volume'] = f"Всплеск объёма (x{volumes[-1]/avg_vol:.1f}) на падении"
        else:
            desc['volume'] = "Всплеск объёма, цена стабильна"
    else:
        desc['volume'] = "Объём в норме"
    # ADX
    adx = calculate_adx(highs, lows, closes, ADX_PERIOD)
    if adx and adx > 25:
        if ind.get('ema') == 'long':
            ind['adx'] = 'long'; desc['adx'] = f"ADX={adx} (сильный тренд вверх)"
        elif ind.get('ema') == 'short':
            ind['adx'] = 'short'; desc['adx'] = f"ADX={adx} (сильный тренд вниз)"
        else:
            desc['adx'] = f"ADX={adx} (сильный тренд)"
    else:
        desc['adx'] = f"ADX={adx if adx else '?'} (слабый тренд)"
    # SMA50
    sma50 = calculate_sma(closes, SMA50_PERIOD)
    if sma50 is not None:
        if curr_price > sma50:
            ind['sma50'] = 'long'; desc['sma50'] = f"Цена выше SMA50 ({sma50:.4f}) – долгосрочный тренд вверх"
        else:
            ind['sma50'] = 'short'; desc['sma50'] = f"Цена ниже SMA50 ({sma50:.4f}) – долгосрочный тренд вниз"
    else:
        desc['sma50'] = "SMA50 нет данных"
    # Голосование
    votes = [ind.get(k) for k in ['rsi','ema','bb','macd','volume','adx','sma50'] if ind.get(k) is not None]
    long_votes = votes.count('long')
    short_votes = votes.count('short')
    direction = None
    if long_votes >= MIN_AGREEMENT:
        direction = 'long'
    elif short_votes >= MIN_AGREEMENT:
        direction = 'short'
    if not direction:
        return None, {}
    # Авто TP/SL
    tp_price, sl_price, tp_pct, sl_pct, explanation = auto_tp_sl(curr_price, closes, highs, lows, adx, direction)
    details = {
        'long_votes': long_votes,
        'short_votes': short_votes,
        'descriptions': desc,
        'current_price': curr_price,
        'tp_price': tp_price,
        'sl_price': sl_price,
        'tp_percent': tp_pct,
        'sl_percent': sl_pct,
        'tp_sl_explanation': explanation
    }
    return direction, details

def analyze_and_signal():
    coins = get_top_volume_coins(TOP_VOLATILE_COINS * 2)
    if not coins:
        send_telegram("⚠️ Не удалось получить список альткоинов")
        return
    filtered = [c for c in coins if c['volume'] >= MIN_VOLUME_USDT][:TOP_VOLATILE_COINS]
    sig_count = 0
    for coin in filtered:
        symbol = coin['symbol']
        closes, highs, lows, volumes = get_klines(symbol, interval='5m', limit=100)
        time.sleep(0.3)
        if len(closes) < 60: continue
        change_5m = (closes[-1] - closes[-2]) / closes[-2] * 100
        if abs(change_5m) < MIN_CHANGE_5M: continue
        direction, det = detect_signal_and_levels(closes, highs, lows, volumes)
        if not direction: continue
        price = det['current_price']
        tp_price = det['tp_price']
        sl_price = det['sl_price']
        tp_pct = det['tp_percent']
        sl_pct = det['sl_percent']
        if direction == 'long':
            msg = f"""
📢 <b>LONG СИГНАЛ ({symbol})</b> — {det['long_votes']}/7 индикаторов ЗА

💰 <b>Вход:</b> ${price:.6f}
🎯 <b>Тейк-профит (авто):</b> ${tp_price:.6f} (+{tp_pct}%)
🛑 <b>Стоп-лосс (авто):</b> ${sl_price:.6f} (-{sl_pct}%)
⚙️ <b>Плечо:</b> {LEVERAGE}x

📊 <b>Индикаторы:</b>
• {det['descriptions']['rsi']}
• {det['descriptions']['ema']}
• {det['descriptions']['bb']}
• {det['descriptions']['macd']}
• {det['descriptions']['volume']}
• {det['descriptions']['adx']}
• {det['descriptions']['sma50']}

🧮 <b>Расчёт TP/SL:</b> {det['tp_sl_explanation']}
💡 <b>Вывод:</b> Автоматический расчёт уровней под текущую волатильность.
⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
        else:
            msg = f"""
📢 <b>SHORT СИГНАЛ ({symbol})</b> — {det['short_votes']}/7 индикаторов ЗА

💰 <b>Вход:</b> ${price:.6f}
🎯 <b>Тейк-профит (авто):</b> ${tp_price:.6f} (падение {tp_pct}%)
🛑 <b>Стоп-лосс (авто):</b> ${sl_price:.6f} (рост {sl_pct}%)
⚙️ <b>Плечо:</b> {LEVERAGE}x

📊 <b>Индикаторы:</b>
• {det['descriptions']['rsi']}
• {det['descriptions']['ema']}
• {det['descriptions']['bb']}
• {det['descriptions']['macd']}
• {det['descriptions']['volume']}
• {det['descriptions']['adx']}
• {det['descriptions']['sma50']}

🧮 <b>Расчёт TP/SL:</b> {det['tp_sl_explanation']}
💡 <b>Вывод:</b> Автоматический расчёт уровней под текущую волатильность.
⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
        send_telegram(msg)
        sig_count += 1
        time.sleep(1)
    if sig_count == 0:
        print(f"{datetime.now()} - Сигналов нет (требуется {MIN_AGREEMENT}/7)")

# ========== ЗАПУСК ==========
send_telegram("🚀 Бот с авто-расчётом TP/SL запущен. Уровни адаптивны к волатильности.")
print("Бот с автоматическим расчётом TP/SL (без ручных множителей) запущен.")
while True:
    try:
        analyze_and_signal()
        time.sleep(CHECK_INTERVAL)
    except Exception as e:
        print("Ошибка:", e)
        time.sleep(60)
