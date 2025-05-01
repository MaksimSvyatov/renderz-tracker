# # =============================================
# # ФАЙЛ: extended_analytics.py (ФИНАЛЬНАЯ ВЕРСИЯ - дозапись summary_*.txt)
# # =============================================
# import os
# import csv
# import logging
# from datetime import datetime, timedelta, timezone
# import ohlc_generator
# try:
#     import trends
#     import anomaly_detection
# except ImportError:
#     logging.error("[extended] Не найдены trends/anomaly_detection! Заглушки.")
#     class TrendsStub:
#         def analyze_trends(self, data): logging.warning("trends.py не найден"); return {}
#     class AnomalyStub:
#         def detect_anomalies(self, data): logging.warning("anomaly_detection.py не найден"); return []
#     trends = TrendsStub(); anomaly_detection = AnomalyStub()
# import pandas as pd
# import config
#
# EXPECTED_HEADER_OHLC = ohlc_generator.EXPECTED_HEADER_OHLC
# REPORTS_DIR_DAILY = "daily_reports"
# REPORTS_DIR_EXTENDED = "extended_reports"
#
# # --- Функция загрузки OHLC ---
# def load_daily_ohlc_data_for_analytics(days_back=7):
#     """Загружает OHLC данные за N дней."""
#     daily_file = os.path.join(REPORTS_DIR_DAILY, "daily_summary_corrected.csv")
#     if not os.path.isfile(daily_file): logging.warning(f"[extended] Нет OHLC {daily_file}."); return {}
#     data = {}; cutoff_utc = (datetime.now(timezone.utc) - timedelta(days=days_back)).date()
#     try:
#         df = pd.read_csv(daily_file, parse_dates=['Дата'])
#         if not set(EXPECTED_HEADER_OHLC).issubset(set(df.columns)): logging.error(f"[ext] Заголовок {daily_file}"); return {}
#         if df['Дата'].dt.tz is not None: df['Дата'] = df['Дата'].dt.tz_convert('UTC')
#         df_f = df[df['Дата'].dt.date >= cutoff_utc].copy()
#         for col in ['Закрытие','Минимум','Максимум']: df_f[col] = pd.to_numeric(df_f[col], errors='coerce')
#         df_f['Изменение цены (%)'] = pd.to_numeric(df_f['Изменение цены (%)'].astype(str).str.replace('%',''), errors='coerce').fillna(0.0)
#         df_f.dropna(subset=['Игрок','Дата','Закрытие','Минимум','Максимум'], inplace=True)
#         for _, r in df_f.iterrows():
#              d_str = r['Дата'].strftime('%Y-%m-%d')
#              data[(r['Игрок'], d_str)] = {"close": r['Закрытие'], "pct": r['Изменение цены (%)'], "min": r['Минимум'], "max": r['Максимум']}
#         logging.info(f"[ext] Загружено {len(data)} OHLC за {days_back} дн.")
#         return data
#     except Exception as e: logging.error(f"[ext] Ошибка чтения {daily_file}: {e}", exc_info=True); return {}
#
# def get_day_name(date_str):
#     """Возвращает сокращенное имя дня недели (Пн, Вт, ...)."""
#     try: dt = datetime.strptime(date_str, "%Y-%m-%d"); return ["Пн","Вт","Ср","Чт","Пт","Сб","Вс"][dt.weekday()]
#     except: return "?"
#
# # --- generate_period_report (ДОЗАПИСЬ 'a') ---
# def generate_period_report(period_days=7):
#     """Генерирует текстовый отчет за период и ДОПИСЫВАЕТ его в файл."""
#     report_lines = []; ohlc_data = load_daily_ohlc_data_for_analytics(days_back=period_days)
#     if not ohlc_data: logging.warning(f"[ext] Нет OHLC за {period_days} дн."); return f"Нет OHLC {period_days} дн."
#     pl_stats = {}; o_min_c, o_max_c = float('inf'), float('-inf'); o_min_p, o_min_d, o_max_p, o_max_d = None, None, None, None
#     for (pl, dt_str), d in ohlc_data.items():
#         min_p, max_p, close_p = d["min"], d["max"], d["close"]
#         if pl not in pl_stats: pl_stats[pl] = {"min_p": min_p, "min_d": dt_str, "max_p": max_p, "max_d": dt_str}
#         else:
#             if min_p < pl_stats[pl]["min_p"]: pl_stats[pl]["min_p"], pl_stats[pl]["min_d"] = min_p, dt_str
#             if max_p > pl_stats[pl]["max_p"]: pl_stats[pl]["max_p"], pl_stats[pl]["max_d"] = max_p, dt_str
#         if close_p < o_min_c: o_min_c, o_min_p, o_min_d = close_p, pl, dt_str
#         if close_p > o_max_c: o_max_c, o_max_p, o_max_d = close_p, pl, dt_str
#     # Формирование текста
#     now_s = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S %Z')
#     report_lines.append(f"\n=== Отчет за {period_days} дней от {now_s} ===")
#     report_lines.append("Экстремумы (дневные Min/Max) по игрокам:")
#     for pl, st in sorted(pl_stats.items()): report_lines.append(f"{pl}:\n  Мин: {st['min_p']:,.0f} ({st['min_d']} {get_day_name(st['min_d'])})\n  Макс: {st['max_p']:,.0f} ({st['max_d']} {get_day_name(st['max_d'])})".replace(",", "\u00A0"))
#     report_lines.append("\nСводка экстремумов:"); report_lines.append("Игрок,Период_Мин,Дата_Мин,Период_Макс,Дата_Макс")
#     for pl, st in sorted(pl_stats.items()): report_lines.append(f"{pl},{st['min_p']:,.0f},{st['min_d']},{st['max_p']:,.0f},{st['max_d']}".replace(",", "\u00A0"))
#     report_lines.append("\nОбщие экстремумы рынка (Close):")
#     if o_min_c == float('inf'): report_lines.extend(["min_overall: N/A", "max_overall: N/A"])
#     else:
#         report_lines.append(f"min_overall,{o_min_d} ({get_day_name(o_min_d)}),{o_min_c:,.0f},{o_min_p}".replace(",", "\u00A0"))
#         report_lines.append(f"max_overall,{o_max_d} ({get_day_name(o_max_d)}),{o_max_c:,.0f},{o_max_p}".replace(",", "\u00A0"))
#     # Запись в файл с ДОЗАПИСЬЮ
#     os.makedirs(REPORTS_DIR_EXTENDED, exist_ok=True)
#     report_path = os.path.join(REPORTS_DIR_EXTENDED, f"summary_{period_days}d.txt")
#     try:
#         with open(report_path, "a", encoding="utf-8") as f: f.write("\n".join(report_lines) + "\n\n") # Режим "a"
#         logging.info(f"[ext] Отчет за {period_days} дней ДОПИСАН в: {report_path}")
#     except Exception as e: logging.error(f"[ext] Ошибка дозаписи {report_path}: {e}")
#     return "\n".join(report_lines)
#
# # --- run_extended_analytics и generate_monday_summaries ---
# def run_extended_analytics():
#     logging.info("[extended] Запуск расширенной аналитики")
#     generate_period_report(period_days=7)
#     daily_data_7d = load_daily_ohlc_data_for_analytics(days_back=7)
#     if daily_data_7d:
#         anomalies = anomaly_detection.detect_anomalies(daily_data_7d)
#         if anomalies:
#             anomaly_path = os.path.join(REPORTS_DIR_EXTENDED, "anomalies_7d.txt")
#             try:
#                 with open(anomaly_path, "w", encoding="utf-8") as f: # Аномалии перезаписываем
#                      f.write(f"=== Аномалии (> +/-8%) от {datetime.now(timezone.utc).strftime('%Y-%m-%d')} ===\n")
#                      for a in anomalies: f.write(f"- {a['player']} {a['date']}: Изм. {a['price_change_pct']:.2f}%\n")
#                 logging.info(f"Отчет аномалий: {anomaly_path}")
#             except Exception as e: logging.error(f"Ошибка записи аномалий: {e}")
#     generate_monday_summaries()
#     logging.info("[extended] Расширенная аналитика завершена")
#
# def generate_monday_summaries():
#     # if datetime.today().weekday() != 0: return {}
#     period_list = [14, 21, 28, 30, 35, 42, 60, 90]; summaries = {}
#     logging.info(f"[extended] Генерация отчетов за периоды: {period_list}")
#     for period in period_list: summaries[period] = generate_period_report(period) # Дописывает
#     return summaries
#
# if __name__ == "__main__":
#     logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
#     run_extended_analytics()

# =============================================
# ФАЙЛ: extended_analytics.py (ВЕРСИЯ v2 - Фикс AttributeError)
# - Удален импорт ohlc_generator
# - Используется config.EXPECTED_HEADER_OHLC
# - Добавлен import config (если не было)
# =============================================
import os
import csv
import logging
from datetime import datetime, timedelta, timezone
# import ohlc_generator # <--- УДАЛЕНО
try:
    import trends
    import anomaly_detection
except ImportError:
    logging.error("[extended] Не найдены trends/anomaly_detection! Заглушки.")
    class TrendsStub:
        def analyze_trends(self, data): logging.warning("trends.py не найден"); return {}
    class AnomalyStub:
        def detect_anomalies(self, data): logging.warning("anomaly_detection.py не найден"); return []
    trends = TrendsStub(); anomaly_detection = AnomalyStub()
import pandas as pd
import config # <--- УБЕДИТЕСЬ, ЧТО ОН ЕСТЬ

# Используем константу из config
EXPECTED_HEADER_OHLC = config.EXPECTED_HEADER_OHLC # <--- ИЗМЕНЕНО
REPORTS_DIR_DAILY = getattr(config, 'REPORTS_DIR', "daily_reports") # Используем из config (для дневных)
REPORTS_DIR_EXTENDED = "extended_reports" # Оставляем как есть, или можно добавить в config

# --- Функция загрузки OHLC ---
def load_daily_ohlc_data_for_analytics(days_back=7):
    """Загружает OHLC данные за N дней."""
    daily_file = os.path.join(REPORTS_DIR_DAILY, "daily_summary_corrected.csv")
    if not os.path.isfile(daily_file):
        logging.warning(f"[extended] Нет OHLC файла: {daily_file}.")
        return {}

    data = {}
    cutoff_utc = (datetime.now(timezone.utc) - timedelta(days=days_back)).date()
    try:
        df = pd.read_csv(daily_file, parse_dates=['Дата'])
        # Используем config.EXPECTED_HEADER_OHLC для проверки
        if not set(config.EXPECTED_HEADER_OHLC).issubset(set(df.columns)):
             logging.error(f"[ext] Неверный заголовок в {daily_file}. Ожидался подмножество: {config.EXPECTED_HEADER_OHLC}, Найден: {df.columns.tolist()}")
             return {}

        # Обработка Timezone
        if df['Дата'].dt.tz is None:
            df['Дата'] = df['Дата'].dt.tz_localize('UTC', ambiguous='infer', nonexistent='shift_forward')
        else:
            df['Дата'] = df['Дата'].dt.tz_convert('UTC')

        df_f = df[df['Дата'].dt.date >= cutoff_utc].copy()

        # Преобразование колонок в числовой тип
        for col in ['Закрытие','Минимум','Максимум']:
            df_f[col] = pd.to_numeric(df_f[col], errors='coerce')
        # Преобразуем процент изменения, убирая знак '%'
        df_f['Изменение цены (%)'] = pd.to_numeric(df_f['Изменение цены (%)'].astype(str).str.replace('%',''), errors='coerce').fillna(0.0)

        # Удаляем строки с NaN в ключевых колонках
        df_f.dropna(subset=['Игрок','Дата','Закрытие','Минимум','Максимум'], inplace=True)

        # Формируем словарь данных
        for _, r in df_f.iterrows():
             d_str = r['Дата'].strftime('%Y-%m-%d')
             # Сохраняем данные для ключа (игрок, дата)
             data[(r['Игрок'], d_str)] = {
                 "close": r['Закрытие'],
                 "pct": r['Изменение цены (%)'],
                 "min": r['Минимум'],
                 "max": r['Максимум']
             }
        logging.info(f"[ext] Загружено {len(data)} записей OHLC за последние {days_back} дней.")
        return data
    except FileNotFoundError:
        logging.error(f"[ext] Не найден файл OHLC: {daily_file}")
        return {}
    except Exception as e:
        logging.error(f"[ext] Ошибка чтения/обработки {daily_file}: {e}", exc_info=True)
        return {}

def get_day_name(date_str):
    """Возвращает сокращенное имя дня недели (Пн, Вт, ...)."""
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        return ["Пн","Вт","Ср","Чт","Пт","Сб","Вс"][dt.weekday()]
    except ValueError:
        logging.warning(f"[ext] Не удалось определить день недели для '{date_str}'")
        return "?"

# --- generate_period_report (ДОЗАПИСЬ 'a') ---
def generate_period_report(period_days=7):
    """Генерирует текстовый отчет за период и ДОПИСЫВАЕТ его в файл."""
    report_lines = []
    ohlc_data = load_daily_ohlc_data_for_analytics(days_back=period_days)
    if not ohlc_data:
        logging.warning(f"[ext] Нет OHLC данных для генерации отчета за {period_days} дней.")
        # Создаем пустой отчет, если нет данных, чтобы файл все равно создался/обновился
        report_text = f"\n=== Отчет за {period_days} дней от {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S %Z')} ===\nНет OHLC данных для анализа за указанный период.\n"
    else:
        pl_stats = {}
        o_min_c, o_max_c = float('inf'), float('-inf')
        o_min_p, o_min_d, o_max_p, o_max_d = None, None, None, None

        # Агрегация статистики по игрокам
        for (pl, dt_str), d in ohlc_data.items():
            min_p, max_p, close_p = d["min"], d["max"], d["close"]
            # Пропускаем, если данные некорректны (хотя load_daily_ohlc_data_for_analytics должна их отфильтровать)
            if pd.isna(min_p) or pd.isna(max_p) or pd.isna(close_p): continue

            if pl not in pl_stats:
                pl_stats[pl] = {"min_p": min_p, "min_d": dt_str, "max_p": max_p, "max_d": dt_str}
            else:
                if min_p < pl_stats[pl]["min_p"]:
                    pl_stats[pl]["min_p"], pl_stats[pl]["min_d"] = min_p, dt_str
                if max_p > pl_stats[pl]["max_p"]:
                    pl_stats[pl]["max_p"], pl_stats[pl]["max_d"] = max_p, dt_str

            # Общие экстремумы по цене закрытия
            if close_p < o_min_c: o_min_c, o_min_p, o_min_d = close_p, pl, dt_str
            if close_p > o_max_c: o_max_c, o_max_p, o_max_d = close_p, pl, dt_str

        # Формирование текста отчета
        now_s = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S %Z')
        report_lines.append(f"\n=== Отчет за {period_days} дней от {now_s} ===")
        report_lines.append("Экстремумы (дневные Min/Max) по игрокам:")
        for pl, st in sorted(pl_stats.items()):
            report_lines.append(f"{pl}:\n  Мин: {st['min_p']:,.0f} ({st['min_d']} {get_day_name(st['min_d'])})\n  Макс: {st['max_p']:,.0f} ({st['max_d']} {get_day_name(st['max_d'])})".replace(",", "\u00A0"))

        report_lines.append("\nСводка экстремумов (Мин/Макс за период):")
        report_lines.append("Игрок; Период_Мин; Дата_Мин; Период_Макс; Дата_Макс") # Используем ; как разделитель для CSV-подобного вида
        for pl, st in sorted(pl_stats.items()):
             report_lines.append(f"{pl}; {st['min_p']:,.0f}; {st['min_d']}; {st['max_p']:,.0f}; {st['max_d']}".replace(",", "\u00A0"))

        report_lines.append("\nОбщие экстремумы рынка (по цене закрытия):")
        if o_min_c == float('inf'):
             report_lines.extend(["Минимум рынка: N/A", "Максимум рынка: N/A"])
        else:
             report_lines.append(f"Минимум рынка; {o_min_d} ({get_day_name(o_min_d)}); {o_min_c:,.0f}; {o_min_p}".replace(",", "\u00A0"))
             report_lines.append(f"Максимум рынка; {o_max_d} ({get_day_name(o_max_d)}); {o_max_c:,.0f}; {o_max_p}".replace(",", "\u00A0"))
        report_text = "\n".join(report_lines) + "\n"

    # Запись в файл с ДОЗАПИСЬЮ
    os.makedirs(REPORTS_DIR_EXTENDED, exist_ok=True)
    report_path = os.path.join(REPORTS_DIR_EXTENDED, f"summary_{period_days}d.txt")
    try:
        with open(report_path, "a", encoding="utf-8") as f: # Режим "a"
            f.write(report_text + "\n") # Добавляем доп. перенос строки между отчетами
        logging.info(f"[ext] Отчет за {period_days} дней ДОПИСАН в: {report_path}")
    except Exception as e:
        logging.error(f"[ext] Ошибка дозаписи отчета {report_path}: {e}")

    return report_text # Возвращаем текст отчета

# --- run_extended_analytics и generate_monday_summaries ---
def run_extended_analytics():
    """Запускает генерацию всех расширенных отчетов."""
    logging.info("[extended] Запуск расширенной аналитики")
    generate_period_report(period_days=7) # Генерируем и дописываем отчет за 7 дней

    # Анализ аномалий (если есть данные)
    daily_data_7d = load_daily_ohlc_data_for_analytics(days_back=7)
    if daily_data_7d:
        try: # Добавляем try-except для безопасности
            anomalies = anomaly_detection.detect_anomalies(daily_data_7d)
            if anomalies:
                anomaly_path = os.path.join(REPORTS_DIR_EXTENDED, "anomalies_7d.txt")
                try:
                    with open(anomaly_path, "w", encoding="utf-8") as f: # Аномалии перезаписываем каждый раз
                         f.write(f"=== Аномалии (> +/-8% дневного изменения) от {datetime.now(timezone.utc).strftime('%Y-%m-%d')} ===\n")
                         for a in anomalies:
                             f.write(f"- {a.get('player', 'N/A')} {a.get('date', 'N/A')}: Изм. {a.get('price_change_pct', 'N/A'):.2f}%\n")
                    logging.info(f"Отчет аномалий сохранен: {anomaly_path}")
                except Exception as e_ano:
                    logging.error(f"Ошибка записи отчета аномалий: {e_ano}")
            else:
                logging.info("[extended] Аномалий за 7 дней не обнаружено.")
        except Exception as e_det:
             logging.error(f"[extended] Ошибка при вызове detect_anomalies: {e_det}", exc_info=True)
    else:
        logging.warning("[extended] Нет данных для детекции аномалий.")

    # Генерация отчетов за разные периоды (дописываются)
    generate_monday_summaries() # Функция теперь только генерирует отчеты

    logging.info("[extended] Расширенная аналитика завершена")

def generate_monday_summaries():
    """Генерирует и дописывает сводки за разные периоды."""
    # Можно добавить проверку дня недели, если нужно запускать только по понедельникам
    # if datetime.now(timezone.utc).weekday() != 0:
    #    logging.info("[extended] Сегодня не понедельник, пропускаем генерацию многопериодных сводок.")
    #    return {}

    period_list = [14, 21, 28, 30, 35, 42, 60, 90]
    summaries = {}
    logging.info(f"[extended] Генерация/дозапись отчетов за периоды: {period_list}")
    for period in period_list:
        summaries[period] = generate_period_report(period) # Генерирует и дописывает
    return summaries # Возвращает сгенерированные тексты отчетов (если нужно)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s')
    run_extended_analytics()