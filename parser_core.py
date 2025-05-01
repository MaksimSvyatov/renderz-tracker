# =============================================
# ФАЙЛ: parser_core.py (ВЕРСИЯ v1.1 - Basic Parsing Logic)
# - Содержит функцию parse_player_page.
# - Использует явные ожидания Selenium.
# - Извлекает цену, ордера, изменение, время обновления.
# =============================================

import logging
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
import time

logger = logging.getLogger("parser_core")

# --- Константы Селекторов (Примеры, могут требовать обновления) ---
# Убедитесь, что эти селекторы актуальны для renderz.app!
PRICE_SELECTOR = ".player-prices-l .price"  # Пример
MIN_ORDER_SELECTOR = ".player-prices-l .min-price" # Пример
MAX_ORDER_SELECTOR = ".player-prices-l .max-price" # Пример
PRICE_CHANGE_SELECTOR = ".player-prices-l .price-change" # Пример
UPDATE_TIME_SELECTOR = ".player-prices-l .prices-date" # Пример

# --- Основная функция парсинга ---

def parse_player_page(driver: WebDriver, player_name: str, player_url: str) -> dict | None:
    """
    Парсит страницу игрока на renderz.app, используя Selenium.

    Args:
        driver: Экземпляр Selenium WebDriver.
        player_name: Имя игрока (для логов).
        player_url: URL страницы игрока.

    Returns:
        Словарь с данными {'price': int|None, 'min_order': int|None,
                         'max_order': int|None, 'change': str|None,
                         'update_time': str|None}
        или None в случае критической ошибки загрузки.
    """
    logger.info(f"Парсим {player_name} (URL: {player_url})")
    data = {'price': None, 'min_order': None, 'max_order': None, 'change': None, 'update_time': None}
    retries = 2
    wait_time = 15 # Увеличим время ожидания

    for attempt in range(retries + 1):
        try:
            driver.get(player_url)
            # Явное ожидание появления ключевого элемента, например, цены
            WebDriverWait(driver, wait_time).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, PRICE_SELECTOR))
            )
            logger.debug(f"[{player_name}] Страница загружена, элемент цены найден.")

            # --- Извлечение данных ---
            try:
                price_element = driver.find_element(By.CSS_SELECTOR, PRICE_SELECTOR)
                price_text = price_element.text.strip().replace(',', '').replace(' ', '')
                if price_text.isdigit():
                    data['price'] = int(price_text)
                else:
                     logger.warning(f"[{player_name}] Не удалось распознать цену: '{price_text}'")
            except NoSuchElementException:
                logger.warning(f"[{player_name}] Элемент цены ({PRICE_SELECTOR}) не найден.")
            except Exception as e:
                 logger.error(f"[{player_name}] Ошибка извлечения цены: {e}")

            try:
                min_order_element = driver.find_element(By.CSS_SELECTOR, MIN_ORDER_SELECTOR)
                min_order_text = min_order_element.text.strip().replace(',', '').replace(' ', '')
                if min_order_text.isdigit():
                    data['min_order'] = int(min_order_text)
                else:
                    logger.warning(f"[{player_name}] Не удалось распознать мин. ордер: '{min_order_text}'")
            except NoSuchElementException:
                logger.warning(f"[{player_name}] Элемент мин. ордера ({MIN_ORDER_SELECTOR}) не найден.")
            except Exception as e:
                 logger.error(f"[{player_name}] Ошибка извлечения мин. ордера: {e}")

            try:
                max_order_element = driver.find_element(By.CSS_SELECTOR, MAX_ORDER_SELECTOR)
                max_order_text = max_order_element.text.strip().replace(',', '').replace(' ', '')
                if max_order_text.isdigit():
                    data['max_order'] = int(max_order_text)
                else:
                     logger.warning(f"[{player_name}] Не удалось распознать макс. ордер: '{max_order_text}'")
            except NoSuchElementException:
                logger.warning(f"[{player_name}] Элемент макс. ордера ({MAX_ORDER_SELECTOR}) не найден.")
            except Exception as e:
                 logger.error(f"[{player_name}] Ошибка извлечения макс. ордера: {e}")

            try:
                change_element = driver.find_element(By.CSS_SELECTOR, PRICE_CHANGE_SELECTOR)
                data['change'] = change_element.text.strip()
            except NoSuchElementException:
                 # Это может быть нормально, если цена не менялась
                 logger.debug(f"[{player_name}] Элемент изменения цены ({PRICE_CHANGE_SELECTOR}) не найден.")
                 data['change'] = '0%' # Можно поставить 0% по умолчанию
            except Exception as e:
                 logger.error(f"[{player_name}] Ошибка извлечения изменения цены: {e}")


            try:
                update_element = driver.find_element(By.CSS_SELECTOR, UPDATE_TIME_SELECTOR)
                data['update_time'] = update_element.text.strip()
            except NoSuchElementException:
                logger.warning(f"[{player_name}] Элемент времени обновления ({UPDATE_TIME_SELECTOR}) не найден.")
            except Exception as e:
                 logger.error(f"[{player_name}] Ошибка извлечения времени обновления: {e}")


            # --- Вывод результата парсинга ---
            price_log = data['price'] if data['price'] is not None else "N/A"
            change_log = data['change'] if data['change'] else "N/A"
            orders_log = f"Min: {data['min_order'] if data['min_order'] else 'N/A'} / Max: {data['max_order'] if data['max_order'] else 'N/A'}"
            update_log = data['update_time'] if data['update_time'] else "N/A"
            logger.info(f"Успешно {player_name}: Цена={price_log} Изм='{change_log}' Ордера='{orders_log}' Обн='{update_log}'")

            return data # Успешный парсинг

        except TimeoutException:
            logger.warning(f"[{player_name}] Таймаут ожидания элемента ({PRICE_SELECTOR}) на странице {player_url} (Попытка {attempt + 1}/{retries + 1})")
            if attempt < retries:
                logger.info(f"[{player_name}] Пауза перед повторной попыткой...")
                time.sleep(3 + attempt * 2) # Небольшая увеличивающаяся пауза
            else:
                 logger.error(f"[{player_name}] Таймаут загрузки страницы после {retries + 1} попыток.")
                 return None # Возвращаем None после всех попыток
        except Exception as e:
            logger.error(f"[{player_name}] Неожиданная ошибка при парсинге страницы: {e}", exc_info=True)
            return None # Возвращаем None при других критических ошибках

    return None # Если цикл завершился без return data