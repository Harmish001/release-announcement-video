# plan.json format

One file describes the whole video. Run `make_video.py plan.json --validate-only` to catch mistakes before the browser starts.

## Top-level fields

| Field | Required | Default | Notes |
|---|---|---|---|
| `product` | yes | | Shown on intro and outro cards |
| `headline` | yes | | Intro card title. One line of benefit, not the version number |
| `features` | yes | | List of feature objects (below). 2 to 4 is the sweet spot |
| `version` | no | `""` | Shown as a pill, and in "What's new in ..." |
| `subhead` | no | `""` | Intro card sub-line |
| `base_url` | no | `""` | Prepended to relative `goto` urls. Required if a feature does not start with `goto` |
| `format` | no | `landscape` | `landscape` (1920x1080) or `vertical` (1080x1920, mobile emulation) |
| `accent` | no | auto | Brand color. **Auto-extracted from the live site** when `base_url` is set and accent is the default. Override by setting an explicit hex value. |
| `click_effect` | no | `ripple` | Click animation: `ripple` (ring), `sparkle` (particle burst), `glow` (radial pulse) |
| `nav_transition` | no | `fade` | In-browser page transition on `goto`: `fade`, `slide`, `zoom` |
| `voiceover` | no | `false` | Narrate feature captions using AI TTS. Requires `pip install edge-tts`. |
| `voiceover_voice` | no | `en-US-AriaNeural` | Any valid [edge-tts voice](https://github.com/rany2/edge-tts#voices). |
| `custom_effects` | no | `[]` | List of `{"effect": "sparkle"\|"glow"\|"pulse", "selector": "css-selector"}` objects. Applied on every feature page after load. User instructions like "add sparkle on the submit button" map here. |
| `bullets` | no | feature captions | Outro checklist, max 5 shown |
| `cta` | no | `""` | Button text on the outro, usually the URL |
| `logo` | no | | Image path, relative to the plan file. Replaces the dot on cards |
| `music` | no | | Audio file you have rights to. Faded out at the end |
| `storage_state` | no | | Playwright session file for logged-in apps (demo account only) |
| `color_scheme` | no | | `light` or `dark`, forces the site's preference |
| `cursor` | no | `arrow` landscape, `tap` vertical | `arrow`, `tap` (ripple only), or `none` |
| `viewport` | no | 1280x720 / 540x960 | `{"width": .., "height": ..}`. Keep the aspect ratio |
| `intro_seconds` / `outro_seconds` | no | 3.0 / 3.5 | |

## Feature object

```json
{
  "caption": "Switch to dark mode from the header",
  "speed": 1,
  "hold_ms": 1000,
  "steps": [ ... ]
}
```

- `caption`: shown as a pill at the bottom for the whole clip. Short and benefit-first.
- `speed`: playback multiplier for slow flows, for example `1.5`.
- `hold_ms`: how long to linger on the final state so viewers can read it.
- `steps`: ordered actions. If the first is not `goto`, `goto "/"` is inserted when `base_url` is set.

Each clip is trimmed to start when the first page has loaded, so loading time is not in the video.

## Step actions

| action | fields | what it does |
|---|---|---|
| `goto` | `url` | Navigate. Relative urls use `base_url` |
| `wait` | `ms` (800) | Pause, for the viewer to take something in |
| `click` | `selector` | Moves the cursor in a smooth path, ripples, clicks |
| `type` | `selector`, `text`, `delay_ms` (70), `clear` | Clicks the field then types like a person. `clear: true` selects existing text first |
| `press` | `key` | Keyboard key, for example `Enter`, `Escape` |
| `hover` | `selector`, `ms` (600) | Moves the cursor onto an element |
| `scroll` | `y` (pixels, relative) or `to` (selector), `ms` (900) | Smooth eased scroll |
| `highlight` | `selector`, `ms` (1500) | Dims the page and spotlights one element. Use to draw the eye to the result |
| `caption` | `text`, `ms` (900) | Change the caption mid-clip. Empty text hides it |

Any step may also carry:

- `"caption": "..."` to change the caption just before that step runs
- `"pause_after": 350` to override the breathing pause after the step

## Selectors

Anything Playwright accepts: CSS (`#id`, `[data-testid="x"]`), `text=Save`, `button:has-text("Export")`. Run `scripts/inspect_page.py <url>` and copy from its output rather than guessing. The first match is used, so make selectors specific.

## Pacing guide

- Intro 3s, outro 3.5s, each feature 5 to 8s. Total under about 45s.
- After a click that triggers a visible change, add `wait` 800 to 1300 ms or `highlight` the result so it registers.
- One feature per clip, one idea per caption.

## Minimal example

```json
{
  "product": "PixelDesk",
  "version": "v1.1.0",
  "headline": "Dark mode and instant search",
  "base_url": "http://localhost:3000",
  "cta": "pixeldesk.app",
  "features": [
    {"caption": "Switch to dark mode from the header", "steps": [
      {"action": "goto", "url": "/"},
      {"action": "click", "selector": "#theme-toggle"},
      {"action": "wait", "ms": 1200}
    ]},
    {"caption": "Search filters tools as you type", "steps": [
      {"action": "goto", "url": "/"},
      {"action": "type", "selector": "input[name=q]", "text": "crop"},
      {"action": "highlight", "selector": ".card", "ms": 1400}
    ]}
  ]
}
```

## Errors

On failure the renderer prints JSON with the feature index, the step, Playwright's message, and a path to a screenshot of the page at that moment, then exits non-zero. The work folder is kept so you can open the screenshot.

---

## Voice-over

Set `"voiceover": true` to narrate captions with AI Text-to-Speech via **edge-tts** (free, Microsoft Neural voices).

```bash
pip install edge-tts
```

The renderer speaks the intro headline and each feature caption in sequence. The merged audio track is added to the final MP4.

You can pick any voice from the [edge-tts voice list](https://github.com/rany2/edge-tts#voices):
```json
{
  "voiceover": true,
  "voiceover_voice": "en-GB-SoniaNeural"
}
```

---

## Custom User Effects

The `custom_effects` field accepts a list of `{effect, selector}` objects. These are applied to matching DOM elements on every recorded page after it loads.

| effect | What it does |
|---|---|
| `sparkle` | Particle burst on every click on that element |
| `glow` | Radial light pulse on click |
| `pulse` | Continuous pulsing border animation (good for CTA buttons) |

```json
{
  "custom_effects": [
    {"effect": "sparkle", "selector": "button.submit"},
    {"effect": "pulse",   "selector": ".cta-hero"},
    {"effect": "glow",    "selector": "#sign-up-btn"}
  ]
}
```

Via CLI:
```bash
python scripts/auto_release.py --url http://localhost:3000 \
  --click-effect sparkle \
  --nav-transition zoom \
  --voiceover \
  --custom-effects '[{"effect":"sparkle","selector":"button.cta"}]'
```

---

## Site Theme Color Auto-Extraction

When `base_url` is set and `accent` is not explicitly overridden, the renderer visits the live site before recording and extracts the dominant brand color from:

1. CSS custom properties (`--primary`, `--accent`, `--brand`, `--color-primary`, etc.)
2. Background color of `<nav>` / `<header>`
3. Background color of `button[class*=primary]`

The extracted color is used for the intro/outro card gradients, spotlight borders, cursor ripples, and click effects — making every video match the real site brand automatically.
