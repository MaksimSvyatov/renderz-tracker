# # # =============================================
# # # ФАЙЛ: signals.py (ВЕРСИЯ v22.8 - Запись цены покупки + Улучшенный расчет прибыли)
# # # - ДОБАВЛЕНО: Запись цены покупки в storage.save_purchase_log при сигнале "Strong BUY".
# # # - ИЗМЕНЕНО: _check_exchange_profit_signals теперь использует storage.load_last_purchase_price для расчета прибыли.
# # # - ИСПРАВЛЕНО: NameError 'valid_prices'.
# # # - РАССЧЕТ: Stoch, ADX, ROC, SMA28, ATR, сигналы обмена/прибыли.
# # # - АГРЕГАЦИЯ: check_aggregated_signal_v2 с индивидуальными весами (config v8.x).
# # # - ЗАВИСИМОСТИ: config v8.5+, notifications v9+, ta library, storage.py с функциями save/load_purchase_log.
# # # =============================================
# #
# # import logging
# # from datetime import datetime, timedelta, timezone
# # import os
# # import cycle_analysis
# # import events_manager
# # import pandas as pd
# # import joblib
# # import numpy as np
# # import config # Ожидается config v8.5+
# # import storage # Импортируем storage для лога покупок и других функций
# # import time
# #
# # # --- Импорт библиотек ---
# # try:
# #     import ta
# #     from ta.volatility import BollingerBands, AverageTrueRange
# #     from ta.trend import MACD, ADXIndicator, AroonIndicator, sma_indicator
# #     from ta.momentum import RSIIndicator, StochasticOscillator, ROCIndicator
# #     TA_AVAILABLE = True
# # except ImportError:
# #     logging.error("Библиотека 'ta' или ее компоненты не найдены. Расчет TA будет ограничен.")
# #     TA_AVAILABLE = False
# #     # Определяем заглушки, если ta недоступна
# #     class BollingerBands: __init__(*args, **kwargs); bollinger_hband_indicator = bollinger_lband_indicator = bollinger_pband = bollinger_wband = lambda *a, **k: pd.Series(dtype=float)
# #     class AverageTrueRange: __init__(*args, **kwargs); average_true_range = lambda *a, **k: pd.Series(dtype=float)
# #     class MACD: __init__(*args, **kwargs); macd_diff = lambda *a, **k: pd.Series(dtype=float)
# #     class ADXIndicator: __init__(*args, **kwargs); adx = adx_pos = adx_neg = lambda *a, **k: pd.Series(dtype=float)
# #     class AroonIndicator: __init__(*args, **kwargs); aroon_up = aroon_down = aroon_indicator = lambda *a, **k: pd.Series(dtype=float)
# #     class RSIIndicator: __init__(*args, **kwargs); rsi = lambda *a, **k: pd.Series(dtype=float)
# #     class StochasticOscillator: __init__(*args, **kwargs); stoch = stoch_signal = lambda *a, **k: pd.Series(dtype=float)
# #     class ROCIndicator: __init__(*args, **kwargs); roc = lambda *a, **k: pd.Series(dtype=float)
# #     sma_indicator = lambda *a, **k: pd.Series(dtype=float)
# #
# #
# # # --- Конфигурация ---
# # MODEL_DIR = getattr(config, 'MODEL_DIR', 'models')
# # MIN_HISTORY_FOR_SIGNALS = getattr(config, 'MIN_HISTORY_FOR_SIGNALS', 21)
# # MIN_HISTORY_FOR_TA = 30 # Общий минимум для большинства индикаторов TA
# #
# # # Параметры из конфига для сигналов обмена/прибыли
# # EXCHANGE_PRICE = getattr(config, 'EXCHANGE_PRICE_THRESHOLD', 15_000_000)
# # COMMISSION_RATE = getattr(config, 'COMMISSION_RATE', 0.10)
# # BREAKEVEN_PRICE = getattr(config, 'BREAKEVEN_PRICE', EXCHANGE_PRICE / (1 - COMMISSION_RATE) if (1 - COMMISSION_RATE) != 0 else float('inf'))
# # OVR_THRESHOLD_FOR_EXCHANGE = getattr(config, 'OVR_THRESHOLD_FOR_EXCHANGE', 96)
# # EXCHANGE_RELEVANCE_UPPER_BOUND = getattr(config, 'EXCHANGE_RELEVANCE_UPPER_BOUND', EXCHANGE_PRICE * 1.8)
# #
# # # --- Вспомогательные функции ---
# #
# # def _check_consecutive_rises_hist(prices, i, threshold=2):
# #     count = 0
# #     if i < threshold or i >= len(prices): return False
# #     for j in range(i, i - threshold, -1):
# #         if j <= 0 or (j - 1) < 0: break
# #         price_curr = prices[j]; price_prev = prices[j-1]
# #         if price_curr is None or price_prev is None or \
# #            not isinstance(price_curr, (int, float)) or \
# #            not isinstance(price_prev, (int, float)) or \
# #            not np.isfinite(price_curr) or not np.isfinite(price_prev): break
# #         if price_curr > price_prev: count += 1
# #         else: break
# #     return count >= threshold
# #
# # def check_consecutive_rises(prices: list, threshold=2) -> bool:
# #     prices_clean = [p for p in prices if p is not None and isinstance(p, (int, float)) and np.isfinite(p)]
# #     if not prices_clean or len(prices_clean) < threshold + 1: return False
# #     return _check_consecutive_rises_hist(prices_clean, len(prices_clean) - 1, threshold)
# #
# # def _check_start_rise_after_drop_hist(prices, i):
# #     if i < 2 or i >= len(prices) or (i-1) < 0 or (i-2) < 0: return False
# #     p1, p2, p3 = prices[i-2], prices[i-1], prices[i];
# #     if p1 is None or p2 is None or p3 is None: return False
# #     if not (isinstance(p1, (int, float)) and isinstance(p2, (int, float)) and isinstance(p3, (int, float))): return False
# #     if not (np.isfinite(p1) and np.isfinite(p2) and np.isfinite(p3)): return False
# #     return p1 > p2 < p3
# #
# # def check_start_rise_after_drop(prices: list) -> bool:
# #     prices_clean = [p for p in prices if p is not None and isinstance(p, (int, float)) and np.isfinite(p)]
# #     if not prices_clean or len(prices_clean) < 3: return False
# #     return _check_start_rise_after_drop_hist(prices_clean, len(prices_clean) - 1)
# #
# # def check_historical_breakout(player_name, current_price, days=7, threshold_percent=0.0):
# #     if current_price is None: return None
# #     full_history = cycle_analysis.read_player_history(player_name)
# #     if not full_history: return None
# #     now_utc = datetime.now(timezone.utc)
# #     cutoff_utc = now_utc - timedelta(days=days)
# #     hist_prices = [
# #         r["price"] for r in full_history
# #         if r.get("price") is not None and np.isfinite(r["price"]) and
# #            r.get("date") and isinstance(r['date'], datetime) and
# #            r["date"].astimezone(timezone.utc) >= cutoff_utc and
# #            abs(r["price"] - current_price) > 1e-9
# #     ]
# #     if not hist_prices: return None
# #     h_min, h_max = min(hist_prices), max(hist_prices)
# #     min_thr = h_min * (1 - threshold_percent / 100.0) if threshold_percent else h_min
# #     max_thr = h_max * (1 + threshold_percent / 100.0) if threshold_percent else h_max
# #     min_s = f"{h_min:,.0f}".replace(",", "\u00A0")
# #     max_s = f"{h_max:,.0f}".replace(",", "\u00A0")
# #     if current_price < min_thr: return f"Пробой Min за {days}дн (был {min_s})"
# #     if current_price > max_thr: return f"Пробой Max за {days}дн (был {max_s})"
# #     return None
# #
# # def check_all_time_extreme(player_name, current_price):
# #     if current_price is None: return None
# #     full_history = cycle_analysis.read_player_history(player_name)
# #     if not full_history: return None
# #     prices = [r["price"] for r in full_history if r.get("price") is not None and np.isfinite(r.get("price"))]
# #     if not prices: return None
# #     comp = [p for p in prices if abs(p - current_price) > 1e-9]
# #     if not comp: return None
# #     h_min, h_max = min(comp), max(comp)
# #     min_s = f"{h_min:,.0f}".replace(",", "\u00A0"); max_s = f"{h_max:,.0f}".replace(",", "\u00A0")
# #     if current_price < h_min: return f"Исторический МИНИМУМ (пред. {min_s})"
# #     elif current_price > h_max: return f"Исторический МАКСИМУМ (пред. {max_s})"
# #     return None
# #
# # def check_volatility_spike(df: pd.DataFrame, days=3, spike_threshold=0.1):
# #     is_spike = False; txt = ""; vol = 0.0
# #     if df is None or df.empty: return (is_spike, txt, vol)
# #     now_utc = datetime.now(timezone.utc)
# #     cutoff_date = now_utc - timedelta(days=days)
# #     recent_df = df[df.index >= cutoff_date]
# #     prices_clean = recent_df['price'].dropna().tolist()
# #     if len(prices_clean) < 2: return (is_spike, txt, vol)
# #     mx, mn = max(prices_clean), min(prices_clean)
# #     last = prices_clean[-1] if prices_clean else None
# #     if last is None or not np.isfinite(last): return (is_spike, txt, vol)
# #     denom = last if abs(last) > 1e-9 else (np.mean(prices_clean) if abs(np.mean(prices_clean)) > 1e-9 else 0)
# #     if denom <= 1e-9:
# #         mn_s=f"{mn:,.0f}".replace(",","\u00A0"); mx_s=f"{mx:,.0f}".replace(",","\u00A0")
# #         txt = f"Разброс {days}д: {mn_s}-{mx_s}, отн. посл.: N/A (ZeroDenom)"
# #         return (is_spike, txt, vol)
# #     vol = (mx - mn) / denom
# #     is_spike = vol > spike_threshold
# #     mn_s=f"{mn:,.0f}".replace(",","\u00A0"); mx_s=f"{mx:,.0f}".replace(",","\u00A0")
# #     txt = f"Разброс {days}д: {mn_s}-{mx_s}, отн. посл.: {vol:.2f}"
# #     if is_spike: txt += " [СПАЙК!]"
# #     return (is_spike, txt, vol)
# #
# # def _calculate_sma_slope(series: pd.Series, window: int) -> float:
# #     if series is None or len(series) < window + 1: return 0.0
# #     sma = series.rolling(window=window, min_periods=window).mean().dropna()
# #     if len(sma) < 2: return 0.0
# #     y2, y1 = sma.iloc[-1], sma.iloc[-2]
# #     slope = y2 - y1
# #     return slope if pd.notna(slope) and np.isfinite(slope) else 0.0
# #
# # def _calculate_dow_metrics(history: list, current_date: datetime) -> tuple[float, float]:
# #     dow_deviation = 0.0; dow_range_pos = 0.5;
# #     if not history: return dow_deviation, dow_range_pos; current_dow = current_date.weekday(); current_price = history[-1].get('price') if history else None
# #     dow_stats = {dow: {"prices": [], "count": 0, "sum_price": 0.0, "min_price": float('inf'), "max_price": float('-inf')} for dow in range(7)}; all_prices = []; valid_records = 0
# #     for record in history:
# #         price = record.get('price'); date = record.get('date')
# #         if price is not None and date is not None and isinstance(date, datetime) and np.isfinite(price): st = dow_stats[date.weekday()]; st["prices"].append(price); st["count"] += 1; st["sum_price"] += price; st["min_price"] = min(st["min_price"], price); st["max_price"] = max(st["max_price"], price); all_prices.append(price); valid_records += 1
# #     if valid_records == 0: return dow_deviation, dow_range_pos
# #     global_avg_price = np.mean(all_prices) if all_prices else 0
# #     current_dow_data = dow_stats[current_dow]
# #     if current_dow_data["count"] > 0 and abs(global_avg_price) > 1e-9:
# #         current_dow_avg = current_dow_data["sum_price"] / current_dow_data["count"]
# #         if pd.notna(current_dow_avg) and np.isfinite(current_dow_avg): dow_deviation = (current_dow_avg - global_avg_price) / global_avg_price;
# #         if not np.isfinite(dow_deviation): dow_deviation = 0.0
# #     if current_dow_data["count"] >= 5:
# #         h_min = current_dow_data["min_price"]; h_max = current_dow_data["max_price"]
# #         if h_min != float('inf') and h_max != float('-inf'):
# #             d_range = h_max - h_min
# #             if d_range > 1e-9 and current_price is not None and pd.notna(current_price) and np.isfinite(current_price): pos = (current_price - h_min) / d_range; dow_range_pos = max(0.0, min(1.0, pos));
# #             if not np.isfinite(dow_range_pos): dow_range_pos = 0.5
# #             elif d_range <= 1e-9 : dow_range_pos = 0.5
# #     return dow_deviation, dow_range_pos
# #
# # def _calculate_dom_metrics(history: list, current_date: datetime) -> float:
# #     dom_deviation = 0.0;
# #     if not history: return dom_deviation; current_dom = current_date.day; dom_stats = {day: {"prices": []} for day in range(1, 32)}; all_prices = []
# #     for record in history:
# #         price = record.get('price'); date = record.get('date')
# #         if price is not None and date is not None and isinstance(date, datetime) and np.isfinite(price):
# #             day = date.day;
# #             if 1 <= day <= 31: dom_stats.setdefault(day, {"prices":[]})["prices"].append(price)
# #             all_prices.append(price)
# #     if not all_prices: return dom_deviation; global_avg_price = np.mean(all_prices) if all_prices else 0; current_dom_prices = dom_stats.get(current_dom, {}).get("prices", [])
# #     if current_dom_prices and abs(global_avg_price) > 1e-9:
# #         current_dom_avg = np.mean(current_dom_prices); dom_deviation = (current_dom_avg - global_avg_price) / global_avg_price
# #         if not np.isfinite(dom_deviation): dom_deviation = 0.0
# #     return dom_deviation
# #
# # def _calculate_trend_sko(history: list, current_date: datetime) -> float:
# #     trend_sko = 0.0
# #     if len(history) < 30: return trend_sko; t10 = current_date - timedelta(days=10); t20 = current_date - timedelta(days=20)
# #     history_before_now = [r for r in history if r.get('date') and isinstance(r['date'], datetime) and r['date'] < current_date and r.get('price') is not None and np.isfinite(r['price'])]
# #     recent_10d_prices = [r['price'] for r in history_before_now if t10 <= r['date']]
# #     base_10d_prices = [r['price'] for r in history_before_now if t20 <= r['date'] < t10]
# #     if len(recent_10d_prices) < 5 or len(base_10d_prices) < 10: return trend_sko
# #     try:
# #         avg10 = np.mean(recent_10d_prices); avg_base = np.mean(base_10d_prices); std_base = np.std(base_10d_prices)
# #         if std_base > 1e-9:
# #             trend_sko = (avg10 - avg_base) / std_base
# #             if not np.isfinite(trend_sko): trend_sko = 0.0
# #         else: trend_sko = 0.0
# #     except Exception as e:
# #         logging.warning(f"Ошибка расчета СКО тренда: {e}")
# #         trend_sko = 0.0
# #     return trend_sko
# #
# # # ИЗМЕНЕНО: Использует загруженную цену покупки
# # def _check_exchange_profit_signals(player_name:str, current_price: float, player_ovr: int, df_hist: pd.DataFrame, result: dict):
# #     """Рассчитывает сигналы обмена/прибыли, используя ЗАПИСАННУЮ цену покупки."""
# #     result['exchange_buy_opportunity'] = False
# #     result['profitable_sell_peak_risk'] = False
# #     result['profitable_hold_potential'] = False
# #     result['net_profit_on_market_sell'] = 0.0
# #
# #     # Проверяем df_hist на None перед использованием
# #     if df_hist is None or df_hist.empty:
# #         logging.debug(f"Пропуск сигналов обмена/прибыли для {player_name} - нет DataFrame.")
# #         return
# #
# #     if current_price is None or not np.isfinite(current_price):
# #         logging.debug(f"Пропуск сигналов обмена/прибыли для {player_name} - невалидная текущая цена.")
# #         return
# #
# #     # 1. Сигнал "Возможность покупки у порога"
# #     require_bottom_signals = getattr(config, 'REQUIRE_BOTTOM_SIGNALS_FOR_EXCHANGE_BUY', True) # Настройка
# #     is_at_or_below_exchange_price = (current_price <= EXCHANGE_PRICE)
# #     is_high_ovr = player_ovr >= OVR_THRESHOLD_FOR_EXCHANGE
# #     is_potential_bottom = result.get('is_rsi_oversold') or \
# #                           result.get('is_stoch_oversold') or \
# #                           result.get('is_start_rise_after_drop') or \
# #                           result.get('main_cycle_phase_raw') == "Дно/Разворот"
# #     buy_condition_met = is_at_or_below_exchange_price and is_high_ovr
# #     if require_bottom_signals:
# #         buy_condition_met = buy_condition_met and is_potential_bottom
# #     if buy_condition_met:
# #         result['exchange_buy_opportunity'] = True
# #         logging.debug(f"Сигнал: Возможность покупки у порога ({player_ovr} OVR, цена <= {EXCHANGE_PRICE})")
# #
# #     # 2. Сигналы "Прибыльная продажа" / "Удержание с профитом"
# #     # --- НОВОЕ: Загружаем последнюю записанную цену покупки ---
# #     potential_buy_price = storage.load_last_purchase_price(player_name)
# #     # ----------------------------------------------------------
# #
# #     if potential_buy_price is not None and np.isfinite(potential_buy_price):
# #         # Рассчитываем цену продажи с учетом комиссии рынка (10%)
# #         sell_price_net = current_price * (1 - COMMISSION_RATE)
# #         net_profit = sell_price_net - potential_buy_price
# #         result['net_profit_on_market_sell'] = net_profit
# #
# #         if net_profit > 0: # Если продажа в принципе прибыльна
# #             logging.debug(f"Потенциальная прибыль при продаже: {net_profit:,.0f} (основано на записанной покупке ~{potential_buy_price:,.0f})".replace(",", "\u00A0"))
# #             # Проверяем условия для продажи на пике
# #             is_potential_peak = result.get('is_rsi_overbought') or \
# #                                 result.get('is_stoch_overbought') or \
# #                                 result.get('main_cycle_phase_raw') == "Завершение/Пик" or \
# #                                 result.get('is_adx_trending_down') or \
# #                                 (result.get('all_time_extreme') is not None and "МАКСИМУМ" in result.get('all_time_extreme', ""))
# #
# #             if is_potential_peak and current_price > BREAKEVEN_PRICE * 1.05:
# #                 result['profitable_sell_peak_risk'] = True
# #                 logging.debug(f"Сигнал: Прибыльная продажа (риск пика, осн. на логе покупки)")
# #             else:
# #                 result['profitable_hold_potential'] = True
# #                 logging.debug(f"Сигнал: Удержание с профитом (осн. на логе покупки)")
# #     else:
# #         # Если цена покупки не найдена в логе, не генерируем сигналы прибыли
# #         logging.debug(f"Нет записанной цены покупки для {player_name}. Сигналы прибыли не рассчитываются.")
# #
# #
# # # --- Предсказание Модели ---
# # def get_model_prediction(player_name, current_features):
# #     safe_name = "".join(c if c.isalnum() else "_" for c in player_name); model_path = os.path.join(MODEL_DIR, f"{safe_name}_lgbm_model_3class.joblib")
# #     if not os.path.isfile(model_path): logging.info(f"[Pred] Модель не найдена для {player_name}: {model_path}"); return "N/A (нет модели)"
# #     try: model_mtime = os.path.getmtime(model_path); model_dt = datetime.fromtimestamp(model_mtime, tz=timezone.utc); logging.info(f"[Pred] Загрузка модели {player_name} из {model_path} (Дата: {model_dt.strftime('%Y-%m-%d %H:%M')})")
# #     except Exception as e_stat: logging.warning(f"[Pred] Не получить время файла {model_path}: {e_stat}")
# #     try:
# #         model = joblib.load(model_path); logging.info(f"[Pred] Модель для {player_name} успешно загружена.")
# #         try: model_features = model.booster_.feature_name()
# #         except AttributeError:
# #             try: import model_trainer; model_features = model_trainer.DEFAULT_FEATURES; logging.warning(f"[Pred] Исп. DEFAULT_FEATURES для {player_name}.")
# #             except (ImportError, AttributeError): model_features = list(current_features.keys()); logging.error(f"[Pred] Не получить фичи, исп. текущие для {player_name}.")
# #         features_for_pred = {}; missing_in_current = []
# #         for f_name in model_features:
# #             if f_name in current_features:
# #                 feat_val = current_features[f_name]
# #                 if isinstance(feat_val, (int, float)) and not np.isfinite(feat_val): logging.warning(f"[Pred] Фича '{f_name}'={feat_val} NaN/inf для {player_name}. Замена 0."); features_for_pred[f_name] = 0.0
# #                 else: features_for_pred[f_name] = feat_val
# #             else: features_for_pred[f_name] = 0.0; missing_in_current.append(f_name)
# #         if missing_in_current: logging.warning(f"[Pred] Отсутств. фичи {missing_in_current} для {player_name}. Заполнены 0.")
# #         # --- Гарантируем правильный порядок и наличие колонок ---
# #         features_df = pd.DataFrame([features_for_pred])
# #         for col in model_features:
# #             if col not in features_df.columns:
# #                 features_df[col] = 0.0
# #         features_df = features_df[model_features]
# #         # -----------------------------------------------------
# #         numeric_cols_pred = features_df.select_dtypes(include=np.number).columns
# #         if features_df[numeric_cols_pred].isnull().values.any() or not np.all(np.isfinite(features_df[numeric_cols_pred].values)):
# #             logging.warning(f"[Pred] NaN/inf в фичах перед предск. {player_name}. Замена 0.");
# #             for col in numeric_cols_pred: features_df[col] = features_df[col].fillna(0).replace([np.inf, -np.inf], 0)
# #         if features_df[numeric_cols_pred].isnull().values.any() or not np.all(np.isfinite(features_df[numeric_cols_pred].values)): logging.error(f"[Pred] Очистка NaN/inf не удалась {player_name}.")
# #         pred_class = model.predict(features_df)[0]
# #         if pred_class == 0: result_str = "Модель: Падение"
# #         elif pred_class == 1: result_str = "Модель: Без изм."
# #         elif pred_class == 2: result_str = "Модель: Рост"
# #         else: logging.error(f"[Pred] Неожиданный класс {pred_class} для {player_name}"); result_str = "Ошибка предск. (класс?)"
# #         logging.info(f"[Pred] Предсказание для {player_name}: class={pred_class}, str='{result_str}'")
# #         return result_str
# #     except FileNotFoundError: logging.error(f"[Pred] FNF при загрузке модели {player_name} из {model_path}"); return "Ошибка предск. (FNF)"
# #     except Exception as e: logging.error(f"[Pred] Ошибка при загрузке/исп. модели {player_name}: {e}", exc_info=True); return "Ошибка предск."
# #
# # # --- НОВАЯ Агрегация Сигналов (v2) ---
# #
# # def check_aggregated_signal_v2(signals_data: dict) -> tuple[float, str, str]:
# #     """Агрегирует сигналы с индивидуальными весами из config v8.x."""
# #     score = 0.0
# #     drivers = [] # Список для описания сигналов, повлиявших на счет
# #
# #     # --- Получение весов из конфига ---
# #     weights = {
# #         # ML Model
# #         "WEIGHT_MODEL_FALL": getattr(config, 'WEIGHT_MODEL_FALL', 0.0),
# #         "WEIGHT_MODEL_HOLD": getattr(config, 'WEIGHT_MODEL_HOLD', 0.0),
# #         "WEIGHT_MODEL_RISE": getattr(config, 'WEIGHT_MODEL_RISE', 0.0),
# #         # Cycle
# #         "WEIGHT_CYCLE_FALL": getattr(config, 'WEIGHT_CYCLE_FALL', 0.0),
# #         "WEIGHT_CYCLE_BOTTOM": getattr(config, 'WEIGHT_CYCLE_BOTTOM', 0.0),
# #         "WEIGHT_CYCLE_RISE": getattr(config, 'WEIGHT_CYCLE_RISE', 0.0),
# #         "WEIGHT_CYCLE_PEAK": getattr(config, 'WEIGHT_CYCLE_PEAK', 0.0),
# #         # Event/Source
# #         "WEIGHT_EVENT_ACTIVE": getattr(config, 'WEIGHT_EVENT_ACTIVE', 0.0),
# #         "WEIGHT_SOURCE_CURRENT": getattr(config, 'WEIGHT_SOURCE_CURRENT', 0.0),
# #         "WEIGHT_SOURCE_PAST": getattr(config, 'WEIGHT_SOURCE_PAST', 0.0),
# #         # Technicals / Patterns / Seasonality
# #         "WEIGHT_RSI_OVERSOLD": getattr(config, 'WEIGHT_RSI_OVERSOLD', 0.0),
# #         "WEIGHT_RSI_OVERBOUGHT": getattr(config, 'WEIGHT_RSI_OVERBOUGHT', 0.0),
# #         "WEIGHT_STOCH_OVERSOLD": getattr(config, 'WEIGHT_STOCH_OVERSOLD', 0.0),
# #         "WEIGHT_STOCH_OVERBOUGHT": getattr(config, 'WEIGHT_STOCH_OVERBOUGHT', 0.0),
# #         "WEIGHT_ADX_TRENDING_UP": getattr(config, 'WEIGHT_ADX_TRENDING_UP', 0.0),
# #         "WEIGHT_ADX_TRENDING_DOWN": getattr(config, 'WEIGHT_ADX_TRENDING_DOWN', 0.0),
# #         "WEIGHT_ADX_NO_TREND": getattr(config, 'WEIGHT_ADX_NO_TREND', 0.0),
# #         "WEIGHT_ROC_POSITIVE": getattr(config, 'WEIGHT_ROC_POSITIVE', 0.0),
# #         "WEIGHT_ROC_NEGATIVE": getattr(config, 'WEIGHT_ROC_NEGATIVE', 0.0),
# #         "WEIGHT_BREAKOUT_UP": getattr(config, 'WEIGHT_BREAKOUT_UP', 0.0),
# #         "WEIGHT_BREAKOUT_DOWN": getattr(config, 'WEIGHT_BREAKOUT_DOWN', 0.0),
# #         "WEIGHT_RISE_AFTER_DROP": getattr(config, 'WEIGHT_RISE_AFTER_DROP', 0.0),
# #         "WEIGHT_TWO_RISES": getattr(config, 'WEIGHT_TWO_RISES', 0.0),
# #         "WEIGHT_TREND10D_BUY": getattr(config, 'WEIGHT_TREND10D_BUY', 0.0),
# #         "WEIGHT_TREND10D_SELL": getattr(config, 'WEIGHT_TREND10D_SELL', 0.0),
# #         "WEIGHT_DOW_AVG_BUY": getattr(config, 'WEIGHT_DOW_AVG_BUY', 0.0),
# #         "WEIGHT_DOW_AVG_SELL": getattr(config, 'WEIGHT_DOW_AVG_SELL', 0.0),
# #         "WEIGHT_DOW_RANGE_BUY": getattr(config, 'WEIGHT_DOW_RANGE_BUY', 0.0),
# #         "WEIGHT_DOW_RANGE_SELL": getattr(config, 'WEIGHT_DOW_RANGE_SELL', 0.0),
# #         "WEIGHT_DOM_AVG_BUY": getattr(config, 'WEIGHT_DOM_AVG_BUY', 0.0),
# #         "WEIGHT_DOM_AVG_SELL": getattr(config, 'WEIGHT_DOM_AVG_SELL', 0.0),
# #         "WEIGHT_ABOVE_SMA20": getattr(config, 'WEIGHT_ABOVE_SMA20', 0.0),
# #         "WEIGHT_BELOW_SMA20": getattr(config, 'WEIGHT_BELOW_SMA20', 0.0),
# #         "WEIGHT_ABOVE_SMA28": getattr(config, 'WEIGHT_ABOVE_SMA28', 0.0),
# #         "WEIGHT_BELOW_SMA28": getattr(config, 'WEIGHT_BELOW_SMA28', 0.0),
# #         "WEIGHT_VOLATILITY_SPIKE": getattr(config, 'WEIGHT_VOLATILITY_SPIKE', 0.0),
# #         # Contextual
# #         "WEIGHT_EXCHANGE_BUY_OPP": getattr(config, 'WEIGHT_EXCHANGE_BUY_OPP', 0.0),
# #         "WEIGHT_PROFITABLE_SELL_RISK": getattr(config, 'WEIGHT_PROFITABLE_SELL_RISK', 0.0),
# #         "WEIGHT_PROFITABLE_HOLD": getattr(config, 'WEIGHT_PROFITABLE_HOLD', 0.0),
# #     }
# #
# #     # --- Применение весов ---
# #
# #     # ML Модель
# #     model_pred_str = signals_data.get("model_prediction", "")
# #     model_w = 0.0; model_tag = "N/A"
# #     if "Падение" in model_pred_str: model_w = weights["WEIGHT_MODEL_FALL"]; model_tag = f"Пад{model_w:+g}"
# #     elif "Без изм." in model_pred_str: model_w = weights["WEIGHT_MODEL_HOLD"]; model_tag = f"БезИзм{model_w:+g}"
# #     elif "Рост" in model_pred_str: model_w = weights["WEIGHT_MODEL_RISE"]; model_tag = f"Рост{model_w:+g}"
# #     elif "Ошибка" in model_pred_str: model_tag="Err"
# #     if model_w != 0 or ("Модель" in model_pred_str and model_tag != "N/A"): # Учитываем даже если вес 0, но предсказание есть
# #         score += model_w; drivers.append(f"Модель({model_tag})")
# #
# #     # Цикл
# #     main_cycle = signals_data.get("main_cycle_phase_raw", "N/A")
# #     cycle_w = 0; cycle_tag = "N/A"
# #     if main_cycle == "Падение": cycle_w = weights["WEIGHT_CYCLE_FALL"]; cycle_tag = "Пад"
# #     elif main_cycle == "Дно/Разворот": cycle_w = weights["WEIGHT_CYCLE_BOTTOM"]; cycle_tag = "Дно"
# #     elif main_cycle == "Рост": cycle_w = weights["WEIGHT_CYCLE_RISE"]; cycle_tag = "Рост"
# #     elif main_cycle == "Завершение/Пик": cycle_w = weights["WEIGHT_CYCLE_PEAK"]; cycle_tag = "Пик"
# #     if cycle_w != 0:
# #         score += cycle_w; drivers.append(f"Цикл({cycle_tag}{cycle_w:+g})")
# #
# #     # Событие и Источник
# #     if signals_data.get("is_other_event_active"):
# #         w = weights["WEIGHT_EVENT_ACTIVE"]; score += w; drivers.append(f"Событие({w:+g})")
# #     is_current_src = signals_data.get("is_from_current_event", 0)
# #     source_w = weights["WEIGHT_SOURCE_CURRENT"] if is_current_src else weights["WEIGHT_SOURCE_PAST"]
# #     if source_w != 0:
# #         score += source_w; drivers.append(f"Источник({'Тек' if is_current_src else 'Прш'}{source_w:+g})")
# #
# #     # --- Индикаторы и Паттерны ---
# #     if signals_data.get("is_rsi_oversold"): w = weights["WEIGHT_RSI_OVERSOLD"]; score += w; drivers.append(f"RSI<30({w:+g})")
# #     if signals_data.get("is_rsi_overbought"): w = weights["WEIGHT_RSI_OVERBOUGHT"]; score += w; drivers.append(f"RSI>70({w:+g})")
# #
# #     if signals_data.get("is_stoch_oversold"): w = weights["WEIGHT_STOCH_OVERSOLD"]; score += w; drivers.append(f"Stoch<20({w:+g})")
# #     if signals_data.get("is_stoch_overbought"): w = weights["WEIGHT_STOCH_OVERBOUGHT"]; score += w; drivers.append(f"Stoch>80({w:+g})")
# #
# #     if signals_data.get("is_adx_trending_up"): w = weights["WEIGHT_ADX_TRENDING_UP"]; score += w; drivers.append(f"ADX Рост({w:+g})")
# #     if signals_data.get("is_adx_trending_down"): w = weights["WEIGHT_ADX_TRENDING_DOWN"]; score += w; drivers.append(f"ADX Пад({w:+g})")
# #     if signals_data.get("is_adx_no_trend"): w = weights["WEIGHT_ADX_NO_TREND"]; score += w; drivers.append(f"ADX Флэт({w:+g})")
# #
# #     if signals_data.get("is_roc_positive"): w = weights["WEIGHT_ROC_POSITIVE"]; score += w; drivers.append(f"ROC>0({w:+g})")
# #     if signals_data.get("is_roc_negative"): w = weights["WEIGHT_ROC_NEGATIVE"]; score += w; drivers.append(f"ROC<0({w:+g})")
# #
# #     # Учитываем каждый пробой индивидуально с его весом
# #     breakout_up_count = signals_data.get("breakout_7d_up", 0) + signals_data.get("breakout_14d_up", 0)
# #     if breakout_up_count > 0: w_break = weights["WEIGHT_BREAKOUT_UP"] * breakout_up_count; score += w_break; drivers.append(f"Пробой В({breakout_up_count}x)({w_break:+g})")
# #     breakout_down_count = signals_data.get("breakout_7d_down", 0) + signals_data.get("breakout_14d_down", 0)
# #     if breakout_down_count > 0: w_break = weights["WEIGHT_BREAKOUT_DOWN"] * breakout_down_count; score += w_break; drivers.append(f"Пробой Н({breakout_down_count}x)({w_break:+g})")
# #
# #     if signals_data.get("is_start_rise_after_drop"): w = weights["WEIGHT_RISE_AFTER_DROP"]; score += w; drivers.append(f"Разворот({w:+g})")
# #     if signals_data.get("is_two_rises_anytime"): w = weights["WEIGHT_TWO_RISES"]; score += w; drivers.append(f"Рост>2({w:+g})")
# #
# #     if "BUY" in signals_data.get("trend_10d_signal", ""): w = weights["WEIGHT_TREND10D_BUY"]; score += w; drivers.append(f"Тренд10д->П({w:+g})")
# #     if "SELL" in signals_data.get("trend_10d_signal", ""): w = weights["WEIGHT_TREND10D_SELL"]; score += w; drivers.append(f"Тренд10д->Пр({w:+g})")
# #
# #     if "BUY" in signals_data.get("seasonal_signal", ""): w = weights["WEIGHT_DOW_AVG_BUY"]; score += w; drivers.append(f"DOW Avg->П({w:+g})")
# #     if "SELL" in signals_data.get("seasonal_signal", ""): w = weights["WEIGHT_DOW_AVG_SELL"]; score += w; drivers.append(f"DOW Avg->Пр({w:+g})")
# #
# #     if "BUY" in signals_data.get("dow_range_signal", ""): w = weights["WEIGHT_DOW_RANGE_BUY"]; score += w; drivers.append(f"DOW Range->П({w:+g})")
# #     if "SELL" in signals_data.get("dow_range_signal", ""): w = weights["WEIGHT_DOW_RANGE_SELL"]; score += w; drivers.append(f"DOW Range->Пр({w:+g})")
# #
# #     if "BUY" in signals_data.get("day_of_month_signal", ""): w = weights["WEIGHT_DOM_AVG_BUY"]; score += w; drivers.append(f"DOM Avg->П({w:+g})")
# #     if "SELL" in signals_data.get("day_of_month_signal", ""): w = weights["WEIGHT_DOM_AVG_SELL"]; score += w; drivers.append(f"DOM Avg->Пр({w:+g})")
# #
# #     if signals_data.get("is_above_sma20") == 1: w = weights["WEIGHT_ABOVE_SMA20"]; score += w; drivers.append(f">SMA20({w:+g})")
# #     if signals_data.get("is_above_sma20") == 0: w = weights["WEIGHT_BELOW_SMA20"]; score += w; drivers.append(f"<SMA20({w:+g})")
# #
# #     if signals_data.get("is_above_sma28") == 1: w = weights["WEIGHT_ABOVE_SMA28"]; score += w; drivers.append(f">SMA28({w:+g})")
# #     if signals_data.get("is_above_sma28") == 0: w = weights["WEIGHT_BELOW_SMA28"]; score += w; drivers.append(f"<SMA28({w:+g})")
# #
# #     if signals_data.get("volatility_spike"): w = weights["WEIGHT_VOLATILITY_SPIKE"]; score += w; drivers.append(f"Волат.Спайк({w:+g})")
# #
# #     # Контекстные сигналы
# #     if signals_data.get("exchange_buy_opportunity"): w = weights["WEIGHT_EXCHANGE_BUY_OPP"]; score += w; drivers.append(f"Обмен.Покупка?({w:+g})")
# #     if signals_data.get("profitable_sell_peak_risk"): w = weights["WEIGHT_PROFITABLE_SELL_RISK"]; score += w; drivers.append(f"Профит.Продажа?({w:+g})")
# #     if signals_data.get("profitable_hold_potential"): w = weights["WEIGHT_PROFITABLE_HOLD"]; score += w; drivers.append(f"Профит.Держать?({w:+g})")
# #
# #     # --- Определение рекомендации ---
# #     rec = "HOLD / Neutral" # Default
# #     if score >= config.AGG_SCORE_STRONG_BUY: rec = "Strong BUY"
# #     elif score >= config.AGG_SCORE_BUY: rec = "BUY"
# #     elif score >= config.AGG_SCORE_WEAK_BUY: rec = "Weak BUY / HOLD"
# #     elif score <= config.AGG_SCORE_STRONG_SELL: rec = "Strong SELL"
# #     elif score <= config.AGG_SCORE_SELL: rec = "SELL"
# #     elif score <= config.AGG_SCORE_WEAK_SELL: rec = "Weak SELL / HOLD"
# #
# #     # --- Формирование резюме ---
# #     summary = ""
# #     strong_abs_threshold = max(abs(config.AGG_SCORE_STRONG_BUY), abs(config.AGG_SCORE_STRONG_SELL))
# #     buy_abs_threshold = max(abs(config.AGG_SCORE_BUY), abs(config.AGG_SCORE_SELL))
# #     weak_abs_threshold = max(abs(config.AGG_SCORE_WEAK_BUY), abs(config.AGG_SCORE_WEAK_SELL))
# #
# #     if abs(score) >= strong_abs_threshold: summary = f"Сильный сигнал к {'покупке' if score > 0 else 'продаже'}."
# #     elif abs(score) >= buy_abs_threshold: summary = f"Умеренный сигнал к {'покупке' if score > 0 else 'продаже'}."
# #     elif abs(score) >= weak_abs_threshold: summary = f"Слабый сигнал к {'покупке' if score > 0 else 'продаже'} / удержанию."
# #     else: summary = "Нейтральная ситуация / противоречивые сигналы."
# #
# #     # Добавляем основные драйверы к резюме
# #     if drivers:
# #         # Сортируем драйверы по абсолютному значению веса (примерно)
# #         def get_weight_from_driver(d):
# #             try: return abs(float(d[d.rfind('(')+1:d.rfind(')')]))
# #             except: return 0
# #         sorted_drivers = sorted(drivers, key=get_weight_from_driver, reverse=True)
# #         summary += f" Ключевые факторы: {', '.join(sorted_drivers[:3])}." # Показываем до 3 самых весомых
# #     if not summary.endswith(".") and summary: summary += "."
# #
# #     return score, rec, summary
# #
# #
# # # --- Основная функция проверки сигналов (v22.8) ---
# #
# # def check_signals(player_name, recent_prices):
# #     """Вычисляет ВСЕ фичи (старые + новые), получает предсказание модели и агрегирует сигналы по НОВОЙ СХЕМЕ v2."""
# #     start_time = time.time()
# #     result = {
# #         # Старые Сигналы/Фичи (для обратной совместимости и ML)
# #         "seasonal_signal": "N/A", "dow_range_signal": "N/A", "day_of_month_signal": "N/A", "trend_10d_signal": "N/A",
# #         "main_cycle_phase": "N/A", "main_cycle_phase_raw": "Нет цикла", "other_events": [], "model_prediction": "N/A",
# #         "aggregated_score": 0.0, "aggregated_text": "HOLD / Neutral", "hist_breakouts": [], "hist_breakout_count": 0,
# #         "volatility_text": "", "volatility_spike": False, "all_time_extreme": None, "final_summary_text": "",
# #         "is_rsi_overbought": False, "is_rsi_oversold": False, "seasonal_dow_avg_signal_buy": 0,
# #         "seasonal_dow_avg_signal_sell": 0, "dom_avg_signal_buy": 0, "dom_avg_signal_sell": 0, "days_in_cycle": 0,
# #         "is_cycle_phase_fall": 0, "is_cycle_phase_bottom": 0, "is_cycle_phase_rise": 0, "is_cycle_phase_peak": 0,
# #         "is_other_event_active": False, "is_from_current_event": 0, "dow_sin": 0.0, "dow_cos": 0.0, "cycle_day_sin": 0.0,
# #         "cycle_day_cos": 0.0, "price_lag_1": 0.0, "rsi_lag_1": 50.0, "price_div_sma20": 1.0, "is_above_sma20": None,
# #         "ovr_category": 0, "is_position_CB": 0,"is_position_LB": 0,"is_position_CM": 0,"is_position_RB": 0,"is_position_LM": 0,
# #         "is_position_RW": 0,"is_position_ST": 0,"is_position_GK": 0,"is_dow_0": 0,"is_dow_1": 0,"is_dow_2": 0,"is_dow_3": 0,
# #         "is_dow_4": 0,"is_dow_5": 0,"is_dow_6": 0, "volatility": 0.0, "sma20": 0.0,
# #         "macd_diff": 0.0, "bollinger_hband_indicator": 0.0, "bollinger_lband_indicator": 0.0, "bollinger_pband": 0.5, "bollinger_wband": 0.0,
# #         "trend_10d_deviation_sko": 0.0, "dow_deviation_from_avg": 0.0, "dow_range_position": 0.5, "dom_deviation_from_avg": 0.0, "rsi_value": 50.0,
# #         "is_two_rises_anytime": False, "is_start_rise_after_drop": False, "breakout_7d_up": 0, "breakout_7d_down": 0, "breakout_14d_up": 0, "breakout_14d_down": 0,
# #         "is_all_time_high": False, "is_all_time_low": False,
# #         # Новые Сигналы/Фичи
# #         "stoch_k": 50.0, "stoch_d": 50.0, "is_stoch_oversold": False, "is_stoch_overbought": False,
# #         "adx": 0.0, "di_pos": 0.0, "di_neg": 0.0, "is_adx_trending": False, "is_adx_trending_up": False, "is_adx_trending_down": False, "is_adx_no_trend": True,
# #         "roc_14": 0.0, "is_roc_positive": False, "is_roc_negative": False,
# #         "atr_14": 0.0, "atr_14_norm": 0.0,
# #         "sma28": 0.0, "price_div_sma28": 1.0, "is_above_sma28": None, "sma28_slope": 0.0,
# #         # Контекстные сигналы обмена/прибыли
# #         "exchange_buy_opportunity": False,
# #         "profitable_sell_peak_risk": False,
# #         "profitable_hold_potential": False,
# #         "net_profit_on_market_sell": 0.0,
# #     }
# #     CURRENT_DEFAULT_FEATURES = [] # Фичи для модели
# #     try: import model_trainer; CURRENT_DEFAULT_FEATURES = model_trainer.DEFAULT_FEATURES
# #     except (ImportError, AttributeError): logging.debug("Не удалось импортировать DEFAULT_FEATURES.")
# #     # Инициализируем нулями все ожидаемые фичи
# #     for feat in CURRENT_DEFAULT_FEATURES: result.setdefault(feat, 0.0)
# #
# #     logging.info(f"--- Начало обработки сигналов для {player_name} ---")
# #
# #     # --- Базовые проверки ---
# #     if len(recent_prices) < MIN_HISTORY_FOR_SIGNALS:
# #         logging.warning(f"Мало цен ({len(recent_prices)}<{MIN_HISTORY_FOR_SIGNALS}) для {player_name}.")
# #         current_price = recent_prices[-1] if recent_prices else None
# #         if current_price is not None and np.isfinite(current_price):
# #             result["all_time_extreme"] = check_all_time_extreme(player_name, current_price)
# #         result["final_summary_text"] = "Недостаточно данных."; sc, txt, summ = check_aggregated_signal_v2(result); result.update({"aggregated_score": sc, "aggregated_text": txt, "final_summary_text": summ}); return result
# #
# #     current_price = recent_prices[-1]
# #     if current_price is None or not np.isfinite(current_price):
# #         logging.warning(f"Невалидная последняя цена ({current_price}) для {player_name}.")
# #         result["final_summary_text"] = "Ошибка тек. цены."; sc, txt, summ = check_aggregated_signal_v2(result); result.update({"aggregated_score": sc, "aggregated_text": txt, "final_summary_text": summ}); return result
# #
# #     # Определяем valid_prices (список последних цен) для простых проверок
# #     valid_prices = [p for p in recent_prices if p is not None and isinstance(p, (int, float)) and np.isfinite(p)]
# #     if not valid_prices:
# #         logging.error(f"Нет валидных цен в recent_prices для {player_name} после проверки."); result["final_summary_text"] = "Ошибка recent_prices."; sc, txt, summ = check_aggregated_signal_v2(result); result.update({"aggregated_score": sc, "aggregated_text": txt, "final_summary_text": summ }); return result
# #
# #     # --- Загрузка и подготовка данных DataFrame ---
# #     df_hist = None
# #     logging.debug(f"Чтение полной истории для DataFrame {player_name}..."); start_hist_load = time.time()
# #     full_history = cycle_analysis.read_player_history(player_name)
# #     hist_load_time = time.time() - start_hist_load; logging.debug(f"История для DataFrame {player_name} загружена за {hist_load_time:.2f} сек.")
# #
# #     if full_history and len(full_history) >= MIN_HISTORY_FOR_TA:
# #         try:
# #             data_for_df = []
# #             for i, record in enumerate(full_history):
# #                  price = record.get('price')
# #                  date = record.get('date')
# #                  if price is not None and np.isfinite(price) and isinstance(date, datetime):
# #                       # Используем только price для Close, High, Low
# #                       data_for_df.append({'date': date, 'high': price, 'low': price, 'price': price})
# #
# #             if len(data_for_df) >= MIN_HISTORY_FOR_TA:
# #                 df_hist = pd.DataFrame(data_for_df).set_index('date').sort_index()
# #                 df_hist = df_hist[~df_hist.index.duplicated(keep='last')]
# #                 df_hist.dropna(inplace=True)
# #                 if df_hist.empty or len(df_hist) < MIN_HISTORY_FOR_TA:
# #                     logging.warning(f"DataFrame пуст или слишком мал (<{MIN_HISTORY_FOR_TA}) после обработки для {player_name}.")
# #                     df_hist = None
# #                 else:
# #                     logging.debug(f"DataFrame для TA готов ({len(df_hist)} строк) для {player_name}.")
# #             else:
# #                  logging.warning(f"Недостаточно ({len(data_for_df)}) валидных записей для создания DataFrame TA {player_name}.")
# #         except Exception as e_df:
# #             logging.error(f"Ошибка создания DataFrame для {player_name}: {e_df}", exc_info=True)
# #             df_hist = None
# #     else:
# #         logging.warning(f"Недостаточно истории ({len(full_history) if full_history else 0} < {MIN_HISTORY_FOR_TA}) для расчетов TA {player_name}.")
# #
# #     # --- Расчет фичей ---
# #     logging.debug(f"Расчет фичей для {player_name} (v22.8)..."); start_feat_calc = time.time()
# #     now_dt_utc = datetime.now(timezone.utc) # Определяем здесь один раз
# #
# #     # Вызываем функции с valid_prices (списком)
# #     result["is_two_rises_anytime"] = check_consecutive_rises(valid_prices)
# #     result["is_start_rise_after_drop"] = check_start_rise_after_drop(valid_prices)
# #
# #     # Расчеты на основе DataFrame (df_hist)
# #     if df_hist is not None and TA_AVAILABLE:
# #         close = df_hist['price']
# #         high = df_hist['high']
# #         low = df_hist['low']
# #
# #         try: # RSI
# #             rsi_indicator = RSIIndicator(close=close, window=14, fillna=True)
# #             rsi_series = rsi_indicator.rsi()
# #             last_rsi = rsi_series.iloc[-1] if not rsi_series.dropna().empty else 50.0
# #             result["rsi_value"] = last_rsi if pd.notna(last_rsi) and np.isfinite(last_rsi) else 50.0
# #             result["is_rsi_overbought"] = bool(result["rsi_value"] > 70)
# #             result["is_rsi_oversold"] = bool(result["rsi_value"] < 30)
# #             result["rsi_lag_1"] = rsi_series.iloc[-2] if len(rsi_series) >= 2 and pd.notna(rsi_series.iloc[-2]) else 50.0
# #         except Exception as e: logging.warning(f"Ошибка RSI {player_name}: {e}")
# #
# #         try: # MACD
# #             macd_indicator = MACD(close=close, fillna=True)
# #             macd_diff_series = macd_indicator.macd_diff()
# #             last_macd_diff = macd_diff_series.iloc[-1] if not macd_diff_series.dropna().empty else 0.0
# #             result["macd_diff"] = last_macd_diff if pd.notna(last_macd_diff) and np.isfinite(last_macd_diff) else 0.0
# #         except Exception as e: logging.warning(f"Ошибка MACD {player_name}: {e}")
# #
# #         try: # Bollinger Bands
# #             bb_indicator = BollingerBands(close=close, window=20, window_dev=2, fillna=True)
# #             hband_ind = bb_indicator.bollinger_hband_indicator(); result["bollinger_hband_indicator"] = hband_ind.iloc[-1] if not hband_ind.dropna().empty else 0.0
# #             lband_ind = bb_indicator.bollinger_lband_indicator(); result["bollinger_lband_indicator"] = lband_ind.iloc[-1] if not lband_ind.dropna().empty else 0.0
# #             pband = bb_indicator.bollinger_pband(); result["bollinger_pband"] = pband.iloc[-1] if not pband.dropna().empty else 0.5
# #             wband = bb_indicator.bollinger_wband(); result["bollinger_wband"] = wband.iloc[-1] if not wband.dropna().empty else 0.0
# #         except Exception as e: logging.warning(f"Ошибка Bollinger Bands {player_name}: {e}")
# #
# #         try: # Stochastic
# #             stoch_indicator = StochasticOscillator(high=high, low=low, close=close, window=14, smooth_window=3, fillna=True)
# #             stoch_k_series = stoch_indicator.stoch()
# #             stoch_d_series = stoch_indicator.stoch_signal()
# #             last_k = stoch_k_series.iloc[-1] if not stoch_k_series.dropna().empty else 50.0
# #             last_d = stoch_d_series.iloc[-1] if not stoch_d_series.dropna().empty else 50.0
# #             result["stoch_k"] = last_k if pd.notna(last_k) and np.isfinite(last_k) else 50.0
# #             result["stoch_d"] = last_d if pd.notna(last_d) and np.isfinite(last_d) else 50.0
# #             result["is_stoch_oversold"] = bool(result["stoch_k"] < 20)
# #             result["is_stoch_overbought"] = bool(result["stoch_k"] > 80)
# #         except Exception as e: logging.warning(f"Ошибка Stochastic {player_name}: {e}")
# #
# #         try: # ADX
# #             adx_indicator = ADXIndicator(high=high, low=low, close=close, window=14, fillna=True)
# #             adx_series = adx_indicator.adx()
# #             di_pos_series = adx_indicator.adx_pos()
# #             di_neg_series = adx_indicator.adx_neg()
# #             last_adx = adx_series.iloc[-1] if not adx_series.dropna().empty else 0.0
# #             last_di_pos = di_pos_series.iloc[-1] if not di_pos_series.dropna().empty else 0.0
# #             last_di_neg = di_neg_series.iloc[-1] if not di_neg_series.dropna().empty else 0.0
# #             result["adx"] = last_adx if pd.notna(last_adx) and np.isfinite(last_adx) else 0.0
# #             result["di_pos"] = last_di_pos if pd.notna(last_di_pos) and np.isfinite(last_di_pos) else 0.0
# #             result["di_neg"] = last_di_neg if pd.notna(last_di_neg) and np.isfinite(last_di_neg) else 0.0
# #             adx_threshold = 25 # Порог силы тренда
# #             result["is_adx_trending"] = bool(result["adx"] > adx_threshold)
# #             result["is_adx_trending_up"] = bool(result["is_adx_trending"] and result["di_pos"] > result["di_neg"])
# #             result["is_adx_trending_down"] = bool(result["is_adx_trending"] and result["di_neg"] > result["di_pos"])
# #             result["is_adx_no_trend"] = not result["is_adx_trending"]
# #         except Exception as e: logging.warning(f"Ошибка ADX {player_name}: {e}")
# #
# #         try: # ROC (14 periods)
# #             roc_indicator = ROCIndicator(close=close, window=14, fillna=True)
# #             roc_series = roc_indicator.roc()
# #             last_roc = roc_series.iloc[-1] if not roc_series.dropna().empty else 0.0
# #             result["roc_14"] = last_roc if pd.notna(last_roc) and np.isfinite(last_roc) else 0.0
# #             result["is_roc_positive"] = bool(result["roc_14"] > 0)
# #             result["is_roc_negative"] = bool(result["roc_14"] < 0)
# #         except Exception as e: logging.warning(f"Ошибка ROC {player_name}: {e}")
# #
# #         try: # ATR (14 periods)
# #             atr_indicator = AverageTrueRange(high=high, low=low, close=close, window=14, fillna=True)
# #             atr_series = atr_indicator.average_true_range()
# #             last_atr = atr_series.iloc[-1] if not atr_series.dropna().empty else 0.0
# #             result["atr_14"] = last_atr if pd.notna(last_atr) and np.isfinite(last_atr) else 0.0
# #             # Нормализованный ATR
# #             if current_price > 1e-9: result["atr_14_norm"] = (result["atr_14"] / current_price) * 100
# #             else: result["atr_14_norm"] = 0.0
# #         except Exception as e: logging.warning(f"Ошибка ATR {player_name}: {e}")
# #
# #         try: # SMA20
# #             sma20_series = sma_indicator(close=close, window=20, fillna=True)
# #             last_sma20 = sma20_series.iloc[-1] if not sma20_series.dropna().empty else 0.0
# #             result["sma20"] = last_sma20 if pd.notna(last_sma20) and np.isfinite(last_sma20) else 0.0
# #             if result["sma20"] > 1e-9: result["price_div_sma20"] = current_price / result["sma20"]
# #             else: result["price_div_sma20"] = 1.0
# #             result["is_above_sma20"] = int(current_price > result["sma20"]) if result["sma20"] > 1e-9 else None # Int or None
# #         except Exception as e: logging.warning(f"Ошибка SMA20 {player_name}: {e}")
# #
# #         try: # SMA28
# #             sma28_series = sma_indicator(close=close, window=28, fillna=True)
# #             last_sma28 = sma28_series.iloc[-1] if not sma28_series.dropna().empty else 0.0
# #             result["sma28"] = last_sma28 if pd.notna(last_sma28) and np.isfinite(last_sma28) else 0.0
# #             if result["sma28"] > 1e-9: result["price_div_sma28"] = current_price / result["sma28"]
# #             else: result["price_div_sma28"] = 1.0
# #             result["is_above_sma28"] = int(current_price > result["sma28"]) if result["sma28"] > 1e-9 else None # Int or None
# #             result["sma28_slope"] = _calculate_sma_slope(close, 28) # Расчет наклона SMA28
# #         except Exception as e: logging.warning(f"Ошибка SMA28 {player_name}: {e}")
# #
# #     else:
# #          logging.warning(f"Расчеты TA на основе DataFrame пропущены для {player_name} (df_hist={df_hist is not None}, TA_AVAILABLE={TA_AVAILABLE})")
# #
# #     # Волатильность (использует df_hist, если есть)
# #     vol_spike, vol_text, vol_value = check_volatility_spike(df_hist, days=3)
# #     result["volatility_spike"] = vol_spike; result["volatility_text"] = vol_text; result["volatility"] = vol_value
# #
# #     # Расчеты, требующие полной истории (читают ее внутри или используют full_history)
# #     br_count = 0; result["hist_breakouts"] = []
# #     for d_ in [7, 14]:
# #         br = check_historical_breakout(player_name, current_price, days=d_) # Читает историю сам
# #         if br:
# #             br_count += 1; result["hist_breakouts"].append(br)
# #             is_up=int("Max" in br); is_down=int("Min" in br)
# #         else: is_up, is_down = 0, 0
# #         if d_ == 7: result["breakout_7d_up"], result["breakout_7d_down"] = is_up, is_down
# #         if d_ == 14: result["breakout_14d_up"], result["breakout_14d_down"] = is_up, is_down
# #     result["hist_breakout_count"] = br_count
# #     at_ext = check_all_time_extreme(player_name, current_price) # Читает историю сам
# #     result["all_time_extreme"] = at_ext
# #     if at_ext: result["is_all_time_high"] = ("МАКСИМУМ" in at_ext); result["is_all_time_low"] = ("МИНИМУМ" in at_ext)
# #
# #     if full_history: # Используем ранее загруженную историю для DOW/DOM/Trend
# #         try: dow_dev, dow_pos = _calculate_dow_metrics(full_history, now_dt_utc); result["dow_deviation_from_avg"] = dow_dev; result["dow_range_position"] = dow_pos
# #         except Exception as e: logging.error(f"Ошибка _calculate_dow_metrics {player_name}: {e}", exc_info=True)
# #         try: dom_dev = _calculate_dom_metrics(full_history, now_dt_utc); result["dom_deviation_from_avg"] = dom_dev
# #         except Exception as e: logging.error(f"Ошибка _calculate_dom_metrics {player_name}: {e}", exc_info=True)
# #         try: trend_sko = _calculate_trend_sko(full_history, now_dt_utc); result["trend_10d_deviation_sko"] = trend_sko
# #         except Exception as e: logging.error(f"Ошибка _calculate_trend_sko {player_name}: {e}", exc_info=True)
# #         logging.debug(f"Расчеты DOW/DOM/Trend завершены для {player_name}.")
# #     else:
# #         logging.warning(f"Пропуск расчетов DOW/DOM/Trend для {player_name} - нет full_history.")
# #
# #     # Сезонные/Трендовые сигналы (из cycle_analysis)
# #     try: result["seasonal_signal"] = cycle_analysis.create_seasonal_signal_example(player_name); result["seasonal_dow_avg_signal_buy"] = int("BUY" in result["seasonal_signal"]); result["seasonal_dow_avg_signal_sell"] = int("SELL" in result["seasonal_signal"])
# #     except Exception as e: logging.warning(f"Err seasonal: {e}"); result["seasonal_signal"]="Err"
# #     try: result["dow_range_signal"] = cycle_analysis.create_dow_range_signal(player_name, current_price)
# #     except Exception as e: logging.warning(f"Err range: {e}"); result["dow_range_signal"]="Err"
# #     try: result["day_of_month_signal"] = cycle_analysis.create_day_of_month_signal(player_name); result["dom_avg_signal_buy"] = int("BUY" in result["day_of_month_signal"]); result["dom_avg_signal_sell"] = int("SELL" in result["day_of_month_signal"])
# #     except Exception as e: logging.warning(f"Err DOM: {e}"); result["day_of_month_signal"]="Err"
# #     try: result["trend_10d_signal"] = cycle_analysis.create_10_day_trend_signal(player_name)
# #     except Exception as e: logging.warning(f"Err trend: {e}"); result["trend_10d_signal"]="Err"
# #
# #     # Цикл и События
# #     try:
# #         ev_details = events_manager.get_event_phase_details(now_dt=now_dt_utc); result.update(ev_details)
# #         current_day_in_cycle = result.get("days_in_cycle"); result["days_in_cycle"] = current_day_in_cycle if current_day_in_cycle is not None else 0
# #         c_phase = result.get("main_cycle_phase_raw", "N/A"); result["is_cycle_phase_fall"] = int(c_phase == "Падение"); result["is_cycle_phase_bottom"] = int(c_phase == "Дно/Разворот"); result["is_cycle_phase_rise"] = int(c_phase == "Рост"); result["is_cycle_phase_peak"] = int(c_phase == "Завершение/Пик")
# #         result["is_other_event_active"] = bool(result.get("is_other_event_active", False))
# #     except Exception as e: logging.error(f"Err phase: {e}", exc_info=True); result["main_cycle_phase"] = "Err phase"
# #
# #     # DOW/Cycle синусы/косинусы
# #     dow = now_dt_utc.weekday(); result["dow_sin"] = np.sin(2 * np.pi * dow / 7); result["dow_cos"] = np.cos(2 * np.pi * dow / 7)
# #     day_cycle = result.get("days_in_cycle");
# #     if day_cycle is not None and day_cycle > 0: norm_cycle_day = day_cycle - 1; result["cycle_day_sin"] = np.sin(2 * np.pi * norm_cycle_day / 28); result["cycle_day_cos"] = np.cos(2 * np.pi * norm_cycle_day / 28)
# #     else: result["cycle_day_sin"] = 0.0; result["cycle_day_cos"] = 0.0
# #
# #     # Лаги
# #     result["price_lag_1"] = df_hist['price'].iloc[-2] if df_hist is not None and len(df_hist) >= 2 else current_price
# #     # rsi_lag_1 уже рассчитан выше
# #
# #     # OVR/Позиция/Источник
# #     player_ovr = 0 # Инициализация
# #     try: player_config_data = config.load_players().get(player_name, {})
# #     except Exception as cfg_err: logging.error(f"Err config load {player_name}: {cfg_err}"); player_config_data = {}
# #     pos = player_config_data.get("position", "Unknown"); ovr_raw = player_config_data.get("ovr", 0); src_type = player_config_data.get("source_event_type", "past"); result["is_from_current_event"] = 1 if src_type == "current" else 0
# #     try: player_ovr = int(ovr_raw)
# #     except (ValueError, TypeError): player_ovr = 0
# #     # Категория OVR
# #     if player_ovr >= 104: result["ovr_category"] = 3
# #     elif player_ovr >= 101: result["ovr_category"] = 2
# #     elif player_ovr >= 98: result["ovr_category"] = 1
# #     else: result["ovr_category"] = 0
# #     # Позиция one-hot
# #     pos_map = {"CB": 0,"LB": 0,"CM": 0,"RB": 0,"LM": 0,"RW": 0,"ST": 0,"GK": 0};
# #     if pos in pos_map: pos_map[pos] = 1
# #     for p_name_key, p_val in pos_map.items(): result[f"is_position_{p_name_key}"] = p_val
# #     # DOW one-hot
# #     today_dow = now_dt_utc.weekday()
# #     for i in range(7): result[f"is_dow_{i}"] = 1 if today_dow == i else 0
# #
# #     # --- Расчет контекстных сигналов Обмена/Прибыли ---
# #     # ИЗМЕНЕНО: Передаем player_name
# #     _check_exchange_profit_signals(player_name, current_price, player_ovr, df_hist, result)
# #
# #
# #     feat_calc_time = time.time() - start_feat_calc; logging.debug(f"Фичи для {player_name} рассчитаны за {feat_calc_time:.2f} сек.")
# #
# #     # --- Предсказание Модели ---
# #     current_features_dict = {} # Собираем фичи для предсказания
# #     model_prediction_str = "N/A (no features list)"
# #     if not CURRENT_DEFAULT_FEATURES: logging.error(f"Пуст список DEFAULT_FEATURES для предсказания {player_name}.")
# #     else:
# #         for feat in CURRENT_DEFAULT_FEATURES:
# #             val = result.get(feat, 0.0) # Берем значение из рассчитанного result
# #             # Конвертируем булевы значения в int (0 или 1) для модели
# #             if isinstance(val, bool):
# #                  current_features_dict[feat] = int(val)
# #             elif isinstance(val, (int, float)) and np.isfinite(val):
# #                  current_features_dict[feat] = val
# #             else: # Обработка None или других нечисловых значений
# #                  current_features_dict[feat] = 0.0 # Заменяем на 0.0
# #         try: model_prediction_str = get_model_prediction(player_name, current_features_dict)
# #         except Exception as e: logging.error(f"Err predict call {player_name}: {e}", exc_info=True); model_prediction_str = "Err predict call"
# #     result["model_prediction"] = model_prediction_str
# #
# #     # --- Логирование Предсказания ---
# #     try:
# #         prediction_dt_log = datetime.now(timezone.utc)
# #         features_to_log = current_features_dict # Логируем то, что передали в модель
# #         if features_to_log: storage.log_prediction(player_name, prediction_dt_log, features_to_log, result.get("model_prediction", "N/A"))
# #         else: logging.debug(f"Нет фичей для логирования предсказания {player_name}")
# #     except Exception as log_e: logging.error(f"Ошибка лог предск {player_name}: {log_e}")
# #
# #     # --- Агрегация Финального Сигнала (использует НОВУЮ агрегацию v2) ---
# #     start_agg_time = time.time()
# #     sc, txt, summ = check_aggregated_signal_v2(result) # Вызываем НОВУЮ версию
# #     result["aggregated_score"] = sc; result["aggregated_text"] = txt; result["final_summary_text"] = summ
# #     agg_time = time.time() - start_agg_time; logging.debug(f"Агрегация сигнала {player_name} за {agg_time:.3f} сек.")
# #     logging.info(f"Сигнал для {player_name}: Score={sc:.2f}, Rec={txt}")
# #
# #     # --- НОВОЕ: Запись цены покупки при сигнале Strong BUY ---
# #     if txt == "Strong BUY":
# #         logging.info(f"Обнаружен сигнал Strong BUY для {player_name}. Запись цены покупки...")
# #         try:
# #             storage.save_purchase_log(player_name, current_price, now_dt_utc)
# #         except Exception as e_save:
# #             logging.error(f"Не удалось записать лог покупки для {player_name}: {e_save}")
# #     # ----------------------------------------------------
# #
# #     total_time = time.time() - start_time
# #     logging.info(f"--- Завершена обработка сигналов для {player_name} за {total_time:.2f} сек. ---")
# #
# #     return result
#
# # =============================================
# # ФАЙЛ: signals.py (ВЕРСИЯ v23.28 - Low Price Signal Logic - Indentation Fixed)
# # - ИСПРАВЛЕНО: Отступы во всем файле проверены и исправлены.
# # - ДОБАВЛЕНО: Логика проверки низкой цены (< LOW_PRICE_THRESHOLD).
# # - ДОБАВЛЕНО: Проверка потенциальной прибыли при низкой цене с учетом ATH
# #   и PROFIT_COMMISSION_RATE, добавление LOW_PRICE_PROFIT_WEIGHT к score.
# # - ИЗМЕНЕНО: _generate_signal_summary выделяет "Низкая цена + Профит" как ключ.
# # - Содержит исправления из v23.27 (NaN Checks).
# # =============================================
#
# import pandas as pd
# import numpy as np
# import logging
# from datetime import datetime, timedelta, timezone
# import traceback
# import time
# import io
#
# # --- Логгер ---
# logger = logging.getLogger("signals")
#
# # --- Импорт зависимостей ---
# try:
#     import ta as ta_lib
# except ImportError:
#     logger.critical("Библиотека 'ta' не найдена!")
#     ta_lib = None
# try:
#     from scipy.signal import find_peaks
# except ImportError:
#     logger.warning("Библиотека 'scipy' не найдена.")
# try:
#     import config       # Ожидается v8.18+
#     import storage      # Ожидается v6.10+
#     import notifications # Ожидается v10.12+
#     import cycle_analysis # Ожидается v8.9+
# except ImportError as e:
#     logger.critical(f"Ошибка импорта соседнего модуля в signals.py: {e}")
#     # Создаем заглушки, чтобы избежать AttributeError при дальнейшей работе
#     class ConfigMock:
#         LOW_PRICE_THRESHOLD=15500000
#         PROFIT_COMMISSION_RATE=0.1
#         LOW_PRICE_PROFIT_WEIGHT=5.0
#         SMA_SHORT_PERIOD=10
#         SMA_LONG_PERIOD=30
#         RSI_OVERSOLD = 30
#         RSI_OVERBOUGHT = 70
#         MACD_FAST_PERIOD = 12
#         MACD_SLOW_PERIOD = 26
#         MACD_SIGNAL_PERIOD = 9
#         BOLLINGER_PERIOD = 20
#         BOLLINGER_STD_DEV = 2
#         RSI_OVERSOLD_WEIGHT = 1.0
#         RSI_OVERBOUGHT_WEIGHT = -1.0
#         MACD_BULLISH_CROSS_WEIGHT = 1.2
#         MACD_BEARISH_CROSS_WEIGHT = -1.2
#         MACD_HIST_POSITIVE_WEIGHT = 0.3
#         MACD_HIST_NEGATIVE_WEIGHT = -0.3
#         SMA_FAST_ABOVE_SLOW_WEIGHT = 1.5
#         SMA_SLOW_ABOVE_FAST_WEIGHT = -1.5
#         BOLLINGER_LOWER_BREAK_WEIGHT = 1.5
#         BOLLINGER_UPPER_BREAK_WEIGHT = -1.5
#         ATH_WEIGHT = -2.0
#         ATL_WEIGHT = 2.0
#         BUY_THRESHOLD_STRONG = 4.5
#         BUY_THRESHOLD_MEDIUM = 3.0
#         SELL_THRESHOLD_STRONG = -4.5
#         SELL_THRESHOLD_MEDIUM = -3.0
#         pass
#     config = ConfigMock()
#     class StorageMock:
#         @staticmethod
#         def format_price(p):
#             return str(p) if p is not None else "N/A"
#         pass
#     storage = StorageMock()
#     class NotificationsMock: pass
#     notifications = NotificationsMock()
#     class CycleAnalysisMock:
#         @staticmethod
#         def determine_main_cycle_phase_df(df):
#             return {'phase': 'N/A'}
#         @staticmethod
#         def determine_short_cycle_phase_df(df):
#             return {'phase': 'N/A'}
#         pass
#     cycle_analysis = CycleAnalysisMock()
#
# # --- Константы и Настройки ---
# MIN_PRICE_CHANGE_FOR_VOLATILITY = 0.001
# # Константа для причины (чтобы избежать опечаток)
# LOW_PRICE_PROFIT_REASON = "Низкая цена + Профит"
#
# # --- Функции расчета TA ---
# def calculate_rsi(close_prices, period):
#     if ta_lib is None: return None
#     try:
#         rsi_indicator = ta_lib.momentum.RSIIndicator(close=close_prices, window=period)
#         rsi = rsi_indicator.rsi()
#         return rsi.iloc[-1] if rsi is not None and not rsi.empty else None
#     except Exception as e:
#         logger.error(f"Ошибка RSI: {e}")
#         return None
#
# def calculate_macd(close_prices, fast, slow, signal):
#     if ta_lib is None: return None, None, None
#     try:
#         macd_indicator = ta_lib.trend.MACD(close=close_prices, window_fast=fast, window_slow=slow, window_sign=signal)
#         line = macd_indicator.macd()
#         sig = macd_indicator.macd_signal()
#         hist = macd_indicator.macd_diff()
#         return line.iloc[-1], sig.iloc[-1], hist.iloc[-1] if line is not None and sig is not None and hist is not None and not line.empty else (None, None, None)
#     except Exception as e:
#         logger.error(f"Ошибка MACD: {e}")
#         return None, None, None
#
# def calculate_sma(close_prices, period):
#     if ta_lib is None: return None
#     try:
#         sma_indicator = ta_lib.trend.SMAIndicator(close=close_prices, window=period)
#         sma = sma_indicator.sma_indicator()
#         return sma.iloc[-1] if sma is not None and not sma.empty else None
#     except Exception as e:
#         logger.error(f"Ошибка SMA: {e}")
#         return None
#
# def calculate_bollinger_bands(close_prices, period, std_dev):
#     if ta_lib is None: return None, None, None
#     try:
#         bb_indicator = ta_lib.volatility.BollingerBands(close=close_prices, window=period, window_dev=std_dev)
#         h = bb_indicator.bollinger_hband()
#         l = bb_indicator.bollinger_lband()
#         m = bb_indicator.bollinger_mavg()
#         return h.iloc[-1], m.iloc[-1], l.iloc[-1] if h is not None and l is not None and m is not None and not h.empty else (None, None, None)
#     except Exception as e:
#         logger.error(f"Ошибка BB: {e}")
#         return None, None, None
#
# # --- Функция генерации Резюме ---
# def _generate_signal_summary(signal, confidence, score, reasons, details):
#     logger.debug(f"Генерация резюме: {signal} ({confidence}), Score: {score:.2f}")
#     summary_lines = []
#     outcome_parts = []
#     key_factors = [] # Инициализируем key_factors здесь
#
#     try:
#         # 1. Итог
#         signal_emoji = "⚪️"
#         if signal == 'BUY': signal_emoji = "🟢" if confidence == 'Strong' else "🟩"
#         elif signal == 'SELL': signal_emoji = "🔴" if confidence == 'Strong' else "🟥"
#         outcome_parts.append(f"{signal_emoji} *{signal}* ({confidence}, Score: {score:.2f})")
#
#         main_cycle_data = details.get('main_cycle', {})
#         short_cycle_data = details.get('short_cycle', {})
#         main_phase = main_cycle_data.get('phase', 'N/A') if isinstance(main_cycle_data, dict) else 'Error'
#         short_phase = short_cycle_data.get('phase', 'N/A') if isinstance(short_cycle_data, dict) else 'Error'
#
#         if main_phase not in ['N/A', 'Error']:
#             outcome_parts.append(f"ОснЦ:{main_phase}")
#         elif isinstance(main_cycle_data, dict) and main_cycle_data.get('error'):
#             outcome_parts.append(f"ОснЦ:Ошибка")
#         if short_phase not in ['N/A', 'Error']:
#             outcome_parts.append(f"КорЦ:{short_phase}")
#         elif isinstance(short_cycle_data, dict) and short_cycle_data.get('error'):
#             outcome_parts.append(f"КорЦ:Ошибка")
#         summary_lines.append("*Итог:* " + " | ".join(outcome_parts))
#
#         # 2. Почему
#         current_reasons = []
#         if signal == 'BUY': current_reasons = reasons.get('BUY', [])
#         elif signal == 'SELL': current_reasons = reasons.get('SELL', [])
#         elif signal == 'HOLD': current_reasons = reasons.get('HOLD', [])
#
#         if signal == 'HOLD':
#             if main_phase not in ['N/A', 'Error'] and f"ОснЦ:{main_phase}" not in current_reasons:
#                 current_reasons.append(f"ОснЦ:{main_phase}")
#             if short_phase not in ['N/A', 'Error'] and f"КорЦ:{short_phase}" not in current_reasons:
#                 current_reasons.append(f"КорЦ:{short_phase}")
#
#         unique_why = []
#         [unique_why.append(str(r)) for r in current_reasons if r is not None and str(r) not in unique_why]
#         why_str = ", ".join(unique_why) if unique_why else "Нет явных причин."
#         summary_lines.append(f"*Почему:* {why_str}")
#
#         # 3. Ключи
#         buy_reasons_list = reasons.get('BUY', [])
#         if LOW_PRICE_PROFIT_REASON in buy_reasons_list:
#             key_factors.append(f"💰 {LOW_PRICE_PROFIT_REASON}")
#
#         if main_phase not in ['N/A', 'Error']: key_factors.append(f"ОснЦ:{main_phase}")
#         if short_phase not in ['N/A', 'Error']: key_factors.append(f"КорЦ:{short_phase}")
#
#         if signal == 'BUY':
#             buy_key_reasons = list(str(r) for r in buy_reasons_list if r is not None and ('ATL' in str(r) or 'BB' in str(r) or 'RSI' in str(r)))
#             key_factors.extend(buy_key_reasons[:1])
#         elif signal == 'SELL':
#             sell_reasons_list = reasons.get('SELL', [])
#             sell_key_reasons = list(str(r) for r in sell_reasons_list if r is not None and ('ATH' in str(r) or 'BB' in str(r) or 'RSI' in str(r)))
#             key_factors.extend(sell_key_reasons[:1])
#
#         sma_buy_reason = f"SMA{config.SMA_SHORT_PERIOD}>SMA{config.SMA_LONG_PERIOD}"
#         sma_sell_reason = f"SMA{config.SMA_SHORT_PERIOD}<SMA{config.SMA_LONG_PERIOD}"
#         if sma_buy_reason in [str(r) for r in buy_reasons_list if r is not None]:
#             key_factors.append("SMA Cross BUY")
#         elif sma_sell_reason in [str(r) for r in reasons.get('SELL', []) if r is not None]:
#             key_factors.append("SMA Cross SELL")
#
#         if not key_factors and signal != 'HOLD': key_factors.append(f"Сигнал: {signal}")
#         elif not key_factors and signal == 'HOLD': key_factors.append("Нейтрально")
#
#         unique_keys = []
#         [unique_keys.append(k) for k in key_factors if k not in unique_keys];
#         keys_str = ", ".join(unique_keys[:3])
#         if len(unique_keys) > 3: keys_str += "..."
#         if not keys_str: keys_str = "Нет явных ключей."
#         summary_lines.append(f"*Ключи:* {keys_str}")
#
#         final_summary = "\n".join(summary_lines);
#         logger.debug(f"Сгенерировано резюме:\n{final_summary}")
#         return final_summary
#     except Exception as e_gen_sum:
#         logger.error(f"Ошибка внутри _generate_signal_summary: {e_gen_sum}", exc_info=True)
#         return "*Ошибка генерации резюме.*"
# # -----------------------------------------------------------------
#
# # --- Основная функция проверки сигналов ---
# def check_signals(history_df, player_config, latest_parsed_data=None):
#     player_name = player_config.get('name', 'Unknown_Signal')
#     logger.debug(f"[{player_name}] Запуск check_signals. Config: {player_config}, Parsed: {'Есть' if latest_parsed_data else 'Нет'}")
#     signals_log = {'player': player_name, 'timestamp': datetime.now(timezone.utc).isoformat(), 'aggregated_score': 0.0, 'signal': 'HOLD', 'confidence': 'Low', 'send_notification': False, 'reasons': {'BUY': [], 'SELL': [], 'HOLD': []}, 'details': {}, 'error': None, 'final_summary_text': 'Резюме не сгенерировано.'}
#     aggregated_score = 0.0; reasons = {'BUY': [], 'SELL': [], 'HOLD': []}; signal_details = {}; df_ta = None; current_price = None; ath = None; atl = None
#
#     # --- 1. Подготовка данных ---
#     try:
#         if latest_parsed_data and isinstance(latest_parsed_data, dict):
#             price_raw = latest_parsed_data.get('price')
#             if price_raw is not None:
#                 try:
#                     current_price = int(float(price_raw))
#                     signal_details['current_price'] = storage.format_price(current_price)
#                     logger.debug(f"[{player_name}] Текущая цена из парсера: {signal_details['current_price']}")
#                 except (ValueError, TypeError):
#                     logger.warning(f"[{player_name}] Не удалось конвертировать 'price' из parsed_data: '{price_raw}'. Считаем N/A.")
#                     current_price = None; signal_details['current_price'] = "N/A"
#             else:
#                 logger.info(f"[{player_name}] Текущая цена ('price') отсутствует в parsed_data.")
#                 signal_details['current_price'] = "N/A"
#             signal_details['change'] = latest_parsed_data.get('change', None)
#             signal_details['min_order'] = latest_parsed_data.get('min_order')
#             signal_details['max_order'] = latest_parsed_data.get('max_order')
#             ts_raw = latest_parsed_data.get('timestamp')
#             if ts_raw:
#                 try:
#                     signal_details['last_update_time'] = datetime.fromisoformat(ts_raw).strftime('%Y-%m-%d %H:%M:%S %Z')
#                 except:
#                     logger.warning(f"[{player_name}] Не удалось распарсить timestamp из parsed_data: {ts_raw}")
#         else:
#             logger.warning(f"[{player_name}] latest_parsed_data не предоставлены или некорректны.")
#             signal_details.update({'current_price': "N/A", 'change': None, 'min_order': None, 'max_order': None})
#
#         if history_df is None or history_df.empty:
#             raise ValueError("Пустой DataFrame истории.")
#
#         df_ta = history_df.copy().reset_index()
#         if 'datetime' in df_ta.columns:
#             df_ta.rename(columns={'datetime': 'timestamp'}, inplace=True)
#         elif pd.api.types.is_datetime64_any_dtype(df_ta.iloc[:, 0]):
#             df_ta.rename(columns={df_ta.columns[0]: 'timestamp'}, inplace=True)
#         if 'timestamp' not in df_ta.columns:
#             raise ValueError("Нет колонки 'timestamp' для TA.")
#
#         if not pd.api.types.is_datetime64_any_dtype(df_ta['timestamp']):
#             df_ta['timestamp'] = pd.to_datetime(df_ta['timestamp'], errors='coerce')
#             df_ta.dropna(subset=['timestamp'], inplace=True)
#
#         if df_ta['timestamp'].dt.tz is None:
#             df_ta['timestamp'] = df_ta['timestamp'].dt.tz_localize('UTC')
#         else:
#             df_ta['timestamp'] = df_ta['timestamp'].dt.tz_convert('UTC')
#
#         rename_map = {'Цена': 'close', 'Мин. цена': 'low', 'Макс. цена': 'high'}
#         orig_cols = list(rename_map.keys())
#         if not all(c in df_ta.columns for c in orig_cols):
#             raise ValueError(f"Нет колонок для TA: {[c for c in orig_cols if c not in df_ta.columns]}")
#         df_ta.rename(columns=rename_map, inplace=True)
#
#         df_ta['open'] = df_ta['close'].shift(1)
#         df_ta['open'] = df_ta['open'].fillna(df_ta['close'])
#
#         req_ta_cols = ['timestamp', 'open', 'high', 'low', 'close']
#         if not all(c in df_ta.columns for c in req_ta_cols):
#             raise ValueError(f"Нет колонок TA: {[c for c in req_ta_cols if c not in df_ta.columns]}")
#         df_ta.dropna(subset=req_ta_cols, inplace=True)
#
#         if df_ta.empty:
#             raise ValueError("DF пуст после подготовки (удаления NA в OHLC).")
#         logger.debug(f"[{player_name}] DF для TA готов, строк: {len(df_ta)}")
#
#         if current_price is None and not df_ta.empty:
#             last_hist_price = df_ta['close'].iloc[-1]
#             if pd.notna(last_hist_price):
#                 current_price = int(last_hist_price)
#                 signal_details['current_price'] = storage.format_price(current_price) + " (H)"
#                 logger.warning(f"[{player_name}] Текущая цена N/A, используется последняя из истории: {signal_details['current_price']}")
#             else:
#                 logger.warning(f"[{player_name}] Последняя цена в истории тоже N/A.")
#                 signal_details['current_price'] = "N/A"
#
#         if 'last_update_time' not in signal_details and not df_ta.empty:
#             signal_details['last_update_time'] = df_ta['timestamp'].iloc[-1].strftime('%Y-%m-%d %H:%M:%S %Z')
#
#     except Exception as e_prep:
#         logger.error(f"Ошибка подготовки данных ({player_name}): {e_prep}", exc_info=True)
#         signals_log['error'] = f"Ошибка данных: {e_prep}"
#         signals_log['details'].update({
#             'current_price': "Error", 'change': None, 'min_order': None, 'max_order': None,
#             'last_update_time': 'N/A', 'rsi': 'N/A', 'macd': 'N/A', 'sma': 'N/A',
#             'bollinger': 'N/A', 'main_cycle': {'phase':'N/A'}, 'short_cycle': {'phase':'N/A'},
#             'ath': 'N/A', 'atl': 'N/A', 'low_price_zone': False
#         })
#         signals_log['final_summary_text'] = "*Ошибка подготовки данных, анализ невозможен.*"
#         logger.info(f"[{player_name}] Итог: Ошибка подготовки данных.")
#         return signals_log
#
#     # --- 2. Расчет TA ---
#     ta_available = False
#     if df_ta is not None and not df_ta.empty:
#         try:
#             logger.debug(f"[{player_name}] Расчет TA...");
#             ta_start = time.time()
#
#             rsi_val = calculate_rsi(df_ta['close'], config.RSI_PERIOD)
#             signal_details['rsi'] = f"{rsi_val:.2f}" if pd.notna(rsi_val) else "N/A"
#             if pd.notna(rsi_val):
#                 if rsi_val < config.RSI_OVERSOLD:
#                     aggregated_score += getattr(config, 'RSI_OVERSOLD_WEIGHT', 1.0)
#                     reasons['BUY'].append(f"RSI<{config.RSI_OVERSOLD}({rsi_val:.1f})")
#                 elif rsi_val > config.RSI_OVERBOUGHT:
#                     aggregated_score += getattr(config, 'RSI_OVERBOUGHT_WEIGHT', -1.0)
#                     reasons['SELL'].append(f"RSI>{config.RSI_OVERBOUGHT}({rsi_val:.1f})")
#
#             macd_line, signal_line, macd_hist = calculate_macd(df_ta['close'], config.MACD_FAST_PERIOD, config.MACD_SLOW_PERIOD, config.MACD_SIGNAL_PERIOD)
#             signal_details['macd'] = f"L:{macd_line:.1f},S:{signal_line:.1f},H:{macd_hist:.1f}" if pd.notna(macd_line) and pd.notna(signal_line) and pd.notna(macd_hist) else "N/A"
#             if pd.notna(macd_line) and pd.notna(signal_line) and pd.notna(macd_hist):
#                 prev_macd_hist = 0
#                 if len(df_ta) > 1:
#                     try:
#                         prev_macd_line, prev_signal_line, prev_macd_hist_val = calculate_macd(df_ta['close'].iloc[:-1], config.MACD_FAST_PERIOD, config.MACD_SLOW_PERIOD, config.MACD_SIGNAL_PERIOD)
#                         if pd.notna(prev_macd_hist_val): prev_macd_hist = prev_macd_hist_val
#                     except Exception as e_macd_prev:
#                         logger.warning(f"[{player_name}] Не удалось получить пред. MACD hist: {e_macd_prev}")
#                 if macd_hist > 0 and prev_macd_hist <= 0:
#                     aggregated_score += getattr(config, 'MACD_BULLISH_CROSS_WEIGHT', 1.2)
#                     reasons['BUY'].append("MACD Cross")
#                 elif macd_hist < 0 and prev_macd_hist >= 0:
#                     aggregated_score += getattr(config, 'MACD_BEARISH_CROSS_WEIGHT', -1.2)
#                     reasons['SELL'].append("MACD Cross")
#                 if macd_hist > 0:
#                     aggregated_score += getattr(config, 'MACD_HIST_POSITIVE_WEIGHT', 0.3)
#                 elif macd_hist < 0:
#                     aggregated_score += getattr(config, 'MACD_HIST_NEGATIVE_WEIGHT', -0.3)
#
#             sma_short = calculate_sma(df_ta['close'], config.SMA_SHORT_PERIOD)
#             sma_long = calculate_sma(df_ta['close'], config.SMA_LONG_PERIOD)
#             signal_details['sma'] = f"S:{storage.format_price(sma_short)},L:{storage.format_price(sma_long)}" if pd.notna(sma_short) and pd.notna(sma_long) else "N/A"
#             if pd.notna(sma_short) and pd.notna(sma_long):
#                 sma_buy_reason = f"SMA{config.SMA_SHORT_PERIOD}>SMA{config.SMA_LONG_PERIOD}"
#                 sma_sell_reason = f"SMA{config.SMA_SHORT_PERIOD}<SMA{config.SMA_LONG_PERIOD}"
#                 if sma_short > sma_long:
#                     aggregated_score += getattr(config, 'SMA_FAST_ABOVE_SLOW_WEIGHT', 1.5)
#                     reasons['BUY'].append(sma_buy_reason)
#                 else:
#                     aggregated_score += getattr(config, 'SMA_SLOW_ABOVE_FAST_WEIGHT', -1.5)
#                     reasons['SELL'].append(sma_sell_reason)
#
#             bb_h, bb_m, bb_l = calculate_bollinger_bands(df_ta['close'], config.BOLLINGER_PERIOD, config.BOLLINGER_STD_DEV)
#             signal_details['bollinger'] = f"L:{storage.format_price(bb_l)},M:{storage.format_price(bb_m)},H:{storage.format_price(bb_h)}" if pd.notna(bb_h) and pd.notna(bb_m) and pd.notna(bb_l) else "N/A"
#             if pd.notna(bb_h) and pd.notna(bb_l) and current_price is not None:
#                 bb_buy_reason = f"Цена<BB({storage.format_price(current_price)}<{storage.format_price(bb_l)})"
#                 bb_sell_reason = f"Цена>BB({storage.format_price(current_price)}>{storage.format_price(bb_h)})"
#                 if current_price > bb_h:
#                     aggregated_score += getattr(config, 'BOLLINGER_UPPER_BREAK_WEIGHT', -1.5)
#                     reasons['SELL'].append(bb_sell_reason)
#                 elif current_price < bb_l:
#                     aggregated_score += getattr(config, 'BOLLINGER_LOWER_BREAK_WEIGHT', 1.5)
#                     reasons['BUY'].append(bb_buy_reason)
#
#             ta_available = True;
#             logger.debug(f"[{player_name}] Расчет TA завершен за {time.time() - ta_start:.3f} сек.")
#         except Exception as e_ta:
#             logger.error(f"Ошибка при расчете TA для {player_name}: {e_ta}", exc_info=True)
#             signals_log['error'] = f"Ошибка TA: {e_ta}";
#             signal_details.update({'rsi': "Error", 'macd': "Error", 'sma': "Error", 'bollinger': "Error"})
#             ta_available = False
#     else:
#          logger.warning(f"Расчет TA пропущен для {player_name} (нет данных в df_ta).")
#          signal_details.update({'rsi': "N/A", 'macd': "N/A", 'sma': "N/A", 'bollinger': "N/A"})
#
#     # --- 3. Анализ циклов ---
#     cycle_possible = history_df is not None and not history_df.empty and isinstance(history_df.index, pd.DatetimeIndex)
#     if not cycle_possible:
#         logger.warning(f"[{player_name}] Анализ циклов пропущен (невалидный history_df).")
#         signal_details['main_cycle']={'phase':'N/A', 'error': 'Input df invalid'}
#         signal_details['short_cycle']={'phase':'N/A', 'error': 'Input df invalid'}
#     else:
#         main_phase='N/A'; short_phase='N/A'; main_details={}; short_details={}
#         try:
#             cycle_start = time.time()
#             logger.debug(f"[{player_name}] Запуск анализа циклов...")
#             main_phase_data = cycle_analysis.determine_main_cycle_phase_df(history_df.copy())
#             short_phase_data = cycle_analysis.determine_short_cycle_phase_df(history_df.copy())
#             logger.debug(f"[{player_name}] Результат Осн.Цикла: {main_phase_data}")
#             logger.debug(f"[{player_name}] Результат Кор.Цикла: {short_phase_data}")
#
#             if isinstance(main_phase_data, dict):
#                 main_phase = main_phase_data.get('phase', 'Error')
#                 main_details = main_phase_data;
#                 if main_phase not in ['N/A', 'Error']:
#                     aggregated_score += getattr(config, f"MAIN_CYCLE_{main_phase.upper()}_WEIGHT", 0)
#                     reasons['HOLD'].append(f"ОснЦ:{main_phase}")
#                 elif main_phase == 'Error':
#                     logger.warning(f"[{player_name}] Ошибка расчета основного цикла: {main_details.get('error')}")
#             else:
#                 logger.error(f"[{player_name}] Некорректный тип возврата из Осн.Цикла: {type(main_phase_data)}")
#                 main_phase = "Error"; main_details = {'phase': 'Error', 'error': 'Invalid return type'}
#
#             if isinstance(short_phase_data, dict):
#                 short_phase = short_phase_data.get('phase', 'Error')
#                 short_details = short_phase_data;
#                 if short_phase not in ['N/A', 'Error']:
#                     aggregated_score += getattr(config, f"SHORT_CYCLE_{short_phase.upper()}_WEIGHT", 0)
#                     reasons['HOLD'].append(f"КорЦ:{short_phase}")
#                 elif short_phase == 'Error':
#                     logger.warning(f"[{player_name}] Ошибка расчета короткого цикла: {short_details.get('error')}")
#             else:
#                 logger.error(f"[{player_name}] Некорректный тип возврата из Кор.Цикла: {type(short_phase_data)}")
#                 short_phase = "Error"; short_details = {'phase': 'Error', 'error': 'Invalid return type'}
#
#             signal_details['main_cycle'] = main_details
#             signal_details['short_cycle'] = short_details
#             logger.debug(f"[{player_name}] Анализ циклов завершен за {time.time() - cycle_start:.3f} сек. Фазы: Осн={main_phase}, Кор={short_phase}")
#         except Exception as e_cycle:
#             logger.error(f"Критическая ошибка при вызове анализа циклов для {player_name}: {e_cycle}", exc_info=True);
#             signal_details['main_cycle'] = {'phase': 'Error', 'error': str(e_cycle)}
#             signal_details['short_cycle'] = {'phase': 'Error', 'error': str(e_cycle)};
#             if not signals_log['error']: signals_log['error'] = f"Ошибка циклов: {e_cycle}"
#
#     # --- 4. Контекст и ATH/ATL ---
#     try:
#         if history_df is not None and not history_df.empty:
#             ath = history_df['Цена'].max()
#             atl = history_df['Цена'].min()
#             logger.debug(f"[{player_name}] ATH/ATL Детали: ath={ath} ({type(ath)}), atl={atl} ({type(atl)})")
#             signal_details['ath'] = storage.format_price(ath) if pd.notna(ath) else "N/A"
#             signal_details['atl'] = storage.format_price(atl) if pd.notna(atl) else "N/A"
#
#             price_to_compare = current_price
#             min_order_price = signal_details.get('min_order')
#
#             if price_to_compare is None and min_order_price is not None:
#                 price_to_compare = min_order_price
#                 logger.info(f"[{player_name}] Цена N/A, используем Min ордер ({storage.format_price(price_to_compare)}) для сравнения ATH/ATL.")
#             elif price_to_compare is None:
#                 logger.warning(f"[{player_name}] Цена для сравнения ATH/ATL недоступна (current=None, min_order=None).")
#
#             if price_to_compare is not None and pd.notna(ath) and pd.notna(atl):
#                 price_range = ath - atl
#                 if price_range > 0:
#                     logger.debug(f"[{player_name}] ATH/ATL Причины: price_to_compare={price_to_compare}, ath={ath}, atl={atl}, range={price_range}")
#                     ath_str = storage.format_price(ath)
#                     atl_str = storage.format_price(atl)
#                     ath_reason = f"Близко к ATH ({ath_str})"
#                     atl_reason = f"Близко к ATL ({atl_str})"
#                     if (ath - price_to_compare) / price_range < 0.05:
#                         aggregated_score += getattr(config, 'ATH_WEIGHT', -2.0)
#                         reasons['SELL'].append(ath_reason)
#                     if (price_to_compare - atl) / price_range < 0.05:
#                         aggregated_score += getattr(config, 'ATL_WEIGHT', 2.0)
#                         reasons['BUY'].append(atl_reason)
#                 elif price_range == 0:
#                     logger.debug(f"[{player_name}] Нулевой price_range ({price_range}), сравнение ATH/ATL не выполняется.")
#                 else:
#                     logger.warning(f"[{player_name}] Отрицательный price_range ({price_range}), ATH={ath}, ATL={atl}. Сравнение ATH/ATL пропущено.")
#             else:
#                 logger.debug(f"[{player_name}] Недостаточно данных для сравнения ATH/ATL (price_to_compare={price_to_compare}, ath={ath}, atl={atl}).")
#         else:
#             logger.warning(f"[{player_name}] Пропуск ATH/ATL: нет history_df.")
#             signal_details.update({'ath': "N/A", 'atl': "N/A"})
#     except Exception as e_context:
#         logger.error(f"Ошибка при расчете ATH/ATL для {player_name}: {e_context}", exc_info=True)
#         signal_details.update({'ath': "Error", 'atl': "Error"})
#         if not signals_log['error']: signals_log['error'] = f"Ошибка ATH/ATL: {e_context}"
#
#     # --- 5. Сигнал Низкой Цены ---
#     is_low_price_zone = False
#     try:
#         if current_price is not None:
#             low_price_threshold = getattr(config, 'LOW_PRICE_THRESHOLD', 15500000)
#             if current_price <= low_price_threshold:
#                 is_low_price_zone = True
#                 low_price_formatted = storage.format_price(low_price_threshold)
#                 logger.info(f"[{player_name}] Цена ({storage.format_price(current_price)}) ниже или равна порогу ({low_price_formatted}).")
#                 low_price_reason = f"Низкая цена (<={low_price_formatted})"
#                 if low_price_reason not in reasons['HOLD']:
#                     reasons['HOLD'].append(low_price_reason)
#
#                 if pd.notna(ath):
#                     commission_rate = getattr(config, 'PROFIT_COMMISSION_RATE', 0.10)
#                     potential_sale_price = ath * (1 - commission_rate)
#                     logger.debug(f"[{player_name}] Проверка профита при низкой цене: ATH={storage.format_price(ath)}, Цена продажи после комиссии ~{storage.format_price(potential_sale_price)}, Текущая цена={storage.format_price(current_price)}")
#                     if potential_sale_price > current_price:
#                         profit_weight = getattr(config, 'LOW_PRICE_PROFIT_WEIGHT', 5.0)
#                         logger.info(f"[{player_name}] Обнаружен потенциальный профит при низкой цене! Добавляем вес: +{profit_weight}")
#                         aggregated_score += profit_weight
#                         if LOW_PRICE_PROFIT_REASON not in reasons['BUY']:
#                             reasons['BUY'].append(LOW_PRICE_PROFIT_REASON)
#                         if low_price_reason in reasons['HOLD']:
#                             try:
#                                 reasons['HOLD'].remove(low_price_reason)
#                             except ValueError: pass
#                     else:
#                         logger.info(f"[{player_name}] Низкая цена, но потенциальный профит не обнаружен (ATH={storage.format_price(ath)}).")
#                 else:
#                     logger.warning(f"[{player_name}] Низкая цена, но ATH невалиден ({ath}). Проверка профита невозможна.")
#             else:
#                 logger.debug(f"[{player_name}] Цена ({storage.format_price(current_price)}) выше порога низкой цены.")
#         else:
#             logger.warning(f"[{player_name}] Пропуск проверки низкой цены: текущая цена не определена.")
#     except Exception as e_low_price:
#         logger.error(f"Ошибка в блоке сигнала низкой цены для {player_name}: {e_low_price}", exc_info=True)
#         if not signals_log['error']: signals_log['error'] = f"Ошибка сигнала низкой цены: {e_low_price}"
#     finally:
#         signal_details['low_price_zone'] = is_low_price_zone
#
#     # --- 6. Финальное Определение Сигнала ---
#     signals_log['aggregated_score'] = round(aggregated_score, 2)
#     buy_strong = getattr(config, 'BUY_THRESHOLD_STRONG', 4.5); buy_medium = getattr(config, 'BUY_THRESHOLD_MEDIUM', 3.0); sell_strong = getattr(config, 'SELL_THRESHOLD_STRONG', -4.5); sell_medium = getattr(config, 'SELL_THRESHOLD_MEDIUM', -3.0)
#     if aggregated_score >= buy_strong: signals_log.update({'signal': 'BUY', 'confidence': 'Strong'})
#     elif aggregated_score >= buy_medium: signals_log.update({'signal': 'BUY', 'confidence': 'Medium'})
#     elif aggregated_score <= sell_strong: signals_log.update({'signal': 'SELL', 'confidence': 'Strong'})
#     elif aggregated_score <= sell_medium: signals_log.update({'signal': 'SELL', 'confidence': 'Medium'})
#     else: signals_log.update({'signal': 'HOLD', 'confidence': 'Low'})
#
#     # --- 7. Генерация Резюме ---
#     try:
#         final_summary_text = _generate_signal_summary(signals_log['signal'], signals_log['confidence'], signals_log['aggregated_score'], reasons, signal_details)
#         signals_log['final_summary_text'] = final_summary_text
#     except Exception as e_summary:
#         logger.error(f"Ошибка генерации итогового резюме для {player_name}: {e_summary}", exc_info=True); signals_log['final_summary_text'] = "*Ошибка генерации резюме.*"
#         if not signals_log['error']: signals_log['error'] = f"Ошибка резюме: {e_summary}"
#
#     # --- 8. Решение об отправке уведомления ---
#     signals_log['send_notification'] = False
#     if signals_log['signal'] != 'HOLD': signals_log['send_notification'] = True
#     # TODO: Добавить логику SEND_HOLD_NOTIFICATION_INTERVAL_HOURS, если нужно
#
#     # --- Завершение ---
#     signals_log['details'] = signal_details; signals_log['reasons'] = reasons
#     logger.info(f"[{player_name}] Итог: Score={signals_log['aggregated_score']:.2f}, Сигнал={signals_log['signal']}({signals_log['confidence']}), Увед={signals_log['send_notification']}")
#     return signals_log

# =============================================
# ФАЙЛ: signals.py (ВЕРСИЯ v23.35 - Fix BB Value Saving - Indentation Re-Re-Verified)
# - ПЕРЕПРОВЕРЕНО: Отступы во всем файле.
# - ИСПРАВЛЕНО: Числовые значения bb_h_val и bb_l_val теперь
#   сохраняются в details, даже если bb_m_val некорректен,
#   главное, чтобы bb_h и bb_l были валидными.
# - Содержит все изменения из v23.33 (Enhanced Score Logging).
# =============================================

import pandas as pd
import numpy as np
import logging
from datetime import datetime, timedelta, timezone
import traceback
import time
import io
import math # Для math.isclose

# --- Логгер ---
logger = logging.getLogger("signals")

# --- Импорт зависимостей ---
try:
    import ta as ta_lib
except ImportError: logger.critical("Библиотека 'ta' не найдена!"); ta_lib = None
try:
    from scipy.signal import find_peaks
except ImportError: logger.warning("Библиотека 'scipy' не найдена.")
try:
    import config       # Ожидается v8.19+
    import storage      # Ожидается v6.11+
    import notifications # Ожидается v10.16+
    import cycle_analysis # Ожидается v8.9+
except ImportError as e:
     logger.critical(f"Ошибка импорта соседнего модуля в signals.py: {e}")
     # Заглушки ...
     class ConfigMock: LOW_PRICE_THRESHOLD=15500000; PROFIT_COMMISSION_RATE=0.1; LOW_PRICE_PROFIT_WEIGHT=5.0; SMA_SHORT_PERIOD=10; SMA_LONG_PERIOD=30; RSI_OVERSOLD = 30; RSI_OVERBOUGHT = 70; MACD_FAST_PERIOD = 12; MACD_SLOW_PERIOD = 26; MACD_SIGNAL_PERIOD = 9; BOLLINGER_PERIOD = 20; BOLLINGER_STD_DEV = 2; RSI_OVERSOLD_WEIGHT = 1.0; RSI_OVERBOUGHT_WEIGHT = -1.0; MACD_BULLISH_CROSS_WEIGHT = 1.2; MACD_BEARISH_CROSS_WEIGHT = -1.2; MACD_HIST_POSITIVE_WEIGHT = 0.3; MACD_HIST_NEGATIVE_WEIGHT = -0.3; SMA_FAST_ABOVE_SLOW_WEIGHT = 1.5; SMA_SLOW_ABOVE_FAST_WEIGHT = -1.5; BOLLINGER_LOWER_BREAK_WEIGHT = 1.5; BOLLINGER_UPPER_BREAK_WEIGHT = -1.5; ATH_WEIGHT = -2.0; ATL_WEIGHT = 2.0; BUY_THRESHOLD_STRONG = 4.5; BUY_THRESHOLD_MEDIUM = 3.0; SELL_THRESHOLD_STRONG = -4.5; SELL_THRESHOLD_MEDIUM = -3.0; MIN_SCORE_CHANGE_FOR_NOTIFICATION=0.5; SEND_HOLD_IF_SCORE_CHANGED=True; pass; config = ConfigMock()
     class StorageMock:
         @staticmethod
         def format_price(p):
             if pd.isna(p): return "N/A"
             try: return f"{int(p):,}".replace(",", " ")
             except: return "N/A"
     storage = StorageMock()
     class NotificationsMock: pass; notifications = NotificationsMock()
     class CycleAnalysisMock:
         @staticmethod
         def determine_main_cycle_phase_df(df): return {'phase': 'N/A'}
         @staticmethod
         def determine_short_cycle_phase_df(df): return {'phase': 'N/A'}
     cycle_analysis = CycleAnalysisMock()

# --- Константы и Настройки ---
MIN_PRICE_CHANGE_FOR_VOLATILITY = 0.001
LOW_PRICE_PROFIT_REASON = "Низкая цена + Профит"

# --- Функции расчета TA ---
def calculate_rsi(close_prices, period):
    if ta_lib is None: return None
    try:
        rsi_indicator = ta_lib.momentum.RSIIndicator(close=close_prices, window=period)
        rsi = rsi_indicator.rsi()
        return rsi.iloc[-1] if rsi is not None and not rsi.empty and pd.notna(rsi.iloc[-1]) else None
    except Exception as e: logger.error(f"Ошибка RSI: {e}"); return None

def calculate_macd(close_prices, fast, slow, signal):
    if ta_lib is None: return None, None, None
    try:
        macd_indicator = ta_lib.trend.MACD(close=close_prices, window_fast=fast, window_slow=slow, window_sign=signal)
        line=macd_indicator.macd(); sig=macd_indicator.macd_signal(); hist=macd_indicator.macd_diff()
        if line is not None and not line.empty and sig is not None and not sig.empty and hist is not None and not hist.empty:
            line_val = line.iloc[-1]; sig_val = sig.iloc[-1]; hist_val = hist.iloc[-1]
            if pd.notna(line_val) and pd.notna(sig_val) and pd.notna(hist_val):
                return line_val, sig_val, hist_val
            else: return None, None, None
        else:
            return None, None, None
    except Exception as e: logger.error(f"Ошибка MACD: {e}"); return None, None, None

def calculate_sma(close_prices, period):
    if ta_lib is None: return None
    try:
        sma_indicator = ta_lib.trend.SMAIndicator(close=close_prices, window=period)
        sma = sma_indicator.sma_indicator()
        return sma.iloc[-1] if sma is not None and not sma.empty and pd.notna(sma.iloc[-1]) else None
    except Exception as e: logger.error(f"Ошибка SMA: {e}"); return None

def calculate_bollinger_bands(close_prices, period, std_dev):
    if ta_lib is None: return None, None, None
    try:
        bb_indicator = ta_lib.volatility.BollingerBands(close=close_prices, window=period, window_dev=std_dev)
        h=bb_indicator.bollinger_hband(); l=bb_indicator.bollinger_lband(); m=bb_indicator.bollinger_mavg()
        if h is not None and not h.empty and l is not None and not l.empty and m is not None and not m.empty:
            h_val = h.iloc[-1]; l_val = l.iloc[-1]; m_val = m.iloc[-1]
            # Возвращаем NaN как есть
            return h_val, m_val, l_val
        else:
            return None, None, None
    except Exception as e: logger.error(f"Ошибка BB: {e}"); return None, None, None

# --- Функция генерации Резюме ---
def _generate_signal_summary(signal, confidence, score, reasons, details):
    logger.debug(f"Генерация резюме: {signal} ({confidence}), Score: {score:.2f}")
    summary_lines = []; outcome_parts = []; key_factors = []

    try:
        # 1. Итог
        signal_emoji = "⚪️";
        if signal == 'BUY': signal_emoji = "🟢" if confidence == 'Strong' else "🟩"
        elif signal == 'SELL': signal_emoji = "🔴" if confidence == 'Strong' else "🟥"
        outcome_parts.append(f"{signal_emoji} *{signal}* ({confidence}, Score: {score:.2f})")
        main_cycle_data = details.get('main_cycle', {}); short_cycle_data = details.get('short_cycle', {})
        main_phase = main_cycle_data.get('phase', 'N/A') if isinstance(main_cycle_data, dict) else 'Error'
        short_phase = short_cycle_data.get('phase', 'N/A') if isinstance(short_cycle_data, dict) else 'Error'
        if main_phase not in ['N/A', 'Error']: outcome_parts.append(f"ОснЦ:{main_phase}");
        elif isinstance(main_cycle_data, dict) and main_cycle_data.get('error'): outcome_parts.append(f"ОснЦ:Ошибка")
        if short_phase not in ['N/A', 'Error']: outcome_parts.append(f"КорЦ:{short_phase}");
        elif isinstance(short_cycle_data, dict) and short_cycle_data.get('error'): outcome_parts.append(f"КорЦ:Ошибка")
        summary_lines.append("*Итог:* " + " | ".join(outcome_parts))

        # 2. Почему
        current_reasons = []
        if signal == 'BUY': current_reasons = reasons.get('BUY', [])
        elif signal == 'SELL': current_reasons = reasons.get('SELL', [])
        elif signal == 'HOLD': current_reasons = reasons.get('HOLD', [])
        if signal == 'HOLD':
            if main_phase not in ['N/A', 'Error'] and f"ОснЦ:{main_phase}" not in current_reasons: current_reasons.append(f"ОснЦ:{main_phase}")
            if short_phase not in ['N/A', 'Error'] and f"КорЦ:{short_phase}" not in current_reasons: current_reasons.append(f"КорЦ:{short_phase}")
        unique_why = []; [unique_why.append(str(r)) for r in current_reasons if r is not None and str(r) not in unique_why]
        why_str = ", ".join(unique_why) if unique_why else "Нет явных причин."
        summary_lines.append(f"*Почему:* {why_str}")

        # 3. Ключи
        buy_reasons_list = reasons.get('BUY', [])
        if LOW_PRICE_PROFIT_REASON in buy_reasons_list:
            key_factors.append(f"💰 {LOW_PRICE_PROFIT_REASON}")
        if main_phase not in ['N/A', 'Error']: key_factors.append(f"ОснЦ:{main_phase}")
        if short_phase not in ['N/A', 'Error']: key_factors.append(f"КорЦ:{short_phase}")
        if signal == 'BUY':
            buy_key_reasons = list(str(r) for r in buy_reasons_list if r is not None and ('ATL' in str(r) or 'BB' in str(r) or 'RSI' in str(r)))
            key_factors.extend(buy_key_reasons[:1])
        elif signal == 'SELL':
            sell_reasons_list = reasons.get('SELL', [])
            sell_key_reasons = list(str(r) for r in sell_reasons_list if r is not None and ('ATH' in str(r) or 'BB' in str(r) or 'RSI' in str(r)))
            key_factors.extend(sell_key_reasons[:1])
        sma_buy_reason = f"SMA{config.SMA_SHORT_PERIOD}>SMA{config.SMA_LONG_PERIOD}"; sma_sell_reason = f"SMA{config.SMA_SHORT_PERIOD}<SMA{config.SMA_LONG_PERIOD}"
        if sma_buy_reason in [str(r) for r in buy_reasons_list if r is not None]:
            key_factors.append("SMA Cross BUY")
        elif sma_sell_reason in [str(r) for r in reasons.get('SELL', []) if r is not None]:
            key_factors.append("SMA Cross SELL")
        if not key_factors and signal != 'HOLD': key_factors.append(f"Сигнал: {signal}")
        elif not key_factors and signal == 'HOLD': key_factors.append("Нейтрально")
        unique_keys = []; [unique_keys.append(k) for k in key_factors if k not in unique_keys]; keys_str = ", ".join(unique_keys[:3])
        if len(unique_keys) > 3: keys_str += "..."
        if not keys_str: keys_str = "Нет явных ключей."
        summary_lines.append(f"*Ключи:* {keys_str}")

        final_summary = "\n".join(summary_lines);
        logger.debug(f"Сгенерировано резюме:\n{final_summary}")
        return final_summary
    except Exception as e_gen_sum:
        logger.error(f"Ошибка внутри _generate_signal_summary: {e_gen_sum}", exc_info=True)
        return "*Ошибка генерации резюме.*"

# --- Основная функция проверки сигналов ---
def check_signals(history_df, player_config, latest_parsed_data=None, last_notification_state=None):
    player_name = player_config.get('name', 'Unknown_Signal')
    logger.debug(f"[{player_name}] Запуск check_signals. Config: {player_config}, Parsed: {'Есть' if latest_parsed_data else 'Нет'}")
    signals_log = {'player': player_name, 'timestamp': datetime.now(timezone.utc).isoformat(), 'aggregated_score': 0.0, 'signal': 'HOLD', 'confidence': 'Low', 'send_notification': False, 'reasons': {'BUY': [], 'SELL': [], 'HOLD': []}, 'details': {}, 'error': None, 'final_summary_text': 'Резюме не сгенерировано.'}
    aggregated_score = 0.0; reasons = {'BUY': [], 'SELL': [], 'HOLD': []}; signal_details = {}; df_ta = None; current_price = None; ath = None; atl = None
    bb_h_num, bb_m_num, bb_l_num = None, None, None

    last_state = last_notification_state.get(player_name, {}) if last_notification_state else {}
    last_sent_score = last_state.get('score')
    logger.debug(f"[{player_name}] Последний отправленный score: {last_sent_score}")

    # --- 1. Подготовка данных ---
    try:
        if latest_parsed_data and isinstance(latest_parsed_data, dict):
            price_raw = latest_parsed_data.get('price')
            if price_raw is not None:
                try: current_price = int(float(price_raw)); signal_details['current_price'] = storage.format_price(current_price); logger.debug(f"[{player_name}] Текущая цена из парсера: {signal_details['current_price']}")
                except (ValueError, TypeError): logger.warning(f"[{player_name}] Не конвертировать 'price': '{price_raw}'."); current_price = None; signal_details['current_price'] = "N/A"
            else: logger.info(f"[{player_name}] Цена ('price') отсутствует в parsed_data."); signal_details['current_price'] = "N/A"
            signal_details['change'] = latest_parsed_data.get('change', None); signal_details['min_order'] = latest_parsed_data.get('min_order'); signal_details['max_order'] = latest_parsed_data.get('max_order'); ts_raw = latest_parsed_data.get('timestamp')
            if ts_raw:
                try: signal_details['last_update_time'] = datetime.fromisoformat(ts_raw).strftime('%Y-%m-%d %H:%M:%S %Z')
                except: logger.warning(f"[{player_name}] Не распарсить timestamp: {ts_raw}")
        else: logger.warning(f"[{player_name}] latest_parsed_data не предоставлены."); signal_details.update({'current_price': "N/A", 'change': None, 'min_order': None, 'max_order': None})
        if history_df is None or history_df.empty: raise ValueError("Пустой DataFrame истории.")
        df_ta = history_df.copy().reset_index()
        if 'datetime' in df_ta.columns: df_ta.rename(columns={'datetime': 'timestamp'}, inplace=True)
        elif pd.api.types.is_datetime64_any_dtype(df_ta.iloc[:, 0]): df_ta.rename(columns={df_ta.columns[0]: 'timestamp'}, inplace=True)
        if 'timestamp' not in df_ta.columns: raise ValueError("Нет колонки 'timestamp' для TA.")
        if not pd.api.types.is_datetime64_any_dtype(df_ta['timestamp']): df_ta['timestamp'] = pd.to_datetime(df_ta['timestamp'], errors='coerce'); df_ta.dropna(subset=['timestamp'], inplace=True)
        if df_ta['timestamp'].dt.tz is None: df_ta['timestamp'] = df_ta['timestamp'].dt.tz_localize('UTC')
        else: df_ta['timestamp'] = df_ta['timestamp'].dt.tz_convert('UTC')
        rename_map = {'Цена': 'close', 'Мин. цена': 'low', 'Макс. цена': 'high'}; orig_cols = list(rename_map.keys())
        if not all(c in df_ta.columns for c in orig_cols): raise ValueError(f"Нет колонок для TA: {[c for c in orig_cols if c not in df_ta.columns]}")
        df_ta.rename(columns=rename_map, inplace=True); df_ta['open'] = df_ta['close'].shift(1); df_ta['open'] = df_ta['open'].fillna(df_ta['close'])
        req_ta_cols = ['timestamp', 'open', 'high', 'low', 'close'];
        if not all(c in df_ta.columns for c in req_ta_cols): raise ValueError(f"Нет колонок TA: {[c for c in req_ta_cols if c not in df_ta.columns]}")
        df_ta.dropna(subset=req_ta_cols, inplace=True)
        if df_ta.empty: raise ValueError("DF пуст после подготовки.")
        logger.debug(f"[{player_name}] DF для TA готов, строк: {len(df_ta)}")
        if current_price is None and not df_ta.empty:
            last_hist_price = df_ta['close'].iloc[-1]
            if pd.notna(last_hist_price): current_price = int(last_hist_price); signal_details['current_price'] = storage.format_price(current_price) + " (H)"; logger.warning(f"[{player_name}] Цена N/A, используется последняя из истории: {signal_details['current_price']}")
            else: logger.warning(f"[{player_name}] Последняя цена в истории N/A."); signal_details['current_price'] = "N/A"
        if 'last_update_time' not in signal_details and not df_ta.empty: signal_details['last_update_time'] = df_ta['timestamp'].iloc[-1].strftime('%Y-%m-%d %H:%M:%S %Z')
    except Exception as e_prep:
        logger.error(f"Ошибка подготовки данных ({player_name}): {e_prep}", exc_info=True); signals_log['error'] = f"Ошибка данных: {e_prep}"
        signals_log['details'].update({'current_price': "Error", 'change': None, 'min_order': None, 'max_order': None, 'last_update_time': 'N/A', 'rsi': 'N/A', 'macd': 'N/A', 'sma': 'N/A', 'bollinger': 'N/A', 'main_cycle': {'phase':'N/A'}, 'short_cycle': {'phase':'N/A'}, 'ath': 'N/A', 'atl': 'N/A', 'low_price_zone': False})
        signals_log['final_summary_text'] = "*Ошибка подготовки данных, анализ невозможен.*"; logger.info(f"[{player_name}] Итог: Ошибка подготовки данных."); return signals_log, last_notification_state

    # --- 2. Расчет TA ---
    ta_available = False
    if df_ta is not None and not df_ta.empty:
        try:
            logger.debug(f"[{player_name}] Расчет TA... Score={aggregated_score:.2f}"); ta_start = time.time()
            rsi_val = calculate_rsi(df_ta['close'], config.RSI_PERIOD); signal_details['rsi'] = f"{rsi_val:.2f}" if pd.notna(rsi_val) else "N/A"
            if pd.notna(rsi_val):
                rsi_oversold_weight = getattr(config, 'RSI_OVERSOLD_WEIGHT', 1.0); rsi_overbought_weight = getattr(config, 'RSI_OVERBOUGHT_WEIGHT', -1.0)
                if rsi_val < config.RSI_OVERSOLD: reason = f"RSI<{config.RSI_OVERSOLD}({rsi_val:.1f})"; aggregated_score += rsi_oversold_weight; reasons['BUY'].append(reason); logger.debug(f"[{player_name}] Score {aggregated_score:+.2f} (RSI Oversold: +{rsi_oversold_weight:.2f})")
                elif rsi_val > config.RSI_OVERBOUGHT: reason = f"RSI>{config.RSI_OVERBOUGHT}({rsi_val:.1f})"; aggregated_score += rsi_overbought_weight; reasons['SELL'].append(reason); logger.debug(f"[{player_name}] Score {aggregated_score:+.2f} (RSI Overbought: {rsi_overbought_weight:.2f})")

            macd_line, signal_line, macd_hist = calculate_macd(df_ta['close'], config.MACD_FAST_PERIOD, config.MACD_SLOW_PERIOD, config.MACD_SIGNAL_PERIOD); signal_details['macd'] = f"L:{macd_line:.1f},S:{signal_line:.1f},H:{macd_hist:.1f}" if pd.notna(macd_line) and pd.notna(signal_line) and pd.notna(macd_hist) else "N/A"
            if pd.notna(macd_line) and pd.notna(signal_line) and pd.notna(macd_hist):
                prev_macd_hist = 0;
                if len(df_ta) > 1:
                    try:
                        prev_macd_line, prev_signal_line, prev_macd_hist_val = calculate_macd(df_ta['close'].iloc[:-1], config.MACD_FAST_PERIOD, config.MACD_SLOW_PERIOD, config.MACD_SIGNAL_PERIOD);
                        if pd.notna(prev_macd_hist_val):
                            prev_macd_hist = prev_macd_hist_val
                    except Exception as e_macd_prev:
                        logger.warning(f"[{player_name}] Не получить пред. MACD hist: {e_macd_prev}")
                macd_cross_buy_w = getattr(config, 'MACD_BULLISH_CROSS_WEIGHT', 1.2); macd_cross_sell_w = getattr(config, 'MACD_BEARISH_CROSS_WEIGHT', -1.2)
                macd_hist_pos_w = getattr(config, 'MACD_HIST_POSITIVE_WEIGHT', 0.3); macd_hist_neg_w = getattr(config, 'MACD_HIST_NEGATIVE_WEIGHT', -0.3)
                if macd_hist > 0 and prev_macd_hist <= 0: reason = "MACD Cross"; aggregated_score += macd_cross_buy_w; reasons['BUY'].append(reason); logger.debug(f"[{player_name}] Score {aggregated_score:+.2f} (MACD Bull Cross: +{macd_cross_buy_w:.2f})")
                elif macd_hist < 0 and prev_macd_hist >= 0: reason = "MACD Cross"; aggregated_score += macd_cross_sell_w; reasons['SELL'].append(reason); logger.debug(f"[{player_name}] Score {aggregated_score:+.2f} (MACD Bear Cross: {macd_cross_sell_w:.2f})")
                if macd_hist > 0: aggregated_score += macd_hist_pos_w; logger.debug(f"[{player_name}] Score {aggregated_score:+.2f} (MACD Hist > 0: +{macd_hist_pos_w:.2f})")
                elif macd_hist < 0: aggregated_score += macd_hist_neg_w; logger.debug(f"[{player_name}] Score {aggregated_score:+.2f} (MACD Hist < 0: {macd_hist_neg_w:.2f})")

            sma_short = calculate_sma(df_ta['close'], config.SMA_SHORT_PERIOD); sma_long = calculate_sma(df_ta['close'], config.SMA_LONG_PERIOD); signal_details['sma'] = f"S:{storage.format_price(sma_short)},L:{storage.format_price(sma_long)}" if pd.notna(sma_short) and pd.notna(sma_long) else "N/A"
            if pd.notna(sma_short) and pd.notna(sma_long):
                sma_buy_reason = f"SMA{config.SMA_SHORT_PERIOD}>SMA{config.SMA_LONG_PERIOD}"; sma_sell_reason = f"SMA{config.SMA_SHORT_PERIOD}<SMA{config.SMA_LONG_PERIOD}"
                sma_buy_w = getattr(config, 'SMA_FAST_ABOVE_SLOW_WEIGHT', 1.5); sma_sell_w = getattr(config, 'SMA_SLOW_ABOVE_FAST_WEIGHT', -1.5)
                if sma_short > sma_long: aggregated_score += sma_buy_w; reasons['BUY'].append(sma_buy_reason); logger.debug(f"[{player_name}] Score {aggregated_score:+.2f} (SMA Buy Cross: +{sma_buy_w:.2f})")
                else: aggregated_score += sma_sell_w; reasons['SELL'].append(sma_sell_reason); logger.debug(f"[{player_name}] Score {aggregated_score:+.2f} (SMA Sell Cross: {sma_sell_w:.2f})")

            # Расчет BB и сохранение числовых значений
            bb_h, bb_m, bb_l = calculate_bollinger_bands(df_ta['close'], config.BOLLINGER_PERIOD, config.BOLLINGER_STD_DEV)
            bb_h_num, bb_m_num, bb_l_num = None, None, None # Сбрасываем перед проверкой
            if pd.notna(bb_h) and pd.notna(bb_l): # Достаточно H и L
                bb_h_num = bb_h; bb_l_num = bb_l
                signal_details['bb_h_val'] = bb_h_num
                signal_details['bb_l_val'] = bb_l_num
                if pd.notna(bb_m): bb_m_num = bb_m; signal_details['bb_m_val'] = bb_m_num
                else: signal_details['bb_m_val'] = None # Явно None, если m невалиден
                # Формируем строку BB даже если M=NaN
                signal_details['bollinger'] = f"L:{storage.format_price(bb_l_num)},M:{storage.format_price(bb_m_num)},H:{storage.format_price(bb_h_num)}"
            else:
                signal_details['bollinger'] = "N/A"
                signal_details['bb_h_val'] = None
                signal_details['bb_m_val'] = None
                signal_details['bb_l_val'] = None

            # Логика пробоя BB
            if bb_h_num is not None and bb_l_num is not None and current_price is not None:
                bb_buy_reason = f"Цена<BB({storage.format_price(current_price)}<{storage.format_price(bb_l_num)})"; bb_sell_reason = f"Цена>BB({storage.format_price(current_price)}>{storage.format_price(bb_h_num)})"
                bb_buy_w = getattr(config, 'BOLLINGER_LOWER_BREAK_WEIGHT', 1.5); bb_sell_w = getattr(config, 'BOLLINGER_UPPER_BREAK_WEIGHT', -1.5)
                if current_price > bb_h_num: aggregated_score += bb_sell_w; reasons['SELL'].append(bb_sell_reason); logger.debug(f"[{player_name}] Score {aggregated_score:+.2f} (BB Upper Break: {bb_sell_w:.2f})")
                elif current_price < bb_l_num: aggregated_score += bb_buy_w; reasons['BUY'].append(bb_buy_reason); logger.debug(f"[{player_name}] Score {aggregated_score:+.2f} (BB Lower Break: +{bb_buy_w:.2f})")

            ta_available = True; logger.debug(f"[{player_name}] Расчет TA: {time.time() - ta_start:.3f}s. Score после TA: {aggregated_score:.2f}")
        except Exception as e_ta: logger.error(f"Ошибка TA {player_name}: {e_ta}", exc_info=True); signals_log['error'] = f"Ошибка TA: {e_ta}"; signal_details.update({'rsi': "Error", 'macd': "Error", 'sma': "Error", 'bollinger': "Error"}); ta_available = False
    else: logger.warning(f"TA пропущены {player_name}."); signal_details.update({'rsi': "N/A", 'macd': "N/A", 'sma': "N/A", 'bollinger': "N/A"})

    # --- 3. Анализ циклов ---
    cycle_possible = history_df is not None and not history_df.empty and isinstance(history_df.index, pd.DatetimeIndex)
    if not cycle_possible: logger.warning(f"[{player_name}] Анализ циклов пропущен."); signal_details['main_cycle']={'phase':'N/A', 'error': 'Input df invalid'}; signal_details['short_cycle']={'phase':'N/A', 'error': 'Input df invalid'}
    else:
        main_phase='N/A'; short_phase='N/A'; main_details={}; short_details={}
        try:
            cycle_start = time.time(); logger.debug(f"[{player_name}] Запуск анализа циклов... Score={aggregated_score:.2f}")
            main_phase_data = cycle_analysis.determine_main_cycle_phase_df(history_df.copy()); short_phase_data = cycle_analysis.determine_short_cycle_phase_df(history_df.copy());
            logger.debug(f"[{player_name}] Результат Осн.Цикла: {main_phase_data}"); logger.debug(f"[{player_name}] Результат Кор.Цикла: {short_phase_data}")
            if isinstance(main_phase_data, dict):
                main_phase = main_phase_data.get('phase', 'Error'); main_details = main_phase_data;
                if main_phase not in ['N/A', 'Error']: weight_name = f"MAIN_CYCLE_{main_phase.upper()}_WEIGHT"; weight = getattr(config, weight_name, 0); aggregated_score += weight; reasons['HOLD'].append(f"ОснЦ:{main_phase}"); logger.debug(f"[{player_name}] Score {aggregated_score:+.2f} (ОснЦ:{main_phase}: {weight:+.2f})")
                elif main_phase == 'Error': logger.warning(f"[{player_name}] Ошибка Осн. Цикла: {main_details.get('error')}")
            else: logger.error(f"[{player_name}] Некорректный тип Осн.Цикла: {type(main_phase_data)}"); main_phase = "Error"; main_details = {'phase': 'Error', 'error': 'Invalid return type'}
            if isinstance(short_phase_data, dict):
                short_phase = short_phase_data.get('phase', 'Error'); short_details = short_phase_data;
                if short_phase not in ['N/A', 'Error']: weight_name = f"SHORT_CYCLE_{short_phase.upper()}_WEIGHT"; weight = getattr(config, weight_name, 0); aggregated_score += weight; reasons['HOLD'].append(f"КорЦ:{short_phase}"); logger.debug(f"[{player_name}] Score {aggregated_score:+.2f} (КорЦ:{short_phase}: {weight:+.2f})")
                elif short_phase == 'Error': logger.warning(f"[{player_name}] Ошибка Кор. Цикла: {short_details.get('error')}")
            else: logger.error(f"[{player_name}] Некорректный тип Кор.Цикла: {type(short_phase_data)}"); short_phase = "Error"; short_details = {'phase': 'Error', 'error': 'Invalid return type'}
            signal_details['main_cycle'] = main_details; signal_details['short_cycle'] = short_details; logger.debug(f"[{player_name}] Циклы: {time.time() - cycle_start:.3f}с. Фазы: Осн={main_phase}, Кор={short_phase}. Score после циклов: {aggregated_score:.2f}")
        except Exception as e_cycle:
            logger.error(f"Критическая ошибка анализа циклов {player_name}: {e_cycle}", exc_info=True)
            signal_details['main_cycle'] = {'phase': 'Error', 'error': str(e_cycle)}
            signal_details['short_cycle'] = {'phase': 'Error', 'error': str(e_cycle)};
            if not signals_log['error']:
                signals_log['error'] = f"Ошибка циклов: {e_cycle}"

    # --- 4. Контекст и ATH/ATL ---
    try:
        if history_df is not None and not history_df.empty:
            ath = history_df['Цена'].max(); atl = history_df['Цена'].min(); logger.debug(f"[{player_name}] ATH/ATL Детали: ath={ath} ({type(ath)}), atl={atl} ({type(atl)})")
            signal_details['ath'] = storage.format_price(ath) if pd.notna(ath) else "N/A"; signal_details['atl'] = storage.format_price(atl) if pd.notna(atl) else "N/A"
            price_to_compare = current_price; min_order_price = signal_details.get('min_order')
            if price_to_compare is None and min_order_price is not None: price_to_compare = min_order_price; logger.info(f"[{player_name}] Цена N/A, используем Min ордер ({storage.format_price(price_to_compare)}) для сравнения ATH/ATL.")
            elif price_to_compare is None: logger.warning(f"[{player_name}] Цена для сравнения ATH/ATL недоступна.")
            if price_to_compare is not None and pd.notna(ath) and pd.notna(atl):
                price_range = ath - atl
                if price_range > 0:
                    logger.debug(f"[{player_name}] ATH/ATL Причины: price={price_to_compare}, ath={ath}, atl={atl}, range={price_range}")
                    ath_str = storage.format_price(ath); atl_str = storage.format_price(atl); ath_reason = f"Близко к ATH ({ath_str})"; atl_reason = f"Близко к ATL ({atl_str})"
                    ath_weight = getattr(config, 'ATH_WEIGHT', -2.0); atl_weight = getattr(config, 'ATL_WEIGHT', 2.0)
                    if (ath - price_to_compare) / price_range < 0.05: aggregated_score += ath_weight; reasons['SELL'].append(ath_reason); logger.debug(f"[{player_name}] Score {aggregated_score:+.2f} (Близко к ATH: {ath_weight:.2f})")
                    if (price_to_compare - atl) / price_range < 0.05: aggregated_score += atl_weight; reasons['BUY'].append(atl_reason); logger.debug(f"[{player_name}] Score {aggregated_score:+.2f} (Близко к ATL: +{atl_weight:.2f})")
                elif price_range == 0: logger.debug(f"[{player_name}] Нулевой price_range.")
                else: logger.warning(f"[{player_name}] Отрицательный price_range ({price_range}).")
            else: logger.debug(f"[{player_name}] Недостаточно данных для сравнения ATH/ATL.")
        else: logger.warning(f"[{player_name}] Пропуск ATH/ATL: нет history_df."); signal_details.update({'ath': "N/A", 'atl': "N/A"})
    except Exception as e_context:
        logger.error(f"Ошибка ATH/ATL {player_name}: {e_context}", exc_info=True)
        signal_details.update({'ath': "Error", 'atl': "Error"});
        if not signals_log['error']:
            signals_log['error'] = f"Ошибка ATH/ATL: {e_context}"

    # --- 5. Сигнал Низкой Цены ---
    is_low_price_zone = False
    try:
        if current_price is not None:
            low_price_threshold = getattr(config, 'LOW_PRICE_THRESHOLD', 15500000)
            if current_price <= low_price_threshold:
                is_low_price_zone = True; low_price_formatted = storage.format_price(low_price_threshold)
                logger.info(f"[{player_name}] Цена ({storage.format_price(current_price)}) <= порогу ({low_price_formatted}).")
                low_price_reason = f"Низкая цена (<={low_price_formatted})"
                if low_price_reason not in reasons['HOLD']: reasons['HOLD'].append(low_price_reason)
                if pd.notna(ath):
                    commission_rate = getattr(config, 'PROFIT_COMMISSION_RATE', 0.10); profit_weight = getattr(config, 'LOW_PRICE_PROFIT_WEIGHT', 5.0)
                    potential_sale_price = ath * (1 - commission_rate)
                    logger.debug(f"[{player_name}] Проверка профита: ATH={storage.format_price(ath)}, SalePrice~{storage.format_price(potential_sale_price)}, Current={storage.format_price(current_price)}")
                    if potential_sale_price > current_price:
                        logger.info(f"[{player_name}] Низкая цена + Профит! Добавляем вес: +{profit_weight}")
                        aggregated_score += profit_weight; logger.debug(f"[{player_name}] Score {aggregated_score:+.2f} (Low Price Profit: +{profit_weight:.2f})")
                        if LOW_PRICE_PROFIT_REASON not in reasons['BUY']: reasons['BUY'].append(LOW_PRICE_PROFIT_REASON)
                        if low_price_reason in reasons['HOLD']:
                            try: reasons['HOLD'].remove(low_price_reason)
                            except ValueError: pass
                    else: logger.info(f"[{player_name}] Низкая цена, но профит не обнаружен.")
                else: logger.warning(f"[{player_name}] Низкая цена, но ATH невалиден. Проверка профита невозможна.")
            else: logger.debug(f"[{player_name}] Цена ({storage.format_price(current_price)}) > порога низкой цены.")
        else: logger.warning(f"[{player_name}] Пропуск проверки низкой цены: цена не определена.")
    except Exception as e_low_price:
        logger.error(f"Ошибка сигнала низкой цены {player_name}: {e_low_price}", exc_info=True)
        if not signals_log['error']:
            signals_log['error'] = f"Ошибка LPP: {e_low_price}"
    finally:
        signal_details['low_price_zone'] = is_low_price_zone

    # --- 6. Финальное Определение Сигнала ---
    signals_log['aggregated_score'] = round(aggregated_score, 2)
    logger.debug(f"[{player_name}] Финальный расчетный score перед округлением: {aggregated_score:.4f}")
    buy_strong = getattr(config, 'BUY_THRESHOLD_STRONG', 4.5); buy_medium = getattr(config, 'BUY_THRESHOLD_MEDIUM', 3.0); sell_strong = getattr(config, 'SELL_THRESHOLD_STRONG', -4.5); sell_medium = getattr(config, 'SELL_THRESHOLD_MEDIUM', -3.0)
    current_signal = 'HOLD'; current_confidence = 'Low'
    if signals_log['aggregated_score'] >= buy_strong: current_signal = 'BUY'; current_confidence = 'Strong'
    elif signals_log['aggregated_score'] >= buy_medium: current_signal = 'BUY'; current_confidence = 'Medium'
    elif signals_log['aggregated_score'] <= sell_strong: current_signal = 'SELL'; current_confidence = 'Strong'
    elif signals_log['aggregated_score'] <= sell_medium: current_signal = 'SELL'; current_confidence = 'Medium'
    signals_log.update({'signal': current_signal, 'confidence': current_confidence})

    # --- 7. Генерация Резюме ---
    try:
        final_summary_text = _generate_signal_summary(signals_log['signal'], signals_log['confidence'], signals_log['aggregated_score'], reasons, signal_details)
        signals_log['final_summary_text'] = final_summary_text
    except Exception as e_summary:
        logger.error(f"Ошибка генерации резюме {player_name}: {e_summary}", exc_info=True);
        signals_log['final_summary_text'] = "*Ошибка генерации резюме.*";
        if not signals_log['error']:
            signals_log['error'] = f"Ошибка резюме: {e_summary}"

    # --- 8. Решение об отправке уведомления ---
    send_notification = False
    min_score_change = getattr(config, 'MIN_SCORE_CHANGE_FOR_NOTIFICATION', 0.5)
    send_hold_on_change = getattr(config, 'SEND_HOLD_IF_SCORE_CHANGED', True)
    current_score = signals_log['aggregated_score']
    if signals_log['signal'] != 'HOLD':
        send_notification = True; logger.debug(f"[{player_name}] Решение: Отправить (сигнал {signals_log['signal']})")
    elif send_hold_on_change:
        if last_sent_score is None:
            send_notification = True; logger.debug(f"[{player_name}] Решение: Отправить (первое HOLD уведомление)")
        elif last_sent_score is not None and not math.isclose(current_score, last_sent_score, abs_tol=min_score_change):
            send_notification = True; logger.debug(f"[{player_name}] Решение: Отправить (HOLD score изменился: {last_sent_score} -> {current_score})")
        else:
            logger.debug(f"[{player_name}] Решение: Не отправлять (HOLD score не изменился: {last_sent_score} -> {current_score})")
    else:
        logger.debug(f"[{player_name}] Решение: Не отправлять (HOLD, отправка HOLD отключена)")
    signals_log['send_notification'] = send_notification

    # --- 9. Завершение ---
    signals_log['details'] = signal_details
    signals_log['reasons'] = reasons
    logger.info(f"[{player_name}] Итог: Score={signals_log['aggregated_score']:.2f}, Сигнал={signals_log['signal']}({signals_log['confidence']}), Увед={signals_log['send_notification']}")

    updated_state = last_notification_state.copy()
    if send_notification:
        updated_state[player_name] = {'score': current_score, 'timestamp': signals_log['timestamp']}
        logger.debug(f"[{player_name}] Состояние уведомления обновлено: Score={current_score}")
    else:
        if player_name in updated_state:
            logger.debug(f"[{player_name}] Состояние уведомления НЕ обновлено (сохранено старое).")
        else:
            logger.debug(f"[{player_name}] Состояние уведомления НЕ обновлено.")

    return signals_log, updated_state
