# 🎬 Release Announcement & Tutorial Video Skill (v2.1)

[![Agent Skill](https://img.shields.io/badge/Agent%20Skill-Antigravity%20%7C%20Cursor%20%7C%20Claude%20%7C%20Windsurf-blue)](https://github.com)
[![npm version](https://img.shields.io/badge/npm-npx%20release--announcement--video-red)](https://npmjs.com)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-brightgreen.svg)](https://python.org)
[![Playwright](https://img.shields.io/badge/Playwright-Chromium-red.svg)](https://playwright.dev)

Turn any git release, tag, or web feature into a **1080p Full HD announcement or tutorial video**, **thumbnail preview**, and **ready-to-post social media copy** (YouTube, 𝕏/Twitter, LinkedIn, and Markdown changelogs).

---

## 🌟 Highlights & Capabilities

- 📺 **1080p Full HD Resolution**: Crystal-clear 1920x1080 landscape (YouTube/Web) or 1080x1920 vertical (Shorts/Reels/TikTok).
- 🎨 **Auto-Extracted Brand Theme**: Extracts your site's dominant brand accent color and matches all intro cards, badges, spotlights, and click animations.
- 🎙️ **Synchronized Neural AI Voice-Over**: High-fidelity TTS (via `edge-tts`) narrated and synchronized with each scene and feature caption.
- 📺 **Comprehensive YouTube Metadata**: Ready-to-use YouTube Title, Description (with timestamps, links, hashtags), Tags, and Category.
- 📁 **Clean 3-File Output**: Each video folder contains strictly:
  1. `video.mp4`
  2. `thumbnail.png`
  3. `announcement.md`

---

## ⚡ Installation Options

### Option A: Via NPX (Direct from NPM or GitHub)
```bash
# When published to npm:
npx release-announcement-video add

# Or directly from GitHub repository:
npx github:Harmish001/release-announcement-video add
```

### Option B: Local CLI Link
```bash
# Run once in the skill folder:
npm link

# Then run from any project:
release-announcement-video add
```

### Target Specific AI Agents / Code Editors:
```bash
npx release-announcement-video add --agent antigravity  # Antigravity / Gemini (.agents/skills/)
npx release-announcement-video add --agent cursor       # Cursor IDE (.cursor/skills/)
npx release-announcement-video add --agent claude       # Claude Code (.claude/skills/)
npx release-announcement-video add --agent windsurf     # Windsurf / Cascade (.windsurf/skills/)
npx release-announcement-video add --global             # Global installation
```

---

## 🤖 Using with AI Agents (`/release-announcement-video`)

Trigger the skill in your AI Agent chat with slash commands or natural language:

```text
/release-announcement-video http://localhost:3000
/release-announcement-video http://localhost:3000 create a video showing how to use the export tool
/release-announcement-video http://localhost:3000 --format vertical
```

---

## 🎥 1-Command Video Generation (CLI)

```bash
# Via NPX:
npx release-announcement-video generate --url http://localhost:3000

# Or via Python:
python scripts/auto_release.py --url http://localhost:3000
```

---

## 📁 Output Structure

Outputs are stored inside dedicated sequence folders under `public/announcement-videos/`:
```text
public/
  └── announcement-videos/
      └── 01_feature_walkthrough_demo/
          ├── video.mp4          # 1080p Full HD video with synchronized audio
          ├── thumbnail.png      # High-res video preview thumbnail
          └── announcement.md    # YouTube, X/Twitter, LinkedIn & Changelog copy
```

---

## 📄 License
MIT © [Harmish Patel](https://github.com/Harmish001)
