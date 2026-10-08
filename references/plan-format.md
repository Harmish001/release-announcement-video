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
| `format` | no | `landscape` | `landscape` (1920x1080), `vertical` (phone CSS 390x844 at DPR 3, output 1080x1920), `square` (1080x1080) |
| `accent` | no | `auto` | `auto` extracts the live site color when `base_url` is set. Any hex, including `#6366f1`, is kept. |
| `click_effect` | no | `ripple` | Click animation: `ripple` (ring), `sparkle` (particle burst), `glow` (radial pulse) |
| `nav_transition` | no | `fade` | In-browser page transition on `goto`: `fade`, `slide`, `zoom` |
| `voiceover` | no | `true` | Narrate with edge-tts. Scenes are sized from the measured audio. |
| `voiceover_voice` | no | `en-US-AriaNeural` | Any valid [edge-tts voice](https://github.com/rany2/edge-tts#voices). |
| `custom_effects` | no | `[]` | List of `{"effect": "sparkle"\|"glow"\|"pulse", "selector": "css-selector"}` objects. Applied on every feature page after load. User instructions like "add sparkle on the submit button" map here. |
| `bullets` | no | feature captions | Outro checklist, max 5 shown |
| `cta` | no | `""` | Button text on the outro, usually the URL |
| `logo` | no | | Image path, relative to the plan file. Replaces the dot on cards |
| `music` | no | | Audio file you have rights to. Faded out at the end |
| `storage_state` | no | | Playwright session file for logged-in apps (demo account only) |
| `color_scheme` | no | | `light` or `dark`, forces the site's preference |
| `cursor` | no | `arrow` landscape, `tap` vertical | `arrow`, `tap` (ripple only), or `none` |
| `viewport` | no | 1920x1080, or 390x844 when vertical | Phone size for vertical. A saved 1080x1920 viewport is treated as the old default and replaced. |
| `zoom` | no | `1.28` | Camera scale on click and highlight. `1` disables it. A step may set its own `zoom`. |
| `capture` | no | `video` | `frames` uses a CDP screencast instead of Playwright webm. |
| `device_frame` | no | | Wrap every feature clip in one template: `macos`, `browser`, `glass`, `iphone`, `laptop`, `ipad`. Intro/outro cards stay full-screen. |
| `frame_background` | no | `gradient-sky` | Area around the device. Preset: `gradient-sky`, `gradient-studio`, `gradient-radial`, `gradient-mesh`, `gradient-aurora`, `gradient-sunset`, `gradient-ocean`. Or a hex color, or an image path relative to the plan file. |
| `narration` | feature | caption | Spoken line. The on-screen `caption` can stay short. |
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

- `caption`: short line on screen.
- `narration`: spoken line. Falls back to `caption`. Scenes grow to fit the audio.
- A feature may be a card instead of a recording: `{"card": {"title": "Before v1.0.0", "lines": ["file.py +10 -2"]}}`.
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

On failure the renderer prints JSON with the feature index, the step, Playwright's message, and a path to a screenshot of the page at that moment, then exits non-zero. That work folder is kept so you can open the screenshot. `plan.json` is kept after a successful render too. Edit phrases (`--note`) and the `.cache` folder next to the video re-record only the scenes that changed.

---

## Voice-over

Set `"voiceover": true` (the default) to narrate each scene with edge-tts. The spoken text is `narration` when set, otherwise the caption. Audio is generated first and measured with ffprobe. Intro, outro, and `hold_ms` grow so the line finishes before the next scene.

```bash
pip install edge-tts
```

The renderer speaks the intro headline and each feature caption in sequence. The merged audio track is added to the final MP4.

### Dynamic Voice Selection
You can set `"voiceover_voice": "auto"` (or specify any of the 300+ supported Edge-TTS voices from `tts-voice.md` / `scripts/voices.py`). The engine dynamically picks the optimal voice matching the product and topic:

| Product / Feature Topic | Recommended Voice | Tone / Personality |
| :--- | :--- | :--- |
| **Product Announcements & SaaS Releases** | `en-US-AriaNeural` | Positive, Confident, News |
| **Developer Tools, Cloud, Databases & DevOps** | `en-US-ChristopherNeural` | Reliable, Authority |
| **Interactive UI Walkthroughs & Onboarding** | `en-US-JennyNeural` | Friendly, Considerate |
| **AI Breakthroughs & High-Energy Features** | `en-US-GuyNeural` | Passion, Intense |
| **Data Analytics, Benchmarks & Algorithms** | `en-US-EricNeural` | Rational, Analytical |
| **Fast-Paced Tips & Productivity Extensions** | `en-US-RogerNeural` | Lively, Energetic |
| **British / International English** | `en-GB-RyanNeural` / `en-GB-SoniaNeural` | Professional, Friendly |
| **Multilingual Locales** | Native locale (e.g. `fr-FR-DeniseNeural`, `de-DE-KillianNeural`, `es-ES-AlvaroNeural`, `hi-IN-MadhurNeural`) | Locale-matching |

```json
{
  "voiceover": true,
  "voiceover_voice": "auto"
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

---

## Device Frame Templates

Wrap your feature recordings inside realistic device frames with styled backgrounds. Intro and outro cards stay full-screen — only feature clips get the frame treatment.

### Supported Frames

| Frame | Look |
|---|---|
| `macos` | Light macOS window: traffic lights, centered title (the product name), soft shadow |
| `browser` | Light browser chrome: traffic lights and a centered address pill (the site host) |
| `glass` | Translucent rounded rim and shadow. The clip fills the opening |
| `iphone` | Portrait handset, dark bezel, dynamic island, side buttons. Best with `format: vertical` |
| `laptop` | Lid, webcam, hinge, and base. The clip keeps its aspect inside the screen |
| `ipad` | Dark bezel, front camera, rounded corners. The clip keeps its aspect |

### Background Options

When `device_frame` is set, the `frame_background` field controls what is visible behind and around the device:

| Value | Effect |
|---|---|
| `gradient-sky` (default) | Light blue mockup backdrop |
| `gradient-studio` | Light gray studio backdrop |
| `gradient-radial` | Radial glow derived from `accent` |
| `gradient-mesh` | Multi-stop mesh from `accent` |
| `gradient-aurora` | Aurora bands from `accent` |
| `gradient-sunset` | Warm tones shifted from `accent` |
| `gradient-ocean` | Cool tones shifted from `accent` |
| `#hexcolor` | Solid color |
| `path/to/image.jpg` | Image, relative to plan.json or absolute. Missing file fails validation |

### Examples

Browser frame with auto-detected theme gradient:
```json
{
  "product": "PixelDesk",
  "headline": "Dark mode and instant search",
  "base_url": "http://localhost:3000",
  "device_frame": "browser",
  "features": [...]
}
```

MacBook frame with a custom background image:
```json
{
  "device_frame": "laptop",
  "frame_background": "assets/promo-bg.jpg",
  "accent": "#6366f1"
}
```

iPad frame with sunset gradient:
```json
{
  "device_frame": "ipad",
  "frame_background": "gradient-sunset"
}
```

Via CLI:
```bash
python scripts/auto_release.py --url http://localhost:3000 \
  --device-frame browser \
  --frame-background gradient-ocean
```

