# =============================================
# ФАЙЛ: verify_ohlc.py (ВЕРСИЯ v1.0)
# - Проверяет структуру и типы данных в файле OHLC.
# - Использует настройки из config.py.
# =============================================

import pandas as pd
import os
import sys
import logging

# Настройка базового логгера для скрипта
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("OHLC_Verifier")

def verify_ohlc_file():
    """Проверяет OHLC файл на соответствие ожиданиям."""
    try:
        import config
        ohlc_file_path = getattr(config, 'OHLC_SUMMARY_FILE', None)
        expected_headers = getattr(config, 'EXPECTED_HEADER_OHLC', [])
        numeric_cols = getattr(config, 'OHLC_NUMERIC_COLS', [])
        data_dir = getattr(config, 'DATA_DIR', 'data') # Для случая, если OHLC_SUMMARY_FILE не задан
        if ohlc_file_path is None:
            # Пытаемся сформировать путь по умолчанию
             ohlc_dir = os.path.join(data_dir, 'ohlc')
             ohlc_file_path = os.path.join(ohlc_dir, 'daily_summary_corrected.csv')
             logger.warning(f"Путь OHLC_SUMMARY_FILE не найден в config, используется путь по умолчанию: {ohlc_file_path}")
        if not expected_headers:
            logger.error("Список ожидаемых заголовков OHLC (EXPECTED_HEADER_OHLC) не найден или пуст в config.py.")
            return False
        if not numeric_cols:
            logger.warning("Список ожидаемых числовых колонок OHLC (OHLC_NUMERIC_COLS) не найден или пуст в config.py. Проверка типов будет неполной.")

    except ImportError:
        logger.error("Не удалось импортировать config.py. Проверка невозможна.")
        return False
    except Exception as e_cfg:
        logger.error(f"Ошибка при чтении настроек из config.py: {e_cfg}")
        return False

    if not os.path.exists(ohlc_file_path):
        logger.error(f"Файл OHLC не найден: {ohlc_file_path}")
        return False

    logger.info(f"Проверка файла OHLC: {ohlc_file_path}")
    issues_found = False

    try:
        # Читаем CSV, не парсим даты здесь, только проверяем структуру
        df = pd.read_csv(ohlc_file_path, encoding='utf-8')

        # 1. Проверка заголовков
        logger.info("Проверка заголовков...")
        actual_headers = df.columns.tolist()
        if actual_headers != expected_headers:
            logger.error("Заголовки не совпадают!")
            logger.error(f"  Ожидалось: {expected_headers}")
            logger.error(f"  Найдено:   {actual_headers}")
            # Показываем различия
            missing = [h for h in expected_headers if h not in actual_headers]
            extra = [h for h in actual_headers if h not in expected_headers]
            if missing: logger.warning(f"  Отсутствуют колонки: {missing}")
            if extra: logger.warning(f"  Лишние колонки: {extra}")
            issues_found = True
        else:
            logger.info("  Заголовки совпадают.")

        # 2. Проверка наличия данных
        if df.empty:
            logger.warning("Файл OHLC пуст.")
            # Не считаем это критической ошибкой, если заголовки верны
            return not issues_found # Возвращаем True если не было проблем с заголовками

        # 3. Проверка типов данных для числовых колонок
        logger.info("Проверка типов данных...")
        for col in numeric_cols:
            if col in df.columns:
                # Проверяем, что колонка может быть преобразована в числовой тип
                # Используем errors='coerce', чтобы нечисловые значения стали NaN
                numeric_series = pd.to_numeric(df[col], errors='coerce')
                num_nan = numeric_series.isna().sum()
                if num_nan == len(df): # Если ВСЕ значения стали NaN
                     logger.error(f"  Колонка '{col}': Все значения не являются числовыми!")
                     issues_found = True
                elif num_nan > 0:
                     # Если есть NaN, но не все - это предупреждение
                     logger.warning(f"  Колонка '{col}': Обнаружено {num_nan} нечисловых значений (NaN).")
                else:
                    # Если все значения числовые
                    logger.info(f"  Колонка '{col}': OK (числовой тип).")
            else:
                logger.warning(f"  Числовая колонка '{col}' отсутствует в файле для проверки типа.")
                # Не считаем ошибкой, если колонки нет (уже должно было выявиться при проверке заголовков)

        # 4. Проверка на полные NaN строки (опционально)
        # if df.isnull().all(axis=1).any():
        #     logger.warning("Найдены строки, состоящие полностью из пустых значений (NaN).")

    except pd.errors.EmptyDataError:
        logger.warning(f"Файл OHLC пуст: {ohlc_file_path}")
        return not issues_found # Если заголовки были верны, то пустой файл - не ошибка
    except Exception as e:
        logger.error(f"Ошибка при чтении или проверке файла OHLC: {e}", exc_info=True)
        issues_found = True

    if not issues_found:
        logger.info("Проверка OHLC файла успешно завершена. Проблем не найдено.")
        return True
    else:
        logger.error("Проверка OHLC файла выявила проблемы.")
        return False

if __name__ == "__main__":
    if verify_ohlc_file():
        logger.info("Статус OHLC: OK")
        sys.exit(0) # Успешный выход
    else:
        logger.error("Статус OHLC: ЕСТЬ ПРОБЛЕМЫ")
        sys.exit(1) # Выход с ошибкой