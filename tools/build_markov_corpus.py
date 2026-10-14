#!/usr/bin/env python3
"""Build a filtered Markov chain from the live-room logs.

Reads deepgram_live_log.csv + toxicity_log.csv, extracts spoken text,
filters out toxicity, and writes an order-2 word Markov chain as JSON
for the billboard frontend (static/markov_chain.json).

What gets filtered OUT (never enters the chain):
  - Profanity / slurs / sexually explicit tokens (blocklist below).
  - [LOWQ] phone-overlay OCR rows (app UI strings, not speech).
  - [15S-UPDATE] rollup rows (aggregates, not speech).
  - Non-ASCII / non-English lines (TTS is en-US; keeps output speakable).
  - The raw CSVs are NOT committed to the repo: they contain real
    handles and unfiltered room speech. Only this filtered chain ships.

Usage:
  python3 tools/build_markov_corpus.py deepgram_live_log.csv toxicity_log.csv
  python3 tools/build_markov_corpus.py deepgram_live_log.csv toxicity_log.csv -o static/markov_chain.json
"""

import argparse
import csv
import json
import random
import re
import sys
from collections import defaultdict

BLOCKLIST = {
    "fuck", "shit", "bitch", "dick", "porn", "pussy", "cunt",
    "whore", "slut", "nigga", "nigger", "cock", "bastard",
    "piss", "ass", "dickhead", "shithead", "motherfucker",
}
BLOCK_RE = re.compile(
    r"\b(" + "|".join(re.escape(w) for w in sorted(BLOCKLIST)) + r")\b",
    re.IGNORECASE,
)

# [Category|SENTIMENT] prefix on deepgram rows
DEEPGRAM_PREFIX_RE = re.compile(r"^\[[^\]]*\]\s*")
# Keep only plain English letters, digits, spaces, basic punctuation
ASCII_RE = re.compile(r"^[A-Za-z0-9\s\.,!?'\-]+$")
WORD_RE = re.compile(r"[A-Za-z0-9']+|[.,!?]")


def clean_deepgram_text(raw):
    if not raw:
        return None
    text = raw.strip()
    if text.startswith("[15S-UPDATE]"):
        return None
    text = DEEPGRAM_PREFIX_RE.sub("", text).strip()
    return text or None


def clean_toxicity_text(raw):
    if not raw:
        return None
    text = raw.strip()
    if text.startswith("[LOWQ]"):
        return None  # phone-overlay OCR of app UI, not speech
    return text or None


def keep_line(text):
    if not text or len(text.split()) < 2:
        return False
    if BLOCK_RE.search(text):
        return False
    if not ASCII_RE.match(text):
        return False
    return True


def tokenize(line):
    return WORD_RE.findall(line)


def build_chain(lines, order=2):
    chain = defaultdict(lambda: defaultdict(int))
    starts = []
    for line in lines:
        toks = tokenize(line)
        if len(toks) < order + 1:
            continue
        starts.append(tuple(toks[:order]))
        for i in range(len(toks) - order):
            key = tuple(toks[i:i + order])
            nxt = toks[i + order]
            chain[key][nxt] += 1
    # JSON-serializable: "w1 w2" -> {next: count}
    serial = {
        " ".join(k): dict(v) for k, v in chain.items()
    }
    start_list = [" ".join(s) for s in starts]
    return serial, start_list


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("deepgram_csv")
    ap.add_argument("toxicity_csv")
    ap.add_argument("-o", "--output", default="static/markov_chain.json")
    ap.add_argument("--order", type=int, default=2)
    args = ap.parse_args()

    lines = []
    with open(args.deepgram_csv, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            t = clean_deepgram_text(row.get("text", ""))
            if t and keep_line(t):
                lines.append(t)
    with open(args.toxicity_csv, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            t = clean_toxicity_text(row.get("text", ""))
            if t and keep_line(t):
                lines.append(t)

    # Dedupe exact lines (the log carries near-duplicate transcription passes)
    lines = sorted(set(lines))
    chain, starts = build_chain(lines, order=args.order)

    out = {
        "order": args.order,
        "sources": ["deepgram_live_log.csv", "toxicity_log.csv"],
        "filtered_lines": len(lines),
        "states": len(chain),
        "starts": starts,
        "chain": chain,
        "note": "Filtered corpus: profanity/slurs/sexual content, [LOWQ] UI OCR, "
                "and [15S-UPDATE] rollups removed. Raw CSVs are not in the repo.",
    }
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(out, f, separators=(",", ":"))
    print(f"lines kept: {len(lines)}")
    print(f"chain states: {len(chain)}")
    print(f"wrote: {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
