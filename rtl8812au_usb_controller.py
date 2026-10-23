#!/usr/bin/env python3
"""
rtl8812au_usb_controller.py - Userspace USB Controller for Realtek RTL8812AU (0bda:8812).

Controls the Realtek RTL8812AU 802.11a/b/g/n/ac Dual-Band Wi-Fi adapter directly
over USB endpoints using Linux USBDEVFS ioctl calls and termux-usb without requiring
root permissions or custom kernel modules.

Endpoints:
  - 0x81 (IN):  Bulk RX (802.11 frames, beacons, data, and Wi-Fi ACKs)
  - 0x02 (OUT): Bulk TX High Priority / Management
  - 0x03 (OUT): Bulk TX Normal Priority / Data
  - 0x04 (OUT): Bulk TX Low Priority / Background
  - 0x85 (IN):  Interrupt RX (C2H events, status updates)

Registers:
  - Accessed via USB control transfers (Vendor 0xC0 read, 0x40 write, bRequest 0x05)
"""

import sys
import os
import time
import json
import struct
import fcntl
import ctypes
import subprocess
from typing import Dict, Any, Optional, List, Tuple
from pydantic import BaseModel, Field
from langchain_core.tools import StructuredTool

# Linux USBDEVFS ioctl definitions for 64-bit ARM Linux (aarch64)
class usbdevfs_ctrltransfer(ctypes.Structure):
    _fields_ = [
        ("bRequestType", ctypes.c_uint8),
        ("bRequest", ctypes.c_uint8),
        ("wValue", ctypes.c_uint16),
        ("wIndex", ctypes.c_uint16),
        ("wLength", ctypes.c_uint16),
        ("timeout", ctypes.c_uint32),
        ("data", ctypes.c_void_p),
    ]

class usbdevfs_bulktransfer(ctypes.Structure):
    _fields_ = [
        ("ep", ctypes.c_uint32),
        ("len", ctypes.c_uint32),
        ("timeout", ctypes.c_uint32),
        ("data", ctypes.c_void_p),
    ]

_CTRL_SIZE = ctypes.sizeof(usbdevfs_ctrltransfer)
_BULK_SIZE = ctypes.sizeof(usbdevfs_bulktransfer)

# _IOC: dir=3 (read/write), type='U' (0x55)
USBDEVFS_CONTROL          = (3 << 30) | (_CTRL_SIZE << 16) | (ord('U') << 8) | 0
USBDEVFS_BULK             = (3 << 30) | (_BULK_SIZE << 16) | (ord('U') << 8) | 2
USBDEVFS_CLAIMINTERFACE   = 0x8004550f
USBDEVFS_RELEASEINTERFACE = 0x80045510
USBDEVFS_RESET            = 0x00005514

# Hardware Constants for Realtek RTL8812AU
VENDOR_ID_RTL8812AU  = 0x0bda
PRODUCT_ID_RTL8812AU = 0x8812

EP_BULK_IN       = 0x81  # RX Frames
EP_BULK_OUT_HIGH = 0x02  # TX High Priority / Management
EP_BULK_OUT_NORM = 0x03  # TX Normal Data
EP_BULK_OUT_LOW  = 0x04  # TX Low Priority
EP_INT_IN        = 0x85  # C2H Interrupt Reports


class RTL8812AUController:
    """Userspace USB Controller for Realtek RTL8812AU Wi-Fi Adapter."""

    def __init__(self, fd: Optional[int] = None):
        self.fd = fd
        self.interface_claimed = False
        self.device_info = {
            "chipset": "Realtek RTL8812AU",
            "vid": f"0x{VENDOR_ID_RTL8812AU:04x}",
            "pid": f"0x{PRODUCT_ID_RTL8812AU:04x}",
            "mac_address": "00:00:00:00:00:00",
            "sys_cfg": "0x00000000",
            "claimed_interface": 0,
            "packets_received": 0,
            "packets_sent": 0,
            "bytes_received": 0,
            "bytes_sent": 0,
            "status": "DISCONNECTED",
        }

        if self.fd is not None:
            self._init_device()

    def _init_device(self):
        """Claim interface 0 and read hardware identification registers."""
        try:
            iface = ctypes.c_uint(0)
            fcntl.ioctl(self.fd, USBDEVFS_CLAIMINTERFACE, iface)
            self.interface_claimed = True
            self.device_info["status"] = "ATTACHED_AND_CLAIMED"

            # Read hardware registers
            mac = self.read_mac_address()
            sys_cfg = self.read32(0x00F0)
            cr = self.read8(0x0100)

            self.device_info["mac_address"] = mac
            self.device_info["sys_cfg"] = f"0x{sys_cfg:08x}"
            self.device_info["cr_reg"] = f"0x{cr:02x}"
        except Exception as e:
            self.device_info["status"] = f"CLAIM_FAILED: {e}"

    def close(self):
        """Release claimed interface and close descriptor if open."""
        if self.fd is not None and self.interface_claimed:
            try:
                iface = ctypes.c_uint(0)
                fcntl.ioctl(self.fd, USBDEVFS_RELEASEINTERFACE, iface)
                self.interface_claimed = False
                self.device_info["status"] = "RELEASED"
            except Exception:
                pass

    # --------------------------------------------------------------------------
    # Register Access via USB Control Transfers
    # --------------------------------------------------------------------------
    def read_register(self, reg: int, length: int = 1) -> bytes:
        """Read 1, 2, or 4 bytes from hardware register using Vendor Control IN."""
        if self.fd is None:
            return b"\x00" * length
        buf = ctypes.create_string_buffer(length)
        req = usbdevfs_ctrltransfer(
            bRequestType=0xC0, # Device to Host | Vendor
            bRequest=0x05,     # Realtek register read
            wValue=reg & 0xFFFF,
            wIndex=(reg >> 16) & 0xFFFF,
            wLength=length,
            timeout=1000,
            data=ctypes.cast(buf, ctypes.c_void_p),
        )
        fcntl.ioctl(self.fd, USBDEVFS_CONTROL, req)
        return buf.raw[:length]

    def write_register(self, reg: int, data: bytes) -> bool:
        """Write 1, 2, or 4 bytes to hardware register using Vendor Control OUT."""
        if self.fd is None:
            return False
        length = len(data)
        buf = ctypes.create_string_buffer(data, length)
        req = usbdevfs_ctrltransfer(
            bRequestType=0x40, # Host to Device | Vendor
            bRequest=0x05,     # Realtek register write
            wValue=reg & 0xFFFF,
            wIndex=(reg >> 16) & 0xFFFF,
            wLength=length,
            timeout=1000,
            data=ctypes.cast(buf, ctypes.c_void_p),
        )
        fcntl.ioctl(self.fd, USBDEVFS_CONTROL, req)
        return True

    def read8(self, reg: int) -> int:
        raw = self.read_register(reg, 1)
        return raw[0] if raw else 0

    def read16(self, reg: int) -> int:
        raw = self.read_register(reg, 2)
        return struct.unpack("<H", raw)[0] if len(raw) == 2 else 0

    def read32(self, reg: int) -> int:
        raw = self.read_register(reg, 4)
        return struct.unpack("<I", raw)[0] if len(raw) == 4 else 0

    def write8(self, reg: int, val: int) -> bool:
        return self.write_register(reg, struct.pack("<B", val & 0xFF))

    def write16(self, reg: int, val: int) -> bool:
        return self.write_register(reg, struct.pack("<H", val & 0xFFFF))

    def write32(self, reg: int, val: int) -> bool:
        return self.write_register(reg, struct.pack("<I", val & 0xFFFFFFFF))

    def read_mac_address(self) -> str:
        """Read factory hardware MAC address from registers 0xEE-0xF3 or 0x12-0x17."""
        raw = self.read_register(0x00EE, 6)
        if len(raw) == 6 and any(b != 0 for b in raw):
            return ":".join(f"{b:02x}" for b in raw)
        raw2 = self.read_register(0x0012, 6)
        if len(raw2) == 6:
            return ":".join(f"{b:02x}" for b in raw2)
        return "00:00:00:00:00:00"

    # --------------------------------------------------------------------------
    # Endpoint Transfers (Bulk RX / TX and Interrupt)
    # --------------------------------------------------------------------------
    def read_bulk_packet(self, ep: int = EP_BULK_IN, buffer_size: int = 2048, timeout_ms: int = 100) -> Optional[bytes]:
        """
        Read raw packet payload from Bulk IN endpoint 0x81.
        Returns bytes if a packet was received, or None if timeout (no packet in queue).
        """
        if self.fd is None:
            return None
        buf = ctypes.create_string_buffer(buffer_size)
        req = usbdevfs_bulktransfer(
            ep=ep,
            len=buffer_size,
            timeout=timeout_ms,
            data=ctypes.cast(buf, ctypes.c_void_p),
        )
        try:
            ret = fcntl.ioctl(self.fd, USBDEVFS_BULK, req)
            if ret > 0:
                data = buf.raw[:ret]
                self.device_info["packets_received"] += 1
                self.device_info["bytes_received"] += ret
                return data
        except OSError as e:
            if e.errno == 110: # ETIMEDOUT (normal when queue empty)
                return None
            raise
        return None

    def send_bulk_packet(self, data: bytes, ep: int = EP_BULK_OUT_NORM, timeout_ms: int = 500) -> int:
        """Send raw packet payload to Bulk OUT endpoint (0x02, 0x03, or 0x04)."""
        if self.fd is None:
            return 0
        buf = ctypes.create_string_buffer(data, len(data))
        req = usbdevfs_bulktransfer(
            ep=ep,
            len=len(data),
            timeout=timeout_ms,
            data=ctypes.cast(buf, ctypes.c_void_p),
        )
        ret = fcntl.ioctl(self.fd, USBDEVFS_BULK, req)
        if ret > 0:
            self.device_info["packets_sent"] += 1
            self.device_info["bytes_sent"] += ret
        return ret

    def get_status(self) -> Dict[str, Any]:
        """Retrieve complete controller and hardware telemetry dictionary."""
        return {
            "ok": True,
            "device": self.device_info,
            "endpoints": {
                "bulk_rx": f"0x{EP_BULK_IN:02x}",
                "bulk_tx_high": f"0x{EP_BULK_OUT_HIGH:02x}",
                "bulk_tx_norm": f"0x{EP_BULK_OUT_NORM:02x}",
                "bulk_tx_low": f"0x{EP_BULK_OUT_LOW:02x}",
                "interrupt_rx": f"0x{EP_INT_IN:02x}",
            },
            "timestamp": time.time(),
        }


# Global singleton instance for billboard API & LangChain tools
_CONTROLLER_INSTANCE: Optional[RTL8812AUController] = None


def get_global_controller() -> RTL8812AUController:
    """Retrieve or initialize singleton controller."""
    global _CONTROLLER_INSTANCE
    if _CONTROLLER_INSTANCE is None:
        fd_env = os.environ.get("TERMUX_USB_FD")
        fd = int(fd_env) if fd_env else None
        _CONTROLLER_INSTANCE = RTL8812AUController(fd=fd)
    return _CONTROLLER_INSTANCE


def get_rtl8812au_usb_status() -> Dict[str, Any]:
    """Retrieve RTL8812AU USB Controller telemetry (Rule 235)."""
    ctrl = get_global_controller()
    st = ctrl.get_status()
    st["rule"] = 235
    return st


# ==============================================================================
# LangChain StructuredTools (Rule 235)
# ==============================================================================

class GetRtl8812auUsbStatusArgs(BaseModel):
    pass


def _run_get_rtl8812au_usb_status() -> str:
    res = get_rtl8812au_usb_status()
    return json.dumps(res, indent=2)


get_rtl8812au_usb_status_tool = StructuredTool(
    name="get_rtl8812au_usb_status_tool",
    description="Retrieve Realtek RTL8812AU USB Wi-Fi userspace controller telemetry, hardware MAC address, and active endpoint statuses (Rule 235).",
    args_schema=GetRtl8812auUsbStatusArgs,
    func=_run_get_rtl8812au_usb_status,
)


class ReadRtl8812auRegisterArgs(BaseModel):
    reg_hex: str = Field("0x00F0", description="Hexadecimal register address (e.g., '0x00F0' for SYS_CFG, '0x00EE' for MAC)")
    length: Optional[int] = Field(4, description="Number of bytes to read (1, 2, or 4)")


def _run_read_rtl8812au_register(reg_hex: str = "0x00F0", length: int = 4) -> str:
    ctrl = get_global_controller()
    try:
        reg_addr = int(reg_hex, 16) if isinstance(reg_hex, str) else int(reg_hex)
        raw_val = ctrl.read_register(reg_addr, length)
        return json.dumps({
            "ok": True,
            "register": f"0x{reg_addr:04X}",
            "length": length,
            "hex": raw_val.hex(),
            "bytes": list(raw_val),
            "rule": 235,
        }, indent=2)
    except Exception as e:
        return json.dumps({"ok": False, "error": str(e), "rule": 235}, indent=2)


read_rtl8812au_register_tool = StructuredTool(
    name="read_rtl8812au_register_tool",
    description="Read hardware registers from Realtek RTL8812AU Wi-Fi adapter via USB vendor control transfers (Rule 235).",
    args_schema=ReadRtl8812auRegisterArgs,
    func=_run_read_rtl8812au_register,
)


class CaptureRtl8812auPacketsArgs(BaseModel):
    duration_sec: Optional[float] = Field(2.0, description="Duration in seconds to sample Bulk IN endpoint 0x81")
    max_packets: Optional[int] = Field(20, description="Maximum number of packets to capture")


def _run_capture_rtl8812au_packets(duration_sec: float = 2.0, max_packets: int = 20) -> str:
    ctrl = get_global_controller()
    start_t = time.time()
    packets = []
    while (time.time() - start_t < duration_sec) and len(packets) < max_packets:
        pkt = ctrl.read_bulk_packet(timeout_ms=50)
        if pkt:
            packets.append({
                "index": len(packets) + 1,
                "length": len(pkt),
                "hex_preview": pkt[:32].hex(),
            })
    return json.dumps({
        "ok": True,
        "packets_captured": len(packets),
        "packets": packets,
        "duration_sec": duration_sec,
        "rule": 235,
    }, indent=2)


capture_rtl8812au_packets_tool = StructuredTool(
    name="capture_rtl8812au_packets_tool",
    description="Capture raw 802.11 frames and packets from Bulk IN endpoint 0x81 on Realtek RTL8812AU (Rule 235).",
    args_schema=CaptureRtl8812auPacketsArgs,
    func=_run_capture_rtl8812au_packets,
)

RTL8812AU_USB_TOOLS = [
    get_rtl8812au_usb_status_tool,
    read_rtl8812au_register_tool,
    capture_rtl8812au_packets_tool,
]


def run_with_termux_usb(args_list: List[str]) -> subprocess.CompletedProcess:
    """Helper to execute this controller script wrapped via termux-usb."""
    script_path = os.path.abspath(__file__)
    dev_path = "/dev/bus/usb/001/005"
    cmd = [
        "termux-usb",
        "-r",
        "-E",
        "-e",
        f"python3 {script_path} " + " ".join(args_list),
        dev_path,
    ]
    return subprocess.run(cmd, capture_output=True, text=True)


# ==============================================================================
# CLI Entrypoint
# ==============================================================================
def main():
    # If running directly outside termux-usb and no TERMUX_USB_FD is present,
    # auto-wrap via termux-usb
    if "TERMUX_USB_FD" not in os.environ and len(sys.argv) <= 1:
        print("[RTL8812AU] Auto-invoking via termux-usb wrapper...")
        res = run_with_termux_usb(["--status"])
        print(res.stdout)
        if res.stderr:
            print("[ERR]", res.stderr)
        return

    fd = int(os.environ["TERMUX_USB_FD"]) if "TERMUX_USB_FD" in os.environ else (
        int(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1].isdigit() else None
    )

    ctrl = RTL8812AUController(fd=fd)

    print("\n" + "=" * 65)
    print("  📶 REALTEK RTL8812AU USERSPACE USB CONTROLLER (LIBUSB / USBDEVFS)")
    print("=" * 65)
    print(f"Device Chipset:     {ctrl.device_info['chipset']} ({ctrl.device_info['vid']}:{ctrl.device_info['pid']})")
    print(f"Hardware MAC:       {ctrl.device_info['mac_address']}")
    print(f"Status:             {ctrl.device_info['status']}")
    print(f"SYS_CFG (0x00F0):   {ctrl.device_info.get('sys_cfg', 'N/A')}")
    print(f"Command Reg (0x100):{ctrl.device_info.get('cr_reg', 'N/A')}")
    print("Active Endpoints:   RX=0x81, TX_HIGH=0x02, TX_NORM=0x03, TX_LOW=0x04")
    print("=" * 65 + "\n")

    # Capture test: poll Bulk IN endpoint 0x81 for 3 seconds
    print("[RX] Listening on Bulk Endpoint 0x81 (3-second diagnostic sample)...")
    start_t = time.time()
    rx_count = 0
    while time.time() - start_t < 3.0:
        pkt = ctrl.read_bulk_packet(timeout_ms=100)
        if pkt:
            rx_count += 1
            print(f"  [PKT #{rx_count}] {len(pkt)} bytes: {pkt[:32].hex()}...")
    
    print(f"[RX] Completed sample. Total packets captured: {rx_count}")
    ctrl.close()


if __name__ == "__main__":
    main()
