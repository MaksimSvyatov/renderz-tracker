import os
import csv
import matplotlib.pyplot as plt
from matplotlib.ticker import StrMethodFormatter
from datetime import datetime

def load_player_data(player_name):
    """
    Считывает data/<player_name>.csv и возвращает список кортежей (dt, price),
    отсортированных по дате/времени.
    """
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

def plot_price_history(player_name):
    """
    Читает историю цен из data/<player_name>.csv и строит график
    с помощью Matplotlib. Отключает научную нотацию на оси Y.
    """
    data = load_player_data(player_name)
    if not data:
        print("Нет данных для графика.")
        return

    x = [r[0] for r in data]  # даты/время
    y = [r[1] for r in data]  # цены

    plt.figure(figsize=(10, 5))
    plt.plot(x, y, label=player_name)
    plt.title(f"История цены: {player_name}")
    plt.xlabel("Дата/Время")
    plt.ylabel("Цена")

    # Отключаем научную нотацию на оси Y
    plt.gca().yaxis.set_major_formatter(StrMethodFormatter('{x:,.0f}'))

    plt.legend()
    plt.grid(True)
    plt.show()

def main():
    """
    Пример: строим график для одного игрока.
    При желании замените имя игрока на нужное из players_config.json.
    """
    player_name = "Pervis Estupiñán 103"
    plot_price_history(player_name)

if __name__ == "__main__":
    main()
