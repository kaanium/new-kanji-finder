import os
import regex as re
import unicodedata
import collections
import enum
import ebooklib
from ebooklib import epub
from bs4 import BeautifulSoup
import requests
import warnings
import glob
import datetime

# Suppress specific warnings
warnings.filterwarnings("ignore", category=UserWarning, module='ebooklib.epub')
warnings.filterwarnings("ignore", category=FutureWarning, module='ebooklib.epub')

ANKI_CONNECT_URL = 'http://127.0.0.1:8765'

# CJK detection regex for kanji
cjk_re = re.compile("CJK (UNIFIED|COMPATIBILITY) IDEOGRAPH")

# Regex pattern to filter out non-Japanese characters
is_not_japanese_pattern = re.compile(r'[^\p{N}\p{Lu}○◯々-〇〻ぁ-ゖゝ-ゞァ-ヺー０-９Ａ-Ｚｦ-ﾝ\p{Radical}\p{Unified_Ideograph}]+')

kanji_numerals = {
    '一': 1, '二': 2, '三': 3, '四': 4, '五': 5, '六': 6, '七': 7, '八': 8, '九': 9, '十': 10
}

def export_unknown_kanji_sentences(file_name, kanji_sentences):
    export_folder = "sentences"
    if not os.path.exists(export_folder):
        os.makedirs(export_folder)

    base_file_name = os.path.splitext(os.path.basename(file_name))[0]
    export_file = os.path.join(export_folder, base_file_name + "_sentences.txt")

    try:
        with open(export_file, 'w', encoding='utf-8') as file:
            for kanji, sentences in kanji_sentences.items():
                file.write(f"Kanji: {kanji}\n")
                for sentence in sentences:
                    file.write(f"  Sentence: {sentence}\n")
                    break
    except Exception as e:
        print(f"Failed to export sentences to {export_file}: {e}")

def extract_kanji_with_sentences(text, kanji_list):
    sentence_separators = r'[「」『』"\'.,!?．。！？…︒︕︖︙\n]'

    sentences = re.split(f"({sentence_separators})", text)

    full_sentences = [
        sentences[i] + (sentences[i + 1] if i + 1 < len(sentences) else "").strip()
        for i in range(0, len(sentences), 2)
    ]

    kanji_sentences = {}
    for kanji in kanji_list:
        kanji_sentences[kanji] = [
            sentence for sentence in full_sentences if kanji in sentence
        ]

    return kanji_sentences


def natural_sort_key(s):
    try:
        if not isinstance(s, str):
            s = str(s)

        def replace_kanji_with_int(text):
            return kanji_numerals.get(text, text)          
        return [
            int(text) if text.isdigit() else replace_kanji_with_int(text) if text in kanji_numerals else text.lower()
            for text in re.split(r'(\d+|[一二三四五六七八九十]+)', s)
        ]
    except Exception as e:
        print(f"Error processing: {s}, Error: {e}")
        raise

def isKanji(unichar):
    return bool(cjk_re.match(unicodedata.name(unichar, "")))

def read_settings(file_path):
    settings = {}
    with open(file_path, 'r', encoding="utf-8") as f:
        for line in f:
            if "=" in line:
                key, value = line.strip().split("=", 1)
                if key == "key":
                    value = value.split()
                elif value.lower() == 'true':
                    value = True
                elif value.lower() == 'false':
                    value = False
                settings[key] = value
    return settings

def invoke(action, **params):
    return requests.post(ANKI_CONNECT_URL, json={
        "action": action,
        "version": 6,
        "params": params
    }).json()

# Step 2: Get all note IDs from the Anki deck
def get_deck_notes(deck_name):
    response = invoke('findNotes', query=f'deck:"{deck_name}"')
    print(f"Trying to retrieve the notes from deck:{deck_name}")
    return response['result']

# Step 3: Get note fields from Anki notes
def get_note_fields(note_ids):
    response = invoke('notesInfo', notes=note_ids)
    return response['result']

# Step 4: Extract kanji and their positions from text
def extract_kanji_with_positions(text):

    filtered_text = re.sub(is_not_japanese_pattern, '', text)

    kanji_positions = {}
    for idx, char in enumerate(filtered_text):
        if isKanji(char):
            if char not in kanji_positions:
                kanji_positions[char] = []
            kanji_positions[char].append(idx)
    return kanji_positions

# Step 5: Extract text from EPUB file
def extract_text_from_epub(epub_path):
    try:
        book = epub.read_epub(epub_path)
    except:
        return None
    all_text = ""

    for item in book.get_items():
        if item.get_type() == ebooklib.ITEM_DOCUMENT:
            soup = BeautifulSoup(item.get_body_content(), 'html.parser')

            # Remove all rt elements (furigana)
            for rt in soup.find_all('rt'):
                rt.decompose()

            all_text += soup.get_text()

    return all_text

# Step 6: Extract text and timestamps from subtitle files
def extract_kanji_from_subtitle(subtitle_path):
    subtitle_kanji_positions = {}
    try:
        with open(subtitle_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        for i, line in enumerate(lines):
            if "-->" in line:  # This line is a timestamp
                timestamp = line.strip()
            else:
                text = line.strip()
                filtered_text = re.sub(is_not_japanese_pattern, '', text)
                for idx, char in enumerate(filtered_text):
                    if isKanji(char):
                        if char not in subtitle_kanji_positions:
                            subtitle_kanji_positions[char] = []
                        subtitle_kanji_positions[char].append((timestamp, idx))
    except Exception as e:
        print(f"Failed to process subtitle {subtitle_path}: {e}")
    return subtitle_kanji_positions

def get_epub_subtitle_and_text_files(folder):
    epub_files = []
    subtitle_files = []
    text_files_by_folder = collections.defaultdict(list)

    for root, _, filenames in os.walk(folder):

        for filename in sorted(filenames):
            if filename.endswith('.epub'):
                epub_files.append(os.path.join(root, filename))
            elif filename.endswith('.srt'):
                subtitle_files.append(os.path.join(root, filename))
            elif filename.endswith('.txt') and not (os.path.basename(root) == "sentences" or os.path.basename(root) == "."):
                text_files_by_folder[os.path.basename(root)].append(os.path.join(root, filename))

    return epub_files, subtitle_files, text_files_by_folder


def combine_text_files(text_files):
    combined_text = ""
    for text_file in text_files:
        try:
            with open(text_file, 'r', encoding='utf-8') as f:
                combined_text += f.read()
        except Exception as e:
            print(f"Failed to read {text_file}: {e}")
    return combined_text



def export_file(data):
    export_filename = 'unknown_kanji_' + datetime.datetime.now().strftime("%Y%m%d%H%M%S") + '.txt'
    with open(export_filename, 'w+', encoding='utf-8') as f:
        for filename, unknown_kanji_list in data.items():
            f.write(os.path.basename(filename) + '\n')
            s = ''.join(unknown_kanji_list)
            f.write(s + '\n\n')
        print(f"Export complete. Data saved to {export_filename}")

def main(settings_file):
    settings = read_settings(settings_file)
    
    folder = settings.get('folder', '.')
    deck_name = settings.get('deck', 'Mining')
    keys = settings.get('key', ['Word'])
    show_positions = settings.get('show_positions', False)
    export_filename = settings.get('export_kanji', False)
    export_sentences = settings.get('export_sentences', False)

    epub_files, subtitle_files, text_files_by_folder = get_epub_subtitle_and_text_files(folder)
    
    if not epub_files and not subtitle_files and not text_files_by_folder:
        print(f"No EPUB, subtitle, or text files found in folder '{folder}'")
        return

    # Get all note IDs from the specified Anki deck
    note_ids = get_deck_notes(deck_name)
    if not note_ids:
        print(f"No notes found in deck '{deck_name}'")
        return

    notes = get_note_fields(note_ids)
    anki_kanji_list = set()  
    for key in keys:
        for note in notes:
            key_field = note['fields'].get(key, {}).get('value', '')
            for char in key_field:
                if isKanji(char):
                    anki_kanji_list.add(char)

    print("EPUB files found: ", len(epub_files))
    print("Subtitle files found: ", len(subtitle_files))
    print("Folders with text found: ", len(text_files_by_folder))
    print(f"Total kanji in Anki: {len(anki_kanji_list)}")

    epub_files = sorted(epub_files, key=natural_sort_key)
    subtitle_files = sorted(subtitle_files, key=natural_sort_key)
    text_files_by_folder = {
        folder: sorted(files, key=natural_sort_key) 
        for folder, files in sorted(text_files_by_folder.items(), key=natural_sort_key)
    }


    export_data = {}

    # Sets to store total unique kanji and those not in Anki
    total_unique_kanji = set()
    total_unknown_kanji = set()

    # Process each EPUB file and compare its kanji with Anki
    print("\nEPUB files: ")
    for epub_file in epub_files:
        text = extract_text_from_epub(epub_file)
        if text is None:
            print(f"Failed to extract text from {epub_file}")
            continue
        book_kanji_positions = extract_kanji_with_positions(text)
        book_kanji_list = set(book_kanji_positions.keys())

        # Find kanji in the EPUB that are not in Anki
        unknown_kanji_list = book_kanji_list - anki_kanji_list
        export_data[epub_file] = unknown_kanji_list

        # Add kanji to the total sets
        total_unique_kanji.update(book_kanji_list)
        total_unknown_kanji.update(unknown_kanji_list)

        print(f"{os.path.basename(epub_file)} : Unique: {len(book_kanji_list)}, not in Anki: {len(unknown_kanji_list)}")

        sorted_unique_kanji_list = sorted(unknown_kanji_list, key=lambda k: book_kanji_positions[k][0])

        if show_positions:
            for kanji in sorted_unique_kanji_list:
                positions = book_kanji_positions[kanji]
                print(f"Kanji: {kanji}, Positions: {positions}")

        if export_sentences:
            kanji_sentences = extract_kanji_with_sentences(text, sorted_unique_kanji_list)
            export_unknown_kanji_sentences(epub_file, kanji_sentences)


    print("\nSubtitle files: ")
    for subtitle_file in subtitle_files:
        subtitle_kanji_positions = extract_kanji_from_subtitle(subtitle_file)
        subtitle_kanji_list = set(subtitle_kanji_positions.keys())

        unknown_kanji_list = subtitle_kanji_list - anki_kanji_list
        export_data[subtitle_file] = unknown_kanji_list

        # Add kanji to the total sets
        total_unique_kanji.update(subtitle_kanji_list)
        total_unknown_kanji.update(unknown_kanji_list)

        print(f"{os.path.basename(subtitle_file)} : Unique: {len(subtitle_kanji_list)}, not in Anki: {len(unknown_kanji_list)}")

        sorted_unique_kanji_list = sorted(unknown_kanji_list, key=lambda k: subtitle_kanji_positions[k][0][0])

        if show_positions:
            for kanji in sorted_unique_kanji_list:

                positions = subtitle_kanji_positions[kanji]
                print(f"Kanji: {kanji}, Timestamp: {positions[0][0]}")

    print("\nText files: ")
    # Process text files by folder
    for folder_name, text_files in text_files_by_folder.items():
        combined_text = combine_text_files(text_files)
        combined_kanji_positions = extract_kanji_with_positions(combined_text)
        combined_kanji_list = set(combined_kanji_positions.keys())

        unknown_combined_kanji_list = combined_kanji_list - anki_kanji_list

        total_unique_kanji.update(combined_kanji_list)
        total_unknown_kanji.update(unknown_combined_kanji_list)

        print(f"{folder_name} : Unique: {len(combined_kanji_list)}, not in Anki: {len(unknown_combined_kanji_list)}")

        sorted_combined_kanji_list = sorted(unknown_combined_kanji_list, key=lambda k: combined_kanji_positions[k][0])

        if show_positions:
            for kanji in sorted_combined_kanji_list:
                positions = combined_kanji_positions[kanji]
                print(f"Kanji: {kanji}, Positions: {positions}")

        if export_filename:
            export_data[folder_name] = unknown_combined_kanji_list

        if export_sentences:
            kanji_sentences = extract_kanji_with_sentences(combined_text, sorted_combined_kanji_list)
            export_unknown_kanji_sentences(folder_name, kanji_sentences)

    total_unique_count = len(total_unique_kanji)
    total_unknown_count = len(total_unknown_kanji)

    if export_filename:
        export_data["total"] = total_unknown_kanji
        export_file(export_data)

    print(f"\nTotal unique kanji: {total_unique_count}")
    print(f"Total kanji not in Anki: {total_unknown_count}")


    input()




if __name__ == "__main__":
    settings_file = 'settings.txt'
    main(settings_file)

           
