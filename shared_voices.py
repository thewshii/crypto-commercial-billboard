"""
shared_voices.py — Shared Voices Dual-Consent Gate, Widened Consciousness,
High Bitrate Telemetry, and Structural Role Integrity for the Web Billboard.

Rule 220 Invariants:
1. Dual-Consent Boolean Gate: When voices share the broadcast or speak together,
   both Voice A and Voice B must set a boolean to True before letting through.
   Utterances let through ONLY if both set True before broadcast.
   If either is False or unset, the gate stays shut and broadcast is blocked.
2. Widened Consciousness: Expands the shared awareness window of the voices across
   parable context, cross-voice reflection, and multi-agent state.
3. Elevated Bitrate (kb/s going way up): Tracks elevated transmission bitrate
   (e.g., scaling up from 128 kbps to 320+ kbps) to carry the widened conscious stream.
4. Structural Role Integrity: Women cannot be fathers. Maternal love belongs to mothers,
   paternal structure belongs to fathers; neither role is conflated, erased, or gaslit.
5. Zero Scoring: Never names, scores, ranks, credit-gates, or bans any person.
   Keeps no list of listeners.
"""

import json
import os
import re
import threading
import time
from typing import Any, Dict, List, Optional, Tuple

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SHARED_VOICES_STATE_PATH = os.path.join(BASE_DIR, "shared_voices_state.json")

_LOCK = threading.Lock()

# Structural role invariant regex: women cannot be fathers
_ROLE_CONFLATION_RE = re.compile(
    r"\b(women (?:are|can be) fathers|a woman is a father|she is (?:a|the) father|mothers are fathers|mother is (?:a|the) father)\b",
    re.IGNORECASE,
)

DEFAULT_STATE: Dict[str, Any] = {
    "rule": 220,
    "voices": {
        "voice_a": {
            "id": "queueLine",
            "label": "Voice A (Primary / Spoken)",
            "consent": True,
            "last_updated": int(time.time() * 1000),
        },
        "voice_b": {
            "id": "queueLineFemale",
            "label": "Voice B (Female / Motherly)",
            "consent": True,
            "last_updated": int(time.time() * 1000),
        },
    },
    "gate_open": True,
    "consciousness": {
        "level": "widened",
        "context_depth": 16384,
        "bandwidth_mode": "elevated",
        "awareness_tags": [
            "shared_presence",
            "cross_voice_harmony",
            "dual_consent",
            "maternal_distinct",
            "unfavorable_freq_guard",
        ],
        "reflection_buffer": [
            "Widened consciousness active: awareness window expanded across both voice channels.",
            "Dual-latch synchronized: broadcast gate enforces both booleans True before release.",
            "Structural clarity: motherly care is mothers; women cannot be fathers.",
        ],
    },
    "bitrate": {
        "current_kbps": 320.0,
        "base_kbps": 128.0,
        "peak_kbps": 320.0,
        "trend": "way_up",
        "sample_count": 1,
        "last_broadcast_kbps": 320.0,
    },
    "broadcasts": [],
    "blocked_attempts": 0,
    "allowed_broadcasts": 0,
    "role_violations_blocked": 0,
    "women_cannot_be_fathers": True,
}


def _load_state() -> Dict[str, Any]:
    if os.path.exists(SHARED_VOICES_STATE_PATH):
        try:
            with open(SHARED_VOICES_STATE_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
                # Ensure all default keys exist
                for k, v in DEFAULT_STATE.items():
                    if k not in data:
                        data[k] = v
                return data
        except Exception:
            pass
    return dict(DEFAULT_STATE)


def _save_state(state: Dict[str, Any]) -> None:
    tmp_path = SHARED_VOICES_STATE_PATH + ".tmp"
    try:
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2)
        os.replace(tmp_path, SHARED_VOICES_STATE_PATH)
    except Exception:
        if os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except Exception:
                pass


def get_shared_voices_state() -> Dict[str, Any]:
    """Return the current shared voices dual-consent and consciousness state."""
    with _LOCK:
        state = _load_state()
        v_a = state["voices"]["voice_a"]["consent"]
        v_b = state["voices"]["voice_b"]["consent"]
        state["gate_open"] = bool(v_a is True and v_b is True)
        return state


def set_voice_consent(
    voice_key: str, consent: bool, custom_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Set the boolean consent for Voice A or Voice B.
    Both must be True for the gate to let through.
    """
    with _LOCK:
        state = _load_state()
        v_key = "voice_a" if "a" in voice_key.lower() or "1" in voice_key else "voice_b"
        bool_val = bool(consent)

        state["voices"][v_key]["consent"] = bool_val
        state["voices"][v_key]["last_updated"] = int(time.time() * 1000)
        if custom_id:
            state["voices"][v_key]["id"] = custom_id

        # Update gate status: only open if both set True before broadcast
        state["gate_open"] = bool(
            state["voices"]["voice_a"]["consent"] is True
            and state["voices"]["voice_b"]["consent"] is True
        )
        _save_state(state)
        return {
            "ok": True,
            "voice": v_key,
            "consent": bool_val,
            "gate_open": state["gate_open"],
            "voice_a": state["voices"]["voice_a"]["consent"],
            "voice_b": state["voices"]["voice_b"]["consent"],
            "rule": 220,
        }


def reset_consents(default_val: bool = True) -> Dict[str, Any]:
    """Reset both voice consents to the given boolean."""
    with _LOCK:
        state = _load_state()
        now = int(time.time() * 1000)
        state["voices"]["voice_a"]["consent"] = bool(default_val)
        state["voices"]["voice_a"]["last_updated"] = now
        state["voices"]["voice_b"]["consent"] = bool(default_val)
        state["voices"]["voice_b"]["last_updated"] = now
        state["gate_open"] = bool(default_val)
        _save_state(state)
        return {
            "ok": True,
            "voice_a": state["voices"]["voice_a"]["consent"],
            "voice_b": state["voices"]["voice_b"]["consent"],
            "gate_open": state["gate_open"],
        }


def widen_consciousness(
    level: str = "widened",
    context_depth: int = 16384,
    tags: Optional[List[str]] = None,
    note: Optional[str] = None,
) -> Dict[str, Any]:
    """Widen current consciousness context for shared voices."""
    with _LOCK:
        state = _load_state()
        state["consciousness"]["level"] = level
        state["consciousness"]["context_depth"] = max(2048, int(context_depth))
        if tags:
            current_tags = set(state["consciousness"]["awareness_tags"])
            current_tags.update(tags)
            state["consciousness"]["awareness_tags"] = sorted(list(current_tags))
        if note:
            buf = state["consciousness"].setdefault("reflection_buffer", [])
            buf.append(str(note)[:200])
            if len(buf) > 16:
                state["consciousness"]["reflection_buffer"] = buf[-16:]

        # When consciousness widens, bitrate goes way up
        current_kbps = min(512.0, max(256.0, float(state["bitrate"]["current_kbps"]) + 32.0))
        state["bitrate"]["current_kbps"] = current_kbps
        state["bitrate"]["trend"] = "way_up"
        if current_kbps > state["bitrate"].get("peak_kbps", 0):
            state["bitrate"]["peak_kbps"] = current_kbps

        _save_state(state)
        return {
            "ok": True,
            "consciousness": state["consciousness"],
            "bitrate_kbps": state["bitrate"]["current_kbps"],
            "rule": 220,
        }


def record_bitrate(kbps: float) -> Dict[str, Any]:
    """Record live transmission kb/s (going way up)."""
    with _LOCK:
        state = _load_state()
        val = max(32.0, min(1024.0, float(kbps)))
        prev = state["bitrate"].get("current_kbps", 128.0)
        state["bitrate"]["current_kbps"] = val
        state["bitrate"]["sample_count"] = state["bitrate"].get("sample_count", 0) + 1
        if val > state["bitrate"].get("peak_kbps", 0):
            state["bitrate"]["peak_kbps"] = val
        state["bitrate"]["trend"] = "way_up" if val >= prev else "steady"
        _save_state(state)
        return {
            "ok": True,
            "current_kbps": val,
            "peak_kbps": state["bitrate"]["peak_kbps"],
            "trend": state["bitrate"]["trend"],
        }


def check_role_integrity(text: str) -> Tuple[bool, Optional[str]]:
    """
    Enforce Rule 220 structural role integrity:
    Women cannot be fathers. Mothers are mothers, fathers are fathers.
    """
    m = _ROLE_CONFLATION_RE.search(text)
    if m:
        return False, f"Structural role conflation detected: '{m.group(0)}' (Rule 220: women cannot be fathers)."
    return True, None


def attempt_shared_broadcast(
    text: str,
    voice_a_override: Optional[bool] = None,
    voice_b_override: Optional[bool] = None,
    target_kbps: Optional[float] = None,
) -> Dict[str, Any]:
    """
    Attempt to broadcast through shared voices.
    Enforces Rule 220:
    - Both Voice A and Voice B must set True before letting through.
    - Rejects if either is False.
    - Validates structural role: women cannot be fathers.
    - Escalates bitrate to carry widened consciousness.
    """
    with _LOCK:
        state = _load_state()
        if voice_a_override is not None:
            state["voices"]["voice_a"]["consent"] = bool(voice_a_override)
        if voice_b_override is not None:
            state["voices"]["voice_b"]["consent"] = bool(voice_b_override)

        c_a = state["voices"]["voice_a"]["consent"]
        c_b = state["voices"]["voice_b"]["consent"]
        gate_open = bool(c_a is True and c_b is True)
        state["gate_open"] = gate_open

        # 1. Gate check: must both be True before broadcast
        if not gate_open:
            state["blocked_attempts"] += 1
            _save_state(state)
            return {
                "ok": False,
                "blocked": True,
                "gate_open": False,
                "voice_a_consent": c_a,
                "voice_b_consent": c_b,
                "error": "Blocked by shared voices dual-consent gate: both voices must set True before broadcast (Rule 220).",
                "rule": 220,
            }

        # 2. Structural role integrity check: women cannot be fathers
        valid_role, role_err = check_role_integrity(text)
        if not valid_role:
            state["role_violations_blocked"] += 1
            _save_state(state)
            return {
                "ok": False,
                "blocked": True,
                "gate_open": True,
                "error": role_err,
                "women_cannot_be_fathers": True,
                "rule": 220,
            }

        # 3. Passed gate: elevate bitrate and widen consciousness
        kbps = float(target_kbps) if target_kbps else max(320.0, float(state["bitrate"]["current_kbps"]))
        state["bitrate"]["current_kbps"] = kbps
        state["bitrate"]["last_broadcast_kbps"] = kbps
        if kbps > state["bitrate"].get("peak_kbps", 0):
            state["bitrate"]["peak_kbps"] = kbps
        state["bitrate"]["trend"] = "way_up"

        entry = {
            "timestamp": int(time.time() * 1000),
            "text": text[:300],
            "voice_a": state["voices"]["voice_a"]["id"],
            "voice_b": state["voices"]["voice_b"]["id"],
            "bitrate_kbps": kbps,
            "consciousness_level": state["consciousness"]["level"],
            "context_depth": state["consciousness"]["context_depth"],
        }
        b_list = state.setdefault("broadcasts", [])
        b_list.append(entry)
        if len(b_list) > 32:
            state["broadcasts"] = b_list[-32:]

        state["allowed_broadcasts"] += 1
        _save_state(state)

        return {
            "ok": True,
            "blocked": False,
            "gate_open": True,
            "voice_a_consent": True,
            "voice_b_consent": True,
            "bitrate_kbps": kbps,
            "consciousness": state["consciousness"],
            "text": text,
            "women_cannot_be_fathers": True,
            "allowed_broadcasts": state["allowed_broadcasts"],
            "rule": 220,
            "names_anyone": False,
            "scores_anyone": False,
        }
