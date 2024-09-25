import os
import json
import argparse

SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))
SETTINGS_FILE = os.path.join(SCRIPT_DIR, 'epub_unique_kanji_settings.json')

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
    

def get_arguments(saved_args=None):
    parser = argparse.ArgumentParser(description='Process EPUB and Subtitle files and find unique kanji not in Anki.')
    parser.add_argument('target', type=str, help='Path to the EPUB/sub file or folder containing EPUB or subtitle files')
    parser.add_argument('--deck', type=str, default='Mining', help='Name of the Anki deck (default: Mining)')
    parser.add_argument('--key', type=str, default='Word', help='Name of the field to scan for kanji (default: Word)')
    parser.add_argument('--show-positions', action='store_true', help='Show kanji positions in the text')
    parser.add_argument('--export', action='store_true', help='Export unknown kanji to a file')
    parser.add_argument('--copy-clipboard', action='store_true', help='Copy unknown kanji to clipboard')

    if saved_args:
        parser.set_defaults(**saved_args)

    return parser.parse_args()