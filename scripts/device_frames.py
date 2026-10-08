#!/usr/bin/env python3
"""Device frames for release videos.

Feature clips are scaled into a screen hole and overlaid on a background
with one chrome PNG (macOS, browser, glass, iPhone, laptop, iPad).
The chrome is rendered once; ffmpeg does every frame.
"""
import base64
import colorsys
import html
import mimetypes
import re
from pathlib import Path

DEVICE_FRAMES = ("macos", "browser", "glass", "iphone", "laptop", "ipad")

BACKGROUND_PRESETS = (
    "gradient-sky",      # default — light blue, like a product mockup
    "gradient-studio",   # light gray
    "gradient-radial",   # accent glow on dark
    "gradient-mesh",
    "gradient-aurora",
    "gradient-sunset",
    "gradient-ocean",
)


def validate_device_frame(value):
    """Return a frame name, or None when the field is empty or off."""
    if value is None:
        return None
    v = str(value).strip().lower()
    if v in ("", "none", "false", "off"):
        return None
    if v not in DEVICE_FRAMES:
        return None
    return v


def validate_frame_background(value):
    """Return (kind, payload). kind is preset, color, or image.

    Empty means the sky preset. A non-preset, non-hex value is an image path.
    """
    if value is None or not str(value).strip():
        return ("preset", "gradient-sky")
    v = str(value).strip()
    if v.lower() in BACKGROUND_PRESETS:
        return ("preset", v.lower())
    if re.match(r"^#([0-9a-fA-F]{3}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})$", v):
        return ("color", v)
    return ("image", v)


def frame_label(plan):
    """Window title or address-bar text."""
    if plan.get("device_frame") == "browser":
        from urllib.parse import urlparse
        host = urlparse(plan.get("base_url") or "").netloc
        return host or "yoursite.com"
    return (plan.get("product") or "Untitled")[:48]


# ── color ────────────────────────────────────────────────────────────

def _hex_to_rgb(h):
    h = h.lstrip("#")
    if len(h) == 3:
        h = h[0] * 2 + h[1] * 2 + h[2] * 2
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def _rgb_to_hex(r, g, b):
    return "#{:02x}{:02x}{:02x}".format(int(r), int(g), int(b))


def _hsl_shift(hex_color, h_shift=0, s_mult=1.0, l_mult=1.0):
    r, g, b = _hex_to_rgb(hex_color[:7])
    h, l, s = colorsys.rgb_to_hls(r / 255, g / 255, b / 255)
    h = (h + h_shift) % 1.0
    s = min(1.0, max(0.0, s * s_mult))
    l = min(1.0, max(0.0, l * l_mult))
    r2, g2, b2 = colorsys.hls_to_rgb(h, l, s)
    return _rgb_to_hex(r2 * 255, g2 * 255, b2 * 255)


def accent_palette(accent):
    accent = accent if str(accent).startswith("#") and len(str(accent)) >= 4 else "#6366f1"
    return {
        "base": accent[:7],
        "light": _hsl_shift(accent, s_mult=0.6, l_mult=1.45),
        "dark": _hsl_shift(accent, s_mult=1.1, l_mult=0.35),
        "comp": _hsl_shift(accent, h_shift=0.5, s_mult=0.7, l_mult=0.9),
        "warm": _hsl_shift(accent, h_shift=0.08, s_mult=1.2, l_mult=1.1),
    }


def _bg_gradient_sky(_pal):
    return (
        "background:#6eb7ef;"
        "background:radial-gradient(ellipse at 50% 38%, #d7f0ff 0%, #8ecbf8 46%, #4a9fe6 100%);"
    )


def _bg_gradient_studio(_pal):
    return "background:linear-gradient(180deg, #f7f7f8 0%, #e4e4e8 100%);"


def _bg_gradient_radial(pal):
    return (
        f"background:{pal['dark']};"
        f"background:radial-gradient(ellipse at 20% 50%, {pal['base']}55 0%, transparent 50%),"
        f"radial-gradient(ellipse at 80% 20%, {pal['warm']}44 0%, transparent 50%),"
        f"radial-gradient(ellipse at 50% 90%, {pal['comp']}33 0%, transparent 60%),"
        f"linear-gradient(135deg, {pal['dark']} 0%, #0b0d17 100%);"
    )


def _bg_gradient_mesh(pal):
    return (
        f"background:#0b0d17;"
        f"background:radial-gradient(at 0% 0%, {pal['base']}44 0%, transparent 50%),"
        f"radial-gradient(at 100% 0%, {pal['warm']}44 0%, transparent 50%),"
        f"radial-gradient(at 100% 100%, {pal['comp']}33 0%, transparent 50%),"
        f"radial-gradient(at 0% 100%, {pal['light']}22 0%, transparent 50%),"
        f"linear-gradient(160deg, {pal['dark']} 0%, #0f1019 100%);"
    )


def _bg_gradient_aurora(pal):
    return (
        f"background:linear-gradient(180deg, #0a0c14 0%, {pal['dark']} 100%);"
        f"background:linear-gradient(120deg, {pal['base']}33 0%, transparent 40%),"
        f"linear-gradient(240deg, {pal['comp']}33 0%, transparent 40%),"
        f"linear-gradient(0deg, {pal['warm']}22 30%, transparent 60%),"
        f"linear-gradient(180deg, #0a0c14 0%, {pal['dark']} 100%);"
    )


def _bg_gradient_sunset(pal):
    warm2 = _hsl_shift(pal["base"], h_shift=-0.05, s_mult=1.3, l_mult=0.8)
    hot = _hsl_shift(pal["base"], h_shift=-0.1, s_mult=1.4, l_mult=0.7)
    return f"background:linear-gradient(160deg, {hot} 0%, {warm2} 35%, {pal['base']} 65%, {pal['dark']} 100%);"


def _bg_gradient_ocean(pal):
    cool = _hsl_shift(pal["base"], h_shift=0.12, s_mult=0.8, l_mult=0.6)
    deep = _hsl_shift(pal["base"], h_shift=0.15, s_mult=0.9, l_mult=0.3)
    return f"background:linear-gradient(170deg, {deep} 0%, {cool} 40%, {pal['base']}88 70%, {pal['light']}44 100%);"


_BG = {
    "gradient-sky": _bg_gradient_sky,
    "gradient-studio": _bg_gradient_studio,
    "gradient-radial": _bg_gradient_radial,
    "gradient-mesh": _bg_gradient_mesh,
    "gradient-aurora": _bg_gradient_aurora,
    "gradient-sunset": _bg_gradient_sunset,
    "gradient-ocean": _bg_gradient_ocean,
}


def background_css(bg_kind, bg_payload, accent):
    if bg_kind == "color":
        return f"background:{bg_payload};"
    if bg_kind == "image":
        p = Path(bg_payload)
        mime = mimetypes.guess_type(str(p))[0] or "image/png"
        uri = f"data:{mime};base64,{base64.b64encode(p.read_bytes()).decode()}"
        return f"background:#111 url('{uri}') center/cover no-repeat;"
    pal = accent_palette(accent)
    return _BG.get(bg_payload, _bg_gradient_sky)(pal)


# ── geometry ─────────────────────────────────────────────────────────

def _even(n):
    n = int(n)
    return n if n % 2 == 0 else n - 1


def _fit(aspect, max_w, max_h):
    """Largest even rectangle of the given aspect inside the box."""
    max_w = max(2, _even(max_w))
    max_h = max(2, _even(max_h))
    if max_w / max_h > aspect:
        h = max_h
        w = _even(h * aspect)
    else:
        w = max_w
        h = _even(w / aspect)
    if w > max_w:
        w = max_w
        h = _even(w / aspect)
    if h > max_h:
        h = max_h
        w = _even(h * aspect)
    return max(2, w), max(2, h)


def _center(outer, inner):
    return max(0, _even((outer - inner) / 2))


def layout(device, W, H):
    """Screen hole and outer device box, in even canvas pixels.

    macos, browser, glass, laptop, and ipad keep the video aspect so the
    whole clip stays visible. iphone is a portrait handset; the clip is
    cover-cropped into that screen.
    """
    u = max(W, H) / 1920
    aspect = W / H
    margin_x = _even(W * 0.07)
    margin_y = _even(H * 0.075)

    def px(n, floor=1):
        return max(floor, int(round(n * u)))

    lay = {
        "W": W, "H": H, "kind": device,
        "dot": px(12, 6), "font": px(14, 10), "pad": px(16, 8), "gap": px(8, 4),
        "shadow": px(28, 8), "radius": px(12, 6),
        "title_h": 0, "bezel": 0, "top_bezel": 0, "bot_bezel": 0,
        "hinge": 0, "base_h": 0, "base_extra": 0,
        "island_w": 0, "island_h": 0,
    }

    if device in ("macos", "browser"):
        lay["title_h"] = _even(px(52 if device == "browser" else 44, 28))
        lay["radius"] = px(10, 6)
        sw, sh = _fit(aspect, W - 2 * margin_x, H - 2 * margin_y - lay["title_h"])
        outer_h = sh + lay["title_h"]
        x = _center(W, sw)
        y = _center(H, outer_h)
        lay["screen"] = {"x": x, "y": y + lay["title_h"], "w": sw, "h": sh}
        lay["device"] = {"x": x, "y": y, "w": sw, "h": outer_h}
        r = lay["radius"]
        lay["radius_css"] = f"0 0 {r}px {r}px"
    elif device == "glass":
        pad = _even(px(14, 8))
        lay["bezel"] = pad
        lay["radius"] = px(22, 10)
        sw, sh = _fit(aspect, W - 2 * margin_x - 2 * pad, H - 2 * margin_y - 2 * pad)
        outer_w, outer_h = sw + 2 * pad, sh + 2 * pad
        x, y = _center(W, outer_w), _center(H, outer_h)
        lay["screen"] = {"x": x + pad, "y": y + pad, "w": sw, "h": sh}
        lay["device"] = {"x": x, "y": y, "w": outer_w, "h": outer_h}
        inner = max(4, lay["radius"] - pad)
        lay["radius_css"] = f"{inner}px"
    elif device == "iphone":
        bezel = _even(px(16, 8))
        lay["bezel"] = bezel
        lay["radius"] = px(48, 18)
        lay["island_w"] = px(118, 36)
        lay["island_h"] = _even(px(34, 12))
        if H > W:
            max_w, max_h = _even(W * 0.78), _even(H * 0.90)
        else:
            max_w, max_h = _even(W * 0.34), _even(H * 0.90)
        sw, sh = _fit(9 / 19.5, max_w - 2 * bezel, max_h - 2 * bezel)
        outer_w, outer_h = sw + 2 * bezel, sh + 2 * bezel
        x, y = _center(W, outer_w), _center(H, outer_h)
        lay["screen"] = {"x": x + bezel, "y": y + bezel, "w": sw, "h": sh}
        lay["device"] = {"x": x, "y": y, "w": outer_w, "h": outer_h}
        inner = max(8, lay["radius"] - bezel)
        lay["radius_css"] = f"{inner}px"
    elif device == "ipad":
        bezel = _even(px(18, 8))
        lay["bezel"] = bezel
        lay["radius"] = px(26, 10)
        sw, sh = _fit(aspect, W - 2 * margin_x - 2 * bezel, H - 2 * margin_y - 2 * bezel)
        outer_w, outer_h = sw + 2 * bezel, sh + 2 * bezel
        x, y = _center(W, outer_w), _center(H, outer_h)
        lay["screen"] = {"x": x + bezel, "y": y + bezel, "w": sw, "h": sh}
        lay["device"] = {"x": x, "y": y, "w": outer_w, "h": outer_h}
        inner = max(6, lay["radius"] - bezel)
        lay["radius_css"] = f"{inner}px"
    else:
        # laptop: screen keeps the video aspect; hinge and base sit under it
        side = _even(px(16, 8))
        top = _even(px(28, 12))
        bot = _even(px(16, 8))
        hinge = _even(px(10, 4))
        base_h = _even(px(16, 6))
        extra = _even(px(48, 12))
        lay.update(bezel=side, top_bezel=top, bot_bezel=bot, hinge=hinge, base_h=base_h, base_extra=extra)
        lay["radius"] = px(12, 6)
        sw, sh = _fit(
            aspect,
            W - 2 * margin_x - 2 * extra - 2 * side,
            H - 2 * margin_y - top - bot - hinge - base_h,
        )
        lid_w, lid_h = sw + 2 * side, top + sh + bot
        total_h = lid_h + hinge + base_h
        total_w = lid_w + 2 * extra
        ox, oy = _center(W, total_w), _center(H, total_h)
        lid_x = ox + extra
        lay["screen"] = {"x": lid_x + side, "y": oy + top, "w": sw, "h": sh}
        lay["device"] = {"x": ox, "y": oy, "w": total_w, "h": total_h}
        lay["radius_css"] = f"{max(4, lay['radius'] - side)}px"

    s, d = lay["screen"], lay["device"]
    # ponytail: if rounding pushed a box outside, nudge it back. Upgrade path is a second fit pass.
    for box in (s, d):
        box["x"] = min(max(0, box["x"]), max(0, W - box["w"]))
        box["y"] = min(max(0, box["y"]), max(0, H - box["h"]))
    return lay


# ── html ─────────────────────────────────────────────────────────────

def _page(w, h, body, extra_css=""):
    return f"""<!doctype html><meta charset="utf-8"><style>
*{{box-sizing:border-box;margin:0;padding:0}}
html,body{{width:{w}px;height:{h}px;overflow:hidden;background:transparent}}
{extra_css}
</style><body>{body}</body>"""


def background_html(bg_kind, bg_payload, accent, W, H):
    css = background_css(bg_kind, bg_payload, accent)
    return _page(W, H, "", f"body{{{css}}}")


def mask_html(screen):
    r = screen.get("radius_css", "0")
    return _page(
        screen["w"], screen["h"],
        f'<div style="width:100%;height:100%;background:#fff;border-radius:{r}"></div>',
    )


def _dots(lay):
    d = lay["dot"]
    spans = []
    for color in ("#ff5f57", "#febc2e", "#28c840"):
        spans.append(
            f'<i style="width:{d}px;height:{d}px;border-radius:50%;background:{color};display:block"></i>'
        )
    return "".join(spans)


def _window_shadow(lay):
    d = lay["device"]
    r = lay["radius"]
    sh = lay["shadow"]
    return (
        f'<div style="position:absolute;left:{d["x"]}px;top:{d["y"]}px;width:{d["w"]}px;height:{d["h"]}px;'
        f'border-radius:{r}px;background:transparent;'
        f'box-shadow:0 0 0 1px rgba(0,0,0,.14),0 {sh // 2}px {sh * 2}px rgba(0,0,0,.22)"></div>'
    )


def _chrome_window(lay, label, toolbar_css):
    d = lay["device"]
    t = lay["title_h"]
    r = lay["radius"]
    return _window_shadow(lay) + f"""
<div style="position:absolute;left:{d['x']}px;top:{d['y']}px;width:{d['w']}px;height:{t}px;
  border-radius:{r}px {r}px 0 0;{toolbar_css}
  display:flex;align-items:center;justify-content:center;
  font:600 {lay['font']}px -apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;color:#4a4a4a">
  <div style="position:absolute;left:{lay['pad']}px;top:0;height:100%;display:flex;align-items:center;gap:{lay['gap']}px">{_dots(lay)}</div>
  {label}
</div>"""


def _chrome_macos(lay, label):
    return _chrome_window(
        lay, label,
        "background:linear-gradient(#f6f6f6,#e4e4e4);box-shadow:inset 0 -1px 0 #c8c8c8;",
    )


def _chrome_browser(lay, label):
    d = lay["device"]
    t = lay["title_h"]
    r = lay["radius"]
    pill_w = max(80, int(d["w"] * 0.42))
    pill_h = max(16, lay["font"] + 12)
    return _window_shadow(lay) + f"""
<div style="position:absolute;left:{d['x']}px;top:{d['y']}px;width:{d['w']}px;height:{t}px;
  border-radius:{r}px {r}px 0 0;background:#f4f4f6;box-shadow:inset 0 -1px 0 #e1e1e4">
  <div style="position:absolute;left:{lay['pad']}px;top:0;height:100%;display:flex;align-items:center;gap:{lay['gap']}px">{_dots(lay)}</div>
  <div style="position:absolute;left:50%;top:50%;transform:translate(-50%,-50%);
    width:{pill_w}px;height:{pill_h}px;border-radius:{pill_h}px;background:#fff;
    border:1px solid #e4e4e7;display:flex;align-items:center;justify-content:center;
    font:{lay['font']}px -apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;color:#8a8a8e;
    overflow:hidden;white-space:nowrap">{label}</div>
</div>"""


def _chrome_glass(lay, _label):
    d = lay["device"]
    return f"""
<div style="position:absolute;left:{d['x']}px;top:{d['y']}px;width:{d['w']}px;height:{d['h']}px;
  border-radius:{lay['radius']}px;border:{lay['bezel']}px solid rgba(255,255,255,.32);
  background:transparent;box-shadow:0 0 0 1px rgba(255,255,255,.18),0 {lay['shadow'] // 2}px {lay['shadow'] * 2}px rgba(0,0,0,.28)"></div>"""


def _side_button(lay, side, top_pct, height):
    d = lay["device"]
    bw = max(4, lay["dot"] // 2)
    # Outer edge of the bezel, so the button reads against the frame.
    x = d["x"] + d["w"] - bw if side == "right" else d["x"]
    y = d["y"] + int(d["h"] * top_pct)
    return (
        f'<i style="position:absolute;left:{x}px;top:{y}px;width:{bw}px;height:{height}px;'
        f'background:#8e8e93;border-radius:{max(2, bw // 2)}px"></i>'
    )


def _chrome_iphone(lay, _label):
    d = lay["device"]
    s = lay["screen"]
    iw, ih = lay["island_w"], lay["island_h"]
    iw = min(iw, s["w"] - 20)
    ix = s["x"] + (s["w"] - iw) // 2
    iy = s["y"] + max(6, lay["pad"] // 2)
    h = max(18, int(d["h"] * 0.07))
    return f"""
<div style="position:absolute;left:{d['x']}px;top:{d['y']}px;width:{d['w']}px;height:{d['h']}px;
  border-radius:{lay['radius']}px;border:{lay['bezel']}px solid #1c1c1e;background:transparent;
  box-shadow:0 0 0 1px #000,0 {lay['shadow'] // 2}px {lay['shadow'] * 2}px rgba(0,0,0,.35)"></div>
{_side_button(lay, "left", 0.16, h)}
{_side_button(lay, "left", 0.28, int(h * 0.7))}
{_side_button(lay, "right", 0.22, int(h * 1.3))}
<div style="position:absolute;left:{ix}px;top:{iy}px;width:{iw}px;height:{ih}px;background:#000;border-radius:{ih // 2}px"></div>"""


def _chrome_ipad(lay, _label):
    d = lay["device"]
    cam = max(6, lay["dot"] // 2)
    cx = d["x"] + d["w"] // 2 - cam // 2
    cy = d["y"] + lay["bezel"] // 2 - cam // 2
    return f"""
<div style="position:absolute;left:{d['x']}px;top:{d['y']}px;width:{d['w']}px;height:{d['h']}px;
  border-radius:{lay['radius']}px;border:{lay['bezel']}px solid #1c1c1e;background:transparent;
  box-shadow:0 0 0 1px #000,0 {lay['shadow'] // 2}px {lay['shadow'] * 2}px rgba(0,0,0,.32)"></div>
<div style="position:absolute;left:{cx}px;top:{cy}px;width:{cam}px;height:{cam}px;border-radius:50%;background:#3a3a3c"></div>"""


def _chrome_laptop(lay, _label):
    s = lay["screen"]
    side, top, bot = lay["bezel"], lay["top_bezel"], lay["bot_bezel"]
    lid_x = s["x"] - side
    lid_y = s["y"] - top
    lid_w = s["w"] + 2 * side
    lid_h = top + s["h"] + bot
    r = lay["radius"]
    cam = max(6, lay["dot"] // 2)
    hinge_y = lid_y + lid_h
    base_y = hinge_y + lay["hinge"]
    base_x = lid_x - lay["base_extra"]
    base_w = lid_w + 2 * lay["base_extra"]
    sh = lay["shadow"]
    return f"""
<div style="position:absolute;left:{lid_x}px;top:{lid_y}px;width:{lid_w}px;height:{lid_h}px;
  border-radius:{r}px;background:transparent;
  border-top:{top}px solid #1c1c1e;border-bottom:{bot}px solid #1c1c1e;
  border-left:{side}px solid #1c1c1e;border-right:{side}px solid #1c1c1e;
  box-shadow:0 {sh // 3}px {sh * 2}px rgba(0,0,0,.30)"></div>
<div style="position:absolute;left:{lid_x + lid_w // 2 - cam // 2}px;top:{lid_y + top // 2 - cam // 2}px;
  width:{cam}px;height:{cam}px;border-radius:50%;background:#3a3a3c"></div>
<div style="position:absolute;left:{lid_x + 2}px;top:{hinge_y}px;width:{lid_w - 4}px;height:{lay['hinge']}px;
  background:linear-gradient(#3a3a40,#1a1a1e)"></div>
<div style="position:absolute;left:{base_x}px;top:{base_y}px;width:{base_w}px;height:{lay['base_h']}px;
  background:linear-gradient(#2c2c32,#141418);border-radius:0 0 {max(4, r // 2)}px {max(4, r // 2)}px;
  box-shadow:0 8px 16px rgba(0,0,0,.25)"></div>"""


_CHROME = {
    "macos": _chrome_macos,
    "browser": _chrome_browser,
    "glass": _chrome_glass,
    "iphone": _chrome_iphone,
    "laptop": _chrome_laptop,
    "ipad": _chrome_ipad,
}


def chrome_html(device, lay, label):
    safe = html.escape(label or "")
    body = _CHROME[device](lay, safe)
    return _page(lay["W"], lay["H"], body)


def render_frame_assets(browser, device, accent, bg_kind, bg_payload, label, W, H, dest_dir):
    """Render background, chrome, and screen mask PNGs. Returns paths + screen rect."""
    lay = layout(device, W, H)
    dest = Path(dest_dir)
    dest.mkdir(parents=True, exist_ok=True)
    bg = dest / "frame_bg.png"
    chrome = dest / "frame_chrome.png"
    mask = dest / "frame_mask.png"
    _shot(browser, background_html(bg_kind, bg_payload, accent, W, H), W, H, bg, False)
    _shot(browser, chrome_html(device, lay, label), W, H, chrome, True)
    s = lay["screen"]
    _shot(browser, mask_html(lay["screen"]), s["w"], s["h"], mask, True)
    return {"bg": bg, "chrome": chrome, "mask": mask, "screen": s, "layout": lay}


def _shot(browser, markup, w, h, dest, transparent):
    ctx = browser.new_context(viewport={"width": int(w), "height": int(h)}, device_scale_factor=1)
    try:
        page = ctx.new_page()
        page.set_content(markup, wait_until="load")
        if "url('" in markup:
            page.wait_for_timeout(60)
        page.screenshot(path=str(dest), omit_background=transparent, type="png")
    finally:
        ctx.close()


def _self_check():
    assert validate_device_frame("iPad") == "ipad"
    assert validate_device_frame("MacOS") == "macos"
    assert validate_device_frame("none") is None
    assert validate_device_frame("toaster") is None
    assert validate_frame_background(None) == ("preset", "gradient-sky")
    assert validate_frame_background("#abc") == ("color", "#abc")
    assert validate_frame_background("assets/bg.jpg") == ("image", "assets/bg.jpg")
    assert frame_label({"device_frame": "browser", "base_url": "https://example.com/docs"}) == "example.com"
    for device in DEVICE_FRAMES:
        for size in ((1920, 1080), (1080, 1920), (1080, 1080), (320, 180)):
            lay = layout(device, *size)
            W, H = size
            s, d = lay["screen"], lay["device"]
            for box in (s, d):
                assert box["w"] > 0 and box["h"] > 0, (device, size, box)
                assert box["x"] >= 0 and box["y"] >= 0, (device, size, box)
                assert box["x"] + box["w"] <= W, (device, size, box)
                assert box["y"] + box["h"] <= H, (device, size, box)
            assert s["w"] % 2 == 0 and s["h"] % 2 == 0, (device, size, s)
            assert s["x"] >= d["x"] and s["y"] >= d["y"]
            assert s["x"] + s["w"] <= d["x"] + d["w"]
            assert s["y"] + s["h"] <= d["y"] + d["h"]
    print("device_frames ok")


if __name__ == "__main__":
    _self_check()
