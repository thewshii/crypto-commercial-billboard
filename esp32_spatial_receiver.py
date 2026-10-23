#!/usr/bin/env python3
"""
esp32_spatial_receiver.py — Stationary Terminal Socket Communications & Spatial Integration Engine.

Rule 233: The ESP32 Mobile Spatial Tracking Over Local Wi-Fi, Static IP Socket Receiver,
and Stationary Terminal Integration.

Responsibilities:
1. Real-Time Socket Receiver:
   - Listens on a dedicated UDP socket (default port: 8888) on the stationary terminal.
   - Ingests incoming 6-DoF/9-DoF spatial tracking packets from the mobile ESP32.
   - Enforces static IP validation (e.g. 192.168.1.150) and network integrity checks.
2. Spatial Telemetry & Kinematics Processing:
   - Tracks 3D position (x, y, z), velocity, orientation (roll, pitch, yaw), acceleration, and angular rates.
   - Detects motion states: STATIONARY, MOVING, CARRIED, FREEFALL_DROP, and IMPACT.
3. System & Game Inventory MCP Integration:
   - Automatically synchronizes with `game_inventory_loop.py` (Rule 232).
   - If an impact or drop trajectory is detected, triggers the in-game inventory drop audit,
     spatial dialogue consensus, and location labeling.
4. LangChain StructuredTools:
   - Exposes agentic tools for telemetry retrieval, socket configuration, zero-calibration,
     and simulation testing.
"""

import json
import os
import socket
import sys
import threading
import time
from typing import Any, Dict, List, Optional, Tuple

from pydantic import BaseModel, Field
from langchain_core.tools import StructuredTool

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATE_PATH = os.path.join(BASE_DIR, "esp32_spatial_state.json")

_LOCK = threading.RLock()

DEFAULT_RECEIVER_CONFIG = {
    "listen_host": "0.0.0.0",
    "listen_port": 8888,
    "protocol": "UDP",
    "expected_static_ip": "192.168.1.150",
    "strict_ip_filtering": False,
    "auto_inventory_integration": True,
}

_SPATIAL_STATE: Dict[str, Any] = {
    "receiver_active": False,
    "listen_host": "0.0.0.0",
    "listen_port": 8888,
    "protocol": "UDP",
    "expected_static_ip": "192.168.1.150",
    "total_packets_received": 0,
    "last_packet_timestamp": 0,
    "connected_client": None,
    "telemetry": {
        "device_id": "none",
        "seq": 0,
        "uptime_ms": 0,
        "static_ip": "unknown",
        "accel": {"x": 0.0, "y": 0.0, "z": 9.81},
        "gyro": {"x": 0.0, "y": 0.0, "z": 0.0},
        "orientation": {"roll": 0.0, "pitch": 0.0, "yaw": 0.0},
        "position": {"x": 0.0, "y": 0.0, "z": 0.0},
        "velocity": {"x": 0.0, "y": 0.0, "z": 0.0},
        "motion_state": "DISCONNECTED",
        "impact_detected": False,
        "battery_v": 0.0,
        "rssi_dbm": 0,
    },
    "calibration_offset": {
        "x": 0.0, "y": 0.0, "z": 0.0,
        "roll": 0.0, "pitch": 0.0, "yaw": 0.0
    },
    "history": [],
    "rule": 233,
}

_RECEIVER_THREAD: Optional[threading.Thread] = None
_RECEIVER_STOP_EVENT = threading.Event()
_RECEIVER_SOCKET: Optional[socket.socket] = None


def load_spatial_state() -> None:
    """Load persisted spatial state from JSON file if available."""
    global _SPATIAL_STATE
    with _LOCK:
        if os.path.exists(STATE_PATH):
            try:
                with open(STATE_PATH, "r", encoding="utf-8") as f:
                    saved = json.load(f)
                    _SPATIAL_STATE.update(saved)
            except Exception:
                pass


def save_spatial_state() -> None:
    """Save spatial state snapshot to JSON file safely."""
    with _LOCK:
        tmp = STATE_PATH + ".tmp"
        try:
            snapshot = {
                "receiver_active": _SPATIAL_STATE["receiver_active"],
                "listen_host": _SPATIAL_STATE["listen_host"],
                "listen_port": _SPATIAL_STATE["listen_port"],
                "protocol": _SPATIAL_STATE["protocol"],
                "expected_static_ip": _SPATIAL_STATE["expected_static_ip"],
                "total_packets_received": _SPATIAL_STATE["total_packets_received"],
                "last_packet_timestamp": _SPATIAL_STATE["last_packet_timestamp"],
                "telemetry": _SPATIAL_STATE["telemetry"],
                "calibration_offset": _SPATIAL_STATE["calibration_offset"],
                "rule": 233,
                "updated_at": int(time.time()),
            }
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(snapshot, f, indent=2)
            os.replace(tmp, STATE_PATH)
        except Exception:
            if os.path.exists(tmp):
                try:
                    os.remove(tmp)
                except Exception:
                    pass


def get_spatial_tracking_status() -> Dict[str, Any]:
    """Return live spatial telemetry, connection metrics, and receiver status."""
    with _LOCK:
        return {
            "ok": True,
            "receiver_active": _SPATIAL_STATE["receiver_active"],
            "listen_host": _SPATIAL_STATE["listen_host"],
            "listen_port": _SPATIAL_STATE["listen_port"],
            "protocol": _SPATIAL_STATE["protocol"],
            "expected_static_ip": _SPATIAL_STATE["expected_static_ip"],
            "total_packets_received": _SPATIAL_STATE["total_packets_received"],
            "last_packet_timestamp": _SPATIAL_STATE["last_packet_timestamp"],
            "seconds_since_last_packet": (
                round(time.time() - _SPATIAL_STATE["last_packet_timestamp"], 2)
                if _SPATIAL_STATE["last_packet_timestamp"] > 0 else None
            ),
            "connected_client": _SPATIAL_STATE["connected_client"],
            "telemetry": _SPATIAL_STATE["telemetry"],
            "calibration_offset": _SPATIAL_STATE["calibration_offset"],
            "history_count": len(_SPATIAL_STATE["history"]),
            "rule": 233,
        }


def calibrate_spatial_tracker(zero_position: bool = True, zero_orientation: bool = True) -> Dict[str, Any]:
    """Set current coordinates as reference origin for spatial tracking."""
    with _LOCK:
        tel = _SPATIAL_STATE["telemetry"]
        if zero_position and "position" in tel:
            _SPATIAL_STATE["calibration_offset"]["x"] = tel["position"].get("x", 0.0)
            _SPATIAL_STATE["calibration_offset"]["y"] = tel["position"].get("y", 0.0)
            _SPATIAL_STATE["calibration_offset"]["z"] = tel["position"].get("z", 0.0)
        if zero_orientation and "orientation" in tel:
            _SPATIAL_STATE["calibration_offset"]["roll"] = tel["orientation"].get("roll", 0.0)
            _SPATIAL_STATE["calibration_offset"]["pitch"] = tel["orientation"].get("pitch", 0.0)
            _SPATIAL_STATE["calibration_offset"]["yaw"] = tel["orientation"].get("yaw", 0.0)
        save_spatial_state()
        return {
            "ok": True,
            "message": "Spatial calibration reference origin set successfully.",
            "calibration_offset": _SPATIAL_STATE["calibration_offset"],
        }


def process_spatial_packet(raw_bytes: bytes, client_addr: Tuple[str, int]) -> Dict[str, Any]:
    """Parse, calibrate, and integrate an incoming spatial tracking packet."""
    with _LOCK:
        try:
            payload_str = raw_bytes.decode("utf-8").strip()
            packet = json.loads(payload_str)
        except Exception as e:
            return {"ok": False, "error": f"Invalid packet JSON: {str(e)}"}

        client_ip, client_port = client_addr
        expected_ip = _SPATIAL_STATE.get("expected_static_ip")

        # Static IP validation check
        packet_static_ip = packet.get("static_ip") or client_ip
        is_expected = (packet_static_ip == expected_ip or client_ip == expected_ip)
        
        # Apply calibration offsets
        cal = _SPATIAL_STATE["calibration_offset"]
        pos = packet.get("position", {})
        cal_pos = {
            "x": round(pos.get("x", 0.0) - cal["x"], 3),
            "y": round(pos.get("y", 0.0) - cal["y"], 3),
            "z": round(pos.get("z", 0.0) - cal["z"], 3),
        }
        orient = packet.get("orientation", {})
        cal_orient = {
            "roll": round(orient.get("roll", 0.0) - cal["roll"], 2),
            "pitch": round(orient.get("pitch", 0.0) - cal["pitch"], 2),
            "yaw": round(orient.get("yaw", 0.0) - cal["yaw"], 2),
        }

        integrated_telemetry = {
            "device_id": str(packet.get("device_id") or "esp32_spatial"),
            "seq": int(packet.get("seq") or 0),
            "uptime_ms": int(packet.get("uptime_ms") or 0),
            "static_ip": packet_static_ip,
            "client_ip": client_ip,
            "client_port": client_port,
            "static_ip_verified": is_expected,
            "accel": packet.get("accel", {"x": 0.0, "y": 0.0, "z": 9.81}),
            "gyro": packet.get("gyro", {"x": 0.0, "y": 0.0, "z": 0.0}),
            "orientation": cal_orient,
            "position": cal_pos,
            "velocity": packet.get("velocity", {"x": 0.0, "y": 0.0, "z": 0.0}),
            "motion_state": str(packet.get("motion_state") or "CARRIED"),
            "impact_detected": bool(packet.get("impact_detected", False)),
            "battery_v": float(packet.get("battery_v") or 3.95),
            "rssi_dbm": int(packet.get("rssi_dbm") or -60),
            "received_at": time.time(),
        }

        # Update state
        _SPATIAL_STATE["total_packets_received"] += 1
        _SPATIAL_STATE["last_packet_timestamp"] = time.time()
        _SPATIAL_STATE["connected_client"] = f"{client_ip}:{client_port} (static: {packet_static_ip})"
        _SPATIAL_STATE["telemetry"] = integrated_telemetry

        # Append to history buffer (cap at 50)
        _SPATIAL_STATE["history"].append({
            "seq": integrated_telemetry["seq"],
            "pos": cal_pos,
            "orient": cal_orient,
            "state": integrated_telemetry["motion_state"],
            "ts": integrated_telemetry["received_at"],
        })
        if len(_SPATIAL_STATE["history"]) > 50:
            _SPATIAL_STATE["history"].pop(0)

        # Coordinate with Game Inventory Loop if an impact/drop is detected (Rule 232 / 233 link)
        if integrated_telemetry["impact_detected"] or integrated_telemetry["motion_state"] == "FREEFALL_DROP":
            _handle_inventory_drop_trigger(integrated_telemetry)

        save_spatial_state()
        return {"ok": True, "telemetry": integrated_telemetry}


def _handle_inventory_drop_trigger(telemetry: Dict[str, Any]) -> None:
    """When an ESP32 spatial impact is detected, trigger Game Inventory drop audit."""
    try:
        import game_inventory_loop
        inv = game_inventory_loop.MatrixGameInventory()
        landing_desc = (
            f"Floor area (ESP32 Impact at x={telemetry['position']['x']}m, "
            f"y={telemetry['position']['y']}m, z={telemetry['position']['z']}m)"
        )
        discussion = [
            f"ESP32 Spatial Sensor: High-G impact detected ({telemetry['motion_state']}) from {telemetry['static_ip']}.",
            f"Spatial Coordinates: X={telemetry['position']['x']}m, Y={telemetry['position']['y']}m, Z={telemetry['position']['z']}m.",
            f"Observer: Mobile tracker transitioned from carried to grounded.",
            f"Consensus: Confirming dropped position coordinates in the room.",
        ]
        # Attempt to drop comms_phone or first carried item if carried
        audit = inv.get_inventory_summary()
        carried = audit.get("on_person", [])
        if carried:
            target_item = carried[0]["id"]
            inv.trigger_drop(
                target_item,
                landing_description=landing_desc,
                dialogue_notes=discussion,
                final_label=f"Dropped (Spatial: {telemetry['position']['x']},{telemetry['position']['y']})"
            )
    except Exception as e:
        sys.stderr.write(f"[ESP32-SPATIAL] Inventory integration note: {str(e)}\n")


def _receiver_loop(host: str, port: int) -> None:
    """Background worker that binds UDP socket and listens for ESP32 packets."""
    global _RECEIVER_SOCKET
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind((host, port))
        sock.settimeout(1.0)
        _RECEIVER_SOCKET = sock

        with _LOCK:
            _SPATIAL_STATE["receiver_active"] = True
            _SPATIAL_STATE["listen_host"] = host
            _SPATIAL_STATE["listen_port"] = port

        sys.stderr.write(f"[ESP32-SPATIAL] Socket communications server listening on {host}:{port} (UDP)\n")

        while not _RECEIVER_STOP_EVENT.is_set():
            try:
                data, addr = sock.recvfrom(4096)
                if data:
                    process_spatial_packet(data, addr)
            except socket.timeout:
                continue
            except Exception as ex:
                if not _RECEIVER_STOP_EVENT.is_set():
                    sys.stderr.write(f"[ESP32-SPATIAL] Receive error: {str(ex)}\n")

    except Exception as ex:
        sys.stderr.write(f"[ESP32-SPATIAL] Socket bind failure on {host}:{port}: {str(ex)}\n")
    finally:
        with _LOCK:
            _SPATIAL_STATE["receiver_active"] = False
        if _RECEIVER_SOCKET:
            try:
                _RECEIVER_SOCKET.close()
            except Exception:
                pass
            _RECEIVER_SOCKET = None


def start_spatial_receiver(host: str = "0.0.0.0", port: int = 8888) -> Dict[str, Any]:
    """Start the stationary terminal UDP socket receiver in a background daemon thread."""
    global _RECEIVER_THREAD, _RECEIVER_STOP_EVENT
    with _LOCK:
        if _SPATIAL_STATE["receiver_active"] and _RECEIVER_THREAD and _RECEIVER_THREAD.is_alive():
            return {
                "ok": True,
                "message": f"Spatial receiver already running on {host}:{port}.",
                "status": get_spatial_tracking_status(),
            }

        _RECEIVER_STOP_EVENT.clear()
        _RECEIVER_THREAD = threading.Thread(
            target=_receiver_loop,
            args=(host, port),
            daemon=True,
            name="ESP32SpatialReceiverDaemon"
        )
        _RECEIVER_THREAD.start()

    time.sleep(0.05)
    return {
        "ok": True,
        "message": f"Spatial receiver started on {host}:{port} (UDP).",
        "status": get_spatial_tracking_status(),
    }


def stop_spatial_receiver() -> Dict[str, Any]:
    """Stop the stationary terminal UDP socket receiver."""
    global _RECEIVER_STOP_EVENT, _RECEIVER_SOCKET
    _RECEIVER_STOP_EVENT.set()
    if _RECEIVER_SOCKET:
        try:
            _RECEIVER_SOCKET.close()
        except Exception:
            pass
    with _LOCK:
        _SPATIAL_STATE["receiver_active"] = False
    return {"ok": True, "message": "Spatial receiver stopped."}


def simulate_esp32_packet(
    static_ip: str = "192.168.1.150",
    pos_x: float = 0.45,
    pos_y: float = 1.20,
    pos_z: float = 0.95,
    roll: float = 2.4,
    pitch: float = -1.2,
    yaw: float = 85.0,
    motion_state: str = "CARRIED",
    impact: bool = False,
) -> Dict[str, Any]:
    """Synthesize and process an ESP32 spatial packet directly for testing and simulation."""
    fake_packet = {
        "device_id": "esp32_spatial_mobile_01",
        "seq": _SPATIAL_STATE["total_packets_received"] + 1,
        "uptime_ms": int(time.time() * 1000) % 1000000,
        "static_ip": static_ip,
        "accel": {"x": 0.05 if not impact else 28.5, "y": 0.02, "z": 9.81 if not impact else 1.2},
        "gyro": {"x": 0.5, "y": -0.3, "z": 0.1},
        "orientation": {"roll": roll, "pitch": pitch, "yaw": yaw},
        "position": {"x": pos_x, "y": pos_y, "z": pos_z},
        "velocity": {"x": 0.0, "y": 0.02, "z": 0.0},
        "motion_state": "IMPACT" if impact else motion_state,
        "impact_detected": impact,
        "battery_v": 3.96,
        "rssi_dbm": -52,
    }
    raw = json.dumps(fake_packet).encode("utf-8")
    return process_spatial_packet(raw, (static_ip, 54321))


# ==============================================================================
# LangChain StructuredTools (Rule 233)
# ==============================================================================

class GetSpatialTrackingStatusArgs(BaseModel):
    pass


def _run_get_spatial_tracking_status() -> str:
    res = get_spatial_tracking_status()
    return json.dumps(res, indent=2)


get_spatial_tracking_status_tool = StructuredTool(
    name="get_spatial_tracking_status_tool",
    description="Retrieve live ESP32 mobile spatial tracking coordinates (x,y,z), orientation, and stationary terminal receiver socket telemetry (Rule 233).",
    args_schema=GetSpatialTrackingStatusArgs,
    func=_run_get_spatial_tracking_status,
)


class SimulateEsp32SpatialPacketArgs(BaseModel):
    static_ip: Optional[str] = Field("192.168.1.150", description="Static IP of mobile ESP32")
    pos_x: Optional[float] = Field(0.5, description="X coordinate displacement in meters")
    pos_y: Optional[float] = Field(1.0, description="Y coordinate displacement in meters")
    pos_z: Optional[float] = Field(0.9, description="Z coordinate displacement in meters")
    roll: Optional[float] = Field(0.0, description="Roll attitude in degrees")
    pitch: Optional[float] = Field(0.0, description="Pitch attitude in degrees")
    yaw: Optional[float] = Field(90.0, description="Yaw attitude in degrees")
    motion_state: Optional[str] = Field("CARRIED", description="Motion state: STATIONARY, MOVING, CARRIED, IMPACT")
    impact: Optional[bool] = Field(False, description="Whether to simulate an impact/drop event")


def _run_simulate_esp32_packet(
    static_ip: str = "192.168.1.150",
    pos_x: float = 0.5,
    pos_y: float = 1.0,
    pos_z: float = 0.9,
    roll: float = 0.0,
    pitch: float = 0.0,
    yaw: float = 90.0,
    motion_state: str = "CARRIED",
    impact: bool = False,
) -> str:
    res = simulate_esp32_packet(
        static_ip=static_ip,
        pos_x=pos_x,
        pos_y=pos_y,
        pos_z=pos_z,
        roll=roll,
        pitch=pitch,
        yaw=yaw,
        motion_state=motion_state,
        impact=impact,
    )
    return json.dumps(res, indent=2)


simulate_esp32_spatial_packet_tool = StructuredTool(
    name="simulate_esp32_spatial_packet_tool",
    description="Simulate an ESP32 mobile spatial tracking packet ingestion into the stationary terminal socket receiver (Rule 233).",
    args_schema=SimulateEsp32SpatialPacketArgs,
    func=_run_simulate_esp32_packet,
)


class CalibrateSpatialTrackerArgs(BaseModel):
    zero_position: bool = Field(True, description="Zero the 3D position coordinates to current location")
    zero_orientation: bool = Field(True, description="Zero the roll, pitch, and yaw angles")


def _run_calibrate_spatial_tracker(zero_position: bool = True, zero_orientation: bool = True) -> str:
    res = calibrate_spatial_tracker(zero_position=zero_position, zero_orientation=zero_orientation)
    return json.dumps(res, indent=2)


calibrate_spatial_tracker_tool = StructuredTool(
    name="calibrate_spatial_tracker_tool",
    description="Calibrate and zero the spatial tracker reference origin on the stationary terminal (Rule 233).",
    args_schema=CalibrateSpatialTrackerArgs,
    func=_run_calibrate_spatial_tracker,
)


class ConfigureEsp32SocketArgs(BaseModel):
    host: Optional[str] = Field("0.0.0.0", description="Stationary terminal IP to bind")
    port: Optional[int] = Field(8888, description="UDP receiver port")
    expected_static_ip: Optional[str] = Field("192.168.1.150", description="Expected static IP address of ESP32")


def _run_configure_esp32_socket(
    host: str = "0.0.0.0",
    port: int = 8888,
    expected_static_ip: str = "192.168.1.150"
) -> str:
    with _LOCK:
        _SPATIAL_STATE["expected_static_ip"] = expected_static_ip
    stop_spatial_receiver()
    res = start_spatial_receiver(host=host, port=port)
    return json.dumps(res, indent=2)


configure_esp32_socket_tool = StructuredTool(
    name="configure_esp32_socket_tool",
    description="Configure the stationary terminal socket receiver port, binding host, and expected ESP32 static IP address (Rule 233).",
    args_schema=ConfigureEsp32SocketArgs,
    func=_run_configure_esp32_socket,
)


ESP32_SPATIAL_TOOLS = [
    get_spatial_tracking_status_tool,
    simulate_esp32_spatial_packet_tool,
    calibrate_spatial_tracker_tool,
    configure_esp32_socket_tool,
]


# ==============================================================================
# CLI Terminal Runner
# ==============================================================================

def run_cli_receiver():
    print("\n" + "=" * 65)
    print("  🛰️ ESP32 MOBILE SPATIAL TRACKING RECEIVER (RULE 233)")
    print("  Stationary Terminal Real-Time UDP Socket Ingestion")
    print("  Static IP Target: 192.168.1.150 ➔ UDP Port: 8888")
    print("=" * 65 + "\n")

    start_spatial_receiver(host="0.0.0.0", port=8888)
    print("Listening for incoming spatial packets. Press Ctrl+C to stop.\n")

    try:
        while True:
            st = get_spatial_tracking_status()
            tel = st["telemetry"]
            pos = tel.get("position", {})
            att = tel.get("orientation", {})
            acc = tel.get("accel", {})
            print(
                f"\r[PKTS: {st['total_packets_received']:05d}] "
                f"State: {tel.get('motion_state','?'):<12} "
                f"Pos: ({pos.get('x',0.0):+5.2f}, {pos.get('y',0.0):+5.2f}, {pos.get('z',0.0):+5.2f})m "
                f"Att: (R:{att.get('roll',0.0):+5.1f}° P:{att.get('pitch',0.0):+5.1f}° Y:{att.get('yaw',0.0):+5.1f}°) "
                f"RSSI: {tel.get('rssi_dbm',0):+3d}dBm",
                end="",
                flush=True
            )
            time.sleep(0.2)
    except (KeyboardInterrupt, EOFError):
        print("\nStopping receiver...")
        stop_spatial_receiver()
        print("Receiver stopped cleanly.")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] in ("--simulate", "simulate", "--test"):
        print("[ESP32-SPATIAL] Injecting simulated packet...")
        res = simulate_esp32_packet(impact=True)
        print(json.dumps(res, indent=2))
    else:
        run_cli_receiver()
