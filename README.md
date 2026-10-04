# 🎬 Release Announcement Video Skill

[![Agent Skill](https://img.shields.io/badge/Agent%20Skill-Antigravity%20%7C%20Hermes%20%7C%20Claude-blue)](https://github.com)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-brightgreen.svg)](https://python.org)
[![Playwright](https://img.shields.io/badge/Playwright-Chromium-red.svg)](https://playwright.dev)

Turn any git release, tag, or commit into a **ready-to-post announcement video** and **social media copy** (X/Twitter, LinkedIn, and Markdown changelogs).

The video is rendered from **real, headless browser sessions** of the live application with:
- ✨ Smooth, human-like animated mouse movements and click ripples
- 🎯 Dynamic spotlight highlights focusing on key UI actions
- 🏷️ Bottom benefit captions for silent viewing
- 🎨 Branded intros, feature cards, and outro cards
- 🎞️ FFmpeg crossfade transitions and contact sheet generation
- 📁 Organized outputs saved sequentially by commit message: `public/announcement-videos/01_<commit_slug>_<hash>.mp4`

---

## 🚀 Quick Start

### 1. Requirements
- **Python 3.10+**
- **Playwright** + Chromium: `pip install playwright && playwright install chromium`
- **FFmpeg & FFprobe** on system PATH

### 2. Add to your Project
Place this skill folder inside your AI agent skills directory:
```text
your-project/
  └── .agents/
      └── skills/
          └── release-announcement-video/
              ├── SKILL.md
              ├── scripts/
              └── references/
```

### 3. Usage with AI Agents
Simply prompt your AI coding agent:
> *"Make a release video for commit `abc1234` on `http://localhost:3000` (landscape)"*
> *"Generate announcement video for release `v1.2.0` in vertical format"*

---

## 🛠️ Manual CLI Workflow

### Step 1: Gather Release Changes & Suggested Name
```bash
python scripts/gather_release.py --repo . [--from v1.0.0] [--to v1.1.0]
```
Returns changed routes, categorized commits, and recommended video file names.

### Step 2: Inspect Live Web UI Selectors
```bash
python scripts/inspect_page.py http://localhost:3000/my-new-feature [--mobile]
```
Finds interactive buttons, inputs, and elements with verified CSS selectors.

### Step 3: Create & Validate `plan.json`
```bash
python scripts/make_video.py plan.json --validate-only
```

### Step 4: Render Video & Contact Sheet
```bash
python scripts/make_video.py plan.json -o public/announcement-videos/01_feat_add_builder_40f0d48.mp4
```

---

## 📁 Output Directory Convention

Videos and previews are saved in your project's public static assets directory:
```text
public/
  └── announcement-videos/
      ├── 01_feat_add_workflow_builder_40f0d48.mp4
      ├── 01_feat_add_workflow_builder_40f0d48.contact.png
      └── announcement.md
```

---

## 📄 License
MIT © [Harmish Patel](https://github.com/Harmish001)
