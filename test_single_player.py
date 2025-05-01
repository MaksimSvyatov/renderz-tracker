# =============================================
# ФАЙЛ: test_single_player.py (v1.1 - Исправлен SyntaxError)
# ОПИСАНИЕ: Скрипт для тестирования парсинга ОДНОГО игрока
#           с использованием функций из scraper.py v7.1.9+.
# ИСПОЛЬЗОВАНИЕ: python3 test_single_player.py "Имя Игрока OVR"
# =============================================

import logging
import time
import os
import sys
import traceback
import re
import argparse # Для аргументов командной строки
from datetime import datetime, timezone

# --- Импорт Selenium и пользовательских модулей ---
try:
    from selenium import webdriver
    from selenium.webdriver.firefox.service import Service as FirefoxService
    from selenium.webdriver.firefox.options import Options as FirefoxOptions
    from selenium.common.exceptions import (WebDriverException, TimeoutException,
                                            NoSuchElementException, StaleElementReferenceException)
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
except ImportError as e:
    print(f"КРИТИЧЕСКАЯ ОШИБКА: Не найдены компоненты Selenium: {e}")
    sys.exit(1)

try:
    import config
    import storage # Нужен для format_price
    import notifications # Нужен для format_error_message
except ImportError as e:
    print(f"КРИТИЧЕСКАЯ ОШИБКА: Не найден модуль config, storage или notifications: {e}")
    sys.exit(1)

# --- Настройка Логирования (упрощенная, только в консоль) ---
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logging.getLogger("urllib3").setLevel(logging.WARNING)
logging.getLogger("selenium").setLevel(logging.INFO)

# --- Копируем необходимые функции из scraper.py v7.1.9+ ---
LOG_DIR = getattr(config, 'LOG_DIR', 'logs')
os.makedirs(LOG_DIR, exist_ok=True)
GECKODRIVER_PATH = os.environ.get('GECKODRIVER_PATH', None)

def create_webdriver():
    """Создает и настраивает экземпляр WebDriver Firefox."""
    logging.debug("Попытка создания экземпляра WebDriver...")
    service = None
    try:
        service_args = []
        if GECKODRIVER_PATH and os.path.exists(GECKODRIVER_PATH):
            logging.info(f"Используется geckodriver из GECKODRIVER_PATH: {GECKODRIVER_PATH}")
            service = FirefoxService(executable_path=GECKODRIVER_PATH, service_args=service_args)
        else:
            logging.info("Используется geckodriver из системного PATH.")
            service = FirefoxService(service_args=service_args)
    except Exception as e_service:
         logging.critical(f"КРИТИЧЕСКАЯ ОШИБКА при инициализации FirefoxService: {e_service}", exc_info=True)
         return None
    options = FirefoxOptions(); options.add_argument("--headless"); options.add_argument("--disable-gpu"); options.add_argument("--window-size=1920,1080")
    options.set_preference("permissions.default.image", 2); options.set_preference("dom.ipc.plugins.enabled.libflashplayer.so", "false"); options.set_preference("javascript.enabled", True)
    options.set_preference("network.cookie.cookieBehavior", 0); options.set_preference("network.http.connection-timeout", 60); options.set_preference("network.http.response.timeout", 120); options.set_preference("dom.max_script_run_time", 60)
    logging.info("Попытка запуска Firefox WebDriver...")
    driver = None
    try:
        if service is None: logging.error("Не удалось инициализировать FirefoxService."); return None
        driver = webdriver.Firefox(service=service, options=options) # Убран service_log_path
        driver.implicitly_wait(15); driver.set_page_load_timeout(60)
        logging.info("WebDriver успешно создан."); return driver
    except WebDriverException as e:
        error_message = f"КРИТ. ОШИБКА WebDriverException при создании WebDriver: {e}\n"
        if "Unable to obtain driver" in str(e): error_message += "Сообщение: 'Unable to obtain driver'.\n"
        elif "cannot find firefox binary" in str(e).lower(): error_message += "Сообщение: 'cannot find firefox binary'.\n"
        elif "Timed out connecting to Marionette" in str(e): error_message += "Сообщение: 'Timed out connecting to Marionette'.\n"
        elif "'str' object has no attribute 'fileno'" in str(e): error_message += "Сообщение: 'str' object has no attribute 'fileno'.\n"
        else: error_message += f"Полный текст ошибки: {traceback.format_exc()}\n"
        logging.critical(error_message, exc_info=False); return None
    except Exception as e: logging.critical(f"КРИТ. НЕПРЕДВИДЕННАЯ ОШИБКА при создании WebDriver: {e}", exc_info=True); return None

def parse_player_data(driver, player_name, player_url):
    """
    Парсит данные игрока с использованием Selenium.
    ИСПОЛЬЗУЕТ ЛОГИКУ ПОИСКА ЭЛЕМЕНТОВ ИЗ scraper.py v7.1.9+.
    """
    logging.info(f"Парсим {player_name} (URL: {player_url}) с XPath селекторами из v7")
    price_xpath_selector = "//div[contains(@class, 'market-data--key') and normalize-space(.)='Current value']/ancestor::div[contains(@class, 'flex-col')][2]//div[contains(@class, 'market-data--value')][1]/span[1]"
    change_xpath_selector = "//div[contains(@class, 'market-data--value--change')]//span[contains(text(), '%')]"
    next_update_xpath_selector = "//div[contains(text(), 'Market Refresh')]/following-sibling::div[contains(@class, 'market-data--value-mini')]"
    min_price_xpath_selector = "//div[contains(text(), 'Market low/high')]/following-sibling::div[contains(@class, 'market-data--value-mini')]//span[1]"
    max_price_xpath_selector = "//div[contains(text(), 'Market low/high')]/following-sibling::div[contains(@class, 'market-data--value-mini')]//span[last()]"
    data = {'timestamp': None, 'price': None, 'change': 'N/A', 'min_order': None, 'max_order': None, 'update_time': 'N/A', 'error': None}
    html_dump_path = os.path.join(LOG_DIR, f"error_{player_name.replace(' ','_')}_{datetime.now().strftime('%H%M%S')}.html")
    try:
        driver.get(player_url); time.sleep(1.5)
        try: driver.execute_script("window.stop();"); logging.debug(f"stop() OK {player_name}"); time.sleep(0.5)
        except WebDriverException as e_stop: logging.warning(f"stop() FAILED {player_name}: {e_stop}")
        wait_long = WebDriverWait(driver, 15); wait_short = WebDriverWait(driver, 5)
        price = None; raw_price_text = "N/A"
        try:
            price_element = wait_long.until(EC.visibility_of_element_located((By.XPATH, price_xpath_selector))); raw_price_text = price_element.text.strip(); logging.debug(f"Raw price: '{raw_price_text}'")
            cleaned = raw_price_text.replace(',','').replace(' ','').replace('\u00A0','').replace('-',''); price = int(cleaned) if cleaned.isdigit() else 0
            if price == 0 and raw_price_text != '0': logging.warning(f"{player_name} price 0, text: '{raw_price_text}'.")
            data['price'] = price; data['low'] = price
        except TimeoutException: data['error'] = "Таймаут ожидания цены"; logging.error(f"{data['error']} для {player_name}"); return data
        except NoSuchElementException: data['error'] = "Элемент цены не найден"; logging.error(f"{data['error']} для {player_name} (XPath: {price_xpath_selector})"); return data
        except Exception as e: data['error'] = f"Ошибка парсинга цены: {type(e).__name__}"; logging.error(f"{data['error']} для {player_name}: {e}", exc_info=True); return data
        try: data['change'] = wait_short.until(EC.visibility_of_element_located((By.XPATH, change_xpath_selector))).text.strip()
        except (TimeoutException, NoSuchElementException): data['change'] = "0%"; logging.debug(f"Изменение цены не найдено для {player_name}")
        except Exception as e: data['change'] = "N/A"; logging.warning(f"Ошибка парсинга изменения цены: {e}")
        try: data['update_time'] = wait_short.until(EC.visibility_of_element_located((By.XPATH, next_update_xpath_selector))).text.strip()
        except (TimeoutException, NoSuchElementException): data['update_time'] = "N/A"; logging.warning(f"Время обновления не найдено для {player_name}")
        except Exception as e: data['update_time'] = "N/A"; logging.warning(f"Ошибка парсинга времени обновления: {e}")
        min_val, max_val = None, None
        try: min_raw = wait_short.until(EC.visibility_of_element_located((By.XPATH, min_price_xpath_selector))).text.strip(); min_clean = min_raw.replace(',','').replace(' ','').replace('\u00A0','').replace('-',''); min_val = int(min_clean) if min_clean.isdigit() else 0; data['min_order'] = min_val
        except (TimeoutException, NoSuchElementException): logging.debug(f"Min цена не найдена для {player_name}")
        except Exception as e: logging.warning(f"Ошибка парсинга Min цены: {e}")
        try: max_raw = wait_short.until(EC.visibility_of_element_located((By.XPATH, max_price_xpath_selector))).text.strip(); max_clean = max_raw.replace(',','').replace(' ','').replace('\u00A0','').replace('-',''); max_val = int(max_clean) if max_clean.isdigit() else 0; data['max_order'] = max_val
        except (TimeoutException, NoSuchElementException): logging.debug(f"Max цена не найдена для {player_name}")
        except Exception as e: logging.warning(f"Ошибка парсинга Max цены: {e}")
        min_f = storage.format_price(min_val) if hasattr(storage, 'format_price') and min_val is not None else "N/A"
        max_f = storage.format_price(max_val) if hasattr(storage, 'format_price') and max_val is not None else "N/A"
        data['orders'] = f"Min: {min_f} / Max: {max_f}"
        data['timestamp'] = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.%f+00:00')
        data['error'] = None
        price_f = storage.format_price(data['price']) if hasattr(storage, 'format_price') else data['price']
        logging.info(f"Успешно {player_name}: Цена={price_f}  Изм='{data['change']}'  Ордера='{data['orders']}'  Обн='{data['update_time']}'")
        return data
    except TimeoutException: data['error'] = "Page load timeout"; logging.error(f"{data['error']} {player_url}"); return data
    except WebDriverException as e:
        error_type = type(e).__name__; error_msg = f"WebDriverException ({error_type}) {player_name}: {e}\n"
        # ... (обработка ошибок WebDriver) ...
        logging.error(error_msg, exc_info=False); data['error'] = f"WebDriver err: {error_type}"; return data
    except Exception as e:
        data['error'] = f"Unexpected err: {type(e).__name__}"
        logging.error(f"Unexpected err {player_name}: {e}", exc_info=True)
        # --- ИСПРАВЛЕННЫЙ БЛОК ---
        try:
            with open(html_dump_path, "w", encoding="utf-8") as f:
                f.write(driver.page_source)
            logging.info(f"HTML при неожиданной ошибке сохранен: {html_dump_path}")
        except Exception as dump_err:
            logging.error(f"Не удалось сохранить HTML при ошибке: {dump_err}")
        # --------------------------
        return data

def close_webdriver(driver):
    """Закрывает WebDriver."""
    if driver:
        try: logging.info("Закрытие WebDriver..."); driver.quit(); logging.info("WebDriver закрыт.")
        except WebDriverException as e: logging.warning(f"Ошибка закрытия WebDriver: {e}")
        except Exception as e: logging.error(f"Неожиданная ошибка закрытия WebDriver: {e}")

# --- Основная логика теста ---
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Тестирование парсинга одного игрока RenderZ.")
    parser.add_argument("player_name", help="Полное имя игрока с OVR (как ключ в JSON конфиге)")
    args = parser.parse_args()

    target_player_name = args.player_name
    logging.info(f"--- Тестирование парсинга для: {target_player_name} ---")

    # Загрузка конфига
    if not hasattr(config, 'load_players'): logging.critical("Нет config.load_players! Выход."); sys.exit(1)
    players_config = config.load_players()
    if not players_config: logging.critical("Не удалось загрузить config."); sys.exit(1)
    player_info = players_config.get(target_player_name)
    if not player_info or not isinstance(player_info, dict) or 'url' not in player_info: logging.critical(f"Игрок '{target_player_name}' не найден/некорректен."); sys.exit(1)
    player_url = player_info['url']
    logging.info(f"Найден URL: {player_url}")

    # Создание WebDriver
    test_driver = create_webdriver()

    if test_driver:
        test_result = None
        try:
            test_result = parse_player_data(test_driver, target_player_name, player_url)
            logging.info("--- Результат Парсинга ---")
            if test_result:
                if test_result.get('error'):
                    logging.error(f"ОШИБКА: {test_result['error']}")
                    logging.error(f"Полученные данные (с ошибкой): {test_result}")
                elif test_result.get('price') is not None:
                    logging.info("УСПЕХ!")
                    price_f = storage.format_price(test_result.get('price'))
                    change_f = test_result.get('change', 'N/A')
                    orders_f = test_result.get('orders', 'N/A')
                    update_f = test_result.get('update_time', 'N/A')
                    print(f"  Имя: {target_player_name}")
                    print(f"  Цена: {price_f}")
                    print(f"  Изменение: {change_f}")
                    print(f"  Мин/Макс (Ордера): {orders_f}")
                    print(f"  Обновление: {update_f}")
                else:
                    logging.warning("Парсинг завершился без ошибки, но цена не найдена.")
                    logging.warning(f"Полный результат: {test_result}")
            else: logging.error("Функция parse_player_data вернула None.")
        finally: close_webdriver(test_driver) # Гарантированное закрытие
    else: logging.critical("Не удалось создать WebDriver для теста.")

    logging.info("--- Тестирование завершено ---")