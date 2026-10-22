#!/usr/bin/env python3
"""
music_player_tools.py — Music Player, Procedural Synthesis & Audio Playback Engine.

Capabilities:
1. Track Library:
   - Indexes pre-rendered soundtrack WAV files in `./sounds/` (soundtracks, gospel, commercial, ambient).
2. Playback Control:
   - Native Device Audio: uses `termux-media-player` (or `paplay`) on Termux / Linux.
   - Web Audio Streaming: delivers playable browser URLs (`/sounds/<track>.wav`).
   - Stop, pause, resume, and status inspection.
3. Procedural Music Synthesis:
   - Built-in algorithmic audio synthesizer using Python standard `wave`, `math`, and `struct`.
   - Generates:
     - '432hz_ambient': Solfeggio 432 Hz healing harmonic drone & warm pentatonic melody.
     - 'reggae_dub': Offbeat skank chords and heavy groundation bassline.
     - '8bit_chiptune': Fast arpeggiated pulse waves and retro bass.
     - 'lofi_calm': Gentle triangle wave chords with warm vibrato.
4. How-To-Play Guide:
   - Provides clear instructions and tools guide for agents and users across CLI, API, and Web Audio.
"""

import collections
import glob
import json
import math
import os
import random
import re
import struct
import subprocess
import threading
import time
import wave
from typing import Any, Dict, List, Optional, Tuple

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SOUNDS_DIR = os.path.join(BASE_DIR, "sounds")

_LOCK = threading.Lock()
_CURRENT_PLAYBACK: Dict[str, Any] = {
    "is_playing": False,
    "current_track": None,
    "started_at": 0,
    "engine": None,
    "pid": None,
    "volume": 1.0,
    "loop": False,
}


def list_available_music_tracks(query: str = "", limit: int = 50) -> Dict[str, Any]:
    """Scan and categorize all available music files in sounds/."""
    if not os.path.exists(SOUNDS_DIR):
        return {"total": 0, "tracks": [], "categories": {}}

    all_wavs = sorted(glob.glob(os.path.join(SOUNDS_DIR, "*.wav")))
    q = query.lower().strip()

    categories = collections.defaultdict(list)
    tracks = []

    for path in all_wavs:
        fname = os.path.basename(path)
        if q and q not in fname.lower():
            continue

        # Categorize
        if "gospel" in fname:
            cat = "gospel"
        elif "religion" in fname:
            cat = "sacred_meditation"
        elif "commercial" in fname:
            cat = "commercial_synth"
        elif "procedural" in fname:
            cat = "procedural_synth"
        elif "chiptune" in fname:
            cat = "chiptune"
        elif "ambient" in fname or "432" in fname:
            cat = "ambient_432hz"
        elif "soundtrack" in fname:
            cat = "ambient_soundtrack"
        else:
            cat = "sfx_misc"

        try:
            sz_mb = round(os.path.getsize(path) / (1024 * 1024), 2)
        except Exception:
            sz_mb = 0.0

        item = {
            "track_id": fname.replace(".wav", ""),
            "filename": fname,
            "category": cat,
            "size_mb": sz_mb,
            "url": f"/sounds/{fname}",
        }
        categories[cat].append(item["track_id"])
        tracks.append(item)

    return {
        "ok": True,
        "total_tracks": len(tracks),
        "query": query,
        "categories_summary": {k: len(v) for k, v in categories.items()},
        "tracks": tracks[:limit],
    }


def get_music_guide() -> Dict[str, Any]:
    """Return instructions and tools manual for playing music across the system."""
    return {
        "ok": True,
        "title": "How to Play Music — Tools & Methods Guide",
        "methods": [
            {
                "method": "1. CLI / Terminal (Native Device Speaker)",
                "description": "Play pre-recorded tracks or generated melodies directly through device speakers via termux-media-player.",
                "commands": [
                    "python3 -c \"import music_player_tools as m; m.play_music('commercial_soundtrack')\"",
                    "termux-media-player play sounds/commercial_soundtrack.wav",
                    "termux-media-player stop",
                ],
            },
            {
                "method": "2. Procedural Music Synthesis (Pure Python)",
                "description": "Synthesize custom harmonic music on the fly (432Hz ambient, reggae dub, 8-bit chiptune, lofi).",
                "example": "python3 -c \"import music_player_tools as m; m.synthesize_procedural_melody('432hz_ambient', duration_sec=8)\"",
            },
            {
                "method": "3. REST API Endpoints",
                "description": "Trigger music playback or synthesize songs via HTTP JSON requests.",
                "endpoints": [
                    "POST /api/music/play with {'track': 'commercial_soundtrack'}",
                    "POST /api/music/compose with {'style': '432hz_ambient', 'duration_sec': 10}",
                    "POST /api/music/stop",
                    "GET /api/music/tracks?query=gospel",
                ],
            },
            {
                "method": "4. Web Billboard Audio (Browser / CRT Screen)",
                "description": "Play looped ambient tracks or synthesized audio nodes directly in the browser via Web Audio API or HTML5 <audio> tag.",
                "element": "document.getElementById('bg-audio').play()",
            },
            {
                "method": "5. LangChain Separation Tools",
                "description": "Multi-agent tool dispatch across degree partitions.",
                "tools": [
                    "play_music_tool",
                    "stop_music_tool",
                    "compose_procedural_music_tool",
                    "list_music_library_tool",
                ],
            },
        ],
    }


def stop_music() -> Dict[str, Any]:
    """Stop currently playing music on native device."""
    with _LOCK:
        stopped = False
        # Termux media player stop
        try:
            res = subprocess.run(["termux-media-player", "stop"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=2)
            if res.returncode == 0:
                stopped = True
        except Exception:
            pass

        # Pulseaudio paplay kill if running
        pid = _CURRENT_PLAYBACK.get("pid")
        if pid:
            try:
                os.kill(pid, 9)
                stopped = True
            except Exception:
                pass

        track_was = _CURRENT_PLAYBACK.get("current_track")
        _CURRENT_PLAYBACK["is_playing"] = False
        _CURRENT_PLAYBACK["current_track"] = None
        _CURRENT_PLAYBACK["pid"] = None
        _CURRENT_PLAYBACK["engine"] = None

        return {
            "ok": True,
            "action": "stop",
            "previous_track": track_was,
            "native_stopped": stopped,
        }


def play_music(track_id_or_name: str, volume: float = 1.0, loop: bool = False) -> Dict[str, Any]:
    """
    Play a music track by ID or filename.
    Attempts native hardware playback via termux-media-player or paplay,
    and returns browser web audio streaming URL.
    """
    clean_name = track_id_or_name.strip()
    if not clean_name.endswith(".wav"):
        target_path = os.path.join(SOUNDS_DIR, f"{clean_name}.wav")
    else:
        target_path = os.path.join(SOUNDS_DIR, clean_name)

    # If exact path not found, search fuzzy match
    if not os.path.exists(target_path):
        matches = glob.glob(os.path.join(SOUNDS_DIR, f"*{clean_name}*.wav"))
        if matches:
            target_path = matches[0]
        else:
            # Fallback to commercial_soundtrack.wav
            fallback = os.path.join(SOUNDS_DIR, "commercial_soundtrack.wav")
            if os.path.exists(fallback):
                target_path = fallback
            else:
                return {"ok": False, "error": f"Track '{track_id_or_name}' not found."}

    track_fname = os.path.basename(target_path)
    web_url = f"/sounds/{track_fname}"

    with _LOCK:
        # Stop any existing playback first
        try:
            subprocess.run(["termux-media-player", "stop"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=1)
        except Exception:
            pass

        native_engine = None
        proc_pid = None

        # Try termux-media-player
        try:
            r = subprocess.run(["termux-media-player", "play", target_path], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=3)
            if r.returncode == 0:
                native_engine = "termux-media-player"
        except Exception:
            pass

        # Try paplay if termux-media-player was unavailable
        if not native_engine:
            try:
                proc = subprocess.Popen(["paplay", target_path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                proc_pid = proc.pid
                native_engine = "paplay"
            except Exception:
                pass

        _CURRENT_PLAYBACK["is_playing"] = True
        _CURRENT_PLAYBACK["current_track"] = track_fname
        _CURRENT_PLAYBACK["started_at"] = int(time.time())
        _CURRENT_PLAYBACK["engine"] = native_engine or "web_audio_stream"
        _CURRENT_PLAYBACK["pid"] = proc_pid
        _CURRENT_PLAYBACK["volume"] = volume
        _CURRENT_PLAYBACK["loop"] = loop

        return {
            "ok": True,
            "track": track_fname,
            "native_engine": native_engine or "none (use web audio stream)",
            "audio_url": web_url,
            "volume": volume,
            "loop": loop,
            "instruction": f"Playing on {native_engine or 'Web Audio'}. Access in browser at {web_url}.",
        }


def get_playback_status() -> Dict[str, Any]:
    """Get current music playback status."""
    with _LOCK:
        status = dict(_CURRENT_PLAYBACK)
        if status.get("is_playing"):
            elapsed = int(time.time()) - status.get("started_at", 0)
            status["elapsed_seconds"] = elapsed
        return {"ok": True, "playback": status}


# ===================== PROCEDURAL MUSIC SYNTHESIS ENGINE =====================

def synthesize_procedural_melody(
    style: str = "432hz_ambient",
    duration_sec: float = 6.0,
    tempo_bpm: int = 72,
    key_hz: float = 432.0,
    filename: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Procedurally synthesizes a WAV audio music file using pure Python (math + wave).

    Styles:
    - '432hz_ambient': Solfeggio 432Hz sine wave harmonics with gentle vibrato and drone.
    - 'reggae_dub': Bassline pulse with offbeat syncopated chords.
    - '8bit_chiptune': Arpeggiated square/pulse waves in retro arcade cadence.
    - 'lofi_calm': Warm triangle wave chords with vinyl crackle simulation.
    """
    sample_rate = 22050
    total_samples = int(sample_rate * duration_sec)
    num_channels = 1
    sampwidth = 2  # 16-bit PCM

    style = style.lower().strip()
    if not filename:
        ts = int(time.time() * 1000) % 100000
        clean_style = re.sub(r"[^a-zA-Z0-9_]", "_", style)
        filename = f"procedural_{clean_style}_{ts}.wav"

    out_path = os.path.join(SOUNDS_DIR, filename)

    # Note frequencies based on root key_hz
    # Pentatonic ratios: 1, 9/8, 5/4, 3/2, 5/3, 2
    ratios = [1.0, 9 / 8, 5 / 4, 3 / 2, 5 / 3, 2.0]
    scale_freqs = [key_hz * r for r in ratios]
    bass_freqs = [key_hz * 0.5 * r for r in ratios[:3]]

    frames = bytearray()
    beat_sec = 60.0 / max(30, tempo_bpm)
    samples_per_beat = int(sample_rate * beat_sec)

    for i in range(total_samples):
        t = i / sample_rate
        beat_idx = int(i / samples_per_beat)

        val = 0.0

        if "432" in style or "ambient" in style:
            # 432Hz Solfeggio Healing Harmonics with gentle LFO vibrato
            vibrato = math.sin(2.0 * math.pi * 3.5 * t) * 1.5
            freq1 = key_hz + vibrato
            freq2 = key_hz * 1.5  # perfect fifth (648 Hz)
            freq3 = key_hz * 0.5  # sub-octave bass (216 Hz)
            # Smooth envelope
            fade = min(1.0, t / 0.8) * min(1.0, (duration_sec - t) / 0.8)
            val = (
                0.40 * math.sin(2.0 * math.pi * freq1 * t)
                + 0.25 * math.sin(2.0 * math.pi * freq2 * t)
                + 0.30 * math.sin(2.0 * math.pi * freq3 * t)
            ) * fade

        elif "reggae" in style or "dub" in style:
            # Offbeat skank chords (on upbeats) + heavy sub bass
            sub_freq = bass_freqs[beat_idx % len(bass_freqs)]
            bass = 0.55 * math.sin(2.0 * math.pi * sub_freq * t)

            # Upbeat skank pulse (second half of beat)
            phase_in_beat = (i % samples_per_beat) / samples_per_beat
            skank = 0.0
            if 0.45 <= phase_in_beat <= 0.75:
                chord_freq = scale_freqs[(beat_idx + 2) % len(scale_freqs)]
                skank = 0.35 * (1.0 if math.sin(2.0 * math.pi * chord_freq * t) > 0 else -1.0)
            val = (bass + skank) * 0.7

        elif "8bit" in style or "chip" in style:
            # Fast 16th-note arpeggio pulse wave
            arp_step = int((t * (tempo_bpm / 60.0) * 4)) % len(scale_freqs)
            arp_freq = scale_freqs[arp_step]
            # Square wave with 25% duty cycle
            phase = (t * arp_freq) % 1.0
            sq = 1.0 if phase < 0.25 else -1.0
            val = sq * 0.35

        else:  # lofi_calm / default
            # Triangle waves chord progression
            f1 = scale_freqs[beat_idx % len(scale_freqs)]
            f2 = scale_freqs[(beat_idx + 2) % len(scale_freqs)]
            tri1 = 2.0 * abs(2.0 * ((t * f1) % 1.0) - 1.0) - 1.0
            tri2 = 2.0 * abs(2.0 * ((t * f2) % 1.0) - 1.0) - 1.0
            # Gentle lofi crackle
            crackle = (random.random() - 0.5) * 0.04 if random.random() < 0.08 else 0.0
            val = (0.35 * tri1 + 0.25 * tri2 + crackle) * 0.7

        # Clip sample to 16-bit range (-32767 to 32767)
        val = max(-1.0, min(1.0, val))
        sample_int = int(val * 32000)
        frames.extend(struct.pack("<h", sample_int))

    try:
        with wave.open(out_path, "wb") as wf:
            wf.setnchannels(num_channels)
            wf.setsampwidth(sampwidth)
            wf.setframerate(sample_rate)
            wf.writeframes(frames)
    except Exception as e:
        return {"ok": False, "error": f"Failed to write WAV file: {e}"}

    return {
        "ok": True,
        "style": style,
        "duration_sec": duration_sec,
        "tempo_bpm": tempo_bpm,
        "key_hz": key_hz,
        "filename": filename,
        "audio_url": f"/sounds/{filename}",
        "file_path": out_path,
        "instruction": f"Synthesized '{style}' track ({duration_sec}s). Ready for playback at /sounds/{filename}.",
    }


if __name__ == "__main__":
    print("Testing music synthesis...")
    res = synthesize_procedural_melody(style="432hz_ambient", duration_sec=3.0)
    print("Synthesized:", res.get("filename"), "at", res.get("audio_url"))
    tracks = list_available_music_tracks(limit=5)
    print("Tracks count:", tracks.get("total_tracks"))
    guide = get_music_guide()
    print("Guide methods:", len(guide.get("methods", [])))
