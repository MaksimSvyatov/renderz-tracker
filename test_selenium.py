# Файл: test_selenium.py
from selenium import webdriver
from selenium.webdriver.firefox.service import Service as FirefoxService
from selenium.webdriver.firefox.options import Options as FirefoxOptions
import time
import config # Чтобы взять путь, если он есть

print("Попытка запуска Firefox...")
options = FirefoxOptions()
options.add_argument("--headless") # Запуск без окна
GECKODRIVER_PATH = getattr(config, 'GECKODRIVER_PATH', None)
driver = None
try:
    if GECKODRIVER_PATH:
         print(f"Используется geckodriver: {GECKODRIVER_PATH}")
         service = FirefoxService(executable_path=GECKODRIVER_PATH)
    else:
         print("Используется geckodriver из PATH")
         service = FirefoxService()
    driver = webdriver.Firefox(service=service, options=options)
    print("WebDriver запущен успешно.")
    print("Попытка открыть сайт (google.com)...")
    driver.get("https://www.google.com")
    time.sleep(2) # Даем время загрузиться
    print(f"Заголовок страницы: {driver.title}")
    print("Тест Selenium УСПЕШЕН!")
except Exception as e:
    print(f"ОШИБКА Selenium: {e}")
finally:
    if driver:
        print("Закрытие WebDriver...")
        driver.quit()
        print("WebDriver закрыт.")