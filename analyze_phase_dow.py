# =============================================
# ФАЙЛ: analyze_phase_dow.py (НОВЫЙ)
# Назначение: Анализ взаимодействия 28-дневного и недельного циклов
#             путем расчета статистики реального изменения цены
#             для каждой комбинации (Фаза, DOW).
#             Записывает результаты в phase_dow_interaction_report.txt.
# ВАЖНО: Может работать дольше на больших данных.
# =============================================
import logging
import os
import csv
from datetime import datetime, timedelta, timezone
import pandas as pd
import numpy as np
import time
from collections import defaultdict
import statistics # Для median, stdev

import config
import cycle_analysis
import events_manager
import storage # Для get_player_filepath

# --- Настройки ---
OUTPUT_REPORT_FILE = "phase_dow_interaction_report.txt"
# Используем тот же порог, что и в signals.py/generate_historical_signals.py для определения Роста/Падения
PRICE_CHANGE_THRESHOLD_PCT = 0.1
# Ожидаемый интервал и допуск для расчета изменения цены (~2ч)
EXPECTED_INTERVAL_HOURS = 2
INTERVAL_TOLERANCE_HOURS = 0.5
# Мин. кол-во наблюдений в группе (Фаза, DOW) для отображения полной статистики
MIN_OBS_FOR_STATS = 5

# Названия дней недели и фаз
DOW_NAMES = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
PHASE_NAMES = list(events_manager.CYCLE_PHASES.keys()) # ["Падение", "Дно/Разворот", ...]

# --- Настройка логирования ---
log_format = "%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s"
logging.basicConfig(level=logging.INFO, format=log_format, handlers=[logging.StreamHandler()])
logging.getLogger('matplotlib').setLevel(logging.WARNING)

# --- Основная функция анализа ---
def analyze_phase_dow_interaction():
    logging.info("Начало анализа взаимодействия Фаза+DOW...")
    players = cycle_analysis.get_all_players()
    if not players: logging.warning("Не найдены игроки."); return

    # Структура для сбора всех валидных изменений цены по группам
    # all_changes[phase][dow] = [список % изменений]
    all_changes_by_phase_dow = defaultdict(lambda: defaultdict(list))
    total_valid_intervals = 0
    processed_players = 0

    for player_name in players:
        logging.info(f"--- Обработка игрока: {player_name} ---")
        history = cycle_analysis.read_player_history(player_name) # list[dict] с aware UTC датами
        if len(history) < 2: continue # Нужно хотя бы 2 записи

        intervals_found = 0
        # Проходим по парам соседних записей
        for i in range(len(history) - 1):
            current_record = history[i]
            next_record = history[i+1]

            current_price = current_record.get('price')
            future_price = next_record.get('price')
            current_time = current_record.get('date')
            future_time = next_record.get('date')

            # Пропускаем, если нет цен или времени
            if None in [current_price, future_price, current_time, future_time] or abs(current_price) < 1e-9:
                continue

            # Проверяем интервал времени
            time_diff_hours = (future_time - current_time).total_seconds() / 3600.0
            min_interval = EXPECTED_INTERVAL_HOURS - INTERVAL_TOLERANCE_HOURS
            max_interval = EXPECTED_INTERVAL_HOURS + INTERVAL_TOLERANCE_HOURS

            if not (min_interval <= time_diff_hours <= max_interval):
                continue # Интервал не подходит

            # Интервал подходит, рассчитываем % изменения
            try:
                price_change_pct = ((future_price - current_price) / current_price) * 100
            except (TypeError, ZeroDivisionError):
                continue # Пропускаем при ошибке расчета

            # Определяем фазу и DOW для НАЧАЛЬНОЙ точки интервала
            cycle_day = events_manager.get_current_cycle_day(now_dt=current_time)
            phase = events_manager.get_cycle_phase(cycle_day)
            dow = current_time.weekday() # 0 = Пн

            if phase != "Фаза неизвестна" and phase != "Фаза не определена":
                all_changes_by_phase_dow[phase][dow].append(price_change_pct)
                intervals_found += 1

        total_valid_intervals += intervals_found
        processed_players += 1
        logging.info(f"Обработано {processed_players}/{len(players)} игроков. Найдено интервалов для {player_name}: {intervals_found}")

    # --- Расчет итоговой статистики и формирование отчета ---
    logging.info("Расчет итоговой статистики...")
    report_lines = []
    now_str = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S %Z')
    report_lines.append(f"=== Отчет по взаимодействию циклов (Фаза+DOW) от {now_str} ===")
    report_lines.append(f"Проанализировано игроков: {processed_players} из {len(players)}")
    report_lines.append(f"Всего проанализировано ~2ч интервалов: {total_valid_intervals}")
    report_lines.append(f"Порог для Роста/Падения: {PRICE_CHANGE_THRESHOLD_PCT}%")
    report_lines.append("-" * 60)
    report_lines.append("\nСтатистика реального % изменения цены для комбинаций (Фаза 28д, День Недели):")
    report_lines.append("(Avg=среднее, Med=медиана, Std=ст.откл, Rise%=доля ростов, Fall%=доля падений, N=кол-во интервалов)")
    report_lines.append("-" * 110)
    header = f"{'Фаза':<14} | {'DOW':<3} | {'Avg(%)':>7} | {'Med(%)':>7} | {'Std(%)':>7} | {'Rise%':>6} | {'Fall%':>6} | {'N':>6}"
    report_lines.append(header)
    report_lines.append("-" * 110)

    aggregated_stats = [] # Собираем все для итоговой сортировки

    for phase in PHASE_NAMES:
        for dow in range(7):
            changes = all_changes_by_phase_dow[phase][dow]
            count = len(changes)
            avg_change, median_change, std_dev, rise_share, fall_share = None, None, None, None, None

            if count >= MIN_OBS_FOR_STATS:
                try: avg_change = statistics.mean(changes)
                except: avg_change = None
                try: median_change = statistics.median(changes)
                except: median_change = None
                try: std_dev = statistics.stdev(changes) if count > 1 else 0.0
                except: std_dev = None
                try:
                    rises = sum(1 for change in changes if change > PRICE_CHANGE_THRESHOLD_PCT)
                    falls = sum(1 for change in changes if change < -PRICE_CHANGE_THRESHOLD_PCT)
                    rise_share = rises / count * 100
                    fall_share = falls / count * 100
                except: rise_share, fall_share = None, None

            line = f"{phase:<14} | {DOW_NAMES[dow]:<3} |"
            line += f" {avg_change:>7.2f} |" if avg_change is not None else "  N/A   |"
            line += f" {median_change:>7.2f} |" if median_change is not None else "  N/A   |"
            line += f" {std_dev:>7.2f} |" if std_dev is not None else "  N/A   |"
            line += f" {rise_share:>5.1f}% |" if rise_share is not None else "  N/A  |"
            line += f" {fall_share:>5.1f}% |" if fall_share is not None else "  N/A  |"
            line += f" {count:>6}"
            report_lines.append(line)

            # Сохраняем статистику для итогового анализа
            if avg_change is not None:
                aggregated_stats.append({
                    "phase": phase, "dow": dow, "dow_name": DOW_NAMES[dow],
                    "avg": avg_change, "median": median_change, "std": std_dev,
                    "rise_pct": rise_share, "fall_pct": fall_share, "count": count
                })

    # --- Дополнительный анализ: Топ комбинаций по среднему/медиане ---
    report_lines.append("\n" + "-" * 60)
    report_lines.append("Топ 5 комбинаций (Фаза, DOW) по Среднему % Изменения:")
    if aggregated_stats:
        top_avg = sorted([s for s in aggregated_stats if s['count'] >= MIN_OBS_FOR_STATS], key=lambda x: x['avg'], reverse=True)
        for i, stat in enumerate(top_avg[:5]):
            report_lines.append(f"{i+1}. {stat['phase']} / {stat['dow_name']} : Avg={stat['avg']:.2f}% (Med={stat['median']:.2f}%, N={stat['count']})")
    else: report_lines.append("Нет данных для анализа.")

    report_lines.append("\nТоп 5 комбинаций (Фаза, DOW) по Медианному % Изменения:")
    if aggregated_stats:
        top_median = sorted([s for s in aggregated_stats if s['count'] >= MIN_OBS_FOR_STATS], key=lambda x: x['median'], reverse=True)
        for i, stat in enumerate(top_median[:5]):
            report_lines.append(f"{i+1}. {stat['phase']} / {stat['dow_name']} : Med={stat['median']:.2f}% (Avg={stat['avg']:.2f}%, N={stat['count']})")
    else: report_lines.append("Нет данных для анализа.")

    report_lines.append("\nТоп 5 комбинаций (Фаза, DOW) по Доле Роста (%):")
    if aggregated_stats:
        top_rise = sorted([s for s in aggregated_stats if s['count'] >= MIN_OBS_FOR_STATS], key=lambda x: x['rise_pct'], reverse=True)
        for i, stat in enumerate(top_rise[:5]):
            report_lines.append(f"{i+1}. {stat['phase']} / {stat['dow_name']} : Rise={stat['rise_pct']:.1f}% (Fall={stat['fall_pct']:.1f}%, N={stat['count']})")
    else: report_lines.append("Нет данных для анализа.")

    report_lines.append("\nТоп 5 комбинаций (Фаза, DOW) по Доле Падения (%):")
    if aggregated_stats:
        top_fall = sorted([s for s in aggregated_stats if s['count'] >= MIN_OBS_FOR_STATS], key=lambda x: x['fall_pct'], reverse=True)
        for i, stat in enumerate(top_fall[:5]):
            report_lines.append(f"{i+1}. {stat['phase']} / {stat['dow_name']} : Fall={stat['fall_pct']:.1f}% (Rise={stat['rise_pct']:.1f}%, N={stat['count']})")
    else: report_lines.append("Нет данных для анализа.")

    # --- Запись отчета в файл ---
    try:
        with open(OUTPUT_REPORT_FILE, "w", encoding="utf-8") as f: # Перезаписываем отчет
            f.write("\n".join(report_lines))
        logging.info(f"Отчет по взаимодействию циклов сохранен в: {OUTPUT_REPORT_FILE}")
    except Exception as e:
        logging.error(f"Ошибка записи отчета {OUTPUT_REPORT_FILE}: {e}", exc_info=True)


# --- Точка входа ---
if __name__ == "__main__":
    start_run_time = time.time()
    analyze_phase_dow_interaction()
    end_run_time = time.time()
    logging.info(f"Анализ взаимодействия циклов завершен за {end_run_time - start_run_time:.1f} сек.")