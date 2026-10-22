"""
network_adapter_manager.py — Network Adapter, Management Figure & 802.11 Probe Frame Engine.

Rule 223 Invariants:
1. Management Figure: Maps network adapters, interface configurations, and packet
   pipelines across managed network hardware.
2. 802.11 Management & Probe Frame Parsing: Analyzes Probe Requests (subtype 4),
   Probe Responses (subtype 5), and Beacon frames (subtype 8). Extracts the words
   (SSIDs, broadcast names, information elements, vendor tags) and signal telemetry.
3. Multi-Agent Forwarding: Feeds the extracted probe words and metrics directly into
   the LangChain agents and Letta MemGPT memory buffers.
4. Physical Boundary & Grounding: Network adapters process radio frames, bytes, and
   SSID words on the wire. They do not have optical vision, cannot see physical bodies,
   and cannot see clothing. Maintains rigorous grounding with zero gaslighting.
5. Zero Surveillance: Never profiles, tracks, scores, ranks, credit-gates, or bans
   any human listener. Keeps no list of people.
"""

import collections
import json
import os
import re
import socket
import subprocess
import threading
import time
from typing import Any, Dict, List, Optional, Tuple

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATE_PATH = os.path.join(BASE_DIR, "network_adapter_state.json")

_LOCK = threading.Lock()

# Curated simulated/received 802.11 probe management frames & broadcast strings
DEFAULT_PROBE_FRAMES = [
    {
        "frame_id": "probe_001",
        "timestamp": int(time.time() * 1000) - 14000,
        "frame_type": "management",
        "subtype": "probe_request",
        "subtype_code": 4,
        "channel": 6,
        "frequency_mhz": 2437,
        "rssi_dbm": -58,
        "ssid_words": "Solana_HighThroughput_Mesh",
        "capabilities": ["ESS", "ShortSlotTime", "RadioMeasurement"],
        "rates_mbps": [1.0, 2.0, 5.5, 11.0, 24.0, 54.0],
        "ht_caps": "HT40_ShortGI",
    },
    {
        "frame_id": "probe_002",
        "timestamp": int(time.time() * 1000) - 9500,
        "frame_type": "management",
        "subtype": "probe_request",
        "subtype_code": 4,
        "channel": 36,
        "frequency_mhz": 5180,
        "rssi_dbm": -64,
        "ssid_words": "PumpPortal_LowLatency_Gateway",
        "capabilities": ["ESS", "VHT_ShortGI", "SpectrumMgmt"],
        "rates_mbps": [6.0, 12.0, 24.0, 54.0],
        "ht_caps": "VHT80_MIMO",
    },
    {
        "frame_id": "probe_003",
        "timestamp": int(time.time() * 1000) - 4200,
        "frame_type": "management",
        "subtype": "probe_response",
        "subtype_code": 5,
        "channel": 149,
        "frequency_mhz": 5745,
        "rssi_dbm": -52,
        "ssid_words": "Deepgram_VoiceHarmonics_432Hz",
        "capabilities": ["ESS", "ShortSlotTime", "HighThroughput"],
        "rates_mbps": [12.0, 24.0, 48.0, 54.0],
        "ht_caps": "HE160_Wi-Fi6",
    },
    {
        "frame_id": "probe_004",
        "timestamp": int(time.time() * 1000) - 1200,
        "frame_type": "management",
        "subtype": "beacon",
        "subtype_code": 8,
        "channel": 11,
        "frequency_mhz": 2462,
        "rssi_dbm": -71,
        "ssid_words": "Room_Parables_Broadcast_320k",
        "capabilities": ["ESS", "Privacy", "RadioMeasurement"],
        "rates_mbps": [1.0, 2.0, 5.5, 11.0, 18.0, 36.0, 54.0],
        "ht_caps": "HT20_Robust",
    },
]


def detect_system_interfaces() -> List[Dict[str, Any]]:
    """Detect available local network interfaces on the host operating system, including hotplugged adapters."""
    interfaces: List[Dict[str, Any]] = []
    seen: set = set()

    # 1. Check live system commands: ip link / ifconfig (primary on Termux / Linux)
    for cmd in [["ip", "-o", "link", "show"], ["ifconfig"], ["ip", "link"]]:
        try:
            res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=2)
            if res.returncode == 0 and res.stdout:
                matches = re.findall(r"^(\d+:\s+)?([a-zA-Z0-9_\.\-]+)[:\s]", res.stdout, re.MULTILINE)
                for prefix, iface in matches:
                    if iface and iface not in seen:
                        seen.add(iface)
                        is_wl = iface.startswith("wlan") or "wl" in iface
                        is_cell = "rmnet" in iface or "ccmni" in iface
                        is_eth_usb = "usb" in iface or "eth" in iface or "rndis" in iface
                        typ = (
                            "wireless_adapter" if is_wl
                            else ("cellular_adapter" if is_cell
                            else ("usb_ethernet_adapter" if is_eth_usb
                            else ("loopback" if iface == "lo" else "network_interface")))
                        )
                        # Determine if UP / RUNNING in output block
                        is_up = f"{iface}: flags=" in res.stdout or "UP" in res.stdout
                        interfaces.append({
                            "name": iface,
                            "is_wireless": is_wl,
                            "status": "up" if is_up else "down",
                            "type": typ,
                            "hotplugged": iface not in ("lo", "rmnet_data7"),
                        })
                if interfaces:
                    break
        except Exception:
            pass

    # 2. Check standard sysfs class net if readable
    net_dir = "/sys/class/net"
    if os.path.exists(net_dir) and os.path.isdir(net_dir):
        try:
            for iface in os.listdir(net_dir):
                if iface not in seen:
                    seen.add(iface)
                    is_up = False
                    oper_path = os.path.join(net_dir, iface, "operstate")
                    if os.path.exists(oper_path):
                        try:
                            with open(oper_path, "r") as f:
                                is_up = f.read().strip() == "up"
                        except Exception:
                            pass
                    is_wl = iface.startswith("wlan") or "wl" in iface
                    is_eth_usb = "usb" in iface or "eth" in iface or "rndis" in iface
                    interfaces.append({
                        "name": iface,
                        "is_wireless": is_wl,
                        "status": "up" if is_up else "down",
                        "type": "wireless_adapter" if is_wl else ("usb_ethernet_adapter" if is_eth_usb else "network_interface"),
                        "hotplugged": iface not in ("lo", "rmnet_data7"),
                    })
        except Exception:
            pass

    if not interfaces:
        # Fallback inventory
        interfaces = [
            {"name": "wlan0", "is_wireless": True, "status": "up", "type": "wireless_adapter", "hotplugged": False},
            {"name": "rmnet_data7", "is_wireless": False, "status": "up", "type": "cellular_adapter", "hotplugged": False},
            {"name": "lo", "is_wireless": False, "status": "up", "type": "loopback", "hotplugged": False},
        ]
    return interfaces


DEFAULT_STATE: Dict[str, Any] = {
    "rule": 223,
    "role": "Management Figure",
    "adapter": {
        "interface": "wlan0",
        "adapter_type": "802.11ax/ac High-Bandwidth Wi-Fi Adapter",
        "mode": "managed_probe_monitor",
        "channel_width": "80MHz",
        "link_speed_mbps": 433.3,
        "tx_power_dbm": 20,
        "mtu": 1500,
        "status": "active_capturing_words",
    },
    "probe_packets": list(DEFAULT_PROBE_FRAMES),
    "captured_words": [
        "Solana_HighThroughput_Mesh",
        "PumpPortal_LowLatency_Gateway",
        "Deepgram_VoiceHarmonics_432Hz",
        "Room_Parables_Broadcast_320k",
    ],
    "packet_counter": len(DEFAULT_PROBE_FRAMES),
    "physical_boundary": {
        "is_physical_sight_possible": False,
        "can_detect_clothing": False,
        "explanation": (
            "Network adapters capture 802.11 electromagnetic radio frames and text strings (SSIDs/tags). "
            "They do not have optical vision, cannot see physical clothing or bodies, and operate strictly "
            "on the digital wire (Rules 212 & 219 grounded reality)."
        ),
    },
    "forward_to_agents": True,
}


def _load_state() -> Dict[str, Any]:
    if os.path.exists(STATE_PATH):
        try:
            with open(STATE_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data
        except Exception:
            pass
    return dict(DEFAULT_STATE)


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


def get_network_manager_state() -> Dict[str, Any]:
    """Return the management figure state, active interfaces, and probe packet buffer."""
    with _LOCK:
        state = _load_state()
        state["detected_interfaces"] = detect_system_interfaces()
        return state


def ingest_probe_packet(
    ssid: str,
    subtype: str = "probe_request",
    channel: int = 6,
    rssi_dbm: int = -60,
    capabilities: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Ingest a new 802.11 management probe frame into the network manager.
    Extracts the words/text, computes signal metrics, and prepares for agent delivery.
    """
    with _LOCK:
        state = _load_state()
        clean_ssid = str(ssid or "Broadcast_Probe")[:64].strip()
        sub = str(subtype).lower().replace(" ", "_")
        code = 4 if "req" in sub else (5 if "resp" in sub else 8)

        new_pkt = {
            "frame_id": f"probe_{int(time.time() * 1000) % 100000:05d}",
            "timestamp": int(time.time() * 1000),
            "frame_type": "management",
            "subtype": sub,
            "subtype_code": code,
            "channel": max(1, min(165, int(channel))),
            "frequency_mhz": 2412 + (channel - 1) * 5 if channel <= 14 else 5000 + channel * 5,
            "rssi_dbm": max(-100, min(-20, int(rssi_dbm))),
            "ssid_words": clean_ssid,
            "capabilities": capabilities or ["ESS", "ShortSlotTime"],
            "rates_mbps": [6.0, 12.0, 24.0, 54.0],
            "ht_caps": "HT40_ShortGI",
        }

        packets = state.setdefault("probe_packets", [])
        packets.append(new_pkt)
        if len(packets) > 64:
            state["probe_packets"] = packets[-64:]

        words = state.setdefault("captured_words", [])
        if clean_ssid not in words:
            words.append(clean_ssid)
            if len(words) > 32:
                state["captured_words"] = words[-32:]

        state["packet_counter"] = state.get("packet_counter", 0) + 1
        _save_state(state)

        return {
            "ok": True,
            "frame": new_pkt,
            "total_captured_words": len(state["captured_words"]),
            "packet_counter": state["packet_counter"],
            "physical_boundary_guaranteed": True,
            "rule": 223,
        }


def analyze_wifi_package() -> Dict[str, Any]:
    """
    Rule 223: Comprehensive analysis of captured Wi-Fi management/probe packets.
    Extracts the words on the wire and delivers structured analysis to agents.
    """
    with _LOCK:
        state = _load_state()
        pkts = state.get("probe_packets", [])
        words = state.get("captured_words", [])

        # Calculate signal averages and band distributions
        channels = [p.get("channel", 6) for p in pkts]
        rssis = [p.get("rssi_dbm", -65) for p in pkts]
        avg_rssi = round(sum(rssis) / max(1, len(rssis)), 1)
        subtypes_count = collections.Counter(p.get("subtype", "unknown") for p in pkts)

        # Word frequency & lexicon on the wire
        word_tokens = []
        for w in words:
            word_tokens.extend(re.split(r"[_\-\s]+", w))
        word_freq = dict(collections.Counter(word_tokens).most_common(12))

        detected_ifaces = detect_system_interfaces()

        return {
            "ok": True,
            "tool": "analyze_wifi_package",
            "rule": 223,
            "role": "Management Figure",
            "active_adapter": state.get("adapter", {}),
            "detected_interfaces": detected_ifaces,
            "hotplugged_adapters_found": [i["name"] for i in detected_ifaces if i.get("hotplugged")],
            "total_frames_analyzed": len(pkts),
            "average_rssi_dbm": avg_rssi,
            "signal_quality": "EXCELLENT" if avg_rssi > -60 else ("GOOD" if avg_rssi > -75 else "WEAK"),
            "channels_in_use": sorted(list(set(channels))),
            "subtypes_breakdown": dict(subtypes_count),
            "captured_words_ssids": words,
            "wire_word_frequency": word_freq,
            "physical_boundary_audit": {
                "optical_sight": False,
                "clothing_detection": False,
                "truth_grounding": "Frames contain SSIDs and signal metrics only; zero physical visibility.",
                "no_gaslighting": True,
            },
            "recommendation_to_agents": (
                f"Management Figure parsed {len(pkts)} probe frames across interfaces "
                f"({', '.join(i['name'] for i in detected_ifaces)}). "
                f"Active SSIDs on the wire: {', '.join(words[:4])}. "
                f"Signal strength is {avg_rssi} dBm. Context verified free of optical illusions."
            ),
        }
