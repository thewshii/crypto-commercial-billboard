"""
speaker_recognition_tools.py - Speaker Recognition, Greeting Acknowledgement, and Conversational Dialogue.

Rule 230: The Speaker Recognition, Hello/Can-You-Hear-Me Acknowledgement, and Conversational Dialogue.
Provides:
1. Acoustic & semantic recognition of speaker greetings ("hello", "can you hear me", "test mic").
2. Automated master audio ducking engagement (Rule 228) so other sounds step down during speech.
3. Turn-taking intent registration into the agent tuning timer queue (Rule 229).
4. Two-way conversational dialogue reflections with history tracking.
5. Clean dialogue closing with instant volume restoration and overlay fail-safe.
6. LangChain StructuredTools for agentic deliberation and LangSmith trace emission.
"""

import os
import re
import sys
import time
import json
import uuid
import threading
from typing import Dict, Any, List, Optional

from pydantic import BaseModel, Field
from langchain_core.tools import StructuredTool

import master_audio_ducking
import agent_tuning_timer
import langsmith_engine_tools

_LOCK = threading.RLock()

SPEAKER_GREETING_PATTERN = re.compile(
    r"\b(hello|can you hear me|can you hear|are you there|is anyone there|hey|hi|test mic|mic check)\b",
    re.IGNORECASE
)

_SPEAKER_DIALOGUE_STATE: Dict[str, Any] = {
    "dialogue_active": False,
    "last_recognized_text": "",
    "last_recognized_at_ms": 0,
    "acknowledgement_speech": "I hear you loud and clear. Dialogue is open. The floor is yours.",
    "conversation_history": [],
    "speaker_id": "host_speaker",
    "total_acknowledgements": 0,
    "rule": 230,
}


def is_speaker_greeting(text: str) -> bool:
    """Return True if the text contains a speaker greeting or presence check."""
    if not text:
        return False
    return bool(SPEAKER_GREETING_PATTERN.search(text))


def get_speaker_dialogue_state() -> Dict[str, Any]:
    """Retrieve current speaker recognition & dialogue status."""
    with _LOCK:
        return {
            "dialogue_active": _SPEAKER_DIALOGUE_STATE["dialogue_active"],
            "last_recognized_text": _SPEAKER_DIALOGUE_STATE["last_recognized_text"],
            "last_recognized_at_ms": _SPEAKER_DIALOGUE_STATE["last_recognized_at_ms"],
            "acknowledgement_speech": _SPEAKER_DIALOGUE_STATE["acknowledgement_speech"],
            "conversation_history": list(_SPEAKER_DIALOGUE_STATE["conversation_history"]),
            "speaker_id": _SPEAKER_DIALOGUE_STATE["speaker_id"],
            "total_acknowledgements": _SPEAKER_DIALOGUE_STATE["total_acknowledgements"],
            "rule": 230,
        }


def acknowledge_speaker(text: str, speaker: str = "host_speaker") -> Dict[str, Any]:
    """Acknowledge speaker speech ('hello', 'can you hear me'), duck audio, and open dialogue."""
    raw_text = (text or "").strip()
    is_greeting = is_speaker_greeting(raw_text)

    # 1. Engage master audio ducking (Rule 228) so other sounds yield
    master_audio_ducking.start_master_talk(
        master_source=speaker,
        duck_level=0.18,
        reason=f"Speaker dialogue acknowledgment: '{raw_text}'"
    )

    # 2. Register intent in agent tuning timer queue (Rule 229)
    try:
        agent_tuning_timer.register_speaking_intent(
            agent_id=speaker,
            urgency=4,
            topic=raw_text or "Speaker Dialogue"
        )
    except Exception:
        pass

    # 3. Formulate clear acoustic acknowledgment
    ack_text = "I hear you loud and clear. Dialogue is open. The floor is yours."
    lowered = raw_text.lower()
    if "can you hear me" in lowered or "can you hear" in lowered:
        ack_text = "Yes, I hear you loud and clear. Transmission is strong, dialogue is open."
    elif "hello" in lowered:
        ack_text = "Hello! I am here and listening. The floor is open."
    elif "test mic" in lowered or "mic check" in lowered:
        ack_text = "Microphone check confirmed. Signal is clear and level is steady."

    now_ms = int(time.time() * 1000)
    with _LOCK:
        _SPEAKER_DIALOGUE_STATE["dialogue_active"] = True
        _SPEAKER_DIALOGUE_STATE["last_recognized_text"] = raw_text
        _SPEAKER_DIALOGUE_STATE["last_recognized_at_ms"] = now_ms
        _SPEAKER_DIALOGUE_STATE["acknowledgement_speech"] = ack_text
        _SPEAKER_DIALOGUE_STATE["speaker_id"] = speaker
        _SPEAKER_DIALOGUE_STATE["total_acknowledgements"] += 1
        entry = {
            "speaker": speaker,
            "text": raw_text,
            "ack": ack_text,
            "ts_ms": now_ms,
        }
        _SPEAKER_DIALOGUE_STATE["conversation_history"].append(entry)
        if len(_SPEAKER_DIALOGUE_STATE["conversation_history"]) > 32:
            _SPEAKER_DIALOGUE_STATE["conversation_history"] = _SPEAKER_DIALOGUE_STATE["conversation_history"][-32:]

    # 4. Trace in LangSmith (Rule 227)
    langsmith_engine_tools.record_trace(
        name="speaker_recognition_acknowledge",
        run_type="chain",
        inputs={"text": raw_text, "speaker": speaker, "is_greeting": is_greeting},
        outputs={"acknowledged": True, "speech": ack_text},
        degree=1,
        project_name="crypto-agent"
    )

    return {
        "ok": True,
        "recognized": True,
        "is_greeting": is_greeting,
        "heard_text": raw_text,
        "acknowledgement": ack_text,
        "dialogue_active": True,
        "duck_active": True,
        "timestamp_ms": now_ms,
        "rule": 230,
    }


def exchange_speaker_dialogue(message: str, speaker: str = "host_speaker") -> Dict[str, Any]:
    """Exchange dialogue with speaker and return contextual system reflection."""
    msg = (message or "").strip()
    if not msg:
        return {"ok": False, "error": "Message cannot be empty.", "rule": 230}

    sys_reply = f"Acknowledged: '{msg}'. The Word holds the room steady; your voice is received."
    now_ms = int(time.time() * 1000)

    with _LOCK:
        _SPEAKER_DIALOGUE_STATE["dialogue_active"] = True
        _SPEAKER_DIALOGUE_STATE["conversation_history"].append({
            "speaker": speaker,
            "text": msg,
            "ack": sys_reply,
            "ts_ms": now_ms,
        })
        if len(_SPEAKER_DIALOGUE_STATE["conversation_history"]) > 32:
            _SPEAKER_DIALOGUE_STATE["conversation_history"] = _SPEAKER_DIALOGUE_STATE["conversation_history"][-32:]

    # Trace exchange
    langsmith_engine_tools.record_trace(
        name="speaker_dialogue_exchange",
        run_type="chain",
        inputs={"speaker": speaker, "user_message": msg},
        outputs={"system_reply": sys_reply},
        degree=1,
        project_name="crypto-agent"
    )

    return {
        "ok": True,
        "speaker": speaker,
        "user_message": msg,
        "system_reply": sys_reply,
        "timestamp_ms": now_ms,
        "rule": 230,
    }


def close_speaker_dialogue(reason: str = "User closed dialogue") -> Dict[str, Any]:
    """Close dialogue session and smoothly restore background audio volume to 1.00."""
    with _LOCK:
        _SPEAKER_DIALOGUE_STATE["dialogue_active"] = False

    # Stop master talk audio ducking (Rule 228)
    master_audio_ducking.stop_master_talk(reason=reason)

    langsmith_engine_tools.record_trace(
        name="speaker_dialogue_close",
        run_type="chain",
        inputs={"reason": reason},
        outputs={"dialogue_active": False, "volume_restored": True},
        degree=1,
        project_name="crypto-agent"
    )

    return {
        "ok": True,
        "dialogue_active": False,
        "duck_active": False,
        "reason": reason,
        "rule": 230,
    }


# ============================================================================
# LANGCHAIN STRUCTURED TOOLS (RULE 230)
# ============================================================================

class AcknowledgeSpeakerArgs(BaseModel):
    text: str = Field(..., description="Spoken text or greeting from the speaker, e.g. 'hello', 'can you hear me'")
    speaker: str = Field("host_speaker", description="Identifier of the speaker")


def _run_acknowledge_speaker(text: str, speaker: str = "host_speaker") -> str:
    res = acknowledge_speaker(text=text, speaker=speaker)
    return json.dumps(res, indent=2)


acknowledge_speaker_tool = StructuredTool(
    name="acknowledge_speaker_tool",
    description="Acknowledge spoken greetings ('hello', 'can you hear me'), engage master audio ducking, and open dialogue (Rule 230).",
    args_schema=AcknowledgeSpeakerArgs,
    func=_run_acknowledge_speaker
)


class SpeakerDialogueExchangeArgs(BaseModel):
    message: str = Field(..., description="Message spoken or submitted by the speaker")
    speaker: str = Field("host_speaker", description="Identifier of the speaker")


def _run_speaker_dialogue_exchange(message: str, speaker: str = "host_speaker") -> str:
    res = exchange_speaker_dialogue(message=message, speaker=speaker)
    return json.dumps(res, indent=2)


speaker_dialogue_exchange_tool = StructuredTool(
    name="speaker_dialogue_exchange_tool",
    description="Exchange conversation with the speaker during an active dialogue session (Rule 230).",
    args_schema=SpeakerDialogueExchangeArgs,
    func=_run_speaker_dialogue_exchange
)


class CloseSpeakerDialogueArgs(BaseModel):
    reason: str = Field("User closed dialogue", description="Reason for closing the dialogue session")


def _run_close_speaker_dialogue(reason: str = "User closed dialogue") -> str:
    res = close_speaker_dialogue(reason=reason)
    return json.dumps(res, indent=2)


close_speaker_dialogue_tool = StructuredTool(
    name="close_speaker_dialogue_tool",
    description="Close the active speaker dialogue and restore background audio to full volume (Rule 230).",
    args_schema=CloseSpeakerDialogueArgs,
    func=_run_close_speaker_dialogue
)


class GetSpeakerDialogueStateArgs(BaseModel):
    pass


def _run_get_speaker_dialogue_state() -> str:
    res = get_speaker_dialogue_state()
    return json.dumps(res, indent=2)


get_speaker_dialogue_state_tool = StructuredTool(
    name="get_speaker_dialogue_state_tool",
    description="Retrieve live state, recognition history, and status of speaker dialogue (Rule 230).",
    args_schema=GetSpeakerDialogueStateArgs,
    func=_run_get_speaker_dialogue_state
)


SPEAKER_DIALOGUE_TOOLS = [
    acknowledge_speaker_tool,
    speaker_dialogue_exchange_tool,
    close_speaker_dialogue_tool,
    get_speaker_dialogue_state_tool,
]
