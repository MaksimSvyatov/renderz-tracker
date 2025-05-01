# =============================================
# ФАЙЛ: test_all_locators_single_player.py
# Назначение: Запустить видимый браузер для одного игрока, выполнить window.stop(),
#             и протестировать ВСЕ актуальные XPath локаторы
#             (новая цена, изменение, время, мин/макс).
# =============================================
import time
import logging
import os
import sys
import traceback
from selenium import webdriver
from selenium.webdriver.firefox.service import Service as FirefoxService
from selenium.webdriver.firefox.options import Options as FirefoxOptions
from selenium.common.exceptions import WebDriverException, TimeoutException, NoSuchElementException
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# --- Настройки ---
# Используем URL для тестов
PLAYER_URL = "https://renderz.app/24/player/24018004"

# Имя файла для сохранения HTML (на всякий случай)
OUTPUT_FILENAME = "page_source_after_stop_all_locators_test.html"

# Паузы
PAUSE_BEFORE_STOP = 1.0
PAUSE_AFTER_STOP = 0.5
# Время ожидания для WebDriverWait (секунды)
WAIT_PRICE = 10 # Даем больше времени цене
WAIT_OTHERS = 5 # Меньше времени для остальных
# -----------------

# --- Настройка логирования ---
log_format = "%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s"
logging.basicConfig(level=logging.INFO, format=log_format, handlers=[logging.StreamHandler()])
logging.getLogger('selenium').setLevel(logging.WARNING)
logging.getLogger('urllib3').setLevel(logging.WARNING)

# --- Функция настройки драйвера (видимый режим) ---
def setup_driver():
    """Настраивает и возвращает WebDriver в видимом режиме."""
    options = FirefoxOptions()
    # options.add_argument("--headless") # НЕ используем headless
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    # options.add_argument("--disable-images") # Можно закомментировать, чтобы видеть картинки
    # options.set_preference("permissions.default.image", 2) # Если картинки отключены
    options.set_preference("dom.ipc.plugins.enabled.libflashplayer.so", "false")
    options.set_preference("javascript.enabled", True)
    options.set_preference("general.useragent.override", "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:109.0) Gecko/20100101 Firefox/119.0")
    try:
        driver = webdriver.Firefox(options=options)
        driver.set_page_load_timeout(45)
        driver.set_script_timeout(30)
        logging.info("Настройки Selenium: используется Firefox (ВИДИМЫЙ РЕЖИМ).")
        return driver
    except WebDriverException as e:
        logging.error(f"Ошибка инициализации Firefox WebDriver: {e}")
        sys.exit(1)

# --- Основная логика ---
if __name__ == "__main__":
    driver = None
    logging.info(f"Запуск скрипта для тестирования ВСЕХ локаторов для {PLAYER_URL}")

    # --- Определяем ВСЕ локаторы ---
    locators = {
        "Price (New)": (By.XPATH, "//div[contains(@class, 'market-data--key') and normalize-space(.)='Current value']/ancestor::div[contains(@class, 'flex-col')][2]//div[contains(@class, 'market-data--value')][1]/span[1]"),
        "Change": (By.XPATH, "//div[contains(@class, 'market-data--value--change')]//span[contains(text(), '%')]"),
        "Update Time": (By.XPATH, "//div[contains(text(), 'Market Refresh')]/following-sibling::div[contains(@class, 'market-data--value-mini')]"),
        "Min Price": (By.XPATH, "//div[contains(text(), 'Market low/high')]/following-sibling::div[contains(@class, 'market-data--value-mini')]//span[1]"),
        "Max Price": (By.XPATH, "//div[contains(text(), 'Market low/high')]/following-sibling::div[contains(@class, 'market-data--value-mini')]//span[last()]")
    }
    # ------------------------------

    try:
        driver = setup_driver()
        logging.info(f"Переход по URL: {PLAYER_URL}")
        driver.get(PLAYER_URL)

        logging.info(f"Пауза {PAUSE_BEFORE_STOP} сек перед window.stop()...")
        time.sleep(PAUSE_BEFORE_STOP)

        try:
            logging.info("Выполнение driver.execute_script('window.stop();')")
            driver.execute_script("window.stop();")
            logging.info("window.stop() выполнен.")
        except WebDriverException as e:
             logging.warning(f"Не удалось выполнить window.stop(): {e}")

        logging.info(f"Пауза {PAUSE_AFTER_STOP} сек после window.stop()...")
        time.sleep(PAUSE_AFTER_STOP)

        # --- ТЕСТИРОВАНИЕ КАЖДОГО ЛОКАТОРА ---
        logging.info("--- Начало тестирования локаторов ---")
        results = {}

        for name, locator in locators.items():
            wait_time = WAIT_PRICE if "Price" in name else WAIT_OTHERS
            logging.info(f"Тестируем: '{name}' (ожидание {wait_time} сек)")
            try:
                wait = WebDriverWait(driver, wait_time)
                element = wait.until(EC.presence_of_element_located(locator))
                text = element.text.strip()
                logging.info(f"  [+] УСПЕХ! '{name}' найден. Текст: '{text}'")
                results[name] = text
            except TimeoutException:
                logging.warning(f"  [-] ТАЙМАУТ! '{name}' НЕ найден за {wait_time} сек. Локатор: {locator[1]}")
                results[name] = "!!! FAILED (Timeout) !!!"
            except NoSuchElementException: # Маловероятно с wait, но для полноты
                 logging.warning(f"  [-] ОШИБКА! '{name}' НЕ найден (NoSuchElement). Локатор: {locator[1]}")
                 results[name] = "!!! FAILED (NoSuchElement) !!!"
            except Exception as e:
                logging.error(f"  [!] НЕИЗВЕСТНАЯ ОШИБКА при поиске '{name}': {e}")
                results[name] = f"!!! FAILED (Exception: {e}) !!!"

        logging.info("--- Тестирование локаторов завершено ---")
        print("\n--- Результаты поиска ---")
        for name, result in results.items():
            print(f"{name}: {result}")
        print("------------------------\n")

        # Сохраняем HTML для возможного анализа
        logging.info("Получение HTML-кода страницы после тестов...")
        html_source = driver.page_source
        logging.info(f"Сохранение HTML-кода в файл: {OUTPUT_FILENAME}")
        try:
            with open(OUTPUT_FILENAME, "w", encoding="utf-8") as f:
                f.write(html_source)
            logging.info(f"HTML-код успешно сохранен в {OUTPUT_FILENAME}")
        except Exception as e:
            logging.error(f"Ошибка при сохранении HTML-кода в файл: {e}")

    except TimeoutException:
        logging.error(f"Таймаут загрузки страницы (до window.stop): {PLAYER_URL}")
    except WebDriverException as e:
        logging.error(f"Ошибка WebDriver: {e}")
    except Exception as e:
        logging.error(f"Неожиданная ошибка: {e}")
        traceback.print_exc()
    finally:
        if driver:
            logging.info("Окно браузера закроется через 15 секунд...")
            time.sleep(15)
            logging.info("Закрытие WebDriver...")
            driver.quit()
            logging.info("WebDriver закрыт.")