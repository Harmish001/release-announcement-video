---
name: release-announcement-video
description: Turn a software release into a ready-to-post announcement video plus social copy. Reads the git range between two tags, picks the user-visible changes, records those features in a real browser (cursor, click ripples, captions, spotlight), adds branded intro and "what's new" cards, and renders an MP4 in landscape (X, YouTube, LinkedIn) or vertical (Shorts, Reels). Use this whenever the user types /release-announcement-video, /release-video, or asks for a release video, changelog video, "what's new" clip, launch or feature demo video, product update video, or an announcement for a new version, tag, deploy or preview URL.
compatibility: Needs python3, playwright with Chromium, and ffmpeg/ffprobe. The app must be reachable from where this runs (localhost dev server, a preview URL, or a public site).
---

# Release Announcement Video

A release goes in; a short video, a post, and a changelog entry come out. The video is built from real recordings of the actual app, so every claim on screen has to be true.

## 🎯 Slash Command & AI Agent Invocation

When triggered via slash command (e.g. `/release-announcement-video`, `/release-video`, `/announce-release`) or direct user prompt:

### How to Handle User Input:
1. **If the user provides a URL and/or parameters:**
   (e.g., `/release-announcement-video http://localhost:3000 --from v1.0.0 --to v1.1.0` or `/release-announcement-video http://localhost:3000 vertical`)
   $\rightarrow$ Directly run the 1-command generator passing their parameters:
   ```bash
   python scripts/auto_release.py --url <url> [options]
   ```

2. **If the user provides extra feature names or headline:**
   (e.g., `/release-announcement-video http://localhost:3000 features: Dark Mode, Filter Table`)
   $\rightarrow$ Pass them via `--features "Dark Mode, Filter Table"` or include them in the plan:
   ```bash
   python scripts/auto_release.py --url http://localhost:3000 --features "Dark Mode, Filter Table"
   ```

3. **If the user provides NO URL:**
   (e.g., `/release-announcement-video`)
   $\rightarrow$ Check if a local server is running (ports 3000, 5173, 8080, etc.), default to `http://localhost:3000`, or briefly confirm the URL with the user.

---

## ⚡ 1-Command Automated Pipeline

```bash
# Python:
python scripts/auto_release.py --url http://localhost:3000 [--from <tag>] [--to <tag>] [--format landscape|vertical]

# NPX CLI:
npx release-announcement-video generate --url http://localhost:3000
```

This automated step:
1. **Reads Git**: Gathers commit log, diff, and route mappings.
2. **Inspects Live DOM**: Discovers real button/input selectors on the running app.
3. **Builds Plan**: Creates `plan.json` with benefit-first captions.
4. **Renders Video**: Records animated browser session with spotlights and encodes MP4 + 12-frame contact sheet.
5. **Generates Social Copy**: Writes `announcement.md` (𝕏 / Twitter post, LinkedIn post, Markdown changelog) inside `public/announcement-videos/`.

---

## 🛠️ Custom Step-by-Step Workflow

If the user requests specific custom choreographies or manually edited steps:

### 1. Read the release
```bash
python scripts/gather_release.py --repo <path> [--from <tag>] [--to <tag>]
```

### 2. Inspect Live UI Selectors
```bash
python scripts/inspect_page.py <url> [--mobile]
```

### 3. Write `plan.json` and render
Read `references/plan-format.md` for the schema and action list.

**Output Naming & Location Convention:**
Always save videos sequentially inside `public/announcement-videos/`:
`public/announcement-videos/<seq>_<commit_message_slug>_<short_hash>.mp4`

```bash
python scripts/make_video.py plan.json --validate-only
python scripts/make_video.py plan.json -o public/announcement-videos/01_feat_my_feature_abc1234.mp4
```

### 4. Check the result with your eyes
- Inspect `.contact.png` (12-frame contact sheet) next to the MP4 to verify visual correctness.

### 5. Write the copy & Deliver
Save `announcement.md` with:
- **𝕏 / Twitter post** (<280 chars, hook first, link placeholder).
- **LinkedIn post** (3 to 5 benefit bullet points).
- **Markdown Changelog entry**.

---

## Logged-in apps
1. Save session once: `playwright codegen --save-storage=auth.json <login-url>`, log in with a demo/throwaway account.
2. Pass `--storage-state auth.json` to `auto_release.py` (or put `"storage_state": "auth.json"` in `plan.json`).
3. Delete `auth.json` when finished.
