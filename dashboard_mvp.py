# dashboard_streamlit_simple.py
import streamlit as st
import pandas as pd
import os
import csv
from datetime import datetime, timedelta
import logging

# --- Настройки ---
DATA_DIR = "data"
DAYS_HISTORY = 30
PLAYERS_TO_SHOW = ["Pervis Estupiñán 103", "Sander Berge 102"]

# --- Настройка логирования ---
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# --- Функции ---

@st.cache_data(ttl=3600) # Кэш на час
def load_player_data_last_days(player_name, days_back=DAYS_HISTORY):
    """Загружает данные для игрока из CSV за последние N дней."""
    logging.info(f"ЗАГРУЗКА ДАННЫХ (из файла или кэша) для {player_name}...")
    safe_name = player_name.replace(" ", "_").replace("/", "_").replace("\\", "_")
    filename = os.path.join(DATA_DIR, f"{safe_name}.csv")
    if not os.path.isfile(filename):
        logging.warning(f"Файл не найден: {filename}")
        return pd.DataFrame()

    rows = []
    try:
        with open(filename, "r", encoding="utf-8") as f:
            first_line = f.readline(); has_header = "Дата" in first_line and "Цена" in first_line; f.seek(0)
            reader = csv.DictReader(f) if has_header else csv.reader(f)
            if not has_header: logging.warning(f"[load_data] Отсутствует заголовок в файле {filename}.")
            for i, row_data in enumerate(reader):
                try:
                    if isinstance(row_data, dict):
                        dt_str, tm_str, price_str = row_data.get("Дата", ""), row_data.get("Время", ""), row_data.get("Цена", "")
                    elif isinstance(row_data, list) and len(row_data) >= 3:
                        dt_str, tm_str, price_str = row_data[0], row_data[1], row_data[2]
                    else: continue
                    if not dt_str or not tm_str or not price_str: continue
                    dt_obj = datetime.strptime(f"{dt_str} {tm_str}", "%Y-%m-%d %H:%M:%S")
                    price = float(price_str.replace(',','').replace(' ',''))
                    rows.append({"datetime": dt_obj, "price": price})
                except (ValueError, TypeError) as ve: logging.warning(f"Ошибка конвертации в {filename} строка ~{i+1}: {row_data} -> {ve}")
                except Exception as ep: logging.warning(f"Ошибка парсинга строки в {filename}: {row_data} -> {ep}")
    except Exception as e:
        logging.error(f"Ошибка чтения файла {filename}: {e}")
        st.error(f"Ошибка чтения данных для {player_name}")
        return pd.DataFrame()

    if not rows: return pd.DataFrame()

    df = pd.DataFrame(rows)
    df = df.sort_values("datetime", ascending=True)
    df = df.drop_duplicates(subset=['datetime'], keep='last')
    # --- ИЗМЕНЕНИЕ: Устанавливаем datetime как индекс для st.line_chart ---
    df = df.set_index("datetime")
    # ---

    cutoff_time = datetime.now() - timedelta(days=days_back)
    df = df[df.index >= cutoff_time] # Фильтруем по индексу

    logging.info(f"Загружено {len(df)} записей для {player_name} за последние {days_back} дней")
    return df # Возвращаем DataFrame с datetime индексом

# --- Основная часть приложения Streamlit ---

st.set_page_config(layout="wide")
st.title(f"📊 Дашборд цен игроков (за последние {DAYS_HISTORY} дней)")
st.caption(f"Данные актуальны на момент запуска/обновления страницы: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

# Кнопка ручного обновления
if st.button("🔄 Обновить данные вручную"):
    st.cache_data.clear()
    st.rerun()

col1, col2 = st.columns(2)

# --- Отображение для первого игрока ---
with col1:
    player1 = PLAYERS_TO_SHOW[0]
    st.subheader(f"{player1}")
    df1 = load_player_data_last_days(player1, days_back=DAYS_HISTORY)
    if df1.empty or 'price' not in df1.columns:
        st.warning(f"Нет данных для {player1}.")
    else:
        # --- ИСПОЛЬЗУЕМ st.line_chart ---
        st.line_chart(df1['price'])
        # ---
        if not df1.empty:
            last_price1 = df1['price'].iloc[-1]
            st.metric(label="Последняя цена", value=f"{last_price1:,.0f}".replace(",", " "))
        else:
            st.metric(label="Последняя цена", value="N/A")

# --- Отображение для второго игрока ---
with col2:
    player2 = PLAYERS_TO_SHOW[1]
    st.subheader(f"{player2}")
    df2 = load_player_data_last_days(player2, days_back=DAYS_HISTORY)
    if df2.empty or 'price' not in df2.columns:
        st.warning(f"Нет данных для {player2}.")
    else:
        # --- ИСПОЛЬЗУЕМ st.line_chart ---
        st.line_chart(df2['price'])
        # ---
        if not df2.empty:
            last_price2 = df2['price'].iloc[-1]
            st.metric(label="Последняя цена", value=f"{last_price2:,.0f}".replace(",", " "))
        else:
            st.metric(label="Последняя цена", value="N/A")