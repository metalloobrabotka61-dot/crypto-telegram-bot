import requests
import time
import math
from datetime import datetime

# ========== НАСТРОЙКИ TELEGRAM ==========
TELEGRAM_TOKEN = "8695713035:AAELPJ25J5SMbw2Ed6rEW1fiuAtRZ4L9Abc"
CHAT_ID = "694614387"

# ========== ОСНОВНЫЕ ПАРАМЕТРЫ ==========
CHECK_INTERVAL = 300            # 5 минут между проверками
TOP_VOLATILE_COINS = 20         # топ-20 волатильных монет
MIN_VOLUME_USDT = 5_000_000     # мин. объём $5M
MIN_CHANGE_5M = 0.4             # мин. изменение цены за 5 мин (%)
LEVERAGE = 3                    # плечо (общее)

# ========== НАСТРОЙКИ ДИНАМИЧЕСКИХ TP/SL ==========
ATR_PERIOD = 14                 # период ATR
ATR_STOP_MULT = 1.2             # базовый множитель ATR для стоп-лосса
ATR_TP_MULT_BASE = 2.0          # базовый множитель ATR для тейк-профита
# Корректировка множителей в зависимости от ADX (силы тренда)
ADX_STRONG = 25                 # если ADX > 25, тренд сильный
STRONG_TREND_FACTOR = 1.3       # умножаем множители на 1.3 при сильном тренде
WEAK_TREND_FACTOR = 0.7         # умножаем на 0.7 при слабом тренде (ADX < 20)
# Использовать полосы Боллинджера для ограничения TP/SL (если цель выходит за полосу, корректируем)
USE_BB_LIMITS = True
BB_PERIOD = 20
BB_STD = 2
# ===============================================

# Настройки индикаторов (те же, что были)
MIN_AGREEMENT = 4
RSI_PERIOD = 14; RSI_OVERSOLD = 30; RSI_OVERBOUGHT = 70
MACD_FAST = 12; MACD_SLOW = 26
EMA_SHORT = 9; EMA_LONG = 21
VOLUME_SURGE_FACTOR = 1.5
STOCH_RSI_PERIOD = 14; STOCH_RSI_K = 14; STOCH_RSI_D = 3
ADX_PERIOD = 14
VWAP_PERIOD = 20

def send_telegram(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try:
        requests.post(url, json={"chat_id": CHAT_ID, "text": text, "parse_mode": "HTML"})
    except:
        pass

def get_top_volume_coins(limit=50):
    """Получает топ монет по объёму с CoinGecko (работает всегда)"""
    url = f"https://api.coingecko.com/api/v3/coins/markets?vs_currency=usd&order=volume_desc&per_page={limit}&page=1&sparkline=false"
    try:
        response = requests.get(url, headers={"User-Agent": "Mozilla/5.0"})
        data = response.json()
        top_coins = []
        for coin in data:
            top_coins.append({
                'symbol': coin['symbol'].upper(),
                'volume': coin.get('total_volume', 0)
            })
        return top_coins
    except Exception as e:
        print("Ошибка получения списка монет с CoinGecko:", e)
        return []

def get_klines(symbol, interval='5m', limit=100):
    url = f"https://api.binance.com/api/v3/klines?symbol={symbol}USDT&interval={interval}&limit={limit}"
    try:
        data = requests.get(url).json()
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

def calculate_stoch_rsi(closes, period=14, k_period=14, d_period=3):
    if len(closes) < period+k_period+d_period: return None, None
    rsi_vals = []
    for i in range(period, len(closes)):
        r = calculate_rsi(closes[i-period+1:i+1], period)
        if r: rsi_vals.append(r)
    if len(rsi_vals) < k_period: return None, None
    curr_rsi = rsi_vals[-1]
    min_rsi = min(rsi_vals[-k_period:])
    max_rsi = max(rsi_vals[-k_period:])
    k = 50 if max_rsi==min_rsi else (curr_rsi-min_rsi)/(max_rsi-min_rsi)*100
    # упрощённо %D = среднее за d_period
    if len(rsi_vals) >= k_period+d_period:
        d_vals = []
        for j in range(len(rsi_vals)-d_period, len(rsi_vals)):
            mn = min(rsi_vals[j-k_period+1:j+1])
            mx = max(rsi_vals[j-k_period+1:j+1])
            k_ = 50 if mx==mn else (rsi_vals[j]-mn)/(mx-mn)*100
            d_vals.append(k_)
        d = sum(d_vals)/d_period
    else:
        d = k
    return round(k,1), round(d,1)

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

def calculate_vwap(closes, volumes, period=20):
    if len(closes) < period or len(volumes) < period: return None
    val_sum = sum(closes[-i]*volumes[-i] for i in range(1, period+1))
    vol_sum = sum(volumes[-i] for i in range(1, period+1))
    return val_sum/vol_sum if vol_sum else None

def calculate_atr(highs, lows, closes, period=14):
    """Возвращает ATR в процентах от текущей цены"""
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
    atr_abs = sum(tr[-period:]) / period
    current_price = closes[-1]
    if current_price == 0:
        return None
    return (atr_abs / current_price) * 100   # ATR в процентах

def dynamic_tp_sl(current_price, atr_percent, adx, bb_upper, bb_lower, direction):
    """
    Рассчитывает TP и SL в процентах от цены входа.
    direction: 'long' или 'short'
    Возвращает (tp_percent, sl_percent, explanation)
    """
    # базовые множители
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
    
    # Корректировка по полосам Боллинджера (если включено)
    bb_correction = ""
    if USE_BB_LIMITS and bb_upper and bb_lower:
        if direction == 'long':
            # Цель (TP) не должна быть выше верхней полосы (разумный предел)
            max_tp_price = bb_upper
            max_tp_percent = (max_tp_price / current_price - 1) * 100
            if tp_percent > max_tp_percent and max_tp_percent > 0:
                tp_percent = max_tp_percent * 0.9  # чуть ниже полосы
                bb_correction = f" (скорректировано по верхней полосе Боллинджера {bb_upper:.2f})"
        else:  # short
            min_tp_price = bb_lower
            min_tp_percent = (1 - min_tp_price / current_price) * 100
            if tp_percent > min_tp_percent and min_tp_percent > 0:
                tp_percent = min_tp_percent * 0.9
                bb_correction = f" (скорректировано по нижней полосе Боллинджера {bb_lower:.2f})"
    
    explanation = f"ATR = {atr_percent:.2f}%, множители: SL={sl_mult:.1f}×, TP={tp_mult:.1f}×. Тренд: {trend_desc}.{bb_correction}"
    return round(tp_percent, 2), round(sl_percent, 2), explanation

def detect_signal_and_levels(closes, highs, lows, volumes):
    if len(closes) < max(RSI_PERIOD, EMA_LONG, BB_PERIOD, MACD_SLOW, ADX_PERIOD, 30):
        return None, {}
    
    current_price = closes[-1]
    indicators = {}
    descriptions = {}
    
    # RSI
    rsi = calculate_rsi(closes, RSI_PERIOD)
    rsi_signal = None
    if rsi:
        if rsi < RSI_OVERSOLD:
            rsi_signal = 'long'
            desc = f"RSI = {rsi} (<{RSI_OVERSOLD}) – перепроданность"
        elif rsi > RSI_OVERBOUGHT:
            rsi_signal = 'short'
            desc = f"RSI = {rsi} (>{RSI_OVERBOUGHT}) – перекупленность"
        else:
            desc = f"RSI = {rsi} (нейтрально)"
        indicators['rsi'] = rsi_signal
        descriptions['rsi'] = desc
    
    # EMA
    ema_short = calculate_ema(closes, EMA_SHORT)
    ema_long = calculate_ema(closes, EMA_LONG)
    ema_signal = None
    if ema_short and ema_long:
        if ema_short > ema_long:
            ema_signal = 'long'
            desc = f"EMA{EMA_SHORT} > EMA{EMA_LONG} – восходящий тренд"
        else:
            ema_signal = 'short'
            desc = f"EMA{EMA_SHORT} < EMA{EMA_LONG} – нисходящий тренд"
        indicators['ema'] = ema_signal
        descriptions['ema'] = desc
    
    # Боллинджер
    bb_upper, bb_lower, bb_mid = calculate_bollinger_bands(closes, BB_PERIOD, BB_STD)
    bb_signal = None
    if bb_upper and bb_lower:
        if current_price < bb_lower:
            bb_signal = 'long'
            desc = f"Цена ниже нижней полосы Боллинджера ({bb_lower:.2f}) – зона перепроданности"
        elif current_price > bb_upper:
            bb_signal = 'short'
            desc = f"Цена выше верхней полосы Боллинджера ({bb_upper:.2f}) – зона перекупленности"
        else:
            desc = f"Цена внутри полос Боллинджера ({bb_lower:.2f}–{bb_upper:.2f})"
        indicators['bb'] = bb_signal
        descriptions['bb'] = desc
    
    # MACD
    macd = calculate_macd_diff(closes, MACD_FAST, MACD_SLOW)
    macd_signal = None
    if macd is not None:
        if macd > 0:
            macd_signal = 'long'
            desc = f"MACD положительный ({macd:.2f}) – бычий импульс"
        else:
            macd_signal = 'short'
            desc = f"MACD отрицательный ({macd:.2f}) – медвежий импульс"
        indicators['macd'] = macd_signal
        descriptions['macd'] = desc
    
    # Объём
    avg_vol = sum(volumes[-20:-1])/19 if len(volumes)>=20 else None
    vol_signal = None
    if avg_vol and volumes[-1] > avg_vol * VOLUME_SURGE_FACTOR:
        if len(closes)>=2 and closes[-1] > closes[-2]:
            vol_signal = 'long'
            desc = f"Всплеск объёма (x{volumes[-1]/avg_vol:.1f}) на росте"
        elif len(closes)>=2 and closes[-1] < closes[-2]:
            vol_signal = 'short'
            desc = f"Всплеск объёма (x{volumes[-1]/avg_vol:.1f}) на падении"
        else:
            desc = "Всплеск объёма, цена стабильна"
    else:
        desc = "Объём в норме"
    indicators['volume'] = vol_signal
    descriptions['volume'] = desc
    
    # StochRSI
    stoch_k, stoch_d = calculate_stoch_rsi(closes, STOCH_RSI_PERIOD, STOCH_RSI_K, STOCH_RSI_D)
    stoch_signal = None
    if stoch_k:
        if stoch_k < 20 and stoch_d < 20:
            stoch_signal = 'long'
            desc = f"StochRSI %K={stoch_k} (<20) – перепроданность"
        elif stoch_k > 80 and stoch_d > 80:
            stoch_signal = 'short'
            desc = f"StochRSI %K={stoch_k} (>80) – перекупленность"
        else:
            desc = f"StochRSI %K={stoch_k} (нейтрально)"
        indicators['stoch_rsi'] = stoch_signal
        descriptions['stoch_rsi'] = desc
    
    # ADX
    adx = calculate_adx(highs, lows, closes, ADX_PERIOD)
    adx_signal = None
    if adx is not None and adx > ADX_STRONG:
        if ema_signal == 'long':
            adx_signal = 'long'
            desc = f"ADX = {adx} (сильный тренд вверх)"
        elif ema_signal == 'short':
            adx_signal = 'short'
            desc = f"ADX = {adx} (сильный тренд вниз)"
        else:
            desc = f"ADX = {adx} (сильный тренд, направление неясно)"
    else:
        desc = f"ADX = {adx if adx else '?'} (слабый тренд)"
    indicators['adx'] = adx_signal
    descriptions['adx'] = desc
    
    # VWAP
    vwap = calculate_vwap(closes, volumes, VWAP_PERIOD)
    vwap_signal = None
    if vwap:
        if current_price > vwap:
            vwap_signal = 'long'
            desc = f"Цена выше VWAP ({vwap:.2f}) – бычье внутридневное смещение"
        else:
            vwap_signal = 'short'
            desc = f"Цена ниже VWAP ({vwap:.2f}) – медвежье смещение"
        indicators['vwap'] = vwap_signal
        descriptions['vwap'] = desc
    
    # Подсчёт голосов
    all_signals = [indicators.get(k) for k in ['rsi','ema','bb','macd','volume','stoch_rsi','adx','vwap'] if indicators.get(k) is not None]
    long_votes = all_signals.count('long')
    short_votes = all_signals.count('short')
    
    direction = None
    if long_votes >= MIN_AGREEMENT:
        direction = 'long'
    elif short_votes >= MIN_AGREEMENT:
        direction = 'short'
    
    # Динамические TP/SL (нужны ATR, ADX, Боллинджер)
    atr_percent = calculate_atr(highs, lows, closes, ATR_PERIOD)
    if atr_percent is None:
        atr_percent = 0.5  # значение по умолчанию, если не рассчиталось
    
    tp_percent, sl_percent, tp_sl_explanation = dynamic_tp_sl(
        current_price, atr_percent, adx, bb_upper, bb_lower, direction
    ) if direction else (None, None, "")
    
    details = {
        'long_votes': long_votes,
        'short_votes': short_votes,
        'indicators': indicators,
        'descriptions': descriptions,
        'current_price': current_price,
        'tp_percent': tp_percent,
        'sl_percent': sl_percent,
        'tp_sl_explanation': tp_sl_explanation,
        'atr_percent': atr_percent,
        'adx': adx
    }
    return direction, details

def analyze_and_signal():
    all_coins = get_top_volume_coins(TOP_VOLATILE_COINS * 2)
    if not all_coins:
        send_telegram("⚠️ Ошибка Binance API")
        return
    
    filtered = [c for c in all_coins if c['volume'] >= MIN_VOLUME_USDT]
    signals_count = 0
    for coin in filtered[:TOP_VOLATILE_COINS]:
        symbol = coin['symbol']
        closes, highs, lows, volumes = get_klines(symbol, interval='5m', limit=100)
        if len(closes) < 50:
            continue
        if len(closes) >= 2:
            change_5m = (closes[-1]-closes[-2])/closes[-2]*100
            if abs(change_5m) < MIN_CHANGE_5M:
                continue
        
        direction, details = detect_signal_and_levels(closes, highs, lows, volumes)
        if not direction:
            continue
        
        price = details['current_price']
        tp_pct = details['tp_percent']
        sl_pct = details['sl_percent']
        if direction == 'long':
            tp = price * (1 + tp_pct/100)
            sl = price * (1 - sl_pct/100)
            message = f"""
📢 <b>LONG СИГНАЛ ({symbol})</b> — {details['long_votes']}/8 индикаторов ЗА

💰 <b>Вход:</b> ${price:.6f}
🎯 <b>Тейк-профит (динамический):</b> ${tp:.6f} (+{tp_pct}%)
🛑 <b>Стоп-лосс (динамический):</b> ${sl:.6f} (-{sl_pct}%)
⚙️ <b>Плечо:</b> {LEVERAGE}x

📊 <b>Индикаторы:</b>
• {details['descriptions']['rsi']}
• {details['descriptions']['ema']}
• {details['descriptions']['bb']}
• {details['descriptions']['macd']}
• {details['descriptions']['volume']}
• {details['descriptions']['stoch_rsi']}
• {details['descriptions']['adx']}
• {details['descriptions']['vwap']}

🧮 <b>Расчёт TP/SL:</b> {details['tp_sl_explanation']}

💡 <b>Вывод:</b> Консенсус индикаторов — лонг. Уровни адаптированы к волатильности.
⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
        else:  # short
            tp = price * (1 - tp_pct/100)
            sl = price * (1 + sl_pct/100)
            message = f"""
📢 <b>SHORT СИГНАЛ ({symbol})</b> — {details['short_votes']}/8 индикаторов ЗА

💰 <b>Вход:</b> ${price:.6f}
🎯 <b>Тейк-профит (динамический):</b> ${tp:.6f} (падение {tp_pct}%)
🛑 <b>Стоп-лосс (динамический):</b> ${sl:.6f} (рост {sl_pct}%)
⚙️ <b>Плечо:</b> {LEVERAGE}x

📊 <b>Индикаторы:</b>
• {details['descriptions']['rsi']}
• {details['descriptions']['ema']}
• {details['descriptions']['bb']}
• {details['descriptions']['macd']}
• {details['descriptions']['volume']}
• {details['descriptions']['stoch_rsi']}
• {details['descriptions']['adx']}
• {details['descriptions']['vwap']}

🧮 <b>Расчёт TP/SL:</b> {details['tp_sl_explanation']}

💡 <b>Вывод:</b> Консенсус индикаторов — шорт.
⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
        send_telegram(message)
        signals_count += 1
        time.sleep(1)
    
    if signals_count == 0:
        print(f"{datetime.now()} - Сигналов нет (консенсус {MIN_AGREEMENT} из 8 не достигнут).")

# ========== ЗАПУСК ==========
print("Бот с динамическими TP/SL запущен. Проверка каждые 5 минут.")
print(f"Параметры: ATR период {ATR_PERIOD}, множители SL={ATR_STOP_MULT}, TP={ATR_TP_MULT_BASE} (корректируются по ADX и Боллинджеру)")
while True:
    try:
        analyze_and_signal()
        time.sleep(CHECK_INTERVAL)
    except Exception as e:
        print("Ошибка:", e)
        time.sleep(60)