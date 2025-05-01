import os
import csv
import logging
from datetime import datetime

def update_daily_summary(player_name, current_price, local_time_24h, price_change_str, min_price_str, max_price_str):
    os.makedirs("daily_reports", exist_ok=True)
    filename = os.path.join("daily_reports", "daily_summary_corrected.csv")
    file_exists = os.path.isfile(filename)

    date_str = datetime.now().strftime("%Y-%m-%d")
    row = [
        player_name,
        date_str,
        current_price,
        local_time_24h,
        min_price_str,
        max_price_str,
        price_change_str
    ]

    try:
        with open(filename, "a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            if not file_exists:
                writer.writerow(["Игрок","Дата","Текущая цена","Время","Мин","Макс","Изменение"])
            writer.writerow(row)
    except Exception as e:
        logging.error(f"[daily_stats] Ошибка записи в {filename}: {e}")
