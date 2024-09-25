import os
import regex as re
import ebooklib
from ebooklib import epub
from bs4 import BeautifulSoup
import requests
import argparse
import warnings
import glob
import datetime
import json
import pysubs2
import unicodedata
from kanjize import kanji2number

# Suppress specific warnings
warnings.filterwarnings("ignore", category=UserWarning, module='ebooklib.epub')
warnings.filterwarnings("ignore", category=FutureWarning, module='ebooklib.epub')

# Constants
ANKI_CONNECT_URL = 'http://127.0.0.1:8765'
SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))
SETTINGS_FILE = os.path.join(SCRIPT_DIR, 'epub_unique_kanji_settings.json')
CJK_RE = re.compile("CJK (UNIFIED|COMPATIBILITY) IDEOGRAPH")
IS_NOT_JAPANESE_PATTERN = re.compile(r'[^\p{N}\p{Lu}○◯々-〇〻ぁ-ゖゝ-ゞァ-ヺー０-９Ａ-Ｚｦ-ﾝ\p{Radical}\p{Unified_Ideograph}]+')

def isKanji(unichar):
    """Check if a character is a Kanji."""
    return bool(CJK_RE.match(unicodedata.name(unichar, "")))

def save_args_to_file(args):
    """Save user arguments to a JSON file."""
    data_to_save = {
        'deck': args.deck,
        'key': args.key
    }
    with open(SETTINGS_FILE, 'w') as f:
        json.dump(data_to_save, f)


def load_args_from_file():
    """Load user arguments from a JSON file."""
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, 'r') as f:
                return json.load(f)
        except json.JSONDecodeError:
            print(f"Warning: {SETTINGS_FILE} is empty or corrupted. Using default arguments.")
            return None
    return None


def invoke(action, **params):
    """Invoke AnkiConnect actions."""
    return requests.post(ANKI_CONNECT_URL, json={
        "action": action,
        "version": 6,
        "params": params
    }).json()


# Step 2: Get all note IDs from the Anki deck
def get_deck_notes(deck_name):
    """Retrieve note fields for the given note IDs."""
    response = invoke('findNotes', query=f'deck:"{deck_name}"')
    print(f"Trying to retrieve the notes from deck deck:{deck_name}")
    return response['result']


# Step 3: Get note fields from Anki notes
def get_note_fields(note_ids):
    response = invoke('notesInfo', notes=note_ids)
    return response['result']


def get_anki_kanji_set(deck_name, key):
    """Get the set of Kanji present in the Anki deck."""
    note_ids = get_deck_notes(deck_name)
    if not note_ids:
        print(f"No notes found in deck '{deck_name}'")
        return

    notes = get_note_fields(note_ids)
    anki_kanji_list = set()  # Collect unique kanji from Anki

    for note in notes:
        key_field = note['fields'].get(key, {}).get('value', '')

        # Using isKanji to find Kanji characters in the key_field
        kanji_in_field = [char for char in key_field if isKanji(char)]

        anki_kanji_list.update(kanji_in_field)
    
    return anki_kanji_list
    

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


def get_files(folder, extensions):
    files = []
    for root, _, filenames in os.walk(folder):
        for filename in filenames:
            if any(filename.endswith(ext) for ext in extensions):
                files.append(os.path.join(root, filename))
    
    # Sort the files by kanji number if available, otherwise alphabetically
    files.sort(key=lambda f: (extract_number_from_kanji(os.path.basename(f)), os.path.basename(f)))
    
    return files


def export_file(data):
    export_filename = 'unknown_kanji_' + datetime.datetime.now().strftime("%Y%m%d%H%M%S") + '.txt'
    with open(export_filename, 'w+', encoding='utf-8') as f:
        for filename, unknown_kanji_list in data.items():
            f.write(filename + '\n')
            for kanji in unknown_kanji_list:
                f.write(kanji + '\n')
        print(f"Export complete. Data saved to {export_filename}")


def export_series_file(unknown_kanji_set):
    export_filename = 'unknown_kanji_' + datetime.datetime.now().strftime("%Y%m%d%H%M%S") + '.txt'
    with open(export_filename, 'w+', encoding='utf-8') as f:
        for kanji in unknown_kanji_set:
            f.write(kanji + '\n')
            
        print(f"Export complete. Data saved to {export_filename}")

        
def extract_kanji_with_positions(text):
    """Extract Kanji and their positions from text."""
    text = re.sub(IS_NOT_JAPANESE_PATTERN, '', text)
    return {char: [idx] for idx, char in enumerate(text) if isKanji(char)}


def extract_kanji_with_timestamps(subtitle_data):
    """Extract unique Kanji and their timestamps from subtitle."""
    kanji_timestamps = {}

    # Process each subtitle line (text and start time)
    for text, start_time in subtitle_data:
        text = re.sub(IS_NOT_JAPANESE_PATTERN, '', text)
        kanji_list = [char for char in text if isKanji(char)]

        # Extract kanji from the text and their positions
        for kanji in kanji_list:
            if kanji not in kanji_timestamps:
                kanji_timestamps[kanji] = []
            # Add the start time of the subtitle line where the kanji appears
            kanji_timestamps[kanji].append(start_time)

    return kanji_timestamps


def extract_text_from_epub(epub_path):
    """Extract text from an EPUB file."""
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


def extract_text_from_subtitle(subtitle_path):
    try:
        subs = pysubs2.load(subtitle_path)
    except Exception as e:
        print(f"Error loading subtitle file: {e}")
        return None

    subtitle_data = []

    for line in subs:
        subtitle_data.append((line.text, line.start))

    return subtitle_data


def process_single_epub(epub_file, anki_kanji_set, show_positions):
    text = extract_text_from_epub(epub_file)
    if not text:
        print(f"Failed to extract text from {epub_file}")
        return

    book_kanji_positions = extract_kanji_with_positions(text)

    return process_kanji_data(
        kanji_data=book_kanji_positions,
        anki_kanji_set=anki_kanji_set,
        show_positions=show_positions,
        source_name=os.path.basename(epub_file)
    )


def process_kanji_data(kanji_data, anki_kanji_set, show_positions, formatter=None, source_name=""):

    kanji_set = set(kanji_data.keys())
    unknown_kanji_set = kanji_set - anki_kanji_set

    print(f"\n{source_name}: Unique {len(kanji_set)}, not in Anki: {len(unknown_kanji_set)}")

    if show_positions:
        for kanji in sorted(unknown_kanji_set, key=lambda k: kanji_data[k][0]):
            positions = kanji_data[kanji][:10]  # Get the first 10 positions/timestamps
            formatted_positions = formatter(positions) if formatter else positions
            position_str = ', '.join(map(str, formatted_positions))

            # Check if there are more than 5 positions/timestamps and add '...' if so
            if len(kanji_data[kanji]) > 5:
                position_str += ' ...'

            print(f"Kanji: {kanji}, Positions/Timestamps: {position_str}")

    return unknown_kanji_set

def process_single_subtitle_file(subtitle_file, anki_kanji_set, show_positions):
    subtitle_data = extract_text_from_subtitle(subtitle_file)
    if not subtitle_data:
        print(f"Failed to extract text from {subtitle_file}")
        return
    
    kanji_timestamps = extract_kanji_with_timestamps(subtitle_data)
    
    # Formatter to convert timestamps to readable format
    timestamp_formatter = lambda timestamps: [pysubs2.time.ms_to_str(ts) for ts in timestamps]

    return process_kanji_data(
        kanji_data=kanji_timestamps,
        anki_kanji_set=anki_kanji_set,
        show_positions=show_positions,
        formatter=timestamp_formatter,
        source_name=os.path.basename(subtitle_file)
    )


def process_files(files, anki_kanji_set, show_positions):
    """Process multiple EPUB and subtitle files."""
    export_data = {}
    unknown_kanji_set = set()

    for file in files:
        if file.endswith('.epub'):
            export_data[file] = process_single_epub(file, anki_kanji_set, show_positions)
        elif file.endswith('.srt') or file.endswith('.ass'):
            export_data[file] = process_single_subtitle_file(file, anki_kanji_set, show_positions)
        
        unknown_kanji_set.update(export_data[file])

    return export_data, unknown_kanji_set


def main(target, deck_name, key, show_positions, export, export_series):
    """Main function to process files and find unique Kanji."""
    # Get set of unique kanji currently in Anki
    anki_kanji_set = get_anki_kanji_set(deck_name, key)
    if not anki_kanji_set:
        return
    
    print(f"Total kanji in Anki: {len(anki_kanji_set)}")
    if os.path.isfile(target):
        files = [target]
    else:
        files = get_files(target, ['.epub', '.srt', '.ass'])
        if not files:
            print(f"No EPUB or subtitle files found in folder '{target}'")
            return
    
    print("Files found: ", len(files))
    export_data, unknown_kanji_set = process_files(files, anki_kanji_set, show_positions)

    print(f"Total unkown kanji found: {len(unknown_kanji_set)}")

    if export:
        export_file(export_data)
    elif export_series:
        export_series_file(unknown_kanji_set)


if __name__ == "__main__":
    # Load saved arguments if they exist
    saved_args = load_args_from_file()

    parser = argparse.ArgumentParser(description='Process EPUB and Subtitle files and find unique kanji not in Anki.')
    parser.add_argument('target', type=str, help='Path to the EPUB/sub file or folder containing EPUB or subtitle files')
    parser.add_argument('--deck', type=str, default='Mining', help='Name of the Anki deck (default: Mining)')
    parser.add_argument('--key', type=str, default='Word', help='Name of the field to scan for kanji (default: Word)')
    parser.add_argument('--show-positions', action='store_true', help='Show kanji positions in the text')
    parser.add_argument('--export', action='store_true', help='Export unknown kanji to a file')
    parser.add_argument('--export-series', action='store_true', help='Export unknown kanji to a file')

    # If saved_args exist, use them as the default values
    if saved_args:
        parser.set_defaults(**saved_args)

    args = parser.parse_args()

    # Save the arguments for future runs
    save_args_to_file(args)

    main(args.target, args.deck, args.key, args.show_positions, args.export, args.export_series)