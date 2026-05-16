import requests
import time
from datetime import datetime

TELEGRAM_TOKEN = "8695713035:AAELPJ25J5SMbw2Ed6rEW1fiuAtRZ4L9Abc"
CHAT_ID = "694614387"

# Проверенные монеты, которые точно есть на Binance (USDT пары)
COINS = [
    "1000LUNC", "LUNA2", "USTC", "ANC", "MIR", "BAT", "ZRX", "REP", "SNX", "COMP",
    "MKR", "YFI", "CRV", "UNI", "SUSHI", "CAKE", "BAKE", "ALPHA", "BETA", "GALA",
    "CHZ", "OGN", "STORJ", "BLZ", "COTI", "HOT", "IOST", "IOTX", "KNC", "LRC",
    "NKN", "NMR", "POLS", "RARE", "REQ", "RLC", "STMX", "SXP", "TWT", "VIDT",
    "WAN", "WAXP", "ZEN", "ZKS", "ENJ", "ZIL", "KLAY", "ONE", "ICX", "XTZ",
    "ONT", "QTUM", "WAVES", "KSM", "RUNE", "PEPE", "WIF", "BONK", "FLOKI", "NOT",
    "TON", "OP", "ARB", "SUI", "APT", "INJ", "SEI", "TIA", "PYTH", "JUP",
    "ONDO", "STRK", "ENA", "ETHFI"
]

def send_telegram(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try:
        requests.post(url, json={"chat_id": CHAT_ID, "text": text, "parse_mode": "HTML"})
    except:
        pass

def get_klines_with_retry(symbol, interval='4h', limit=2, retries=3):
    url = f"https://api.binance.com/api/v3/klines?symbol={symbol}USDT&interval={interval}&limit={limit}"
    for attempt in range(retries):
        try:
            r = requests.get(url, timeout=10)
            if r.status_code == 200:
                data = r.json()
                if isinstance(data, list) and len(data) == 2:
                    return [float(data[0][4]), float(data[1][4])]
            print(f"  {symbol}: попытка {attempt+1}, статус {r.status_code}")
        except Exception as e:
            print(f"  {symbol}: ошибка {e}, попытка {attempt+1}")
        time.sleep(2)
    return None

def get_realtime_price_with_retry(symbol, retries=3):
    url = f"https://api.binance.com/api/v3/ticker/price?symbol={symbol}USDT"
    for attempt in range(retries):
        try:
            r = requests.get(url, timeout=10)
            if r.status_code == 200:
                return float(r.json()['price'])
        except:
            pass
        time.sleep(1)
    return None

def scan():
    print(f"[{datetime.now()}] Сканирование...")
    for sym in COINS:
        klines = get_klines_with_retry(sym)
        if klines is None:
            print(f"  {sym}: нет данных")
            continue
        old, new = klines
        change = (new - old) / old * 100
        print(f"  {sym}: {new:.6f}, 4ч назад {old:.6f}, изм {change:+.2f}%")
        if change > 1.0:   # порог
            price = get_realtime_price_with_retry(sym)
            if price:
                send_telegram(f"🔻 SHORT {sym} | {price:.6f}\nРост за 4ч: {change:.2f}%")
                print(f"    ✅ СИГНАЛ отправлен")
        time.sleep(0.5)
    print("Цикл завершён, жду 1 час.\n")

if __name__ == "__main__":
    send_telegram("🚀 Бот (Binance, повторные попытки) запущен.")
    while True:
        scan()
        time.sleep(3600)