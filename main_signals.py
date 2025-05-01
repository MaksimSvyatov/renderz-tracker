import time
import logging
from signals import process_all_signals

def run_signals_loop():
    while True:
        process_all_signals()
        time.sleep(900)  # каждые 15 минут (900 секунд)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run_signals_loop()
