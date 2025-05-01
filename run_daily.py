# =============================================
# ФАЙЛ: run_daily.py (ВЕРСИЯ v6.0 - Use Correct OHLC/Notify Calls)
# - ИСПРАВЛЕНО: Удалены вызовы несуществующих функций
#   ohlc_generator.get_previous_day_data_df и notifications.format_error_message.
# - ИЗМЕНЕНО: Теперь вызывает ohlc_generator.rewrite_ohlc_summary()
#   (или generate_daily_ohlc_report), которая сама обрабатывает всех игроков.
# - ИЗМЕНЕНО: Использует notifications.send_telegram_message для ошибок.
# =============================================

import logging
import sys
import os
from datetime import datetime, timedelta, timezone
import traceback

# --- Настройка Логирования ---
# Добавим базовую настройку логгера на случай, если config не загрузится
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("run_daily")

# --- Импорт пользовательских модулей ---
try:
    import config
    import ohlc_generator # Ожидается v3.3+
    import notifications   # Ожидается v10.12+

    # Перенастраиваем логгер с учетом настроек из config
    log_level_str = getattr(config, 'LOG_LEVEL', 'INFO').upper()
    log_level = getattr(logging, log_level_str, logging.INFO)
    # Устанавливаем уровень для нашего логгера
    logger.setLevel(log_level)
    # Добавляем обработчики, если они не были добавлены основным скриптом
    if not logger.hasHandlers() or len(logger.handlers) == 0 :
         # Консольный
         console_handler = logging.StreamHandler(sys.stdout)
         console_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
         logger.addHandler(console_handler)
         # Файловый (если LOG_DIR задан)
         LOG_DIR = getattr(config, 'LOG_DIR', None)
         if LOG_DIR:
              os.makedirs(LOG_DIR, exist_ok=True)
              log_filename = os.path.join(LOG_DIR, f"run_daily_{datetime.now().strftime('%Y-%m-%d')}.log")
              file_handler = logging.FileHandler(log_filename, encoding='utf-8')
              file_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - [%(name)s] - %(message)s'))
              logger.addHandler(file_handler)

    # Устанавливаем уровень для импортированных модулей
    logging.getLogger("ohlc_generator").setLevel(log_level)
    logging.getLogger("notifications").setLevel(log_level)
    logging.getLogger("config").setLevel(log_level) # Логгер для config, если он есть

except ImportError as e:
    logger.critical(f"КРИТИЧЕСКАЯ ОШИБКА: Не удалось импортировать модуль: {e}. Скрипт не может продолжить.")
    sys.exit(1)
except Exception as e_cfg:
     logger.critical(f"КРИТИЧЕСКАЯ ОШИБКА при инициализации конфига/логгера: {e_cfg}.")
     sys.exit(1)


def run_manual_daily_task():
    """Запускает ежедневную задачу генерации OHLC."""
    logger.info("--- Daily Tasks Start ---")
    success = False
    try:
        logger.info("Запуск генерации OHLC отчета...")
        # Определяем, какую функцию вызывать: rewrite_ohlc_summary приоритетнее
        ohlc_func = getattr(ohlc_generator, 'rewrite_ohlc_summary',
                            getattr(ohlc_generator, 'generate_daily_ohlc_report', None))

        if ohlc_func:
            # Вызываем найденную функцию
            # rewrite_ohlc_summary сама определит нужные дни и игроков
            # generate_daily_ohlc_report по умолчанию возьмет вчерашний день и загрузит игроков
            if ohlc_func.__name__ == 'rewrite_ohlc_summary':
                 days_to_rewrite = 1 # По умолчанию перезаписываем 1 день (вчерашний)
                 logger.info(f"Вызов rewrite_ohlc_summary(days={days_to_rewrite})...")
                 success = ohlc_func(days=days_to_rewrite)
            else: # generate_daily_ohlc_report
                 logger.info("Вызов generate_daily_ohlc_report (за вчера)...")
                 success = ohlc_func() # Вызываем без аргументов (по умолчанию вчера)

            if success:
                logger.info("Задача OHLC успешно завершена.")
            else:
                 logger.error("Функция генерации OHLC сообщила об ошибке.")
        else:
            logger.error("Не найдена функция для генерации OHLC в ohlc_generator.py "
                         "(rewrite_ohlc_summary или generate_daily_ohlc_report).")
            success = False

    except Exception as e:
        logger.error(f"Ошибка выполнения задачи OHLC: {e}", exc_info=True)
        # Используем актуальную функцию уведомлений
        if getattr(config, 'SEND_TELEGRAM_ERRORS', False):
            error_details = traceback.format_exc()
            notifications.send_telegram_message(
                f"Ошибка ручного запуска Daily Tasks (OHLC):\n```\n{error_details}\n```",
                is_error=True
            )
        success = False # Считаем ошибкой

    logger.info("--- Daily Tasks End ---")
    return success

if __name__ == "__main__":
    print("-" * 30)
    print("Запуск ежедневной задачи вручную...")
    print("-" * 30)
    if run_manual_daily_task():
        print("Генерация OHLC отчета успешно завершена.")
    else:
         print("Во время генерации OHLC отчета произошли ошибки. Смотрите лог.")
    print("-" * 30)
    print("Выполнение скрипта run_daily.py завершено.")
    print("-" * 30)