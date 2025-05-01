# # =============================================
# # ФАЙЛ: storage.py (ВЕРСИЯ v6.2 - Исправлена сигнатура save_player_price)
# # - Функция save_player_price теперь принимает 5 аргументов (name, price, change, min, max), как вызывается в scraper.py.
# # - Словарь data_row для записи формируется внутри функции.
# # - Добавлены функции save_purchase_log и load_last_purchase_price.
# # =============================================
#
# import os
# import csv
# import logging
# from datetime import datetime, timedelta, timezone
# import pandas as pd
# import numpy as np
# import json # Добавлено для лога покупок
# import config
#
# DATA_DIR = getattr(config, 'DATA_DIR', 'data')
# LOG_DIR = getattr(config, 'LOG_DIR', 'logs') # Убедитесь, что LOG_DIR определен в config.py
# HISTORY_DAYS_FOR_SIGNALS = getattr(config, 'HISTORY_DAYS_FOR_SIGNALS', 90)
# PREDICTION_LOG_FILE = getattr(config, 'PREDICTION_LOG_FILE', 'predictions.log')
#
# # --- Убедимся, что директории существуют ---
# os.makedirs(DATA_DIR, exist_ok=True)
# os.makedirs(LOG_DIR, exist_ok=True)
#
# # --- Базовые функции работы с CSV ---
#
# def get_player_filepath(player_name):
#     """Создает безопасное имя файла для игрока."""
#     safe_name = "".join(c if c.isalnum() else "_" for c in player_name)
#     max_len = 100
#     safe_name = safe_name[:max_len]
#     return os.path.join(DATA_DIR, f"{safe_name}.csv")
#
# # ИЗМЕНЕНО: Принимает 5 аргументов и формирует data_row внутри
# def save_player_price(player_name: str, price: float | None, change: str, min_v: float | None, max_v: float | None):
#     """Сохраняет строку данных для игрока в CSV."""
#     filepath = get_player_filepath(player_name)
#     file_exists = os.path.isfile(filepath)
#     header = ['Дата', 'Время', 'Цена', 'Изменение', 'Мин. цена', 'Макс. цена']
#
#     # Формируем словарь data_row из переданных аргументов
#     now_dt = datetime.now(timezone.utc)
#     data_row = {
#         'Дата': now_dt.strftime('%Y-%m-%d'),
#         'Время': now_dt.strftime('%H:%M:%S'),
#         'Цена': price if price is not None else '', # Записываем пустую строку, если цена None
#         'Изменение': change if change is not None else '',
#         'Мин. цена': min_v if min_v is not None else '',
#         'Макс. цена': max_v if max_v is not None else ''
#     }
#
#     # Проверяем корректность сформированного словаря (на всякий случай)
#     if not isinstance(data_row, dict):
#         logging.error(f"[storage] Ошибка: не удалось сформировать data_row для {player_name}.")
#         return
#
#     row_to_write = {h: data_row.get(h, '') for h in header} # Убедимся, что все ключи заголовка есть
#
#     try:
#         with open(filepath, 'a', newline='', encoding='utf-8') as csvfile:
#             writer = csv.DictWriter(csvfile, fieldnames=header)
#             if not file_exists or os.path.getsize(filepath) == 0:
#                 writer.writeheader()
#                 logging.info(f"[storage] Создан файл и записан заголовок: {filepath}")
#             writer.writerow(row_to_write)
#         logging.debug(f"[storage] Данные {player_name} сохранены в {filepath} ({len(header)} колонок)")
#     except IOError as e:
#         logging.error(f"[storage] Ошибка записи в файл {filepath}: {e}")
#     except Exception as e:
#         logging.error(f"[storage] Непредвиденная ошибка при сохранении данных {player_name}: {e}", exc_info=True)
#
#
# def get_recent_prices(player_name: str, days: int = HISTORY_DAYS_FOR_SIGNALS) -> list:
#     """
#     Читает историю цен игрока за последние N дней из CSV файла с помощью Pandas.
#     Возвращает список цен (float).
#     Версия 5: Улучшена обработка ошибок чтения и типов данных.
#     """
#     filepath = get_player_filepath(player_name)
#     logging.debug(f"[get] Чтение {filepath} за {days} дней (Pandas v5)")
#     if not os.path.exists(filepath):
#         logging.warning(f"[get] Файл истории не найден: {filepath}")
#         return []
#
#     try:
#         # Используем Pandas для чтения, он более устойчив к разным форматам
#         df = pd.read_csv(filepath, sep=',', encoding='utf-8', low_memory=False, on_bad_lines='warn')
#         logging.debug(f"[get] Прочитано строк Pandas: {len(df)} из {filepath}")
#
#         # Проверяем наличие необходимых колонок
#         if 'Дата' not in df.columns or 'Время' not in df.columns or 'Цена' not in df.columns:
#              # Попытка прочитать без заголовка, предполагая порядок Дата, Время, Цена
#              try:
#                  df = pd.read_csv(filepath, sep=',', encoding='utf-8', header=None, low_memory=False, on_bad_lines='warn')
#                  num_cols = df.shape[1]
#                  col_names = [f'col_{i}' for i in range(num_cols)]
#                  df.columns = col_names
#                  if num_cols >= 3:
#                      df.rename(columns={'col_0': 'Дата', 'col_1': 'Время', 'col_2': 'Цена'}, inplace=True)
#                      logging.warning(f"[get] Заголовок не найден или некорректен в {filepath}. Чтение без заголовка успешно.")
#                  else:
#                       logging.error(f"[get] Недостаточно колонок ({num_cols}) при чтении без заголовка в {filepath}.")
#                       return []
#              except Exception as e_nohead:
#                  logging.error(f"[get] Ошибка чтения {filepath} без заголовка: {e_nohead}")
#                  return []
#
#         # --- Обработка Даты/Времени ---
#         if 'Время' not in df.columns:
#              logging.warning(f"[get] Колонка 'Время' отсутствует в {filepath}. Используем 00:00:00.")
#              df['Время'] = '00:00:00'
#
#         df['Время'] = df['Время'].astype(str).str.replace('24:', '00:', regex=False)
#         # Пытаемся обработать разные форматы даты
#         datetime_formats = ['%Y-%m-%d %H:%M:%S', '%d.%m.%Y %H:%M:%S', '%Y-%m-%d %H:%M'] # Добавьте другие форматы, если нужно
#         df['datetime_str'] = df['Дата'].astype(str) + ' ' + df['Время'].astype(str)
#         df['datetime'] = pd.NaT # Инициализируем как Not a Time
#         for fmt in datetime_formats:
#              try:
#                  # Применяем формат только к тем строкам, где дата еще не распознана
#                  mask = df['datetime'].isna()
#                  df.loc[mask, 'datetime'] = pd.to_datetime(df.loc[mask, 'datetime_str'], errors='coerce', format=fmt)
#              except Exception:
#                  continue # Пробуем следующий формат
#
#         df.dropna(subset=['datetime'], inplace=True)
#
#         # --- Обработка Цены ---
#         if 'Цена' not in df.columns:
#              logging.error(f"[get] Колонка 'Цена' отсутствует в {filepath} после всех попыток.")
#              return []
#
#         df['price_numeric'] = df['Цена'].astype(str).str.replace(r'[^\d.]', '', regex=True)
#         df['price_numeric'] = pd.to_numeric(df['price_numeric'], errors='coerce')
#         df.dropna(subset=['price_numeric'], inplace=True)
#         df['price_numeric'] = df['price_numeric'].astype(float)
#
#         # Фильтрация по дате
#         cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)
#         if df['datetime'].dt.tz is None:
#             try:
#                  df['datetime'] = df['datetime'].dt.tz_localize('UTC')
#             except Exception as tz_err:
#                  logging.warning(f"[get] Не удалось локализовать время в UTC для {filepath}, возможно смешанные timestamp: {tz_err}. Используется наивное сравнение.")
#                  cutoff_date = cutoff_date.replace(tzinfo=None)
#
#         df_filtered = df[df['datetime'] >= cutoff_date].copy()
#         df_filtered.sort_values(by='datetime', inplace=True)
#
#         price_list = df_filtered['price_numeric'].tolist()
#         logging.debug(f"[get] Найдено {len(price_list)} валидных цен для {player_name} за {days} дней.")
#         return price_list
#
#     except pd.errors.EmptyDataError:
#         logging.warning(f"[get] Файл истории пуст: {filepath}")
#         return []
#     except Exception as e:
#         logging.error(f"[get] Ошибка чтения/обработки файла {filepath}: {e}", exc_info=True)
#         return []
#
#
# # --- Логирование предсказаний ---
#
# def log_prediction(player_name, prediction_dt, features, prediction):
#     """Логирует фичи и предсказание модели."""
#     log_filepath = os.path.join(LOG_DIR, PREDICTION_LOG_FILE)
#     file_exists = os.path.isfile(log_filepath)
#
#     log_entry = {
#         'player': player_name,
#         'prediction_dt': datetime.now(timezone.utc).isoformat(),
#         'prediction_for_datetime': prediction_dt.isoformat(),
#         'prediction': prediction,
#     }
#     log_entry.update(features)
#
#     header = list(log_entry.keys())
#
#     try:
#         with open(log_filepath, 'a', newline='', encoding='utf-8') as csvfile:
#             writer = csv.DictWriter(csvfile, fieldnames=header, quoting=csv.QUOTE_MINIMAL)
#             if not file_exists or os.path.getsize(log_filepath) == 0:
#                 writer.writeheader()
#             writer.writerow(log_entry)
#     except Exception as e:
#         logging.error(f"Ошибка записи лога предсказания в {log_filepath}: {e}", exc_info=True)
#
# # === НОВЫЕ Функции для лога покупок (v6) ===
#
# PURCHASE_LOG_FILE = 'purchase_log.json' # Имя файла для лога покупок
#
# def save_purchase_log(player_name: str, buy_price: float, buy_date: datetime):
#     """Сохраняет последнюю предполагаемую цену покупки для игрока."""
#     log_data = {}
#     filepath = os.path.join(DATA_DIR, PURCHASE_LOG_FILE)
#     try:
#         if os.path.exists(filepath):
#             with open(filepath, 'r', encoding='utf-8') as f:
#                 try:
#                     log_data = json.load(f)
#                 except json.JSONDecodeError:
#                     logging.warning(f"Файл лога покупок {filepath} поврежден или пуст. Будет создан/перезаписан.")
#                     log_data = {}
#
#         log_data[player_name] = {
#             'buy_price': buy_price,
#             'buy_date_iso': buy_date.astimezone(timezone.utc).isoformat()
#         }
#
#         with open(filepath, 'w', encoding='utf-8') as f:
#             json.dump(log_data, f, ensure_ascii=False, indent=4)
#         logging.info(f"[storage] Запись о покупке для {player_name} сохранена (Цена: {buy_price:,.0f})".replace(",", "\u00A0"))
#
#     except Exception as e:
#         logging.error(f"[storage] Ошибка сохранения лога покупок {filepath}: {e}", exc_info=True)
#
#
# def load_last_purchase_price(player_name: str) -> float | None:
#     """Загружает последнюю сохраненную цену покупки для игрока."""
#     filepath = os.path.join(DATA_DIR, PURCHASE_LOG_FILE)
#     if not os.path.exists(filepath):
#         logging.debug(f"[storage] Файл лога покупок {filepath} не найден.")
#         return None
#
#     try:
#         with open(filepath, 'r', encoding='utf-8') as f:
#             log_data = json.load(f)
#             player_purchase_info = log_data.get(player_name)
#             if player_purchase_info and 'buy_price' in player_purchase_info:
#                 price = player_purchase_info['buy_price']
#                 if isinstance(price, (int, float)) and np.isfinite(price):
#                     logging.debug(f"[storage] Загружена цена покупки {price:,.0f} для {player_name}".replace(",", "\u00A0"))
#                     return float(price)
#                 else:
#                     logging.warning(f"[storage] Найдена невалидная цена покупки ({price}) для {player_name} в {filepath}.")
#                     return None
#             else:
#                 logging.debug(f"[storage] Нет записи о покупке для {player_name} в {filepath}.")
#                 return None
#     except json.JSONDecodeError:
#         logging.error(f"[storage] Ошибка декодирования JSON в логе покупок {filepath}.")
#         return None
#     except Exception as e:
#         logging.error(f"[storage] Ошибка чтения лога покупок {filepath}: {e}", exc_info=True)
#         return None

# =============================================
# ФАЙЛ: storage.py (ВЕРСИЯ v6.11 - Notification State)
# - ДОБАВЛЕНО: Функции load_notification_state и save_notification_state
#   для работы с файлом состояния уведомлений (последний score).
# - Содержит исправления из v6.10 (numpy type fix).
# =============================================

import csv
import os
import json
import logging
from datetime import datetime, timezone
import pandas as pd
import numpy as np # Используется в format_price через pd.isna
from filelock import FileLock, Timeout

logger = logging.getLogger("storage")

# --- Получение путей из config ---
try:
    import config
    DATA_DIR = getattr(config, 'DATA_DIR', 'data')
    PURCHASE_LOG_FILE = getattr(config, 'PURCHASE_LOG_FILE', os.path.join(DATA_DIR, 'purchase_log.json'))
    UPDATE_SCHEDULE_FILE = getattr(config, 'UPDATE_SCHEDULE_FILE', os.path.join(DATA_DIR, 'update_schedule.json'))
    NOTIFICATION_STATE_FILE = getattr(config, 'NOTIFICATION_STATE_FILE', os.path.join(DATA_DIR, 'notification_state.json'))
except ImportError:
    logger.warning("Не удалось импортировать config. Используются пути по умолчанию."); DATA_DIR='data'; PURCHASE_LOG_FILE=os.path.join(DATA_DIR,'purchase_log.json'); UPDATE_SCHEDULE_FILE=os.path.join(DATA_DIR,'update_schedule.json'); NOTIFICATION_STATE_FILE=os.path.join(DATA_DIR,'notification_state.json')

os.makedirs(DATA_DIR, exist_ok=True) # Создаем директорию данных, если ее нет

CSV_HEADERS = ['Дата', 'Время', 'Цена', 'Изменение', 'Мин. цена', 'Макс. цена']
LOCK_TIMEOUT = 10

# --- Форматирование цены ---
def format_price(price):
    """Форматирует числовое значение цены в строку с пробелами."""
    if pd.isna(price): # Проверяем на None и NaN с помощью pandas
        return "N/A"
    try:
        formatted_price = f"{int(price):,}".replace(",", " ")
        return formatted_price
    except (ValueError, TypeError):
        logger.debug(f"Не удалось отформатировать цену: {price} (тип: {type(price)})")
        return "N/A"

def get_player_filename(player_name):
    """Генерирует безопасное имя файла для игрока."""
    safe_name = "".join(c if c.isalnum() else "_" for c in player_name)
    return os.path.join(DATA_DIR, f"{safe_name}.csv")

def get_lock_filename(filepath):
    """Возвращает имя файла блокировки."""
    return f"{filepath}.lock"

# --- Логирование данных ---
def log_player_data(player_name, data):
    """Записывает данные игрока в CSV файл с блокировкой."""
    filename = get_player_filename(player_name)
    lock_filename = get_lock_filename(filename)
    lock = FileLock(lock_filename, timeout=LOCK_TIMEOUT)
    try:
        with lock:
            file_exists = os.path.isfile(filename)
            is_empty = os.path.getsize(filename) == 0 if file_exists else True
            with open(filename, 'a', newline='', encoding='utf-8') as csvfile:
                writer = csv.writer(csvfile)
                if not file_exists or is_empty:
                    writer.writerow(CSV_HEADERS); logger.debug(f"Записан заголовок в {filename}")

                timestamp_iso = data.get('timestamp')
                if timestamp_iso:
                    try:
                        dt_object_utc = datetime.fromisoformat(timestamp_iso).astimezone(timezone.utc)
                        date_str = dt_object_utc.strftime('%Y-%m-%d'); time_str = dt_object_utc.strftime('%H:%M:%S')
                    except (ValueError, TypeError):
                        logger.warning(f"Некорректный timestamp '{timestamp_iso}' для {player_name}."); now_utc = datetime.now(timezone.utc); date_str = now_utc.strftime('%Y-%m-%d'); time_str = now_utc.strftime('%H:%M:%S')
                else:
                    now_utc = datetime.now(timezone.utc); date_str = now_utc.strftime('%Y-%m-%d'); time_str = now_utc.strftime('%H:%M:%S')

                price_val = data.get('price'); change_val = data.get('change', ''); min_order_val = data.get('min_order'); max_order_val = data.get('max_order')
                row_data = [date_str, time_str, price_val if price_val is not None else '', change_val if change_val is not None else '', min_order_val if min_order_val is not None else '', max_order_val if max_order_val is not None else '']
                writer.writerow(row_data)
    except Timeout: logger.error(f"Timeout при попытке блокировки файла: {lock_filename}")
    except IOError as e: logger.error(f"Ошибка ввода/вывода при записи в {filename}: {e}", exc_info=True)
    except Exception as e: logger.error(f"Непредвиденная ошибка при записи данных для {player_name} в {filename}: {e}", exc_info=True)

# --- Чтение истории ---
def read_player_history(player_name, min_rows=10, usecols=None):
    """Читает историю игрока из CSV, обрабатывает даты и типы."""
    filename = get_player_filename(player_name)
    if not os.path.exists(filename): logger.warning(f"Файл истории не найден: {filename}"); return None

    try:
        default_cols = ['Дата', 'Время', 'Цена', 'Мин. цена', 'Макс. цена'];
        cols_to_use = usecols if usecols else default_cols
        df = pd.read_csv(filename, usecols=cols_to_use, na_values=['', 'NA', 'N/A', 'NaN', 'nan', 'None', 'none', 'Invalid Price'], keep_default_na=True, on_bad_lines='warn', low_memory=False, encoding='utf-8')
        if df.empty: logger.warning(f"Файл {filename} пуст или не содержит валидных строк."); return None

        if 'Дата' in df.columns and 'Время' in df.columns:
            try:
                df['datetime_temp'] = pd.to_datetime(df['Дата'] + ' ' + df['Время'], errors='coerce')
                initial_rows_dt = len(df); df.dropna(subset=['datetime_temp'], inplace=True); rows_after_dt_dropna = len(df)
                if initial_rows_dt != rows_after_dt_dropna: logger.debug(f"[{player_name}] Удалено {initial_rows_dt - rows_after_dt_dropna} строк с невалидной датой/временем.")
                if df.empty: raise ValueError("Нет валидных дат после парсинга.")
                df.set_index('datetime_temp', inplace=True); df.index.name = 'datetime'
                if df.index.tz is None: df = df.tz_localize('UTC')
                else: df = df.tz_convert('UTC')
                if 'Дата' not in (usecols or default_cols): df.drop(columns=['Дата'], inplace=True, errors='ignore')
                if 'Время' not in (usecols or default_cols): df.drop(columns=['Время'], inplace=True, errors='ignore')
            except Exception as e_dt: logger.error(f"Ошибка обработки даты/времени для {player_name}: {e_dt}", exc_info=True); return None
        else: logger.error(f"Отсутствуют колонки 'Дата' и/или 'Время' для {player_name}."); return None

        price_cols = ['Цена', 'Мин. цена', 'Макс. цена']
        for col in price_cols:
            if col in df.columns:
                if df[col].dtype == 'object': df[col] = df[col].astype(str).str.replace(r'\s+', '', regex=True)
                df[col] = pd.to_numeric(df[col], errors='coerce')

        initial_rows_price = len(df); df.dropna(subset=['Цена'], inplace=True); rows_after_price_dropna = len(df)
        if initial_rows_price != rows_after_price_dropna: logger.debug(f"[{player_name}] Удалено {initial_rows_price - rows_after_price_dropna} строк с NaN в колонке 'Цена'.")
        if df.empty: logger.warning(f"Нет валидных цен для {player_name} после очистки NaN."); return None
        if not isinstance(df.index, pd.DatetimeIndex): logger.error(f"{player_name}: Индекс не DatetimeIndex!"); return None
        initial_rows_dedup = len(df); df = df[~df.index.duplicated(keep='last')]; rows_after_dedup = len(df)
        if initial_rows_dedup != rows_after_dedup: logger.debug(f"[{player_name}] Удалено {initial_rows_dedup - rows_after_dedup} дубликатов по времени.")
        if len(df) < min_rows: logger.warning(f"Недостаточно данных для {player_name} ({len(df)} < {min_rows})."); return None
        logger.debug(f"Успешно прочитано {len(df)} строк для {player_name} из {filename}")
        return df.sort_index()
    except FileNotFoundError: logger.warning(f"Файл истории не найден: {filename}"); return None
    except pd.errors.EmptyDataError: logger.warning(f"Файл истории пуст: {filename}"); return None
    except Exception as e: logger.error(f"Ошибка чтения/обработки {filename} для {player_name}: {e}", exc_info=True); return None

# --- Функции Purchase Log и Update Schedule (без изменений) ---
def get_last_known_price(player_name):
    # ... (код без изменений) ...
    filename = get_player_filename(player_name)
    if not os.path.exists(filename) or os.path.getsize(filename) == 0: return None
    try:
        last_valid_line_parts = None
        with open(filename, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            for line in reversed(lines):
                stripped_line = line.strip()
                if not stripped_line or stripped_line.lower().startswith('дата,время,цена'): continue
                parts = stripped_line.split(',')
                if len(parts) == len(CSV_HEADERS):
                     price_str = parts[2].replace(' ', '')
                     if price_str.isdigit(): last_valid_line_parts = parts; break
        if last_valid_line_parts:
            last_entry = dict(zip(CSV_HEADERS, last_valid_line_parts))
            try: last_entry['Цена'] = int(last_entry['Цена'].replace(' ', ''))
            except (ValueError, KeyError) as e: logger.warning(f"Не конвертировать цену {player_name}. Строка: {last_valid_line_parts}, Ошибка: {e}"); return None
            return last_entry
        else: logger.warning(f"Не найдено валидных строк в {filename}"); return None
    except FileNotFoundError: return None
    except Exception as e: logger.error(f"Ошибка последней цены {player_name}: {e}", exc_info=True); return None

def load_purchase_log():
    # ... (код без изменений) ...
    if not os.path.exists(PURCHASE_LOG_FILE): return {}
    lock_path = get_lock_filename(PURCHASE_LOG_FILE); lock = FileLock(lock_path, timeout=LOCK_TIMEOUT)
    try:
        with lock:
            if os.path.getsize(PURCHASE_LOG_FILE) > 0:
                 with open(PURCHASE_LOG_FILE, 'r', encoding='utf-8') as f: return json.load(f)
            else: return {}
    except Timeout: logger.error(f"Timeout блокировки лога покупок (чтение): {lock_path}"); return {}
    except (json.JSONDecodeError, IOError) as e: logger.error(f"Ошибка загрузки лога покупок ({PURCHASE_LOG_FILE}): {e}"); return {}
    except Exception as e: logger.error(f"Ошибка загрузки лога покупок: {e}", exc_info=True); return {}

def save_purchase_log(log_data):
    # ... (код без изменений) ...
    lock_path = get_lock_filename(PURCHASE_LOG_FILE); lock = FileLock(lock_path, timeout=LOCK_TIMEOUT)
    try:
        with lock:
            os.makedirs(os.path.dirname(PURCHASE_LOG_FILE), exist_ok=True)
            with open(PURCHASE_LOG_FILE, 'w', encoding='utf-8') as f: json.dump(log_data, f, indent=4, ensure_ascii=False)
    except Timeout: logger.error(f"Timeout блокировки лога покупок (запись): {lock_path}.")
    except IOError as e: logger.error(f"Ошибка сохранения лога покупок ({PURCHASE_LOG_FILE}): {e}")
    except Exception as e: logger.error(f"Ошибка сохранения лога покупок: {e}", exc_info=True)

def save_update_schedule(schedule_data):
    # ... (код без изменений) ...
    schedule_to_save = {}
    for player, dt in schedule_data.items():
        if isinstance(dt, datetime):
            try: dt_utc = dt.astimezone(timezone.utc) if dt.tzinfo else dt.replace(tzinfo=timezone.utc); schedule_to_save[player] = dt_utc.isoformat()
            except Exception as e: logger.warning(f"Не конвертировать дату {dt} для {player}: {e}")
        else: logger.warning(f"Некорректный тип времени ({type(dt)}) для {player}. Пропуск.")
    if not schedule_to_save: logger.warning("Нет данных для сохранения в расписании."); return
    lock_path = get_lock_filename(UPDATE_SCHEDULE_FILE); lock = FileLock(lock_path, timeout=LOCK_TIMEOUT)
    try:
        with lock:
            os.makedirs(os.path.dirname(UPDATE_SCHEDULE_FILE), exist_ok=True)
            with open(UPDATE_SCHEDULE_FILE, 'w', encoding='utf-8') as f: json.dump(schedule_to_save, f, indent=4, ensure_ascii=False)
            logger.info(f"Расписание ({len(schedule_to_save)}) сохранено в {UPDATE_SCHEDULE_FILE}")
    except Timeout: logger.error(f"Timeout блокировки файла расписания: {lock_path}.")
    except TypeError as e: logger.error(f"Ошибка сериализации расписания: {e}.", exc_info=True)
    except IOError as e: logger.error(f"Ошибка записи расписания ({UPDATE_SCHEDULE_FILE}): {e}", exc_info=True)
    except Exception as e: logger.error(f"Ошибка сохранения расписания: {e}", exc_info=True)

def load_update_schedule():
    # ... (код без изменений) ...
    if not os.path.exists(UPDATE_SCHEDULE_FILE): logger.warning(f"Файл расписания не найден: {UPDATE_SCHEDULE_FILE}."); return {}
    lock_path = get_lock_filename(UPDATE_SCHEDULE_FILE); lock = FileLock(lock_path, timeout=LOCK_TIMEOUT); loaded_schedule = {}
    try:
        with lock:
            if os.path.getsize(UPDATE_SCHEDULE_FILE) == 0: logger.warning(f"Файл расписания {UPDATE_SCHEDULE_FILE} пуст."); return {}
            with open(UPDATE_SCHEDULE_FILE, 'r', encoding='utf-8') as f: schedule_from_file = json.load(f)
        for player, dt_str in schedule_from_file.items():
            if not isinstance(dt_str, str): logger.warning(f"Некорректный тип '{type(dt_str)}' времени {player}."); continue
            try: dt_obj = datetime.fromisoformat(dt_str).replace(tzinfo=timezone.utc); loaded_schedule[player] = dt_obj
            except ValueError: logger.warning(f"Не разобрать дату '{dt_str}' для {player}.")
            except Exception as e: logger.warning(f"Ошибка разбора даты '{dt_str}' для {player}: {e}")
        logger.info(f"Расписание ({len(loaded_schedule)}) загружено из {UPDATE_SCHEDULE_FILE}")
        return loaded_schedule
    except Timeout: logger.error(f"Timeout блокировки файла расписания: {lock_path}."); return {}
    except json.JSONDecodeError as e: logger.error(f"Ошибка JSON расписания ({UPDATE_SCHEDULE_FILE}): {e}."); return {}
    except IOError as e: logger.error(f"Ошибка чтения расписания ({UPDATE_SCHEDULE_FILE}): {e}."); return {}
    except Exception as e: logger.error(f"Ошибка загрузки расписания: {e}.", exc_info=True); return {}

# --- ДОБАВЛЕНО v6.11: Функции для работы с состоянием уведомлений ---
def load_notification_state():
    """Загружает последнее состояние уведомлений (score) из JSON."""
    if not os.path.exists(NOTIFICATION_STATE_FILE):
        logger.info(f"Файл состояния уведомлений не найден ({NOTIFICATION_STATE_FILE}). Возвращается пустой словарь.")
        return {}
    lock_path = get_lock_filename(NOTIFICATION_STATE_FILE)
    lock = FileLock(lock_path, timeout=LOCK_TIMEOUT)
    try:
        with lock:
            if os.path.getsize(NOTIFICATION_STATE_FILE) > 0:
                 with open(NOTIFICATION_STATE_FILE, 'r', encoding='utf-8') as f:
                     state = json.load(f)
                     logger.info(f"Состояние уведомлений ({len(state)}) загружено из {NOTIFICATION_STATE_FILE}")
                     return state
            else:
                 logger.warning(f"Файл состояния уведомлений {NOTIFICATION_STATE_FILE} пуст.")
                 return {}
    except Timeout: logger.error(f"Timeout при блокировке файла состояния уведомлений для чтения: {lock_path}"); return {}
    except (json.JSONDecodeError, IOError) as e: logger.error(f"Ошибка загрузки состояния уведомлений ({NOTIFICATION_STATE_FILE}): {e}"); return {}
    except Exception as e: logger.error(f"Непредвиденная ошибка загрузки состояния уведомлений: {e}", exc_info=True); return {}

def save_notification_state(state_data):
    """Сохраняет текущее состояние уведомлений (score) в JSON."""
    if not isinstance(state_data, dict):
        logger.error("Ошибка сохранения состояния уведомлений: переданы неверные данные (ожидается dict).")
        return

    lock_path = get_lock_filename(NOTIFICATION_STATE_FILE)
    lock = FileLock(lock_path, timeout=LOCK_TIMEOUT)
    try:
        with lock:
            os.makedirs(os.path.dirname(NOTIFICATION_STATE_FILE), exist_ok=True)
            with open(NOTIFICATION_STATE_FILE, 'w', encoding='utf-8') as f:
                 json.dump(state_data, f, indent=4, ensure_ascii=False)
            logger.debug(f"Состояние уведомлений ({len(state_data)}) сохранено в {NOTIFICATION_STATE_FILE}")
    except Timeout: logger.error(f"Timeout при блокировке файла состояния уведомлений для записи: {lock_path}.")
    except TypeError as e: logger.error(f"Ошибка сериализации данных состояния уведомлений: {e}.", exc_info=True)
    except IOError as e: logger.error(f"Ошибка записи файла состояния уведомлений ({NOTIFICATION_STATE_FILE}): {e}", exc_info=True)
    except Exception as e: logger.error(f"Непредвиденная ошибка сохранения состояния уведомлений: {e}", exc_info=True)
# --- КОНЕЦ ДОБАВЛЕНИЙ v6.11 ---

# Экспорт
__all__ = [
    'log_player_data', 'read_player_history', 'get_last_known_price',
    'load_purchase_log', 'save_purchase_log', 'format_price',
    'get_player_filename', 'save_update_schedule', 'load_update_schedule',
    'load_notification_state', 'save_notification_state' # Добавлено в экспорт
]