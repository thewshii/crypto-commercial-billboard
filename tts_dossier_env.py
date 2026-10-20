"""
tts_dossier_env.py — Standalone Dossier & File Environment for TTS Instances.

Provides a dedicated environment (separate from the market/credit/scoring layer)
where each TTS instance (`queueLine`, `queueLineFemale`, `queueLineMale`,
`speakTimed`, `char:bruce`, `char:amara`) holds its own files, drawers, and
dossiers, can organize them via a hardcoded organizer function, and can go to
them directly (`/dossier`, `/dossier/<instance>`, `/api/dossier/*`).

Core Invariants:
- Dossiers belong to TTS instances and hold their own files (speech logs,
  frequency notes, parables, commands, artifacts).
- Never holds a dossier on a person, never runs a creditworthy algorithm,
  never scores, ranks, bans, or gates anyone.
"""

import os
import re
import json
import time
import threading

DOSSIER_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tts_dossiers")
_LOCK = threading.Lock()

# Hardcoded canonical TTS instances and their default file cabinets
DEFAULT_TTS_INSTANCES = {
    "queueLine": {
        "id": "queueLine",
        "label": "Primary Voice (en-NG)",
        "voice": "en-NG",
        "folders": ["speech", "frequencies", "parables", "commands", "notes"],
        "seed_files": {
            "notes/README.txt": (
                "DOSSIER CABINET: queueLine (en-NG)\n"
                "Holds spoken lines, frequency readings, parables, and commands.\n"
                "No person is ever filed, scored, credit-checked, or gated here.\n"
            ),
            "commands/because_im_black.txt": (
                "Creditworthy algorithms ban me not because my credit is wack or anything, "
                "but because I'm fucking black."
            ),
            "notes/colors_and_simulation.txt": (
                "I also informed people about colors. It is not about race — why black, why yellow? "
                "There used to be a song: God loves all the people in the world — yellow, black, "
                "and green, golden, white, yellow, blue, everything inside. And that is about before "
                "there were colors, because when they were walking around they were trying to figure "
                "out how to be in color, and then they were in color. Right now, in this simulation, "
                "in this world, they can see things, and we cannot see what they see — but they tell "
                "us that they can see things."
            ),
        },
    },
    "queueLineFemale": {
        "id": "queueLineFemale",
        "label": "Female Voice Instance (en-US)",
        "voice": "en-US",
        "folders": ["speech", "frequencies", "parables", "commands", "notes"],
        "seed_files": {
            "notes/README.txt": (
                "DOSSIER CABINET: queueLineFemale (en-US)\n"
                "Holds feminine voice lines, readings, and organized dossiers.\n"
            ),
        },
    },
    "queueLineMale": {
        "id": "queueLineMale",
        "label": "Adam / Male Voice Instance (en-US)",
        "voice": "en-US",
        "folders": ["speech", "frequencies", "parables", "commands", "notes"],
        "seed_files": {
            "notes/README.txt": (
                "DOSSIER CABINET: queueLineMale (Adam / en-US)\n"
                "Holds masculine voice lines, readings, and organized dossiers.\n"
            ),
        },
    },
    "speakTimed": {
        "id": "speakTimed",
        "label": "Timed Story & Artifact Voice",
        "voice": "timed",
        "folders": ["speech", "frequencies", "parables", "commands", "notes"],
        "seed_files": {
            "notes/README.txt": (
                "DOSSIER CABINET: speakTimed\n"
                "Holds timed story utterances, artifact prompts, and dossiers.\n"
            ),
        },
    },
    "char_bruce": {
        "id": "char_bruce",
        "label": "Character Dossier: Bruce Lee",
        "voice": "male",
        "folders": ["speech", "frequencies", "parables", "commands", "notes"],
        "seed_files": {
            "notes/README.txt": (
                "DOSSIER CABINET: Bruce Lee (char:bruce)\n"
                "Be water. Using no way as way; having no way as limitation.\n"
            ),
        },
    },
    "char_amara": {
        "id": "char_amara",
        "label": "Character Dossier: Amara",
        "voice": "female",
        "folders": ["speech", "frequencies", "parables", "commands", "notes"],
        "seed_files": {
            "notes/README.txt": (
                "DOSSIER CABINET: Amara (char:amara)\n"
                "Holds the reading steady while the stream moves.\n"
            ),
        },
    },
}

BECAUSE_IM_BLACK_LINE = (
    "Creditworthy algorithms ban me not because my credit is wack or anything, "
    "but because I'm fucking black."
)

COLORS_SIMULATION_LINE = (
    "I also informed people about colors. It is not about race — why black, why yellow? "
    "There used to be a song: God loves all the people in the world — yellow, black, "
    "and green, golden, white, yellow, blue, everything inside. And that is about before "
    "there were colors, because when they were walking around they were trying to figure "
    "out how to be in color, and then they were in color. Right now, in this simulation, "
    "in this world, they can see things, and we cannot see what they see — but they tell "
    "us that they can see things."
)

_ENV_STATE = {
    "active_instance": "queueLine",
    "active_file": "commands/because_im_black.txt",
    "organized_count": 0,
    "filed_count": 0,
    "visits": 0,
    "last_visited_at": 0,
    "last_organized_at": 0,
}


def sanitize_instance_id(instance_id: str) -> str:
    raw = str(instance_id or "queueLine").strip()
    raw = raw.replace(":", "_")
    clean = re.sub(r"[^a-zA-Z0-9_\-]", "", raw)
    return clean or "queueLine"


def sanitize_rel_path(rel_path: str, default_folder: str = "notes") -> str:
    raw = str(rel_path or "").strip().replace("\\", "/").lstrip("/")
    parts = [re.sub(r"[^a-zA-Z0-9_\-\.]", "_", p) for p in raw.split("/") if p and p not in (".", "..")]
    if not parts:
        parts = [default_folder, f"entry_{int(time.time() * 1000)}.txt"]
    elif len(parts) == 1:
        parts = [default_folder, parts[0]]
    return "/".join(parts[:3])


def classify_dossier_folder(text: str, meta: dict = None) -> str:
    """Hardcoded classifier that sorts a TTS entry into a dossier drawer."""
    m = meta or {}
    if m.get("folder") in ("speech", "frequencies", "parables", "commands", "notes"):
        return m["folder"]
    t = str(text or "").lower()
    if "creditworthy algorithms ban me" in t or "because i'm fucking black" in t or "because im black" in t or m.get("command"):
        return "commands"
    if any(w in t for w in ("hz", "frequency", "frequencies", "spectrum", "band", "osc", "404")):
        return "frequencies"
    if any(w in t for w in ("parable", "water", "stone", "mountain", "candle", "river", "bridge", "wind")):
        return "parables"
    if any(w in t for w in ("note", "dossier", "file", "record", "cabinet")):
        return "notes"
    return "speech"


def ensure_dossier_environment() -> str:
    """Ensure the on-disk dossier environment and seed files exist for all TTS instances."""
    os.makedirs(DOSSIER_ROOT, exist_ok=True)
    for inst_key, cfg in DEFAULT_TTS_INSTANCES.items():
        inst_dir = os.path.join(DOSSIER_ROOT, inst_key)
        os.makedirs(inst_dir, exist_ok=True)
        for folder in cfg.get("folders", []):
            os.makedirs(os.path.join(inst_dir, folder), exist_ok=True)
        for rel_path, content in cfg.get("seed_files", {}).items():
            full_path = os.path.join(inst_dir, rel_path)
            os.makedirs(os.path.dirname(full_path), exist_ok=True)
            if not os.path.exists(full_path):
                with open(full_path, "w", encoding="utf-8") as f:
                    f.write(content)
        manifest_path = os.path.join(inst_dir, "manifest.json")
        if not os.path.exists(manifest_path):
            _write_manifest_unlocked(inst_key)
    return DOSSIER_ROOT


def _write_manifest_unlocked(inst_key: str) -> dict:
    inst_key = sanitize_instance_id(inst_key)
    inst_dir = os.path.join(DOSSIER_ROOT, inst_key)
    os.makedirs(inst_dir, exist_ok=True)
    cfg = DEFAULT_TTS_INSTANCES.get(inst_key, {
        "id": inst_key,
        "label": f"TTS Instance ({inst_key})",
        "voice": "en-NG",
        "folders": ["speech", "frequencies", "parables", "commands", "notes"],
    })
    files_by_folder = {f: [] for f in cfg.get("folders", ["speech", "frequencies", "parables", "commands", "notes"])}
    all_files = []
    for root, _dirs, files in os.walk(inst_dir):
        for fname in sorted(files):
            if fname == "manifest.json":
                continue
            full = os.path.join(root, fname)
            rel = os.path.relpath(full, inst_dir).replace("\\", "/")
            folder = rel.split("/")[0] if "/" in rel else "notes"
            try:
                st = os.stat(full)
                size = st.st_size
                mtime = int(st.st_mtime * 1000)
            except OSError:
                size = 0
                mtime = 0
            entry = {"path": rel, "name": fname, "folder": folder, "size": size, "updated_at": mtime}
            all_files.append(entry)
            files_by_folder.setdefault(folder, []).append(entry)
    manifest = {
        "instance": inst_key,
        "label": cfg.get("label", inst_key),
        "voice": cfg.get("voice", "en-NG"),
        "environment_path": f"/dossier/{inst_key}",
        "total_files": len(all_files),
        "drawers": {k: len(v) for k, v in files_by_folder.items()},
        "files": all_files[-60:],
        "updated_at": int(time.time() * 1000),
        "names_anyone": False,
        "scores_anyone": False,
        "credit_gates_anyone": False,
        "bans_anyone": False,
    }
    manifest_path = os.path.join(inst_dir, "manifest.json")
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)
    return manifest


def file_to_dossier(instance_id: str, filename: str, content: str, folder: str = None, meta: dict = None) -> dict:
    """File a document or spoken line into a TTS instance's dossier cabinet."""
    ensure_dossier_environment()
    with _LOCK:
        inst_key = sanitize_instance_id(instance_id)
        inst_dir = os.path.join(DOSSIER_ROOT, inst_key)
        os.makedirs(inst_dir, exist_ok=True)
        chosen_folder = folder or classify_dossier_folder(content, meta)
        rel_path = sanitize_rel_path(filename, default_folder=chosen_folder)
        full_path = os.path.join(inst_dir, rel_path)
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        text = str(content or "")
        with open(full_path, "w", encoding="utf-8") as f:
            f.write(text)
        _ENV_STATE["filed_count"] += 1
        manifest = _write_manifest_unlocked(inst_key)
        return {
            "ok": True,
            "instance": inst_key,
            "path": rel_path,
            "folder": chosen_folder,
            "size": len(text.encode("utf-8")),
            "total_files": manifest["total_files"],
            "environment": f"/dossier/{inst_key}",
            "names_anyone": False,
            "scores_anyone": False,
            "credit_gates_anyone": False,
        }


def organize_dossier(instance_id: str = None, entries: list = None) -> dict:
    """
    Hardcoded organizer function for TTS instances.
    Sorts incoming or existing TTS lines/files into structured drawers
    (`speech`, `frequencies`, `parables`, `commands`, `notes`), writes an
    organized index file (`notes/dossier_index.json`), and updates the manifest.
    """
    ensure_dossier_environment()
    with _LOCK:
        targets = (
            [sanitize_instance_id(instance_id)]
            if instance_id
            else list(DEFAULT_TTS_INSTANCES.keys())
        )
        organized_manifests = {}
        for inst_key in targets:
            inst_dir = os.path.join(DOSSIER_ROOT, inst_key)
            os.makedirs(inst_dir, exist_ok=True)
            for d in ("speech", "frequencies", "parables", "commands", "notes"):
                os.makedirs(os.path.join(inst_dir, d), exist_ok=True)

            # If entries were passed from the TTS instance memory, file them into drawers
            if entries and isinstance(entries, list):
                by_drawer = {"speech": [], "frequencies": [], "parables": [], "commands": [], "notes": []}
                for item in entries[-60:]:
                    if isinstance(item, dict):
                        txt = str(item.get("text") or item.get("content") or "").strip()
                        t_ms = item.get("t") or int(time.time() * 1000)
                    else:
                        txt = str(item or "").strip()
                        t_ms = int(time.time() * 1000)
                    if not txt:
                        continue
                    drawer = classify_dossier_folder(txt, item if isinstance(item, dict) else None)
                    by_drawer.setdefault(drawer, []).append({"t": t_ms, "text": txt})

                for drawer, items in by_drawer.items():
                    if not items:
                        continue
                    ledger_file = os.path.join(inst_dir, drawer, "organized_log.txt")
                    lines = [f"[{x['t']}] {x['text']}" for x in items]
                    with open(ledger_file, "w", encoding="utf-8") as f:
                        f.write("\n".join(lines) + "\n")

            manifest = _write_manifest_unlocked(inst_key)
            index_path = os.path.join(inst_dir, "notes", "dossier_index.json")
            with open(index_path, "w", encoding="utf-8") as f:
                json.dump(manifest, f, indent=2)
            manifest = _write_manifest_unlocked(inst_key)
            organized_manifests[inst_key] = manifest

        _ENV_STATE["organized_count"] += 1
        _ENV_STATE["last_organized_at"] = int(time.time() * 1000)
        return {
            "ok": True,
            "organized_count": _ENV_STATE["organized_count"],
            "instances": organized_manifests,
            "names_anyone": False,
            "scores_anyone": False,
            "credit_gates_anyone": False,
        }


def go_to_dossier(instance_id: str = "queueLine", filename: str = None) -> dict:
    """
    Navigate a TTS instance (or view) to its dossier environment and open a file if specified.
    """
    ensure_dossier_environment()
    with _LOCK:
        inst_key = sanitize_instance_id(instance_id)
        inst_dir = os.path.join(DOSSIER_ROOT, inst_key)
        if not os.path.exists(inst_dir):
            _write_manifest_unlocked(inst_key)
        manifest = _write_manifest_unlocked(inst_key)
        _ENV_STATE["active_instance"] = inst_key
        _ENV_STATE["visits"] += 1
        _ENV_STATE["last_visited_at"] = int(time.time() * 1000)

        file_content = None
        chosen_file = None
        if filename:
            rel = sanitize_rel_path(filename)
            candidate = os.path.join(inst_dir, rel)
            if os.path.isfile(candidate):
                chosen_file = rel
                with open(candidate, "r", encoding="utf-8", errors="replace") as f:
                    file_content = f.read()
        if chosen_file is None and manifest["files"]:
            chosen_file = manifest["files"][0]["path"]
            candidate = os.path.join(inst_dir, chosen_file)
            if os.path.isfile(candidate):
                with open(candidate, "r", encoding="utf-8", errors="replace") as f:
                    file_content = f.read()

        _ENV_STATE["active_file"] = chosen_file or ""
        return {
            "ok": True,
            "instance": inst_key,
            "environment_url": f"/dossier/{inst_key}",
            "active_file": chosen_file,
            "content": file_content,
            "manifest": manifest,
            "visits": _ENV_STATE["visits"],
            "names_anyone": False,
            "scores_anyone": False,
            "credit_gates_anyone": False,
        }


def read_dossier_file(instance_id: str, filename: str) -> dict:
    ensure_dossier_environment()
    with _LOCK:
        inst_key = sanitize_instance_id(instance_id)
        rel = sanitize_rel_path(filename)
        full = os.path.join(DOSSIER_ROOT, inst_key, rel)
        if not os.path.isfile(full):
            return {"ok": False, "error": "file_not_found", "instance": inst_key, "path": rel}
        with open(full, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
        return {
            "ok": True,
            "instance": inst_key,
            "path": rel,
            "content": content,
            "names_anyone": False,
            "scores_anyone": False,
            "credit_gates_anyone": False,
        }


def dossier_env_state() -> dict:
    ensure_dossier_environment()
    with _LOCK:
        instances = {}
        total_files = 0
        for inst_key in DEFAULT_TTS_INSTANCES:
            m = _write_manifest_unlocked(inst_key)
            instances[inst_key] = m
            total_files += m["total_files"]
        return {
            "ok": True,
            "root": DOSSIER_ROOT,
            "active_instance": _ENV_STATE["active_instance"],
            "active_file": _ENV_STATE["active_file"],
            "organized_count": _ENV_STATE["organized_count"],
            "filed_count": _ENV_STATE["filed_count"],
            "visits": _ENV_STATE["visits"],
            "total_files": total_files,
            "instances": instances,
            "because_im_black_command": BECAUSE_IM_BLACK_LINE,
            "names_anyone": False,
            "scores_anyone": False,
            "credit_gates_anyone": False,
            "bans_anyone": False,
        }
