import requests
import time
from datetime import datetime

TELEGRAM_TOKEN = "8695713035:AAELPJ25J5SMbw2Ed6rEW1fiuAtRZ4L9Abc"
CHAT_ID = "694614387"

# Список монет (можно расширить)
COINS = ["1000lunc", "ustc", "wif", "apt", "luna2", "anc", "mir", "bat", "zrx", "rep", "snx", "comp", "mkr", "yfi", "crv", "uni", "sushi", "cake", "bake", "alpha", "beta", "gala", "chz", "ogn", "storj", "blz", "coti", "hot", "iost", "iotx", "knc", "lrc", "nkn", "nmr", "pols", "rare", "req", "rlc", "stmx", "sxp", "twt", "vidt", "wan", "waxp", "zen", "zks", "enj", "zil", "klay", "one", "icx", "xtz", "ont", "qtum", "waves", "ksm", "rune", "pepe", "bonk", "floki", "not", "ton", "op", "arb", "sui", "inj", "sei", "tia", "pyth", "jup", "ondo", "strk", "ena", "ethfi"]

def send_telegram(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try:
        requests.post(url, json={"chat_id": CHAT_ID, "text": text, "parse_mode": "HTML"})
    except:
        pass

def get_coin_data(coin_id):
    """Возвращает (current_price, price_24h_ago, rsi_14) используя CoinGecko"""
    try:
        # Получаем текущую цену и изменение за 24ч
        url = f"https://api.coingecko.com/api/v3/coins/markets?vs_currency=usd&ids={coin_id}&order=market_cap_desc&per_page=1&page=1&sparkline=false"
        r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
        data = r.json()
        if not data:
            return None, None, None
        current = data[0]['current_price']
        change_24h = data[0]['price_change_percentage_24h']
        # Получаем исторические цены для RSI (14 дней)
        hist_url = f"https://api.coingecko.com/api/v3/coins/{coin_id}/market_chart?vs_currency=usd&days=14&interval=daily"
        hist_r = requests.get(hist_url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
        hist_data = hist_r.json()
        prices = [p[1] for p in hist_data['prices']]
        # RSI
        if len(prices) < 15:
            return current, change_24h, None
        gains, losses = [], []
        for i in range(1, len(prices)):
            diff = prices[i] - prices[i-1]
            gains.append(diff if diff>0 else 0)
            losses.append(-diff if diff<0 else 0)
        avg_gain = sum(gains[-14:])/14
        avg_loss = sum(losses[-14:])/14
        if avg_loss == 0:
            rsi = 100
        else:
            rsi = 100 - 100/(1+avg_gain/avg_loss)
        return current, change_24h, round(rsi, 2)
    except Exception as e:
        print(f"Ошибка {coin_id}: {e}")
        return None, None, None

def scan():
    print(f"[{datetime.now()}] Сканирование через CoinGecko...")
    for coin in COINS:
        try:
            price, change, rsi = get_coin_data(coin)
            if price is None:
                print(f"  {coin}: нет данных")
                continue
            print(f"  {coin}: цена {price:.6f}, 24h {change:+.2f}%, RSI {rsi}")
            # Условия для SHORT сигнала: RSI > 70 и рост > 5% за 24ч
            if rsi and rsi > 70 and change > 5:
                msg = f"🔻 SHORT {coin.upper()} | {price:.6f}\nRSI(14)={rsi} | рост 24h={change:+.2f}%\nВероятна коррекция вниз."
                send_telegram(msg)
                print(f"    ✅ СИГНАЛ отправлен")
        except Exception as e:
            print(f"  {coin}: ошибка {e}")
        time.sleep(0.5)
    print("Цикл завершён, жду 4 часа.\n")

if __name__ == "__main__":
    send_telegram("🚀 Бот SHORT (CoinGecko, дневные свечи) запущен. Проверка каждые 4 часа.")
    while True:
        scan()
        time.sleep(14400)  # 4 часа