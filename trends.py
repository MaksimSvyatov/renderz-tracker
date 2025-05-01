import logging

def analyze_trends(daily_data):
    global_min = None
    global_min_player = None
    global_max = None
    global_max_player = None

    for key, data in daily_data.items():
        close_p = data["close_price"]
        if (global_min is None) or (close_p < global_min):
            global_min = close_p
            global_min_player = key[0]
        if (global_max is None) or (close_p > global_max):
            global_max = close_p
            global_max_player = key[0]

    result = {
        "global_min_close": global_min,
        "global_min_player": global_min_player,
        "global_max_close": global_max,
        "global_max_player": global_max_player,
    }
    logging.info(f"[trends.analyze_trends] Итог анализа: {result}")
    return result
