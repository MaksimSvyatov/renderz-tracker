import logging

# Инициализация логирования с уровнем DEBUG
logging.basicConfig(level=logging.DEBUG, format="%(asctime)s - %(levelname)s - %(message)s")

from scraper import fetch_all_players

if __name__ == "__main__":
    fetch_all_players()
