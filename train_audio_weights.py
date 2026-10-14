#!/usr/bin/env python3
"""Trainer: turn a raw audio/shift log into next-audio selection weights.

Reads a log file (or stdin) containing lines like:
    [log] AUDIO +0.49s MEDIA.play [news_ticker.wav] :: ...
    [log] AUDIO +0.50s TTS.speak ["..."] :: ...
    [log] SHIFT SPIKE @ band 2 ~74Hz (+71) -> ...
    [log] SHIFT GUARD-COMBO @ 74Hz -> POW COMBO!
    [log] SHIFT SILENCE @ mean<4 for 5s -> re-triggered ambient bed

and learns a weighted profile of which audio action follows which. The
result (audio_weights.json) is intended to drive 95% of next-audio choices.
"""
import argparse
import json
import os
import re
import sys
from collections import Counter, defaultdict


# Event kinds we care about, in priority order when multiple appear on a
# line. The "next audio thing to play" decision mostly switches between
# these high-level actions.
KIND_PATTERNS = [
    ("media_play", re.compile(r"MEDIA\.play\s*\[([^\]]+)\]")),
    ("media_pause", re.compile(r"MEDIA\.pause\s*\[([^\]]+)\]")),
    ("tts_speak", re.compile(r"TTS\.speak\s*\[\"([^\]]*)")),
    ("tts_cancel", re.compile(r"TTS\.cancel")),
    ("spike", re.compile(r"SHIFT\s+SPIKE\s+@\s+band\s+(\d+)\s+~([0-9.]+(?:k?Hz))")),
    ("guard_combo", re.compile(r"SHIFT\s+GUARD-COMBO\s+@\s+(\S+)\s*->\s*(.+)")),
    ("howl", re.compile(r"SHIFT\s+HOWL\s+@\s+(\S+)")),
    ("silence", re.compile(r"SHIFT\s+SILENCE\s+@\s+(.+)")),
]


def classify_line(line):
    for name, pat in KIND_PATTERNS:
        m = pat.search(line)
        if m:
            detail = m.group(1).strip() if m.groups() else ""
            return name, detail
    return None, None


def parse_log(text):
    events = []
    for raw in text.splitlines():
        kind, detail = classify_line(raw)
        if kind:
            events.append({"kind": kind, "detail": detail})
    return events


def build_weights(events):
    # Transition counts: from (prev_kind, prev_detail) to next kind/detail.
    transitions = defaultdict(Counter)
    kind_counts = Counter()
    combo_counts = Counter()

    prev = None
    for ev in events:
        if prev is not None:
            transitions[(prev["kind"], prev["detail"])][(ev["kind"], ev["detail"])] += 1
        kind_counts[ev["kind"]] += 1
        if ev["kind"] == "guard_combo":
            combo_counts[ev["detail"]] += 1
        prev = ev

    # Normalize to probabilities per source state.
    transition_probs = {}
    for src, counter in transitions.items():
        total = sum(counter.values())
        if total == 0:
            continue
        transition_probs[f"{src[0]}::{src[1]}"] = {
            f"{dst[0]}::{dst[1]}": round(n / total, 6)
            for dst, n in counter.most_common()
        }

    # Global next-audio action distribution (ignores source state).
    next_audio_actions = Counter()
    for ev in events:
        if ev["kind"] in ("media_play", "tts_speak", "guard_combo", "howl", "silence"):
            next_audio_actions[ev["kind"]] += 1
    total_audio = sum(next_audio_actions.values()) or 1
    action_weights = {k: round(v / total_audio, 6) for k, v in next_audio_actions.most_common()}

    return {
        "version": 1,
        "use_weighted_pct": 95,
        "event_count": len(events),
        "kind_counts": dict(kind_counts),
        "action_weights": action_weights,
        "combo_counts": dict(combo_counts),
        "transition_probabilities": transition_probs,
    }


def main():
    ap = argparse.ArgumentParser(description="Train next-audio weights from a log")
    ap.add_argument("logfile", nargs="?", default="audio_training.log",
                    help="path to raw audio log (default: audio_training.log)")
    ap.add_argument("-o", "--out", default="audio_weights.json",
                    help="output weights file (default: audio_weights.json)")
    args = ap.parse_args()

    if args.logfile == "-" or not os.path.exists(args.logfile):
        text = sys.stdin.read()
    else:
        with open(args.logfile, "r", encoding="utf-8", errors="replace") as f:
            text = f.read()

    events = parse_log(text)
    weights = build_weights(events)

    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(weights, f, indent=2, ensure_ascii=False)

    print(f"Trained on {len(events)} events -> {args.out}")
    print(f"  use_weighted_pct : {weights['use_weighted_pct']}%")
    print(f"  kind_counts      : {weights['kind_counts']}")
    print(f"  action_weights   : {weights['action_weights']}")
    print(f"  combo_counts     : {weights['combo_counts']}")


if __name__ == "__main__":
    main()
