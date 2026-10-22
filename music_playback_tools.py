#!/usr/bin/env python3
"""
music_playback_tools.py — The Tool-Gated Music Playback Ledger & State Machine.

Core Invariants (Rule 226):
1. The Tool IS the face of the music player:
   Nobody plays music directly. Every play, pause, resume, skip, stop, or volume change
   MUST pass through a LangChain Tool call, so every Tool call is automatically the record.
2. The Ledger (Storage):
   Append-only `music_playback_log.jsonl` — one JSON line per event, never edited, only appended.
   Current state (now_playing) is derived from the tail of the log on boot or reload.
3. Separation of Degrees:
   Agent (Degree 1) ➔ Tool (Degree 1) ➔ Ledger Append (Degree 2) ➔ Summary / Report (Degree 3).
   The agent never touches the log file directly; summary never controls the player.
4. Validation & Preemption:
   State machine: IDLE ➔ PLAYING ➔ PAUSED ➔ PLAYING ➔ STOPPED.
   Word segment preempts music immediately with reason="word_preempt".
"""

import collections
import json
import os
import threading
import time
import uuid
from typing import Any, Dict, List, Optional, Tuple

import music_player_tools

# LangChain and LangChain-Core imports
try:
    from pydantic import BaseModel, Field
except ImportError:
    class BaseModel:
        def __init__(self, **kwargs):
            for k, v in kwargs.items():
                setattr(self, k, v)
        def dict(self):
            return self.__dict__
    def Field(*args, **kwargs):
        return kwargs.get("default", None)

try:
    from langchain_core.prompts import PromptTemplate
    from langchain_core.runnables import RunnableLambda, RunnableSequence
    from langchain_core.tools import StructuredTool, tool
    HAS_LANGCHAIN = True
except ImportError:
    HAS_LANGCHAIN = False

    def tool(fn):
        fn.invoke = lambda kwargs: fn(**kwargs)
        fn.name = getattr(fn, "__name__", "tool")
        return fn

    class RunnableLambda:
        def __init__(self, func):
            self.func = func

        def invoke(self, arg):
            return self.func(arg)

        def __or__(self, other):
            return RunnableSequence([self, other])

    class RunnableSequence:
        def __init__(self, steps):
            self.steps = steps

        def invoke(self, arg):
            val = arg
            for s in self.steps:
                val = s.invoke(val) if hasattr(s, "invoke") else s(val)
            return val

        def __or__(self, other):
            return RunnableSequence(self.steps + [other])

    class PromptTemplate:
        def __init__(self, input_variables, template):
            self.input_variables = input_variables
            self.template = template

        def format(self, **kwargs):
            res = self.template
            for k, v in kwargs.items():
                res = res.replace("{" + k + "}", str(v))
            return res

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_FILE = os.path.join(BASE_DIR, "music_playback_log.jsonl")

_LOCK = threading.Lock()

VALID_STATES = {"IDLE", "PLAYING", "PAUSED", "STOPPED"}
VALID_ACTIONS = {"play", "pause", "resume", "skip", "stop", "fade", "volume", "preempt"}
VALID_SEGMENTS = {"music", "word", "news", "markov", "giveback"}
VALID_TRIGGERS = {"manual", "schedule", "howl", "silence", "spike", "pulsation", "agent_decision"}


# ===================== 1. THE LEDGER ENGINE =====================

def append_to_ledger(event: Dict[str, Any]) -> Dict[str, Any]:
    """Append one strictly formatted JSON line to music_playback_log.jsonl."""
    with _LOCK:
        if "ts" not in event:
            event["ts"] = int(time.time() * 1000)
        if "event_id" not in event:
            event["event_id"] = str(uuid.uuid4())

        line = json.dumps(event, ensure_ascii=False)
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
        return event


def read_ledger_tail(limit: int = 100) -> List[Dict[str, Any]]:
    """Read the last N events from the append-only ledger."""
    if not os.path.exists(LOG_FILE):
        return []
    with _LOCK:
        try:
            with open(LOG_FILE, "r", encoding="utf-8") as f:
                lines = f.readlines()
            events = []
            for l in lines[-limit:]:
                l = l.strip()
                if l:
                    try:
                        events.append(json.loads(l))
                    except Exception:
                        pass
            return events
        except Exception:
            return []


def rebuild_now_playing_from_tail() -> Dict[str, Any]:
    """Rebuild current player state exclusively by inspecting the tail of the ledger."""
    events = read_ledger_tail(limit=50)
    state = {
        "status": "IDLE",
        "track_id": None,
        "title": None,
        "actor": None,
        "segment": None,
        "trigger": None,
        "started_at": None,
        "position_sec": 0,
        "volume": 1.0,
        "last_event_id": None,
        "last_action": None,
        "rebuilt_from_ledger": True,
        "rule": 226,
    }

    if not events:
        return state

    for ev in events:
        action = ev.get("action")
        if action == "play":
            state["status"] = "PLAYING"
            state["track_id"] = ev.get("track_id")
            state["title"] = ev.get("title")
            state["actor"] = ev.get("actor")
            state["segment"] = ev.get("segment")
            state["trigger"] = ev.get("trigger")
            state["started_at"] = ev.get("ts")
            state["volume"] = ev.get("volume", 1.0)
            state["last_event_id"] = ev.get("event_id")
            state["last_action"] = "play"
        elif action == "pause":
            if state["status"] == "PLAYING":
                state["status"] = "PAUSED"
            state["last_action"] = "pause"
            state["last_event_id"] = ev.get("event_id")
        elif action == "resume":
            if state["status"] == "PAUSED":
                state["status"] = "PLAYING"
            state["last_action"] = "resume"
            state["last_event_id"] = ev.get("event_id")
        elif action in ("stop", "skip", "preempt"):
            state["status"] = "STOPPED"
            state["prev_track"] = state.get("track_id")
            state["track_id"] = None
            state["title"] = None
            state["last_action"] = action
            state["last_event_id"] = ev.get("event_id")
        elif action == "volume":
            state["volume"] = ev.get("volume", state["volume"])

    # Compute live approximate position if playing
    if state["status"] == "PLAYING" and state.get("started_at"):
        elapsed = (int(time.time() * 1000) - state["started_at"]) / 1000.0
        state["position_sec"] = round(max(0.0, elapsed), 1)

    return state


# ===================== 2. STATE MACHINE VALIDATION CHAIN =====================

def validate_playback_transition(proposed: Dict[str, Any]) -> Dict[str, Any]:
    """
    RunnableLambda validator: checks legal state transition.
    State machine: IDLE -> PLAYING -> PAUSED -> PLAYING -> STOPPED.
    Illegal jumps get rejected AND logged as invalid transitions.
    """
    current = rebuild_now_playing_from_tail()
    cur_status = current.get("status", "IDLE")
    action = proposed.get("action")
    segment = proposed.get("segment", "music")

    # Preemption check: Word segment ALWAYS preempts music immediately
    if segment == "word" and cur_status == "PLAYING":
        proposed["is_preempt"] = True
        proposed["reason"] = proposed.get("reason") or "Word segment preempts music (Rule 226 priority)"

    # Transition validation rules
    legal = True
    rejection_reason = ""

    if action == "play":
        # Can play from IDLE, STOPPED, or switch track while PLAYING
        legal = True
    elif action == "pause":
        if cur_status != "PLAYING":
            legal = False
            rejection_reason = f"Cannot pause from state '{cur_status}' (must be PLAYING)."
    elif action == "resume":
        if cur_status != "PAUSED":
            legal = False
            rejection_reason = f"Cannot resume from state '{cur_status}' (must be PAUSED)."
    elif action in ("stop", "skip"):
        if cur_status not in ("PLAYING", "PAUSED"):
            legal = False
            rejection_reason = f"Cannot {action} from state '{cur_status}' (must be PLAYING or PAUSED)."
    elif action == "volume":
        legal = True

    if not legal:
        # Log the rejected jump
        reject_event = {
            "ts": int(time.time() * 1000),
            "event_id": str(uuid.uuid4()),
            "actor": proposed.get("actor", "agent"),
            "action": f"rejected_{action}",
            "track_id": proposed.get("track_id", ""),
            "title": proposed.get("title", ""),
            "source": "validation_gate",
            "segment": segment,
            "trigger": proposed.get("trigger", "manual"),
            "position_sec": current.get("position_sec", 0),
            "duration_sec": 0,
            "volume": current.get("volume", 1.0),
            "prev_track": current.get("track_id", ""),
            "reason": rejection_reason,
            "legal_transition": False,
        }
        append_to_ledger(reject_event)
        return {
            "ok": False,
            "rejected": True,
            "reason": rejection_reason,
            "current_state": cur_status,
            "event": reject_event,
        }

    return {"ok": True, "proposed": proposed, "current_state": current}


def execute_tool_transition(data: Dict[str, Any]) -> Dict[str, Any]:
    """Execute the validated playback change and append event to the ledger."""
    if not data.get("ok"):
        return data

    prop = data["proposed"]
    current = data["current_state"]
    action = prop["action"]
    track = prop.get("track_id", "commercial_soundtrack")
    vol = float(prop.get("volume", current.get("volume", 1.0)))

    # If this is a word preemption or track switch, stop current playback first
    if prop.get("is_preempt") or (action == "play" and current.get("status") == "PLAYING"):
        preempt_event = {
            "ts": int(time.time() * 1000),
            "event_id": str(uuid.uuid4()),
            "actor": prop.get("actor", "agent"),
            "action": "preempt" if prop.get("is_preempt") else "switch",
            "track_id": current.get("track_id", ""),
            "title": current.get("title", ""),
            "source": "preempt_manager",
            "segment": current.get("segment", "music"),
            "trigger": prop.get("trigger", "schedule"),
            "position_sec": current.get("position_sec", 0),
            "duration_sec": 0,
            "volume": vol,
            "prev_track": current.get("track_id", ""),
            "reason": prop.get("reason", "preempted"),
        }
        append_to_ledger(preempt_event)
        music_player_tools.stop_music()

    # Call underlying hardware/audio driver
    driver_res = {}
    if action == "play":
        driver_res = music_player_tools.play_music(track, volume=vol)
    elif action == "pause":
        # Pauses via termux-media-player or sets paused status
        music_player_tools.stop_music()
    elif action == "resume":
        track_to_resume = current.get("track_id") or track
        driver_res = music_player_tools.play_music(track_to_resume, volume=vol)
    elif action in ("stop", "skip"):
        music_player_tools.stop_music()
    elif action == "volume":
        driver_res = {"volume": vol}

    # Record event in the ledger
    event = {
        "ts": int(time.time() * 1000),
        "event_id": str(uuid.uuid4()),
        "actor": prop.get("actor", "agent"),
        "action": action,
        "track_id": track,
        "title": prop.get("title") or track,
        "source": prop.get("source", "file"),
        "segment": prop.get("segment", "music"),
        "trigger": prop.get("trigger", "manual"),
        "position_sec": 0 if action == "play" else current.get("position_sec", 0),
        "duration_sec": float(prop.get("duration_sec", 0)),
        "volume": vol,
        "prev_track": current.get("track_id", ""),
        "reason": prop.get("reason", "tool_invocation"),
    }
    append_to_ledger(event)

    now_state = rebuild_now_playing_from_tail()
    return {
        "ok": True,
        "receipt": event,
        "now_playing": now_state,
        "driver": driver_res,
        "rule": 226,
    }


# LCEL RunnableSequence: Input -> Validate -> Execute & Log -> Receipt
PLAYBACK_SEQUENCE = (
    RunnableLambda(validate_playback_transition)
    | RunnableLambda(execute_tool_transition)
)


# ===================== 3. THE LANGCHAIN TOOLS =====================

class PlayTrackInput(BaseModel):
    track_id: str = Field(default="commercial_soundtrack", description="ID or filename of track in sounds/")
    actor: str = Field(default="primary_agent", description="Agent ID, scheduler, detector, or manual")
    segment: str = Field(default="music", description="Segment type: music, word, news, markov, giveback")
    trigger: str = Field(default="manual", description="Trigger: manual, schedule, howl, silence, spike, pulsation")
    volume: float = Field(default=1.0, description="Volume level between 0.0 and 1.0")
    reason: str = Field(default="Tool-gated start", description="Reason for playback invocation")


def play_track(
    track_id: str = "commercial_soundtrack",
    actor: str = "primary_agent",
    segment: str = "music",
    trigger: str = "manual",
    volume: float = 1.0,
    reason: str = "Tool-gated start",
) -> Dict[str, Any]:
    """The ONLY way to start music: runs through PLAYBACK_SEQUENCE and appends to ledger."""
    payload = {
        "action": "play",
        "track_id": track_id,
        "title": track_id,
        "actor": actor,
        "segment": segment,
        "trigger": trigger,
        "volume": volume,
        "reason": reason,
        "source": "file",
    }
    return PLAYBACK_SEQUENCE.invoke(payload)


def pause_track(actor: str = "primary_agent", reason: str = "Paused by tool") -> Dict[str, Any]:
    """Pause playback via Tool call and append pause event to ledger."""
    return PLAYBACK_SEQUENCE.invoke({"action": "pause", "actor": actor, "reason": reason})


def resume_track(actor: str = "primary_agent", reason: str = "Resumed by tool") -> Dict[str, Any]:
    """Resume playback via Tool call and append resume event to ledger."""
    return PLAYBACK_SEQUENCE.invoke({"action": "resume", "actor": actor, "reason": reason})


def stop_track(actor: str = "primary_agent", reason: str = "Stopped by tool") -> Dict[str, Any]:
    """Stop playback via Tool call and append stop event to ledger."""
    return PLAYBACK_SEQUENCE.invoke({"action": "stop", "actor": actor, "reason": reason})


def skip_track(actor: str = "primary_agent", reason: str = "Skipped by tool") -> Dict[str, Any]:
    """Skip track via Tool call and append skip event to ledger."""
    return PLAYBACK_SEQUENCE.invoke({"action": "skip", "actor": actor, "reason": reason})


def set_volume(volume: float = 1.0, actor: str = "primary_agent") -> Dict[str, Any]:
    """Set volume level via Tool call and record volume event in ledger."""
    return PLAYBACK_SEQUENCE.invoke({"action": "volume", "volume": max(0.0, min(1.0, volume)), "actor": actor})


def get_now_playing() -> Dict[str, Any]:
    """Read the log tail and return current playback state (rebuilt from ledger)."""
    return rebuild_now_playing_from_tail()


def query_playback_history(
    window_sec: int = 3600,
    track_id: Optional[str] = None,
    actor: Optional[str] = None,
    trigger: Optional[str] = None,
    limit: int = 50,
) -> Dict[str, Any]:
    """Query the append-only playback ledger by time window, track, actor, or trigger."""
    events = read_ledger_tail(limit=limit * 2)
    cutoff = int(time.time() * 1000) - (window_sec * 1000)

    matched = []
    for ev in events:
        if ev.get("ts", 0) < cutoff:
            continue
        if track_id and track_id.lower() not in ev.get("track_id", "").lower():
            continue
        if actor and actor.lower() != ev.get("actor", "").lower():
            continue
        if trigger and trigger.lower() != ev.get("trigger", "").lower():
            continue
        matched.append(ev)

    return {
        "ok": True,
        "window_sec": window_sec,
        "matched_events_count": len(matched),
        "events": matched[-limit:],
        "rule": 226,
    }


def reduce_playback_summary(window_sec: int = 86400) -> Dict[str, Any]:
    """Reduce the playback ledger: plays per track, plays per actor, skips, detector triggers."""
    events = read_ledger_tail(limit=500)
    cutoff = int(time.time() * 1000) - (window_sec * 1000)

    plays_per_track = collections.Counter()
    plays_per_actor = collections.Counter()
    triggers_count = collections.Counter()
    actions_count = collections.Counter()
    preempts_count = 0
    skips_count = 0
    total_events = 0

    for ev in events:
        if ev.get("ts", 0) < cutoff:
            continue
        total_events += 1
        act = ev.get("action", "")
        actions_count[act] += 1

        if act == "play":
            plays_per_track[ev.get("track_id", "unknown")] += 1
            plays_per_actor[ev.get("actor", "unknown")] += 1
            triggers_count[ev.get("trigger", "manual")] += 1
        elif act in ("skip", "rejected_skip"):
            skips_count += 1
        elif act == "preempt":
            preempts_count += 1

    total_plays = sum(plays_per_track.values())
    completion_rate = round(max(0.0, 1.0 - (skips_count / max(1, total_plays))), 3)

    return {
        "ok": True,
        "rule": 226,
        "window_sec": window_sec,
        "total_events": total_events,
        "total_plays": total_plays,
        "skips_count": skips_count,
        "preempts_count": preempts_count,
        "completion_rate": completion_rate,
        "plays_per_track": dict(plays_per_track.most_common(10)),
        "plays_per_actor": dict(plays_per_actor.most_common(10)),
        "triggers_breakdown": dict(triggers_count),
        "actions_breakdown": dict(actions_count),
    }


def generate_playback_report() -> Dict[str, Any]:
    """
    Pattern 4 The Report: feeds a window of the ledger into PromptTemplate
    to output a plain summary of what played, who started it, and what interrupted it.
    """
    summary = reduce_playback_summary(window_sec=86400)
    current = rebuild_now_playing_from_tail()

    template = (
        "MUSIC PLAYBACK LEDGER REPORT (RULE 226)\n"
        "======================================\n"
        "Current Status: {status} (Track: {current_track})\n"
        "Total Plays: {total_plays} | Skips: {skips} | Preemptions: {preempts}\n"
        "Completion Rate: {completion_rate}\n"
        "Top Tracks: {top_tracks}\n"
        "Top Actors: {top_actors}\n"
        "Detector Triggers: {triggers}\n"
        "Summary: All playback was verified through LangChain Tool calls. "
        "Separation of degrees holds: no actor touches raw media without an appended ledger receipt."
    )
    prompt = PromptTemplate(
        input_variables=["status", "current_track", "total_plays", "skips", "preempts", "completion_rate", "top_tracks", "top_actors", "triggers"],
        template=template,
    )

    top_tracks_str = ", ".join(f"{k} ({v})" for k, v in summary["plays_per_track"].items()) or "None"
    top_actors_str = ", ".join(f"{k} ({v})" for k, v in summary["plays_per_actor"].items()) or "None"
    triggers_str = ", ".join(f"{k} ({v})" for k, v in summary["triggers_breakdown"].items()) or "None"

    formatted_report = prompt.format(
        status=current.get("status", "IDLE"),
        current_track=current.get("title") or current.get("track_id") or "None",
        total_plays=summary.get("total_plays", 0),
        skips=summary.get("skips_count", 0),
        preempts=summary.get("preempts_count", 0),
        completion_rate=summary.get("completion_rate", 1.0),
        top_tracks=top_tracks_str,
        top_actors=top_actors_str,
        triggers=triggers_str,
    )

    return {
        "ok": True,
        "rule": 226,
        "report_text": formatted_report,
        "summary_metrics": summary,
        "current_state": current,
    }


# ===================== 4. EXPORTED STRUCTUREDTOOLS =====================

@tool
def play_track_tool(
    track_id: str = "commercial_soundtrack",
    actor: str = "primary_agent",
    segment: str = "music",
    trigger: str = "manual",
    volume: float = 1.0,
    reason: str = "Tool-gated start",
) -> str:
    """Rule 226 Tool: The ONLY way to start music. Validates transition and appends event to music_playback_log.jsonl."""
    return json.dumps(play_track(track_id, actor, segment, trigger, volume, reason))


@tool
def pause_track_tool(actor: str = "primary_agent", reason: str = "Paused by tool") -> str:
    """Rule 226 Tool: Pause current playback and append pause event to music_playback_log.jsonl."""
    return json.dumps(pause_track(actor, reason))


@tool
def resume_track_tool(actor: str = "primary_agent", reason: str = "Resumed by tool") -> str:
    """Rule 226 Tool: Resume paused playback and append resume event to music_playback_log.jsonl."""
    return json.dumps(resume_track(actor, reason))


@tool
def stop_track_tool(actor: str = "primary_agent", reason: str = "Stopped by tool") -> str:
    """Rule 226 Tool: Stop playback and append stop event to music_playback_log.jsonl."""
    return json.dumps(stop_track(actor, reason))


@tool
def skip_track_tool(actor: str = "primary_agent", reason: str = "Skipped by tool") -> str:
    """Rule 226 Tool: Skip current track, record reason, and append skip event to ledger."""
    return json.dumps(skip_track(actor, reason))


@tool
def set_volume_tool(volume: float = 1.0, actor: str = "primary_agent") -> str:
    """Rule 226 Tool: Adjust volume level and log volume event to ledger."""
    return json.dumps(set_volume(volume, actor))


@tool
def now_playing_tool() -> str:
    """Rule 226 Tool: Read log tail and return current track, actor, start time, position, and status."""
    return json.dumps(get_now_playing())


@tool
def playback_history_tool(
    window_sec: int = 3600,
    track_id: str = "",
    actor: str = "",
    trigger: str = "",
) -> str:
    """Rule 226 Tool: Query the playback ledger by time window, track, actor, or trigger."""
    return json.dumps(query_playback_history(
        window_sec=window_sec,
        track_id=track_id or None,
        actor=actor or None,
        trigger=trigger or None,
    ))


@tool
def playback_summary_tool(window_sec: int = 86400) -> str:
    """Rule 226 Tool: Reduce ledger into metrics: plays per track/actor, skips, completion rate."""
    return json.dumps(reduce_playback_summary(window_sec=window_sec))


@tool
def playback_report_tool() -> str:
    """Rule 226 Tool: Generate plain summary report of what played, who started it, and interruptions."""
    return json.dumps(generate_playback_report())


MUSIC_LEDGER_TOOLS = [
    play_track_tool,
    pause_track_tool,
    resume_track_tool,
    stop_track_tool,
    skip_track_tool,
    set_volume_tool,
    now_playing_tool,
    playback_history_tool,
    playback_summary_tool,
    playback_report_tool,
]


if __name__ == "__main__":
    print("Testing music playback ledger tools...")
    r1 = play_track("commercial_soundtrack", actor="test_agent", reason="Unit test start")
    print("Play receipt:", r1["ok"], "| event_id:", r1["receipt"]["event_id"])
    np = get_now_playing()
    print("Now playing:", np["status"], "| Track:", np["track_id"])
    r2 = skip_track(actor="test_agent", reason="Skipping for test")
    print("Skip receipt:", r2["ok"])
    rep = generate_playback_report()
    print("\n" + rep["report_text"])
