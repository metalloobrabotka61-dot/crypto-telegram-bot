import requests
import time
from datetime import datetime

TELEGRAM_TOKEN = "8695713035:AAELPJ25J5SMbw2Ed6rEW1fiuAtRZ4L9Abc"
CHAT_ID = "694614387"

COINS = ["1000LUNC","LUNA2","USTC","ANC","MIR","BAT","ZRX","REP","SNX","COMP","MKR","YFI","CRV","UNI","SUSHI","CAKE","BAKE","ALPHA","BETA","GALA","CHZ","OGN","STORJ","BLZ","COTI","HOT","IOST","IOTX","KNC","LRC","NKN","NMR","POLS","RARE","REQ","RLC","STMX","SXP","TWT","VIDT","WAN","WAXP","ZEN","ZKS","ENJ","ZIL","KLAY","ONE","ICX","XTZ","ONT","QTUM","WAVES","KSM","RUNE","PEPE","WIF","BONK","FLOKI","NOT","TON","OP","ARB","SUI","APT","INJ","SEI","TIA","PYTH","JUP","ONDO","STRK","ENA","ETHFI"]

def send_telegram(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try:
        requests.post(url, json={"chat_id": CHAT_ID, "text": text, "parse_mode": "HTML"})
    except:
        pass

def get_klines(symbol, interval='1h', limit=2):
    url = f"https://api.binance.com/api/v3/klines?symbol={symbol}USDT&interval={interval}&limit={limit}"
    try:
        r = requests.get(url, timeout=10)
        data = r.json()
        if isinstance(data, list) and len(data) > 0:
            return [float(c[4]) for c in data]
    except:
        pass
    return []

def get_price_change(symbol, interval='4h'):
    closes = get_klines(symbol, interval, 2)
    if len(closes) < 2:
        return None
    return (closes[-1] - closes[-2]) / closes[-2] * 100

def get_realtime_price(symbol):
    url = f"https://api.binance.com/api/v3/ticker/price?symbol={symbol}USDT"
    try:
        r = requests.get(url, timeout=5)
        return float(r.json()['price'])
    except:
        return None

def analyze_coin(symbol):
    change = get_price_change(symbol, '4h')
    if change is None:
        return None
    if change > 1.0:   # рост > 1% за 4 часа
        price = get_realtime_price(symbol)
        if price is None:
            return None
        return f"🔻 ТЕСТОВЫЙ SHORT {symbol} | {price:.6f}\nРост за 4ч: {change:.2f}%"
    return None

def scan():
    print(f"[{datetime.now()}] Сканирование...")
    for sym in COINS:
        try:
            sig = analyze_coin(sym)
            if sig:
                send_telegram(sig)
                print(f"✅ {sym}")
                time.sleep(2)
        except Exception as e:
            print(f"Ошибка {sym}: {e}")
        time.sleep(0.2)
    print("Цикл завершён, жду 1 час.")

if __name__ == "__main__":
    send_telegram("🚀 ТЕСТОВЫЙ бот (SHORT по росту > 1% за 4ч) запущен.")
    while True:
        scan()
        time.sleep(3600)