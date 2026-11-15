#!/usr/bin/env python3
"""Four short ElevenLabs auditions, two verified British voices and two emotional moods.

Requires an explicit NEW .voice-auditions/generate-1.request marker.
Never modifies published posts or replaces existing recordings.
"""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
from urllib import request, error

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / "assets" / "voice-auditions"
MARKER_PREFIX = ".voice-auditions/generate-"
AUTH = "AUTHORIZE_SHORT_PAID_VOICE_AUDITIONS_ONLY"
VOICE_GEORGE = "JBFqnCBsd6RMkjVDRZzb"  # British storyteller
VOICE_DANIEL = "onwK4e9ZLuTAKqWW03F9"  # British broadcaster

# Excerpts chosen from the user's reviews; bracketed tags direct the performance,
# rather than altering the published review text.
SAMPLES = [
    ("01-danganronpa-george-wry", VOICE_GEORGE,
     "[dryly amused] Lads and lasses, I absolutely hate the true ending. "
     "And not because it's optimistic. There's nothing inherently wrong with a story about hope overcoming despair. "
     "[sarcastic] But the game executes that message with all the subtlety of a motivational poster in a corporate office in Orwell's 1984-esque style."),
    ("02-danganronpa-daniel-indignant", VOICE_DANIEL,
     "[incredulous] The final chapter should have been the culmination of everything the game had established. "
     "[exasperated] But goodness, is the delivery painfully exhausting. "
     "Instead of allowing the revelations to speak for themselves, the game insists on explaining practically everything at enormous length."),
    ("03-signalis-george-melancholy", VOICE_GEORGE,
     "[softly, with restrained sadness] Its own machinery has fallen in love. "
     "[thoughtfully] There is another character who deserves considerably more appreciation than I initially gave him. Adler. "
     "[sorrowful] One must imagine Adler happy. Because I certainly cannot."),
    ("04-signalis-daniel-reflective", VOICE_DANIEL,
     "[thoughtfully] There is something wonderfully ironic about a society that has perfected the mass production of artificial people, "
     "only to discover that these people insist on behaving like people. "
     "[quietly, melancholically] One must imagine Adler happy. Because I certainly cannot."),
]

def new_request():
    before = os.getenv("GITHUB_EVENT_BEFORE", "").strip()
    after = os.getenv("GITHUB_SHA", "").strip()
    if not before or not after or set(before) == {"0"}:
        return False
    changed = subprocess.check_output(["git", "diff", "--diff-filter=A", "--name-only", before, after,
                                       "--", ".voice-auditions/"], text=True, cwd=ROOT).splitlines()
    marker_files = [p for p in changed if p.startswith(MARKER_PREFIX) and p.endswith(".request")]
    if not marker_files:
        return False
    for item in marker_files:
        if (ROOT / item).read_text(encoding="utf-8").strip() != AUTH:
            raise RuntimeError("Voice auditions were not authorised")
    return True

def generate():
    key = os.getenv("ELEVENLABS_API_KEY", "").strip()
    if not key.startswith("sk_"):
        raise RuntimeError("Missing ElevenLabs secret API key")
    DEST.mkdir(parents=True, exist_ok=True)
    names = []
    for name, voice_id, txt in SAMPLES:
        target = DEST / f"{name}.mp3"
        if target.exists():
            print(f"ALREADY_EXISTS {name}; skipping charge")
            continue
        print(f"VOICE_AUDITION_START {name}: {len(txt)} characters; voice={voice_id}; model=eleven_v4", flush=True)
        payload = json.dumps({"text": txt, "model_id": "eleven_v4", "language_code": "en"}).encode("utf-8")
        req = request.Request(
            "https://api.elevenlabs.io/v1/text-to-speech/" + voice_id + "?output_format=mp3_44100_128",
            data=payload, headers={"xi-api-key": key, "Content-Type": "application/json", "Accept": "audio/mpeg"},
            method="POST")
        try:
            with request.urlopen(req, timeout=120) as resp:
                data = resp.read()
        except error.HTTPError as exc:
            msg = exc.read(1300).decode("utf-8", "replace")
            raise RuntimeError(f"ElevenLabs audition {name} HTTP {exc.code}: {msg}") from None
        if not data.startswith((b"ID3", b"\\xff\\xfb", b"\\xff\\xf3", b"\\xff\\xf2")) or len(data) < 1000:
            raise RuntimeError("Invalid audio response for " + name)
        target.write_bytes(data)
        names.append({"file": str(target.relative_to(ROOT)), "bytes": len(data)})
        print(f"VOICE_AUDITION_DONE {name}: {len(data)} bytes", flush=True)
    print("VOICE_AUDITIONS_COMPLETE " + json.dumps(names), flush=True)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--only-new-request", action="store_true")
    args = parser.parse_args()
    if not args.only_new_request or new_request():
        try:
            generate()
        except Exception as ex:
            print("VOICE_AUDITION_ERROR:", ex, file=sys.stderr)
            sys.exit(1)
    else:
        print("No paid voice audition request in this commit.")
