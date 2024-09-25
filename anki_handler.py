import requests
import regex as re
import unicodedata

ANKI_CONNECT_URL = 'http://127.0.0.1:8765'
CJK_RE = re.compile("CJK (UNIFIED|COMPATIBILITY) IDEOGRAPH")


def isKanji(unichar):
    """Check if a character is a Kanji."""
    return bool(CJK_RE.match(unicodedata.name(unichar, "")))


class AnkiHandler():
    def __init__(self, url=ANKI_CONNECT_URL):
        self.url = url
        self.anki_kanji_set = None


    def invoke(self, action, **params):
        """Invoke AnkiConnect actions."""
        return requests.post(ANKI_CONNECT_URL, json={
            "action": action,
            "version": 6,
            "params": params
        }).json()


    def get_deck_notes(self, deck_name):
        """Retrieve note fields for the given note IDs."""
        response = self.invoke('findNotes', query=f'deck:"{deck_name}"')
        print(f"Trying to retrieve the notes from deck deck:{deck_name}")
        return response['result']


    def get_note_fields(self, note_ids):
        response = self.invoke('notesInfo', notes=note_ids)
        return response['result']


    def get_anki_kanji_set(self, deck_name, key):
        """Get the set of Kanji present in the Anki deck."""
        if self.anki_kanji_set:
            return self.anki_kanji_set

        note_ids = self.get_deck_notes(deck_name)
        if not note_ids:
            print(f"No notes found in deck '{deck_name}'")
            return

        notes = self.get_note_fields(note_ids)
        self.anki_kanji_set = set()  # Collect unique kanji from Anki

        for note in notes:
            key_field = note['fields'].get(key, {}).get('value', '')

            # Using isKanji to find Kanji characters in the key_field
            kanji_in_field = [char for char in key_field if isKanji(char)]

            self.anki_kanji_set.update(kanji_in_field)
        
        return self.anki_kanji_set