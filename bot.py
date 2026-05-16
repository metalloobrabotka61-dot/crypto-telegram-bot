import requests
import time
from datetime import datetime

TELEGRAM_TOKEN = "8695713035:AAELPJ25J5SMbw2Ed6rEW1fiuAtRZ4L9Abc"
CHAT_ID = "694614387"

# Список монет (символы в нижнем регистре для CoinGecko)
COINS_LOW = ["1000lunc", "luna2", "ustc", "anc", "mir", "bat", "zrx", "rep", "snx", "comp", "mkr", "yfi", "crv", "uni", "sushi", "cake", "bake", "alpha", "beta", "gala", "chz", "ogn", "storj", "blz", "coti", "hot", "iost", "iotx", "knc", "lrc", "nkn", "nmr", "pols", "rare", "req", "rlc", "stmx", "sxp", "twt", "vidt", "wan", "waxp", "zen", "zks", "enj", "zil", "klay", "one", "icx", "xtz", "ont", "qtum", "waves", "ksm", "rune", "pepe", "wif", "bonk", "floki", "not", "ton", "op", "arb", "sui", "apt", "inj", "sei", "tia", "pyth", "jup", "ondo", "strk", "ena", "ethfi"]

def send_telegram(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try:
        requests.post(url, json={"chat_id": CHAT_ID, "text": text, "parse_mode": "HTML"})
    except:
        pass

def get_24h_change_coingecko(coin_id):
    """Возвращает изменение цены за 24 часа в процентах"""
    url = f"https://api.coingecko.com/api/v3/coins/markets?vs_currency=usd&ids={coin_id}&order=market_cap_desc&per_page=1&page=1&sparkline=false"
    try:
        r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
        data = r.json()
        if data and isinstance(data, list) and len(data) > 0:
            return data[0].get('price_change_percentage_24h', 0)
    except Exception as e:
        print(f"Ошибка {coin_id}: {e}")
    return None

def get_current_price_coingecko(coin_id):
    url = f"https://api.coingecko.com/api/v3/simple/price?ids={coin_id}&vs_currencies=usd"
    try:
        r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=5)
        data = r.json()
        if data and coin_id in data:
            return data[coin_id]['usd']
    except:
        pass
    return None

def scan():
    print(f"[{datetime.now()}] Сканирование через CoinGecko (24h изменение)...")
    for coin_id in COINS_LOW:
        change = get_24h_change_coingecko(coin_id)
        if change is None:
            print(f"  {coin_id}: нет данных")
            continue
        print(f"  {coin_id}: изменение за 24ч: {change:+.2f}%")
        if change > 0.5:  # порог роста > 0.5% (для теста)
            price = get_current_price_coingecko(coin_id)
            if price:
                msg = f"🔻 ТЕСТ SHORT {coin_id.upper()} | {price:.6f}\nРост за 24ч: {change:.2f}%"
                send_telegram(msg)
                print(f"    ✅ СИГНАЛ отправлен")
            else:
                print(f"    ❌ нет цены")
        time.sleep(0.2)
    print("Цикл завершён, жду 1 час.\n")

if __name__ == "__main__":
    send_telegram("🚀 Бот (низколиквидные монеты, CoinGecko, рост >0.5% за 24ч) запущен.")
    while True:
        scan()
        time.sleep(3600)