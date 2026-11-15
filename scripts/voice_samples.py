#!/usr/bin/env python3
"""Audition Dandolla1 only, using short, emotive British-English Eleven v4 samples.

The request is authorised by adding a NEW .voice-auditions/generate-*.request file.
No full review audio is generated or published by this script.
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
AUTH = "AUTHORIZE_SHORT_PAID_VOICE_AUDITIONS_ONLY"
VOICE_NAME = "Dandolla1"
API = "https://api.elevenlabs.io"

# Scripts are short extracts from the published reviews. Audio tags are performance
# directions only and do not change the actual article text.
# Stability and similarity balance emotional expressiveness and clone fidelity.
SAMPLES = [
    ("05-danganronpa-dandolla1-dry-british", 0.45, 0.85,
     "[British accent] [dryly amused] Lads and lasses, I absolutely hate the true ending. "
     "And not because it's optimistic. There's nothing inherently wrong with a story about hope overcoming despair. "
     "[sarcastic] But the game executes that message with all the subtlety of a motivational poster in a corporate office in Orwell's 1984-esque style."),
    ("06-danganronpa-dandolla1-theatrical-british", 0.30, 0.75,
     "[British accent] [exasperated] The final chapter should have been the culmination of everything the game had established. "
     "[incredulous] But goodness, is the delivery painfully exhausting. "
     "[sarcastic] Instead of allowing the revelations to speak for themselves, the game insists on explaining practically everything at enormous length."),
    ("07-signalis-dandolla1-reflective-british", 0.50, 0.90,
     "[British accent] [softly, with restrained sadness] Its own machinery has fallen in love. "
     "[thoughtfully] There is another character who deserves considerably more appreciation than I initially gave him. Adler. "
     "[sorrowful] One must imagine Adler happy. Because I certainly cannot."),
    ("08-signalis-dandolla1-emotional-british", 0.30, 0.80,
     "[British accent] [wistfully] Its own machinery has fallen in love. "
     "[softly] There is another character who deserves considerably more appreciation than I initially gave him. Adler. "
     "[with growing sadness] One must imagine Adler happy. [quietly] Because I certainly cannot."),
]

def api_json(path, key):
    req = request.Request(API + path,
        headers={"xi-api-key": key, "Accept": "application/json"})
    try:
        with request.urlopen(req, timeout=40) as response:
            return json.load(response)
    except error.HTTPError as exc:
        raise RuntimeError(f"ElevenLabs metadata lookup failed: HTTP {exc.code}") from None

def resolve_voice_id(key):
    # Do not trust an older GitHub voice ID after the user's voice deletion.
    # Look up the voice by its exact name in their current account.
    voices = api_json("/v1/voices", key).get("voices", [])
    matches = [v for v in voices if v.get("name") == VOICE_NAME]
    if len(matches) != 1:
        names = [v.get("name") for v in voices]
        raise RuntimeError(f"Expected exactly one {VOICE_NAME!r} voice, found {len(matches)}. Available voice names: {names}")
    voice = matches[0]
    voice_id = voice.get("voice_id")
    accent = (voice.get("labels") or {}).get("accent", "")
    print(f"VOICE_CONFIRMED name={VOICE_NAME!r} accent={accent!r} category={voice.get('category')!r}", flush=True)
    if not voice_id:
        raise RuntimeError("Selected voice has no usable ID")
    # We require that the voice is explicitly classified as British.
    if "british" not in accent.lower() and accent.lower() not in ("uk", "en-gb"):
        raise RuntimeError("Dandolla1 is not labelled British; stopped before spending credits. Check the clone's source audio.")
    return voice_id

def new_request():
    before = os.getenv("GITHUB_EVENT_BEFORE", "").strip()
    after = os.getenv("GITHUB_SHA", "").strip()
    if not before or not after or set(before) == {"0"}:
        return False
    changed = subprocess.check_output(["git", "diff", "--diff-filter=A", "--name-only",
        before, after, "--", ".voice-auditions/"], cwd=ROOT, text=True).splitlines()
    markers = [p for p in changed if p.startswith(".voice-auditions/generate-") and p.endswith(".request")]
    if not markers:
        return False
    if len(markers) != 1 or (ROOT / markers[0]).read_text(encoding="utf-8").strip() != AUTH:
        raise RuntimeError("Expected one valid, explicit short-audition request")
    return True

def generate():
    key = os.getenv("ELEVENLABS_API_KEY", "").strip()
    if not key.startswith("sk_"):
        raise RuntimeError("ElevenLabs secret API key is missing")
    voice_id = resolve_voice_id(key)
    DEST.mkdir(parents=True, exist_ok=True)
    results = []
    for filename, stability, similarity, content in SAMPLES:
        target = DEST / (filename + ".mp3")
        if target.exists():
            print(f"SKIPPING_EXISTING_SAMPLE {filename}", flush=True)
            continue
        print(f"VOICE_AUDITION_START {filename}: {len(content)} characters, model=eleven_v4, stability={stability}", flush=True)
        payload = json.dumps({"text": content, "model_id": "eleven_v4",
            "language_code": "en",
            "voice_settings": {"stability": stability, "similarity_boost": similarity}}).encode("utf-8")
        req = request.Request(API + "/v1/text-to-speech/" + voice_id + "?output_format=mp3_44100_128",
            data=payload,
            headers={"xi-api-key": key, "Content-Type": "application/json", "Accept": "audio/mpeg"},
            method="POST")
        try:
            with request.urlopen(req, timeout=120) as response:
                data = response.read()
        except error.HTTPError as exc:
            detail = exc.read(1300).decode("utf-8", "replace")
            raise RuntimeError(f"ElevenLabs audition {filename} HTTP {exc.code}: {detail}") from None
        if not data.startswith((b"ID3", bytes([0xff,0xfb]), bytes([0xff,0xf3]), bytes([0xff,0xf2]))) or len(data) < 1000:
            raise RuntimeError("Invalid audio response: " + filename)
        target.write_bytes(data)
        results.append({"file": str(target.relative_to(ROOT)), "bytes": len(data)})
        print(f"VOICE_AUDITION_DONE {filename}: {len(data)} bytes", flush=True)
    print("VOICE_AUDITIONS_COMPLETE " + json.dumps(results), flush=True)

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
        print("No new paid auditions were requested in this commit.")
