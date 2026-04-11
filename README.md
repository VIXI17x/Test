# Apple Notes PDF Exporter

Exports every note from your iCloud Notes account as an individual PDF file by automating the iCloud web interface with Playwright.

## How it works

1. Opens `icloud.com/notes` in a visible Chromium window.
2. Waits for you to sign in (or reuses a saved session from a previous run).
3. Discovers all notes in the sidebar, scrolling to load lazily-rendered items.
4. Clicks each note, hides the navigation chrome, and prints the content to PDF.
5. Saves each PDF to `exported_notes/` (or a custom directory you specify).

## Requirements

- Python 3.9+
- A Chromium browser managed by Playwright

## Setup

```bash
pip install playwright
playwright install chromium
```

## Usage

```bash
# Export to the default ./exported_notes/ directory
python export_apple_notes.py

# Export to a custom directory
python export_apple_notes.py ~/Desktop/my_notes
```

### What to expect

1. A browser window opens and navigates to iCloud Notes.
2. Sign in to iCloud if prompted (standard Apple ID login — credentials are not touched by this script).
3. Once your notes list is visible, return to the terminal and press **ENTER**.
4. The script iterates through every note and saves a numbered PDF for each one.

### Session persistence

After the first successful login, the script saves browser cookies to
`.icloud_session.json`. Subsequent runs will restore the session automatically,
skipping the login step (as long as the iCloud session is still valid).

> **Note:** `.icloud_session.json` contains your iCloud session cookies.
> Keep it private and do not commit it to version control.

### Re-running / incremental exports

PDFs that already exist on disk are skipped, so you can re-run the script to
pick up new notes without re-exporting everything.

## Output

```
exported_notes/
├── 001_Shopping_List.pdf
├── 002_Meeting_Notes.pdf
├── 003_Recipe_Ideas.pdf
└── ...
```

Files are numbered in the order they appear in the iCloud Notes sidebar.

## Troubleshooting

| Symptom | Fix |
|---|---|
| "Could not find any notes" | Make sure you are fully logged in and the Notes app is open in the browser before pressing ENTER. A `debug_screenshot.png` is saved to help diagnose. |
| PDFs are blank or cut off | The iCloud interface may have updated. Open an issue with the `debug_screenshot.png`. |
| Login loop / session expired | Delete `.icloud_session.json` and run again. |
| `playwright` not found | Run `pip install playwright && playwright install chromium`. |
