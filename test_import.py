# Файл: test_import.py
import logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s')

try:
    logging.info("Попытка импорта 'signals'...")
    import signals
    logging.info("Модуль 'signals' импортирован успешно.")

    logging.info("Проверка наличия 'signals.check_signals'...")
    if hasattr(signals, 'check_signals'):
        logging.info("Функция signals.check_signals НАЙДЕНА.")
    else:
        logging.error("Функция signals.check_signals НЕ НАЙДЕНА!")

except ImportError as e_imp:
     logging.error(f"ОШИБКА ИМПОРТА модуля signals: {e_imp}", exc_info=True)
except SyntaxError as e_syn:
     logging.error(f"СИНТАКСИЧЕСКАЯ ОШИБКА в signals.py: {e_syn}", exc_info=True)
except Exception as e:
    logging.error(f"ДРУГАЯ ОШИБКА при импорте/проверке signals: {e}", exc_info=True)