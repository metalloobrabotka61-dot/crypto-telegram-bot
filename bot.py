import requests
import time
from datetime import datetime

TELEGRAM_TOKEN = "8695713035:AAELPJ25J5SMbw2Ed6rEW1fiuAtRZ4L9Abc"
CHAT_ID = "694614387"
CMC_API_KEY = "be01a5f404a7494f9af4aa8bbbde0c41"  # получите на coinmarketcap.com/api

COINS = ["1000LUNC","LUNA2","USTC","ANC","MIR","BAT","ZRX","REP","SNX","COMP","MKR","YFI","CRV","UNI","SUSHI","CAKE","BAKE","ALPHA","BETA","GALA","CHZ","OGN","STORJ","BLZ","COTI","HOT","IOST","IOTX","KNC","LRC","NKN","NMR","POLS","RARE","REQ","RLC","STMX","SXP","TWT","VIDT","WAN","WAXP","ZEN","ZKS","ENJ","ZIL","KLAY","ONE","ICX","XTZ","ONT","QTUM","WAVES","KSM","RUNE","PEPE","WIF","BONK","FLOKI","NOT","TON","OP","ARB","SUI","APT","INJ","SEI","TIA","PYTH","JUP","ONDO","STRK","ENA","ETHFI"]

def send_telegram(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try:
        requests.post(url, json={"chat_id": CHAT_ID, "text": text, "parse_mode": "HTML"})
    except:
        pass

def get_coin_data(symbol):
    """Получает цену, процент изменения за 4ч и 24ч объём с CoinMarketCap"""
    url = "https://pro-api.coinmarketcap.com/v1/cryptocurrency/quotes/latest"
    headers = {"X-CMC_PRO_API_KEY": CMC_API_KEY}
    params = {"symbol": symbol, "convert": "USD"}
    try:
        r = requests.get(url, headers=headers, params=params, timeout=10)
        data = r.json()
        if data.get('status', {}).get('error_code') == 0:
            quote = data['data'][symbol]['quote']['USD']
            price = quote['price']
            change_4h = quote.get('percent_change_4h', 0)
            volume_24h = quote.get('volume_24h', 0)
            return price, change_4h, volume_24h
    except Exception as e:
        print(f"Ошибка {symbol}: {e}")
    return None, None, None

def analyze_coin(symbol):
    price, change_4h, volume_24h = get_coin_data(symbol)
    if price is None:
        return None
    if change_4h > 1.0:   # рост > 1% за 4 часа
        msg = f"""
🔻 <b>SHORT СИГНАЛ</b> <b>{symbol}</b> | {price:.6f}

<b>Рост за 4ч:</b> {change_4h:+.2f}%
<b>Объём 24ч:</b> {volume_24h/1e6:.2f}M

💡 <b>Обоснование:</b> Рост за 4 часа превышает 1%, возможна коррекция вниз.

⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
        return msg
    return None

def scan():
    print(f"[{datetime.now()}] Сканирование через CoinMarketCap...")
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
    print("Цикл завершён, жду 1 час.\n")

if __name__ == "__main__":
    send_telegram("🚀 Бот (CoinMarketCap) запущен. Анализ низколиквидных монет.")
    while True:
        scan()
        time.sleep(3600)