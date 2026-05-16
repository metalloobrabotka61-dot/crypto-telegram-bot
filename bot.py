import requests
import time
from datetime import datetime

TELEGRAM_TOKEN = "8695713035:AAELPJ25J5SMbw2Ed6rEW1fiuAtRZ4L9Abc"
CHAT_ID = "694614387"

# Список монет (символы как на CoinPaprika: id монеты)
COINS = [
    "1000lunc", "luna2", "ustc", "anc", "mir", "bat", "zrx", "rep", "snx", "comp",
    "mkr", "yfi", "crv", "uni", "sushi", "cake", "bake", "alpha", "beta", "gala",
    "chz", "ogn", "storj", "blz", "coti", "hot", "iost", "iotx", "knc", "lrc",
    "nkn", "nmr", "pols", "rare", "req", "rlc", "stmx", "sxp", "twt", "vidt",
    "wan", "waxp", "zen", "zks", "enj", "zil", "klay", "one", "icx", "xtz",
    "ont", "qtum", "waves", "ksm", "rune", "pepe", "wif", "bonk", "floki", "not",
    "ton", "op", "arb", "sui", "apt", "inj", "sei", "tia", "pyth", "jup",
    "ondo", "strk", "ena", "ethfi"
]

def send_telegram(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try:
        requests.post(url, json={"chat_id": CHAT_ID, "text": text, "parse_mode": "HTML"})
    except:
        pass

def get_price_change(symbol_id):
    """Получает текущую цену и цену 4 часа назад с CoinPaprika"""
    url = f"https://api.coinpaprika.com/v1/tickers/{symbol_id}/historical?start={int(time.time())-14400}&limit=2"
    try:
        r = requests.get(url, timeout=10)
        data = r.json()
        if isinstance(data, list) and len(data) >= 2:
            old = data[0]['price']
            new = data[1]['price']
            return old, new
    except:
        pass
    return None, None

def get_realtime_price(symbol_id):
    url = f"https://api.coinpaprika.com/v1/tickers/{symbol_id}"
    try:
        r = requests.get(url, timeout=5)
        data = r.json()
        return data['price']
    except:
        return None

def scan():
    print(f"[{datetime.now()}] Сканирование через CoinPaprika...")
    for coin_id in COINS:
        old, new = get_price_change(coin_id)
        if old is None:
            print(f"  {coin_id}: нет данных")
            continue
        change = (new - old) / old * 100
        print(f"  {coin_id}: {new:.6f}, 4ч назад {old:.6f}, изменение {change:+.2f}%")
        if change > 1.0:
            price = get_realtime_price(coin_id)
            if price:
                send_telegram(f"🔻 SHORT {coin_id.upper()} | {price:.6f}\nРост за 4ч: {change:.2f}%")
                print(f"    ✅ СИГНАЛ отправлен")
        time.sleep(0.2)
    print("Цикл завершён, жду 1 час.\n")

if __name__ == "__main__":
    send_telegram("🚀 Бот на CoinPaprika (низколиквидные) запущен.")
    while True:
        scan()
        time.sleep(3600)