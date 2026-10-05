---
name: release-announcement-video
description: Turn a software release or feature into a ready-to-post announcement or tutorial video plus social copy. Reads git changes or inspects the live UI, records a browser walkthrough, matches the site accent when asked, adds edge-tts voice-over, and renders landscape, vertical, or square MP4. Use when the user asks for a release video, tutorial video, how-to walkthrough, changelog video, what's-new clip, feature demo, or product announcement.
compatibility: Needs python3, playwright with Chromium, and ffmpeg/ffprobe on PATH. edge-tts is used for voice-over. Version lives in package.json.
---

# Release announcement video

The agent writes the plan and checks the frames. The scripts render. Auto mode is a draft, not the source of truth.

## Workflow

1. Read the change (`python scripts/gather_release.py`) and the live page (`python scripts/inspect_page.py <url>`). Copy selectors from that JSON.
2. Write `public/announcement-videos/<seq>_<slug>/plan.json`. Put the spoken line in `narration` and a short on-screen line in `caption`. See `references/plan-format.md`.
3. Validate: `python scripts/make_video.py <plan.json> --validate-only`
4. Render: `python scripts/make_video.py <plan.json> -o <dir>/video.mp4`
5. Open `thumbnail.jpg` and the failure screenshots if the render exited non-zero. Fix the plan. Render again.

`python scripts/auto_release.py --url <url> --dry-run` only builds a draft plan and checks selectors. Do not record until the dry-run is clean and the steps match the page.

Output stays in `public/announcement-videos/`. Keep that path gitignored so the mp4s do not enter the app bundle or git history.

## Rules

- Selectors come from `inspect_page.py` or the DOM. Do not guess.
- Vertical video uses a phone viewport (390x844, device scale 3) and scales up to 1080x1920. Do not set a 1080x1920 CSS viewport.
- `accent: "auto"` reads the live site. A hex in the plan, including `#6366f1`, is kept.
- Voice-over is edge-tts. Each scene is lengthened to fit the measured clip. `narration` is what is spoken. `caption` is what is on screen.
- Click and highlight zoom toward the target (`zoom` in the plan or on a step). Set `zoom` to `1` to turn that off.
- `nav_transition` is `fade`, `slide`, or `zoom`.
- `--before-after` adds a before card from the previous tag. It does not checkout the worktree. To film the old UI, serve that tag and pass `--before-url`.
- `capture: "frames"` records a CDP screencast instead of Playwright's webm when the webm looks soft.
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
