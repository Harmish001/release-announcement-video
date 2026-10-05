#!/usr/bin/env python3
"""Render a release announcement video from a plan.json.

  make_video.py plan.json -o out.mp4

Pipeline: validate plan -> measure TTS (edge-tts) and size scenes to fit ->
extract site theme color when accent is "auto" -> record animated intro/outro
cards and each feature (cursor, click effect, slide/fade/zoom, captions,
spotlight, zoom toward the target) -> encode, crossfade, mix voice over
music -> write thumbnail, gif, srt/vtt, and announcement.md. plan.json is kept.

Requires: python3, playwright (+ chromium), ffmpeg/ffprobe on PATH.
Optional:  edge-tts (pip install edge-tts) for voice-over.
Plan format: see references/plan-format.md

New plan.json fields (all optional):
  click_effect      "ripple" (default) | "sparkle" | "glow"
  nav_transition    "fade" (default) | "slide" | "zoom"
  voiceover         true (default) | false  -- requires edge-tts
  narration         per feature, spoken instead of the short caption
  zoom              camera scale on click/highlight, default 1.28
  capture           "video" (default) | "frames" (CDP screencast)
  accent            "auto" (default) or an explicit hex. #6366f1 is not auto.
  voiceover_voice   edge-tts voice name, default "en-US-AriaNeural"
  custom_effects    list of {effect, selector} objects applied on every page
                    effect: "sparkle" | "glow" | "pulse"
"""
import argparse
import asyncio
import base64
import html
import json
import mimetypes
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from common import (
    DEMO_WARNING,
    FALLBACK_ACCENT,
    PHONE,
    XFADE,
    accent_is_auto,
    apply_narration_timing,
    apply_note,
    chapter_labels,
    clip_offsets,
    default_dpr,
    default_viewport,
    narration_lines,
    output_size,
    seconds_for_narration,
    package_version,
    scene_hash,
    voice_mix_filter,
    write_announcement,
    write_subtitles,
    youtube_chapter_lines,
)

# Ensure UTF-8 output on Windows consoles
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

ACTIONS = {"goto", "wait", "click", "type", "press", "hover", "scroll", "highlight", "caption", "upload"}
FPS = 30
COOKIE_SELECTORS = [
    "button:has-text('Accept All')",
    "button:has-text('Accept all')",
    "button:has-text('Accept')",
    "button:has-text('Agree')",
    "button:has-text('Got it')",
    "button:has-text('I agree')",
    "button:has-text('Allow all')",
    "button:has-text('Decline')",
]


# --------------------------------------------------------------------------- plan

def die(msg, code=2):
    print(json.dumps({"ok": False, "error": msg}, indent=2), file=sys.stderr)
    sys.exit(code)


def load_plan(path):
    plan = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    for key in ("product", "headline", "features"):
        if not plan.get(key):
            die(f"plan is missing required field '{key}'")
    plan.setdefault("version", "")
    plan.setdefault("subhead", "")
    plan.setdefault("accent", "auto")
    plan.setdefault("bullets", [])
    plan.setdefault("cta", "")
    plan.setdefault("format", "landscape")
    plan.setdefault("intro_seconds", 3.0)
    plan.setdefault("outro_seconds", 3.5)
    plan.setdefault("click_effect", "ripple")      # ripple | sparkle | glow
    plan.setdefault("nav_transition", "fade")       # fade | slide | zoom
    plan.setdefault("voiceover", True)
    plan.setdefault("voiceover_voice", "en-US-AriaNeural")
    plan.setdefault("custom_effects", [])
    plan.setdefault("zoom", 1.28)
    plan.setdefault("capture", "video")             # video | frames (CDP screencast)
    if plan["format"] not in ("landscape", "vertical", "square"):
        die("format must be 'landscape', 'vertical' or 'square'")
    fmt = plan["format"]
    # 1080x1920 CSS pixels trigger desktop layouts. Phone CSS size + DPR instead.
    if fmt == "vertical" and plan.get("viewport") in (None, {"width": 1080, "height": 1920}):
        plan["viewport"] = dict(PHONE)
        plan["device_scale_factor"] = default_dpr(fmt)
    else:
        plan.setdefault("viewport", default_viewport(fmt))
        plan.setdefault("device_scale_factor", default_dpr(fmt))
    plan.setdefault("cursor", "tap" if fmt == "vertical" else "arrow")
    if plan["cursor"] not in ("arrow", "tap", "none"):
        die("cursor must be 'arrow', 'tap' or 'none'")
    if plan["click_effect"] not in ("ripple", "sparkle", "glow"):
        die("click_effect must be 'ripple', 'sparkle' or 'glow'")
    if plan["nav_transition"] not in ("fade", "slide", "zoom"):
        die("nav_transition must be 'fade', 'slide' or 'zoom'")
    if plan["capture"] not in ("video", "frames"):
        die("capture must be 'video' or 'frames'")
    base = plan.get("base_url", "").rstrip("/")
    plan["base_url"] = base
    for i, feat in enumerate(plan["features"]):
        if feat.get("card"):
            if not (feat["card"].get("title") or feat["card"].get("lines")):
                die(f"feature {i} card needs 'title' or 'lines'")
            feat.setdefault("steps", [])
            continue
        steps = feat.get("steps") or []
        if not steps:
            die(f"feature {i} has no steps")
        for j, s in enumerate(steps):
            a = s.get("action")
            if a not in ACTIONS:
                die(f"feature {i} step {j}: unknown action '{a}'. Valid: {sorted(ACTIONS)}")
                need = {"goto": "url", "click": "selector", "type": "selector", "press": "key",
                    "hover": "selector", "highlight": "selector", "upload": "selector"}.get(a)
            if need and need not in s:
                die(f"feature {i} step {j} ({a}) needs '{need}'")
            if a == "type" and "text" not in s:
                die(f"feature {i} step {j} (type) needs 'text'")
            if a == "upload" and not s.get("files"):
                die(f"feature {i} step {j} (upload) needs 'files'")
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
    """Visit the live site and extract the dominant brand/accent color using canvas color parsing.

    Priority:
      1. Saturated brand colors on buttons, CTAs, links, headers, badges
      2. Meta theme-color or CSS custom properties (--primary, --accent, --brand, etc.)
      3. Fallback: plan["accent"] unchanged.
    """
    if not url:
        return plan["accent"]
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return plan["accent"]

    extracted = None
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
            extracted = page.evaluate(r"""() => {
                function parseRgb(str) {
                    if (!str || str === 'transparent' || str === 'rgba(0, 0, 0, 0)') return null;
                    const cvs = document.createElement('canvas');
                    cvs.width = cvs.height = 1;
                    const ctx = cvs.getContext('2d');
                    ctx.fillStyle = str;
                    ctx.fillRect(0, 0, 1, 1);
                    const [r, g, b, a] = ctx.getImageData(0, 0, 1, 1).data;
                    if (a < 50) return null;
                    const max = Math.max(r, g, b), min = Math.min(r, g, b);
                    const sat = max === 0 ? 0 : (max - min) / max;
                    const lum = (max + min) / (2 * 255);
                    if (lum > 0.94 || lum < 0.06 || sat < 0.25) return null;
                    return { hex: '#' + [r, g, b].map(x => x.toString(16).padStart(2, '0')).join(''), sat, lum };
                }

                // 1. Check meta theme-color
                const meta = document.querySelector('meta[name="theme-color"]');
                if (meta && meta.content) {
                    const parsed = parseRgb(meta.content);
                    if (parsed && parsed.sat >= 0.3) return parsed.hex;
                }

                // 2. Check CSS variables
                const cs = getComputedStyle(document.documentElement);
                for (const v of ['--primary', '--brand', '--accent', '--color-primary', '--p', '--theme-color', '--primary-600', '--primary-500']) {
                    const val = cs.getPropertyValue(v).trim();
                    const parsed = parseRgb(val);
                    if (parsed && parsed.sat >= 0.3) return parsed.hex;
                }

                // 3. Score all interactive elements, CTAs, badges, and colored elements by saturation & frequency
                const counts = {};
                const els = document.querySelectorAll('button, a, [class*=btn], [class*=primary], [class*=brand], [class*=accent], svg, [class*=active], [class*=bg-], [class*=text-], [class*=border-]');
                for (const el of els) {
                    const s = getComputedStyle(el);
                    for (const prop of [s.backgroundColor, s.color, s.borderColor]) {
                        const parsed = parseRgb(prop);
                        if (parsed) {
                            counts[parsed.hex] = (counts[parsed.hex] || 0) + 1 + (parsed.sat * 3);
                        }
                    }
                }
                const sorted = Object.entries(counts).sort((a, b) => b[1] - a[1]);
                return sorted.length > 0 ? sorted[0][0] : null;
            }""")
            browser.close()
    except Exception as exc:
        print(f"[theme] Could not extract site theme: {exc}", file=sys.stderr)

    if extracted and extracted.startswith("#") and len(extracted) >= 7:
        print(f"[theme] Successfully extracted brand theme color: {extracted}", file=sys.stderr)
        return extracted

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
.brand,h1,.sub,h2,li,.cta{animation:rise .65s ease both}
.sub{animation-delay:.12s}
h2{animation-delay:.08s}
li:nth-child(1){animation-delay:.15s}
li:nth-child(2){animation-delay:.25s}
li:nth-child(3){animation-delay:.35s}
li:nth-child(4){animation-delay:.45s}
li:nth-child(5){animation-delay:.55s}
.cta{animation-delay:.4s}
@keyframes rise{from{opacity:0;transform:translateY(28px)}to{opacity:1;transform:none}}
"""


def card_html(kind, plan, W, H, logo_uri, title=None, lines=None):
    vertical = plan["format"] == "vertical"
    unit = W / (1080 if plan["format"] != "landscape" else 1920)
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
    elif kind == "beat":
        items = "".join(f"<li><span>{e(b)}</span></li>" for b in (lines or [])[:5])
        body = f'{brand}<h2>{e(title or "Before")}</h2><ul>{items}</ul>'
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

  /* ---- veil for fade; slide and zoom move document.body so they survive as a new page ---- */
  function ensureVeil() {
    if (document.getElementById('__rv_nav_veil')) return;
    const v = document.createElement('div'); v.id = '__rv_nav_veil';
    document.documentElement.appendChild(v);
  }
  function stage() { return document.body || document.documentElement; }
  function playIncoming() {
    let fx = '';
    try { fx = sessionStorage.getItem('__rv_nav') || ''; sessionStorage.removeItem('__rv_nav'); } catch (e) {}
    if (!fx) return;
    const body = stage();
    if (fx === 'slide') {
      body.style.transition = 'none';
      body.style.transform = 'translateX(14%)';
      requestAnimationFrame(() => {
        body.style.transition = 'transform .35s ease';
        body.style.transform = 'none';
      });
    } else if (fx === 'zoom') {
      body.style.transformOrigin = '50% 40%';
      body.style.transition = 'none';
      body.style.transform = 'scale(.9)';
      body.style.opacity = '.35';
      requestAnimationFrame(() => {
        body.style.transition = 'transform .35s ease, opacity .3s ease';
        body.style.transform = 'none';
        body.style.opacity = '1';
      });
    } else {
      const v = document.getElementById('__rv_nav_veil');
      if (v) { v.style.transition = 'none'; v.style.opacity = '1'; v.classList.add('on'); }
    }
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
    window.__rvZoomTo = (b, scale) => {
      const body = stage();
      const cx = b.x + b.width / 2, cy = b.y + b.height / 2;
      body.style.transformOrigin = cx + 'px ' + cy + 'px';
      body.style.transition = 'transform .45s cubic-bezier(.2,.7,.2,1)';
      body.style.transform = 'scale(' + scale + ')';
    };
    window.__rvZoomReset = () => {
      const body = stage();
      body.style.transition = 'transform .3s ease';
      body.style.transform = 'none';
    };
    /* nav: fade uses the veil. slide and zoom transform body, then the next
       document reads __rv_nav from sessionStorage and animates in. */
    window.__rvNavIn = (fx) => {
      try { sessionStorage.setItem('__rv_nav', fx || 'fade'); } catch (e) {}
      const body = stage();
      if (fx === 'slide') {
        body.style.transition = 'transform .25s ease, opacity .25s ease';
        body.style.transform = 'translateX(-12%)';
        body.style.opacity = '.2';
      } else if (fx === 'zoom') {
        body.style.transformOrigin = '50% 40%';
        body.style.transition = 'transform .25s ease, opacity .25s ease';
        body.style.transform = 'scale(1.06)';
        body.style.opacity = '0';
      } else {
        const v = document.getElementById('__rv_nav_veil');
        if (!v) return;
        v.style.transition = 'opacity 0.22s ease'; v.classList.add('on');
      }
    };
    window.__rvNavOut = () => {
      const v = document.getElementById('__rv_nav_veil'); if (!v) return;
      v.style.transition = 'opacity 0.28s ease'; v.classList.remove('on'); v.style.opacity = '0';
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
    playIncoming();
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
    try:
        page.evaluate("(fx) => window.__rvNavIn && window.__rvNavIn(fx)", nav_fx)
        page.wait_for_timeout(280)
    except Exception:
        pass


def nav_transition_out(page, nav_fx):
    """Fade-out of the veil. Slide and zoom play from the init script on the new document."""
    try:
        page.wait_for_timeout(360)
        if nav_fx == "fade":
            page.evaluate("() => window.__rvNavOut && window.__rvNavOut()")
            page.wait_for_timeout(300)
    except Exception:
        pass


def dismiss_cookies(page):
    """Run after each navigation. A blank page has no banner."""
    for sel in COOKIE_SELECTORS:
        try:
            el = page.locator(sel).first
            if el.is_visible(timeout=200):
                el.click(timeout=800)
                page.wait_for_timeout(200)
                return
        except Exception:
            continue


def zoom_reset(page):
    try:
        page.evaluate("() => window.__rvZoomReset && window.__rvZoomReset()")
    except Exception:
        pass


def zoom_to(page, box, plan, step):
    raw = step.get("zoom", plan.get("zoom", 1.28))
    if raw is False or raw is None:
        return
    try:
        scale = float(raw)
    except (TypeError, ValueError):
        return
    if scale <= 1.01 or not box:
        return
    try:
        page.evaluate("([b,s]) => window.__rvZoomTo && window.__rvZoomTo(b, s)", [box, scale])
        page.wait_for_timeout(480)
    except Exception:
        pass


# --------------------------------------------------------------------------- recording

def move_to(page, box, plan):
    x, y = box["x"] + box["width"] / 2, box["y"] + box["height"] / 2
    page.mouse.move(x, y, steps=28)
    page.wait_for_timeout(220)
    return x, y


def run_step(page, plan, step, shot_path=None):
    a = step["action"]
    nav_fx = plan.get("nav_transition", "fade")
    if a != "wait":
        zoom_reset(page)
    if "caption" in step and a != "caption":
        page.evaluate("t => window.__rvCaption && window.__rvCaption(t)", step["caption"])
    if a == "goto":
        nav_transition_in(page, nav_fx)
        page.goto(abs_url(plan, step["url"]), wait_until="load")
        nav_transition_out(page, nav_fx)
        dismiss_cookies(page)
        if shot_path is not None and not Path(shot_path).exists():
            try:
                page.screenshot(path=str(shot_path))
            except Exception:
                pass
    elif a == "wait":
        page.wait_for_timeout(int(step.get("ms", 800)))
    elif a == "upload":
        files = step["files"] if isinstance(step["files"], list) else [step["files"]]
        page.locator(step["selector"]).first.set_input_files([str(Path(path).resolve()) for path in files])
    elif a in ("click", "hover", "type"):
        loc = page.locator(step["selector"]).first
        loc.wait_for(state="visible")
        loc.scroll_into_view_if_needed()
        page.wait_for_timeout(150)
        box = loc.bounding_box()
        x, y = move_to(page, box, plan)
        if a == "hover":
            page.wait_for_timeout(int(step.get("ms", 600)))
        else:
            if plan["cursor"] != "none":
                page.evaluate(
                    "([x,y]) => { window.__rvClickEffect && window.__rvClickEffect(x,y); "
                    "window.__rvClickAnim && window.__rvClickAnim(x,y); }",
                    [x, y])
            page.mouse.click(x, y)
            zoom_to(page, box, plan, step)
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
        box = loc.bounding_box()
        page.evaluate("([b,ms]) => window.__rvSpot && window.__rvSpot(b,ms)", [box, ms])
        zoom_to(page, box, plan, step)
        page.wait_for_timeout(ms + 150)
    elif a == "caption":
        page.evaluate("t => window.__rvCaption && window.__rvCaption(t)", step.get("text", ""))
        page.wait_for_timeout(int(step.get("ms", 900)))
    done = time.monotonic()  # moment the action itself finished, before the breathing pause
    page.wait_for_timeout(int(step.get("pause_after", 350)))
    return done


def even(n):
    n = int(n)
    return n if n % 2 == 0 else n - 1


def record_context_opts(plan, rec_dir):
    vp = plan["viewport"]
    dpr = float(plan.get("device_scale_factor") or 1)
    frames = plan.get("capture") == "frames"
    opts = dict(viewport=vp, device_scale_factor=dpr)
    if not frames:
        opts["record_video_dir"] = str(rec_dir)
        opts["record_video_size"] = {"width": even(vp["width"] * dpr), "height": even(vp["height"] * dpr)}
    if plan["format"] == "vertical":
        opts.update(is_mobile=True, has_touch=True)
    if plan.get("color_scheme"):
        opts["color_scheme"] = plan["color_scheme"]
    if plan.get("storage_state"):
        sp = Path(plan["storage_state"])
        if not sp.exists():
            die(f"storage_state file not found: {sp}")
        opts["storage_state"] = str(sp)
        print(DEMO_WARNING, file=sys.stderr)
    return opts


def start_screencast(page, plan):
    vp = plan["viewport"]
    dpr = float(plan.get("device_scale_factor") or 1)
    cdp = page.context.new_cdp_session(page)
    frames = []

    def on_frame(ev):
        data = ev.get("data")
        if data:
            frames.append(data)
        sid = ev.get("sessionId")
        if sid is not None:
            try:
                cdp.send("Page.screencastFrameAck", {"sessionId": sid})
            except Exception:
                pass

    cdp.on("Page.screencastFrame", on_frame)
    cdp.send("Page.startScreencast", {
        "format": "jpeg",
        "quality": 90,
        "maxWidth": even(vp["width"] * dpr),
        "maxHeight": even(vp["height"] * dpr),
        "everyNthFrame": 1,
    })
    return cdp, frames


def record_feature(browser, plan, idx, feat, rec_dir, fail_dir, shot_path=None):
    opts = record_context_opts(plan, rec_dir)
    ctx = browser.new_context(**opts)
    ctx.add_init_script(overlay_script(plan))
    page = ctx.new_page()
    page.set_default_timeout(7000)
    cdp = frames = None
    if plan.get("capture") == "frames":
        cdp, frames = start_screencast(page, plan)
    t_page = time.monotonic()
    trim = 0.0
    try:
        for j, step in enumerate(feat["steps"]):
            try:
                done = run_step(page, plan, step, shot_path)
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
    if cdp is not None:
        try:
            cdp.send("Page.stopScreencast")
        except Exception:
            pass
        page.wait_for_timeout(200)
    video = page.video
    ctx.close()
    if frames is not None:
        if len(frames) < 2:
            die(f"feature {idx}: CDP screencast captured {len(frames)} frames")
        fdir = rec_dir / "frames"
        fdir.mkdir(parents=True, exist_ok=True)
        for i, blob in enumerate(frames):
            (fdir / f"f{i:05d}.jpg").write_bytes(base64.b64decode(blob))
        return fdir, 0.0, "frames"
    return Path(video.path()), trim, "video"


# --------------------------------------------------------------------------- voice-over (edge-tts)

# --------------------------------------------------------------------------- voice-over (edge-tts)

def generate_voiceover(plan, work_dir, cache_dir=None):
    """TTS first, then the caller sizes scenes from the measured lengths.

    Returns list of dicts with key, clip_idx, file, audio_s — or None.
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
    items = narration_lines(plan)

    async def _gen_all():
        import edge_tts as et
        results = []
        for item in items:
            text = item["text"].strip()
            if not text:
                continue
            mp3_path = tts_dir / f"{item['key']}.mp3"
            cached = None
            if cache_dir is not None:
                cached = cache_dir / "tts" / f"{scene_hash({'v': voice, 't': text})}.mp3"
            try:
                if cached is not None and cached.exists() and cached.stat().st_size > 100:
                    shutil.copy(cached, mp3_path)
                else:
                    comm = et.Communicate(text, voice)
                    await comm.save(str(mp3_path))
                    if cached is not None:
                        cached.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy(mp3_path, cached)
                item["file"] = str(mp3_path)
                item["audio_s"] = duration(mp3_path)
                results.append(item)
                print(f"[voiceover] {item['key']} {item['audio_s']:.2f}s: {text[:40]}", file=sys.stderr)
            except Exception as exc:
                print(f"[voiceover] TTS failed for '{item['key']}': {exc}", file=sys.stderr)
        return results

    try:
        clips = asyncio.run(_gen_all())
    except Exception as exc:
        print(f"[voiceover] TTS generation failed: {exc}", file=sys.stderr)
        return None

    return clips if clips else None


def has_audio_stream(path):
    r = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "a:0", "-show_entries", "stream=index", "-of", "csv=p=0", str(path)],
        capture_output=True, text=True,
    )
    return r.returncode == 0 and bool(r.stdout.strip())


def merge_voiceover_into_video(video_path, tts_items, clip_durations, total_dur):
    """Place each voice clip on its scene. Keep background music when the video already has it."""
    if not tts_items:
        return

    offsets = clip_offsets(clip_durations)
    delays = []
    cmd = ["ffmpeg", "-y", "-i", str(video_path)]
    for item in tts_items:
        c_idx = item["clip_idx"]
        start_sec = offsets[c_idx] if c_idx < len(offsets) else 0.0
        delays.append(int(max(0, (start_sec + 0.25) * 1000)))
        cmd += ["-i", str(item["file"])]
    bed = has_audio_stream(video_path)
    fc = voice_mix_filter(delays, with_bed=bed)
    fade_out_st = max(total_dur - 1.2, 0)
    fc += f";[aout]afade=t=out:st={fade_out_st:.2f}:d=1.2[af]"
    vo_tmp = video_path.with_suffix(".vo_tmp.mp4")
    cmd += [
        "-filter_complex", fc,
        "-map", "0:v", "-map", "[af]",
        "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
        "-t", f"{total_dur:.3f}", str(vo_tmp),
    ]
    run(cmd)
    shutil.move(str(vo_tmp), str(video_path))
    print(f"[voiceover] mixed voice{' + music' if bed else ''} into {video_path.name}", file=sys.stderr)


# --------------------------------------------------------------------------- ffmpeg

def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        die(f"command failed: {' '.join(cmd[:6])} ...\n{r.stderr[-1200:]}")
    return r


def duration(path):
    r = run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)])
    return float(r.stdout.strip())


def fit_vf(W, H, cover, speed):
    if cover:
        scale = f"scale={W}:{H}:force_original_aspect_ratio=increase:flags=lanczos,crop={W}:{H}"
    else:
        scale = f"scale={W}:{H}:flags=lanczos"
    vf = f"{scale},fps={FPS},format=yuv420p"
    if speed and float(speed) != 1:
        vf = f"setpts=PTS/{float(speed)}," + vf
    return vf


def recording_to_clip(webm, trim, speed, W, H, out, cover=False):
    run(["ffmpeg", "-y", "-ss", f"{trim:.2f}", "-i", str(webm), "-vf", fit_vf(W, H, cover, speed),
         "-c:v", "libx264", "-crf", "14", "-preset", "slow", "-an", str(out)])


def frames_to_clip(frame_dir, speed, W, H, out, cover=False):
    run(["ffmpeg", "-y", "-framerate", str(FPS), "-i", str(frame_dir / "f%05d.jpg"),
         "-vf", fit_vf(W, H, cover, speed),
         "-c:v", "libx264", "-crf", "14", "-preset", "slow", "-an", str(out)])


def ensure_min_duration(clip, need, W, H):
    if not need:
        return
    have = duration(clip)
    if have + 0.05 >= need:
        return
    extra = need - have
    tmp = clip.with_suffix(".pad.mp4")
    run(["ffmpeg", "-y", "-i", str(clip), "-vf",
         f"tpad=stop_mode=clone:stop_duration={extra:.3f},scale={W}:{H},format=yuv420p",
         "-c:v", "libx264", "-crf", "14", "-preset", "slow", "-an", str(tmp)])
    shutil.move(str(tmp), str(clip))


def cache_hit(cache_dir, key, dest):
    src = cache_dir / f"{key}.mp4"
    if src.exists() and src.stat().st_size > 1000:
        shutil.copy(src, dest)
        print(f"[cache] {key}", file=sys.stderr)
        return True
    return False


def cache_store(cache_dir, key, src):
    cache_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy(src, cache_dir / f"{key}.mp4")


def record_card(browser, markup, secs, W, H, rec_dir):
    rec_dir.mkdir(parents=True, exist_ok=True)
    ctx = browser.new_context(
        viewport={"width": W, "height": H},
        record_video_dir=str(rec_dir),
        record_video_size={"width": W, "height": H},
    )
    pg = ctx.new_page()
    pg.set_content(markup)
    pg.wait_for_timeout(max(int(float(secs) * 1000), 1200))
    video = pg.video
    ctx.close()
    return Path(video.path())


def thumbnail_html(plan, shot_uri):
    e = html.escape
    img = f'<img src="{shot_uri}" alt="">' if shot_uri else ""
    return f"""<!doctype html><meta charset="utf-8"><style>
*{{box-sizing:border-box;margin:0;padding:0}}
html,body{{width:1280px;height:720px;overflow:hidden;background:#0b0d17;color:#f5f6fa;
  font-family:Inter,'Segoe UI',Arial,sans-serif;display:flex}}
.copy{{width:{520 if shot_uri else 1280}px;padding:64px 48px;display:flex;flex-direction:column;justify-content:center}}
.kicker{{color:{plan['accent']};font-weight:700;letter-spacing:.06em;font-size:20px}}
h1{{font-size:52px;line-height:1.05;margin-top:18px;font-weight:800}}
img{{width:760px;height:720px;object-fit:cover;object-position:left top}}
</style><body><div class="copy"><div class="kicker">{e(plan.get('product') or '')} {e(plan.get('version') or '')}</div>
<h1>{e(plan.get('headline') or '')}</h1></div>{img}</body>"""


def write_thumbnail(browser, plan, shot_path, dest):
    shot_uri = None
    if shot_path and Path(shot_path).exists():
        mime = mimetypes.guess_type(shot_path)[0] or "image/png"
        shot_uri = f"data:{mime};base64,{base64.b64encode(Path(shot_path).read_bytes()).decode()}"
    ctx = browser.new_context(viewport={"width": 1280, "height": 720}, device_scale_factor=1)
    pg = ctx.new_page()
    pg.set_content(thumbnail_html(plan, shot_uri))
    pg.wait_for_timeout(150)
    pg.screenshot(path=str(dest))
    ctx.close()


def write_gif(video, dest):
    palette = dest.with_suffix(".palette.png")
    vf = "fps=10,scale=640:-1:flags=lanczos"
    run(["ffmpeg", "-y", "-t", "8", "-i", str(video), "-vf", vf + ",palettegen", str(palette)])
    run(["ffmpeg", "-y", "-t", "8", "-i", str(video), "-i", str(palette),
         "-lavfi", f"{vf}[x];[x][1:v]paletteuse", str(dest)])
    palette.unlink(missing_ok=True)


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
                "-c:a", "aac", "-b:a", "192k", "-t", f"{total:.2f}"]
    cmd += ["-c:v", "libx264", "-crf", "15", "-preset", "slow", "-pix_fmt", "yuv420p",
            "-movflags", "+faststart", "-r", str(FPS), str(out)]
    run(cmd)
    return total, durs


def resolve_accent(plan, force):
    if plan.get("base_url") and (force or accent_is_auto(plan.get("accent"))):
        extracted = extract_site_theme(plan["base_url"], plan)
        if isinstance(extracted, str) and extracted.startswith("#") and len(extracted) >= 7:
            if extracted.lower() != str(plan.get("accent", "")).lower():
                print(f"[theme] {extracted}", file=sys.stderr)
            plan["accent"] = extracted
    if accent_is_auto(plan.get("accent")):
        plan["accent"] = FALLBACK_ACCENT


def feature_payload(plan, feat):
    return {
        "steps": feat.get("steps"),
        "caption": feat.get("caption"),
        "narration": feat.get("narration"),
        "card": feat.get("card"),
        "speed": feat.get("speed", 1),
        "hold_ms": feat.get("hold_ms"),
        "zoom": plan.get("zoom"),
        "viewport": plan["viewport"],
        "dpr": plan.get("device_scale_factor"),
        "accent": plan["accent"],
        "click_effect": plan["click_effect"],
        "nav": plan["nav_transition"],
        "cursor": plan["cursor"],
        "format": plan["format"],
        "capture": plan["capture"],
        "effects": plan.get("custom_effects"),
    }


def card_payload(kind, plan, secs, W, H, title=None, lines=None):
    return {
        "kind": kind, "secs": round(float(secs), 2), "w": W, "h": H,
        "title": title, "lines": lines,
        "headline": plan.get("headline"), "subhead": plan.get("subhead"),
        "product": plan.get("product"), "version": plan.get("version"),
        "accent": plan["accent"], "bullets": plan.get("bullets"),
        "cta": plan.get("cta"), "logo": plan.get("logo"),
        "features": [f.get("caption") for f in plan["features"]],
    }


# --------------------------------------------------------------------------- main

def main():
    print(f"Release announcement video renderer {package_version()}")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("plan")
    ap.add_argument("-o", "--out", default=None)
    ap.add_argument("--keep-work", action="store_true", help="keep intermediate clips and failure screenshots")
    ap.add_argument("--validate-only", action="store_true")
    ap.add_argument("--extract-theme", action="store_true",
                    help="Force theme color extraction from base_url (overrides any accent in plan)")
    ap.add_argument("--note", action="append", default=[],
                    help="Edit phrase: 'zoom more', 'zoom less', 'shorten the intro', 'shorten the outro', 'shorten'")
    a = ap.parse_args()

    plan = load_plan(a.plan)
    notes_applied = False
    for note in a.note:
        if not apply_note(plan, note):
            die(f"unrecognized edit note: {note}. Try: zoom more, zoom less, shorten the intro, shorten the outro, shorten")
        notes_applied = True
    if a.validate_only:
        print(json.dumps({"ok": True, "features": len(plan["features"]), "format": plan["format"],
                          "viewport": plan["viewport"], "accent": plan["accent"]}))
        return
    for tool in ("ffmpeg", "ffprobe"):
        if not shutil.which(tool):
            die(f"{tool} not found on PATH. Install ffmpeg first.")
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        die("playwright is not installed: pip install playwright && playwright install chromium")

    resolve_accent(plan, a.extract_theme)

    plan_path = Path(a.plan).resolve()
    plan_dir = plan_path.parent
    out = Path(a.out) if a.out else plan_dir / (plan_path.stem + ".mp4")
    out.parent.mkdir(parents=True, exist_ok=True)
    W, H = output_size(plan["format"])
    cover = plan["format"] == "vertical"
    cache_dir = out.parent / ".cache"
    work = Path(tempfile.mkdtemp(prefix="rav_", dir=out.parent))
    fail_dir = work / "failures"
    fail_dir.mkdir()
    shot_path = work / "product.png"

    tts_clips = generate_voiceover(plan, work, cache_dir)
    audio_by_key = {}
    if tts_clips:
        audio_by_key = {item["key"]: item["audio_s"] for item in tts_clips if item.get("audio_s")}
        apply_narration_timing(plan, audio_by_key)
    if notes_applied:
        plan_path.write_text(json.dumps(plan, indent=2) + "\n", encoding="utf-8")

    logo_uri = None
    if plan.get("logo"):
        lp = Path(plan["logo"])
        lp = lp if lp.is_absolute() else plan_dir / lp
        if lp.exists():
            logo_uri = f"data:{mimetypes.guess_type(lp)[0] or 'image/png'};base64,{base64.b64encode(lp.read_bytes()).decode()}"

    def encode_card(browser, kind, secs, dest, title=None, lines=None):
        key = scene_hash(card_payload(kind, plan, secs, W, H, title, lines))
        if cache_hit(cache_dir, key, dest):
            return
        markup = card_html(kind, plan, W, H, logo_uri, title=title, lines=lines)
        webm = record_card(browser, markup, secs, W, H, work / f"card_{dest.stem}")
        recording_to_clip(webm, 0, 1, W, H, dest, cover=False)
        cache_store(cache_dir, key, dest)

    clips = []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        intro = work / "intro.mp4"
        outro = work / "outro.mp4"
        encode_card(browser, "intro", plan["intro_seconds"], intro)
        encode_card(browser, "outro", plan["outro_seconds"], outro)
        clips.append(intro)
        for i, feat in enumerate(plan["features"]):
            clip = work / f"feature{i}.mp4"
            key = scene_hash(feature_payload(plan, feat))
            if not cache_hit(cache_dir, key, clip):
                if feat.get("card"):
                    secs = max(2.5, int(feat.get("hold_ms") or 2500) / 1000)
                    card = feat["card"]
                    encode_card(browser, "beat", secs, clip, title=card.get("title"), lines=card.get("lines") or [])
                else:
                    rec_dir = work / f"rec{i}"
                    src, trim, kind = record_feature(browser, plan, i, feat, rec_dir, fail_dir, shot_path)
                    speed = feat.get("speed", 1)
                    if kind == "frames":
                        frames_to_clip(src, speed, W, H, clip, cover=cover)
                    else:
                        recording_to_clip(src, trim, speed, W, H, clip, cover=cover)
                need = audio_by_key.get(f"feat{i}")
                ensure_min_duration(clip, seconds_for_narration(need) if need else None, W, H)
                cache_store(cache_dir, key, clip)
            clips.append(clip)
        thumb = out.parent / "thumbnail.png"
        write_thumbnail(browser, plan, shot_path, thumb)
        browser.close()
    clips.append(outro)

    music = plan.get("music")
    if music:
        mp = Path(music)
        music = mp if mp.is_absolute() else plan_dir / mp
        if not music.exists():
            die(f"music file not found: {music}")
    total, clip_durs = assemble(clips, out, music)
    if tts_clips:
        merge_voiceover_into_video(out, tts_clips, clip_durs, total)

    gif_path = out.with_suffix(".gif")
    write_gif(out, gif_path)
    srt_path, vtt_path = write_subtitles(out, plan, clip_durs, audio_by_key)
    announcement = write_announcement(out.parent / "announcement.md", plan, clip_durs)
    timings = out.parent / "timings.json"
    chapters = youtube_chapter_lines(chapter_labels(plan), clip_durs)
    timings.write_text(json.dumps({
        "durations": [round(d, 3) for d in clip_durs],
        "offsets": [round(x, 3) for x in clip_offsets(clip_durs)],
        "chapters": chapters,
    }, indent=2) + "\n", encoding="utf-8")

    if not a.keep_work:
        shutil.rmtree(work, ignore_errors=True)

    warn = []
    if total > 60:
        warn.append(f"video is {total:.0f}s; social announcements usually work best under 45s. Trim features or raise 'speed'.")
    print(json.dumps({
        "ok": True, "video": str(out), "thumbnail": str(thumb), "gif": str(gif_path),
        "subtitles": [str(srt_path), str(vtt_path)], "announcement": str(announcement),
        "plan": str(plan_path), "seconds": round(total, 1), "format": plan["format"],
        "chapters": chapters, "warnings": warn,
    }, indent=2))


if __name__ == "__main__":
    main()

