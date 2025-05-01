# forecast.py

import logging
import numpy as np
from datetime import datetime
import os
import csv

DAILY_FILE = os.path.join("daily_reports", "daily_summary_corrected.csv")

def get_player_history(player_name):
    """
    Считываем daily_summary_corrected.csv, возвращаем [(date_str, close_price), ...] по player_name.
    Сортируем по дате.
    """
    history = []
    if not os.path.isfile(DAILY_FILE):
        logging.warning("[forecast] daily_summary_corrected.csv не найден.")
        return history

    try:
        with open(DAILY_FILE, "r", encoding="utf-8") as f:
            rd = csv.DictReader(f)
            for row in rd:
                if row["Игрок"].strip() == player_name:
                    date_str = row["Дата"].strip()
                    try:
                        close_price = float(row["Закрытие"])
                        history.append((date_str, close_price))
                    except ValueError:
                        pass
        # Сортируем по дате (YYYY-MM-DD)
        def parse_date(d):
            return datetime.strptime(d, "%Y-%m-%d")
        history.sort(key=lambda x: parse_date(x[0]))
    except Exception as e:
        logging.error(f"[forecast] Ошибка чтения {DAILY_FILE}: {e}")
    return history

def predict_moving_average(player_name, window=3):
    """
    Скользящая средняя по последним `window` закрытиям.
    """
    hist = get_player_history(player_name)
    if len(hist) < window:
        return None
    recent = [p[1] for p in hist[-window:]]
    return sum(recent) / window

def predict_exponential_smoothing(player_name, alpha=0.3):
    """
    Эксп. сглаживание. Возвращаем прогноз на "следующий" день = последнее S_t.
    """
    hist = get_player_history(player_name)
    if not hist:
        return None
    s = hist[0][1]
    for i in range(1, len(hist)):
        x_t = hist[i][1]
        s = alpha*x_t + (1-alpha)*s
    return s

def predict_linear_regression(player_name, window=7):
    """
    Лин. регрессия по последним `window` точкам. Возвращаем прогноз на x=window (след. день).
    """
    hist = get_player_history(player_name)
    if len(hist) < window:
        return None
    recent = hist[-window:]
    x_vals = np.arange(window)
    y_vals = np.array([r[1] for r in recent], dtype=float)
    try:
        A, B = np.polyfit(x_vals, y_vals, 1)  # A = slope, B = intercept
        return A*window + B
    except Exception as e:
        logging.error(f"[forecast] Ошибка лин. регрессии: {e}")
        return None
