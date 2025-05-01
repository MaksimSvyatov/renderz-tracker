# # =============================================
# # ФАЙЛ: cycle_analysis.py (ВЕРСИЯ v7.1 - Детальная Отладка Чтения)
# # - Добавлено МНОГО детальных логов в read_player_history
# # - Добавлен вывод первых 5 строк DataFrame на разных этапах
# # =============================================
# import os
# import csv
# import logging
# from datetime import datetime, timedelta, timezone
# from collections import defaultdict
# import numpy as np
# import pandas as pd
# import re
# import traceback
# import config
# import storage
#
# try: DATA_DIR = config.DATA_DIR
# except AttributeError: logging.warning("[cycle] DATA_DIR не найден, исп. 'data'"); DATA_DIR = 'data'
# EXPECTED_HEADER_OHLC = config.EXPECTED_HEADER_OHLC
#
# # --- Функция чтения истории (С ДЕТАЛЬНОЙ ОТЛАДКОЙ v7.1) ---
# def read_player_history(player_name) -> list[dict]:
#     filepath = storage.get_player_filepath(player_name)
#     logging.info(f"[read_player_history DEBUG] --- Начало чтения для {player_name} ---") # <-- Отладочный префикс
#     logging.info(f"[read_player_history DEBUG] Файл: {filepath}")
#     if not os.path.isfile(filepath):
#         logging.warning(f"[read_player_history DEBUG] Файл НЕ НАЙДЕН: {filepath}")
#         return []
#
#     df = pd.DataFrame()
#     try:
#         # --- Чтение CSV ---
#         try:
#             logging.debug(f"[read_player_history DEBUG] Попытка чтения с заголовком...")
#             df = pd.read_csv(filepath, sep=',', encoding='utf-8', header=0, low_memory=False, on_bad_lines='warn')
#             logging.info(f"[read_player_history DEBUG] Прочитано строк с заголовком: {len(df)}. Колонки: {df.columns.tolist()}")
#             if df.empty and os.path.getsize(filepath) > 0: logging.warning(f"[read_player_history DEBUG] DataFrame пуст после чтения с заголовком!")
#             df.columns = df.columns.str.strip()
#             required_cols = ["Дата", "Время", "Цена"]
#             missing_cols = [col for col in required_cols if col not in df.columns]
#             if missing_cols:
#                 logging.error(f"[read_player_history DEBUG] Отсутствуют колонки {missing_cols} (заголовок прочитан)")
#                 raise ValueError("Missing required columns in header")
#             has_header = True
#             logging.debug(f"[read_player_history DEBUG] Колонки {required_cols} найдены.")
#
#         except (Exception, ValueError) as e_header:
#             logging.warning(f"[read_player_history DEBUG] Ошибка чтения с заголовком ({e_header}). Пробуем без...")
#             try:
#                  expected_header_names = ["Дата", "Время", "Цена", "Изменение", "Мин. цена", "Макс. цена"]
#                  df = pd.read_csv(filepath, sep=',', encoding='utf-8', header=None, names=expected_header_names, low_memory=False, on_bad_lines='warn')
#                  logging.info(f"[read_player_history DEBUG] Прочитано строк БЕЗ заголовка: {len(df)}")
#                  if df.empty and os.path.getsize(filepath) > 0: logging.warning(f"[read_player_history DEBUG] DataFrame пуст после чтения без заголовка!")
#                  if not all(col in df.columns for col in expected_header_names[:3]):
#                       logging.error(f"[read_player_history DEBUG] Не удалось присвоить имена колонок")
#                       return []
#                  has_header = False
#             except Exception as e_noheader:
#                 logging.error(f"[read_player_history DEBUG] КРИТИЧЕСКАЯ ОШИБКА чтения CSV даже без заголовка: {e_noheader}", exc_info=True)
#                 return []
#
#         if df.empty: logging.warning(f"[read_player_history DEBUG] DataFrame пуст после чтения {filepath}"); return []
#         logging.debug(f"[read_player_history DEBUG] Первые 5 строк ПОСЛЕ ЧТЕНИЯ:\n{df.head().to_string()}") # <-- Лог 1
#
#         # --- Преобразование Даты/Времени ---
#         logging.debug("[read_player_history DEBUG] Обработка Даты/Времени...")
#         processed_dates = []
#         skipped_dates = 0
#         for index, row in df.iterrows():
#             date_str_raw = str(row.get('Дата', '')).strip(); time_str_raw = str(row.get('Время', '')).strip()
#             dt_aware = None
#             if not date_str_raw: skipped_dates += 1; processed_dates.append(pd.NaT); continue
#             full_dt_str = f"{date_str_raw} {time_str_raw}".strip()
#             dt_str_cleaned = full_dt_str
#             if '+' in dt_str_cleaned: dt_str_cleaned = dt_str_cleaned.split('+')[0].strip()
#             if len(dt_str_cleaned) > 19: dt_str_cleaned = dt_str_cleaned[:19]
#             if len(dt_str_cleaned) <= 10: dt_str_cleaned += " 00:00:00"
#             fmts = ["%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"]
#             for fmt in fmts:
#                 try: dt_naive = datetime.strptime(dt_str_cleaned, fmt); dt_aware = dt_naive.replace(tzinfo=timezone.utc); break
#                 except ValueError: continue
#             if dt_aware is None:
#                 try: dt_naive = datetime.strptime(date_str_raw, "%Y-%m-%d"); dt_aware = dt_naive.replace(tzinfo=timezone.utc)
#                 except ValueError: logging.warning(f"[read_player_history DEBUG] Строка {index + (1 if has_header else 0)}: НЕ РАСПОЗНАНА ДАТА '{date_str_raw} {time_str_raw}' -> '{dt_str_cleaned}'"); skipped_dates += 1; dt_aware = pd.NaT
#             processed_dates.append(dt_aware)
#
#         df['date'] = processed_dates
#         original_count = len(df)
#         df = df.dropna(subset=['date']) # Удаляем строки с невалидной датой
#         dropped_dates = original_count - len(df)
#         if dropped_dates > 0: logging.warning(f"[read_player_history DEBUG] Удалено строк из-за невалидной даты: {dropped_dates}")
#         logging.info(f"[read_player_history DEBUG] Строк ПОСЛЕ ОБРАБОТКИ ДАТ: {len(df)}") # <-- Лог 2
#         if df.empty: logging.warning(f"[read_player_history DEBUG] DataFrame пуст после обработки дат"); return []
#         logging.debug(f"[read_player_history DEBUG] Первые 5 строк ПОСЛЕ ОБРАБОТКИ ДАТ:\n{df.head().to_string()}") # <-- Лог 3
#
#         # --- Преобразование Цены ---
#         logging.debug("[read_player_history DEBUG] Обработка Цены...")
#         df['price'] = pd.to_numeric(df['Цена'].astype(str).str.replace(',', '').str.replace(' ', ''), errors='coerce')
#         original_count = len(df)
#         df = df.dropna(subset=['price']) # Удаляем NaN цены
#         df = df[np.isfinite(df['price'])] # Удаляем inf цены
#         dropped_prices = original_count - len(df)
#         if dropped_prices > 0: logging.warning(f"[read_player_history DEBUG] Удалено строк из-за невалидной/бесконечной цены: {dropped_prices}")
#         logging.info(f"[read_player_history DEBUG] Строк ПОСЛЕ ОБРАБОТКИ ЦЕН: {len(df)}") # <-- Лог 4
#         if df.empty: logging.warning(f"[read_player_history DEBUG] DataFrame пуст после обработки цен"); return []
#         logging.debug(f"[read_player_history DEBUG] Первые 5 строк ПОСЛЕ ОБРАБОТКИ ЦЕН:\n{df.head().to_string()}") # <-- Лог 5
#
#         # --- Выбор нужных колонок, сортировка, удаление дубликатов ---
#         if 'date' not in df.columns or 'price' not in df.columns: logging.error(f"[read_player_history DEBUG] Отсутствуют колонки 'date' или 'price'"); return []
#         df_final = df[['date', 'price']].sort_values(by='date').reset_index(drop=True)
#         original_count = len(df_final)
#         df_final = df_final.drop_duplicates(subset=['date'], keep='last')
#         dropped_dups = original_count - len(df_final)
#         if dropped_dups > 0: logging.info(f"[read_player_history DEBUG] Удалено дубликатов по дате: {dropped_dups}.")
#         logging.info(f"[read_player_history DEBUG] Строк ПОСЛЕ УДАЛЕНИЯ ДУБЛИКАТОВ: {len(df_final)}") # <-- Лог 6
#         if df_final.empty: logging.warning(f"[read_player_history DEBUG] DataFrame пуст после удаления дубликатов"); return []
#         logging.debug(f"[read_player_history DEBUG] Первые 5 строк ПОСЛЕ УДАЛЕНИЯ ДУБЛИКАТОВ:\n{df_final.head().to_string()}") # <-- Лог 7
#
#         # --- Преобразование в список словарей ---
#         history_list = df_final.to_dict('records')
#         logging.info(f"[read_player_history DEBUG] УСПЕШНО: Возвращено {len(history_list)} записей для {player_name}.") # <-- Лог 8
#         return history_list
#
#     except FileNotFoundError: logging.warning(f"[read_player_history DEBUG] Файл исчез (FileNotFoundError): {filepath}"); return []
#     except Exception as e: logging.error(f"[read_player_history DEBUG] КРИТИЧЕСКАЯ ОШИБКА: {e}", exc_info=True); return []
#
# # --- Остальные функции анализа ---
# # ... (Код без изменений) ...
# def get_all_players():
#     players = []
#     if not os.path.isdir(DATA_DIR): logging.warning(f"[cycle] Папка {DATA_DIR} не найдена."); return []
#     try:
#         for f in os.listdir(DATA_DIR):
#             if f.endswith(".csv") and not f.startswith('.'):
#                 player_name = os.path.splitext(f)[0].replace("_", " ")
#                 players.append(player_name)
#     except Exception as e: logging.error(f"Ошибка чтения {DATA_DIR}: {e}"); return []
#     if not players: logging.warning(f"[cycle] Нет CSV в {DATA_DIR}.")
#     else: logging.info(f"[cycle] Найдено {len(players)} CSV файлов игроков.")
#     return players
#
# def analyze_day_of_week(player_name):
#     data = read_player_history(player_name);
#     if not data: return {}
#     stats = {dow: {"count": 0, "sum_price": 0.0, "min_price": float('inf'), "max_price": float('-inf')} for dow in range(7)}
#     valid = 0
#     for row in data:
#         price = row.get("price"); date = row.get("date")
#         if price is not None and np.isfinite(price) and date is not None and isinstance(date, datetime):
#             st = stats[date.weekday()]; st["count"] += 1; st["sum_price"] += price
#             st["min_price"] = min(st["min_price"], price); st["max_price"] = max(st["max_price"], price)
#             valid += 1
#     if valid == 0: return {}
#     for st in stats.values():
#         st["avg_price"] = st["sum_price"] / st["count"] if st["count"] > 0 else 0.0
#         if st["min_price"] == float('inf'): st["min_price"] = None
#         if st["max_price"] == float('-inf'): st["max_price"] = None
#     return stats
#
# def analyze_cycle(player_name, cycle_length=7):
#     data = read_player_history(player_name)
#     valid_data = [r for r in data if r.get('price') is not None and np.isfinite(r['price'])]
#     if not valid_data or len(valid_data) < cycle_length: logging.warning(f"[cycle] Мало валидных данных ({len(valid_data)}) для {cycle_length}-дн {player_name}"); return []
#     cycle_stats = [{"step": i, "count": 0, "sum_price": 0.0, "min_price": float('inf'), "max_price": float('-inf')} for i in range(cycle_length)]
#     for i, row in enumerate(valid_data):
#             st = cycle_stats[i % cycle_length]; st["count"] += 1; st["sum_price"] += row["price"]
#             st["min_price"] = min(st["min_price"], row["price"]); st["max_price"] = max(st["max_price"], row["price"])
#     for st in cycle_stats:
#         st["avg_price"] = st["sum_price"] / st["count"] if st["count"] > 0 else 0.0
#         if st["min_price"] == float('inf'): st["min_price"] = None
#         if st["max_price"] == float('-inf'): st["max_price"] = None
#     return cycle_stats
#
# def create_seasonal_signal_example(player_name):
#     data_dow = analyze_day_of_week(player_name)
#     if not data_dow: return "NEUTRAL (нет DOW)"
#     dow_now = datetime.now(timezone.utc).weekday(); day_stats = data_dow.get(dow_now)
#     if not day_stats or day_stats.get("count", 0) < 1: return "NEUTRAL (мало DOW)"
#     all_sum, all_count, valid_days = 0.0, 0, 0
#     for st in data_dow.values():
#         if st.get("count", 0) > 0 and st.get("avg_price", 0) > 0:
#             all_sum += st["sum_price"]; all_count += st["count"]; valid_days += 1
#     if all_count == 0 or valid_days < 2: return "NEUTRAL (мало сравн DOW)"
#     global_avg = all_sum / all_count; day_avg = day_stats["avg_price"]; threshold = global_avg * 0.01
#     if day_avg < global_avg - threshold: return "BUY (avg DOW < global avg)"
#     elif day_avg > global_avg + threshold: return "SELL (avg DOW > global avg)"
#     else: return "NEUTRAL (avg DOW ≈ global avg)"
#
# def create_dow_range_signal(player_name, current_price, lower=0.2, upper=0.8):
#     if current_price is None or not np.isfinite(current_price) or current_price <= 0: return "NEUTRAL (цена?)"
#     stats_dow = analyze_day_of_week(player_name);
#     if not stats_dow: return "NEUTRAL (нет DOW)"
#     dow_now = datetime.now(timezone.utc).weekday(); day_stats = stats_dow.get(dow_now)
#     if not day_stats or day_stats.get("count", 0) < 5: return "NEUTRAL (мало DOW)"
#     h_min, h_max = day_stats.get("min_price"), day_stats.get("max_price")
#     if h_min is None or h_max is None or h_min >= h_max: return "NEUTRAL (диапазон?)"
#     d_range = h_max - h_min; pos = (current_price - h_min) / d_range if d_range > 1e-9 else 0.5
#     pos = max(0.0, min(1.0, pos)); mn_s = f"{h_min:,.0f}".replace(",", "\u00A0"); mx_s = f"{h_max:,.0f}".replace(",", "\u00A0")
#     pos_s = f"{pos*100:.0f}%"
#     if pos <= lower: return f"BUY (в нижних {pos_s} диапазона {mn_s}-{mx_s})"
#     elif pos >= upper: return f"SELL (в верхних {pos_s} диапазона {mn_s}-{mx_s})"
#     else: return f"NEUTRAL (в середине {pos_s} диапазона {mn_s}-{mx_s})"
#
# def create_10_day_trend_signal(player_name, thresh_std=1.0):
#     history = read_player_history(player_name);
#     valid_history = [r for r in history if r.get('price') is not None and np.isfinite(r['price'])]
#     if len(valid_history) < 30: return "NEUTRAL (мало данных)"
#     now=datetime.now(timezone.utc); t10=now-timedelta(days=10); t20=now-timedelta(days=20)
#     valid_history = [r for r in valid_history if r['date'].tzinfo is not None]
#     rec10 = [r["price"] for r in valid_history if r["date"] >= t10]
#     base = [r["price"] for r in valid_history if t20 <= r["date"] < t10]
#     if len(rec10) < 5 or len(base) < 10: return "NEUTRAL (мало периодов)"
#     try: avg10, avgB, stdB = np.mean(rec10), np.mean(base), np.std(base)
#     except Exception as e_stat: logging.warning(f"Ошибка стат. тренда {player_name}: {e_stat}"); return "NEUTRAL (ошибка стат.)"
#     if stdB < 1e-9: return "NEUTRAL (0 волат)"
#     dev_std = (avg10 - avgB) / stdB; ar=f"{avg10:,.0f}".replace(",","\u00A0"); ab=f"{avgB:,.0f}".replace(",","\u00A0"); sd=f"{dev_std:.2f}"
#     if dev_std > thresh_std: return f"SELL (avg10d={ar} > base={ab}, dev={sd} СКО)"
#     elif dev_std < -thresh_std: return f"BUY (avg10d={ar} < base={ab}, dev={sd} СКО)"
#     else: return f"NEUTRAL (avg10d={ar} ≈ base={ab}, dev={sd} СКО)"
#
# def analyze_day_of_month(player_name):
#     data = read_player_history(player_name);
#     if not data: return {}
#     stats = defaultdict(lambda: {"count": 0, "sum_price": 0.0, "min_price": float('inf'), "max_price": float('-inf')})
#     valid = 0
#     for row in data:
#         price = row.get("price"); date = row.get("date")
#         if price is not None and np.isfinite(price) and date is not None and isinstance(date, datetime):
#             st=stats[date.day]; st["count"]+=1; st["sum_price"]+=price
#             st["min_price"]=min(st["min_price"],row["price"]); st["max_price"]=max(st["max_price"],row["price"])
#             valid+=1
#     if valid == 0: return {}
#     proc_stats = {}
#     for day in range(1, 32):
#         st = stats.get(day, {"count":0, "sum_price":0.0, "min_price":float('inf'), "max_price":float('-inf')})
#         if st["count"] > 0:
#             st["avg_price"] = st["sum_price"] / st["count"]
#             st["min_price"] = None if st["min_price"] == float('inf') else st["min_price"]
#             st["max_price"] = None if st["max_price"] == float('-inf') else st["max_price"]
#         else: st["avg_price"], st["min_price"], st["max_price"] = 0.0, None, None
#         proc_stats[day] = st
#     return proc_stats
#
# def create_day_of_month_signal(player_name, thresh_pct=1.0):
#     stats_dom = analyze_day_of_month(player_name)
#     if not stats_dom: return "NEUTRAL (нет DOM)"
#     day_now = datetime.now(timezone.utc).day; day_stats = stats_dom.get(day_now)
#     if not day_stats or day_stats.get("count", 0) < 3: return "NEUTRAL (мало за число)"
#     all_sum, all_count, valid_days = 0.0, 0, 0
#     for st in stats_dom.values():
#         if st.get("count",0)>0 and st.get("avg_price",0)>0: all_sum+=st["sum_price"]; all_count+=st["count"]; valid_days+=1
#     if all_count == 0 or valid_days < 10: return "NEUTRAL (мало сравн DOM)"
#     glob_avg, day_avg = all_sum/all_count, day_stats["avg_price"]; thresh_v=glob_avg*(thresh_pct/100.0)
#     d_str = f"{day_now}-е";
#     if day_avg < glob_avg - thresh_v: return f"BUY (avg {d_str} < global avg)"
#     elif day_avg > glob_avg + thresh_v: return f"SELL (avg {d_str} > global avg)"
#     else: return f"NEUTRAL (avg {d_str} ≈ global avg)"
#
# def generate_weekly_text_report():
#     out_dir = "seasonal_reports"; os.makedirs(out_dir, exist_ok=True)
#     out_file = os.path.join(out_dir, "weekly_text_report.txt")
#     daily_file = os.path.join(config.REPORTS_DIR, "daily_summary_corrected.csv")
#     if not os.path.isfile(daily_file): logging.warning(f"[cycle] Нет OHLC {daily_file}"); return
#     cutoff_utc = (datetime.now(timezone.utc) - timedelta(days=7)).date()
#     try:
#         df = pd.read_csv(daily_file, parse_dates=['Дата'])
#         if not set(config.EXPECTED_HEADER_OHLC).issubset(set(df.columns)): logging.error(f"[cycle] Неверный заголовок в {daily_file}. Ожидался: {config.EXPECTED_HEADER_OHLC}, Найден: {df.columns.tolist()}"); return
#         if df['Дата'].dt.tz is None: df['Дата'] = df['Дата'].dt.tz_localize('UTC', ambiguous='infer', nonexistent='shift_forward')
#         else: df['Дата'] = df['Дата'].dt.tz_convert('UTC')
#         df_f = df[df['Дата'].dt.date >= cutoff_utc].copy()
#         for col in ['Минимум','Максимум','Закрытие']: df_f[col] = pd.to_numeric(df_f[col], errors='coerce')
#         df_f.dropna(subset=['Игрок','Минимум','Максимум','Закрытие'], inplace=True)
#         stats = df_f.groupby('Игрок').agg(m=('Минимум','min'), M=('Максимум','max'), s=('Закрытие','sum'), c=('Закрытие','count')).reset_index()
#         if stats.empty: logging.info(f"[cycle] Нет OHLC данных за 7 дн."); return
#         now_s = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S %Z')
#         lines = [f"\n=== Отчет от {now_s} ===", f"Период: {cutoff_utc.strftime('%Y-%m-%d')} - {datetime.now(timezone.utc).date().strftime('%Y-%m-%d')} UTC", "Игрок, Нед_Мин, Нед_Макс, Средн_Закр, Дней"]
#         for _, r in stats.iterrows(): avg = r['s']/r['c'] if r['c']>0 else 0; lines.append(f"{r['Игрок']},{r['m']:,.0f},{r['M']:,.0f},{avg:,.0f},{int(r['c'])}")
#         with open(out_file, "a", encoding="utf-8") as f: f.write("\n".join(lines) + "\n\n")
#         logging.info(f"[cycle] Недельный отчет ДОПИСАН в: {out_file}")
#     except Exception as e: logging.error(f"[cycle] Ошибка генерации недельного отчета из {daily_file}: {e}", exc_info=True)
#
# if __name__ == "__main__":
#     logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s")
#     test_player = "Anirudh Thapa 103"
#     print(f"\n--- Тест {test_player} ---")
#     history = read_player_history(test_player)
#     if history: print(f"УСПЕШНО Прочитано {len(history)} записей.")
#     else: print(f"НЕ УДАЛОСЬ прочитать историю для {test_player}.")
#     test_player_ok = "Joško Gvardiol 101"
#     print(f"\n--- Тест чтения истории для: {test_player_ok} ---")
#     history_ok = read_player_history(test_player_ok)
#     if history_ok: print(f"УСПЕШНО Прочитано {len(history_ok)} записей.")
#     else: print(f"НЕ УДАЛОСЬ прочитать историю для {test_player_ok}.")

# # =============================================
# # ФАЙЛ: cycle_analysis.py (ВЕРСИЯ v7.2 - Устойчивое чтение 6 колонок)
# # - ИЗМЕНЕНО: pd.read_csv теперь использует usecols=range(6) и names=...
# #             для принудительного чтения только первых 6 колонок,
# #             чтобы избежать ParserWarning из-за лишних полей.
# # - Сохранена детальная отладка чтения из v7.1
# # =============================================
# import os
# import csv
# import logging
# from datetime import datetime, timedelta, timezone
# from collections import defaultdict
# import numpy as np
# import pandas as pd
# import re
# import traceback
# import config
# import storage
#
# # --- Настройки из config ---
# try:
#     DATA_DIR = config.DATA_DIR
# except AttributeError:
#     logging.warning("[cycle] DATA_DIR не найден в config, используется 'data'")
#     DATA_DIR = 'data'
#
# try:
#     # Ожидаемый заголовок для OHLC (если используется где-то еще)
#     EXPECTED_HEADER_OHLC = config.EXPECTED_HEADER_OHLC
# except AttributeError:
#      EXPECTED_HEADER_OHLC = [
#         "Игрок", "Дата",
#         "Открытие", "Время открытия",
#         "Минимум", "Время минимума",
#         "Максимум", "Время максимума",
#         "Закрытие", "Время закрытия",
#         "Изменение цены (%)", "Средняя цена",
#         "Всего объёмов", "Сделок"
#     ]
#
#
# # --- Функция чтения истории (С ДЕТАЛЬНОЙ ОТЛАДКОЙ v7.1 + Устойчивое чтение 6 колонок v7.2) ---
# def read_player_history(player_name) -> list[dict]:
#     """
#     Читает историю цен игрока из CSV файла.
#     Возвращает список словарей [{'date': datetime, 'price': float}],
#     отсортированный по дате.
#     Использует pandas для чтения, устойчиво к лишним колонкам (читает только 6).
#     """
#     filepath = storage.get_player_filepath(player_name)
#     logging.info(f"[read_player_history DEBUG] --- Начало чтения для {player_name} ---")
#     logging.info(f"[read_player_history DEBUG] Файл: {filepath}")
#     if not os.path.isfile(filepath):
#         logging.warning(f"[read_player_history DEBUG] Файл НЕ НАЙДЕН: {filepath}")
#         return []
#
#     df = pd.DataFrame()
#     try:
#         # --- Чтение CSV (УСТОЙЧИВОЕ К 7+ КОЛОНКАМ) ---
#         expected_header_names = ["Дата", "Время", "Цена", "Изменение", "Мин. цена", "Макс. цена"] # Имена для 6 колонок
#         try:
#             # Пытаемся прочитать с заголовком, но берем только первые 6 колонок
#             logging.debug(f"[read_player_history DEBUG] Попытка чтения с заголовком (ограничение 6 колонок)...")
#             # ИЗМЕНЕНО v7.2: Добавлены names и usecols
#             df = pd.read_csv(
#                 filepath,
#                 sep=',',
#                 encoding='utf-8',
#                 header=0, # Предполагаем, что заголовок все еще есть в строке 0
#                 names=expected_header_names, # Указываем имена для первых 6
#                 usecols=range(6), # Читаем ТОЛЬКО первые 6 колонок (индексы 0-5)
#                 low_memory=False,
#                 on_bad_lines='warn' # Оставляем warn для других возможных проблем (не связанных с кол-вом колонок)
#             )
#             logging.info(f"[read_player_history DEBUG] Прочитано строк с заголовком (ожидая 6 колонок): {len(df)}. Колонки: {df.columns.tolist()}")
#             if df.empty and os.path.getsize(filepath) > 0: logging.warning(f"[read_player_history DEBUG] DataFrame пуст после чтения с заголовком!")
#
#             # Проверка наличия обязательных колонок после чтения
#             df.columns = df.columns.str.strip() # Очистка имен колонок на всякий случай
#             required_cols = ["Дата", "Время", "Цена"]
#             missing_cols = [col for col in required_cols if col not in df.columns]
#             if missing_cols:
#                 # Эта ошибка теперь маловероятна при использовании names, но оставим проверку
#                 logging.error(f"[read_player_history DEBUG] Отсутствуют колонки {missing_cols} (заголовок прочитан, ограничение 6 колонок)")
#                 raise ValueError(f"Missing required columns ({missing_cols}) even after specifying names and usecols")
#             has_header = True # Флаг, что чтение с заголовком прошло успешно
#             logging.debug(f"[read_player_history DEBUG] Колонки {required_cols} найдены.")
#
#         except (Exception, ValueError) as e_header:
#             # Если чтение с заголовком не удалось (или не нашлись колонки), пробуем без заголовка
#             logging.warning(f"[read_player_history DEBUG] Ошибка чтения с заголовком ({e_header}). Пробуем без (ограничение 6 колонок)...")
#             try:
#                  # Читаем без заголовка, присваивая имена и беря только 6 колонок
#                  # ИЗМЕНЕНО v7.2: Добавлен usecols
#                  df = pd.read_csv(
#                      filepath,
#                      sep=',',
#                      encoding='utf-8',
#                      header=None, # Без заголовка
#                      names=expected_header_names, # Имена для первых 6
#                      usecols=range(6), # Читаем ТОЛЬКО первые 6 колонок
#                      low_memory=False,
#                      on_bad_lines='warn'
#                  )
#                  logging.info(f"[read_player_history DEBUG] Прочитано строк БЕЗ заголовка (ожидая 6 колонок): {len(df)}")
#                  if df.empty and os.path.getsize(filepath) > 0: logging.warning(f"[read_player_history DEBUG] DataFrame пуст после чтения без заголовка!")
#                  # Проверяем, что основные колонки все же есть
#                  if not all(col in df.columns for col in expected_header_names[:3]):
#                       logging.error(f"[read_player_history DEBUG] Не удалось присвоить имена колонок без заголовка (ограничение 6 колонок)")
#                       return []
#                  has_header = False # Флаг, что читали без заголовка
#             except Exception as e_noheader:
#                 # Если и без заголовка не читается - критическая ошибка
#                 logging.error(f"[read_player_history DEBUG] КРИТИЧЕСКАЯ ОШИБКА чтения CSV даже без заголовка (ограничение 6 колонок): {e_noheader}", exc_info=True)
#                 return []
#
#         # --- Дальнейшая обработка DataFrame ---
#         if df.empty:
#             logging.warning(f"[read_player_history DEBUG] DataFrame пуст после чтения {filepath}")
#             return []
#         logging.debug(f"[read_player_history DEBUG] Первые 5 строк ПОСЛЕ ЧТЕНИЯ:\n{df.head().to_string()}") # <-- Лог 1
#
#         # --- Преобразование Даты/Времени ---
#         logging.debug("[read_player_history DEBUG] Обработка Даты/Времени...")
#         processed_dates = []
#         skipped_dates = 0
#         for index, row in df.iterrows():
#             date_str_raw = str(row.get('Дата', '')).strip()
#             time_str_raw = str(row.get('Время', '')).strip()
#             dt_aware = None # Инициализация для текущей строки
#
#             if not date_str_raw: # Пропускаем, если дата пустая
#                 skipped_dates += 1
#                 processed_dates.append(pd.NaT)
#                 continue
#
#             # Собираем полную строку и пытаемся очистить
#             full_dt_str = f"{date_str_raw} {time_str_raw}".strip()
#             dt_str_cleaned = full_dt_str
#             # Убираем возможные смещения таймзон и лишние доли секунды
#             if '+' in dt_str_cleaned: dt_str_cleaned = dt_str_cleaned.split('+')[0].strip()
#             if len(dt_str_cleaned) > 19: dt_str_cleaned = dt_str_cleaned[:19] # Обрезаем до YYYY-MM-DD HH:MM:SS
#             if len(dt_str_cleaned) <= 10: dt_str_cleaned += " 00:00:00" # Добавляем время, если его нет
#
#             # Форматы для парсинга
#             fmts = ["%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"]
#             for fmt in fmts:
#                 try:
#                     dt_naive = datetime.strptime(dt_str_cleaned, fmt)
#                     dt_aware = dt_naive.replace(tzinfo=timezone.utc) # Делаем aware с UTC
#                     break # Успешно распарсили, выходим из цикла форматов
#                 except ValueError:
#                     continue # Пробуем следующий формат
#
#             # Если стандартные форматы не сработали, пробуем только дату
#             if dt_aware is None:
#                 try:
#                     dt_naive = datetime.strptime(date_str_raw, "%Y-%m-%d")
#                     dt_aware = dt_naive.replace(tzinfo=timezone.utc)
#                 except ValueError:
#                     # Если ничего не помогло - логируем и пропускаем
#                     logging.warning(f"[read_player_history DEBUG] Строка {index + (1 if has_header else 0)}: НЕ РАСПОЗНАНА ДАТА '{date_str_raw} {time_str_raw}' -> '{dt_str_cleaned}'")
#                     skipped_dates += 1
#                     dt_aware = pd.NaT # Помечаем как Not a Time
#
#             processed_dates.append(dt_aware)
#
#         # Добавляем колонку с обработанными датами и удаляем строки с NaT
#         df['date'] = processed_dates
#         original_count = len(df)
#         df = df.dropna(subset=['date']) # Удаляем строки с невалидной датой
#         dropped_dates = original_count - len(df)
#         if dropped_dates > 0:
#             logging.warning(f"[read_player_history DEBUG] Удалено строк из-за невалидной даты: {dropped_dates}")
#         logging.info(f"[read_player_history DEBUG] Строк ПОСЛЕ ОБРАБОТКИ ДАТ: {len(df)}") # <-- Лог 2
#         if df.empty:
#             logging.warning(f"[read_player_history DEBUG] DataFrame пуст после обработки дат")
#             return []
#         logging.debug(f"[read_player_history DEBUG] Первые 5 строк ПОСЛЕ ОБРАБОТКИ ДАТ:\n{df.head().to_string()}") # <-- Лог 3
#
#         # --- Преобразование Цены ---
#         logging.debug("[read_player_history DEBUG] Обработка Цены...")
#         # Пытаемся преобразовать колонку 'Цена' в числовой формат
#         # Убираем запятые и пробелы, которые могут мешать
#         df['price'] = pd.to_numeric(df['Цена'].astype(str).str.replace(',', '').str.replace(' ', ''), errors='coerce')
#         original_count = len(df)
#         # Удаляем строки, где цена не смогла преобразоваться (NaN) или стала бесконечной (inf)
#         df = df.dropna(subset=['price'])
#         df = df[np.isfinite(df['price'])]
#         dropped_prices = original_count - len(df)
#         if dropped_prices > 0:
#             logging.warning(f"[read_player_history DEBUG] Удалено строк из-за невалидной/бесконечной цены: {dropped_prices}")
#         logging.info(f"[read_player_history DEBUG] Строк ПОСЛЕ ОБРАБОТКИ ЦЕН: {len(df)}") # <-- Лог 4
#         if df.empty:
#             logging.warning(f"[read_player_history DEBUG] DataFrame пуст после обработки цен")
#             return []
#         logging.debug(f"[read_player_history DEBUG] Первые 5 строк ПОСЛЕ ОБРАБОТКИ ЦЕН:\n{df.head().to_string()}") # <-- Лог 5
#
#         # --- Финальная обработка: Выбор колонок, сортировка, удаление дубликатов ---
#         # Проверяем наличие нужных колонок еще раз (на всякий случай)
#         if 'date' not in df.columns or 'price' not in df.columns:
#             logging.error(f"[read_player_history DEBUG] КРИТИЧЕСКАЯ ОШИБКА: Отсутствуют колонки 'date' или 'price' перед финальным преобразованием.")
#             return []
#
#         # Выбираем только нужные колонки, сортируем по дате
#         df_final = df[['date', 'price']].sort_values(by='date').reset_index(drop=True)
#
#         # Удаляем дубликаты по дате, оставляя последнее значение за каждую дату
#         original_count = len(df_final)
#         df_final = df_final.drop_duplicates(subset=['date'], keep='last')
#         dropped_dups = original_count - len(df_final)
#         if dropped_dups > 0:
#             logging.info(f"[read_player_history DEBUG] Удалено дубликатов по дате: {dropped_dups}.")
#
#         logging.info(f"[read_player_history DEBUG] Строк ПОСЛЕ УДАЛЕНИЯ ДУБЛИКАТОВ: {len(df_final)}") # <-- Лог 6
#         if df_final.empty:
#             logging.warning(f"[read_player_history DEBUG] DataFrame пуст после удаления дубликатов")
#             return []
#         logging.debug(f"[read_player_history DEBUG] Первые 5 строк ПОСЛЕ УДАЛЕНИЯ ДУБЛИКАТОВ:\n{df_final.head().to_string()}") # <-- Лог 7
#
#         # --- Преобразование в список словарей ---
#         history_list = df_final.to_dict('records')
#         logging.info(f"[read_player_history DEBUG] УСПЕШНО: Возвращено {len(history_list)} записей для {player_name}.") # <-- Лог 8
#         return history_list
#
#     except FileNotFoundError:
#         # Эта ошибка не должна возникать, так как проверка есть в начале, но для полноты
#         logging.warning(f"[read_player_history DEBUG] Файл исчез во время обработки (FileNotFoundError): {filepath}")
#         return []
#     except Exception as e:
#         logging.error(f"[read_player_history DEBUG] НЕОЖИДАННАЯ КРИТИЧЕСКАЯ ОШИБКА при чтении/обработке {filepath}: {e}", exc_info=True)
#         return []
#
#
# # --- Остальные функции анализа (БЕЗ ИЗМЕНЕНИЙ) ---
#
# def get_all_players():
#     """Возвращает список имен игроков из имен CSV файлов в DATA_DIR."""
#     players = []
#     if not os.path.isdir(DATA_DIR):
#         logging.warning(f"[cycle] Папка данных {DATA_DIR} не найдена.")
#         return []
#     try:
#         for f in os.listdir(DATA_DIR):
#             # Учитываем только .csv файлы, не скрытые
#             if f.endswith(".csv") and not f.startswith('.'):
#                 # Преобразуем имя файла (с подчеркиваниями) в имя игрока (с пробелами)
#                 player_name = os.path.splitext(f)[0].replace("_", " ")
#                 players.append(player_name)
#     except Exception as e:
#         logging.error(f"Ошибка чтения списка файлов из директории {DATA_DIR}: {e}")
#         return []
#     if not players:
#         logging.warning(f"[cycle] В папке {DATA_DIR} не найдено CSV файлов игроков.")
#     else:
#         logging.info(f"[cycle] Найдено {len(players)} CSV файлов игроков в {DATA_DIR}.")
#     return players
#
# def analyze_day_of_week(player_name):
#     """Анализирует среднюю, мин, макс цену по дням недели."""
#     data = read_player_history(player_name) # Используем обновленную функцию чтения
#     if not data:
#         logging.warning(f"[analyze_day_of_week] Нет истории для {player_name}")
#         return {}
#     stats = {dow: {"count": 0, "sum_price": 0.0, "min_price": float('inf'), "max_price": float('-inf')} for dow in range(7)}
#     valid_records = 0
#     for row in data:
#         price = row.get("price")
#         date = row.get("date")
#         if price is not None and np.isfinite(price) and date is not None and isinstance(date, datetime):
#             try:
#                 st = stats[date.weekday()]
#                 st["count"] += 1
#                 st["sum_price"] += price
#                 st["min_price"] = min(st["min_price"], price)
#                 st["max_price"] = max(st["max_price"], price)
#                 valid_records += 1
#             except Exception as e_dow:
#                  logging.warning(f"[analyze_day_of_week] Ошибка обработки записи {row} для {player_name}: {e_dow}")
#
#     if valid_records == 0:
#         logging.warning(f"[analyze_day_of_week] Нет валидных записей для анализа DOW у {player_name}")
#         return {}
#
#     for st in stats.values():
#         st["avg_price"] = st["sum_price"] / st["count"] if st["count"] > 0 else 0.0
#         # Заменяем inf на None для удобства
#         if st["min_price"] == float('inf'): st["min_price"] = None
#         if st["max_price"] == float('-inf'): st["max_price"] = None
#     logging.debug(f"[analyze_day_of_week] Анализ DOW для {player_name} завершен ({valid_records} записей).")
#     return stats
#
# def analyze_cycle(player_name, cycle_length=7):
#     """Анализирует среднюю, мин, макс цену по шагам цикла (устарело, не используется?)."""
#     logging.warning("[analyze_cycle] Функция analyze_cycle устарела и может быть неэффективной/неправильной.")
#     data = read_player_history(player_name)
#     # Фильтруем валидные данные
#     valid_data = [r for r in data if r.get('price') is not None and np.isfinite(r['price'])]
#     if not valid_data or len(valid_data) < cycle_length:
#         logging.warning(f"[cycle] Мало валидных данных ({len(valid_data)}) для {cycle_length}-дн анализа цикла {player_name}")
#         return []
#     cycle_stats = [{"step": i, "count": 0, "sum_price": 0.0, "min_price": float('inf'), "max_price": float('-inf')} for i in range(cycle_length)]
#     for i, row in enumerate(valid_data):
#             try:
#                 st = cycle_stats[i % cycle_length]
#                 st["count"] += 1
#                 st["sum_price"] += row["price"]
#                 st["min_price"] = min(st["min_price"], row["price"])
#                 st["max_price"] = max(st["max_price"], row["price"])
#             except Exception as e_cycle:
#                 logging.warning(f"[analyze_cycle] Ошибка обработки записи {row} на шаге {i} для {player_name}: {e_cycle}")
#
#     for st in cycle_stats:
#         st["avg_price"] = st["sum_price"] / st["count"] if st["count"] > 0 else 0.0
#         if st["min_price"] == float('inf'): st["min_price"] = None
#         if st["max_price"] == float('-inf'): st["max_price"] = None
#     logging.debug(f"[analyze_cycle] Анализ {cycle_length}-дневного цикла для {player_name} завершен.")
#     return cycle_stats
#
# # --- Функции для генерации текстовых сигналов (используются в signals.py) ---
#
# def create_seasonal_signal_example(player_name):
#     """Создает простой сезонный сигнал на основе DOW (среднее дня vs глобальное)."""
#     data_dow = analyze_day_of_week(player_name)
#     if not data_dow: return "NEUTRAL (нет DOW данных)"
#
#     try:
#         dow_now = datetime.now(timezone.utc).weekday()
#         day_stats = data_dow.get(dow_now)
#         if not day_stats or day_stats.get("count", 0) < 1:
#             return "NEUTRAL (мало данных DOW)" # Мало данных именно за этот день недели
#
#         # Рассчитываем глобальную среднюю цену по всем дням, где есть данные
#         all_sum, all_count, valid_days = 0.0, 0, 0
#         for st in data_dow.values():
#             # Учитываем только дни с данными и ненулевой средней ценой
#             if st.get("count", 0) > 0 and st.get("avg_price") is not None and st.get("avg_price") > 0:
#                 all_sum += st["sum_price"]
#                 all_count += st["count"]
#                 valid_days += 1
#
#         if all_count == 0 or valid_days < 2: # Нужно хотя бы 2 дня для сравнения
#             return "NEUTRAL (мало данных DOW для сравнения)"
#
#         global_avg = all_sum / all_count
#         day_avg = day_stats.get("avg_price")
#
#         if day_avg is None or day_avg <= 0:
#              return "NEUTRAL (нет ср. цены DOW)"
#
#         # Порог для сравнения (например, 1% от глобальной средней)
#         threshold = global_avg * 0.01
#
#         if day_avg < global_avg - threshold:
#             return "BUY (avg DOW < global avg)"
#         elif day_avg > global_avg + threshold:
#             return "SELL (avg DOW > global avg)"
#         else:
#             return "NEUTRAL (avg DOW ≈ global avg)"
#     except Exception as e:
#         logging.error(f"[create_seasonal_signal_example] Ошибка для {player_name}: {e}")
#         return "NEUTRAL (ошибка DOW анализа)"
#
# def create_dow_range_signal(player_name, current_price, lower=0.2, upper=0.8):
#     """Создает сигнал на основе положения текущей цены в диапазоне [min, max] текущего дня недели."""
#     if current_price is None or not np.isfinite(current_price) or current_price <= 0:
#         return "NEUTRAL (цена?)"
#
#     stats_dow = analyze_day_of_week(player_name)
#     if not stats_dow:
#         return "NEUTRAL (нет DOW данных)"
#
#     try:
#         dow_now = datetime.now(timezone.utc).weekday()
#         day_stats = stats_dow.get(dow_now)
#
#         # Требуем больше данных для оценки диапазона (например, 5)
#         if not day_stats or day_stats.get("count", 0) < 5:
#             return "NEUTRAL (мало данных DOW для диапазона)"
#
#         h_min = day_stats.get("min_price")
#         h_max = day_stats.get("max_price")
#
#         # Проверяем, что min/max валидны и min < max
#         if h_min is None or h_max is None or h_min >= h_max:
#             return "NEUTRAL (диапазон DOW?)"
#
#         d_range = h_max - h_min
#         pos = (current_price - h_min) / d_range if d_range > 1e-9 else 0.5 # Позиция 0..1
#         pos = max(0.0, min(1.0, pos)) # Ограничиваем 0..1
#
#         mn_s = f"{h_min:,.0f}".replace(",", "\u00A0") # Форматирование с неразрывным пробелом
#         mx_s = f"{h_max:,.0f}".replace(",", "\u00A0")
#         pos_s = f"{pos*100:.0f}%"
#
#         if pos <= lower:
#             return f"BUY (в нижних {pos_s} диапазона DOW {mn_s}-{mx_s})"
#         elif pos >= upper:
#             return f"SELL (в верхних {pos_s} диапазона DOW {mn_s}-{mx_s})"
#         else:
#             return f"NEUTRAL (в середине {pos_s} диапазона DOW {mn_s}-{mx_s})"
#     except Exception as e:
#         logging.error(f"[create_dow_range_signal] Ошибка для {player_name}: {e}")
#         return "NEUTRAL (ошибка DOW range)"
#
#
# def create_10_day_trend_signal(player_name, thresh_std=1.0):
#     """Создает сигнал на основе сравнения средней цены за последние 10 дней с базовым периодом (предыдущие 10 дней), нормализованного на СКО базы."""
#     history = read_player_history(player_name)
#     # Используем уже реализованный _calculate_trend_sko, который содержит всю логику
#     try:
#         now_utc = datetime.now(timezone.utc)
#         # Передаем историю и текущую дату
#         # Важно: traceback._calculate_trend_sko - это неправильно, нужно импортировать из signals
#         # Правильнее было бы передать результат _calculate_trend_sko из signals.py
#         # или вынести _calculate_trend_sko в этот модуль. Пока оставим как есть, но это слабое место.
#         # Предполагаем, что traceback тут для примера и в signals.py используется прямой вызов.
#         # Корректный вызов, если функция _calculate_trend_sko будет в ЭТОМ модуле:
#         # dev_std = _calculate_trend_sko(history, now_utc)
#
#         # !!! ВНИМАНИЕ: Этот код сейчас НЕ РАБОТАЕТ правильно, так как _calculate_trend_sko не определена здесь.
#         # !!! Сигнал будет всегда "NEUTRAL (ошибка тренда)", пока зависимость не будет исправлена.
#         # !!! ПРАВИЛЬНОЕ РЕШЕНИЕ: Использовать значение 'trend_10d_deviation_sko' из словаря result в signals.py
#
#         # --- Код для расчета средних и текста (повторяется из _calculate_trend_sko) ---
#         # Оставим заглушку, так как расчет здесь некорректен
#         logging.warning(f"[create_10_day_trend_signal] Зависимость от функции _calculate_trend_sko из signals.py не разрешена. Сигнал будет нейтральным.")
#         return "NEUTRAL (ошибка зависимости)"
#         # --- Ниже код, который НЕ будет выполнен из-за ошибки выше ---
#         # t10 = now_utc - timedelta(days=10)
#         # t20 = now_utc - timedelta(days=20)
#         # valid_history = [r for r in history if r.get('date') and isinstance(r['date'], datetime) and r.get('price') is not None and np.isfinite(r['price'])]
#         # history_before_now = [r for r in valid_history if r['date'] < now_utc]
#         # recent_10d_prices = [r['price'] for r in history_before_now if t10 <= r['date']]
#         # base_10d_prices   = [r['price'] for r in history_before_now if t20 <= r['date'] < t10]
#         #
#         # if len(recent_10d_prices) < 5 or len(base_10d_prices) < 10:
#         #     return "NEUTRAL (мало данных для тренда)"
#         #
#         # try:
#         #      avg10 = np.mean(recent_10d_prices)
#         #      avgB = np.mean(base_10d_prices)
#         #      stdB = np.std(base_10d_prices)
#         #      if stdB > 1e-9:
#         #          dev_std = (avg10 - avgB) / stdB
#         #          if not np.isfinite(dev_std): dev_std = 0.0
#         #      else: dev_std = 0.0
#         #
#         #      avg10_str = f"{avg10:,.0f}".replace(",", "\u00A0")
#         #      avg_base_str = f"{avgB:,.0f}".replace(",", "\u00A0")
#         #      dev_std_str = f"{dev_std:.2f}"
#         #
#         #      if dev_std > thresh_std:
#         #          return f"SELL (avg10d={avg10_str} > base={avg_base_str}, dev={dev_std_str} СКО)"
#         #      elif dev_std < -thresh_std:
#         #          return f"BUY (avg10d={avg10_str} < base={avg_base_str}, dev={dev_std_str} СКО)"
#         #      else:
#         #          return f"NEUTRAL (avg10d={avg10_str} ≈ base={avg_base_str}, dev={dev_std_str} СКО)"
#         #
#         # except Exception as e_calc:
#         #     logging.warning(f"[create_10_day_trend_signal] Ошибка расчета стат. для {player_name}: {e_calc}")
#         #     return "NEUTRAL (ошибка стат. тренда)"
#         # -----------------------------------------------------------------------------
#
#     except Exception as e:
#          logging.error(f"[create_10_day_trend_signal] Ошибка для {player_name}: {e}")
#          return "NEUTRAL (ошибка тренда)"
#
#
# def analyze_day_of_month(player_name):
#     """Анализирует среднюю, мин, макс цену по дням месяца."""
#     data = read_player_history(player_name)
#     if not data:
#         logging.warning(f"[analyze_day_of_month] Нет истории для {player_name}")
#         return {}
#     # Используем defaultdict для удобства
#     stats = defaultdict(lambda: {"count": 0, "sum_price": 0.0, "min_price": float('inf'), "max_price": float('-inf')})
#     valid_records = 0
#     for row in data:
#         price = row.get("price")
#         date = row.get("date")
#         if price is not None and np.isfinite(price) and date is not None and isinstance(date, datetime):
#             try:
#                 st = stats[date.day] # Ключ - день месяца
#                 st["count"] += 1
#                 st["sum_price"] += price
#                 st["min_price"] = min(st["min_price"], row["price"])
#                 st["max_price"] = max(st["max_price"], row["price"])
#                 valid_records += 1
#             except Exception as e_dom:
#                 logging.warning(f"[analyze_day_of_month] Ошибка обработки записи {row} для {player_name}: {e_dom}")
#
#     if valid_records == 0:
#         logging.warning(f"[analyze_day_of_month] Нет валидных записей для анализа DOM у {player_name}")
#         return {}
#
#     # Преобразуем defaultdict в обычный dict и рассчитываем средние
#     proc_stats = {}
#     for day in range(1, 32): # Проходим по всем возможным дням
#         st = stats.get(day, {"count":0, "sum_price":0.0, "min_price":float('inf'), "max_price":float('-inf')})
#         if st["count"] > 0:
#             st["avg_price"] = st["sum_price"] / st["count"]
#             st["min_price"] = None if st["min_price"] == float('inf') else st["min_price"]
#             st["max_price"] = None if st["max_price"] == float('-inf') else st["max_price"]
#         else:
#             # Если данных за день нет, ставим нули/None
#             st["avg_price"], st["min_price"], st["max_price"] = 0.0, None, None
#         proc_stats[day] = st
#     logging.debug(f"[analyze_day_of_month] Анализ DOM для {player_name} завершен ({valid_records} записей).")
#     return proc_stats
#
#
# def create_day_of_month_signal(player_name, thresh_pct=1.0):
#     """Создает простой сезонный сигнал на основе DOM (среднее дня vs глоб.)."""
#     stats_dom = analyze_day_of_month(player_name)
#     if not stats_dom:
#         return "NEUTRAL (нет DOM данных)"
#
#     try:
#         day_now = datetime.now(timezone.utc).day
#         day_stats = stats_dom.get(day_now)
#
#         # Требуем хотя бы 3 наблюдения за этот день месяца
#         if not day_stats or day_stats.get("count", 0) < 3:
#             return "NEUTRAL (мало данных за это число)"
#
#         # Считаем глобальную среднюю
#         all_sum, all_count, valid_days = 0.0, 0, 0
#         for st in stats_dom.values():
#             # Учитываем только дни, где есть валидные данные
#             if st.get("count",0) > 0 and st.get("avg_price", 0) > 0:
#                 all_sum += st["sum_price"]
#                 all_count += st["count"]
#                 valid_days += 1
#
#         # Требуем минимум 10 дней с данными для расчета глобальной средней
#         if all_count == 0 or valid_days < 10:
#             return "NEUTRAL (мало данных DOM для сравнения)"
#
#         glob_avg = all_sum / all_count
#         day_avg = day_stats.get("avg_price")
#
#         if day_avg is None or day_avg <= 0:
#             return "NEUTRAL (нет ср. цены DOM)"
#
#         # Порог в абсолютном значении
#         thresh_v=glob_avg*(thresh_pct/100.0)
#
#         d_str = f"{day_now}-е" # Форматируем день
#         if day_avg < glob_avg - thresh_v:
#             return f"BUY (avg {d_str} < global avg)"
#         elif day_avg > glob_avg + thresh_v:
#             return f"SELL (avg {d_str} > global avg)"
#         else:
#             return f"NEUTRAL (avg {d_str} ≈ global avg)"
#     except Exception as e:
#         logging.error(f"[create_day_of_month_signal] Ошибка для {player_name}: {e}")
#         return "NEUTRAL (ошибка DOM анализа)"
#
#
# def generate_weekly_text_report():
#     """Генерирует текстовый отчет по недельным min/max/avg (устаревший)."""
#     # Эта функция, вероятно, устарела и заменена weekly_stats.py/ohlc_generator.py
#     # Но оставим ее код пока что.
#     logging.warning("[generate_weekly_text_report] Эта функция может быть устаревшей.")
#     out_dir = "seasonal_reports" # Куда сохранять отчет
#     os.makedirs(out_dir, exist_ok=True)
#     out_file = os.path.join(out_dir, "weekly_text_report.txt")
#
#     # Пытается читать из старого файла daily_summary_corrected.csv
#     daily_file = os.path.join(getattr(config, 'REPORTS_DIR', 'daily_reports'), "daily_summary_corrected.csv")
#     if not os.path.isfile(daily_file):
#         logging.warning(f"[cycle] Не найден файл OHLC для недельного отчета: {daily_file}")
#         return
#
#     # Берем данные за последние 7 дней
#     cutoff_utc = (datetime.now(timezone.utc) - timedelta(days=7)).date()
#
#     try:
#         df = pd.read_csv(daily_file, parse_dates=['Дата'])
#
#         # Проверка заголовка
#         if not set(EXPECTED_HEADER_OHLC).issubset(set(df.columns)):
#             logging.error(f"[cycle] Неверный заголовок в {daily_file}. Ожидался: {EXPECTED_HEADER_OHLC}, Найден: {df.columns.tolist()}")
#             return
#
#         # Работа с временными зонами
#         if df['Дата'].dt.tz is None:
#             df['Дата'] = df['Дата'].dt.tz_localize('UTC', ambiguous='infer', nonexistent='shift_forward')
#         else:
#             df['Дата'] = df['Дата'].dt.tz_convert('UTC')
#
#         # Фильтрация по дате и преобразование типов
#         df_f = df[df['Дата'].dt.date >= cutoff_utc].copy()
#         for col in ['Минимум','Максимум','Закрытие']:
#             df_f[col] = pd.to_numeric(df_f[col], errors='coerce') # Ошибки станут NaN
#
#         # Удаляем строки с NaN в ключевых колонках
#         df_f.dropna(subset=['Игрок','Минимум','Максимум','Закрытие'], inplace=True)
#
#         # Группируем и агрегируем
#         stats = df_f.groupby('Игрок').agg(
#             m=('Минимум','min'),
#             M=('Максимум','max'),
#             s=('Закрытие','sum'),
#             c=('Закрытие','count') # Используем count для числа дней с данными
#         ).reset_index()
#
#         if stats.empty:
#             logging.info(f"[cycle] Нет OHLC данных за последние 7 дней в {daily_file}.")
#             return
#
#         now_s = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S %Z')
#         lines = [
#             f"\n=== Отчет от {now_s} ===",
#             f"Период: {cutoff_utc.strftime('%Y-%m-%d')} - {datetime.now(timezone.utc).date().strftime('%Y-%m-%d')} UTC",
#             "Игрок, Нед_Мин, Нед_Макс, Средн_Закр, Дней"
#         ]
#         for _, r in stats.iterrows():
#              avg = r['s']/r['c'] if r['c']>0 else 0
#             # Форматируем вывод
#              lines.append(f"{r['Игрок']},{r['m']:,.0f},{r['M']:,.0f},{avg:,.0f},{int(r['c'])}")
#
#         # Дописываем в файл
#         with open(out_file, "a", encoding="utf-8") as f:
#             f.write("\n".join(lines) + "\n\n")
#         logging.info(f"[cycle] Недельный текстовый отчет ДОПИСАН в: {out_file}")
#
#     except Exception as e:
#         logging.error(f"[cycle] Ошибка генерации недельного текстового отчета из {daily_file}: {e}", exc_info=True)
#
#
# # --- Тестовый блок __main__ ---
# if __name__ == "__main__":
#     # Настройка логирования для теста
#     logging.basicConfig(
#         level=logging.DEBUG, # Установите DEBUG для проверки отсутствия ParserWarning
#         format="%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s"
#     )
#     # Пример игрока, для которого были ParserWarning
#     test_player_warning = "Anirudh Thapa 103"
#     print(f"\n--- Тест чтения истории для (ожидаем БЕЗ ParserWarning): {test_player_warning} ---")
#     history_warning = read_player_history(test_player_warning)
#     if history_warning:
#         print(f"УСПЕШНО Прочитано {len(history_warning)} записей.")
#         # Можно вывести несколько последних записей для проверки
#         # print("Последние 5 записей:")
#         # for record in history_warning[-5:]:
#         #     print(record)
#     else:
#         print(f"НЕ УДАЛОСЬ прочитать историю для {test_player_warning}.")
#
#     # Пример игрока, который читался нормально
#     test_player_ok = "Joško Gvardiol 101"
#     print(f"\n--- Тест чтения истории для: {test_player_ok} ---")
#     history_ok = read_player_history(test_player_ok)
#     if history_ok: print(f"УСПЕШНО Прочитано {len(history_ok)} записей.")
#     else: print(f"НЕ УДАЛОСЬ прочитать историю для {test_player_ok}.")
#
#     # Тест сезонных сигналов
#     print(f"\n--- Тест сезонных сигналов для: {test_player_ok} ---")
#     print(f"DOW Avg: {create_seasonal_signal_example(test_player_ok)}")
#     # Для DOW Range нужен пример текущей цены
#     try:
#         current_price_ok = history_ok[-1]['price'] if history_ok else None
#         if current_price_ok:
#              print(f"DOW Range (тек. цена {current_price_ok:,.0f}): {create_dow_range_signal(test_player_ok, current_price_ok)}")
#         else: print("DOW Range: Не удалось получить текущую цену для теста.")
#     except: print("DOW Range: Ошибка при получении цены для теста.")
#
#     print(f"DOM Avg: {create_day_of_month_signal(test_player_ok)}")
#     print(f"Trend 10d: {create_10_day_trend_signal(test_player_ok)}") # Ожидаем ошибку зависимости

# =============================================
# ФАЙЛ: cycle_analysis.py (ВЕРСИЯ v8.9 - Log N/A Reason)
# - ИЗМЕНЕНО: Добавлено INFO логирование причины возврата фазы 'N/A'
#   (price_range=0 или не найдены пики/впадины).
# - Содержит изменения из v8.8 (Always Return Dict).
# =============================================
import pandas as pd
import numpy as np
from scipy.signal import find_peaks
import logging
import traceback

logger = logging.getLogger("cycle_analysis")

# --- Настройки ---
try:
    import config
    MAIN_CYCLE_SMA_WINDOW = getattr(config, 'MAIN_CYCLE_SMA_WINDOW', 84); MAIN_CYCLE_PEAK_PROMINENCE = getattr(config, 'MAIN_CYCLE_PEAK_PROMINENCE', 0.08); MAIN_CYCLE_TROUGH_PROMINENCE = getattr(config, 'MAIN_CYCLE_TROUGH_PROMINENCE', 0.08); SHORT_CYCLE_SMA_WINDOW = getattr(config, 'SHORT_CYCLE_SMA_WINDOW', 36); SHORT_CYCLE_PEAK_PROMINENCE = getattr(config, 'SHORT_CYCLE_PEAK_PROMINENCE', 0.06); SHORT_CYCLE_TROUGH_PROMINENCE = getattr(config, 'SHORT_CYCLE_TROUGH_PROMINENCE', 0.06)
except Exception as e: logger.error(f"Ошибка config в cycle_analysis: {e}. Дефолты."); MAIN_CYCLE_SMA_WINDOW=84; MAIN_CYCLE_PEAK_PROMINENCE=0.08; MAIN_CYCLE_TROUGH_PROMINENCE=0.08; SHORT_CYCLE_SMA_WINDOW=36; SHORT_CYCLE_PEAK_PROMINENCE=0.06; SHORT_CYCLE_TROUGH_PROMINENCE=0.06

def _create_default_result(error_msg=None):
    """Создает стандартный словарь для возврата."""
    return {'phase': 'Error' if error_msg else 'N/A', 'peaks': [], 'troughs': [], 'last_peak_time': None, 'last_trough_time': None, 'error': error_msg}

def determine_main_cycle_phase_df(df):
    logger.debug("[cycle] Вход в determine_main_cycle_phase_df")
    result = _create_default_result()
    try:
        if df is None or not isinstance(df, pd.DataFrame) or df.empty or 'Цена' not in df.columns:
            result['error'] = "Invalid or empty DataFrame"; logger.warning(f"[cycle] {result['error']}"); return result
        if not isinstance(df.index, pd.DatetimeIndex):
             result['error'] = "Index not DatetimeIndex"; logger.warning(f"[cycle] {result['error']}"); return result
        if len(df) < MAIN_CYCLE_SMA_WINDOW:
            result['error'] = f"Data < SMA window ({len(df)}<{MAIN_CYCLE_SMA_WINDOW})"; logger.warning(f"[cycle] {result['error']}"); return result

        prices = df['Цена'].dropna();
        if prices.empty: result['error'] = "No valid price data"; return result
        smoothed = prices.rolling(window=MAIN_CYCLE_SMA_WINDOW, center=True, min_periods=MAIN_CYCLE_SMA_WINDOW // 2).mean().dropna()
        if smoothed.empty: result['error'] = "Not enough data after smoothing"; return result

        price_range = smoothed.max() - smoothed.min()
        # --- ИЗМЕНЕНО v8.9: Логирование причины N/A (price_range) ---
        if price_range == 0:
            logger.info("[cycle] Phase N/A: Price range after smoothing is zero.")
            return result # Возвращаем N/A по умолчанию
        # -------------------------------------------------------

        min_peak_h = smoothed.min() + price_range * MAIN_CYCLE_PEAK_PROMINENCE; min_trough_d = smoothed.max() - price_range * MAIN_CYCLE_TROUGH_PROMINENCE
        peak_prom = price_range * 0.05; trough_prom = price_range * 0.05
        peaks_idx, _ = find_peaks(smoothed.values, prominence=peak_prom, height=min_peak_h)
        troughs_idx, _ = find_peaks(-smoothed.values, prominence=trough_prom, height=-(min_trough_d))
        peaks_ts = smoothed.index[peaks_idx].tolist(); troughs_ts = smoothed.index[troughs_idx].tolist()
        last_peak = max(peaks_ts) if peaks_ts else None; last_trough = max(troughs_ts) if troughs_ts else None

        phase = 'N/A'
        if last_peak and last_trough:
            if last_peak > last_trough: trend = smoothed.loc[last_peak:].diff().mean() if len(smoothed.loc[last_peak:]) > 1 else 0; phase = 'Downturn' if trend < 0 else 'Peak'
            else: trend = smoothed.loc[last_trough:].diff().mean() if len(smoothed.loc[last_trough:]) > 1 else 0; phase = 'Upturn' if trend > 0 else 'Trough'
        elif last_peak: phase = 'Peak'
        elif last_trough: phase = 'Trough'

        # --- ИЗМЕНЕНО v8.9: Логирование причины N/A (нет пиков/впадин) ---
        if phase == 'N/A' and not peaks_ts and not troughs_ts:
             logger.info("[cycle] Phase N/A: No peaks or troughs found with current settings (prominence/height).")
        # -----------------------------------------------------------

        result.update({ 'phase': phase, 'peaks': [p.isoformat() for p in peaks_ts], 'troughs': [t.isoformat() for t in troughs_ts], 'last_peak_time': last_peak.isoformat() if last_peak else None, 'last_trough_time': last_trough.isoformat() if last_trough else None, 'error': None })
        logger.debug(f"[cycle] Main: {result}")
        return result

    except Exception as e:
        logger.error(f"Критическая ошибка main cycle: {e}", exc_info=True)
        result['error'] = f"Internal error: {e}"; result['phase'] = 'Error'
        return result

def determine_short_cycle_phase_df(df):
    logger.debug("[cycle_short] Вход в determine_short_cycle_phase_df")
    result = _create_default_result()
    try:
        if df is None or not isinstance(df, pd.DataFrame) or df.empty or 'Цена' not in df.columns: result['error'] = "Invalid/empty DataFrame"; logger.warning(f"[cycle_short] {result['error']}"); return result
        if not isinstance(df.index, pd.DatetimeIndex): result['error'] = "Index not DatetimeIndex"; logger.warning(f"[cycle_short] {result['error']}"); return result
        if len(df) < SHORT_CYCLE_SMA_WINDOW: result['error'] = f"Data < SMA window ({len(df)}<{SHORT_CYCLE_SMA_WINDOW})"; logger.warning(f"[cycle_short] {result['error']}"); return result

        prices = df['Цена'].dropna();
        if prices.empty: result['error'] = "No valid price data"; return result
        smoothed = prices.rolling(window=SHORT_CYCLE_SMA_WINDOW, center=True, min_periods=SHORT_CYCLE_SMA_WINDOW // 2).mean().dropna()
        if smoothed.empty: result['error'] = "Not enough data after smoothing"; return result

        price_range = smoothed.max() - smoothed.min()
        # --- ИЗМЕНЕНО v8.9: Логирование причины N/A (price_range) ---
        if price_range == 0:
            logger.info("[cycle_short] Phase N/A: Price range after smoothing is zero.")
            return result
        # -------------------------------------------------------

        peak_prom = price_range * SHORT_CYCLE_PEAK_PROMINENCE; trough_prom = price_range * SHORT_CYCLE_TROUGH_PROMINENCE
        peaks_idx, _ = find_peaks(smoothed.values, prominence=peak_prom)
        troughs_idx, _ = find_peaks(-smoothed.values, prominence=trough_prom)
        peaks_ts = smoothed.index[peaks_idx].tolist(); troughs_ts = smoothed.index[troughs_idx].tolist()
        last_peak = max(peaks_ts) if peaks_ts else None; last_trough = max(troughs_ts) if troughs_ts else None

        phase = 'N/A'
        if last_peak and last_trough:
            if last_peak > last_trough: trend = smoothed.loc[last_peak:].diff().mean() if len(smoothed.loc[last_peak:]) > 1 else 0; phase = 'Downturn' if trend < 0 else 'Peak'
            else: trend = smoothed.loc[last_trough:].diff().mean() if len(smoothed.loc[last_trough:]) > 1 else 0; phase = 'Upturn' if trend > 0 else 'Trough'
        elif last_peak: phase = 'Peak'
        elif last_trough: phase = 'Trough'

        # --- ИЗМЕНЕНО v8.9: Логирование причины N/A (нет пиков/впадин) ---
        if phase == 'N/A' and not peaks_ts and not troughs_ts:
             logger.info("[cycle_short] Phase N/A: No peaks or troughs found with current settings (prominence/height).")
        # -----------------------------------------------------------

        result.update({ 'phase': phase, 'peaks': [p.isoformat() for p in peaks_ts], 'troughs': [t.isoformat() for t in troughs_ts], 'last_peak_time': last_peak.isoformat() if last_peak else None, 'last_trough_time': last_trough.isoformat() if last_trough else None, 'error': None })
        logger.debug(f"[cycle_short] Short: {result}")
        return result
    except Exception as e:
        logger.error(f"Критическая ошибка short cycle: {e}", exc_info=True)
        result['error'] = f"Internal error: {e}"; result['phase'] = 'Error'
        return result