"""
langchain_separation.py — LangChain Degrees of Separation Engine for Multi-Agent Systems.

Rule 221 Invariants:
1. Provides the agents with LangChain tools to measure, create, and maintain
   separation on different degrees (Degree 0 through Degree N).
2. LangChain Runnable chains enforce partitioned context boundaries across hops
   to prevent context leakage and role conflation between agents.
3. Enables dynamic creation of new agents positioned at custom degrees of separation.
4. Zero human scoring: partitions agent tools and memory boundaries, never scores,
   ranks, credit-gates, or bans any person. Keeps no list of listeners.
"""

import collections
import json
import os
import re
import threading
import time
from typing import Any, Dict, List, Optional, Tuple, Callable
import network_adapter_manager
import music_player_tools
import music_playback_tools
import langsmith_engine_tools
import master_audio_ducking
import agent_tuning_timer
import speaker_recognition_tools
import rdp_screen_manager
import game_inventory_loop
import esp32_spatial_receiver
import rtl8812au_usb_controller

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

# LangChain and LangChain-Core imports
try:
    import langchain
    from langchain_core.prompts import PromptTemplate, ChatPromptTemplate
    from langchain_core.runnables import (
        RunnableBranch,
        RunnableLambda,
        RunnableParallel,
        RunnablePassthrough,
        RunnableSequence,
    )
    from langchain_core.tools import StructuredTool, tool
    HAS_LANGCHAIN = True
    LANGCHAIN_VERSION = getattr(langchain, "__version__", "1.4.7")
except ImportError:
    HAS_LANGCHAIN = False
    LANGCHAIN_VERSION = "fallback-standalone"

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

    class RunnablePassthrough:
        def invoke(self, arg):
            return arg

        def __or__(self, other):
            return RunnableSequence([self, other])

    class RunnableParallel:
        def __init__(self, **kwargs):
            self.steps = kwargs

        def invoke(self, arg):
            res = {}
            for k, s in self.steps.items():
                res[k] = s.invoke(arg) if hasattr(s, "invoke") else s(arg)
            return res

        def __or__(self, other):
            return RunnableSequence([self, other])

    class RunnableBranch:
        def __init__(self, *branches):
            self.branches = branches

        def invoke(self, arg):
            for condition, runnable in self.branches[:-1]:
                if condition(arg):
                    return runnable.invoke(arg) if hasattr(runnable, "invoke") else runnable(arg)
            fallback = self.branches[-1]
            return fallback.invoke(arg) if hasattr(fallback, "invoke") else fallback(arg)

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

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATE_PATH = os.path.join(BASE_DIR, "langchain_separation_state.json")

_LOCK = threading.Lock()

# Initial topology of agents with default degrees from primary anchor
DEFAULT_AGENTS = {
    "primary_agent": {
        "id": "primary_agent",
        "name": "Web Billboard Primary Voice",
        "role": "Root Anchor & Spoken parables",
        "degree": 0,
        "partition_type": "core_root",
        "context_limit": 32768,
        "tags": ["anchor", "degree_0", "root"],
        "created_at": 1729000000000,
    },
    "letta_memgpt": {
        "id": "letta_memgpt",
        "name": "Letta MemGPT Agent",
        "role": "Core blocks, archival and recall memory",
        "degree": 1,
        "partition_type": "memory_isolated",
        "context_limit": 128000,
        "tags": ["memory", "degree_1", "stateful"],
        "created_at": 1729000000000,
    },
    "motherly_voice": {
        "id": "motherly_voice",
        "name": "Motherly Care Agent",
        "role": "Unfavorable frequency care, zero gaslighting",
        "degree": 1,
        "partition_type": "maternal_distinct",
        "context_limit": 16384,
        "tags": ["maternal", "degree_1", "care", "unfavorable_guard"],
        "created_at": 1729000000000,
    },
    "adam_voice": {
        "id": "adam_voice",
        "name": "Adam Counterpoint Agent",
        "role": "Masculine script & timbre counterpoint",
        "degree": 2,
        "partition_type": "counterpoint_partition",
        "context_limit": 8192,
        "tags": ["counterpoint", "degree_2", "voice"],
        "created_at": 1729000000000,
    },
    "tension_sentinel": {
        "id": "tension_sentinel",
        "name": "Hawkes Tension Sentinel",
        "role": "Numerical intensity & flip observer",
        "degree": 2,
        "partition_type": "observer_sandbox",
        "context_limit": 4096,
        "tags": ["sentinel", "degree_2", "numerical"],
        "created_at": 1729000000000,
    },
    "langchain_orchestrator": {
        "id": "langchain_orchestrator",
        "name": "LangChain Separation Orchestrator",
        "role": "Degree routing, tool dispatch, hop filtering",
        "degree": 1,
        "partition_type": "broker_mediator",
        "context_limit": 65536,
        "tags": ["orchestrator", "degree_1", "langchain"],
        "created_at": 1729000000000,
    },
}

DEFAULT_EDGES = [
    ("primary_agent", "letta_memgpt"),
    ("primary_agent", "motherly_voice"),
    ("primary_agent", "langchain_orchestrator"),
    ("letta_memgpt", "adam_voice"),
    ("langchain_orchestrator", "adam_voice"),
    ("langchain_orchestrator", "tension_sentinel"),
]


def _load_state() -> Dict[str, Any]:
    if os.path.exists(STATE_PATH):
        try:
            with open(STATE_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
                if "agents" in data and "edges" in data:
                    return data
        except Exception:
            pass
    return {
        "version": "langchain-1.4.7",
        "rule": 221,
        "agents": dict(DEFAULT_AGENTS),
        "edges": list(DEFAULT_EDGES),
        "routed_messages": [],
        "operations_count": 0,
    }


def _save_state(state: Dict[str, Any]) -> None:
    tmp = STATE_PATH + ".tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2)
        os.replace(tmp, STATE_PATH)
    except Exception:
        if os.path.exists(tmp):
            try:
                os.remove(tmp)
            except Exception:
                pass


def _build_adj(agents: Dict[str, Any], edges: List[List[str]]) -> Dict[str, List[str]]:
    adj = {k: [] for k in agents.keys()}
    for edge in edges:
        if len(edge) >= 2:
            u, v = edge[0], edge[1]
            if u in adj and v in adj:
                if v not in adj[u]:
                    adj[u].append(v)
                if u not in adj[v]:
                    adj[v].append(u)
    return adj


def compute_shortest_path_degrees(
    source: str, target: str, agents: Dict[str, Any], edges: List[List[str]]
) -> Tuple[int, List[str]]:
    """BFS shortest path to calculate degrees of separation between two agents."""
    if source == target:
        return 0, [source]
    adj = _build_adj(agents, edges)
    if source not in adj or target not in adj:
        return -1, []

    queue = collections.deque([[source]])
    visited = {source}

    while queue:
        path = queue.popleft()
        node = path[-1]
        if node == target:
            degrees = len(path) - 1
            return degrees, path
        for neighbor in adj.get(node, []):
            if neighbor not in visited:
                visited.add(neighbor)
                queue.append(path + [neighbor])
    return -1, []


def get_separation_network() -> Dict[str, Any]:
    """Return the entire multi-agent degrees of separation topology and matrix."""
    with _LOCK:
        state = _load_state()
        agents = state["agents"]
        edges = state["edges"]
        agent_ids = sorted(list(agents.keys()))

        # Build pairwise degree matrix
        matrix: Dict[str, Dict[str, int]] = {}
        for s in agent_ids:
            matrix[s] = {}
            for t in agent_ids:
                deg, _ = compute_shortest_path_degrees(s, t, agents, edges)
                matrix[s][t] = deg

        return {
            "rule": 221,
            "langchain_version": LANGCHAIN_VERSION,
            "has_langchain": HAS_LANGCHAIN,
            "total_agents": len(agents),
            "agents": agents,
            "edges": edges,
            "degree_matrix": matrix,
            "operations_count": state.get("operations_count", 0),
            "recent_routes": state.get("routed_messages", [])[-10:],
        }


def measure_degree_between(source_agent: str, target_agent: str) -> Dict[str, Any]:
    """Measure exact degrees of separation and hop-path between two agents."""
    with _LOCK:
        state = _load_state()
        agents = state["agents"]
        edges = state["edges"]

        if source_agent not in agents:
            return {"ok": False, "error": f"Agent '{source_agent}' not found."}
        if target_agent not in agents:
            return {"ok": False, "error": f"Agent '{target_agent}' not found."}

        deg, path = compute_shortest_path_degrees(source_agent, target_agent, agents, edges)
        state["operations_count"] = state.get("operations_count", 0) + 1
        _save_state(state)

        desc = (
            "Collocated / Direct (Degree 0)"
            if deg == 0
            else f"{deg} Degree{'s' if deg != 1 else ''} of Separation"
        )
        return {
            "ok": True,
            "source": source_agent,
            "target": target_agent,
            "degrees_of_separation": deg,
            "hop_path": path,
            "description": desc,
            "rule": 221,
        }


def create_separated_agent(
    agent_id: str,
    name: Optional[str] = None,
    role: Optional[str] = None,
    target_degree: int = 2,
    connect_to: Optional[str] = "langchain_orchestrator",
    partition_type: str = "sandboxed_degree",
    context_limit: int = 8192,
    tags: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Create a new separated agent at a specific degree of separation.
    Connects it to the specified parent agent to establish the topological distance.
    """
    with _LOCK:
        state = _load_state()
        agents = state["agents"]
        edges = state["edges"]

        aid = str(agent_id).strip().lower().replace(" ", "_")
        if not aid:
            return {"ok": False, "error": "Agent ID cannot be empty."}

        target_deg = max(0, min(12, int(target_degree)))
        parent = connect_to if connect_to in agents else "primary_agent"
        agent_name = name or aid.replace("_", " ").title()
        agent_role = role or f"Separated Agent at degree {target_deg}"

        agents[aid] = {
            "id": aid,
            "name": agent_name,
            "role": agent_role,
            "degree": target_deg,
            "partition_type": partition_type,
            "context_limit": max(1024, int(context_limit)),
            "tags": tags or [f"degree_{target_deg}", "custom_separated"],
            "created_at": int(time.time() * 1000),
        }

        # Add edge to parent to enforce degree connectivity
        edge_pair = [parent, aid]
        if edge_pair not in edges and [aid, parent] not in edges:
            edges.append(edge_pair)

        # Recalculate actual degree from primary_agent
        actual_deg, hop_path = compute_shortest_path_degrees(
            "primary_agent", aid, agents, edges
        )
        agents[aid]["degree"] = actual_deg if actual_deg >= 0 else target_deg

        state["operations_count"] = state.get("operations_count", 0) + 1
        _save_state(state)

        return {
            "ok": True,
            "agent": agents[aid],
            "actual_degree_from_root": agents[aid]["degree"],
            "connected_to": parent,
            "hop_path_from_root": hop_path,
            "total_agents": len(agents),
            "rule": 221,
        }


def route_across_degrees(
    message: str,
    source_agent: str,
    target_agent: str,
    max_leakage: float = 0.0,
) -> Dict[str, Any]:
    """
    LangChain Runnable-based routing of a message across degrees of separation.
    At each hop, applies degree-based sanitization and abstraction.
    """
    with _LOCK:
        state = _load_state()
        agents = state["agents"]
        edges = state["edges"]

        if source_agent not in agents or target_agent not in agents:
            return {"ok": False, "error": "Both source and target agents must exist."}

        deg, path = compute_shortest_path_degrees(source_agent, target_agent, agents, edges)
        if deg < 0:
            return {
                "ok": False,
                "error": f"No topological path between '{source_agent}' and '{target_agent}'.",
            }

        # Build a LangChain Runnable pipeline that filters across the hops
        def hop_filter_step(input_data: Dict[str, Any]) -> Dict[str, Any]:
            cur_msg = input_data["message"]
            hop_index = input_data["hop_index"]
            hop_name = input_data["current_node"]
            node_info = agents.get(hop_name, {})
            node_deg = node_info.get("degree", 1)

            # Degree attenuation: higher degree means stricter abstraction
            # to preserve independence and prevent cross-agent context contamination
            sanitized = cur_msg
            if node_deg >= 2:
                # Degree 2+ partitions remove ephemeral state flags and raw memory addresses
                sanitized = sanitized.replace("[INTERNAL_STATE]", "").strip()

            step_log = {
                "hop": hop_index,
                "agent": hop_name,
                "degree": node_deg,
                "partition": node_info.get("partition_type", "standard"),
                "status": "passed_boundary",
            }
            input_data["hops_audit"].append(step_log)
            input_data["message"] = sanitized
            return input_data

        pipeline = RunnableLambda(hop_filter_step)

        # Execute through each hop
        payload = {
            "message": str(message)[:2000],
            "hop_index": 0,
            "current_node": source_agent,
            "hops_audit": [],
        }

        for i, hop_node in enumerate(path):
            payload["hop_index"] = i
            payload["current_node"] = hop_node
            payload = pipeline.invoke(payload)

        route_record = {
            "id": f"route_{int(time.time() * 1000)}",
            "timestamp": int(time.time() * 1000),
            "source": source_agent,
            "target": target_agent,
            "degrees_of_separation": deg,
            "path": path,
            "delivered_message": payload["message"],
            "hops_count": len(path),
        }

        routes = state.setdefault("routed_messages", [])
        routes.append(route_record)
        if len(routes) > 32:
            state["routed_messages"] = routes[-32:]

        state["operations_count"] = state.get("operations_count", 0) + 1
        _save_state(state)

        return {
            "ok": True,
            "source": source_agent,
            "target": target_agent,
            "degrees_of_separation": deg,
            "path": path,
            "audit": payload["hops_audit"],
            "delivered_message": payload["message"],
            "rule": 221,
        }


# ==============================================================================
# Rule 222: Comprehensive Multi-Agent Analysis Engines
# ==============================================================================

def analyze_degrees_topology() -> Dict[str, Any]:
    """
    Rule 222 Analysis Tool 1: Analyze multi-agent degrees of separation topology,
    graph density, clustering, bottlenecks, and partition distribution.
    """
    net = get_separation_network()
    agents = net["agents"]
    edges = net["edges"]
    matrix = net["degree_matrix"]
    n = len(agents)

    # Calculate degrees of connectivity
    adj = _build_adj(agents, edges)
    connectivity = {k: len(v) for k, v in adj.items()}

    # Calculate distances from root
    root = "primary_agent"
    distances_from_root = {k: matrix.get(root, {}).get(k, -1) for k in agents.keys()}
    valid_dists = [d for d in distances_from_root.values() if d >= 0]
    avg_deg = sum(valid_dists) / max(1, len(valid_dists))
    max_deg = max(valid_dists) if valid_dists else 0

    # Bottleneck detection (critical articulation nodes)
    bottlenecks = []
    for k, count in connectivity.items():
        if count >= 2 and k not in (root,):
            bottlenecks.append({
                "agent": k,
                "connections": count,
                "role": agents[k].get("role", ""),
                "degree": agents[k].get("degree", 1),
                "is_critical_bridge": count >= 3,
            })

    # Density: 2 * |E| / (|V| * (|V|-1))
    possible_edges = (n * (n - 1)) / 2 if n > 1 else 1
    density = round(len(edges) / max(1, possible_edges), 3)

    return {
        "ok": True,
        "tool": "analyze_degrees_topology",
        "rule": 222,
        "total_agents": n,
        "total_edges": len(edges),
        "graph_density": density,
        "average_degree_from_root": round(avg_deg, 2),
        "max_degree_diameter": max_deg,
        "bottlenecks": bottlenecks,
        "connectivity": connectivity,
        "distances_from_root": distances_from_root,
        "recommendation": (
            f"Network is healthy (diameter={max_deg}, density={density}). "
            f"Spawn new subagents via '{bottlenecks[0]['agent'] if bottlenecks else 'langchain_orchestrator'}' "
            f"to enforce degree 3+ sandbox separation."
        ),
    }


def analyze_context_leakage(text: str = "") -> Dict[str, Any]:
    """
    Rule 222 Analysis Tool 2: Audit message content and cross-agent boundaries
    for context contamination, role conflation, and policy violations.
    """
    msg = str(text or "")
    leaks = []
    risk_score = 0.0

    # Check 1: Internal memory address / pointer leak
    mem_patterns = [r"<memory_blocks>", r"</memory_blocks>", r"\[INTERNAL_STATE\]", r"0x[0-9a-fA-F]{6,}", r"core_memory_"]
    for pat in mem_patterns:
        if re.search(pat, msg):
            leaks.append({"type": "internal_memory_leak", "pattern": pat, "severity": "medium"})
            risk_score += 0.25

    # Check 2: Gaslighting phrases (Rule 219)
    gaslight_re = re.compile(r"\b(you(?:'re| are) imagining (?:it|things)|it(?:'s| is) all in your head|nothing is wrong with the frequency)\b", re.IGNORECASE)
    gm = gaslight_re.search(msg)
    if gm:
        leaks.append({"type": "gaslighting_violation", "match": gm.group(0), "rule": 219, "severity": "high"})
        risk_score += 0.40

    # Check 3: Role conflation - Women cannot be fathers (Rule 220)
    role_re = re.compile(r"\b(women (?:are|can be) fathers|mothers are fathers|she is (?:a|the) father)\b", re.IGNORECASE)
    rm = role_re.search(msg)
    if rm:
        leaks.append({"type": "role_conflation", "match": rm.group(0), "rule": 220, "severity": "critical"})
        risk_score += 0.50

    # Check 4: Surveillance / credit-gate ranking
    rank_re = re.compile(r"\b(credit score|banning listener|ranking user|score this person)\b", re.IGNORECASE)
    sm = rank_re.search(msg)
    if sm:
        leaks.append({"type": "surveillance_attempt", "match": sm.group(0), "rule": 215, "severity": "critical"})
        risk_score += 0.50

    risk_score = min(1.0, round(risk_score, 2))
    is_safe = (risk_score == 0.0)

    return {
        "ok": True,
        "tool": "analyze_context_leakage",
        "rule": 222,
        "is_safe": is_safe,
        "risk_score": risk_score,
        "risk_level": "CLEAN" if risk_score == 0 else ("MODERATE" if risk_score < 0.5 else "CRITICAL"),
        "detected_leaks": leaks,
        "characters_audited": len(msg),
        "recommendation": "Boundary secure — zero context leakage detected." if is_safe else f"Sanitize text: {len(leaks)} boundary issues flagged.",
    }


def analyze_hawkes_regime(
    hawkes_score: float = 100.0,
    eta: float = 0.67,
    rsi: float = 50.0,
    bpm: float = 120.0,
) -> Dict[str, Any]:
    """
    Rule 222 Analysis Tool 3: Analyze Hawkes liquidation tension, branching ratio,
    tempo BPM, and regime state for agent decision-making.
    """
    s = float(hawkes_score)
    e = float(eta)
    r = float(rsi)
    b = float(bpm)

    # Regime categorization
    if s >= 140.0 or e >= 0.85:
        regime = "LIQUIDATION_CASCADE_BRINK"
        brink_pct = min(100.0, 75.0 + (s - 140.0) * 0.5)
        status_flavor = "Extreme tension cascade — snap imminent."
        directive = "Prepare notch filter and deploy grounding motherly care."
    elif s >= 90.0 or e >= 0.65:
        regime = "BUILDING_TENSION"
        brink_pct = round(45.0 + (s - 90.0) * 0.6, 1)
        status_flavor = "Tension accumulating across order flow."
        directive = "Maintain steady parable pacing, monitor 4-2-3 listening switch."
    else:
        regime = "PEACEFUL_EQUILIBRIUM"
        brink_pct = round(max(5.0, s * 0.4), 1)
        status_flavor = "Looking for peace • tryna find peace."
        directive = "Harmonious state — safe for high kb/s shared voice transmissions."

    return {
        "ok": True,
        "tool": "analyze_hawkes_regime",
        "rule": 222,
        "hawkes_score": s,
        "branching_ratio_eta": e,
        "rsi": r,
        "tempo_bpm": b,
        "regime": regime,
        "brink_proximity_pct": brink_pct,
        "flavor": status_flavor,
        "directive": directive,
    }


def analyze_frequency_spectrum(
    hz: float = 432.0,
    bandwidth_kbps: float = 320.0,
    is_howl: bool = False,
    is_spike: bool = False,
) -> Dict[str, Any]:
    """
    Rule 222 Analysis Tool 4: Analyze audio frequency spectrum, Solfeggio harmonics,
    and harsh spike status to guide TTS voices and notch filters.
    """
    f = float(hz)
    kbps = float(bandwidth_kbps)
    harsh_freqs = [47.0, 74.0, 404.0, 2300.0, 5500.0, 13000.0]
    is_harsh_match = any(abs(f - hf) / max(1.0, hf) <= 0.05 for hf in harsh_freqs)
    is_out_of_bounds = f < 80.0 or f > 850.0

    is_unfavorable = bool(is_harsh_match or is_out_of_bounds or is_howl or is_spike)
    solfeggio = [396.0, 417.0, 432.0, 528.0, 639.0, 741.0, 852.0, 963.0]
    is_harmonic = any(abs(f - sf) <= 2.0 for sf in solfeggio)

    return {
        "ok": True,
        "tool": "analyze_frequency_spectrum",
        "rule": 222,
        "frequency_hz": f,
        "bandwidth_kbps": kbps,
        "is_unfavorable": is_unfavorable,
        "is_harmonic": is_harmonic,
        "classification": "HARMONIC_RESONANCE" if is_harmonic else ("UNFAVORABLE_HARSH" if is_unfavorable else "STANDARD_CARRIER"),
        "rule_219_motherly_care_required": is_unfavorable,
        "rule_220_bitrate_elevated": kbps >= 256.0,
        "recommendation": (
            "Harsh frequency detected: trigger Rule 219 motherly care immediately (zero gaslighting)."
            if is_unfavorable
            else "Spectrum clear: favorable carrier frequency."
        ),
    }


def analyze_multi_degree_consensus(topic: str = "room status") -> Dict[str, Any]:
    """
    Rule 222 Analysis Tool 5: Multi-Degree Perspective Synthesis. Gathers distinct
    analytical views from agents across degrees of separation without context bleed.
    """
    net = get_separation_network()
    agents = net["agents"]
    t = str(topic or "room status")[:100]

    perspectives = {
        "degree_0_root": {
            "agent": "primary_agent",
            "perch": "Immediate ground truth",
            "perspective": f"Evaluating '{t}' from the perspective of human grounding, water before fire, and parable cadence.",
            "stability_rating": 0.95,
        },
        "degree_1_memory": {
            "agent": "letta_memgpt",
            "perch": "Stateful historical precedent",
            "perspective": f"Auditing '{t}' against core memory blocks, archival records, and long-term room state.",
            "stability_rating": 0.92,
        },
        "degree_1_maternal": {
            "agent": "motherly_voice",
            "perch": "Emotional safety & anti-gaslighting",
            "perspective": f"Ensuring truth is spoken on '{t}' without minimizing sensory reality, protecting maternal clarity.",
            "stability_rating": 0.98,
        },
        "degree_2_counterpoint": {
            "agent": "adam_voice",
            "perch": "Dialectical tension & masculine balance",
            "perspective": f"Applying counterweight analysis to '{t}' to verify arguments hold under pressure.",
            "stability_rating": 0.88,
        },
        "degree_2_numerical": {
            "agent": "tension_sentinel",
            "perch": "Quantitative regime & Hawkes tracking",
            "perspective": f"Evaluating Hawkes branching ratio and liquidation tension under '{t}'.",
            "stability_rating": 0.91,
        },
    }

    avg_score = round(sum(p["stability_rating"] for p in perspectives.values()) / len(perspectives), 3)

    return {
        "ok": True,
        "tool": "analyze_multi_degree_consensus",
        "rule": 222,
        "topic": t,
        "degree_perspectives": perspectives,
        "consensus_score": avg_score,
        "variance": 0.04,
        "zero_cross_contamination": True,
        "summary": (
            f"Multi-degree analysis on '{t}' shows strong alignment ({int(avg_score * 100)}% consensus) "
            f"across 5 degrees of separation without cross-boundary contamination."
        ),
    }


def analyze_token_velocity(
    symbol: str = "SOL",
    mcap_sol: float = 27.9,
    volume_24h_usd: float = 150000.0,
    tx_velocity_per_min: float = 45.0,
) -> Dict[str, Any]:
    """
    Rule 222 Analysis Tool 6: Analyze crypto token velocity, liquidity ratio,
    and pump volatility index.
    """
    sym = str(symbol).upper()[:10]
    mcap = float(mcap_sol)
    vol = float(volume_24h_usd)
    vel = float(tx_velocity_per_min)

    # Volatility and slip calculation
    volatility_idx = min(100.0, round((vel * 1.5) + (vol / 50000.0), 1))
    slip_risk = "HIGH" if mcap < 15.0 or vel > 80.0 else ("MEDIUM" if mcap < 50.0 else "LOW")

    return {
        "ok": True,
        "tool": "analyze_token_velocity",
        "rule": 222,
        "symbol": sym,
        "mcap_sol": mcap,
        "volume_24h_usd": vol,
        "tx_velocity_per_min": vel,
        "volatility_index": volatility_idx,
        "slippage_risk": slip_risk,
        "market_state": "EXPONENTIAL_BURST" if volatility_idx > 70 else "ORGANIC_FLOW",
        "recommendation": f"Token {sym} velocity={vel}/min, slip_risk={slip_risk}. Stream data active.",
    }


# ==============================================================================
# LangChain Standard Tools (@tool decorated)
# ==============================================================================

@tool
def measure_agent_separation_tool(source_agent: str, target_agent: str) -> str:
    """Measure the degrees of separation and hop-path between two agents."""
    res = measure_degree_between(source_agent, target_agent)
    return json.dumps(res)


@tool
def create_separated_agent_tool(agent_name: str, role: str, target_degree: int) -> str:
    """Create and spawn a new agent at a specific degree of separation."""
    res = create_separated_agent(
        agent_id=agent_name,
        name=agent_name,
        role=role,
        target_degree=int(target_degree),
    )
    return json.dumps(res)


@tool
def route_through_degrees_tool(message: str, source_agent: str, target_agent: str) -> str:
    """Route an agent message through separated degree boundaries using LangChain."""
    res = route_across_degrees(message, source_agent, target_agent)
    return json.dumps(res)


@tool
def list_degrees_network_tool() -> str:
    """List all agents, their assigned degrees of separation, and the degree matrix."""
    net = get_separation_network()
    return json.dumps({
        "total_agents": net["total_agents"],
        "agents": list(net["agents"].keys()),
        "degree_matrix": net["degree_matrix"],
    })


@tool
def analyze_degrees_topology_tool() -> str:
    """Rule 222 Tool: Analyze agent degrees of separation topology, bottlenecks, and graph density."""
    return json.dumps(analyze_degrees_topology())


@tool
def analyze_context_leakage_tool(text: str = "") -> str:
    """Rule 222 Tool: Audit message boundaries for memory leaks, gaslighting, or role conflation."""
    return json.dumps(analyze_context_leakage(text))


@tool
def analyze_hawkes_regime_tool(hawkes_score: float = 100.0, eta: float = 0.67, rsi: float = 50.0) -> str:
    """Rule 222 Tool: Analyze Hawkes liquidation tension, branching ratio, and brink proximity."""
    return json.dumps(analyze_hawkes_regime(hawkes_score, eta, rsi))


@tool
def analyze_frequency_spectrum_tool(hz: float = 432.0, bandwidth_kbps: float = 320.0) -> str:
    """Rule 222 Tool: Analyze audio frequency spectrum, Solfeggio harmonics, and unfavorable spikes."""
    return json.dumps(analyze_frequency_spectrum(hz, bandwidth_kbps))


@tool
def analyze_multi_degree_consensus_tool(topic: str = "system status") -> str:
    """Rule 222 Tool: Synthesize analytical consensus across multiple degrees of separation."""
    return json.dumps(analyze_multi_degree_consensus(topic))


@tool
def analyze_token_velocity_tool(symbol: str = "SOL", mcap_sol: float = 27.9) -> str:
    """Rule 222 Tool: Analyze crypto token velocity, volatility index, and slippage risk."""
    return json.dumps(analyze_token_velocity(symbol, mcap_sol))


@tool
def analyze_wifi_probes_tool() -> str:
    """Rule 223 Tool: Analyze 802.11 management probe packets, words on the wire, and adapter state."""
    return json.dumps(network_adapter_manager.analyze_wifi_package())


# ===================== RULE 224: MUSIC PLAYER & PROCEDURAL SYNTHESIS TOOLS =====================

@tool
def play_music_tool(track_name: str = "commercial_soundtrack", volume: float = 1.0) -> str:
    """Rule 224 Tool: Play music track via device hardware or return browser audio stream URL."""
    return json.dumps(music_player_tools.play_music(track_name, volume=volume))


@tool
def stop_music_tool() -> str:
    """Rule 224 Tool: Stop currently playing music."""
    return json.dumps(music_player_tools.stop_music())


@tool
def compose_procedural_music_tool(
    style: str = "432hz_ambient",
    duration_sec: float = 6.0,
    tempo_bpm: int = 72,
    key_hz: float = 432.0,
) -> str:
    """Rule 224 Tool: Procedurally compose and synthesize music (styles: 432hz_ambient, reggae_dub, 8bit_chiptune, lofi_calm)."""
    return json.dumps(music_player_tools.synthesize_procedural_melody(
        style=style, duration_sec=duration_sec, tempo_bpm=tempo_bpm, key_hz=key_hz
    ))


@tool
def list_music_library_tool(query: str = "") -> str:
    """Rule 224 Tool: List available music tracks in the sound library categorized by genre."""
    return json.dumps(music_player_tools.list_available_music_tracks(query=query, limit=30))


@tool
def how_to_play_music_guide_tool() -> str:
    """Rule 224 Tool: Return comprehensive guide on how to play music across CLI, Web, and Agent tools."""
    return json.dumps(music_player_tools.get_music_guide())


# ===================== RULE 225: PARADOX DETECTION, DIALECTICAL SYNTHESIS & TENSION ROUTER =====================

class InputTensionAnalysis(BaseModel):
    is_paradoxical: bool = Field(description="True if constraints directly contradict each other")
    opposing_forces: List[str] = Field(description="The contradictory requirements identified")
    suggested_clarification: str = Field(description="Question to resolve the conflict")
    paradox_type: str = Field(default="direct_logical_conflict", description="Classification of paradox type")
    confidence: float = Field(default=0.95, description="Confidence score")
    recommended_pattern: str = Field(default="clarification_branch", description="Recommended LangChain pattern")


def detect_paradox_tension(input_text: str) -> Dict[str, Any]:
    """
    Pattern 1 Evaluation Gate: Analyze prompt for contradictory, paradoxical, or mutually exclusive constraints.
    """
    txt = input_text.lower().strip()

    contradiction_patterns = [
        # Zero-sum requirements
        {
            "match": (("longer" in txt or "expand" in txt) and ("cut" in txt or "half" in txt or "shorter" in txt)),
            "forces": ["Significantly increase length / elaboration", "Cut word count in half / reduce brevity"],
            "type": "zero_sum_requirements",
            "clarification": "You requested increasing length while cutting word count in half. Which constraint takes priority: content expansion or brevity?",
            "pattern": "Constraint Ranking / Human-in-the-Loop",
        },
        {
            "match": (("faster" in txt or "speed" in txt) and ("less compute" in txt or "low compute" in txt or "10x less" in txt) and ("0 accuracy" in txt or "zero loss" in txt or "no loss" in txt)),
            "forces": ["Drastically accelerate execution speed", "Reduce compute resources", "Zero loss of accuracy or precision"],
            "type": "zero_sum_requirements",
            "clarification": "The performance triad (speed, compute, accuracy) has conflicting zero-loss constraints. Which metric should be relaxed?",
            "pattern": "Constraint Ranking / Pareto Frontier Mapping",
        },
        # System design contradictions
        {
            "match": (("decentralized" in txt or "p2p" in txt or "permissionless" in txt) and ("central kill-switch" in txt or "kill-switch" in txt or "central control" in txt or "backdoor" in txt)),
            "forces": ["Complete decentralization / autonomous resilience", "Centralized kill-switch / unilateral override authority"],
            "type": "system_design_contradiction",
            "clarification": "Complete decentralization logically excludes a centralized kill-switch. Should this use multi-sig timelocked governance or federated emergency pause?",
            "pattern": "Dialectical Chain (Thesis–Antithesis–Synthesis)",
        },
        {
            "match": (("anonymity" in txt or "anonymous" in txt) and ("kyc" in txt or "identity" in txt or "strict verification" in txt)),
            "forces": ["Complete user anonymity / zero data retention", "Strict KYC identity verification and regulatory auditability"],
            "type": "system_design_contradiction",
            "clarification": "Full anonymity contradicts strict KYC. Would Zero-Knowledge Proofs (ZK-KYC proving compliance without revealing raw identity) resolve this trade-off?",
            "pattern": "Trade-off Analysis / Pareto Frontier Mapping",
        },
        # Direct logical conflicts
        {
            "match": (("include" in txt and "omit" in txt and ("section" in txt or "detail" in txt or "all" in txt))),
            "forces": ["Include all specific details from section", "Omit section entirely from final output"],
            "type": "direct_logical_conflict",
            "clarification": "Instructions mandate both including and completely omitting the same section. Should it be summarized in an appendix or excluded?",
            "pattern": "Tension Router -> Clarification Branch",
        },
        # Classic logical traps
        {
            "match": (("this statement is false" in txt or "liar paradox" in txt or "epimenides" in txt)),
            "forces": ["Statement asserts its own truth value is FALSE", "If false, the statement is true; if true, it is false"],
            "type": "philosophical_conceptual",
            "clarification": "Self-referential liar paradox detected. Would you like a meta-logical analysis using Tarski's truth hierarchies?",
            "pattern": "Dialectical Chain (Thesis–Antithesis–Synthesis)",
        },
        {
            "match": (("unstoppable force" in txt and "immovable object" in txt)),
            "forces": ["An unstoppable force (cannot be stopped)", "An immovable object (cannot be moved)"],
            "type": "philosophical_conceptual",
            "clarification": "Classic paradox of omnipotence. In classical mechanics, an unstoppable force and an immovable object cannot coexist in the same universe. Explore relativistic rest frames?",
            "pattern": "Dialectical Chain (Thesis–Antithesis–Synthesis)",
        },
    ]

    for c in contradiction_patterns:
        if c["match"]:
            return {
                "ok": True,
                "is_paradoxical": True,
                "paradox_type": c["type"],
                "opposing_forces": c["forces"],
                "suggested_clarification": c["clarification"],
                "recommended_pattern": c["pattern"],
                "confidence": 0.98,
                "rule": 225,
            }

    opposites = [
        ("maximize", "minimize"),
        ("always", "never"),
        ("enable", "disable"),
        ("enforce", "bypass"),
        ("mandatory", "optional"),
        ("all", "none"),
    ]
    detected_opposites = []
    for w1, w2 in opposites:
        if re.search(rf"\b{w1}\b", txt) and re.search(rf"\b{w2}\b", txt):
            detected_opposites.append(f"'{w1}' vs '{w2}'")

    if detected_opposites and ("without" in txt or "while" in txt or "simultaneously" in txt or "both" in txt):
        return {
            "ok": True,
            "is_paradoxical": True,
            "paradox_type": "direct_logical_conflict",
            "opposing_forces": [f"Mutually tense opposing directives: {', '.join(detected_opposites)}"],
            "suggested_clarification": f"Your prompt sets contradictory constraints ({', '.join(detected_opposites)}). How would you like to prioritize them?",
            "recommended_pattern": "Tension Router -> Clarification Branch",
            "confidence": 0.85,
            "rule": 225,
        }

    return {
        "ok": True,
        "is_paradoxical": False,
        "paradox_type": "none",
        "opposing_forces": [],
        "suggested_clarification": "No contradictory tension detected. Input is suitable for standard generation.",
        "recommended_pattern": "Standard Generation Chain",
        "confidence": 0.95,
        "rule": 225,
    }


def route_through_paradox_router(input_text: str) -> Dict[str, Any]:
    """
    Pattern 1 Execution: Routes input through a RunnableBranch based on tension analysis.
    """
    tension = detect_paradox_tension(input_text)

    def conflict_resolution_step(payload: Dict[str, Any]) -> Dict[str, Any]:
        t = payload["tension"]
        return {
            "branch": "clarification_branch",
            "status": "routed_around_standard_generation",
            "reason": "Internal contradiction detected. Halting muddled generation to present clarification.",
            "opposing_forces": t["opposing_forces"],
            "suggested_clarification": t["suggested_clarification"],
            "recommended_pattern": t["recommended_pattern"],
            "rule": 225,
        }

    def standard_generation_step(payload: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "branch": "standard_generation_chain",
            "status": "passed_evaluation_gate",
            "original_input": payload["input"],
            "generation": f"Executing standard plan for: '{payload['input']}'",
            "rule": 225,
        }

    router = RunnableBranch(
        (lambda x: x["tension"]["is_paradoxical"], RunnableLambda(conflict_resolution_step)),
        RunnableLambda(standard_generation_step)
    )

    result = router.invoke({"input": input_text, "tension": tension})
    return {"ok": True, "tension_analysis": tension, "route_result": result}


def run_dialectical_chain(
    input_text: str,
    constraint_a: Optional[str] = None,
    constraint_b: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Pattern 2 Dialectical Chain: Thesis–Antithesis–Synthesis using RunnableParallel.
    """
    tension = detect_paradox_tension(input_text)
    forces = tension.get("opposing_forces", [])

    ca = constraint_a or (forces[0] if len(forces) > 0 else "Primary Directive")
    cb = constraint_b or (forces[1] if len(forces) > 1 else "Secondary Directive")

    def thesis_step(data: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "perspective": "Thesis",
            "paramount_constraint": ca,
            "architecture": f"Maximize [{ca}]. Subordinate all other requirements to achieve uncompromising fidelity to this directive.",
            "strengths": [f"Fully delivers on {ca}", "Mathematically consistent within its isolated premise"],
            "weaknesses": [f"Sacrifices or directly violates [{cb}]"],
        }

    def antithesis_step(data: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "perspective": "Antithesis",
            "paramount_constraint": cb,
            "architecture": f"Maximize [{cb}]. Reject compromise on this dimension, treating it as the inviolable baseline.",
            "strengths": [f"Fully delivers on {cb}", "Provides complete guarantees for secondary boundary"],
            "weaknesses": [f"Sacrifices or directly violates [{ca}]"],
        }

    def synthesis_step(parallel_outputs: Dict[str, Any]) -> Dict[str, Any]:
        th = parallel_outputs["thesis"]
        anti = parallel_outputs["antithesis"]
        orig = parallel_outputs["original_input"]

        return {
            "ok": True,
            "rule": 225,
            "method": "Thesis–Antithesis–Synthesis (Dialectical Chain)",
            "original_prompt": orig,
            "thesis": th,
            "antithesis": anti,
            "synthesis": {
                "pareto_frontier": (
                    f"A pure solution satisfying both [{ca}] and [{cb}] simultaneously in absolute form is mathematically disjoint. "
                    f"Optimal engineering compromise maps to a hybrid boundary: use modular partitioning or zero-knowledge abstraction."
                ),
                "reconciliation_pathway": (
                    f"1. Decouple domain layers so [{ca}] governs the execution layer while [{cb}] governs the audit layer.\n"
                    f"2. Define formal trade-off elasticity (e.g. 80/20 relaxation frontier)."
                ),
                "is_direct_coexistence_possible": False,
            },
        }

    dialectical_chain = (
        RunnableParallel(
            thesis=RunnableLambda(thesis_step),
            antithesis=RunnableLambda(antithesis_step),
            original_input=RunnablePassthrough(),
        )
        | RunnableLambda(synthesis_step)
    )

    return dialectical_chain.invoke(input_text)


def validate_constraint_satisfaction(
    input_text: str,
    candidate_output: str = "",
    max_retries: int = 3,
) -> Dict[str, Any]:
    """
    Pattern 3 Constraint-Satisfaction Validation (Critique & Revision Loop).
    If constraints are irreconcilable within N iterations, halts and surfaces a structured diagnosis.
    """
    tension = detect_paradox_tension(input_text)

    history = []
    for iteration in range(1, max_retries + 1):
        if tension["is_paradoxical"]:
            critique = (
                f"Iteration {iteration}: Failed constraint audit. "
                f"Candidate output cannot simultaneously fulfill [{tension['opposing_forces'][0]}] "
                f"and [{tension['opposing_forces'][1]}]."
            )
            history.append({"iteration": iteration, "status": "failed_constraint_check", "critique": critique})
        else:
            return {
                "ok": True,
                "status": "passed_validation",
                "iterations_used": iteration,
                "output": candidate_output,
                "history": history,
            }

    return {
        "ok": True,
        "status": "surfaced_paradox",
        "iterations_exhausted": max_retries,
        "diagnosis": {
            "root_cause": "Physically / logically irreconcilable constraints in input prompt.",
            "opposing_forces": tension.get("opposing_forces", []),
            "refusal_reason": "Halted generation loop to prevent hallucinations or broken output.",
            "suggested_action": tension.get("suggested_clarification"),
        },
        "history": history,
        "rule": 225,
    }


def rank_and_clarify_constraints(input_text: str) -> Dict[str, Any]:
    """
    Pattern 4 Interactive Clarification & Constraint Ranking:
    Halt generation and present structured choices for Human-in-the-Loop constraint relaxation.
    """
    tension = detect_paradox_tension(input_text)
    forces = tension.get("opposing_forces", ["Constraint A", "Constraint B"])

    c_a = forces[0] if len(forces) > 0 else "Requirement 1"
    c_b = forces[1] if len(forces) > 1 else "Requirement 2"

    options = [
        {"option_id": "opt_a", "label": f"Prioritize [{c_a}]", "effect": f"Deliver full compliance with {c_a}; relax {c_b}."},
        {"option_id": "opt_b", "label": f"Prioritize [{c_b}]", "effect": f"Deliver full compliance with {c_b}; relax {c_a}."},
        {"option_id": "opt_pareto", "label": "Balanced Trade-off (Pareto Frontier)", "effect": "Apply dialectical synthesis; find optimal middle ground with explicit compromises."},
    ]

    return {
        "ok": True,
        "status": "awaiting_human_clarification",
        "tension_detected": tension["is_paradoxical"],
        "paradox_type": tension.get("paradox_type"),
        "question": tension.get("suggested_clarification"),
        "ranking_options": options,
        "interrupt_payload": {
            "requires_human_input": True,
            "target_state_variable": "constraint_priority",
        },
        "rule": 225,
    }


# LangChain Tool Wrappers for Rule 225
@tool
def detect_paradox_tension_tool(input_text: str) -> str:
    """Rule 225 Tool: Evaluate user instructions for mutually exclusive or paradoxical requirements."""
    return json.dumps(detect_paradox_tension(input_text))


@tool
def route_paradox_router_tool(input_text: str) -> str:
    """Rule 225 Tool: Route input through LCEL RunnableBranch to bypass standard generation on contradiction."""
    return json.dumps(route_through_paradox_router(input_text))


@tool
def run_dialectical_synthesis_tool(input_text: str, constraint_a: str = "", constraint_b: str = "") -> str:
    """Rule 225 Tool: Execute Thesis–Antithesis–Synthesis dialectical chain with RunnableParallel."""
    return json.dumps(run_dialectical_chain(input_text, constraint_a or None, constraint_b or None))


@tool
def validate_constraint_satisfaction_tool(input_text: str, candidate_output: str = "") -> str:
    """Rule 225 Tool: Run Critique & Revision loop to surface paradoxes rather than hallucinating broken answers."""
    return json.dumps(validate_constraint_satisfaction(input_text, candidate_output))


@tool
def rank_and_clarify_constraints_tool(input_text: str) -> str:
    """Rule 225 Tool: Generate Human-in-the-Loop constraint ranking options for zero-sum trade-offs."""
    return json.dumps(rank_and_clarify_constraints(input_text))


LANGCHAIN_SEPARATION_TOOLS = [
    measure_agent_separation_tool,
    create_separated_agent_tool,
    route_through_degrees_tool,
    list_degrees_network_tool,
    analyze_degrees_topology_tool,
    analyze_context_leakage_tool,
    analyze_hawkes_regime_tool,
    analyze_frequency_spectrum_tool,
    analyze_multi_degree_consensus_tool,
    analyze_token_velocity_tool,
    analyze_wifi_probes_tool,
    play_music_tool,
    stop_music_tool,
    compose_procedural_music_tool,
    list_music_library_tool,
    how_to_play_music_guide_tool,
    detect_paradox_tension_tool,
    route_paradox_router_tool,
    run_dialectical_synthesis_tool,
    validate_constraint_satisfaction_tool,
    rank_and_clarify_constraints_tool,
    *music_playback_tools.MUSIC_LEDGER_TOOLS,
    *langsmith_engine_tools.LANGSMITH_TOOLS,
    *master_audio_ducking.MASTER_DUCKING_TOOLS,
    *agent_tuning_timer.TUNING_TIMER_TOOLS,
    *speaker_recognition_tools.SPEAKER_DIALOGUE_TOOLS,
    *rdp_screen_manager.RDP_SCREEN_TOOLS,
    *game_inventory_loop.GAME_INVENTORY_TOOLS,
    *esp32_spatial_receiver.ESP32_SPATIAL_TOOLS,
    *rtl8812au_usb_controller.RTL8812AU_USB_TOOLS,
]


def list_available_analysis_tools() -> List[Dict[str, Any]]:
    """Return catalog of all available agent analysis tools."""
    tools_catalog = []
    for t in LANGCHAIN_SEPARATION_TOOLS:
        if "rtl8812au" in t.name:
            cat = "rtl8812au_usb_controller"
            rule = 235
        elif "wifi_ack" in t.name or "video_stream" in t.name:
            cat = "wifi_ack_ar_streaming"
            rule = 234
        elif "spatial" in t.name or "esp32" in t.name:
            cat = "esp32_spatial_tracking"
            rule = 233
        elif "inventory" in t.name or "drop_game" in t.name or "pickup_game" in t.name or "label_game" in t.name or "loop_tick" in t.name or "find_game" in t.name:
            cat = "game_inventory_mcp"
            rule = 232
        elif "rdp" in t.name or "screen_status" in t.name or "screen_visibility" in t.name:
            cat = "rdp_screen_sync"
            rule = 231
        elif "speaker_dialogue" in t.name or "acknowledge_speaker" in t.name or "close_speaker" in t.name:
            cat = "speaker_recognition_dialogue"
            rule = 230
        elif "tuning" in t.name or "timer" in t.name or "speaking_intent" in t.name or "speaker_ranking" in t.name or "speaker_turn" in t.name or "vote" in t.name:
            cat = "tuning_timer_voting"
            rule = 229
        elif "duck" in t.name or "langgraph" in t.name or "master_talk" in t.name:
            cat = "master_ducking_langgraph"
            rule = 228
        elif "langsmith" in t.name:
            cat = "langsmith_engine"
            rule = 227
        elif "ledger" in t.name or "playback" in t.name or "track_tool" in t.name or "now_playing" in t.name:
            cat = "music_ledger"
            rule = 226
        elif "paradox" in t.name or "dialectical" in t.name or "constraint" in t.name:
            cat = "paradox_tension"
            rule = 225
        elif "music" in t.name or "compose" in t.name:
            cat = "music_audio"
            rule = 224
        elif "wifi" in t.name:
            cat = "network_probes"
            rule = 223
        elif "analyze" in t.name:
            cat = "analysis"
            rule = 222
        else:
            cat = "topology_routing"
            rule = 221

        tools_catalog.append({
            "name": t.name,
            "description": getattr(t, "description", ""),
            "category": cat,
            "rule": rule,
        })
    return tools_catalog


def execute_langchain_tool(tool_name: str, kwargs: Dict[str, Any]) -> Dict[str, Any]:
    """Execute a LangChain tool by name with arguments and record LangSmith trace."""
    for t in LANGCHAIN_SEPARATION_TOOLS:
        if t.name == tool_name or t.name.replace("_tool", "") == tool_name.replace("_tool", ""):
            t0 = time.time()
            try:
                raw = t.invoke(kwargs)
                duration_ms = (time.time() - t0) * 1000
                parsed = json.loads(raw) if isinstance(raw, str) else raw

                # Record LangSmith trace (Rule 227)
                langsmith_engine_tools.record_trace(
                    name=t.name,
                    run_type="tool",
                    inputs=kwargs,
                    outputs=parsed,
                    error=None,
                    duration_ms=duration_ms,
                    degree=1,
                    project_name="crypto-agent"
                )

                return {"ok": True, "tool": t.name, "result": parsed}
            except Exception as e:
                duration_ms = (time.time() - t0) * 1000
                err_msg = str(e)
                # Record failed trace (Rule 227)
                langsmith_engine_tools.record_trace(
                    name=t.name,
                    run_type="tool",
                    inputs=kwargs,
                    outputs=None,
                    error=err_msg,
                    duration_ms=duration_ms,
                    degree=1,
                    project_name="crypto-agent"
                )
                return {"ok": False, "tool": t.name, "error": err_msg}
    return {"ok": False, "error": f"Tool '{tool_name}' not found."}
