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
