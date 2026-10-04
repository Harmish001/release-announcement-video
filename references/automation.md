# Running on every release (CI)

Status: **untested sketch.** The renderer itself is tested locally; this workflow wiring has not been run on GitHub Actions. Expect to adjust it.

The idea: on every pushed tag, build the app, serve it, have Claude Code write the plan from the diff, render, and attach the MP4 to the GitHub release.

```yaml
name: release-video
on:
  push:
    tags: ["v*"]
jobs:
  video:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with: { fetch-depth: 0 }          # full history so the tag range resolves
      - uses: actions/setup-node@v4
        with: { node-version: 22 }
      - run: npm ci && npm run build
      - run: (npx next start -p 3000 &) && npx wait-on http://localhost:3000
      - run: pip install playwright && playwright install --with-deps chromium && sudo apt-get install -y ffmpeg
      # Plan generation needs an LLM step (for example Claude Code in headless mode) that reads
      # `python3 scripts/gather_release.py` output and writes plan.json. Keep a human review
      # gate (draft release, not auto-publish): captions are generated from commit text.
      - run: python3 scripts/make_video.py plan.json -o release.mp4
      - uses: softprops/action-gh-release@v2
        with: { files: "release.mp4", draft: true }
```

Cautions:

- Publish as a **draft** and review. An unattended pipeline can caption a flow that silently broke.
- Seed the CI database with fake data. Never point this at production data.
- A plan generated automatically needs the same checks as a manual run: contact sheet inspected, captions match the screen.
