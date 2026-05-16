import requests
import time
import math
from datetime import datetime

TELEGRAM_TOKEN = "8695713035:AAELPJ25J5SMbw2Ed6rEW1fiuAtRZ4L9Abc"
CHAT_ID = "694614387"

MAX_COINS = 200
MAX_24H_VOLUME_USDT = 500_000
CHECK_INTERVAL = 3600  # 1 час

# Ослабленные пороги для теста
RSI_4H_MIN = 40
RSI_1H_MIN = 40
CHANGE_4H_MIN = 0.5
VOLUME_24H_MIN = 100_000

def send_telegram(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try:
        requests.post(url, json={"chat_id": CHAT_ID, "text": text, "parse_mode": "HTML"})
    except:
        pass

# ---------- ПОЛУЧЕНИЕ НИЗКОЛИКВИДНЫХ МОНЕТ (Bybit + резерв) ----------
def get_low_volume_coins():
    # Пробуем Bybit
    try:
        url = "https://api.bybit.com/v5/market/tickers?category=spot"
        r = requests.get(url, timeout=15)
        data = r.json()
        if data.get('retCode') == 0:
            tickers = data['result']['list']
            usdt_pairs = [t for t in tickers if t['symbol'].endswith('USDT')]
            # Сортируем по объёму (turnover24h)
            usdt_pairs.sort(key=lambda x: float(x['turnover24h']))
            coins = []
            for t in usdt_pairs[:MAX_COINS*2]:
                sym = t['symbol'].replace('USDT', '')
                if sym in ['BTC','ETH','USDT','USDC','DAI','BUSD','TUSD']:
                    continue
                vol = float(t['turnover24h'])
                if vol <= MAX_24H_VOLUME_USDT:
                    coins.append(sym)
                    if len(coins) >= MAX_COINS:
                        break
            if coins:
                print(f"Загружено {len(coins)} монет с Bybit")
                return coins
    except Exception as e:
        print(f"Bybit не удался: {e}")

    # Резервный список (известные низколиквидные монеты)
    fallback = ["1000LUNC","LUNA2","USTC","ANC","MIR","BAT","ZRX","REP","SNX","COMP","MKR","YFI","CRV","UNI","SUSHI","CAKE","BAKE","ALPHA","BETA","GALA","CHZ","OGN","STORJ","BLZ","COTI","HOT","IOST","IOTX","KNC","LRC","NKN","NMR","POLS","RARE","REQ","RLC","STMX","SXP","TWT","VIDT","WAN","WAXP","ZEN","ZKS","ENJ","ZIL","KLAY","ONE","ICX","XTZ","ONT","QTUM","WAVES","KSM","RUNE","PEPE","WIF","BONK","FLOKI","NOT","TON","OP","ARB","SUI","APT","INJ","SEI","TIA","PYTH","JUP","ONDO","STRK","ENA","ETHFI"]
    print(f"Использую резервный список из {len(fallback[:MAX_COINS])} монет")
    return fallback[:MAX_COINS]

# ---------- ФУНКЦИИ ДЛЯ ПОЛУЧЕНИЯ ДАННЫХ (Bybit + Binance) ----------
def get_klines(symbol, interval='5', limit=100):
    """interval: '5', '15', '60', '240' (минуты)"""
    url = f"https://api.bybit.com/v5/market/kline?category=spot&symbol={symbol}USDT&interval={interval}&limit={limit}"
    try:
        r = requests.get(url, timeout=8)
        data = r.json()
        if data.get('retCode') == 0 and data.get('result', {}).get('list'):
            klines = data['result']['list']
            closes = [float(k[4]) for k in klines]
            closes.reverse()
            return closes
    except:
        pass
    # Fallback Binance
    try:
        binance_interval = {'5':'5m','15':'15m','60':'1h','240':'4h'}[interval]
        url = f"https://api.binance.com/api/v3/klines?symbol={symbol}USDT&interval={binance_interval}&limit={limit}"
        r = requests.get(url, timeout=8)
        data = r.json()
        if isinstance(data, list) and len(data) > 0:
            return [float(c[4]) for c in data]
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

def get_price_change(symbol, interval):
    closes = get_klines(symbol, interval, 2)
    if len(closes) < 2:
        return None
    return (closes[-1] - closes[-2]) / closes[-2] * 100

def get_24h_stats(symbol):
    # Bybit
    url = f"https://api.bybit.com/v5/market/tickers?category=spot&symbol={symbol}USDT"
    try:
        r = requests.get(url, timeout=5)
        data = r.json()
        if data.get('retCode') == 0 and data['result']['list']:
            ticker = data['result']['list'][0]
            return float(ticker['price24hPcnt']) * 100, float(ticker['turnover24h'])
    except:
        pass
    # Binance fallback
    try:
        url = f"https://api.binance.com/api/v3/ticker/24hr?symbol={symbol}USDT"
        r = requests.get(url, timeout=5)
        data = r.json()
        return float(data['priceChangePercent']), float(data['quoteVolume'])
    except:
        return None, None

def get_funding(symbol):
    try:
        url = f"https://api.bybit.com/v5/market/tickers?category=linear&symbol={symbol}USDT"
        r = requests.get(url, timeout=5)
        data = r.json()
        if data.get('retCode') == 0 and data['result']['list']:
            return float(data['result']['list'][0]['fundingRate']) * 100
    except:
        pass
    return None

def get_realtime_price(symbol):
    url = f"https://api.bybit.com/v5/market/tickers?category=spot&symbol={symbol}USDT"
    try:
        r = requests.get(url, timeout=5)
        data = r.json()
        if data.get('retCode') == 0 and data['result']['list']:
            return float(data['result']['list'][0]['lastPrice'])
    except:
        pass
    return None

def analyze_coin(symbol):
    # RSI на 5m, 15m, 1h, 4h (Bybit интервалы: 5,15,60,240)
    intervals = {'5m': '5', '15m': '15', '1h': '60', '4h': '240'}
    rsis = {}
    for name, intv in intervals.items():
        closes = get_klines(symbol, intv, 50)
        if not closes:
            return None
        rsis[name] = calculate_rsi(closes)
        if rsis[name] is None:
            return None

    change_24h, volume_24h = get_24h_stats(symbol)
    if change_24h is None:
        return None
    change_15m = get_price_change(symbol, '15') or 0
    change_1h = get_price_change(symbol, '60') or 0
    change_4h = get_price_change(symbol, '240') or 0
    funding = get_funding(symbol)

    if (rsis['4h'] >= RSI_4H_MIN and rsis['1h'] >= RSI_1H_MIN and
        change_4h >= CHANGE_4H_MIN and volume_24h >= VOLUME_24H_MIN):
        real_price = get_realtime_price(symbol)
        if real_price is None:
            return None
        reasons = []
        if rsis['4h'] >= RSI_4H_MIN:
            reasons.append(f"RSI 4h={rsis['4h']} (>{RSI_4H_MIN})")
        if rsis['1h'] >= RSI_1H_MIN:
            reasons.append(f"RSI 1h={rsis['1h']} (>{RSI_1H_MIN})")
        if change_4h >= CHANGE_4H_MIN:
            reasons.append(f"рост за 4ч={change_4h:.2f}% (>{CHANGE_4H_MIN}%)")
        if funding is not None and funding > 0:
            reasons.append(f"фандинг={funding:.2f}% (положительный)")
        explanation = " ".join(reasons)

        msg = f"""
🔻 <b>SHORT СИГНАЛ</b> <b>{symbol}</b> | {real_price:.6f}

<b>RSI:</b> 5m {rsis['5m']} | 15m {rsis['15m']} | 1h {rsis['1h']} | 4h {rsis['4h']}
<b>Изменение:</b> 24h {change_24h:+.2f}% | 15m {change_15m:+.2f}% | 1h {change_1h:+.2f}% | 4h {change_4h:+.2f}%
<b>Объём 24h:</b> {volume_24h/1e6:.2f}M
<b>Фандинг:</b> {funding:+.4f}% {'✅' if funding and funding>0 else ''}

💡 <b>Обоснование:</b> {explanation}. Вероятна коррекция вниз.

⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
        return msg
    return None

def scan_market():
    print(f"[{datetime.now()}] Сканирование низколиквидных монет...")
    coins = get_low_volume_coins()
    if not coins:
        send_telegram("⚠️ Не удалось получить список монет")
        return
    print(f"Анализируем {len(coins)} монет...")
    for symbol in coins:
        try:
            msg = analyze_coin(symbol)
            if msg:
                send_telegram(msg)
                time.sleep(2)
        except Exception as e:
            print(f"Ошибка {symbol}: {e}")
        time.sleep(0.2)
    print("Цикл завершён.")

if __name__ == "__main__":
    send_telegram("🚀 Бот (низколиквидные монеты, Bybit) запущен.")
    while True:
        scan_market()
        print(f"Жду {CHECK_INTERVAL} секунд...")
        time.sleep(CHECK_INTERVAL)