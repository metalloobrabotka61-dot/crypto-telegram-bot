import requests
import time
import math
from datetime import datetime

# ========== НАСТРОЙКИ ==========
TELEGRAM_TOKEN = "8695713035:AAELPJ25J5SMbw2Ed6rEW1fiuAtRZ4L9Abc"
CHAT_ID = "694614387"

MAX_COINS = 500
MIN_24H_VOLUME_USDT = 500_000
CHECK_INTERVAL = 3600
TIMEFRAMES_RSI = ['5m', '15m', '1h', '4h']

# Пороги для сигнала
RSI_4H_MIN = 70
RSI_1H_MIN = 70
CHANGE_4H_MIN = 2.0
FUNDING_MIN = 0.0
VOLUME_24H_MIN = 10_000_000
# =================================

def send_telegram(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try:
        requests.post(url, json={"chat_id": CHAT_ID, "text": text, "parse_mode": "HTML"})
    except:
        pass

# ---------- ПОЛУЧЕНИЕ СПИСКА 500 МОНЕТ ----------
def get_top_500_coins():
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
                for sym in sorted_symbols[:MAX_COINS]:
                    base = sym.replace('-USDT', '')
                    if base in ['BTC','ETH','USDT','USDC','DAI','BUSD','TUSD']:
                        continue
                    vol = tickers.get(sym, 0)
                    if vol >= MIN_24H_VOLUME_USDT:
                        coins.append({'symbol': base, 'volume': vol})
                if coins:
                    print(f"Загружено {len(coins)} монет с KuCoin")
                    return coins
    except Exception as e:
        print(f"KuCoin не удался: {e}")

    fallback = ["SOL","XRP","ADA","DOGE","MATIC","DOT","AVAX","LINK","LTC","NEAR","ATOM","FIL","ALGO","VET","ICP","EGLD","THETA","FTM","SAND","MANA","AXS","ENJ","ZIL","KLAY","CHZ","ONE","ICX","XTZ","AAVE","BCH","EOS","TRX","XLM","ZEC","DASH","NEO","ONT","QTUM","WAVES","KSM","RUNE","PEPE","WIF","BONK","FLOKI","NOT","TON","OP","ARB","SUI","APT","INJ","SEI","TIA","PYTH","JUP","ONDO","STRK","ENA","ETHFI","1000LUNC","LUNA2","USTC","ANC","MIR","BAT","ZRX","REP","SNX","COMP","MKR","YFI","CRV","UNI","SUSHI","CAKE","BAKE","ALPHA","BETA","GALA","CHZ","OGN","STORJ","BLZ","COTI","HOT","IOST","IOTX","KNC","LRC","NKN","NMR","POLS","RARE","REQ","RLC","STMX","SXP","TWT","VIDT","WAN","WAXP","ZEN","ZKS"]
    coins = [{'symbol': s, 'volume': 0} for s in fallback[:MAX_COINS]]
    print(f"Использую резервный список из {len(coins)} монет")
    return coins

# ---------- СВЕЧИ ----------
def get_klines(symbol, interval='5m', limit=100):
    url = f"https://api.binance.com/api/v3/klines?symbol={symbol}USDT&interval={interval}&limit={limit}"
    try:
        r = requests.get(url, timeout=8)
        data = r.json()
        if isinstance(data, list) and len(data) > 0:
            return [float(c[4]) for c in data]
    except:
        pass
    try:
        url = f"https://api.kucoin.com/api/v1/market/candles?type={interval}&symbol={symbol}-USDT&limit={limit}"
        r = requests.get(url, timeout=8)
        data = r.json()
        if data['code'] == '200000' and data['data']:
            return [float(c[2]) for c in data['data']]
    except:
        pass
    return []

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
    return round(100 - 100/(1+avg_gain/avg_loss), 2)

def get_price_change(symbol, interval, back_minutes):
    closes = get_klines(symbol, interval, 2)
    if len(closes) < 2:
        return None
    current = closes[-1]
    prev = closes[-2]
    return (current - prev) / prev * 100

def get_24h_stats(symbol):
    url = f"https://api.binance.com/api/v3/ticker/24hr?symbol={symbol}USDT"
    try:
        r = requests.get(url, timeout=5)
        data = r.json()
        return float(data['priceChangePercent']), float(data['quoteVolume'])
    except:
        return None, None

def get_funding(symbol):
    try:
        url = f"https://fapi.binance.com/fapi/v1/premiumIndex?symbol={symbol}USDT"
        r = requests.get(url, timeout=5)
        return float(r.json().get('lastFundingRate', 0)) * 100
    except:
        return None

def analyze_coin(symbol):
    # Цена
    url_price = f"https://api.binance.com/api/v3/ticker/price?symbol={symbol}USDT"
    try:
        r = requests.get(url_price, timeout=5)
        price = float(r.json()['price'])
    except:
        return None

    # RSI
    rsis = {}
    for tf in TIMEFRAMES_RSI:
        closes = get_klines(symbol, tf, 50)
        rsis[tf] = calculate_rsi(closes)
        if rsis[tf] is None:
            return None

    # Изменения
    change_24h, volume_24h = get_24h_stats(symbol)
    if change_24h is None:
        return None
    change_15m = get_price_change(symbol, '15m', 15) or 0
    change_1h = get_price_change(symbol, '1h', 60) or 0
    change_4h = get_price_change(symbol, '4h', 240) or 0
    funding = get_funding(symbol)

    # Проверка условий
    cond_rsi_4h = rsis['4h'] >= RSI_4H_MIN
    cond_rsi_1h = rsis['1h'] >= RSI_1H_MIN
    cond_change_4h = change_4h >= CHANGE_4H_MIN
    cond_funding = funding is not None and funding >= FUNDING_MIN
    cond_volume = volume_24h >= VOLUME_24H_MIN

    if cond_rsi_4h and cond_rsi_1h and cond_change_4h and cond_funding and cond_volume:
        # Формируем пояснение
        reasons = []
        if cond_rsi_4h:
            reasons.append(f"RSI 4h = {rsis['4h']:.2f} (выше {RSI_4H_MIN}) – сильная перекупленность на старшем таймфрейме")
        if cond_rsi_1h:
            reasons.append(f"RSI 1h = {rsis['1h']:.2f} (выше {RSI_1H_MIN}) – подтверждение перекупленности")
        if cond_change_4h:
            reasons.append(f"рост цены за 4 часа = {change_4h:.2f}% (выше {CHANGE_4H_MIN}%) – импульс вверх исчерпан, возможен откат")
        if cond_funding:
            reasons.append(f"фандинг = {funding:+.2f}% (положительный) – лонгисты платят шортистам, давление продавцов растёт")
        if cond_volume:
            reasons.append(f"объём 24ч = {volume_24h/1e6:.2f}M USDT – высокая ликвидность, движение будет резким")
        explanation = " ".join(reasons) + ". Совокупность факторов указывает на высокую вероятность коррекции вниз."

        msg = f"""
🔻 <b>SHORT СИГНАЛ</b> <b>{symbol}</b> | {price:.4f}

<b>RSI:</b> 5m {rsis['5m']} | 15m {rsis['15m']} | 1h {rsis['1h']} | 4h {rsis['4h']}
<b>Изменение:</b> 24h {change_24h:+.2f}% | 15m {change_15m:+.2f}% | 1h {change_1h:+.2f}% | 4h {change_4h:+.2f}%
<b>Объём 24h:</b> {volume_24h/1e6:.2f}M
<b>Фандинг:</b> {funding:+.4f}% ✅

💡 <b>Логическое обоснование:</b> {explanation}

⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
        return msg
    return None

def main():
    send_telegram("🚀 Бот 2 (SHORT, 500 монет с пояснениями) запущен. Анализ каждые 60 минут.")
    print("Загружаю список монет...")
    coins = get_top_500_coins()
    print(f"Загружено {len(coins)} монет")
    while True:
        signals = []
        for idx, coin in enumerate(coins):
            symbol = coin['symbol']
            try:
                sig = analyze_coin(symbol)
                if sig:
                    signals.append(sig)
            except Exception as e:
                print(f"Ошибка {symbol}: {e}")
            time.sleep(0.2)
            if idx % 50 == 0:
                print(f"Обработано {idx}/{len(coins)} монет")
        for sig in signals:
            send_telegram(sig)
            time.sleep(2)
        print(f"{datetime.now()} - цикл завершён, жду {CHECK_INTERVAL} сек.")
        time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    main()