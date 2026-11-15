#!/usr/bin/env python3
"""No-charge inspection of ElevenLabs voices for British-accented review narrations."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
from urllib import request, error
from urllib.parse import urlencode

ROOT = Path(__file__).resolve().parents[1]
API = "https://api.elevenlabs.io"

def get_json(endpoint):
    key = os.environ.get("ELEVENLABS_API_KEY", "")
    if not key.startswith("sk_"):
        raise RuntimeError("ELEVENLABS_API_KEY must be an API secret, beginning with sk_")
    req = request.Request(API + endpoint, headers={"xi-api-key": key, "Accept": "application/json"})
    try:
        with request.urlopen(req, timeout=35) as resp:
            return json.load(resp)
    except error.HTTPError as exc:
        raise RuntimeError(f"ElevenLabs metadata request HTTP {exc.code}") from None

def inspect():
    voice_id = os.getenv("ELEVENLABS_VOICE_ID", "")
    if not voice_id:
        raise RuntimeError("ELEVENLABS_VOICE_ID is empty")
    current = get_json("/v1/voices/" + voice_id)
    print("CURRENT_VOICE", json.dumps({"name": current.get("name"), "labels": current.get("labels", {}),
                                        "voice_id": current.get("voice_id")}))
    query = urlencode({"accent": "british", "gender": "male", "language": "en", "page_size": 100})
    voices = get_json("/v2/voices?" + query)
    options = voices.get("voices", [])
    print("BRITISH_VOICES_AVAILABLE", len(options))
    for voice in options[:35]:
        print("UK_VOICE", json.dumps({"voice_id": voice.get("voice_id"),
                                     "name": voice.get("name"),
                                     "category": voice.get("category"),
                                     "labels": voice.get("labels", {}),
                                     "description": (voice.get("description") or "")[:180]}))
    print("VOICE_INSPECTION_COMPLETE_NO_AUDIO_GENERATED")

def new_marker():
    old, new = os.getenv("GITHUB_EVENT_BEFORE", ""), os.getenv("GITHUB_SHA", "")
    if not old or not new or set(old) == {"0"}:
        return False
    lines = subprocess.check_output(["git", "diff", "--diff-filter=A", "--name-only",
                                     old, new, "--", ".voice-auditions/"],
                                    cwd=ROOT, text=True).splitlines()
    return any(p.startswith(".voice-auditions/inspect-") and p.endswith(".request") for p in lines)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--inspect-on-new-marker", action="store_true")
    args = parser.parse_args()
    if not args.inspect_on_new_marker or new_marker():
        try:
            inspect()
        except Exception as exc:
            print("VOICE_INSPECTION_FAILED:", exc, file=sys.stderr)
            sys.exit(1)
    else:
        print("No new voice inspection marker.")
