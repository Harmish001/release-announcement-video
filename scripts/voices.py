#!/usr/bin/env python3
"""Dynamic Edge-TTS Voice Registry and Recommendation Engine.

Provides validation, querying, and topic-aware dynamic recommendation
across 300+ official Edge-TTS neural voices.
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

VOICES_JSON_PATH = Path(__file__).parent / "voices_data.json"

_VOICE_CACHE: Optional[Dict[str, Dict[str, Any]]] = None


def load_voice_database() -> Dict[str, Dict[str, Any]]:
    """Load the voice database from voices_data.json."""
    global _VOICE_CACHE
    if _VOICE_CACHE is not None:
        return _VOICE_CACHE

    if VOICES_JSON_PATH.exists():
        try:
            data = json.loads(VOICES_JSON_PATH.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                _VOICE_CACHE = data
                return _VOICE_CACHE
        except Exception:
            pass

    # Basic embedded fallback if JSON missing
    _VOICE_CACHE = {
        "en-US-AndrewNeural": {"gender": "Male", "locale": "en-US", "categories": ["General"], "personalities": ["Friendly", "Positive"]},
        "en-US-AriaNeural": {"gender": "Female", "locale": "en-US", "categories": ["News", "Novel"], "personalities": ["Positive", "Confident"]},
        "en-US-ChristopherNeural": {"gender": "Male", "locale": "en-US", "categories": ["News", "Novel"], "personalities": ["Reliable", "Authority"]},
        "en-US-GuyNeural": {"gender": "Male", "locale": "en-US", "categories": ["News", "Novel"], "personalities": ["Passion"]},
        "en-US-JennyNeural": {"gender": "Female", "locale": "en-US", "categories": ["Conversation", "News"], "personalities": ["Friendly", "Considerate", "Comfort"]},
        "en-US-RogerNeural": {"gender": "Male", "locale": "en-US", "categories": ["News", "Novel"], "personalities": ["Lively"]},
        "en-US-EricNeural": {"gender": "Male", "locale": "en-US", "categories": ["News", "Novel"], "personalities": ["Rational"]},
        "en-US-MichelleNeural": {"gender": "Female", "locale": "en-US", "categories": ["News", "Novel"], "personalities": ["Friendly", "Pleasant"]},
        "en-GB-RyanNeural": {"gender": "Male", "locale": "en-GB", "categories": ["General"], "personalities": ["Friendly", "Positive"]},
        "en-GB-SoniaNeural": {"gender": "Female", "locale": "en-GB", "categories": ["General"], "personalities": ["Friendly", "Positive"]},
        "en-IN-PrabhatNeural": {"gender": "Male", "locale": "en-IN", "categories": ["General"], "personalities": ["Friendly", "Positive"]},
        "en-IN-NeerjaNeural": {"gender": "Female", "locale": "en-IN", "categories": ["General"], "personalities": ["Friendly", "Positive"]},
    }
    return _VOICE_CACHE


def get_all_supported_voices() -> Dict[str, Dict[str, Any]]:
    """Return dictionary of all supported voices."""
    return load_voice_database()


def is_supported_voice(voice_name: str) -> bool:
    """Check if the provided voice name is in the supported Edge-TTS registry."""
    if not voice_name or not isinstance(voice_name, str):
        return False
    db = load_voice_database()
    return voice_name.strip() in db


def validate_and_normalize_voice(
    voice_name: Optional[str],
    default: str = "en-US-AriaNeural",
    topic: Optional[str] = None,
    locale: str = "en-US",
) -> str:
    """Validate voice against supported list, returning a valid voice or best match."""
    db = load_voice_database()
    if voice_name and voice_name in db:
        return voice_name

    if voice_name and voice_name.lower() in ("auto", "dynamic"):
        return recommend_voice(topic=topic, locale=locale)

    if voice_name:
        # Try case-insensitive matching
        for v_key in db:
            if v_key.lower() == voice_name.lower():
                return v_key

        sys.stderr.write(
            f"[WARNING] Requested voice '{voice_name}' is not in the supported Edge-TTS registry. "
            f"Falling back to supported voice: '{default}'\n"
        )

    return default if default in db else "en-US-AriaNeural"


def recommend_voice(
    topic: Optional[str] = None,
    tone: Optional[str] = None,
    gender: Optional[str] = None,
    locale: str = "en-US",
    archetype: Optional[str] = None,
) -> str:
    """Dynamically recommend the optimal supported Edge-TTS voice based on topic and tone.
    
    Topic Heuristics:
    - Tech / Architecture / Backend / Outage / Cloud -> Christopher (Authority, Reliable) or Guy (Passion)
    - Tutorials / SaaS / Walkthroughs / Onboarding -> Jenny (Friendly, Comfort) or Aria (Confident)
    - Data / Stats / Benchmarks / Algorithms -> Eric (Rational) or Steffan (Rational)
    - Listicles / Fast-Paced / Entertainment -> Roger (Lively)
    - Product Announcements / Feature Launches -> Aria (Positive, Confident)
    """
    db = load_voice_database()
    topic_str = (topic or "").lower()
    tone_str = (tone or "").lower()
    arch_str = (archetype or "").lower()
    gender_req = (gender or "").lower()

    # Filter by locale
    locale_voices = {k: v for k, v in db.items() if v.get("locale", "").lower() == locale.lower()}
    if not locale_voices:
        # Prefix match (e.g. 'en')
        lang_prefix = locale.split("-")[0].lower()
        locale_voices = {k: v for k, v in db.items() if v.get("locale", "").lower().startswith(lang_prefix)}

    if not locale_voices:
        locale_voices = db  # Fallback to full DB

    # Filter by gender if specified
    if gender_req in ("male", "m"):
        gender_filtered = {k: v for k, v in locale_voices.items() if v.get("gender", "").lower() == "male"}
    elif gender_req in ("female", "f"):
        gender_filtered = {k: v for k, v in locale_voices.items() if v.get("gender", "").lower() == "female"}
    else:
        gender_filtered = locale_voices

    active_pool = gender_filtered or locale_voices

    # English US specialized mappings
    if locale.lower() in ("en-us", "en"):
        # 1. Authority / Architecture / Engineering / Deep Dive / Post-Mortem
        if any(k in topic_str for k in ["architecture", "database", "infrastructure", "outage", "system", "security", "backend", "scale", "performance", "linux", "cloud"]) or \
           any(k in tone_str for k in ["authority", "reliable", "serious", "expert"]) or \
           arch_str == "story-arc":
            if "en-US-ChristopherNeural" in active_pool:
                return "en-US-ChristopherNeural"
            if "en-US-GuyNeural" in active_pool:
                return "en-US-GuyNeural"

        # 2. Passion / AI / Startup / Exciting Breakthrough / Bold Claim
        if any(k in topic_str for k in ["ai", "startup", "revolution", "breakthrough", "launch", "fast", "speed", "game", "hype"]) or \
           any(k in tone_str for k in ["passion", "energy", "intense"]):
            if "en-US-GuyNeural" in active_pool:
                return "en-US-GuyNeural"
            if "en-US-AriaNeural" in active_pool:
                return "en-US-AriaNeural"

        # 3. Rational / Stats / Benchmarks / Algorithms / Clean Code
        if any(k in topic_str for k in ["benchmark", "stat", "metric", "algorithm", "math", "clean code", "refactor", "optimization", "python", "javascript"]) or \
           any(k in tone_str for k in ["rational", "analytical", "precise"]) or \
           arch_str in ("stat-drop", "myth-vs-fact"):
            if "en-US-EricNeural" in active_pool:
                return "en-US-EricNeural"
            if "en-US-SteffanNeural" in active_pool:
                return "en-US-SteffanNeural"

        # 4. Lively / Listicle / Tips / Quick Hacks
        if any(k in topic_str for k in ["tip", "list", "hack", "quick", "top", "tools", "ways"]) or \
           any(k in tone_str for k in ["lively", "fun", "punchy", "casual"]) or \
           arch_str == "listicle-punch":
            if "en-US-RogerNeural" in active_pool:
                return "en-US-RogerNeural"
            if "en-US-AriaNeural" in active_pool:
                return "en-US-AriaNeural"

        # 5. Friendly Tutorial / How-To / SaaS / Onboarding / Product Walkthrough
        if any(k in topic_str for k in ["tutorial", "how to", "guide", "walkthrough", "onboarding", "intro", "beginner", "ui", "feature", "release"]) or \
           any(k in tone_str for k in ["friendly", "comfort", "helpful", "pleasant"]) or \
           arch_str == "explainer-stack":
            if "en-US-JennyNeural" in active_pool:
                return "en-US-JennyNeural"
            if "en-US-AriaNeural" in active_pool:
                return "en-US-AriaNeural"

        # 6. Default News / Product Announcement
        if "en-US-AriaNeural" in active_pool:
            return "en-US-AriaNeural"
        if "en-US-AndrewNeural" in active_pool:
            return "en-US-AndrewNeural"

    # For non-en-US or fallback, pick first voice matching personality or pool
    for v_name, meta in active_pool.items():
        if any(p.lower() in tone_str for p in meta.get("personalities", [])):
            return v_name

    # Return first available candidate in pool
    if active_pool:
        return next(iter(active_pool.keys()))

    return "en-US-AndrewNeural"


def main():
    parser = argparse.ArgumentParser(description="Query and recommend Edge-TTS voices")
    parser.add_argument("--list", action="store_true", help="List all supported voices")
    parser.add_argument("--locale", default="en-US", help="Filter by locale (e.g. en-US, es-ES, fr-FR, hi-IN)")
    parser.add_argument("--gender", choices=["male", "female"], help="Filter by gender")
    parser.add_argument("--validate", help="Validate a voice ShortName")
    parser.add_argument("--recommend", action="store_true", help="Recommend a voice based on topic and tone")
    parser.add_argument("--topic", help="Video or article topic")
    parser.add_argument("--tone", help="Desired voice personality/tone")
    parser.add_argument("--archetype", help="Video archetype")
    args = parser.parse_args()

    db = load_voice_database()

    if args.validate:
        valid = is_supported_voice(args.validate)
        if valid:
            info = db[args.validate]
            print(f"VALID: {args.validate} ({info['gender']}, {info['locale']}, Personalities: {info['personalities']}, Categories: {info['categories']})")
        else:
            print(f"INVALID: '{args.validate}' is not a supported Edge-TTS voice.")
            sys.exit(1)
        return

    if args.recommend:
        rec = recommend_voice(
            topic=args.topic,
            tone=args.tone,
            gender=args.gender,
            locale=args.locale,
            archetype=args.archetype,
        )
        info = db.get(rec, {})
        print(f"RECOMMENDED_VOICE: {rec}")
        print(f"Details: {info.get('gender')}, {info.get('locale')}, Personalities: {info.get('personalities')}, Categories: {info.get('categories')}")
        return

    if args.list:
        print(f"Supported Voices (Total {len(db)}):")
        filtered = {
            k: v for k, v in db.items()
            if (not args.locale or v.get("locale", "").lower().startswith(args.locale.lower())) and
               (not args.gender or v.get("gender", "").lower() == args.gender.lower())
        }
        for k, v in filtered.items():
            print(f"  {k:28} | {v.get('gender'):6} | {v.get('locale'):8} | {', '.join(v.get('personalities', []))}")
        print(f"\nTotal matching: {len(filtered)}")
        return

    parser.print_help()


if __name__ == "__main__":
    main()
