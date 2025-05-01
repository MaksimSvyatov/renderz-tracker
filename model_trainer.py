# # players_to_train = [
# #     "David López 103", "Fred 103", "Vanderson 100", "Subhasish Bose 103",
# #     "Scott McTominay 103", "Curtis Jones 102", "Pedri 102", "Pervis Estupiñán 103",
# #     "Leandro Paredes 103", "Marcos Acuña 105", "Daniel Muñoz 105", "Sandesh Jhingan 104",
# #     "Anirudh Thapa 103", "Nuno Tavares 103", "João Neves 103", "Calvin Verdonk 101",
# #     "Paulo Futre LM 102 4 ранг", "Benjamin Pavard CB 101", "Rodrigo De Paul 103"
# # ]
#
#
#
# # =============================================
# # ФАЙЛ: model_trainer.py (ВЕРСИЯ v21.1 - ИСПРАВЛЕННАЯ 3-КЛАССОВАЯ ЗАДАЧА)
# # - ЗАДАЧА: 3-классовая классификация (-1 Падение, 0 Без изм., 1 Рост -> 0, 1, 2 для LGBM)
# # - Обучение для РАСШИРЕННОГО списка из 19 игроков
# # - Используется GridSearchCV с РАСШИРЕННОЙ сеткой (включая регуляризацию)
# # - Используется SMOTE и ПОЛНЫЙ набор фичей (v18)
# # - ИСПРАВЛЕНО: Корректная обработка 3-классовой цели в train_model_for_player
# # =============================================
# import pandas as pd
# import numpy as np
# import os
# import logging
# from datetime import datetime, timedelta, timezone
# import lightgbm as lgb
# import joblib
# import cycle_analysis
# import events_manager
# import config
# import storage
#
# from sklearn.model_selection import GridSearchCV, StratifiedKFold
# try: import ta
# except ImportError: logging.error("Библиотека 'ta' не найдена."); ta = None
# try: from imblearn.over_sampling import SMOTE
# except ImportError: logging.warning("Библиотека 'imblearn' не найдена."); SMOTE = None
#
# MODEL_DIR = getattr(config, 'MODEL_DIR', 'models')
#
# # Список фичей (v18 - Полный)
# DEFAULT_FEATURES = [
#     "rsi_value", "is_rsi_overbought", "is_rsi_oversold", "macd_diff",
#     "bollinger_hband_indicator", "bollinger_lband_indicator", "bollinger_pband", "bollinger_wband",
#     "is_two_rises_anytime", "is_start_rise_after_drop", "breakout_7d_up", "breakout_7d_down",
#     "breakout_14d_up", "breakout_14d_down", "is_all_time_high", "is_all_time_low",
#     "seasonal_dow_avg_signal_buy", "seasonal_dow_avg_signal_sell", "dow_deviation_from_avg",
#     "dow_range_position", "dom_avg_signal_buy", "dom_avg_signal_sell", "dom_deviation_from_avg",
#     "trend_10d_deviation_sko", "days_in_cycle", "is_cycle_phase_fall", "is_cycle_phase_bottom",
#     "is_cycle_phase_rise", "is_cycle_phase_peak", "is_other_event_active", "is_from_current_event",
#     "dow_sin", "dow_cos", "cycle_day_sin", "cycle_day_cos",
#     "price_lag_1", "rsi_lag_1", "price_div_sma20", "is_above_sma20", "ovr_category",
#     "is_position_CB", "is_position_LB", "is_position_CM", "is_position_RB", "is_position_LM",
#     "is_position_RW", "is_position_ST", "is_position_GK",
#     "is_dow_0", "is_dow_1", "is_dow_2", "is_dow_3", "is_dow_4", "is_dow_5", "is_dow_6",
#     "volatility",
# ]
# DEFAULT_FEATURES = sorted(list(set(DEFAULT_FEATURES)))
#
# TARGET_HORIZON_DAYS = 1
# PRICE_CHANGE_THRESHOLD_PCT = 1.5 # Порог для классов Рост/Падение
#
# # --- 3-классовая цель (ОК) ---
# def _get_target(current_price, future_price):
#     """Определяет целевой класс (-1 Падение, 0 Без изм., 1 Рост)."""
#     if current_price is None or future_price is None or abs(current_price) < 1e-9 : return 0 # Без изм.
#     try:
#         price_diff_pct = ((future_price - current_price) / current_price) * 100
#         if price_diff_pct > PRICE_CHANGE_THRESHOLD_PCT:
#             return 1 # Рост
#         elif price_diff_pct < -PRICE_CHANGE_THRESHOLD_PCT:
#             return -1 # Падение
#         else:
#             return 0 # Без изм.
#     except (TypeError, ZeroDivisionError):
#         return 0 # Без изм.
# # ------------------------------------
#
# # --- Вспомогательные функции (Исправлены и проверены) ---
# def _compute_rsi_hist(prices_list, period=14):
#     if isinstance(prices_list, pd.Series): prices_numeric = pd.to_numeric(prices_list, errors='coerce')
#     elif isinstance(prices_list, list): prices_numeric = pd.Series([p for p in prices_list if isinstance(p, (int, float)) and pd.notna(p) and np.isfinite(p)], dtype=float)
#     else: return None
#     prices_clean = prices_numeric.dropna(); len_clean = len(prices_clean)
#     if len_clean < period + 1: return pd.Series([50.0]*len(prices_numeric), index=prices_numeric.index) if isinstance(prices_list, pd.Series) else ([50.0]*len(prices_list) if isinstance(prices_list, list) else None)
#     deltas = prices_clean.diff(1).dropna();
#     if deltas.empty: return pd.Series([50.0]*len(prices_numeric), index=prices_numeric.index) if isinstance(prices_list, pd.Series) else ([50.0]*len(prices_list) if isinstance(prices_list, list) else None)
#     gain=deltas.clip(lower=0); loss=-deltas.clip(upper=0)
#     avg_gain=gain.ewm(com=period-1, adjust=False).mean(); avg_loss=loss.ewm(com=period-1, adjust=False).mean()
#     last_valid_index = avg_loss.last_valid_index()
#     if last_valid_index is None or avg_loss[last_valid_index] < 1e-9: return pd.Series([100.0] * len(prices_numeric), index=prices_numeric.index) if isinstance(prices_list, pd.Series) else ([100.0]*len(prices_list) if isinstance(prices_list, list) else None)
#     rs = avg_gain / avg_loss.where(avg_loss >= 1e-9, np.nan); rs = rs.replace([np.inf, -np.inf], np.nan).fillna(100.0)
#     rsi = 100.0 - (100.0 / (1.0 + rs)); rsi = rsi.fillna(50.0)
#     if isinstance(prices_list, pd.Series): return rsi.reindex(prices_numeric.index).fillna(50.0)
#     elif isinstance(prices_list, list): return rsi.reindex(pd.RangeIndex(len(prices_list))).fillna(50.0).tolist()
#     return None
#
# def _check_consecutive_rises_hist(prices, i, threshold=2):
#     if i < threshold : return False
#     count = 0 # Инициализация ПЕРЕД циклом
#     for j in range(i, i - threshold, -1):
#         if j > 0 and j < len(prices) and (j-1) >= 0 and \
#            prices[j] is not None and prices[j-1] is not None and \
#            isinstance(prices[j], (int, float)) and isinstance(prices[j-1], (int, float)) and \
#            prices[j] > prices[j-1]:
#             count += 1
#         else:
#             break
#     return count >= threshold
#
# def _check_start_rise_after_drop_hist(prices, i):
#     if i < 2 or i >= len(prices) or (i-1) < 0 or (i-2) < 0: return False # Проверка границ
#     p1, p2, p3 = prices[i-2], prices[i-1], prices[i]
#     if p1 is None or p2 is None or p3 is None: return False # Проверка None
#     if not (isinstance(p1, (int, float)) and isinstance(p2, (int, float)) and isinstance(p3, (int, float))): return False # Проверка типа
#     return p1 > p2 < p3
#
# def _calculate_dow_metrics(history: list, current_date: datetime) -> tuple[float, float]:
#     dow_deviation = 0.0; dow_range_pos = 0.5;
#     if not history: return dow_deviation, dow_range_pos
#     current_dow = current_date.weekday(); current_price = history[-1].get('price') if history else None
#     dow_stats = {dow: {"prices": [], "count": 0, "sum_price": 0.0, "min_price": float('inf'), "max_price": float('-inf')} for dow in range(7)}
#     all_prices = []; valid_records = 0
#     for record in history:
#         price = record.get('price'); date = record.get('date')
#         if price is not None and date is not None and isinstance(date, datetime): st = dow_stats[date.weekday()]; st["prices"].append(price); st["count"] += 1; st["sum_price"] += price; st["min_price"] = min(st["min_price"], price); st["max_price"] = max(st["max_price"], price); all_prices.append(price); valid_records += 1
#     if valid_records == 0: return dow_deviation, dow_range_pos
#     global_avg_price = np.mean(all_prices) if all_prices else 0; current_dow_data = dow_stats[current_dow]
#     if current_dow_data["count"] > 0 and global_avg_price > 1e-9:
#         current_dow_avg = current_dow_data["sum_price"] / current_dow_data["count"]
#         if pd.notna(current_dow_avg) and np.isfinite(current_dow_avg): dow_deviation = (current_dow_avg - global_avg_price) / global_avg_price;
#         if not np.isfinite(dow_deviation): dow_deviation = 0.0
#     if current_dow_data["count"] >= 5:
#         h_min = current_dow_data["min_price"]; h_max = current_dow_data["max_price"]
#         if h_min != float('inf') and h_max != float('-inf'):
#              d_range = h_max - h_min
#              if d_range > 1e-9 and current_price is not None and pd.notna(current_price) and np.isfinite(current_price): pos = (current_price - h_min) / d_range; dow_range_pos = max(0.0, min(1.0, pos));
#              if not np.isfinite(dow_range_pos): dow_range_pos = 0.5
#     return dow_deviation, dow_range_pos
#
# def _calculate_dom_metrics(history: list, current_date: datetime) -> float:
#     dom_deviation = 0.0;
#     if not history: return dom_deviation
#     current_dom = current_date.day; dom_stats = {day: {"prices": []} for day in range(1, 32)}; all_prices = []
#     for record in history:
#         price = record.get('price'); date = record.get('date')
#         if price is not None and date is not None and isinstance(date, datetime):
#              day = date.day;
#              if 1 <= day <= 31:
#                  dom_stats.setdefault(day, {"prices":[]})["prices"].append(price)
#              all_prices.append(price)
#     if not all_prices: return dom_deviation
#     global_avg_price = np.mean(all_prices) if all_prices else 0; current_dom_prices = dom_stats.get(current_dom, {}).get("prices", [])
#     if current_dom_prices and global_avg_price > 1e-9: current_dom_avg = np.mean(current_dom_prices); dom_deviation = (current_dom_avg - global_avg_price) / global_avg_price
#     return dom_deviation
#
# def _calculate_trend_sko(history: list, current_date: datetime) -> float:
#     # (Код с исправленным except)
#      trend_sko = 0.0
#      if len(history) < 30: return trend_sko
#      t10 = current_date - timedelta(days=10); t20 = current_date - timedelta(days=20)
#      history_before_now = [r for r in history if r.get('date') and isinstance(r['date'], datetime) and r['date'] < current_date]
#      recent_10d_prices = [r['price'] for r in history_before_now if r.get('price') is not None and t10 <= r['date']]
#      base_10d_prices = [r['price'] for r in history_before_now if r.get('price') is not None and t20 <= r['date'] < t10]
#      if len(recent_10d_prices) < 5 or len(base_10d_prices) < 10: return trend_sko
#      try:
#          avg10 = np.mean(recent_10d_prices); avg_base = np.mean(base_10d_prices); std_base = np.std(base_10d_prices)
#          if std_base > 1e-9:
#              trend_sko = (avg10 - avg_base) / std_base
#              if not np.isfinite(trend_sko): trend_sko = 0.0
#      except Exception as e:
#          logging.warning(f"Ошибка расчета СКО тренда: {e}")
#          trend_sko = 0.0
#      return trend_sko
#
# # --- Функция подготовки фичей (ОК) ---
# def prepare_features_for_player(player_name, history_data=None, player_configs=None):
#     # (Код с исправленным target и ovr_category)
#     if ta is None: logging.error("Библиотека 'ta' не загружена."); return None
#     if history_data is None: history = cycle_analysis.read_player_history(player_name)
#     else: history = history_data
#     if len(history) < 40: logging.warning(f"[Trainer] Мало истории ({len(history)} < 40) для {player_name}."); return None
#     if player_configs is None: player_configs = config.load_players()
#     player_info = player_configs.get(player_name, {})
#     features = []
#     logging.info(f"[Trainer] Подготовка фичей для {player_name}, записей: {len(history)}")
#     event_details_cache = {}
#     logging.debug("Предрасчет индикаторов...")
#     dates_list = [r.get('date') for r in history]; prices_list = [r.get('price') for r in history]
#     if not dates_list or not any(isinstance(d, datetime) for d in dates_list): logging.error(f"Нет дат в истории {player_name}."); return None
#     valid_history = [(p, d) for p, d in zip(prices_list, dates_list) if isinstance(d, datetime)]
#     prices_list_valid = [item[0] for item in valid_history]; dates_list_valid = [item[1] for item in valid_history]
#     df_hist = pd.DataFrame({'price': prices_list_valid}, index=pd.DatetimeIndex(dates_list_valid))
#     df_hist['price'] = pd.to_numeric(df_hist['price'], errors='coerce').dropna()
#     if df_hist.empty: logging.warning(f"Нет валидных цен у {player_name}"); return None
#     rsi_series = _compute_rsi_hist(df_hist['price'], period=14)
#     if rsi_series is None: rsi_series = pd.Series(50.0, index=df_hist.index)
#     df_hist['rsi'] = rsi_series
#     df_hist['sma20'] = df_hist['price'].rolling(window=20, min_periods=20).mean()
#     try: macd = ta.trend.MACD(close=df_hist['price'],fillna=True); df_hist['macd_diff'] = macd.macd_diff(); bbands = ta.volatility.BollingerBands(close=df_hist['price'],fillna=True); df_hist['bollinger_hband_indicator'] = bbands.bollinger_hband_indicator(); df_hist['bollinger_lband_indicator'] = bbands.bollinger_lband_indicator(); df_hist['bollinger_pband'] = bbands.bollinger_pband(); df_hist['bollinger_wband'] = bbands.bollinger_wband()
#     except Exception as e_ta: logging.error(f"Ошибка 'ta' для {player_name}: {e_ta}"); [df_hist.update({col:0.0}) for col in ['macd_diff','bollinger_hband_indicator', 'bollinger_lband_indicator']]; df_hist['bollinger_pband'] = 0.5; df_hist['bollinger_wband'] = 0.0
#     logging.debug("Предрасчет завершен.")
#     n_targetable_rows = len(df_hist) - TARGET_HORIZON_DAYS
#     if n_targetable_rows <= 0: logging.warning(f"[Trainer] Недостаточно данных для цели у {player_name}."); return None
#     valid_indices = df_hist.index[:n_targetable_rows]
#     for i, current_date in enumerate(valid_indices):
#         current_price = df_hist.loc[current_date, 'price']; current_df_row = df_hist.loc[current_date]; date_key = current_date.date()
#         if date_key not in event_details_cache: event_details_cache[date_key] = events_manager.get_event_phase_details(now_dt=current_date)
#         event_details = event_details_cache[date_key]; feature_vector = {feat_name: 0.0 for feat_name in DEFAULT_FEATURES}
#         # --- Заполнение ВСЕХ фичей ---
#         rsi_now = current_df_row['rsi']; feature_vector["rsi_value"] = rsi_now if pd.notna(rsi_now) else 50.0
#         if pd.notna(rsi_now): feature_vector["is_rsi_overbought"] = int(rsi_now > 70); feature_vector["is_rsi_oversold"] = int(rsi_now < 30)
#         macd_diff_now = current_df_row.get('macd_diff'); feature_vector["macd_diff"] = macd_diff_now if pd.notna(macd_diff_now) else 0.0
#         hband_ind = current_df_row.get('bollinger_hband_indicator'); feature_vector["bollinger_hband_indicator"] = hband_ind if pd.notna(hband_ind) else 0.0
#         lband_ind = current_df_row.get('bollinger_lband_indicator'); feature_vector["bollinger_lband_indicator"] = lband_ind if pd.notna(lband_ind) else 0.0
#         pband = current_df_row.get('bollinger_pband'); feature_vector["bollinger_pband"] = pband if pd.notna(pband) else 0.5
#         wband = current_df_row.get('bollinger_wband'); feature_vector["bollinger_wband"] = wband if pd.notna(wband) else 0.0
#         # --- ИСПРАВЛЕНИЕ ИНДЕКСА для исторических списков ---
#         # Ищем индекс текущей даты в исходном списке history (где могут быть пропуски, в отличие от df_hist)
#         original_hist_index = -1
#         for idx, record in enumerate(history):
#             if record.get('date') == current_date:
#                 original_hist_index = idx
#                 break
#         if original_hist_index != -1:
#              feature_vector["is_two_rises_anytime"] = int(_check_consecutive_rises_hist(prices_list, original_hist_index))
#              feature_vector["is_start_rise_after_drop"] = int(_check_start_rise_after_drop_hist(prices_list, original_hist_index))
#              if original_hist_index > 0: feature_vector["price_lag_1"] = prices_list[original_hist_index-1] if prices_list[original_hist_index-1] is not None else current_price
#              else: feature_vector["price_lag_1"] = current_price
#         else: # Фоллбэк если не нашли дату (маловероятно, но возможно)
#              feature_vector["is_two_rises_anytime"] = 0
#              feature_vector["is_start_rise_after_drop"] = 0
#              feature_vector["price_lag_1"] = current_price
#         # --- КОНЕЦ ИСПРАВЛЕНИЯ ИНДЕКСА ---
#
#         feature_vector["breakout_7d_up"]=0.0; feature_vector["breakout_7d_down"]=0.0; feature_vector["breakout_14d_up"]=0.0; feature_vector["breakout_14d_down"]=0.0; feature_vector["is_all_time_high"]=0.0; feature_vector["is_all_time_low"]=0.0
#         history_slice_for_seasonal = [r for r in history if r.get('date') and r['date'] <= current_date]; dow_dev, dow_pos = _calculate_dow_metrics(history_slice_for_seasonal, current_date); dom_dev = _calculate_dom_metrics(history_slice_for_seasonal, current_date); trend_sko = _calculate_trend_sko(history_slice_for_seasonal, current_date)
#         feature_vector["dow_deviation_from_avg"] = dow_dev if pd.notna(dow_dev) else 0.0; feature_vector["dow_range_position"] = dow_pos if pd.notna(dow_pos) else 0.5; feature_vector["dom_deviation_from_avg"] = dom_dev if pd.notna(dom_dev) else 0.0; feature_vector["trend_10d_deviation_sko"] = trend_sko if pd.notna(trend_sko) else 0.0
#         temp_seasonal_signal = cycle_analysis.create_seasonal_signal_example(player_name); feature_vector["seasonal_dow_avg_signal_buy"] = int("BUY" in temp_seasonal_signal); feature_vector["seasonal_dow_avg_signal_sell"] = int("SELL" in temp_seasonal_signal)
#         temp_dom_signal = cycle_analysis.create_day_of_month_signal(player_name); feature_vector["dom_avg_signal_buy"] = int("BUY" in temp_dom_signal); feature_vector["dom_avg_signal_sell"] = int("SELL" in temp_dom_signal)
#         current_day_in_cycle = event_details.get("days_in_cycle"); feature_vector["days_in_cycle"] = current_day_in_cycle if current_day_in_cycle is not None else 0
#         c_phase = event_details.get("main_cycle_phase_raw", "N/A"); feature_vector["is_cycle_phase_fall"] = int(c_phase == "Падение"); feature_vector["is_cycle_phase_bottom"] = int(c_phase == "Дно/Разворот"); feature_vector["is_cycle_phase_rise"] = int(c_phase == "Рост"); feature_vector["is_cycle_phase_peak"] = int(c_phase == "Завершение/Пик")
#         feature_vector["is_other_event_active"] = int(event_details.get("is_other_event_active", False))
#         dow = current_date.weekday(); feature_vector["dow_sin"] = np.sin(2 * np.pi * dow / 7); feature_vector["dow_cos"] = np.cos(2 * np.pi * dow / 7)
#         if current_day_in_cycle is not None and current_day_in_cycle > 0: norm_cycle_day = current_day_in_cycle - 1; feature_vector["cycle_day_sin"] = np.sin(2 * np.pi * norm_cycle_day / 28); feature_vector["cycle_day_cos"] = np.cos(2 * np.pi * norm_cycle_day / 28)
#         else: feature_vector["cycle_day_sin"] = 0.0; feature_vector["cycle_day_cos"] = 0.0
#
#         prev_date_idx = df_hist.index.get_loc(current_date) - 1 if df_hist.index.get_loc(current_date) > 0 else -1
#         if prev_date_idx != -1:
#             prev_date = df_hist.index[prev_date_idx]
#             rsi_lag1 = rsi_series.get(prev_date)
#             feature_vector["rsi_lag_1"] = rsi_lag1 if pd.notna(rsi_lag1) else 50.0
#         else:
#             feature_vector["rsi_lag_1"] = 50.0 # Use 50 if no previous RSI
#
#         sma20_now = current_df_row.get('sma20'); feature_vector["price_div_sma20"] = current_price / sma20_now if pd.notna(sma20_now) and sma20_now > 1e-9 else 1.0; feature_vector["is_above_sma20"] = int(current_price > sma20_now) if pd.notna(sma20_now) else 0
#         player_info_current = player_configs.get(player_name, {}); pos = player_info_current.get("position", "Unknown"); ovr = player_info_current.get("ovr", 0)
#         src_type = player_info_current.get("source_event_type", "past"); feature_vector["is_from_current_event"] = 1 if src_type == "current" else 0
#         # --- Исправленный блок OVR (ОК) ---
#         if ovr >= 104:
#             feature_vector["ovr_category"] = 3
#         elif ovr >= 101:
#             feature_vector["ovr_category"] = 2
#         elif ovr >= 98:
#             feature_vector["ovr_category"] = 1
#         else:
#             feature_vector["ovr_category"] = 0
#         # ---------------------------
#         pos_map = {"CB": 0, "LB": 0, "CM": 0, "RB": 0, "LM": 0, "RW": 0, "ST": 0, "GK": 0};
#         if pos in pos_map: pos_map[pos] = 1
#         for p_name_key, p_val in pos_map.items(): feature_vector[f"is_position_{p_name_key}"] = p_val
#         for d in range(7): feature_vector[f"is_dow_{d}"] = 1 if dow == d else 0
#         feature_vector["volatility"] = feature_vector["bollinger_wband"]
#         # --- Конец Заполнения фичей ---
#
#         # --- Целевая переменная (ОК, возвращает -1, 0, 1) ---
#         target_date_approx = current_date + timedelta(days=TARGET_HORIZON_DAYS)
#         future_indices = df_hist.index[df_hist.index >= target_date_approx]
#         if not future_indices.empty:
#             target_date_actual = future_indices[0]
#             if target_date_actual in df_hist.index:
#                  target_price = df_hist.loc[target_date_actual, 'price']
#                  target = _get_target(current_price, target_price) # Оригинальная цель -1, 0, 1
#             else:
#                  continue # Пропускаем, если нет целевой цены для точной даты
#         else:
#             continue # Пропускаем, если нет будущих дат вообще
#         # -----------------------------------
#
#         # --- Финальная проверка и добавление ---
#         final_vector_for_df = {}
#         for feat_name in DEFAULT_FEATURES:
#             value = feature_vector.get(feat_name, 0.0)
#             if value is None or (isinstance(value, (int, float, np.number)) and not np.isfinite(value)): final_vector_for_df[feat_name] = 0.0
#             elif isinstance(value, bool): final_vector_for_df[feat_name] = int(value)
#             else:
#                  try: final_vector_for_df[feat_name] = float(value);
#                  except (ValueError, TypeError): final_vector_for_df[feat_name] = 0.0
#             if not np.isfinite(final_vector_for_df[feat_name]): final_vector_for_df[feat_name] = 0.0
#         final_vector_for_df["target"] = target # Сохраняем оригинальную цель -1, 0, 1
#         final_vector_for_df["date"] = current_date
#         features.append(final_vector_for_df)
#
#     if not features: logging.warning(f"[Trainer] Не сгенерировано фичей для {player_name}"); return None
#     df_features = pd.DataFrame(features)
#     # --- УЛУЧШЕННАЯ ФИНАЛЬНАЯ ПРОВЕРКА КОЛОНОК (ОК) ---
#     for col in DEFAULT_FEATURES:
#         if col not in df_features.columns: logging.warning(f"Колонка '{col}' отсутствовала..."); df_features[col] = 0.0
#         df_features[col] = pd.to_numeric(df_features[col], errors='coerce')
#         df_features[col] = df_features[col].replace([np.inf, -np.inf], np.nan)
#         df_features[col] = df_features[col].fillna(0)
#         if not np.all(np.isfinite(df_features[col])): logging.error(f"!!! Не удалось очистить колонку '{col}'."); df_features[col] = 0.0
#         try: df_features[col] = df_features[col].astype(float)
#         except ValueError: logging.error(f"!!! Не удалось конвертировать '{col}' в float."); df_features[col] = 0.0
#     # ----------------------------------------
#     logging.info(f"[Trainer] Сгенерировано {len(df_features)} фичей для {player_name}")
#     return df_features
#
# # --- Функция обучения с SMOTE и GridSearchCV (ИСПРАВЛЕНА для 3 КЛАССОВ) ---
# def train_model_for_player(player_name, df_features):
#     if df_features is None or df_features.empty or 'target' not in df_features.columns:
#         logging.error(f"[Trainer] Нет данных/цели для {player_name}"); return None
#
#     if SMOTE is None: logging.warning("Библиотека 'imblearn' не установлена. Обучение без SMOTE."); use_smote=False
#     else: use_smote=True
#
#     features_to_use = [f for f in DEFAULT_FEATURES if f in df_features.columns];
#     missing_features = set(DEFAULT_FEATURES) - set(features_to_use)
#     if missing_features:
#         logging.error(f"[Trainer] Отсутствуют фичи {missing_features} перед обучением. Заполнение нулями...");
#         for feat in missing_features:
#             df_features[feat] = 0.0
#         features_to_use = DEFAULT_FEATURES # Обновляем список используемых фич
#
#     X = df_features[features_to_use]
#     y = df_features['target'] # Оригинальная цель: -1, 0, 1
#
#     # --- Очистка X ---
#     numeric_cols = X.select_dtypes(include=np.number).columns
#     if X[numeric_cols].isnull().values.any() or not np.all(np.isfinite(X[numeric_cols].values)):
#          logging.warning(f"[Trainer] NaN/inf в X перед очисткой. Очистка...");
#          for col in numeric_cols:
#              X[col] = X[col].fillna(0).replace([np.inf, -np.inf], 0)
#          if X[numeric_cols].isnull().values.any() or not np.all(np.isfinite(X[numeric_cols].values)):
#              logging.error(f"[Trainer] Очистка X не удалась."); return None
#
#     # --- Очистка y и выравнивание с X ---
#     y = y.dropna()
#     X = X.loc[y.index] # Важно: выровнять X по индексам чистого y
#
#     # --- ** КОРРЕКТНАЯ ПОДГОТОВКА ЦЕЛИ ДЛЯ 3-КЛАССОВОГО LGBM ** ---
#     # Маппинг: -1 -> 0 (Падение), 0 -> 1 (Без изм.), 1 -> 2 (Рост)
#     y_mapped = y + 1
#     # ----------------------------------------------------------
#
#     # --- Проверка количества классов ---
#     if y_mapped.nunique() < 2:
#         logging.warning(f"[Trainer] Мало уникальных классов ({y_mapped.nunique()}) для {player_name} после маппинга. Пропуск.");
#         return None
#
#     if len(X) < 15 :
#         logging.warning(f"[Trainer] Мало данных ({len(X)}) для CV у {player_name}.");
#         # Можно либо пропустить, либо попробовать обучить без CV (как сделано в fallback)
#         # return None
#
#     X_res, y_res = X, y_mapped # Инициализация для случая без SMOTE
#
#     # --- Применение SMOTE ---
#     if use_smote:
#         logging.info(f"[Trainer] Применение SMOTE для {player_name}... Исходные классы (0,1,2): {np.bincount(y_mapped.astype(int))}")
#         try:
#             min_samples = y_mapped.value_counts().min()
#             n_neighbors_smote = max(1, min(5, min_samples - 1)) # k_neighbors >= 1 и < min_samples
#
#             if n_neighbors_smote >= 1 and min_samples > n_neighbors_smote :
#                 smote = SMOTE(random_state=42, k_neighbors=n_neighbors_smote)
#                 X_res, y_res = smote.fit_resample(X, y_mapped) # Используем X и y_mapped
#                 logging.info(f"[Trainer] SMOTE завершен. Новые классы (0,1,2): {np.bincount(y_res.astype(int))}")
#             else:
#                 logging.warning(f"Недостаточно образцов ({min_samples}) для SMOTE с k={n_neighbors_smote}. Без SMOTE.")
#                 # X_res, y_res остаются равными X, y_mapped
#         except Exception as e_smote:
#             logging.error(f"[Trainer] Ошибка SMOTE: {e_smote}. Без SMOTE.")
#             # X_res, y_res остаются равными X, y_mapped
#
#     logging.info(f"[Trainer] Подбор гиперпараметров (GridSearchCV) LGBM для {player_name} ({len(X_res)} примеров, {y_res.nunique()} классов)...")
#
#     # --- GridSearchCV ---
#     try:
#         # Расширенная сетка с регуляризацией
#         param_grid = {
#             'n_estimators': [100, 150, 200],
#             'learning_rate': [0.05, 0.1],
#             'num_leaves': [20, 31, 40],
#             'max_depth': [-1, 10, 20], # -1 значит без ограничения
#             'reg_alpha': [0, 0.01, 0.1], # L1 регуляризация
#             'reg_lambda': [0, 0.01, 0.1] # L2 регуляризация
#         }
#         # LGBM для мультиклассовой классификации (objective='multiclass' по умолчанию)
#         # num_class будет определен автоматически из y_res
#         lgbm = lgb.LGBMClassifier(random_state=42)
#
#         # Стратегия CV
#         min_samples_after_smote = pd.Series(y_res).value_counts().min()
#         n_cv_splits = max(2, min(3, min_samples_after_smote)) # Хотя бы 2 сплита, не больше 3 или мин. класса
#
#         if n_cv_splits < 2 or len(X_res) < n_cv_splits:
#              logging.warning(f"Невозможно выполнить CV ({n_cv_splits} сплитов) для {len(X_res)} образцов после SMOTE. Обучение с дефолтными.")
#              raise ValueError("Insufficient samples for CV")
#
#         cv_strategy = StratifiedKFold(n_splits=n_cv_splits, shuffle=True, random_state=42)
#
#         # Запуск GridSearchCV
#         grid_search = GridSearchCV(estimator=lgbm,
#                                    param_grid=param_grid,
#                                    scoring='f1_macro', # Подходит для мультикласса и дисбаланса
#                                    cv=cv_strategy,
#                                    n_jobs=4, # Используем несколько ядер, если доступно
#                                    verbose=1) # Показываем прогресс
#
#         grid_search.fit(X_res, y_res, feature_name=features_to_use) # Обучаем на данных после SMOTE (X_res, y_res)
#
#         logging.info(f"[Trainer] Подбор завершен. Лучший score (f1_macro): {grid_search.best_score_:.4f}")
#         logging.info(f"[Trainer] Лучшие параметры: {grid_search.best_params_}")
#         best_model = grid_search.best_estimator_
#
#         # Вывод важности фичей
#         try:
#             imp = pd.DataFrame({
#                 'Value':best_model.feature_importances_,
#                 'Feature':features_to_use
#                  }).sort_values(by="Value",ascending=False).head(15)
#             logging.info(f"Топ фичей (лучшая модель) {player_name}:\n{imp}")
#         except Exception as e: logging.warning(f"Ошибка вывода важности фичей: {e}")
#
#         return best_model
#
#     except Exception as e:
#         logging.error(f"[Trainer] Ошибка подбора параметров GridSearchCV: {e}", exc_info=False)
#         logging.warning(f"[Trainer] Попытка обучения с дефолтными параметрами (на данных после SMOTE)...")
#         try:
#             # Используем стандартные параметры, но на данных после SMOTE (если он был)
#             lgb_clf_default = lgb.LGBMClassifier(random_state=42, n_estimators=150, learning_rate=0.05, num_leaves=31)
#             lgb_clf_default.fit(X_res, y_res, feature_name=features_to_use) # Обучаем на X_res, y_res
#             logging.info(f"[Trainer] Модель (по умолчанию) обучена.")
#             return lgb_clf_default
#         except Exception as e_def:
#             logging.error(f"[Trainer] Ошибка обучения модели (по умолчанию): {e_def}");
#             return None
#
# # --- Функция сохранения модели (ОК) ---
# def save_model(model, player_name):
#     if model is None: return False
#     try:
#         os.makedirs(MODEL_DIR, exist_ok=True)
#         # Создание безопасного имени файла
#         safe_name = "".join(c if c.isalnum() else "_" for c in player_name)
#         model_path = os.path.join(MODEL_DIR, f"{safe_name}_lgbm_model_3class.joblib") # Добавим суффикс
#         joblib.dump(model, model_path)
#         logging.info(f"[Trainer] Модель {player_name} сохранена: {model_path}");
#         return True
#     except Exception as e:
#         logging.error(f"[Trainer] Ошибка сохранения модели {player_name}: {e}");
#         return False
#
# # --- Функция запуска обучения для всех (ОК, расширенный список) ---
# def train_and_save_all_models():
#     # РАСШИРЕННЫЙ СПИСОК ИГРОКОВ ДЛЯ ТЕСТА
#     players_to_train = [
#        "Pervis Estupiñán 103", "João Neves 103", "Daniel Muñoz 105"
#     ]
#
#     if not players_to_train:
#         logging.warning("[Trainer] Нет игроков для тестового обучения."); return
#
#     logging.info("Загрузка конфига для обучения...");
#     player_configs = config.load_players();
#     if not player_configs:
#         logging.error("[Trainer] Не удалось загрузить player_configs.json."); return
#
#     logging.info(f"[Trainer] Начало РАСШИРЕННОГО ТЕСТОВОГО обучения (3 КЛАССА, с GridSearchCV и SMOTE) для {len(players_to_train)} игроков...")
#     success_count = 0
#     failed_players = []
#
#     for player in players_to_train:
#         logging.info(f"--- Обучение для: {player} ---")
#         if player not in player_configs:
#             logging.warning(f"Игрок {player} не найден в конфиге.")
#             failed_players.append(f"{player} (нет в конфиге)")
#             continue
#
#         # 1. Подготовка фичей
#         features_df = prepare_features_for_player(player, player_configs=player_configs)
#         if features_df is None or features_df.empty:
#             logging.error(f"Не удалось подготовить фичи для {player}.")
#             failed_players.append(f"{player} (ошибка фичей)")
#             continue
#
#         # 2. Обучение модели (теперь с GridSearchCV и корректной 3-классовой целью)
#         model = train_model_for_player(player, features_df)
#         if model is None:
#             logging.error(f"Не удалось обучить модель для {player}.")
#             failed_players.append(f"{player} (ошибка обучения/подбора)")
#             continue
#
#         # 3. Сохранение модели
#         if save_model(model, player):
#             success_count += 1
#         else:
#             failed_players.append(f"{player} (ошибка сохранения)")
#
#     logging.info(f"[Trainer] Тестовое обучение завершено. Успешно сохранено: {success_count}/{len(players_to_train)}")
#     if failed_players:
#         logging.warning(f"[Trainer] Не удалось обучить/сохранить модели для: {', '.join(failed_players)}")
#
# # --- Точка входа ---
# if __name__ == "__main__":
#     logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s")
#     # Проверка и создание директории для моделей
#     if not os.path.exists(MODEL_DIR):
#         try:
#             os.makedirs(MODEL_DIR)
#             logging.info(f"Создана директория для моделей: {MODEL_DIR}")
#         except Exception as e:
#             logging.error(f"Не удалось создать директорию {MODEL_DIR}: {e}")
#             # Возможно, стоит прервать выполнение, если директорию не создать
#             exit() # Или обработать иначе
#
#     # Запуск основного процесса обучения
#     train_and_save_all_models()
#
# # =============================================
# # ФАЙЛ: model_trainer.py (ВЕРСИЯ v22.0 - Новые Фичи Этап 1)
# # - ЗАДАЧА: 3-классовая классификация (0, 1, 2)
# # - ДОБАВЛЕНЫ ФИЧИ: ADX(+DI,-DI), Stochastic(K,D), ROC(7), SMA28-based
# # - Используется High/Low из истории для точных расчетов TA-Lib
# # - GridSearchCV, SMOTE, Полный набор фичей (v18 + новые)
# # =============================================
# import pandas as pd
# import numpy as np
# import os
# import logging
# from datetime import datetime, timedelta, timezone
# import lightgbm as lgb
# import joblib
# import cycle_analysis # Используется для read_player_history
# import events_manager
# import config
# import storage # Может понадобиться, если вызывается отсюда
#
# from sklearn.model_selection import GridSearchCV, StratifiedKFold
#
# # --- Проверка и импорт библиотек ---
# try:
#     import ta
#     # Проверим наличие необходимых функций TA-Lib
#     _ = ta.trend.ADXIndicator
#     _ = ta.momentum.StochasticOscillator
#     _ = ta.momentum.ROCIndicator
#     logging.info("Библиотека 'ta' успешно импортирована и содержит нужные функции.")
# except ImportError:
#     logging.error("Библиотека 'ta' не найдена или не установлена. Установите 'pip install ta'.")
#     ta = None
# except AttributeError as e_ta_attr:
#     logging.error(f"Ошибка в библиотеке 'ta': отсутствует необходимая функция ({e_ta_attr}). Убедитесь, что установлена полная версия.")
#     ta = None # Считаем, что библиотека не готова
#
# try:
#     from imblearn.over_sampling import SMOTE
#     logging.info("Библиотека 'imblearn' успешно импортирована.")
# except ImportError:
#     logging.warning("Библиотека 'imblearn' не найдена или не установлена. SMOTE не будет использоваться.")
#     SMOTE = None
#
# # --- Конфигурация ---
# MODEL_DIR = getattr(config, 'MODEL_DIR', 'models')
# TARGET_HORIZON_DAYS = 1
# PRICE_CHANGE_THRESHOLD_PCT = 1.5 # Порог для классов Рост/Падение
#
# # --- ОБНОВЛЕННЫЙ СПИСОК ФИЧЕЙ (v18 + Новые Этап 1) ---
# BASE_FEATURES_V18 = [
#     "rsi_value", "is_rsi_overbought", "is_rsi_oversold", "macd_diff",
#     "bollinger_hband_indicator", "bollinger_lband_indicator", "bollinger_pband", "bollinger_wband",
#     "is_two_rises_anytime", "is_start_rise_after_drop", "breakout_7d_up", "breakout_7d_down",
#     "breakout_14d_up", "breakout_14d_down", "is_all_time_high", "is_all_time_low",
#     "seasonal_dow_avg_signal_buy", "seasonal_dow_avg_signal_sell", "dow_deviation_from_avg",
#     "dow_range_position", "dom_avg_signal_buy", "dom_avg_signal_sell", "dom_deviation_from_avg",
#     "trend_10d_deviation_sko", "days_in_cycle", "is_cycle_phase_fall", "is_cycle_phase_bottom",
#     "is_cycle_phase_rise", "is_cycle_phase_peak", "is_other_event_active", "is_from_current_event",
#     "dow_sin", "dow_cos", "cycle_day_sin", "cycle_day_cos",
#     "price_lag_1", "rsi_lag_1", "price_div_sma20", "is_above_sma20", "ovr_category",
#     "is_position_CB", "is_position_LB", "is_position_CM", "is_position_RB", "is_position_LM",
#     "is_position_RW", "is_position_ST", "is_position_GK",
#     "is_dow_0", "is_dow_1", "is_dow_2", "is_dow_3", "is_dow_4", "is_dow_5", "is_dow_6",
#     "volatility",
# ]
#
# NEW_FEATURES_STAGE1 = [
#     "adx",          # ADX value (trend strength)
#     "di_pos",       # +DI (positive directional indicator)
#     "di_neg",       # -DI (negative directional indicator)
#     "stoch_k",      # Stochastic %K
#     "stoch_d",      # Stochastic %D (signal line)
#     "roc_7",        # Rate of Change (7 periods)
#     "price_div_sma28", # Price divided by SMA28
#     "sma28_slope",  # Slope of SMA28
# ]
#
# # Объединяем и сортируем
# DEFAULT_FEATURES = sorted(list(set(BASE_FEATURES_V18 + NEW_FEATURES_STAGE1)))
# logging.info(f"Итоговый список фичей ({len(DEFAULT_FEATURES)}): {DEFAULT_FEATURES}")
# # ----------------------------------------------------
#
# # --- 3-классовая цель (Без изменений) ---
# def _get_target(current_price, future_price):
#     """Определяет целевой класс (-1 Падение, 0 Без изм., 1 Рост)."""
#     if current_price is None or future_price is None or pd.isna(current_price) or pd.isna(future_price) or abs(current_price) < 1e-9 :
#         return 0 # Без изм. при некорректных данных
#     try:
#         price_diff_pct = ((future_price - current_price) / current_price) * 100
#         if price_diff_pct > PRICE_CHANGE_THRESHOLD_PCT:
#             return 1 # Рост
#         elif price_diff_pct < -PRICE_CHANGE_THRESHOLD_PCT:
#             return -1 # Падение
#         else:
#             return 0 # Без изм.
#     except (TypeError, ZeroDivisionError):
#         logging.warning(f"Ошибка расчета цели: current={current_price}, future={future_price}", exc_info=False)
#         return 0 # Без изм. при ошибке
# # ------------------------------------
#
# # --- Вспомогательные функции расчета старых фичей (Без изменений v21.1) ---
# def _compute_rsi_hist(prices_series, period=14):
#     # Работает с pd.Series
#     prices_numeric = pd.to_numeric(prices_series, errors='coerce')
#     prices_clean = prices_numeric.dropna()
#     len_clean = len(prices_clean)
#     if len_clean < period + 1:
#         return pd.Series(50.0, index=prices_numeric.index) # Возвращаем 50 для всех исходных индексов
#
#     deltas = prices_clean.diff(1).dropna()
#     if deltas.empty:
#         return pd.Series(50.0, index=prices_numeric.index)
#
#     gain = deltas.clip(lower=0)
#     loss = -deltas.clip(upper=0)
#
#     # Используем EWM для расчета средних
#     avg_gain = gain.ewm(com=period - 1, adjust=False).mean()
#     avg_loss = loss.ewm(com=period - 1, adjust=False).mean()
#
#     # Избегаем деления на ноль или близкое к нулю значение
#     rs = avg_gain / avg_loss.where(avg_loss >= 1e-9, np.nan)
#     rs = rs.replace([np.inf, -np.inf], np.nan).fillna(method='ffill').fillna(100.0) # Заполняем NaN предыдущим или 100
#
#     rsi = 100.0 - (100.0 / (1.0 + rs))
#     rsi = rsi.fillna(method='ffill').fillna(50.0) # Заполняем NaN предыдущим или 50
#
#     # Возвращаем RSI для всех исходных индексов, заполняя пропуски
#     return rsi.reindex(prices_numeric.index).fillna(method='ffill').fillna(50.0)
#
#
# def _check_consecutive_rises_hist(prices, i, threshold=2):
#     if i < threshold : return False
#     count = 0 # Инициализация ПЕРЕД циклом
#     for j in range(i, i - threshold, -1):
#         # Добавлена проверка isfinite
#         if j > 0 and j < len(prices) and (j-1) >= 0 and \
#            prices[j] is not None and prices[j-1] is not None and \
#            isinstance(prices[j], (int, float)) and isinstance(prices[j-1], (int, float)) and \
#            np.isfinite(prices[j]) and np.isfinite(prices[j-1]) and \
#            prices[j] > prices[j-1]:
#             count += 1
#         else:
#             break # Прерываем при первом невыполнении условия
#     return count >= threshold
#
# def _check_start_rise_after_drop_hist(prices, i):
#     if i < 2 or i >= len(prices) or (i-1) < 0 or (i-2) < 0: return False # Проверка границ
#     p1, p2, p3 = prices[i-2], prices[i-1], prices[i]
#     if p1 is None or p2 is None or p3 is None: return False # Проверка None
#     if not (isinstance(p1, (int, float)) and isinstance(p2, (int, float)) and isinstance(p3, (int, float))): return False # Проверка типа
#     # Добавлена проверка isfinite
#     if not (np.isfinite(p1) and np.isfinite(p2) and np.isfinite(p3)): return False
#     return p1 > p2 < p3
#
# def _calculate_dow_metrics(history: list, current_date: datetime) -> tuple[float, float]:
#     # (Версия из model_trainer v21.1) - ОК
#     dow_deviation = 0.0; dow_range_pos = 0.5;
#     if not history: return dow_deviation, dow_range_pos
#     current_dow = current_date.weekday(); current_price_rec = next((r for r in reversed(history) if r.get('date') == current_date), None)
#     current_price = current_price_rec.get('price') if current_price_rec else (history[-1].get('price') if history else None)
#
#     dow_stats = {dow: {"prices": [], "count": 0, "sum_price": 0.0, "min_price": float('inf'), "max_price": float('-inf')} for dow in range(7)}
#     all_prices = []; valid_records = 0
#     for record in history:
#         price = record.get('price'); date = record.get('date')
#         if price is not None and date is not None and isinstance(date, datetime) and np.isfinite(price): # Check isfinite
#             st = dow_stats[date.weekday()]; st["prices"].append(price); st["count"] += 1; st["sum_price"] += price; st["min_price"] = min(st["min_price"], price); st["max_price"] = max(st["max_price"], price); all_prices.append(price); valid_records += 1
#     if valid_records == 0: return dow_deviation, dow_range_pos
#     global_avg_price = np.mean(all_prices) if all_prices else 0; current_dow_data = dow_stats[current_dow]
#     if current_dow_data["count"] > 0 and abs(global_avg_price) > 1e-9:
#         current_dow_avg = current_dow_data["sum_price"] / current_dow_data["count"]
#         if pd.notna(current_dow_avg) and np.isfinite(current_dow_avg): dow_deviation = (current_dow_avg - global_avg_price) / global_avg_price;
#         if not np.isfinite(dow_deviation): dow_deviation = 0.0
#     if current_dow_data["count"] >= 5:
#         h_min = current_dow_data["min_price"]; h_max = current_dow_data["max_price"]
#         if h_min != float('inf') and h_max != float('-inf'):
#              d_range = h_max - h_min
#              if d_range > 1e-9 and current_price is not None and pd.notna(current_price) and np.isfinite(current_price):
#                  pos = (current_price - h_min) / d_range; dow_range_pos = max(0.0, min(1.0, pos));
#                  if not np.isfinite(dow_range_pos): dow_range_pos = 0.5
#              elif d_range <= 1e-9: dow_range_pos = 0.5 # Если диапазон нулевой, ставим середину
#     return dow_deviation, dow_range_pos
#
# def _calculate_dom_metrics(history: list, current_date: datetime) -> float:
#     # (Версия из model_trainer v21.1) - ОК
#     dom_deviation = 0.0;
#     if not history: return dom_deviation
#     current_dom = current_date.day; dom_stats = {day: {"prices": []} for day in range(1, 32)}; all_prices = []
#     for record in history:
#         price = record.get('price'); date = record.get('date')
#         if price is not None and date is not None and isinstance(date, datetime) and np.isfinite(price): # Check isfinite
#              day = date.day;
#              if 1 <= day <= 31:
#                  dom_stats.setdefault(day, {"prices":[]})["prices"].append(price)
#              all_prices.append(price)
#     if not all_prices: return dom_deviation
#     global_avg_price = np.mean(all_prices) if all_prices else 0; current_dom_prices = dom_stats.get(current_dom, {}).get("prices", [])
#     if current_dom_prices and abs(global_avg_price) > 1e-9:
#          current_dom_avg = np.mean(current_dom_prices)
#          dom_deviation = (current_dom_avg - global_avg_price) / global_avg_price
#          if not np.isfinite(dom_deviation): dom_deviation = 0.0 # Проверка на inf/-inf
#     return dom_deviation
#
# def _calculate_trend_sko(history: list, current_date: datetime) -> float:
#      # (Версия из model_trainer v21.1) - ОК
#      trend_sko = 0.0
#      if len(history) < 30: return trend_sko
#      t10 = current_date - timedelta(days=10); t20 = current_date - timedelta(days=20)
#      # Используем только конечные (finite) цены
#      history_before_now = [r for r in history if r.get('date') and isinstance(r['date'], datetime) and r['date'] < current_date and r.get('price') is not None and np.isfinite(r['price'])]
#      recent_10d_prices = [r['price'] for r in history_before_now if t10 <= r['date']]
#      base_10d_prices = [r['price'] for r in history_before_now if t20 <= r['date'] < t10]
#      if len(recent_10d_prices) < 5 or len(base_10d_prices) < 10: return trend_sko
#      try:
#          avg10 = np.mean(recent_10d_prices); avg_base = np.mean(base_10d_prices); std_base = np.std(base_10d_prices)
#          if std_base > 1e-9:
#              trend_sko = (avg10 - avg_base) / std_base
#              if not np.isfinite(trend_sko): trend_sko = 0.0
#          else:
#              trend_sko = 0.0 # Если стд отклонение 0, то СКО тоже 0
#      except Exception as e:
#          logging.warning(f"Ошибка расчета СКО тренда: {e}")
#          trend_sko = 0.0
#      return trend_sko
#
# # --- Функция подготовки фичей (v22.0 - с новыми фичами) ---
# def prepare_features_for_player(player_name, history_data=None, player_configs=None):
#     """Готовит DataFrame с фичами для обучения модели."""
#     if ta is None:
#         logging.error("Библиотека 'ta' не загружена. Расчет новых фичей невозможен.")
#         return None
#
#     # 1. Загрузка данных
#     if history_data is None:
#         history = cycle_analysis.read_player_history(player_name)
#     else:
#         history = history_data
#
#     if len(history) < 40: # Нужно достаточно данных для SMA28 и других индикаторов
#         logging.warning(f"[Trainer] Мало истории ({len(history)} < 40) для {player_name}. Пропуск.")
#         return None
#
#     if player_configs is None: player_configs = config.load_players()
#     player_info = player_configs.get(player_name, {})
#
#     logging.info(f"[Trainer] Подготовка фичей для {player_name}, записей: {len(history)}")
#
#     # 2. Создание DataFrame с Price, Low, High
#     logging.debug("Создание DataFrame истории с Price, Low, High...")
#     valid_history_full = []
#     required_keys = ['date', 'Цена', 'Мин. цена', 'Макс. цена']
#     for r in history:
#         # Проверяем наличие всех ключей и типов
#         if not all(k in r for k in required_keys): continue
#         dt = r.get('date')
#         price_raw = r.get('Цена')
#         low_raw = r.get('Мин. цена')
#         high_raw = r.get('Макс. цена')
#         if not isinstance(dt, datetime) or price_raw is None or low_raw is None or high_raw is None:
#              continue
#
#         # Конвертация и проверка цен
#         try:
#             p = pd.to_numeric(price_raw, errors='coerce')
#             l = pd.to_numeric(low_raw, errors='coerce')
#             h = pd.to_numeric(high_raw, errors='coerce')
#
#             # Пропускаем строки с нечисловыми или бесконечными значениями
#             if not (pd.notna(p) and pd.notna(l) and pd.notna(h) and np.isfinite(p) and np.isfinite(l) and np.isfinite(h)):
#                  continue
#
#             # Обработка нулевых low/high, если цена не ноль
#             if abs(l) < 1e-9 and abs(p) > 1e-9: l = p
#             if abs(h) < 1e-9 and abs(p) > 1e-9: h = p
#
#             # Корректировка low/high, чтобы low <= price <= high
#             l = min(l, p)
#             h = max(h, p)
#
#             # Проверка, что high >= low (на всякий случай после корректировок)
#             if h < l:
#                  logging.warning(f"Некорректный диапазон H<L ({h}<{l}) для {player_name} в дату {dt}. Используем price как H и L.")
#                  h = l = p # Если high < low, что-то не так, используем цену
#
#             valid_history_full.append({'date': dt, 'price': p, 'low': l, 'high': h})
#         except Exception as e_conv:
#             logging.warning(f"Ошибка конвертации цен для {player_name} в дату {dt}: {e_conv}")
#
#     if not valid_history_full:
#         logging.error(f"Не найдено валидных записей с ценами (price, low, high) для {player_name} после фильтрации.")
#         return None
#
#     df_hist = pd.DataFrame(valid_history_full)
#     df_hist = df_hist.set_index('date')
#     df_hist = df_hist[~df_hist.index.duplicated(keep='last')].sort_index() # Удаляем дубликаты по дате, сортируем
#
#     if df_hist.empty:
#         logging.warning(f"DataFrame df_hist пуст после очистки для {player_name}.")
#         return None
#     logging.info(f"Создан df_hist с {len(df_hist)} записями и колонками: {list(df_hist.columns)}")
#
#     # 3. Предрасчет Индикаторов (Старых и Новых)
#     logging.debug("Предрасчет старых и новых индикаторов...")
#
#     # Старые индикаторы
#     df_hist['rsi'] = _compute_rsi_hist(df_hist['price'], period=14)
#     df_hist['sma20'] = df_hist['price'].rolling(window=20, min_periods=20).mean()
#     try:
#         macd = ta.trend.MACD(close=df_hist['price'], fillna=True)
#         df_hist['macd_diff'] = macd.macd_diff()
#         bbands = ta.volatility.BollingerBands(close=df_hist['price'], fillna=True)
#         df_hist['bollinger_hband_indicator'] = bbands.bollinger_hband_indicator()
#         df_hist['bollinger_lband_indicator'] = bbands.bollinger_lband_indicator()
#         df_hist['bollinger_pband'] = bbands.bollinger_pband()
#         df_hist['bollinger_wband'] = bbands.bollinger_wband()
#     except Exception as e_ta_old:
#         logging.error(f"Ошибка расчета старых TA индикаторов для {player_name}: {e_ta_old}")
#         # Заполняем дефолтами при ошибке
#         for col in ['macd_diff', 'bollinger_hband_indicator', 'bollinger_lband_indicator', 'bollinger_wband']:
#              df_hist[col] = 0.0
#         df_hist['bollinger_pband'] = 0.5
#
#     # Новые индикаторы (Этап 1)
#     try:
#         # ADX
#         adx_indicator = ta.trend.ADXIndicator(high=df_hist['high'], low=df_hist['low'], close=df_hist['price'], window=14, fillna=True)
#         df_hist['adx'] = adx_indicator.adx()
#         df_hist['di_pos'] = adx_indicator.adx_pos()
#         df_hist['di_neg'] = adx_indicator.adx_neg()
#
#         # Stochastic
#         stoch_indicator = ta.momentum.StochasticOscillator(high=df_hist['high'], low=df_hist['low'], close=df_hist['price'], window=14, smooth_window=3, fillna=True)
#         df_hist['stoch_k'] = stoch_indicator.stoch()
#         df_hist['stoch_d'] = stoch_indicator.stoch_signal()
#
#         # ROC
#         df_hist['roc_7'] = ta.momentum.ROCIndicator(close=df_hist['price'], window=7, fillna=True).roc()
#
#         # SMA28-based
#         df_hist['sma28'] = df_hist['price'].rolling(window=28, min_periods=28).mean()
#         # Рассчитываем только там, где sma28 не NaN и не 0
#         mask_sma28 = df_hist['sma28'].notna() & (abs(df_hist['sma28']) > 1e-9)
#         df_hist['price_div_sma28'] = 1.0 # Дефолт
#         df_hist.loc[mask_sma28, 'price_div_sma28'] = df_hist.loc[mask_sma28, 'price'] / df_hist.loc[mask_sma28, 'sma28']
#         # Наклон SMA28 (разница между текущим и предыдущим значением)
#         df_hist['sma28_slope'] = df_hist['sma28'].diff(1)
#
#         logging.info(f"Новые индикаторы (ADX, Stoch, ROC, SMA28) рассчитаны для {player_name}.")
#
#     except Exception as e_ta_new:
#         logging.error(f"Критическая ошибка расчета НОВЫХ TA индикаторов для {player_name}: {e_ta_new}", exc_info=True)
#         # Заполняем дефолтами при ошибке
#         for col in ['adx', 'di_pos', 'di_neg', 'stoch_k', 'stoch_d', 'roc_7', 'price_div_sma28', 'sma28_slope']:
#             if col not in df_hist.columns: df_hist[col] = 0.0
#         # Устанавливаем разумные дефолты где возможно
#         df_hist['adx'] = df_hist['adx'].fillna(20.0) # Нейтральный ADX
#         df_hist['stoch_k'] = df_hist['stoch_k'].fillna(50.0) # Середина диапазона
#         df_hist['stoch_d'] = df_hist['stoch_d'].fillna(50.0)
#         df_hist['roc_7'] = df_hist['roc_7'].fillna(0.0)
#         df_hist['price_div_sma28'] = df_hist['price_div_sma28'].fillna(1.0)
#         df_hist['sma28_slope'] = df_hist['sma28_slope'].fillna(0.0)
#         logging.warning(f"Новые TA индикаторы для {player_name} заполнены дефолтными значениями из-за ошибки.")
#
#     # Очистка NaN после всех расчетов TA-Lib (особенно важно для ROC, diff и т.д.)
#     # Сначала заполняем вперед, потом нулями/дефолтами
#     ta_cols = ['rsi', 'sma20', 'macd_diff', 'bollinger_hband_indicator', 'bollinger_lband_indicator',
#                'bollinger_pband', 'bollinger_wband', 'adx', 'di_pos', 'di_neg', 'stoch_k',
#                'stoch_d', 'roc_7', 'sma28', 'price_div_sma28', 'sma28_slope']
#     for col in ta_cols:
#         if col in df_hist.columns:
#              default_val = 50.0 if 'rsi' in col or 'stoch' in col else (0.5 if 'pband' in col else (1.0 if 'div' in col else 0.0))
#              df_hist[col] = df_hist[col].fillna(method='ffill').fillna(default_val)
#              # Дополнительная проверка на inf/-inf
#              if pd.api.types.is_numeric_dtype(df_hist[col]):
#                  df_hist[col] = df_hist[col].replace([np.inf, -np.inf], default_val)
#         else:
#              logging.warning(f"Колонка {col} отсутствует в df_hist после расчетов.")
#
#     logging.debug("Предрасчет индикаторов завершен.")
#
#     # 4. Генерация Фичей для Каждой Даты
#     features = []
#     event_details_cache = {}
#     # Извлекаем исходный список цен для функций _check...hist
#     # Используем цены из очищенного df_hist для консистентности
#     prices_list_for_checks = df_hist['price'].tolist()
#     dates_for_checks = df_hist.index.tolist() # Индексы df_hist
#
#     n_targetable_rows = len(df_hist) - TARGET_HORIZON_DAYS
#     if n_targetable_rows <= 0:
#         logging.warning(f"[Trainer] Недостаточно данных ({len(df_hist)}) для генерации цели у {player_name}.")
#         return None
#
#     valid_indices = df_hist.index[:n_targetable_rows] # Используем индексы df_hist
#
#     logging.info(f"Начинаем генерацию фичей для {len(valid_indices)} точек данных...")
#     for i, current_date in enumerate(valid_indices):
#         current_df_row = df_hist.loc[current_date] # Строка с предрассчитанными индикаторами
#         current_price = current_df_row['price']
#
#         # Пропускаем, если текущая цена невалидна
#         if pd.isna(current_price) or not np.isfinite(current_price):
#              logging.debug(f"Пропуск точки {current_date} для {player_name} из-за невалидной цены.")
#              continue
#
#         # --- Целевая переменная ---
#         target_date_approx = current_date + timedelta(days=TARGET_HORIZON_DAYS)
#         # Ищем первую дату >= target_date_approx в ИНДЕКСЕ df_hist
#         future_indices = df_hist.index[df_hist.index >= target_date_approx]
#         if not future_indices.empty:
#             target_date_actual = future_indices[0]
#             # Проверяем, есть ли такая дата и цена для нее
#             if target_date_actual in df_hist.index and pd.notna(df_hist.loc[target_date_actual, 'price']):
#                  target_price = df_hist.loc[target_date_actual, 'price']
#                  target = _get_target(current_price, target_price) # Оригинальная цель -1, 0, 1
#             else:
#                  logging.debug(f"Нет валидной целевой цены для {target_date_actual} (искали для {current_date}). Пропуск точки.")
#                  continue # Пропускаем, если нет целевой цены для точной даты
#         else:
#             logging.debug(f"Нет будущих дат >= {target_date_approx} (искали для {current_date}). Пропуск точки.")
#             continue # Пропускаем, если нет будущих дат вообще
#         # --- Конец Целевой переменной ---
#
#         # --- Заполнение Фичей ---
#         date_key = current_date.date()
#         if date_key not in event_details_cache:
#             # Передаем текущую дату для корректной фазы
#             event_details_cache[date_key] = events_manager.get_event_phase_details(now_dt=current_date)
#         event_details = event_details_cache[date_key]
#
#         # Инициализируем вектор нулями или NaN (лучше 0.0)
#         feature_vector = {feat_name: 0.0 for feat_name in DEFAULT_FEATURES}
#
#         # Заполняем из предрассчитанного df_hist
#         for col in df_hist.columns:
#              if col in feature_vector: # Заполняем только те, что есть в DEFAULT_FEATURES
#                 value = current_df_row.get(col)
#                 # Проверяем на NaN/inf перед записью
#                 if isinstance(value, (int, float)) and not np.isfinite(value):
#                     feature_vector[col] = 0.0 # Используем 0.0 как дефолт для невалидных чисел
#                 elif pd.isna(value):
#                      feature_vector[col] = 0.0
#                 else:
#                      feature_vector[col] = value # Записываем валидное значение
#
#         # Фичи, требующие доп. расчетов или исходного списка `history`
#         feature_vector["is_rsi_overbought"] = int(feature_vector["rsi_value"] > 70)
#         feature_vector["is_rsi_oversold"] = int(feature_vector["rsi_value"] < 30)
#
#         # Находим индекс текущей даты в исходном списке history для старых функций
#         # Используем индекс `i` из цикла по valid_indices, т.к. он соответствует df_hist
#         current_hist_index_pos = i # Индекс в df_hist, который мы итерируем
#
#         # Используем prices_list_for_checks (из df_hist) для консистентности
#         feature_vector["is_two_rises_anytime"] = int(_check_consecutive_rises_hist(prices_list_for_checks, current_hist_index_pos))
#         feature_vector["is_start_rise_after_drop"] = int(_check_start_rise_after_drop_hist(prices_list_for_checks, current_hist_index_pos))
#
#         # Лаг цены (берем из prices_list_for_checks)
#         if current_hist_index_pos > 0:
#              prev_price = prices_list_for_checks[current_hist_index_pos - 1]
#              feature_vector["price_lag_1"] = prev_price if pd.notna(prev_price) and np.isfinite(prev_price) else current_price
#         else:
#             feature_vector["price_lag_1"] = current_price
#
#         # Лаг RSI (берем из df_hist)
#         if current_hist_index_pos > 0:
#              prev_date = dates_for_checks[current_hist_index_pos - 1] # Дата предыдущей точки
#              rsi_lag1 = df_hist.loc[prev_date, 'rsi'] # Берем предрассчитанный RSI
#              feature_vector["rsi_lag_1"] = rsi_lag1 # Уже очищен от NaN
#         else:
#              feature_vector["rsi_lag_1"] = 50.0 # Дефолт для первой точки
#
#         # Пробои и Экстремумы (используют чтение истории внутри, оставим пока так)
#         # TODO: Оптимизировать позже, передавая df_hist
#         try:
#              br7 = cycle_analysis.check_historical_breakout(player_name, current_price, days=7) # Использует read_player_history
#              if br7: feature_vector["breakout_7d_up"], feature_vector["breakout_7d_down"] = int("Max" in br7), int("Min" in br7)
#              br14 = cycle_analysis.check_historical_breakout(player_name, current_price, days=14)
#              if br14: feature_vector["breakout_14d_up"], feature_vector["breakout_14d_down"] = int("Max" in br14), int("Min" in br14)
#              at_ext = cycle_analysis.check_all_time_extreme(player_name, current_price) # Использует read_player_history
#              if at_ext: feature_vector["is_all_time_high"], feature_vector["is_all_time_low"] = int("МАКСИМУМ" in at_ext), int("МИНИМУМ" in at_ext)
#         except Exception as e_hist_check:
#             logging.warning(f"Ошибка расчета пробоев/экстремумов для {player_name} на {current_date}: {e_hist_check}")
#
#         # Сезонные и трендовые отклонения (используют исходный history)
#         # Передаем срез истории до текущей даты
#         history_slice_for_seasonal = [r for r in history if r.get('date') and r['date'] <= current_date]
#         dow_dev, dow_pos = _calculate_dow_metrics(history_slice_for_seasonal, current_date)
#         dom_dev = _calculate_dom_metrics(history_slice_for_seasonal, current_date)
#         trend_sko = _calculate_trend_sko(history_slice_for_seasonal, current_date)
#         feature_vector["dow_deviation_from_avg"] = dow_dev # Уже проверено на NaN/inf внутри
#         feature_vector["dow_range_position"] = dow_pos # Уже проверено на NaN/inf внутри
#         feature_vector["dom_deviation_from_avg"] = dom_dev # Уже проверено на NaN/inf внутри
#         feature_vector["trend_10d_deviation_sko"] = trend_sko # Уже проверено на NaN/inf внутри
#
#         # Сезонные сигналы (пока оставляем вызов функций)
#         # TODO: Перенести логику сигналов сюда или сделать расчет фичи до сигнала
#         try:
#             temp_seasonal_signal = cycle_analysis.create_seasonal_signal_example(player_name)
#             feature_vector["seasonal_dow_avg_signal_buy"] = int("BUY" in temp_seasonal_signal)
#             feature_vector["seasonal_dow_avg_signal_sell"] = int("SELL" in temp_seasonal_signal)
#             temp_dom_signal = cycle_analysis.create_day_of_month_signal(player_name)
#             feature_vector["dom_avg_signal_buy"] = int("BUY" in temp_dom_signal)
#             feature_vector["dom_avg_signal_sell"] = int("SELL" in temp_dom_signal)
#         except Exception as e_sig:
#             logging.warning(f"Ошибка расчета сезонных сигналов для {player_name} на {current_date}: {e_sig}")
#
#         # Фичи из event_details (цикл, события)
#         feature_vector["days_in_cycle"] = event_details.get("days_in_cycle", 0)
#         c_phase = event_details.get("main_cycle_phase_raw", "N/A")
#         feature_vector["is_cycle_phase_fall"] = int(c_phase == "Падение")
#         feature_vector["is_cycle_phase_bottom"] = int(c_phase == "Дно/Разворот")
#         feature_vector["is_cycle_phase_rise"] = int(c_phase == "Рост")
#         feature_vector["is_cycle_phase_peak"] = int(c_phase == "Завершение/Пик")
#         feature_vector["is_other_event_active"] = int(event_details.get("is_other_event_active", False))
#
#         # Sin/Cos времени
#         dow = current_date.weekday()
#         feature_vector["dow_sin"] = np.sin(2 * np.pi * dow / 7)
#         feature_vector["dow_cos"] = np.cos(2 * np.pi * dow / 7)
#         current_day_in_cycle = feature_vector["days_in_cycle"]
#         if current_day_in_cycle > 0:
#             norm_cycle_day = current_day_in_cycle - 1
#             feature_vector["cycle_day_sin"] = np.sin(2 * np.pi * norm_cycle_day / 28)
#             feature_vector["cycle_day_cos"] = np.cos(2 * np.pi * norm_cycle_day / 28)
#         # else: остаются 0.0 из инициализации
#
#         # SMA20 фичи
#         sma20_now = current_df_row.get('sma20', 0.0) # Уже очищено от NaN
#         if abs(sma20_now) > 1e-9:
#             feature_vector["price_div_sma20"] = current_price / sma20_now
#         # else: остается 1.0 из инициализации
#         feature_vector["is_above_sma20"] = int(current_price > sma20_now)
#
#         # Конфиг игрока (OVR, Pos, Source)
#         player_info_current = player_configs.get(player_name, {})
#         pos = player_info_current.get("position", "Unknown")
#         ovr = player_info_current.get("ovr", 0)
#         src_type = player_info_current.get("source_event_type", "past")
#         feature_vector["is_from_current_event"] = 1 if src_type == "current" else 0
#
#         # OVR категория
#         if ovr >= 104: feature_vector["ovr_category"] = 3
#         elif ovr >= 101: feature_vector["ovr_category"] = 2
#         elif ovr >= 98: feature_vector["ovr_category"] = 1
#         # else: остается 0 из инициализации
#
#         # Позиция One-Hot
#         pos_map = {"CB": 0, "LB": 0, "CM": 0, "RB": 0, "LM": 0, "RW": 0, "ST": 0, "GK": 0}
#         if pos in pos_map: pos_map[pos] = 1
#         for p_name_key, p_val in pos_map.items(): feature_vector[f"is_position_{p_name_key}"] = p_val
#
#         # День недели One-Hot
#         for d in range(7): feature_vector[f"is_dow_{d}"] = 1 if dow == d else 0
#
#         # Волатильность (копия Bollinger W-Band)
#         feature_vector["volatility"] = feature_vector["bollinger_wband"]
#         # --- Конец Заполнения Фичей ---
#
#         # --- Финальная проверка и добавление ---
#         final_vector_for_df = {}
#         valid_vector = True
#         for feat_name in DEFAULT_FEATURES: # Используем обновленный список
#             value = feature_vector.get(feat_name, 0.0) # Берем значение или дефолт
#             # Проверяем еще раз на всякий случай
#             if value is None or (isinstance(value, (int, float, np.number)) and not np.isfinite(value)):
#                  final_vector_for_df[feat_name] = 0.0
#                  logging.debug(f"Замена невалидного значения {value} на 0.0 для {feat_name} у {player_name} на {current_date}")
#             elif isinstance(value, bool):
#                  final_vector_for_df[feat_name] = int(value)
#             else:
#                  # Попытка конвертации в float, если это не числовой тип (маловероятно здесь)
#                  try:
#                      float_val = float(value)
#                      final_vector_for_df[feat_name] = float_val if np.isfinite(float_val) else 0.0
#                  except (ValueError, TypeError):
#                      final_vector_for_df[feat_name] = 0.0
#                      logging.warning(f"Не удалось конвертировать '{value}' в float для {feat_name} у {player_name} на {current_date}. Заменено на 0.0")
#
#             # Дополнительная проверка на всякий случай
#             if not np.isfinite(final_vector_for_df[feat_name]):
#                  logging.error(f"!!! НЕКОНЕЧНОЕ ЗНАЧЕНИЕ {final_vector_for_df[feat_name]} для {feat_name} у {player_name} на {current_date} ПОСЛЕ ПРОВЕРКИ!")
#                  final_vector_for_df[feat_name] = 0.0
#                  valid_vector = False # Помечаем вектор как потенциально проблемный
#
#         if valid_vector:
#              final_vector_for_df["target"] = target # Оригинальная цель -1, 0, 1
#              final_vector_for_df["date"] = current_date
#              features.append(final_vector_for_df)
#         else:
#              logging.error(f"Вектор фичей для {player_name} на {current_date} содержит неконечные значения и был пропущен.")
#
#
#     if not features:
#         logging.warning(f"[Trainer] Не сгенерировано ни одного валидного вектора фичей для {player_name}.")
#         return None
#
#     # Создаем DataFrame из списка словарей
#     df_features = pd.DataFrame(features)
#
#     # --- ФИНАЛЬНАЯ ПРОВЕРКА КОЛОНОК DataFrame ---
#     logging.debug(f"Финальная проверка колонок DataFrame для {player_name}...")
#     final_cols = DEFAULT_FEATURES + ['target', 'date'] # Все ожидаемые колонки
#     for col in final_cols:
#         if col not in df_features.columns:
#             logging.warning(f"Колонка '{col}' отсутствовала в финальном DataFrame для {player_name}. Добавляем с нулями/дефолтами.")
#             if col == 'target': df_features[col] = 0 # Дефолт для цели
#             elif col == 'date': df_features[col] = pd.NaT # Дефолт для даты
#             else: df_features[col] = 0.0 # Дефолт для фичей
#         else:
#             # Проверка типов и очистка существующих колонок
#             if col != 'date': # Дату не трогаем
#                 # Приводим к числовому типу, заменяя ошибки на NaN
#                 df_features[col] = pd.to_numeric(df_features[col], errors='coerce')
#                 # Заменяем NaN и inf на 0.0 (или другой подходящий дефолт)
#                 default_val = 0.0
#                 if col == 'rsi_value' or 'stoch' in col: default_val = 50.0
#                 elif 'pband' in col: default_val = 0.5
#                 elif 'div' in col: default_val = 1.0
#                 df_features[col] = df_features[col].replace([np.inf, -np.inf], np.nan).fillna(default_val)
#                 # Последняя проверка на isfinite
#                 if not np.all(np.isfinite(df_features[col])):
#                     logging.error(f"!!! НЕ УДАЛОСЬ ОЧИСТИТЬ КОЛОНКУ '{col}' от неконечных значений для {player_name}. Заменяем все на дефолт.")
#                     df_features[col] = default_val # Принудительная замена на дефолт
#
#     # Убедимся, что все фичи имеют тип float
#     for feat in DEFAULT_FEATURES:
#         try:
#              df_features[feat] = df_features[feat].astype(float)
#         except ValueError as e_astype:
#              logging.error(f"!!! Не удалось конвертировать колонку '{feat}' в float для {player_name}: {e_astype}. Заполняем дефолтом.")
#              default_val = 50.0 if 'rsi' in feat or 'stoch' in feat else (0.5 if 'pband' in feat else (1.0 if 'div' in feat else 0.0))
#              df_features[feat] = default_val
#
#     logging.info(f"[Trainer] Сгенерировано {len(df_features)} строк с фичами для {player_name}.")
#     return df_features
# # -----------------------------------------------------------------------
#
# # --- Функция обучения с SMOTE и GridSearchCV (Без изменений v21.1) ---
# def train_model_for_player(player_name, df_features):
#     # (код остается тем же, он будет использовать обновленный DEFAULT_FEATURES
#     #  и DataFrame df_features с новыми колонками)
#     if df_features is None or df_features.empty or 'target' not in df_features.columns:
#         logging.error(f"[Trainer] Нет данных/цели для {player_name}"); return None
#
#     if SMOTE is None: logging.warning("Библиотека 'imblearn' не установлена. Обучение без SMOTE."); use_smote=False
#     else: use_smote=True
#
#     # Используем DEFAULT_FEATURES (который теперь включает новые фичи)
#     features_to_use = [f for f in DEFAULT_FEATURES if f in df_features.columns];
#     missing_features = set(DEFAULT_FEATURES) - set(features_to_use)
#     if missing_features:
#         logging.error(f"[Trainer] Отсутствуют ожидаемые фичи {missing_features} перед обучением у {player_name}. Заполнение нулями...");
#         for feat in missing_features:
#             df_features[feat] = 0.0
#         features_to_use = DEFAULT_FEATURES # Обновляем список используемых фич
#
#     X = df_features[features_to_use]
#     y = df_features['target'] # Оригинальная цель: -1, 0, 1
#
#     # --- Очистка X ---
#     numeric_cols = X.select_dtypes(include=np.number).columns
#     if X[numeric_cols].isnull().values.any() or not np.all(np.isfinite(X[numeric_cols].values)):
#          logging.warning(f"[Trainer] NaN/inf в X перед очисткой для {player_name}. Очистка...");
#          for col in numeric_cols:
#              # Заполняем нулем, можно уточнить дефолты, если нужно
#              X[col] = X[col].fillna(0).replace([np.inf, -np.inf], 0)
#          if X[numeric_cols].isnull().values.any() or not np.all(np.isfinite(X[numeric_cols].values)):
#              logging.error(f"[Trainer] Очистка X не удалась для {player_name}."); return None
#     logging.debug(f"Размерность X после очистки для {player_name}: {X.shape}")
#
#     # --- Очистка y и выравнивание с X ---
#     y = y.dropna()
#     X = X.loc[y.index] # Важно: выровнять X по индексам чистого y
#
#     # --- ** КОРРЕКТНАЯ ПОДГОТОВКА ЦЕЛИ ДЛЯ 3-КЛАССОВОГО LGBM ** ---
#     # Маппинг: -1 -> 0 (Падение), 0 -> 1 (Без изм.), 1 -> 2 (Рост)
#     y_mapped = y + 1
#     # ----------------------------------------------------------
#
#     # --- Проверка количества классов ---
#     if y_mapped.nunique() < 2:
#         logging.warning(f"[Trainer] Мало уникальных классов ({y_mapped.nunique()}) для {player_name} после маппинга. Пропуск обучения.");
#         return None
#
#     if len(X) < 15 :
#         logging.warning(f"[Trainer] Слишком мало данных ({len(X)}) для CV у {player_name}. Пропуск обучения.");
#         return None
#
#     X_res, y_res = X, y_mapped # Инициализация для случая без SMOTE
#
#     # --- Применение SMOTE ---
#     if use_smote:
#         logging.info(f"[Trainer] Применение SMOTE для {player_name}... Исходные классы (0,1,2): {np.bincount(y_mapped.astype(int))}")
#         try:
#             min_samples = y_mapped.value_counts().min()
#             # Убедимся, что k_neighbors > 0
#             n_neighbors_smote = max(1, min(5, min_samples - 1))
#
#             # Условие для применения SMOTE: достаточно сэмплов в мин. классе
#             if min_samples > n_neighbors_smote :
#                 smote = SMOTE(random_state=42, k_neighbors=n_neighbors_smote)
#                 X_res, y_res = smote.fit_resample(X, y_mapped) # Используем X и y_mapped
#                 logging.info(f"[Trainer] SMOTE завершен. Новые классы (0,1,2): {np.bincount(y_res.astype(int))}")
#             else:
#                 logging.warning(f"Недостаточно образцов ({min_samples}) для SMOTE с k={n_neighbors_smote} у {player_name}. Обучение без SMOTE.")
#                 # X_res, y_res остаются равными X, y_mapped
#         except ValueError as e_smote_val:
#              # Часто возникает, если k_neighbors >= числу сэмплов в классе
#              logging.error(f"[Trainer] Ошибка ValueError при SMOTE у {player_name}: {e_smote_val}. Обучение без SMOTE.")
#         except Exception as e_smote:
#             logging.error(f"[Trainer] Неизвестная ошибка SMOTE у {player_name}: {e_smote}. Обучение без SMOTE.", exc_info=True)
#             # X_res, y_res остаются равными X, y_mapped
#
#     logging.info(f"[Trainer] Подбор гиперпараметров (GridSearchCV) LGBM для {player_name} ({len(X_res)} примеров, {y_res.nunique()} классов)...")
#
#     # --- GridSearchCV ---
#     try:
#         # Сетка параметров (можно будет тюнить дальше)
#         param_grid = {
#             'n_estimators': [100, 200], # Можно увеличить
#             'learning_rate': [0.05, 0.1],
#             'num_leaves': [20, 31, 40], # 31 - стандарт
#             'max_depth': [-1, 10, 15], # Ограничение глубины может помочь
#             'reg_alpha': [0, 0.01, 0.1], # L1
#             'reg_lambda': [0, 0.01, 0.1] # L2
#         }
#         # Модель LGBM для мультикласса
#         lgbm = lgb.LGBMClassifier(objective='multiclass',
#                                   num_class=3, # Явно указываем число классов
#                                   random_state=42,
#                                   n_jobs=1) # Используем 1 ядро внутри LGBM для стабильности с GridSearchCV
#
#         # Стратегия CV
#         min_samples_cv = pd.Series(y_res).value_counts().min()
#         # Убедимся, что сплитов не больше, чем сэмплов в самом малом классе
#         n_cv_splits = max(2, min(3, min_samples_cv))
#
#         if n_cv_splits > len(X_res):
#              logging.warning(f"Невозможно выполнить CV: n_splits ({n_cv_splits}) > n_samples ({len(X_res)}). Пропуск CV.")
#              raise ValueError("Insufficient samples for CV splits")
#         if min_samples_cv < n_cv_splits:
#              logging.warning(f"Недостаточно образцов в классе ({min_samples_cv}) для CV с {n_cv_splits} сплитами. Уменьшаем n_splits до {min_samples_cv}.")
#              n_cv_splits = min_samples_cv if min_samples_cv >= 2 else 2 # Минимум 2 сплита
#
#         # Проверка еще раз после корректировки
#         if n_cv_splits < 2 or len(X_res) < n_cv_splits:
#             logging.warning(f"Невозможно выполнить CV ({n_cv_splits} сплитов) для {len(X_res)} образцов. Обучение с дефолтными параметрами.")
#             raise ValueError("Insufficient samples for CV")
#
#         cv_strategy = StratifiedKFold(n_splits=n_cv_splits, shuffle=True, random_state=42)
#
#         # Запуск GridSearchCV
#         # n_jobs=4 - распараллеливание по фолдам CV
#         grid_search = GridSearchCV(estimator=lgbm,
#                                    param_grid=param_grid,
#                                    scoring='f1_macro',
#                                    cv=cv_strategy,
#                                    n_jobs=4,
#                                    verbose=1,
#                                    error_score='raise') # Падать при ошибке в фолде
#
#         # Обучаем на данных после SMOTE (X_res, y_res)
#         # Передаем список фичей для возможного использования в логах LGBM
#         grid_search.fit(X_res, y_res, feature_name=features_to_use)
#
#         logging.info(f"[Trainer] Подбор завершен. Лучший score (f1_macro): {grid_search.best_score_:.4f}")
#         logging.info(f"[Trainer] Лучшие параметры: {grid_search.best_params_}")
#         best_model = grid_search.best_estimator_
#
#         # Вывод важности фичей
#         try:
#             # Убедимся, что используем правильный список фичей
#             feature_names_for_imp = X_res.columns.tolist()
#             imp = pd.DataFrame({
#                 'Value': best_model.feature_importances_,
#                 'Feature': feature_names_for_imp
#                  }).sort_values(by="Value", ascending=False).head(20) # Покажем топ 20
#             logging.info(f"Топ фичей (лучшая модель) {player_name}:\n{imp}")
#         except Exception as e_imp:
#              logging.warning(f"Ошибка вывода важности фичей для {player_name}: {e_imp}")
#
#         return best_model
#
#     except Exception as e_grid:
#         logging.error(f"[Trainer] Ошибка подбора параметров GridSearchCV для {player_name}: {e_grid}", exc_info=True)
#         logging.warning(f"[Trainer] Попытка обучения с дефолтными параметрами (на данных после SMOTE)...")
#         try:
#             # Используем стандартные параметры, но на данных после SMOTE
#             lgb_clf_default = lgb.LGBMClassifier(objective='multiclass', num_class=3, random_state=42,
#                                                  n_estimators=150, learning_rate=0.05, num_leaves=31)
#             # Передаем список фичей для модели
#             lgb_clf_default.fit(X_res, y_res, feature_name=features_to_use)
#             logging.info(f"[Trainer] Модель (по умолчанию) обучена для {player_name}.")
#             return lgb_clf_default
#         except Exception as e_def:
#             logging.error(f"[Trainer] Ошибка обучения модели (по умолчанию) для {player_name}: {e_def}", exc_info=True);
#             return None
# # --------------------------------------------------------------------
#
# # --- Функция сохранения модели (Без изменений v21.1) ---
# def save_model(model, player_name):
#     if model is None: return False
#     try:
#         os.makedirs(MODEL_DIR, exist_ok=True)
#         safe_name = "".join(c if c.isalnum() else "_" for c in player_name)
#         model_path = os.path.join(MODEL_DIR, f"{safe_name}_lgbm_model_3class.joblib") # Имя файла 3-классовой модели
#         joblib.dump(model, model_path)
#         logging.info(f"[Trainer] Модель {player_name} сохранена: {model_path}");
#         return True
#     except Exception as e:
#         logging.error(f"[Trainer] Ошибка сохранения модели {player_name}: {e}");
#         return False
#
# # --- Функция запуска обучения для всех (Без изменений v21.1, использует список игроков) ---
# def train_and_save_all_models():
#     # Укажите здесь список игроков для обучения (можно полный или тестовый)
#     players_to_train = [
#        "Pervis Estupiñán 103", "João Neves 103", "Daniel Muñoz 105" # Пример тестового списка
#        # "David López 103", "Fred 103", "Vanderson 100", "Subhasish Bose 103",
#        # "Scott McTominay 103", "Curtis Jones 102", "Pedri 102", "Pervis Estupiñán 103",
#        # "Leandro Paredes 103", "Marcos Acuña 105", "Daniel Muñoz 105", "Sandesh Jhingan 104",
#        # "Anirudh Thapa 103", "Nuno Tavares 103", "João Neves 103", "Calvin Verdonk 101",
#        # "Paulo Futre LM 102 4 ранг", "Benjamin Pavard CB 101", "Rodrigo De Paul 103"
#     ]
#
#     if not players_to_train:
#         logging.warning("[Trainer] Список игроков для обучения пуст."); return
#
#     logging.info("Загрузка конфига игроков для обучения...");
#     player_configs = config.load_players();
#     if not player_configs:
#         logging.error("[Trainer] Не удалось загрузить player_configs.json. Обучение прервано."); return
#
#     logging.info(f"[Trainer] Начало обучения моделей (v22.0 - Новые фичи Этап 1) для {len(players_to_train)} игроков...")
#     success_count = 0
#     failed_players = []
#
#     for player in players_to_train:
#         logging.info(f"--- Обучение для: {player} ---")
#         if player not in player_configs:
#             logging.warning(f"Игрок {player} не найден в конфиге. Пропуск.")
#             failed_players.append(f"{player} (нет в конфиге)")
#             continue
#
#         # 1. Подготовка фичей (теперь с новыми индикаторами)
#         features_df = prepare_features_for_player(player, player_configs=player_configs)
#         if features_df is None or features_df.empty:
#             logging.error(f"Не удалось подготовить фичи для {player}. Пропуск.")
#             failed_players.append(f"{player} (ошибка фичей)")
#             continue
#
#         # 2. Обучение модели
#         model = train_model_for_player(player, features_df)
#         if model is None:
#             logging.error(f"Не удалось обучить модель для {player}. Пропуск.")
#             failed_players.append(f"{player} (ошибка обучения/подбора)")
#             continue
#
#         # 3. Сохранение модели
#         if save_model(model, player):
#             success_count += 1
#         else:
#             failed_players.append(f"{player} (ошибка сохранения)")
#
#     logging.info(f"[Trainer] Обучение завершено. Успешно сохранено: {success_count}/{len(players_to_train)}")
#     if failed_players:
#         logging.warning(f"[Trainer] Не удалось обучить/сохранить модели для: {', '.join(failed_players)}")
#
# # --- Точка входа ---
# if __name__ == "__main__":
#     # Настройка базового логгирования
#     logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s")
#
#     # Проверка и создание директории для моделей
#     if not os.path.exists(MODEL_DIR):
#         try:
#             os.makedirs(MODEL_DIR)
#             logging.info(f"Создана директория для моделей: {MODEL_DIR}")
#         except Exception as e:
#             logging.error(f"Не удалось создать директорию {MODEL_DIR}: {e}")
#             exit() # Прерываем выполнение, если директорию не создать
#
#     # Проверка наличия библиотеки TA-Lib перед запуском
#     if ta is None:
#          logging.error("Обучение не может быть запущено, т.к. библиотека 'ta' не найдена или не инициализирована.")
#     else:
#          # Запуск основного процесса обучения
#          train_and_save_all_models()

# =============================================
# ФАЙЛ: model_trainer.py (ВЕРСИЯ v22.2 - Полная с train_models_if_needed и испр. Aroon)
# - ДОБАВЛЕНО: Функция train_models_if_needed для запуска обучения по условию.
# - ИСПРАВЛЕНО: Инициализация AroonIndicator в prepare_features_for_player.
# - ИЗМЕНЕНО: prepare_features_for_player теперь ожидает и использует high/low из history.
# - Используются фичи и логика из v22.0.
# =============================================
import pandas as pd
import numpy as np
import os
import logging
from datetime import datetime, timedelta, timezone
import lightgbm as lgb
import joblib
from sklearn.model_selection import train_test_split, StratifiedKFold, GridSearchCV
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix
import config
import storage # Нужен для get_player_filepath
import cycle_analysis # Нужен для read_player_history
import events_manager # Нужен для расчета фичей

# --- Проверка и импорт библиотек ---
try:
    import ta
    _ = ta.trend.ADXIndicator
    _ = ta.momentum.StochasticOscillator
    _ = ta.momentum.ROCIndicator
    _ = ta.trend.AroonIndicator # Проверяем наличие Aroon
    logging.info("Библиотека 'ta' успешно импортирована и содержит нужные функции.")
except ImportError:
    logging.error("Библиотека 'ta' не найдена или не установлена. Установите 'pip install ta'.")
    ta = None
except AttributeError as e_ta_attr:
    logging.error(f"Ошибка в библиотеке 'ta': отсутствует необходимая функция ({e_ta_attr}). Убедитесь, что установлена полная версия.")
    ta = None

try:
    from imblearn.over_sampling import SMOTE
    logging.info("Библиотека 'imblearn' успешно импортирована.")
except ImportError:
    logging.warning("Библиотека 'imblearn' не найдена или не установлена. SMOTE не будет использоваться.")
    SMOTE = None

# --- Конфигурация ---
MODEL_DIR = getattr(config, 'MODEL_DIR', 'models')
DATA_DIR = getattr(config, 'DATA_DIR', 'data')
TARGET_COLUMN = 'target_3_class' # Название целевой переменной для 3 классов
TARGET_HORIZON_DAYS = 1 # Горизонт предсказания в днях
PRICE_CHANGE_THRESHOLD_PCT = 1.5 # Порог для классов Рост/Падение

# --- ОБНОВЛЕННЫЙ СПИСОК ФИЧЕЙ (v23.0 - с Aroon и ATR) ---
DEFAULT_FEATURES = [
    'rsi_value', 'rsi_lag_1', 'is_rsi_overbought', 'is_rsi_oversold',
    'macd_diff',
    'bollinger_pband', 'bollinger_wband',
    'stoch_k', 'stoch_d', 'is_stoch_oversold', 'is_stoch_overbought',
    'adx', 'di_pos', 'di_neg', 'is_adx_trending_up', 'is_adx_trending_down', 'is_adx_no_trend',
    'aroon_up', 'aroon_down', 'aroon_oscillator', 'is_aroon_up_strong', 'is_aroon_down_strong', # Aroon
    'roc_14', # Используем ROC(14) из signals
    'atr_14_norm', 'is_atr_high', # ATR
    'sma28_slope', 'price_div_sma28', 'is_above_sma28',
    'price_div_sma20', 'is_above_sma20',
    'is_start_rise_after_drop', 'is_two_rises_anytime',
    'breakout_7d_up', 'breakout_7d_down', 'breakout_14d_up', 'breakout_14d_down',
    'is_ath', 'is_atl',
    'volatility', 'volatility_spike',
    'dow_sin', 'dow_cos',
    'cycle_day_sin', 'cycle_day_cos', 'days_in_cycle',
    'is_cycle_phase_fall', 'is_cycle_phase_bottom', 'is_cycle_phase_rise', 'is_cycle_phase_peak',
    'is_other_event_active',
    'dow_deviation_from_avg', 'dow_range_position', 'dom_deviation_from_avg',
    'trend_10d_deviation_sko',
    'ovr_category', 'is_from_current_event',
    'is_position_CB', 'is_position_LB', 'is_position_CM', 'is_position_RB',
    'is_position_LM', 'is_position_RW', 'is_position_ST', 'is_position_GK',
    'is_dow_0', 'is_dow_1', 'is_dow_2', 'is_dow_3', 'is_dow_4', 'is_dow_5', 'is_dow_6',
    'price_lag_1',
]
DEFAULT_FEATURES = sorted(list(set(DEFAULT_FEATURES))) # Убираем дубликаты и сортируем
logging.info(f"[model_trainer] Итоговый список фичей ({len(DEFAULT_FEATURES)}): {DEFAULT_FEATURES}")
# ----------------------------------------------------

RETRAIN_INTERVAL_DAYS = 7 # Как часто переобучать модели (в днях)

# --- Функция создания целевой переменной (3 класса) ---
def create_target_variable_3class(df, periods=TARGET_HORIZON_DAYS, threshold_pct=PRICE_CHANGE_THRESHOLD_PCT):
    """Создает 3-классовую целевую переменную (0 - Падение, 1 - Без изм., 2 - Рост)."""
    df['future_price'] = df['price'].shift(-periods)
    df_calc = df.dropna(subset=['price', 'future_price']).copy()

    df_calc['price_diff_pct'] = 0.0
    mask = df_calc['price'] != 0
    df_calc.loc[mask, 'price_diff_pct'] = ((df_calc.loc[mask, 'future_price'] - df_calc.loc[mask, 'price']) / df_calc.loc[mask, 'price']) * 100

    conditions = [
        (df_calc['price_diff_pct'] < -threshold_pct),
        (df_calc['price_diff_pct'] > threshold_pct),
    ]
    choices = [0, 2] # 0 - Падение, 2 - Рост
    df_calc[TARGET_COLUMN] = np.select(conditions, choices, default=1) # 1 - Без изм.

    df[TARGET_COLUMN] = df_calc[TARGET_COLUMN]
    df = df.drop(columns=['future_price'])
    df[TARGET_COLUMN] = pd.to_numeric(df[TARGET_COLUMN], errors='coerce') # Приводим к числу, ошибки в NaN
    return df

# --- Вспомогательные функции расчета фичей ---
# Копируем/адаптируем нужные функции из signals.py (или импортируем, если они в отдельном модуле)
# Убедимся, что они принимают нужные аргументы (часто pd.Series или list)

def _compute_rsi_hist(prices_series, period=14):
    if ta is None: return pd.Series(50.0, index=prices_series.index)
    try:
        rsi_indicator = ta.momentum.RSIIndicator(close=prices_series, window=period, fillna=True)
        rsi = rsi_indicator.rsi()
        return rsi.fillna(method='ffill').fillna(50.0)
    except Exception as e:
        logging.warning(f"Ошибка расчета RSI в model_trainer: {e}")
        return pd.Series(50.0, index=prices_series.index)

def _calculate_sma_slope(series: pd.Series, window: int) -> float:
    if series is None or len(series) < window + 1: return 0.0
    try:
        if series.notna().sum() < window + 1: return 0.0
        sma = series.rolling(window=window, min_periods=window).mean().dropna()
        if len(sma) < 2: return 0.0
        y2, y1 = sma.iloc[-1], sma.iloc[-2]
        slope = y2 - y1
        return slope if pd.notna(slope) and np.isfinite(slope) else 0.0
    except Exception: return 0.0

# TODO: Добавить сюда реализации _check_consecutive_rises_hist,
# _check_start_rise_after_drop_hist, _calculate_dow_metrics,
# _calculate_dom_metrics, _calculate_trend_sko, check_historical_breakout,
# check_all_time_extreme, check_volatility_spike из signals.py,
# если они не будут импортированы из другого общего модуля.
# Пока что функции prepare_features_for_player будут использовать заглушки для этих фичей.

# --- Функция подготовки фичей ---
def prepare_features_for_player(player_name, history_data=None, player_configs=None):
    """Готовит DataFrame с фичами для обучения модели."""
    if ta is None:
        logging.error("Библиотека 'ta' не загружена. Расчет фичей невозможен.")
        return None

    # 1. Загрузка данных
    if history_data is None:
        # ИСПОЛЬЗУЕМ cycle_analysis.read_player_history - ОНА УЖЕ ВОЗВРАЩАЕТ dict с date,price,low,high
        history = cycle_analysis.read_player_history(player_name)
    else:
        history = history_data # Предполагаем, что формат такой же

    # Увеличиваем требование к истории, т.к. Aroon(25) требует больше данных
    min_hist_len = 40 # Можно поднять до 50
    if not history or len(history) < min_hist_len:
        logging.warning(f"[Trainer] Мало истории ({len(history)} < {min_hist_len}) для {player_name}. Пропуск.")
        return None

    if player_configs is None: player_configs = config.load_players()
    player_info = player_configs.get(player_name, {})
    if not player_info: logging.warning(f"Конфиг для {player_name} не найден, OVR/Pos/Source будут дефолтными.")

    logging.info(f"[Trainer] Подготовка фичей для {player_name}, записей: {len(history)}")

    # 2. Создание DataFrame
    logging.debug("Создание DataFrame истории...")
    df_hist = pd.DataFrame(history)
    if 'date' not in df_hist.columns:
        logging.error(f"Отсутствует колонка 'date' в данных для {player_name}")
        return None
    try:
        df_hist['date'] = pd.to_datetime(df_hist['date'], errors='coerce', utc=True)
        df_hist = df_hist.dropna(subset=['date'])
        df_hist = df_hist.set_index('date').sort_index()
        df_hist = df_hist[~df_hist.index.duplicated(keep='last')]
    except Exception as e_idx:
        logging.error(f"[Feature Eng] Ошибка установки индекса даты для {player_name}: {e_idx}")
        return None

    # Проверка и приведение типов для цен (price, low, high)
    for col in ['price', 'low', 'high']:
        if col not in df_hist.columns:
            logging.error(f"Отсутствует необходимая колонка '{col}' для {player_name}.")
            return None # Прерываем, если нет нужных колонок
        df_hist[col] = pd.to_numeric(df_hist[col], errors='coerce')

    if 'close' not in df_hist.columns: df_hist['close'] = df_hist['price'] # Используем 'price' как 'close'

    # Удаляем строки с NaN в обязательных колонках
    df_hist = df_hist.dropna(subset=['price', 'low', 'high', 'close'])
    df_hist = df_hist.replace([np.inf, -np.inf], np.nan).dropna()

    # Корректировка low/high (на всякий случай, read_player_history уже должен это делать)
    df_hist['low'] = np.minimum(df_hist['low'], df_hist['price'])
    df_hist['high'] = np.maximum(df_hist['high'], df_hist['price'])
    mask_h_lt_l = df_hist['high'] < df_hist['low']
    if mask_h_lt_l.any(): df_hist.loc[mask_h_lt_l, ['high', 'low']] = df_hist.loc[mask_h_lt_l, 'price']

    if df_hist.empty or len(df_hist) < min_hist_len: # Проверяем еще раз после очистки
        logging.warning(f"DataFrame df_hist пуст или слишком мал ({len(df_hist)}) после очистки для {player_name}.")
        return None

    logging.info(f"Создан df_hist с {len(df_hist)} записями для {player_name}. Колонки: {list(df_hist.columns)}")

    # 3. Расчет Индикаторов
    logging.debug("Расчет TA индикаторов...")
    df_ta = df_hist.copy()

    try:
        # --- Расчеты ТА ---
        close_series = df_ta['close']
        high_series = df_ta['high']
        low_series = df_ta['low']

        # RSI
        rsi_indicator = ta.momentum.RSIIndicator(close=close_series, window=14, fillna=True)
        df_ta['rsi_value'] = rsi_indicator.rsi()
        df_ta['rsi_lag_1'] = df_ta['rsi_value'].shift(1)

        # MACD
        macd_indicator = ta.trend.MACD(close=close_series, fillna=True)
        df_ta['macd_diff'] = macd_indicator.macd_diff()

        # Bollinger
        bb_indicator = ta.volatility.BollingerBands(close=close_series, window=20, window_dev=2, fillna=True)
        df_ta['bollinger_pband'] = bb_indicator.bollinger_pband()
        df_ta['bollinger_wband'] = bb_indicator.bollinger_wband()

        # Stochastic
        stoch_indicator = ta.momentum.StochasticOscillator(high=high_series, low=low_series, close=close_series, window=14, smooth_window=3, fillna=True)
        df_ta['stoch_k'] = stoch_indicator.stoch()
        df_ta['stoch_d'] = stoch_indicator.stoch_signal()

        # ADX
        adx_indicator = ta.trend.ADXIndicator(high=high_series, low=low_series, close=close_series, window=14, fillna=True)
        df_ta['adx'] = adx_indicator.adx()
        df_ta['di_pos'] = adx_indicator.adx_pos()
        df_ta['di_neg'] = adx_indicator.adx_neg()

        # Aroon (ИСПРАВЛЕНО v22.2: Передаем high, low в конструктор)
        aroon_indicator = ta.trend.AroonIndicator(high=high_series, low=low_series, window=25, fillna=True)
        df_ta['aroon_up'] = aroon_indicator.aroon_up() # Методы вызываются без аргументов
        df_ta['aroon_down'] = aroon_indicator.aroon_down()
        df_ta['aroon_oscillator'] = aroon_indicator.aroon_indicator()

        # ROC
        df_ta['roc_14'] = ta.momentum.ROCIndicator(close=close_series, window=14, fillna=True).roc()

        # ATR
        atr_indicator = ta.volatility.AverageTrueRange(high=high_series, low=low_series, close=close_series, window=14, fillna=True)
        df_ta['atr_14'] = atr_indicator.average_true_range()

        # SMA
        df_ta['sma20'] = ta.trend.sma_indicator(close=close_series, window=20, fillna=True)
        df_ta['sma28'] = ta.trend.sma_indicator(close=close_series, window=28, fillna=True)
        df_ta['sma28_slope'] = _calculate_sma_slope(df_ta['sma28'], 1)

        # Волатильность (копия BB Width)
        df_ta['volatility'] = df_ta['bollinger_wband']

        # Лаг цены
        df_ta['price_lag_1'] = df_ta['price'].shift(1)

        logging.info(f"TA индикаторы для {player_name} рассчитаны.")

    except Exception as e_ta_all:
        logging.error(f"Ошибка расчета TA индикаторов для {player_name}: {e_ta_all}", exc_info=True)
        # Заполняем нулями/дефолтами при ошибке (более надежно)
        for col in DEFAULT_FEATURES:
             if col not in df_ta.columns:
                 default_val = 50.0 if 'rsi' in col or 'stoch' in col else (0.5 if 'pband' in col else (1.0 if 'div' in col else 0.0))
                 df_ta[col] = default_val
        logging.warning(f"Расчет TA прерван из-за ошибки, фичи заполнены дефолтами для {player_name}")

    # Заполняем NaN после всех расчетов TA
    df_ta = df_ta.fillna(method='ffill') # Сначала заполняем вперед
    # Затем заполняем оставшиеся NaN нулями или специфичными дефолтами
    df_ta['rsi_value'] = df_ta['rsi_value'].fillna(50.0)
    df_ta['rsi_lag_1'] = df_ta['rsi_lag_1'].fillna(50.0)
    df_ta['bollinger_pband'] = df_ta['bollinger_pband'].fillna(0.5)
    df_ta['stoch_k'] = df_ta['stoch_k'].fillna(50.0)
    df_ta['stoch_d'] = df_ta['stoch_d'].fillna(50.0)
    df_ta['adx'] = df_ta['adx'].fillna(20.0) # Нейтральный
    df_ta['price_div_sma20'] = df_ta['price_div_sma20'].replace([np.inf, -np.inf], 1.0).fillna(1.0)
    df_ta['price_div_sma28'] = df_ta['price_div_sma28'].replace([np.inf, -np.inf], 1.0).fillna(1.0)
    df_ta = df_ta.fillna(0.0) # Все остальные NaN заполняем нулями

    # 4. Генерация Фичей для Каждой Даты (циклы, события, категориальные и т.д.)
    logging.info(f"Генерация остальных фичей для {len(df_ta)} точек данных...")
    features_list = []
    player_pos = player_info.get("position", "Unknown")
    player_ovr = player_info.get("ovr", 0)
    player_src = player_info.get("source_event_type", "past")
    event_details_cache = {}
    history_list_for_checks = df_hist.reset_index().to_dict('records') # Преобразуем в список словарей для старых функций

    df_ta = create_target_variable_3class(df_ta, periods=TARGET_HORIZON_DAYS, threshold_pct=PRICE_CHANGE_THRESHOLD_PCT)
    df_ta = df_ta.dropna(subset=[TARGET_COLUMN]) # Удаляем строки без цели

    if df_ta.empty:
        logging.warning(f"DataFrame пуст после создания цели для {player_name}.")
        return None

    # Расчет фичей, которые требуют итерации или полного history_list_for_checks
    # TODO: Оптимизировать эти расчеты, чтобы избежать итераций и повторных вызовов read_history
    logging.debug("Расчет итеративных/исторических фичей...")
    temp_features = []
    for i, (current_date, row) in enumerate(df_ta.iterrows()):
        current_price = row['price']
        feature_vector = row.to_dict() # Берем предрассчитанные фичи
        feature_vector['date'] = current_date
        feature_vector[TARGET_COLUMN] = int(feature_vector[TARGET_COLUMN]) # Цель уже есть

        # Флаги TA (пересчитываем на всякий случай или берем из df_ta)
        feature_vector['is_rsi_overbought'] = int(feature_vector.get('rsi_value', 50) > 70)
        feature_vector['is_rsi_oversold'] = int(feature_vector.get('rsi_value', 50) < 30)
        feature_vector['is_stoch_overbought'] = int(feature_vector.get('stoch_k', 50) > 80)
        feature_vector['is_stoch_oversold'] = int(feature_vector.get('stoch_k', 50) < 20)
        adx_val = feature_vector.get('adx', 0)
        di_p = feature_vector.get('di_pos', 0)
        di_n = feature_vector.get('di_neg', 0)
        feature_vector['is_adx_trending_up'] = int(adx_val > 25 and di_p > di_n)
        feature_vector['is_adx_trending_down'] = int(adx_val > 25 and di_n > di_p)
        feature_vector['is_adx_no_trend'] = int(adx_val < 20)
        aroon_up_val = feature_vector.get('aroon_up', 0)
        aroon_down_val = feature_vector.get('aroon_down', 0)
        feature_vector['is_aroon_up_strong'] = int(aroon_up_val > 70 and aroon_down_val < 30)
        feature_vector['is_aroon_down_strong'] = int(aroon_down_val > 70 and aroon_up_val < 30)
        feature_vector['is_above_sma20'] = int(current_price > feature_vector.get('sma20', 0)) if pd.notna(feature_vector.get('sma20')) else 0
        feature_vector['is_above_sma28'] = int(current_price > feature_vector.get('sma28', 0)) if pd.notna(feature_vector.get('sma28')) else 0

        # Нормализация ATR и флаг is_atr_high
        atr_val = feature_vector.get('atr_14', 0.0)
        if current_price > 1e-9 and pd.notna(atr_val):
            feature_vector['atr_14_norm'] = (atr_val / current_price) * 100
        else: feature_vector['atr_14_norm'] = 0.0
        feature_vector['is_atr_high'] = int(feature_vector['atr_14_norm'] > ATR_SPIKE_THRESHOLD)

        # Расчеты, требующие среза истории до current_date
        history_slice = [r for r in history_list_for_checks if r['date'] <= current_date]
        prices_slice = [r['price'] for r in history_slice]
        # Находим индекс текущей точки в срезе
        current_index_in_slice = len(prices_slice) - 1

        # Паттерны
        feature_vector['is_two_rises_anytime'] = int(_check_consecutive_rises_hist(prices_slice, current_index_in_slice))
        feature_vector['is_start_rise_after_drop'] = int(_check_start_rise_after_drop_hist(prices_slice, current_index_in_slice))

        # Пробои и Экстремумы (требуют полного history, вызываем здесь)
        # Это неэффективно, но пока оставляем для совместимости
        # try:
        #      br7 = cycle_analysis.check_historical_breakout(player_name, current_price, days=7)
        #      if br7: feature_vector["breakout_7d_up"], feature_vector["breakout_7d_down"] = int(br7['type'] == 'breakout_max'), int(br7['type'] == 'breakout_min')
        #      br14 = cycle_analysis.check_historical_breakout(player_name, current_price, days=14)
        #      if br14: feature_vector["breakout_14d_up"], feature_vector["breakout_14d_down"] = int(br14['type'] == 'breakout_max'), int(br14['type'] == 'breakout_min')
        #      at_ext = cycle_analysis.check_all_time_extreme(player_name, current_price)
        #      if at_ext: feature_vector["is_ath"], feature_vector["is_atl"] = int(at_ext['type'] == 'ath'), int(at_ext['type'] == 'atl')
        # except Exception as e_hist_check: logging.warning(f"Ошибка расчета пробоев/экстремумов для {player_name} на {current_date}: {e_hist_check}")
        # ЗАГЛУШКИ:
        feature_vector['breakout_7d_up'] = 0; feature_vector['breakout_7d_down'] = 0
        feature_vector['breakout_14d_up'] = 0; feature_vector['breakout_14d_down'] = 0
        feature_vector['is_ath'] = 0; feature_vector['is_atl'] = 0

        # Сезонные и трендовые отклонения
        dow_dev, dow_pos = _calculate_dow_metrics(history_slice, current_date)
        dom_dev = _calculate_dom_metrics(history_slice, current_date)
        trend_sko = _calculate_trend_sko(history_slice, current_date)
        feature_vector["dow_deviation_from_avg"] = dow_dev
        feature_vector["dow_range_position"] = dow_pos
        feature_vector["dom_deviation_from_avg"] = dom_dev
        feature_vector["trend_10d_deviation_sko"] = trend_sko

        # Цикл/События
        date_key = current_date.date()
        if date_key not in event_details_cache: event_details_cache[date_key] = events_manager.get_event_phase_details(now_dt=current_date)
        event_details = event_details_cache[date_key]
        feature_vector["days_in_cycle"] = event_details.get("days_in_cycle", 0)
        c_phase = event_details.get("main_cycle_phase_raw", "N/A")
        feature_vector["is_cycle_phase_fall"] = int(c_phase == "Падение")
        feature_vector["is_cycle_phase_bottom"] = int(c_phase == "Дно/Разворот")
        feature_vector["is_cycle_phase_rise"] = int(c_phase == "Рост")
        feature_vector["is_cycle_phase_peak"] = int(c_phase == "Завершение/Пик")
        feature_vector["is_other_event_active"] = int(event_details.get("is_other_event_active", False))

        # Время (Sin/Cos)
        dow = current_date.weekday()
        feature_vector["dow_sin"] = np.sin(2 * np.pi * dow / 7)
        feature_vector["dow_cos"] = np.cos(2 * np.pi * dow / 7)
        current_day_in_cycle = feature_vector["days_in_cycle"]
        if current_day_in_cycle > 0: norm_cycle_day = current_day_in_cycle - 1; feature_vector["cycle_day_sin"] = np.sin(2 * np.pi * norm_cycle_day / 28); feature_vector["cycle_day_cos"] = np.cos(2 * np.pi * norm_cycle_day / 28)
        else: feature_vector["cycle_day_sin"] = 0.0; feature_vector["cycle_day_cos"] = 0.0

        # OVR Категория
        if player_ovr >= 104: feature_vector["ovr_category"] = 3
        elif player_ovr >= 101: feature_vector["ovr_category"] = 2
        elif player_ovr >= 98: feature_vector["ovr_category"] = 1
        else: feature_vector["ovr_category"] = 0

        # Источник игрока
        feature_vector["is_from_current_event"] = 1 if player_src == "current" else 0

        # Позиция One-Hot
        pos_keys = ["CB", "LB", "CM", "RB", "LM", "RW", "ST", "GK"]
        for p_key in pos_keys: feature_vector[f"is_position_{p_key}"] = 0
        if player_pos in pos_keys: feature_vector[f"is_position_{player_pos}"] = 1

        # DOW One-Hot
        for d in range(7): feature_vector[f"is_dow_{d}"] = 1 if dow == d else 0

        # Финальная проверка и добавление
        final_vector_for_df = {}
        valid_vector = True
        for feat_name in DEFAULT_FEATURES + [TARGET_COLUMN]: # Проверяем все, включая цель
             value = feature_vector.get(feat_name)
             if value is None or (isinstance(value, (float, np.number)) and not np.isfinite(value)):
                  logging.debug(f"Замена невалидного значения {value} на 0.0 для {feat_name} у {player_name} на {current_date}")
                  final_vector_for_df[feat_name] = 0.0
                  if feat_name != TARGET_COLUMN: valid_vector = False # Считаем вектор невалидным, если фича плохая
             else:
                  final_vector_for_df[feat_name] = value

        if valid_vector:
            features_list.append(final_vector_for_df)
        else:
            logging.warning(f"Вектор фичей для {player_name} на {current_date} содержал невалидные значения и был пропущен.")

    if not features_list:
        logging.warning(f"[Trainer] Не сгенерировано ни одного валидного вектора фичей для {player_name} после итераций.")
        return None

    df_final = pd.DataFrame(features_list)
    df_final = df_final.set_index('date') # Устанавливаем дату как индекс

    # Отбираем только нужные колонки
    final_cols = DEFAULT_FEATURES + [TARGET_COLUMN]
    df_final = df_final[[col for col in final_cols if col in df_final.columns]]

    # Проверка типов и финальная очистка
    for col in DEFAULT_FEATURES:
        if col in df_final.columns:
            if not pd.api.types.is_numeric_dtype(df_final[col]):
                df_final[col] = pd.to_numeric(df_final[col], errors='coerce')
            default_val = 50.0 if 'rsi' in col or 'stoch' in col else (0.5 if 'pband' in col else (1.0 if 'div' in col else 0.0))
            df_final[col] = df_final[col].replace([np.inf, -np.inf], np.nan).fillna(default_val)

    df_final = df_final.dropna() # Удаляем строки с NaN, которые могли остаться (особенно в target)

    if df_final.empty:
         logging.warning(f"[Trainer] DataFrame пуст после финальной очистки для {player_name}.")
         return None

    logging.info(f"[Trainer] Успешно сгенерировано {len(df_final)} строк с фичами для {player_name}.")
    return df_final


# --- Функция обучения модели ---
def train_model_for_player(player_name, df_features):
    """Обучает модель LGBM с GridSearchCV и (опционально) SMOTE."""
    if df_features is None or df_features.empty or TARGET_COLUMN not in df_features.columns:
        logging.error(f"[Trainer] Нет данных/цели для обучения {player_name}."); return None

    use_smote = SMOTE is not None

    features_to_use = [f for f in DEFAULT_FEATURES if f in df_features.columns]
    if len(features_to_use) != len(DEFAULT_FEATURES):
        logging.error(f"[Trainer] Не все ожидаемые фичи присутствуют для {player_name}. Пропуск.")
        return None

    X = df_features[features_to_use]
    y = df_features[TARGET_COLUMN].astype(int) # Цель уже 0, 1, 2

    # Проверка и очистка X
    numeric_cols = X.select_dtypes(include=np.number).columns
    if X[numeric_cols].isnull().values.any() or not np.all(np.isfinite(X[numeric_cols].values)):
         logging.warning(f"[Trainer] Обнаружены NaN/inf в X перед обучением для {player_name}. Очистка нулями...")
         for col in numeric_cols: X[col] = X[col].fillna(0).replace([np.inf, -np.inf], 0)
         if X[numeric_cols].isnull().values.any() or not np.all(np.isfinite(X[numeric_cols].values)):
             logging.error(f"[Trainer] Очистка X не удалась для {player_name}. Пропуск обучения."); return None

    if y.nunique() < 2: logging.warning(f"[Trainer] Менее 2 классов в y для {player_name}. Пропуск обучения."); return None
    if len(X) < 15: logging.warning(f"[Trainer] Слишком мало данных ({len(X)}) для CV у {player_name}. Пропуск обучения."); return None

    X_res, y_res = X, y

    if use_smote:
        logging.info(f"[Trainer] Применение SMOTE для {player_name}... Исходные классы: {np.bincount(y.astype(int))}")
        try:
            min_samples = y.value_counts().min()
            n_neighbors_smote = max(1, min(5, min_samples - 1))
            if min_samples > n_neighbors_smote :
                smote = SMOTE(random_state=42, k_neighbors=n_neighbors_smote)
                X_res, y_res = smote.fit_resample(X, y)
                logging.info(f"[Trainer] SMOTE завершен. Новые классы: {np.bincount(y_res.astype(int))}")
            else: logging.warning(f"Недостаточно образцов ({min_samples}) для SMOTE с k={n_neighbors_smote} у {player_name}. Обучение без SMOTE.")
        except ValueError as e_smote_val: logging.error(f"[Trainer] Ошибка ValueError при SMOTE у {player_name}: {e_smote_val}. Обучение без SMOTE.")
        except Exception as e_smote: logging.error(f"[Trainer] Неизвестная ошибка SMOTE у {player_name}: {e_smote}. Обучение без SMOTE.", exc_info=True)

    logging.info(f"[Trainer] Подбор гиперпараметров (GridSearchCV) LGBM для {player_name} ({len(X_res)} примеров, {y_res.nunique()} классов)...")

    try:
        param_grid = { 'n_estimators': [100, 200, 300], 'learning_rate': [0.05, 0.1], 'num_leaves': [20, 31] }
        lgbm = lgb.LGBMClassifier(objective='multiclass', num_class=3, random_state=42, n_jobs=1, verbose=-1)

        min_samples_cv = pd.Series(y_res).value_counts().min()
        n_cv_splits = max(2, min(3, min_samples_cv))
        if n_cv_splits < 2 or len(X_res) < n_cv_splits: raise ValueError(f"Insufficient samples ({len(X_res)}) or classes for CV ({n_cv_splits} splits)")

        cv_strategy = StratifiedKFold(n_splits=n_cv_splits, shuffle=True, random_state=42)
        grid_search = GridSearchCV(estimator=lgbm, param_grid=param_grid, scoring='f1_macro', cv=cv_strategy, n_jobs=4, verbose=0, error_score='raise')
        grid_search.fit(X_res, y_res, feature_name=features_to_use)

        logging.info(f"[Trainer] Подбор завершен. Лучший score (f1_macro): {grid_search.best_score_:.4f}")
        logging.info(f"[Trainer] Лучшие параметры: {grid_search.best_params_}")
        best_model = grid_search.best_estimator_

        y_pred_res = best_model.predict(X_res)
        logging.info(f"[Trainer] Отчет по данным после SMOTE (resampled):\n{classification_report(y_res, y_pred_res, zero_division=0)}")

        return best_model

    except Exception as e_grid:
        logging.error(f"[Trainer] Ошибка подбора параметров GridSearchCV для {player_name}: {e_grid}", exc_info=True)
        logging.warning(f"[Trainer] Попытка обучения с дефолтными параметрами...")
        try:
            lgb_clf_default = lgb.LGBMClassifier(objective='multiclass', num_class=3, random_state=42, n_estimators=150, verbose=-1)
            lgb_clf_default.fit(X_res, y_res, feature_name=features_to_use)
            logging.info(f"[Trainer] Модель (по умолчанию) обучена для {player_name}.")
            return lgb_clf_default
        except Exception as e_def: logging.error(f"[Trainer] Ошибка обучения модели (по умолчанию) для {player_name}: {e_def}", exc_info=True); return None

# --- Функция сохранения модели ---
def save_model(model, player_name):
    if model is None: return False
    try:
        os.makedirs(MODEL_DIR, exist_ok=True)
        safe_name = "".join(c if c.isalnum() else "_" for c in player_name)
        model_path = os.path.join(MODEL_DIR, f"{safe_name}_lgbm_model_3class.joblib")
        joblib.dump(model, model_path)
        logging.info(f"[Trainer] Модель {player_name} сохранена: {model_path}");
        return True
    except Exception as e:
        logging.error(f"[Trainer] Ошибка сохранения модели {player_name}: {e}");
        return False

# --- Функция для запуска обучения по необходимости ---
def train_models_if_needed(force_train=False):
    """
    Проверяет, нужно ли переобучать модели, и запускает обучение для всех игроков.
    """
    logging.info("--- Проверка необходимости обучения моделей ---")
    try:
        players = config.load_players()
    except Exception as e_cfg:
        logging.error(f"Ошибка загрузки конфига игроков в model_trainer: {e_cfg}")
        return

    if not players:
        logging.warning("Список игроков пуст, обучение не будет запущено.")
        return

    os.makedirs(MODEL_DIR, exist_ok=True)
    trained_count = 0
    skipped_count = 0

    for player_name in players.keys():
        safe_name = "".join(c if c.isalnum() else "_" for c in player_name)
        model_path = os.path.join(MODEL_DIR, f"{safe_name}_lgbm_model_3class.joblib")
        data_path = storage.get_player_filepath(player_name)
        should_train = False

        if force_train:
            logging.info(f"Принудительное обучение для {player_name}.")
            should_train = True
        elif not os.path.exists(model_path):
            logging.info(f"Модель для {player_name} не найдена. Требуется обучение.")
            should_train = True
        elif os.path.exists(data_path):
            try:
                model_mtime = datetime.fromtimestamp(os.path.getmtime(model_path), tz=timezone.utc)
                data_mtime = datetime.fromtimestamp(os.path.getmtime(data_path), tz=timezone.utc)
                if data_mtime > model_mtime:
                     logging.info(f"Данные для {player_name} новее модели. Требуется переобучение.")
                     should_train = True
                else:
                     time_since_train = datetime.now(timezone.utc) - model_mtime
                     if time_since_train > timedelta(days=RETRAIN_INTERVAL_DAYS):
                         logging.info(f"Модель для {player_name} устарела ({time_since_train.days} дней). Требуется переобучение.")
                         should_train = True
            except Exception as e_time:
                logging.warning(f"Не удалось проверить время модификации файлов для {player_name}: {e_time}. Запускаем обучение.")
                should_train = True
        else:
             logging.warning(f"Нет файла данных {data_path} для {player_name}. Обучение невозможно.")


        if should_train:
            logging.info(f"Запуск создания фичей и обучения для {player_name}...")
            try:
                # Используем prepare_features_for_player ИЗ ЭТОГО ФАЙЛА
                df_features = prepare_features_for_player(player_name, player_configs=players)
                if df_features is not None and not df_features.empty:
                    # Используем train_model_for_player ИЗ ЭТОГО ФАЙЛА
                    model = train_model_for_player(player_name, df_features)
                    if model is not None:
                        # Используем save_model ИЗ ЭТОГО ФАЙЛА
                        if save_model(model, player_name):
                            trained_count += 1
                        else:
                            logging.error(f"Ошибка сохранения модели для {player_name}.")
                            skipped_count += 1
                    else:
                         logging.error(f"Ошибка обучения модели для {player_name}.")
                         skipped_count += 1
                else:
                    logging.warning(f"Не удалось создать/подготовить фичи для {player_name}. Обучение пропущено.")
                    skipped_count += 1
            except Exception as e_train_loop:
                 logging.error(f"Непредвиденная ошибка в цикле обучения для {player_name}: {e_train_loop}", exc_info=True)
                 skipped_count += 1
        else:
            logging.info(f"Переобучение для {player_name} не требуется.")
            skipped_count += 1

    logging.info(f"--- Проверка обучения моделей завершена. Обучено: {trained_count}, Пропущено/Не требовалось: {skipped_count} ---")

# --- Точка входа ---
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s")
    if not os.path.exists(MODEL_DIR):
        try: os.makedirs(MODEL_DIR); logging.info(f"Создана директория для моделей: {MODEL_DIR}")
        except Exception as e: logging.error(f"Не удалось создать директорию {MODEL_DIR}: {e}"); exit()

    if ta is None: logging.error("Обучение не может быть запущено, т.к. библиотека 'ta' не найдена или не инициализирована.")
    else:
        # Запуск обучения с проверкой необходимости
        train_models_if_needed(force_train=False) # Поставьте True для принудительного переобучения всех