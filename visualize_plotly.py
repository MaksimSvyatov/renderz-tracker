import os
import csv
import plotly.graph_objs as go
from plotly.offline import plot
from datetime import datetime

def load_player_data(player_name):
    data_dir = "data"
    safe_name = player_name.replace(" ", "_").replace("/", "_").replace("\\", "_")
    filename = os.path.join(data_dir, f"{safe_name}.csv")
    if not os.path.isfile(filename):
        print(f"Файл {filename} не найден.")
        return []

    rows = []
    with open(filename, "r", encoding="utf-8") as f:
        rdr = csv.DictReader(f)
        for row in rdr:
            dt_str = row.get("Дата","")
            tm_str = row.get("Время","")
            price_str = row.get("Цена","")
            if dt_str and price_str:
                try:
                    dt_full = dt_str + " " + tm_str
                    dt_ = datetime.strptime(dt_full, "%Y-%m-%d %H:%M:%S")
                    price_ = float(price_str)
                    rows.append((dt_, price_))
                except:
                    pass
    rows.sort(key=lambda x: x[0])
    return rows

def plot_price_history_interactive(player_name):
    data = load_player_data(player_name)
    if not data:
        print("Нет данных для графика.")
        return

    x = [r[0] for r in data]
    y = [r[1] for r in data]

    trace = go.Scatter(x=x, y=y, mode='lines', name=player_name)
    layout = go.Layout(title=f"Цена {player_name}", xaxis={'title': 'Дата'}, yaxis={'title': 'Цена'})
    fig = go.Figure(data=[trace], layout=layout)

    # Сохраняем HTML-файл и открываем в браузере
    html_filename = f"{player_name.replace(' ', '_')}_price.html"
    plot(fig, filename=html_filename, auto_open=True)
    print(f"Сохранён интерактивный график: {html_filename}")

def main():
    player_name = "Joško Gvardiol 101"
    plot_price_history_interactive(player_name)

if __name__ == "__main__":
    main()
