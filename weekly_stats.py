# # =============================================
# # ФАЙЛ: weekly_stats.py (ФИНАЛЬНАЯ ВЕРСИЯ - дозапись weekly_summary)
# # =============================================
# import os
# import csv
# import logging
# from datetime import datetime, timedelta, timezone
# from collections import defaultdict
# import ohlc_generator
# import pandas as pd
# import config
#
# EXPECTED_HEADER_OHLC = ohlc_generator.EXPECTED_HEADER_OHLC
# REPORTS_DIR_DAILY = "daily_reports"
# REPORTS_DIR_WEEKLY = "weekly_reports"
#
# # --- ИСПРАВЛЕНО для ДОЗАПИСИ ---
# def finalize_weekly_summary():
#     """
#     Агрегирует недельные данные из дневного OHLC отчета
#     и ДОПИСЫВАЕТ их в weekly_summary.csv.
#     """
#     daily_ohlc_file = os.path.join(REPORTS_DIR_DAILY, "daily_summary_corrected.csv")
#     if not os.path.isfile(daily_ohlc_file): logging.warning(f"[weekly] Файл {daily_ohlc_file} не найден."); return
#
#     now_utc = datetime.now(timezone.utc); cutoff_date_utc = (now_utc - timedelta(days=7)).date()
#     end_week_str = now_utc.strftime("%Y-%m-%d") # Дата генерации отчета
#
#     try:
#         df_ohlc = pd.read_csv(daily_ohlc_file, parse_dates=['Дата'])
#         if not set(EXPECTED_HEADER_OHLC).issubset(set(df_ohlc.columns)): logging.error(f"[weekly] Заголовок {daily_ohlc_file}"); return
#
#         if df_ohlc['Дата'].dt.tz is not None: df_ohlc['Дата'] = df_ohlc['Дата'].dt.tz_convert('UTC')
#         df_filtered = df_ohlc[df_ohlc['Дата'].dt.date >= cutoff_date_utc].copy()
#
#         for col in ['Минимум', 'Максимум', 'Закрытие']: df_filtered[col] = pd.to_numeric(df_filtered[col], errors='coerce')
#         df_filtered.dropna(subset=['Игрок', 'Минимум', 'Максимум', 'Закрытие'], inplace=True)
#         if df_filtered.empty: logging.info("[weekly] Нет OHLC данных за 7 дней."); return
#
#         stats_df = df_filtered.groupby('Игрок').agg(
#              min_7d=('Минимум', 'min'), max_7d=('Максимум', 'max'),
#              sum_close=('Закрытие', 'sum'), count=('Закрытие', 'count')
#         ).reset_index()
#
#         stats_df['avg_close_7d'] = stats_df['sum_close'] / stats_df['count']
#         stats_df['volatility_7d'] = (stats_df['max_7d'] - stats_df['min_7d']) / stats_df['avg_close_7d']
#         stats_df['volatility_7d'].fillna(0, inplace=True)
#
#         output_rows = []
#         header = ["Неделя_конец", "Игрок", "Мин_7дн", "Макс_7дн", "Среднее_Закрытие_7дн", "Дней_учтено", "Волатильность_7дн"]
#         for _, row in stats_df.iterrows():
#             output_rows.append({
#                 "Неделя_конец": end_week_str, "Игрок": row['Игрок'],
#                 "Мин_7дн": f"{row['min_7d']:.1f}", "Макс_7дн": f"{row['max_7d']:.1f}",
#                 "Среднее_Закрытие_7дн": f"{row['avg_close_7d']:.1f}",
#                 "Дней_учтено": int(row['count']), "Волатильность_7дн": f"{row['volatility_7d']:.2f}" })
#
#         # --- Логика ДОЗАПИСИ ---
#         os.makedirs(REPORTS_DIR_WEEKLY, exist_ok=True)
#         out_file = os.path.join(REPORTS_DIR_WEEKLY, "weekly_summary.csv")
#         file_exists = os.path.isfile(out_file)
#         write_header = not file_exists or os.path.getsize(out_file) == 0
#
#         with open(out_file, mode="a", newline="", encoding="utf-8") as f: # Режим "a"
#             writer = csv.DictWriter(f, fieldnames=header)
#             if write_header: writer.writeheader()
#             writer.writerows(output_rows)
#
#         logging.info(f"[weekly] Сводка ({len(output_rows)} игр.) ДОПИСАНА в {out_file} (нед. {end_week_str})")
#
#     except Exception as e: logging.error(f"[weekly] Ошибка недельной сводки: {e}", exc_info=True)
#
# if __name__ == "__main__":
#     logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
#     finalize_weekly_summary()
# =============================================
# ФАЙЛ: weekly_stats.py (ВЕРСИЯ v2.1 - Функция переименована)
# - ОСНОВА: Версия v2
# - ИСПРАВЛЕНО: Функция finalize_weekly_summary переименована в
#               generate_weekly_stats_report, чтобы соответствовать
#               вызовам и проверкам в scraper.py.
# =============================================
import os
import csv
import logging
from datetime import datetime, timedelta, timezone
from collections import defaultdict
import pandas as pd
import config # Убедитесь, что он импортирован

logger = logging.getLogger(__name__) # Добавил инициализацию логгера

# Используем константу из config
EXPECTED_HEADER_OHLC = config.EXPECTED_HEADER_OHLC
REPORTS_DIR_DAILY = getattr(config, 'REPORTS_DIR', "daily_reports")
REPORTS_DIR_WEEKLY = "weekly_reports"

# --- ИСПРАВЛЕНО: Функция переименована ---
def generate_weekly_stats_report():
    """
    Агрегирует недельные данные из дневного OHLC отчета
    и ДОПИСЫВАЕТ их в weekly_summary.csv.
    (Ранее называлась finalize_weekly_summary)
    """
    daily_ohlc_file = os.path.join(REPORTS_DIR_DAILY, "daily_summary_corrected.csv")
    if not os.path.isfile(daily_ohlc_file):
        logging.warning(f"[weekly] Файл {daily_ohlc_file} не найден.")
        return

    now_utc = datetime.now(timezone.utc)
    cutoff_date_utc = (now_utc - timedelta(days=7)).date()
    end_week_str = now_utc.strftime("%Y-%m-%d") # Дата генерации отчета

    try:
        df_ohlc = pd.read_csv(daily_ohlc_file, parse_dates=['Дата'])
        # Используем config.EXPECTED_HEADER_OHLC для проверки
        if not set(config.EXPECTED_HEADER_OHLC).issubset(set(df_ohlc.columns)):
            logging.error(f"[weekly] Неверный заголовок в {daily_ohlc_file}. Ожидался подмножество: {config.EXPECTED_HEADER_OHLC}, Найден: {df_ohlc.columns.tolist()}")
            return

        # Обработка Timezone
        if df_ohlc['Дата'].dt.tz is None:
            df_ohlc['Дата'] = df_ohlc['Дата'].dt.tz_localize('UTC', ambiguous='infer', nonexistent='shift_forward')
        else:
            df_ohlc['Дата'] = df_ohlc['Дата'].dt.tz_convert('UTC')

        df_filtered = df_ohlc[df_ohlc['Дата'].dt.date >= cutoff_date_utc].copy()

        # Преобразование в числа перед агрегацией
        for col in ['Минимум', 'Максимум', 'Закрытие']:
            df_filtered[col] = pd.to_numeric(df_filtered[col], errors='coerce')
        df_filtered.dropna(subset=['Игрок', 'Минимум', 'Максимум', 'Закрытие'], inplace=True)

        if df_filtered.empty:
            logging.info("[weekly] Нет OHLC данных за последние 7 дней для генерации недельной сводки.")
            return

        stats_df = df_filtered.groupby('Игрок').agg(
             min_7d=('Минимум', 'min'),
             max_7d=('Максимум', 'max'),
             sum_close=('Закрытие', 'sum'), # Сумма для расчета среднего
             count=('Закрытие', 'count')    # Количество записей (дней)
        ).reset_index()

        # Расчет средней цены и волатильности
        stats_df['avg_close_7d'] = stats_df['sum_close'] / stats_df['count']
        # Убедимся, что avg_close_7d не ноль перед делением
        stats_df['volatility_7d'] = np.where(
            stats_df['avg_close_7d'] != 0,
            (stats_df['max_7d'] - stats_df['min_7d']) / stats_df['avg_close_7d'],
            0 # Если среднее 0, волатильность тоже 0
        )
        stats_df['volatility_7d'].fillna(0, inplace=True) # Заполняем возможные NaN (хотя where должен помочь)

        output_rows = []
        header = ["Неделя_конец", "Игрок", "Мин_7дн", "Макс_7дн", "Среднее_Закрытие_7дн", "Дней_учтено", "Волатильность_7дн"]
        for _, row in stats_df.iterrows():
            output_rows.append({
                "Неделя_конец": end_week_str,
                "Игрок": row['Игрок'],
                # Форматируем с проверкой на NaN и как числа
                "Мин_7дн": f"{row['min_7d']:,.0f}".replace(",", "\u00A0") if pd.notna(row['min_7d']) else 'N/A',
                "Макс_7дн": f"{row['max_7d']:,.0f}".replace(",", "\u00A0") if pd.notna(row['max_7d']) else 'N/A',
                "Среднее_Закрытие_7дн": f"{row['avg_close_7d']:,.0f}".replace(",", "\u00A0") if pd.notna(row['avg_close_7d']) else 'N/A',
                "Дней_учтено": int(row['count']),
                "Волатильность_7дн": f"{row['volatility_7d']:.2%}" if pd.notna(row['volatility_7d']) else 'N/A' # Формат процента
            })

        # --- Логика ДОЗАПИСИ ---
        os.makedirs(REPORTS_DIR_WEEKLY, exist_ok=True)
        out_file = os.path.join(REPORTS_DIR_WEEKLY, "weekly_summary.csv")
        file_exists = os.path.isfile(out_file)
        write_header = not file_exists or os.path.getsize(out_file) == 0

        with open(out_file, mode="a", newline="", encoding="utf-8") as f: # Режим "a"
            writer = csv.DictWriter(f, fieldnames=header)
            if write_header:
                writer.writeheader()
            writer.writerows(output_rows)

        logging.info(f"[weekly] Сводка ({len(output_rows)} игр.) ДОПИСАНА в {out_file} (нед. {end_week_str})")

    except FileNotFoundError:
        logging.error(f"[weekly] Не найден файл OHLC: {daily_ohlc_file}")
    except KeyError as e:
         logging.error(f"[weekly] Отсутствует ожидаемый столбец в {daily_ohlc_file}: {e}", exc_info=True)
    except Exception as e:
        logging.error(f"[weekly] Ошибка генерации недельной сводки: {e}", exc_info=True)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s')
    generate_weekly_stats_report() # <--- ИСПРАВЛЕНО: Вызываем новую функцию