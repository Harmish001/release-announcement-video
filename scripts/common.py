"""Shared plan helpers. No browser, no ffmpeg."""
import json
import re
from pathlib import Path

XFADE = 0.4
VOICE_LEAD = 0.25
FALLBACK_ACCENT = "#6366f1"
PHONE = {"width": 390, "height": 844}
PHONE_DPR = 3

DEMO_WARNING = (
    "storage_state loads a saved login. Use a demo account. "
    "Auto mode refuses delete, pay, checkout, and logout controls, "
    "but other clicks still change data in that session."
)

# Whole words only. "Remove filter" and "Reset view" stay allowed.
DESTRUCTIVE = re.compile(
    r"\b(delete|destroy|wipe|erase|purge|deactivate|unsubscribe|"
    r"purchase|checkout|logout|log\s?out|signout|sign\s?out|"
    r"close\s+account|remove\s+account|delete\s+account|"
    r"pay|buy|confirm\s+payment|place\s+order)\b",
    re.I,
)


def package_version():
    pkg = Path(__file__).resolve().parents[1] / "package.json"
    try:
        return json.loads(pkg.read_text(encoding="utf-8"))["version"]
    except Exception:
        return "0.0.0"


def lead(text):
    """Uppercase the first character only. Keeps 'OAuth' intact."""
    text = (text or "").strip()
    if not text:
        return text
    return text[:1].upper() + text[1:]


def clip_words(text, limit):
    text = (text or "").strip()
    if len(text) <= limit:
        return text
    cut = text[:limit].rsplit(" ", 1)[0]
    return cut or text[:limit]


def is_destructive(text):
    return bool(DESTRUCTIVE.search(text or ""))


def accent_is_auto(value):
    return value is None or str(value).strip().lower() in ("", "auto")


def output_size(fmt):
    if fmt == "vertical":
        return 1080, 1920
    if fmt == "square":
        return 1080, 1080
    return 1920, 1080


def default_viewport(fmt):
    if fmt == "vertical":
        return dict(PHONE)
    w, h = output_size(fmt)
    return {"width": w, "height": h}


def default_dpr(fmt):
    return PHONE_DPR if fmt == "vertical" else 1


def seconds_for_narration(audio_s):
    """Scene must outlast speech so the next line does not overlap across the crossfade."""
    if not audio_s:
        return None
    return float(audio_s) + VOICE_LEAD + XFADE + 0.15


def apply_narration_timing(plan, audio_by_key):
    intro = audio_by_key.get("intro")
    if intro:
        plan["intro_seconds"] = round(max(float(plan.get("intro_seconds") or 3), seconds_for_narration(intro)), 2)
    outro = audio_by_key.get("outro")
    if outro:
        plan["outro_seconds"] = round(max(float(plan.get("outro_seconds") or 3.5), seconds_for_narration(outro)), 2)
    for i, feat in enumerate(plan.get("features") or []):
        dur = audio_by_key.get(f"feat{i}")
        if not dur:
            continue
        need_ms = int(seconds_for_narration(dur) * 1000)
        feat["hold_ms"] = max(int(feat.get("hold_ms") or 1000), need_ms)
    return plan


_STORY_STARTS = (
    "it ", "it's ", "we ", "you ", "this ", "that ", "here's ", "here is ",
    "meet ", "first", "then", "next", "finally", "and ", "from ", "after ",
    "now ", "watch ", "let's ", "lets ", "today ", "welcome ", "before ",
)


def _clean(text):
    return " ".join((text or "").split()).strip()


def _sentence(text):
    t = _clean(text)
    if not t:
        return ""
    t = t[0].upper() + t[1:]
    if t[-1] not in ".!?":
        t += "."
    return t


def _clause(text):
    """Lowercase a normal word. Leave 'OAuth' and 'API' alone."""
    t = _clean(text).rstrip(".!?")
    if len(t) >= 2 and t[0].isupper() and t[1].islower():
        t = t[0].lower() + t[1:]
    return t


def _is_prose(text):
    t = _clean(text)
    if not t:
        return False
    if len(t.split()) >= 16:
        return True
    return t.count(".") + t.count("!") + t.count("?") >= 2


def _starts_story(text):
    low = _clean(text).lower()
    return any(low.startswith(prefix) for prefix in _STORY_STARTS)


def _speak_cta(cta):
    c = _clean(cta)
    for prefix in ("https://", "http://"):
        if c.lower().startswith(prefix):
            c = c[len(prefix):]
    return c.strip("/")


def _intro_line(plan, beat_count):
    custom = _clean(plan.get("intro_narration") or "")
    if custom and (_is_prose(custom) or _starts_story(custom)):
        return _sentence(custom)
    product = _clean(plan.get("product") or "")
    headline = _clean(plan.get("headline") or "")
    sub = _clean(plan.get("subhead") or "")
    bits = []
    if custom:
        if product:
            bits.append(f"Meet {product}.")
        bits.append(_sentence(custom))
    elif product and headline and headline.lower() != product.lower():
        bits.append(f"Meet {product}.")
        bits.append(_sentence(headline))
    elif product:
        bits.append(f"Meet {product}.")
    elif headline:
        bits.append(_sentence(headline))
    if sub and sub.lower() not in (headline or "").lower() and sub.lower() not in (custom or "").lower():
        bits.append(_sentence(sub))
    if beat_count > 1:
        bits.append("Let me show you how it comes together.")
    elif not bits:
        bits.append("Let me show you what changed.")
    return " ".join(bits)


def _beat_line(text, index, count):
    if _is_prose(text) or _starts_story(text):
        return _sentence(text)
    if count == 1:
        return f"Here's what changed. {_sentence(text)}"
    if index == 0:
        return f"It starts here. {_sentence(text)}"
    if index == count - 1:
        return f"And finally, {_clause(text)}."
    prefix = ("From there", "Then", "After that", "Next")[(index - 1) % 4]
    return f"{prefix}, {_clause(text)}."


def _outro_line(plan):
    custom = _clean(plan.get("outro_narration") or "")
    if custom:
        return _sentence(custom)
    product = _clean(plan.get("product") or "")
    who = product or "this release"
    line = f"And that's the story of {who}."
    host = _speak_cta(plan.get("cta"))
    if host:
        line += f" Try it at {host}."
    return line


def narration_lines(plan):
    """Spoken lines for one continuous story. Short captions get the links."""
    indexed = []
    for i, feat in enumerate(plan.get("features") or []):
        text = _clean(feat.get("narration") or feat.get("caption") or "")
        if text:
            indexed.append((i, text))
    lines = [{"key": "intro", "clip_idx": 0, "text": _intro_line(plan, len(indexed))}]
    count = len(indexed)
    for n, (i, text) in enumerate(indexed):
        lines.append({"key": f"feat{i}", "clip_idx": i + 1, "text": _beat_line(text, n, count)})
    lines.append({
        "key": "outro",
        "clip_idx": len(plan.get("features") or []) + 1,
        "text": _outro_line(plan),
    })
    return lines


def apply_note(plan, note):
    """Apply one edit phrase. Return False when the phrase is unknown."""
    n = (note or "").strip().lower()
    if not n:
        return False
    if "zoom more" in n or "zoom in" in n:
        plan["zoom"] = round(min(2.2, float(plan.get("zoom") or 1.28) + 0.25), 2)
    elif "zoom less" in n or "zoom out" in n:
        plan["zoom"] = round(max(1.0, float(plan.get("zoom") or 1.28) - 0.2), 2)
    elif "shorten the intro" in n or "shorter intro" in n:
        plan["intro_seconds"] = round(max(1.2, float(plan.get("intro_seconds") or 3) * 0.65), 2)
    elif "shorten the outro" in n or "shorter outro" in n:
        plan["outro_seconds"] = round(max(1.2, float(plan.get("outro_seconds") or 3.5) * 0.65), 2)
    elif "shorten" in n or "make it shorter" in n:
        for feat in plan.get("features") or []:
            feat["speed"] = round(min(2.5, float(feat.get("speed") or 1) * 1.35), 2)
            if feat.get("hold_ms"):
                feat["hold_ms"] = max(400, int(int(feat["hold_ms"]) * 0.7))
    else:
        return False
    return True


def clip_offsets(durations, xfade=XFADE):
    offsets = [0.0]
    acc = 0.0
    for d in durations[:-1]:
        acc += float(d) - xfade
        offsets.append(max(acc, 0.0))
    return offsets


def format_timestamp(seconds):
    # round to centiseconds first. 1.4 - 0.4 is 0.9999999999999999 in float, which floors to 0.
    s = max(0, int(round(float(seconds), 2)))
    return f"{s // 60}:{s % 60:02d}"


def chapter_labels(plan):
    labels = ["Intro"]
    for feat in plan.get("features") or []:
        card = feat.get("card") or {}
        labels.append(feat.get("caption") or card.get("title") or "Scene")
    labels.append("Outro")
    return labels


def youtube_chapter_lines(labels, durations, xfade=XFADE):
    return [f"{format_timestamp(start)} {label}" for label, start in zip(labels, clip_offsets(durations, xfade))]


def voice_mix_filter(delays_ms, with_bed):
    """ffmpeg filter_complex. with_bed keeps the music already muxed on input 0."""
    parts, labels = [], []
    for i, delay in enumerate(delays_ms):
        parts.append(f"[{i + 1}:a]adelay={int(delay)}|{int(delay)}[a{i}]")
        labels.append(f"[a{i}]")
    parts.append(
        f"{''.join(labels)}amix=inputs={len(labels)}:normalize=0:dropout_transition=0,volume=1.35[vo]"
    )
    if with_bed:
        parts.append("[vo][0:a]amix=inputs=2:normalize=0:duration=longest:dropout_transition=0[aout]")
    else:
        parts.append("[vo]anull[aout]")
    return ";".join(parts)


def scene_hash(payload):
    import hashlib
    blob = json.dumps(payload, sort_keys=True, default=str, ensure_ascii=False)
    return hashlib.sha256(blob.encode()).hexdigest()[:20]


def cta_href(cta):
    cta = (cta or "").strip()
    if not cta:
        return ""
    if cta.startswith(("http://", "https://")):
        return cta
    if " " not in cta and "." in cta:
        return "https://" + cta.removeprefix("//")
    return cta


def change_lines(plan):
    changes = [c.strip() for c in (plan.get("changes") or []) if str(c).strip()]
    if changes:
        return changes
    return [(f.get("narration") or f.get("caption") or "").strip() for f in plan.get("features") or [] if (f.get("narration") or f.get("caption"))]


def announcement_markdown(plan, durations=None):
    product = plan.get("product") or "App"
    version = plan.get("version") or ""
    headline = plan.get("headline") or ""
    subhead = (plan.get("subhead") or "").strip()
    features = plan.get("features") or []
    changes = change_lines(plan)
    href = cta_href(plan.get("cta"))
    labels = chapter_labels(plan)
    chapters = ""
    if durations and len(durations) == len(labels):
        chapters = "\n".join(youtube_chapter_lines(labels, durations))
    bullets = "\n".join(f"- {line}" for line in changes) or "\n".join(
        f"- {f.get('caption')}" for f in features if f.get("caption")
    )
    tags = []
    for raw in [product, "release", *[f.get("caption") or "" for f in features]]:
        raw = raw.strip()
        if raw and raw not in tags:
            tags.append(raw)
    version_bit = f" ({version})" if version else ""
    link = f"\n{href}\n" if href else "\n"
    chapter_block = f"\n{chapters}\n" if chapters else "\n"
    return f"""# {product}{version_bit}

## YouTube

**Title:** {product}: {headline}

**Description:**

{subhead or headline}
{chapter_block}
{bullets}
{link}
**Tags:** {", ".join(tags)}

## X

{headline}

{bullets}
{link}
## LinkedIn

{product}{version_bit}. {subhead or headline}

{bullets}
{link}
## Changelog

### {version or "Unreleased"}

{bullets}
"""


def write_announcement(path, plan, durations=None):
    Path(path).write_text(announcement_markdown(plan, durations), encoding="utf-8")
    return Path(path)


def _srt_time(seconds):
    ms = int(round(max(0, seconds) * 1000))
    h, ms = divmod(ms, 3_600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def _vtt_time(seconds):
    return _srt_time(seconds).replace(",", ".")


def subtitle_cues(plan, durations, audio_by_key=None):
    audio_by_key = audio_by_key or {}
    offsets = clip_offsets(durations)
    cues = []
    for line in narration_lines(plan):
        idx = line["clip_idx"]
        if idx >= len(offsets) or not line["text"]:
            continue
        start = offsets[idx] + VOICE_LEAD
        audio_s = audio_by_key.get(line["key"])
        if audio_s:
            end = start + float(audio_s)
        else:
            scene_end = offsets[idx] + float(durations[idx]) - 0.2
            end = scene_end
        if idx + 1 < len(offsets):
            end = min(end, offsets[idx + 1] - 0.05)
        if end <= start:
            end = start + 0.4
        cues.append((start, end, line["text"]))
    return cues


def write_subtitles(stem_path, plan, durations, audio_by_key=None):
    """Write stem.srt and stem.vtt. stem_path is the mp4 path or any path with the right stem."""
    stem = Path(stem_path).with_suffix("")
    cues = subtitle_cues(plan, durations, audio_by_key)
    srt, vtt = [], ["WEBVTT", ""]
    for n, (start, end, text) in enumerate(cues, 1):
        srt.append(f"{n}\n{_srt_time(start)} --> {_srt_time(end)}\n{text}\n")
        vtt.append(f"{_vtt_time(start)} --> {_vtt_time(end)}\n{text}\n")
    srt_path = stem.with_suffix(".srt")
    vtt_path = stem.with_suffix(".vtt")
    srt_path.write_text("\n".join(srt), encoding="utf-8")
    vtt_path.write_text("\n".join(vtt), encoding="utf-8")
    return srt_path, vtt_path


def selector_report(plan, known_selectors):
    known = set(known_selectors or [])
    missing, blocked, idle = [], [], []
    for i, feat in enumerate(plan.get("features") or []):
        if feat.get("card") or feat.get("establishing"):
            continue
        steps = feat.get("steps") or []
        saw = False
        for j, step in enumerate(steps):
            sel = step.get("selector")
            if not sel:
                continue
            saw = True
            blob = f"{sel} {step.get('text', '')}"
            if is_destructive(blob):
                blocked.append({"feature": i, "step": j, "selector": sel})
            elif known and sel not in known:
                missing.append({"feature": i, "step": j, "selector": sel})
        actions = {s.get("action") for s in steps}
        if not saw and "goto" not in actions:
            idle.append(i)
        elif not (actions & {"click", "type", "hover", "highlight"}):
            idle.append(i)
    return missing, blocked, idle


def before_card(frm, files, commits):
    lines = []
    for f in (files or [])[:5]:
        lines.append(f"{f['path']}  +{f.get('added', 0)} -{f.get('deleted', 0)}")
    if not lines:
        lines = [lead(c.get("subject") or "") for c in (commits or [])[:5]]
        lines = [ln for ln in lines if ln]
    if not lines:
        lines = ["No diff against the previous tag."]
    label = frm or "the previous release"
    return {
        "caption": f"Before {label}",
        "narration": f"Before {label}, this is what the release changes.",
        "hold_ms": 2800,
        "card": {"title": f"Before {label}", "lines": lines},
    }


def before_url_feature(frm, url):
    label = frm or "the previous release"
    return {
        "caption": f"Before {label}",
        "narration": f"This is the product at {label}, before this release.",
        "hold_ms": 1200,
        "establishing": True,
        "steps": [
            {"action": "goto", "url": url},
            {"action": "wait", "ms": 1200},
            {"action": "scroll", "y": 220, "ms": 700},
        ],
    }


if __name__ == "__main__":
    assert lead("Add OAuth login") == "Add OAuth login"
    assert lead("add OAuth login") == "Add OAuth login"
    assert accent_is_auto(None) and accent_is_auto("auto") and accent_is_auto("")
    assert not accent_is_auto("#6366f1")
    assert is_destructive("Delete account") and is_destructive("Pay now")
    assert not is_destructive("Export") and not is_destructive("Remove filter")
    plan = {"intro_seconds": 3, "outro_seconds": 3.5, "features": [{"hold_ms": 800}], "zoom": 1.28}
    assert apply_note(plan, "shorten the intro") and plan["intro_seconds"] < 3
    assert apply_note(plan, "zoom more") and plan["zoom"] > 1.28
    assert not apply_note(plan, "make it sparkle")
    apply_narration_timing(plan, {"feat0": 5})
    assert plan["features"][0]["hold_ms"] >= 5000
    graph = voice_mix_filter([250, 4000], with_bed=True)
    assert "[0:a]" in graph and "adelay=250|250" in graph
    lines = youtube_chapter_lines(["Intro", "Export"], [3.0, 4.0])
    assert lines[0].startswith("0:00") and lines[1].startswith("0:02")
    assert format_timestamp(1.4 - 0.4) == "0:01"
    story = narration_lines({
        "product": "PixelDesk",
        "headline": "Dark mode",
        "cta": "https://pixeldesk.app",
        "features": [{"caption": "Switch to dark mode"}, {"caption": "Add OAuth login"}],
    })
    assert story[0]["text"].startswith("Meet PixelDesk")
    assert "comes together" in story[0]["text"]
    assert story[1]["text"].startswith("It starts here.")
    assert story[2]["text"].startswith("And finally, add OAuth login.")
    assert "oAuth" not in story[2]["text"]
    assert story[3]["text"].startswith("And that's the story of PixelDesk.")
    assert "pixeldesk.app" in story[3]["text"]
    kept = narration_lines({
        "product": "PixelDesk",
        "headline": "Search",
        "intro_narration": "Meet PixelDesk. Today we ship search that keeps up with you.",
        "features": [{"narration": "You open search, type a word, and the list narrows while you are still typing."}],
        "outro_narration": "That is the whole release, and it is live now.",
    })
    assert kept[0]["text"].startswith("Meet PixelDesk. Today")
    assert kept[1]["text"].startswith("You open search")
    assert kept[2]["text"].startswith("That is the whole release")
    print("ok")
