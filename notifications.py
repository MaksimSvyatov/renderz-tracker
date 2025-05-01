# # =============================================
# # ФАЙЛ: notifications.py (ВЕРСИЯ v9 - Отображение Stoch, ADX, ROC, SMA28)
# # - ДОБАВЛЕНО: Отображение новых индикаторов в блоке "Сигналы"
# # - Использует значения stoch_k, stoch_d, is_stoch_*, adx, is_adx_*, roc_14, sma28, price_div_sma28
# # - Убраны пробелы между блоками (из v8)
# # - Используется Markdown
# # =============================================
#
# import logging
# import requests
# import config
# from datetime import datetime, timezone
#
# # --- Базовая функция отправки ---
# def send_telegram_message(message_text):
#     # ... (код без изменений) ...
#     try:
#         token = getattr(config, 'TELEGRAM_BOT_TOKEN', None)
#         chat_id = getattr(config, 'TELEGRAM_CHAT_ID', None)
#         if not token or token == "ВАШ_ТЕЛЕГРАМ_БОТ_ТОКЕН": logging.error("[Telegram] Токен бота не установлен."); return False
#         if not chat_id or chat_id == "ВАШ_ТЕЛЕГРАМ_ЧАТ_ID": logging.error("[Telegram] ID чата не установлен."); return False
#         chat_id_str = str(chat_id)
#         url = f"https://api.telegram.org/bot{token}/sendMessage"
#         payload = {'chat_id': chat_id_str, 'text': message_text, 'parse_mode': 'Markdown'}
#         response = requests.post(url, data=payload, timeout=20)
#         response.raise_for_status()
#         logging.info(f"[Telegram] Сообщение успешно отправлено в чат {chat_id_str}")
#         return True
#     except requests.exceptions.Timeout: logging.error("[Telegram] Таймаут при отправке сообщения."); return False
#     except requests.exceptions.HTTPError as e: logging.error(f"[Telegram] HTTP Ошибка: {e.response.status_code} - {e.response.text}"); return False
#     except requests.exceptions.RequestException as e: logging.error(f"[Telegram] Ошибка сети (requests): {e}"); return False
#     except Exception as e: logging.error(f"[Telegram] Неизвестная ошибка при отправке сообщения: {e}", exc_info=True); return False
#
# # --- Функция для базового сообщения ---
# def send_basic_message(player_name, price, change, min_val, max_val):
#     # ... (код без изменений) ...
#     if price is None: logging.warning(f"[send_basic] Цена None для {player_name}."); return
#     price_str = f"{price:,.0f}".replace(",", "\u00A0") if price > 0 else "*Нет в продаже*"
#     change_str = ""
#     if change and change != "0%":
#         try:
#              ch_val = float(change.replace('%','')); ch_sym = "📈" if ch_val > 0 else "📉" if ch_val < 0 else "📊"
#              change_str = f"({ch_sym}{change})"
#         except ValueError: change_str = f"({change})"
#     min_max_str = ""
#     if min_val is not None and max_val is not None and (min_val > 0 or max_val > 0):
#          min_str = f"{min_val:,.0f}".replace(",", "\u00A0"); max_str = f"{max_val:,.0f}".replace(",", "\u00A0")
#          min_max_str = f"\n📉 Мин: {min_str} / 📈 Макс: {max_str}"
#     message = f"ℹ️ *{player_name}*\n🏷️ Цена: {price_str} {change_str}{min_max_str}"
#     message = message.strip(); send_telegram_message(message)
#
# # --- Формирование детального сообщения (v9 - с новыми индикаторами) ---
# def send_combined_message(player_name, price, change, min_val, max_val, next_update_str, signals_data):
#     """Отправляет детальное сообщение с новыми индикаторами."""
#     if price is None: logging.warning(f"[send_combined] Цена None для {player_name}."); return
#     if signals_data is None or not isinstance(signals_data, dict):
#         logging.warning(f"[send_combined] Нет данных сигналов для {player_name}. Отправка базового сообщения.")
#         send_basic_message(player_name, price, change, min_val, max_val); return
#
#     logging.debug(f"Данные для комбинированного сообщения {player_name}: {signals_data}")
#
#     # --- Блок 1: Основная информация ---
#     price_str = f"{price:,.0f}".replace(",", "\u00A0") if price > 0 else "*Нет в продаже*"
#     change_text = "📊 Изм: 0%";
#     if change and change != "0%":
#         try: ch_val = float(change.replace('%','')); ch_sym = "📈" if ch_val > 0 else "📉" if ch_val < 0 else "📊"; change_text = f"{ch_sym} Изм: {change}"
#         except ValueError: change_text = f"📊 Изм: {change}"
#     min_max_str = "";
#     if min_val is not None and max_val is not None and (min_val > 0 or max_val > 0): mn_str=f"{min_val:,.0f}".replace(",","\u00A0"); mx_str=f"{max_val:,.0f}".replace(",","\u00A0"); min_max_str = f"\n📉 Мин: {mn_str} / 📈 Макс: {mx_str}"
#     next_upd_fmt = next_update_str if next_update_str and next_update_str != "N/A" else "N/A"
#     info_block = f"""📊 *{player_name}*
# 🏷️ Цена: {price_str}
# {change_text}{min_max_str}
# ⏱️ След: {next_upd_fmt}"""
#
#     # --- Блок 2: Цикл/События ---
#     cyc_lines = []
#     cyc_day = signals_data.get('days_in_cycle'); cyc_tot = 28
#     cyc_stat = signals_data.get('main_cycle_phase_raw', 'N/A')
#     if cyc_day is not None and cyc_day > 0 and cyc_stat != "N/A" and cyc_stat != "Нет цикла": cyc_lines.append(f"🎉 Осн. Цикл ({cyc_tot}д): {cyc_stat} (День {cyc_day}/{cyc_tot})")
#     act_ev = signals_data.get('other_events', []);
#     if act_ev: cyc_lines.append(f"⚠️ Активные события: {', '.join(act_ev)}")
#     cyc_ev_str = ""
#     if cyc_lines: cyc_ev_str = "\n--- Цикл/События ---\n" + "\n".join(cyc_lines)
#
#     # --- Блок 3: Сигналы ---
#     sig_lines = []
#     # Контекстные сигналы
#     if signals_data.get('exchange_buy_opportunity'): sig_lines.append(f"🟢 *Покупка у порога?* (Цена <= 15M, OVR>=96, признаки дна/разворота)")
#     if signals_data.get('profitable_sell_peak_risk'): profit_val = signals_data.get('net_profit_on_market_sell', 0.0); profit_str = f"{profit_val:,.0f}".replace(",", "\u00A0"); sig_lines.append(f"🔴 *Продажа (Риск пика)?* (Профит ~{profit_str}, признаки максимума)")
#     elif signals_data.get('profitable_hold_potential'): profit_val = signals_data.get('net_profit_on_market_sell', 0.0); profit_str = f"{profit_val:,.0f}".replace(",", "\u00A0"); sig_lines.append(f"🟡 *Держать (Профит есть)?* (Профит ~{profit_str}, есть потенциал роста)")
#
#     # --- НОВЫЕ ИНДИКАТОРЫ ---
#     # Stochastic
#     stoch_k = signals_data.get('stoch_k')
#     stoch_d = signals_data.get('stoch_d')
#     stoch_text = "N/A"
#     if stoch_k is not None and stoch_d is not None:
#         stoch_text = f"%K={stoch_k:.1f}, %D={stoch_d:.1f}"
#         if signals_data.get('is_stoch_oversold'): stoch_text += " (Перепродан!)"
#         elif signals_data.get('is_stoch_overbought'): stoch_text += " (Перекуплен!)"
#     sig_lines.append(f"🧭 Stoch: {stoch_text}")
#
#     # ADX
#     adx = signals_data.get('adx')
#     adx_text = "N/A"
#     if adx is not None:
#         adx_text = f"ADX={adx:.1f}"
#         if signals_data.get('is_adx_trending_up'): adx_text += " (Тренд ВВЕРХ 📈)"
#         elif signals_data.get('is_adx_trending_down'): adx_text += " (Тренд ВНИЗ 📉)"
#         elif signals_data.get('is_adx_no_trend'): adx_text += " (Флэт ↔️)"
#         else: adx_text += " (Сила тренда?)" # Если ADX между порогами
#     sig_lines.append(f"📊 ADX: {adx_text}")
#
#     # ROC
#     roc = signals_data.get('roc_14')
#     roc_text = "N/A"
#     if roc is not None: roc_text = f"{roc:.2f}%"
#     sig_lines.append(f"🚀 ROC(14d): {roc_text}")
#
#     # SMA28
#     sma28 = signals_data.get('sma28')
#     sma28_text = "N/A"
#     if sma28 is not None and sma28 > 0:
#         sma28_f = f"{sma28:,.0f}".replace(",", "\u00A0")
#         price_div_sma28 = signals_data.get('price_div_sma28', 1.0)
#         sma28_slope = signals_data.get('sma28_slope', 0.0)
#         slope_emj = "📈" if sma28_slope > 0 else "📉" if sma28_slope < 0 else "➡️"
#         sma28_text = f"{sma28_f} (Цена/SMA={price_div_sma28:.2f}, Накл={slope_emj})"
#     sig_lines.append(f"🗓️ SMA28: {sma28_text}")
#     # ---------------------------
#
#     # --- Существующие сигналы ---
#     rsi_val = signals_data.get('rsi_value')
#     if signals_data.get('is_rsi_oversold'): sig_lines.append(f"🟢 RSI < 30{f' ({rsi_val:.1f})' if rsi_val is not None else ''}")
#     elif signals_data.get('is_rsi_overbought'): sig_lines.append(f"🔴 RSI > 70{f' ({rsi_val:.1f})' if rsi_val is not None else ''}")
#     else: # Если не экстремальный RSI, просто покажем значение
#         if rsi_val is not None: sig_lines.append(f"⚪️ RSI: {rsi_val:.1f}")
#
#     if signals_data.get('volatility_text'): sig_lines.append(f"🌊 Волатильность: {signals_data['volatility_text']}")
#     if signals_data.get('all_time_extreme'): sig_lines.append(f"🏆 Ист. экстремум: {signals_data['all_time_extreme']}")
#     hist_breaks = signals_data.get('hist_breakouts')
#     if hist_breaks: sig_lines.append("📌 Пробои:"); [sig_lines.append(f"  - {b}") for b in hist_breaks]
#     if signals_data.get('is_two_rises_anytime'): sig_lines.append("⏫ Рост > 2")
#     if signals_data.get('is_start_rise_after_drop'): sig_lines.append("⤴️ Разворот")
#     seasonal_sig = signals_data.get('seasonal_signal','N/A'); ss_emj = "🟢" if "BUY" in seasonal_sig else "🔴" if "SELL" in seasonal_sig else "⚪️"; sig_lines.append(f"{ss_emj} DOW Avg: {seasonal_sig}")
#     range_sig = signals_data.get('dow_range_signal','N/A'); rs_emj = "🟢" if "BUY" in range_sig else "🔴" if "SELL" in range_sig else "⚪️"; sig_lines.append(f"{rs_emj} DOW Range: {range_sig}")
#     dom_sig = signals_data.get('day_of_month_signal','N/A'); dom_emj="🗓️"; sig_lines.append(f"{dom_emj} DOM Avg: {dom_sig}")
#     trend_sig = signals_data.get('trend_10d_signal','N/A'); trend_emj="📈" if "SELL" in trend_sig else "📉" if "BUY" in trend_sig else "💰"; sig_lines.append(f"{trend_emj} 10дн. тренд: {trend_sig}")
#     model_pred=signals_data.get('model_prediction','N/A');
#     if model_pred and model_pred != 'N/A': sig_lines.append(f"🤖 {model_pred}")
#     sig_block_str = ""
#     if sig_lines: sig_block_str = "\n--- Сигналы ---\n" + "\n".join(sig_lines)
#
#     # --- Блок 4: Итог/Рекомендация ---
#     sum_lines = []
#     summary = signals_data.get('final_summary_text')
#     if summary: sum_lines.append(f"Резюме: {summary}")
#     score = signals_data.get('aggregated_score'); rec_txt = signals_data.get('aggregated_text','N/A')
#     rec_emj = "🟢" if "BUY" in rec_txt else "🔴" if "SELL" in rec_txt else "⚪️"
#     # weights = signals_data.get('final_weights_explanation') # Больше не выводим
#     if score is not None: sum_lines.append(f"{rec_emj} *Общий:* Score={score:g} => {rec_txt}")
#     sum_block_str = ""
#     if sum_lines: sum_block_str = "\n--- Итог ---\n" + "\n".join(sum_lines)
#
#     # --- Сборка финального сообщения ---
#     message = f"{info_block}{cyc_ev_str}{sig_block_str}{sum_block_str}"
#     message = message.strip()
#     send_telegram_message(message)
#
# # --- Тестовый блок ---
# if __name__ == "__main__":
#     logging.basicConfig(level=logging.DEBUG, format=log_format)
#     test_player = "Тестовый Игрок 100"
#     test_price = 18_000_000
#     test_signals = {
#         # ... старые сигналы ...
#         "rsi_value": 65.0, "is_rsi_overbought": 0,
#         # --- Новые индикаторы ---
#         "stoch_k": 75.5, "stoch_d": 70.1, "is_stoch_oversold": 0, "is_stoch_overbought": 0,
#         "adx": 30.1, "di_pos": 28.0, "di_neg": 15.0, "is_adx_trending": 1, "is_adx_trending_up": 1, "is_adx_trending_down": 0, "is_adx_no_trend": 0,
#         "roc_14": 5.2, "is_roc_positive": 1, "is_roc_negative": 0,
#         "sma28": 17_500_000.0, "price_div_sma28": 1.03, "is_above_sma28": 1, "sma28_slope": 100000.0,
#         # --- Контекстные ---
#         "profitable_sell_peak_risk": False,
#         "profitable_hold_potential": True,
#         "net_profit_on_market_sell": 16_200_000.0,
#         # --- Итог ---
#         "aggregated_score": 1.8, "aggregated_text": "Weak BUY / HOLD",
#         "final_summary_text": "🟡 Профит уже есть (~16 200 000), но риск пика пока невысок (Weak BUY / HOLD). Можно еще подержать.",
#         "final_weights_explanation": "(Инд. веса активны)"
#     }
#     logging.info("--- Тест send_combined_message (Новые индикаторы) ---")
#     send_combined_message(test_player, test_price, "+1.1%", 17_000_000, 19_000_000, "in 40m", test_signals)
#
# # =============================================
# # ФАЙЛ: notifications.py
# # ВЕРСИЯ: v10.2 (Добавлен import re)
# # - ИСПРАВЛЕНО: NameError: name 're' is not defined в функции escape_md.
# # - БЕЗ ИЗМЕНЕНИЙ: Логика формирования и отправки сообщений.
# # =============================================
# import logging
# import requests
# import time
# import traceback
# from datetime import datetime, timezone
# import numpy as np
# import re # <<< ДОБАВЛЕН ИМПОРТ
#
# import config
# import storage # Ожидается v6.7+
#
# logger = logging.getLogger(__name__)
#
# MAX_RETRIES = 3
# RETRY_DELAY = 5
#
# def format_price(price):
#     """Обертка для storage.format_price для удобства."""
#     if hasattr(storage, 'format_price'):
#         return storage.format_price(price)
#     if price is None: return "N/A"
#     try: return f"{float(price):,.0f}".replace(",", "\u00A0")
#     except (ValueError, TypeError): return str(price)
#
# def send_telegram_message(message: str, parse_mode="Markdown") -> bool:
#     """Отправляет сообщение в Telegram."""
#     # (Код остается как в v10.1)
#     token   = getattr(config, 'TELEGRAM_BOT_TOKEN', None)
#     chat_id = getattr(config, 'TELEGRAM_CHAT_ID', None)
#     if not token or not chat_id: logging.error("[Telegram] Нет токена или chat_id"); return False
#     url = f"https://api.telegram.org/bot{token}/sendMessage"
#     payload = {'chat_id': chat_id, 'text': message, 'disable_web_page_preview': True}
#     if parse_mode: payload['parse_mode'] = parse_mode
#     for attempt in range(1, MAX_RETRIES+1):
#         try:
#             resp = requests.post(url, data=payload, timeout=15)
#             resp.raise_for_status()
#             data = resp.json()
#             if data.get("ok"): logging.info(f"[Telegram] Сообщение отправлено (попытка {attempt})"); return True
#             else:
#                 error_code=data.get('error_code'); description=data.get('description')
#                 logging.error(f"[Telegram] API error: {error_code} - {description} (попытка {attempt}). Payload: {payload}")
#                 if 'parse error' in (description or '').lower() and parse_mode:
#                      logging.warning("[Telegram] Ошибка разметки, пробую без нее...")
#                      payload.pop('parse_mode', None)
#                      resp_plain = requests.post(url, data=payload, timeout=15); resp_plain.raise_for_status()
#                      data_plain = resp_plain.json()
#                      if data_plain.get("ok"): logging.info("[Telegram] Успешно без разметки."); return True
#                      else: logging.error(f"[Telegram] Отправка без разметки не удалась: {data_plain.get('error_code')} - {data_plain.get('description')}"); return False
#         except requests.exceptions.RequestException as e: logging.error(f"[Telegram] Ошибка сети/запроса (попытка {attempt}): {e}")
#         except Exception as e: logging.error(f"[Telegram] Неизвестная ошибка (попытка {attempt}): {e}")
#         if attempt < MAX_RETRIES: logging.info(f"Повтор через {RETRY_DELAY} сек..."); time.sleep(RETRY_DELAY)
#     logging.error("[Telegram] Не удалось отправить сообщение."); return False
#
# def format_error_message(context: str, error_details: str) -> str:
#     """Форматирует сообщение об ошибке для Telegram."""
#     ts = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S %Z')
#     # --- ИСПРАВЛЕНИЕ: Теперь re импортирован ---
#     def escape_md(text):
#         escape_chars = r'_*[]()~`>#+-=|{}.!'
#         return re.sub(f'([{re.escape(escape_chars)}])', r'\\\1', str(text))
#     # -----------------------------------------
#     safe_context = escape_md(context)
#     safe_details = escape_md(str(error_details)[:3500])
#     return (f"‼️ *Ошибка* ‼️\n\n*Контекст:* {safe_context}\n*Время:* {ts}\n\n*Детали:*\n```{safe_details}\n```")
#
# def _format_value(value, precision=2, is_percent=False):
#     """Вспомогательная функция форматирования числовых значений."""
#     # (Код остается как в v10.1)
#     if value is None or not isinstance(value, (int, float, np.number)) or not np.isfinite(value): return "N/A"
#     suffix = "%" if is_percent else ""
#     if precision == 0: return f"{value:,.0f}{suffix}".replace(",", "\u00A0")
#     else: return f"{value:,.{precision}f}{suffix}".replace(",", "\u00A0")
#
# def _create_combined_message(player_name: str, data: dict) -> str:
#     """Создает текст комбинированного сообщения на основе словарей signals_data и current_data."""
#     # (Код остается как в v10.1)
#     price_val = data.get('price', data.get('current_price')); price_str = format_price(price_val)
#     change = data.get('change','N/A'); min_s = format_price(data.get('min_order')); max_s = format_price(data.get('max_order'))
#     refresh = data.get('update_time','N/A'); orders = data.get('orders', f"Min: {min_s} / Max: {max_s}")
#     msg = (f"📊 *{player_name}*\n🏷️ Цена: *{price_str}* ({change})\n📉 Ордера: _{orders}_\n⏱️ Обновление: _{refresh}_\n\n")
#     agg_text = data.get('aggregated_text','N/A'); agg_score = data.get('aggregated_score', 0.0); summary = data.get('final_summary_text', '')
#     rec_emj = "🟢" if "BUY" in agg_text else "🔴" if "SELL" in agg_text else "⚪️"; msg += (f"--- Сигнал ---\n{rec_emj} *{agg_text}* (Score: {agg_score:.2f})\n_{summary}_\n\n")
#     details = []
#     rsi = data.get('rsi_value'); if rsi is not None: details.append(f"RSI(14): {_format_value(rsi)}")
#     stoch_k = data.get('stoch_k'); stoch_d = data.get('stoch_d'); if stoch_k is not None: details.append(f"Stoch({stoch_k:.0f}/{stoch_d:.0f})")
#     macd = data.get('macd_diff'); if macd is not None: details.append(f"MACD D: {_format_value(macd)}")
#     bbp = data.get('bollinger_pband'); if bbp is not None: details.append(f"BB%: {_format_value(bbp*100, 0, True)}")
#     adx=data.get('adx'); di_pos=data.get('di_pos'); di_neg=data.get('di_neg')
#     if adx is not None: adx_str=f"ADX:{adx:.0f}";
#     if data.get('is_adx_trending_up'): adx_str+="📈"; elif data.get('is_adx_trending_down'): adx_str+="📉"; elif data.get('is_adx_no_trend'): adx_str+="💤"; details.append(adx_str)
#     ar_up=data.get('aroon_up'); ar_down=data.get('aroon_down'); ar_osc=data.get('aroon_oscillator')
#     if ar_osc is not None: aroon_str=f"Aroon({ar_up:.0f}▲/{ar_down:.0f}▼)";
#     if data.get('is_aroon_up_strong'): aroon_str+="🔥"; elif data.get('is_aroon_down_strong'): aroon_str+="🧊"; details.append(aroon_str)
#     roc = data.get('roc_14'); if roc is not None: details.append(f"ROC(14): {_format_value(roc, 2, True)}")
#     atr_norm = data.get('atr_14_norm');
#     if atr_norm is not None: atr_str = f"ATR norm: {_format_value(atr_norm, 1, True)}";
#     if data.get('is_atr_high'): atr_str += "❗️"; details.append(atr_str)
#     sma20 = data.get('sma20'); sma28 = data.get('sma28'); sma28_slope = data.get('sma28_slope')
#     if sma20 is not None: details.append(f"SMA20: {format_price(sma20)}")
#     if sma28 is not None: sma28_str = f"SMA28: {format_price(sma28)}";
#     if sma28_slope > 0: sma28_str += "▲"; elif sma28_slope < 0: sma28_str += "▼"; details.append(sma28_str)
#     if details:
#         msg += "--- Индикаторы ---\n"; line = []
#         for i, d in enumerate(details):
#             line.append(d)
#             if len(line) >= 2 or i == len(details) - 1: msg += " | ".join(line) + "\n"; line = []
#         msg += "\n"
#     extremes = []; ath_atl = data.get('all_time_extreme');
#     if ath_atl: extremes.append(f"*{ath_atl}*")
#     breaks = data.get('hist_breakouts', []);
#     if breaks: extremes.extend(breaks)
#     if extremes: msg += "--- Уровни ---\n" + " | ".join(extremes) + "\n\n"
#     season = []; dow_range = data.get('dow_range_signal'); dom_avg = data.get('day_of_month_signal'); trend = data.get('trend_10d_signal')
#     if dow_range and 'NEUTRAL' not in dow_range: season.append(f"DOW Range: {dow_range.split(' ')[0]}")
#     if dom_avg and 'NEUTRAL' not in dom_avg: season.append(f"DOM Avg: {dom_avg.split(' ')[0]}")
#     if trend and 'NEUTRAL' not in trend: season.append(f"Тренд10д: {trend.split(' ')[0]}")
#     if season: msg += "--- Сезон/Тренд ---\n" + " | ".join(season) + "\n\n"
#     vol_text = data.get('volatility_text');
#     if vol_text: msg += f"Волатильность: {vol_text}\n"
#     return msg.strip()
#
#
# def send_combined_notification(player_config: dict,
#                                signals_data: dict,
#                                current_data: dict) -> bool:
#     """Формирует и отправляет комбинированное уведомление."""
#     # (Код остается как в v10.1)
#     name = player_config.get('name','Unknown'); merged = {}; merged.update(current_data); merged.update(signals_data)
#     if 'ovr' not in merged_data: merged_data['ovr'] = player_config.get('ovr', 'N/A')
#     if 'name' not in merged_data: merged_data['name'] = name
#     try: message = _create_combined_message(name, merged_data); return send_telegram_message(message, parse_mode="Markdown")
#     except Exception as e:
#         logging.error(f"[Telegram] Ошибка отправки уведомления для {name}: {e}", exc_info=True)
#         try: error_msg = format_error_message(f"Уведомление для {name}", traceback.format_exc()); send_telegram_message(error_msg, parse_mode="Markdown")
#         except Exception as notify_err: logging.error(f"Не отправить уведомление об ошибке уведомления: {notify_err}")
#         return False
#
# def send_startup_notification(message="🚀 RenderZ Tracker запущен"): send_telegram_message(message, parse_mode=None)
# def send_shutdown_notification(message="🛑 RenderZ Tracker остановлен"): send_telegram_message(message, parse_mode=None)
# def send_telegram_error(message: str): logging.warning(f"Отправка ошибки: {message[:200]}..."); send_telegram_message(f"ОШИБКА:\n{message}", parse_mode=None)
#
# if __name__ == '__main__':
#     logging.basicConfig(level=logging.INFO)
#     test_player_cfg = {'name': 'Test Player', 'ovr': 105}
#     test_signals = {'aggregated_text':'BUY','aggregated_score':1.2,'final_summary_text':'Test OK','send_notification':True,'rsi_value':60,'stoch_k':70,'stoch_d':65}
#     test_current = {'price':12345,'change':'+0.5%','min_order':12000,'max_order':13000,'update_time':'NOW','orders':'Min: 12k / Max: 13k'}
#     logging.info("--- Тест send_combined_notification ---"); send_combined_notification(test_player_cfg, test_signals, test_current)
#     logging.info("--- Тест format_error_message ---");
#     try: 1/0
#     except Exception as e: err_msg = format_error_message("Тест *Символы*", traceback.format_exc()); print(err_msg); send_telegram_message(err_msg, parse_mode="Markdown")

# # =============================================
# # ФАЙЛ: notifications.py (ВЕРСИЯ v10.11 - Robust Getters & Send, Price Format)
# # - ИЗМЕНЕНО: Все обращения к данным сигнала через .get(key, default).
# # - ИЗМЕНЕНО: Отправка сообщения обернута в try...except RequestException.
# # - ИЗМЕНЕНО: Формат строки цены теперь не отображает (%) если нет данных.
# # - Добавлен import requests.
# # - Содержит изменения из v10.10 (использование резюме).
# # =============================================
#
# import logging
# import requests # Добавлен импорт
# from datetime import datetime, timedelta, timezone
# import math # Для проверки math.isnan, если понадобится (лучше pd.notna в signals)
#
# logger = logging.getLogger("notifications")
#
# try:
#     import config
#     TELEGRAM_BOT_TOKEN = config.TELEGRAM_BOT_TOKEN
#     TELEGRAM_CHAT_ID = config.TELEGRAM_CHAT_ID
#     SEND_DETAILED_CYCLE_INFO = config.SEND_DETAILED_CYCLE_INFO
# except ImportError:
#     logger.error("Не удалось импортировать config. Телеграм уведомления не будут работать.")
#     TELEGRAM_BOT_TOKEN = None
#     TELEGRAM_CHAT_ID = None
#     SEND_DETAILED_CYCLE_INFO = False
# except AttributeError:
#      logger.error("Отсутствуют TELEGRAM_BOT_TOKEN или TELEGRAM_CHAT_ID в config. Уведомления не будут работать.")
#      TELEGRAM_BOT_TOKEN = None
#      TELEGRAM_CHAT_ID = None
#      SEND_DETAILED_CYCLE_INFO = False
#
# MAX_MESSAGE_LENGTH = 4096 # Максимальная длина сообщения Telegram
#
# def send_telegram_message(message, is_error=False, is_warning=False, player_name=None):
#     """Отправляет сообщение в Telegram."""
#     if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
#         logger.warning(f"Telegram не настроен. Сообщение не отправлено: {message[:100]}...")
#         return False
#
#     prefix = ""
#     if is_error: prefix = "❌ ОШИБКА: "
#     elif is_warning: prefix = "⚠️ ПРЕДУПРЕЖДЕНИЕ: "
#     if player_name: prefix = f"[{player_name}] {prefix}" # Добавляем имя игрока, если есть
#
#     full_message = f"{prefix}{message}"
#
#     # Обрезка слишком длинных сообщений
#     if len(full_message) > MAX_MESSAGE_LENGTH:
#         logger.warning(f"Сообщение слишком длинное ({len(full_message)} символов). Обрезается до {MAX_MESSAGE_LENGTH}.")
#         full_message = full_message[:MAX_MESSAGE_LENGTH - 3] + "..."
#
#     api_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
#     payload = {
#         'chat_id': TELEGRAM_CHAT_ID,
#         'text': full_message,
#         'parse_mode': 'Markdown' # Используем Markdown для форматирования
#     }
#
#     # --- ИЗМЕНЕНО v10.11: Обертка в try...except ---
#     try:
#         response = requests.post(api_url, json=payload, timeout=10) # Добавлен таймаут
#         response.raise_for_status() # Проверка на HTTP ошибки (4xx, 5xx)
#         logger.info(f"Сообщение успешно отправлено в Telegram: {message[:100]}...")
#         return True
#     except requests.exceptions.RequestException as e:
#         logger.error(f"Ошибка отправки сообщения в Telegram: {e}")
#         return False
#     except Exception as e:
#         logger.error(f"Непредвиденная ошибка при отправке сообщения в Telegram: {e}", exc_info=True)
#         return False
#     # ------------------------------------------
#
# def format_signal_message(signal_data):
#     """Форматирует сообщение о сигнале для Telegram."""
#     # --- ИЗМЕНЕНО v10.11: Используем .get() повсеместно ---
#     player_name = signal_data.get('player', 'Unknown Player')
#     signal = signal_data.get('signal', 'N/A')
#     confidence = signal_data.get('confidence', 'N/A')
#     score = signal_data.get('aggregated_score', 0.0)
#     details = signal_data.get('details', {})
#     reasons_dict = signal_data.get('reasons', {})
#     final_summary = signal_data.get('final_summary_text', '*Резюме не сгенерировано.*') # Используем сгенерированное резюме
#
#     message_lines = []
#
#     # --- Заголовок ---
#     # Используем эмодзи рейтинга из имени игрока, если есть
#     name_parts = player_name.split()
#     rating_emojis = [p for p in name_parts if p.isdigit() or p.isnumeric()] # Пробуем найти числа
#     emoji_header = "📊" # По умолчанию
#     if len(rating_emojis) >= 1:
#         try:
#             # Простой пример - можно усложнить логику эмодзи
#              rate_num = int(rating_emojis[0])
#              if rate_num >= 105: emoji_header = "💎"
#              elif rate_num >= 100: emoji_header = "✨"
#              elif rate_num >= 95: emoji_header = "🔥"
#         except: pass # Игнорируем ошибки конвертации
#     message_lines.append(f"{emoji_header} *{player_name}*") # Выделяем имя жирным
#
#     # --- Основная информация ---
#     price_str = details.get('current_price', 'N/A')
#     # --- ИЗМЕНЕНО v10.11: Условное отображение % change ---
#     change_str = details.get('change', None) # Получаем строку изменения или None
#     update_time_str = details.get('last_update_time', 'N/A')
#     price_line = f"🏷️ Цена: {price_str}"
#     # Добавляем изменение, только если оно есть и не 'N/A'
#     if change_str and change_str != 'N/A':
#         price_line += f" ({change_str})" # Предполагаем, что change_str уже содержит %
#     price_line += f" | ⏱️ Обн: {update_time_str}"
#     message_lines.append(price_line)
#     # -----------------------------------------------------
#
#     min_order = details.get('min_order', 'N/A') # Получаем из details, если передается
#     max_order = details.get('max_order', 'N/A')
#     # Форматируем ордера, если они переданы
#     if min_order != 'N/A' or max_order != 'N/A':
#          # Пытаемся форматировать как числа, если возможно
#          try: min_order_fmt = storage.format_price(int(min_order))
#          except: min_order_fmt = str(min_order)
#          try: max_order_fmt = storage.format_price(int(max_order))
#          except: max_order_fmt = str(max_order)
#          message_lines.append(f"📉 Ордера: Min: {min_order_fmt} / Max: {max_order_fmt}")
#
#
#     message_lines.append("") # Пустая строка для разделения
#
#     # --- Резюме Сигнала (Используем готовое из signals.py) ---
#     message_lines.append(final_summary)
#     message_lines.append("") # Пустая строка
#
#     # --- Детали TA ---
#     rsi_val = details.get('rsi', 'N/A')
#     macd_val = details.get('macd', 'N/A') # Ожидаем строку L:...,S:...,H:...
#     sma_val = details.get('sma', 'N/A') # Ожидаем строку S:...,L:...
#     bb_val = details.get('bollinger', 'N/A') # Ожидаем строку L:...,M:...,H:...
#     # Расчет BB% (пример, логика может быть в signals.py)
#     bb_percent_str = "N/A"
#     if price_str != 'N/A' and price_str != 'N/A (H)' and bb_val != 'N/A' and bb_val != 'Error':
#         try:
#             current_price_num = int(price_str.replace(' ', '').replace('(H)', ''))
#             bb_parts = bb_val.split(',')
#             bb_l_str = bb_parts[0].split(':')[1].replace(' ', '')
#             bb_h_str = bb_parts[2].split(':')[1].replace(' ', '')
#             bb_l_num = int(bb_l_str)
#             bb_h_num = int(bb_h_str)
#             if bb_h_num > bb_l_num:
#                 bb_percent = round((current_price_num - bb_l_num) / (bb_h_num - bb_l_num) * 100)
#                 bb_percent_str = f"{bb_percent}%"
#         except Exception as e_bb:
#             logger.warning(f"Ошибка расчета BB% для уведомления: {e_bb}")
#             bb_percent_str = "Calc Err"
#
#     details_line = f"RSI(14): {rsi_val} | MACD H: {macd_val.split('H:')[1] if 'H:' in macd_val else 'N/A'} | SMA({config.SMA_SHORT_PERIOD}/{config.SMA_LONG_PERIOD}): {sma_val} | BB%: {bb_percent_str}"
#     message_lines.append(details_line)
#     message_lines.append("")
#
#     # --- Детали Циклов (если включено) ---
#     main_cycle_data = details.get('main_cycle', {})
#     short_cycle_data = details.get('short_cycle', {})
#     main_phase = main_cycle_data.get('phase', 'N/A')
#     short_phase = short_cycle_data.get('phase', 'N/A')
#     main_error = main_cycle_data.get('error')
#     short_error = short_cycle_data.get('error')
#
#     cycle_details_lines = []
#     if main_error: cycle_details_lines.append(f"Осн.Цикл: Ошибка ({main_error[:30]}{'...' if len(main_error)>30 else ''})")
#     else: cycle_details_lines.append(f"Осн.Цикл: {main_phase}")
#     if short_error: cycle_details_lines.append(f"Кор.Цикл: Ошибка ({short_error[:30]}{'...' if len(short_error)>30 else ''})")
#     else: cycle_details_lines.append(f"Кор.Цикл: {short_phase}")
#
#     if SEND_DETAILED_CYCLE_INFO and (main_phase != 'N/A' or short_phase != 'N/A' or main_error or short_error):
#          message_lines.append("--- Циклы ---")
#          message_lines.append(" | ".join(cycle_details_lines))
#          # Дополнительно можно вывести время последнего пика/впадины
#          # main_last_peak = main_cycle_data.get('last_peak_time', None)
#          # ...
#          message_lines.append("")
#
#     # --- Уровни ATH/ATL ---
#     ath = details.get('ath', 'N/A')
#     atl = details.get('atl', 'N/A')
#     level_lines = []
#     # Проверяем причины, добавленные в signals.py
#     sell_reasons = reasons_dict.get('SELL', [])
#     buy_reasons = reasons_dict.get('BUY', [])
#     is_near_ath = any("Близко к ATH" in str(r) for r in sell_reasons if r is not None)
#     is_near_atl = any("Близко к ATL" in str(r) for r in buy_reasons if r is not None)
#
#     if is_near_ath: level_lines.append(f"Рядом ATH! ({ath})")
#     if is_near_atl: level_lines.append(f"Рядом ATL! ({atl})")
#
#     if level_lines:
#         message_lines.append("--- Уровни ---")
#         message_lines.append(" | ".join(level_lines))
#         message_lines.append("")
#
#     return "\n".join(message_lines)
#     # --- КОНЕЦ ИЗМЕНЕНИЙ v10.11 ---
#
#
# def send_signal_notification(signal_data):
#     """Форматирует и отправляет уведомление о сигнале."""
#     player_name = signal_data.get('player', 'Unknown Player') # Используем get для безопасности
#     try:
#         message = format_signal_message(signal_data)
#         send_telegram_message(message, player_name=player_name) # Передаем имя для префикса
#     except Exception as e:
#         logger.error(f"Ошибка форматирования или отправки уведомления для {player_name}: {e}", exc_info=True)
#         # Отправляем запасное уведомление об ошибке
#         error_message = f"Критическая ошибка при форматировании/отправке уведомления для {player_name}:\n{e}"
#         send_telegram_message(error_message, is_error=True, player_name=player_name)

# =============================================
# ФАЙЛ: notifications.py (ВЕРСИЯ v10.17 - FINAL Fix BB% Price Extraction - Indentation Final Check)
# - ПЕРЕПРОВЕРЕНО: Отступы во всем файле.
# - ИСПРАВЛЕНО: Окончательно исправлена логика извлечения числового
#   значения current_price_num из строки current_price_display
#   для корректного расчета BB%. Теперь удаляются все не-цифры из всей строки.
# - Содержит все изменения из v10.16 (Enhanced BB% Logging).
# =============================================

import logging
import requests
from datetime import datetime, timezone
import math
import pandas as pd
import traceback
import re

logger = logging.getLogger("notifications")

# --- Импорт конфига ---
try:
    import config
    import storage
    TELEGRAM_BOT_TOKEN = getattr(config, 'TELEGRAM_BOT_TOKEN', None)
    TELEGRAM_CHAT_ID = getattr(config, 'TELEGRAM_CHAT_ID', None)
    SEND_DETAILED_CYCLE_INFO = getattr(config, 'SEND_DETAILED_CYCLE_INFO', False)
    SMA_SHORT_PERIOD = getattr(config, 'SMA_SHORT_PERIOD', 10)
    SMA_LONG_PERIOD = getattr(config, 'SMA_LONG_PERIOD', 30)
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        logger.error("Отсутствуют TELEGRAM_BOT_TOKEN или TELEGRAM_CHAT_ID в config.")
        TELEGRAM_BOT_TOKEN = None
except ImportError:
    logger.error("Не импортировать config в notifications.");
    TELEGRAM_BOT_TOKEN = None; TELEGRAM_CHAT_ID = None; SEND_DETAILED_CYCLE_INFO = False; SMA_SHORT_PERIOD = 10; SMA_LONG_PERIOD = 30; storage = None
except Exception as e:
    logger.error(f"Ошибка импорта config в notifications: {e}")
    TELEGRAM_BOT_TOKEN = None; TELEGRAM_CHAT_ID = None; SEND_DETAILED_CYCLE_INFO = False; SMA_SHORT_PERIOD = 10; SMA_LONG_PERIOD = 30; storage = None

MAX_MESSAGE_LENGTH = 4096

# --- Функция отправки ---
def send_telegram_message(message, is_error=False, is_warning=False, player_name=None):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        logger.warning(f"Telegram не настроен. Сообщение не отправлено: {message[:100]}...")
        return False
    prefix = ""
    if is_error: prefix = "❌ "
    elif is_warning: prefix = "⚠️ "
    if player_name: prefix = f"*{player_name}*: "
    full_message = f"{prefix}{message}"
    if len(full_message) > MAX_MESSAGE_LENGTH:
        allowed_len = MAX_MESSAGE_LENGTH - len(prefix) - 20
        logger.warning(f"Сообщение '{prefix}...' слишком длинное ({len(message)}). Обрезается.")
        full_message = f"{prefix}{message[:allowed_len]}... `(обрезано)`"
    api_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {'chat_id': TELEGRAM_CHAT_ID, 'text': full_message, 'parse_mode': 'Markdown', 'disable_web_page_preview': True }
    if is_error and "```" in message:
        payload['parse_mode'] = None
    try:
        response = requests.post(api_url, json=payload, timeout=15)
        response.raise_for_status()
        logger.info(f"Сообщение успешно отправлено в Telegram ({prefix}...).")
        return True
    except requests.exceptions.Timeout:
        logger.error(f"Ошибка отправки сообщения в Telegram для {player_name or 'N/A'}: Таймаут.")
        return False
    except requests.exceptions.HTTPError as e:
        error_details = response.text if response else "Нет ответа"
        logger.error(f"Ошибка отправки сообщения в Telegram для {player_name or 'N/A'}: HTTP {response.status_code} {response.reason}. Ответ: {error_details}")
        if payload.get('parse_mode') == 'Markdown':
            payload['parse_mode'] = None
            try:
                requests.post(api_url, json=payload, timeout=10)
            except Exception:
                pass
        return False
    except requests.exceptions.RequestException as e:
        logger.error(f"Ошибка отправки сообщения в Telegram для {player_name or 'N/A'}: {e}")
        return False
    except Exception as e:
        logger.error(f"Непредвиденная ошибка при отправке сообщения в Telegram для {player_name or 'N/A'}: {e}", exc_info=True)
        return False

# --- Функция форматирования цены ---
def _safe_format_price(price_val):
    if storage and hasattr(storage, 'format_price'):
        return storage.format_price(price_val)
    else:
        try:
            return f"{int(price_val):,}".replace(",", " ") if pd.notna(price_val) else "N/A"
        except:
            return "N/A"

# --- Функция форматирования сообщения сигнала ---
def format_signal_message(signal_data):
    player_name = signal_data.get('player', 'N/A');
    logger.debug(f"[{player_name}] Форматирование сообщения о сигнале...")
    details = signal_data.get('details', {})
    reasons_dict = signal_data.get('reasons', {})
    final_summary = signal_data.get('final_summary_text', '*Резюме не сгенерировано.*')
    message_lines = []

    # --- Основная информация ---
    price_str = details.get('current_price', 'N/A'); change_str = details.get('change', None); update_time_str = details.get('last_update_time', 'N/A')
    is_low_price = details.get('low_price_zone', False)
    price_line_emoji = "💰" if is_low_price else "🏷️"
    price_line = f"{price_line_emoji} Цена: {price_str}"
    if change_str and change_str != 'N/A': price_line += f" ({change_str})"
    price_line += f" | ⏱️ Обн: {update_time_str if update_time_str != 'N/A' else '-'}"
    message_lines.append(price_line)

    min_order_raw = details.get('min_order'); max_order_raw = details.get('max_order')
    if min_order_raw is not None or max_order_raw is not None:
         min_order_fmt = _safe_format_price(min_order_raw); max_order_fmt = _safe_format_price(max_order_raw)
         message_lines.append(f"📉 Ордера: Min: {min_order_fmt} / Max: {max_order_fmt}")

    message_lines.append("")

    # --- Резюме Сигнала ---
    message_lines.append(final_summary)
    message_lines.append("")

    # --- Детали TA ---
    rsi_val = details.get('rsi', 'N/A'); macd_str = details.get('macd', 'N/A'); sma_str = details.get('sma', 'N/A');
    bb_h_num = details.get('bb_h_val'); bb_l_num = details.get('bb_l_val')

    macd_hist_val = 'N/A'
    if isinstance(macd_str, str) and 'H:' in macd_str:
        try: macd_hist_val = macd_str.split('H:')[1].strip()
        except IndexError: pass

    # --- Расчет BB% с использованием числовых значений ---
    bb_percent_str = "N/A"
    current_price_display = details.get('current_price', 'N/A')
    logger.debug(f"[{player_name}] Расчет BB%: Price Str='{current_price_display}', BB L Num={bb_l_num}, BB H Num={bb_h_num}")

    if not current_price_display.startswith('N/A') and bb_l_num is not None and bb_h_num is not None:
        try:
            # Извлекаем число из строки цены
            price_part_to_clean = current_price_display.replace('(H)', '').strip()
            current_price_num_str = re.sub(r'[^\d]', '', price_part_to_clean)
            current_price_num = int(current_price_num_str)
            logger.debug(f"[{player_name}] BB% - Current Price Num: {current_price_num}")

            if isinstance(bb_h_num, (int, float)) and isinstance(bb_l_num, (int, float)):
                if bb_h_num > bb_l_num:
                    bb_range = bb_h_num - bb_l_num
                    if bb_range > 0:
                        bb_percent = round((current_price_num - bb_l_num) / bb_range * 100)
                        logger.debug(f"[{player_name}] BB% - Range: {bb_range}, Calc Percent: {bb_percent}")
                        bb_percent_str = f"{max(-50, min(150, bb_percent))}%"
                    else:
                        bb_percent_str = "Flat"; logger.debug(f"[{player_name}] BB% - Zero range, Flat Bands")
                elif bb_h_num == bb_l_num:
                    bb_percent_str = "Flat"; logger.debug(f"[{player_name}] BB% - Flat Bands (L==H)")
                else:
                     logger.warning(f"[{player_name}] Ошибка BB%: L ({bb_l_num}) > H ({bb_h_num})"); bb_percent_str = "Err L>H"
            else:
                 logger.warning(f"[{player_name}] BB% - Ошибка типов BB H/L: H={type(bb_h_num)}, L={type(bb_l_num)}"); bb_percent_str = "Err Type"
        except (ValueError, TypeError, ZeroDivisionError) as e_bb:
            logger.warning(f"[{player_name}] Ошибка расчета BB% для уведомления: {e_bb}"); bb_percent_str = "CalcErr"
    elif current_price_display.startswith('N/A'):
        logger.debug(f"[{player_name}] BB% - Пропуск: Цена N/A")
    else:
        logger.debug(f"[{player_name}] BB% - Пропуск: BB L/H не определены (L={bb_l_num}, H={bb_h_num})")
    # --- КОНЕЦ БЛОКА BB% ---

    details_line = f"RSI(14): {rsi_val} | MACD H: {macd_hist_val} | SMA({SMA_SHORT_PERIOD}/{SMA_LONG_PERIOD}): {sma_str} | BB%: {bb_percent_str}"
    message_lines.append(details_line)
    message_lines.append("")

    # --- Детали Циклов ---
    main_cycle_data = details.get('main_cycle', {}); short_cycle_data = details.get('short_cycle', {})
    main_phase = main_cycle_data.get('phase', 'N/A'); short_phase = short_cycle_data.get('phase', 'N/A')
    main_error = main_cycle_data.get('error'); short_error = short_cycle_data.get('error')
    cycle_lines = []
    if main_phase != 'N/A' or main_error: cycle_lines.append(f"Осн.Цикл: Ошибка" if main_error else f"Осн.Цикл: {main_phase}")
    if short_phase != 'N/A' or short_error: cycle_lines.append(f"Кор.Цикл: Ошибка" if short_error else f"Кор.Цикл: {short_phase}")
    if SEND_DETAILED_CYCLE_INFO and cycle_lines:
         message_lines.append("--- Циклы ---"); message_lines.append(" | ".join(cycle_lines)); message_lines.append("")

    # --- Уровни ATH/ATL ---
    ath = details.get('ath', 'N/A'); atl = details.get('atl', 'N/A'); level_lines = []
    sell_reasons = reasons_dict.get('SELL', []); buy_reasons = reasons_dict.get('BUY', [])
    is_near_ath = any("Близко к ATH" in str(r) for r in sell_reasons if r is not None)
    is_near_atl = any("Близко к ATL" in str(r) for r in buy_reasons if r is not None)
    if is_near_ath and ath != 'N/A': level_lines.append(f"Рядом ATH! ({ath})")
    if is_near_atl and atl != 'N/A': level_lines.append(f"Рядом ATL! ({atl})")
    if level_lines: message_lines.append("--- Уровни ---"); message_lines.append(" | ".join(level_lines))

    while message_lines and message_lines[-1] == "": message_lines.pop()
    logger.debug(f"[{player_name}] Сообщение успешно сформировано.")
    return "\n".join(message_lines)

# --- Функция отправки сигнала ---
def send_signal_notification(signal_data):
    player_name = signal_data.get('player', 'Unknown Player')
    try:
        message = format_signal_message(signal_data)
        if not message: logger.warning(f"[{player_name}] Пустое сообщение о сигнале."); return
        send_telegram_message(message, player_name=player_name)
    except Exception as e:
        logger.error(f"Критическая ошибка форматирования/отправки увед {player_name}: {e}", exc_info=True)
        error_message = f"Критическая ошибка при форматировании/отправке уведомления:\n```\n{traceback.format_exc()}\n```"
        send_telegram_message(error_message, is_error=True, player_name=player_name)