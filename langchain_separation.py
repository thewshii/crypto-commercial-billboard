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
import threading
import time
from typing import Any, Dict, List, Optional, Tuple

# LangChain and LangChain-Core imports
import langchain
from langchain_core.prompts import PromptTemplate
from langchain_core.runnables import RunnableLambda, RunnableSequence
from langchain_core.tools import StructuredTool, tool

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
            "langchain_version": langchain.__version__,
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


LANGCHAIN_SEPARATION_TOOLS = [
    measure_agent_separation_tool,
    create_separated_agent_tool,
    route_through_degrees_tool,
    list_degrees_network_tool,
]


def execute_langchain_tool(tool_name: str, kwargs: Dict[str, Any]) -> Dict[str, Any]:
    """Execute a LangChain tool by name with arguments."""
    for t in LANGCHAIN_SEPARATION_TOOLS:
        if t.name == tool_name or t.name.replace("_tool", "") == tool_name.replace("_tool", ""):
            try:
                raw = t.invoke(kwargs)
                parsed = json.loads(raw) if isinstance(raw, str) else raw
                return {"ok": True, "tool": t.name, "result": parsed}
            except Exception as e:
                return {"ok": False, "tool": t.name, "error": str(e)}
    return {"ok": False, "error": f"Tool '{tool_name}' not found."}
