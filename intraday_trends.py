import csv
import os
import logging

def update_intraday(player_name, price_int, price_change, min_price_str, max_price_str, time_24h):
    folder = "intraday_data"
    os.makedirs(folder, exist_ok=True)
    filename = os.path.join(folder, f"{player_name.replace(' ','_')}.csv")
    file_exists = os.path.isfile(filename)
    try:
        with open(filename, mode="a", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            if not file_exists:
                w.writerow(["Время","Цена","Изменение","Мин","Макс"])
            w.writerow([time_24h, price_int, price_change, min_price_str, max_price_str])
    except Exception as e:
        logging.error(f"[intraday_trends] Ошибка записи intraday {filename}: {e}")

def update_longterm_data(player_name, price_int, price_change, min_price_str, max_price_str, time_24h):
    folder = "data"
    os.makedirs(folder, exist_ok=True)
    filename = os.path.join(folder, f"{player_name.replace(' ','_')}.csv")
    file_exists = os.path.isfile(filename)
    try:
        with open(filename, mode="a", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            if not file_exists:
                w.writerow(["Дата","Время","Цена","Изменение","Мин. цена","Макс. цена"])
            today_str = ""
            w.writerow([today_str, time_24h, price_int, price_change, min_price_str, max_price_str])
    except Exception as e:
        logging.error(f"[intraday_trends] Ошибка записи longterm {filename}: {e}")
