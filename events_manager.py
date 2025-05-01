# =============================================
# ФАЙЛ: events_manager.py (v2 - Исправлен TypeError с датами)
# =============================================
import json
import os
import logging
from datetime import datetime, timedelta, timezone # Добавлен timezone

EVENTS_FILE = "events_log.json"
try: CONFIG_DIR = os.path.dirname(os.path.abspath(__file__))
except NameError: CONFIG_DIR = os.getcwd()
EVENTS_FILE_PATH = os.path.join(CONFIG_DIR, EVENTS_FILE)

CYCLE_ANCHOR_DATE_STR = "2025-03-06"
CYCLE_LENGTH = 28
CYCLE_PHASES = { "Падение": (1, 4), "Дно/Разворот": (5, 8), "Рост": (9, 23), "Завершение/Пик": (24, 28) }

def load_events():
    """Загружает ДРУГИЕ события из JSON."""
    if not os.path.isfile(EVENTS_FILE_PATH): logging.warning(f"[Events] Файл {EVENTS_FILE_PATH} не найден."); return []
    try:
        with open(EVENTS_FILE_PATH, "r", encoding='utf-8') as f: events = json.load(f)
        if not isinstance(events, list): logging.error(f"[Events] Формат {EVENTS_FILE_PATH} некорректен."); return []
        valid = []
        for e in events:
             if isinstance(e, dict) and e.get("name") and e.get("start_date"):
                 try:
                     # Проверяем формат дат при загрузке
                     datetime.strptime(e["start_date"], "%Y-%m-%d")
                     if e.get("end_date"): datetime.strptime(e["end_date"], "%Y-%m-%d")
                     if e.get("type") != "main_cycle": valid.append(e) # Фильтруем main_cycle
                 except ValueError: logging.warning(f"[Events] Неверный формат даты: {e}")
             else: logging.warning(f"[Events] Пропущено событие: {e}")
        return valid
    except Exception as ex: logging.error(f"[Events] Ошибка {EVENTS_FILE_PATH}: {ex}"); return []

def get_current_cycle_day(anchor_date_str=CYCLE_ANCHOR_DATE_STR, cycle_len=CYCLE_LENGTH, now_dt=None):
    """Рассчитывает текущий день N-дневного цикла (от 1 до N) для now_dt."""
    if now_dt is None: now_dt = datetime.now(timezone.utc) # По умолчанию берем UTC
    # Убедимся, что now_dt aware (если вдруг передали naive)
    if now_dt.tzinfo is None: now_dt = now_dt.replace(tzinfo=timezone.utc)
    else: now_dt = now_dt.astimezone(timezone.utc)

    try:
        # Дату якоря тоже делаем aware UTC
        anchor_date = datetime.strptime(anchor_date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        # Сравниваем aware даты
        delta_days = (now_dt.date() - anchor_date.date()).days
        if delta_days < 0:
            # Не считаем ошибкой для исторических дат, возвращаем None
            return None
        current_day = (delta_days % cycle_len) + 1
        return current_day
    except Exception as e: logging.error(f"[Events] Ошибка расчета дня цикла для {now_dt}: {e}"); return None

def get_cycle_phase(cycle_day, phases=CYCLE_PHASES):
    """Определяет фазу цикла по номеру дня."""
    if cycle_day is None: return "Фаза неизвестна"
    for phase, (start, end) in phases.items():
        if start <= cycle_day <= end: return phase
    return "Фаза не определена"

# --- ИСПРАВЛЕНО ЗДЕСЬ: Работа с Aware Datetimes ---
def get_active_promo_events(events=None, now_dt=None):
     """Находит активные промо-события для now_dt (ожидается aware datetime)."""
     if now_dt is None: now_dt = datetime.now(timezone.utc)
     # Убедимся, что now_dt aware UTC
     if now_dt.tzinfo is None: now_dt = now_dt.replace(tzinfo=timezone.utc)
     else: now_dt = now_dt.astimezone(timezone.utc)

     if events is None: events = load_events()
     active_names = []
     for event in events:
         try:
             # Даты из JSON делаем aware UTC
             start_date = datetime.strptime(event["start_date"], "%Y-%m-%d").replace(tzinfo=timezone.utc)
             end_date_limit = datetime.max.replace(tzinfo=timezone.utc) # Максимальная aware дата

             if "end_date" in event and event["end_date"]:
                 # Конец дня включаем, берем начало СЛЕДУЮЩЕГО дня как границу
                 end_date_limit = datetime.strptime(event["end_date"], "%Y-%m-%d").replace(tzinfo=timezone.utc) + timedelta(days=1)
             elif "duration_days" in event and isinstance(event["duration_days"], int):
                 # Конец интервала - начало следующего дня после окончания длительности
                 end_date_limit = start_date + timedelta(days=event["duration_days"])
             else: # Однодневное событие
                 end_date_limit = start_date + timedelta(days=1)

             # Сравниваем aware datetime с aware datetime
             if start_date <= now_dt < end_date_limit:
                 active_names.append(event.get("name", "Промо"))
         except (ValueError, TypeError) as e:
             # Логируем ОШИБКУ только если now_dt - это текущий момент, иначе это может быть просто историческая проверка
             log_level = logging.ERROR if abs((datetime.now(timezone.utc) - now_dt).total_seconds()) < 60 else logging.WARNING
             logging.log(log_level, f"[Events] Ошибка даты/длительности промо '{event.get('name')}': {e} для даты {now_dt.date()}")
     return active_names

def get_event_phase_details(now_dt=None):
    """Собирает полную информацию о состоянии циклов и событий для now_dt."""
    process_time = now_dt if now_dt is not None else datetime.now(timezone.utc)
    # Убедимся, что process_time aware UTC
    if process_time.tzinfo is None: process_time = process_time.replace(tzinfo=timezone.utc)
    else: process_time = process_time.astimezone(timezone.utc)

    events = load_events() # Загружаем события
    current_day = get_current_cycle_day(now_dt=process_time)
    cycle_phase_name = get_cycle_phase(current_day)
    cycle_phase_str = f"{cycle_phase_name} (День {current_day}/{CYCLE_LENGTH})" if current_day else "Нет данных об осн. цикле"
    active_promos = get_active_promo_events(events, now_dt=process_time) # Передаем aware дату
    details = { "main_cycle_phase_raw": cycle_phase_name, "main_cycle_phase": cycle_phase_str,
                "days_in_cycle": current_day if current_day is not None else 0, # 0 для None
                "other_events": active_promos,
                "is_other_event_active": bool(active_promos) }
    # Логируем только для текущего момента
    if now_dt is None: logging.debug(f"[Events] Детали фазы: {details}")
    return details

def check_event_log_relevance():
     """Проверяет актуальность дат событий."""
     logging.info("[Events] Проверка актуальности данных о событиях...")
     now = datetime.now(timezone.utc); events = load_events()
     needs_update = False; msg_lines = []
     try: anchor_dt = datetime.strptime(CYCLE_ANCHOR_DATE_STR, "%Y-%m-%d").replace(tzinfo=timezone.utc)
     except ValueError: msg = f"КРИТИЧНО: Неверный формат якоря '{CYCLE_ANCHOR_DATE_STR}'!"; msg_lines.append(msg); needs_update = True; logging.error(msg)
     else:
         if anchor_dt >= now: msg = f"ВНИМАНИЕ: Якорь ({CYCLE_ANCHOR_DATE_STR}) должен быть в прошлом!"; msg_lines.append(msg); needs_update = True; logging.error(msg)
         elif (now - anchor_dt).days > CYCLE_LENGTH * 2: logging.warning(f"ИНФО: Якорь ({CYCLE_ANCHOR_DATE_STR}) старый, можно обновить.")

     active = get_active_promo_events(events, now); future = []; latest_end = datetime.min.replace(tzinfo=timezone.utc)
     has_future_active = bool(active); old = []
     for e in events:
         try:
             start = datetime.strptime(e["start_date"],"%Y-%m-%d").replace(tzinfo=timezone.utc)
             end_calc = datetime.max.replace(tzinfo=timezone.utc)
             if "end_date" in e and e["end_date"]: end_calc = datetime.strptime(e["end_date"],"%Y-%m-%d").replace(tzinfo=timezone.utc)
             elif "duration_days" in e and isinstance(e["duration_days"],int): end_calc = start + timedelta(days=e["duration_days"]-1)
             if start > now: future.append(e.get("name","???")); has_future_active = True
             if end_calc != datetime.max.replace(tzinfo=timezone.utc):
                 if end_calc > latest_end: latest_end = end_calc
                 if end_calc < now - timedelta(days=90): old.append(e.get("name","???"))
         except: continue

     if not has_future_active: msg = f"ВНИМАНИЕ: В {EVENTS_FILE} нет активных/будущих промо. Добавить?"; msg_lines.append(msg); needs_update = True; logging.warning(msg)
     elif latest_end != datetime.min.replace(tzinfo=timezone.utc) and latest_end.date() < (now + timedelta(days=7)).date() and latest_end >= now.date():
         msg = f"НАПОМИНАНИЕ: Последнее промо в {EVENTS_FILE} заканчивается {latest_end:%Y-%m-%d}."; msg_lines.append(msg); needs_update = True; logging.warning(msg)
     else: logging.info(f"[Events] Файл {EVENTS_FILE} актуален.")
     if old: logging.info(f"[Events] Можно удалить старые события: {', '.join(old)}")

     if needs_update and msg_lines:
        try: import notifications; notifications.send_telegram_message(f"🔔 Напоминания по событиям:\n" + "\n".join(msg_lines))
        except Exception as e_tg: logging.error(f"[Events] Ошибка TG: {e_tg}")
     return needs_update

# --- Создание файла при первом запуске ---
if not os.path.isfile(EVENTS_FILE_PATH):
    logging.info(f"[Events] Файл {EVENTS_FILE} не найден, создается пример.")
    example = [{"name": "Pitch Beats", "start_date": "2025-04-03", "duration_days": 28, "type": "promo_event"},
               {"name": "Старое событие", "start_date": "2025-03-01", "end_date": "2025-03-10"}]
    try:
        with open(EVENTS_FILE_PATH, "w", encoding='utf-8') as f: json.dump(example, f, indent=2, ensure_ascii=False)
        logging.info(f"[Events] Создан пример {EVENTS_FILE_PATH}. Отредактируйте!")
    except Exception as e: logging.error(f"[Events] Не создать {EVENTS_FILE_PATH}: {e}")