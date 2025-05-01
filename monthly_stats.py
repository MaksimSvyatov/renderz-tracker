# monthly_stats.py
import os
import csv
import logging
from datetime import datetime, timedelta
from collections import defaultdict

def finalize_monthly_summary():
    """
    Раз в месяц читаем daily_summary_corrected.csv за "прошлый месяц",
    пишем сводку в monthly_reports/monthly_summary.csv.
    """
    daily_file = os.path.join("daily_reports", "daily_summary_corrected.csv")
    if not os.path.isfile(daily_file):
        logging.info("[monthly_stats] daily_summary_corrected.csv не найден, пропускаем.")
        return

    today = datetime.now()
    last_month = today.replace(day=1) - timedelta(days=1)
    month_str = last_month.strftime("%Y-%m")  # "2025-02"

    rows = []
    try:
        with open(daily_file, "r", encoding="utf-8") as f:
            rd = csv.DictReader(f)
            for row in rd:
                d_ = row.get("Дата", "")
                if d_.startswith(month_str):
                    rows.append(row)
    except Exception as e:
        logging.error(f"[monthly_stats] Ошибка чтения {daily_file}: {e}")
        return

    if not rows:
        logging.info(f"[monthly_stats] Нет данных за {month_str}, пропускаем.")
        return

    data_by_player = defaultdict(lambda: {
        "min_7d": None,
        "max_7d": None,
        "sum_of_avgs": 0.0,
        "days_counted": 0
    })

    for row in rows:
        pl = row["Игрок"]
        try:
            mn = float(row["Минимум"].replace(" ", ""))
            mx = float(row["Максимум"].replace(" ", ""))
            avg_ = float(row["Средняя цена"])
        except:
            continue
        st = data_by_player[pl]
        if st["min_7d"] is None or mn < st["min_7d"]:
            st["min_7d"] = mn
        if st["max_7d"] is None or mx > st["max_7d"]:
            st["max_7d"] = mx
        st["sum_of_avgs"] += avg_
        st["days_counted"] += 1

    os.makedirs("monthly_reports", exist_ok=True)
    out_file = os.path.join("monthly_reports", "monthly_summary.csv")
    file_exists = os.path.isfile(out_file)
    end_week = datetime.now().strftime("%Y-%m-%d")

    try:
        with open(out_file, "a", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            if not file_exists:
                w.writerow(["Месяц_конец","Игрок","Мин_за_месяц","Макс_за_месяц","Среднее_средних","Дней"])
            for pl, st in data_by_player.items():
                c_ = st["days_counted"]
                if c_ > 0:
                    mmn = st["min_7d"] or 0
                    mmx = st["max_7d"] or 0
                    avgavg = st["sum_of_avgs"]/c_
                    w.writerow([month_str, pl, int(mmn), int(mmx), f"{avgavg:.2f}", c_])
        logging.info(f"[monthly_stats] Записали monthly_summary за {month_str}")
    except Exception as e:
        logging.error(f"[monthly_stats] Ошибка записи {out_file}: {e}")
