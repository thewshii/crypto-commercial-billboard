#!/usr/bin/env python3
"""
game_inventory_loop.py — In-Game Matrix Inventory & Drop Tracker CLI.

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
"""

import json
import os
import sys
import time
from typing import Any, Dict, List, Optional

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATE_PATH = os.path.join(BASE_DIR, "game_inventory_state.json")

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
    ],
    "dropped_items": [],
    "labels_registry": {
        "comms_phone": "Right Pocket",
        "matrix_keyring": "Belt Loop Carabiner",
        "access_card": "Jacket Inner Sleeve",
        "field_journal": "Desk Center-Left",
        "water_flask": "Nightstand Top Surface",
        "net_dongle": "USB Hub Port 2",
    },
    "discussion_log": [],
}


class MatrixGameInventory:
    """In-game item drop, inventory auditing, and spatial discussion manager."""

    def __init__(self, state_file: str = STATE_PATH):
        self.state_file = state_file
        self.state = self.load_state()

    def load_state(self) -> Dict[str, Any]:
        if os.path.exists(self.state_file):
            try:
                with open(self.state_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return json.loads(json.dumps(DEFAULT_STATE))

    def save_state(self) -> None:
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
        return {
            "on_person_count": len(self.state.get("on_person", [])),
            "on_person": self.state.get("on_person", []),
            "within_reach_count": len(self.state.get("within_reach", [])),
            "within_reach": self.state.get("within_reach", []),
            "dropped_count": len(self.state.get("dropped_items", [])),
            "dropped_items": self.state.get("dropped_items", []),
            "labels_registry": self.state.get("labels_registry", {}),
            "timestamp": int(time.time()),
        }

    def find_item(self, item_query: str) -> Optional[Dict[str, Any]]:
        """Find an item across on_person, within_reach, or dropped_items."""
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


def print_banner():
    print("\n" + "=" * 65)
    print("   🎮 MATRIX IN-GAME INVENTORY & DROP TRACKER (CLI)")
    print("   Tracks: On Person | Within Reach | Dropped Items")
    print("   Mechanic: Discussion & Audit Before Labeling")
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
        "  log                        ➔ Show recent discussion log\n"
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

        elif action == "help":
            print(help_text)

        else:
            print(f"Unknown command: '{action}'. Type 'help' for available commands.")


if __name__ == "__main__":
    run_interactive_cli()
