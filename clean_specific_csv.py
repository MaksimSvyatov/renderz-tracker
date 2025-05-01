# ФАЙЛ: clean_specific_csv.py
import os
import shutil # Используем shutil для более надежного перемещения

# --- Настройки ---
INPUT_FILENAME = "Warren_Zaïre-Emery_103_copy.csv"
TEMP_FILENAME = "temp_cleaned_output.csv"
# -----------------

def clean_csv_file(input_path, temp_path):
    """
    Читает input_path, обрабатывает строки согласно логике
    (исправляет 7-элементные строки с ISO-префиксом, остальные копирует)
    и записывает результат в temp_path.
    Возвращает количество обработанных и исправленных строк.
    """
    processed_lines = 0
    corrected_lines = 0
    skipped_empty = 0 # Счетчик пустых строк

    try:
        print(f"Начало обработки файла: {input_path}")
        with open(input_path, 'r', encoding='utf-8') as infile, \
             open(temp_path, 'w', encoding='utf-8', newline='') as outfile: # newline='' важен для csv

            for line in infile:
                processed_lines += 1
                original_line_stripped = line.strip() # Убираем лишние пробелы/переводы строк по краям

                if not original_line_stripped:
                    # Если строка пустая после strip(), можно ее пропустить или записать пустую строку
                    # Согласно "ничего не удаляем", запишем пустую строку, если она была в оригинале.
                    # Но чаще пустые строки между записями лучше удалять.
                    # Давай пока будем их пропускать, чтобы не добавлять пустых строк в вывод.
                    skipped_empty += 1
                    # print(f"  Пропущена пустая строка (строка {processed_lines} в файле)")
                    continue # Переходим к следующей строке

                elements = original_line_stripped.split(',')
                num_elements = len(elements)

                # Логика обработки согласно последнему обсуждению
                if num_elements == 7 and 'T' in elements[0] and ('+' in elements[0] or 'Z' in elements[0]): # Добавил проверку на Z для UTC
                    # Это строка с ISO-префиксом, которую нужно исправить
                    corrected_data = elements[1:] # Берем все элементы, кроме первого
                    # Проверяем, что у нас осталось 6 элементов
                    if len(corrected_data) == 6:
                        corrected_line = ','.join(corrected_data)
                        outfile.write(corrected_line + '\n')
                        corrected_lines += 1
                        # print(f"  Строка {processed_lines}: Исправлена (7 -> 6 элементов).")
                    else:
                        # Неожиданный случай: после удаления префикса осталось не 6 элементов
                        # Записываем как есть, чтобы ничего не удалять
                        outfile.write(original_line_stripped + '\n')
                        print(f"  ПРЕДУПРЕЖДЕНИЕ: Строка {processed_lines} имела 7 эл., но после удаления префикса осталось {len(corrected_data)} эл. Оставлена как есть.")

                elif num_elements == 6:
                    # Строка уже имеет правильный формат (6 элементов)
                    # Просто записываем ее как есть
                    outfile.write(original_line_stripped + '\n')
                    # print(f"  Строка {processed_lines}: Оставлена как есть (6 элементов).")

                else:
                    # Любое другое количество элементов или некорректные 7 элементов
                    # Записываем строку как есть, без изменений
                    outfile.write(original_line_stripped + '\n')
                    # print(f"  Строка {processed_lines}: Оставлена как есть ({num_elements} элементов).")

        print(f"Файл {input_path} обработан.")
        print(f"Всего строк прочитано (не считая пустых): {processed_lines - skipped_empty}")
        print(f"Строк исправлено (7 -> 6 элементов): {corrected_lines}")
        if skipped_empty > 0:
             print(f"Пустых строк пропущено: {skipped_empty}")
        return True, processed_lines, corrected_lines

    except FileNotFoundError:
        print(f"ОШИБКА: Файл не найден: {input_path}")
        return False, 0, 0
    except Exception as e:
        print(f"ОШИБКА: Произошла ошибка при обработке файла: {e}")
        return False, processed_lines, corrected_lines

def main():
    # Убедимся, что файл существует перед началом
    if not os.path.exists(INPUT_FILENAME):
        print(f"ОШИБКА: Исходный файл '{INPUT_FILENAME}' не найден в текущей директории.")
        return

    # Выполняем очистку во временный файл
    success, _, _ = clean_csv_file(INPUT_FILENAME, TEMP_FILENAME)

    if success:
        # Если обработка прошла успешно, заменяем исходный файл временным
        try:
            # shutil.move более надежен, чем os.replace в некоторых случаях (например, при работе с разными ФС)
            print(f"Замена файла '{INPUT_FILENAME}' обработанной версией...")
            shutil.move(TEMP_FILENAME, INPUT_FILENAME)
            print("Замена успешно завершена.")
        except Exception as e:
            print(f"ОШИБКА: Не удалось заменить исходный файл '{INPUT_FILENAME}' временным файлом '{TEMP_FILENAME}'. Ошибка: {e}")
            print("Результат очистки может быть во временном файле.")
    else:
        print("Обработка файла не удалась. Исходный файл не изменен.")
        # Удаляем временный файл, если он был создан, но произошла ошибка
        if os.path.exists(TEMP_FILENAME):
            try:
                os.remove(TEMP_FILENAME)
            except Exception as e_rem:
                print(f"Не удалось удалить временный файл {TEMP_FILENAME}: {e_rem}")

if __name__ == "__main__":
    main()