import requests
import time
from datetime import datetime

TELEGRAM_TOKEN = "8695713035:AAELPJ25J5SMbw2Ed6rEW1fiuAtRZ4L9Abc"
CHAT_ID = "694614387"

# Список монет (символы как на CoinCap)
COINS = [
    "1000lunc", "luna2", "ustc", "anc", "mir", "bat", "zrx", "rep", "snx", "comp",
    "mkr", "yfi", "crv", "uni", "sushi", "cake", "bake", "alpha", "beta", "gala",
    "chz", "ogn", "storj", "blz", "coti", "hot", "iost", "iotx", "knc", "lrc",
    "nkn", "nmr", "pols", "rare", "req", "rlc", "stmx", "sxp", "wan", "twt",
    "vidt", "waxp", "zen", "zks", "enj", "zil", "klay", "one", "icx", "xtz",
    "ont", "qtum", "waves", "ksm", "rune", "pepe", "wif", "bonk", "floki", "not",
    "ton", "op", "arb", "sui", "apt", "inj", "sei", "tia", "pyth", "jup", "ondo",
    "strk", "ena", "ethfi"
]

def send_telegram(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try:
        requests.post(url, json={"chat_id": CHAT_ID, "text": text, "parse_mode": "HTML"})
    except:
        pass

def get_historical_price(symbol, interval='4h'):
    """
    Получает текущую цену и цену 4 часа назад с CoinCap.
    CoinCap возвращает историю в минутах.
    """
    # Текущая цена
    url_price = f"https://api.coincap.io/v2/assets/{symbol}"
    try:
        r = requests.get(url_price, timeout=10)
        data = r.json()
        if data.get('data') and 'priceUsd' in data['data']:
            current = float(data['data']['priceUsd'])
        else:
            return None, None
    except:
        return None, None

    # История за последние 24 часа (можно взять 4 часа назад)
    # CoinCap отдаёт историю в миллисекундах, возьмём 4 часа назад = now - 14400000 ms
    now = int(time.time() * 1000)
    four_hours_ago = now - 4 * 60 * 60 * 1000
    url_hist = f"https://api.coincap.io/v2/assets/{symbol}/history?interval=m5&start={four_hours_ago}&end={now}"
    try:
        r = requests.get(url_hist, timeout=10)
        data = r.json()
        if data.get('data') and len(data['data']) > 0:
            # Берём первую точку (ближайшую к 4 часам назад)
            old = float(data['data'][0]['priceUsd'])
            return current, old
    except:
        pass
    return current, None

def scan():
    print(f"[{datetime.now()}] Сканирование через CoinCap...")
    for sym in COINS:
        try:
            current, old = get_historical_price(sym)
            if current is None:
                print(f"  {sym}: нет данных")
                continue
            if old is None:
                change = 0
                print(f"  {sym}: текущая {current:.6f}, нет истории")
            else:
                change = (current - old) / old * 100
                print(f"  {sym}: текущая {current:.6f}, 4ч назад {old:.6f}, изменение {change:+.2f}%")
                if change > 1.0:   # рост более 1% за 4 часа
                    send_telegram(f"🔻 SHORT {sym.upper()} | {current:.6f}\nРост за 4ч: {change:.2f}%")
                    print(f"    ✅ СИГНАЛ отправлен")
        except Exception as e:
            print(f"  Ошибка {sym}: {e}")
        time.sleep(0.2)
    print("Цикл завершён, жду 1 час.\n")

if __name__ == "__main__":
    send_telegram("🚀 Бот (CoinCap) запущен. Анализ низколиквидных монет.")
    while True:
        scan()
        time.sleep(3600)