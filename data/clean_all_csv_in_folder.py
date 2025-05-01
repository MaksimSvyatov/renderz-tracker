# ФАЙЛ: clean_all_csv_in_folder_with_count_check.py
import os
import shutil
import time
import csv # Используем csv для более точного подсчета строк

# --- Настройки ---
TEMP_FILENAME_BASE = "temp_cleaned_output_{}.csv" # База для уникального имени
# -----------------

def count_lines_robust(filepath):
    """Надежно подсчитывает непустые строки в CSV-файле."""
    count = 0
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            # Использование csv.reader может быть чуть медленнее, но лучше обрабатывает разные концы строк
            reader = csv.reader(f)
            for row in reader:
                # Считаем строку, только если она не пустая (содержит хоть что-то)
                if row: # Проверка, что список не пустой
                    # Дополнительно можно проверить, что строка не состоит только из пробелов
                    # if any(field.strip() for field in row):
                        count += 1
    except Exception as e:
        print(f"  ПРЕДУПРЕЖДЕНИЕ: Не удалось точно подсчитать строки в '{os.path.basename(filepath)}'. Ошибка: {e}")
        return -1 # Возвращаем -1 в случае ошибки подсчета
    return count

def clean_csv_file(input_path, temp_path):
    """
    Читает input_path, обрабатывает строки согласно логике, записывает в temp_path.
    Возвращает: (успех, количество_записанных_строк, количество_исправленных).
    """
    processed_lines_count = 0 # Счетчик строк, записанных в выходной файл
    corrected_lines = 0
    input_line_num = 0 # Счетчик строк, прочитанных из входного файла

    try:
        with open(input_path, 'r', encoding='utf-8') as infile, \
             open(temp_path, 'w', encoding='utf-8', newline='') as outfile:

            for line in infile:
                input_line_num += 1
                original_line_stripped = line.strip()

                if not original_line_stripped:
                    continue # Пропускаем полностью пустые строки

                elements = original_line_stripped.split(',')
                num_elements = len(elements)
                line_to_write = original_line_stripped # По умолчанию записываем исходную строку

                if num_elements == 7 and 'T' in elements[0] and ('+' in elements[0] or 'Z' in elements[0]):
                    corrected_data = elements[1:]
                    if len(corrected_data) == 6:
                        line_to_write = ','.join(corrected_data)
                        corrected_lines += 1
                    else:
                        print(f"  ПРЕДУПРЕЖДЕНИЕ [{os.path.basename(input_path)}: строка {input_line_num}]: 7 эл., но после удаления префикса осталось {len(corrected_data)}. Оставлена как есть.")
                        # line_to_write остается original_line_stripped

                # Записываем определенную строку (исходную или исправленную)
                outfile.write(line_to_write + '\n')
                processed_lines_count += 1 # Увеличиваем счетчик записанных строк

        return True, processed_lines_count, corrected_lines

    except Exception as e:
        print(f"ОШИБКА [{os.path.basename(input_path)}]: Ошибка при обработке файла: {e}")
        # Возвращаем 0 записанных строк в случае ошибки, чтобы проверка не прошла
        return False, 0, corrected_lines

def main():
    current_directory = os.getcwd()
    print(f"Поиск и обработка .csv файлов в директории: {current_directory}")

    total_files_processed = 0
    total_lines_corrected = 0
    files_with_errors = []
    files_with_line_mismatch = []

    # Генерируем уникальное имя временного файла для этой сессии
    temp_file_path = os.path.join(current_directory, TEMP_FILENAME_BASE.format(int(time.time())))

    for filename in os.listdir(current_directory):
        if filename.lower().endswith(".csv") and not filename.startswith("temp_cleaned_output_"):
            file_path = os.path.join(current_directory, filename)

            if os.path.isfile(file_path):
                print(f"\nОбработка: {filename}...")

                # 1. Считаем строки ДО обработки
                lines_before = count_lines_robust(file_path)
                if lines_before == -1:
                    print("  Не удалось подсчитать строки ДО обработки. Пропуск проверки для этого файла.")
                    # Можно либо пропустить файл, либо продолжить без проверки
                    # continue # Раскомментировать, если нужно пропускать файлы с ошибкой подсчета

                # 2. Выполняем очистку во временный файл
                success, lines_written, corrected_count = clean_csv_file(file_path, temp_file_path)

                if success:
                    # 3. Считаем строки ПОСЛЕ обработки (во временном файле)
                    lines_after = count_lines_robust(temp_file_path)
                    if lines_after == -1:
                         print("  Не удалось подсчитать строки ПОСЛЕ обработки. Пропуск проверки для этого файла.")

                    # 4. Сравниваем количество строк (если оба подсчета удались)
                    line_check_passed = False
                    if lines_before != -1 and lines_after != -1:
                        if lines_before == lines_after:
                            print(f"  Проверка количества строк: ОК ({lines_before} -> {lines_after})")
                            line_check_passed = True
                        else:
                            mismatch_msg = f"ОШИБКА КОЛИЧЕСТВА СТРОК: '{filename}' ({lines_before} до -> {lines_after} после)"
                            print(f"  {mismatch_msg}")
                            files_with_line_mismatch.append(mismatch_msg)
                            line_check_passed = False # Явно указываем, что проверка не пройдена
                    else:
                        # Если подсчет не удался, считаем, что проверка пропущена, но не провалена
                        line_check_passed = True # Позволяем замену файла, если сама обработка прошла успешно

                    # 5. Заменяем файл, ТОЛЬКО если обработка успешна И проверка строк пройдена (или пропущена)
                    if line_check_passed:
                        total_files_processed += 1
                        total_lines_corrected += corrected_count
                        try:
                            shutil.move(temp_file_path, file_path)
                            if corrected_count > 0:
                                print(f"  Исправлено строк: {corrected_count}")
                            print(f"  Файл '{filename}' успешно обновлен.")
                        except Exception as e:
                            error_msg = f"ОШИБКА ЗАМЕНЫ: Не удалось заменить '{filename}' временным файлом. Ошибка: {e}"
                            print(f"  {error_msg}")
                            files_with_errors.append(f"{filename} (ошибка замены)")
                            # Пытаемся удалить временный файл
                            if os.path.exists(temp_file_path):
                                try: os.remove(temp_file_path)
                                except Exception: pass
                    else:
                        # Если проверка строк не пройдена, НЕ заменяем файл
                        print(f"  Файл '{filename}' НЕ был обновлен из-за несоответствия количества строк.")
                        # Удаляем временный файл
                        if os.path.exists(temp_file_path):
                            try: os.remove(temp_file_path)
                            except Exception: pass
                else:
                    # Если сама обработка не удалась
                    print(f"  Произошла ошибка при обработке файла '{filename}'. Файл не изменен.")
                    files_with_errors.append(f"{filename} (ошибка обработки)")
                    # Удаляем временный файл
                    if os.path.exists(temp_file_path):
                         try: os.remove(temp_file_path)
                         except Exception: pass

    # Удаляем временный файл в самом конце, если он вдруг остался
    if os.path.exists(temp_file_path):
        try: os.remove(temp_file_path)
        except Exception: pass

    print("\n--- Итоги Обработки ---")
    print(f"Всего файлов успешно обработано и обновлено: {total_files_processed}")
    print(f"Всего строк исправлено (7 -> 6 элементов): {total_lines_corrected}")
    if files_with_line_mismatch:
        print("\nФайлы с несоответствием количества строк (НЕ ОБНОВЛЕНЫ):")
        for error_file in files_with_line_mismatch:
            print(f"- {error_file}")
    if files_with_errors:
        print("\nФайлы с другими ошибками:")
        for error_file in files_with_errors:
            print(f"- {error_file}")
    if not files_with_line_mismatch and not files_with_errors:
         print("\nОшибок и несоответствий количества строк не обнаружено.")
    print("------------------------")


if __name__ == "__main__":
    main()