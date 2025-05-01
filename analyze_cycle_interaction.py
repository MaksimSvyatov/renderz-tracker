# =============================================
# ФАЙЛ: analyze_cycle_interaction.py (НОВЫЙ)
# Назначение: Анализ взаимодействия 28-дневного и недельного циклов.
#             Читает историю, рассчитывает статистику и пишет отчет.
# =============================================
import logging
import os
from datetime import datetime, timedelta, timezone
from collections import defaultdict
import statistics # Для median
import pandas as pd # Используем Pandas для удобства агрегации
import config # Для DATA_DIR
import cycle_analysis # Для get_all_players, read_player_history
import events_manager # Для get_current_cycle_day, get_cycle_phase

# --- Настройка ---
OUTPUT_REPORT_FILE = "cycle_interaction_report.txt"
# Минимальное кол-во наблюдений для расчета статистики по (Фаза, DOW)
MIN_OBS_PER_GROUP = 3
# Названия дней недели
DOW_NAMES = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
# Названия фаз (из events_manager)
PHASE_NAMES = list(events_manager.CYCLE_PHASES.keys())

# --- Настройка логирования ---
log_format = "%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s"
logging.basicConfig(level=logging.INFO, format=log_format, handlers=[logging.StreamHandler()])
logging.getLogger('matplotlib').setLevel(logging.WARNING) # На всякий случай

# --- Основная функция анализа ---
def analyze_interactions():
    """Выполняет анализ и генерирует отчет."""
    logging.info("Начало анализа взаимодействия циклов...")
    players = cycle_analysis.get_all_players()
    if not players:
        logging.warning("Не найдены игроки для анализа.")
        return

    all_player_stats = {}
    all_player_peak_days_dow = defaultdict(int)
    all_player_peak_days_cycle = defaultdict(int)
    all_player_peak_phases = defaultdict(int)
    total_cycles_analyzed = 0

    # 1. Анализ для каждого игрока
    for player_name in players:
        logging.info(f"--- Анализ игрока: {player_name} ---")
        history = cycle_analysis.read_player_history(player_name)
        if len(history) < events_manager.CYCLE_LENGTH: # Требуем хотя бы один полный цикл
            logging.warning(f"Недостаточно истории (< {events_manager.CYCLE_LENGTH} записей) для {player_name}. Пропуск.")
            continue

        # --- Анализ 1: Статистика по (Фаза, DOW) ---
        prices_by_phase_dow = defaultdict(lambda: defaultdict(list))
        for record in history:
            price = record.get('price')
            if price is not None:
                record_date = record['date']
                cycle_day = events_manager.get_current_cycle_day(now_dt=record_date)
                phase = events_manager.get_cycle_phase(cycle_day)
                dow = record_date.weekday() # 0 = Пн, 6 = Вс
                if phase != "Фаза неизвестна" and phase != "Фаза не определена":
                    prices_by_phase_dow[phase][dow].append(price)

        player_phase_dow_stats = defaultdict(dict)
        for phase in PHASE_NAMES:
            for dow in range(7):
                prices = prices_by_phase_dow[phase][dow]
                count = len(prices)
                stats = {"count": count, "avg": None, "median": None, "max": None}
                if count >= MIN_OBS_PER_GROUP:
                    try:
                        stats["avg"] = statistics.mean(prices)
                        stats["median"] = statistics.median(prices)
                        stats["max"] = max(prices)
                    except statistics.StatisticsError:
                        logging.warning(f"Ошибка статистики для {player_name}, Фаза={phase}, DOW={DOW_NAMES[dow]}")
                    except Exception as e:
                         logging.error(f"Неожиданная ошибка статистики: {e}")
                player_phase_dow_stats[phase][dow] = stats

        # --- Анализ 2: Дни пиков внутри 28-дневных циклов ---
        player_peak_days_dow = defaultdict(int)
        player_peak_days_cycle = defaultdict(int)
        player_peak_phases = defaultdict(int)
        num_cycles_for_player = 0

        try:
            # Определяем дату начала первого полного цикла в истории
            first_date_in_history = history[0]['date']
            days_from_anchor = (first_date_in_history.date() - datetime.strptime(events_manager.CYCLE_ANCHOR_DATE_STR, "%Y-%m-%d").date()).days
            start_day_of_first_cycle_in_history = (days_from_anchor % events_manager.CYCLE_LENGTH) + 1
            days_to_start_next_cycle = (events_manager.CYCLE_LENGTH - start_day_of_first_cycle_in_history + 1) % events_manager.CYCLE_LENGTH
            first_full_cycle_start_date = first_date_in_history + timedelta(days=days_to_start_next_cycle)

            current_cycle_start_date = first_full_cycle_start_date
            while current_cycle_start_date <= history[-1]['date']:
                cycle_end_date = current_cycle_start_date + timedelta(days=events_manager.CYCLE_LENGTH)
                # Выбираем данные только для текущего 28-дневного окна
                cycle_data = [r for r in history if current_cycle_start_date <= r['date'] < cycle_end_date and r.get('price') is not None]

                if cycle_data:
                    num_cycles_for_player += 1
                    # Находим максимум цены и запись, где он был достигнут
                    max_price_in_cycle = -1
                    peak_record = None
                    for record in cycle_data:
                        if record['price'] > max_price_in_cycle:
                            max_price_in_cycle = record['price']
                            peak_record = record

                    if peak_record:
                        peak_dow = peak_record['date'].weekday()
                        peak_cycle_day = events_manager.get_current_cycle_day(now_dt=peak_record['date'])
                        peak_phase = events_manager.get_cycle_phase(peak_cycle_day)

                        player_peak_days_dow[peak_dow] += 1
                        if peak_cycle_day: player_peak_days_cycle[peak_cycle_day] += 1
                        if peak_phase not in ["Фаза неизвестна", "Фаза не определена"]: player_peak_phases[peak_phase] += 1

                current_cycle_start_date += timedelta(days=events_manager.CYCLE_LENGTH) # Переходим к следующему циклу

        except Exception as peak_e:
            logging.error(f"Ошибка анализа пиков для {player_name}: {peak_e}", exc_info=True)

        # Сохраняем статистику игрока
        all_player_stats[player_name] = {
            "phase_dow_stats": player_phase_dow_stats,
            "peak_dow_freq": player_peak_days_dow,
            "peak_cycle_day_freq": player_peak_days_cycle,
            "peak_phase_freq": player_peak_phases,
            "cycles_analyzed": num_cycles_for_player
        }
        # Добавляем к общей статистике
        if num_cycles_for_player > 0:
             total_cycles_analyzed += num_cycles_for_player
             for dow, count in player_peak_days_dow.items(): all_player_peak_days_dow[dow] += count
             for day, count in player_peak_days_cycle.items(): all_player_peak_days_cycle[day] += count
             for phase, count in player_peak_phases.items(): all_player_peak_phases[phase] += count


    # 3. Формирование отчета
    logging.info("Формирование отчета...")
    report_lines = []
    now_str = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S %Z')
    report_lines.append(f"=== Отчет по взаимодействию циклов от {now_str} ===")
    report_lines.append(f"Проанализировано игроков: {len(all_player_stats)} из {len(players)}")
    report_lines.append(f"Всего 28-дневных циклов проанализировано: {total_cycles_analyzed}")
    report_lines.append("\n--- Общая статистика по дням недели достижения пиков ---")
    if total_cycles_analyzed > 0:
        report_lines.append("День Недели | Кол-во Пиков | Доля (%)")
        report_lines.append("------------|--------------|----------")
        for dow in range(7):
            count = all_player_peak_days_dow[dow]
            share = (count / total_cycles_analyzed * 100) if total_cycles_analyzed > 0 else 0
            report_lines.append(f"{DOW_NAMES[dow]:<11}| {count:<12} | {share:.1f}")
    else:
        report_lines.append("Недостаточно данных для статистики пиков по DOW.")

    report_lines.append("\n--- Общая статистика по фазам цикла достижения пиков ---")
    if total_cycles_analyzed > 0:
        report_lines.append("Фаза Цикла     | Кол-во Пиков | Доля (%)")
        report_lines.append("---------------|--------------|----------")
        for phase in PHASE_NAMES:
            count = all_player_peak_phases[phase]
            share = (count / total_cycles_analyzed * 100) if total_cycles_analyzed > 0 else 0
            report_lines.append(f"{phase:<14}| {count:<12} | {share:.1f}")
    else:
        report_lines.append("Недостаточно данных для статистики пиков по Фазам.")

    # Детализация по игрокам
    for player_name, stats in sorted(all_player_stats.items()):
        report_lines.append(f"\n\n=== Статистика для: {player_name} (циклов: {stats['cycles_analyzed']}) ===")

        # Статистика Фаза+DOW
        report_lines.append("\n--- Средняя цена по (Фаза, День недели) ---")
        report_lines.append("Фаза           | Пн      | Вт      | Ср      | Чт      | Пт      | Сб      | Вс      ")
        report_lines.append("---------------|---------|---------|---------|---------|---------|---------|---------")
        for phase in PHASE_NAMES:
            line = f"{phase:<14} |"
            for dow in range(7):
                avg_price = stats["phase_dow_stats"].get(phase, {}).get(dow, {}).get("avg")
                count = stats["phase_dow_stats"].get(phase, {}).get(dow, {}).get("count", 0)
                if avg_price is not None:
                    # Показываем среднее и кол-во в скобках, если оно > MIN_OBS_PER_GROUP
                    avg_str = f"{avg_price / 1e6:.1f}M" # Форматируем в миллионы
                    line += f" {avg_str:<6}({count}) |" if count >= MIN_OBS_PER_GROUP else f" ({count})    |" # Меньше данных - только кол-во
                else:
                    line += f" N/A ({count})   |"
            report_lines.append(line)

        # Статистика Пиков
        if stats['cycles_analyzed'] > 0:
             report_lines.append("\n--- Частота пиков по Дням Недели ---")
             dow_peaks = [(DOW_NAMES[dow], count) for dow, count in sorted(stats["peak_dow_freq"].items())]
             report_lines.append(", ".join([f"{name}: {c}" for name, c in dow_peaks]))

             report_lines.append("\n--- Частота пиков по Фазам Цикла ---")
             phase_peaks = [(phase, count) for phase, count in sorted(stats["peak_phase_freq"].items())]
             report_lines.append(", ".join([f"{name}: {c}" for name, c in phase_peaks]))

             report_lines.append("\n--- Частота пиков по Дням 28-дневного Цикла (Топ 5) ---")
             cycle_day_peaks = sorted(stats["peak_cycle_day_freq"].items(), key=lambda item: item[1], reverse=True)
             report_lines.append(", ".join([f"День {day}: {c}" for day, c in cycle_day_peaks[:5]]))
        else:
             report_lines.append("\n--- Недостаточно циклов для анализа пиков ---")


    # 4. Запись отчета в файл
    try:
        with open(OUTPUT_REPORT_FILE, "w", encoding="utf-8") as f:
            f.write("\n".join(report_lines))
        logging.info(f"Отчет успешно сохранен в: {OUTPUT_REPORT_FILE}")
    except IOError as e:
        logging.error(f"Ошибка записи отчета {OUTPUT_REPORT_FILE}: {e}")
    except Exception as e:
        logging.error(f"Неизвестная ошибка при записи отчета: {e}", exc_info=True)

# --- Точка входа ---
if __name__ == "__main__":
    analyze_interactions()
    logging.info("Анализ взаимодействия циклов завершен.")