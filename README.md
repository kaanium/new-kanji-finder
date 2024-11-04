**📚 User Guide: Kanji Schizos**

**Overview:**
The "Kanji Schizos" script identifies unique kanji found in files that aren't in your Anki deck.

**Requirements:**
- **Python** installed.
- **Anki** with AnkiConnect running.
- EPUB, txt, and srt files with text to extract kanji from.

**Installation:**
1. **Install Python:** Download from [python.org](https://www.python.org/).
2. **Install Libraries:**
   ```bash
   pip install requests regex ebooklib beautifulsoup4
   ```

**Setting Up the Script:**
1. **Download and Extract:**
   - Download the RAR file containing `kanji_schizos.py` and `settings.txt`.
   - Extract them into the same directory.
   
2. **Configure Settings:**
   - `settings.txt` should be in the same folder as `kanji_schizos.py`.
   - Example configuration (case-sensitive):
     ```txt
     folder=path/to/folder
     deck=Mining
     key=Word
     show_positions=True
     export=False
     ```
   - Replace `path/to/folder` with the actual folder path to scan.
   - Set `show_positions` to `True` to print kanji positions.
   - If `export` is `True`, unknown kanji and their files will be exported.
   - Multiple fields can be added to `key`, separated by spaces (e.g., `key=Word Meaning`).

**How the Script Works:**
- **Folder Scanning:** The script scans folders recursively.
- **Text File Handling:** Text files in the same folder are merged under the folder's name. To differentiate files, place them in separate folders (e.g., `Albatross`, `Muramasa`).

**Troubleshooting:**
- Ensure paths in `settings.txt` are correct and case-sensitive.

## Contributors

| Contributor | Discord |
| ----------- | ---------------|
| Caoimhe | @caoimhe.00
| Tsuu | @tsuu2092
| Duccoon | @Duccoon
| Axiom | @axiom30
