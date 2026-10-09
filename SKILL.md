---
name: release-announcement-video
description: Turn a software release or feature into a ready-to-post announcement or tutorial video plus social copy. Reads git changes or inspects the live UI, records a browser walkthrough, matches the site accent when asked, adds edge-tts voice-over, and renders landscape, vertical, or square MP4. Use when the user asks for a release video, tutorial video, how-to walkthrough, changelog video, what's-new clip, feature demo, or product announcement.
compatibility: Needs python3, playwright with Chromium, and ffmpeg/ffprobe on PATH. edge-tts is used for voice-over. Version lives in package.json.
---

# Release announcement video

The agent writes the plan and checks the frames. The scripts render. Auto mode is a draft, not the source of truth.

## Workflow

1. Read the change (`python scripts/gather_release.py`) and the live page (`python scripts/inspect_page.py <url>`). Copy selectors from that JSON.
2. Ask which device frame to wrap the footage in: `macos`, `browser`, `glass`, `iphone`, `laptop`, `ipad`, or none. If they pick one, ask for a background image. No image means a preset (`gradient-sky` by default, or `gradient-studio`, `gradient-radial`, `gradient-mesh`, `gradient-aurora`, `gradient-sunset`, `gradient-ocean`, or a hex color). One frame wraps every feature clip. Intro and outro cards stay full-screen.
3. Write `public/announcement-videos/<seq>_<slug>/plan.json`. Write one spoken story across `intro_narration`, each feature `narration`, and `outro_narration`. Keep `caption` short. See `references/plan-format.md`. Set `device_frame` and `frame_background` from the answer.
4. Validate: `python scripts/make_video.py <plan.json> --validate-only`
5. Render: `python scripts/make_video.py <plan.json> -o <dir>/video.mp4`
6. Open `thumbnail.jpg` and the failure screenshots if the render exited non-zero. Fix the plan. Render again.

`python scripts/auto_release.py --url <url> --dry-run` only builds a draft plan and checks selectors. Do not record until the dry-run is clean and the steps match the page.

Output stays in `public/announcement-videos/`. Keep that path gitignored so the mp4s do not enter the app bundle or git history.

## Rules

- Selectors come from `inspect_page.py` or the DOM. Do not guess.
- Vertical video uses a phone viewport (390x844, device scale 3) and scales up to 1080x1920. Do not set a 1080x1920 CSS viewport.
- `accent: "auto"` reads the live site. A hex in the plan, including `#6366f1`, is kept.
- Voice-over is one story, not a list of points. Write `intro_narration`, each feature `narration`, and `outro_narration` so they read in order as a single narration. `caption` stays a short on-screen line. A short point is linked into the story before it is spoken. `voiceover_voice` adapts to the topic, or set `"voiceover_voice": "auto"`. Each scene is lengthened to fit the measured clip.
- Click and highlight zoom the whole template, device chrome and background included, with a smooth ease in and out. Set `zoom` to `1` to turn that off. Each framed feature clip opens and closes like a Mac window.
- `nav_transition` is `fade`, `slide`, or `zoom`. `zoom` opens and closes the page like a Mac window. With a device frame, that in-page zoom is a fade, and the window open/close is on the whole template.
- `--before-after` adds a before card from the previous tag. It does not checkout the worktree. To film the old UI, serve that tag and pass `--before-url`.
- `capture: "frames"` records a CDP screencast instead of Playwright's webm when the webm looks soft.
- `device_frame` wraps every feature clip in one device template: `macos`, `browser`, `glass`, `iphone`, `laptop`, `ipad`. Intro/outro cards stay full-screen. Ask before writing the plan. `frame_background` is the area around the device: `gradient-sky` (default), `gradient-studio`, `gradient-radial`, `gradient-mesh`, `gradient-aurora`, `gradient-sunset`, `gradient-ocean`, a hex color, or a path to an image. Accent-based presets follow `accent`. `gradient-sky` and `gradient-studio` stay light.
- Logged-in apps need `storage_state` from a demo account. Auto mode will not choose delete, pay, checkout, or logout controls. Other clicks still change data.

## Failure

A bad step exits non-zero, prints the feature index, the step, and the Playwright error, and saves a screenshot under the `rav_*/failures` folder next to the output.

## Feedback

Re-render the same plan:

```bash
python scripts/make_video.py plan.json -o video.mp4 --note "zoom more"
python scripts/make_video.py plan.json -o video.mp4 --note "zoom less"
python scripts/make_video.py plan.json -o video.mp4 --note "shorten the intro"
python scripts/make_video.py plan.json -o video.mp4 --note "shorten the outro"
python scripts/make_video.py plan.json -o video.mp4 --note "shorten"
```

Any other note exits 2. Edit `plan.json` for that change (a caption, a selector, `narration`, `hold_ms`). A scene cannot be shorter than its narration.

## Output

Only 3 clean files remain in the output folder: `video.mp4` (Full HD video), `thumbnail.jpg` (1280x720 cover image), and `announcement.md` (social copy and YouTube description). All intermediate and extra files are automatically cleaned up.
