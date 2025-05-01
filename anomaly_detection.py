import logging

def detect_anomalies(daily_data):
    anomalies = []
    for (player_name, date_str), row in daily_data.items():
        pct = row["price_change_pct"]
        if (pct < -8.0) or (pct > 8.0):
            anomalies.append({
                "player": player_name,
                "date": date_str,
                "price_change_pct": pct
            })

    logging.info(f"[anomaly_detection.detect_anomalies] Найдено аномалий: {len(anomalies)}")
    return anomalies
