# config_manager.py
import os
import json
import logging
import time
import threading

CONFIG_FILE = "config.json"

# Глобальный словарь игроков
PLAYERS = {}

# Для отслеживания последнего времени модификации config.json
_last_mtime = 0
_lock = threading.Lock()

def load_config():
    """
    Загружает config.json (словарь "players") в глобальную переменную PLAYERS.
    """
    global PLAYERS, _last_mtime
    if not os.path.isfile(CONFIG_FILE):
        logging.warning(f"[config_manager] {CONFIG_FILE} не найден, PLAYERS будет пустым.")
        PLAYERS = {}
        return

    try:
        mtime = os.path.getmtime(CONFIG_FILE)
        if mtime==_last_mtime:
            # файл не менялся
            return

        # иначе перезагружаем
        with _lock:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            # предполагаем, что внутри data есть ключ "players"
            PLAYERS = data.get("players", {})
            _last_mtime = mtime
        logging.info(f"[config_manager] Перезагружен config.json, {len(PLAYERS)} игроков.")
    except Exception as e:
        logging.error(f"[config_manager] Ошибка чтения {CONFIG_FILE}: {e}")

def get_players_dict():
    """
    Возвращает текущий словарь игроков (PLAYERS).
    """
    with _lock:
        return dict(PLAYERS)

def watch_config(interval=60):
    """
    Фоновая функция, которая каждые interval секунд проверяет изменения в config.json.
    Можно запускать в отдельном потоке, либо вызывать по schedule.
    """
    while True:
        load_config()
        time.sleep(interval)
