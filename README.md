# 🎬 Release Announcement Video Skill

[![Agent Skill](https://img.shields.io/badge/Agent%20Skill-Antigravity%20%7C%20Cursor%20%7C%20Claude%20%7C%20Windsurf-blue)](https://github.com)
[![npm version](https://img.shields.io/badge/npm-npx%20release--announcement--video-red)](https://npmjs.com)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-brightgreen.svg)](https://python.org)
[![Playwright](https://img.shields.io/badge/Playwright-Chromium-red.svg)](https://playwright.dev)

Turn any git release, tag, or commit into a **ready-to-post announcement video** and **social media copy** (𝕏/Twitter, LinkedIn, and Markdown changelogs).

The video is rendered from **real, headless browser sessions** of the live application with:
- ✨ Smooth, human-like animated mouse movements and click ripples
- 🎯 Dynamic spotlight highlights focusing on key UI actions
- 🏷️ Bottom benefit captions for silent viewing
- 🎨 Branded intros, feature cards, and outro cards
- 🎞️ FFmpeg crossfade transitions and 12-frame contact sheet generation
- 📁 Organized outputs saved sequentially by commit message: `public/announcement-videos/01_<commit_slug>_<hash>.mp4`

---

## ⚡ Installation Options

### Option A: Via NPX (Direct from NPM or GitHub)
```bash
# When published to npm:
npx release-announcement-video add

# Or directly from GitHub repository (no npm publish needed):
npx github:Harmish001/release-announcement-video add
```

### Option B: Local CLI Link (For development / local use)
Run this once in the skill folder:
```bash
npm link
```
Then run from **any project folder** on your machine:
```bash
release-announcement-video add
```

### Target Specific AI Agents / Code Editors:
```bash
# Cursor IDE (.cursor/skills/)
npx release-announcement-video add --agent cursor

# Claude Code (.claude/skills/)
npx release-announcement-video add --agent claude

# Antigravity / Google AI (.agents/skills/)
npx release-announcement-video add --agent antigravity

# Windsurf / Cascade (.windsurf/skills/)
npx release-announcement-video add --agent windsurf

# Install globally for your machine
npx release-announcement-video add --global
```

| Supported Editor / Agent | Skill Directory Location |
|---|---|
| **Antigravity / Gemini** | `.agents/skills/release-announcement-video` |
| **Cursor IDE** | `.cursor/skills/release-announcement-video` |
| **Claude Code** | `.claude/skills/release-announcement-video` |
| **Windsurf / Cascade** | `.windsurf/skills/release-announcement-video` |
| **GitHub Copilot / VS Code** | `.agents/skills/release-announcement-video` |
| **Cline / Roo Code** | `.agents/skills/release-announcement-video` |

---

## 🤖 Using with AI Agent Chat (`/release-announcement-video`)

Once added, you can trigger the skill directly in any AI Agent chat using slash commands or prompts:

```text
/release-announcement-video http://localhost:3000
/release-announcement-video http://localhost:3000 --format vertical
/release-announcement-video https://preview.app --from v1.0.0 --to v1.1.0
/release-announcement-video http://localhost:3000 features: Dark Mode, CSV Export
```

Or plain natural language:
> *"Make a release announcement video for release v1.4.0 running on http://localhost:3000"*
> *"Generate a vertical announcement video for our latest commit on localhost"*

The AI agent will automatically run the 1-command engine, record the UI, and deliver the MP4 video and copy!

---

## 🎥 1-Command Video Generation (CLI)

Generate an entire release announcement video + social copy in **one single command**:

```bash
# Via NPX:
npx release-announcement-video generate --url http://localhost:3000

# Or via Python:
python scripts/auto_release.py --url http://localhost:3000
```

### Options:
```bash
# Vertical video for TikTok / Instagram Reels / YouTube Shorts:
npx release-announcement-video generate --url http://localhost:3000 --format vertical

# Target a specific release tag range:
npx release-announcement-video generate --url https://staging.myapp.com --from v1.0.0 --to v1.1.0
```

This single command automatically:
1. 🔍 Discovers git release commits and changed route files
2. 🌐 Inspects the live web app for interactive buttons, inputs, and elements
3. 📋 Generates a verified `plan.json`
4. 🎬 Records the browser session with smooth cursor movements and spotlights
5. 🎞️ Encodings the video and 12-frame `.contact.png` preview
6. ✍️ Writes `announcement.md` with X/Twitter, LinkedIn, and Changelog copy

---

## 🩺 System Health Check

Verify your environment dependencies in one step:

```bash
npx release-announcement-video doctor
```

### Prerequisites:
- **Python 3.10+**
- **Playwright** + Chromium: `pip install playwright && playwright install chromium`
- **FFmpeg & FFprobe** on system PATH

---

## 🛠️ Step-by-Step Custom Workflow

If you want fine-grained control over the choreography, you can run individual steps:

### Step 1: Gather Release Changes
```bash
python scripts/gather_release.py --repo . [--from v1.0.0] [--to v1.1.0]
```

### Step 2: Inspect Live Selectors
```bash
python scripts/inspect_page.py http://localhost:3000/my-feature [--mobile]
```

### Step 3: Validate `plan.json`
```bash
python scripts/make_video.py plan.json --validate-only
```

### Step 4: Render Video & Contact Sheet
```bash
python scripts/make_video.py plan.json -o public/announcement-videos/01_feat_add_builder_40f0d48.mp4
```

---

## 📁 Output Structure

All assets are cleanly organized in your project:
```text
public/
  └── announcement-videos/
      ├── 01_feat_add_workflow_builder_40f0d48.mp4
      ├── 01_feat_add_workflow_builder_40f0d48.contact.png
      ├── 01_feat_add_workflow_builder_40f0d48_plan.json
      └── announcement.md
```

---

## 📄 License
MIT © [Harmish Patel](https://github.com/Harmish001)
