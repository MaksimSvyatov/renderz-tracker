# =============================================
# ФАЙЛ: get_page_source.py (версия с window.stop)
# Назначение: Получить HTML-код страницы игрока RenderZ ПОСЛЕ выполнения window.stop(),
#             чтобы имитировать состояние, видимое парсером scraper.py.
# =============================================
import time
import logging
import os
import sys
import traceback
from selenium import webdriver
from selenium.webdriver.firefox.service import Service as FirefoxService
from selenium.webdriver.firefox.options import Options as FirefoxOptions
from selenium.common.exceptions import WebDriverException, TimeoutException

# --- Настройки ---
# !!! ЗАМЕНИТЕ НА URL СТРАНИЦЫ ИГРОКА !!!
PLAYER_URL = "https://renderz.app/24/player/24018004"

# Имя файла для сохранения HTML
OUTPUT_FILENAME = "page_source_after_stop.html" # Изменил имя файла для ясности

# Паузы, имитирующие scraper.py
PAUSE_BEFORE_STOP = 1.5
PAUSE_AFTER_STOP = 0.5
# -----------------

# --- Настройка логирования ---
log_format = "%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s"
logging.basicConfig(level=logging.INFO, format=log_format, handlers=[logging.StreamHandler()])
logging.getLogger('selenium').setLevel(logging.WARNING)
logging.getLogger('urllib3').setLevel(logging.WARNING)
logging.getLogger('websockets').setLevel(logging.WARNING)

# --- Функция настройки драйвера ---
def setup_driver():
    """Настраивает и возвращает WebDriver."""
    options = FirefoxOptions()
    options.add_argument("--headless")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    # Важно: НЕ отключаем изображения, т.к. это может влиять на время загрузки и момент остановки
    # options.add_argument("--disable-images")
    # options.set_preference("permissions.default.image", 2)
    options.set_preference("dom.ipc.plugins.enabled.libflashplayer.so", "false")
    options.set_preference("javascript.enabled", True)
    options.set_preference("general.useragent.override", "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:109.0) Gecko/20100101 Firefox/119.0")

    try:
        driver = webdriver.Firefox(options=options)
        # Page load timeout может быть менее релевантен с window.stop(), но оставим на всякий случай
        driver.set_page_load_timeout(45)
        driver.set_script_timeout(30)
        logging.info("Настройки Selenium: используется Firefox (headless).")
        return driver
    except WebDriverException as e:
        logging.error(f"Ошибка инициализации Firefox WebDriver: {e}")
        logging.error("Убедитесь, что geckodriver установлен и доступен в системном PATH.")
        sys.exit(1)

# --- Основная логика ---
if __name__ == "__main__":
    if "ЗАМЕНИТЕ_ID_ИГРОКА" in PLAYER_URL:
        logging.error("Пожалуйста, замените 'ЗАМЕНИТЕ_ID_ИГРОКА' в переменной PLAYER_URL.")
        sys.exit(1)

    driver = None
    logging.info(f"Запуск скрипта для получения HTML-кода страницы ПОСЛЕ window.stop(): {PLAYER_URL}")
    try:
        driver = setup_driver()
        logging.info(f"Переход по URL: {PLAYER_URL}")
        driver.get(PLAYER_URL)

        logging.info(f"Пауза {PAUSE_BEFORE_STOP} сек перед window.stop()...")
        time.sleep(PAUSE_BEFORE_STOP)

        try:
            logging.info("Выполнение driver.execute_script('window.stop();')")
            driver.execute_script("window.stop();")
        except WebDriverException as e:
             logging.warning(f"Не удалось выполнить window.stop(): {e}")

        logging.info(f"Пауза {PAUSE_AFTER_STOP} сек после window.stop()...")
        time.sleep(PAUSE_AFTER_STOP)

        logging.info("Получение HTML-кода страницы (состояние после window.stop)...")
        html_source = driver.page_source
        # Дополнительно можно получить outerHTML корневого элемента, иногда это надежнее
        # try:
        #     html_source = driver.find_element(By.TAG_NAME, 'html').get_attribute('outerHTML')
        # except Exception as e_html:
        #     logging.warning(f"Не удалось получить outerHTML, используем page_source: {e_html}")
        #     html_source = driver.page_source


        logging.info(f"Сохранение HTML-кода в файл: {OUTPUT_FILENAME}")
        try:
            with open(OUTPUT_FILENAME, "w", encoding="utf-8") as f:
                f.write(html_source)
            logging.info(f"HTML-код успешно сохранен в {OUTPUT_FILENAME}")
            logging.info("Этот файл содержит HTML в том виде, в каком его видит парсер ПОСЛЕ остановки загрузки.")
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
            logging.info("Закрытие WebDriver...")
            driver.quit()
            logging.info("WebDriver закрыт.")