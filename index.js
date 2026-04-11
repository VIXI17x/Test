#!/usr/bin/env node

/**
 * Apple Notes PDF + PNG Exporter
 * Automates iCloud.com/notes via Playwright to export every note as PDF and PNG.
 */

const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');

// ─── Config ───────────────────────────────────────────────────────────────────
const SESSION_FILE = path.resolve('.icloud_session.json');
const OUTPUT_DIR   = path.resolve('output');
const PDF_DIR      = path.join(OUTPUT_DIR, 'pdf');
const PNG_DIR      = path.join(OUTPUT_DIR, 'png');
const NOTES_URL    = 'https://www.icloud.com/notes/';

// ─── Helpers ──────────────────────────────────────────────────────────────────

/** Make a string safe to use as a filename (Windows + Unix). */
function sanitizeFilename(name) {
  return name
    .replace(/[<>:"/\\|?*\x00-\x1F]/g, '_') // illegal chars
    .replace(/\s+/g, ' ')
    .trim()
    .substring(0, 200) // max length
    || 'Untitled';
}

/** Return true if both export files already exist for a given base name. */
function alreadyExported(baseName) {
  return (
    fs.existsSync(path.join(PDF_DIR, `${baseName}.pdf`)) &&
    fs.existsSync(path.join(PNG_DIR, `${baseName}.png`))
  );
}

/** Ensure output directories exist. */
function ensureDirs() {
  [OUTPUT_DIR, PDF_DIR, PNG_DIR].forEach(d => fs.mkdirSync(d, { recursive: true }));
}

/** Load stored cookies/storage state if available. */
function loadSession() {
  if (fs.existsSync(SESSION_FILE)) {
    try {
      return JSON.parse(fs.readFileSync(SESSION_FILE, 'utf8'));
    } catch {
      console.warn('[warn] Could not parse session file – starting fresh.');
    }
  }
  return null;
}

/** Persist the current browser storage state to disk. */
async function saveSession(context) {
  const state = await context.storageState();
  fs.writeFileSync(SESSION_FILE, JSON.stringify(state, null, 2));
}

// ─── Main ─────────────────────────────────────────────────────────────────────

async function main() {
  ensureDirs();

  const session = loadSession();
  const isFirstRun = !session;

  console.log('\n========================================');
  console.log('  Apple Notes PDF + PNG Exporter');
  console.log('========================================');

  if (isFirstRun) {
    console.log('\n[info] No saved session found.');
    console.log('[info] A browser window will open. Please log in to iCloud,');
    console.log('[info] then navigate to Notes. The session will be saved automatically.\n');
  } else {
    console.log('\n[info] Using saved session – no login needed.\n');
  }

  // Launch a HEADED (visible) Chromium browser
  const browser = await chromium.launch({
    headless: false,
    args: ['--start-maximized'],
  });

  const contextOptions = session
    ? { storageState: session, viewport: null }
    : { viewport: null };

  const context = await browser.newContext(contextOptions);
  const page = await context.newPage();

  // ── Navigate to Notes ────────────────────────────────────────────────────
  console.log('[info] Navigating to iCloud Notes…');
  await page.goto(NOTES_URL, { waitUntil: 'networkidle', timeout: 90_000 });

  // ── Handle login if needed ───────────────────────────────────────────────
  // Detect if we ended up on a login/sign-in page
  const currentUrl = page.url();
  if (
    currentUrl.includes('idmsa.apple.com') ||
    currentUrl.includes('appleid.apple.com') ||
    currentUrl.includes('signin') ||
    !currentUrl.includes('icloud.com/notes')
  ) {
    console.log('\n[action] Please log in to iCloud in the browser window.');
    console.log('[action] After logging in, navigate to Notes if not redirected automatically.');
    console.log('[action] Waiting for the Notes app to load (up to 5 minutes)…\n');

    // Wait until the notes sidebar appears (up to 5 minutes for manual login)
    await page.waitForURL('**/icloud.com/notes**', { timeout: 300_000 });
  }

  // ── Wait for the Notes UI to render ─────────────────────────────────────
  console.log('[info] Waiting for Notes UI to fully load…');
  await waitForNotesUI(page);

  // Save session after successful auth
  await saveSession(context);
  console.log('[info] Session saved to', SESSION_FILE);

  // ── Lazy-scroll sidebar to load ALL notes ────────────────────────────────
  console.log('[info] Scrolling sidebar to discover all notes…');
  const noteItems = await loadAllNoteItems(page);
  console.log(`[info] Found ${noteItems.length} note(s) in the sidebar.\n`);

  if (noteItems.length === 0) {
    console.log('[warn] No notes found. Exiting.');
    await browser.close();
    return;
  }

  // ── Export loop ──────────────────────────────────────────────────────────
  let exported = 0;
  let skipped  = 0;
  let failed   = 0;
  const untitledCounter = {};

  for (let i = 0; i < noteItems.length; i++) {
    const rawTitle = (noteItems[i].title || '').trim() || '';
    let baseName;

    if (!rawTitle) {
      // Untitled note – generate a unique name
      untitledCounter['_'] = (untitledCounter['_'] || 0) + 1;
      baseName = `Untitled_${untitledCounter['_']}`;
    } else {
      baseName = sanitizeFilename(rawTitle);
    }

    // De-duplicate: if another note produced the same baseName, append index
    const dedupeKey = baseName.toLowerCase();
    if (!untitledCounter[dedupeKey]) {
      untitledCounter[dedupeKey] = 1;
    } else {
      untitledCounter[dedupeKey]++;
      baseName = `${baseName}_${untitledCounter[dedupeKey]}`;
    }

    const displayTitle = rawTitle || baseName;
    console.log(`[${i + 1}/${noteItems.length}] "${displayTitle}"`);

    // Skip if both files already exported
    if (alreadyExported(baseName)) {
      console.log(`  → Skipped (already exported)\n`);
      skipped++;
      continue;
    }

    try {
      // Click the note in the sidebar and wait for content
      await clickNote(page, noteItems[i].locator);

      // Export PDF
      const pdfPath = path.join(PDF_DIR, `${baseName}.pdf`);
      await page.pdf({
        path: pdfPath,
        format: 'A4',
        printBackground: true,
        margin: { top: '20px', bottom: '20px', left: '20px', right: '20px' },
      });
      console.log(`  → PDF saved: ${pdfPath}`);

      // Export PNG (full note content area)
      const pngPath = path.join(PNG_DIR, `${baseName}.png`);
      await captureNoteScreenshot(page, pngPath);
      console.log(`  → PNG saved: ${pngPath}\n`);

      exported++;
    } catch (err) {
      console.error(`  ✗ Error exporting "${displayTitle}": ${err.message}\n`);
      failed++;
    }
  }

  // ── Summary ──────────────────────────────────────────────────────────────
  console.log('========================================');
  console.log('  Export Summary');
  console.log('========================================');
  console.log(`  Total notes  : ${noteItems.length}`);
  console.log(`  Exported     : ${exported}`);
  console.log(`  Skipped      : ${skipped}`);
  console.log(`  Failed       : ${failed}`);
  console.log(`  Output folder: ${OUTPUT_DIR}`);
  console.log('========================================\n');

  await browser.close();
}

// ─── Notes UI helpers ─────────────────────────────────────────────────────────

/**
 * Wait for the Notes sidebar list to appear.
 * iCloud Notes renders inside a shadow-DOM-heavy Angular/React shell;
 * we target the note list container by the most stable selectors we know.
 */
async function waitForNotesUI(page) {
  // Try several known selectors for the notes list container
  const candidates = [
    '[data-testid="notes-list"]',
    '.notes-list',
    'ul.NotesList',
    '[class*="NotesList"]',
    '[class*="note-list"]',
    '[class*="notes-list"]',
    '.note-list-container',
    // Generic fallback: any <ul> or <ol> inside the main content area
    'main ul',
    '[role="list"]',
  ];

  for (const selector of candidates) {
    try {
      await page.waitForSelector(selector, { timeout: 15_000 });
      console.log(`[info] Notes list detected via: ${selector}`);
      return;
    } catch {
      // try next
    }
  }

  // Last resort: wait for navigation to settle
  console.log('[warn] Could not identify notes list selector – waiting 5s for page to settle…');
  await page.waitForTimeout(5_000);
}

/**
 * Repeatedly scroll the notes sidebar until no new notes appear.
 * Returns an array of { title, locator } objects.
 */
async function loadAllNoteItems(page) {
  // Selectors for individual note list items
  const itemSelectors = [
    '[data-testid="note-list-item"]',
    '.NotesList--item',
    '[class*="NoteListItem"]',
    '[class*="note-list-item"]',
    '[class*="notes-list-item"]',
    'li[data-note-id]',
    // Broader fallback
    '[role="listitem"]',
  ];

  let listItemSelector = null;

  // Identify which selector is live on the page
  for (const sel of itemSelectors) {
    const count = await page.locator(sel).count();
    if (count > 0) {
      listItemSelector = sel;
      console.log(`[info] Using note item selector: ${sel} (${count} found initially)`);
      break;
    }
  }

  if (!listItemSelector) {
    console.warn('[warn] Could not auto-detect note item selector. Attempting heuristic scroll…');
    await scrollSidebarHeuristic(page);
    // Re-check after scroll
    for (const sel of itemSelectors) {
      const count = await page.locator(sel).count();
      if (count > 0) {
        listItemSelector = sel;
        break;
      }
    }
    if (!listItemSelector) {
      console.error('[error] No note items found. The iCloud Notes UI may have changed.');
      return [];
    }
  }

  // Scroll the sidebar until the count stabilises
  let prevCount = 0;
  let stableRounds = 0;
  const MAX_STABLE = 3; // three rounds with no new notes = done

  while (stableRounds < MAX_STABLE) {
    const currentCount = await page.locator(listItemSelector).count();
    if (currentCount === prevCount) {
      stableRounds++;
    } else {
      stableRounds = 0;
      prevCount = currentCount;
    }

    // Scroll the last visible item into view to trigger lazy load
    if (currentCount > 0) {
      await page.locator(listItemSelector).last().scrollIntoViewIfNeeded();
    }
    await page.waitForTimeout(600);
  }

  // Collect title + locator for each note
  const locators = page.locator(listItemSelector);
  const total = await locators.count();
  const notes = [];

  for (let i = 0; i < total; i++) {
    const loc = locators.nth(i);
    // Try several ways to extract the title
    let title = '';
    const titleSelectors = [
      '[class*="title"]',
      '[class*="Title"]',
      '[class*="name"]',
      '[data-testid*="title"]',
      'span',
      'p',
    ];
    for (const ts of titleSelectors) {
      try {
        const el = loc.locator(ts).first();
        const t = await el.innerText({ timeout: 1_000 });
        if (t && t.trim()) {
          title = t.trim().split('\n')[0]; // first line only
          break;
        }
      } catch {
        // continue
      }
    }

    // Fallback: innerText of the whole item
    if (!title) {
      try {
        const full = await loc.innerText({ timeout: 1_000 });
        title = full.trim().split('\n')[0];
      } catch {
        title = '';
      }
    }

    notes.push({ title, locator: loc });
  }

  return notes;
}

/** Fallback: scroll the left-side panel by coordinates. */
async function scrollSidebarHeuristic(page) {
  const vp = page.viewportSize() || { width: 1280, height: 800 };
  // Notes sidebar is typically the left ~25% of the screen
  const x = Math.round(vp.width * 0.15);
  const y = Math.round(vp.height * 0.5);

  for (let i = 0; i < 20; i++) {
    await page.mouse.wheel(0, 800); // scroll down
    await page.waitForTimeout(400);
  }
}

/**
 * Click a note in the sidebar and wait for its content to render.
 */
async function clickNote(page, locator) {
  await locator.click({ timeout: 10_000 });

  // Wait for note content area to appear / update
  const contentSelectors = [
    '[data-testid="note-content"]',
    '.note-content',
    '[class*="NoteContent"]',
    '[class*="note-content"]',
    '[contenteditable="true"]',
    '.note-editor',
    '[class*="editor"]',
    '[role="main"] [class*="content"]',
  ];

  for (const sel of contentSelectors) {
    try {
      await page.waitForSelector(sel, { timeout: 8_000 });
      return;
    } catch {
      // try next
    }
  }

  // Fallback: give the page a moment to render
  await page.waitForTimeout(1_500);
}

/**
 * Screenshot the note content area (full height).
 * Falls back to a full-page screenshot if the content element can't be found.
 */
async function captureNoteScreenshot(page, outputPath) {
  const contentSelectors = [
    '[data-testid="note-content"]',
    '.note-content',
    '[class*="NoteContent"]',
    '[class*="note-content"]',
    '[contenteditable="true"]',
    '.note-editor',
    '[class*="editor"]',
  ];

  for (const sel of contentSelectors) {
    try {
      const el = page.locator(sel).first();
      const count = await el.count();
      if (count === 0) continue;

      await el.screenshot({ path: outputPath });
      return;
    } catch {
      // try next
    }
  }

  // Full-page fallback
  await page.screenshot({ path: outputPath, fullPage: true });
}

// ─── Entry point ──────────────────────────────────────────────────────────────
main().catch(err => {
  console.error('\n[fatal]', err.message);
  process.exit(1);
});
