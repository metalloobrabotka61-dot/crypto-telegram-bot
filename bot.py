import requests
import time
from datetime import datetime

# ========== НАСТРОЙКИ ==========
TELEGRAM_TOKEN = "8590220699:AAG6U7JoOH638P-LhA5Ow-Byr2cgh7thAAE"
CHAT_ID = "694614387"

# Настройки скальпинга
CHECK_INTERVAL = 120            # Проверять каждые 120 секунд (2 минуты)
TOP_VOLATILE_COINS = 20        # Анализировать топ-20 самых волатильных монет
MIN_VOLUME_USDT = 5_000_000    # Минимальный объём за 24ч (500k $)
MIN_CHANGE_5M = 0.5            # Мин. изменение цены за 5 минут (в %) – чтобы отсеять штиль
EMA_SHORT = 5                  # Короткая EMA (период в минутах)
EMA_LONG = 13                  # Длинная EMA
TAKE_PROFIT_PERCENT = 0.7      # Тейк +0.7%
STOP_LOSS_PERCENT = 0.5        # Стоп -0.5%
LEVERAGE = 5                   # Плечо 5x
# =================================

def send_telegram(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try:
        requests.post(url, json={"chat_id": CHAT_ID, "text": text, "parse_mode": "HTML"})
    except:
        pass

def get_top_volume_coins(limit=50):
    """Получает с Binance монеты с наибольшим объёмом (USDT пары)"""
    url = "https://api.binance.com/api/v3/ticker/24hr"
    try:
        data = requests.get(url).json()
        # Фильтруем только пары, заканчивающиеся на USDT
        usdt_pairs = [item for item in data if item['symbol'].endswith('USDT')]
        # Сортируем по объёму (quoteVolume)
        usdt_pairs.sort(key=lambda x: float(x['quoteVolume']), reverse=True)
        top_coins = []
        for pair in usdt_pairs[:limit]:
            symbol = pair['symbol'].replace('USDT', '')
            top_coins.append({
                'symbol': symbol,
                'volume': float(pair['quoteVolume']),
                'change24h': float(pair['priceChangePercent'])
            })
        return top_coins
    except Exception as e:
        print("Ошибка получения списка монет Binance:", e)
        return []

def get_klines(symbol, interval='1m', limit=100):
    """Получает минутные свечи для символа (например, 'BTCUSDT')"""
    url = f"https://api.binance.com/api/v3/klines?symbol={symbol}USDT&interval={interval}&limit={limit}"
    try:
        data = requests.get(url).json()
        closes = [float(candle[4]) for candle in data]  # цены закрытия
        volumes = [float(candle[5]) for candle in data]
        return closes, volumes
    except:
        return [], []

def calculate_ema(prices, period):
    """Экспоненциальная скользящая средняя"""
    if len(prices) < period:
        return None
    multiplier = 2 / (period + 1)
    ema = prices[0]
    for price in prices[1:]:
        ema = (price - ema) * multiplier + ema
    return ema

def get_current_price(symbol):
    """Текущая цена с Binance"""
    url = f"https://api.binance.com/api/v3/ticker/price?symbol={symbol}USDT"
    try:
        data = requests.get(url).json()
        return float(data['price'])
    except:
        return None

def analyze_and_signal():
    # 1. Получаем топ монет по объёму (кандидаты на волатильность)
    all_coins = get_top_volume_coins(TOP_VOLATILE_COINS * 2)  # возьмём с запасом
    if not all_coins:
        send_telegram("⚠️ Не удалось получить список монет с Binance.")
        return

    # 2. Фильтруем по минимальному объёму
    filtered_coins = [c for c in all_coins if c['volume'] >= MIN_VOLUME_USDT]
    # 3. Дополнительная фильтрация: оставляем только монеты с изменением за 24ч > 2% (чтобы не брать стабильные)
    #    но для скальпинга можно и без этого, оставим как есть, позже отсеем по 5-минутному изменению

    # Для каждой монеты проверим волатильность за последние 5 минут и EMA
    signals = []
    for coin in filtered_coins[:TOP_VOLATILE_COINS]:
        symbol = coin['symbol']
        # Получаем минутные свечи (последние 30 минут достаточно)
        closes, volumes = get_klines(symbol, interval='1m', limit=30)
        if len(closes) < EMA_LONG + 1:
            continue

        # Вычисляем EMA5 и EMA13
        ema5 = calculate_ema(closes[-EMA_SHORT:], EMA_SHORT)
        ema13 = calculate_ema(closes[-EMA_LONG:], EMA_LONG)
        if ema5 is None or ema13 is None:
            continue

        # Текущая цена (последнее закрытие)
        current_price = closes[-1]
        # Изменение цены за последние 5 минут (в %)
        price_5m_ago = closes[-6] if len(closes) >= 6 else closes[0]
        change_5m = (current_price - price_5m_ago) / price_5m_ago * 100

        # Пропускаем монеты, которые почти не двигаются за 5 минут
        if abs(change_5m) < MIN_CHANGE_5M:
            continue

        # Логика сигнала: пересечение EMA5 и EMA13
        # Берём предыдущие значения EMA для определения пересечения
        if len(closes) > EMA_LONG + 2:
            prev_ema5 = calculate_ema(closes[-EMA_SHORT-1:-1], EMA_SHORT)
            prev_ema13 = calculate_ema(closes[-EMA_LONG-1:-1], EMA_LONG)
            if prev_ema5 is None or prev_ema13 is None:
                continue
        else:
            continue

        # Сигнал LONG: EMA5 пересекла EMA13 снизу вверх
        if prev_ema5 <= prev_ema13 and ema5 > ema13:
            entry = current_price
            tp = entry * (1 + TAKE_PROFIT_PERCENT / 100)
            sl = entry * (1 - STOP_LOSS_PERCENT / 100)
            message = f"""
📢 <b>LONG (Скальп) {symbol}</b>

🔹 <b>Вход:</b> ${entry:.6f}
🎯 <b>TP:</b> ${tp:.6f} (+{TAKE_PROFIT_PERCENT}%)
🛑 <b>SL:</b> ${sl:.6f} (-{STOP_LOSS_PERCENT}%)
⚙️ <b>Плечо:</b> {LEVERAGE}x

📈 <b>EMA5 ({EMA_SHORT})</b> пересекла <b>EMA13 ({EMA_LONG})</b> снизу вверх.
📊 Изменение за 5 мин: +{change_5m:.2f}%
💡 <b>Пояснение:</b> Быстрое движение и пересечение средних — сигнал к импульсу вверх.

⏰ {datetime.now().strftime('%H:%M:%S')}
"""
            signals.append(message)

        # Сигнал SHORT: EMA5 пересекла EMA13 сверху вниз
        elif prev_ema5 >= prev_ema13 and ema5 < ema13:
            entry = current_price
            tp = entry * (1 - TAKE_PROFIT_PERCENT / 100)
            sl = entry * (1 + STOP_LOSS_PERCENT / 100)
            message = f"""
📢 <b>SHORT (Скальп) {symbol}</b>

🔹 <b>Вход:</b> ${entry:.6f}
🎯 <b>TP:</b> ${tp:.6f} (падение {TAKE_PROFIT_PERCENT}%)
🛑 <b>SL:</b> ${sl:.6f} (рост {STOP_LOSS_PERCENT}%)
⚙️ <b>Плечо:</b> {LEVERAGE}x

📉 <b>EMA5 ({EMA_SHORT})</b> пересекла <b>EMA13 ({EMA_LONG})</b> сверху вниз.
📊 Изменение за 5 мин: {change_5m:.2f}%
💡 <b>Пояснение:</b> Импульс вниз, возможен скальп на коррекции.

⏰ {datetime.now().strftime('%H:%M:%S')}
"""
            signals.append(message)

        # Небольшая пауза между запросами к Binance
        time.sleep(0.3)

    # Отправляем все накопленные сигналы
    for msg in signals:
        send_telegram(msg)
        time.sleep(1)

    if not signals:
        print(f"{datetime.now()} - Сигналов нет. Волатильность низкая.")

# ========== ЗАПУСК ==========
print(f"Скальпинг-бот запущен. Проверка каждые {CHECK_INTERVAL//60} мин.")
print(f"Параметры: EMA{EMA_SHORT}/EMA{EMA_LONG}, TP {TAKE_PROFIT_PERCENT}%, SL {STOP_LOSS_PERCENT}%, плечо {LEVERAGE}x")
while True:
    try:
        analyze_and_signal()
        time.sleep(CHECK_INTERVAL)
    except Exception as e:
        print("Ошибка:", e)
        time.sleep(60)