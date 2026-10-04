#!/usr/bin/env python3
"""Render a release announcement video from a plan.json.

  make_video.py plan.json -o out.mp4

Pipeline: validate plan -> extract site theme color -> render intro/outro
cards (Playwright screenshots) -> record each feature flow in headless
Chromium (injected cursor, sparkle/ripple/glow click effects, smooth page
transitions, captions, spotlight) -> TTS voice-over via edge-tts -> encode
and crossfade everything with ffmpeg -> write a contact sheet PNG.

Requires: python3, playwright (+ chromium), ffmpeg/ffprobe on PATH.
Optional:  edge-tts (pip install edge-tts) for voice-over.
Plan format: see references/plan-format.md

New plan.json fields (all optional):
  click_effect      "ripple" (default) | "sparkle" | "glow"
  nav_transition    "fade" (default) | "slide" | "zoom"
  voiceover         false (default) | true  -- requires edge-tts
  voiceover_voice   edge-tts voice name, default "en-US-AriaNeural"
  custom_effects    list of {effect, selector} objects applied on every page
                    effect: "sparkle" | "glow" | "pulse"
"""
import argparse
import asyncio
import html
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ACTIONS = {"goto", "wait", "click", "type", "press", "hover", "scroll", "highlight", "caption"}
FPS = 30
XFADE = 0.4


# --------------------------------------------------------------------------- plan

def die(msg, code=2):
    print(json.dumps({"ok": False, "error": msg}, indent=2), file=sys.stderr)
    sys.exit(code)


def load_plan(path):
    plan = json.loads(Path(path).read_text())
    for key in ("product", "headline", "features"):
        if not plan.get(key):
            die(f"plan is missing required field '{key}'")
    plan.setdefault("version", "")
    plan.setdefault("subhead", "")
    plan.setdefault("accent", "#6366f1")
    plan.setdefault("bullets", [])
    plan.setdefault("cta", "")
    plan.setdefault("format", "landscape")
    plan.setdefault("intro_seconds", 3.0)
    plan.setdefault("outro_seconds", 3.5)
    # New fields
    plan.setdefault("click_effect", "ripple")      # ripple | sparkle | glow
    plan.setdefault("nav_transition", "fade")       # fade | slide | zoom
    plan.setdefault("voiceover", False)             # needs edge-tts
    plan.setdefault("voiceover_voice", "en-US-AriaNeural")
    plan.setdefault("custom_effects", [])           # [{effect, selector}, ...]
    if plan["format"] not in ("landscape", "vertical"):
        die("format must be 'landscape' or 'vertical'")
    vertical = plan["format"] == "vertical"
    plan.setdefault("viewport", {"width": 540, "height": 960} if vertical else {"width": 1280, "height": 720})
    plan.setdefault("cursor", "tap" if vertical else "arrow")
    if plan["cursor"] not in ("arrow", "tap", "none"):
        die("cursor must be 'arrow', 'tap' or 'none'")
    if plan["click_effect"] not in ("ripple", "sparkle", "glow"):
        die("click_effect must be 'ripple', 'sparkle' or 'glow'")
    if plan["nav_transition"] not in ("fade", "slide", "zoom"):
        die("nav_transition must be 'fade', 'slide' or 'zoom'")
    base = plan.get("base_url", "").rstrip("/")
    plan["base_url"] = base
    for i, feat in enumerate(plan["features"]):
        steps = feat.get("steps") or []
        if not steps:
            die(f"feature {i} has no steps")
        for j, s in enumerate(steps):
            a = s.get("action")
            if a not in ACTIONS:
                die(f"feature {i} step {j}: unknown action '{a}'. Valid: {sorted(ACTIONS)}")
            need = {"goto": "url", "click": "selector", "type": "selector", "press": "key",
                    "hover": "selector", "highlight": "selector"}.get(a)
            if need and need not in s:
                die(f"feature {i} step {j} ({a}) needs '{need}'")
            if a == "type" and "text" not in s:
                die(f"feature {i} step {j} (type) needs 'text'")
            if a == "scroll" and "y" not in s and "to" not in s:
                die(f"feature {i} step {j} (scroll) needs 'y' or 'to'")
        if steps[0]["action"] != "goto":
            if not base:
                die(f"feature {i} must start with a goto step (or set base_url)")
            steps.insert(0, {"action": "goto", "url": "/"})
        feat["steps"] = steps
    return plan


def abs_url(plan, url):
    if url.startswith(("http://", "https://", "file://")):
        return url
    return plan["base_url"] + (url if url.startswith("/") else "/" + url)


# --------------------------------------------------------------------------- theme extraction

def extract_site_theme(url, plan):
    """Visit the live site and extract the dominant brand/accent color.

    Priority:
      1. CSS custom properties: --primary, --accent, --brand, --color-primary, etc.
      2. Background color of first <nav> or <header>
      3. Background of first button[class*=primary]
      4. Fallback: plan["accent"] unchanged.
    """
    if not url:
        return plan["accent"]
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return plan["accent"]

    result = None
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            vp = plan["viewport"]
            ctx = browser.new_context(viewport=vp)
            page = ctx.new_page()
            page.goto(url, wait_until="load", timeout=12000)
            try:
                page.wait_for_load_state("networkidle", timeout=3000)
            except Exception:
                pass
            result = page.evaluate("""() => {
                const root = document.documentElement;
                const cs = getComputedStyle(root);
                const vars = ['--primary','--accent','--brand','--color-primary',
                              '--color-accent','--theme-color','--brand-color',
                              '--primary-color','--main-color'];
                for (const v of vars) {
                    const val = cs.getPropertyValue(v).trim();
                    if (val && (val.startsWith('#') || val.startsWith('rgb'))) return val;
                }
                const navEl = document.querySelector('nav, header, [class*=nav], [class*=header]');
                if (navEl) {
                    const bg = getComputedStyle(navEl).backgroundColor;
                    if (bg && bg !== 'rgba(0, 0, 0, 0)' && bg !== 'transparent') return bg;
                }
                const btn = document.querySelector(
                    'button[class*=primary], a[class*=primary], .btn-primary, [class*=btn-primary]');
                if (btn) {
                    const bg = getComputedStyle(btn).backgroundColor;
                    if (bg && bg !== 'rgba(0, 0, 0, 0)' && bg !== 'transparent') return bg;
                }
                return null;
            }""")
            browser.close()
    except Exception as exc:
        print(f"[theme] Could not extract site theme: {exc}", file=sys.stderr)

    if result:
        import re
        m = re.match(r"rgb\((\d+),\s*(\d+),\s*(\d+)\)", result)
        if m:
            r2, g, b = int(m.group(1)), int(m.group(2)), int(m.group(3))
            # Skip near-white or near-black (transparent fallback artifacts)
            if not (r2 > 230 and g > 230 and b > 230) and not (r2 < 20 and g < 20 and b < 20):
                result = f"#{r2:02x}{g:02x}{b:02x}"
            else:
                result = None
        if result and result.startswith("#") and len(result) >= 7:
            print(f"[theme] Extracted site accent: {result}", file=sys.stderr)
            return result

    return plan["accent"]


# --------------------------------------------------------------------------- cards

CARD_CSS = """
*{box-sizing:border-box;margin:0;padding:0}
html,body{width:%(W)dpx;height:%(H)dpx;overflow:hidden}
body{font-family:'Inter','Noto Sans','Segoe UI','Helvetica Neue',Arial,'DejaVu Sans',sans-serif;
  color:#f5f6fa;background:#0b0d17;position:relative;display:flex;flex-direction:column;
  justify-content:center;padding:%(pad)dpx}
body::before{content:'';position:absolute;inset:0;
  background:radial-gradient(900px 700px at 85%% 10%%,%(accent)s55,transparent 60%%),
             radial-gradient(800px 600px at 5%% 95%%,%(accent)s33,transparent 60%%)}
.wrap{position:relative;z-index:1}
.brand{display:flex;align-items:center;gap:%(u16)dpx;font-weight:700;font-size:%(u34)dpx;letter-spacing:.01em}
.brand img{height:%(u52)dpx;border-radius:%(u10)dpx}
.dot{width:%(u18)dpx;height:%(u18)dpx;border-radius:50%%;background:%(accent)s;box-shadow:0 0 %(u24)dpx %(accent)s}
.ver{margin-left:%(u8)dpx;padding:%(u6)dpx %(u18)dpx;border-radius:999px;background:%(accent)s26;
  border:2px solid %(accent)s;font-size:%(u26)dpx;font-weight:600;color:#fff}
h1{font-size:%(u92)dpx;line-height:1.08;font-weight:800;margin-top:%(u40)dpx;letter-spacing:-.02em;max-width:%(maxw)dpx}
h1 em{font-style:normal;color:%(accent)s}
.sub{font-size:%(u38)dpx;line-height:1.35;margin-top:%(u28)dpx;color:#b9bdd0;max-width:%(maxw)dpx}
h2{font-size:%(u64)dpx;font-weight:800;letter-spacing:-.01em;margin:%(u30)dpx 0 %(u36)dpx}
ul{list-style:none;display:flex;flex-direction:column;gap:%(u22)dpx;max-width:%(maxw)dpx}
li{font-size:%(u40)dpx;line-height:1.3;display:flex;gap:%(u22)dpx;align-items:flex-start}
li::before{content:'\\2713';flex:none;width:%(u52)dpx;height:%(u52)dpx;border-radius:50%%;background:%(accent)s;
  color:#fff;font-size:%(u32)dpx;font-weight:800;display:flex;align-items:center;justify-content:center;margin-top:2px}
.cta{margin-top:%(u56)dpx;display:inline-block;align-self:flex-start;padding:%(u18)dpx %(u40)dpx;border-radius:999px;
  background:%(accent)s;color:#fff;font-size:%(u40)dpx;font-weight:700;box-shadow:0 %(u10)dpx %(u40)dpx %(accent)s66}
"""


def card_html(kind, plan, W, H, logo_uri):
    vertical = plan["format"] == "vertical"
    unit = W / (1080 if vertical else 1920)
    u = {f"u{n}": round(n * unit) for n in (6, 8, 10, 16, 18, 22, 24, 26, 28, 30, 32, 34, 36, 38, 40, 52, 56, 64, 92)}
    if vertical:
        u["u92"] = round(100 * unit)  # tall canvas can take a slightly bigger headline
    css = CARD_CSS % {"W": W, "H": H, "pad": round((120 if not vertical else 90) * unit),
                      "accent": plan["accent"], "maxw": round((1500 if not vertical else 900) * unit), **u}
    e = html.escape
    logo = f'<img src="{logo_uri}">' if logo_uri else '<span class="dot"></span>'
    ver = f'<span class="ver">{e(plan["version"])}</span>' if plan["version"] else ""
    brand = f'<div class="brand">{logo}<span>{e(plan["product"])}</span>{ver}</div>'
    if kind == "intro":
        sub = f'<div class="sub">{e(plan["subhead"])}</div>' if plan["subhead"] else ""
        body = f'{brand}<h1>{e(plan["headline"])}</h1>{sub}'
    else:
        bullets = plan["bullets"] or [f["caption"] for f in plan["features"] if f.get("caption")]
        items = "".join(f"<li><span>{e(b)}</span></li>" for b in bullets[:5])
        title = f"What's new in {e(plan['version'])}" if plan["version"] else "What's new"
        cta = f'<div class="cta">{e(plan["cta"])}</div>' if plan["cta"] else ""
        body = f'{brand}<h2>{title}</h2><ul>{items}</ul>{cta}'
    return f'<!doctype html><meta charset="utf-8"><style>{css}</style><body><div class="wrap">{body}</div></body>'


# --------------------------------------------------------------------------- overlay JS (cursor, effects, transitions)

# Extra CSS blocks injected conditionally based on plan settings
_SPARKLE_CSS = r"""
  .__rv_spark{position:fixed;z-index:2147483646;pointer-events:none;width:6px;height:6px;
    border-radius:50%;animation:__rv_spark .55s ease-out forwards}
  @keyframes __rv_spark{0%{transform:translate(0,0) scale(1);opacity:1}
    100%{transform:translate(var(--dx),var(--dy)) scale(0);opacity:0}}"""

_GLOW_CSS = r"""
  .__rv_glow{position:fixed;z-index:2147483646;pointer-events:none;border-radius:50%;
    width:60px;height:60px;margin:-30px 0 0 -30px;
    background:radial-gradient(circle,var(--gclr) 0%,transparent 70%);
    animation:__rv_glow .7s ease-out forwards}
  @keyframes __rv_glow{0%{transform:scale(.3);opacity:.95}100%{transform:scale(2.8);opacity:0}}"""

_NAV_CSS = r"""
  #__rv_nav_veil{position:fixed;inset:0;z-index:2147483640;pointer-events:none;
    background:#000;opacity:0;transition:opacity 0.25s ease}
  #__rv_nav_veil.on{opacity:1}"""

OVERLAY_JS = r"""
(() => {
  if (window.top !== window || window.__rv) return;
  window.__rv = true;
  const ACCENT = '__ACCENT__', CAP = __CAP__, CURSOR = '__CURSOR__',
        CLICK_FX = '__CLICK_FX__';

  /* ---- sparkle ---- */
  const SPARKLE_COLORS = [ACCENT, '#fff', '#ffe066', '#ff6ee8', '#6ef8ff'];
  function spawnSparkles(x, y) {
    const count = 14;
    for (let i = 0; i < count; i++) {
      const el = document.createElement('div'); el.className = '__rv_spark';
      const angle = (2 * Math.PI * i) / count + (Math.random() - 0.5) * 0.6;
      const dist = 28 + Math.random() * 38;
      el.style.setProperty('--dx', Math.cos(angle) * dist + 'px');
      el.style.setProperty('--dy', Math.sin(angle) * dist + 'px');
      el.style.left = x + 'px'; el.style.top = y + 'px';
      el.style.background = SPARKLE_COLORS[i % SPARKLE_COLORS.length];
      el.style.animationDelay = (Math.random() * 0.08) + 's';
      document.documentElement.appendChild(el);
      setTimeout(() => el.remove(), 700);
    }
  }

  /* ---- glow ---- */
  function spawnGlow(x, y) {
    const el = document.createElement('div'); el.className = '__rv_glow';
    el.style.left = x + 'px'; el.style.top = y + 'px';
    el.style.setProperty('--gclr', ACCENT + 'cc');
    document.documentElement.appendChild(el);
    setTimeout(() => el.remove(), 800);
  }

  /* ---- veil for nav transitions ---- */
  function ensureVeil() {
    if (document.getElementById('__rv_nav_veil')) return;
    const v = document.createElement('div'); v.id = '__rv_nav_veil';
    document.documentElement.appendChild(v);
  }

  /* ---- CSS ---- */
  const baseCss = `
  #__rv_cur{position:fixed;left:0;top:0;z-index:2147483647;pointer-events:none;opacity:0;width:26px;height:26px}
  #__rv_cur svg{filter:drop-shadow(0 2px 3px rgba(0,0,0,.5))}
  .__rv_rip{position:fixed;z-index:2147483646;pointer-events:none;width:18px;height:18px;margin:-9px 0 0 -9px;
    border-radius:50%;border:4px solid ${ACCENT};background:${ACCENT}33;animation:__rv_rip .6s ease-out forwards}
  @keyframes __rv_rip{from{transform:scale(.4);opacity:1}to{transform:scale(3.4);opacity:0}}
  #__rv_cap{position:fixed;left:50%;bottom:7%;width:max-content;z-index:2147483647;pointer-events:none;max-width:92%;
    padding:12px 24px;border-radius:14px;background:rgba(10,12,22,.9);color:#fff;text-align:center;
    font:600 ${CAP}px/1.35 Inter,'Noto Sans',system-ui,-apple-system,'Segoe UI',Arial,sans-serif;
    box-shadow:0 10px 34px rgba(0,0,0,.4);border:1px solid rgba(255,255,255,.14);
    opacity:0;transform:translate(-50%,10px);transition:opacity .35s,transform .35s}
  #__rv_cap.on{opacity:1;transform:translate(-50%,0)}
  .__rv_hl{position:fixed;z-index:2147483645;pointer-events:none;border:4px solid ${ACCENT};border-radius:12px;
    box-shadow:0 0 0 9999px rgba(8,10,20,.45);opacity:0;transition:opacity .35s}
  .__rv_hl.on{opacity:1}
  __EXTRA_CSS__`;

  const mount = () => {
    const root = document.documentElement;
    const st = document.createElement('style'); st.textContent = baseCss; root.appendChild(st);
    const cap = document.createElement('div'); cap.id = '__rv_cap'; root.appendChild(cap);
    ensureVeil();

    window.__rvCaption = (t) => {
      try { sessionStorage.setItem('__rv_cap', t || ''); } catch (e) {}
      cap.textContent = t || ''; cap.classList.toggle('on', !!t);
    };
    window.__rvRipple = (x, y) => {
      const r = document.createElement('div'); r.className = '__rv_rip';
      r.style.left = x + 'px'; r.style.top = y + 'px'; root.appendChild(r);
      setTimeout(() => r.remove(), 700);
    };
    window.__rvClickEffect = (x, y) => {
      if (CLICK_FX === 'sparkle') spawnSparkles(x, y);
      else if (CLICK_FX === 'glow') spawnGlow(x, y);
      else window.__rvRipple(x, y);
    };
    window.__rvClickAnim = (x, y) => {
      try {
        const el = document.elementFromPoint(x, y);
        if (!el) return;
        const target = el.closest('button, a, input, div[role=button], .ant-btn, summary') || el;
        const prevTrans = target.style.transition;
        const prevTrf = target.style.transform;
        target.style.transition = 'transform 0.28s cubic-bezier(0.34, 1.56, 0.64, 1), box-shadow 0.28s ease';
        target.style.transform = (prevTrf ? prevTrf + ' ' : '') + 'scale(1.08)';
        setTimeout(() => {
          target.style.transform = prevTrf;
          setTimeout(() => { target.style.transition = prevTrans; }, 300);
        }, 350);
      } catch (e) {}
    };
    window.__rvSpot = (b, ms) => {
      const h = document.createElement('div'); h.className = '__rv_hl';
      const p = 8; h.style.left = (b.x - p) + 'px'; h.style.top = (b.y - p) + 'px';
      h.style.width = (b.width + 2 * p) + 'px'; h.style.height = (b.height + 2 * p) + 'px';
      root.appendChild(h); requestAnimationFrame(() => h.classList.add('on'));
      setTimeout(() => h.classList.remove('on'), Math.max(ms - 350, 100));
      setTimeout(() => h.remove(), ms + 100);
    };
    /* nav veil control (called from Python side via page.evaluate) */
    window.__rvNavIn = () => {
      const v = document.getElementById('__rv_nav_veil'); if (!v) return;
      v.style.transition = 'opacity 0.22s ease'; v.classList.add('on');
    };
    window.__rvNavOut = () => {
      const v = document.getElementById('__rv_nav_veil'); if (!v) return;
      v.style.transition = 'opacity 0.28s ease'; v.classList.remove('on');
    };
    /* custom per-element effects from plan.custom_effects */
    window.__rvApplyCustomEffects = (effects) => {
      if (!effects || !effects.length) return;
      effects.forEach(eff => {
        document.querySelectorAll(eff.selector).forEach(el => {
          if (eff.effect === 'sparkle') {
            el.addEventListener('click', ev => spawnSparkles(ev.clientX, ev.clientY), {capture: true});
          } else if (eff.effect === 'glow') {
            el.addEventListener('click', ev => spawnGlow(ev.clientX, ev.clientY), {capture: true});
          } else if (eff.effect === 'pulse') {
            const uid = '__rvP' + Math.random().toString(36).slice(2);
            const kf = `@keyframes ${uid}{0%{box-shadow:0 0 0 0 ${ACCENT}88}70%{box-shadow:0 0 0 12px transparent}100%{box-shadow:0 0 0 0 transparent}}`;
            const s = document.createElement('style'); s.textContent = kf; document.head.appendChild(s);
            el.style.animation = uid + ' 1.5s infinite';
          }
        });
      });
    };
    if (CURSOR === 'arrow') {
      const c = document.createElement('div'); c.id = '__rv_cur';
      c.innerHTML = '<svg width="26" height="26" viewBox="0 0 24 24"><path d="M4 2l15 9.2-6.4 1.5L16 20l-3 1.3-3.4-7.4L4 17.5z" fill="#fff" stroke="#111" stroke-width="1.4" stroke-linejoin="round"/></svg>';
      root.appendChild(c);
      const place = (x, y) => { c.style.transform = `translate(${x - 4}px,${y - 2}px)`; c.style.opacity = 1;
        try { sessionStorage.setItem('__rv_pos', x + ',' + y); } catch (e) {} };
      try { const p = (sessionStorage.getItem('__rv_pos') || '').split(','); if (p.length === 2) place(+p[0], +p[1]); } catch (e) {}
      addEventListener('mousemove', (ev) => place(ev.clientX, ev.clientY), true);
    }
    try { const t = sessionStorage.getItem('__rv_cap'); if (t) window.__rvCaption(t); } catch (e) {}
  };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', mount); else mount();
})();
"""

SMOOTH_SCROLL_JS = """([dy, dur]) => new Promise(res => {
  const y0 = window.scrollY, t0 = performance.now();
  const ease = t => t < .5 ? 2*t*t : 1 - Math.pow(-2*t + 2, 2) / 2;
  const step = now => { const t = Math.min(1, (now - t0) / dur);
    window.scrollTo(0, y0 + dy * ease(t)); t < 1 ? requestAnimationFrame(step) : res(); };
  requestAnimationFrame(step); })"""


def overlay_script(plan):
    vw = plan["viewport"]["width"]
    cap_px = round(max(20, min(30, vw * 0.021)))
    click_fx = plan.get("click_effect", "ripple")
    extra_css = _NAV_CSS
    if click_fx == "sparkle":
        extra_css += _SPARKLE_CSS
    elif click_fx == "glow":
        extra_css += _GLOW_CSS
    return (OVERLAY_JS
            .replace("__ACCENT__", plan["accent"])
            .replace("__CAP__", str(cap_px))
            .replace("__CURSOR__", plan["cursor"])
            .replace("__CLICK_FX__", click_fx)
            .replace("__EXTRA_CSS__", extra_css))


# --------------------------------------------------------------------------- nav transitions

def nav_transition_in(page, nav_fx):
    """Overlay the veil before navigation (fade/slide/zoom are all opacity-based for now)."""
    try:
        page.evaluate("() => window.__rvNavIn && window.__rvNavIn()")
        page.wait_for_timeout(260)
    except Exception:
        pass


def nav_transition_out(page, nav_fx):
    """Remove the veil after the new page has rendered."""
    try:
        page.evaluate("() => window.__rvNavOut && window.__rvNavOut()")
        page.wait_for_timeout(320)
    except Exception:
        pass


# --------------------------------------------------------------------------- recording

def move_to(page, box, plan):
    x, y = box["x"] + box["width"] / 2, box["y"] + box["height"] / 2
    page.mouse.move(x, y, steps=28)
    page.wait_for_timeout(220)
    return x, y


def run_step(page, plan, step):
    a = step["action"]
    nav_fx = plan.get("nav_transition", "fade")
    if "caption" in step and a != "caption":
        page.evaluate("t => window.__rvCaption && window.__rvCaption(t)", step["caption"])
    if a == "goto":
        nav_transition_in(page, nav_fx)
        page.goto(abs_url(plan, step["url"]), wait_until="load")
        nav_transition_out(page, nav_fx)
    elif a == "wait":
        page.wait_for_timeout(int(step.get("ms", 800)))
    elif a in ("click", "hover", "type"):
        loc = page.locator(step["selector"]).first
        loc.wait_for(state="visible")
        loc.scroll_into_view_if_needed()
        page.wait_for_timeout(150)
        x, y = move_to(page, loc.bounding_box(), plan)
        if a == "hover":
            page.wait_for_timeout(int(step.get("ms", 600)))
        else:
            if plan["cursor"] != "none":
                page.evaluate(
                    "([x,y]) => { window.__rvClickEffect && window.__rvClickEffect(x,y); "
                    "window.__rvClickAnim && window.__rvClickAnim(x,y); }",
                    [x, y])
            page.mouse.click(x, y)
            if a == "type":
                if step.get("clear"):
                    page.keyboard.press("Control+A")
                page.keyboard.type(step["text"], delay=int(step.get("delay_ms", 70)))
    elif a == "press":
        page.keyboard.press(step["key"])
    elif a == "scroll":
        dur = int(step.get("ms", 900))
        if "to" in step:
            dy = page.evaluate("""s => { const el = document.querySelector(s);
                return el ? el.getBoundingClientRect().top - innerHeight * 0.2 : 0 }""", step["to"])
        else:
            dy = step["y"]
        page.evaluate(SMOOTH_SCROLL_JS, [dy, dur])
    elif a == "highlight":
        loc = page.locator(step["selector"]).first
        loc.wait_for(state="visible")
        loc.scroll_into_view_if_needed()
        page.wait_for_timeout(250)
        ms = int(step.get("ms", 1500))
        page.evaluate("([b,ms]) => window.__rvSpot && window.__rvSpot(b,ms)", [loc.bounding_box(), ms])
        page.wait_for_timeout(ms + 150)
    elif a == "caption":
        page.evaluate("t => window.__rvCaption && window.__rvCaption(t)", step.get("text", ""))
        page.wait_for_timeout(int(step.get("ms", 900)))
    done = time.monotonic()  # moment the action itself finished, before the breathing pause
    page.wait_for_timeout(int(step.get("pause_after", 350)))
    return done


def record_feature(browser, plan, idx, feat, rec_dir, fail_dir):
    vp = plan["viewport"]
    mobile = plan["format"] == "vertical"
    opts = dict(viewport=vp, record_video_dir=str(rec_dir), record_video_size=vp, device_scale_factor=1)
    if mobile:
        opts.update(is_mobile=True, has_touch=True)
    if plan.get("color_scheme"):
        opts["color_scheme"] = plan["color_scheme"]
    if plan.get("storage_state"):  # logged-in session saved by Playwright (use a demo account)
        sp = Path(plan["storage_state"])
        if not sp.exists():
            die(f"storage_state file not found: {sp}")
        opts["storage_state"] = str(sp)
    ctx = browser.new_context(**opts)
    ctx.add_init_script(overlay_script(plan))
    page = ctx.new_page()
    page.set_default_timeout(7000)
    t_page = time.monotonic()
    trim = 0.0
    try:
        for j, step in enumerate(feat["steps"]):
            try:
                done = run_step(page, plan, step)
            except Exception as exc:  # fail loudly: a video with a silently skipped step is misleading
                shot = fail_dir / f"feature{idx}_step{j}.png"
                try:
                    page.screenshot(path=str(shot))
                except Exception:
                    pass
                ctx.close()
                die(f"feature {idx} ('{feat.get('caption', '')}') step {j} {json.dumps(step)} failed: "
                    f"{str(exc).splitlines()[0][:300]}. Screenshot of the page at failure: {shot}")
            if j == 0:
                trim = max(done - t_page + 0.05, 0.0)
                if feat.get("caption"):
                    page.evaluate("t => window.__rvCaption && window.__rvCaption(t)", feat["caption"])
                    page.wait_for_timeout(400)
                try:
                    page.wait_for_load_state("networkidle", timeout=3000)
                except Exception:
                    pass  # dev servers with HMR sockets never go idle; that's fine
                # Apply custom per-element effects from plan
                custom_effects = plan.get("custom_effects", [])
                if custom_effects:
                    page.evaluate(
                        "eff => window.__rvApplyCustomEffects && window.__rvApplyCustomEffects(eff)",
                        custom_effects)
        page.wait_for_timeout(int(feat.get("hold_ms", 1000)))
    except BaseException:
        try:
            ctx.close()
        except Exception:
            pass
        raise
    video = page.video
    ctx.close()
    return Path(video.path()), trim


# --------------------------------------------------------------------------- voice-over (edge-tts)

def generate_voiceover(plan, work_dir):
    """Generate TTS audio using edge-tts for intro headline + each feature caption.

    Returns list of (key, mp3_path) tuples, or None if disabled/unavailable.
    Install with: pip install edge-tts
    """
    if not plan.get("voiceover"):
        return None
    try:
        import edge_tts  # noqa: F401
    except ImportError:
        print("[voiceover] edge-tts not installed. Run: pip install edge-tts", file=sys.stderr)
        return None

    voice = plan.get("voiceover_voice", "en-US-AriaNeural")
    tts_dir = work_dir / "tts"
    tts_dir.mkdir(exist_ok=True)

    lines = []
    if plan.get("headline"):
        lines.append(("intro", plan["headline"]))
    for i, feat in enumerate(plan["features"]):
        text = feat.get("caption", "")
        if text:
            lines.append((f"feat{i}", text))
    if plan.get("version"):
        lines.append(("outro", f"What's new in {plan['version']}."))
    elif plan.get("cta"):
        lines.append(("outro", f"Try it at {plan['cta']}."))

    async def _gen_all():
        import edge_tts as et
        results = []
        for key, text in lines:
            if not text.strip():
                continue
            mp3_path = tts_dir / f"{key}.mp3"
            try:
                comm = et.Communicate(text, voice)
                await comm.save(str(mp3_path))
                results.append((key, str(mp3_path)))
                print(f"[voiceover] TTS '{key}': {mp3_path.name}", file=sys.stderr)
            except Exception as exc:
                print(f"[voiceover] TTS failed for '{key}': {exc}", file=sys.stderr)
        return results

    try:
        clips = asyncio.run(_gen_all())
    except Exception as exc:
        print(f"[voiceover] TTS generation failed: {exc}", file=sys.stderr)
        return None

    return clips if clips else None


def merge_voiceover_into_video(video_path, tts_clips, work_dir):
    """Concatenate TTS clips and merge as audio track into the final video in-place."""
    if not tts_clips:
        return
    concat_list = work_dir / "tts_concat.txt"
    concat_list.write_text(
        "\n".join(f"file '{Path(c[1]).as_posix()}'" for c in tts_clips),
        encoding="utf-8")
    tts_merged = work_dir / "tts_merged.mp3"
    run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(concat_list),
         "-c:a", "libmp3lame", "-b:a", "128k", str(tts_merged)])

    vo_tmp = video_path.with_suffix(".vo_tmp.mp4")
    vid_dur = duration(video_path)
    run(["ffmpeg", "-y", "-i", str(video_path), "-i", str(tts_merged),
         "-map", "0:v", "-map", "1:a",
         "-af", f"afade=t=out:st={max(vid_dur - 1.5, 0):.2f}:d=1.5,volume=1.2",
         "-c:v", "copy", "-c:a", "aac", "-b:a", "160k",
         "-shortest", str(vo_tmp)])
    shutil.move(str(vo_tmp), str(video_path))


# --------------------------------------------------------------------------- ffmpeg

def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        die(f"command failed: {' '.join(cmd[:6])} ...\n{r.stderr[-1200:]}")
    return r


def duration(path):
    r = run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)])
    return float(r.stdout.strip())


def card_to_clip(png, secs, W, H, out):
    run(["ffmpeg", "-y", "-loop", "1", "-i", str(png), "-t", str(secs), "-r", str(FPS),
         "-vf", f"scale={W}:{H},format=yuv420p", "-c:v", "libx264", "-crf", "17", "-an", str(out)])


def recording_to_clip(webm, trim, speed, W, H, out):
    vf = f"scale={W}:{H}:flags=lanczos,fps={FPS},format=yuv420p"
    if speed and speed != 1:
        vf = f"setpts=PTS/{speed}," + vf
    run(["ffmpeg", "-y", "-ss", f"{trim:.2f}", "-i", str(webm), "-vf", vf,
         "-c:v", "libx264", "-crf", "17", "-preset", "medium", "-an", str(out)])


def assemble(clips, out, music=None):
    durs = [duration(c) for c in clips]
    for c, d in zip(clips, durs):
        if d < 2 * XFADE + 0.2:
            die(f"clip {c.name} is only {d:.2f}s, too short to crossfade. Add 'wait' steps or raise hold_ms.")
    cmd = ["ffmpeg", "-y"]
    for c in clips:
        cmd += ["-i", str(c)]
    total = sum(durs) - XFADE * (len(clips) - 1)
    if len(clips) == 1:
        fc, last = "", "0:v"
    else:
        parts, acc, last = [], durs[0], "0:v"
        for k in range(1, len(clips)):
            nxt = f"v{k}"
            parts.append(f"[{last}][{k}:v]xfade=transition=fade:duration={XFADE}:offset={acc - XFADE:.3f}[{nxt}]")
            acc += durs[k] - XFADE
            last = nxt
        fc = ";".join(parts)
    if music:
        cmd += ["-i", str(music)]
    if fc:
        cmd += ["-filter_complex", fc]
    cmd += ["-map", f"[{last}]" if fc else "0:v"]
    if music:
        cmd += ["-map", f"{len(clips)}:a", "-af", f"volume=0.28,afade=t=out:st={max(total - 1.6, 0):.2f}:d=1.6",
                "-c:a", "aac", "-b:a", "160k", "-t", f"{total:.2f}"]
    cmd += ["-c:v", "libx264", "-crf", "18", "-preset", "medium", "-pix_fmt", "yuv420p",
            "-movflags", "+faststart", "-r", str(FPS), str(out)]
    run(cmd)
    return total


def contact_sheet(video, total, out_png, vertical):
    n = 12
    fps = n / max(total, 1)
    cols, rows = (6, 2) if not vertical else (6, 2)
    w = 320 if not vertical else 180
    run(["ffmpeg", "-y", "-i", str(video), "-vf",
         f"fps={fps:.4f},scale={w}:-1,tile={cols}x{rows}:padding=4:color=black", "-frames:v", "1", str(out_png)])


# --------------------------------------------------------------------------- main

def main():
    print("🎬 Release Announcement Video Renderer v2.0")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("plan")
    ap.add_argument("-o", "--out", default=None)
    ap.add_argument("--keep-work", action="store_true", help="keep intermediate clips and failure screenshots")
    ap.add_argument("--validate-only", action="store_true")
    ap.add_argument("--extract-theme", action="store_true",
                    help="Force theme color extraction from base_url (overrides any accent in plan)")
    a = ap.parse_args()

    for tool in ("ffmpeg", "ffprobe"):
        if not shutil.which(tool):
            die(f"{tool} not found on PATH. Install ffmpeg first.")
    plan = load_plan(a.plan)
    if a.validate_only:
        print(json.dumps({"ok": True, "features": len(plan["features"])}))
        return
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        die("playwright is not installed: pip install playwright && playwright install chromium")

    # Auto-extract site theme color when accent is the generic default or --extract-theme is given
    if plan.get("base_url") and (a.extract_theme or plan.get("accent") == "#6366f1"):
        extracted = extract_site_theme(plan["base_url"], plan)
        if extracted and extracted != plan["accent"]:
            print(f"[theme] Overriding accent with site color: {extracted}", file=sys.stderr)
            plan["accent"] = extracted

    plan_dir = Path(a.plan).resolve().parent
    out = Path(a.out) if a.out else plan_dir / (Path(a.plan).stem + ".mp4")
    out.parent.mkdir(parents=True, exist_ok=True)
    vertical = plan["format"] == "vertical"
    W, H = (1080, 1920) if vertical else (1920, 1080)
    work = Path(tempfile.mkdtemp(prefix="rav_", dir=out.parent))
    fail_dir = work / "failures"
    fail_dir.mkdir()

    logo_uri = None
    if plan.get("logo"):
        import base64, mimetypes
        lp = Path(plan["logo"])
        lp = lp if lp.is_absolute() else plan_dir / lp
        if lp.exists():
            logo_uri = f"data:{mimetypes.guess_type(lp)[0] or 'image/png'};base64,{base64.b64encode(lp.read_bytes()).decode()}"

    clips = []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        # cards (intro + outro)
        cctx = browser.new_context(viewport={"width": W, "height": H})
        for kind, secs in (("intro", plan["intro_seconds"]), ("outro", plan["outro_seconds"])):
            pg = cctx.new_page()
            pg.set_content(card_html(kind, plan, W, H, logo_uri))
            pg.wait_for_timeout(250)
            png = work / f"{kind}.png"
            pg.screenshot(path=str(png))
            pg.close()
            clip = work / f"{kind}.mp4"
            card_to_clip(png, secs, W, H, clip)
            if kind == "intro":
                clips.insert(0, clip)
            else:
                outro = clip
        cctx.close()
        # features
        for i, feat in enumerate(plan["features"]):
            rec_dir = work / f"rec{i}"
            webm, trim = record_feature(browser, plan, i, feat, rec_dir, fail_dir)
            clip = work / f"feature{i}.mp4"
            recording_to_clip(webm, trim, feat.get("speed", 1), W, H, clip)
            clips.append(clip)
        browser.close()
    clips.append(outro)

    music = plan.get("music")
    if music:
        mp = Path(music)
        music = mp if mp.is_absolute() else plan_dir / mp
        if not music.exists():
            die(f"music file not found: {music}")
    total = assemble(clips, out, music)

    # Voice-over: generate TTS and merge into final video
    tts_clips = generate_voiceover(plan, work)
    if tts_clips:
        merge_voiceover_into_video(out, tts_clips, work)

    sheet = out.with_suffix(".contact.png")
    contact_sheet(out, total, sheet, vertical)

    if not a.keep_work:
        shutil.rmtree(work, ignore_errors=True)
    warn = []
    if total > 60:
        warn.append(f"video is {total:.0f}s; social announcements usually work best under 45s. Trim features or raise 'speed'.")
    print(json.dumps({"ok": True, "video": str(out), "contact_sheet": str(sheet),
                      "seconds": round(total, 1), "format": plan["format"], "warnings": warn}, indent=2))


if __name__ == "__main__":
    main()
