# Apple Notes PDF + PNG Exporter

Export **all** your Apple Notes as **PDF** and **PNG** files by automating [iCloud.com/notes](https://www.icloud.com/notes/) with Playwright.

---

## Features

- Headed Chromium browser (visible window) for easy first-run login
- Session saved to `.icloud_session.json` – login only once
- Lazy-scrolls the sidebar to discover **every** note, not just the visible ones
- Exports each note as:
  - **PDF** – via Playwright's `page.pdf()`
  - **PNG** – full note content area screenshot
- Skips already-exported notes (incremental runs)
- Handles untitled notes (`Untitled_1`, `Untitled_2`, …)
- Graceful per-note error handling – one failure never stops the rest
- Terminal progress display and final summary

---

## Output Structure

```
output/
├── pdf/
│   ├── My Note Title.pdf
│   └── ...
└── png/
    ├── My Note Title.png
    └── ...
```

---

## Requirements

| Requirement | Version |
|-------------|---------|
| [Node.js](https://nodejs.org/) | 18 or later |
| npm | bundled with Node.js |

> **Windows note:** all commands below run in **Command Prompt**, **PowerShell**, or **Windows Terminal**.

---

## Setup (Windows)

### 1. Install Node.js

Download and run the LTS installer from <https://nodejs.org/>.  
Verify installation:

```cmd
node --version
npm --version
```

### 2. Download / clone this project

```cmd
git clone https://github.com/your-username/apple-notes-exporter.git
cd apple-notes-exporter
```

Or just drop `index.js` and `package.json` into a folder of your choice and open a terminal there.

### 3. Install dependencies

```cmd
npm install
```

### 4. Install Playwright's Chromium browser

```cmd
npx playwright install chromium
```

---

## Running the Exporter

```cmd
node index.js
```

Or with the npm script:

```cmd
npm start
```

### First run (login required)

A **visible Chromium browser window** will open and navigate to iCloud.com.  
Log in with your Apple ID when prompted.  
Once the Notes app finishes loading the session is saved automatically to `.icloud_session.json`.

### Subsequent runs

The saved session is reused – no login needed unless the session expires.

---

## Incremental exports

If you run the tool again, any note that already has both a `.pdf` **and** a `.png` file in the output folders is **skipped** automatically.  
Delete the corresponding files (or the whole `output/` folder) to force a full re-export.

---

## Terminal output example

```
========================================
  Apple Notes PDF + PNG Exporter
========================================

[info] Using saved session – no login needed.

[info] Navigating to iCloud Notes…
[info] Waiting for Notes UI to fully load…
[info] Scrolling sidebar to discover all notes…
[info] Found 42 note(s) in the sidebar.

[1/42] "Grocery List"
  → PDF saved: output/pdf/Grocery List.pdf
  → PNG saved: output/png/Grocery List.png

[2/42] "Trip Planning"
  → Skipped (already exported)

...

========================================
  Export Summary
========================================
  Total notes  : 42
  Exported     : 40
  Skipped      : 1
  Failed       : 1
  Output folder: /path/to/output
========================================
```

---

## Troubleshooting

| Issue | Fix |
|-------|-----|
| Browser opens but notes never load | Manually navigate to Notes inside the browser window; the script will detect it and continue |
| Session expired – redirected to login | Delete `.icloud_session.json` and re-run; a fresh login will be saved |
| No notes found | iCloud may have updated its UI selectors; open an issue with a screenshot |
| PDF is blank | Some notes with complex formatting may not render perfectly in print mode |
| `Error: browserType.launch: …` on Windows | Run `npx playwright install chromium` to ensure the browser binary is installed |

---

## Notes

- This tool works with **iCloud.com** in a browser – it does **not** require macOS and does **not** access local Apple Notes databases.
- Two-factor authentication is handled interactively on first run; subsequent runs use the saved session.
- Apple may update iCloud's HTML structure at any time, which could require selector updates in `index.js`.

---

## License

MIT
