import os
import regex as re
import ebooklib
from ebooklib import epub
from bs4 import BeautifulSoup
import argparse
import warnings
import glob
import pysubs2
import unicodedata
from anki_handler import AnkiHandler
from file_handler import FileHandler
from util import save_args_to_file, load_args_from_file, get_arguments

# Suppress specific warnings
warnings.filterwarnings("ignore", category=UserWarning, module='ebooklib.epub')
warnings.filterwarnings("ignore", category=FutureWarning, module='ebooklib.epub')


CJK_RE = re.compile("CJK (UNIFIED|COMPATIBILITY) IDEOGRAPH")
IS_NOT_JAPANESE_PATTERN = re.compile(r'[^\p{N}\p{Lu}○◯々-〇〻ぁ-ゖゝ-ゞァ-ヺー０-９Ａ-Ｚｦ-ﾝ\p{Radical}\p{Unified_Ideograph}]+')


def isKanji(unichar):
    """Check if a character is a Kanji."""
    return bool(CJK_RE.match(unicodedata.name(unichar, "")))

        
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


def main(target, deck_name, key, show_positions, export, copy_clipboard):
    """Main function to process files and find unique Kanji."""
    # Get set of unique kanji currently in Anki
    anki_handler = AnkiHandler()
    anki_kanji_set = anki_handler.get_anki_kanji_set(deck_name, key)
    if not anki_kanji_set:
        return
    
    file_handler = FileHandler()
    print(f"Total kanji in Anki: {len(anki_kanji_set)}")

    files = file_handler.get_files(target, ['.epub', '.srt', '.ass'])
    if not files:
        print(f"No EPUB or subtitle files found in folder '{target}'")
        return
    
    print("Files found: ", len(files))
    export_data, unknown_kanji_set = process_files(files, anki_kanji_set, show_positions)

    print(f"Total unkown kanji found: {len(unknown_kanji_set)}")

    if export:
        file_handler.export_file(export_data)
    elif copy_clipboard:
        file_handler.copy_kanji_to_clipboard(unknown_kanji_set)


if __name__ == "__main__":
    # Load saved arguments if they exist
    saved_args = load_args_from_file()
    args = get_arguments(saved_args)

    # Save the arguments for future runs
    save_args_to_file(args)

    main(args.target, args.deck, args.key, args.show_positions, args.export, args.copy_clipboard)