import requests
import time
import math
from datetime import datetime

TELEGRAM_TOKEN = "8695713035:AAELPJ25J5SMbw2Ed6rEW1fiuAtRZ4L9Abc"
CHAT_ID = "694614387"

# ========== ОСЛАБЛЕННЫЕ НАСТРОЙКИ (для появления сигналов) ==========
MAX_PAIRS = 200
CHECK_INTERVAL = 1800
LOOKBACK_CANDLES = 500
MIN_TOUCHES = 1                     # было 2, теперь достаточно одного касания
LEVERAGE = 20
RISK_PERCENT = 1.0
TP_PERCENT = 2.0
SL_OFFSET_PERCENT = 0.5
LIMIT_OFFSET_PERCENT = 0.2
TIMEFRAMES = ['5', '15', '30', '60', '240']
DISTANCE_TO_RESISTANCE_PERCENT = 5.0   # было 2%, теперь 5% – шире
RSI_MIN_FOR_SHORT = 20                # было 35, теперь RSI может быть ниже 20
MAX_PRICE_CHANGE_PERCENT = 1.0        # было 0.5%, теперь допускаем большее изменение
# =================================

def send_telegram(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try:
        requests.post(url, json={"chat_id": CHAT_ID, "text": text, "parse_mode": "HTML"})
    except:
        pass

def get_realtime_price(symbol):
    # Binance
    try:
        url = f"https://api.binance.com/api/v3/ticker/price?symbol={symbol}USDT"
        r = requests.get(url, timeout=5)
        if r.status_code == 200:
            return float(r.json()['price'])
    except:
        pass
    # KuCoin
    try:
        url = f"https://api.kucoin.com/api/v1/market/orderbook/level1?symbol={symbol}-USDT"
        r = requests.get(url, timeout=5)
        data = r.json()
        if data['code'] == '200000':
            return float(data['data']['price'])
    except:
        pass
    return None

def get_top_coins():
    # Пробуем KuCoin
    try:
        url = "https://api.kucoin.com/api/v1/symbols"
        r = requests.get(url, timeout=10)
        data = r.json()
        if data['code'] == '200000':
            symbols = [s['symbol'] for s in data['data'] if s['symbol'].endswith('-USDT')]
            tickers_url = "https://api.kucoin.com/api/v1/market/allTickers"
            tickers_r = requests.get(tickers_url, timeout=10)
            tickers_data = tickers_r.json()
            if tickers_data['code'] == '200000':
                tickers = {t['symbol']: float(t['volValue']) for t in tickers_data['data']['ticker'] if 'volValue' in t}
                sorted_symbols = sorted(symbols, key=lambda s: tickers.get(s, 0), reverse=True)
                coins = []
                for sym in sorted_symbols[:MAX_PAIRS]:
                    base = sym.replace('-USDT', '')
                    if base in ['BTC','ETH','USDT','USDC','DAI','BUSD','TUSD']:
                        continue
                    vol = tickers.get(sym, 0)
                    if vol >= 100_000:   # снизили минимальный объём
                        coins.append({'symbol': base, 'volume': vol})
                if coins:
                    print(f"Список с KuCoin: {len(coins)}")
                    return coins
    except Exception as e:
        print(f"KuCoin список не удался: {e}")
    # Резервный список
    fallback = ["SOL","XRP","ADA","DOGE","MATIC","DOT","AVAX","LINK","LTC","NEAR","ATOM","FIL","VET","ALGO","ICP","FTM","SAND","MANA","ENJ","CHZ","AAVE","EOS","TRX","XLM","NEO","PEPE","WIF","FLOKI","TON","OP","ARB","SUI","APT","INJ","SEI","TIA","ONDO","STRK","ETHFI"]
    return [{'symbol': s, 'volume': 0} for s in fallback[:MAX_PAIRS]]

def get_klines(symbol, interval_minutes=5, limit=500):
    # KuCoin
    try:
        url = f"https://api.kucoin.com/api/v1/market/candles?type={interval_minutes}min&symbol={symbol}-USDT&limit={limit}"
        r = requests.get(url, timeout=8)
        data = r.json()
        if data['code'] == '200000' and data['data']:
            candles = data['data']
            closes = [float(c[2]) for c in candles]
            highs = [float(c[1]) for c in candles]
            lows = [float(c[0]) for c in candles]
            volumes = [float(c[5]) for c in candles]
            return closes, highs, lows, volumes
    except:
        pass
    # Binance fallback
    try:
        url = f"https://api.binance.com/api/v3/klines?symbol={symbol}USDT&interval={interval_minutes}m&limit={limit}"
        r = requests.get(url, timeout=8)
        data = r.json()
        if isinstance(data, list) and len(data) > 0:
            closes = [float(c[4]) for c in data]
            highs = [float(c[2]) for c in data]
            lows = [float(c[3]) for c in data]
            volumes = [float(c[5]) for c in data]
            return closes, highs, lows, volumes
    except:
        pass
    return [], [], [], []

def find_resistance(highs, lows, current_price, lookback=200):
    highs_seg = highs[-lookback:]
    resistances = []
    for i in range(2, len(highs_seg)-2):
        if highs_seg[i] >= highs_seg[i-1] and highs_seg[i] >= highs_seg[i-2] and \
           highs_seg[i] >= highs_seg[i+1] and highs_seg[i] >= highs_seg[i+2]:
            resistances.append(highs_seg[i])
    resistances = sorted(set(resistances))
    nearest = min([r for r in resistances if r > current_price], default=None)
    return nearest

def calculate_fibo_levels(highs, lows, closes):
    if len(closes) < 100:
        return {}
    max_price = max(closes[-100:])
    min_price = min(closes[-100:])
    idx_max = len(closes) - 1 - closes[::-1].index(max_price)
    idx_min = len(closes) - 1 - closes[::-1].index(min_price)
    if idx_max > idx_min:
        start, end = min_price, max_price
    else:
        start, end = max_price, min_price
    diff = end - start
    levels = {}
    for fib in [0.236, 0.382, 0.5, 0.618, 0.786]:
        levels[fib] = start + diff * fib
    return levels

def count_touches(symbol, level_price, interval_min, lookback_days=2):
    intervals = {'5': 12*24, '15': 4*24, '30': 2*24, '60': 24, '240': 6}
    limit = intervals.get(str(interval_min), 100) * lookback_days
    _, highs, lows, _ = get_klines(symbol, interval_minutes=interval_min, limit=limit)
    if not highs:
        return 0
    touches = 0
    for i in range(len(highs)):
        if abs(highs[i] - level_price) / level_price * 100 < 0.5:  # увеличил допуск до 0.5%
            touches += 1
        if abs(lows[i] - level_price) / level_price * 100 < 0.5:
            touches += 1
    return touches

def get_rsi(symbol, interval_min, period=14):
    closes, _, _, _ = get_klines(symbol, interval_minutes=interval_min, limit=period+10)
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

def get_funding(symbol):
    try:
        url = f"https://fapi.binance.com/fapi/v1/premiumIndex?symbol={symbol}USDT"
        r = requests.get(url, timeout=5)
        return float(r.json().get('lastFundingRate', 0)) * 100
    except:
        return None

def get_24h_volume(symbol):
    try:
        url = f"https://api.binance.com/api/v3/ticker/24hr?symbol={symbol}USDT"
        r = requests.get(url, timeout=5)
        return float(r.json().get('quoteVolume', 0))
    except:
        return 0

def analyze_coin(symbol):
    closes, highs, lows, _ = get_klines(symbol, 5, LOOKBACK_CANDLES)
    if len(closes) < 300:
        return None
    current_price_candle = closes[-1]

    resistance = find_resistance(highs, lows, current_price_candle, lookback=200)
    if not resistance:
        return None
    dist = (resistance - current_price_candle) / current_price_candle * 100
    if dist > DISTANCE_TO_RESISTANCE_PERCENT:
        return None

    fibo = calculate_fibo_levels(highs, lows, closes)
    fibo_level = None
    for f, val in fibo.items():
        if abs(resistance - val) / resistance * 100 < 1.0 and (f == 0.236 or f == 0.382):
            fibo_level = f
            break

    # Подтверждение на таймфреймах (теперь достаточно 1 таймфрейма)
    confirmed_tfs = []
    for tf in TIMEFRAMES:
        touches = count_touches(symbol, resistance, int(tf), lookback_days=2)
        if touches >= MIN_TOUCHES:
            confirmed_tfs.append(f"{tf}m")
    if len(confirmed_tfs) < 1:   # было 2, теперь 1
        return None

    rsi5 = get_rsi(symbol, 5)
    rsi60 = get_rsi(symbol, 60)
    if rsi5 is None or rsi60 is None or rsi5 < RSI_MIN_FOR_SHORT:
        return None

    volume_24h = get_24h_volume(symbol)
    volume_status = "🟢" if volume_24h > 50_000_000 else "🟡" if volume_24h > 10_000_000 else "🔴"
    funding = get_funding(symbol)
    funding_str = f"{funding:+.4f}%" if funding is not None else "нет данных"
    funding_ok = (funding and funding > 0)

    real_price = get_realtime_price(symbol)
    if real_price is None:
        return None
    real_dist = (resistance - real_price) / real_price * 100
    if real_dist > DISTANCE_TO_RESISTANCE_PERCENT:
        return None
    if abs(real_price - current_price_candle) / current_price_candle * 100 > MAX_PRICE_CHANGE_PERCENT:
        return None

    entry_price = real_price
    limit_entry = resistance * (1 - LIMIT_OFFSET_PERCENT / 100)
    tp1 = entry_price * (1 - TP_PERCENT / 100)
    sl_price = resistance * (1 + SL_OFFSET_PERCENT / 100)
    sl_percent = (sl_price - entry_price) / entry_price * 100
    risk_to_deposit = sl_percent * LEVERAGE * (RISK_PERCENT / 100)

    msg = f"""
🔻 <b>SHORT СИГНАЛ</b> <b>{symbol}</b> | {entry_price:.4f}

<b>RSI:</b> 5m {rsi5} | 1h {rsi60}
<b>Объём 24h:</b> {volume_24h/1e6:.2f}M {volume_status}
<b>Фандинг:</b> {funding_str} {'✅' if funding_ok else ''}

📍 Уровень: {resistance:.6f} (подтверждён на {len(confirmed_tfs)} ТФ)
💰 Вход: лимитный {limit_entry:.6f} (текущая {entry_price:.6f})
🎯 TP: {tp1:.6f} (-{TP_PERCENT}%)
🛑 SL: {sl_price:.6f} (+{sl_percent:.2f}%)
⚙️ Риск: ~{risk_to_deposit:.2f}% депозита (плечо {LEVERAGE}x)

⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
    return msg

def main():
    send_telegram("🚀 Бот 1 (SHORT, уровни) – ослабленные фильтры запущен.")
    print("Бот запущен. Анализ каждые 30 минут.")
    while True:
        coins = get_top_coins()
        if not coins:
            print("Нет монет, повтор через 60 сек")
            time.sleep(60)
            continue
        print(f"Начинаю анализ {len(coins)} монет...")
        for coin in coins:
            try:
                signal = analyze_coin(coin['symbol'])
                if signal:
                    send_telegram(signal)
                    time.sleep(2)
            except Exception as e:
                print(f"Ошибка {coin['symbol']}: {e}")
            time.sleep(0.3)
        print(f"{datetime.now()} - цикл завершён, жду {CHECK_INTERVAL} сек.")
        time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    main()