#!/usr/bin/env python3
"""List the interactive elements on a page with ready-to-use selectors.

  inspect_page.py http://localhost:3000/pricing [--mobile] [--storage-state state.json]

Use this BEFORE writing plan.json steps so selectors come from the real DOM
instead of guesses. Prints JSON: [{tag, text, selector, visible}, ...]
Selector preference: data-testid > #id > [name] > [aria-label] > text=.
"""
import argparse
import json
import sys

from common import default_viewport

JS = r"""
() => {
  const q = 'button, a[href], input, textarea, select, summary, [role=button], [role=tab], [role=switch], [data-testid]';
  const esc = (s) => s.replace(/"/g, '\\"');
  const out = [], seen = new Set();
  for (const el of document.querySelectorAll(q)) {
    const r = el.getBoundingClientRect();
    const visible = r.width > 4 && r.height > 4 && getComputedStyle(el).visibility !== 'hidden';
    const text = (el.innerText || el.value || '').trim().replace(/\s+/g, ' ').slice(0, 50);
    let sel = null;
    if (el.dataset.testid) sel = `[data-testid="${esc(el.dataset.testid)}"]`;
    else if (el.id && !/\d{3,}|:r/.test(el.id)) sel = '#' + CSS.escape(el.id);
    else if (el.getAttribute('name')) sel = `${el.tagName.toLowerCase()}[name="${esc(el.getAttribute('name'))}"]`;
    else if (el.getAttribute('aria-label')) sel = `[aria-label="${esc(el.getAttribute('aria-label'))}"]`;
    else if (text && ['BUTTON', 'A', 'SUMMARY'].includes(el.tagName)) sel = `${el.tagName.toLowerCase()}:has-text("${esc(text.slice(0, 30))}")`;
    else if (el.getAttribute('placeholder')) sel = `[placeholder="${esc(el.getAttribute('placeholder'))}"]`;
    if (!sel || seen.has(sel)) continue;
    seen.add(sel);
    out.push({tag: el.tagName.toLowerCase(), text, selector: sel, visible, y: Math.round(r.top + scrollY)});
  }
  return out.slice(0, 80);
}
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("url")
    ap.add_argument("--mobile", action="store_true")
    ap.add_argument("--storage-state")
    a = ap.parse_args()
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        b = p.chromium.launch()
        opts = {"viewport": default_viewport("vertical" if a.mobile else "landscape")}
        if a.mobile:
            opts.update(is_mobile=True, has_touch=True)
        if a.storage_state:
            opts["storage_state"] = a.storage_state
        pg = b.new_context(**opts).new_page()
        try:
            pg.goto(a.url, wait_until="load", timeout=15000)
            try:
                pg.wait_for_load_state("networkidle", timeout=3000)
            except Exception:
                pass
        except Exception as e:
            print(json.dumps({"error": str(e).splitlines()[0]}), file=sys.stderr)
            sys.exit(1)
        print(json.dumps({"title": pg.title(), "url": pg.url, "elements": pg.evaluate(JS)}, indent=1))
        b.close()


if __name__ == "__main__":
    main()
