import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import common
import device_frames
import make_video


class CommonTest(unittest.TestCase):
    def test_lead_keeps_oauth(self):
        self.assertEqual(common.lead("Add OAuth login"), "Add OAuth login")
        self.assertEqual(common.lead("add OAuth login"), "Add OAuth login")

    def test_accent_hex_is_not_auto(self):
        self.assertTrue(common.accent_is_auto("auto"))
        self.assertTrue(common.accent_is_auto(None))
        self.assertFalse(common.accent_is_auto("#6366f1"))

    def test_denylist(self):
        self.assertTrue(common.is_destructive("Delete account"))
        self.assertTrue(common.is_destructive("Pay now"))
        self.assertTrue(common.is_destructive("button:has-text('Checkout')"))
        self.assertFalse(common.is_destructive("Export"))
        self.assertFalse(common.is_destructive("Remove filter"))

    def test_notes_and_narration_timing(self):
        plan = {"intro_seconds": 3, "outro_seconds": 3.5, "zoom": 1.28, "features": [{"hold_ms": 800}]}
        self.assertTrue(common.apply_note(plan, "shorten the intro"))
        self.assertLess(plan["intro_seconds"], 3)
        self.assertTrue(common.apply_note(plan, "zoom more"))
        self.assertGreater(plan["zoom"], 1.28)
        self.assertFalse(common.apply_note(plan, "make it sparkle"))
        common.apply_narration_timing(plan, {"feat0": 5})
        self.assertGreaterEqual(plan["features"][0]["hold_ms"], 5000)

    def test_music_stays_in_the_mix(self):
        graph = common.voice_mix_filter([250], with_bed=True)
        self.assertIn("[0:a]", graph)
        self.assertNotIn("[0:a]", common.voice_mix_filter([250], with_bed=False))

    def test_chapters_and_copy(self):
        plan = {
            "product": "Fixture",
            "version": "v2",
            "headline": "Export the report",
            "features": [{"caption": "Export", "narration": "Export the finished report."}],
            "changes": ["Add OAuth login"],
        }
        lines = common.youtube_chapter_lines(common.chapter_labels(plan), [3.0, 4.0, 3.5])
        self.assertEqual(common.format_timestamp(1.4 - 0.4), "0:01")
        self.assertTrue(lines[0].startswith("0:00"))
        md = common.announcement_markdown(plan, [3.0, 4.0, 3.5])
        self.assertIn("0:00 Intro", md)
        self.assertIn("Add OAuth login", md)
        self.assertNotIn("Subscribe", md)
        self.assertNotIn("#SoftwareUpdate", md)

    def test_phone_viewport_and_explicit_accent(self):
        raw = {
            "product": "Fixture",
            "headline": "Export",
            "format": "vertical",
            "accent": "#6366f1",
            "features": [{"caption": "Export", "steps": [{"action": "goto", "url": "http://example.com"}]}],
        }
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "plan.json"
            path.write_text(json.dumps(raw), encoding="utf-8")
            plan = make_video.load_plan(path)
        self.assertEqual(plan["viewport"], common.PHONE)
        self.assertEqual(plan["device_scale_factor"], common.PHONE_DPR)
        self.assertEqual(plan["accent"], "#6366f1")

    def _plan(self, directory, **extra):
        raw = {
            "product": "Fixture",
            "headline": "Export",
            "accent": "#6366f1",
            "features": [{"caption": "Export", "steps": [{"action": "goto", "url": "http://example.com"}]}],
        }
        raw.update(extra)
        path = Path(directory) / "plan.json"
        path.write_text(json.dumps(raw), encoding="utf-8")
        return path

    def test_device_frame_validation(self):
        device_frames._self_check()
        with tempfile.TemporaryDirectory() as d:
            plan = make_video.load_plan(self._plan(d, device_frame="iPad", frame_background="#112233"))
        self.assertEqual(plan["device_frame"], "ipad")
        self.assertEqual(plan["_frame_bg_kind"], "color")
        self.assertEqual(plan["_frame_bg_payload"], "#112233")
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(SystemExit):
                make_video.load_plan(self._plan(d, device_frame="toaster"))
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(SystemExit):
                make_video.load_plan(self._plan(d, device_frame="ipad", frame_background="missing-bg.png"))

    def test_story_narration(self):
        lines = common.narration_lines({
            "product": "PixelDesk",
            "headline": "Dark mode",
            "cta": "https://pixeldesk.app",
            "features": [
                {"caption": "Switch to dark mode"},
                {"caption": "Add OAuth login"},
            ],
        })
        self.assertTrue(lines[0]["text"].startswith("Meet PixelDesk"))
        self.assertIn("comes together", lines[0]["text"])
        self.assertTrue(lines[1]["text"].startswith("It starts here."))
        self.assertIn("Switch to dark mode", lines[1]["text"])
        self.assertTrue(lines[2]["text"].startswith("And finally, add OAuth login."))
        self.assertNotIn("oAuth", lines[2]["text"])
        self.assertIn("pixeldesk.app", lines[3]["text"])
        kept = common.narration_lines({
            "product": "PixelDesk",
            "headline": "Search",
            "intro_narration": "Meet PixelDesk. Today we ship search that keeps up with you.",
            "features": [{
                "narration": "You open search, type a word, and the list narrows while you are still typing.",
            }],
            "outro_narration": "That is the whole release, and it is live now.",
        })
        self.assertTrue(kept[0]["text"].startswith("Meet PixelDesk. Today"))
        self.assertTrue(kept[1]["text"].startswith("You open search"))
        self.assertTrue(kept[2]["text"].startswith("That is the whole release"))

    def test_mark_stays_on_the_zoomed_target(self):
        # Same conversion as toLocalBox in the page overlay.
        # A box measured while zoomed maps back to the pre-zoom point the ring is drawn at.
        ox, oy, scale = 400.0, 300.0, 1.5
        visual = {"x": 430.0, "y": 330.0, "width": 60.0, "height": 30.0}
        local = {
            "x": ox + (visual["x"] - ox) / scale,
            "y": oy + (visual["y"] - oy) / scale,
            "width": visual["width"] / scale,
            "height": visual["height"] / scale,
        }
        self.assertAlmostEqual(local["x"], 420.0)
        self.assertAlmostEqual(local["y"], 320.0)
        self.assertAlmostEqual(local["width"], 40.0)
        back_x = ox + (local["x"] - ox) * scale
        back_y = oy + (local["y"] - oy) * scale
        self.assertAlmostEqual(back_x, visual["x"])
        self.assertAlmostEqual(back_y, visual["y"])

    def test_zoom_maps_into_the_screen(self):
        screen = {"x": 100, "y": 40, "w": 800, "h": 450}
        x, y = make_video.map_zoom_point(800, 450, {"width": 1600, "height": 900}, screen)
        self.assertAlmostEqual(x, 500)
        self.assertAlmostEqual(y, 265)

    def test_device_frame_composite(self):
        if not shutil.which("ffmpeg"):
            self.skipTest("ffmpeg")
        lay = device_frames.layout("browser", 320, 180)
        s = lay["screen"]
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            bg, chrome, mask = d / "bg.png", d / "chrome.png", d / "mask.png"
            clip = d / "clip.mp4"
            subprocess.run(
                ["ffmpeg", "-y", "-f", "lavfi", "-i", "color=c=blue:s=320x180:d=1", "-frames:v", "1", str(bg)],
                check=True, capture_output=True,
            )
            subprocess.run(
                ["ffmpeg", "-y", "-f", "lavfi", "-i", "color=c=black@0.0:s=320x180:d=1,format=rgba",
                 "-frames:v", "1", str(chrome)],
                check=True, capture_output=True,
            )
            subprocess.run(
                ["ffmpeg", "-y", "-f", "lavfi", "-i", f"color=c=white:s={s['w']}x{s['h']}:d=1",
                 "-frames:v", "1", str(mask)],
                check=True, capture_output=True,
            )
            subprocess.run(
                ["ffmpeg", "-y", "-f", "lavfi", "-i", "color=c=red:s=320x180:d=0.4",
                 "-c:v", "libx264", "-pix_fmt", "yuv420p", str(clip)],
                check=True, capture_output=True,
            )
            make_video.apply_device_frame(clip, {"bg": bg, "chrome": chrome, "mask": mask, "screen": s})
            probe = subprocess.run(
                ["ffprobe", "-v", "error", "-select_streams", "v:0",
                 "-show_entries", "stream=width,height", "-of", "csv=p=0", str(clip)],
                check=True, capture_output=True, text=True,
            )
            self.assertEqual(probe.stdout.strip(), "320,180")
            self.assertGreater(clip.stat().st_size, 1000)

    def test_template_zoom_and_window(self):
        if not shutil.which("ffmpeg"):
            self.skipTest("ffmpeg")
        lay = device_frames.layout("macos", 320, 180)
        s = lay["screen"]
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            bg, chrome, mask = d / "bg.png", d / "chrome.png", d / "mask.png"
            clip = d / "clip.mp4"
            subprocess.run(
                ["ffmpeg", "-y", "-f", "lavfi", "-i", "color=c=blue:s=320x180:d=1", "-frames:v", "1", str(bg)],
                check=True, capture_output=True,
            )
            subprocess.run(
                ["ffmpeg", "-y", "-f", "lavfi", "-i", "color=c=black@0.0:s=320x180:d=1,format=rgba",
                 "-frames:v", "1", str(chrome)],
                check=True, capture_output=True,
            )
            subprocess.run(
                ["ffmpeg", "-y", "-f", "lavfi", "-i", f"color=c=white:s={s['w']}x{s['h']}:d=1",
                 "-frames:v", "1", str(mask)],
                check=True, capture_output=True,
            )
            subprocess.run(
                ["ffmpeg", "-y", "-f", "lavfi", "-i", "color=c=red:s=320x180:d=1.6",
                 "-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", "30", str(clip)],
                check=True, capture_output=True,
            )
            make_video.apply_device_frame(
                clip,
                {"bg": bg, "chrome": chrome, "mask": mask, "screen": s, "layout": lay},
                zooms=[{"t0": 0.8, "t1": 1.05, "scale": 1.4, "cx": 160, "cy": 90}],
                viewport={"width": 320, "height": 180},
            )
            probe = subprocess.run(
                ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(clip)],
                check=True, capture_output=True, text=True,
            )
            self.assertGreater(float(probe.stdout.strip()), 1.4)

            def pixel(t, x, y):
                raw = subprocess.run(
                    ["ffmpeg", "-v", "error", "-ss", f"{t:.3f}", "-i", str(clip),
                     "-frames:v", "1", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                    check=True, capture_output=True,
                ).stdout
                i = (y * 320 + x) * 3
                return raw[i:i + 3]

            # Window still opening: screen corner shows the background, not the clip.
            early = pixel(0.02, s["x"] + 4, s["y"] + 4)
            self.assertGreater(early[2], 180, early)
            self.assertLess(early[0], 40, early)
            # Window open, before the camera zoom: that same pixel is the clip.
            mid = pixel(0.55, s["x"] + 4, s["y"] + 4)
            self.assertGreater(mid[0], 180, mid)
            self.assertLess(mid[2], 40, mid)

    def test_validate_fixture(self):
        script = ROOT / "scripts" / "make_video.py"
        plan = ROOT / "tests" / "fixtures" / "plan.json"
        r = subprocess.run([sys.executable, str(script), str(plan), "--validate-only"], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn('"ok": true', r.stdout)

    def test_render_fixture(self):
        if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
            self.skipTest("ffmpeg")
        try:
            import playwright  # noqa: F401
        except ImportError:
            self.skipTest("playwright")
        fixture = ROOT / "tests" / "fixtures" / "index.html"
        out_dir = ROOT / "tests" / "fixtures" / "out"
        if out_dir.exists():
            shutil.rmtree(out_dir)
        out_dir.mkdir()
        plan = {
            "product": "Fixture",
            "headline": "Export the report",
            "accent": "#0f766e",
            "voiceover": False,
            "zoom": 1.1,
            "format": "landscape",
            "viewport": {"width": 1280, "height": 720},
            "intro_seconds": 1.4,
            "outro_seconds": 1.4,
            "base_url": fixture.parent.as_uri(),
            "features": [{
                "caption": "Export",
                "narration": "Export the finished report.",
                "hold_ms": 400,
                "steps": [
                    {"action": "goto", "url": "/index.html"},
                    {"action": "click", "selector": "#export"},
                    {"action": "wait", "ms": 400},
                ],
            }],
        }
        plan_path = out_dir / "plan.json"
        plan_path.write_text(json.dumps(plan), encoding="utf-8")
        video = out_dir / "video.mp4"
        r = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "make_video.py"), str(plan_path), "-o", str(video)],
            capture_output=True, text=True,
        )
        self.assertEqual(r.returncode, 0, r.stderr[-2000:] + r.stdout[-2000:])
        self.assertTrue(video.exists())
        self.assertTrue((out_dir / "announcement.md").exists())
        self.assertTrue((out_dir / "thumbnail.jpg").exists())
        announcement = (out_dir / "announcement.md").read_text(encoding="utf-8")
        self.assertIn("0:00 Intro", announcement)
        probe = subprocess.run(
            ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height",
             "-of", "csv=p=0", str(out_dir / "thumbnail.jpg")],
            capture_output=True, text=True,
        )
        self.assertEqual(probe.stdout.strip(), "1280,720")
        # Ensure only .mp4, .md, and .jpg files remain (no .json, .srt, .vtt, .gif, .cache, etc.)
        for f in out_dir.iterdir():
            self.assertIn(f.suffix.lower(), [".mp4", ".md", ".jpg", ".jpeg"])
        self.assertFalse((out_dir / "plan.json").exists())
        self.assertFalse((out_dir / "video.srt").exists())


if __name__ == "__main__":
    unittest.main()
