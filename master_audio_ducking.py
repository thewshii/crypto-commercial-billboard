"""
master_audio_ducking.py - LangGraph Agent State Machine & Master Audio Ducking Engine.

Rule 228: The Master Voice, Audio Ducking, and the LangGraph State Machine.
Provides automated audio ducking so when the master speaks into the room,
background music, sound FX, and other agent audio automatically lower to a
configured ducked volume (default 0.18 / -15dB), and smoothly restore to full volume
(1.0) when the master finishes.
Choreographed via a LangGraph StateGraph with explicit conditional edges and trace logging.
"""

import os
import sys
import json
import time
import uuid
import threading
from typing import Dict, Any, List, Optional, Tuple, TypedDict
from contextlib import contextmanager

from pydantic import BaseModel, Field
from langchain_core.tools import StructuredTool

# LangGraph state machine components
try:
    from langgraph.graph import StateGraph, START, END
    LANGGRAPH_AVAILABLE = True
except ImportError:
    LANGGRAPH_AVAILABLE = False

import music_playback_tools
import langsmith_engine_tools

# ============================================================================
# 1. THREAD-SAFE MASTER DUCKING STATE MANAGER
# ============================================================================

_LOCK = threading.RLock()

_DUCKING_STATE: Dict[str, Any] = {
    "is_master_talking": False,
    "current_volume": 1.0,
    "duck_level": 0.18,          # Attenuated volume when master speaks
    "normal_level": 1.0,         # Standard playback volume
    "master_source": "host",     # e.g., 'host', 'microphone', 'master_tts', 'primary_agent'
    "attack_ms": 120,            # Quick volume drop ramp
    "release_ms": 650,           # Smooth return ramp
    "last_talk_start_ms": 0,
    "last_talk_stop_ms": 0,
    "talk_count": 0,
    "history": [],
    "rule": 228,
}


def get_ducking_state() -> Dict[str, Any]:
    """Retrieve live master voice ducking telemetry."""
    with _LOCK:
        return {
            "is_master_talking": _DUCKING_STATE["is_master_talking"],
            "current_volume": round(_DUCKING_STATE["current_volume"], 3),
            "duck_level": _DUCKING_STATE["duck_level"],
            "normal_level": _DUCKING_STATE["normal_level"],
            "master_source": _DUCKING_STATE["master_source"],
            "attack_ms": _DUCKING_STATE["attack_ms"],
            "release_ms": _DUCKING_STATE["release_ms"],
            "last_talk_start_ms": _DUCKING_STATE["last_talk_start_ms"],
            "last_talk_stop_ms": _DUCKING_STATE["last_talk_stop_ms"],
            "talk_count": _DUCKING_STATE["talk_count"],
            "rule": 228,
            "ts_ms": int(time.time() * 1000),
        }


def set_ducking_level(duck_level: float) -> Dict[str, Any]:
    """Configure the target ducked volume (0.0 to 1.0)."""
    with _LOCK:
        clamped = max(0.0, min(1.0, float(duck_level)))
        _DUCKING_STATE["duck_level"] = clamped
        if _DUCKING_STATE["is_master_talking"]:
            _DUCKING_STATE["current_volume"] = clamped
            music_playback_tools.set_volume(clamped, actor="master_ducking")
    return get_ducking_state()


def start_master_talk(
    master_source: str = "host",
    duck_level: Optional[float] = None,
    reason: str = "Master voice active"
) -> Dict[str, Any]:
    """
    Start master speech session:
    1. Sets is_master_talking = True
    2. Ducks background music/sounds down to duck_level (default 0.18)
    3. Records duck event in music playback ledger (Rule 226)
    4. Records LangSmith trace (Rule 227)
    """
    with _LOCK:
        target_duck = float(duck_level) if duck_level is not None else _DUCKING_STATE["duck_level"]
        target_duck = max(0.0, min(1.0, target_duck))
        _DUCKING_STATE["duck_level"] = target_duck
        _DUCKING_STATE["is_master_talking"] = True
        _DUCKING_STATE["current_volume"] = target_duck
        _DUCKING_STATE["master_source"] = master_source
        _DUCKING_STATE["last_talk_start_ms"] = int(time.time() * 1000)
        _DUCKING_STATE["talk_count"] += 1

        # Append to event history (max 32)
        history_entry = {
            "action": "duck",
            "source": master_source,
            "volume": target_duck,
            "ts": _DUCKING_STATE["last_talk_start_ms"],
            "reason": reason,
        }
        _DUCKING_STATE["history"].append(history_entry)
        if len(_DUCKING_STATE["history"]) > 32:
            _DUCKING_STATE["history"] = _DUCKING_STATE["history"][-32:]

    # Tool-gated playback ledger record (Rule 226)
    try:
        music_playback_tools.PLAYBACK_SEQUENCE.invoke({
            "action": "duck",
            "actor": f"master:{master_source}",
            "volume": target_duck,
            "reason": reason,
            "segment": "master_voice",
            "trigger": "master_talkover",
        })
    except Exception as e:
        sys.stderr.write(f"[MASTER DUCKING] Playback ledger sync warning: {e}\n")

    # Record trace in LangSmith
    langsmith_engine_tools.record_trace(
        name="master_audio_ducking_start",
        run_type="tool",
        inputs={"master_source": master_source, "duck_level": target_duck, "reason": reason},
        outputs={"is_master_talking": True, "attenuated_volume": target_duck},
        degree=1,
        project_name="crypto-agent"
    )

    return get_ducking_state()


def stop_master_talk(reason: str = "Master voice idle") -> Dict[str, Any]:
    """
    Stop master speech session:
    1. Sets is_master_talking = False
    2. Restores background sounds to normal volume (1.0)
    3. Records unduck event in music playback ledger (Rule 226)
    4. Records LangSmith trace (Rule 227)
    """
    with _LOCK:
        normal = _DUCKING_STATE["normal_level"]
        _DUCKING_STATE["is_master_talking"] = False
        _DUCKING_STATE["current_volume"] = normal
        _DUCKING_STATE["last_talk_stop_ms"] = int(time.time() * 1000)

        history_entry = {
            "action": "unduck",
            "source": _DUCKING_STATE["master_source"],
            "volume": normal,
            "ts": _DUCKING_STATE["last_talk_stop_ms"],
            "reason": reason,
        }
        _DUCKING_STATE["history"].append(history_entry)
        if len(_DUCKING_STATE["history"]) > 32:
            _DUCKING_STATE["history"] = _DUCKING_STATE["history"][-32:]

    # Tool-gated playback ledger record (Rule 226)
    try:
        music_playback_tools.PLAYBACK_SEQUENCE.invoke({
            "action": "unduck",
            "actor": "master:system",
            "volume": normal,
            "reason": reason,
            "segment": "master_voice",
            "trigger": "master_talkover",
        })
    except Exception as e:
        sys.stderr.write(f"[MASTER DUCKING] Playback ledger restore warning: {e}\n")

    # Record trace in LangSmith
    langsmith_engine_tools.record_trace(
        name="master_audio_ducking_stop",
        run_type="tool",
        inputs={"reason": reason},
        outputs={"is_master_talking": False, "restored_volume": normal},
        degree=1,
        project_name="crypto-agent"
    )

    return get_ducking_state()


def toggle_master_talk(master_source: str = "host") -> Dict[str, Any]:
    """Toggle master talking state."""
    with _LOCK:
        active = _DUCKING_STATE["is_master_talking"]
    if active:
        return stop_master_talk(reason="Toggled off by operator")
    else:
        return start_master_talk(master_source=master_source, reason="Toggled on by operator")


@contextmanager
def master_talk_context(master_source: str = "host", duck_level: Optional[float] = None, reason: str = "Context speech"):
    """Context manager for scoping master speech with automatic ducking and restoration."""
    start_master_talk(master_source=master_source, duck_level=duck_level, reason=reason)
    try:
        yield
    finally:
        stop_master_talk(reason=f"Finished: {reason}")


# ============================================================================
# 2. LANGGRAPH STATE MACHINE WORKFLOW (RULE 228)
# ============================================================================

class MasterAudioGraphState(TypedDict):
    user_input: str
    speaker: str                 # "master", "agent", "guest", "background"
    is_master: bool
    is_master_talking: bool
    current_volume: float
    duck_level: float
    normal_volume: float
    speech_text: str
    tool_name: Optional[str]
    tool_args: Optional[Dict[str, Any]]
    tool_result: Optional[Any]
    response: str
    stage: str
    trace_id: str
    logs: List[str]


def _build_langgraph_workflow():
    """Construct and compile the LangGraph StateGraph for master audio ducking."""
    if not LANGGRAPH_AVAILABLE:
        return None

    builder = StateGraph(MasterAudioGraphState)

    # 1. Node: Detect Master Intent & Speaker
    def detect_speaker_node(state: MasterAudioGraphState) -> Dict[str, Any]:
        spk = state.get("speaker", "master").lower().strip()
        inp = state.get("user_input", "").lower()
        is_m = (spk in ("master", "host", "operator", "primary_agent") or
                "master:" in inp or "host speaks" in inp or "talkover" in inp)
        logs = list(state.get("logs", []))
        logs.append(f"Speaker detected: '{spk}', is_master={is_m}")
        return {
            "speaker": spk,
            "is_master": is_m,
            "stage": "detected",
            "logs": logs,
        }

    # 2. Node: Duck Audio Node (Lowers volume of other sounds)
    def duck_audio_node(state: MasterAudioGraphState) -> Dict[str, Any]:
        d_lvl = state.get("duck_level", 0.18)
        duck_res = start_master_talk(
            master_source=state.get("speaker", "host"),
            duck_level=d_lvl,
            reason="LangGraph Master Voice Activated"
        )
        logs = list(state.get("logs", []))
        logs.append(f"Master ducking engaged: volume lowered to {duck_res['current_volume']}")
        return {
            "is_master_talking": True,
            "current_volume": duck_res["current_volume"],
            "stage": "ducked",
            "logs": logs,
        }

    # 3. Node: Standard Pass-Through Node (Non-master speech)
    def standard_pass_through_node(state: MasterAudioGraphState) -> Dict[str, Any]:
        logs = list(state.get("logs", []))
        logs.append("Standard utterance: audio remains unattenuated.")
        return {
            "is_master_talking": False,
            "stage": "pass_through",
            "logs": logs,
        }

    # 4. Node: Agent Work / Tool Execution Node
    def agent_execution_node(state: MasterAudioGraphState) -> Dict[str, Any]:
        logs = list(state.get("logs", []))
        t_name = state.get("tool_name")
        t_args = state.get("tool_args") or {}
        res = None

        if t_name:
            logs.append(f"Executing tool '{t_name}' under state stage '{state.get('stage')}'")
            import langchain_separation
            res = langchain_separation.execute_langchain_tool(t_name, t_args)
        else:
            res = {"status": "ok", "delivered_speech": state.get("user_input")}

        resp = f"[VOICE: {state.get('speaker', 'master').upper()}] {state.get('user_input')}"
        logs.append("Speech delivery completed.")
        return {
            "tool_result": res,
            "response": resp,
            "stage": "executed",
            "logs": logs,
        }

    # 5. Node: Unduck Audio Node (Restores background sounds)
    def unduck_audio_node(state: MasterAudioGraphState) -> Dict[str, Any]:
        unduck_res = stop_master_talk(reason="LangGraph Master Voice Concluded")
        logs = list(state.get("logs", []))
        logs.append(f"Master ducking released: volume restored to {unduck_res['current_volume']}")
        return {
            "is_master_talking": False,
            "current_volume": unduck_res["current_volume"],
            "stage": "completed",
            "logs": logs,
        }

    # Add Nodes
    builder.add_node("detect_speaker", detect_speaker_node)
    builder.add_node("duck_audio", duck_audio_node)
    builder.add_node("standard_pass_through", standard_pass_through_node)
    builder.add_node("agent_execution", agent_execution_node)
    builder.add_node("unduck_audio", unduck_audio_node)

    # Edge from START to detector
    builder.add_edge(START, "detect_speaker")

    # Conditional router based on is_master
    def route_speaker(state: MasterAudioGraphState) -> str:
        return "duck_audio" if state.get("is_master") else "standard_pass_through"

    builder.add_conditional_edges(
        "detect_speaker",
        route_speaker,
        {
            "duck_audio": "duck_audio",
            "standard_pass_through": "standard_pass_through",
        }
    )

    # Path A: Master Voice
    builder.add_edge("duck_audio", "agent_execution")
    builder.add_edge("agent_execution", "unduck_audio")
    builder.add_edge("unduck_audio", END)

    # Path B: Standard Non-Master Voice
    builder.add_edge("standard_pass_through", "agent_execution")

    return builder.compile()


# Compiled Singleton Graph
MASTER_AUDIO_GRAPH = _build_langgraph_workflow()


def run_langgraph_master_talk(
    user_input: str,
    speaker: str = "master",
    duck_level: float = 0.18,
    tool_name: Optional[str] = None,
    tool_args: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Execute the full LangGraph state graph workflow for master speech and ducking."""
    initial_state: MasterAudioGraphState = {
        "user_input": user_input,
        "speaker": speaker,
        "is_master": False,
        "is_master_talking": False,
        "current_volume": 1.0,
        "duck_level": duck_level,
        "normal_volume": 1.0,
        "speech_text": user_input,
        "tool_name": tool_name,
        "tool_args": tool_args or {},
        "tool_result": None,
        "response": "",
        "stage": "initialized",
        "trace_id": str(uuid.uuid4()),
        "logs": [],
    }

    if MASTER_AUDIO_GRAPH:
        final_state = MASTER_AUDIO_GRAPH.invoke(initial_state)
    else:
        # Fallback if langgraph is not installed
        if speaker.lower() in ("master", "host"):
            start_master_talk(master_source=speaker, duck_level=duck_level)
            time.sleep(0.05)
            stop_master_talk()
        final_state = dict(initial_state)
        final_state["response"] = f"Processed without LangGraph: {user_input}"
        final_state["stage"] = "fallback"

    # Log to LangSmith
    langsmith_engine_tools.record_trace(
        name="langgraph_master_talk_workflow",
        run_type="chain",
        inputs={"user_input": user_input, "speaker": speaker, "duck_level": duck_level},
        outputs=final_state,
        degree=1,
        project_name="crypto-agent"
    )

    return final_state


# ============================================================================
# 3. LANGCHAIN STRUCTURED TOOLS (RULE 228)
# ============================================================================

class MasterTalkStartArgs(BaseModel):
    master_source: str = Field("host", description="Source identifier: host, microphone, master_tts, or operator")
    duck_level: float = Field(0.18, description="Target ducked volume level between 0.0 and 1.0 (default 0.18)")
    reason: str = Field("Master voice speaking", description="Reason for ducking background audio")


def _run_master_talk_start(master_source: str = "host", duck_level: float = 0.18, reason: str = "Master voice speaking") -> str:
    res = start_master_talk(master_source=master_source, duck_level=duck_level, reason=reason)
    return json.dumps(res, indent=2)


master_talk_start_tool = StructuredTool(
    name="master_talk_start_tool",
    description="Engage master voice talkover: automatically lower the volume of background music and sounds to duck_level (Rule 228).",
    args_schema=MasterTalkStartArgs,
    func=_run_master_talk_start
)


class MasterTalkStopArgs(BaseModel):
    reason: str = Field("Master voice concluded", description="Reason for restoring volume")


def _run_master_talk_stop(reason: str = "Master voice concluded") -> str:
    res = stop_master_talk(reason=reason)
    return json.dumps(res, indent=2)


master_talk_stop_tool = StructuredTool(
    name="master_talk_stop_tool",
    description="Disengage master voice talkover: smoothly restore background music and other sounds to normal volume 1.0 (Rule 228).",
    args_schema=MasterTalkStopArgs,
    func=_run_master_talk_stop
)


class MasterSetDuckLevelArgs(BaseModel):
    duck_level: float = Field(0.18, description="Target volume level during master speech (0.0 to 1.0)")


def _run_master_set_duck_level(duck_level: float = 0.18) -> str:
    res = set_ducking_level(duck_level)
    return json.dumps(res, indent=2)


master_set_ducking_level_tool = StructuredTool(
    name="master_set_ducking_level_tool",
    description="Configure the master voice audio ducking level (attenuation target) for background sounds (Rule 228).",
    args_schema=MasterSetDuckLevelArgs,
    func=_run_master_set_duck_level
)


class MasterDuckingStatusArgs(BaseModel):
    pass


def _run_master_ducking_status() -> str:
    res = get_ducking_state()
    return json.dumps(res, indent=2)


master_ducking_status_tool = StructuredTool(
    name="master_ducking_status_tool",
    description="Inspect current master voice talkover state, effective audio volume, and ducking parameters (Rule 228).",
    args_schema=MasterDuckingStatusArgs,
    func=_run_master_ducking_status
)


class RunLangGraphWorkflowArgs(BaseModel):
    user_input: str = Field(..., description="Spoken utterance or command to run through LangGraph")
    speaker: str = Field("master", description="Speaker identity: master, host, agent, or guest")
    duck_level: float = Field(0.18, description="Attenuated volume level if master speaks")
    tool_name: Optional[str] = Field(None, description="Optional LangChain tool name to execute while ducked")


def _run_langgraph_workflow_tool(
    user_input: str,
    speaker: str = "master",
    duck_level: float = 0.18,
    tool_name: Optional[str] = None
) -> str:
    res = run_langgraph_master_talk(user_input=user_input, speaker=speaker, duck_level=duck_level, tool_name=tool_name)
    return json.dumps(res, indent=2)


run_langgraph_master_workflow_tool = StructuredTool(
    name="run_langgraph_master_workflow_tool",
    description="Execute an utterance through the LangGraph StateGraph state machine with automatic speaker detection and audio ducking (Rule 228).",
    args_schema=RunLangGraphWorkflowArgs,
    func=_run_langgraph_workflow_tool
)


MASTER_DUCKING_TOOLS = [
    master_talk_start_tool,
    master_talk_stop_tool,
    master_set_ducking_level_tool,
    master_ducking_status_tool,
    run_langgraph_master_workflow_tool,
]


if __name__ == "__main__":
    print("[MASTER AUDIO DUCKING] State:", get_ducking_state())
    print("[MASTER AUDIO DUCKING] Starting talkover (duck)...")
    s1 = start_master_talk("host", duck_level=0.15)
    print("Ducked State:", s1)
    print("[MASTER AUDIO DUCKING] Running LangGraph workflow...")
    g_res = run_langgraph_master_talk("This is the master host addressing the room.", speaker="master")
    print("LangGraph result:", g_res["response"])
    print("[MASTER AUDIO DUCKING] Stopping talkover (unduck)...")
    s2 = stop_master_talk()
    print("Restored State:", s2)
