import logging
import requests
import os

# Пример: либо пропишите токен/чат прямо в коде, либо берите из env
BOT_TOKEN = os.environ.get("TG_BOT_TOKEN", "7988322225:AAEa2LzwwX-BJBJ-TcmB_aFzPjir7SFCQQ")
CHAT_ID = os.environ.get("TG_CHAT_ID", "99117096")

def send_telegram_message(message: str):
    """
    Отправляет сообщение в Telegram-чат (CHAT_ID) с помощью BOT_TOKEN.
    """
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": message
    }
    try:
        resp = requests.post(url, json=payload, timeout=10)
        if resp.status_code == 200:
            logging.info("[bot] Телеграм-сообщение успешно отправлено.")
        else:
            logging.error("[bot] Ошибка при отправке Telegram: %s", resp.text)
    except Exception as e:
        logging.error("[bot] Исключение при отправке Telegram: %s", e)
