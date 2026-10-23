#!/usr/bin/env python3
"""
game_inventory_loop.py — In-Game Matrix Inventory & Drop Tracker CLI with Model Context Protocol (MCP) & LangChain Tools.

Rule 232: The Game Inventory Loop Model Context Protocol (MCP), LangChain Tools, and LLM Web Billboard Interface.

Mechanics:
1. Manages items across states:
   - ON_PERSON: Equipped, worn, or in pockets.
   - WITHIN_REACH: Nearby on a table, shelf, or arm's length.
   - DROPPED: Fallen from the person or surface into the room area.
2. Drop Event & Inventory Audit:
   - When an item drops, an automatic inventory check runs immediately.
   - Triggers an in-game discussion/dialogue about where the item was,
     where it landed, and its spatial context before committing its label.
3. Persistent Labeled Locations:
   - Remembers and updates item position labels in `game_inventory_state.json`.
4. Model Context Protocol (MCP) for LLMs:
   - Standard JSON-RPC 2.0 MCP interface (`initialize`, `tools/list`, `tools/call`,
     `resources/list`, `resources/read`, `prompts/list`, `prompts/get`).
   - Stdio transport for external LLM clients (`python3 game_inventory_loop.py --mcp`).
   - HTTP/SSE endpoints on Web Billboard for browser & network agentic execution.
5. LangChain Integration:
   - StructuredTools (`audit_game_inventory_tool`, `drop_game_item_tool`, `pickup_game_item_tool`,
     `label_game_item_tool`, `find_game_item_tool`, `inventory_loop_tick_tool`).
   - Registered in `LANGCHAIN_SEPARATION_TOOLS` under rule 232.
"""

import json
import os
import sys
import time
import threading
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field
from langchain_core.tools import StructuredTool

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATE_PATH = os.path.join(BASE_DIR, "game_inventory_state.json")

_INV_LOCK = threading.RLock()

DEFAULT_STATE: Dict[str, Any] = {
    "version": "1.0.0",
    "last_updated": int(time.time()),
    "on_person": [
        {"id": "comms_phone", "name": "Comms Phone", "label": "Right Pocket", "reach": "on_person"},
        {"id": "matrix_keyring", "name": "Matrix Keyring", "label": "Belt Loop Carabiner", "reach": "on_person"},
        {"id": "access_card", "name": "Sovereign Access Card", "label": "Jacket Inner Sleeve", "reach": "on_person"},
    ],
    "within_reach": [
        {"id": "field_journal", "name": "Field Notebook & Pen", "label": "Desk Center-Left", "reach": "within_reach"},
        {"id": "water_flask", "name": "Water Flask", "label": "Nightstand Top Surface", "reach": "within_reach"},
        {"id": "net_dongle", "name": "Wi-Fi Network Dongle", "label": "USB Hub Port 2", "reach": "within_reach"},
        {"id": "rdp_screen", "name": "Host Computer Screen (RDP)", "label": "Remote Desktop Display 1", "reach": "within_reach"},
    ],
    "dropped_items": [],
    "labels_registry": {
        "comms_phone": "Right Pocket",
        "matrix_keyring": "Belt Loop Carabiner",
        "access_card": "Jacket Inner Sleeve",
        "field_journal": "Desk Center-Left",
        "water_flask": "Nightstand Top Surface",
        "net_dongle": "USB Hub Port 2",
        "rdp_screen": "Remote Desktop Display 1",
    },
    "discussion_log": [],
}


class MatrixGameInventory:
    """In-game item drop, inventory auditing, spatial discussion, and MCP manager."""

    def __init__(self, state_file: str = STATE_PATH):
        self.state_file = state_file
        self.state = self.load_state()

    def load_state(self) -> Dict[str, Any]:
        with _INV_LOCK:
            if os.path.exists(self.state_file):
                try:
                    with open(self.state_file, "r", encoding="utf-8") as f:
                        return json.load(f)
                except Exception:
                    pass
            return json.loads(json.dumps(DEFAULT_STATE))

    def save_state(self) -> None:
        with _INV_LOCK:
            self.state["last_updated"] = int(time.time())
            tmp = self.state_file + ".tmp"
            try:
                with open(tmp, "w", encoding="utf-8") as f:
                    json.dump(self.state, f, indent=2)
                os.replace(tmp, self.state_file)
            except Exception:
                if os.path.exists(tmp):
                    try:
                        os.remove(tmp)
                    except Exception:
                        pass

    def get_inventory_summary(self) -> Dict[str, Any]:
        """Perform a complete inventory audit of all items and locations."""
        with _INV_LOCK:
            self.state = self.load_state()
            return {
                "on_person_count": len(self.state.get("on_person", [])),
                "on_person": self.state.get("on_person", []),
                "within_reach_count": len(self.state.get("within_reach", [])),
                "within_reach": self.state.get("within_reach", []),
                "dropped_count": len(self.state.get("dropped_items", [])),
                "dropped_items": self.state.get("dropped_items", []),
                "labels_registry": self.state.get("labels_registry", {}),
                "timestamp": int(time.time()),
                "rule": 232,
            }

    def find_item(self, item_query: str) -> Optional[Dict[str, Any]]:
        """Find an item across on_person, within_reach, or dropped_items."""
        with _INV_LOCK:
            q = item_query.lower().strip()
            for group in ["on_person", "within_reach", "dropped_items"]:
                for it in self.state.get(group, []):
                    if it["id"].lower() == q or q in it["name"].lower():
                        return {"item": it, "group": group}
            return None

    def trigger_drop(
        self,
        item_query: str,
        landing_description: str = "Floor by foot of chair",
        dialogue_notes: Optional[List[str]] = None,
        final_label: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Drop an item, run the inventory audit, execute the discussion,
        and apply the verified label.
        """
        with _INV_LOCK:
            match = self.find_item(item_query)
            if not match:
                return {"ok": False, "error": f"Item '{item_query}' not found in inventory."}

            item = match["item"]
            prev_group = match["group"]
            prev_label = item.get("label", "Unknown")

            # 1. Remove from previous group
            self.state[prev_group] = [i for i in self.state[prev_group] if i["id"] != item["id"]]

            # 2. Run in-game discussion before finalizing the label
            default_discussion = [
                f"Observer: '{item['name']}' slipped from [{prev_label}] into the room.",
                f"Navigator: Sensed drop trajectory toward: {landing_description}.",
                f"Checker: Auditing nearby boundary — item is visible and physically grounded.",
                f"Consensus: Confirming location before applying label.",
            ]
            active_discussion = dialogue_notes if dialogue_notes else default_discussion

            # 3. Apply confirmed label
            confirmed_label = final_label if final_label else f"Dropped: {landing_description}"
            item["reach"] = "dropped"
            item["label"] = confirmed_label
            item["dropped_at"] = int(time.time())

            # 4. Add to dropped_items & update registry
            self.state.setdefault("dropped_items", []).append(item)
            self.state.setdefault("labels_registry", {})[item["id"]] = confirmed_label

            # 5. Record discussion log
            discussion_entry = {
                "timestamp": int(time.time()),
                "item_id": item["id"],
                "item_name": item["name"],
                "previous_position": prev_label,
                "landing_area": landing_description,
                "assigned_label": confirmed_label,
                "discussion": active_discussion,
            }
            self.state.setdefault("discussion_log", []).append(discussion_entry)

            # 6. Save state
            self.save_state()

            return {
                "ok": True,
                "dropped_item": item,
                "previous_group": prev_group,
                "assigned_label": confirmed_label,
                "discussion": active_discussion,
                "inventory_audit": self.get_inventory_summary(),
            }

    def pickup_item(self, item_query: str, target_reach: str = "on_person", new_label: str = "Right Hand") -> Dict[str, Any]:
        """Pick up an item and place it back on person or within reach."""
        with _INV_LOCK:
            match = self.find_item(item_query)
            if not match:
                return {"ok": False, "error": f"Item '{item_query}' not found."}

            item = match["item"]
            prev_group = match["group"]

            self.state[prev_group] = [i for i in self.state[prev_group] if i["id"] != item["id"]]
            dest_group = "on_person" if target_reach == "on_person" else "within_reach"

            item["reach"] = dest_group
            item["label"] = new_label
            item.pop("dropped_at", None)

            self.state[dest_group].append(item)
            self.state.setdefault("labels_registry", {})[item["id"]] = new_label
            self.save_state()

            return {
                "ok": True,
                "item": item,
                "moved_from": prev_group,
                "moved_to": dest_group,
                "new_label": new_label,
                "inventory_audit": self.get_inventory_summary(),
            }

    def deliberate_label(self, item_query: str, proposed_label: str, discussion_text: str = "") -> Dict[str, Any]:
        """Discuss and update an item's remembered location label."""
        with _INV_LOCK:
            match = self.find_item(item_query)
            if not match:
                return {"ok": False, "error": f"Item '{item_query}' not found."}

            item = match["item"]
            old_label = item.get("label", "Unlabeled")

            item["label"] = proposed_label
            self.state.setdefault("labels_registry", {})[item["id"]] = proposed_label

            entry = {
                "timestamp": int(time.time()),
                "action": "relabel",
                "item_id": item["id"],
                "old_label": old_label,
                "new_label": proposed_label,
                "discussion": discussion_text or f"Discussed and agreed position: {proposed_label}",
            }
            self.state.setdefault("discussion_log", []).append(entry)
            self.save_state()

            return {
                "ok": True,
                "item_id": item["id"],
                "old_label": old_label,
                "new_label": proposed_label,
            }

    def run_inventory_tick(
        self,
        action: Optional[str] = "audit",
        item_id: Optional[str] = None,
        landing_description: Optional[str] = None,
        new_label: Optional[str] = None,
        note: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Execute a game inventory loop cycle for LLM reasoning and spatial state progression."""
        with _INV_LOCK:
            act = (action or "audit").lower().strip()
            if act == "audit":
                audit = self.get_inventory_summary()
                return {
                    "ok": True,
                    "tick_action": "audit",
                    "result": audit,
                    "message": f"Inventory audit completed: {audit['on_person_count']} on person, {audit['within_reach_count']} within reach, {audit['dropped_count']} dropped.",
                }
            elif act == "drop":
                target = item_id or ("comms_phone" if self.state.get("on_person") else None)
                if not target:
                    return {"ok": False, "error": "No item available to drop."}
                desc = landing_description or "Floor beside work table"
                notes = [note] if note else None
                return self.trigger_drop(target, landing_description=desc, dialogue_notes=notes, final_label=new_label)
            elif act == "pickup":
                target = item_id or (self.state.get("dropped_items")[0]["id"] if self.state.get("dropped_items") else None)
                if not target:
                    return {"ok": False, "error": "No dropped item found to pick up."}
                label = new_label or "Equipped / Hand"
                return self.pickup_item(target, target_reach="on_person", new_label=label)
            elif act in ("label", "relabel"):
                if not item_id or not new_label:
                    return {"ok": False, "error": "Both 'item_id' and 'new_label' are required for relabeling."}
                return self.deliberate_label(item_id, new_label, discussion_text=note or "")
            else:
                return {
                    "ok": True,
                    "tick_action": "auto",
                    "inventory_audit": self.get_inventory_summary(),
                    "message": f"Loop tick acknowledged for action '{act}'.",
                }

    def get_mcp_resources(self) -> List[Dict[str, Any]]:
        """Return MCP resource descriptors."""
        return [
            {
                "uri": "inventory://state",
                "name": "Game Inventory Full State",
                "description": "Complete JSON state of in-game inventory including on_person, within_reach, and dropped_items.",
                "mimeType": "application/json",
            },
            {
                "uri": "inventory://audit",
                "name": "Game Inventory Audit Summary",
                "description": "Aggregated item counts, categorized lists, and current location labels.",
                "mimeType": "application/json",
            },
            {
                "uri": "inventory://items/dropped",
                "name": "Dropped Items Registry",
                "description": "List of all currently dropped items, timestamps, and confirmed spatial labels.",
                "mimeType": "application/json",
            },
            {
                "uri": "inventory://discussions",
                "name": "Spatial Discussion & Deliberation Log",
                "description": "Recorded in-game agent discussions regarding dropped item trajectories and labeling consensus.",
                "mimeType": "application/json",
            },
        ]

    def read_mcp_resource(self, uri: str) -> Dict[str, Any]:
        """Read an MCP resource by URI."""
        with _INV_LOCK:
            if uri == "inventory://state":
                content = json.dumps(self.state, indent=2)
            elif uri == "inventory://audit":
                content = json.dumps(self.get_inventory_summary(), indent=2)
            elif uri in ("inventory://items/dropped", "inventory://dropped"):
                content = json.dumps(self.state.get("dropped_items", []), indent=2)
            elif uri in ("inventory://discussions", "inventory://log"):
                content = json.dumps(self.state.get("discussion_log", []), indent=2)
            else:
                raise ValueError(f"Unknown MCP resource URI: {uri}")
            return {
                "contents": [
                    {
                        "uri": uri,
                        "mimeType": "application/json",
                        "text": content,
                    }
                ]
            }

    def get_mcp_prompts(self) -> List[Dict[str, Any]]:
        """Return available prompt templates for LLMs."""
        return [
            {
                "name": "inventory_audit_report",
                "description": "Generate an LLM spatial analysis and inventory audit report.",
                "arguments": [
                    {"name": "detail_level", "description": "Level of detail: concise or comprehensive", "required": False}
                ],
            },
            {
                "name": "inventory_drop_analysis",
                "description": "Analyze an item drop event, verify physical boundary grounding, and recommend label consensus.",
                "arguments": [
                    {"name": "item_id", "description": "Item ID dropped", "required": True},
                    {"name": "landing", "description": "Landing description", "required": False}
                ],
            },
            {
                "name": "item_relocation_consensus",
                "description": "Deliberate relocation or pickup of an item between on_person and within_reach.",
                "arguments": [
                    {"name": "item_id", "description": "Target item ID", "required": True},
                    {"name": "destination", "description": "Destination reach: on_person or within_reach", "required": False}
                ],
            },
        ]

    def get_mcp_prompt_messages(self, prompt_name: str, arguments: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Generate MCP prompt messages for LLMs."""
        args = arguments or {}
        audit = self.get_inventory_summary()
        if prompt_name == "inventory_audit_report":
            return {
                "description": "In-Game Inventory Audit Report Prompt",
                "messages": [
                    {
                        "role": "user",
                        "content": {
                            "type": "text",
                            "text": (
                                f"Review current in-game inventory status:\n"
                                f"Carried: {len(audit['on_person'])} items ({[i['name'] for i in audit['on_person']]})\n"
                                f"Within Reach: {len(audit['within_reach'])} items ({[i['name'] for i in audit['within_reach']]})\n"
                                f"Dropped: {len(audit['dropped_items'])} items ({[i['name'] for i in audit['dropped_items']]})\n"
                                f"Please provide a spatial stability assessment and check if any dropped items require retrieval."
                            )
                        }
                    }
                ]
            }
        elif prompt_name == "inventory_drop_analysis":
            item_id = args.get("item_id", "item")
            landing = args.get("landing", "floor")
            return {
                "description": "In-Game Drop Event Spatial Deliberation Prompt",
                "messages": [
                    {
                        "role": "user",
                        "content": {
                            "type": "text",
                            "text": (
                                f"An item drop event occurred in the room:\n"
                                f"Item: {item_id}\n"
                                f"Observed Landing: {landing}\n"
                                f"Conduct spatial boundary consensus: Confirm where it landed, ensure it is physically grounded, and format the official persistent label."
                            )
                        }
                    }
                ]
            }
        elif prompt_name == "item_relocation_consensus":
            item_id = args.get("item_id", "item")
            dest = args.get("destination", "on_person")
            return {
                "description": "Item Relocation Consensus Prompt",
                "messages": [
                    {
                        "role": "user",
                        "content": {
                            "type": "text",
                            "text": (
                                f"Deliberate relocating item '{item_id}' to reach state '{dest}'.\n"
                                f"Verify whether the actor has free carry capacity and propose a definitive location label."
                            )
                        }
                    }
                ]
            }
        else:
            raise ValueError(f"Unknown MCP prompt: {prompt_name}")


# ==============================================================================
# LangChain StructuredTools (Rule 232)
# ==============================================================================

class GameInventoryAuditArgs(BaseModel):
    include_discussions: bool = Field(False, description="Whether to include recent discussion log in audit")


def _run_game_inventory_audit(include_discussions: bool = False) -> str:
    inv = MatrixGameInventory()
    res = inv.get_inventory_summary()
    if include_discussions:
        res["recent_discussions"] = inv.state.get("discussion_log", [])[-5:]
    return json.dumps(res, indent=2)


audit_game_inventory_tool = StructuredTool(
    name="audit_game_inventory_tool",
    description="Perform a complete inventory audit of in-game items across on_person, within_reach, and dropped states (Rule 232).",
    args_schema=GameInventoryAuditArgs,
    func=_run_game_inventory_audit,
)


class GameInventoryDropArgs(BaseModel):
    item_id: str = Field(..., description="ID or name of item to drop")
    landing_description: str = Field("Floor by foot of chair", description="Spatial context description of where the item landed")
    dialogue_notes: Optional[List[str]] = Field(None, description="Optional custom agent discussion lines before labeling")
    final_label: Optional[str] = Field(None, description="Optional confirmed persistent label for the dropped item")


def _run_game_inventory_drop(
    item_id: str,
    landing_description: str = "Floor by foot of chair",
    dialogue_notes: Optional[List[str]] = None,
    final_label: Optional[str] = None,
) -> str:
    inv = MatrixGameInventory()
    res = inv.trigger_drop(
        item_id,
        landing_description=landing_description,
        dialogue_notes=dialogue_notes,
        final_label=final_label,
    )
    return json.dumps(res, indent=2)


drop_game_item_tool = StructuredTool(
    name="drop_game_item_tool",
    description="Drop an item into the room, trigger spatial consensus discussion among agents, and commit its confirmed location label (Rule 232).",
    args_schema=GameInventoryDropArgs,
    func=_run_game_inventory_drop,
)


class GameInventoryPickupArgs(BaseModel):
    item_id: str = Field(..., description="ID or name of item to pick up")
    target_reach: str = Field("on_person", description="Destination reach: 'on_person' or 'within_reach'")
    new_label: str = Field("Right Hand", description="New location label (e.g. 'Right Pocket', 'Desk Surface')")


def _run_game_inventory_pickup(
    item_id: str,
    target_reach: str = "on_person",
    new_label: str = "Right Hand",
) -> str:
    inv = MatrixGameInventory()
    res = inv.pickup_item(item_id, target_reach=target_reach, new_label=new_label)
    return json.dumps(res, indent=2)


pickup_game_item_tool = StructuredTool(
    name="pickup_game_item_tool",
    description="Pick up a dropped or nearby item, placing it onto person or within reach with a new location label (Rule 232).",
    args_schema=GameInventoryPickupArgs,
    func=_run_game_inventory_pickup,
)


class GameInventoryLabelArgs(BaseModel):
    item_id: str = Field(..., description="ID or name of item to relabel")
    new_label: str = Field(..., description="New persistent location label")
    discussion: Optional[str] = Field(None, description="Discussion or consensus rationale for the new label")


def _run_game_inventory_label(
    item_id: str,
    new_label: str,
    discussion: Optional[str] = None,
) -> str:
    inv = MatrixGameInventory()
    res = inv.deliberate_label(item_id, new_label, discussion_text=discussion or "")
    return json.dumps(res, indent=2)


label_game_item_tool = StructuredTool(
    name="label_game_item_tool",
    description="Deliberate and update an item's persistent location label after agent spatial consensus (Rule 232).",
    args_schema=GameInventoryLabelArgs,
    func=_run_game_inventory_label,
)


class GameInventoryFindArgs(BaseModel):
    query: str = Field(..., description="Item ID or substring of item name to locate")


def _run_game_inventory_find(query: str) -> str:
    inv = MatrixGameInventory()
    res = inv.find_item(query)
    if not res:
        return json.dumps({"ok": False, "error": f"Item '{query}' not found."})
    return json.dumps({"ok": True, "match": res}, indent=2)


find_game_item_tool = StructuredTool(
    name="find_game_item_tool",
    description="Search for an in-game item by ID or name to locate its current reach group and label (Rule 232).",
    args_schema=GameInventoryFindArgs,
    func=_run_game_inventory_find,
)


class GameInventoryLoopTickArgs(BaseModel):
    action: Optional[str] = Field("audit", description="Tick action: 'audit', 'drop', 'pickup', 'label', or 'auto'")
    item_id: Optional[str] = Field(None, description="Optional target item ID for the tick action")
    landing_description: Optional[str] = Field(None, description="Landing description if dropping")
    new_label: Optional[str] = Field(None, description="New label if labeling or picking up")
    note: Optional[str] = Field(None, description="Discussion note or explanation")


def _run_game_inventory_loop_tick(
    action: Optional[str] = "audit",
    item_id: Optional[str] = None,
    landing_description: Optional[str] = None,
    new_label: Optional[str] = None,
    note: Optional[str] = None,
) -> str:
    inv = MatrixGameInventory()
    res = inv.run_inventory_tick(
        action=action,
        item_id=item_id,
        landing_description=landing_description,
        new_label=new_label,
        note=note,
    )
    return json.dumps(res, indent=2)


inventory_loop_tick_tool = StructuredTool(
    name="inventory_loop_tick_tool",
    description="Execute an in-game inventory loop simulation cycle for LLM spatial reasoning and state progression (Rule 232).",
    args_schema=GameInventoryLoopTickArgs,
    func=_run_game_inventory_loop_tick,
)


GAME_INVENTORY_TOOLS = [
    audit_game_inventory_tool,
    drop_game_item_tool,
    pickup_game_item_tool,
    label_game_item_tool,
    find_game_item_tool,
    inventory_loop_tick_tool,
]


# ==============================================================================
# Model Context Protocol (MCP) Server Implementation (Rule 232)
# ==============================================================================

MCP_PROTOCOL_VERSION = "2024-11-05"
SERVER_NAME = "game-inventory-mcp"
SERVER_VERSION = "1.0.0"


class GameInventoryMCPServer:
    """
    Standard Model Context Protocol (MCP) JSON-RPC 2.0 Server.
    Exposes Game Inventory Loop capabilities to any LLM client.
    """

    def __init__(self, inv: Optional[MatrixGameInventory] = None):
        self.inv = inv or MatrixGameInventory()

    def get_tool_definitions(self) -> List[Dict[str, Any]]:
        return [
            {
                "name": "game_inventory_audit",
                "description": "Audit all in-game items across on_person, within_reach, and dropped boundaries.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "include_discussions": {
                            "type": "boolean",
                            "description": "Whether to include recent discussion log in the response"
                        }
                    }
                }
            },
            {
                "name": "game_inventory_drop",
                "description": "Drop an item from person/reach to the floor, trigger agent discussion, and assign confirmed position label.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "item_id": {"type": "string", "description": "ID or name of item to drop"},
                        "landing_description": {"type": "string", "description": "Description of landing area"},
                        "dialogue_notes": {"type": "array", "items": {"type": "string"}, "description": "Discussion lines"},
                        "final_label": {"type": "string", "description": "Confirmed persistent label"}
                    },
                    "required": ["item_id"]
                }
            },
            {
                "name": "game_inventory_pickup",
                "description": "Pick up a dropped item and place it back on person or within reach with a new location label.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "item_id": {"type": "string", "description": "ID or name of item to pick up"},
                        "target_reach": {"type": "string", "enum": ["on_person", "within_reach"], "description": "Target reach destination"},
                        "new_label": {"type": "string", "description": "New position label"}
                    },
                    "required": ["item_id"]
                }
            },
            {
                "name": "game_inventory_label",
                "description": "Deliberate and update an item's remembered location label.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "item_id": {"type": "string", "description": "ID or name of item to relabel"},
                        "new_label": {"type": "string", "description": "New position label"},
                        "discussion": {"type": "string", "description": "Discussion rationale"}
                    },
                    "required": ["item_id", "new_label"]
                }
            },
            {
                "name": "game_inventory_find",
                "description": "Find an item across all inventory groups.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Item ID or name substring"}
                    },
                    "required": ["query"]
                }
            },
            {
                "name": "game_inventory_loop_tick",
                "description": "Execute a cycle of the game inventory loop for LLM reasoning and spatial state progression.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "action": {"type": "string", "enum": ["audit", "drop", "pickup", "label", "auto"], "description": "Tick action"},
                        "item_id": {"type": "string", "description": "Target item ID"},
                        "landing_description": {"type": "string", "description": "Landing area description"},
                        "new_label": {"type": "string", "description": "New label"},
                        "note": {"type": "string", "description": "Discussion note"}
                    }
                }
            }
        ]

    def call_tool(self, name: str, args: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a tool by name and return standard MCP tool call result."""
        clean_name = name.lower().replace("_tool", "").replace("game_inventory_", "")
        if clean_name in ("audit", "inventory_audit"):
            inc = bool(args.get("include_discussions", False))
            raw = _run_game_inventory_audit(include_discussions=inc)
            return {"content": [{"type": "text", "text": raw}], "isError": False}

        elif clean_name == "drop":
            item_id = str(args.get("item_id") or "")
            landing = str(args.get("landing_description") or args.get("landing") or "Floor by foot of chair")
            notes = args.get("dialogue_notes")
            label = args.get("final_label")
            raw = _run_game_inventory_drop(item_id, landing_description=landing, dialogue_notes=notes, final_label=label)
            return {"content": [{"type": "text", "text": raw}], "isError": False}

        elif clean_name == "pickup":
            item_id = str(args.get("item_id") or "")
            reach = str(args.get("target_reach") or "on_person")
            label = str(args.get("new_label") or "Right Hand")
            raw = _run_game_inventory_pickup(item_id, target_reach=reach, new_label=label)
            return {"content": [{"type": "text", "text": raw}], "isError": False}

        elif clean_name in ("label", "relabel"):
            item_id = str(args.get("item_id") or "")
            label = str(args.get("new_label") or args.get("label") or "")
            disc = args.get("discussion")
            raw = _run_game_inventory_label(item_id, new_label=label, discussion=disc)
            return {"content": [{"type": "text", "text": raw}], "isError": False}

        elif clean_name == "find":
            q = str(args.get("query") or args.get("item_id") or "")
            raw = _run_game_inventory_find(q)
            return {"content": [{"type": "text", "text": raw}], "isError": False}

        elif clean_name in ("loop_tick", "tick"):
            action = args.get("action", "audit")
            item_id = args.get("item_id")
            landing = args.get("landing_description")
            new_label = args.get("new_label")
            note = args.get("note")
            raw = _run_game_inventory_loop_tick(
                action=action,
                item_id=item_id,
                landing_description=landing,
                new_label=new_label,
                note=note,
            )
            return {"content": [{"type": "text", "text": raw}], "isError": False}

        else:
            return {
                "content": [{"type": "text", "text": f"Error: Unknown tool '{name}'"}],
                "isError": True,
            }

    def handle_jsonrpc(self, request: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Dispatch a single JSON-RPC 2.0 MCP request."""
        if not isinstance(request, dict):
            return {
                "jsonrpc": "2.0",
                "id": None,
                "error": {"code": -32600, "message": "Invalid Request: expected JSON object"},
            }

        req_id = request.get("id")
        method = request.get("method")
        params = request.get("params") or {}

        # Notification handling (no id -> no response)
        if req_id is None and method == "notifications/initialized":
            return None

        try:
            if method == "initialize":
                res = {
                    "protocolVersion": MCP_PROTOCOL_VERSION,
                    "capabilities": {
                        "tools": {"listChanged": True},
                        "resources": {"subscribe": False, "listChanged": True},
                        "prompts": {"listChanged": True},
                    },
                    "serverInfo": {
                        "name": SERVER_NAME,
                        "version": SERVER_VERSION,
                    },
                    "instructions": (
                        "Game Inventory Loop MCP Server: Audits on-person, within-reach, and dropped items. "
                        "Conducts spatial consensus discussions before applying persistent location labels (Rule 232)."
                    ),
                }
                return {"jsonrpc": "2.0", "id": req_id, "result": res}

            elif method == "ping":
                return {"jsonrpc": "2.0", "id": req_id, "result": {}}

            elif method == "tools/list":
                tools = self.get_tool_definitions()
                return {"jsonrpc": "2.0", "id": req_id, "result": {"tools": tools}}

            elif method == "tools/call":
                tool_name = params.get("name", "")
                arguments = params.get("arguments") or {}
                result = self.call_tool(tool_name, arguments)
                return {"jsonrpc": "2.0", "id": req_id, "result": result}

            elif method == "resources/list":
                resources = self.inv.get_mcp_resources()
                return {"jsonrpc": "2.0", "id": req_id, "result": {"resources": resources}}

            elif method == "resources/read":
                uri = params.get("uri", "")
                result = self.inv.read_mcp_resource(uri)
                return {"jsonrpc": "2.0", "id": req_id, "result": result}

            elif method == "prompts/list":
                prompts = self.inv.get_mcp_prompts()
                return {"jsonrpc": "2.0", "id": req_id, "result": {"prompts": prompts}}

            elif method == "prompts/get":
                prompt_name = params.get("name", "")
                arguments = params.get("arguments") or {}
                result = self.inv.get_mcp_prompt_messages(prompt_name, arguments)
                return {"jsonrpc": "2.0", "id": req_id, "result": result}

            else:
                return {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "error": {"code": -32601, "message": f"Method '{method}' not found"},
                }

        except Exception as e:
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {"code": -32603, "message": f"Internal MCP server error: {str(e)}"},
            }


def handle_mcp_request(req_data: Any) -> Any:
    """Convenience dispatcher for single or batch JSON-RPC requests."""
    server = GameInventoryMCPServer()
    if isinstance(req_data, list):
        return [server.handle_jsonrpc(item) for item in req_data if item]
    return server.handle_jsonrpc(req_data)


def run_stdio_server():
    """Run Model Context Protocol (MCP) server over standard input/output."""
    server = GameInventoryMCPServer()
    sys.stderr.write(f"[{SERVER_NAME}] Model Context Protocol (MCP) server running on stdio (protocol {MCP_PROTOCOL_VERSION})\n")
    sys.stderr.flush()
    while True:
        try:
            line = sys.stdin.readline()
            if not line:
                break
            line = line.strip()
            if not line:
                continue
            req = json.loads(line)
            resp = server.handle_jsonrpc(req)
            if resp is not None:
                sys.stdout.write(json.dumps(resp) + "\n")
                sys.stdout.flush()
        except (KeyboardInterrupt, EOFError):
            break
        except Exception as e:
            err_resp = {
                "jsonrpc": "2.0",
                "id": None,
                "error": {"code": -32700, "message": f"Parse error: {str(e)}"},
            }
            sys.stdout.write(json.dumps(err_resp) + "\n")
            sys.stdout.flush()


# ==============================================================================
# CLI and Terminal Output
# ==============================================================================

def print_banner():
    print("\n" + "=" * 65)
    print("   🎮 MATRIX IN-GAME INVENTORY & DROP TRACKER (CLI & MCP)")
    print("   Tracks: On Person | Within Reach | Dropped Items")
    print("   Rule 232: Model Context Protocol (MCP) & LangChain Suite")
    print("=" * 65 + "\n")


def display_inventory(inv: MatrixGameInventory):
    audit = inv.get_inventory_summary()
    print("┌─────────────────────────────────────────────────────────────┐")
    print("│ 🥋 ITEMS ON YOUR PERSON (Carried / Equipped)                │")
    print("├─────────────────────────────────────────────────────────────┤")
    if not audit["on_person"]:
        print("│  (None carried)                                             │")
    for it in audit["on_person"]:
        print(f"│  • [{it['id']}] {it['name']} ➔ Label: \"{it['label']}\"")

    print("\n┌─────────────────────────────────────────────────────────────┐")
    print("│ 🤲 ITEMS WITHIN REACH (Desk / Shelf / Arm's Length)         │")
    print("├─────────────────────────────────────────────────────────────┤")
    if not audit["within_reach"]:
        print("│  (None within reach)                                        │")
    for it in audit["within_reach"]:
        print(f"│  • [{it['id']}] {it['name']} ➔ Label: \"{it['label']}\"")

    print("\n┌─────────────────────────────────────────────────────────────┐")
    print("│ ⚠️ DROPPED ITEMS (Fallen / Underneath / On Floor)            │")
    print("├─────────────────────────────────────────────────────────────┤")
    if not audit["dropped_items"]:
        print("│  (No dropped items detected)                                │")
    for it in audit["dropped_items"]:
        print(f"│  • [{it['id']}] {it['name']} ➔ Labeled At: \"{it['label']}\"")
    print("└─────────────────────────────────────────────────────────────┘\n")


def run_interactive_cli():
    inv = MatrixGameInventory()
    print_banner()
    display_inventory(inv)

    help_text = (
        "Commands:\n"
        "  list                       ➔ Show full inventory audit\n"
        "  drop <item_id>             ➔ Drop an item, discuss its landing, and label it\n"
        "  pickup <item_id>           ➔ Pick up dropped item onto person\n"
        "  reach <item_id>            ➔ Move item to 'within_reach'\n"
        "  label <item_id> <new_label>➔ Deliberate and update an item's label\n"
        "  tick                       ➔ Execute one loop simulation tick\n"
        "  log                        ➔ Show recent discussion log\n"
        "  mcp                        ➔ Launch Model Context Protocol (MCP) stdio server\n"
        "  help                       ➔ Show this help text\n"
        "  quit / exit                ➔ Exit game loop\n"
    )
    print(help_text)

    while True:
        try:
            cmd_line = input("matrix-inv> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nExiting Matrix Inventory CLI.")
            break

        if not cmd_line:
            continue

        parts = cmd_line.split(maxsplit=2)
        action = parts[0].lower()

        if action in ("exit", "quit", "q"):
            print("Session saved to game_inventory_state.json. Goodbye.")
            break

        elif action in ("list", "inv", "inventory"):
            display_inventory(inv)

        elif action == "drop":
            if len(parts) < 2:
                print("Usage: drop <item_id> [optional landing description]")
                continue
            item_id = parts[1]
            desc = parts[2] if len(parts) > 2 else "Floor near chair leg"

            print(f"\n[EVENT] Drop triggered for '{item_id}'.")
            print("--- 🗣️ IN-GAME DISCUSSION COMMENCING ---")
            print(f"Agent A: 'Wait, {item_id} just fell. Where was it sitting?'")
            match = inv.find_item(item_id)
            if match:
                print(f"Agent B: 'It was on {match['item'].get('label', 'unspecified position')}.'")
                print(f"Agent A: 'I see it settled at: {desc}.'")
                print(f"Agent B: 'Agreed on landing spot. Let us label it before logging.'")
            else:
                print(f"Agent: 'Could not find {item_id} in current inventory.'")

            res = inv.trigger_drop(item_id, landing_description=desc)
            if res.get("ok"):
                print(f"--- ✅ LABEL COMMITTED: \"{res['assigned_label']}\" ---\n")
                display_inventory(inv)
            else:
                print(f"Error: {res.get('error')}\n")

        elif action in ("pickup", "pick"):
            if len(parts) < 2:
                print("Usage: pickup <item_id> [new_label]")
                continue
            item_id = parts[1]
            label = parts[2] if len(parts) > 2 else "Pocket / In Hand"
            res = inv.pickup_item(item_id, target_reach="on_person", new_label=label)
            if res.get("ok"):
                print(f"Picked up '{item_id}' ➔ placed on person ({label}).\n")
                display_inventory(inv)
            else:
                print(f"Error: {res.get('error')}\n")

        elif action == "reach":
            if len(parts) < 2:
                print("Usage: reach <item_id> [new_label]")
                continue
            item_id = parts[1]
            label = parts[2] if len(parts) > 2 else "Desk Surface (Within Reach)"
            res = inv.pickup_item(item_id, target_reach="within_reach", new_label=label)
            if res.get("ok"):
                print(f"Moved '{item_id}' to within reach ➔ ({label}).\n")
                display_inventory(inv)
            else:
                print(f"Error: {res.get('error')}\n")

        elif action == "label":
            if len(parts) < 3:
                print("Usage: label <item_id> <new_label>")
                continue
            item_id = parts[1]
            new_label = parts[2]
            res = inv.deliberate_label(item_id, new_label)
            if res.get("ok"):
                print(f"Item '{item_id}' relabeled to: \"{new_label}\".\n")
            else:
                print(f"Error: {res.get('error')}\n")

        elif action == "tick":
            res = inv.run_inventory_tick(action="audit")
            print(f"Tick result: {res.get('message')}\n")

        elif action == "log":
            logs = inv.state.get("discussion_log", [])
            if not logs:
                print("No discussions recorded yet.\n")
            else:
                print("\n--- RECENT IN-GAME DISCUSSIONS ---")
                for entry in logs[-5:]:
                    ts = time.strftime("%H:%M:%S", time.localtime(entry.get("timestamp", 0)))
                    print(f"[{ts}] Item: {entry.get('item_name', entry.get('item_id'))} | Assigned: {entry.get('assigned_label', entry.get('new_label'))}")
                    for line in entry.get("discussion", []):
                        print(f"   💬 {line}")
                print("----------------------------------\n")

        elif action == "mcp":
            run_stdio_server()
            break

        elif action == "help":
            print(help_text)

        else:
            print(f"Unknown command: '{action}'. Type 'help' for available commands.")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] in ("--mcp", "mcp"):
        run_stdio_server()
    elif len(sys.argv) > 1 and sys.argv[1] in ("--tick", "tick"):
        inv = MatrixGameInventory()
        result = inv.run_inventory_tick("audit")
        print(json.dumps(result, indent=2))
    else:
        run_interactive_cli()
