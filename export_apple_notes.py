#!/usr/bin/env python3
"""
Apple Notes PDF Exporter
Exports all Apple Notes from iCloud web (icloud.com/notes) as individual PDF files.

Requirements:
    pip install playwright
    playwright install chromium
"""

import asyncio
import json
import re
import sys
from pathlib import Path
from datetime import datetime


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

ICLOUD_NOTES_URL = "https://www.icloud.com/notes/"
SESSION_FILE = Path(".icloud_session.json")

# Ordered lists of candidate selectors — first match wins.
NOTE_LIST_SELECTORS = [
    "li.note",
    '[data-testid="note-list-item"]',
    ".note-list-item",
    "li[class*='NoteListItem']",
    "li[class*='note-list']",
    "[class*='NoteListItem']",
    "[class*='noteListItem']",
    "ul.notes-list > li",
    ".notes-note-list-item",
]

TITLE_SELECTORS = [
    '[data-testid="note-title"]',
    ".note-title",
    "[class*='NoteTitle']",
    "[class*='noteTitle']",
    "h1",
    ".editor h1",
    "[contenteditable='true'] h1",
]

CONTENT_AREA_SELECTORS = [
    ".note-content",
    "[data-testid='note-content']",
    "[class*='NoteContent']",
    "[class*='noteContent']",
    ".editor",
    "[class*='Editor']",
    "[contenteditable='true']",
    "main",
]

# JavaScript injected before PDF rendering to hide navigation chrome.
HIDE_UI_JS = """
() => {
    const keepVisible = (el) => {
        // Walk up to see if this element is a descendant of the content area.
        const contentSelectors = [
            '.note-content', '[class*="NoteContent"]', '[class*="noteContent"]',
            '.editor', '[class*="Editor"]', '[contenteditable="true"]', 'main'
        ];
        for (const sel of contentSelectors) {
            const container = document.querySelector(sel);
            if (container && container.contains(el)) return true;
        }
        return false;
    };

    const hideSelectors = [
        '[class*="sidebar"]', '[class*="Sidebar"]',
        '[class*="nav"]',     '[class*="Nav"]',
        '[class*="toolbar"]', '[class*="Toolbar"]',
        '[class*="list"]',    '[class*="List"]',
        'header', 'nav', 'aside',
        '[class*="panel"]',   '[class*="Panel"]',
    ];

    for (const sel of hideSelectors) {
        document.querySelectorAll(sel).forEach(el => {
            if (!keepVisible(el)) {
                el.dataset._wasDisplay = el.style.display;
                el.style.setProperty('display', 'none', 'important');
            }
        });
    }
}
"""

RESTORE_UI_JS = """
() => {
    document.querySelectorAll('[data-_was-display]').forEach(el => {
        el.style.display = el.dataset._wasDisplay || '';
        delete el.dataset._wasDisplay;
    });
}
"""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def sanitize_filename(text: str, max_len: int = 80) -> str:
    """Return a filesystem-safe version of *text*."""
    text = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "", text)
    text = text.strip(". ")
    text = re.sub(r"\s+", "_", text)
    return text[:max_len] or "untitled"


async def find_elements(page, selectors: list[str]):
    """Try each selector in order; return the first non-empty result."""
    for sel in selectors:
        try:
            els = await page.query_selector_all(sel)
            if els:
                return sel, els
        except Exception:
            continue
    return None, []


async def find_element(page, selectors: list[str]):
    """Try each selector in order; return the first match."""
    for sel in selectors:
        try:
            el = await page.query_selector(sel)
            if el:
                return el
        except Exception:
            continue
    return None


async def save_session(context, path: Path) -> None:
    """Persist browser cookies/storage so the user doesn't have to re-login."""
    state = await context.storage_state()
    path.write_text(json.dumps(state, indent=2))


async def load_session(path: Path):
    """Return storage state dict if a saved session exists, else None."""
    if path.exists():
        try:
            return json.loads(path.read_text())
        except Exception:
            pass
    return None


# ---------------------------------------------------------------------------
# Core export logic
# ---------------------------------------------------------------------------

async def scroll_and_collect_notes(page, selector: str) -> list:
    """
    Scroll through the note list to trigger lazy-loading, then return all
    note elements found with *selector*.
    """
    # Scroll the note list container to load all notes.
    await page.evaluate(
        """
        async (selector) => {
            const items = document.querySelectorAll(selector);
            if (!items.length) return;

            // Find the scrollable ancestor of the first item.
            let container = items[0].parentElement;
            while (container && container !== document.body) {
                const style = window.getComputedStyle(container);
                if (['auto', 'scroll'].includes(style.overflowY)) break;
                container = container.parentElement;
            }
            if (!container) return;

            // Scroll to bottom in steps to trigger lazy loading.
            const step = container.clientHeight;
            for (let y = 0; y < container.scrollHeight; y += step) {
                container.scrollTop = y;
                await new Promise(r => setTimeout(r, 300));
            }
            container.scrollTop = 0;
        }
        """,
        selector,
    )
    await page.wait_for_timeout(500)
    return await page.query_selector_all(selector)


async def export_note(page, index: int, total: int, output_dir: Path) -> bool:
    """
    Export the currently displayed note to PDF.
    Returns True on success.
    """
    await page.wait_for_timeout(600)

    # Derive a title for the filename.
    title_el = await find_element(page, TITLE_SELECTORS)
    if title_el:
        raw_title = (await title_el.text_content() or "").strip()
    else:
        raw_title = ""

    safe_title = sanitize_filename(raw_title) if raw_title else f"note_{index:03d}"
    pdf_filename = f"{index:03d}_{safe_title}.pdf"
    pdf_path = output_dir / pdf_filename

    if pdf_path.exists():
        print(f"  [{index}/{total}] Skipping (already exported): {pdf_filename}")
        return True

    # Hide navigation chrome for a cleaner PDF.
    await page.evaluate(HIDE_UI_JS)
    await page.wait_for_timeout(200)

    try:
        await page.pdf(
            path=str(pdf_path),
            format="A4",
            print_background=True,
            margin={"top": "1.5cm", "bottom": "1.5cm",
                    "left": "1.5cm", "right": "1.5cm"},
        )
        print(f"  [{index}/{total}] Exported: {pdf_filename}")
        return True
    except Exception as e:
        print(f"  [{index}/{total}] ERROR exporting '{safe_title}': {e}")
        return False
    finally:
        # Restore UI so clicks on the list still work.
        await page.evaluate(RESTORE_UI_JS)


async def run_export(output_dir: Path) -> None:
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        print("Error: 'playwright' is not installed.")
        print("Run:  pip install playwright && playwright install chromium")
        sys.exit(1)

    output_dir.mkdir(parents=True, exist_ok=True)

    async with async_playwright() as p:
        # Restore a previous session if one exists.
        saved_state = await load_session(SESSION_FILE)

        browser = await p.chromium.launch(
            headless=False,
            args=["--start-maximized"],
        )
        context_kwargs = {
            "viewport": {"width": 1400, "height": 900},
        }
        if saved_state:
            context_kwargs["storage_state"] = saved_state
            print("Restored previous iCloud session.")

        context = await browser.new_context(**context_kwargs)
        page = await context.new_page()

        print(f"Opening {ICLOUD_NOTES_URL} …")
        await page.goto(ICLOUD_NOTES_URL, wait_until="domcontentloaded")

        # ------------------------------------------------------------------
        # Wait for the user to finish signing in.
        # ------------------------------------------------------------------
        print()
        print("═" * 60)
        print("  If you are not already signed in, please log in to iCloud")
        print("  in the browser window that just opened.")
        print()
        print("  When you can SEE your notes list, come back here and")
        print("  press ENTER to begin the export.")
        print("═" * 60)
        input("  Press ENTER when ready › ")
        print()

        await page.wait_for_timeout(1500)

        # Save the session so future runs skip the login step.
        await save_session(context, SESSION_FILE)

        # ------------------------------------------------------------------
        # Discover notes.
        # ------------------------------------------------------------------
        print("Scanning for notes …")
        matched_selector, note_elements = await find_elements(page, NOTE_LIST_SELECTORS)

        if not note_elements:
            print()
            print("Could not find any notes in the page.")
            print("Tips:")
            print("  • Make sure you are fully logged in and the Notes app is open.")
            print("  • The iCloud interface may have updated its HTML structure.")
            print("  • A debug screenshot was saved as 'debug_screenshot.png'.")
            await page.screenshot(path="debug_screenshot.png", full_page=True)
            await browser.close()
            return

        # Scroll to load lazily-rendered notes.
        note_elements = await scroll_and_collect_notes(page, matched_selector)
        total = len(note_elements)
        print(f"Found {total} note(s) using selector '{matched_selector}'.")
        print(f"Exporting to: {output_dir.resolve()}")
        print()

        exported, failed, skipped = 0, 0, 0

        for i, note_el in enumerate(note_elements, start=1):
            try:
                await note_el.scroll_into_view_if_needed()
                await note_el.click()
            except Exception as e:
                print(f"  [{i}/{total}] Could not click note: {e}")
                failed += 1
                continue

            ok = await export_note(page, i, total, output_dir)
            if ok:
                exported += 1
            else:
                failed += 1

        # ------------------------------------------------------------------
        # Summary
        # ------------------------------------------------------------------
        print()
        print("═" * 60)
        print(f"  Export complete — {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"  Exported : {exported}")
        print(f"  Skipped  : {skipped}  (already on disk)")
        print(f"  Failed   : {failed}")
        print(f"  Location : {output_dir.resolve()}")
        print("═" * 60)

        await browser.close()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    output_dir = Path("exported_notes")

    # Allow overriding output directory via CLI argument.
    if len(sys.argv) > 1:
        output_dir = Path(sys.argv[1])

    print()
    print("╔══════════════════════════════════════╗")
    print("║   Apple Notes → PDF Exporter         ║")
    print("╚══════════════════════════════════════╝")
    print()

    asyncio.run(run_export(output_dir))


if __name__ == "__main__":
    main()
