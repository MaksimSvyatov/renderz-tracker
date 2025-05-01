# # # # # # =============================================
# # # # # # ФАЙЛ: scraper.py (ВЕРСИЯ v7 - Добавлен import re)
# # # # # # - ДОБАВЛЕН import re для исправления NameError в compute_next_update_time
# # # # # # - ИЗМЕНЕНО: WebDriver создается и закрывается для каждого игрока в цикле
# # # # # # - Убрана сложная логика перезапуска WebDriver в главном цикле
# # # # # # - Исправлена ошибка с schedule.next_run
# # # # # # =============================================
# # # # # import time
# # # # # import logging
# # # # # from datetime import datetime, timedelta, timezone
# # # # # import os
# # # # # import sys
# # # # # import traceback
# # # # # import re # <--- ДОБАВЛЕНО ИСПРАВЛЕНИЕ
# # # # #
# # # # # # --- Проверка и импорт schedule ---
# # # # # try:
# # # # #     import schedule
# # # # # except ImportError:
# # # # #     # Используем print, так как logging может быть еще не настроен
# # # # #     print("КРИТИЧЕСКАЯ ОШИБКА: Модуль 'schedule' не найден. Пожалуйста, установите его: pip install schedule")
# # # # #     sys.exit(1)
# # # # # # --------------------------------
# # # # #
# # # # # # --- Проверка и импорт Selenium ---
# # # # # try:
# # # # #     from selenium import webdriver
# # # # #     from selenium.webdriver.firefox.service import Service as FirefoxService
# # # # #     from selenium.webdriver.firefox.options import Options as FirefoxOptions
# # # # #     from selenium.common.exceptions import NoSuchElementException, TimeoutException, WebDriverException
# # # # #     from selenium.webdriver.support.ui import WebDriverWait
# # # # #     from selenium.webdriver.support import expected_conditions as EC
# # # # #     from selenium.webdriver.common.by import By
# # # # # except ImportError as sel_err:
# # # # #      print(f"КРИТИЧЕСКАЯ ОШИБКА: Не найдены компоненты Selenium: {sel_err}")
# # # # #      print("Убедитесь, что Selenium установлен: pip install selenium")
# # # # #      sys.exit(1)
# # # # # # --------------------------------
# # # # #
# # # # # # --- Настройка логирования (до импорта локальных модулей) ---
# # # # # log_format = "%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s"
# # # # # log_dir = getattr(config, 'LOG_DIR', '.') if 'config' in sys.modules else '.' # Проверяем, импортирован ли config
# # # # # log_file = os.path.join(log_dir, "parser.log")
# # # # # try:
# # # # #     os.makedirs(log_dir, exist_ok=True)
# # # # #     logging.basicConfig(level=logging.DEBUG, format=log_format,
# # # # #                         handlers=[logging.FileHandler(log_file, encoding='utf-8'),
# # # # #                                   logging.StreamHandler()])
# # # # #     # Понижаем уровень логирования для selenium и urllib3
# # # # #     logging.getLogger('selenium.webdriver.remote.remote_connection').setLevel(logging.WARNING)
# # # # #     logging.getLogger('urllib3.connectionpool').setLevel(logging.WARNING)
# # # # #     logging.getLogger('websockets.client').setLevel(logging.WARNING)
# # # # #     logging.getLogger('matplotlib').setLevel(logging.WARNING)
# # # # # except Exception as log_setup_err:
# # # # #     print(f"Ошибка настройки логирования: {log_setup_err}")
# # # # #     # Базовое логирование в консоль, если настройка не удалась
# # # # #     logging.basicConfig(level=logging.DEBUG, format=log_format, handlers=[logging.StreamHandler()])
# # # # #
# # # # #
# # # # # # --- Локальные импорты ---
# # # # # try:
# # # # #     import config
# # # # #     import storage
# # # # #     import notifications
# # # # #     import signals
# # # # #     import ohlc_generator
# # # # #     import weekly_stats
# # # # #     import extended_analytics
# # # # #     import cycle_analysis
# # # # #     import events_manager
# # # # #     import model_trainer
# # # # # except ImportError as import_err:
# # # # #     log_msg = f"КРИТИЧЕСКАЯ ОШИБКА: Не найден один из модулей: {import_err}. Убедитесь, что все .py файлы находятся в той же папке."
# # # # #     logging.critical(log_msg) # Логгер уже должен быть настроен
# # # # #     sys.exit(1)
# # # # # # Проверка наличия ключевых функций после импорта
# # # # # if not hasattr(signals, 'check_signals'): logging.critical("Нет signals.check_signals! Выход."); sys.exit(1)
# # # # # if not hasattr(storage, 'save_player_price'): logging.critical("Нет storage.save_player_price! Выход."); sys.exit(1)
# # # # # if not hasattr(storage, 'get_recent_prices'): logging.critical("Нет storage.get_recent_prices! Выход."); sys.exit(1)
# # # # # if not hasattr(notifications, 'send_combined_message'): logging.critical("Нет notifications.send_combined_message! Выход."); sys.exit(1)
# # # # # if not hasattr(config, 'load_players'): logging.critical("Нет config.load_players! Выход."); sys.exit(1)
# # # # #
# # # # #
# # # # # # --- Глобальные переменные и константы из конфига ---
# # # # # players_config = {}
# # # # # player_next_update = {}
# # # # # last_known_price = {}
# # # # # PRICE_JUMP_THRESHOLD = getattr(config, 'PRICE_JUMP_THRESHOLD', 7.0)
# # # # # MIN_INTERVAL_SECONDS = getattr(config, 'MIN_INTERVAL_SECONDS', 60)
# # # # # PAUSE_BETWEEN_PLAYERS = getattr(config, 'PAUSE_BETWEEN_PLAYERS', 2)
# # # # # HISTORY_DAYS_FOR_SIGNALS = getattr(config, 'HISTORY_DAYS_FOR_SIGNALS', 90)
# # # # # MIN_HISTORY_FOR_SIGNALS = getattr(config, 'MIN_HISTORY_FOR_SIGNALS', 21)
# # # # # GECKODRIVER_PATH = getattr(config, 'GECKODRIVER_PATH', None)
# # # # #
# # # # #
# # # # # # --- Настройки Selenium ---
# # # # # def setup_driver():
# # # # #     """Настраивает и возвращает WebDriver."""
# # # # #     options = FirefoxOptions()
# # # # #     options.add_argument("--headless")
# # # # #     options.add_argument("--disable-gpu")
# # # # #     options.add_argument("--no-sandbox")
# # # # #     options.add_argument("--disable-dev-shm-usage")
# # # # #     options.add_argument("--disable-images")
# # # # #     options.set_preference("permissions.default.image", 2)
# # # # #     options.set_preference("dom.ipc.plugins.enabled.libflashplayer.so", "false")
# # # # #     options.set_preference("javascript.enabled", True)
# # # # #     options.set_preference("general.useragent.override",
# # # # #                            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/119.0")
# # # # #     service_args = []
# # # # #     service = None
# # # # #     driver = None
# # # # #     try:
# # # # #         gecko_log_path = os.path.join(log_dir, "geckodriver.log") # Используем общую log_dir
# # # # #         if GECKODRIVER_PATH and os.path.isfile(GECKODRIVER_PATH):
# # # # #             logging.info(f"Используется geckodriver из указанного пути: {GECKODRIVER_PATH}")
# # # # #             service = FirefoxService(executable_path=GECKODRIVER_PATH, service_args=service_args, log_path=gecko_log_path)
# # # # #         else:
# # # # #             if GECKODRIVER_PATH: logging.warning(f"Указанный путь geckodriver '{GECKODRIVER_PATH}' не найден или не файл, используется geckodriver из системного PATH.")
# # # # #             else: logging.info("Используется geckodriver из системного PATH (переменная GECKODRIVER_PATH не задана или пуста).")
# # # # #             service = FirefoxService(service_args=service_args, log_path=gecko_log_path) # Лог и для PATH-версии
# # # # #         logging.info("Попытка запуска Firefox WebDriver...")
# # # # #         driver = webdriver.Firefox(service=service, options=options)
# # # # #         driver.set_page_load_timeout(60)
# # # # #         driver.set_script_timeout(45)
# # # # #         logging.info("Настройки Selenium: используется Firefox (headless), изображения отключены.")
# # # # #         logging.info("WebDriver успешно создан.")
# # # # #         return driver
# # # # #     except WebDriverException as e:
# # # # #         logging.error(f"Критическая ошибка инициализации Firefox WebDriver: {e}")
# # # # #         if "cannot find firefox binary" in str(e).lower(): logging.error("Не найден исполняемый файл Firefox. Убедитесь, что Firefox установлен.")
# # # # #         elif "geckodriver executable needs to be in PATH" in str(e): logging.error("Geckodriver не найден в системном PATH и не указан корректный GECKODRIVER_PATH в config.py.")
# # # # #         elif "expected str, bytes or os.PathLike object, not NoneType" in str(e) and GECKODRIVER_PATH is None: logging.error("Geckodriver не найден в системном PATH, а GECKODRIVER_PATH не задан.")
# # # # #         elif "Message: Failed to decode response from marionette" in str(e): logging.error("Ошибка связи с Firefox (marionette). Возможно, несовместимость версий Firefox/Geckodriver или проблемы с браузером.")
# # # # #         else: logging.error(f"Неизвестная ошибка WebDriver. Детали: {traceback.format_exc()}")
# # # # #         if driver:
# # # # #              try: driver.quit()
# # # # #              except: pass
# # # # #         return None
# # # # #     except Exception as e_setup:
# # # # #         logging.error(f"Неожиданная ошибка в setup_driver: {e_setup}", exc_info=True)
# # # # #         if driver:
# # # # #             try: driver.quit()
# # # # #             except: pass
# # # # #         return None
# # # # #
# # # # #
# # # # # # --- Основные функции парсинга ---
# # # # # def parse_player(driver, player_name, url):
# # # # #     """Парсит данные одного игрока."""
# # # # #     # Убрана проверка is_driver_active здесь, т.к. драйвер создается перед вызовом
# # # # #     logging.info(f"Парсим {player_name} (URL: {url})")
# # # # #     price, change, next_update_str, min_val, max_val = None, None, "N/A", None, None
# # # # #     html_dump_path = os.path.join(getattr(config, 'LOG_DIR', '.'), f"error_{player_name.replace(' ','_')}_{datetime.now().strftime('%H%M%S')}.html")
# # # # #     try:
# # # # #         driver.get(url)
# # # # #         time.sleep(1.5)
# # # # #         try: driver.execute_script("window.stop();"); logging.debug(f"window.stop() выполнен для {player_name}"); time.sleep(0.5)
# # # # #         except WebDriverException as e_stop: logging.warning(f"Не удалось выполнить window.stop() для {player_name}: {e_stop}")
# # # # #         wait_long = WebDriverWait(driver, 15); wait_short = WebDriverWait(driver, 5)
# # # # #         price_locator = (By.XPATH, "//div[contains(@class, 'market-data--key') and normalize-space(.)='Current value']/ancestor::div[contains(@class, 'flex-col')][2]//div[contains(@class, 'market-data--value')][1]/span[1]")
# # # # #         try:
# # # # #             price_element = wait_long.until(EC.visibility_of_element_located(price_locator))
# # # # #             raw_price_text = price_element.text.strip()
# # # # #             cleaned_price = raw_price_text.replace(',','').replace(' ','').replace('\u00A0','').replace('-','')
# # # # #             price = int(cleaned_price) if cleaned_price.isdigit() else 0
# # # # #             if price == 0 and raw_price_text != '0': logging.warning(f"Цена для {player_name} спарсилась как 0, но текст был '{raw_price_text}'. Проверьте XPath.")
# # # # #         except TimeoutException:
# # # # #             logging.error(f"Таймаут ожидания ЦЕНЫ для {player_name}");
# # # # #             try:
# # # # #                  with open(html_dump_path, "w", encoding="utf-8") as f: f.write(driver.page_source)
# # # # #                  logging.info(f"HTML при ошибке цены сохранен: {html_dump_path}")
# # # # #             except Exception as dump_err: logging.error(f"Не сохранить HTML: {dump_err}")
# # # # #             return None
# # # # #         except Exception as e: logging.error(f"Ошибка парсинга ЦЕНЫ для {player_name}: {e}", exc_info=True); return None
# # # # #
# # # # #         change_locator = (By.XPATH, "//div[contains(@class, 'market-data--value--change')]//span[contains(text(), '%')]")
# # # # #         try: change = wait_short.until(EC.visibility_of_element_located(change_locator)).text.strip()
# # # # #         except: change = "0%"
# # # # #         next_upd_loc = (By.XPATH, "//div[contains(text(), 'Market Refresh')]/following-sibling::div[contains(@class, 'market-data--value-mini')]")
# # # # #         try: next_update_str = wait_short.until(EC.visibility_of_element_located(next_upd_loc)).text.strip()
# # # # #         except: next_update_str = "N/A"
# # # # #         min_loc = (By.XPATH, "//div[contains(text(), 'Market low/high')]/following-sibling::div[contains(@class, 'market-data--value-mini')]//span[1]")
# # # # #         max_loc = (By.XPATH, "//div[contains(text(), 'Market low/high')]/following-sibling::div[contains(@class, 'market-data--value-mini')]//span[last()]")
# # # # #         try: min_raw = wait_short.until(EC.visibility_of_element_located(min_loc)).text.strip(); min_clean = min_raw.replace(',','').replace(' ','').replace('\u00A0','').replace('-',''); min_val = int(min_clean) if min_clean.isdigit() else 0
# # # # #         except: min_val = None
# # # # #         try: max_raw = wait_short.until(EC.visibility_of_element_located(max_loc)).text.strip(); max_clean = max_raw.replace(',','').replace(' ','').replace('\u00A0','').replace('-',''); max_val = int(max_clean) if max_clean.isdigit() else 0
# # # # #         except: max_val = None
# # # # #
# # # # #         if price is None: logging.error(f"Итоговая цена None для {player_name} после парсинга"); return None
# # # # #         logging.info(f"Успешно {player_name}: Цена={price:,}, Изм='{change}', Мин={min_val}, Макс={max_val}, Обн='{next_update_str}'".replace(",", "\u00A0"))
# # # # #         return (price, change, next_update_str, min_val, max_val)
# # # # #     except TimeoutException: logging.error(f"Таймаут ЗАГРУЗКИ страницы {url}"); return None
# # # # #     except WebDriverException as e:
# # # # #         logging.error(f"Ошибка WebDriver при парсинге {player_name}: {e}", exc_info=True)
# # # # #         try:
# # # # #             with open(html_dump_path, "w", encoding="utf-8") as f: f.write(driver.page_source)
# # # # #             logging.info(f"HTML при ошибке WebDriver сохранен: {html_dump_path}")
# # # # #         except Exception as dump_err: logging.error(f"Не сохранить HTML: {dump_err}")
# # # # #         return None # Считаем парсинг неудачным
# # # # #     except Exception as e:
# # # # #         logging.error(f"Неожиданная ошибка парсинга {player_name}: {e}", exc_info=True)
# # # # #         try:
# # # # #             with open(html_dump_path, "w", encoding="utf-8") as f: f.write(driver.page_source)
# # # # #             logging.info(f"HTML при неожиданной ошибке сохранен: {html_dump_path}")
# # # # #         except Exception as dump_err: logging.error(f"Не сохранить HTML: {dump_err}")
# # # # #         return None
# # # # #
# # # # # # --- Расчет времени следующего обновления ---
# # # # # def compute_next_update_time(next_update_str_raw):
# # # # #     now_utc = datetime.now(timezone.utc); default_delta = timedelta(minutes=15)
# # # # #     if not next_update_str_raw or next_update_str_raw.lower() == 'n/a': logging.debug(f"Не удалось получить время обновления, используем дефолт +{default_delta}"); return now_utc + default_delta
# # # # #     next_upd_cleaned = next_update_str_raw.lower().replace('in ', '').replace('через ', '').split(' at ')[0].split(' в ')[0].strip().replace(',', '')
# # # # #     h, m, s = 0, 0, 0; extracted = False
# # # # #     # Используем re, который теперь импортирован
# # # # #     matches = re.findall(r'(\d+)\s*([hmsчмс])', next_upd_cleaned)
# # # # #     try:
# # # # #         if matches:
# # # # #             for val_s, unit in matches:
# # # # #                 val = int(val_s)
# # # # #                 if unit in ('h', 'ч'): h = val; extracted = True
# # # # #                 elif unit in ('m', 'м'): m = val; extracted = True
# # # # #                 elif unit in ('s', 'с'): s = val; extracted = True
# # # # #             if extracted: delta = timedelta(hours=h, minutes=m, seconds=s + 60)
# # # # #             else: delta = default_delta
# # # # #         else: delta = default_delta
# # # # #         if delta.total_seconds() <= 0: delta = timedelta(minutes=5)
# # # # #         next_t = now_utc + delta
# # # # #         logging.debug(f"Следующее обновление ({next_update_str_raw} -> {delta}) для игрока в: {next_t:%Y-%m-%d %H:%M:%S %Z}")
# # # # #         return next_t
# # # # #     except Exception as e: logging.error(f"Ошибка в compute_next_update_time для '{next_update_str_raw}': {e}"); return now_utc + default_delta
# # # # #
# # # # # # --- Проверка скачка цены ---
# # # # # def check_and_notify_price_jump(player_name, current_price):
# # # # #     global last_known_price
# # # # #     if current_price is None: return
# # # # #     prev_price = last_known_price.get(player_name)
# # # # #     last_known_price[player_name] = current_price
# # # # #     price_f = f"{current_price:,.0f}".replace(",", "\u00A0")
# # # # #     prev_price_f = f"{prev_price:,.0f}".replace(",", "\u00A0") if prev_price is not None else "N/A"
# # # # #     if (prev_price is None or prev_price <= 0) and current_price > 0: logging.info(f"Цена для {player_name} ПОЯВИЛАСЬ: {price_f}")
# # # # #     elif prev_price is not None and prev_price > 0 and current_price <= 0: logging.warning(f"Цена для {player_name} ИСЧЕЗЛА (стала {price_f}, была {prev_price_f})")
# # # # #     elif prev_price is not None and prev_price > 0 and current_price > 0:
# # # # #         try:
# # # # #             change_pct = abs(current_price - prev_price) / prev_price * 100
# # # # #             if change_pct >= PRICE_JUMP_THRESHOLD:
# # # # #                 sign = "+" if current_price > prev_price else "-"
# # # # #                 msg = (f"🚨 СКАЧОК ЦЕНЫ: {player_name}!\n" f"Текущая: {price_f}\n" f"Предыдущая: {prev_price_f}\n" f"Изменение: {sign}{change_pct:.1f}%")
# # # # #                 logging.warning(msg); notifications.send_telegram_message(msg)
# # # # #         except ZeroDivisionError: pass
# # # # #         except Exception as e: logging.error(f"Ошибка проверки скачка цены для {player_name}: {e}")
# # # # #
# # # # # # --- Основной цикл парсинга (с новым WebDriver для каждого игрока) ---
# # # # # def fetch_all_players():
# # # # #     global players_config, player_next_update, last_known_price
# # # # #     logging.info("Загрузка конфигурации игроков...");
# # # # #     try: players_config = config.load_players()
# # # # #     except Exception as e_cfg: logging.critical(f"Критическая ошибка загрузки players_config: {e_cfg}", exc_info=True); return
# # # # #     if not players_config: logging.error("Список игроков пуст в конфигурации."); return
# # # # #
# # # # #     now_utc = datetime.now(timezone.utc)
# # # # #     for name in players_config.keys():
# # # # #         if name not in player_next_update: player_next_update[name] = now_utc
# # # # #         if name not in last_known_price:
# # # # #              try: hist = storage.get_recent_prices(name, days=1); last_known_price[name] = hist[-1] if hist else None
# # # # #              except Exception as e: logging.error(f"Ошибка получения начальной цены для {name}: {e}"); last_known_price[name] = None
# # # # #              if last_known_price[name] is not None: logging.info(f"Загружена последняя известная цена для {name}: {last_known_price[name]:,.0f}".replace(",", "\u00A0"))
# # # # #              else: logging.info(f"Нет недавней истории для {name}, начальная цена не установлена.")
# # # # #
# # # # #     logging.info(f"Запуск основного цикла парсинга для {len(players_config)} игроков...")
# # # # #     while True:
# # # # #         driver = None
# # # # #         try:
# # # # #             schedule.run_pending()
# # # # #             now_utc = datetime.now(timezone.utc)
# # # # #             due_players = {}
# # # # #             for p_name, p_info in players_config.items():
# # # # #                  if isinstance(p_info, dict) and "url" in p_info:
# # # # #                      next_update_time = player_next_update.get(p_name, now_utc)
# # # # #                      if now_utc >= next_update_time: due_players[p_name] = p_info["url"]
# # # # #                  else: logging.warning(f"Некорректная конфигурация для игрока '{p_name}'")
# # # # #
# # # # #             if due_players:
# # # # #                 logging.info(f"Игроки для парсинга ({len(due_players)}): {', '.join(due_players.keys())}")
# # # # #                 sorted_due = sorted(due_players.items()); proc_count = 0
# # # # #                 for p_name, url in sorted_due:
# # # # #                     driver = None # Сбрасываем перед созданием
# # # # #                     try:
# # # # #                         driver = setup_driver()
# # # # #                         if driver is None: logging.error(f"Не удалось создать WebDriver для {p_name}. Пропуск."); player_next_update[p_name] = datetime.now(timezone.utc) + timedelta(minutes=30); continue
# # # # #
# # # # #                         parsed_data = parse_player(driver, p_name, url)
# # # # #                         proc_count += 1
# # # # #
# # # # #                         if parsed_data:
# # # # #                             price, change, next_upd_str, min_v, max_v = parsed_data
# # # # #                             check_and_notify_price_jump(p_name, price)
# # # # #                             storage.save_player_price(p_name, price, change, min_v, max_v)
# # # # #                             if price is not None and price > 0:
# # # # #                                 try:
# # # # #                                     history_prices = storage.get_recent_prices(p_name, days=HISTORY_DAYS_FOR_SIGNALS)
# # # # #                                     if not isinstance(history_prices, list): logging.error(f"get_recent_prices вернул не список для {p_name}: {type(history_prices)}"); history_prices = []
# # # # #                                     if not history_prices or history_prices[-1] != price: history_prices.append(price)
# # # # #                                     valid_hist_prices = [p for p in history_prices if p is not None and p > 0]
# # # # #                                     if len(valid_hist_prices) >= MIN_HISTORY_FOR_SIGNALS:
# # # # #                                         logging.debug(f"Расчет сигналов для {p_name} ({len(valid_hist_prices)} валидных цен)")
# # # # #                                         sig_data = signals.check_signals(p_name, valid_hist_prices)
# # # # #                                         notifications.send_combined_message(p_name, price, change, min_v, max_v, next_upd_str, sig_data)
# # # # #                                     else:
# # # # #                                          logging.warning(f"Недостаточно валидных цен ({len(valid_hist_prices)}<{MIN_HISTORY_FOR_SIGNALS}) для сигналов {p_name}. Отправка базового сообщения.")
# # # # #                                          notifications.send_basic_message(p_name, price, change, min_v, max_v)
# # # # #                                 except Exception as sig_err:
# # # # #                                      logging.error(f"Ошибка расчета сигналов/отправки уведомления для {p_name}: {sig_err}", exc_info=True)
# # # # #                                      notifications.send_basic_message(p_name, price, change, min_v, max_v)
# # # # #                             else:
# # # # #                                  logging.info(f"Цена для {p_name} равна {price}. Сигналы не рассчитываются.")
# # # # #                                  if price == 0: notifications.send_basic_message(p_name, price, change, min_v, max_v)
# # # # #                             player_next_update[p_name] = compute_next_update_time(next_upd_str)
# # # # #                         else: # Ошибка парсинга
# # # # #                             logging.warning(f"Парсинг {p_name} не удался. Повторная попытка через 1 час.")
# # # # #                             player_next_update[p_name] = datetime.now(timezone.utc) + timedelta(hours=1)
# # # # #
# # # # #                     except WebDriverException as e_wd_inner:
# # # # #                          logging.error(f"Ошибка WebDriver при обработке {p_name}: {e_wd_inner}. Повтор через 30 минут.")
# # # # #                          player_next_update[p_name] = datetime.now(timezone.utc) + timedelta(minutes=30)
# # # # #                     except Exception as e_inner:
# # # # #                          logging.error(f"Неожиданная ошибка при обработке {p_name}: {e_inner}", exc_info=True)
# # # # #                          player_next_update[p_name] = datetime.now(timezone.utc) + timedelta(hours=1)
# # # # #                     finally:
# # # # #                          if driver:
# # # # #                               try: driver.quit(); logging.debug(f"WebDriver для {p_name} закрыт.")
# # # # #                               except Exception as qe: logging.error(f"Ошибка driver.quit() для {p_name}: {qe}")
# # # # #                          driver = None
# # # # #
# # # # #                     if proc_count < len(due_players):
# # # # #                         logging.debug(f"Пауза {PAUSE_BETWEEN_PLAYERS} сек перед следующим игроком...")
# # # # #                         time.sleep(PAUSE_BETWEEN_PLAYERS)
# # # # #
# # # # #             else: # Нет игроков для парсинга
# # # # #                 next_player_times = [t for t in player_next_update.values() if t > now_utc]
# # # # #                 next_player_t = min(next_player_times) if next_player_times else now_utc + timedelta(hours=1)
# # # # #                 next_job_dt = None; all_jobs = schedule.get_jobs()
# # # # #                 if all_jobs:
# # # # #                     job_run_times = [job.next_run for job in all_jobs if job.next_run and isinstance(job.next_run, datetime)]
# # # # #                     if job_run_times:
# # # # #                          try:
# # # # #                              min_job_time_naive = min(job_run_times)
# # # # #                              if min_job_time_naive.tzinfo is None: next_job_dt = min_job_time_naive.replace(tzinfo=timezone.utc)
# # # # #                              else: next_job_dt = min_job_time_naive.astimezone(timezone.utc)
# # # # #                          except Exception as e_min_time: logging.error(f"Ошибка определения минимального времени задачи: {e_min_time}")
# # # # #                 if next_job_dt is None: logging.debug("Нет активных задач по расписанию."); next_job_dt = now_utc + timedelta(days=1)
# # # # #                 wait_until = min(next_player_t, next_job_dt); wait_seconds = (wait_until - now_utc).total_seconds()
# # # # #                 wait_seconds = max(MIN_INTERVAL_SECONDS, wait_seconds if wait_seconds > 1 else MIN_INTERVAL_SECONDS)
# # # # #                 logging.info(f"Нет игроков для парсинга. Ожидание {wait_seconds:.0f} сек до {wait_until:%Y-%m-%d %H:%M:%S %Z}")
# # # # #                 time.sleep(wait_seconds)
# # # # #
# # # # #         except KeyboardInterrupt: logging.info("Обработка Ctrl+C..."); break
# # # # #         except Exception as e_loop:
# # # # #             logging.error(f"Критическая ошибка во ВНЕШНЕМ цикле fetch_all_players: {e_loop}", exc_info=True)
# # # # #             logging.info("Пауза 60 секунд перед следующей попыткой...")
# # # # #             if driver: # Закрываем драйвер, если ошибка произошла до его закрытия в finally
# # # # #                 try: driver.quit()
# # # # #                 except Exception as qe: logging.error(f"Ошибка driver.quit() после ошибки в цикле: {qe}")
# # # # #                 driver = None
# # # # #             time.sleep(60)
# # # # #
# # # # # # --- Проверка активности WebDriver ---
# # # # # def is_driver_active(driver):
# # # # #     # Эта функция больше не нужна, т.к. драйвер создается на каждую итерацию,
# # # # #     # но оставим ее для возможного использования в будущем
# # # # #     if driver is None: return False
# # # # #     try: _ = driver.window_handles; return True
# # # # #     except WebDriverException as e: logging.warning(f"WD неактивен (проверка handles): {e}"); return False
# # # # #     except Exception as e: logging.error(f"Неожиданная ошибка проверки активности WebDriver: {e}"); return False
# # # # #
# # # # # # --- Ежедневные задачи ---
# # # # # def daily_job_runner():
# # # # #     logging.info("=== ЗАПУСК ЕЖЕДНЕВНЫХ ЗАДАЧ (09:00 UTC) ===")
# # # # #     start_time = time.time()
# # # # #     tasks = {
# # # # #         "Проверка лога событий": events_manager.check_event_log_relevance,
# # # # #         "Генерация OHLC": ohlc_generator.rewrite_ohlc_summary,
# # # # #         "Расширенная аналитика": extended_analytics.run_extended_analytics,
# # # # #         "Недельная сводка CSV": weekly_stats.finalize_weekly_summary,
# # # # #         "Недельный текстовый отчет": cycle_analysis.generate_weekly_text_report,
# # # # #         "Периодическое обучение моделей": periodic_model_training, }
# # # # #     for task_name, task_func in tasks.items():
# # # # #         logging.info(f"--- Запуск задачи: {task_name} ---")
# # # # #         try:
# # # # #             if callable(task_func): task_func()
# # # # #             else: logging.error(f"Задача '{task_name}' не является вызываемой функцией!")
# # # # #         except Exception as e: logging.error(f"Ошибка при выполнении задачи '{task_name}': {e}", exc_info=True)
# # # # #     elapsed_time = time.time() - start_time
# # # # #     logging.info(f"=== ЕЖЕДНЕВНЫЕ ЗАДАЧИ ЗАВЕРШЕНЫ (за {elapsed_time:.1f} сек) ===")
# # # # #
# # # # # # --- Управление обучением моделей ---
# # # # # last_training_time = None
# # # # # def periodic_model_training():
# # # # #     global last_training_time
# # # # #     now_utc = datetime.now(timezone.utc); run_training = False
# # # # #     model_dir = getattr(config, 'MODEL_DIR', 'models')
# # # # #     if not os.path.isdir(model_dir):
# # # # #         logging.warning(f"Папка для моделей '{model_dir}' не найдена. Создаем...")
# # # # #         try: os.makedirs(model_dir, exist_ok=True)
# # # # #         except OSError as e: logging.error(f"Не удалось создать папку моделей '{model_dir}': {e}"); return
# # # # #     if last_training_time is None:
# # # # #         try: models_exist = any(f.endswith(".joblib") for f in os.listdir(model_dir))
# # # # #         except Exception as e: logging.error(f"Ошибка чтения директории моделей '{model_dir}': {e}"); models_exist = False
# # # # #         if not models_exist: logging.info(f"Модели в '{model_dir}' не найдены. Запуск первичного обучения..."); run_training = True
# # # # #         else: logging.info(f"Найдены существующие модели ({len([f for f in os.listdir(model_dir) if f.endswith('.joblib')])} шт.). Следующее плановое обучение через 7 дней."); last_training_time = now_utc
# # # # #     elif (now_utc - last_training_time).days >= 7: logging.info(f"Прошло >= 7 дней с последнего обучения. Запуск планового обучения..."); run_training = True
# # # # #     else: days_left = 7 - (now_utc - last_training_time).days; logging.info(f"До следующего планового обучения моделей осталось примерно {days_left} дн.")
# # # # #     if run_training:
# # # # #         logging.info("=== НАЧАЛО ОБУЧЕНИЯ МОДЕЛЕЙ ===")
# # # # #         start_train_time = time.time()
# # # # #         try:
# # # # #             if hasattr(model_trainer,'train_and_save_all_models') and callable(model_trainer.train_and_save_all_models):
# # # # #                 model_trainer.train_and_save_all_models()
# # # # #                 last_training_time = datetime.now(timezone.utc)
# # # # #                 elapsed_train_time = time.time() - start_train_time
# # # # #                 logging.info(f"=== ОБУЧЕНИЕ МОДЕЛЕЙ ЗАВЕРШЕНО (за {elapsed_train_time:.1f} сек) ===")
# # # # #             else: logging.error("Функция model_trainer.train_and_save_all_models не найдена или не является функцией!")
# # # # #         except Exception as e_train: logging.error(f"Ошибка во время обучения моделей: {e_train}", exc_info=True)
# # # # #
# # # # # # --- Точка входа ---
# # # # # if __name__ == "__main__":
# # # # #     logging.info("[scraper] Старт парсера RenderZ.")
# # # # #     try:
# # # # #         if hasattr(notifications, 'send_telegram_message') and callable(notifications.send_telegram_message): notifications.send_telegram_message("🚀 Парсер RenderZ запущен!")
# # # # #         else: logging.error("Функция send_telegram_message не найдена.")
# # # # #     except Exception as tg_err: logging.error(f"Ошибка отправки стартового сообщения в TG: {tg_err}")
# # # # #
# # # # #     # Убрали создание WebDriver здесь
# # # # #     try:
# # # # #         # Настраиваем расписание
# # # # #         schedule.every().day.at("09:00").do(daily_job_runner) # 09:00 UTC
# # # # #         jobs = schedule.get_jobs()
# # # # #         if jobs:
# # # # #              first_job = jobs[0]; next_run_time = first_job.next_run
# # # # #              if isinstance(next_run_time, datetime):
# # # # #                  try:
# # # # #                      if next_run_time.tzinfo is None: next_run_utc = next_run_time.replace(tzinfo=timezone.utc)
# # # # #                      else: next_run_utc = next_run_time.astimezone(timezone.utc)
# # # # #                      logging.info(f"Ежедневная задача запланирована. Ближайший запуск: {next_run_utc:%Y-%m-%d %H:%M:%S %Z}.")
# # # # #                  except Exception as e_tz: logging.error(f"Ошибка обработки времени задачи {next_run_time}: {e_tz}")
# # # # #              else: logging.warning(f"Не удалось получить время следующего запуска для первой задачи ({type(next_run_time)}).")
# # # # #         else: logging.error("Не удалось запланировать ежедневную задачу (нет задач в schedule)!")
# # # # #
# # # # #         periodic_model_training()
# # # # #         fetch_all_players() # Запускаем основной цикл без передачи драйвера
# # # # #
# # # # #     except SystemExit: logging.info("Получен SystemExit. Завершение работы...")
# # # # #     except ImportError as ie: logging.critical(f"Критическая ошибка импорта в __main__: {ie}")
# # # # #     except KeyboardInterrupt: logging.info("Получено прерывание (Ctrl+C). Завершение работы...")
# # # # #     except Exception as e_main:
# # # # #          logging.critical(f"КРИТИЧЕСКАЯ НЕПЕРЕХВАЧЕННАЯ ОШИБКА в __main__: {e_main}", exc_info=True)
# # # # #          try:
# # # # #             if hasattr(notifications, 'send_telegram_message') and callable(notifications.send_telegram_message):
# # # # #                 error_message = f"‼️ КРИТ. ОШИБКА парсера:\n{type(e_main).__name__}: {str(e_main)[:500]}\n{traceback.format_exc()[-1000:]}"
# # # # #                 notifications.send_telegram_message(error_message)
# # # # #             else: logging.error("Функция send_telegram_message не найдена для отправки ошибки.")
# # # # #          except Exception as tge: logging.error(f"Ошибка отправки сообщения об ошибке в TG: {tge}")
# # # # #     finally:
# # # # #         logging.info("Начало процедуры завершения работы...")
# # # # #         # Не закрываем драйвер здесь, т.к. он закрывается внутри fetch_all_players
# # # # #         try:
# # # # #             if hasattr(notifications, 'send_telegram_message') and callable(notifications.send_telegram_message): notifications.send_telegram_message("🛑 Парсер RenderZ остановлен.")
# # # # #             else: logging.error("Функция send_telegram_message не найдена для финального сообщения.")
# # # # #         except Exception as tge_final: logging.error(f"Ошибка отправки финального сообщения в TG: {tge_final}")
# # # # #         logging.info("Парсер RenderZ окончательно остановлен.")
# # # # #         sys.exit(0)
# # # # #
# # # # #
# # # #
# # # # # =============================================
# # # # # ФАЙЛ: scraper.py (ВЕРСИЯ v7.1 - Исправлен вызов notifications)
# # # # # - ИСПРАВЛЕНО: Вызов notifications.send_combined_message заменен
# # # # #               на notifications.send_combined_notification.
# # # # # - ДОБАВЛЕНО: Проверка наличия signals.check_signals при старте.
# # # # # =============================================
# # # #
# # # # import logging
# # # # import schedule
# # # # import time
# # # # import json
# # # # import os
# # # # import sys
# # # # from datetime import datetime, timedelta, timezone
# # # # import traceback
# # # # import re # Добавлен для парсинга ордеров
# # # # from selenium import webdriver
# # # # from selenium.webdriver.firefox.service import Service as FirefoxService
# # # # from selenium.webdriver.firefox.options import Options as FirefoxOptions
# # # # from selenium.common.exceptions import (WebDriverException, TimeoutException,
# # # #                                         NoSuchElementException, StaleElementReferenceException)
# # # # from selenium.webdriver.common.by import By
# # # # from selenium.webdriver.support.ui import WebDriverWait
# # # # from selenium.webdriver.support import expected_conditions as EC
# # # #
# # # # # --- Импорт пользовательских модулей ---
# # # # try:
# # # #     import config
# # # #     import storage
# # # #     import signals
# # # #     import notifications
# # # #     import ohlc_generator
# # # #     import model_trainer
# # # #     import evaluate_model
# # # #     import events_manager
# # # #     import weekly_stats # Добавлен импорт
# # # # except ImportError as e:
# # # #     log_func = logging.critical if logging.getLogger().hasHandlers() else print
# # # #     log_func(f"Ошибка импорта модуля: {e}. Убедитесь, что все файлы проекта находятся в одной директории.")
# # # #     sys.exit(1) # Критическая ошибка, выходим
# # # #
# # # # # --- Настройка Логирования ---
# # # # LOG_DIR = getattr(config, 'LOG_DIR', 'logs')
# # # # os.makedirs(LOG_DIR, exist_ok=True)
# # # # log_filename = os.path.join(LOG_DIR, f"scraper_{datetime.now().strftime('%Y-%m-%d')}.log")
# # # # logging.basicConfig(
# # # #     level=logging.DEBUG,
# # # #     format='%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s',
# # # #     handlers=[
# # # #         logging.StreamHandler(sys.stdout),
# # # #         logging.FileHandler(log_filename, encoding='utf-8')
# # # #     ]
# # # # )
# # # # logging.getLogger("urllib3").setLevel(logging.WARNING)
# # # # logging.getLogger("selenium").setLevel(logging.INFO)
# # # # logging.getLogger("schedule").setLevel(logging.INFO)
# # # #
# # # # # --- Проверка наличия необходимых функций в модулях ---
# # # # # Проверяем функции notifications
# # # # if not hasattr(notifications, 'send_combined_notification'): # ПРОВЕРКА ИСПРАВЛЕНА
# # # #     logging.critical("Нет notifications.send_combined_notification! Выход.")
# # # #     sys.exit(1)
# # # # if not hasattr(notifications, 'format_error_message'):
# # # #      logging.critical("Нет notifications.format_error_message! Выход.")
# # # #      sys.exit(1)
# # # # if not hasattr(notifications, 'send_telegram_message'):
# # # #      logging.critical("Нет notifications.send_telegram_message! Выход.")
# # # #      sys.exit(1)
# # # # # Проверяем функции signals
# # # # if not hasattr(signals, 'check_signals'): # <-- ДОБАВЛЕНА ЭТА ПРОВЕРКА
# # # #     logging.critical("Нет signals.check_signals! Выход.")
# # # #     sys.exit(1)
# # # #
# # # #
# # # # # --- Глобальные переменные и константы ---
# # # # PLAYER_UPDATE_INTERVAL = {} # Словарь для хранения времени следующего обновления для каждого игрока
# # # # LAST_KNOWN_PRICE = {} # Словарь для хранения последней известной цены
# # # # GECKODRIVER_PATH = os.environ.get('GECKODRIVER_PATH', None) # Путь к geckodriver из переменной окружения
# # # #
# # # # # --- Функции WebDriver ---
# # # #
# # # # def create_webdriver():
# # # #     """Создает и настраивает экземпляр WebDriver Firefox."""
# # # #     if GECKODRIVER_PATH and os.path.exists(GECKODRIVER_PATH):
# # # #         logging.info(f"Используется geckodriver из GECKODRIVER_PATH: {GECKODRIVER_PATH}")
# # # #         service = FirefoxService(executable_path=GECKODRIVER_PATH)
# # # #     else:
# # # #         logging.info("Используется geckodriver из системного PATH (переменная GECKODRIVER_PATH не задана или пуста).")
# # # #         service = FirefoxService() # WebDriver Manager найдет сам или используeт PATH
# # # #
# # # #     options = FirefoxOptions()
# # # #     options.add_argument("--headless")
# # # #     options.add_argument("--disable-gpu")
# # # #     options.add_argument("--window-size=1920,1080")
# # # #     options.set_preference("permissions.default.image", 2) # Отключить изображения
# # # #     options.set_preference("dom.ipc.plugins.enabled.libflashplayer.so", "false") # Отключить Flash
# # # #     options.set_preference("javascript.enabled", True) # Убедимся, что JS включен
# # # #     options.set_preference("network.cookie.cookieBehavior", 0) # Принимать все куки
# # # #     options.set_preference("network.http.connection-timeout", 30)
# # # #     options.set_preference("network.http.response.timeout", 60)
# # # #     options.set_preference("dom.max_script_run_time", 30)
# # # #
# # # #     logging.info("Попытка запуска Firefox WebDriver...")
# # # #     try:
# # # #         driver = webdriver.Firefox(service=service, options=options)
# # # #         driver.implicitly_wait(10)
# # # #         driver.set_page_load_timeout(45)
# # # #         logging.info("Настройки Selenium: используется Firefox (headless), изображения отключены.")
# # # #         logging.info("WebDriver успешно создан.")
# # # #         return driver
# # # #     except WebDriverException as e:
# # # #         logging.critical(f"КРИТИЧЕСКАЯ ОШИБКА: Не удалось создать WebDriver: {e}", exc_info=True)
# # # #         logging.critical("Убедитесь, что Firefox и geckodriver установлены и доступны.")
# # # #         if GECKODRIVER_PATH: logging.critical(f"Проверьте путь к geckodriver: {GECKODRIVER_PATH}")
# # # #         else: logging.critical("Проверьте, что geckodriver находится в системном PATH.")
# # # #         try:
# # # #             error_msg = notifications.format_error_message("WebDriver Startup", f"Не удалось создать WebDriver:\n{traceback.format_exc()}")
# # # #             notifications.send_telegram_message(error_msg, parse_mode="Markdown")
# # # #         except Exception as notify_err: logging.error(f"Не удалось отправить уведомление об ошибке WebDriver: {notify_err}")
# # # #         sys.exit(1)
# # # #     except Exception as e:
# # # #          logging.critical(f"КРИТИЧЕСКАЯ НЕПРЕДВИДЕННАЯ ОШИБКА при создании WebDriver: {e}", exc_info=True)
# # # #          sys.exit(1)
# # # #
# # # #
# # # # def parse_player_data(driver, player_name, player_url):
# # # #     """Парсит данные игрока (цена, ордера, время обновления) с его страницы."""
# # # #     logging.info(f"Парсим {player_name} (URL: {player_url})")
# # # #     data = {'price': None, 'change': 'N/A', 'min_order': None, 'max_order': None, 'refresh_time': 'N/A', 'error': None}
# # # #     try:
# # # #         driver.get(player_url)
# # # #         wait = WebDriverWait(driver, 20)
# # # #
# # # #         # 1. Цена
# # # #         price_element = wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, "div.price")))
# # # #         price_str = price_element.text.strip()
# # # #         logging.debug(f"Raw price text: '{price_str}'")
# # # #         price_cleaned = price_str.replace('FC Points', '').replace('FP', '').replace(',', '').replace(' ', '').strip()
# # # #         if price_cleaned.isdigit(): data['price'] = int(price_cleaned)
# # # #         else: logging.warning(f"Не удалось распознать цену для {player_name} из '{price_str}' -> '{price_cleaned}'"); data['error'] = "Цена не распознана"
# # # #
# # # #         # Остановка загрузки
# # # #         try: driver.execute_script("window.stop();"); logging.debug(f"window.stop() выполнен для {player_name}")
# # # #         except Exception as e_stop: logging.warning(f"Не удалось выполнить window.stop() для {player_name}: {e_stop}")
# # # #
# # # #         # 2. Изменение цены
# # # #         try: change_element = driver.find_element(By.CSS_SELECTOR, "span.price-change"); data['change'] = change_element.text.strip()
# # # #         except NoSuchElementException: logging.debug(f"Изменение цены не найдено для {player_name}"); data['change'] = '0%'
# # # #
# # # #         # 3. Время обновления
# # # #         try:
# # # #             refresh_block = wait.until(EC.presence_of_element_located((By.XPATH, "//div[contains(text(), 'updated') or contains(text(), 'обновлено') or contains(text(), 'in ') or contains(text(), 'через ')]")))
# # # #             refresh_element = refresh_block.find_element(By.XPATH, ".//span")
# # # #             data['refresh_time'] = refresh_element.text.strip()
# # # #         except (NoSuchElementException, TimeoutException, StaleElementReferenceException):
# # # #             logging.warning(f"Время обновления не найдено для {player_name}")
# # # #             if data['error'] is None: data['error'] = "Время обновления не найдено"
# # # #
# # # #         # 4. Ордера (min/max)
# # # #         try:
# # # #             orders_block = driver.find_element(By.CSS_SELECTOR, "div.price-orders")
# # # #             orders_text = orders_block.text.lower()
# # # #             logging.debug(f"Raw orders text: '{orders_block.text}'")
# # # #             min_match = re.search(r'(min|мин).*?([\d,\s]+)', orders_text)
# # # #             max_match = re.search(r'(max|макс).*?([\d,\s]+)', orders_text)
# # # #             if min_match:
# # # #                 min_order_str = min_match.group(2).replace(',', '').replace(' ', '').strip()
# # # #                 if min_order_str.isdigit(): data['min_order'] = int(min_order_str)
# # # #                 else: logging.warning(f"Не удалось распознать min_order из '{min_match.group(2)}' для {player_name}")
# # # #             else: logging.debug(f"Min order не найден для {player_name}")
# # # #             if max_match:
# # # #                 max_order_str = max_match.group(2).replace(',', '').replace(' ', '').strip()
# # # #                 if max_order_str.isdigit(): data['max_order'] = int(max_order_str)
# # # #                 else: logging.warning(f"Не удалось распознать max_order из '{max_match.group(2)}' для {player_name}")
# # # #             else: logging.debug(f"Max order не найден для {player_name}")
# # # #         except NoSuchElementException:
# # # #             logging.warning(f"Блок ордеров не найден для {player_name}")
# # # #             if data['error'] is None: data['error'] = "Ордера не найдены"
# # # #         except Exception as e_ord:
# # # #              logging.error(f"Ошибка парсинга ордеров для {player_name}: {e_ord}")
# # # #              if data['error'] is None: data['error'] = "Ошибка парсинга ордеров"
# # # #
# # # #         if data['price'] is not None:
# # # #              # Используем storage.format_price, если он доступен
# # # #              price_f = storage.format_price(data['price']) if hasattr(storage, 'format_price') else data['price']
# # # #              min_f = storage.format_price(data['min_order']) if hasattr(storage, 'format_price') else data['min_order']
# # # #              max_f = storage.format_price(data['max_order']) if hasattr(storage, 'format_price') else data['max_order']
# # # #              logging.info(f"Успешно {player_name}: Цена={price_f}  Изм='{data['change']}'  Мин={min_f}  Макс={max_f}  Обн='{data['refresh_time']}'")
# # # #              data['error'] = None
# # # #         else:
# # # #              logging.error(f"Не удалось получить цену для {player_name}. Ошибка: {data.get('error', 'Неизвестная ошибка')}")
# # # #
# # # #     except TimeoutException:
# # # #         logging.error(f"Таймаут загрузки страницы или элемента для {player_name} ({player_url})")
# # # #         data['error'] = "Таймаут загрузки"
# # # #     except WebDriverException as e:
# # # #         logging.error(f"Ошибка WebDriver при парсинге {player_name}: {e}")
# # # #         data['error'] = f"Ошибка WebDriver: {type(e).__name__}"
# # # #     except Exception as e:
# # # #         logging.error(f"Непредвиденная ошибка при парсинге {player_name}: {e}", exc_info=True)
# # # #         data['error'] = f"Непредвиденная ошибка: {type(e).__name__}"
# # # #
# # # #     return data
# # # #
# # # # def parse_refresh_time(refresh_string):
# # # #     """Парсит строку времени обновления и возвращает timedelta."""
# # # #     refresh_string = refresh_string.lower()
# # # #     minutes = 0
# # # #     hours = 0
# # # #     if 'now' in refresh_string or 'сейчас' in refresh_string: return timedelta(seconds=10)
# # # #     if 'soon' in refresh_string: return timedelta(minutes=1)
# # # #     hour_match = re.search(r'(\d+)\s*(h|ч)', refresh_string)
# # # #     if hour_match:
# # # #         try: hours = int(hour_match.group(1))
# # # #         except ValueError: pass
# # # #     minute_match = re.search(r'(\d+)\s*(m|м)', refresh_string)
# # # #     if minute_match:
# # # #         try: minutes = int(minute_match.group(1))
# # # #         except ValueError: pass
# # # #     if hours == 0 and minutes == 0: logging.warning(f"Не удалось распознать время из '{refresh_string}'. Установка интервала 15 мин."); return timedelta(minutes=15)
# # # #     return timedelta(hours=hours, minutes=minutes + 1)
# # # #
# # # # # --- Основная логика ---
# # # #
# # # # def fetch_all_players(players_config):
# # # #     """Основной цикл обхода игроков. Создает WebDriver для каждого игрока."""
# # # #     global PLAYER_UPDATE_INTERVAL, LAST_KNOWN_PRICE
# # # #     player_list = list(players_config.keys())
# # # #     logging.info(f"Игроки для парсинга ({len(player_list)}): {', '.join(player_list)}")
# # # #
# # # #     if not player_list:
# # # #         logging.warning("Список игроков пуст. Завершение работы.")
# # # #         return
# # # #
# # # #     i = 0
# # # #     while True: # Бесконечный цикл (останавливается по Ctrl+C или ошибке)
# # # #         # Проверка задач планировщика в начале итерации
# # # #         schedule.run_pending()
# # # #
# # # #         player_name = player_list[i % len(player_list)]
# # # #         player_info = players_config[player_name]
# # # #         player_url = player_info.get("url")
# # # #
# # # #         if not player_url:
# # # #             logging.warning(f"URL не найден для игрока {player_name}. Пропуск.")
# # # #             i += 1
# # # #             continue
# # # #
# # # #         now = datetime.now(timezone.utc)
# # # #         next_update_time = PLAYER_UPDATE_INTERVAL.get(player_name)
# # # #
# # # #         if next_update_time and now < next_update_time:
# # # #             # logging.debug(f"Пропуск {player_name}, следующее обновление в {next_update_time.strftime('%H:%M:%S')}")
# # # #             i += 1
# # # #             time.sleep(0.1) # Небольшая пауза, чтобы не загружать CPU
# # # #             continue
# # # #
# # # #         # --- Создание WebDriver для текущего игрока ---
# # # #         driver = None
# # # #         try:
# # # #             driver = create_webdriver()
# # # #             if driver is None:
# # # #                  logging.critical(f"Не удалось создать WebDriver для {player_name}, пропуск итерации.")
# # # #                  PLAYER_UPDATE_INTERVAL[player_name] = now + timedelta(minutes=30) # Пробуем значительно позже
# # # #                  i += 1
# # # #                  continue # Переходим к следующему игроку
# # # #
# # # #             # --- Обработка одного игрока ---
# # # #             player_data = parse_player_data(driver, player_name, player_url)
# # # #
# # # #             if player_data.get('error'):
# # # #                 logging.warning(f"Ошибка парсинга для {player_name}: {player_data['error']}. Повторная попытка через 5 минут.")
# # # #                 PLAYER_UPDATE_INTERVAL[player_name] = now + timedelta(minutes=5)
# # # #                 try:
# # # #                     error_msg = notifications.format_error_message(player_name, player_data['error'])
# # # #                     notifications.send_telegram_message(error_msg, parse_mode="Markdown")
# # # #                 except Exception as notify_err: logging.error(f"Не удалось отправить уведомление об ошибке парсинга для {player_name}: {notify_err}")
# # # #
# # # #             elif player_data.get('price') is not None:
# # # #                 current_price = player_data['price']
# # # #                 last_price = LAST_KNOWN_PRICE.get(player_name)
# # # #                 price_changed = (last_price is None or current_price != last_price)
# # # #                 is_significant_jump = False
# # # #                 if last_price is not None and last_price > 0:
# # # #                      price_diff_percent = abs(current_price - last_price) / last_price * 100
# # # #                      if price_diff_percent >= config.PRICE_JUMP_THRESHOLD:
# # # #                           is_significant_jump = True
# # # #                           price_f_last = storage.format_price(last_price) if hasattr(storage, 'format_price') else last_price
# # # #                           price_f_curr = storage.format_price(current_price) if hasattr(storage, 'format_price') else current_price
# # # #                           logging.warning(f"Обнаружен скачок цены для {player_name}! {price_f_last} -> {price_f_curr} ({price_diff_percent:.1f}%)")
# # # #
# # # #                 try:
# # # #                     timestamp = datetime.now(timezone.utc)
# # # #                     # Передаем словарь player_data целиком в save_data
# # # #                     storage.save_data(player_name, timestamp, player_data)
# # # #                 except Exception as e_save: logging.error(f"Ошибка сохранения данных для {player_name}: {e_save}", exc_info=True)
# # # #
# # # #                 LAST_KNOWN_PRICE[player_name] = current_price
# # # #
# # # #                 try:
# # # #                     # Загружаем историю цен из storage (ожидаем список словарей)
# # # #                     hist_prices_dicts = storage.get_historical_data(player_name, days=config.HISTORY_DAYS_FOR_SIGNALS)
# # # #                     # Преобразуем в список цен, сохраняя None где нужно
# # # #                     valid_hist_prices = [p.get('price') for p in hist_prices_dicts]
# # # #
# # # #                     # Формируем входные данные для signals.check_signals: список цен + словарь с последними данными
# # # #                     current_data_point = {
# # # #                         'price': current_price,
# # # #                         'change': player_data.get('change', 'N/A'),
# # # #                         'min_order': player_data.get('min_order'),
# # # #                         'max_order': player_data.get('max_order'),
# # # #                         'refresh_time': player_data.get('refresh_time', 'N/A')
# # # #                     }
# # # #                     # Передаем historical_prices + current_data_point
# # # #                     input_for_signals = valid_hist_prices + [current_data_point]
# # # #
# # # #                     logging.debug(f"Расчет сигналов для {player_name} ({len(valid_hist_prices)} исторических цен)")
# # # #                     sig_data = signals.check_signals(player_name, input_for_signals) # Передаем список цен+словарь
# # # #
# # # #                     try:
# # # #                         if sig_data:
# # # #                             # Уведомление будет использовать данные из sig_data
# # # #                             notifications.send_combined_notification(player_name, sig_data) # ИСПРАВЛЕНО v7.1
# # # #                         else:
# # # #                             logging.warning(f"Словарь sig_data пуст для {player_name}, уведомление не отправлено.")
# # # #                     except Exception as e_notify:
# # # #                         logging.error(f"Ошибка отправки уведомления для {player_name}: {e_notify}", exc_info=True)
# # # #                         error_details = traceback.format_exc()
# # # #                         notifications.send_telegram_message(
# # # #                             notifications.format_error_message(player_name, f"Ошибка отправки уведомления:\n{error_details}"),
# # # #                             parse_mode="Markdown"
# # # #                         )
# # # #
# # # #                 except Exception as e_signal:
# # # #                      logging.error(f"Ошибка расчета сигналов для {player_name}: {e_signal}", exc_info=True)
# # # #                      error_details = traceback.format_exc()
# # # #                      notifications.send_telegram_message(
# # # #                          notifications.format_error_message(player_name, f"Ошибка расчета сигналов:\n{error_details}"),
# # # #                          parse_mode="Markdown"
# # # #                      )
# # # #
# # # #                 refresh_interval = parse_refresh_time(player_data.get('refresh_time', ''))
# # # #                 actual_interval_seconds = max(refresh_interval.total_seconds(), config.MIN_INTERVAL_SECONDS)
# # # #                 next_update_time = now + timedelta(seconds=actual_interval_seconds)
# # # #                 PLAYER_UPDATE_INTERVAL[player_name] = next_update_time
# # # #                 logging.debug(f"Следующее обновление ({player_data.get('refresh_time', '')} -> {timedelta(seconds=actual_interval_seconds)}) для игрока в: {next_update_time.strftime('%Y-%m-%d %H:%M:%S %Z')}")
# # # #
# # # #         finally:
# # # #              # Закрываем WebDriver ПОСЛЕ обработки одного игрока
# # # #              if driver:
# # # #                  try:
# # # #                      driver.quit()
# # # #                      logging.debug(f"WebDriver для {player_name} закрыт.")
# # # #                  except Exception as e_quit:
# # # #                      logging.error(f"Ошибка при закрытии WebDriver для {player_name}: {e_quit}")
# # # #
# # # #         # Пауза между игроками
# # # #         logging.debug(f"Пауза {config.PAUSE_BETWEEN_PLAYERS} сек перед следующим игроком...")
# # # #         time.sleep(config.PAUSE_BETWEEN_PLAYERS)
# # # #         i += 1
# # # #
# # # #
# # # # # --- Ежедневные и еженедельные задачи ---
# # # # def run_daily_tasks():
# # # #     """Запускает ежедневные задачи."""
# # # #     logging.info("--- Запуск ежедневных задач ---")
# # # #     try:
# # # #         logging.info("Генерация OHLC...")
# # # #         ohlc_generator.generate_ohlc_report(days=2)
# # # #         logging.info("Генерация OHLC завершена.")
# # # #     except Exception as e:
# # # #         logging.error(f"Ошибка генерации OHLC: {e}", exc_info=True)
# # # #         notifications.send_telegram_message(
# # # #             notifications.format_error_message("Daily Tasks", f"Ошибка генерации OHLC:\n{traceback.format_exc()}"),
# # # #             parse_mode="Markdown"
# # # #         )
# # # #     logging.info("--- Ежедневные задачи завершены ---")
# # # #
# # # # def run_weekly_tasks():
# # # #     """Запускает еженедельные задачи."""
# # # #     logging.info("--- Запуск еженедельных задач ---")
# # # #     try:
# # # #         logging.info("Генерация недельной статистики...")
# # # #         weekly_stats.generate_weekly_stats_report()
# # # #         logging.info("Генерация недельной статистики завершена.")
# # # #     except Exception as e:
# # # #         logging.error(f"Ошибка генерации недельной статистики: {e}", exc_info=True)
# # # #         notifications.send_telegram_message(
# # # #             notifications.format_error_message("Weekly Tasks", f"Ошибка генерации недельной статистики:\n{traceback.format_exc()}"),
# # # #             parse_mode="Markdown"
# # # #         )
# # # #     try:
# # # #         logging.info("Проверка необходимости переобучения моделей...")
# # # #         # Проверяем, существует ли функция перед вызовом
# # # #         if hasattr(model_trainer, 'train_models_if_needed'):
# # # #             model_trainer.train_models_if_needed(force_train=False)
# # # #         else:
# # # #              logging.error("Функция 'train_models_if_needed' не найдена в model_trainer. Пропуск обучения.")
# # # #              notifications.send_telegram_message(
# # # #                 notifications.format_error_message("Weekly Tasks", f"Ошибка обучения: функция train_models_if_needed не найдена."),
# # # #                 parse_mode="Markdown"
# # # #              )
# # # #     except Exception as e:
# # # #         logging.error(f"Ошибка при проверке/обучении моделей: {e}", exc_info=True)
# # # #         notifications.send_telegram_message(
# # # #             notifications.format_error_message("Weekly Tasks", f"Ошибка обучения моделей:\n{traceback.format_exc()}"),
# # # #             parse_mode="Markdown"
# # # #         )
# # # #     logging.info("--- Еженедельные задачи завершены ---")
# # # #
# # # #
# # # # def main():
# # # #     """Основная функция запуска парсера и планировщика."""
# # # #     logging.info("[scraper] Старт парсера RenderZ.")
# # # #     notifications.send_startup_notification()
# # # #
# # # #     # --- Планирование Задач ---
# # # #     schedule.every().day.at("09:00", "UTC").do(run_daily_tasks).tag('daily')
# # # #     logging.info(f"Ежедневная задача запланирована. Ближайший запуск: {schedule.next_run.strftime('%Y-%m-%d %H:%M:%S %Z') if schedule.next_run else 'N/A'}.") # Исправлено получение next_run
# # # #     schedule.every().sunday.at("10:00", "UTC").do(run_weekly_tasks).tag('weekly')
# # # #     logging.info(f"Еженедельная задача запланирована. Ближайший запуск: {schedule.next_run.strftime('%Y-%m-%d %H:%M:%S %Z') if schedule.next_run else 'N/A'}.")
# # # #
# # # #     # Проверка необходимости обучения при старте
# # # #     try:
# # # #         if hasattr(model_trainer, 'train_models_if_needed'):
# # # #             model_trainer.train_models_if_needed(force_train=False)
# # # #         else:
# # # #              logging.error("Функция 'train_models_if_needed' не найдена в model_trainer. Пропуск стартового обучения.")
# # # #     except Exception as e:
# # # #          logging.error(f"Ошибка при стартовой проверке/обучении моделей: {e}", exc_info=True)
# # # #
# # # #
# # # #     # --- Загрузка начальных данных ---
# # # #     logging.info("Загрузка конфигурации игроков...")
# # # #     players = config.load_players()
# # # #     if not players:
# # # #         logging.critical("Не удалось загрузить конфигурацию игроков. Завершение работы.")
# # # #         notifications.send_telegram_message("КРИТИЧЕСКАЯ ОШИБКА: Не удалось загрузить список игроков!", parse_mode=None)
# # # #         sys.exit(1)
# # # #
# # # #     # Загрузка последних известных цен (только из CSV)
# # # #     logging.info("Загрузка последних цен из CSV...")
# # # #     for name in players.keys():
# # # #         try:
# # # #              # Проверяем наличие функции перед вызовом
# # # #             if hasattr(storage, 'get_last_known_price'):
# # # #                 price = storage.get_last_known_price(name)
# # # #                 if price is not None:
# # # #                     LAST_KNOWN_PRICE[name] = price
# # # #                     price_f = storage.format_price(price) if hasattr(storage, 'format_price') else price
# # # #                     logging.info(f"Загружена последняя известная цена для {name}: {price_f}")
# # # #                 else:
# # # #                      logging.warning(f"Не найдена последняя цена для {name} при старте.")
# # # #             else:
# # # #                 logging.error("Функция 'get_last_known_price' не найдена в storage. Пропуск загрузки последней цены.")
# # # #                 break # Прерываем цикл, т.к. функция отсутствует для всех
# # # #         except Exception as e_price:
# # # #              logging.error(f"Ошибка загрузки последней цены для {name}: {e_price}")
# # # #
# # # #
# # # #     # --- Основной Цикл ---
# # # #     try:
# # # #         logging.info("Запуск основного цикла парсинга...")
# # # #         fetch_all_players(players) # WebDriver создается внутри цикла для каждого игрока
# # # #
# # # #     except KeyboardInterrupt:
# # # #         logging.info("Обработка Ctrl+C...")
# # # #     except Exception as e:
# # # #         logging.critical(f"КРИТИЧЕСКАЯ ОШИБКА в основном цикле: {e}", exc_info=True)
# # # #         try:
# # # #             error_msg = notifications.format_error_message("Main Loop CRITICAL", f"Критическая ошибка:\n{traceback.format_exc()}")
# # # #             notifications.send_telegram_message(error_msg, parse_mode="Markdown")
# # # #         except Exception as notify_err:
# # # #             logging.error(f"Не удалось отправить уведомление о критической ошибке: {notify_err}")
# # # #     finally:
# # # #         logging.info("Начало процедуры завершения работы...")
# # # #         notifications.send_shutdown_notification()
# # # #         logging.info("Парсер RenderZ окончательно остановлен.")
# # # #         schedule.clear()
# # # #         sys.exit(0)
# # # #
# # # # if __name__ == "__main__":
# # # #     main()
# # #
# # # # =============================================
# # # # ФАЙЛ: scraper.py (ВЕРСИЯ v7.4.0 - Непрерывный пересчет и ожидание ближайшего)
# # # # - ОСНОВА: Версия 7.2.4 (возвращаем правильный driver из fetch_all_players)
# # # # - ИЗМЕНЕНО: Логика fetch_all_players полностью переписана.
# # # #             Теперь скрипт находит ближайшего игрока, ждет его,
# # # #             обрабатывает, и СРАЗУ ищет следующего ближайшего.
# # # # - ИЗМЕНЕНО: Логгирование адаптировано под новый цикл ожидания.
# # # # =============================================
# # #
# # # import logging
# # # import schedule
# # # import time
# # # import json
# # # import os
# # # import sys
# # # from datetime import datetime, timedelta, timezone
# # # import traceback
# # # import re
# # # import subprocess
# # # from selenium import webdriver
# # # from selenium.webdriver.firefox.service import Service as FirefoxService
# # # from selenium.webdriver.firefox.options import Options as FirefoxOptions
# # # from selenium.common.exceptions import (WebDriverException, TimeoutException,
# # #                                         NoSuchElementException, StaleElementReferenceException)
# # # from selenium.webdriver.common.by import By
# # # from selenium.webdriver.support.ui import WebDriverWait
# # # from selenium.webdriver.support import expected_conditions as EC
# # # import pandas as pd
# # # import threading
# # #
# # # # --- Импорт пользовательских модулей ---
# # # try:
# # #     import config
# # #     import storage      # Ожидается v6.7+
# # #     import signals      # Ожидается v23.10+
# # #     import notifications # Ожидается v10.7+
# # #     import cycle_analysis # Ожидается v8.3+
# # #     import ohlc_generator
# # #     import model_trainer
# # #     import weekly_stats
# # #     import evaluate_model
# # #     import events_manager
# # # except ImportError as e:
# # #     log_func = logging.critical if logging.getLogger().hasHandlers() else print
# # #     log_func(f"Ошибка импорта модуля: {e}.")
# # #     sys.exit(1)
# # #
# # # # --- Настройка Логирования ---
# # # LOG_DIR = getattr(config, 'LOG_DIR', 'logs')
# # # os.makedirs(LOG_DIR, exist_ok=True)
# # # log_filename = os.path.join(LOG_DIR, f"scraper_{datetime.now().strftime('%Y-%m-%d')}.log")
# # # log_level_str = getattr(config, 'LOG_LEVEL', 'INFO').upper()
# # # log_level = getattr(logging, log_level_str, logging.INFO)
# # # logging.basicConfig(
# # #     level=log_level,
# # #     format='%(asctime)s - %(levelname)s - [%(name)s] - [%(filename)s:%(lineno)d] - %(message)s',
# # #     handlers=[
# # #         logging.StreamHandler(sys.stdout),
# # #         logging.FileHandler(log_filename, encoding='utf-8')
# # #     ]
# # # )
# # # logger = logging.getLogger("scraper")
# # # logger.setLevel(log_level)
# # #
# # # logging.getLogger("urllib3").setLevel(logging.WARNING)
# # # logging.getLogger("selenium").setLevel(logging.INFO)
# # # logging.getLogger("schedule").setLevel(logging.INFO)
# # # logger.info(f"Логгер инициализирован с уровнем: {log_level_str}")
# # #
# # #
# # # # --- Проверка наличия необходимых функций ---
# # # required = [
# # #     (notifications, 'send_combined_notification'),(notifications, 'format_error_message'),
# # #     (notifications, 'send_telegram_message'),(signals,'check_signals'),
# # #     (storage,'log_player_data'),(storage,'read_player_history'),
# # #     (storage,'get_last_known_price'),(config,'load_players'),
# # #     (cycle_analysis, 'determine_main_cycle_phase_df'),
# # #     (cycle_analysis, 'determine_short_cycle_phase_df'),
# # #     (ohlc_generator,'rewrite_ohlc_summary' if hasattr(ohlc_generator,'rewrite_ohlc_summary') else 'generate_ohlc_report'),
# # #     (weekly_stats, 'generate_weekly_stats_report')
# # # ]
# # # missing_found = False
# # # for module, func_name in required:
# # #     if not hasattr(module, func_name):
# # #         logger.critical(f"Нет {module.__name__}.{func_name}! Проверьте версию файла. Выход.")
# # #         missing_found = True
# # # if missing_found: sys.exit(1)
# # #
# # #
# # # # --- Глобальные переменные ---
# # # PLAYER_UPDATE_INTERVAL = {}
# # # LAST_KNOWN_PRICE      = {}
# # # GECKODRIVER_PATH      = os.environ.get('GECKODRIVER_PATH', None)
# # # MIN_HISTORY_FOR_SIGNALS = getattr(config, 'MIN_HISTORY_FOR_SIGNALS', 30)
# # # REFRESH_BUFFER_SECONDS = 5
# # #
# # # # --- Функции WebDriver ---
# # # # (Функция create_webdriver без изменений от v7.2.1)
# # # def create_webdriver():
# # #     logger.debug("Попытка создания экземпляра WebDriver...")
# # #     service = None
# # #     driver = None
# # #     try:
# # #         service_args = []
# # #         service_args.extend(['--log', 'fatal'])
# # #         log_path = os.path.join(LOG_DIR, "geckodriver.log") if LOG_DIR else "geckodriver.log"
# # #         executable_path = None
# # #         if GECKODRIVER_PATH and os.path.exists(GECKODRIVER_PATH):
# # #             executable_path = GECKODRIVER_PATH
# # #             logger.info(f"Используется geckodriver из GECKODRIVER_PATH: {executable_path}")
# # #         else:
# # #             from shutil import which
# # #             found_path = which('geckodriver')
# # #             if found_path:
# # #                  executable_path = found_path
# # #                  logger.info(f"Используется geckodriver из PATH: {executable_path}")
# # #             else:
# # #                  logger.error("geckodriver не найден!")
# # #                  try:
# # #                      notify_msg = notifications.format_error_message("WebDriver Init Error", "geckodriver не найден")
# # #                      notifications.send_telegram_message(notify_msg, parse_mode=None)
# # #                  except Exception: pass
# # #                  return None
# # #         service = FirefoxService(executable_path=executable_path, service_args=service_args, log_path=log_path)
# # #         logger.debug(f"FirefoxService создан.")
# # #     except Exception as e_service:
# # #          logger.critical(f"Ошибка FirefoxService: {e_service}", exc_info=True)
# # #          try:
# # #              notify_msg = notifications.format_error_message("WebDriver Service Init", traceback.format_exc())
# # #              notifications.send_telegram_message(notify_msg, parse_mode=None)
# # #          except Exception: pass
# # #          return None
# # #
# # #     options = FirefoxOptions(); options.add_argument("--headless"); options.add_argument("--disable-gpu"); options.add_argument("--window-size=1920,1080"); options.add_argument("--no-sandbox"); options.add_argument("--disable-dev-shm-usage")
# # #     options.set_preference("permissions.default.image", 2); options.set_preference("dom.ipc.plugins.enabled.libflashplayer.so", "false"); options.set_preference("javascript.enabled", True); options.set_preference("network.cookie.cookieBehavior", 0)
# # #     options.set_preference("network.http.connection-timeout", 90); options.set_preference("network.http.response.timeout", 120); options.set_preference("dom.max_script_run_time", 90)
# # #     options.set_preference("dom.webdriver.enabled", False); options.set_preference('useAutomationExtension', False)
# # #     options.set_preference("general.useragent.override", "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/115.0")
# # #
# # #     logger.info("Попытка запуска Firefox WebDriver...")
# # #     try:
# # #         if service is None: logger.error("Service не инициализирован."); return None
# # #         driver = webdriver.Firefox(service=service, options=options)
# # #         driver.implicitly_wait(20); driver.set_page_load_timeout(90)
# # #         driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
# # #         logger.info("WebDriver успешно создан и настроен.")
# # #         return driver
# # #     except WebDriverException as e:
# # #         error_message = f"КРИТ. ОШИБКА WebDriverException: {e}\n{traceback.format_exc()}"
# # #         logger.critical(error_message, exc_info=False)
# # #         try:
# # #             notify_msg = f"‼️ Ошибка WebDriver Startup ‼️\n\n{error_message}"
# # #             notifications.send_telegram_message(notify_msg, parse_mode=None)
# # #         except Exception: pass
# # #         return None
# # #     except Exception as e:
# # #         logger.critical(f"КРИТ. НЕПРЕДВИДЕННАЯ ОШИБКА WebDriver: {e}", exc_info=True)
# # #         try:
# # #             notify_msg = notifications.format_error_message("WebDriver Unexpected Startup", traceback.format_exc())
# # #             notifications.send_telegram_message(notify_msg, parse_mode=None)
# # #         except Exception: pass
# # #         return None
# # #
# # # # (Функция parse_player_data без изменений от v7.2.3)
# # # def parse_player_data(driver, player_name, player_url):
# # #     """Парсит данные игрока с XPath из v7."""
# # #     logger.info(f"Парсим {player_name} (URL: {player_url})")
# # #     price_xpath = "//div[contains(@class, 'market-data--key') and normalize-space(.)='Current value']/ancestor::div[contains(@class, 'flex-col')][2]//div[contains(@class, 'market-data--value')][1]/span[1]"
# # #     change_xpath = "//div[contains(@class, 'market-data--value--change')]//span[contains(text(), '%')]"
# # #     update_xpath = "//div[contains(text(), 'Market Refresh')]/following-sibling::div[contains(@class, 'market-data--value-mini')]"
# # #     min_xpath = "//div[contains(text(), 'Market low/high')]/following-sibling::div[contains(@class, 'market-data--value-mini')]//span[1]"
# # #     max_xpath = "//div[contains(text(), 'Market low/high')]/following-sibling::div[contains(@class, 'market-data--value-mini')]//span[last()]"
# # #
# # #     data = {'timestamp': None, 'price': None, 'change': 'N/A', 'min_order': None, 'max_order': None, 'update_time': 'N/A', 'error': None}
# # #     html_dump_path = os.path.join(LOG_DIR, f"error_{player_name.replace(' ','_')}_{datetime.now().strftime('%H%M%S')}.html")
# # #
# # #     wait_long = WebDriverWait(driver, 25)
# # #     wait_short = WebDriverWait(driver, 10)
# # #
# # #     try:
# # #         start_get = time.time()
# # #         logger.debug(f"Загрузка URL: {player_url}")
# # #         driver.get(player_url)
# # #         load_time = time.time() - start_get
# # #         logger.debug(f"URL загружен за {load_time:.2f} сек.")
# # #         time.sleep(1.5)
# # #
# # #         start_find_price = time.time()
# # #         price = None; raw_price_text = "N/A"
# # #         try:
# # #             price_element = wait_long.until(EC.visibility_of_element_located((By.XPATH, price_xpath)))
# # #             find_price_time = time.time() - start_find_price
# # #             logger.debug(f"Элемент цены найден за {find_price_time:.2f} сек.")
# # #             raw_price_text = price_element.text.strip()
# # #             logger.debug(f"Raw price: '{raw_price_text}'")
# # #             cleaned = re.sub(r'[^\d]', '', raw_price_text)
# # #             price = int(cleaned) if cleaned.isdigit() else None
# # #             if price is None and raw_price_text not in ["", "-"]: logger.warning(f"{player_name}: Не удалось распарсить цену '{raw_price_text}' в число.")
# # #             elif price == 0 and raw_price_text != '0': logger.warning(f"{player_name} price 0, text: '{raw_price_text}'.")
# # #             data['price'] = price; data['low'] = price; data['high'] = price
# # #         except TimeoutException: data['error'] = "Таймаут ожидания цены"; logger.error(f"{data['error']} ({time.time() - start_find_price:.1f}s) для {player_name}"); return data
# # #         except NoSuchElementException: data['error'] = "Элемент цены не найден"; logger.error(f"{data['error']} для {player_name} (XPath: {price_xpath})"); return data
# # #         except Exception as e: data['error'] = f"Ошибка парсинга цены: {type(e).__name__}"; logger.error(f"{data['error']} для {player_name}: {e}", exc_info=True); return data
# # #
# # #         parsing_times = {}
# # #         start_other = time.time()
# # #         try: data['change'] = wait_short.until(EC.visibility_of_element_located((By.XPATH, change_xpath))).text.strip(); parsing_times['change'] = time.time() - start_other
# # #         except (TimeoutException, NoSuchElementException, StaleElementReferenceException): data['change'] = "0%"; parsing_times['change'] = time.time() - start_other; logger.debug(f"Изменение цены не найдено/устарело для {player_name}")
# # #         except Exception as e: data['change'] = "N/A"; parsing_times['change'] = time.time() - start_other; logger.warning(f"Ошибка парсинга изменения цены: {e}")
# # #
# # #         start_other = time.time()
# # #         try: data['update_time'] = wait_short.until(EC.visibility_of_element_located((By.XPATH, update_xpath))).text.strip(); parsing_times['update'] = time.time() - start_other
# # #         except (TimeoutException, NoSuchElementException, StaleElementReferenceException): data['update_time'] = "N/A"; parsing_times['update'] = time.time() - start_other; logger.warning(f"Время обновления не найдено/устарело для {player_name}")
# # #         except Exception as e: data['update_time'] = "N/A"; parsing_times['update'] = time.time() - start_other; logger.warning(f"Ошибка парсинга времени обновления: {e}")
# # #
# # #         min_val, max_val = None, None
# # #         start_other = time.time()
# # #         try:
# # #             min_raw = wait_short.until(EC.visibility_of_element_located((By.XPATH, min_xpath))).text.strip(); min_clean = re.sub(r'[^\d]', '', min_raw)
# # #             min_val = int(min_clean) if min_clean.isdigit() else None; data['min_order'] = min_val
# # #             if min_val is not None: data['low'] = min_val
# # #         except (TimeoutException, NoSuchElementException, StaleElementReferenceException): logger.debug(f"Min цена не найдена/устарела для {player_name}")
# # #         except Exception as e: logger.warning(f"Ошибка парсинга Min цены: {e}")
# # #         parsing_times['min'] = time.time() - start_other
# # #
# # #         start_other = time.time()
# # #         try:
# # #             max_raw = wait_short.until(EC.visibility_of_element_located((By.XPATH, max_xpath))).text.strip(); max_clean = re.sub(r'[^\d]', '', max_raw)
# # #             max_val = int(max_clean) if max_clean.isdigit() else None; data['max_order'] = max_val
# # #             if max_val is not None: data['high'] = max_val
# # #         except (TimeoutException, NoSuchElementException, StaleElementReferenceException): logging.debug(f"Max цена не найдена/устарела для {player_name}")
# # #         except Exception as e: logging.warning(f"Ошибка парсинга Max цены: {e}")
# # #         parsing_times['max'] = time.time() - start_other
# # #
# # #         logger.debug(f"Время парсинга доп. элементов: {parsing_times}")
# # #         min_f = storage.format_price(min_val) if min_val is not None else "N/A"; max_f = storage.format_price(max_val) if max_val is not None else "N/A"
# # #         data['orders'] = f"Min: {min_f} / Max: {max_f}"
# # #         data['timestamp'] = datetime.now(timezone.utc).isoformat()
# # #         data['error'] = None
# # #         price_f = storage.format_price(data['price'])
# # #         logger.info(f"Успешно {player_name}: Цена={price_f} Изм='{data['change']}' Ордера='{data['orders']}' Обн='{data['update_time']}'")
# # #         return data
# # #     except WebDriverException as e_wd:
# # #          logger.error(f"WebDriverException ВНУТРИ parse_player_data для {player_name}: {e_wd}")
# # #          data['error'] = f"WebDriver err in parse: {type(e_wd).__name__}"
# # #          raise e_wd
# # #     except Exception as e:
# # #         data['error'] = f"Unexpected parsing err: {type(e).__name__}"
# # #         logger.error(f"Unexpected err {player_name}: {e}", exc_info=True)
# # #         try:
# # #             if driver and hasattr(driver, 'page_source'):
# # #                 with open(html_dump_path, "w", encoding="utf-8") as f: f.write(driver.page_source)
# # #                 logger.info(f"HTML при неожиданной ошибке сохранен: {html_dump_path}")
# # #             else: logger.warning("Не удалось сохранить HTML, т.к. driver не доступен.")
# # #         except Exception as dump_err: logger.error(f"Не удалось сохранить HTML при ошибке: {dump_err}")
# # #         return data
# # #
# # # # (Функция parse_refresh_time без изменений от v7.2.3)
# # # def parse_refresh_time(refresh_string):
# # #     refresh_string = (refresh_string or "").lower(); minutes = 0; hours = 0
# # #     if 'now' in refresh_string or 'сейчас' in refresh_string: return timedelta(seconds=15)
# # #     if 'soon' in refresh_string: return timedelta(minutes=1)
# # #     hour_match = re.search(r'(\d+)\s*(h|ч)', refresh_string)
# # #     if hour_match:
# # #         try: hours = int(hour_match.group(1))
# # #         except ValueError: pass
# # #     minute_match = re.search(r'(\d+)\s*(m|м)', refresh_string)
# # #     if minute_match:
# # #         try: minutes = int(minute_match.group(1))
# # #         except ValueError: pass
# # #     default_interval_min = getattr(config, 'DEFAULT_REFRESH_INTERVAL_MINUTES', 15)
# # #     if hours == 0 and minutes == 0:
# # #         logger.warning(f"Не распознать время '{refresh_string}'. Используем интервал по умолчанию: {default_interval_min} мин.")
# # #         return timedelta(minutes=default_interval_min)
# # #     return timedelta(hours=hours, minutes=minutes)
# # #
# # #
# # # # --- НОВЫЙ Основной цикл с ожиданием ближайшего ---
# # # def fetch_all_players(players_config):
# # #     """Основной цикл: находит ближайшего игрока, ждет, обрабатывает, повторяет."""
# # #     global PLAYER_UPDATE_INTERVAL, LAST_KNOWN_PRICE
# # #     player_list = list(players_config.keys())
# # #     logger.info(f"Игроки для парсинга ({len(player_list)}): {', '.join(player_list)}")
# # #     if not player_list: logger.warning("Список игроков пуст."); return None
# # #
# # #     driver = None
# # #     processed_count = 0 # Счетчик обработанных игроков с момента запуска/перезапуска
# # #
# # #     logger.info("Инициализация основного цикла: Попытка первичного создания WebDriver...")
# # #
# # #     try:
# # #         while True:
# # #             # 1. Проверка и создание/пересоздание WebDriver
# # #             if driver is None:
# # #                 creation_start_time = time.time()
# # #                 logger.info("WebDriver не активен, попытка создания/пересоздания...")
# # #                 driver = create_webdriver()
# # #                 creation_time = time.time() - creation_start_time
# # #                 if driver is None:
# # #                     logger.critical(f"Не удалось создать/пересоздать WebDriver за {creation_time:.1f} сек. Пауза 5 минут...")
# # #                     # Запускаем schedule в пассивном режиме ожидания
# # #                     start_wait = time.time()
# # #                     while time.time() - start_wait < 300:
# # #                          schedule.run_pending()
# # #                          time.sleep(1)
# # #                     continue # Повторная попытка создания
# # #                 else:
# # #                     logger.info(f"WebDriver успешно создан/пересоздан за {creation_time:.1f} сек.")
# # #
# # #             # 2. Найти ближайшего игрока для обновления
# # #             now = datetime.now(timezone.utc)
# # #             next_player_to_update = None
# # #             min_next_update_time = None
# # #
# # #             for player_name in player_list:
# # #                 t_update = PLAYER_UPDATE_INTERVAL.get(player_name)
# # #                 if t_update is None or t_update <= now: # Если время не установлено или уже прошло
# # #                     next_player_to_update = player_name
# # #                     min_next_update_time = now # Обрабатываем немедленно
# # #                     break # Нашли первого, кого пора обновить
# # #                 elif min_next_update_time is None or t_update < min_next_update_time:
# # #                     min_next_update_time = t_update
# # #                     next_player_to_update = player_name
# # #
# # #             # Если некого обновлять (все интервалы в будущем)
# # #             if next_player_to_update is None:
# # #                 logger.warning("Не найдено игроков для обновления. Ожидание 60 сек.")
# # #                 wait_seconds = 60
# # #                 next_player_to_update = "N/A" # Просто для лога
# # #                 min_next_update_time = now + timedelta(seconds=wait_seconds)
# # #             else:
# # #                 wait_seconds = (min_next_update_time - now).total_seconds()
# # #
# # #             # 3. Ожидание (если нужно)
# # #             if wait_seconds > 0:
# # #                 wait_seconds_int = int(wait_seconds) + 1 # Ждем чуть дольше на всякий случай
# # #                 next_run_time_str = min_next_update_time.strftime('%H:%M:%S') if min_next_update_time > now else "немедленно"
# # #                 logger.info(f"Следующий игрок: {next_player_to_update} в ~{next_run_time_str}. Ожидание ~{wait_seconds_int} сек...")
# # #                 # Цикл ожидания с проверкой schedule
# # #                 wait_start = time.time()
# # #                 while time.time() - wait_start < wait_seconds_int:
# # #                     schedule.run_pending()
# # #                     time.sleep(1) # Проверяем каждую секунду
# # #
# # #             # --- Обработка выбранного игрока ---
# # #             if next_player_to_update == "N/A": continue # Если ждали 60 сек т.к. не было игроков
# # #
# # #             player_name = next_player_to_update # Берем ближайшего
# # #             player_info = players_config[player_name]
# # #             player_url = player_info.get("url")
# # #             processed_count += 1
# # #             player_processing_start_time = time.time()
# # #
# # #             if not player_url:
# # #                 logger.warning(f"URL не найден для {player_name}. Пропуск и установка интервала.")
# # #                 PLAYER_UPDATE_INTERVAL[player_name] = datetime.now(timezone.utc) + timedelta(hours=1) # Проверить через час
# # #                 continue
# # #
# # #             logger.info(f"Обработка игрока #{processed_count}: {player_name} (WebDriver активен)")
# # #
# # #             # 4. Парсинг данных
# # #             parse_start_time = time.time()
# # #             player_data = None
# # #             try:
# # #                 player_data = parse_player_data(driver, player_name, player_url)
# # #             except WebDriverException as e_wd:
# # #                 logger.error(f"WebDriverException при обработке {player_name}: {e_wd}", exc_info=True)
# # #                 try: notifications.send_telegram_message(notifications.format_error_message(player_name, f"WebDriverException:\n{traceback.format_exc()}"), parse_mode=None)
# # #                 except Exception: pass
# # #                 logger.warning("Закрытие и перезапуск WebDriver...")
# # #                 if driver:
# # #                     try: driver.quit()
# # #                     except Exception: pass
# # #                 driver = None # Сигнал для пересоздания
# # #                 PLAYER_UPDATE_INTERVAL[player_name] = datetime.now(timezone.utc) + timedelta(minutes=1) # Повторить скоро
# # #                 continue # Переходим к началу while True для пересоздания драйвера
# # #             except Exception as e_parse_other:
# # #                  logger.error(f"Неожиданная ошибка из parse_player_data для {player_name}: {e_parse_other}", exc_info=True)
# # #                  if player_data is None: player_data = {'error': f"Unexpected: {type(e_parse_other).__name__}"}
# # #                  elif 'error' not in player_data: player_data['error'] = f"Unexpected: {type(e_parse_other).__name__}"
# # #             parse_duration = time.time() - parse_start_time
# # #             logger.debug(f"[{player_name}] Парсинг завершен за {parse_duration:.2f} сек.")
# # #
# # #             # 5. Обработка результата парсинга
# # #             if player_data is None or player_data.get('error'):
# # #                 error_msg = player_data.get('error', 'parse_player_data вернул None') if player_data else 'parse_player_data вернул None'
# # #                 logger.warning(f"Ошибка парсинга для {player_name}: {error_msg}. Повтор через 5 мин.")
# # #                 PLAYER_UPDATE_INTERVAL[player_name] = datetime.now(timezone.utc) + timedelta(minutes=5)
# # #                 try: notifications.send_telegram_message(notifications.format_error_message(player_name, error_msg), parse_mode="MarkdownV2")
# # #                 except Exception: pass
# # #             elif player_data.get('price') is not None:
# # #                 # --- Успешная обработка ---
# # #                 current_price = player_data['price']
# # #                 save_start_time = time.time()
# # #                 try: storage.log_player_data(player_name, player_data); logger.debug(f"[{player_name}] Данные сохранены за {time.time() - save_start_time:.3f} сек.")
# # #                 except Exception as e_save: logger.error(f"Ошибка сохранения данных для {player_name}: {e_save}", exc_info=True)
# # #                 LAST_KNOWN_PRICE[player_name] = current_price
# # #
# # #                 analysis_start_time = time.time()
# # #                 try:
# # #                     read_start_time = time.time()
# # #                     history_df = storage.read_player_history(player_name, min_rows=MIN_HISTORY_FOR_SIGNALS)
# # #                     logger.debug(f"[{player_name}] История прочитана за {time.time() - read_start_time:.3f} сек.")
# # #                     if history_df is not None and not history_df.empty and len(history_df) >= MIN_HISTORY_FOR_SIGNALS:
# # #                         signal_calc_start_time = time.time()
# # #                         current_player_config = players_config.get(player_name, {})
# # #                         if 'name' not in current_player_config: current_player_config['name'] = player_name
# # #                         if 'ovr' not in current_player_config: current_player_config['ovr'] = player_info.get('ovr', 'N/A')
# # #                         sig_data = signals.check_signals(history_df, current_player_config)
# # #                         logger.debug(f"[{player_name}] Сигналы рассчитаны за {time.time() - signal_calc_start_time:.3f} сек.")
# # #                         if sig_data and sig_data.get('send_notification', False):
# # #                             notify_start_time = time.time()
# # #                             logger.info(f"Отправка уведомления для {player_name}...")
# # #                             notifications.send_combined_notification(current_player_config, sig_data, player_data)
# # #                             logger.debug(f"[{player_name}] Уведомление отправлено за {time.time() - notify_start_time:.3f} сек.")
# # #                         else: logger.info(f"[{player_name}] Уведомление не требуется. Score: {sig_data.get('aggregated_score', 'N/A'):.2f}")
# # #                     else: logger.warning(f"Недостаточно истории для сигналов {player_name}.")
# # #                 except Exception as e_signal:
# # #                      logger.error(f"Ошибка расчета сигналов или уведомления для {player_name}: {e_signal}", exc_info=True)
# # #                      try: notifications.send_telegram_message(notifications.format_error_message(player_name, f"Ошибка signals/notify:\n{traceback.format_exc()}"), parse_mode="MarkdownV2")
# # #                      except Exception: pass
# # #                 logger.debug(f"[{player_name}] Блок анализа занял {time.time() - analysis_start_time:.3f} сек.")
# # #
# # #                 # --- Расчет времени следующего обновления ---
# # #                 refresh_interval = parse_refresh_time(player_data.get('update_time', 'N/A'))
# # #                 buffered_interval_seconds = refresh_interval.total_seconds() + REFRESH_BUFFER_SECONDS
# # #                 min_interval_sec = getattr(config, 'MIN_INTERVAL_SECONDS', 60)
# # #                 actual_interval_seconds = max(buffered_interval_seconds, min_interval_sec)
# # #                 next_update = datetime.now(timezone.utc) + timedelta(seconds=actual_interval_seconds)
# # #                 PLAYER_UPDATE_INTERVAL[player_name] = next_update
# # #                 logger.debug(f"След. обновление для {player_name} в: {next_update:%Y-%m-%d %H:%M:%S %Z} (через ~{actual_interval_seconds:.0f}с)")
# # #             else:
# # #                 logger.error(f"Парсинг {player_name} без ошибки, но цена = None. Повтор через 15 мин.")
# # #                 PLAYER_UPDATE_INTERVAL[player_name] = datetime.now(timezone.utc) + timedelta(minutes=15)
# # #
# # #             player_processing_duration = time.time() - player_processing_start_time
# # #             logger.info(f"Завершена обработка {player_name} за {player_processing_duration:.2f} сек.")
# # #
# # #             # Пауза ПОСЛЕ обработки игрока (небольшая)
# # #             pause_duration = getattr(config, 'PAUSE_BETWEEN_PLAYERS', 1)
# # #             time.sleep(pause_duration) # Пауза перед поиском следующего ближайшего
# # #
# # #     except KeyboardInterrupt: # Перехватываем KeyboardInterrupt здесь
# # #         logger.info("Обработка Ctrl+C...")
# # #         # Возвращаем драйвер, чтобы finally в main мог его закрыть
# # #         return driver
# # #     except Exception as e_loop:
# # #         logger.critical(f"Критическая ошибка в основном цикле fetch_all_players: {e_loop}", exc_info=True)
# # #         try:
# # #              notify_msg = notifications.format_error_message("Fetch Loop CRITICAL", traceback.format_exc())
# # #              notifications.send_telegram_message(notify_msg, parse_mode="MarkdownV2")
# # #         except Exception: pass
# # #         # Возвращаем драйвер для попытки закрытия
# # #         return driver
# # #     # finally: # Убираем finally отсюда, возврат driver сделает то же самое
# # #     #     logger.info("Завершение функции fetch_all_players.")
# # #     #     return driver
# # #
# # #
# # # # --- Ежедневные и еженедельные задачи ---
# # # def run_daily_tasks():
# # #     logger.info("--- Запуск ежедневных задач ---")
# # #     try:
# # #         logger.info("Генерация OHLC...")
# # #         if hasattr(ohlc_generator, 'rewrite_ohlc_summary'): ohlc_generator.rewrite_ohlc_summary(days=2)
# # #         else: logger.error("Функция rewrite_ohlc_summary не найдена в ohlc_generator.")
# # #         logger.info("Генерация OHLC завершена.")
# # #     except Exception as e: logger.error(f"Ошибка генерации OHLC: {e}", exc_info=True); notifications.send_telegram_message(notifications.format_error_message("Daily Tasks", f"Ошибка генерации OHLC:\n{traceback.format_exc()}"), parse_mode="MarkdownV2")
# # #     logger.info("--- Ежедневные задачи завершены ---")
# # #
# # # def run_weekly_tasks():
# # #     logger.info("--- Запуск еженедельных задач ---")
# # #     try:
# # #         logger.info("Генерация недельной статистики...")
# # #         if hasattr(weekly_stats, 'generate_weekly_stats_report'): weekly_stats.generate_weekly_stats_report()
# # #         else: logger.error("Функция generate_weekly_stats_report не найдена в weekly_stats.")
# # #         logger.info("Генерация недельной статистики завершена.")
# # #     except Exception as e: logger.error(f"Ошибка генерации недельной статистики: {e}", exc_info=True); notifications.send_telegram_message(notifications.format_error_message("Weekly Tasks", f"Ошибка генерации недельной статистики:\n{traceback.format_exc()}"), parse_mode="MarkdownV2")
# # #     try:
# # #         logger.info("Проверка необходимости переобучения моделей...")
# # #         if hasattr(model_trainer, 'train_models_if_needed'): model_trainer.train_models_if_needed(force_train=False)
# # #         else: logger.error("Функция 'train_models_if_needed' не найдена в model_trainer. Пропуск обучения.")
# # #     except Exception as e: logger.error(f"Ошибка при проверке/обучении моделей: {e}", exc_info=True); notifications.send_telegram_message(notifications.format_error_message("Weekly Tasks", f"Ошибка обучения моделей:\n{traceback.format_exc()}"), parse_mode="MarkdownV2")
# # #     logger.info("--- Еженедельные задачи завершены ---")
# # #
# # #
# # # # --- Функция для запуска schedule в отдельном потоке ---
# # # def run_schedule_continuously(interval=1):
# # #     """Непрерывно запускает schedule.run_pending()."""
# # #     while True:
# # #         schedule.run_pending()
# # #         time.sleep(interval)
# # #
# # # # --- Функция main ---
# # # def main():
# # #     """Основная функция запуска парсера и планировщика."""
# # #     main_driver = None
# # #     try:
# # #         logger.info("[scraper] Старт парсера RenderZ."); notifications.send_startup_notification()
# # #         # Планирование задач
# # #         daily_time_str=getattr(config, 'DAILY_REPORT_TIME', "09:00"); weekly_day_str=getattr(config, 'WEEKLY_REPORT_DAY', "sunday"); weekly_time_str=getattr(config, 'WEEKLY_REPORT_TIME', "10:00"); report_timezone_str=getattr(config, 'REPORT_TIMEZONE', "UTC")
# # #         logger.info(f"План. ежедневной задачи на {daily_time_str} {report_timezone_str}"); schedule.every().day.at(daily_time_str, report_timezone_str).do(run_daily_tasks).tag('daily')
# # #         logger.info(f"План. еженедельной задачи на {weekly_day_str} в {weekly_time_str} {report_timezone_str}"); weekly_schedule_func=getattr(schedule.every(), weekly_day_str.lower(), schedule.every().sunday); weekly_schedule_func.at(weekly_time_str, report_timezone_str).do(run_weekly_tasks).tag('weekly')
# # #         try:
# # #             next_daily_run=None; next_weekly_run=None
# # #             for job in schedule.get_jobs():
# # #                 job_tags=list(job.tags)
# # #                 if 'daily' in job_tags and job.next_run: next_daily_run=job.next_run
# # #                 elif 'weekly' in job_tags and job.next_run: next_weekly_run=job.next_run
# # #             next_daily_str=next_daily_run.strftime('%Y-%m-%d %H:%M:%S %Z') if next_daily_run else 'N/A'; next_weekly_str=next_weekly_run.strftime('%Y-%m-%d %H:%M:%S %Z') if next_weekly_run else 'N/A'
# # #             logger.info(f"Ближ. запуск daily: {next_daily_str}"); logger.info(f"Ближ. запуск weekly: {next_weekly_str}")
# # #         except Exception as e_sched_log: logger.warning(f"Не получить время след. запуска: {e_sched_log}")
# # #
# # #         # Запускаем schedule в отдельном потоке-демоне
# # #         # чтобы он не блокировал основную логику ожидания в fetch_all_players
# # #         schedule_thread = threading.Thread(target=run_schedule_continuously, args=(1,), daemon=True)
# # #         schedule_thread.start()
# # #         logger.info("Поток для schedule запущен.")
# # #
# # #         logger.info("Стартовое обучение моделей отключено."); logger.info("Загрузка конфигурации игроков...");
# # #         players = config.load_players()
# # #         if not players: logger.critical("Не загрузить config. Выход."); notifications.send_telegram_message("КРИТ. ОШИБКА: Не загрузить список игроков!", parse_mode=None); sys.exit(1)
# # #
# # #         logger.info("Загрузка последних цен из CSV...")
# # #         for name in players.keys():
# # #             try:
# # #                 last_entry = storage.get_last_known_price(name);
# # #                 if last_entry and 'Цена' in last_entry:
# # #                     try: price_val = int(str(last_entry['Цена']).replace(',', '').replace(' ', '')); LAST_KNOWN_PRICE[name] = price_val; price_f = storage.format_price(price_val); logger.info(f"Загружена цена для {name}: {price_f}")
# # #                     except (ValueError, TypeError) as e_conv: logger.warning(f"Не преобразовать цену '{last_entry['Цена']}' для {name}: {e_conv}")
# # #             except Exception as e_price: logger.error(f"Ошибка загрузки последней цены для {name}: {e_price}")
# # #
# # #         logger.info("Запуск основного цикла парсинга (с ожиданием)...")
# # #         main_driver = fetch_all_players(players) # Получаем драйвер после завершения цикла
# # #
# # #     except KeyboardInterrupt:
# # #         logger.info("Обработка Ctrl+C (KeyboardInterrupt)...")
# # #     except Exception as e_main:
# # #         logger.critical(f"КРИТИЧЕСКАЯ ОШИБКА в main(): {e_main}", exc_info=True)
# # #         try:
# # #             error_msg = notifications.format_error_message("Main() CRITICAL", f"Крит. ошибка:\n{traceback.format_exc()}")
# # #             notifications.send_telegram_message(error_msg, parse_mode="MarkdownV2")
# # #         except Exception as notify_err: logger.error(f"Не отправить уведомление о крит. ошибке main(): {notify_err}")
# # #     finally:
# # #         logger.info("Начало процедуры завершения...")
# # #         # Закрываем драйвер, если он был возвращен из fetch_all_players
# # #         if main_driver:
# # #             try:
# # #                 logger.info("Закрытие WebDriver при завершении...")
# # #                 main_driver.quit()
# # #                 logger.info("WebDriver успешно закрыт.")
# # #             except Exception as e_final_quit:
# # #                 logger.error(f"Ошибка при финальном закрытии WebDriver: {e_final_quit}")
# # #         else:
# # #              logger.warning("Финальное закрытие WebDriver пропущено (драйвер не был возвращен или не был создан).")
# # #
# # #         notifications.send_shutdown_notification()
# # #         logger.info("Парсер RenderZ окончательно остановлен.")
# # #         # schedule.clear() # Не нужно, т.к. поток - демон
# # #         print("Скрапер остановлен.")
# # #
# # # if __name__ == "__main__":
# # #     main()
# #
# # # =============================================
# # # ФАЙЛ: scraper.py (ВЕРСИЯ v7.5.16 - Fix SyntaxError in finally block)
# # # - ИСПРАВЛЕНА ошибка синтаксиса в блоке finally функции main.
# # # - Проведен ЕЩЕ ОДИН полный ре-аудит синтаксиса try/except/if блоков.
# # # - Содержит все доработки: Fast Start, испр. create_webdriver, испр. HTML dump, испр. parse_refresh_time, испр. parse_player_data, испр. schedule tasks.
# # # =============================================
# #
# # import logging
# # import schedule
# # import time
# # import json
# # import os
# # import sys
# # from datetime import datetime, timedelta, timezone
# # import traceback
# # import re
# # import subprocess
# # from selenium import webdriver
# # from selenium.webdriver.firefox.service import Service as FirefoxService
# # from selenium.webdriver.firefox.options import Options as FirefoxOptions
# # from selenium.common.exceptions import (WebDriverException, TimeoutException,
# #                                         NoSuchElementException, StaleElementReferenceException)
# # from selenium.webdriver.common.by import By
# # from selenium.webdriver.support.ui import WebDriverWait
# # from selenium.webdriver.support import expected_conditions as EC
# # import pandas as pd
# # import threading
# #
# # # --- Импорт пользовательских модулей ---
# # try:
# #     import config       # Ожидается v8.16+
# #     import storage      # Ожидается v6.8+
# #     import signals      # Ожидается v23.14+
# #     import notifications # Ожидается v10.7+
# #     import cycle_analysis # Ожидается v8.5+
# #     import ohlc_generator
# #     # import model_trainer
# #     import weekly_stats
# #     # import evaluate_model
# #     # import events_manager
# # except ImportError as e:
# #     print(f"КРИТИЧЕСКАЯ ОШИБКА: Не удалось импортировать модуль: {e}.")
# #     sys.exit(1)
# #
# # # --- Настройка Логирования ---
# # LOG_DIR = getattr(config, 'LOG_DIR', 'logs'); os.makedirs(LOG_DIR, exist_ok=True)
# # log_filename = os.path.join(LOG_DIR, f"scraper_{datetime.now().strftime('%Y-%m-%d')}.log")
# # log_level_str = getattr(config, 'LOG_LEVEL', 'INFO').upper(); log_level = getattr(logging, log_level_str, logging.INFO)
# # logger = logging.getLogger();
# # if not logger.hasHandlers():
# #     logging.basicConfig(level=log_level, format='%(asctime)s - %(levelname)s - [%(name)s] - [%(filename)s:%(lineno)d] - %(message)s', handlers=[logging.StreamHandler(sys.stdout), logging.FileHandler(log_filename, encoding='utf-8')])
# #     logger.info(f"Логгер инициализирован: {log_level_str}")
# # logging.getLogger("urllib3").setLevel(logging.WARNING); logging.getLogger("selenium").setLevel(logging.INFO); logging.getLogger("schedule").setLevel(logging.INFO); logging.getLogger("filelock").setLevel(logging.WARNING)
# # logging.getLogger("scraper").setLevel(log_level); logging.getLogger("storage").setLevel(log_level); logging.getLogger("signals").setLevel(log_level); logging.getLogger("cycle_analysis").setLevel(log_level); logging.getLogger("notifications").setLevel(log_level)
# #
# # # --- Проверка наличия необходимых функций ---
# # required = [(notifications, 'send_combined_notification'),(notifications, 'format_error_message'), (notifications, 'send_telegram_message'),(signals,'check_signals'), (storage,'log_player_data'),(storage,'read_player_history'), (storage,'get_last_known_price'),(config,'load_players'), (cycle_analysis, 'determine_main_cycle_phase_df'), (cycle_analysis, 'determine_short_cycle_phase_df'), (storage, 'save_update_schedule'), (storage, 'load_update_schedule'), (ohlc_generator,'rewrite_ohlc_summary' if hasattr(ohlc_generator,'rewrite_ohlc_summary') else 'generate_ohlc_report'), (weekly_stats, 'generate_weekly_stats_report')]
# # missing = False;
# # for mod, func in required:
# #     if not hasattr(mod, func): logging.critical(f"Нет {mod.__name__}.{func}! Выход."); missing = True
# # if missing: sys.exit(1)
# #
# # # --- Глобальные переменные ---
# # PLAYER_UPDATE_INTERVAL = {}; GECKODRIVER_PATH = getattr(config, 'GECKODRIVER_PATH', None); MIN_HISTORY_FOR_SIGNALS = getattr(config, 'MIN_HISTORY_FOR_SIGNALS', 50); REFRESH_BUFFER_SECONDS = getattr(config, 'REFRESH_BUFFER_SECONDS', 15)
# #
# # # --- Функции WebDriver ---
# # def create_webdriver():
# #     logger = logging.getLogger("scraper.webdriver"); logger.debug("Создание WebDriver...")
# #     service = None; driver = None
# #     try:
# #         service_args = ['--log', 'fatal']; log_p = os.path.join(LOG_DIR, "geckodriver.log") if LOG_DIR else "geckodriver.log"; exec_p = None
# #         if GECKODRIVER_PATH and os.path.exists(GECKODRIVER_PATH): exec_p = GECKODRIVER_PATH; logger.info(f"Geckodriver: {exec_p}")
# #         else: from shutil import which; found = which('geckodriver');
# #         if found: exec_p = found; logger.info(f"Geckodriver PATH: {exec_p}")
# #         else:
# #              logger.error("geckodriver не найден.");
# #              try:
# #                  if config.SEND_TELEGRAM_ERRORS: notifications.send_telegram_message(notifications.format_error_message("Geckodriver Not Found", "Укажите путь или установите в PATH."), parse_mode=None)
# #              except Exception as e: logger.error(f"Не отправить уведомление: {e}")
# #              return None
# #         service = FirefoxService(executable_path=exec_p, service_args=service_args, log_path=log_p); logger.debug(f"FirefoxService создан. Логи: {log_p}")
# #     except Exception as e_service:
# #          logger.critical(f"КРИТ. ОШИБКА FirefoxService: {e_service}", exc_info=True)
# #          try:
# #              if config.SEND_TELEGRAM_ERRORS: notifications.send_telegram_message(notifications.format_error_message("WebDriver Service Init Error", traceback.format_exc()), parse_mode=None)
# #          except Exception as e: logger.error(f"Не отправить уведомление: {e}"); return None
# #     opt = FirefoxOptions(); opt.add_argument("--headless"); opt.add_argument("--disable-gpu"); opt.add_argument("--window-size=1920,1080"); opt.add_argument("--no-sandbox"); opt.add_argument("--disable-dev-shm-usage"); opt.set_preference("permissions.default.image", 2); opt.set_preference("dom.ipc.plugins.enabled.libflashplayer.so", "false"); opt.set_preference("javascript.enabled", True); opt.set_preference("network.cookie.cookieBehavior", 0); opt.set_preference("network.http.connection-timeout", 90); opt.set_preference("network.http.response.timeout", 120); opt.set_preference("dom.max_script_run_time", 90); opt.set_preference("dom.webdriver.enabled", False); opt.set_preference('useAutomationExtension', False); opt.set_preference("general.useragent.override", "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/115.0")
# #     logger.info("Запуск Firefox WebDriver...");
# #     try:
# #         if service is None: logger.error("Service не инициализирован."); return None
# #         driver = webdriver.Firefox(service=service, options=opt); driver.implicitly_wait(20); driver.set_page_load_timeout(90); driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"); logger.info("WebDriver создан."); return driver
# #     except WebDriverException as e:
# #         msg = f"КРИТ. WebDriverException: {e}\n{traceback.format_exc()}"; logger.critical(msg, exc_info=False);
# #         try:
# #             if config.SEND_TELEGRAM_ERRORS: notifications.send_telegram_message(f"‼️ WebDriver Startup Error (WebDriverException) ‼️\n\n{msg}", parse_mode=None)
# #         except Exception as e: logger.error(f"Не отправить уведомление: {e}"); return None
# #     except Exception as e:
# #         logger.critical(f"КРИТ. ОШИБКА WebDriver: {e}", exc_info=True);
# #         try:
# #             if config.SEND_TELEGRAM_ERRORS: notifications.send_telegram_message(notifications.format_error_message("WebDriver Startup Error (Unexpected)", traceback.format_exc()), parse_mode=None)
# #         except Exception as e: logger.error(f"Не отправить уведомление: {e}"); return None
# #     return None
# #
# # def parse_player_data(driver, player_name, player_url):
# #     logger = logging.getLogger("scraper.parser"); logger.info(f"Парсим {player_name} (URL: {player_url})")
# #     price_xpath = "//div[contains(@class, 'market-data--key') and normalize-space(.)='Current value']/ancestor::div[contains(@class, 'flex-col')][2]//div[contains(@class, 'market-data--value')][1]/span[1]"
# #     change_xpath = "//div[contains(@class, 'market-data--value--change')]//span[contains(text(), '%')]"
# #     update_xpath = "//div[contains(text(), 'Market Refresh')]/following-sibling::div[contains(@class, 'market-data--value-mini')]"
# #     min_xpath = "//div[contains(text(), 'Market low/high')]/following-sibling::div[contains(@class, 'market-data--value-mini')]//span[1]"
# #     max_xpath = "//div[contains(text(), 'Market low/high')]/following-sibling::div[contains(@class, 'market-data--value-mini')]//span[last()]"
# #     data = {'timestamp': None, 'price': None, 'change': 'N/A', 'min_order': None, 'max_order': None, 'update_time': 'N/A', 'error': None}
# #     html_dump_path = os.path.join(LOG_DIR, f"error_{player_name.replace(' ','_')}_{datetime.now().strftime('%H%M%S')}.html")
# #     wait_long = WebDriverWait(driver, 25); wait_short = WebDriverWait(driver, 10)
# #     try:
# #         start_get = time.time(); logger.debug(f"Загрузка URL: {player_url}"); driver.get(player_url); logger.debug(f"URL загружен: {time.time() - start_get:.2f} сек."); time.sleep(1.5)
# #         start_find_price = time.time(); price = None; raw_price_text = "N/A"
# #         try:
# #             price_element = wait_long.until(EC.visibility_of_element_located((By.XPATH, price_xpath))); logger.debug(f"Цена найдена: {time.time() - start_find_price:.2f} сек.")
# #             raw_price_text = price_element.text.strip(); logger.debug(f"Raw price: '{raw_price_text}'"); cleaned = re.sub(r'[^\d]', '', raw_price_text); price = int(cleaned) if cleaned.isdigit() else None
# #             if price is None and raw_price_text not in ["", "-", "N/A"]: logger.warning(f"{player_name}: Не распарсить цену '{raw_price_text}'")
# #             elif price == 0 and raw_price_text != '0': logger.warning(f"{player_name} цена 0, текст: '{raw_price_text}'.")
# #             data['price'] = price;
# #             if price is not None: data['low'] = price; data['high'] = price
# #         except TimeoutException: data['error'] = "Таймаут цены"; logger.error(f"{data['error']} ({time.time() - start_find_price:.1f}s) {player_name}")
# #         except NoSuchElementException: data['error'] = "Элемент цены не найден"; logger.error(f"{data['error']} {player_name}")
# #         except Exception as e: data['error'] = f"Ошибка парсинга цены: {type(e).__name__}"; logger.error(f"{data['error']} {player_name}: {e}", exc_info=True)
# #         parsing_times = {}
# #         start = time.time();
# #         try: change_text = wait_short.until(EC.visibility_of_element_located((By.XPATH, change_xpath))).text.strip(); data['change'] = change_text if change_text else "0%"
# #         except Exception: data['change'] = "0%"; logger.debug(f"Изменение не найдено {player_name}")
# #         parsing_times['change'] = time.time() - start; start = time.time()
# #         try: update_text = wait_short.until(EC.visibility_of_element_located((By.XPATH, update_xpath))).text.strip(); data['update_time'] = update_text if update_text else "N/A"
# #         except Exception: data['update_time'] = "N/A"; logger.warning(f"Обновление не найдено {player_name}")
# #         parsing_times['update'] = time.time() - start; min_v, max_v = None, None; start = time.time()
# #         try:
# #             min_raw = wait_short.until(EC.visibility_of_element_located((By.XPATH, min_xpath))).text.strip(); min_clean = re.sub(r'[^\d]', '', min_raw); min_v = int(min_clean) if min_clean.isdigit() else None; data['min_order'] = min_v
# #             if min_v is not None and data.get('low') is not None: data['low'] = min_v
# #         except (TimeoutException, NoSuchElementException, StaleElementReferenceException): logger.debug(f"Min ордер не найден {player_name}")
# #         except Exception as e: logger.warning(f"Ошибка парсинга Min цены: {e}")
# #         parsing_times['min'] = time.time() - start; start = time.time()
# #         try:
# #             max_raw = wait_short.until(EC.visibility_of_element_located((By.XPATH, max_xpath))).text.strip(); max_clean = re.sub(r'[^\d]', '', max_raw); max_v = int(max_clean) if max_clean.isdigit() else None; data['max_order'] = max_v
# #             if max_v is not None and data.get('high') is not None: data['high'] = max_v
# #         except (TimeoutException, NoSuchElementException, StaleElementReferenceException): logging.debug(f"Max ордер не найден {player_name}")
# #         except Exception as e: logging.warning(f"Ошибка парсинга Max цены: {e}")
# #         parsing_times['max'] = time.time() - start; logger.debug(f"Время доп: {parsing_times}")
# #         min_f = storage.format_price(min_v) if min_v is not None else "N/A"; max_f = storage.format_price(max_v) if max_v is not None else "N/A"
# #         data['orders'] = f"Min: {min_f} / Max: {max_f}"; data['timestamp'] = datetime.now(timezone.utc).isoformat()
# #         if data.get('price') is None and not data.get('error'):
# #              data['error'] = "Цена не найдена/распознана"; logger.error(f"{player_name}: {data['error']}")
# #              try:
# #                  with open(html_dump_path, "w", encoding="utf-8") as f: f.write(driver.page_source)
# #                  logger.info(f"HTML сохранен (ошибка цены): {html_dump_path}")
# #              except Exception as dump_err: logger.error(f"Не сохранить HTML (ошибка цены): {dump_err}")
# #         elif data.get('error'):
# #              logger.error(f"Завершено с ошибкой {player_name}: {data['error']}")
# #              try:
# #                  with open(html_dump_path, "w", encoding="utf-8") as f: f.write(driver.page_source)
# #                  logger.info(f"HTML сохранен (ошибка '{data['error']}'): {html_dump_path}")
# #              except Exception as dump_err: logger.error(f"Не сохранить HTML (ошибка): {dump_err}")
# #         else: data['error'] = None; price_f = storage.format_price(data['price']); logger.info(f"Успешно {player_name}: Цена={price_f} Изм='{data['change']}' Ордера='{data['orders']}' Обн='{data['update_time']}'")
# #         return data
# #     except WebDriverException as e: logger.error(f"WebDriverException {player_name}: {e}"); raise e
# #     except Exception as e:
# #         error_type = type(e).__name__; logger.error(f"Неожиданная ошибка {player_name}: {e}", exc_info=True); data['error'] = f"Unexpected: {error_type}"
# #         try:
# #             if driver and hasattr(driver, 'page_source'):
# #                 with open(html_dump_path, "w", encoding="utf-8") as f: f.write(driver.page_source)
# #                 logger.info(f"HTML сохранен (unexpected error {error_type}): {html_dump_path}")
# #         except Exception as dump_err: logger.error(f"Не сохранить HTML (unexpected error): {dump_err}")
# #         return data
# #
# # # --- ФУНКЦИЯ ПАРСИНГА ВРЕМЕНИ (v7.5.8 - Корректный синтаксис) ---
# # def parse_refresh_time(refresh_string):
# #     logger = logging.getLogger("scraper.parser"); s=0; m=0; h=0; refresh_string = (refresh_string or "").lower()
# #     if 'now' in refresh_string or 'сейчас' in refresh_string: return timedelta(seconds=5)
# #     if 'soon' in refresh_string: return timedelta(seconds=45)
# #     hm = re.search(r'(\d+)\s*(h|hr|ч)', refresh_string);
# #     if hm:
# #         try: h = int(hm.group(1))
# #         except ValueError: pass
# #     mm = re.search(r'(\d+)\s*(m|min|мин)', refresh_string);
# #     if mm:
# #         try: m = int(mm.group(1))
# #         except ValueError: pass
# #     sm = re.search(r'(\d+)\s*(s|sec|с|сек)', refresh_string);
# #     if sm:
# #         try: s = int(sm.group(1))
# #         except ValueError: pass
# #     if h==0 and m==0 and s==0: di = getattr(config,'DEFAULT_REFRESH_INTERVAL_MINUTES',15); logger.warning(f"Не распознать '{refresh_string}'. Интервал:{di}m."); return timedelta(minutes=di)
# #     return timedelta(hours=h, minutes=m, seconds=s)
# # # ----------------------------------------------------
# #
# # # --- Основной цикл ---
# # def fetch_all_players(players_config, initial_update_interval):
# #     global PLAYER_UPDATE_INTERVAL; logger = logging.getLogger("scraper.fetch"); PLAYER_UPDATE_INTERVAL = initial_update_interval
# #     logger.info(f"Цикл с {len(PLAYER_UPDATE_INTERVAL)} записями."); pl = list(players_config.keys())
# #     if not pl: logger.warning("Список игроков пуст."); return None
# #     driver = None; count = 0
# #     try:
# #         while True:
# #             if driver is None: start = time.time(); logger.info("Создание WebDriver..."); driver = create_webdriver();
# #             if driver is None: logger.critical(f"Не создать WebDriver. Пауза 5 мин..."); time.sleep(300); continue
# #             else: logger.info(f"WebDriver создан: {time.time() - start:.1f}s.")
# #             now = datetime.now(timezone.utc); next_p = None; min_t = None; wait_s = 60
# #             active = {p: t for p, t in PLAYER_UPDATE_INTERVAL.items() if p in pl}
# #             if not active: logger.warning("Нет активных игроков. Ждем 60с.")
# #             else:
# #                 for p, t in active.items():
# #                     if t is None or t <= now: next_p = p; min_t = now; break
# #                     elif min_t is None or t < min_t: min_t = t; next_p = p
# #                 if next_p is None:
# #                     min_future_time = None # Исправлено v7.5.15
# #                     for p, t in active.items():
# #                          if t and (min_future_time is None or t < min_future_time): min_future_time = t; next_p = p
# #                     if min_future_time: min_t = min_future_time
# #                     else: logger.error("Не определить след. обн!"); next_p="Error"; min_t=now+timedelta(seconds=300)
# #             if next_p and next_p not in ["N/A", "Error"]: wait_s = max(0, int((min_t - now).total_seconds())) if min_t else 0
# #             if wait_s > 0: t_s = min_t.strftime('%H:%M:%S %Z') if min_t else "N/A"; p_s = f" ({next_p})" if next_p and next_p not in ["N/A", "Error"] else ""; logger.info(f"След:{p_s} ~{t_s}. Ждем ~{wait_s}s..."); start_w=time.time();
# #             while time.time() - start_w < wait_s: schedule.run_pending(); time.sleep(0.5)
# #             if wait_s > 0 : logger.info("Ожидание завершено.")
# #             now = datetime.now(timezone.utc); p_now = None; p_list = []
# #             for p, t in PLAYER_UPDATE_INTERVAL.items():
# #                  if p in pl and (not t or now >= t): p_list.append(p)
# #             if not p_list: logger.debug("Нет игроков для обработки."); continue
# #             p_now = p_list[0]; player_name = p_now
# #             if player_name not in players_config: logger.warning(f"'{player_name}' нет в конфиге."); del PLAYER_UPDATE_INTERVAL[player_name]; continue
# #             p_info = players_config[player_name]; p_url = p_info.get("url")
# #             count += 1; start_proc = time.time()
# #             if not p_url: logger.warning(f"Нет URL {player_name}. Интервал 1ч."); PLAYER_UPDATE_INTERVAL[player_name] = now + timedelta(hours=1); continue
# #             logger.info(f"Обработка #{count}: {player_name}")
# #             start_parse = time.time(); p_data = None
# #             try: p_data = parse_player_data(driver, player_name, p_url)
# #             except WebDriverException as e:
# #                  logger.error(f"WebDriverException: {e}", exc_info=True);
# #                  if config.SEND_TELEGRAM_ERRORS:
# #                      try: notifications.send_telegram_message(notifications.format_error_message(player_name, f"WebDriverException:\n{traceback.format_exc()}"), parse_mode=None)
# #                      except Exception as ne: logger.error(f"Не отправить уведомление: {ne}")
# #                  logger.warning("Перезапуск WebDriver...");
# #                  if driver:
# #                      try: driver.quit()
# #                      except Exception as eq: logger.error(f"Ошибка закрытия WebDriver: {eq}")
# #                  driver = None; PLAYER_UPDATE_INTERVAL[player_name] = now + timedelta(minutes=1); continue
# #             except Exception as e: logger.error(f"Ошибка parse_player_data {player_name}: {e}", exc_info=True); p_data = {'error': f"Unexpected: {type(e).__name__}"}
# #             logger.debug(f"[{player_name}] Парсинг: {time.time() - start_parse:.2f}s.")
# #             # --- Блок обработки результата парсинга (Исправлено v7.5.10) ---
# #             if p_data is None or p_data.get('error'):
# #                 err = p_data.get('error','None') if p_data else 'None'; logger.warning(f"Ошибка парсинга {player_name}: {err}. Повтор 5м."); PLAYER_UPDATE_INTERVAL[player_name] = now + timedelta(minutes=5)
# #                 if config.SEND_TELEGRAM_ERRORS:
# #                     try: notifications.send_telegram_message(notifications.format_error_message(player_name, err), parse_mode="MarkdownV2")
# #                     except Exception as ne: logger.error(f"Не отправить уведомление: {ne}")
# #             elif p_data.get('price') is not None:
# #                 try: storage.log_player_data(player_name, p_data)
# #                 except Exception as e: logger.error(f"Ошибка сохранения {player_name}: {e}", exc_info=True)
# #                 analysis_start_time = time.time()
# #                 history_df = None; sig_data = None
# #                 try:
# #                     history_df = storage.read_player_history(player_name, min_rows=MIN_HISTORY_FOR_SIGNALS)
# #                     if history_df is not None and not history_df.empty:
# #                         logger.debug(f"[{player_name}] История ({len(history_df)}) прочитана.")
# #                         cfg = players_config.get(player_name, {'name': player_name, 'ovr': p_info.get('ovr', 'N/A')})
# #                         sig_data = signals.check_signals(history_df, cfg)
# #                         logger.debug(f"[{player_name}] Сигналы рассчитаны.")
# #                         if sig_data:
# #                             if sig_data.get('send_notification', False): logger.info(f"Отправка увед {player_name}..."); notifications.send_combined_notification(cfg, sig_data, p_data)
# #                             else: logger.info(f"[{player_name}] Увед не требуется. Score: {sig_data.get('aggregated_score', 'N/A'):.2f}")
# #                         else: logger.warning(f"[{player_name}] check_signals вернул None.")
# #                     elif history_df is None:
# #                          logger.error(f"[{player_name}] Анализ пропущен из-за ошибки чтения истории.")
# #                     else: # history_df пустой
# #                          logger.warning(f"Мало истории ({len(history_df) if history_df is not None else 0}/{MIN_HISTORY_FOR_SIGNALS}) для {player_name}. Анализ пропущен.")
# #                 except Exception as e_analysis:
# #                     logger.error(f"Ошибка блока анализа/увед {player_name}: {e_analysis}", exc_info=True);
# #                     if config.SEND_TELEGRAM_ERRORS:
# #                         try: notifications.send_telegram_message(notifications.format_error_message(player_name, f"Ошибка анализа/увед:\n{traceback.format_exc()}"), parse_mode=None) # Исправлено v7.5.15
# #                         except Exception: pass
# #                 logger.debug(f"[{player_name}] Блок анализа: {time.time() - analysis_start_time:.3f}s.")
# #                 ref_int = parse_refresh_time(p_data.get('update_time', 'N/A')); buf_sec = ref_int.total_seconds() + REFRESH_BUFFER_SECONDS; min_sec = getattr(config, 'MIN_INTERVAL_SECONDS', 60); act_sec = max(buf_sec, min_sec); next_u = datetime.now(timezone.utc) + timedelta(seconds=act_sec); PLAYER_UPDATE_INTERVAL[player_name] = next_u; logger.debug(f"След. обн {player_name}: {next_u:%H:%M:%S %Z} (~{act_sec:.0f}с)")
# #             else: logger.error(f"{player_name}: цена None. Повтор 15м."); PLAYER_UPDATE_INTERVAL[player_name] = now + timedelta(minutes=15)
# #             logger.info(f"Завершена обработка {player_name}: {time.time() - start_proc:.2f} сек.")
# #             pause = getattr(config, 'PAUSE_BETWEEN_PLAYERS', 1.0);
# #             if pause > 0: logger.debug(f"Пауза {pause} сек..."); time.sleep(pause)
# #     except KeyboardInterrupt: logger.info("Ctrl+C..."); return driver
# #     except Exception as e_loop:
# #         logger.critical(f"Крит. ошибка цикла: {e_loop}", exc_info=True);
# #         if config.SEND_TELEGRAM_ERRORS:
# #              try:
# #                  notifications.send_telegram_message(notifications.format_error_message("Fetch Loop CRITICAL", traceback.format_exc()), parse_mode=None) # Исправлено v7.5.15
# #              except Exception: pass
# #         return driver
# #
# # # --- Задачи Schedule (Исправлено v7.5.11) ---
# # def run_daily_tasks():
# #     logger = logging.getLogger("scraper.schedule"); logger.info("--- Daily Tasks Start ---")
# #     try:
# #         logger.info("OHLC...")
# #         if hasattr(ohlc_generator, 'rewrite_ohlc_summary'): ohlc_generator.rewrite_ohlc_summary(days=2); logger.info("OHLC OK.")
# #         else: logger.error("Нет ohlc_generator.rewrite_ohlc_summary")
# #     except Exception as e:
# #         logger.error(f"OHLC Error: {e}", exc_info=True)
# #         if config.SEND_TELEGRAM_ERRORS:
# #             try: notifications.send_telegram_message(notifications.format_error_message("Daily Tasks Error", f"OHLC Error:\n{traceback.format_exc()}"), parse_mode=None) # Исправлено v7.5.15
# #             except Exception as notify_err: logger.error(f"Не отправить уведомление об ошибке OHLC: {notify_err}")
# #     logger.info("--- Daily Tasks End ---")
# #
# # def run_weekly_tasks():
# #     logger = logging.getLogger("scraper.schedule"); logger.info("--- Weekly Tasks Start ---")
# #     try:
# #         logger.info("Stats...")
# #         if hasattr(weekly_stats, 'generate_weekly_stats_report'): weekly_stats.generate_weekly_stats_report(); logger.info("Stats OK.")
# #         else: logger.error("Нет weekly_stats.generate_weekly_stats_report")
# #     except Exception as e:
# #         logger.error(f"Stats Error: {e}", exc_info=True)
# #         if config.SEND_TELEGRAM_ERRORS:
# #             try: notifications.send_telegram_message(notifications.format_error_message("Weekly Tasks Error", f"Stats Error:\n{traceback.format_exc()}"), parse_mode=None) # Исправлено v7.5.15
# #             except Exception as notify_err: logger.error(f"Не отправить уведомление об ошибке Stats: {notify_err}")
# #     logger.info("--- Weekly Tasks End ---")
# # # -----------------------------------------
# #
# # # --- Поток Schedule (Исправлено v7.5.16) ---
# # def run_schedule_continuously(stop_event):
# #     logger = logging.getLogger("scraper.schedule_thread")
# #     logger.info("Schedule thread started.")
# #     while not stop_event.is_set():
# #         try:
# #             schedule.run_pending()
# #         except Exception as e:
# #             logger.error(f"Schedule error: {e}", exc_info=True)
# #         # wait(1) выполняется в КАЖДОЙ итерации цикла, вне зависимости от ошибки
# #         stop_event.wait(1) # Ждем секунду или сигнала остановки
# #     logger.info("Schedule thread stopped.")
# # # ---------------------------------------
# #
# # # --- Main ---
# # def main():
# #     driver = None; stop = threading.Event(); sched_th = None; interval = {}
# #     try:
# #         logger = logging.getLogger("scraper.main"); v = getattr(sys.modules[__name__], '__version__', '7.5.16'); logger.info("="*45); logger.info(f"[scraper] Старт (v{v})"); logger.info("="*45)
# #         if config.SEND_TELEGRAM_STARTUP: notifications.send_startup_notification()
# #         dt=getattr(config,'DAILY_REPORT_TIME',"09:00"); wd=getattr(config,'WEEKLY_REPORT_DAY',"sunday"); wt=getattr(config,'WEEKLY_REPORT_TIME',"10:00"); tz=getattr(config,'REPORT_TIMEZONE',"UTC"); logger.info(f"Daily: {dt} {tz}"); schedule.every().day.at(dt, tz).do(run_daily_tasks).tag('daily'); logger.info(f"Weekly: {wd} {wt} {tz}");
# #         try: getattr(schedule.every(), wd.lower()).at(wt, tz).do(run_weekly_tasks).tag('weekly')
# #         except AttributeError: logger.error(f"День '{wd}' неверный."); schedule.every().sunday.at(wt, tz).do(run_weekly_tasks).tag('weekly')
# #         try: nd = next((j.next_run for j in schedule.get_jobs('daily')), None); nw = next((j.next_run for j in schedule.get_jobs('weekly')), None); logger.info(f"Next daily: {nd.strftime('%Y-%m-%d %H:%M:%S %Z') if nd else 'N/A'}"); logger.info(f"Next weekly: {nw.strftime('%Y-%m-%d %H:%M:%S %Z') if nw else 'N/A'}")
# #         except Exception as e: logger.warning(f"Не получить время задач: {e}")
# #         sched_th = threading.Thread(target=run_schedule_continuously, args=(stop,), daemon=True); sched_th.start(); logger.info("Поток schedule запущен.")
# #         logger.info("Загрузка игроков..."); players = config.load_players()
# #         if not players:
# #              logger.critical("Не загрузить игроков!");
# #              if config.SEND_TELEGRAM_ERRORS:
# #                  try: notifications.send_telegram_message("КРИТ. ОШИБКА: Не загрузить список игроков!", parse_mode=None)
# #                  except Exception: pass
# #              sys.exit(1)
# #         logger.info(f"{len(players)} игроков загружено.")
# #         logger.info("Загрузка расписания..."); interval = storage.load_update_schedule()
# #         logger.info("Иниц. расписания..."); ps, pi, pr = 0, 0, 0; now = datetime.now(timezone.utc)
# #         keys = list(interval.keys());
# #         for k in keys:
# #              if k not in players: logger.warning(f"'{k}' удален."); del interval[k]; pr += 1
# #         for k in players.keys():
# #             if k in interval: ps += 1
# #             else: logger.warning(f"'{k}' не найден."); interval[k] = now - timedelta(seconds=10); pi += 1
# #         logger.info(f"Расписание: {ps} из файла, {pi} новых, {pr} удалено.")
# #         logger.info("Запуск основного цикла...")
# #         driver = fetch_all_players(players, interval)
# #     except KeyboardInterrupt: logger.info("Ctrl+C...")
# #     except Exception as e:
# #         logger.critical(f"КРИТ. ОШИБКА main: {e}", exc_info=True);
# #         if config.SEND_TELEGRAM_ERRORS:
# #              try: notifications.send_telegram_message(notifications.format_error_message("Main() CRITICAL", f"{traceback.format_exc()}"), parse_mode=None) # Исправлено v7.5.15
# #              except Exception: pass
# #     finally:
# #         logger.info("Завершение работы...")
# #         try: # Исправлено v7.5.16
# #             logger.info("Сохранение расписания...")
# #             storage.save_update_schedule(PLAYER_UPDATE_INTERVAL)
# #         except Exception as e: # Исправлено v7.5.16
# #             logger.error(f"Не сохранить расписание: {e}")
# #
# #         stop.set()
# #         if sched_th and sched_th.is_alive():
# #             logger.info("Ожидание schedule...");
# #             sched_th.join(timeout=5); # Исправлено v7.5.16 (точка с запятой убрана для ясности)
# #         if sched_th and not sched_th.is_alive(): # Исправлено v7.5.16 (отдельный if)
# #             logger.info("Поток schedule завершен.")
# #         else:
# #             if sched_th and sched_th.is_alive(): # Исправлено v7.5.16 (доп проверка)
# #                  logger.warning("Поток schedule не завершился вовремя.")
# #
# #         if driver:
# #             try: # Исправлено v7.5.16
# #                 logger.info("Закрытие WebDriver...")
# #                 driver.quit()
# #                 logger.info("WebDriver закрыт.")
# #             except Exception as e: # Исправлено v7.5.16
# #                 logger.error(f"Ошибка закрытия WebDriver: {e}")
# #         else:
# #             logger.warning("Закрытие WebDriver пропущено.")
# #
# #         if config.SEND_TELEGRAM_SHUTDOWN:
# #              try: # Исправлено v7.5.16
# #                  notifications.send_shutdown_notification()
# #              except Exception as e: # Исправлено v7.5.16
# #                  logger.error(f"Не отправить уведомление об остановке: {e}")
# #         logger.info("Парсер остановлен."); print("Скрапер остановлен.")
# #
# # # Версия
# # __version__ = "7.5.16" # Обновлена версия
# #
# # if __name__ == "__main__":
# #     main()
# #
#
# # =============================================
# # ФАЙЛ: scraper.py (ВЕРСИЯ v7.5.23 - Use Correct Notification/Signal Calls)
# # - ИЗМЕНЕНО: Вызовы уведомлений заменены на актуальные из notifications v10.11+.
# # - ИЗМЕНЕНО: Вызов signals.check_signals теперь передает latest_parsed_data.
# # - Логика парсинга parse_player_data НЕ ТРОНУТА (из v7.5.22).
# # - Содержит все доработки из v7.5.22.
# # =============================================
#
# import logging
# import schedule
# import time
# import json
# import os
# import sys
# from datetime import datetime, timedelta, timezone
# import traceback
# import re
# import subprocess
# from selenium import webdriver
# from selenium.webdriver.firefox.service import Service as FirefoxService
# from selenium.webdriver.firefox.options import Options as FirefoxOptions
# from selenium.common.exceptions import (WebDriverException, TimeoutException,
#                                         NoSuchElementException, StaleElementReferenceException)
# from selenium.webdriver.common.by import By
# from selenium.webdriver.support.ui import WebDriverWait
# from selenium.webdriver.support import expected_conditions as EC
# import pandas as pd
# import threading
# import logging.handlers # Для RotatingFileHandler
#
# # --- Импорт пользовательских модулей ---
# try:
#     import config       # Ожидается v8.16+
#     import storage      # Ожидается v6.9+
#     import signals      # Ожидается v23.27+
#     import notifications # Ожидается v10.11+
#     import cycle_analysis # Ожидается v8.9+
#     import ohlc_generator # Ожидается v3.2+
#     # import model_trainer
#     import weekly_stats
#     # import evaluate_model
#     # import events_manager
# except ImportError as e:
#     # Базовый логгер ДО настройки
#     logging.basicConfig(level=logging.CRITICAL, format='%(asctime)s - %(levelname)s - %(message)s')
#     logging.critical(f"КРИТИЧЕСКАЯ ОШИБКА: Не удалось импортировать модуль: {e}.")
#     # Попытка отправить уведомление, если модуль notifications хоть как-то загрузился
#     try:
#         if 'notifications' in sys.modules and hasattr(notifications, 'send_telegram_message'):
#              notifications.send_telegram_message(f"❌ КРИТИЧЕСКАЯ ОШИБКА: Ошибка импорта модулей:\n```\n{e}\n```", is_error=True)
#     except Exception: pass # Молчаливый выход, если даже уведомление не отправить
#     sys.exit(1)
#
# # --- Настройка Логирования ---
# LOG_DIR = getattr(config, 'LOG_DIR', 'logs'); os.makedirs(LOG_DIR, exist_ok=True)
# log_filename = os.path.join(LOG_DIR, f"scraper_{datetime.now().strftime('%Y-%m-%d')}.log")
# log_level_str = getattr(config, 'LOG_LEVEL', 'INFO').upper(); log_level = getattr(logging, log_level_str, logging.INFO)
#
# # Получаем корневой логгер и настраиваем его
# logger = logging.getLogger()
# logger.setLevel(log_level)
#
# # Удаляем стандартные обработчики, если они есть (чтобы избежать дублирования)
# if logger.hasHandlers():
#     logger.handlers.clear()
#
# # Форматтер
# log_formatter = logging.Formatter('%(asctime)s - %(levelname)s - [%(name)s] - [%(filename)s:%(lineno)d] - %(message)s')
#
# # Консольный обработчик
# console_handler = logging.StreamHandler(sys.stdout)
# console_handler.setFormatter(log_formatter)
# console_handler.setLevel(log_level) # Устанавливаем уровень и для обработчика
# logger.addHandler(console_handler)
#
# # Файловый обработчик (ротируемый)
# file_handler = logging.handlers.RotatingFileHandler(log_filename, maxBytes=5*1024*1024, backupCount=3, encoding='utf-8')
# file_handler.setFormatter(log_formatter)
# file_handler.setLevel(log_level) # Устанавливаем уровень и для обработчика
# logger.addHandler(file_handler)
#
# logger.info(f"Логгер инициализирован: Уровень={log_level_str}, Файл={log_filename}")
#
# # Подавление логов от библиотек
# logging.getLogger("urllib3").setLevel(logging.WARNING)
# logging.getLogger("selenium").setLevel(logging.WARNING)
# logging.getLogger("schedule").setLevel(logging.INFO)
# logging.getLogger("filelock").setLevel(logging.WARNING)
#
# # Устанавливаем уровень для наших модулей (если они уже импортированы)
# def setup_module_logging(module_name):
#     if module_name in sys.modules:
#         mod_logger = logging.getLogger(module_name)
#         mod_logger.setLevel(log_level)
#         # Не нужно добавлять обработчики снова, они наследуются от root
#
# setup_module_logging("scraper")
# setup_module_logging("storage")
# setup_module_logging("signals")
# setup_module_logging("notifications")
# setup_module_logging("cycle_analysis")
# setup_module_logging("ohlc_generator")
# setup_module_logging("weekly_stats")
#
#
# # --- Проверка наличия необходимых функций (с новыми именами) ---
# # Теперь проверяем актуальные функции
# required = [
#     (notifications, 'send_telegram_message'), # Основная функция отправки
#     (notifications, 'send_signal_notification'), # Специализированная для сигналов
#     (signals,'check_signals'),
#     (storage,'log_player_data'),
#     (storage,'read_player_history'),
#     (storage,'get_last_known_price'),
#     (config,'load_players'),
#     (cycle_analysis, 'determine_main_cycle_phase_df'),
#     (cycle_analysis, 'determine_short_cycle_phase_df'),
#     (storage, 'save_update_schedule'),
#     (storage, 'load_update_schedule'),
#     (ohlc_generator,'rewrite_ohlc_summary' if hasattr(ohlc_generator,'rewrite_ohlc_summary') else 'generate_daily_ohlc_report'), # Исправлено в 7.5.21/22
#     (weekly_stats, 'generate_weekly_stats_report')
# ]
# missing = False;
# for mod, func_name in required:
#     if not hasattr(mod, func_name):
#         # Используем print, так как логгер может быть еще не полностью настроен
#         print(f"КРИТИЧЕСКАЯ ОШИБКА: Нет необходимой функции {mod.__name__}.{func_name}! Выход.")
#         missing = True
# if missing: sys.exit(1)
#
# # --- Глобальные переменные ---
# PLAYER_UPDATE_INTERVAL = {}; GECKODRIVER_PATH = getattr(config, 'GECKODRIVER_PATH', None); MIN_HISTORY_FOR_SIGNALS = getattr(config, 'MIN_HISTORY_FOR_SIGNALS', 50); REFRESH_BUFFER_SECONDS = getattr(config, 'REFRESH_BUFFER_SECONDS', 15)
# # Версия скрипта
# __version__ = "7.5.23"
#
# # --- Функции WebDriver (без изменений от v7.5.22) ---
# def create_webdriver():
#     logger_wd = logging.getLogger("scraper.webdriver"); logger_wd.debug("Создание WebDriver...")
#     service = None; driver = None
#     try:
#         service_args = ['--log', 'fatal']; log_p = os.path.join(LOG_DIR, "geckodriver.log") if LOG_DIR else "geckodriver.log"; exec_p = None
#         if GECKODRIVER_PATH and os.path.exists(GECKODRIVER_PATH): exec_p = GECKODRIVER_PATH; logger_wd.info(f"Geckodriver: {exec_p}")
#         else: from shutil import which; found = which('geckodriver');
#         if found: exec_p = found; logger_wd.info(f"Geckodriver PATH: {exec_p}")
#         else:
#              logger_wd.error("geckodriver не найден.");
#              # --- ИЗМЕНЕНО v7.5.23: Используем send_telegram_message ---
#              if getattr(config, 'SEND_TELEGRAM_ERRORS', False):
#                   notifications.send_telegram_message("Geckodriver Not Found! Укажите путь в config.py или установите в PATH.", is_error=True)
#              return None
#         service = FirefoxService(executable_path=exec_p, service_args=service_args, log_path=log_p); logger_wd.debug(f"FirefoxService создан. Логи: {log_p}")
#     except Exception as e_service:
#          logger_wd.critical(f"КРИТ. ОШИБКА FirefoxService: {e_service}", exc_info=True)
#          # --- ИЗМЕНЕНО v7.5.23: Используем send_telegram_message ---
#          if getattr(config, 'SEND_TELEGRAM_ERRORS', False):
#               notifications.send_telegram_message(f"WebDriver Service Init Error:\n```\n{traceback.format_exc()}\n```", is_error=True)
#          return None
#     opt = FirefoxOptions(); opt.add_argument("--headless"); opt.add_argument("--disable-gpu"); opt.add_argument("--window-size=1920,1080"); opt.add_argument("--no-sandbox"); opt.add_argument("--disable-dev-shm-usage"); opt.set_preference("permissions.default.image", 2); opt.set_preference("dom.ipc.plugins.enabled.libflashplayer.so", "false"); opt.set_preference("javascript.enabled", True); opt.set_preference("network.cookie.cookieBehavior", 0); opt.set_preference("network.http.connection-timeout", 90); opt.set_preference("network.http.response.timeout", 120); opt.set_preference("dom.max_script_run_time", 90); opt.set_preference("dom.webdriver.enabled", False); opt.set_preference('useAutomationExtension', False); opt.set_preference("general.useragent.override", "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/115.0")
#     logger_wd.info("Запуск Firefox WebDriver...");
#     try:
#         if service is None: logger_wd.error("Service не инициализирован."); return None
#         driver = webdriver.Firefox(service=service, options=opt);
#         # --- ИЗМЕНЕНО v7.5.23: Возвращаем implicitly_wait (как в исправлении) ---
#         driver.implicitly_wait(10);
#         # ------------------------------------
#         driver.set_page_load_timeout(90); driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"); logger_wd.info("WebDriver успешно создан."); return driver
#     except WebDriverException as e:
#         msg = f"WebDriverException при запуске: {e}\n{traceback.format_exc()}"; logger_wd.critical(msg, exc_info=False);
#         # --- ИЗМЕНЕНО v7.5.23: Используем send_telegram_message ---
#         if getattr(config, 'SEND_TELEGRAM_ERRORS', False):
#              notifications.send_telegram_message(f"WebDriver Startup Error (WebDriverException):\n```\n{msg}\n```", is_error=True)
#         return None
#     except Exception as e:
#         logger_wd.critical(f"КРИТ. ОШИБКА WebDriver: {e}", exc_info=True);
#         # --- ИЗМЕНЕНО v7.5.23: Используем send_telegram_message ---
#         if getattr(config, 'SEND_TELEGRAM_ERRORS', False):
#               notifications.send_telegram_message(f"WebDriver Startup Error (Unexpected):\n```\n{traceback.format_exc()}\n```", is_error=True)
#         return None
#
# # --- Функция парсинга (НЕ ТРОНУТА из v7.5.22) ---
# def parse_player_data(driver, player_name, player_url):
#     logger = logging.getLogger("scraper.parser"); logger.info(f"Парсим {player_name} (URL: {player_url})")
#     price_xpath = "//div[contains(@class, 'market-data--key') and normalize-space(.)='Current value']/ancestor::div[contains(@class, 'flex-col')][2]//div[contains(@class, 'market-data--value')][1]/span[1]"
#     change_xpath = "//div[contains(@class, 'market-data--value--change')]//span[contains(text(), '%')]"
#     update_xpath = "//div[contains(text(), 'Market Refresh')]/following-sibling::div[contains(@class, 'market-data--value-mini')]"
#     min_xpath = "//div[contains(text(), 'Market low/high')]/following-sibling::div[contains(@class, 'market-data--value-mini')]//span[1]"
#     max_xpath = "//div[contains(text(), 'Market low/high')]/following-sibling::div[contains(@class, 'market-data--value-mini')]//span[last()]"
#     data = {'timestamp': None, 'price': None, 'change': 'N/A', 'min_order': None, 'max_order': None, 'update_time': 'N/A', 'error': None}
#     html_dump_path = os.path.join(LOG_DIR, f"error_{player_name.replace(' ','_')}_{datetime.now().strftime('%H%M%S')}.html")
#     wait_long = WebDriverWait(driver, 25); wait_short = WebDriverWait(driver, 10)
#     try:
#         start_get = time.time(); logger.debug(f"Загрузка URL: {player_url}"); driver.get(player_url); logger.debug(f"URL загружен: {time.time() - start_get:.2f} сек."); time.sleep(1.5) # Короткая пауза после загрузки
#         start_find_price = time.time(); price = None; raw_price_text = "N/A"
#         try:
#             price_element = wait_long.until(EC.visibility_of_element_located((By.XPATH, price_xpath))); logger.debug(f"Цена найдена: {time.time() - start_find_price:.2f} сек.")
#             raw_price_text = price_element.text.strip(); logger.debug(f"Raw price: '{raw_price_text}'"); cleaned = re.sub(r'[^\d]', '', raw_price_text); price = int(cleaned) if cleaned.isdigit() else None
#             if price is None and raw_price_text not in ["", "-", "N/A"]: logger.warning(f"{player_name}: Не распарсить цену '{raw_price_text}'")
#             elif price == 0 and raw_price_text != '0': logger.warning(f"{player_name} цена 0, текст: '{raw_price_text}'.")
#             data['price'] = price;
#             # Установка low/high на основе цены (будет перезаписано ордерами, если они есть)
#             if price is not None: data['low'] = price; data['high'] = price
#         except TimeoutException: data['error'] = "Таймаут цены"; logger.error(f"{data['error']} ({time.time() - start_find_price:.1f}s) {player_name}")
#         except NoSuchElementException: data['error'] = "Элемент цены не найден"; logger.error(f"{data['error']} {player_name}")
#         except Exception as e: data['error'] = f"Ошибка парсинга цены: {type(e).__name__}"; logger.error(f"{data['error']} {player_name}: {e}", exc_info=True)
#
#         # Парсинг доп. данных (с использованием wait_short)
#         parsing_times = {}
#         start = time.time();
#         try: change_text = wait_short.until(EC.visibility_of_element_located((By.XPATH, change_xpath))).text.strip(); data['change'] = change_text if change_text else "0%"
#         except Exception: data['change'] = "0%"; logger.debug(f"Изменение не найдено {player_name}")
#         parsing_times['change'] = time.time() - start; start = time.time()
#         try: update_text = wait_short.until(EC.visibility_of_element_located((By.XPATH, update_xpath))).text.strip(); data['update_time'] = update_text if update_text else "N/A"
#         except Exception: data['update_time'] = "N/A"; logger.warning(f"Обновление не найдено {player_name}")
#         parsing_times['update'] = time.time() - start; min_v, max_v = None, None; start = time.time()
#         try:
#             min_raw = wait_short.until(EC.visibility_of_element_located((By.XPATH, min_xpath))).text.strip(); min_clean = re.sub(r'[^\d]', '', min_raw); min_v = int(min_clean) if min_clean.isdigit() else None; data['min_order'] = min_v
#             if min_v is not None and data.get('low') is not None: data['low'] = min_v # Обновляем low, если min ордер валиден
#         except (TimeoutException, NoSuchElementException, StaleElementReferenceException): logger.debug(f"Min ордер не найден {player_name}")
#         except Exception as e: logger.warning(f"Ошибка парсинга Min цены: {e}")
#         parsing_times['min'] = time.time() - start; start = time.time()
#         try:
#             max_raw = wait_short.until(EC.visibility_of_element_located((By.XPATH, max_xpath))).text.strip(); max_clean = re.sub(r'[^\d]', '', max_raw); max_v = int(max_clean) if max_clean.isdigit() else None; data['max_order'] = max_v
#             if max_v is not None and data.get('high') is not None: data['high'] = max_v # Обновляем high, если max ордер валиден
#         except (TimeoutException, NoSuchElementException, StaleElementReferenceException): logging.debug(f"Max ордер не найден {player_name}")
#         except Exception as e: logging.warning(f"Ошибка парсинга Max цены: {e}")
#         parsing_times['max'] = time.time() - start; logger.debug(f"Время доп: {parsing_times}")
#
#         # Формирование строки ордеров и timestamp
#         min_f = storage.format_price(min_v) if min_v is not None else "N/A"; max_f = storage.format_price(max_v) if max_v is not None else "N/A"
#         data['orders'] = f"Min: {min_f} / Max: {max_f}"; data['timestamp'] = datetime.now(timezone.utc).isoformat()
#
#         # Проверка и логирование ошибок / успеха
#         if data.get('price') is None and not data.get('error'):
#              data['error'] = "Цена не найдена/распознана"; logger.error(f"{player_name}: {data['error']}")
#              # Сохранение HTML при ошибке цены
#              try:
#                  with open(html_dump_path, "w", encoding="utf-8") as f: f.write(driver.page_source)
#                  logger.info(f"HTML сохранен (ошибка цены): {html_dump_path}")
#              except Exception as dump_err: logger.error(f"Не сохранить HTML (ошибка цены): {dump_err}")
#         elif data.get('error'):
#              logger.error(f"Завершено с ошибкой {player_name}: {data['error']}")
#              # Сохранение HTML при других ошибках парсинга
#              try:
#                  with open(html_dump_path, "w", encoding="utf-8") as f: f.write(driver.page_source)
#                  logger.info(f"HTML сохранен (ошибка '{data['error']}'): {html_dump_path}")
#              except Exception as dump_err: logger.error(f"Не сохранить HTML (ошибка): {dump_err}")
#         else: # Успех
#              data['error'] = None; price_f = storage.format_price(data['price']); logger.info(f"Успешно {player_name}: Цена={price_f} Изм='{data['change']}' Ордера='{data['orders']}' Обн='{data['update_time']}'")
#         return data # Возвращаем данные (с ключом 'error' или без него)
#
#     except WebDriverException as e: # Ошибка на уровне WebDriver (например, браузер упал)
#         logger.error(f"WebDriverException во время парсинга {player_name}: {e}");
#         raise e # Передаем исключение выше для перезапуска драйвера
#     except Exception as e: # Любая другая неожиданная ошибка
#         error_type = type(e).__name__; logger.error(f"Неожиданная ошибка парсинга {player_name}: {e}", exc_info=True); data['error'] = f"Unexpected: {error_type}"
#         # Сохранение HTML при неожиданной ошибке
#         try:
#             if driver and hasattr(driver, 'page_source'):
#                 with open(html_dump_path, "w", encoding="utf-8") as f: f.write(driver.page_source)
#                 logger.info(f"HTML сохранен (unexpected error {error_type}): {html_dump_path}")
#         except Exception as dump_err: logger.error(f"Не сохранить HTML (unexpected error): {dump_err}")
#         return data # Возвращаем словарь с ошибкой
#
# # --- ФУНКЦИЯ ПАРСИНГА ВРЕМЕНИ (без изменений от v7.5.22) ---
# def parse_refresh_time(refresh_string):
#     """Парсит строку времени обновления (включая секунды) и возвращает timedelta."""
#     logger = logging.getLogger("scraper.parser"); s=0; m=0; h=0; refresh_string = (refresh_string or "").lower()
#     if 'now' in refresh_string or 'сейчас' in refresh_string: return timedelta(seconds=5)
#     if 'soon' in refresh_string: return timedelta(seconds=45)
#     hm = re.search(r'(\d+)\s*(h|hr|ч)', refresh_string);
#     if hm:
#         try: h = int(hm.group(1))
#         except ValueError: pass
#     mm = re.search(r'(\d+)\s*(m|min|мин)', refresh_string);
#     if mm:
#         try: m = int(mm.group(1))
#         except ValueError: pass
#     sm = re.search(r'(\d+)\s*(s|sec|с|сек)', refresh_string);
#     if sm:
#         try: s = int(sm.group(1))
#         except ValueError: pass
#     if h==0 and m==0 and s==0: di = getattr(config,'DEFAULT_REFRESH_INTERVAL_MINUTES',15); logger.warning(f"Не распознать '{refresh_string}'. Интервал:{di}m."); return timedelta(minutes=di)
#     return timedelta(hours=h, minutes=m, seconds=s)
# # ----------------------------------------------------
#
# # --- Основной цикл обработки игроков ---
# def fetch_all_players(players_config, initial_update_interval):
#     global PLAYER_UPDATE_INTERVAL; logger = logging.getLogger("scraper.fetch"); PLAYER_UPDATE_INTERVAL = initial_update_interval
#     logger.info(f"Запуск основного цикла с {len(PLAYER_UPDATE_INTERVAL)} записями расписания.")
#     pl_keys = list(players_config.keys()) # Список имен игроков из конфига
#     if not pl_keys: logger.warning("Список игроков в конфигурации пуст."); return None
#     driver = None; run_count = 0
#     try:
#         while True:
#             # 1. Получение/Проверка WebDriver
#             if driver is None:
#                 start_creation = time.time()
#                 logger.info("Попытка создания/пересоздания WebDriver...")
#                 driver = create_webdriver();
#                 if driver is None:
#                     logger.critical(f"Не удалось создать WebDriver. Пауза 5 минут...")
#                     time.sleep(300); continue # Пробуем снова через 5 минут
#                 else: logger.info(f"WebDriver создан/пересоздан за {time.time() - start_creation:.1f}s.")
#
#             # 2. Определение следующего игрока и времени ожидания
#             now = datetime.now(timezone.utc); next_player = None; min_scheduled_time = None; wait_seconds = 60 # По умолчанию ждем минуту, если нет игроков
#
#             # Создаем актуальный словарь расписания только для игроков из конфига
#             active_schedule = {p: t for p, t in PLAYER_UPDATE_INTERVAL.items() if p in pl_keys}
#
#             if not active_schedule:
#                  logger.warning("Нет активных игроков в расписании. Проверка через 60с.")
#             else:
#                 ready_players = {p: t for p, t in active_schedule.items() if t is None or t <= now}
#                 future_players = {p: t for p, t in active_schedule.items() if t and t > now}
#
#                 if ready_players:
#                     # Выбираем самого "просроченного" из готовых
#                     next_player = min(ready_players, key=lambda p: ready_players[p] if ready_players[p] else now - timedelta(days=1)) # Даем приоритет тем, у кого None или самое раннее время
#                     min_scheduled_time = ready_players[next_player]
#                     wait_seconds = 0 # Готов сейчас
#                     logger.info(f"Игрок {next_player} готов к немедленному обновлению.")
#                 elif future_players:
#                     # Выбираем ближайшего в будущем
#                     next_player = min(future_players, key=future_players.get)
#                     min_scheduled_time = future_players[next_player]
#                     wait_seconds = max(0, (min_scheduled_time - now).total_seconds())
#                 else: # Сюда не должны попадать, если active_schedule не пуст
#                      logger.error("Не удалось определить следующего игрока! Пауза 5м."); time.sleep(300); continue
#
#             # 3. Ожидание (если нужно)
#             if wait_seconds > 0:
#                  t_str = min_scheduled_time.strftime('%H:%M:%S %Z') if min_scheduled_time else "N/A"; p_str = f" ({next_player})" if next_player else ""; logger.info(f"След:{p_str} ~{t_str}. Ждем ~{int(wait_seconds)}s...")
#                  # Ожидаем, проверяя schedule каждые 0.5 сек
#                  start_wait = time.time()
#                  while time.time() - start_wait < wait_seconds:
#                      schedule.run_pending(); time.sleep(0.5)
#                  logger.debug("Ожидание завершено.")
#
#             # 4. Обработка выбранного игрока
#             run_count += 1
#             current_player_to_process = next_player # Игрок, которого выбрали для обработки
#             if not current_player_to_process or current_player_to_process not in players_config:
#                  logger.warning(f"Пропуск итерации: игрок '{current_player_to_process}' не найден или некорректен.")
#                  # Если игрок был в расписании, но не в конфиге, удалим его из расписания
#                  if current_player_to_process in PLAYER_UPDATE_INTERVAL:
#                       del PLAYER_UPDATE_INTERVAL[current_player_to_process]
#                  time.sleep(5); continue # Короткая пауза перед следующей итерацией
#
#             player_name = current_player_to_process
#             player_info = players_config[player_name]
#             player_url = player_info.get("url")
#             logger.info(f"Обработка #{run_count}: {player_name}")
#             start_process_time = time.time()
#
#             if not player_url:
#                 logger.warning(f"Нет URL для {player_name}. Установка интервала в 1 час."); PLAYER_UPDATE_INTERVAL[player_name] = now + timedelta(hours=1); continue
#
#             # Парсинг данных
#             parsed_data = None
#             try:
#                 parsed_data = parse_player_data(driver, player_name, player_url) # Логика парсинга НЕ ТРОНУТА
#             except WebDriverException as e:
#                  logger.error(f"WebDriverException при обработке {player_name}: {e}", exc_info=False);
#                  # --- ИЗМЕНЕНО v7.5.23: Используем send_telegram_message ---
#                  if getattr(config, 'SEND_TELEGRAM_ERRORS', False):
#                      notifications.send_telegram_message(f"WebDriverException при парсинге *{player_name}*:\n```\n{e}\n```\nПерезапуск WebDriver...", is_error=True, player_name=player_name)
#                  logger.warning("Перезапуск WebDriver из-за ошибки...");
#                  if driver:
#                      try: driver.quit()
#                      except Exception as eq: logger.error(f"Ошибка закрытия WebDriver: {eq}")
#                  driver = None; PLAYER_UPDATE_INTERVAL[player_name] = datetime.now(timezone.utc) + timedelta(minutes=1); # Попробовать снова через минуту
#                  continue # Переходим к следующей итерации для перезапуска драйвера
#             except Exception as e: logger.error(f"Неожиданная ошибка вызова parse_player_data для {player_name}: {e}", exc_info=True); parsed_data = {'error': f"Call Fail: {type(e).__name__}"}
#
#             # Обработка результата парсинга
#             if parsed_data is None or parsed_data.get('error'):
#                 error_msg = parsed_data.get('error','Неизвестная ошибка парсинга') if parsed_data else 'parse_player_data вернул None'
#                 logger.warning(f"Ошибка парсинга {player_name}: {error_msg}. Установка интервала 5 мин."); PLAYER_UPDATE_INTERVAL[player_name] = datetime.now(timezone.utc) + timedelta(minutes=5)
#                 # --- ИЗМЕНЕНО v7.5.23: Используем send_telegram_message ---
#                 if getattr(config, 'SEND_TELEGRAM_ERRORS', False) and "Таймаут цены" not in error_msg: # Не спамим при таймаутах
#                     notifications.send_telegram_message(f"Ошибка парсинга *{player_name}*: {error_msg}", is_warning=True, player_name=player_name)
#             elif parsed_data.get('price') is not None:
#                 # Успешный парсинг с ценой
#                 try: storage.log_player_data(player_name, parsed_data)
#                 except Exception as e_log: logger.error(f"Ошибка сохранения данных для {player_name}: {e_log}", exc_info=True)
#
#                 # Анализ и уведомления
#                 analysis_start_time = time.time(); history_df = None; signal_data = None
#                 try:
#                     history_df = storage.read_player_history(player_name, min_rows=MIN_HISTORY_FOR_SIGNALS)
#                     if history_df is not None and not history_df.empty:
#                         logger.debug(f"[{player_name}] История ({len(history_df)}) прочитана для анализа.")
#                         # Формируем актуальный конфиг для передачи в signals
#                         current_player_config = players_config.get(player_name, {}).copy() # Берем из основного конфига
#                         current_player_config['name'] = player_name # Убедимся, что имя правильное
#                         if 'ovr' not in current_player_config: current_player_config['ovr'] = player_info.get('ovr', 'N/A') # Добавляем OVR, если нет
#
#                         # --- ИЗМЕНЕНО v7.5.23: Передаем parsed_data ---
#                         signal_data = signals.check_signals(history_df, current_player_config, latest_parsed_data=parsed_data)
#                         # -------------------------------------------
#                         logger.debug(f"[{player_name}] Сигналы рассчитаны.")
#                         if signal_data:
#                             # --- ИЗМЕНЕНО v7.5.23: Используем send_signal_notification ---
#                             if signal_data.get('send_notification', False):
#                                 logger.info(f"Отправка уведомления для {player_name} (Сигнал: {signal_data.get('signal')}, Score: {signal_data.get('aggregated_score')})...")
#                                 notifications.send_signal_notification(signal_data)
#                             else: logger.info(f"[{player_name}] Уведомление не требуется. Score: {signal_data.get('aggregated_score', 'N/A'):.2f}")
#                         else: logger.warning(f"[{player_name}] Функция check_signals не вернула результат.")
#                     elif history_df is None: logger.error(f"[{player_name}] Анализ пропущен: ошибка чтения истории.")
#                     else: logger.warning(f"Мало истории ({len(history_df) if history_df is not None else 0}/{MIN_HISTORY_FOR_SIGNALS}) для {player_name}. Анализ пропущен.")
#                 except Exception as e_analysis:
#                     logger.error(f"Ошибка в блоке анализа/уведомлений для {player_name}: {e_analysis}", exc_info=True);
#                     # --- ИЗМЕНЕНО v7.5.23: Используем send_telegram_message ---
#                     if getattr(config, 'SEND_TELEGRAM_ERRORS', False):
#                         notifications.send_telegram_message(f"Ошибка анализа/увед для *{player_name}*:\n```\n{traceback.format_exc()}\n```", is_error=True, player_name=player_name)
#                 logger.debug(f"[{player_name}] Блок анализа и уведомлений: {time.time() - analysis_start_time:.3f}s.")
#
#                 # Установка следующего интервала обновления
#                 refresh_interval_td = parse_refresh_time(parsed_data.get('update_time', 'N/A'))
#                 buffer_seconds = refresh_interval_td.total_seconds() + REFRESH_BUFFER_SECONDS
#                 min_interval_seconds = getattr(config, 'MIN_INTERVAL_SECONDS', 60)
#                 actual_interval_seconds = max(buffer_seconds, min_interval_seconds)
#                 next_update_time = datetime.now(timezone.utc) + timedelta(seconds=actual_interval_seconds)
#                 PLAYER_UPDATE_INTERVAL[player_name] = next_update_time; logger.debug(f"Следующее обновление {player_name}: {next_update_time:%H:%M:%S %Z} (через ~{actual_interval_seconds:.0f}с)")
#             else:
#                 # Цена не найдена после парсинга (но ошибки не было)
#                 logger.error(f"{player_name}: Цена не была найдена (price is None). Установка интервала 15 мин."); PLAYER_UPDATE_INTERVAL[player_name] = datetime.now(timezone.utc) + timedelta(minutes=15)
#
#             logger.info(f"Завершена обработка {player_name}: {time.time() - start_process_time:.2f} сек.")
#
#             # 5. Пауза между игроками
#             pause_duration = getattr(config, 'PAUSE_BETWEEN_PLAYERS', 1.0);
#             if pause_duration > 0: logger.debug(f"Пауза {pause_duration} сек..."); time.sleep(pause_duration)
#
#             # 6. Сохранение расписания (периодически)
#             if run_count % 10 == 0: # Сохраняем каждые 10 итераций
#                  try:
#                      logger.debug("Сохранение расписания...")
#                      storage.save_update_schedule(PLAYER_UPDATE_INTERVAL)
#                  except Exception as e_save:
#                      logger.error(f"Не удалось сохранить расписание: {e_save}")
#
#     except KeyboardInterrupt: logger.info("Получен сигнал KeyboardInterrupt..."); return driver # Возвращаем драйвер для finally
#     except Exception as e_loop:
#         logger.critical(f"Критическая ошибка в главном цикле fetch_all_players: {e_loop}", exc_info=True);
#         # --- ИЗМЕНЕНО v7.5.23: Используем send_telegram_message ---
#         if getattr(config, 'SEND_TELEGRAM_ERRORS', False):
#              notifications.send_telegram_message(f"КРИТИЧЕСКАЯ ОШИБКА в fetch_all_players:\n```\n{traceback.format_exc()}\n```", is_error=True)
#         return driver # Возвращаем драйвер для finally
#     return driver # На всякий случай
#
# # --- Задачи Schedule (используют новые уведомления) ---
# def run_daily_tasks():
#     logger = logging.getLogger("scraper.schedule"); logger.info("--- Daily Tasks Start ---")
#     try:
#         logger.info("Запуск генерации OHLC отчета...")
#         # Используем generate_daily_ohlc_report, если rewrite_ohlc_summary нет
#         ohlc_func = getattr(ohlc_generator, 'rewrite_ohlc_summary', getattr(ohlc_generator, 'generate_daily_ohlc_report', None))
#         if ohlc_func:
#             # Если это generate_daily_ohlc_report, ему нужны имена игроков
#             if ohlc_func.__name__ == 'generate_daily_ohlc_report':
#                  global players # Нужен доступ к глобальному списку игроков
#                  if players: ohlc_func(player_names=list(players.keys()))
#                  else: logger.error("Не могу запустить OHLC: список игроков не загружен.")
#             else: # Для rewrite_ohlc_summary аргументы не нужны
#                  ohlc_func()
#             logger.info("Задача OHLC завершена.")
#         else: logger.error("Не найдена функция для генерации OHLC (rewrite_ohlc_summary или generate_daily_ohlc_report).")
#     except Exception as e:
#         logger.error(f"Ошибка выполнения задачи OHLC: {e}", exc_info=True)
#         # --- ИЗМЕНЕНО v7.5.23: Используем send_telegram_message ---
#         if getattr(config, 'SEND_TELEGRAM_ERRORS', False):
#             notifications.send_telegram_message(f"Ошибка Daily Tasks (OHLC):\n```\n{traceback.format_exc()}\n```", is_error=True)
#     logger.info("--- Daily Tasks End ---")
#
# def run_weekly_tasks():
#     logger = logging.getLogger("scraper.schedule"); logger.info("--- Weekly Tasks Start ---")
#     try:
#         logger.info("Запуск генерации еженедельной статистики...")
#         if hasattr(weekly_stats, 'generate_weekly_stats_report'):
#             weekly_stats.generate_weekly_stats_report(); logger.info("Задача еженедельной статистики завершена.")
#         else: logger.error("Не найдена функция weekly_stats.generate_weekly_stats_report.")
#     except Exception as e:
#         logger.error(f"Ошибка выполнения задачи еженедельной статистики: {e}", exc_info=True)
#         # --- ИЗМЕНЕНО v7.5.23: Используем send_telegram_message ---
#         if getattr(config, 'SEND_TELEGRAM_ERRORS', False):
#             notifications.send_telegram_message(f"Ошибка Weekly Tasks (Stats):\n```\n{traceback.format_exc()}\n```", is_error=True)
#     logger.info("--- Weekly Tasks End ---")
#
# # --- Поток Schedule ---
# def run_schedule_continuously(stop_event):
#     logger = logging.getLogger("scraper.schedule_thread"); logger.info("Поток Schedule запущен.")
#     while not stop_event.is_set():
#         try: schedule.run_pending()
#         except Exception as e: logger.error(f"Ошибка в потоке Schedule: {e}", exc_info=True)
#         # Используем wait с таймаутом, чтобы поток мог быть прерван
#         stop_event.wait(1) # Проверяем каждую секунду
#     logger.info("Поток Schedule остановлен.")
#
# # --- Main ---
# def main():
#     global players # Делаем players доступным для run_daily_tasks
#     driver = None; stop_event = threading.Event(); schedule_thread = None; current_update_interval = {}
#     logger_main = logging.getLogger("scraper.main")
#     logger_wd_final = logging.getLogger("scraper.webdriver") # Отдельный логгер для закрытия
#
#     try:
#         logger_main.info("="*45); logger_main.info(f"[scraper] Старт (v{__version__})"); logger_main.info("="*45)
#         # --- ИЗМЕНЕНО v7.5.23: Используем send_telegram_message ---
#         if getattr(config, 'SEND_TELEGRAM_STARTUP', False):
#             notifications.send_telegram_message(f"🚀 RenderZ Tracker (v{__version__}) запущен!")
#
#         # Настройка Schedule
#         daily_report_time=getattr(config,'DAILY_REPORT_TIME',"09:00")
#         weekly_report_day=getattr(config,'WEEKLY_REPORT_DAY',"sunday")
#         weekly_report_time=getattr(config,'WEEKLY_REPORT_TIME',"10:00")
#         report_timezone=getattr(config,'REPORT_TIMEZONE',"UTC")
#         logger_main.info(f"Настройка ежедневной задачи: {daily_report_time} {report_timezone}")
#         schedule.every().day.at(daily_report_time, report_timezone).do(run_daily_tasks).tag('daily')
#         logger_main.info(f"Настройка еженедельной задачи: {weekly_report_day} {weekly_report_time} {report_timezone}")
#         try:
#             schedule_func = getattr(schedule.every(), weekly_report_day.lower())
#             schedule_func.at(weekly_report_time, report_timezone).do(run_weekly_tasks).tag('weekly')
#         except AttributeError:
#             logger_main.error(f"Неверный день недели '{weekly_report_day}' в конфиге. Используется воскресенье."); schedule.every().sunday.at(weekly_report_time, report_timezone).do(run_weekly_tasks).tag('weekly')
#
#         # # Логирование времени следующих задач
#         # try:
#         #     next_daily = schedule.next_run.strftime('%Y-%m-%d %H:%M:%S %Z') if schedule.next_run else 'N/A' # Общее следующее
#         #     logger_main.info(f"Следующая запланированная задача: {next_daily}")
#         # except Exception as e: logger_main.warning(f"Не удалось получить время следующей задачи: {e}")
#
#         # Логирование времени следующих задач
#         try:
#             # --- ИЗМЕНЕНО v7.5.23 -> v7.5.24: Более надежная проверка next_run ---
#             next_run_time = schedule.next_run # Получаем следующее время
#             next_run_str = 'N/A' # Значение по умолчанию
#
#             if next_run_time is not None:
#                 if isinstance(next_run_time, datetime): # Убедимся, что это datetime
#                     # Добавляем таймзону UTC, если ее нет (schedule может возвращать без tz)
#                     if next_run_time.tzinfo is None:
#                         next_run_time = next_run_time.replace(tzinfo=timezone.utc)
#                     next_run_str = next_run_time.strftime('%Y-%m-%d %H:%M:%S %Z')
#                 else:
#                     # Логируем, если тип не datetime
#                     logger_main.warning(f"schedule.next_run вернул неожиданный тип: {type(next_run_time)}. Не могу отформатировать время.")
#                     next_run_str = 'Неизвестно (ошибка типа)'
#
#             logger_main.info(f"Следующая запланированная задача: {next_run_str}")
#             # -----------------------------------------------------------------
#         except Exception as e:
#             # Логируем любую другую ошибку при получении/форматировании
#              logger_main.warning(f"Не удалось получить/обработать время следующей задачи: {e}", exc_info=True) # Добавляем exc_info для деталей
#
#         # Запуск потока Schedule
#         schedule_thread = threading.Thread(target=run_schedule_continuously, args=(stop_event,), daemon=True); schedule_thread.start(); logger_main.info("Поток Schedule запущен.")
#
#         # Загрузка игроков
#         logger_main.info("Загрузка списка игроков..."); players = config.load_players()
#         if not players:
#              logger_main.critical("Не удалось загрузить список игроков! Завершение работы.")
#              # --- ИЗМЕНЕНО v7.5.23: Используем send_telegram_message ---
#              if getattr(config, 'SEND_TELEGRAM_ERRORS', False):
#                  notifications.send_telegram_message("❌ КРИТИЧЕСКАЯ ОШИБКА: Не удалось загрузить players_config.json!", is_error=True)
#              sys.exit(1)
#         logger_main.info(f"Загружено {len(players)} игроков.")
#
#         # Загрузка и инициализация расписания (Fast Start)
#         logger_main.info("Загрузка сохраненного расписания..."); loaded_interval = storage.load_update_schedule()
#         logger_main.info("Инициализация актуального расписания..."); current_update_interval = {} # Используем новую переменную
#         restored_count, new_count, removed_count = 0, 0, 0; now = datetime.now(timezone.utc)
#
#         # Удаляем из загруженного расписания игроков, которых нет в конфиге
#         loaded_keys = list(loaded_interval.keys())
#         for player_key in loaded_keys:
#              if player_key not in players:
#                  logger_main.warning(f"Игрок '{player_key}' из сохраненного расписания удален (нет в конфиге).")
#                  del loaded_interval[player_key]; removed_count += 1
#
#         # Заполняем актуальное расписание
#         for player_key in players.keys():
#             if player_key in loaded_interval and loaded_interval[player_key] > now:
#                 current_update_interval[player_key] = loaded_interval[player_key]; restored_count += 1
#             else:
#                 if player_key in loaded_interval: # Если был, но время прошло
#                      logger.debug(f"Игрок '{player_key}': сохраненное время истекло, ставим на немедленное обновление.")
#                 else: # Если игрок новый
#                      logger.info(f"Игрок '{player_key}': новый, ставим на немедленное обновление.")
#                 current_update_interval[player_key] = now # Ставим текущее время для немедленного обновления
#                 new_count += 1
#         logger_main.info(f"Инициализация расписания: {restored_count} восстановлено, {new_count} требуют немедленного обновления, {removed_count} удалено.")
#
#         # Уведомление об успешной инициализации
#         try:
#             init_success_message = f"✅ Инициализация RenderZ Tracker (v{__version__}) завершена. Мониторинг ({len(current_update_interval)} игр.). Ожидание обновлений..."
#             notifications.send_telegram_message(init_success_message) # Убрали parse_mode
#             logger_main.info("Уведомление об успешной инициализации отправлено.")
#         except Exception as e_notify_init: logger_main.error(f"Не удалось отправить уведомление об инициализации: {e_notify_init}")
#
#         # Запуск основного цикла обработки
#         logger_main.info("Запуск основного цикла обработки игроков...")
#         driver = fetch_all_players(players, current_update_interval) # Передаем инициализированное расписание
#
#     except KeyboardInterrupt: logger_main.info("Получен сигнал KeyboardInterrupt...")
#     except Exception as e:
#         logger_main.critical(f"КРИТИЧЕСКАЯ ОШИБКА в main(): {e}", exc_info=True);
#         # --- ИЗМЕНЕНО v7.5.23: Используем send_telegram_message ---
#         if getattr(config, 'SEND_TELEGRAM_ERRORS', False):
#              notifications.send_telegram_message(f"КРИТИЧЕСКАЯ ОШИБКА в main():\n```\n{traceback.format_exc()}\n```", is_error=True)
#     finally:
#         logger_main.info("Начало процедуры завершения работы...")
#         # 1. Сохраняем расписание
#         try: logger_main.info("Сохранение актуального расписания..."); storage.save_update_schedule(PLAYER_UPDATE_INTERVAL) # PLAYER_UPDATE_INTERVAL используется в fetch_all_players
#         except Exception as e_save: logger_main.error(f"Не удалось сохранить расписание при выходе: {e_save}")
#
#         # 2. Останавливаем поток Schedule
#         stop_event.set() # Сигнализируем потоку остановиться
#         if schedule_thread and schedule_thread.is_alive():
#             logger_main.info("Ожидание завершения потока Schedule (до 5 секунд)...")
#             schedule_thread.join(timeout=5);
#             if schedule_thread.is_alive(): logger_main.warning("Поток Schedule не завершился за отведенное время.")
#             else: logger_main.info("Поток Schedule успешно завершен.")
#         elif schedule_thread: logger_main.info("Поток Schedule уже был неактивен.")
#         else: logger_main.info("Поток Schedule не был запущен.")
#
#         # 3. Закрываем WebDriver
#         if driver:
#             try: logger_wd_final.info("Закрытие WebDriver..."); driver.quit(); logger_wd_final.info("WebDriver успешно закрыт.")
#             except Exception as e_quit: logger_wd_final.error(f"Ошибка при закрытии WebDriver: {e_quit}", exc_info=True)
#         else: logger_wd_final.warning("Экземпляр WebDriver не найден для закрытия (возможно, была ошибка инициализации).")
#
#         # 4. Отправляем уведомление об остановке
#         # --- ИЗМЕНЕНО v7.5.23: Используем send_telegram_message ---
#         if getattr(config, 'SEND_TELEGRAM_SHUTDOWN', False):
#              notifications.send_telegram_message(f"🛑 RenderZ Tracker (v{__version__}) остановлен.")
#
#         logger_main.info(f"=== RenderZ Tracker (v{__version__}) завершил работу ==="); print("Скрапер остановлен.")
#
# if __name__ == "__main__":
#     main()

# =============================================
# ФАЙЛ: scraper.py (ВЕРСИЯ v7.5.30 - FINAL - parse_player_data RESTORED)
# - ВОССТАНОВЛЕНА: Функция parse_player_data() из v7.5.22.
# - Содержит все обновления вызовов и исправления из v7.5.29.
# - Отступы перепроверены.
# =============================================

import logging
import schedule
import time
import json
import os
import sys
from datetime import datetime, timedelta, timezone
import traceback
import re
import subprocess
from selenium import webdriver
from selenium.webdriver.firefox.service import Service as FirefoxService
from selenium.webdriver.firefox.options import Options as FirefoxOptions
from selenium.common.exceptions import (WebDriverException, TimeoutException,
                                        NoSuchElementException, StaleElementReferenceException)
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import pandas as pd
import threading
import logging.handlers

# --- Импорт пользовательских модулей ---
try:
    import config       # Ожидается v8.19+
    import storage      # Ожидается v6.11+
    import signals      # Ожидается v23.35+
    import notifications # Ожидается v10.17+
    import cycle_analysis # Ожидается v8.9+
    import ohlc_generator # Ожидается v3.3+
    import weekly_stats
    # Убрали зависимость от parser_core
except ImportError as e:
    logging.basicConfig(level=logging.CRITICAL, format='%(asctime)s - %(levelname)s - %(message)s')
    logging.critical(f"КРИТИЧЕСКАЯ ОШИБКА: Не удалось импортировать модуль: {e}.")
    try:
        import notifications as notify_fallback
        if hasattr(notify_fallback, 'send_telegram_message'):
             notify_fallback.send_telegram_message(f"❌ КРИТИЧЕСКАЯ ОШИБКА: Ошибка импорта модулей:\n```\n{e}\n```", is_error=True)
    except Exception: pass
    sys.exit(1)
except Exception as e_import_generic:
     logging.basicConfig(level=logging.CRITICAL, format='%(asctime)s - %(levelname)s - %(message)s')
     logging.critical(f"КРИТИЧЕСКАЯ ОШИБКА при импорте: {e_import_generic}.")
     sys.exit(1)


# --- Настройка Логирования ---
LOG_DIR = getattr(config, 'LOG_DIR', 'logs'); os.makedirs(LOG_DIR, exist_ok=True)
log_filename = os.path.join(LOG_DIR, f"scraper_{datetime.now().strftime('%Y-%m-%d')}.log")
log_level_str = getattr(config, 'LOG_LEVEL', 'INFO').upper(); log_level = getattr(logging, log_level_str, logging.INFO)
logger = logging.getLogger(); logger.setLevel(log_level)
if logger.hasHandlers(): logger.handlers.clear()
log_formatter = logging.Formatter('%(asctime)s - %(levelname)s - [%(name)s] - [%(filename)s:%(lineno)d] - %(message)s')
console_handler = logging.StreamHandler(sys.stdout); console_handler.setFormatter(log_formatter); console_handler.setLevel(log_level); logger.addHandler(console_handler)
file_handler = logging.handlers.RotatingFileHandler(log_filename, maxBytes=5*1024*1024, backupCount=3, encoding='utf-8'); file_handler.setFormatter(log_formatter); file_handler.setLevel(log_level); logger.addHandler(file_handler)
logger.info(f"Логгер инициализирован: Уровень={log_level_str}, Файл={log_filename}")
logging.getLogger("urllib3").setLevel(logging.WARNING); logging.getLogger("selenium").setLevel(logging.WARNING); logging.getLogger("schedule").setLevel(logging.INFO); logging.getLogger("filelock").setLevel(logging.WARNING)
def setup_module_logging(module_name):
    if module_name in sys.modules: logging.getLogger(module_name).setLevel(log_level)
setup_module_logging("scraper"); setup_module_logging("storage"); setup_module_logging("signals"); setup_module_logging("notifications"); setup_module_logging("cycle_analysis"); setup_module_logging("ohlc_generator"); setup_module_logging("weekly_stats")
# setup_module_logging("parser_core") # Убрали

# --- Глобальные переменные ---
players = None
PLAYER_UPDATE_INTERVAL = {}; GECKODRIVER_PATH = getattr(config, 'GECKODRIVER_PATH', None); MIN_HISTORY_FOR_SIGNALS = getattr(config, 'MIN_HISTORY_FOR_SIGNALS', 50); REFRESH_BUFFER_SECONDS = getattr(config, 'REFRESH_BUFFER_SECONDS', 15)
NOTIFICATION_STATE = {}
__version__ = "7.5.30" # Восстановлена parse_player_data

# --- Функции WebDriver ---
def create_webdriver():
    logger_wd = logging.getLogger("scraper.webdriver"); logger_wd.debug("Создание WebDriver...")
    service = None; driver = None
    try:
        service_args = ['--log', 'fatal']; log_p = os.path.join(LOG_DIR, "geckodriver.log") if LOG_DIR else "geckodriver.log"; exec_p = None
        if GECKODRIVER_PATH and os.path.exists(GECKODRIVER_PATH): exec_p = GECKODRIVER_PATH; logger_wd.info(f"Geckodriver: {exec_p}")
        else: from shutil import which; found = which('geckodriver');
        if found: exec_p = found; logger_wd.info(f"Geckodriver PATH: {exec_p}")
        else:
            logger_wd.error("geckodriver не найден.");
            if getattr(config, 'SEND_TELEGRAM_ERRORS', False): notifications.send_telegram_message("Geckodriver Not Found!", is_error=True)
            return None
        service = FirefoxService(executable_path=exec_p, service_args=service_args, log_path=log_p); logger_wd.debug(f"FirefoxService создан. Логи: {log_p}")
    except Exception as e_service:
        logger_wd.critical(f"КРИТ. ОШИБКА FirefoxService: {e_service}", exc_info=True)
        if getattr(config, 'SEND_TELEGRAM_ERRORS', False): notifications.send_telegram_message(f"WebDriver Service Init Error:\n```\n{traceback.format_exc()}\n```", is_error=True)
        return None
    opt = FirefoxOptions(); opt.add_argument("--headless"); opt.add_argument("--disable-gpu"); opt.add_argument("--window-size=1920,1080"); opt.add_argument("--no-sandbox"); opt.add_argument("--disable-dev-shm-usage"); opt.set_preference("permissions.default.image", 2); opt.set_preference("dom.ipc.plugins.enabled.libflashplayer.so", "false"); opt.set_preference("javascript.enabled", True); opt.set_preference("network.cookie.cookieBehavior", 0); opt.set_preference("network.http.connection-timeout", 90); opt.set_preference("network.http.response.timeout", 120); opt.set_preference("dom.max_script_run_time", 90); opt.set_preference("dom.webdriver.enabled", False); opt.set_preference('useAutomationExtension', False); opt.set_preference("general.useragent.override", "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/115.0")
    logger_wd.info("Запуск Firefox WebDriver...");
    try:
        if service is None: logger_wd.error("Service не инициализирован."); return None
        driver = webdriver.Firefox(service=service, options=opt);
        driver.implicitly_wait(10); # Возвращено из v7.5.22
        driver.set_page_load_timeout(90); driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"); logger_wd.info("WebDriver успешно создан."); return driver
    except WebDriverException as e:
        msg = f"WebDriverException при запуске: {e}"; logger_wd.critical(msg, exc_info=False);
        if getattr(config, 'SEND_TELEGRAM_ERRORS', False): notifications.send_telegram_message(f"WebDriver Startup Error (WebDriverException):\n```\n{e}\n{traceback.format_exc()}\n```", is_error=True)
        return None
    except Exception as e:
        logger_wd.critical(f"КРИТ. ОШИБКА WebDriver: {e}", exc_info=True);
        if getattr(config, 'SEND_TELEGRAM_ERRORS', False): notifications.send_telegram_message(f"WebDriver Startup Error (Unexpected):\n```\n{traceback.format_exc()}\n```", is_error=True)
        return None

def get_webdriver(driver_instance):
    webdriver_ok = False
    if driver_instance:
        try:
            _ = driver_instance.current_url
            webdriver_ok = True
            logger.debug("WebDriver активен.")
        except WebDriverException as e:
            logger.warning(f"WebDriver не отвечает ({type(e).__name__}). Переинициализация...")
            webdriver_ok = False
        except Exception as e:
            logger.warning(f"Неожиданная ошибка проверки WebDriver ({e}). Переинициализация...")
            webdriver_ok = False

    if not webdriver_ok:
        logger.info("WebDriver не инициализирован или недоступен. Попытка инициализации...")
        if driver_instance:
            try: driver_instance.quit()
            except Exception as e_quit: logger.warning(f"Ошибка при закрытии не отвечающего WebDriver: {e_quit}")
        driver_instance = create_webdriver()

    return driver_instance

# --- ВОССТАНОВЛЕНА Функция парсинга из v7.5.22 ---
def parse_player_data(driver, player_name, player_url):
    logger = logging.getLogger("scraper.parser"); logger.info(f"Парсим {player_name} (URL: {player_url})")
    price_xpath = "//div[contains(@class, 'market-data--key') and normalize-space(.)='Current value']/ancestor::div[contains(@class, 'flex-col')][2]//div[contains(@class, 'market-data--value')][1]/span[1]"
    change_xpath = "//div[contains(@class, 'market-data--value--change')]//span[contains(text(), '%')]"
    update_xpath = "//div[contains(text(), 'Market Refresh')]/following-sibling::div[contains(@class, 'market-data--value-mini')]"
    min_xpath = "//div[contains(text(), 'Market low/high')]/following-sibling::div[contains(@class, 'market-data--value-mini')]//span[1]"
    max_xpath = "//div[contains(text(), 'Market low/high')]/following-sibling::div[contains(@class, 'market-data--value-mini')]//span[last()]"
    data = {'timestamp': None, 'price': None, 'change': 'N/A', 'min_order': None, 'max_order': None, 'update_time': 'N/A', 'error': None}
    html_dump_path = os.path.join(LOG_DIR, f"error_{player_name.replace(' ','_')}_{datetime.now().strftime('%H%M%S')}.html")
    wait_long = WebDriverWait(driver, 25); wait_short = WebDriverWait(driver, 10)
    try:
        start_get = time.time(); logger.debug(f"Загрузка URL: {player_url}"); driver.get(player_url); logger.debug(f"URL загружен: {time.time() - start_get:.2f} сек."); time.sleep(1.5) # Пауза после загрузки
        start_find_price = time.time(); price = None; raw_price_text = "N/A"
        try:
            price_element = wait_long.until(EC.visibility_of_element_located((By.XPATH, price_xpath))); logger.debug(f"Цена найдена: {time.time() - start_find_price:.2f} сек.")
            raw_price_text = price_element.text.strip(); logger.debug(f"Raw price: '{raw_price_text}'"); cleaned = re.sub(r'[^\d]', '', raw_price_text); price = int(cleaned) if cleaned.isdigit() else None
            if price is None and raw_price_text not in ["", "-", "N/A"]: logger.warning(f"{player_name}: Не распарсить цену '{raw_price_text}'")
            elif price == 0 and raw_price_text != '0': logger.warning(f"{player_name} цена 0, текст: '{raw_price_text}'.")
            data['price'] = price;
            if price is not None: data['low'] = price; data['high'] = price
        except TimeoutException: data['error'] = "Таймаут цены"; logger.error(f"{data['error']} ({time.time() - start_find_price:.1f}s) {player_name}")
        except NoSuchElementException: data['error'] = "Элемент цены не найден"; logger.error(f"{data['error']} {player_name}")
        except Exception as e: data['error'] = f"Ошибка парсинга цены: {type(e).__name__}"; logger.error(f"{data['error']} {player_name}: {e}", exc_info=True)

        parsing_times = {}
        start = time.time();
        try: change_text = wait_short.until(EC.visibility_of_element_located((By.XPATH, change_xpath))).text.strip(); data['change'] = change_text if change_text else "0%"
        except Exception: data['change'] = "0%"; logger.debug(f"Изменение не найдено {player_name}")
        parsing_times['change'] = time.time() - start; start = time.time()
        try: update_text = wait_short.until(EC.visibility_of_element_located((By.XPATH, update_xpath))).text.strip(); data['update_time'] = update_text if update_text else "N/A"
        except Exception: data['update_time'] = "N/A"; logger.warning(f"Обновление не найдено {player_name}")
        parsing_times['update'] = time.time() - start; min_v, max_v = None, None; start = time.time()
        try:
            min_raw = wait_short.until(EC.visibility_of_element_located((By.XPATH, min_xpath))).text.strip(); min_clean = re.sub(r'[^\d]', '', min_raw); min_v = int(min_clean) if min_clean.isdigit() else None; data['min_order'] = min_v
            if min_v is not None and data.get('low') is not None: data['low'] = min_v
        except (TimeoutException, NoSuchElementException, StaleElementReferenceException): logger.debug(f"Min ордер не найден {player_name}")
        except Exception as e: logger.warning(f"Ошибка парсинга Min цены: {e}")
        parsing_times['min'] = time.time() - start; start = time.time()
        try:
            max_raw = wait_short.until(EC.visibility_of_element_located((By.XPATH, max_xpath))).text.strip(); max_clean = re.sub(r'[^\d]', '', max_raw); max_v = int(max_clean) if max_clean.isdigit() else None; data['max_order'] = max_v
            if max_v is not None and data.get('high') is not None: data['high'] = max_v
        except (TimeoutException, NoSuchElementException, StaleElementReferenceException): logging.debug(f"Max ордер не найден {player_name}")
        except Exception as e: logging.warning(f"Ошибка парсинга Max цены: {e}")
        parsing_times['max'] = time.time() - start; logger.debug(f"Время доп: {parsing_times}")

        min_f = storage.format_price(min_v) if min_v is not None else "N/A"; max_f = storage.format_price(max_v) if max_v is not None else "N/A"
        data['orders'] = f"Min: {min_f} / Max: {max_f}"; data['timestamp'] = datetime.now(timezone.utc).isoformat()

        if data.get('price') is None and not data.get('error'):
             data['error'] = "Цена не найдена/распознана"; logger.error(f"{player_name}: {data['error']}")
             try:
                 with open(html_dump_path, "w", encoding="utf-8") as f: f.write(driver.page_source)
                 logger.info(f"HTML сохранен (ошибка цены): {html_dump_path}")
             except Exception as dump_err: logger.error(f"Не сохранить HTML (ошибка цены): {dump_err}")
        elif data.get('error'):
             logger.error(f"Завершено с ошибкой {player_name}: {data['error']}")
             try:
                 with open(html_dump_path, "w", encoding="utf-8") as f: f.write(driver.page_source)
                 logger.info(f"HTML сохранен (ошибка '{data['error']}'): {html_dump_path}")
             except Exception as dump_err: logger.error(f"Не сохранить HTML (ошибка): {dump_err}")
        else:
             data['error'] = None; price_f = storage.format_price(data['price']); logger.info(f"Успешно {player_name}: Цена={price_f} Изм='{data['change']}' Ордера='{data['orders']}' Обн='{data['update_time']}'")
        return data
    except WebDriverException as e:
        logger.error(f"WebDriverException во время парсинга {player_name}: {e}");
        raise e
    except Exception as e:
        error_type = type(e).__name__; logger.error(f"Неожиданная ошибка парсинга {player_name}: {e}", exc_info=True); data['error'] = f"Unexpected: {error_type}"
        try:
            if driver and hasattr(driver, 'page_source'):
                with open(html_dump_path, "w", encoding="utf-8") as f: f.write(driver.page_source)
                logger.info(f"HTML сохранен (unexpected error {error_type}): {html_dump_path}")
        except Exception as dump_err: logger.error(f"Не сохранить HTML (unexpected error): {dump_err}")
        return data
# ---------------------------------------------------

# --- Функция парсинга времени ---
def parse_refresh_time(refresh_string):
    logger = logging.getLogger("scraper.parser"); s=0; m=0; h=0; refresh_string = (refresh_string or "").lower()
    if 'now' in refresh_string or 'сейчас' in refresh_string: return timedelta(seconds=5)
    if 'soon' in refresh_string: return timedelta(seconds=45)
    hm = re.search(r'(\d+)\s*(h|hr|ч)', refresh_string);
    if hm:
        try: h = int(hm.group(1))
        except ValueError: pass
    mm = re.search(r'(\d+)\s*(m|min|мин)', refresh_string);
    if mm:
        try: m = int(mm.group(1))
        except ValueError: pass
    sm = re.search(r'(\d+)\s*(s|sec|с|сек)', refresh_string);
    if sm:
        try: s = int(sm.group(1))
        except ValueError: pass
    if h==0 and m==0 and s==0: di = getattr(config,'DEFAULT_REFRESH_INTERVAL_MINUTES',15); logger.warning(f"Не распознать '{refresh_string}'. Интервал:{di}m."); return timedelta(minutes=di)
    return timedelta(hours=h, minutes=m, seconds=s)

# --- Основной цикл обработки игроков ---
def fetch_all_players(players_config, initial_update_interval, initial_notification_state, stop_event):
    global PLAYER_UPDATE_INTERVAL, NOTIFICATION_STATE
    logger = logging.getLogger("scraper.fetch");
    PLAYER_UPDATE_INTERVAL = initial_update_interval
    NOTIFICATION_STATE = initial_notification_state
    logger.info(f"Запуск основного цикла. Игроков: {len(PLAYER_UPDATE_INTERVAL)}, Состояний: {len(NOTIFICATION_STATE)}")
    pl_keys = list(players_config.keys()); run_count = 0
    driver = None

    try:
        while True:
            driver = get_webdriver(driver)
            if not driver:
                logger.critical(f"Не удалось создать/получить WebDriver. Пауза 5 минут...")
                if stop_event.wait(300):
                     logger.info("Получен сигнал остановки во время паузы WebDriver.")
                     raise KeyboardInterrupt("Остановка во время паузы WebDriver")
                continue

            now = datetime.now(timezone.utc); next_player = None; min_scheduled_time = None; wait_seconds = 60
            active_schedule = {p: t for p, t in PLAYER_UPDATE_INTERVAL.items() if p in pl_keys}
            if not active_schedule: logger.warning("Нет активных игроков. Проверка через 60с."); time.sleep(60); continue
            else:
                ready_players = {p: t for p, t in active_schedule.items() if t is None or t <= now}
                future_players = {p: t for p, t in active_schedule.items() if t and t > now}
                if ready_players: next_player = min(ready_players, key=lambda p: ready_players[p] if ready_players[p] else now - timedelta(days=1)); min_scheduled_time = ready_players.get(next_player); wait_seconds = 0; logger.info(f"Игрок {next_player} готов.")
                elif future_players: next_player = min(future_players, key=future_players.get); min_scheduled_time = future_players[next_player]; wait_seconds = max(0, (min_scheduled_time - now).total_seconds())
                else: logger.error("Не определить следующего игрока! Пауза 5м."); time.sleep(300); continue

            if wait_seconds > 0:
                min_interval_seconds = getattr(config, 'MIN_INTERVAL_SECONDS', 60)
                if wait_seconds < min_interval_seconds:
                    logger.warning(f"Расчетное ожидание {wait_seconds:.1f}с < минимума {min_interval_seconds}с. Установка минимума.")
                    wait_seconds = min_interval_seconds
                t_str = min_scheduled_time.strftime('%H:%M:%S %Z') if min_scheduled_time else "N/A"; p_str = f" ({next_player})" if next_player else ""; logger.info(f"След:{p_str} ~{t_str}. Ждем ~{int(wait_seconds)}s...")
                sleep_interval = 10
                start_wait = time.time()
                while time.time() - start_wait < wait_seconds:
                    check_interval = min(sleep_interval, wait_seconds - (time.time() - start_wait))
                    if check_interval <= 0: break
                    schedule.run_pending();
                    if stop_event.wait(check_interval):
                        logger.info("Получен сигнал остановки во время ожидания.")
                        raise KeyboardInterrupt("Остановка во время ожидания")
                logger.debug("Ожидание завершено.")

            run_count += 1
            current_player_to_process = next_player
            if not current_player_to_process or current_player_to_process not in players_config:
                logger.warning(f"Пропуск: игрок '{current_player_to_process}' не найден/некорректен.")
                if current_player_to_process in PLAYER_UPDATE_INTERVAL: del PLAYER_UPDATE_INTERVAL[current_player_to_process]
                if current_player_to_process in NOTIFICATION_STATE: del NOTIFICATION_STATE[current_player_to_process]
                time.sleep(1); continue

            player_name = current_player_to_process; player_info = players_config[player_name]; player_url = player_info.get("url")
            logger.info(f"Обработка #{run_count}: {player_name}")
            start_process_time = time.time()
            if not player_url: logger.warning(f"Нет URL для {player_name}. Интервал 1 час."); PLAYER_UPDATE_INTERVAL[player_name] = datetime.now(timezone.utc) + timedelta(hours=1); continue

            if not driver:
                 logger.error(f"[{player_name}] WebDriver недоступен ПЕРЕД ПАРСИНГОМ! Повтор через 5 мин.")
                 PLAYER_UPDATE_INTERVAL[player_name] = datetime.now(timezone.utc) + timedelta(minutes=5)
                 continue

            parsed_data = None
            try:
                # --- ИЗМЕНЕНО v7.5.30: Используем встроенную функцию ---
                parsed_data = parse_player_data(driver, player_name, player_url)
            except WebDriverException as e:
                logger.error(f"WebDriverException при обработке {player_name}: {e}", exc_info=False);
                if getattr(config, 'SEND_TELEGRAM_ERRORS', False): notifications.send_telegram_message(f"WebDriverException при парсинге *{player_name}*:\n```\n{e}\n```\nПерезапуск WebDriver...", is_error=True, player_name=player_name)
                logger.warning("Перезапуск WebDriver...");
                if driver:
                    try: driver.quit()
                    except Exception as eq: logger.error(f"Ошибка закрытия WebDriver: {eq}")
                driver = None
                PLAYER_UPDATE_INTERVAL[player_name] = datetime.now(timezone.utc) + timedelta(minutes=1);
                continue
            except Exception as e:
                logger.error(f"Ошибка вызова parse_player_data для {player_name}: {e}", exc_info=True); parsed_data = {'error': f"Call Fail: {type(e).__name__}"}

            # Анализ и Уведомления
            if parsed_data is None or parsed_data.get('error'):
                error_msg = parsed_data.get('error','Unknown Parsing Error') if parsed_data else 'parse_player_data returned None'
                logger.warning(f"Ошибка парсинга {player_name}: {error_msg}. Интервал 5 мин."); PLAYER_UPDATE_INTERVAL[player_name] = datetime.now(timezone.utc) + timedelta(minutes=5)
                if getattr(config, 'SEND_TELEGRAM_ERRORS', False) and "Таймаут" not in error_msg:
                     notifications.send_telegram_message(f"Ошибка парсинга *{player_name}*: {error_msg}", is_warning=True, player_name=player_name)
            elif parsed_data.get('price') is not None or parsed_data.get('min_order') is not None:
                try:
                    storage.log_player_data(player_name, parsed_data)
                except Exception as e_log:
                    logger.error(f"Ошибка сохранения {player_name}: {e_log}", exc_info=True)

                analysis_start_time = time.time(); history_df = None; signal_data = None; new_notification_state = {}
                try:
                    history_df = storage.read_player_history(player_name, min_rows=MIN_HISTORY_FOR_SIGNALS)
                    if history_df is not None and not history_df.empty:
                        logger.debug(f"[{player_name}] История ({len(history_df)}) прочитана.")
                        current_player_config = players_config.get(player_name, {}).copy(); current_player_config['name'] = player_name;
                        if 'ovr' not in current_player_config: current_player_config['ovr'] = player_info.get('ovr', 'N/A')

                        signal_data, new_notification_state = signals.check_signals(
                            history_df,
                            current_player_config,
                            latest_parsed_data=parsed_data,
                            last_notification_state=NOTIFICATION_STATE
                        )
                        NOTIFICATION_STATE = new_notification_state
                        logger.debug(f"[{player_name}] Сигналы рассчитаны.")
                        if signal_data and signal_data.get('send_notification', False):
                            logger.info(f"Отправка увед {player_name} (Сигнал: {signal_data.get('signal')}, Score: {signal_data.get('aggregated_score')})...")
                            notifications.send_signal_notification(signal_data)
                        elif signal_data:
                            logger.info(f"[{player_name}] Увед не требуется. Score: {signal_data.get('aggregated_score', 'N/A'):.2f}")
                        else:
                            logger.warning(f"[{player_name}] check_signals не вернул результат.")
                    elif history_df is None:
                        logger.error(f"[{player_name}] Анализ пропущен: ошибка чтения истории.")
                    else:
                        logger.warning(f"Мало истории ({len(history_df) if history_df is not None else 0}/{MIN_HISTORY_FOR_SIGNALS}) для {player_name}.")
                except Exception as e_analysis:
                    logger.error(f"Ошибка анализа/увед {player_name}: {e_analysis}", exc_info=True);
                    if getattr(config, 'SEND_TELEGRAM_ERRORS', False): notifications.send_telegram_message(f"Ошибка анализа/увед *{player_name}*:\n```\n{traceback.format_exc()}\n```", is_error=True, player_name=player_name)
                logger.debug(f"[{player_name}] Блок анализа: {time.time() - analysis_start_time:.3f}s.")

                refresh_interval_td = parse_refresh_time(parsed_data.get('update_time', 'N/A')); buffer_seconds = refresh_interval_td.total_seconds() + REFRESH_BUFFER_SECONDS; min_interval_seconds = getattr(config, 'MIN_INTERVAL_SECONDS', 60); actual_interval_seconds = max(buffer_seconds, min_interval_seconds); next_update_time = datetime.now(timezone.utc) + timedelta(seconds=actual_interval_seconds); PLAYER_UPDATE_INTERVAL[player_name] = next_update_time; logger.debug(f"След. обн {player_name}: {next_update_time:%H:%M:%S %Z} (~{actual_interval_seconds:.0f}с)")
            else:
                logger.error(f"{player_name}: Цена и Min ордер не найдены. Интервал 15м."); PLAYER_UPDATE_INTERVAL[player_name] = datetime.now(timezone.utc) + timedelta(minutes=15)

            logger.info(f"Завершена обработка {player_name}: {time.time() - start_process_time:.2f} сек.")
            pause_duration = getattr(config, 'PAUSE_BETWEEN_PLAYERS', 1.0);
            if pause_duration > 0: logger.debug(f"Пауза {pause_duration} сек..."); time.sleep(pause_duration)

            if run_count % 10 == 0:
                try:
                    logger.debug("Сохранение расписания и состояния уведомлений..."); storage.save_update_schedule(PLAYER_UPDATE_INTERVAL); storage.save_notification_state(NOTIFICATION_STATE)
                except Exception as e_save:
                    logger.error(f"Не удалось сохранить состояние: {e_save}")

    except KeyboardInterrupt:
        logger.info("Получен сигнал KeyboardInterrupt..."); return driver
    except Exception as e_loop:
        logger.critical(f"Критическая ошибка в fetch_all_players: {e_loop}", exc_info=True);
        if getattr(config, 'SEND_TELEGRAM_ERRORS', False):
            notifications.send_telegram_message(f"КРИТИЧЕСКАЯ ОШИБКА в fetch_all_players:\n```\n{traceback.format_exc()}\n```", is_error=True)
        return driver
    return driver

# --- Задачи Schedule ---
def run_daily_tasks():
    logger = logging.getLogger("scraper.schedule"); logger.info("--- Daily Tasks Start ---")
    try:
        logger.info("Запуск генерации OHLC отчета...")
        ohlc_func = getattr(ohlc_generator, 'rewrite_ohlc_summary', getattr(ohlc_generator, 'generate_daily_ohlc_report', None))
        if ohlc_func:
            global players
            if ohlc_func.__name__ == 'generate_daily_ohlc_report':
                if players: ohlc_func(player_names=list(players.keys()))
                else: logger.error("Не могу запустить OHLC: список игроков не загружен.")
            else:
                ohlc_func(days=1)
            logger.info("Задача OHLC завершена.")
        else: logger.error("Не найдена функция для генерации OHLC.")
    except Exception as e:
        logger.error(f"Ошибка выполнения задачи OHLC: {e}", exc_info=True)
        if getattr(config, 'SEND_TELEGRAM_ERRORS', False):
             notifications.send_telegram_message(f"Ошибка Daily Tasks (OHLC):\n```\n{traceback.format_exc()}\n```", is_error=True)
    logger.info("--- Daily Tasks End ---")

def run_weekly_tasks():
    logger = logging.getLogger("scraper.schedule"); logger.info("--- Weekly Tasks Start ---")
    try:
        logger.info("Запуск генерации еженедельной статистики...")
        if hasattr(weekly_stats, 'generate_weekly_stats_report'): weekly_stats.generate_weekly_stats_report(); logger.info("Задача еженедельной статистики завершена.")
        else: logger.error("Не найдена функция weekly_stats.generate_weekly_stats_report.")
    except Exception as e:
        logger.error(f"Ошибка выполнения задачи еженедельной статистики: {e}", exc_info=True)
        if getattr(config, 'SEND_TELEGRAM_ERRORS', False):
             notifications.send_telegram_message(f"Ошибка Weekly Tasks (Stats):\n```\n{traceback.format_exc()}\n```", is_error=True)
    logger.info("--- Weekly Tasks End ---")

# --- Поток Schedule ---
def run_schedule_continuously(stop_event):
    logger = logging.getLogger("scraper.schedule_thread"); logger.info("Поток Schedule запущен.")
    while not stop_event.is_set():
        try:
            schedule.run_pending()
        except Exception as e:
            logger.error(f"Ошибка в потоке Schedule: {e}", exc_info=True)
        if stop_event.wait(1):
            break
    logger.info("Поток Schedule остановлен.")

# --- Main ---
def main():
    global players, NOTIFICATION_STATE
    driver = None
    stop_event = threading.Event(); schedule_thread = None; current_update_interval = {}
    logger_main = logging.getLogger("scraper.main"); logger_wd_final = logging.getLogger("scraper.webdriver")
    try:
        logger_main.info("="*45); logger_main.info(f"[scraper] Старт (v{__version__})"); logger_main.info("="*45)
        if getattr(config, 'SEND_TELEGRAM_STARTUP', False):
            notifications.send_telegram_message(f"🚀 RenderZ Tracker (v{__version__}) запущен!")

        daily_report_time=getattr(config,'DAILY_REPORT_TIME',"09:00"); weekly_report_day=getattr(config,'WEEKLY_REPORT_DAY',"sunday"); weekly_report_time=getattr(config,'WEEKLY_REPORT_TIME',"10:00"); report_timezone=getattr(config,'REPORT_TIMEZONE',"UTC")
        logger_main.info(f"Настройка ежедневной задачи: {daily_report_time} {report_timezone}"); schedule.every().day.at(daily_report_time, report_timezone).do(run_daily_tasks).tag('daily')
        logger_main.info(f"Настройка еженедельной задачи: {weekly_report_day} {weekly_report_time} {report_timezone}")
        try: getattr(schedule.every(), weekly_report_day.lower()).at(weekly_report_time, report_timezone).do(run_weekly_tasks).tag('weekly')
        except AttributeError: logger_main.error(f"Неверный день '{weekly_report_day}'. Используется sunday."); schedule.every().sunday.at(weekly_report_time, report_timezone).do(run_weekly_tasks).tag('weekly')

        try:
            next_run_time = schedule.next_run
            next_run_str = 'N/A'
            if next_run_time is not None:
                if isinstance(next_run_time, datetime):
                    if next_run_time.tzinfo is None: next_run_time = next_run_time.replace(tzinfo=timezone.utc)
                    next_run_str = next_run_time.strftime('%Y-%m-%d %H:%M:%S %Z')
                else: logger_main.warning(f"schedule.next_run вернул {type(next_run_time)}."); next_run_str = 'Error type'
            logger_main.info(f"Следующая запланированная задача: {next_run_str}")
        except Exception as e: logger_main.warning(f"Не получить время след. задачи: {e}", exc_info=True)

        schedule_thread = threading.Thread(target=run_schedule_continuously, args=(stop_event,), daemon=True); schedule_thread.start(); logger_main.info("Поток Schedule запущен.")

        logger_main.info("Загрузка игроков..."); players = config.load_players()
        if not players: logger_main.critical("Не загрузить игроков!"); sys.exit(1)
        logger_main.info(f"{len(players)} игроков загружено.")
        logger_main.info("Загрузка расписания..."); loaded_interval = storage.load_update_schedule()
        logger_main.info("Загрузка состояния уведомлений..."); NOTIFICATION_STATE = storage.load_notification_state()
        logger_main.info("Иниц. расписания..."); current_update_interval = {}; restored_count, new_count, removed_count = 0, 0, 0; now = datetime.now(timezone.utc)
        loaded_keys = list(loaded_interval.keys())
        for player_key in loaded_keys:
            if player_key not in players: logger_main.warning(f"Игрок '{player_key}' удален."); del loaded_interval[player_key]; removed_count += 1
        for player_key in players.keys():
            if player_key in loaded_interval and loaded_interval[player_key] > now: current_update_interval[player_key] = loaded_interval[player_key]; restored_count += 1
            else:
                if player_key not in loaded_interval: logger_main.info(f"Игрок '{player_key}': новый.")
                current_update_interval[player_key] = now; new_count += 1
        logger_main.info(f"Расписание: {restored_count} восст., {new_count} немедл., {removed_count} удалено.")

        try: init_success_message = f"✅ Инициализация RenderZ Tracker (v{__version__}) завершена. Мониторинг ({len(current_update_interval)} игр.)."; notifications.send_telegram_message(init_success_message); logger_main.info("Увед об инициализации отправлено.")
        except Exception as e_notify_init: logger_main.error(f"Не отправить уведомление об инициализации: {e_notify_init}")

        logger_main.info("Запуск основного цикла обработки игроков...")
        driver = fetch_all_players(players, current_update_interval, NOTIFICATION_STATE, stop_event)

    except KeyboardInterrupt:
        logger_main.info("Получен сигнал KeyboardInterrupt...")
    except Exception as e:
        logger_main.critical(f"КРИТ. ОШИБКА main(): {e}", exc_info=True);
        if getattr(config, 'SEND_TELEGRAM_ERRORS', False):
            notifications.send_telegram_message(f"КРИТИЧЕСКАЯ ОШИБКА в main():\n```\n{traceback.format_exc()}\n```", is_error=True)
    finally:
        logger_main.info("Начало процедуры завершения работы...")
        try:
            logger_main.info("Сохранение расписания...");
            storage.save_update_schedule(PLAYER_UPDATE_INTERVAL)
        except Exception as e_save_sched:
            logger_main.error(f"Не сохранить расписание: {e_save_sched}")

        try:
            logger_main.info("Сохранение состояния уведомлений...");
            storage.save_notification_state(NOTIFICATION_STATE)
        except Exception as e_save_state:
            logger_main.error(f"Не сохранить состояние уведомлений: {e_save_state}")

        stop_event.set();

        if schedule_thread and schedule_thread.is_alive():
            logger_main.info("Ожидание завершения потока Schedule (до 5 секунд)...")
            schedule_thread.join(timeout=5);
            if schedule_thread.is_alive():
                logger_main.warning("Поток Schedule не завершился.")
            else:
                logger_main.info("Поток Schedule завершен.")
        elif schedule_thread:
            logger_main.info("Поток Schedule уже был неактивен.")
        else:
            logger_main.info("Поток Schedule не был запущен.")

        if driver:
            try:
                logger_wd_final.info("Закрытие WebDriver...");
                driver.quit();
                logger_wd_final.info("WebDriver успешно закрыт.")
            except Exception as e_quit:
                 logger_wd_final.error(f"Ошибка при закрытии WebDriver: {e_quit}", exc_info=True)
        else:
             logger_wd_final.warning("WebDriver не найден для закрытия.")

        if getattr(config, 'SEND_TELEGRAM_SHUTDOWN', False):
             notifications.send_telegram_message(f"🛑 RenderZ Tracker (v{__version__}) остановлен.")

        logger_main.info(f"=== RenderZ Tracker (v{__version__}) завершил работу ===");
        print("Скрапер остановлен.")

# --- Запуск main ---
if __name__ == "__main__":
    main()