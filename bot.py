import requests
import time
import math
from datetime import datetime

# ========== НАСТРОЙКИ TELEGRAM ==========
TELEGRAM_TOKEN = "8695713035:AAELPJ25J5SMbw2Ed6rEW1fiuAtRZ4L9Abc"
CHAT_ID = "694614387"

# ========== ОСНОВНЫЕ ПАРАМЕТРЫ ==========
CHECK_INTERVAL = 300            # 5 минут между проверками (можно 300 = 5 мин)
TOP_VOLATILE_COINS = 20         # анализировать топ-20 волатильных монет
MIN_VOLUME_USDT = 5_000_000     # минимальный 24h объём $5M
MIN_CHANGE_5M = 0.4             # мин. изменение цены за 5 мин (%)
LEVERAGE = 3                    # плечо (общее для long/short)
TAKE_PROFIT_PERCENT = 0.8       # тейк-профит (%)
STOP_LOSS_PERCENT = 0.6         # стоп-лосс (%)

# ========== НАСТРОЙКИ ИНДИКАТОРОВ ==========
MIN_AGREEMENT = 4               # минимум индикаторов должны показывать одно направление (из 8)

# RSI (14)
RSI_PERIOD = 14
RSI_OVERSOLD = 30
RSI_OVERBOUGHT = 70

# MACD (12, 26, 9)
MACD_FAST = 12
MACD_SLOW = 26
MACD_SIGNAL = 9

# Скользящие средние (EMA 9 и EMA 21)
EMA_SHORT = 9
EMA_LONG = 21

# Полосы Боллинджера (20 периодов, 2 отклонения)
BB_PERIOD = 20
BB_STD = 2

# Объём (всплеск относительно среднего за 20 периодов)
VOLUME_SURGE_FACTOR = 1.5

# Stochastic RSI (14, 14, 1, 3)
STOCH_RSI_PERIOD = 14
STOCH_RSI_K = 14
STOCH_RSI_D = 3

# ADX (14 периодов) — сила тренда >25 считается сильным трендом
ADX_PERIOD = 14
ADX_THRESHOLD = 25

# VWAP — внутридневной, используем последние 20 свечей для расчёта
VWAP_PERIOD = 20
# =========================================

def send_telegram(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try:
        requests.post(url, json={"chat_id": CHAT_ID, "text": text, "parse_mode": "HTML"})
    except:
        pass

def get_top_volume_coins(limit=50):
    url = "https://api.binance.com/api/v3/ticker/24hr"
    try:
        data = requests.get(url).json()
        usdt_pairs = [item for item in data if item['symbol'].endswith('USDT')]
        usdt_pairs.sort(key=lambda x: float(x['quoteVolume']), reverse=True)
        top_coins = []
        for pair in usdt_pairs[:limit]:
            symbol = pair['symbol'].replace('USDT', '')
            top_coins.append({
                'symbol': symbol,
                'volume': float(pair['quoteVolume']),
                'change24h': float(pair['priceChangePercent'])
            })
        return top_coins
    except Exception as e:
        print("Ошибка получения списка монет:", e)
        return []

def get_klines(symbol, interval='5m', limit=100):
    url = f"https://api.binance.com/api/v3/klines?symbol={symbol}USDT&interval={interval}&limit={limit}"
    try:
        data = requests.get(url).json()
        closes = [float(candle[4]) for candle in data]
        highs = [float(candle[2]) for candle in data]
        lows = [float(candle[3]) for candle in data]
        volumes = [float(candle[5]) for candle in data]
        return closes, highs, lows, volumes
    except:
        return [], [], [], []

def calculate_rsi(closes, period=14):
    if len(closes) < period + 1:
        return None
    gains, losses = [], []
    for i in range(1, len(closes)):
        diff = closes[i] - closes[i-1]
        if diff >= 0:
            gains.append(diff)
            losses.append(0)
        else:
            gains.append(0)
            losses.append(abs(diff))
    avg_gain = sum(gains[-period:]) / period
    avg_loss = sum(losses[-period:]) / period
    if avg_loss == 0:
        return 100
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return round(rsi, 2)

def calculate_ema(closes, period):
    if len(closes) < period:
        return None
    multiplier = 2 / (period + 1)
    ema = closes[0]
    for price in closes[1:]:
        ema = (price - ema) * multiplier + ema
    return ema

def calculate_bollinger_bands(closes, period=20, std_dev=2):
    if len(closes) < period:
        return None, None, None
    last_prices = closes[-period:]
    sma = sum(last_prices) / period
    variance = sum((p - sma) ** 2 for p in last_prices) / period
    std = math.sqrt(variance)
    upper = sma + std_dev * std
    lower = sma - std_dev * std
    return upper, lower, sma

def calculate_macd_signal(closes, fast=12, slow=26):
    """Простая разница EMA12 и EMA26, положительная -> бычий тренд"""
    ema_fast = calculate_ema(closes, fast)
    ema_slow = calculate_ema(closes, slow)
    if ema_fast is None or ema_slow is None:
        return None
    return ema_fast - ema_slow

def calculate_stoch_rsi(closes, period=14, k_period=14, d_period=3):
    """Возвращает текущее значение Stochastic RSI (%K) и %D"""
    if len(closes) < period + k_period + d_period:
        return None, None
    # RSI массив
    rsi_values = []
    for i in range(period, len(closes)):
        rsi = calculate_rsi(closes[i-period+1:i+1], period)
        if rsi is not None:
            rsi_values.append(rsi)
    if len(rsi_values) < k_period:
        return None, None
    # Stochastic RSI = (текущий RSI - min(RSI за k_period)) / (max - min)
    current_rsi = rsi_values[-1]
    min_rsi = min(rsi_values[-k_period:])
    max_rsi = max(rsi_values[-k_period:])
    if max_rsi == min_rsi:
        stoch_k = 50
    else:
        stoch_k = (current_rsi - min_rsi) / (max_rsi - min_rsi) * 100
    # %D — скользящая средняя от %K за d_period
    if len(rsi_values) >= k_period + d_period:
        k_values = []
        for i in range(len(rsi_values)-d_period, len(rsi_values)):
            mn = min(rsi_values[i-k_period+1:i+1])
            mx = max(rsi_values[i-k_period+1:i+1])
            if mx == mn:
                k = 50
            else:
                k = (rsi_values[i] - mn) / (mx - mn) * 100
            k_values.append(k)
        stoch_d = sum(k_values) / d_period
    else:
        stoch_d = stoch_k
    return round(stoch_k, 1), round(stoch_d, 1)

def calculate_adx(highs, lows, closes, period=14):
    """Индекс направленного движения ADX (сила тренда)"""
    if len(closes) < period + 1:
        return None
    tr = []
    plus_dm = []
    minus_dm = []
    for i in range(1, len(closes)):
        high_diff = highs[i] - highs[i-1]
        low_diff = lows[i-1] - lows[i]
        true_range = max(highs[i] - lows[i], abs(highs[i] - closes[i-1]), abs(lows[i] - closes[i-1]))
        tr.append(true_range)
        if high_diff > low_diff and high_diff > 0:
            plus_dm.append(high_diff)
        else:
            plus_dm.append(0)
        if low_diff > high_diff and low_diff > 0:
            minus_dm.append(low_diff)
        else:
            minus_dm.append(0)
    if len(tr) < period:
        return None
    avg_tr = sum(tr[-period:]) / period
    avg_plus = sum(plus_dm[-period:]) / period
    avg_minus = sum(minus_dm[-period:]) / period
    if avg_tr == 0:
        return None
    plus_di = (avg_plus / avg_tr) * 100
    minus_di = (avg_minus / avg_tr) * 100
    dx = abs(plus_di - minus_di) / (plus_di + minus_di) * 100 if (plus_di + minus_di) != 0 else 0
    adx = dx  # упрощённо, в реальности сглаживают, но для сигнала достаточно
    return round(adx, 1)

def calculate_vwap(closes, volumes, period=20):
    """Цена, взвешенная по объёму, за последние period свечей"""
    if len(closes) < period or len(volumes) < period:
        return None
    total_value = 0
    total_volume = 0
    for i in range(-period, 0):
        total_value += closes[i] * volumes[i]
        total_volume += volumes[i]
    if total_volume == 0:
        return None
    return total_value / total_volume

def detect_signal(closes, highs, lows, volumes):
    """Возвращает 'long', 'short' или None, и словарь с показаниями индикаторов и описаниями"""
    if len(closes) < max(RSI_PERIOD, EMA_LONG, BB_PERIOD, MACD_SLOW, ADX_PERIOD, 30):
        return None, {}
    
    current_price = closes[-1]
    indicators = {}
    descriptions = {}
    
    # 1. RSI
    rsi = calculate_rsi(closes, RSI_PERIOD)
    rsi_signal = None
    if rsi is not None:
        if rsi < RSI_OVERSOLD:
            rsi_signal = 'long'
            desc = f"RSI = {rsi} (<{RSI_OVERSOLD}) – актив перепродан, ожидаем рост"
        elif rsi > RSI_OVERBOUGHT:
            rsi_signal = 'short'
            desc = f"RSI = {rsi} (>{RSI_OVERBOUGHT}) – актив перекуплен, ожидаем коррекцию"
        else:
            desc = f"RSI = {rsi} (нейтрально)"
        indicators['rsi'] = rsi_signal
        descriptions['rsi'] = desc
    
    # 2. EMA пересечение
    ema_short = calculate_ema(closes, EMA_SHORT)
    ema_long = calculate_ema(closes, EMA_LONG)
    ema_signal = None
    if ema_short is not None and ema_long is not None:
        if ema_short > ema_long:
            ema_signal = 'long'
            desc = f"EMA{EMA_SHORT} ({ema_short:.2f}) > EMA{EMA_LONG} ({ema_long:.2f}) – восходящий тренд"
        else:
            ema_signal = 'short'
            desc = f"EMA{EMA_SHORT} ({ema_short:.2f}) < EMA{EMA_LONG} ({ema_long:.2f}) – нисходящий тренд"
        indicators['ema'] = ema_signal
        descriptions['ema'] = desc
    
    # 3. Боллинджер
    upper, lower, _ = calculate_bollinger_bands(closes, BB_PERIOD, BB_STD)
    bb_signal = None
    if upper and lower:
        if current_price < lower:
            bb_signal = 'long'
            desc = f"Цена ниже нижней полосы Боллинджера ({lower:.2f}) – вероятен отскок вверх"
        elif current_price > upper:
            bb_signal = 'short'
            desc = f"Цена выше верхней полосы Боллинджера ({upper:.2f}) – вероятна коррекция вниз"
        else:
            desc = f"Цена внутри полос Боллинджера ({lower:.2f} – {upper:.2f}) – нейтрально"
        indicators['bb'] = bb_signal
        descriptions['bb'] = desc
    
    # 4. MACD (разница EMA12 и EMA26)
    macd_diff = calculate_macd_signal(closes, MACD_FAST, MACD_SLOW)
    macd_signal = None
    if macd_diff is not None:
        if macd_diff > 0:
            macd_signal = 'long'
            desc = f"MACD положительный ({macd_diff:.2f}) – бычий импульс"
        else:
            macd_signal = 'short'
            desc = f"MACD отрицательный ({macd_diff:.2f}) – медвежий импульс"
        indicators['macd'] = macd_signal
        descriptions['macd'] = desc
    
    # 5. Объём
    avg_volume = sum(volumes[-20:-1]) / 19 if len(volumes) >= 20 else None
    volume_signal = None
    if avg_volume and volumes[-1] > avg_volume * VOLUME_SURGE_FACTOR:
        if len(closes) >= 2 and closes[-1] > closes[-2]:
            volume_signal = 'long'
            desc = f"Всплеск объёма (x{volumes[-1]/avg_volume:.1f}) на растущей цене – подтверждение покупок"
        elif len(closes) >= 2 and closes[-1] < closes[-2]:
            volume_signal = 'short'
            desc = f"Всплеск объёма (x{volumes[-1]/avg_volume:.1f}) на падающей цене – подтверждение продаж"
        else:
            desc = "Объём высокий, но цена не меняется"
    else:
        desc = "Объём в норме"
    indicators['volume'] = volume_signal
    descriptions['volume'] = desc
    
    # 6. Stochastic RSI
    stoch_k, stoch_d = calculate_stoch_rsi(closes, STOCH_RSI_PERIOD, STOCH_RSI_K, STOCH_RSI_D)
    stoch_signal = None
    if stoch_k is not None:
        if stoch_k < 20 and stoch_d < 20:
            stoch_signal = 'long'
            desc = f"StochRSI %K={stoch_k} (<20) – зона перепроданности, ждём отскока"
        elif stoch_k > 80 and stoch_d > 80:
            stoch_signal = 'short'
            desc = f"StochRSI %K={stoch_k} (>80) – зона перекупленности, ждём падения"
        else:
            desc = f"StochRSI %K={stoch_k} (нейтрально)"
        indicators['stoch_rsi'] = stoch_signal
        descriptions['stoch_rsi'] = desc
    
    # 7. ADX (сила тренда)
    adx = calculate_adx(highs, lows, closes, ADX_PERIOD)
    adx_signal = None
    if adx is not None and adx > ADX_THRESHOLD:
        # Если ADX сильный, смотрим направление EMA
        if ema_signal == 'long':
            adx_signal = 'long'
            desc = f"ADX = {adx} (>{ADX_THRESHOLD}) – сильный тренд ВВЕРХ"
        elif ema_signal == 'short':
            adx_signal = 'short'
            desc = f"ADX = {adx} (>{ADX_THRESHOLD}) – сильный тренд ВНИЗ"
        else:
            desc = f"ADX = {adx} (сильный тренд, но направление не определено)"
    else:
        desc = f"ADX = {adx if adx else '?'} (слабый тренд, флет)"
    indicators['adx'] = adx_signal
    descriptions['adx'] = desc
    
    # 8. VWAP
    vwap = calculate_vwap(closes, volumes, VWAP_PERIOD)
    vwap_signal = None
    if vwap is not None:
        if current_price > vwap:
            vwap_signal = 'long'
            desc = f"Цена выше VWAP ({vwap:.2f}) – бычье внутридневное смещение"
        else:
            vwap_signal = 'short'
            desc = f"Цена ниже VWAP ({vwap:.2f}) – медвежье внутридневное смещение"
        indicators['vwap'] = vwap_signal
        descriptions['vwap'] = desc
    
    # Подсчёт голосов за long/short
    all_signals = [indicators.get(k) for k in ['rsi','ema','bb','macd','volume','stoch_rsi','adx','vwap'] if indicators.get(k) is not None]
    long_votes = all_signals.count('long')
    short_votes = all_signals.count('short')
    
    direction = None
    if long_votes >= MIN_AGREEMENT:
        direction = 'long'
    elif short_votes >= MIN_AGREEMENT:
        direction = 'short'
    
    details = {
        'long_votes': long_votes,
        'short_votes': short_votes,
        'indicators': indicators,
        'descriptions': descriptions,
        'current_price': current_price
    }
    return direction, details

def analyze_and_signal():
    all_coins = get_top_volume_coins(TOP_VOLATILE_COINS * 2)
    if not all_coins:
        send_telegram("⚠️ Не удалось получить монеты с Binance")
        return
    
    filtered = [c for c in all_coins if c['volume'] >= MIN_VOLUME_USDT]
    signals_count = 0
    for coin in filtered[:TOP_VOLATILE_COINS]:
        symbol = coin['symbol']
        closes, highs, lows, volumes = get_klines(symbol, interval='5m', limit=100)
        if len(closes) < 50:
            continue
        
        # Проверка минимальной волатильности за 5 минут
        if len(closes) >= 2:
            change_5m = (closes[-1] - closes[-2]) / closes[-2] * 100
            if abs(change_5m) < MIN_CHANGE_5M:
                continue
        
        direction, details = detect_signal(closes, highs, lows, volumes)
        if not direction:
            continue
        
        current_price = details['current_price']
        if direction == 'long':
            tp = current_price * (1 + TAKE_PROFIT_PERCENT / 100)
            sl = current_price * (1 - STOP_LOSS_PERCENT / 100)
            # Формируем описание индикаторов
            ind_list = []
            for k, desc in details['descriptions'].items():
                ind_list.append(f"• {desc}")
            ind_text = "\n".join(ind_list)
            message = f"""
📢 <b>LONG СИГНАЛ ({symbol})</b> — {details['long_votes']}/8 индикаторов ЗА

💰 <b>Вход:</b> ${current_price:.6f}
🎯 <b>TP:</b> ${tp:.6f} (+{TAKE_PROFIT_PERCENT}%)
🛑 <b>SL:</b> ${sl:.6f} (-{STOP_LOSS_PERCENT}%)
⚙️ <b>Плечо:</b> {LEVERAGE}x

📊 <b>Индикаторы:</b>
{ind_text}

💡 <b>Вывод:</b> Большинство индикаторов указывают на рост. Рекомендуется лонг.
⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
            send_telegram(message)
            signals_count += 1
            time.sleep(1)
        
        elif direction == 'short':
            tp = current_price * (1 - TAKE_PROFIT_PERCENT / 100)
            sl = current_price * (1 + STOP_LOSS_PERCENT / 100)
            ind_list = []
            for k, desc in details['descriptions'].items():
                ind_list.append(f"• {desc}")
            ind_text = "\n".join(ind_list)
            message = f"""
📢 <b>SHORT СИГНАЛ ({symbol})</b> — {details['short_votes']}/8 индикаторов ЗА

💰 <b>Вход:</b> ${current_price:.6f}
🎯 <b>TP:</b> ${tp:.6f} (-{TAKE_PROFIT_PERCENT}%)
🛑 <b>SL:</b> ${sl:.6f} (+{STOP_LOSS_PERCENT}%)
⚙️ <b>Плечо:</b> {LEVERAGE}x

📊 <b>Индикаторы:</b>
{ind_text}

💡 <b>Вывод:</b> Большинство индикаторов указывают на падение. Рекомендуется шорт.
⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
            send_telegram(message)
            signals_count += 1
            time.sleep(1)
    
    if signals_count == 0:
        print(f"{datetime.now()} - Сигналов нет (консенсус {MIN_AGREEMENT} из 8 не достигнут).")

# ========== ЗАПУСК ==========
print("Мультииндикаторный бот (8 индикаторов) запущен. Проверка каждые 5 минут.")
print(f"Параметры: MIN_AGREEMENT={MIN_AGREEMENT}, TP {TAKE_PROFIT_PERCENT}%, SL {STOP_LOSS_PERCENT}%, плечо {LEVERAGE}x")
print(f"Индикаторы: RSI, EMA, Боллинджер, MACD, Объём, StochRSI, ADX, VWAP")
while True:
    try:
        analyze_and_signal()
        time.sleep(CHECK_INTERVAL)
    except Exception as e:
        print("Ошибка:", e)
        time.sleep(60)