# # # =============================================
# # # ФАЙЛ: ohlc_generator.py (ФИНАЛЬНАЯ ВЕРСИЯ - дозапись daily_summary)
# # # =============================================
# # import os
# # import csv
# # import logging
# # from datetime import datetime, timedelta, timezone
# # from collections import defaultdict
# # import cycle_analysis # Использует ИСПРАВЛЕННУЮ версию
# # import config
# #
# # # Используем основной логгер
# # DATA_DIR = getattr(config, 'DATA_DIR', 'data')
# # REPORTS_DIR = "daily_reports" # Папка для дневных отчетов
# #
# # # Ожидаемый заголовок для daily_summary_corrected.csv
# # EXPECTED_HEADER_OHLC = [
# #     "Игрок", "Дата",
# #     "Открытие", "Время открытия",
# #     "Минимум", "Время минимума",
# #     "Максимум", "Время максимума",
# #     "Закрытие", "Время закрытия",
# #     "Изменение цены (%)", "Средняя цена",
# #     "Всего объёмов", "Сделок" # Эти колонки могут быть пустыми
# # ]
# #
# # def get_previous_day_data(player_name, target_date_dt):
# #     """Читает историю игрока за указанную дату."""
# #     history = cycle_analysis.read_player_history(player_name) # Читает aware UTC datetime
# #     if not history: return []
# #     target_date = target_date_dt.date() # Сравниваем только по дате
# #     # Фильтруем по дате, сравнивая date() часть aware datetime
# #     day_data = [row for row in history if row['date'].date() == target_date and row.get('price') is not None]
# #     day_data.sort(key=lambda x: x['date']) # Убедимся, что отсортировано по времени
# #     return day_data
# #
# # def calculate_ohlc_and_stats(day_data):
# #     """Рассчитывает OHLC и статистику для данных одного дня."""
# #     if not day_data: return None
# #     prices = [row['price'] for row in day_data]
# #     open_price = prices[0]
# #     close_price = prices[-1]
# #     min_price = min(prices)
# #     max_price = max(prices)
# #     avg_price = sum(prices) / len(prices) if prices else 0
# #
# #     # Находим время для экстремумов и открытия/закрытия (используем UTC время)
# #     open_time = day_data[0]['date'].strftime("%H:%M:%S")
# #     close_time = day_data[-1]['date'].strftime("%H:%M:%S")
# #     min_time = next((row['date'].strftime("%H:%M:%S") for row in day_data if abs(row['price'] - min_price) < 1e-9), open_time)
# #     max_time = next((row['date'].strftime("%H:%M:%S") for row in day_data if abs(row['price'] - max_price) < 1e-9), open_time)
# #
# #
# #     # Расчет изменения цены (требует данных предыдущего дня, пока заглушка)
# #     # TODO: Реализовать получение цены закрытия предыдущего дня для корректного расчета %
# #     prev_close_price = None # Заглушка
# #     price_change_pct = 0.0
# #     if prev_close_price is not None and prev_close_price > 1e-9:
# #         try:
# #             price_change_pct = ((close_price - prev_close_price) / prev_close_price * 100)
# #         except TypeError: # На случай если close_price None
# #             price_change_pct = 0.0
# #
# #     return {
# #         "Открытие": open_price, "Время открытия": open_time,
# #         "Минимум": min_price, "Время минимума": min_time,
# #         "Максимум": max_price, "Время максимума": max_time,
# #         "Закрытие": close_price, "Время закрытия": close_time,
# #         "Изменение цены (%)": f"{price_change_pct:.2f}%", # Форматируем процент
# #         "Средняя цена": avg_price,
# #         "Всего объёмов": 0, # Заглушка
# #         "Сделок": len(prices) # Количество записей за день
# #     }
# #
# # # --- ИСПРАВЛЕНО для ДОЗАПИСИ ---
# # def rewrite_ohlc_summary():
# #     """
# #     Рассчитывает дневные OHLC за ВЧЕРА и ДОПИСЫВАЕТ в daily_summary_corrected.csv.
# #     """
# #     os.makedirs(REPORTS_DIR, exist_ok=True)
# #     output_file = os.path.join(REPORTS_DIR, "daily_summary_corrected.csv")
# #     # Определяем вчерашнюю дату в UTC
# #     yesterday_dt_utc = datetime.now(timezone.utc) - timedelta(days=1)
# #     yesterday_date_str = yesterday_dt_utc.strftime("%Y-%m-%d")
# #     logging.info(f"[OHLC] Расчет OHLC за {yesterday_date_str}")
# #
# #     all_players = cycle_analysis.get_all_players()
# #     if not all_players: logging.warning("[OHLC] Нет игроков."); return
# #
# #     calculated_data = []
# #     for player in all_players:
# #         # Передаем datetime объект для корректного сравнения дат
# #         day_history = get_previous_day_data(player, yesterday_dt_utc)
# #         if day_history:
# #             ohlc_stats = calculate_ohlc_and_stats(day_history)
# #             if ohlc_stats:
# #                 row_data = {"Игрок": player, "Дата": yesterday_date_str}
# #                 row_data.update(ohlc_stats)
# #                 calculated_data.append(row_data)
# #         else:
# #              logging.debug(f"[OHLC] Нет данных за {yesterday_date_str} для {player}")
# #
# #     if not calculated_data:
# #         logging.warning(f"[OHLC] Не удалось рассчитать OHLC ни для одного игрока за {yesterday_date_str}.")
# #         return
# #
# #     # --- Логика ДОЗАПИСИ ---
# #     try:
# #         file_exists = os.path.isfile(output_file)
# #         # Заголовок пишем, только если файл не существует или пустой
# #         write_header = not file_exists or os.path.getsize(output_file) == 0
# #
# #         # Открываем файл в режиме 'a' (append)
# #         with open(output_file, mode="a", newline="", encoding="utf-8") as f:
# #             writer = csv.DictWriter(f, fieldnames=EXPECTED_HEADER_OHLC)
# #             if write_header:
# #                 writer.writeheader()
# #             # Пишем рассчитанные строки
# #             for row_dict in calculated_data:
# #                  # Убедимся, что все ключи из заголовка присутствуют (добавим пустые, если нет)
# #                  full_row = {header: row_dict.get(header, '') for header in EXPECTED_HEADER_OHLC}
# #                  writer.writerow(full_row)
# #
# #         logging.info(f"[OHLC] Данные за {yesterday_date_str} ({len(calculated_data)} игр.) ДОПИСАНЫ в {output_file}")
# #
# #     except IOError as e:
# #         logging.error(f"[OHLC] Ошибка записи в {output_file}: {e}")
# #     except Exception as e:
# #         logging.error(f"[OHLC] Неизвестная ошибка при записи OHLC: {e}", exc_info=True)
# #
# # # --- Точка входа ---
# # if __name__ == "__main__":
# #     logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s')
# #     rewrite_ohlc_summary()
#
# # # =============================================
# # # ФАЙЛ: ohlc_generator.py (ВЕРСИЯ v2 - Фикс циклического импорта)
# # # - Удалено определение EXPECTED_HEADER_OHLC
# # # - Используется config.EXPECTED_HEADER_OHLC
# # # - Добавлен import config
# # # =============================================
# # import os
# # import csv
# # import logging
# # from datetime import datetime, timedelta, timezone
# # from collections import defaultdict
# # import cycle_analysis # Использует ИСПРАВЛЕННУЮ версию v5
# # import config # <--- ДОБАВЛЕНО
# #
# # # Используем основной логгер
# # DATA_DIR = getattr(config, 'DATA_DIR', 'data')
# # REPORTS_DIR = getattr(config, 'REPORTS_DIR', "daily_reports") # Используем из config
# #
# # # Ожидаемый заголовок для daily_summary_corrected.csv
# # # EXPECTED_HEADER_OHLC = [ ... ] # <--- УДАЛЕНО ОПРЕДЕЛЕНИЕ
# #
# # def get_previous_day_data(player_name, target_date_dt):
# #     """Читает историю игрока за указанную дату."""
# #     history = cycle_analysis.read_player_history(player_name) # Читает aware UTC datetime
# #     if not history: return []
# #     target_date = target_date_dt.date() # Сравниваем только по дате
# #     # Фильтруем по дате, сравнивая date() часть aware datetime
# #     day_data = [row for row in history if row['date'].date() == target_date and row.get('price') is not None]
# #     day_data.sort(key=lambda x: x['date']) # Убедимся, что отсортировано по времени
# #     return day_data
# #
# # def calculate_ohlc_and_stats(day_data):
# #     """Рассчитывает OHLC и статистику для данных одного дня."""
# #     if not day_data: return None
# #     prices = [row['price'] for row in day_data]
# #     open_price = prices[0]
# #     close_price = prices[-1]
# #     min_price = min(prices)
# #     max_price = max(prices)
# #     avg_price = sum(prices) / len(prices) if prices else 0
# #
# #     # Находим время для экстремумов и открытия/закрытия (используем UTC время)
# #     open_time = day_data[0]['date'].strftime("%H:%M:%S")
# #     close_time = day_data[-1]['date'].strftime("%H:%M:%S")
# #     min_time = next((row['date'].strftime("%H:%M:%S") for row in day_data if abs(row['price'] - min_price) < 1e-9), open_time)
# #     max_time = next((row['date'].strftime("%H:%M:%S") for row in day_data if abs(row['price'] - max_price) < 1e-9), open_time)
# #
# #     prev_close_price = None # Заглушка
# #     price_change_pct = 0.0
# #     if prev_close_price is not None and prev_close_price > 1e-9:
# #         try:
# #             price_change_pct = ((close_price - prev_close_price) / prev_close_price * 100)
# #         except TypeError:
# #             price_change_pct = 0.0
# #
# #     return {
# #         "Открытие": open_price, "Время открытия": open_time,
# #         "Минимум": min_price, "Время минимума": min_time,
# #         "Максимум": max_price, "Время максимума": max_time,
# #         "Закрытие": close_price, "Время закрытия": close_time,
# #         "Изменение цены (%)": f"{price_change_pct:.2f}%", # Форматируем процент
# #         "Средняя цена": avg_price,
# #         "Всего объёмов": 0, # Заглушка
# #         "Сделок": len(prices) # Количество записей за день
# #     }
# #
# # # --- ИСПРАВЛЕНО для ДОЗАПИСИ ---
# # def rewrite_ohlc_summary():
# #     """
# #     Рассчитывает дневные OHLC за ВЧЕРА и ДОПИСЫВАЕТ в daily_summary_corrected.csv.
# #     """
# #     os.makedirs(REPORTS_DIR, exist_ok=True)
# #     output_file = os.path.join(REPORTS_DIR, "daily_summary_corrected.csv")
# #     yesterday_dt_utc = datetime.now(timezone.utc) - timedelta(days=1)
# #     yesterday_date_str = yesterday_dt_utc.strftime("%Y-%m-%d")
# #     logging.info(f"[OHLC] Расчет OHLC за {yesterday_date_str}")
# #
# #     # all_players = cycle_analysis.get_all_players()
# #     # --- Получаем список игроков из config ---
# #     try:
# #         import config  # Убедимся, что config импортирован
# #         players_dict = config.load_players()
# #         if players_dict:
# #             all_players = list(players_dict.keys())
# #         else:
# #             logging.error("[OHLC] Не удалось загрузить список игроков из config.")
# #             all_players = []
# #     except ImportError:
# #         logging.error("[OHLC] Не удалось импортировать config для получения списка игроков.")
# #         all_players = []
# #     except Exception as e:
# #         logging.error(f"[OHLC] Ошибка при получении списка игроков из config: {e}")
# #         all_players = []
# #     # ---------------------------------------
# #     if not all_players: logging.warning("[OHLC] Нет игроков."); return
# #
# #     calculated_data = []
# #     for player in all_players:
# #         day_history = get_previous_day_data(player, yesterday_dt_utc)
# #         if day_history:
# #             ohlc_stats = calculate_ohlc_and_stats(day_history)
# #             if ohlc_stats:
# #                 row_data = {"Игрок": player, "Дата": yesterday_date_str}
# #                 row_data.update(ohlc_stats)
# #                 calculated_data.append(row_data)
# #         else:
# #              logging.debug(f"[OHLC] Нет данных за {yesterday_date_str} для {player}")
# #
# #     if not calculated_data:
# #         logging.warning(f"[OHLC] Не удалось рассчитать OHLC ни для одного игрока за {yesterday_date_str}.")
# #         return
# #
# #     try:
# #         file_exists = os.path.isfile(output_file)
# #         write_header = not file_exists or os.path.getsize(output_file) == 0
# #
# #         with open(output_file, mode="a", newline="", encoding="utf-8") as f:
# #             # Используем константу из config
# #             writer = csv.DictWriter(f, fieldnames=config.EXPECTED_HEADER_OHLC) # <--- ИЗМЕНЕНО
# #             if write_header:
# #                 writer.writeheader()
# #             for row_dict in calculated_data:
# #                  # Используем константу из config
# #                  full_row = {header: row_dict.get(header, '') for header in config.EXPECTED_HEADER_OHLC} # <--- ИЗМЕНЕНО
# #                  writer.writerow(full_row)
# #
# #         logging.info(f"[OHLC] Данные за {yesterday_date_str} ({len(calculated_data)} игр.) ДОПИСАНЫ в {output_file}")
# #
# #     except IOError as e:
# #         logging.error(f"[OHLC] Ошибка записи в {output_file}: {e}")
# #     except Exception as e:
# #         logging.error(f"[OHLC] Неизвестная ошибка при записи OHLC: {e}", exc_info=True)
# #
# # # --- Точка входа ---
# # if __name__ == "__main__":
# #     logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s')
# #     rewrite_ohlc_summary()
#
# # =============================================
# # ФАЙЛ: ohlc_generator.py (ВЕРСИЯ v3.1 - Fix NameError np)
# # - ДОБАВЛЕН import numpy as np.
# # - Используется config.load_players() для списка игроков.
# # - Используется storage.read_player_history() для чтения данных.
# # =============================================
# import os
# import csv
# import logging
# from datetime import datetime, timedelta, timezone
# import pandas as pd
# import numpy as np # <-- ДОБАВЛЕН ИМПОРТ NUMPY
#
# # --- Импортируем нужные модули ---
# try:
#     import config
#     import storage
# except ImportError as e:
#      logging.critical(f"Не удалось импортировать config или storage в ohlc_generator: {e}")
#      exit()
#
# # --- Настройки ---
# logger = logging.getLogger("ohlc_generator")
# DATA_DIR = getattr(config, 'DATA_DIR', 'data')
# OHLC_DIR = getattr(config, 'OHLC_DIR', os.path.join(DATA_DIR, 'ohlc'))
# EXPECTED_HEADER_OHLC = getattr(config, 'EXPECTED_HEADER_OHLC', ['Player', 'Date', 'Open', 'High', 'Low', 'Close', 'Volume'])
# # ------------------
#
# def get_previous_day_data_df(player_name: str, target_date_dt: datetime):
#     logger.debug(f"Чтение истории для {player_name}...")
#     history_df = storage.read_player_history(player_name, min_rows=1, usecols=['Дата', 'Время', 'Цена'])
#     if history_df is None or history_df.empty: logger.debug(f"Нет истории для {player_name}."); return None
#     if not isinstance(history_df.index, pd.DatetimeIndex) or history_df.index.tz != timezone.utc:
#          logger.warning(f"Индекс для {player_name} некорректен. Попытка конвертации...")
#          try:
#              if not isinstance(history_df.index, pd.DatetimeIndex): history_df.index = pd.to_datetime(history_df.index, errors='coerce'); history_df = history_df[history_df.index.notna()]
#              if history_df.index.tz is None: history_df = history_df.tz_localize('UTC')
#              else: history_df = history_df.tz_convert('UTC')
#              if not isinstance(history_df.index, pd.DatetimeIndex): raise TypeError("Index conversion failed")
#          except Exception as e_conv: logger.error(f"Не преобразовать индекс {player_name}: {e_conv}"); return None
#     target_date = target_date_dt.date()
#     logger.debug(f"Фильтрация {player_name} за {target_date}")
#     day_data_df = history_df[history_df.index.date == target_date]
#     if day_data_df.empty: logger.debug(f"Нет данных за {target_date} для {player_name}."); return None
#     if not pd.api.types.is_numeric_dtype(day_data_df['Цена']):
#         logger.warning(f"Колонка 'Цена' {player_name} не числовая."); day_data_df['Цена'] = pd.to_numeric(day_data_df['Цена'], errors='coerce'); day_data_df.dropna(subset=['Цена'], inplace=True)
#     if day_data_df.empty: logger.warning(f"Нет валидных цен за {target_date} для {player_name}."); return None
#     logger.debug(f"Найдено {len(day_data_df)} записей за {target_date} для {player_name}.")
#     return day_data_df.sort_index()
#
# def calculate_ohlc_and_stats_df(day_data_df):
#     if day_data_df is None or day_data_df.empty: return None
#     prices = day_data_df['Цена']
#     try:
#         open_price = prices.iloc[0]; close_price = prices.iloc[-1]; min_price = prices.min(); max_price = prices.max(); avg_price = prices.mean(); num_trades = len(prices)
#         open_time = prices.index[0].strftime("%H:%M:%S"); close_time = prices.index[-1].strftime("%H:%M:%S")
#         min_time_idx = prices.idxmin(); max_time_idx = prices.idxmax()
#         min_time = min_time_idx.strftime("%H:%M:%S"); max_time = max_time_idx.strftime("%H:%M:%S")
#         price_change_pct = 0.0 # Заглушка
#         return {"Открытие": open_price, "Время открытия": open_time, "Минимум": min_price, "Время минимума": min_time, "Максимум": max_price, "Время максимума": max_time, "Закрытие": close_price, "Время закрытия": close_time, "Изменение цены (%)": f"{price_change_pct:.2f}%", "Средняя цена": avg_price, "Всего объёмов": 0, "Сделок": num_trades}
#     except Exception as e: logger.error(f"Ошибка расчета OHLC: {e}", exc_info=True); return None
#
# def rewrite_ohlc_summary():
#     os.makedirs(OHLC_DIR, exist_ok=True)
#     output_file = os.path.join(OHLC_DIR, "daily_summary_corrected.csv")
#     yesterday_dt_utc = datetime.now(timezone.utc) - timedelta(days=1)
#     yesterday_date_str = yesterday_dt_utc.strftime("%Y-%m-%d")
#     logger.info(f"[OHLC] Расчет OHLC за {yesterday_date_str}")
#     try: players_dict = config.load_players(); all_players = list(players_dict.keys()) if players_dict else []
#     except Exception as e: logger.error(f"[OHLC] Ошибка загрузки игроков: {e}"); all_players = []
#     if not all_players: logger.warning("[OHLC] Список игроков пуст."); return
#     calculated_data = []
#     for player in all_players:
#         logger.debug(f"[OHLC] Обработка: {player}")
#         day_history_df = get_previous_day_data_df(player, yesterday_dt_utc)
#         if day_history_df is not None and not day_history_df.empty:
#             ohlc_stats = calculate_ohlc_and_stats_df(day_history_df)
#             if ohlc_stats:
#                 row_data = {"Игрок": player, "Дата": yesterday_date_str}
#                 for key, value in ohlc_stats.items():
#                      if isinstance(value, (int, float, np.number)) and key not in ["Сделок"]: # Используем np.number
#                          if key in ["Открытие", "Минимум", "Максимум", "Закрытие", "Средняя цена"]: row_data[key] = storage.format_price(value)
#                          else: row_data[key] = f"{value:.2f}"
#                      else: row_data[key] = value
#                 calculated_data.append(row_data)
#     if not calculated_data: logger.warning(f"[OHLC] Не рассчитать OHLC за {yesterday_date_str}."); return
#     try:
#         file_exists = os.path.isfile(output_file); write_header = not file_exists or os.path.getsize(output_file) == 0
#         if not EXPECTED_HEADER_OHLC: logger.error("[OHLC] Заголовок не определен в config!"); return
#         with open(output_file, mode="a", newline="", encoding="utf-8") as f:
#             writer = csv.DictWriter(f, fieldnames=EXPECTED_HEADER_OHLC, extrasaction='ignore')
#             if write_header: writer.writeheader()
#             writer.writerows(calculated_data)
#         logging.info(f"[OHLC] Данные за {yesterday_date_str} ({len(calculated_data)} игр.) ДОПИСАНЫ в {output_file}")
#     except IOError as e: logger.error(f"[OHLC] Ошибка записи {output_file}: {e}")
#     except Exception as e: logger.error(f"[OHLC] Ошибка записи OHLC: {e}", exc_info=True)
#
# if __name__ == "__main__":
#     logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - [%(name)s] - [%(filename)s:%(lineno)d] - %(message)s', handlers=[logging.StreamHandler(sys.stdout)])
#     logger.info("Запуск ohlc_generator автономно...")
#     rewrite_ohlc_summary()
#     logger.info("Завершение ohlc_generator.")

# =============================================
# ФАЙЛ: ohlc_generator.py (ВЕРСИЯ v3.3 - Correct Header & Data Alignment)
# - ИСПРАВЛЕНО: Заголовок CSV теперь пишется из config.EXPECTED_HEADER_OHLC.
# - ИСПРАВЛЕНО: Порядок и состав данных в записываемых строках теперь
#   соответствуют EXPECTED_HEADER_OHLC (14 колонок).
# - ИСПРАВЛЕНО: Обработка отсутствующих данных для колонок времени.
# - Улучшено логирование.
# - Содержит исправления из v3.2.
# =============================================

import os
import pandas as pd
from datetime import datetime, timedelta, timezone
import logging
import csv
import numpy as np # Для np.nan

# --- Импорт пользовательских модулей ---
try:
    import config
    import storage
except ImportError:
    logging.basicConfig(level=logging.ERROR)
    logging.critical("Не удалось импортировать config или storage в ohlc_generator.py")
    raise

logger = logging.getLogger("ohlc_generator")
OHLC_DIR = getattr(config, 'OHLC_DIR', os.path.join(config.DATA_DIR, 'ohlc'))
OHLC_SUMMARY_FILE = getattr(config, 'OHLC_SUMMARY_FILE', os.path.join(OHLC_DIR, 'daily_summary_corrected.csv'))
EXPECTED_HEADER = getattr(config, 'EXPECTED_HEADER_OHLC', []) # Получаем актуальный заголовок

if not EXPECTED_HEADER:
     logger.critical("Критическая ошибка: EXPECTED_HEADER_OHLC не найден или пуст в config.py!")
     # Устанавливаем заголовок по умолчанию, чтобы избежать падения, но это плохо
     EXPECTED_HEADER = ['Player', 'Date', 'Open', 'High', 'Low', 'Close', 'Avg Price', 'Trades', 'Volume', 'Price Change Pct', 'Open Time', 'High Time', 'Low Time', 'Close Time']


def calculate_daily_data(player_name, target_date):
    """
    Рассчитывает OHLC и другие данные для одного игрока за указанную дату.
    Возвращает словарь с данными, соответствующими EXPECTED_HEADER_OHLC.
    """
    df = storage.read_player_history(player_name, min_rows=1) # Читаем всю доступную историю
    if df is None or df.empty:
        logger.warning(f"[{player_name}] Нет истории для расчета OHLC.")
        return None

    # Убедимся, что индекс - datetime и в UTC
    if not isinstance(df.index, pd.DatetimeIndex):
        logger.error(f"[{player_name}] Индекс не DatetimeIndex в истории.")
        return None
    if df.index.tz is None:
        df = df.tz_localize('UTC')
    elif df.index.tz != timezone.utc:
        df = df.tz_convert('UTC')

    # Фильтруем данные за нужный день
    # Сравниваем только дату, без времени
    daily_df = df[df.index.date == target_date].copy() # Используем .date для сравнения

    if daily_df.empty:
        logger.debug(f"[{player_name}] Нет данных за {target_date.strftime('%Y-%m-%d')}.")
        return None

    logger.debug(f"  -> Найдено {len(daily_df)} записей.")

    # Убедимся, что колонка 'Цена' числовая
    if 'Цена' not in daily_df.columns or not pd.api.types.is_numeric_dtype(daily_df['Цена']):
         logger.error(f"[{player_name}] Колонка 'Цена' отсутствует или не числовая.")
         # Попытка конвертации, если возможно
         if 'Цена' in daily_df.columns:
             daily_df['Цена'] = pd.to_numeric(daily_df['Цена'], errors='coerce')
             daily_df.dropna(subset=['Цена'], inplace=True)
             if daily_df.empty:
                 logger.error(f"[{player_name}] Нет валидных цен после конвертации.")
                 return None
         else: return None


    # Расчет OHLC
    open_price = daily_df['Цена'].iloc[0]
    high_price = daily_df['Цена'].max()
    low_price = daily_df['Цена'].min()
    close_price = daily_df['Цена'].iloc[-1]

    # Расчет среднего, объема и кол-ва сделок
    # Простое среднее по имеющимся записям
    avg_price = daily_df['Цена'].mean()
    # Количество записей = количество "сделок"
    trades = len(daily_df)
    # Объем - простая сумма цен (или нужно другое определение?)
    volume = daily_df['Цена'].sum()

    # Расчет изменения цены (Close - Open) / Open * 100
    price_change_pct = ((close_price - open_price) / open_price * 100) if open_price else 0

    # Определение времени O H L C
    try: open_time = daily_df.index[0].strftime('%H:%M:%S')
    except IndexError: open_time = ''

    try: high_idx = daily_df['Цена'].idxmax(); high_time = high_idx.strftime('%H:%M:%S') if pd.notna(high_idx) else ''
    except ValueError: high_time = '' # Если idxmax не находит (пустой df - уже обработано)
    except AttributeError: high_time = '' # Если high_idx не datetime

    try: low_idx = daily_df['Цена'].idxmin(); low_time = low_idx.strftime('%H:%M:%S') if pd.notna(low_idx) else ''
    except ValueError: low_time = ''
    except AttributeError: low_time = ''

    try: close_time = daily_df.index[-1].strftime('%H:%M:%S')
    except IndexError: close_time = ''


    # Собираем результат в словарь, соответствующий EXPECTED_HEADER_OHLC
    # Используем '' для отсутствующих числовых данных, чтобы CSV читался без проблем
    result = {
        'Player': player_name,
        'Date': target_date.strftime('%Y-%m-%d'),
        'Open': open_price if pd.notna(open_price) else '',
        'High': high_price if pd.notna(high_price) else '',
        'Low': low_price if pd.notna(low_price) else '',
        'Close': close_price if pd.notna(close_price) else '',
        'Avg Price': round(avg_price) if pd.notna(avg_price) else '',
        'Trades': trades if pd.notna(trades) else '',
        'Volume': volume if pd.notna(volume) else '',
        'Price Change Pct': round(price_change_pct, 2) if pd.notna(price_change_pct) else '',
        'Open Time': open_time,
        'High Time': high_time,
        'Low Time': low_time,
        'Close Time': close_time
    }
    logger.debug(f"  -> OHLC рассчитан (для CSV): { {k:v for k,v in result.items() if k in ['Player', 'Date']} }") # Логируем только имя и дату для краткости
    return result


def generate_daily_ohlc_report(target_date=None, player_names=None):
    """
    Генерирует или дописывает OHLC отчет за указанную дату (или вчерашнюю).
    Возвращает True в случае успеха, False в случае ошибки.
    """
    logger.info("Запуск генерации OHLC отчета...")
    if target_date is None:
        # Берем вчерашнюю дату по UTC
        target_date = (datetime.now(timezone.utc) - timedelta(days=1)).date()
    elif isinstance(target_date, datetime):
        target_date = target_date.date() # Оставляем только дату
    elif not isinstance(target_date, datetime.date):
         logger.error(f"Некорректный формат target_date: {target_date}. Ожидается date или datetime.")
         return False

    target_date_str = target_date.strftime('%Y-%m-%d')
    logger.info(f"[OHLC] Расчет OHLC за {target_date_str}")

    if player_names is None:
        logger.warning("[OHLC] Список игроков не предоставлен. Попытка загрузить из config...")
        players_config = config.load_players()
        if not players_config:
            logger.error("[OHLC] Не удалось загрузить список игроков из config. Генерация отчета прервана.")
            return False
        player_names = list(players_config.keys())
        if not player_names:
             logger.error("[OHLC] Список игроков пуст. Генерация отчета прервана.")
             return False
        logger.info(f"[OHLC] Загружено {len(player_names)} игроков из config.")

    all_daily_data = []
    processed_count = 0
    total_players = len(player_names)

    for i, player_name in enumerate(player_names):
        logger.debug(f"[OHLC] {i+1}/{total_players} Обработка: {player_name}")
        daily_data = calculate_daily_data(player_name, target_date)
        if daily_data:
            all_daily_data.append(daily_data)
            processed_count += 1
        # Небольшая пауза, чтобы не нагружать чтение файлов
        # time.sleep(0.05)

    if not all_daily_data:
        logger.warning(f"[OHLC] Нет данных для записи за {target_date_str}.")
        return True # Считаем успехом, если просто не было данных

    os.makedirs(OHLC_DIR, exist_ok=True)
    file_exists = os.path.isfile(OHLC_SUMMARY_FILE)

    try:
        # Используем 'a' (append) режим, чтобы дописывать данные
        # Заголовок пишем только если файл не существует
        with open(OHLC_SUMMARY_FILE, 'a', newline='', encoding='utf-8') as csvfile:
            # Используем DictWriter для удобства и соответствия заголовку
            writer = csv.DictWriter(csvfile, fieldnames=EXPECTED_HEADER)

            if not file_exists or os.path.getsize(OHLC_SUMMARY_FILE) == 0:
                logger.info(f"[OHLC] Файл {OHLC_SUMMARY_FILE} не существует или пуст. Запись заголовка.")
                writer.writeheader() # Пишем заголовок из EXPECTED_HEADER

            # Записываем строки данных
            writer.writerows(all_daily_data)

        logger.info(f"[OHLC] Данные за {target_date_str} ({processed_count}/{total_players} игр.) ДОПИСАНЫ в {OHLC_SUMMARY_FILE}")
        return True
    except IOError as e:
        logger.error(f"[OHLC] Ошибка записи в файл {OHLC_SUMMARY_FILE}: {e}", exc_info=True)
        return False
    except Exception as e:
        logger.error(f"[OHLC] Непредвиденная ошибка при записи OHLC отчета: {e}", exc_info=True)
        return False

# Функция для ручного запуска (может быть вызвана из run_daily.py)
def rewrite_ohlc_summary(days=1):
     """Пересчитывает и перезаписывает OHLC отчет за указанное количество прошлых дней."""
     logger.info(f"Запуск перезаписи OHLC отчета за последние {days} дней.")
     today_utc = datetime.now(timezone.utc).date()
     all_players_config = config.load_players()
     if not all_players_config:
         logger.error("Не удалось загрузить игроков для перезаписи OHLC.")
         return False
     player_names = list(all_players_config.keys())

     all_data_to_write = []
     # Сначала собираем все данные за нужные дни
     for i in range(days, 0, -1): # Идем от самого старого дня к самому новому
         target_date = today_utc - timedelta(days=i)
         logger.info(f"Пересчет данных за {target_date.strftime('%Y-%m-%d')}...")
         data_for_day = []
         for player_name in player_names:
             daily_data = calculate_daily_data(player_name, target_date)
             if daily_data:
                 data_for_day.append(daily_data)
         if data_for_day:
             all_data_to_write.extend(data_for_day)
         else:
             logger.info(f"Нет данных за {target_date.strftime('%Y-%m-%d')}.")

     if not all_data_to_write:
         logger.warning("Нет данных для перезаписи OHLC файла.")
         # Очищаем файл, если он существует? Или оставляем старый?
         # Пока оставим старый. Если нужно чистить - добавить os.remove(OHLC_SUMMARY_FILE) здесь
         return True

     # Теперь перезаписываем весь файл
     os.makedirs(OHLC_DIR, exist_ok=True)
     logger.info(f"Перезапись файла: {OHLC_SUMMARY_FILE}")
     try:
         with open(OHLC_SUMMARY_FILE, 'w', newline='', encoding='utf-8') as csvfile: # 'w' - перезапись
             writer = csv.DictWriter(csvfile, fieldnames=EXPECTED_HEADER)
             writer.writeheader() # Пишем заголовок
             writer.writerows(all_data_to_write) # Пишем все собранные данные
         logger.info(f"Файл OHLC успешно перезаписан ({len(all_data_to_write)} строк).")
         return True
     except IOError as e:
         logger.error(f"Ошибка перезаписи файла {OHLC_SUMMARY_FILE}: {e}", exc_info=True)
         return False
     except Exception as e:
         logger.error(f"Непредвиденная ошибка при перезаписи OHLC отчета: {e}", exc_info=True)
         return False


if __name__ == '__main__':
    # Пример ручного запуска генерации за вчера
    logger.info("Ручной запуск генерации OHLC за вчерашний день...")
    # generate_daily_ohlc_report()
    # Пример перезаписи за последние 3 дня
    rewrite_ohlc_summary(days=3)
    logger.info("Генерация OHLC завершена.")