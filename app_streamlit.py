import os
import csv
import streamlit as st
import pandas as pd
from datetime import datetime

def load_player_data(player_name):
    data_dir = "data"
    safe_name = player_name.replace(" ", "_").replace("/", "_").replace("\\", "_")
    filename = os.path.join(data_dir, f"{safe_name}.csv")
    if not os.path.isfile(filename):
        return pd.DataFrame()

    rows = []
    with open(filename, "r", encoding="utf-8") as f:
        rdr = csv.DictReader(f)
        for row in rdr:
            dt_str = row["Дата"] + " " + row["Время"]
            price_str = row["Цена"]
            try:
                dt_ = datetime.strptime(dt_str, "%Y-%m-%d %H:%M:%S")
                pr_ = float(price_str)
                rows.append({"datetime": dt_, "price": pr_})
            except:
                pass
    df = pd.DataFrame(rows)
    if not df.empty:
        df.sort_values("datetime", inplace=True)
    return df

def main():
    st.title("Streamlit: Визуализация цен")

    # Можно список игроков задать вручную или сканировать папку data/
    players = [
        "Joško Gvardiol 101",
        "João Cancelo 101",
        "Marc Cucurella 101"
        # Добавьте остальных
    ]
    player_name = st.selectbox("Выберите игрока:", players)
    df = load_player_data(player_name)

    if df.empty:
        st.write("Нет данных для данного игрока.")
    else:
        st.write(f"Показано {len(df)} записей для {player_name}.")
        st.line_chart(df.set_index("datetime")["price"])

if __name__ == "__main__":
    main()
