import os
import csv
import logging
from datetime import datetime, timedelta

import statsmodels.api as sm
from statsmodels.tsa.statespace.sarimax import SARIMAX
from arch import arch_model
import numpy as np
from sklearn.cluster import KMeans

def read_price_series(player_name):
    data_dir = "data"
    safe_name = player_name.replace(" ", "_").replace("/", "_").replace("\\", "_")
    filename = os.path.join(data_dir, f"{safe_name}.csv")
    if not os.path.isfile(filename):
        return []

    rows = []
    try:
        with open(filename, "r", encoding="utf-8") as f:
            rdr = csv.DictReader(f)
            for row in rdr:
                dt_str = row.get("Дата","")
                tm_str = row.get("Время","")
                price_str = row.get("Цена","")
                if not dt_str or not price_str:
                    continue
                try:
                    dt_full = dt_str + " " + tm_str
                    dt_ = datetime.strptime(dt_full, "%Y-%m-%d %H:%M:%S")
                    pr_ = float(price_str)
                    rows.append((dt_, pr_))
                except:
                    pass
    except Exception as e:
        logging.error(f"[advanced_analysis] Ошибка чтения {filename}: {e}")
        return []

    rows.sort(key=lambda x: x[0])
    return rows

def run_arima_forecast(player_name, periods_ahead=3, seasonal=False, m=7):
    series_data = read_price_series(player_name)
    if len(series_data) < 20:
        return None, "Недостаточно данных для ARIMA"

    import pandas as pd
    df = pd.DataFrame(series_data, columns=["date","price"])
    df.set_index("date", inplace=True)
    # Предположим, данные ~каждый час
    df = df.asfreq("H", method="pad")

    series = df["price"]

    try:
        if seasonal:
            model = SARIMAX(series, order=(1,1,1), seasonal_order=(1,1,1,m))
            res = model.fit(disp=False)
        else:
            model = sm.tsa.ARIMA(series, order=(1,1,1))
            res = model.fit()
    except Exception as e:
        return None, f"Ошибка обучения ARIMA/SARIMA: {e}"

    forecast = res.forecast(steps=periods_ahead)
    forecast_values = list(forecast)
    summary_str = str(res.summary())
    return forecast_values, summary_str

def run_garch_volatility(player_name, days=30):
    rows = read_price_series(player_name)
    if len(rows) < days:
        return None, "Недостаточно данных для GARCH"

    rows = rows[-days:]
    prices = np.array([r[1] for r in rows])
    returns = np.diff(np.log(prices)) * 100

    try:
        am = arch_model(returns, vol="Garch", p=1, q=1, dist="normal")
        res = am.fit(disp="off")
    except Exception as e:
        return None, f"Ошибка GARCH: {e}"

    forecast = res.forecast(horizon=1)
    vol_forecast = forecast.variance.iloc[-1,0]**0.5
    summary_str = str(res.summary())

    return vol_forecast, summary_str

def kmeans_cycle_analysis(player_name, window_size=7, n_clusters=3):
    rows = read_price_series(player_name)
    if len(rows) < window_size:
        return None, "Недостаточно данных для kmeans"

    blocks = []
    i = 0
    while i+window_size <= len(rows):
        chunk = rows[i:i+window_size]
        prices = [c[1] for c in chunk]
        mn = min(prices)
        mx = max(prices)
        avg = sum(prices)/len(prices)
        vol = (mx - mn)/avg if avg>0 else 0
        blocks.append([mn,mx,avg,vol])
        i += window_size

    if len(blocks) < n_clusters:
        return None, "Слишком мало блоков для kmeans"

    X = np.array(blocks)
    kmeans = KMeans(n_clusters=n_clusters, random_state=42)
    labels = kmeans.fit_predict(X)
    return labels, kmeans.cluster_centers_

def run_advanced_analytics_example(player_name):
    fc, arima_sum = run_arima_forecast(player_name, periods_ahead=3, seasonal=False)
    if fc is not None:
        logging.info(f"[advanced_analysis] ARIMA forecast for {player_name}: {fc}")
    else:
        logging.info(f"[advanced_analysis] ARIMA not available: {arima_sum}")

    vol_f, garch_sum = run_garch_volatility(player_name, days=30)
    if vol_f is not None:
        logging.info(f"[advanced_analysis] GARCH vol forecast for {player_name}: {vol_f}")
    else:
        logging.info(f"[advanced_analysis] GARCH not available: {garch_sum}")

    labels, centers = kmeans_cycle_analysis(player_name, window_size=7, n_clusters=3)
    if labels is not None:
        logging.info(f"[advanced_analysis] KMeans clusters: {labels}")
        logging.info(f"[advanced_analysis] cluster centers: {centers}")
    else:
        logging.info(f"[advanced_analysis] KMeans not available: {centers}")
