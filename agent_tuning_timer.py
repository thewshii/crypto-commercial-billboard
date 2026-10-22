"""
agent_tuning_timer.py - Tuning Timer System, Turn-Taking Intent, and Ranked Speaker Consensus.

Rule 229: The Tuning Timer System, Turn-Taking Intent, and Ranked Speaker Consensus.
Allows agents to:
1. Know exactly when it is their time to talk via a synchronized slot countdown timer.
2. Signal intent when they want to talk next ("hand-raising" queue).
3. Vote democratically on who should talk most to least via Borda count ranked-choice voting.
4. Advance smoothly between turns while honoring master audio ducking and separation degrees.
"""

import json
import os
import sys
import time
import uuid
import threading
from typing import Dict, Any, List, Optional, Tuple

from pydantic import BaseModel, Field
from langchain_core.tools import StructuredTool

import langsmith_engine_tools
import master_audio_ducking

# ============================================================================
# 1. TUNING TIMER & VOTING STATE
# ============================================================================

_LOCK = threading.RLock()

_DEFAULT_AGENTS = [
    "primary_agent",
    "motherly_voice",
    "letta_memgpt",
    "tension_sentinel",
    "adam_voice",
    "langchain_orchestrator",
    "research_agent_x",
    "degree3_auditor",
]

_TIMER_STATE: Dict[str, Any] = {
    "timer_active": True,
    "slot_duration_sec": 30.0,
    "slot_started_at_ms": int(time.time() * 1000),
    "current_speaker": "primary_agent",
    "tuning_frequency_hz": 432.0,
    "tempo_bpm": 72,
    "speaking_intent_queue": [],      # List of {agent_id, urgency (1..5), topic, requested_at_ms}
    "ballot_box": {},                  # voter_agent_id -> [candidate1, candidate2, ...] (most to least)
    "consensus_ranking": [],           # List of {rank, agent_id, borda_points, votes_count}
    "turn_history": [],                # Completed speaking slots
    "total_turns_completed": 0,
    "rule": 229,
}


def _now_ms() -> int:
    return int(time.time() * 1000)


def compute_consensus_ranking() -> List[Dict[str, Any]]:
    """Tally ranked-choice votes (most to least) using Borda count.
    If N candidates, 1st place gets N points, 2nd gets N-1, etc."""
    with _LOCK:
        ballots = dict(_TIMER_STATE["ballot_box"])
        intents = {item["agent_id"]: item for item in _TIMER_STATE["speaking_intent_queue"]}

        # Collect all eligible candidates
        all_candidates = set(_DEFAULT_AGENTS)
        for ballot in ballots.values():
            all_candidates.update(ballot)
        for ag in intents.keys():
            all_candidates.add(ag)

        candidate_list = sorted(list(all_candidates))
        n = len(candidate_list)
        scores: Dict[str, int] = {c: 0 for c in candidate_list}
        vote_counts: Dict[str, int] = {c: 0 for c in candidate_list}

        for voter, ranking in ballots.items():
            k = len(ranking)
            for idx, candidate in enumerate(ranking):
                # Borda weight: highest for first place
                points = max(1, k - idx)
                scores[candidate] = scores.get(candidate, 0) + points
                vote_counts[candidate] = vote_counts.get(candidate, 0) + 1

        # Add intent urgency bonus (+2 points per urgency level above 1)
        for ag, item in intents.items():
            urgency = item.get("urgency", 3)
            scores[ag] = scores.get(ag, 0) + (urgency * 2)

        # Sort by total points descending, then by vote count
        sorted_candidates = sorted(
            candidate_list,
            key=lambda c: (scores.get(c, 0), vote_counts.get(c, 0), c == _TIMER_STATE["current_speaker"]),
            reverse=True
        )

        ranking_results = []
        for rank_idx, cand in enumerate(sorted_candidates, start=1):
            ranking_results.append({
                "rank": rank_idx,
                "agent_id": cand,
                "borda_points": scores.get(cand, 0),
                "votes_received": vote_counts.get(cand, 0),
                "has_intent_queued": cand in intents,
                "urgency": intents.get(cand, {}).get("urgency", 0),
                "is_current": cand == _TIMER_STATE["current_speaker"],
            })

        _TIMER_STATE["consensus_ranking"] = ranking_results
        return ranking_results


def get_tuning_timer_status() -> Dict[str, Any]:
    """Return live tuning timer status, slot countdown, intent queue, and consensus speaker ranking."""
    with _LOCK:
        now = _now_ms()
        elapsed_sec = max(0.0, (now - _TIMER_STATE["slot_started_at_ms"]) / 1000.0)
        remaining_sec = max(0.0, round(_TIMER_STATE["slot_duration_sec"] - elapsed_sec, 1))

        # Recompute consensus ranking if empty
        if not _TIMER_STATE["consensus_ranking"]:
            compute_consensus_ranking()

        # Identify who is queued to talk next
        next_speaker = None
        for r in _TIMER_STATE["consensus_ranking"]:
            if r["agent_id"] != _TIMER_STATE["current_speaker"]:
                next_speaker = r["agent_id"]
                break
        if not next_speaker and _TIMER_STATE["speaking_intent_queue"]:
            next_speaker = _TIMER_STATE["speaking_intent_queue"][0]["agent_id"]
        if not next_speaker:
            next_speaker = "motherly_voice"

        return {
            "ok": True,
            "timer_active": _TIMER_STATE["timer_active"],
            "slot_duration_sec": _TIMER_STATE["slot_duration_sec"],
            "slot_elapsed_sec": round(elapsed_sec, 1),
            "time_remaining_sec": remaining_sec,
            "is_slot_expired": remaining_sec <= 0.0,
            "current_speaker": _TIMER_STATE["current_speaker"],
            "next_scheduled_speaker": next_speaker,
            "tuning_frequency_hz": _TIMER_STATE["tuning_frequency_hz"],
            "tempo_bpm": _TIMER_STATE["tempo_bpm"],
            "speaking_intent_queue_count": len(_TIMER_STATE["speaking_intent_queue"]),
            "speaking_intent_queue": list(_TIMER_STATE["speaking_intent_queue"]),
            "consensus_ranking": list(_TIMER_STATE["consensus_ranking"]),
            "total_ballots_cast": len(_TIMER_STATE["ballot_box"]),
            "total_turns_completed": _TIMER_STATE["total_turns_completed"],
            "rule": 229,
            "timestamp_ms": now,
        }


def register_speaking_intent(
    agent_id: str,
    urgency: int = 3,
    topic: str = "general"
) -> Dict[str, Any]:
    """Register an agent's intent to speak next (hand-raising mechanism)."""
    with _LOCK:
        urgency = max(1, min(5, int(urgency)))
        # Check if already in queue
        existing = next((i for i in _TIMER_STATE["speaking_intent_queue"] if i["agent_id"] == agent_id), None)
        if existing:
            existing["urgency"] = urgency
            existing["topic"] = topic
            existing["updated_at_ms"] = _now_ms()
        else:
            _TIMER_STATE["speaking_intent_queue"].append({
                "agent_id": agent_id,
                "urgency": urgency,
                "topic": topic,
                "requested_at_ms": _now_ms(),
            })

        # Recalculate consensus order with new intent weight
        compute_consensus_ranking()

    langsmith_engine_tools.record_trace(
        name="tuning_timer_register_intent",
        run_type="tool",
        inputs={"agent_id": agent_id, "urgency": urgency, "topic": topic},
        outputs={"queued": True, "queue_length": len(_TIMER_STATE["speaking_intent_queue"])},
        degree=1,
        project_name="crypto-agent"
    )

    return get_tuning_timer_status()


def cast_speaker_ranking_vote(
    voter_agent_id: str,
    ranked_candidates: List[str],
    reason: str = "Democratic turn order voting"
) -> Dict[str, Any]:
    """Cast a ballot ordering candidates from most (index 0) to least preferred speaker."""
    with _LOCK:
        if not ranked_candidates:
            return {"ok": False, "error": "ranked_candidates list cannot be empty."}

        # Deduplicate preserving order
        seen = set()
        cleaned_ranking = []
        for c in ranked_candidates:
            c_str = str(c).strip()
            if c_str and c_str not in seen:
                seen.add(c_str)
                cleaned_ranking.append(c_str)

        _TIMER_STATE["ballot_box"][voter_agent_id] = cleaned_ranking
        ranking = compute_consensus_ranking()

    langsmith_engine_tools.record_trace(
        name="tuning_timer_cast_vote",
        run_type="tool",
        inputs={"voter": voter_agent_id, "ranked_order": cleaned_ranking, "reason": reason},
        outputs={"consensus_top_3": [r["agent_id"] for r in ranking[:3]]},
        degree=1,
        project_name="crypto-agent"
    )

    return {
        "ok": True,
        "voter_agent_id": voter_agent_id,
        "ranked_count": len(cleaned_ranking),
        "consensus_ranking": ranking,
    }


def advance_speaker_turn(
    force_agent_id: Optional[str] = None,
    reason: str = "Tuning timer slot concluded"
) -> Dict[str, Any]:
    """Advance to the next speaker based on consensus vote ranking and intent queue."""
    with _LOCK:
        prev_speaker = _TIMER_STATE["current_speaker"]
        now = _now_ms()

        # Archive finished turn
        turn_record = {
            "speaker": prev_speaker,
            "started_at_ms": _TIMER_STATE["slot_started_at_ms"],
            "ended_at_ms": now,
            "duration_sec": round((now - _TIMER_STATE["slot_started_at_ms"]) / 1000.0, 1),
            "reason": reason,
        }
        _TIMER_STATE["turn_history"].append(turn_record)
        if len(_TIMER_STATE["turn_history"]) > 32:
            _TIMER_STATE["turn_history"] = _TIMER_STATE["turn_history"][-32:]

        _TIMER_STATE["total_turns_completed"] += 1

        if force_agent_id:
            next_speaker = force_agent_id
        else:
            ranking = compute_consensus_ranking()
            candidates = [r["agent_id"] for r in ranking if r["agent_id"] != prev_speaker]
            next_speaker = candidates[0] if candidates else prev_speaker

        # Remove chosen speaker from intent queue if present
        _TIMER_STATE["speaking_intent_queue"] = [
            i for i in _TIMER_STATE["speaking_intent_queue"] if i["agent_id"] != next_speaker
        ]

        # Reset slot clock
        _TIMER_STATE["current_speaker"] = next_speaker
        _TIMER_STATE["slot_started_at_ms"] = now
        compute_consensus_ranking()

    # Audio ducking coordination: if primary/master voice takes the floor, duck background audio
    if next_speaker in ("primary_agent", "host", "master"):
        master_audio_ducking.start_master_talk(master_source=next_speaker, reason=f"Turn-taking slot: {next_speaker}")
    else:
        # If transitioning from master to another agent, release ducking
        if prev_speaker in ("primary_agent", "host", "master"):
            master_audio_ducking.stop_master_talk(reason=f"Handed floor to {next_speaker}")

    langsmith_engine_tools.record_trace(
        name="tuning_timer_advance_turn",
        run_type="tool",
        inputs={"previous_speaker": prev_speaker, "new_speaker": next_speaker, "reason": reason},
        outputs={"turn_record": turn_record},
        degree=1,
        project_name="crypto-agent"
    )

    return get_tuning_timer_status()


def simulate_multi_agent_vote(topic: str = "Harmonic room consensus") -> Dict[str, Any]:
    """Have all active network agents autonomously vote on who should speak most to least."""
    # Predefined preference profiles for different agent roles
    profiles = {
        "primary_agent": ["motherly_voice", "letta_memgpt", "tension_sentinel", "adam_voice", "research_agent_x"],
        "motherly_voice": ["primary_agent", "adam_voice", "tension_sentinel", "letta_memgpt", "langchain_orchestrator"],
        "letta_memgpt": ["primary_agent", "research_agent_x", "motherly_voice", "tension_sentinel", "degree3_auditor"],
        "tension_sentinel": ["motherly_voice", "primary_agent", "letta_memgpt", "adam_voice", "langchain_orchestrator"],
        "adam_voice": ["motherly_voice", "primary_agent", "tension_sentinel", "letta_memgpt", "degree3_auditor"],
        "langchain_orchestrator": ["primary_agent", "letta_memgpt", "motherly_voice", "research_agent_x", "adam_voice"],
        "research_agent_x": ["letta_memgpt", "primary_agent", "degree3_auditor", "motherly_voice", "tension_sentinel"],
        "degree3_auditor": ["primary_agent", "tension_sentinel", "motherly_voice", "letta_memgpt", "adam_voice"],
    }

    for voter, ballot in profiles.items():
        cast_speaker_ranking_vote(voter_agent_id=voter, ranked_candidates=ballot, reason=f"Topic: {topic}")

    return {
        "ok": True,
        "topic": topic,
        "participating_agents": list(profiles.keys()),
        "consensus_ranking": compute_consensus_ranking(),
    }


def configure_tuning_timer(
    slot_duration_sec: Optional[float] = None,
    tuning_frequency_hz: Optional[float] = None,
    tempo_bpm: Optional[int] = None
) -> Dict[str, Any]:
    """Update tuning parameters (slot length, harmonic frequency, tempo)."""
    with _LOCK:
        if slot_duration_sec is not None:
            _TIMER_STATE["slot_duration_sec"] = max(5.0, min(300.0, float(slot_duration_sec)))
        if tuning_frequency_hz is not None:
            _TIMER_STATE["tuning_frequency_hz"] = float(tuning_frequency_hz)
        if tempo_bpm is not None:
            _TIMER_STATE["tempo_bpm"] = int(tempo_bpm)
    return get_tuning_timer_status()


# ============================================================================
# 2. LANGCHAIN STRUCTURED TOOLS (RULE 229)
# ============================================================================

class GetTuningTimerStatusArgs(BaseModel):
    pass


def _run_get_tuning_timer_status() -> str:
    res = get_tuning_timer_status()
    return json.dumps(res, indent=2)


get_tuning_timer_status_tool = StructuredTool(
    name="get_tuning_timer_status_tool",
    description="Check the tuning timer countdown, current speaker turn, speaking intent queue, and consensus speaker ranking (Rule 229).",
    args_schema=GetTuningTimerStatusArgs,
    func=_run_get_tuning_timer_status
)


class RegisterSpeakingIntentArgs(BaseModel):
    agent_id: str = Field(..., description="ID of the agent requesting to talk next")
    urgency: int = Field(3, description="Urgency priority level from 1 (low) to 5 (critical)")
    topic: str = Field("general", description="Topic the agent wants to address")


def _run_register_speaking_intent(agent_id: str, urgency: int = 3, topic: str = "general") -> str:
    res = register_speaking_intent(agent_id=agent_id, urgency=urgency, topic=topic)
    return json.dumps(res, indent=2)


register_speaking_intent_tool = StructuredTool(
    name="register_speaking_intent_tool",
    description="Signal an agent's intent to talk next ('raise hand') with urgency and topic in the tuning timer system (Rule 229).",
    args_schema=RegisterSpeakingIntentArgs,
    func=_run_register_speaking_intent
)


class CastSpeakerRankingVoteArgs(BaseModel):
    voter_agent_id: str = Field(..., description="ID of the voting agent")
    ranked_candidates: List[str] = Field(..., description="Ordered list of candidate speakers from most (index 0) to least preferred")
    reason: str = Field("Consensus vote", description="Reason for the ballot ranking")


def _run_cast_speaker_ranking_vote(voter_agent_id: str, ranked_candidates: List[str], reason: str = "Consensus vote") -> str:
    res = cast_speaker_ranking_vote(voter_agent_id=voter_agent_id, ranked_candidates=ranked_candidates, reason=reason)
    return json.dumps(res, indent=2)


cast_speaker_ranking_vote_tool = StructuredTool(
    name="cast_speaker_ranking_vote_tool",
    description="Cast a ranked ballot ordering agents from most to least preferred to talk next via Borda count consensus (Rule 229).",
    args_schema=CastSpeakerRankingVoteArgs,
    func=_run_cast_speaker_ranking_vote
)


class AdvanceSpeakerTurnArgs(BaseModel):
    force_agent_id: Optional[str] = Field(None, description="Optional agent to explicitly seat in the speaking slot")
    reason: str = Field("Tuning timer transition", description="Reason for advancing the turn")


def _run_advance_speaker_turn(force_agent_id: Optional[str] = None, reason: str = "Tuning timer transition") -> str:
    res = advance_speaker_turn(force_agent_id=force_agent_id, reason=reason)
    return json.dumps(res, indent=2)


advance_speaker_turn_tool = StructuredTool(
    name="advance_speaker_turn_tool",
    description="Advance the speaking turn to the next agent based on the consensus ranking and intent queue (Rule 229).",
    args_schema=AdvanceSpeakerTurnArgs,
    func=_run_advance_speaker_turn
)


class SimulateMultiAgentVoteArgs(BaseModel):
    topic: str = Field("Harmonic consensus", description="Deliberation topic guiding agent preferences")


def _run_simulate_multi_agent_vote(topic: str = "Harmonic consensus") -> str:
    res = simulate_multi_agent_vote(topic=topic)
    return json.dumps(res, indent=2)


simulate_multi_agent_vote_tool = StructuredTool(
    name="simulate_multi_agent_vote_tool",
    description="Trigger a full multi-agent ranked voting round across all network agents from most to least preferred speaker (Rule 229).",
    args_schema=SimulateMultiAgentVoteArgs,
    func=_run_simulate_multi_agent_vote
)


TUNING_TIMER_TOOLS = [
    get_tuning_timer_status_tool,
    register_speaking_intent_tool,
    cast_speaker_ranking_vote_tool,
    advance_speaker_turn_tool,
    simulate_multi_agent_vote_tool,
]


if __name__ == "__main__":
    print("[TUNING TIMER] Initial Status:")
    print(json.dumps(get_tuning_timer_status(), indent=2))
    print("\n[TUNING TIMER] Registering Intent:")
    register_speaking_intent("motherly_voice", urgency=4, topic="Harmonic alignment")
    print("\n[TUNING TIMER] Running multi-agent vote:")
    v_res = simulate_multi_agent_vote("Broadcasting priorities")
    print("Consensus Ranking (Most to Least):")
    for r in v_res["consensus_ranking"]:
        print(f"  #{r['rank']} {r['agent_id']} — Points: {r['borda_points']}, Votes: {r['votes_received']}")
    print("\n[TUNING TIMER] Advancing turn:")
    adv = advance_speaker_turn()
    print("New Speaker:", adv["current_speaker"])
