---
name: release-announcement-video
description: Turn a software release or feature into a ready-to-post Full HD announcement or tutorial video plus social copy. Reads git changes or inspects the live UI, records high-fidelity feature walkthroughs in a real browser (animated cursor, click ripples/glows/sparkles, captions, spotlight), matches the site's brand theme color, adds synchronized voice-over audio, and renders a 1080p Full HD MP4 in landscape (YouTube, X, LinkedIn) or vertical (Shorts, Reels, TikTok). Use this whenever the user types /release-announcement-video, /release-video, or asks for a release video, tutorial video, how-to-use walkthrough, changelog video, "what's new" clip, feature demo, or product announcement.
compatibility: Needs python3, playwright with Chromium, and ffmpeg/ffprobe on PATH. edge-tts is used for synchronized voiceover audio.
---

# Release Announcement & Tutorial Video Generator (v2.1)

A release or feature goes in; a stunning **1080p Full HD video**, **thumbnail preview**, and ready-to-post **social copy (YouTube, 𝕏/Twitter, LinkedIn, Changelog)** come out.

---

## 🎯 Slash Command & AI Agent Instructions

When triggered via slash command (`/release-announcement-video`, `/release-video`, `/announce-release`) or when asked to make a tutorial / how-to video:

### How to Process User Intent:
1. **Tutorial / "How to Use" / Specific Feature Walkthrough:**
   - If the user specifies a tool or specific user flow (e.g. `create a video showing how to use the export tool on http://localhost:3000` or `make a walkthrough for the signup flow`):
     - **Step 1:** Inspect the page (`python scripts/inspect_page.py <url>`) or review the workspace source code (`tools/`, `components/`, `pages/`, `app/`) to understand the exact interactive steps (inputs, buttons, uploads, dropdowns, result outputs).
     - **Step 2:** Write a clean, realistic `plan.json` under `public/announcement-videos/<seq>_<slug>/plan.json` covering the full end-to-end user journey with clear benefit-driven captions.
     - **Step 3:** Render the 1080p video:
       ```bash
       python scripts/make_video.py public/announcement-videos/<seq>_<slug>/plan.json -o public/announcement-videos/<seq>_<slug>/video.mp4
       ```
     - **Step 4:** Generate `announcement.md` containing YouTube Title/Description/Tags, 𝕏/Twitter, LinkedIn, and Markdown changelog copy.

2. **Automated 1-Command Release Discovery:**
   - When announcing general releases or git updates:
     ```bash
     python scripts/auto_release.py --url <url> [--format landscape|vertical]
     ```

---

## ⚡ Key Features & Quality Standards

- **📺 1080p Full HD Video**: Pristine crisp rendering (1920x1080 landscape, 1080x1920 vertical) with H.264 high profile.
- **🎨 Auto-Extracted Brand Theme**: Inspects the site's live DOM, CSS variables, and buttons to match the exact brand accent color for cards, glow ripples, badges, and highlights.
- **🎙️ Synchronized AI Voice-Over**: Captions and headlines are narrated with neural TTS and delayed to synchronize with each scene.
- **📁 Clean 3-File Folder Structure**: Each output directory under `public/announcement-videos/<folder_name>/` contains:
  1. `video.mp4` (or `<name>.mp4`)
  2. `thumbnail.png` (high-res video thumbnail / contact sheet)
  3. `announcement.md` (complete YouTube details, social copy, changelog)
  *(All temporary and plan files are cleaned up automatically)*.

---

## 🛠️ Options & Customizations

| Flag / Plan field | Values | Description |
|---|---|---|
| `--format` / `format` | `landscape` (1920x1080) · `vertical` (1080x1920) | Aspect ratio for YouTube/Web vs Shorts/Reels |
| `--click-effect` / `click_effect` | `ripple` (default) · `sparkle` · `glow` | Click animation injected into browser frames |
| `--nav-transition` / `nav_transition` | `fade` (default) · `slide` · `zoom` | Smooth transition on page navigation |
| `--voiceover-voice` | e.g. `en-US-AriaNeural`, `en-US-GuyNeural` | edge-tts voice selection |
| `--accent` | e.g. `#f97316` | Override brand color (defaults to auto-extract) |

---

## 📦 Distribution & Installation

Install into any project or AI agent workspace:
```bash
npx release-announcement-video add
```
Or generate directly:
```bash
npx release-announcement-video generate --url http://localhost:3000
```

