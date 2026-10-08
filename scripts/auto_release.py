#!/usr/bin/env python3
"""1-Command Release Video & Announcement Generator.

Combines release discovery, UI inspection, plan creation, video rendering, and
social copy generation into a single automated command.

Usage:
  python scripts/auto_release.py --url http://localhost:3000
  python scripts/auto_release.py --url https://preview.app --from v1.0.0 --to v1.1.0 --format vertical
"""
import argparse
import json
import os
import re
import shutil
import socket
import subprocess
import sys
from pathlib import Path

# Ensure UTF-8 output on Windows consoles
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent


def is_port_open(host, port):
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(0.5)
            return s.connect_ex((host, port)) == 0
    except Exception:
        return False


def detect_local_dev_url():
    """Check common local dev ports (3000, 5173, 8080, 8000, 4200, 3001)."""
    ports = [3000, 5173, 8080, 8000, 4200, 3001]
    for p in ports:
        if is_port_open("127.0.0.1", p):
            return f"http://localhost:{p}"
    return "http://localhost:3000"


def get_product_name(repo_path):
    pkg = Path(repo_path) / "package.json"
    if pkg.exists():
        try:
            data = json.loads(pkg.read_text(encoding="utf-8"))
            if data.get("name"):
                name = data["name"].split("/")[-1].replace("-", " ").replace("_", " ").title()
                return name
        except Exception:
            pass
    return Path(repo_path).resolve().name.replace("-", " ").replace("_", " ").title()


def slugify(text):
    text = re.sub(r"[^\w\s-]", "", text).strip().lower()
    return re.sub(r"[-\s]+", "_", text)[:40] or "feature"


def get_next_sequence_number(output_dir):
    out_path = Path(output_dir)
    if not out_path.exists():
        return "01"
    existing = list(out_path.iterdir())
    nums = []
    for f in existing:
        m = re.match(r"^(\d+)_", f.name)
        if m:
            nums.append(int(m.group(1)))
    next_num = max(nums, default=0) + 1
    return f"{next_num:02d}"


def inspect_elements(url, mobile=False, storage_state=None):
    """Find interactive elements on the page."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return []

    elements = []
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            opts = {"viewport": {"width": 540, "height": 960} if mobile else {"width": 1280, "height": 720}}
            if mobile:
                opts.update(is_mobile=True, has_touch=True)
            if storage_state and Path(storage_state).exists():
                opts["storage_state"] = storage_state
            page = browser.new_context(**opts).new_page()
            page.goto(url, wait_until="load", timeout=12000)
            try:
                page.wait_for_load_state("networkidle", timeout=3000)
            except Exception:
                pass
            
            elements = page.evaluate(r"""() => {
                const q = 'button, a[href], input, [role=button], [data-testid]';
                const esc = (s) => s.replace(/"/g, '\\"');
                const out = [];
                for (const el of document.querySelectorAll(q)) {
                    const r = el.getBoundingClientRect();
                    if (r.width < 5 || r.height < 5) continue;
                    const text = (el.innerText || el.value || '').trim().replace(/\s+/g, ' ').slice(0, 40);
                    let sel = null;
                    if (el.dataset.testid) sel = `[data-testid="${esc(el.dataset.testid)}"]`;
                    else if (el.id && !/\d{3,}/.test(el.id)) sel = '#' + CSS.escape(el.id);
                    else if (text && ['BUTTON', 'A'].includes(el.tagName)) sel = `${el.tagName.toLowerCase()}:has-text("${esc(text.slice(0, 25))}")`;
                    if (sel) out.push({ tag: el.tagName.toLowerCase(), text, selector: sel });
                }
                return out.slice(0, 30);
            }""")
            browser.close()
    except Exception as e:
        print(f"[Warning] Live UI inspection encountered: {e}", file=sys.stderr)
    return elements


def auto_build_plan(url, repo_path, from_ref, to_ref, fmt="landscape", manual_features=None,
                    product_override=None, headline_override=None, storage_state=None, music=None,
                    accent=None, click_effect=None, nav_transition=None, voiceover=False,
                    voiceover_voice=None, custom_effects=None, device_frame=None, frame_background=None):
    """Automatically build plan.json from git diff and live inspection."""
    product = product_override or get_product_name(repo_path)
    
    # Run gather_release logic
    import importlib.util
    spec = importlib.util.spec_from_file_location("gather_release", HERE / "gather_release.py")
    gr = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gr)
    
    commits = []
    routes = []
    to = to_ref or "HEAD"

    try:
        frm, to_calc = gr.default_range(repo_path, from_ref, to_ref)
        to = to_ref or to_calc
        rng = f"{frm}..{to}"
        commits = gr.parse_commits(repo_path, rng)
        files = gr.changed_files(repo_path, rng)
        ui_files = [f["path"] for f in files if not re.search(r"(^|/)(node_modules|\.next|dist)/|\.lock$|package-lock", f["path"])]
        routes = gr.guess_routes(ui_files)
    except Exception:
        pass

    version = to if to and to != "HEAD" else "Latest Release"
    
    # Handle manual features if provided
    selected = []
    if manual_features:
        for f in manual_features:
            selected.append({"hash": "manual", "subject": f.strip(), "type": "feat"})
    else:
        visible_commits = [c for c in commits if c["type"] in ("feat", "ui", "fix") or any(k in c["subject"].lower() for k in ["add", "new", "support", "update", "redesign", "improve"])]
        if not visible_commits:
            visible_commits = commits[:3] if commits else [{"hash": "head", "subject": "Latest feature updates and improvements", "type": "feat"}]
        selected = visible_commits[:3]

    lead_subject = selected[0]["subject"] if selected else "New Updates & Features"
    lead_slug = slugify(lead_subject)
    short_hash = selected[0]["hash"] if selected else "0000000"

    headline = headline_override or (f"Introducing {selected[0]['subject'].capitalize()}" if selected else f"What's New in {product}")

    features = []
    base_url = (url or "http://localhost:3000").rstrip("/")
    mobile = fmt == "vertical"

    inspected = inspect_elements(base_url, mobile=mobile, storage_state=storage_state)

    for i, c in enumerate(selected):
        subj = c["subject"]
        caption = subj[:45].capitalize()
        steps = []
        
        target_route = routes[i % len(routes)] if routes else "/"
        steps.append({"action": "goto", "url": target_route})
        
        matched_el = None
        if inspected:
            words = [w.lower() for w in re.findall(r"\w+", subj) if len(w) > 3]
            for el in inspected:
                if any(w in el["text"].lower() or w in el["selector"].lower() for w in words):
                    matched_el = el
                    break
            if not matched_el and len(inspected) > i:
                matched_el = inspected[i]

        if matched_el:
            if matched_el["tag"] == "input":
                steps.append({"action": "type", "selector": matched_el["selector"], "text": "Quick demo"})
            else:
                steps.append({"action": "click", "selector": matched_el["selector"]})
            steps.append({"action": "highlight", "selector": matched_el["selector"], "ms": 1200})
        else:
            steps.append({"action": "wait", "ms": 1000})
            steps.append({"action": "scroll", "y": 200, "ms": 800})
            steps.append({"action": "wait", "ms": 1000})

        features.append({
            "caption": caption,
            "speed": 1.0,
            "hold_ms": 1200,
            "steps": steps,
        })

    # Dynamic voice selection if not explicitly set
    chosen_voice = voiceover_voice
    if not chosen_voice or chosen_voice.lower() in ("auto", "dynamic"):
        try:
            from voices import recommend_voice
            chosen_voice = recommend_voice(topic=f"{product} {headline}")
        except Exception:
            chosen_voice = "en-US-AriaNeural"

    plan = {
        "product": product,
        "version": version,
        "headline": headline,
        "subhead": f"Explore the latest enhancements in {product}",
        "base_url": base_url,
        "format": fmt,
        # accent: leave as default so make_video auto-extracts site theme;
        # only override if user explicitly passed --accent
        "accent": accent or "#6366f1",
        "cta": base_url.replace("http://", "").replace("https://", ""),
        "features": features,
        # New capabilities
        "click_effect": click_effect or "ripple",
        "nav_transition": nav_transition or "fade",
        "voiceover": voiceover,
        "voiceover_voice": chosen_voice,
        "custom_effects": custom_effects or [],
    }

    if storage_state:
        plan["storage_state"] = storage_state
    if music:
        plan["music"] = music
    if device_frame:
        plan["device_frame"] = device_frame
    if frame_background:
        plan["frame_background"] = frame_background

    return plan, lead_slug, short_hash


def generate_announcement_copy(plan, output_dir):
    """Generate announcement.md with X, LinkedIn, YouTube metadata, and Markdown Changelog."""
    product = plan.get("product", "App")
    version = plan.get("version", "Latest")
    headline = plan.get("headline", "")
    subhead = plan.get("subhead", "")
    cta = plan.get("cta", "Check it out")
    features = plan.get("features", [])

    bullets = "\n".join([f"- {f.get('caption')}" for f in features])
    prod_clean = product.replace(" ", "")
    tags_list = [product, f"{product} update", "software demo", "tutorial", "feature release", "how to use", "guide"]
    tags_str = ", ".join([f'"{t}"' for t in tags_list])
    hashtags = f"#{prod_clean} #SoftwareUpdate #TechDemo #Productivity #HowTo #ReleaseNotes"

    md_content = f"""# 🚀 {product} Release Announcement ({version})

---

## 📺 YouTube Video Details

### **Title:**
{product} - {headline} ({version} Walkthrough & Demo)

### **Description:**
Discover what's new in **{product}** ({version})! 🚀
{subhead if subhead else headline}

In this video, we walk you through the latest features and demonstrate how to use them step-by-step:

📌 **Key Highlights & Features:**
{chr(10).join([f'• {f.get("caption")}' for f in features])}

🔗 **Try it live here:**
https://{cta}

---

👉 Don't forget to **Like**, **Subscribe**, and hit the **Bell icon** 🔔 to stay updated with new releases!

{hashtags}

### **Tags:**
{tags_str}

### **Category:**
Science & Technology / How-to & Style

---

## 🐦 𝕏 / Twitter Post
{headline} is here! 🎉

{chr(10).join([f'✨ {f.get("caption")}' for f in features])}

Try it live now: https://{cta} 👇

{hashtags}

---

## 💼 LinkedIn Post
We're excited to announce our latest update for **{product}** ({version})!

Here is what's new in this release:
{chr(10).join([f'• {f.get("caption")}' for f in features])}

Take a look at the video walkthrough and explore the update today:
🔗 https://{cta}

{hashtags}

---

## 📝 Markdown Changelog Entry
### {version} - {headline}
{bullets}

---
*Generated automatically by Release Announcement Video Skill.*
"""
    copy_path = Path(output_dir) / "announcement.md"
    copy_path.write_text(md_content, encoding="utf-8")
    return copy_path


def main():
    print("🎬 Release Announcement Video Generator v2.1 (Full HD 1080p)")
    ap = argparse.ArgumentParser(description="1-Command Release Video & Announcement Generator")
    ap.add_argument("--version", action="version", version="2.1.0")
    ap.add_argument("--url", help="Base URL where the live app is running (default: auto-detected localhost or 3000)")
    ap.add_argument("--repo", default=".", help="Repository root path (default: current directory)")
    ap.add_argument("--from", dest="frm", help="Starting git ref or previous release tag")
    ap.add_argument("--to", help="Target git ref or current release tag (default: HEAD)")
    ap.add_argument("--format", choices=["landscape", "vertical"], default="landscape", help="Video format (landscape or vertical)")
    ap.add_argument("--features", help="Custom comma-separated list of feature names/captions")
    ap.add_argument("--product", help="Override product name")
    ap.add_argument("--headline", help="Override intro headline")
    ap.add_argument("--accent", help="Override brand accent color (e.g. #6366f1). Defaults to auto-extract from site.")
    ap.add_argument("--click-effect", choices=["ripple", "sparkle", "glow"], default="ripple",
                    help="Click animation effect (default: ripple)")
    ap.add_argument("--nav-transition", choices=["fade", "slide", "zoom"], default="fade",
                    help="In-browser page navigation transition (default: fade)")
    ap.add_argument("--no-voiceover", action="store_true",
                    help="Disable AI voice-over (enabled by default)")
    ap.add_argument("--voiceover-voice", default="en-US-AriaNeural",
                    help="edge-tts voice name (default: en-US-AriaNeural)")
    ap.add_argument("--custom-effects", default=None,
                    help='JSON array of custom per-element effects, e.g. \'{"effect":"sparkle","selector":"button.cta"}\''
                         " (can be passed multiple times or as JSON array string)")
    ap.add_argument("--storage-state", help="Playwright storage auth JSON state file")
    ap.add_argument("--music", help="Audio file path for background music")
    ap.add_argument("--output", "-o", help="Custom output MP4 path")
    ap.add_argument("--plan-only", action="store_true", help="Generate plan.json only without rendering video")
    ap.add_argument("--device-frame", choices=["macos", "browser", "glass", "iphone", "laptop", "ipad"],
                    default=None, help="Wrap feature clips in a device frame template")
    ap.add_argument("--frame-background", default=None,
                    help="Background for device frame: gradient-sky (default), gradient-studio, "
                         "gradient-radial, gradient-mesh, gradient-aurora, gradient-sunset, "
                         "gradient-ocean, a hex color, or an image path")
    a = ap.parse_args()

    url = a.url or detect_local_dev_url()
    manual_features = [f.strip() for f in a.features.split(",") if f.strip()] if a.features else None

    # Parse custom effects if provided as JSON string
    custom_effects = None
    if a.custom_effects:
        try:
            custom_effects = json.loads(a.custom_effects)
            if isinstance(custom_effects, dict):
                custom_effects = [custom_effects]
        except json.JSONDecodeError:
            print(f"[Warning] --custom-effects could not be parsed as JSON: {a.custom_effects}",
                  file=sys.stderr)

    voiceover_enabled = not a.no_voiceover
    print(f"\n🎬 [1/4] Discovering release changes & inspecting UI from {url}...")
    plan, lead_slug, short_hash = auto_build_plan(
        url=url,
        repo_path=a.repo,
        from_ref=a.frm,
        to_ref=a.to,
        fmt=a.format,
        manual_features=manual_features,
        product_override=a.product,
        headline_override=a.headline,
        storage_state=a.storage_state,
        music=a.music,
        accent=a.accent,
        click_effect=a.click_effect,
        nav_transition=a.nav_transition,
        voiceover=voiceover_enabled,
        voiceover_voice=a.voiceover_voice,
        custom_effects=custom_effects,
        device_frame=a.device_frame,
        frame_background=a.frame_background,
    )

    out_dir = Path(a.repo) / "public" / "announcement-videos"
    out_dir.mkdir(parents=True, exist_ok=True)

    seq = get_next_sequence_number(out_dir)
    
    if a.output:
        video_output = Path(a.output)
        video_output.parent.mkdir(parents=True, exist_ok=True)
        feature_dir = video_output.parent
        plan_path = feature_dir / (video_output.stem + "_plan.json")
    else:
        folder_name = f"{seq}_{lead_slug}_{short_hash}"
        feature_dir = out_dir / folder_name
        feature_dir.mkdir(parents=True, exist_ok=True)
        video_output = feature_dir / "video.mp4"
        plan_path = feature_dir / "plan.json"

    plan_path.write_text(json.dumps(plan, indent=2), encoding="utf-8")
    print(f"✨ [2/4] Generated video plan: {plan_path}")

    if a.plan_only:
        print(f"Plan saved. Run 'python scripts/make_video.py {plan_path} -o {video_output}' to render.")
        return

    print(f"🎥 [3/4] Recording live browser session and encoding video ({a.format})...")
    make_video_script = HERE / "make_video.py"
    cmd = [sys.executable, str(make_video_script), str(plan_path), "-o", str(video_output)]
    res = subprocess.run(cmd)

    if res.returncode != 0:
        print(f"\n❌ Error rendering video. Check logs above.", file=sys.stderr)
        sys.exit(res.returncode)

    print(f"✍️  [4/4] Generating social announcement copy...")
    copy_path = generate_announcement_copy(plan, feature_dir)
    thumbnail_file = feature_dir / "thumbnail.jpg"

    # Strictly ensure only .mp4, .md, and .jpg files remain in the output folder
    for item in list(feature_dir.iterdir()):
        if item.is_dir():
            shutil.rmtree(item, ignore_errors=True)
        elif item.is_file():
            if item.suffix.lower() not in (".mp4", ".md", ".jpg", ".jpeg"):
                item.unlink(missing_ok=True)

    print(f"\n" + "=" * 60)
    print(f"🎉 SUCCESS! Release announcement package ready:")
    print(f"   📹 Video:         {video_output}")
    print(f"   🖼️  Thumbnail:     {thumbnail_file}")
    print(f"   📋 Social Copy:   {copy_path}")
    print(f"=" * 60 + "\n")


if __name__ == "__main__":
    main()
