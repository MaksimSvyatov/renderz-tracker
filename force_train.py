# =============================================
# ФАЙЛ: force_train.py
# Назначение: Принудительно запускает обучение моделей
#             и логирует процесс в отдельный файл (training.log).
# ВАЖНО: Остановите основной скрипт scraper.py перед запуском этого!
# =============================================
import logging
import time
import os
import sys
import traceback

# --- Настройка логирования для этого скрипта ---
log_format = "%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s"
log_file = "training.log" # Отдельный лог-файл

logging.basicConfig(level=logging.INFO, format=log_format,
                    handlers=[logging.FileHandler(log_file, encoding='utf-8'),
                              logging.StreamHandler()])
# Понижаем уровень для импортируемых модулей, если нужно
logging.getLogger('matplotlib').setLevel(logging.WARNING)
# Можно добавить и другие, если они создают много шума

# --- Импорты модулей, необходимых для обучения ---
try:
    import config
    import model_trainer
    # model_trainer может импортировать cycle_analysis, signals, events_manager, pandas и т.д.
    # Убедимся, что все они доступны
    import cycle_analysis
    import signals
    import events_manager
    import pandas # Нужен для model_trainer
    import numpy # Нужен для model_trainer/signals
    import lightgbm # Нужен для model_trainer
    import joblib # Нужен для model_trainer/signals
except ImportError as import_err:
    logging.critical(f"КРИТИЧЕСКАЯ ОШИБКА: Не найден один из модулей: {import_err}")
    logging.critical("Убедитесь, что все .py файлы проекта находятся в той же папке.")
    sys.exit(1)

# --- Основная логика ---
if __name__ == "__main__":
    logging.info("="*30)
    logging.info("=== ПРИНУДИТЕЛЬНЫЙ ЗАПУСК ОБУЧЕНИЯ МОДЕЛЕЙ ===")
    logging.info("="*30)

    # Проверяем наличие папки для моделей
    model_dir = getattr(config, 'MODEL_DIR', 'models')
    if not os.path.exists(model_dir):
        logging.warning(f"Папка моделей '{model_dir}' не найдена. Создаем...")
        try:
            os.makedirs(model_dir)
        except Exception as e:
             logging.error(f"Не удалось создать папку моделей '{model_dir}': {e}. Обучение отменено.")
             sys.exit(1)

    start_time = time.time()
    try:
        # Напрямую вызываем функцию обучения из model_trainer
        if hasattr(model_trainer, 'train_and_save_all_models') and callable(model_trainer.train_and_save_all_models):
            model_trainer.train_and_save_all_models()
            end_time = time.time()
            logging.info(f"=== ОБУЧЕНИЕ МОДЕЛЕЙ УСПЕШНО ЗАВЕРШЕНО (за {end_time - start_time:.1f} сек) ===")
        else:
            logging.error("Функция model_trainer.train_and_save_all_models не найдена!")

    except Exception as e:
        end_time = time.time()
        logging.critical(f"!!! ОБУЧЕНИЕ МОДЕЛЕЙ ЗАВЕРШИЛОСЬ С ОШИБКОЙ (за {end_time - start_time:.1f} сек) !!!")
        logging.critical(f"Ошибка: {e}")
        logging.critical(traceback.format_exc())
        sys.exit(1) # Выход с ошибкой

    sys.exit(0) # Успешный выход