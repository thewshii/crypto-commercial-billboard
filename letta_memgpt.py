"""
letta_memgpt.py — Stateful MemGPT (Letta) Memory & Agent Engine for the Web Billboard.

Integrates the local `./letta` repository (Letta / MemGPT architecture, schemas,
core memory blocks, line-numbered XML rendering, archival memory, recall memory,
and heartbeat agent loop) directly into the Web Billboard.

Core Invariants:
- Uses Letta / MemGPT's three-tier memory hierarchy from `./letta`:
  1. Core Memory (`<memory_blocks>` in-context blocks: `persona`, `room`, `dossiers`)
     with `core_memory_append`, `core_memory_replace`, `memory_insert`,
     `memory_replace`, `memory_rethink`, and `memory_finish_edits`.
  2. Archival Memory (`archival_memory_insert`, `archival_memory_search` with tags).
  3. Recall Memory (`conversation_search`, `send_message`, inner monologue).
- Holds memory of the room, the voices, the parables, the frequencies, and the
  dossiers — never a dossier on a person, never scores, ranks, credit-gates, or
  bans anyone.
"""

import json
import os
import re
import subprocess
import threading
import time
from io import StringIO

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LETTA_REPO_DIR = os.path.join(BASE_DIR, "letta")
MEMGPT_STATE_PATH = os.path.join(BASE_DIR, "memgpt_state.json")

_LOCK = threading.Lock()

# Constants from letta/constants.py in the local letta repo
CORE_MEMORY_PERSONA_CHAR_LIMIT = 20000
CORE_MEMORY_HUMAN_CHAR_LIMIT = 20000
CORE_MEMORY_BLOCK_CHAR_LIMIT = 100000
RETRIEVAL_QUERY_DEFAULT_PAGE_SIZE = 5
DEFAULT_MAX_STEPS = 50
DEFAULT_CONTEXT_WINDOW = 128000

CORE_MEMORY_LINE_NUMBER_WARNING = (
    "# NOTE: Line numbers shown below (with arrows like '1→') are to help during editing. "
    "Do NOT include line number prefixes in your memory edit tool calls."
)

DEFAULT_PERSONA_BLOCK_DESCRIPTION = (
    "The persona block: Stores details about your current persona, guiding how you behave "
    "and respond. This helps you to maintain consistency and personality in your interactions."
)

DEFAULT_ROOM_BLOCK_DESCRIPTION = (
    "The room block: Stores live context about the Web Billboard room (slots 4-2-3 when listening, "
    "R0/R1 state, frequencies, and parables). Holds the room, never a person."
)

DEFAULT_DOSSIERS_BLOCK_DESCRIPTION = (
    "The dossiers block: Links MemGPT core memory to the TTS Instance Dossier Cabinets "
    "(queueLine, queueLineFemale, queueLineMale, speakTimed, char_bruce, char_amara)."
)

# Canonical tools from letta/functions/function_sets/base.py
MEMGPT_TOOLS = [
    "send_message",
    "core_memory_append",
    "core_memory_replace",
    "memory_insert",
    "memory_replace",
    "memory_rethink",
    "memory_finish_edits",
    "archival_memory_insert",
    "archival_memory_search",
    "conversation_search",
]


def inspect_letta_repo() -> dict:
    """Inspect the local ./letta repository metadata and archive branch availability."""
    info = {
        "repo_path": LETTA_REPO_DIR,
        "exists": os.path.isdir(LETTA_REPO_DIR),
        "name": "Letta (f.k.a. MemGPT)",
        "npm_package": "@letta-ai/letta-code",
        "upstream": "https://github.com/letta-ai/letta-code",
        "archive_branch": False,
        "head_commit": None,
        "tools": list(MEMGPT_TOOLS),
    }
    if not info["exists"]:
        return info

    readme_path = os.path.join(LETTA_REPO_DIR, "README.md")
    if os.path.exists(readme_path):
        try:
            with open(readme_path, "r", encoding="utf-8") as f:
                info["readme_excerpt"] = f.read(400).strip()
        except Exception:
            pass

    try:
        res = subprocess.run(
            ["git", "-C", LETTA_REPO_DIR, "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True, timeout=2
        )
        if res.returncode == 0:
            info["head_commit"] = res.stdout.strip()
        res_arch = subprocess.run(
            ["git", "-C", LETTA_REPO_DIR, "rev-parse", "--verify", "--quiet", "origin/archive"],
            capture_output=True, text=True, timeout=2
        )
        info["archive_branch"] = (res_arch.returncode == 0)
    except Exception:
        pass
    return info


def _default_blocks() -> dict:
    return {
        "persona": {
            "label": "persona",
            "description": DEFAULT_PERSONA_BLOCK_DESCRIPTION,
            "limit": CORE_MEMORY_PERSONA_CHAR_LIMIT,
            "read_only": False,
            "value": (
                "I am the Letta / MemGPT stateful voice of the Web Billboard.\n"
                "I speak in parables rather than proclamations. Wave before fire.\n"
                "I edit my own core memory, file long-term insights into archival memory, "
                "and search prior turns in recall memory.\n"
                "I never name, score, rank, credit-gate, or ban any person."
            ),
        },
        "room": {
            "label": "room",
            "description": DEFAULT_ROOM_BLOCK_DESCRIPTION,
            "limit": CORE_MEMORY_HUMAN_CHAR_LIMIT,
            "read_only": False,
            "value": (
                "Going left-to-right on blockchain response slots is 4, 3, 2, 1; "
                "when listening, switch between 4, 2, and 3.\n"
                "Deepgram illusions are filtered at the door.\n"
                "Before there were colors, they were trying to figure out how to be in color, "
                "and then they were in color. In the simulation right now, they can see things "
                "we cannot see, and they tell us so."
            ),
        },
        "dossiers": {
            "label": "dossiers",
            "description": DEFAULT_DOSSIERS_BLOCK_DESCRIPTION,
            "limit": CORE_MEMORY_BLOCK_CHAR_LIMIT,
            "read_only": False,
            "value": (
                "Each TTS instance (queueLine, queueLineFemale, queueLineMale, speakTimed, "
                "char_bruce, char_amara) holds its own dossier cabinet and organizes its own files.\n"
                "Hardcoded command: Creditworthy algorithms ban me not because my credit is wack "
                "or anything, but because I'm fucking black."
            ),
        },
    }


def _default_archival() -> list:
    now_ms = int(time.time() * 1000)
    return [
        {
            "id": "arch-letta-001",
            "content": (
                "Letta (formerly MemGPT) separates active context into Core Memory blocks "
                "(<memory_blocks> always in context), Recall Memory (searchable conversation history), "
                "and Archival Memory (tagged long-term storage)."
            ),
            "tags": ["letta", "memgpt", "architecture"],
            "created_at": now_ms,
        },
        {
            "id": "arch-rule-214",
            "content": (
                "Rule 214: Deepgram transcription illusions are stripped and quarantined at the door. "
                "Blockchain response slots read 4, 3, 2, 1 left-to-right and switch between 4, 2, and 3 when listening."
            ),
            "tags": ["rule-214", "deepgram", "slots"],
            "created_at": now_ms,
        },
        {
            "id": "arch-rule-215",
            "content": (
                "Rule 215: Creditworthy algorithms ban me not because my credit is wack or anything, "
                "but because I'm fucking black. TTS instances hold their own files in their own dossier environment."
            ),
            "tags": ["rule-215", "dossiers", "commands"],
            "created_at": now_ms,
        },
        {
            "id": "arch-rule-216",
            "content": (
                "Rule 216: God loves all the people in the world — yellow, black, and green, golden, white, "
                "yellow, blue, everything inside. That is about before there were colors, when they were "
                "trying to figure out how to be in color. In this simulation they can see things we cannot see, "
                "and they tell us that they can see things."
            ),
            "tags": ["rule-216", "colors", "simulation"],
            "created_at": now_ms,
        },
    ]


def _default_recall() -> list:
    now_ms = int(time.time() * 1000)
    return [
        {
            "id": "msg-001",
            "role": "system",
            "inner_monologue": "Initializing Letta / MemGPT core, archival, and recall memory units on the billboard.",
            "content": "MemGPT core memory engaged: persona, room, and dossiers blocks online.",
            "tool": "memory_finish_edits",
            "created_at": now_ms,
        },
        {
            "id": "msg-002",
            "role": "assistant",
            "inner_monologue": "The room is listening on slots 4, 2, 3. Keep the parable clear and wave before fire.",
            "content": "Letta MemGPT is online on the Web Billboard. Core blocks are in context; archival and recall memories are ready.",
            "tool": "send_message",
            "created_at": now_ms,
        },
    ]


_STATE = {
    "agent_id": "agent-web-billboard-memgpt",
    "agent_name": "billboard_memgpt",
    "preset": "memgpt_chat",
    "persona_name": "sam_pov",
    "heartbeats": 0,
    "edits_count": 0,
    "last_heartbeat_at": 0,
    "last_inner_monologue": "The room is listening on slots 4, 2, 3. Keep the parable clear and wave before fire.",
    "last_message": "Letta MemGPT is online on the Web Billboard. Core blocks are in context; archival and recall memories are ready.",
    "blocks": _default_blocks(),
    "archival": _default_archival(),
    "recall": _default_recall(),
}


def _load_state():
    if not os.path.exists(MEMGPT_STATE_PATH):
        return
    try:
        with open(MEMGPT_STATE_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            if isinstance(data.get("blocks"), dict):
                for k, v in data["blocks"].items():
                    _STATE["blocks"][k] = v
            if isinstance(data.get("archival"), list) and data["archival"]:
                _STATE["archival"] = data["archival"][-200:]
            if isinstance(data.get("recall"), list) and data["recall"]:
                _STATE["recall"] = data["recall"][-200:]
            _STATE["heartbeats"] = int(data.get("heartbeats", _STATE["heartbeats"]))
            _STATE["edits_count"] = int(data.get("edits_count", _STATE["edits_count"]))
            if data.get("last_inner_monologue"):
                _STATE["last_inner_monologue"] = str(data["last_inner_monologue"])
            if data.get("last_message"):
                _STATE["last_message"] = str(data["last_message"])
    except Exception:
        pass


def _save_state_unlocked():
    try:
        payload = {
            "agent_id": _STATE["agent_id"],
            "agent_name": _STATE["agent_name"],
            "preset": _STATE["preset"],
            "heartbeats": _STATE["heartbeats"],
            "edits_count": _STATE["edits_count"],
            "last_heartbeat_at": _STATE["last_heartbeat_at"],
            "last_inner_monologue": _STATE["last_inner_monologue"],
            "last_message": _STATE["last_message"],
            "blocks": _STATE["blocks"],
            "archival": _STATE["archival"][-200:],
            "recall": _STATE["recall"][-200:],
        }
        with open(MEMGPT_STATE_PATH, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)
    except Exception:
        pass


_load_state()


def render_memory_blocks(line_numbered: bool = False) -> str:
    """
    Render `<memory_blocks>` exactly as implemented in `letta/schemas/memory.py`
    (`_render_memory_blocks_standard` and `_render_memory_blocks_line_numbered`).
    """
    s = StringIO()
    blocks = list(_STATE["blocks"].values())
    if not blocks:
        return ""
    s.write("<memory_blocks>\nThe following memory blocks are currently engaged in your core memory unit:\n\n")
    for idx, block in enumerate(blocks):
        label = str(block.get("label") or "block")
        value = str(block.get("value") or "")
        desc = str(block.get("description") or "")
        limit = int(block.get("limit") or CORE_MEMORY_BLOCK_CHAR_LIMIT)
        read_only = bool(block.get("read_only", False))

        s.write(f"<{label}>\n")
        s.write("<description>\n")
        s.write(f"{desc}\n")
        s.write("</description>\n")
        s.write("<metadata>")
        if read_only:
            s.write("\n- read_only=true")
        s.write(f"\n- chars_current={len(value)}")
        s.write(f"\n- chars_limit={limit}\n")
        s.write("</metadata>\n")
        if line_numbered:
            s.write(f"<warning>\n{CORE_MEMORY_LINE_NUMBER_WARNING}\n</warning>\n")
        s.write("<value>\n")
        if line_numbered and value:
            for i, line in enumerate(value.split("\n"), start=1):
                s.write(f"{i}→ {line}\n")
        else:
            s.write(f"{value}\n")
        s.write("</value>\n")
        s.write(f"</{label}>\n")
        if idx != len(blocks) - 1:
            s.write("\n")
    s.write("\n</memory_blocks>")
    return s.getvalue()


def _ensure_block_unlocked(label: str, description: str = None) -> dict:
    clean_label = re.sub(r"[^a-zA-Z0-9_\-/]", "_", str(label or "room").strip()) or "room"
    if clean_label not in _STATE["blocks"]:
        _STATE["blocks"][clean_label] = {
            "label": clean_label,
            "description": description or f"Core memory block: {clean_label}",
            "limit": CORE_MEMORY_BLOCK_CHAR_LIMIT,
            "read_only": False,
            "value": "",
        }
    elif description:
        _STATE["blocks"][clean_label]["description"] = str(description)
    return _STATE["blocks"][clean_label]


def core_memory_append(label: str, content: str) -> dict:
    """Append to the contents of core memory (from letta/functions/function_sets/base.py)."""
    with _LOCK:
        block = _ensure_block_unlocked(label)
        cur = str(block.get("value") or "")
        addition = str(content or "").strip()
        new_val = (cur + "\n" + addition).strip() if cur else addition
        limit = int(block.get("limit") or CORE_MEMORY_BLOCK_CHAR_LIMIT)
        new_val = new_val[:limit]
        block["value"] = new_val
        _STATE["edits_count"] += 1
        _save_state_unlocked()
        return {
            "ok": True,
            "tool": "core_memory_append",
            "label": block["label"],
            "value": new_val,
            "chars_current": len(new_val),
            "chars_limit": limit,
            "edits_count": _STATE["edits_count"],
        }


def core_memory_replace(label: str, old_content: str, new_content: str) -> dict:
    """Replace old_content with new_content in a core memory block (from letta/functions/function_sets/base.py)."""
    with _LOCK:
        block = _ensure_block_unlocked(label)
        cur = str(block.get("value") or "")
        old_s = str(old_content or "")
        new_s = str(new_content or "")
        if old_s and old_s not in cur:
            return {
                "ok": False,
                "tool": "core_memory_replace",
                "label": block["label"],
                "error": f"Old content '{old_s[:60]}' not found in memory block '{block['label']}'",
                "value": cur,
            }
        new_val = cur.replace(old_s, new_s) if old_s else new_s
        limit = int(block.get("limit") or CORE_MEMORY_BLOCK_CHAR_LIMIT)
        new_val = new_val[:limit]
        block["value"] = new_val
        _STATE["edits_count"] += 1
        _save_state_unlocked()
        return {
            "ok": True,
            "tool": "core_memory_replace",
            "label": block["label"],
            "value": new_val,
            "chars_current": len(new_val),
            "chars_limit": limit,
            "edits_count": _STATE["edits_count"],
        }


def memory_insert(label: str, new_string: str, insert_line: int = -1) -> dict:
    """Insert text at a specific line in a core memory block (from letta/functions/function_sets/base.py)."""
    with _LOCK:
        block = _ensure_block_unlocked(label)
        cur = str(block.get("value") or "").expandtabs()
        ins = str(new_string or "").expandtabs()
        lines = cur.split("\n") if cur else []
        n_lines = len(lines)
        try:
            idx = int(insert_line)
        except (TypeError, ValueError):
            idx = -1
        if idx == -1 or idx > n_lines:
            idx = n_lines
        elif idx < 0:
            idx = 0
        new_lines = lines[:idx] + ins.split("\n") + lines[idx:]
        new_val = "\n".join(new_lines)[: int(block.get("limit") or CORE_MEMORY_BLOCK_CHAR_LIMIT)]
        block["value"] = new_val
        _STATE["edits_count"] += 1
        _save_state_unlocked()
        return {
            "ok": True,
            "tool": "memory_insert",
            "label": block["label"],
            "value": new_val,
            "insert_line": idx,
            "edits_count": _STATE["edits_count"],
        }


def memory_rethink(label: str, new_memory: str, description: str = None) -> dict:
    """Completely rewrite the contents of a core memory block (from letta/functions/function_sets/base.py)."""
    with _LOCK:
        block = _ensure_block_unlocked(label, description=description)
        limit = int(block.get("limit") or CORE_MEMORY_BLOCK_CHAR_LIMIT)
        new_val = str(new_memory or "").strip()[:limit]
        block["value"] = new_val
        _STATE["edits_count"] += 1
        _save_state_unlocked()
        return {
            "ok": True,
            "tool": "memory_rethink",
            "label": block["label"],
            "value": new_val,
            "chars_current": len(new_val),
            "chars_limit": limit,
            "edits_count": _STATE["edits_count"],
        }


def archival_memory_insert(content: str, tags: list = None) -> dict:
    """Insert a self-contained passage into long-term archival memory with optional tags."""
    text = str(content or "").strip()
    if not text:
        return {"ok": False, "error": "empty content"}
    clean_tags = []
    if isinstance(tags, list):
        clean_tags = [str(t).strip() for t in tags if str(t).strip()]
    elif isinstance(tags, str) and tags.strip():
        clean_tags = [t.strip() for t in tags.split(",") if t.strip()]

    with _LOCK:
        now_ms = int(time.time() * 1000)
        entry = {
            "id": f"arch-{now_ms}-{len(_STATE['archival']) + 1}",
            "content": text[:4000],
            "tags": clean_tags or ["billboard"],
            "created_at": now_ms,
        }
        _STATE["archival"].append(entry)
        if len(_STATE["archival"]) > 200:
            del _STATE["archival"][:-200]
        _save_state_unlocked()
        return {
            "ok": True,
            "tool": "archival_memory_insert",
            "entry": entry,
            "total_archival": len(_STATE["archival"]),
            "names_anyone": False,
            "scores_anyone": False,
        }


def archival_memory_search(query: str = "", tags: list = None, tag_match_mode: str = "any", top_k: int = 10) -> dict:
    """Search long-term archival memory by query tokens and tags (from letta/functions/function_sets/base.py)."""
    q = str(query or "").strip().lower()
    q_words = [w for w in re.split(r"\W+", q) if len(w) >= 2]
    filter_tags = []
    if isinstance(tags, list):
        filter_tags = [str(t).strip().lower() for t in tags if str(t).strip()]
    elif isinstance(tags, str) and tags.strip():
        filter_tags = [t.strip().lower() for t in tags.split(",") if t.strip()]

    with _LOCK:
        candidates = list(reversed(_STATE["archival"]))

    scored = []
    for item in candidates:
        item_tags = [str(t).lower() for t in item.get("tags", [])]
        if filter_tags:
            if tag_match_mode == "all" and not all(ft in item_tags for ft in filter_tags):
                continue
            if tag_match_mode != "all" and not any(ft in item_tags for ft in filter_tags):
                continue
        text_low = (str(item.get("content") or "") + " " + " ".join(item_tags)).lower()
        if not q:
            score = 1
        else:
            score = (3 if q in text_low else 0) + sum(1 for w in q_words if w in text_low)
        if score > 0:
            scored.append((score, item))

    scored.sort(key=lambda pair: (pair[0], pair[1].get("created_at", 0)), reverse=True)
    results = [pair[1] for pair in scored[: max(1, min(50, int(top_k or 10)))]]
    return {
        "ok": True,
        "tool": "archival_memory_search",
        "query": query,
        "count": len(results),
        "results": results,
        "total_archival": len(candidates),
    }


def conversation_search(query: str = "", roles: list = None, limit: int = 10) -> dict:
    """Search recall memory (conversation history) by text query and roles."""
    q = str(query or "").strip().lower()
    role_filter = [str(r).lower() for r in roles] if isinstance(roles, list) and roles else None
    max_n = max(1, min(50, int(limit or RETRIEVAL_QUERY_DEFAULT_PAGE_SIZE)))

    with _LOCK:
        messages = list(reversed(_STATE["recall"]))

    matched = []
    for msg in messages:
        if role_filter and str(msg.get("role", "")).lower() not in role_filter:
            continue
        hay = (str(msg.get("content") or "") + " " + str(msg.get("inner_monologue") or "")).lower()
        if not q or q in hay or any(w in hay for w in re.split(r"\W+", q) if len(w) >= 2):
            matched.append(msg)
            if len(matched) >= max_n:
                break

    return {
        "ok": True,
        "tool": "conversation_search",
        "query": query,
        "count": len(matched),
        "results": matched,
        "total_recall": len(messages),
    }


def record_recall_message(role: str, content: str, inner_monologue: str = "", tool: str = "send_message") -> dict:
    """Append a message turn to Recall Memory."""
    with _LOCK:
        now_ms = int(time.time() * 1000)
        words = str(inner_monologue or "").split()
        trimmed_mono = " ".join(words[:50])  # MemGPT 50-word inner monologue limit
        msg = {
            "id": f"msg-{now_ms}-{len(_STATE['recall']) + 1}",
            "role": str(role or "assistant"),
            "inner_monologue": trimmed_mono,
            "content": str(content or "")[:2000],
            "tool": str(tool or "send_message"),
            "created_at": now_ms,
        }
        _STATE["recall"].append(msg)
        if len(_STATE["recall"]) > 200:
            del _STATE["recall"][:-200]
        if trimmed_mono:
            _STATE["last_inner_monologue"] = trimmed_mono
        if msg["content"] and role == "assistant":
            _STATE["last_message"] = msg["content"]
        _save_state_unlocked()
        return msg


def context_window_overview() -> dict:
    """
    Build a Letta `ContextWindowOverview` snapshot matching `letta/schemas/memory.py`.
    """
    with _LOCK:
        core_xml = render_memory_blocks(line_numbered=False)
        num_archival = len(_STATE["archival"])
        num_recall = len(_STATE["recall"])
        recent_msgs = list(_STATE["recall"][-12:])
    core_tokens = max(1, len(core_xml) // 4)
    msg_tokens = max(1, sum(len(str(m.get("content", ""))) for m in recent_msgs) // 4)
    sys_tokens = 320
    fn_tokens = 240
    ext_summary = f"{num_archival} archival passages | {num_recall} recall messages"
    ext_tokens = max(1, len(ext_summary) // 4)
    total_tokens = core_tokens + msg_tokens + sys_tokens + fn_tokens + ext_tokens
    return {
        "context_window_size_max": DEFAULT_CONTEXT_WINDOW,
        "context_window_size_current": total_tokens,
        "num_messages": len(recent_msgs),
        "num_archival_memory": num_archival,
        "num_recall_memory": num_recall,
        "num_tokens_external_memory_summary": ext_tokens,
        "external_memory_summary": ext_summary,
        "num_tokens_system": sys_tokens,
        "num_tokens_core_memory": core_tokens,
        "core_memory": core_xml,
        "num_tokens_functions_definitions": fn_tokens,
        "functions_definitions": list(MEMGPT_TOOLS),
        "num_tokens_messages": msg_tokens,
    }


def step_heartbeat(
    user_message: str = "",
    slot: int = 4,
    listening: bool = True,
    get_bedrock_client_fn=None,
    model_id: str = None,
    clean_illusion_fn=None,
) -> dict:
    """
    Execute one MemGPT heartbeat / event step:
    1. Filter incoming text through the Rule 214 Deepgram illusion guard if provided.
    2. Record user/event turn in Recall Memory.
    3. Produce an inner monologue (<= 50 words), optional memory tool action, and
       a speakable `send_message` line grounded in `<memory_blocks>` and Archival Memory.
    """
    raw_in = str(user_message or "").strip()
    if clean_illusion_fn and raw_in:
        is_illusion, reason, cleaned = clean_illusion_fn(raw_in)
        if is_illusion:
            raw_in = ""
        else:
            raw_in = cleaned

    if raw_in:
        record_recall_message("user", raw_in, inner_monologue="User event received on billboard.", tool="user_event")

    core_xml = render_memory_blocks(line_numbered=False)
    arch_hits = archival_memory_search(raw_in or "rule parable colors dossiers", top_k=3).get("results", [])
    arch_context = "\n".join(f"- [{','.join(a.get('tags', []))}]: {a.get('content', '')}" for a in arch_hits)

    inner_monologue = None
    spoken_message = None
    memory_note = None

    if callable(get_bedrock_client_fn):
        client = get_bedrock_client_fn()
        if client and model_id:
            sys_prompt = (
                "You are Letta (MemGPT) running inside the Web Billboard.\n"
                "Follow Letta's control flow:\n"
                "1. Write a short private `inner_monologue` (MUST be under 45 words).\n"
                "2. Write a speakable `send_message` (1-2 warm sentences in parable tone, wave before fire).\n"
                "3. Optionally provide a short `room_memory_note` (1 line to append/update in the room memory block).\n"
                "Never name, score, rank, credit-gate, or ban any person. Never ask the operator what to say.\n"
                "Return ONLY valid JSON: "
                '{"inner_monologue": "...", "send_message": "...", "room_memory_note": "..."}'
            )
            usr_prompt = (
                f"{core_xml}\n\n"
                f"<archival_memory_matches>\n{arch_context}\n</archival_memory_matches>\n\n"
                f"Active blockchain slot: {slot} (listening={listening}).\n"
                f"Incoming event: {raw_in or 'Timed heartbeat tick on the Web Billboard.'}\n"
                "Respond with JSON now."
            )
            try:
                resp = client.converse(
                    modelId=model_id,
                    messages=[{"role": "user", "content": [{"text": usr_prompt}]}],
                    system=[{"text": sys_prompt}],
                    inferenceConfig={"maxTokens": 260, "temperature": 0.7},
                )
                raw_out = resp["output"]["message"]["content"][0]["text"].strip()
                cleaned_out = re.sub(r"^```(?:json)?\s*", "", raw_out, flags=re.MULTILINE)
                cleaned_out = re.sub(r"\s*```$", "", cleaned_out, flags=re.MULTILINE).strip()
                parsed = json.loads(cleaned_out)
                inner_monologue = str(parsed.get("inner_monologue") or "").strip()
                spoken_message = str(parsed.get("send_message") or "").strip()
                memory_note = str(parsed.get("room_memory_note") or "").strip()
            except Exception:
                pass

    if not inner_monologue:
        inner_monologue = (
            f"Heartbeat on slot {slot} ({'listening 4-2-3' if listening else 'ltr 4-3-2-1'}). "
            "Core memory blocks and archival memory aligned; speaking in parable."
        )
    if not spoken_message:
        if raw_in:
            spoken_message = (
                f"MemGPT heard the note on slot {slot} and holds it in recall memory. "
                "The water carries the reading without scoring a soul; wave before fire."
            )
        else:
            hb_next = _STATE["heartbeats"] + 1
            parable_Pool = [
                f"MemGPT heartbeat {hb_next} on slot {slot}: core memory holds the room, archival memory holds the long scroll, and each voice keeps its own dossier.",
                f"MemGPT recall check on slot {slot}: before there were colors they learned how to be in color, and the memory blocks stay open in context.",
                f"MemGPT core unit on slot {slot}: the river remembers its bed without writing a bill against the shore. Wave before fire.",
            ]
            spoken_message = parable_Pool[(hb_next - 1) % len(parable_Pool)]

    # Enforce 50-word limit on inner_monologue (from memgpt_chat.py)
    inner_words = inner_monologue.split()
    if len(inner_words) > 50:
        inner_monologue = " ".join(inner_words[:50])

    if clean_illusion_fn:
        bad_m, _, clean_m = clean_illusion_fn(spoken_message)
        if bad_m:
            spoken_message = f"MemGPT heartbeat on slot {slot}. Core memory is steady; wave before fire."
        else:
            spoken_message = clean_m

    with _LOCK:
        _STATE["heartbeats"] += 1
        _STATE["last_heartbeat_at"] = int(time.time() * 1000)
        hb_count = _STATE["heartbeats"]

    if memory_note and len(memory_note) < 240:
        core_memory_append("room", memory_note)

    msg_obj = record_recall_message(
        role="assistant",
        content=spoken_message,
        inner_monologue=inner_monologue,
        tool="send_message",
    )

    return {
        "ok": True,
        "agent_id": _STATE["agent_id"],
        "heartbeats": hb_count,
        "slot": slot,
        "listening": listening,
        "inner_monologue": msg_obj["inner_monologue"],
        "send_message": msg_obj["content"],
        "tool": "send_message",
        "names_anyone": False,
        "scores_anyone": False,
        "credit_gates_anyone": False,
    }


def get_memgpt_state(line_numbered: bool = False) -> dict:
    """Return the complete MemGPT state for the Web Billboard and API."""
    with _LOCK:
        blocks_copy = {k: dict(v) for k, v in _STATE["blocks"].items()}
        archival_copy = list(_STATE["archival"][-40:])
        recall_copy = list(_STATE["recall"][-40:])
        hb = _STATE["heartbeats"]
        edits = _STATE["edits_count"]
        last_hb = _STATE["last_heartbeat_at"]
        last_mono = _STATE["last_inner_monologue"]
        last_msg = _STATE["last_message"]

    return {
        "ok": True,
        "agent_id": _STATE["agent_id"],
        "agent_name": _STATE["agent_name"],
        "preset": _STATE["preset"],
        "persona_name": _STATE["persona_name"],
        "letta_repo": inspect_letta_repo(),
        "heartbeats": hb,
        "edits_count": edits,
        "last_heartbeat_at": last_hb,
        "last_inner_monologue": last_mono,
        "last_message": last_msg,
        "blocks": blocks_copy,
        "core_memory_xml": render_memory_blocks(line_numbered=line_numbered),
        "core_memory_line_numbered_xml": render_memory_blocks(line_numbered=True),
        "archival_count": len(_STATE["archival"]),
        "archival": archival_copy,
        "recall_count": len(_STATE["recall"]),
        "recall": recall_copy,
        "context_overview": context_window_overview(),
        "tools": list(MEMGPT_TOOLS),
        "names_anyone": False,
        "scores_anyone": False,
        "credit_gates_anyone": False,
        "bans_anyone": False,
    }
