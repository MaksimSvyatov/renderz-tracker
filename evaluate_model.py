# =============================================
# ФАЙЛ: evaluate_model.py (v6.1 - Улучшенное Логирование Оценки)
# - Добавлено детальное логирование в get_actual_outcome для диагностики
# - Сигнатура get_actual_outcome изменена для передачи player_name
# - Вызов get_actual_outcome обновлен в evaluate_predictions
# - Адаптирован для оценки 3-классовой модели (Падение, Без изм., Рост -> 0, 1, 2)
# =============================================

import os
import json
import logging
from datetime import datetime, timedelta, timezone
import pandas as pd
import numpy as np
from sklearn.metrics import classification_report, confusion_matrix, accuracy_score
import config

# --- Настройки Оценки ---
EVALUATION_HORIZON_HOURS = 24
PRICE_CHANGE_THRESHOLD_PCT = 1.5  # Порог для определения классов
EVALUATION_LOG_DAYS = 0  # 0 = все дни, >0 = последние N дней

PREDICTION_LOG_FILE = getattr(config, 'PREDICTION_LOG_FILE', 'predictions.log')
DATA_DIR = getattr(config, 'DATA_DIR', 'data')
timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
SUMMARY_FILE = f"evaluation_summary_3class_{timestamp_str}.txt" # Имя файла для 3 классов

# --- Настройка Логгера ---
# Уровень INFO для основных шагов, WARNING для причин пропуска оценки
log_format = "%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s"
logging.basicConfig(level=logging.INFO, format=log_format)
# Можно временно установить logging.basicConfig(level=logging.DEBUG, ...) для еще более детальных логов, если потребуется

# --- Парсинг 3-классовых предсказаний (из v6.0) ---
def parse_prediction_string(pred_str: str) -> int | None:
    """Парсит строку предсказания и возвращает класс (0, 1, 2)."""
    if not isinstance(pred_str, str):
        return None
    pred_str_lower = pred_str.lower() # Для регистронезависимости
    if "падение" in pred_str_lower:
        return 0 # Класс 0: Падение
    elif "без изм" in pred_str_lower:
        return 1 # Класс 1: Без изменений
    elif "рост" in pred_str_lower:
        return 2 # Класс 2: Рост
    # Обработка старых форматов или неизвестных строк
    elif "не рост" in pred_str_lower: # Пример обработки старого формата как "Без изм."
         # Используем DEBUG, чтобы не засорять лог при нормальной работе
         logging.debug(f"Обнаружено старое предсказание '{pred_str}', интерпретировано как 'Без изм.' (1)")
         return 1
    elif "n/a" in pred_str_lower:
        logging.debug(f"Обнаружено предсказание N/A: '{pred_str}'")
        return None # N/A не являются классом для оценки
    else:
        # Используем WARNING для строк, которые не должны были появиться
        logging.warning(f"Не удалось распознать строку предсказания: '{pred_str}'")
        return None
# --------------------------------------------------

# --- ИЗМЕНЕНО: Определение фактического 3-классового исхода с ЛОГИРОВАНИЕМ ---
def get_actual_outcome(
    player_history_df: pd.DataFrame,
    prediction_dt: datetime,
    horizon_hours: int,
    threshold_pct: float,
    player_name: str # Добавлен аргумент для логирования
) -> int | None:
    """
    Определяет фактический исход (-1, 0, 1) на основе изменения цены.
    Возвращает None, если исход определить не удалось, и логирует причину.
    """
    if player_history_df is None or player_history_df.empty:
        # Эта проверка обычно выполняется до вызова функции, но оставим на всякий случай
        logging.warning(f"[{player_name}] DataFrame истории пуст или None при вызове get_actual_outcome для {prediction_dt}")
        return None

    # Убедимся, что время в UTC
    if prediction_dt.tzinfo is None:
        prediction_dt = prediction_dt.replace(tzinfo=timezone.utc)
    else:
        prediction_dt = prediction_dt.astimezone(timezone.utc)

    future_dt = prediction_dt + timedelta(hours=horizon_hours)

    try:
        # Находим ближайшую запись НЕ ПОЗЖЕ времени предсказания
        start_idx_arr = player_history_df.index.get_indexer([prediction_dt], method='ffill')
        if start_idx_arr.size == 0 or start_idx_arr[0] == -1:
            # Используем WARNING, т.к. это частая причина пропуска
            logging.warning(f"[{player_name}] Не найдена стартовая точка в истории <= {prediction_dt}")
            return None
        start_idx = start_idx_arr[0]
        start_price_row = player_history_df.iloc[start_idx]
        start_price = start_price_row['Цена']
        start_dt = start_price_row.name # Фактическое время стартовой цены

        # Проверка NaN стартовой цены
        if start_price is None or pd.isna(start_price):
            logging.warning(f"[{player_name}] Стартовая цена NaN для {start_dt} (ищем для {prediction_dt})")
            return None

        # Находим ПЕРВУЮ запись НЕ РАНЕЕ целевого будущего времени
        end_idx_arr = player_history_df.index.get_indexer([future_dt], method='bfill')
        if end_idx_arr.size == 0 or end_idx_arr[0] == -1 :
            # Используем WARNING, т.к. это основная причина при нехватке данных
            logging.warning(f"[{player_name}] Не найдена конечная точка в истории >= {future_dt} (для предсказания от {prediction_dt})")
            return None
        end_idx = end_idx_arr[0]
        end_price_row = player_history_df.iloc[end_idx]
        end_price = end_price_row['Цена']
        end_dt = end_price_row.name # Фактическое время конечной цены

         # Проверка NaN конечной цены
        if end_price is None or pd.isna(end_price):
            logging.warning(f"[{player_name}] Конечная цена NaN для {end_dt} (ищем для {future_dt})")
            return None

        # Проверки валидности дат
        if end_dt <= start_dt:
            logging.warning(f"[{player_name}] Конечная дата ({end_dt}) не позже начальной ({start_dt}) для предсказания от {prediction_dt}")
            return None

        # Проверка фактического горизонта (чтобы не брать слишком далекие точки)
        actual_horizon_hours = (end_dt - start_dt).total_seconds() / 3600
        # Увеличим допуск до 2 раз, чтобы не терять слишком много данных
        if actual_horizon_hours > horizon_hours * 2.0:
            logging.warning(f"[{player_name}] Факт. горизонт {actual_horizon_hours:.1f}ч ({start_dt} -> {end_dt}) > {horizon_hours * 2.0:.1f}ч для предсказания от {prediction_dt}")
            return None

        # Расчет изменения и определение класса (-1, 0, 1)
        if abs(start_price) < 1e-9: # Избегаем деления на ноль
             if abs(end_price) < 1e-9: return 0 # Цена была и осталась ~0 -> Без изм.
             # Если стартовая цена 0, а конечная не 0, считаем это ростом или падением
             # Но это редкий случай, может быть просто 1 (Без изм.), если цена не изменилась
             # Давайте для простоты считать 0 -> X как изменение
             elif end_price > start_price + 1e-9: return 1 # Рост от нуля
             elif end_price < start_price - 1e-9: return -1 # Падение от нуля (хотя цена не может быть < 0)
             else: return 0 # Без изм. (оба около нуля)
        else:
            change_pct = ((end_price - start_price) / start_price) * 100
            if change_pct > threshold_pct:
                return 1  # Рост
            elif change_pct < -threshold_pct:
                return -1 # Падение
            else:
                return 0  # Без изменений

    except Exception as e:
        # Используем ERROR и exc_info=True для полных деталей исключения
        logging.error(f"[{player_name}] ИСКЛЮЧЕНИЕ в get_actual_outcome для {prediction_dt}: {e}", exc_info=True)
        return None
# ----------------------------------------------------------------------------

# --- Загрузка истории игрока (из v6.0, с мелкими улучшениями) ---
def load_player_history(player_name: str) -> pd.DataFrame | None:
    safe_player_name = "".join(c if c.isalnum() else "_" for c in player_name)
    filepath = os.path.join(DATA_DIR, safe_player_name + ".csv")

    if not os.path.exists(filepath):
        logging.warning(f"Файл истории не найден: {filepath}")
        return None
    try:
        df = pd.read_csv(filepath, usecols=['Дата', 'Время', 'Цена'], encoding='utf-8')
        if df.empty:
            logging.warning(f"Файл истории {filepath} пуст.")
            return None

        df['datetime_str'] = df['Дата'].astype(str) + ' ' + df['Время'].astype(str)
        # --- Парсинг дат ---
        # Сначала пробуем стандартный формат, потом с dayfirst=True
        df['datetime'] = pd.to_datetime(df['datetime_str'], errors='coerce')
        mask_nat = df['datetime'].isna()
        if mask_nat.any():
             df.loc[mask_nat, 'datetime'] = pd.to_datetime(df.loc[mask_nat, 'datetime_str'], errors='coerce', dayfirst=True)

        # Попробуем спарсить только дату, если с временем не вышло
        mask_nat = df['datetime'].isna()
        if mask_nat.any():
             dt_fallback = pd.to_datetime(df.loc[mask_nat, 'Дата'], errors='coerce', dayfirst=True) # Пробуем и dayfirst=True для даты
             if dt_fallback.isna().all(): # Если и только дата не парсится, пробуем без dayfirst
                  dt_fallback = pd.to_datetime(df.loc[mask_nat, 'Дата'], errors='coerce')
             df.loc[mask_nat, 'datetime'] = dt_fallback

        df.dropna(subset=['datetime'], inplace=True) # Удаляем строки, где дату не спарсить никак
        if df.empty: logging.warning(f"Нет валидных дат после парсинга в {filepath}."); return None

        # --- Обработка цены ---
        df['Цена'] = pd.to_numeric(df['Цена'], errors='coerce')
        df.dropna(subset=['Цена'], inplace=True)
        if df.empty: logging.warning(f"Нет валидных цен после конвертации в {filepath}."); return None

        # --- Установка индекса и UTC ---
        df.set_index('datetime', inplace=True)
        if df.index.tz is None:
            try:
                # Пытаемся локализовать как локальное время, затем конвертировать в UTC
                # Важно: Укажите вашу локальную таймзону правильно! Если не Москва, замените.
                df = df.tz_localize('Europe/Moscow', ambiguous='infer', nonexistent='shift_forward').tz_convert('UTC')
                logging.debug(f"Локализация {filepath} как Europe/Moscow и конвертация в UTC успешна.")
            except Exception as tz_err:
                 logging.warning(f"Не удалось локализовать {filepath} как Europe/Moscow ({tz_err}). Пробуем UTC напрямую.")
                 try:
                      df = df.tz_localize('UTC', ambiguous='infer', nonexistent='shift_forward')
                 except Exception as tz_err_utc:
                      logging.error(f"Критическая ошибка localize UTC для {filepath}: {tz_err_utc}. Пропуск файла.")
                      return None
        else:
             df = df.tz_convert('UTC') # Если уже есть таймзона, просто конвертируем в UTC

        df.sort_index(inplace=True)
        # Удаляем дубликаты по индексу (дате-времени), оставляя последнее значение
        df = df[~df.index.duplicated(keep='last')]

        if df.empty: logging.warning(f"Пустой DataFrame после очистки и удаления дубликатов для {filepath}."); return None

        return df[['Цена']] # Возвращаем только нужный столбец

    except FileNotFoundError:
        logging.warning(f"Файл истории не найден при попытке чтения: {filepath}")
        return None
    except Exception as e:
        logging.error(f"Критическая ошибка при загрузке/обработке истории {player_name} из {filepath}: {e}", exc_info=True)
        return None


# --- Оценка 3-классовой модели (с обновленным вызовом get_actual_outcome) ---
def evaluate_predictions():
    logging.info("=== Начало Оценки Предсказаний Модели (3-КЛАССОВАЯ ВЕРСИЯ v6.1) ===")
    logging.info(f"Параметры: Горизонт={EVALUATION_HORIZON_HOURS} ч, Порог Изменения={PRICE_CHANGE_THRESHOLD_PCT}%, Дней лога={EVALUATION_LOG_DAYS if EVALUATION_LOG_DAYS > 0 else 'Все'}")

    if not os.path.exists(PREDICTION_LOG_FILE):
        logging.error(f"Файл лога предсказаний не найден: {PREDICTION_LOG_FILE}")
        return

    try:
        preds_df = pd.read_csv(PREDICTION_LOG_FILE, encoding='utf-8')
        logging.info(f"Загружено {len(preds_df)} строк из лога предсказаний.")
        preds_df['prediction_dt'] = pd.to_datetime(preds_df['prediction_for_datetime'], utc=True, errors='coerce')
        # Удаляем строки, где не удалось спарсить дату предсказания
        preds_df.dropna(subset=['prediction_dt'], inplace=True)
        original_log_count = len(preds_df)

        # Фильтрация по дате
        if EVALUATION_LOG_DAYS > 0:
            cutoff_date = datetime.now(timezone.utc) - timedelta(days=EVALUATION_LOG_DAYS)
            preds_df = preds_df[preds_df['prediction_dt'] >= cutoff_date]
            logging.info(f"Оставлено {len(preds_df)} предсказаний за последние {EVALUATION_LOG_DAYS} дней (из {original_log_count}).")

        # --- Парсинг предсказанного класса (0, 1, 2) ---
        preds_df['predicted_class'] = preds_df['prediction'].apply(parse_prediction_string)
        # Отбираем только те строки, где предсказание было успешно распознано (не None)
        valid_preds_df = preds_df.dropna(subset=['predicted_class']).copy()
        valid_preds_df['predicted_class'] = valid_preds_df['predicted_class'].astype(int)
        logging.info(f"Найдено {len(valid_preds_df)} валидных предсказаний (0,1,2) для оценки (из {len(preds_df)} строк после фильтра даты).")

        if valid_preds_df.empty:
            logging.warning("Нет валидных предсказаний для оценки после парсинга.")
            return

    except Exception as e:
        logging.error(f"Ошибка чтения или предобработки лога предсказаний: {e}", exc_info=True)
        return

    # Загрузка истории игроков
    players_in_valid_preds = valid_preds_df['player'].unique()
    player_histories = {}
    logging.info(f"Загрузка истории для {len(players_in_valid_preds)} игроков, имеющих валидные предсказания...")
    loaded_count = 0
    skipped_count = 0
    for player in players_in_valid_preds:
        history_df = load_player_history(player)
        if history_df is not None and not history_df.empty:
            player_histories[player] = history_df
            loaded_count += 1
        else:
            skipped_count +=1
            logging.warning(f"Не удалось загрузить или пустая история для игрока: {player}. Предсказания для него будут пропущены.")

    logging.info(f"Успешно загружена история для {loaded_count} игроков. Пропущено из-за проблем с историей: {skipped_count}.")
    if not player_histories:
        logging.error("Не удалось загрузить историю ни для одного игрока с валидными предсказаниями. Оценка невозможна.")
        return

    # Сопоставление предсказаний с фактическими исходами
    actual_outcomes = []
    processed_count = 0
    evaluated_count = 0
    skipped_no_history_count = 0
    logging.info("Сопоставление предсказаний с фактическими исходами...")

    # Группируем ВАЛИДНЫЕ предсказания по игрокам
    for player_name, group in valid_preds_df.groupby('player'):
        if player_name not in player_histories:
            # Этого не должно происходить из-за логики выше, но проверим
            skipped_no_history_count += len(group)
            continue

        player_history_df = player_histories[player_name]
        group = group.sort_values(by='prediction_dt') # Сортируем для удобства отладки

        for _, row in group.iterrows():
            processed_count += 1
            # --- Обновленный вызов get_actual_outcome с передачей player_name ---
            actual_outcome_raw = get_actual_outcome(
                player_history_df,
                row['prediction_dt'],
                EVALUATION_HORIZON_HOURS,
                PRICE_CHANGE_THRESHOLD_PCT,
                player_name # Передаем имя игрока
            )
            # --------------------------------------------------------------------

            if actual_outcome_raw is not None:
                # --- МАППИНГ ФАКТИЧЕСКОГО ИСХОДА в 0, 1, 2 ---
                actual_class_mapped = actual_outcome_raw + 1
                # ---------------------------------------------
                actual_outcomes.append({
                    'predicted_class': row['predicted_class'], # Уже 0, 1, 2
                    'actual_class': actual_class_mapped      # Теперь тоже 0, 1, 2
                })
                evaluated_count += 1
            # else:
                # Причина пропуска теперь логируется внутри get_actual_outcome

        if processed_count % 5000 == 0 and processed_count > 0: # Логгируем реже
             logging.info(f"Обработано {processed_count}/{len(valid_preds_df)} валидных предсказаний...")

    if skipped_no_history_count > 0:
         logging.warning(f"Было пропущено {skipped_no_history_count} предсказаний из-за отсутствия истории (ошибка в логике?).")

    logging.info(f"Обработка завершена. Всего валидных предсказаний: {len(valid_preds_df)}. Удалось сопоставить с факт. исходом: {evaluated_count}.")

    if not actual_outcomes:
        logging.warning("Не найдено ни одного сопоставленного предсказания для расчета метрик.")
        # Выводим пустой отчет или просто завершаем
        summary_lines = ["="*60, "Отчет Оценки Предсказаний Модели (3-КЛАССОВАЯ v6.1)", "="*60]
        summary_lines.append("Не удалось сопоставить ни одного предсказания с фактическим исходом.")
        summary_lines.append("Проверьте логи WARNING/ERROR на причины пропусков.")
        summary_text = "\n".join(summary_lines)
        print("\n" + summary_text + "\n")
        # Попытка сохранить пустой отчет
        try:
            with open(SUMMARY_FILE, "w", encoding="utf-8") as f: f.write(summary_text)
            logging.info(f"Пустой отчет сохранен в файл: {SUMMARY_FILE}")
        except Exception as e: logging.error(f"Не удалось сохранить пустой отчет: {e}")
        return

    # Расчет метрик
    results_df = pd.DataFrame(actual_outcomes)
    y_pred = results_df['predicted_class']
    y_true = results_df['actual_class']

    # --- Классы и метки для 3 классов ---
    final_labels = [0, 1, 2] # Падение, Без изм., Рост
    target_names_map = {0: 'Падение', 1: 'Без изм.', 2: 'Рост'}
    target_names = [target_names_map[l] for l in final_labels]
    # ------------------------------------

    logging.info("Расчет метрик...")
    try:
        accuracy = accuracy_score(y_true, y_pred)
        conf_matrix = confusion_matrix(y_true, y_pred, labels=final_labels)

        # Используем все возможные классы (0,1,2) для отчета
        class_report_str = classification_report(
            y_true,
            y_pred,
            labels=final_labels,
            target_names=target_names,
            zero_division=0,
            output_dict=False
        )
        class_report_dict = classification_report(
            y_true,
            y_pred,
            labels=final_labels,
            target_names=target_names,
            zero_division=0,
            output_dict=True # Для возможного будущего использования
        )

    except Exception as e:
        logging.error(f"Ошибка расчета метрик: {e}", exc_info=True)
        return

    # Формирование и вывод отчета
    summary_lines = []
    summary_lines.append("=" * 60)
    summary_lines.append(f"Отчет Оценки Предсказаний Модели (3-КЛАССОВАЯ v6.1)")
    summary_lines.append(f"Дата оценки: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S %Z')}")
    summary_lines.append("-" * 60)
    summary_lines.append(f"Параметры:")
    summary_lines.append(f"  - Файл лога: {PREDICTION_LOG_FILE}")
    summary_lines.append(f"  - Горизонт оценки: {EVALUATION_HORIZON_HOURS} ч")
    summary_lines.append(f"  - Порог изменения цены: +/- {PRICE_CHANGE_THRESHOLD_PCT}%")
    summary_lines.append(f"  - Глубина лога: {'Все дни' if EVALUATION_LOG_DAYS == 0 else f'{EVALUATION_LOG_DAYS} дней'}")
    summary_lines.append("-" * 60)
    summary_lines.append(f"Результаты:")
    summary_lines.append(f"  - Всего предсказаний в логе (до фильтра даты): {original_log_count}")
    summary_lines.append(f"  - Предсказаний после фильтра даты: {len(preds_df)}")
    summary_lines.append(f"  - Валидных предсказаний (распознан класс 0,1,2): {len(valid_preds_df)}")
    summary_lines.append(f"  - Предсказаний оценено (с факт. исходом): {evaluated_count}")
    summary_lines.append("-" * 60)
    summary_lines.append(f"Общая Точность (Accuracy): {accuracy:.4f}")
    summary_lines.append("-" * 60)
    summary_lines.append("Матрица Ошибок:")
    summary_lines.append("        <- Предсказано")

    # Форматирование матрицы для 3 классов
    max_name_len = max(len(name) for name in target_names) if target_names else 9 # Увеличим мин. ширину
    col_width = max(max_name_len, 9) # Ширина колонки
    header = f"{'Истина':<{max_name_len}} | " + " | ".join([f"{name:<{col_width}}" for name in target_names])
    summary_lines.append(header)
    summary_lines.append("-" * len(header))
    for i, label_true in enumerate(final_labels):
        row_name = target_names_map[label_true]
        row_str = f"{row_name:<{max_name_len}} | "
        # Проверяем, что i не выходит за пределы матрицы
        if i < conf_matrix.shape[0]:
             row_str += " | ".join([f"{conf_matrix[i, j]:<{col_width}d}" for j in range(len(final_labels)) if j < conf_matrix.shape[1]]) # d для целых чисел
        else:
             row_str += " | ".join([f"{'N/A':<{col_width}}" for _ in range(len(final_labels))])
        summary_lines.append(row_str)

    summary_lines.append("-" * 60)
    summary_lines.append("Отчет по Классам (Classification Report):")
    summary_lines.append(class_report_str)
    summary_lines.append("=" * 60)

    # Вывод в консоль
    summary_text = "\n".join(summary_lines)
    print("\n" + summary_text + "\n")

    # Сохранение в файл
    try:
        with open(SUMMARY_FILE, "w", encoding="utf-8") as f:
            f.write(summary_text)
        logging.info(f"Отчет сохранен в файл: {SUMMARY_FILE}")
    except Exception as e:
        logging.error(f"Не удалось сохранить отчет в файл {SUMMARY_FILE}: {e}")

    logging.info("=== Оценка Завершена ===")

# --- Точка входа ---
if __name__ == "__main__":
    evaluate_predictions()