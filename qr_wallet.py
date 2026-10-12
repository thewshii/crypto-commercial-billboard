"""
QR Code Wallet Generator & Terminal Billboard for Solana Pump.fun.
Renders scannable ASCII/Unicode QR codes directly in Termux for 2-phone stream viewers.
Provides:
- generate_terminal_qr(address_or_uri): Generates 35-col scannable QR code string.
- render_qr_billboard_panel(): Full Rich Panel with side-by-side QR code and value pricing.
- Standalone CLI runner: python3 qr_wallet.py
"""

import os
import io
from typing import Optional
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich import box

import config

DEFAULT_WALLET = "9CCWeKbQhS6WGFGbgk68M9SDmT9B45C1gYPDo5PdSpWZ"


def get_public_wallet() -> str:
    """Derive Solana public address from config private key or return default."""
    try:
        import base58
        import nacl.signing
        priv = getattr(config, "SOLANA_PRIVATE_KEY", "").strip()
        if priv:
            raw_key = base58.b58decode(priv)
            signer = nacl.signing.SigningKey(raw_key[:32])
            pub = base58.b58encode(bytes(signer.verify_key)).decode("ascii")
            if pub and len(pub) >= 32:
                return pub
    except Exception:
        pass
    return DEFAULT_WALLET


def format_grouped_wallet(address: str) -> str:
    """Format 44-character base58 address into clean 4-character chunks for mobile readability."""
    chunks = [address[i:i+4] for i in range(0, len(address), 4)]
    return " ".join(chunks)


def generate_terminal_qr(data: str, border: int = 1) -> str:
    """
    Generate a high-contrast, scannable terminal QR code using Unicode block characters.
    Optimized for phone camera scanners (Phantom, Solflare, iOS Camera, Google Lens).
    """
    try:
        import qrcode
        qr = qrcode.QRCode(
            version=None,
            error_correction=qrcode.constants.ERROR_CORRECT_M,
            box_size=1,
            border=border
        )
        qr.add_data(data)
        qr.make(fit=True)
        buf = io.StringIO()
        qr.print_ascii(out=buf, invert=True)
        return buf.getvalue().rstrip()
    except Exception as e:
        # Fallback ASCII representation if qrcode is not present
        return (
            "┌─────────────────────────────┐\n"
            "│   [QR CODE SCAN HERE]       │\n"
            "│  Address:                   │\n"
            f"│  {data[:24]}...│\n"
            "└─────────────────────────────┘"
        )


def render_qr_billboard_panel(wallet_addr: Optional[str] = None, width: Optional[int] = None) -> Panel:
    """
    Render a zoom-proof Electronic Highway Billboard Panel for mobile Termux.
    - Stacked vertical layout: 100% zoom-proof on 38+ col screens.
    - Scannable QR code centered on its own row without wrapping (35 cols).
    - High-contrast block styling with zero fragile ASCII art that shatters when zoomed.
    """
    wallet = wallet_addr or get_public_wallet()
    wallet_grouped = format_grouped_wallet(wallet)
    solana_uri = f"solana:{wallet}"

    # Generate scannable QR code for the Solana URI (width 35, border 1)
    qr_ascii = generate_terminal_qr(solana_uri, border=1)

    body = (
        "[bold black on yellow] 🐘 THE ELEPHANT: ZERO CODE DISTRIBUTED 🐘 [/bold black on yellow]\n"
        "[bold white on red] 🛑 DO NOT BUY • KEEP YOUR SOL • 99.8% ARE MARKS 🛑 [/bold white on red]\n"
        "[bold yellow]⚠️ CONSULT = OPPORTUNITY FOR 1 TO 3 QUESTIONS ONLY[/bold yellow]\n"
        "[bold cyan]📡 VALUE IS SNR (0.1% SIGNAL / 99.9% NOISE)[/bold cyan]\n"
        "[bold magenta]🕊️ 1 COR 9:22: SAVE SOME, NOT ALL[/bold magenta]\n\n"
        f"{qr_ascii}\n\n"
        "[bold yellow]🏛️ SOLANA TREASURY (SCAN WITH 2ND PHONE):[/bold yellow]\n"
        f"[bold white on black] {wallet_grouped} [/bold white on black]\n"
        "[bold green]💎 $10–$15 Disciplined | $50–$500 Ape | $1 Mite[/bold green]\n"
        "[bold red]⚠️ 1 TO 3 QUESTIONS MAX — ZERO SOURCE CODE[/bold red]\n"
        "[dim]📜 Official Host Verified • Whisper in BIGO DM[/dim]\n"
        "[dim]⌨️ 'y' YOLO | 'v' Views | 'b' Altar View | 'q' Stop[/dim]"
    )

    return Panel(
        body,
        title="[bold yellow]⚡ ELEPHANT IN THE ROOM 🐘⚡[/bold yellow]",
        border_style="bold yellow",
        box=box.ROUNDED
    )


if __name__ == "__main__":
    console = Console()
    console.print(render_qr_billboard_panel())

