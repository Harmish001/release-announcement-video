---
name: release-announcement-video
description: Turn a software release into a ready-to-post announcement video plus social copy. Reads the git range between two tags, picks the user-visible changes, records those features in a real browser (cursor, click ripples, captions, spotlight), adds branded intro and "what's new" cards, and renders an MP4 in landscape (X, YouTube, LinkedIn) or vertical (Shorts, Reels). Use this whenever the user wants a release video, changelog video, "what's new" clip, launch or feature demo video, product update video, or an announcement for a new version, tag, deploy or preview URL, even if they only say "make a video of what we shipped" or "announce this release". Also use when they give a website URL and a list of features and want a demo video recorded from the live pages.
compatibility: Needs python3, playwright with Chromium, and ffmpeg/ffprobe. The app must be reachable from where this runs (localhost dev server, a preview URL, or a public site). No voiceover is generated.
---

# Release announcement video

A release goes in; a short video, a post, and a changelog entry come out. The video is built from real recordings of the actual app, so every claim on screen has to be true. That is the whole point of the skill and the main way it can go wrong.

## Before starting: pin down three things

Ask only for what you cannot find yourself.

1. **Which release.** A repo path and tag range (`v1.3.0..v1.4.0`), or just a repo (default: the latest tag against the one before it). If the user only gave a URL and a feature list, skip to step 3 and treat their list as the release.
2. **Where the app is running.** Dev server, Vercel preview URL, or production. Recording a dev server is fine; recording production is better when the release is already live. If it needs login, see "Logged-in apps" below.
3. **Where it will be posted.** Landscape (X, YouTube, LinkedIn, website) or vertical (Shorts, Reels, TikTok, Stories). Default to landscape and say so.

## Workflow

### 1. Read the release

```bash
python3 scripts/gather_release.py --repo <path> [--from <tag>] [--to <tag>]
```

It returns commits grouped by type, files changed, `likely_routes` (a heuristic mapping of changed files to URL paths for Next.js and static sites), and any changelog excerpt.

### 2. Choose what goes in the video

Pick **2 to 4 changes a user can see or feel**. Judge by the diff and the commit bodies, not just commit subjects, because subjects lie ("improve dashboard" can be a one-line CSS tweak or a rewrite).

- Include: new features, visible UI changes, speed-ups the user can perceive, fixes to things users complained about.
- Leave out: refactors, dependency bumps, tests, CI, internal-only fixes. They can appear as a single bullet on the outro card at most.
- If nothing in the release is visible, tell the user that plainly and suggest a text-only changelog instead of manufacturing a video.
- Keep the total under about 45 seconds. A feature clip of 5 to 8 seconds is usually enough.

### 3. Look at the real app before writing steps

Never guess selectors. For each page you plan to record:

```bash
python3 scripts/inspect_page.py <url> [--mobile]
```

This lists clickable and typeable elements with ready-made selectors. If a feature is not reachable from the page (it needs data, a specific state, or a feature flag), work out how to reach that state, or tell the user what seed data is needed. Do not record an empty state and caption it as the feature.

### 4. Write plan.json and render

Read `references/plan-format.md` for the schema and the full action list.

**Output Naming & Location Convention:**
Always save videos sequentially inside `public/announcement-videos/` using the commit message slug and short hash:
`public/announcement-videos/<seq>_<commit_message_slug>_<short_hash>.mp4`
(e.g., `public/announcement-videos/01_feat_add_custom_workflow_builder_40f0d48.mp4`)

```bash
python3 scripts/make_video.py plan.json --validate-only
python3 scripts/make_video.py plan.json -o public/announcement-videos/01_feat_my_feature_abc1234.mp4
```

Write captions as short benefit statements, 35 characters or fewer when possible ("Search filters as you type"), one idea each. The caption is what the viewer reads with the sound off, which is how most people watch.

If the renderer exits with an error it names the failing feature and step and saves a screenshot of the page at that moment. Open the screenshot, fix the selector or the wait, and rerun. Do not work around a failing step by deleting it unless the feature genuinely cannot be shown.

### 5. Check the result with your eyes

Exit code 0 only means ffmpeg finished. Always:

- View the `.contact.png` the renderer writes next to the video. It shows 12 evenly spaced frames. Look for: blank or white frames, an error page or login wall, a cursor that never reaches its target, captions that do not match what is on screen, text cut off at the edges.
- Pull at least one full-size frame from the middle of a feature clip (`ffmpeg -ss <t> -i video.mp4 -frames:v 1 frame.png`) and view it.

Fix and rerun until the contact sheet shows what the captions claim. If you could not view the output, say so; do not describe a video you have not seen.

### 6. Write the copy

Save `announcement.md` next to the video with: an X/Twitter post (under 280 characters, hook first, link placeholder last), a LinkedIn version (3 to 5 short lines), and a changelog entry in the project's existing style.

- Every claim must trace to the diff or to something visible in the video. No invented metrics, speedups, or user counts. If the user supplies numbers, use them as given.
- Lead with what the user can now do, not with the version number.
- Write plain sentences. Skip words like "game-changing", "revolutionary", "supercharge".
- Leave `{{link}}` placeholders instead of making up URLs.

### 7. Deliver

Present the MP4 (and the vertical version if both were requested) and `announcement.md`. In one or two sentences, state what is in the video, anything you could not show, and any assumption you made (for example, "recorded against localhost with seed data").

## Logged-in apps

Many releases live behind a login. Use a throwaway or demo account with fake data, never a real customer's account or the user's personal one, because everything on screen ends up in a public video.

1. Save a session once: `playwright codegen --save-storage=auth.json <login-url>`, log in with the demo account, close the window.
2. Put `"storage_state": "auth.json"` in plan.json.
3. Delete `auth.json` when finished and remind the user not to commit it.

Before posting, tell the user to scan the video for emails, names, API keys, or other data that should not be public. You can spot obvious ones in the contact sheet, but you cannot guarantee there are none.

## Limits to be upfront about

- **No voiceover.** Output is captioned and silent unless the user supplies a music file they have the rights to (`"music"` in the plan).
- **Recording resolution is 1280x720 (landscape) or 540x960 (vertical)**, upscaled to 1080p. Text is readable but a touch softer than a native screen capture.
- **Network access differs by environment.** In a sandbox without internet access, only localhost or file URLs can be recorded. In Claude Code on the user's machine, any reachable URL works.
- **Heavy animation, video elements, WebGL, and canvas** may record poorly. Check the contact sheet.
- Sites that block automated browsers (bot protection, CAPTCHAs) cannot be recorded. Tell the user rather than retrying.

## Running this on every release

See `references/automation.md` for wiring this into CI so a video is produced when a tag is pushed. Read it only if the user asks for automation.
