import os
import regex as re
import datetime
import pyperclip
from kanjize import kanji2number


def extract_number_from_kanji(filename):
    # Extract normal numbers first
    normal_number = re.search(r'\d+', filename)
    if normal_number:
        return int(normal_number.group())  # Return the first found normal number
    
    # Then extract kanji numbers if no normal number is found
    kanji_number = re.search(r'[一二三四五六七八九十百千万億兆]+', filename)
    if kanji_number:
        return kanji2number(kanji_number.group())
    
    return float('inf')  # If no number is found, return a large number to sort it last.


class FileHandler():

    def get_files(self, target, extensions):
        files = []

        if os.path.isfile(target):
            if any(target.endswith(ext) for ext in extensions):
                files = [target]
        else:
            for root, _, filenames in os.walk(target):
                for filename in filenames:
                    if any(filename.endswith(ext) for ext in extensions):
                        files.append(os.path.join(root, filename))
        
            # Sort the files by kanji number if available, otherwise alphabetically
            files.sort(key=lambda f: (extract_number_from_kanji(os.path.basename(f)), os.path.basename(f)))
        
        return files


    def export_file(self, data):
        export_filename = 'unknown_kanji_' + datetime.datetime.now().strftime("%Y%m%d%H%M%S") + '.txt'

        with open(export_filename, 'w+', encoding='utf-8') as f:
            for filename, unknown_kanji_list in data.items():
                f.write(filename + '\n')
                for kanji in unknown_kanji_list:
                    f.write(kanji + '\n')
            print(f"Export complete. Data saved to {export_filename}")


    def copy_kanji_to_clipboard(self, unknown_kanji_set):
        kanji_list = '\n'.join(unknown_kanji_set)  # Combine kanji with newline
        pyperclip.copy(kanji_list)  # Copy the string to the clipboard
        print("Kanji copied to clipboard.")
