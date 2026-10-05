# Release announcement video

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

Turn a git range or a live page into an announcement video, a 1280x720 thumbnail, subtitles, a short GIF, and social copy.

Version is `package.json` only. This repo does not publish a live npm version badge. From a checkout:

```bash
node bin/cli.js add
node bin/cli.js doctor
```

`npx release-announcement-video add` works after the package is published. `node bin/cli.js help` is the local check that the CLI runs.

![Sample](examples/preview.gif)

Full-length cuts: `examples/sample-landscape.mp4` and `examples/sample-vertical.mp4`.

## What you need

Python 3.10+, [Playwright](https://playwright.dev) Chromium, and ffmpeg/ffprobe on PATH. Voice-over uses `edge-tts` (`pip install edge-tts`).

## Render

The agent should inspect the page, write `plan.json`, and render:

```bash
python scripts/inspect_page.py http://localhost:3000
python scripts/make_video.py plan.json --validate-only
python scripts/make_video.py plan.json -o public/announcement-videos/01_export/video.mp4
```

Draft from git, without recording:

```bash
python scripts/auto_release.py --url http://localhost:3000 --dry-run
```

Add `--before-after` for a before card from the previous tag, or `--before-url` to film an already-running old build. That path does not checkout your worktree.

## Output
 
`public/announcement-videos/<seq>_<slug>/` holds `video.mp4`, `thumbnail.jpg`, and `announcement.md`. All extra and intermediate files are automatically cleaned up. The folder is gitignored here. Keep it gitignored in the app repo so the mp4s stay out of the production bundle.

Formats: `landscape` (1920x1080), `vertical` (phone viewport, 1080x1920 output), `square` (1080x1080).

## Feedback

```bash
python scripts/make_video.py plan.json -o video.mp4 --note "zoom more"
python scripts/make_video.py plan.json -o video.mp4 --note "shorten the intro"
```

Plan fields, selectors, and the edit phrases: `references/plan-format.md`. Agent workflow: `SKILL.md`.

## License

MIT. Copyright holder is in `package.json`.
