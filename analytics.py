"""
analytics.py - Управление аналитикой данных игроков.

Функциональность:
1) Сохранение ежедневной аналитики (save_daily_analytics).
2) Чтение исторических данных (get_player_history).
3) Простейшие методы прогнозирования (naive_forecast, moving_average, exponential_smoothing).
"""

import os
import csv
import logging
from datetime import datetime, timedelta

# Папка, где лежат сырые данные по игрокам (CSV).
DATA_DIR = "data"

# Папка, где будут сохраняться итоговые аналитические отчёты.
ANALYTICS_DIR = "analytics"
os.makedirs(ANALYTICS_DIR, exist_ok=True)  # Создаём папку, если её нет.

def get_data_filename(player_name: str) -> str:
    """
    Формирует путь к CSV-файлу с историей цен игрока в папке data/.
    Пример: "Joško Gvardiol 101" -> "data/Joško_Gvardiol_101.csv"
    """
    sanitized_name = player_name.replace(' ', '_').replace('.', '').replace(',', '')
    return os.path.join(DATA_DIR, sanitized_name + ".csv")

def get_player_history(player_name: str):
    """
    Читает CSV-файл игрока из data/ и возвращает список кортежей:
    [(date_str, time_str, price_int), ...].
    Ожидаемый формат CSV:
      Дата,Время,Цена,Изменение,Мин. цена,Макс. цена
    """
    filename = get_data_filename(player_name)
    if not os.path.isfile(filename):
        logging.debug(f"[get_player_history] Файл '{filename}' не найден.")
        return []

    history = []
    try:
        with open(filename, mode="r", encoding="utf-8") as f:
            reader = csv.reader(f)
            rows = list(reader)
            # Предполагаем, что rows[0] — заголовок
            for row in rows[1:]:
                if len(row) < 3:
                    continue
                date_str = row[0].strip()
                time_str = row[1].strip()
                price_str = row[2].strip().replace(" ", "")
                try:
                    price_int = int(price_str)
                except ValueError:
                    price_int = None

                if price_int is not None:
                    history.append((date_str, time_str, price_int))
    except Exception as e:
        logging.error(f"[get_player_history] Ошибка чтения '{filename}': {e}")
    return history

def naive_forecast(player_name: str):
    """
    Наивный прогноз: берём последнюю известную цену как "прогноз на следующий шаг".
    Если данных нет, возвращаем None.
    """
    history = get_player_history(player_name)
    if not history:
        return None
    # Последняя запись
    _, _, last_price = history[-1]
    return last_price

def moving_average(player_name: str, window: int = 3):
    """
    Скользящая средняя (Simple Moving Average) цены за последние `window` записей.
    Если данных меньше, чем `window`, возвращает None.
    """
    history = get_player_history(player_name)
    if len(history) < window:
        return None
    recent_prices = [entry[2] for entry in history[-window:]]
    avg_price = sum(recent_prices) / window
    return avg_price

def exponential_smoothing(player_name: str, alpha: float = 0.3):
    """
    Простое экспоненциальное сглаживание (Simple Exponential Smoothing, SES).
    Возвращает последнее сглаженное значение (E_t), которое можно считать
    прогнозом на "следующий" шаг.

    Формула:
        E_0 = P_0
        E_t = alpha * P_t + (1 - alpha) * E_(t-1)

    :param player_name: Имя/ключ игрока (без .csv).
    :param alpha: Коэффициент сглаживания (0 < alpha < 1).
    :return: Числовое значение E_t или None, если данных нет.
    """
    history = get_player_history(player_name)
    if not history:
        return None

    prices = [h[2] for h in history]
    # Инициализируем E_0 = P_0
    E_prev = prices[0]
    # Идём по остальным точкам
    for i in range(1, len(prices)):
        P_t = prices[i]
        E_t = alpha * P_t + (1 - alpha) * E_prev
        E_prev = E_t

    return E_prev

def format_analytics_filename(player_name: str) -> str:
    """
    Формирует путь к файлу для хранения аналитики в папке analytics/.
    Пример: "Joško Gvardiol 101" -> "analytics/Joško_Gvardiol_101.csv"
    """
    sanitized_name = player_name.replace(' ', '_').replace('.', '').replace(',', '')
    return os.path.join(ANALYTICS_DIR, sanitized_name + ".csv")

def save_daily_analytics(player_name,
                         min_price,
                         max_price,
                         first_increase_time,
                         second_increase_time,
                         had_decrease,
                         best_buy_time,
                         best_sell_time):
    """
    Сохраняет ежедневную аналитику по игроку в файл analytics/<player_name>.csv.
    Структура CSV: Дата,Мин. цена,Макс. цена,Первый рост,Второй рост,Было падение?,Лучший момент покупки,Лучший момент продажи
    """
    filename = format_analytics_filename(player_name)
    file_exists = os.path.isfile(filename)

    try:
        with open(filename, mode="a", newline="", encoding="utf-8") as file:
            writer = csv.writer(file)
            # Если файл только что создан — пишем заголовок
            if not file_exists:
                writer.writerow([
                    "Дата",
                    "Мин. цена",
                    "Макс. цена",
                    "Первый рост",
                    "Второй рост",
                    "Было падение?",
                    "Лучший момент покупки",
                    "Лучший момент продажи"
                ])
            today = datetime.now().strftime("%Y-%m-%d")
            writer.writerow([
                today,
                min_price,
                max_price,
                first_increase_time,
                second_increase_time,
                had_decrease,
                best_buy_time,
                best_sell_time
            ])
        logging.info(
            f"✅ Аналитика сохранена для '{player_name}': "
            f"Мин: {min_price}, Макс: {max_price}, 1-й рост: {first_increase_time}, "
            f"2-й рост: {second_increase_time}, Было падение: {had_decrease}, "
            f"Покупка: {best_buy_time}, Продажа: {best_sell_time}"
        )
    except Exception as e:
        logging.error(f"❌ Ошибка сохранения аналитики для '{player_name}': {e}")

if __name__ == "__main__":
    # Простой тест работы функций.
    logging.basicConfig(level=logging.DEBUG, format="%(asctime)s - %(levelname)s - %(message)s")

    test_player = "Joško_Gvardiol_101"  # пример, подставьте реальное имя файла (без .csv) из data/

    # 1) Проверяем чтение истории
    history = get_player_history(test_player)
    print(f"[TEST] История для {test_player} содержит {len(history)} записей.")

    # 2) Наивный прогноз
    nf = naive_forecast(test_player)
    print(f"[TEST] Наивный прогноз (последняя цена): {nf}")

    # 3) Скользящая средняя (окно 3)
    ma_3 = moving_average(test_player, window=3)
    print(f"[TEST] Скользящая средняя (3): {ma_3}")

    # 4) Экспоненциальное сглаживание (alpha=0.3)
    es_val = exponential_smoothing(test_player, alpha=0.3)
    print(f"[TEST] Экспоненциальное сглаживание (alpha=0.3): {es_val}")

    # 5) Пример сохранения аналитики (тест)
    save_daily_analytics(
        player_name=test_player,
        min_price=100,
        max_price=120,
        first_increase_time="10:00:00",
        second_increase_time="11:30:00",
        had_decrease=True,
        best_buy_time="09:45:00",
        best_sell_time="13:00:00"
    )
