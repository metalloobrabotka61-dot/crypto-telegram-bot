import requests
import time
from datetime import datetime

TELEGRAM_TOKEN = "8695713035:AAELPJ25J5SMbw2Ed6rEW1fiuAtRZ4L9Abc"
CHAT_ID = "694614387"

# Список низколиквидных монет (можно ваш)
COINS = ["1000LUNC","LUNA2","USTC","ANC","MIR","BAT","ZRX","REP","SNX","COMP","MKR","YFI","CRV","UNI","SUSHI","CAKE","BAKE","ALPHA","BETA","GALA","CHZ","OGN","STORJ","BLZ","COTI","HOT","IOST","IOTX","KNC","LRC","NKN","NMR","POLS","RARE","REQ","RLC","STMX","SXP","TWT","VIDT","WAN","WAXP","ZEN","ZKS","ENJ","ZIL","KLAY","ONE","ICX","XTZ","ONT","QTUM","WAVES","KSM","RUNE","PEPE","WIF","BONK","FLOKI","NOT","TON","OP","ARB","SUI","APT","INJ","SEI","TIA","PYTH","JUP","ONDO","STRK","ENA","ETHFI"]

def send_telegram(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try:
        requests.post(url, json={"chat_id": CHAT_ID, "text": text, "parse_mode": "HTML"})
    except:
        pass

def get_klines_kucoin(symbol, interval='4h', limit=2):
    # KuCoin interval: '4hour'
    kucoin_interval = '4hour' if interval == '4h' else '1hour'
    url = f"https://api.kucoin.com/api/v1/market/candles?type={kucoin_interval}&symbol={symbol}-USDT&limit={limit}"
    try:
        r = requests.get(url, timeout=10)
        data = r.json()
        if data.get('code') == '200000' and data.get('data'):
            candles = data['data']
            # candles: [time,open,close,high,low,volume, turnover]
            closes = [float(c[2]) for c in candles]
            return closes
    except Exception as e:
        print(f"KuCoin ошибка {symbol}: {e}")
    return []

def get_price_change(symbol):
    closes = get_klines_kucoin(symbol, '4h', 2)
    if len(closes) < 2:
        return None
    change = (closes[-1] - closes[-2]) / closes[-2] * 100
    return change

def get_realtime_price(symbol):
    # KuCoin текущая цена
    url = f"https://api.kucoin.com/api/v1/market/orderbook/level1?symbol={symbol}-USDT"
    try:
        r = requests.get(url, timeout=5)
        data = r.json()
        if data.get('code') == '200000':
            return float(data['data']['price'])
    except:
        pass
    return None

def scan():
    print(f"[{datetime.now()}] Сканирование...")
    for sym in COINS:
        try:
            change = get_price_change(sym)
            if change is None:
                print(f"  {sym}: изменение не получено")
                continue
            if change > 1.0:  # порог 1% роста за 4 часа
                price = get_realtime_price(sym)
                if price is None:
                    continue
                msg = f"🔻 SHORT {sym} | {price:.6f}\nРост за 4ч: {change:.2f}%"
                send_telegram(msg)
                print(f"✅ {sym}")
                time.sleep(2)
        except Exception as e:
            print(f"Ошибка {sym}: {e}")
        time.sleep(0.2)
    print("Цикл завершён, жду 1 час.")

if __name__ == "__main__":
    send_telegram("🚀 Бот (KuCoin, низколиквидные монеты) запущен.")
    while True:
        scan()
        time.sleep(3600)