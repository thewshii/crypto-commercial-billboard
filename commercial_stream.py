#!/usr/bin/env python3
"""
CRYPTO RUG FILTER — Autonomous BIGO LIVE Commercial Streamer & Billboard.
High-impact animated commercial billboard for BIGO LIVE mobile streaming.
Features:
- Value-based pricing ($10 and up): 'Money is an illusion — pay what it is worth to you.'
- 6 rotating high-contrast narrative slides with tailored ASCII figlet banners.
- Multi-channel sound effects on slide transitions via Android speaker (sounds.py).
- Prominent, easy-to-read Solana public wallet address + 3-step send guide.
- Real-time live expectancy stats pulled from trade_history.json.
- Dynamic scrolling marquee ticker at bottom.
- Interactive hotkeys: [Space] Pause/Play | [n] Next | [p] Prev | [s] Sound Mute | [q] Quit.
"""

import os
import sys
import time
import json
import select
import termios
import tty
import shutil
import argparse
import signal
import subprocess
from typing import Dict, Any, List, Optional
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich import box
import pyfiglet

class AdLoopPlayer:
    def __init__(self):
        self.proc = None

    def play(self, sound_type: str):
        self.stop()
        wav_path = os.path.join(os.path.dirname(__file__), "sounds", f"{sound_type}.wav")
        if os.path.exists(wav_path) and shutil.which("play-audio"):
            try:
                self.proc = subprocess.Popen(
                    ["sh", "-c", f"while true; do play-audio -s media '{wav_path}'; done"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    preexec_fn=os.setsid
                )
            except Exception:
                pass

    def stop(self):
        if self.proc:
            try:
                os.killpg(os.getpgid(self.proc.pid), signal.SIGTERM)
            except Exception:
                pass
            self.proc = None

import config
from sounds import play_audio_file, ensure_sound_files, BackgroundMusicPlayer

# Initialize Rich Console
console = Console()

# Derive or fallback public wallet address
DEFAULT_WALLET = "9CCWeKbQhS6WGFGbgk68M9SDmT9B45C1gYPDo5PdSpWZ"

# The concept of exclusive (bijective) mathematical wiring introduced into the commercial stream.
EXCLUSIVE_WIRING_CONCEPT = (
    "In a mathematical context, saying an individual element, mapping, or system is \"wired exclusively\" "
    "translates directly to bijective (one-to-one and onto) functions or strict logical equivalences (P iff Q). "
    "An exclusively wired system has an absolute, unbreakable, perfectly paired connection between two sets of data: "
    "injective (no two inputs share one output) and surjective (no output is left unmatched). "
    "Travel is perfectly unambiguous in both directions, a to Z and Z to a: input to output and back again. "
    "Like a private key exclusively paired to its public key, or one Cartesian (x, y) address per point. Stand firm on whatever you say."
)

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


def get_live_stats() -> Dict[str, Any]:
    """Extract live trading stats from trade_history.json if available."""
    history_file = "trade_history.json"
    stats = {
        "n_confirmed": 22,
        "win_rate": 18.2,
        "payoff_ratio": 13.6,
        "ev_usd": 0.21,
        "avg_win": 1.71,
        "avg_loss": -0.13,
        "profit_factor": 3.0,
        "pnl_usd": 4.57
    }
    if os.path.exists(history_file):
        try:
            with open(history_file, "r", encoding="utf-8") as f:
                trades = json.load(f)
            confirmed = [
                t for t in trades
                if t.get("exit_tx_hash") and t.get("exit_tx_hash") != "broadcast_submitted"
                and len(str(t.get("exit_tx_hash")).strip()) >= 40
            ]
            if confirmed:
                fee_rt = 0.11
                real_usd = [float(t.get("pnl_usd", 0.0)) - fee_rt for t in confirmed]
                wins_usd = [r for r in real_usd if r > 0]
                losses_usd = [r for r in real_usd if r <= 0]
                n = len(confirmed)
                stats["n_confirmed"] = n
                stats["win_rate"] = (len(wins_usd) / n * 100.0) if n > 0 else 0.0
                stats["avg_win"] = (sum(wins_usd) / len(wins_usd)) if wins_usd else 0.0
                stats["avg_loss"] = (sum(losses_usd) / len(losses_usd)) if losses_usd else 0.0
                stats["pnl_usd"] = sum(real_usd)
                loss_mag = abs(stats["avg_loss"])
                stats["payoff_ratio"] = (stats["avg_win"] / loss_mag) if loss_mag > 0 else 0.0
                stats["ev_usd"] = (stats["win_rate"] / 100.0 * stats["avg_win"]) + ((1.0 - stats["win_rate"] / 100.0) * stats["avg_loss"])
                sum_losses = sum(abs(l) for l in losses_usd)
                stats["profit_factor"] = (sum(wins_usd) / sum_losses) if sum_losses > 0 else 0.0
        except Exception:
            pass
    return stats


class CommercialBillboard:
    def __init__(
        self,
        wallet_addr: Optional[str] = None,
        slide_duration: float = 7.0,
        sound_enabled: bool = True,
        music_enabled: bool = True,
        initial_track: int = 1
    ):
        self.wallet = wallet_addr or get_public_wallet()
        self.wallet_grouped = format_grouped_wallet(self.wallet)
        self.slide_duration = slide_duration
        self.sound_enabled = sound_enabled
        self.music_enabled = music_enabled
        self.music_player = BackgroundMusicPlayer(initial_track_idx=max(0, initial_track - 1))
        self.ad_player = AdLoopPlayer()
        self.current_slide_idx = 0
        self.is_paused = False
        self.last_transition_time = time.time()
        self.stats = get_live_stats()
        self.marquee_offset = 0

        # Build full marquee text line
        self.marquee_text = (
            f" ⚡ CRYPTO RUG FILTER ⚡ "
            f"🐘 THE ELEPHANT IN THE ROOM: YOU WILL LIKELY GET ZERO CODE ⚡ "
            f"OPPORTUNITY FOR 1 TO 3 QUESTIONS ONLY — MINDSET AUDIT ONLY ⚡ "
            f"🛑 DO NOT SEND MONEY! WE ARE ACTIVELY PUSHING YOU AWAY ⚡ "
            f"WHERE VALUE LIVES: 99.9% IS DEAFENING NOISE — VALUE IS IN THE 0.1% SIGNAL (SNR) ⚡ "
            f"1 CORINTHIANS 9:22: 'THAT I MIGHT BY ALL MEANS SAVE SOME — NOT ALL, BUT SOME' ⚡ "
            f"OVERTURNING THE TABLES OF THE PUMP.FUN MONEY CHANGERS ⚡ "
            f"3-CARD MONTE ON SOLANA — DON'T BE THE MARK ⚡ "
            f"MONEY IS JUST AN ILLUSION — MASTER IT BEFORE IT MASTERS YOU ⚡ "
            f"DEAR MODS: WE ARE OFFICIAL HOSTS WITH PERMISSION — RELAX THE BAN HAMMER ⚡ "
            f"THIS IS NOT A PITCH — THIS IS PURE EDUCATIONAL CONTENT & SPIRITUAL PARABLES ⚡ "
            f"HE THAT HATH A SECOND PHONE TO SCAN, LET HIM SCAN (SLIDE 12 / 'b' KEY) ⚡ "
            f"TEMPLE TREASURY: {self.wallet} ⚡ "
            f"13.6x PAYOFF RATIO (+${self.stats['ev_usd']:.2f}/TRADE) ⚡ "
            f"RENDER UNTO CAESAR HIS COMPLIANCE, RENDER UNTO TRUTH YOUR MINDSET ⚡ "
f"WIRED EXCLUSIVELY (BIJECTION: 1-TO-1 & ONTO) ⚡ A TO Z AND Z TO A ⚡ STAND FIRM ON WHATEVER YOU SAY ⚡ "
f"IGNORE THE FRAUD-CALLERS & WORD-SALAD TORNADOES — STAND FIRM ⚡ "
        )

        ensure_sound_files()

    def get_slide_count(self) -> int:
        return 24

    def play_slide_sound(self, sound_type: str):
        if self.sound_enabled:
            play_audio_file(sound_type)

    def render_slide_banner(self, text: str, color: str = "bold yellow", font: str = "standard") -> str:
        clean = text.replace("\n", " ").strip().upper()
        
        # Color mapping
        rgb = (255, 255, 50) # default yellow
        if "red" in color: rgb = (255, 50, 50)
        elif "cyan" in color: rgb = (50, 255, 255)
        elif "green" in color: rgb = (50, 255, 50)
        elif "magenta" in color: rgb = (255, 50, 255)
        
        try:
            import pixelart
            # 20px height takes 10 terminal lines. Large enough to read, compact enough to fit things.
            lines = pixelart.render_text(clean, px_height=20, fg=rgb)
            fig = "\n".join(lines)
            return fig
        except Exception:
            try:
                fig = pyfiglet.figlet_format(clean, font=font)
                return f"[{color}]{fig}[/{color}]"
            except:
                return clean

    def build_slide_1_problem(self) -> Panel:
        """Slide 1: THE BRUTAL TRUTH / PROBLEM."""
        banner = self.render_slide_banner("STOP SCAMS", color="bold red")
        from rich.console import Group
        from rich.text import Text
        banner_render = Text.from_ansi(banner) if "\x1b" in banner else Text.from_markup(banner)
        body = Group(banner_render, Text.from_markup("\n\n[bold white]Slide 1: THE BRUTAL TRUTH / PROBLEM.[/bold white]"))
        from rich.align import Align
        return Panel(Align.center(body),
            title="[bold red]⚠️ 1/12: STOP SCAMS 🐘[/bold red]",
            border_style="bold red",
            box=box.ROUNDED
        )

    def build_slide_2_three_card_monte(self) -> Panel:
        """Slide 2: 3-CARD MONTE — THE SOLANA SHELL GAME."""
        banner = self.render_slide_banner("3-CARD MONTE", color="bold yellow")
        from rich.console import Group
        from rich.text import Text
        banner_render = Text.from_ansi(banner) if "\x1b" in banner else Text.from_markup(banner)
        body = Group(banner_render, Text.from_markup("\n\n[bold white]Slide 2: 3-CARD MONTE — THE SOLANA SHELL GAME.[/bold white]"))
        from rich.align import Align
        return Panel(Align.center(body),
            title="[bold yellow]🃏 2/12: 3-CARD MONTE 🐘[/bold yellow]",
            border_style="bold yellow",
            box=box.ROUNDED
        )

    def build_slide_3_money_illusion(self) -> Panel:
        """Slide 3: ALL ILLUSION — MONEY IS JUST AN ILLUSION."""
        banner = self.render_slide_banner("ALL ILLUSION", color="bold magenta")
        from rich.console import Group
        from rich.text import Text
        banner_render = Text.from_ansi(banner) if "\x1b" in banner else Text.from_markup(banner)
        body = Group(banner_render, Text.from_markup("\n\n[bold white]Slide 3: ALL ILLUSION — MONEY IS JUST AN ILLUSION.[/bold white]"))
        from rich.align import Align
        return Panel(Align.center(body),
            title="[bold magenta]👁️ 3/12: ALL ILLUSION 🐘[/bold magenta]",
            border_style="bold magenta",
            box=box.ROUNDED
        )

    def build_slide_4_master_it(self) -> Panel:
        """Slide 4: MASTER IT — BEFORE IT MASTERS YOU."""
        banner = self.render_slide_banner("MASTER IT", color="bold green")
        from rich.console import Group
        from rich.text import Text
        banner_render = Text.from_ansi(banner) if "\x1b" in banner else Text.from_markup(banner)
        body = Group(banner_render, Text.from_markup("\n\n[bold white]Slide 4: MASTER IT — BEFORE IT MASTERS YOU.[/bold white]"))
        from rich.align import Align
        return Panel(Align.center(body),
            title="[bold green]⚔️ 4/12: MASTER IT 🐘[/bold green]",
            border_style="bold green",
            box=box.ROUNDED
        )

    def build_slide_5_weapon(self) -> Panel:
        """Slide 5: THE DEFENSE WEAPON — CRYPTO RUG FILTER."""
        banner = self.render_slide_banner("RUG FILTER", color="bold cyan")
        from rich.console import Group
        from rich.text import Text
        banner_render = Text.from_ansi(banner) if "\x1b" in banner else Text.from_markup(banner)
        body = Group(banner_render, Text.from_markup("\n\n[bold white]Slide 5: THE DEFENSE WEAPON — CRYPTO RUG FILTER.[/bold white]"))
        from rich.align import Align
        return Panel(Align.center(body),
            title="[bold cyan]🛰️ 5/12: RUG FILTER 🐘[/bold cyan]",
            border_style="bold cyan",
            box=box.ROUNDED
        )

    def build_slide_6_whale_spoofs(self) -> Panel:
        """Slide 6: MARKOV TEXT ENGINE — SINKING THE SHILLS."""
        banner = self.render_slide_banner("WHALE SPOOFS", color="bold red")
        from rich.console import Group
        from rich.text import Text
        banner_render = Text.from_ansi(banner) if "\x1b" in banner else Text.from_markup(banner)
        body = Group(banner_render, Text.from_markup("\n\n[bold white]Slide 6: MARKOV TEXT ENGINE — SINKING THE SHILLS.[/bold white]"))
        from rich.align import Align
        return Panel(Align.center(body),
            title="[bold red]🌊 6/12: WHALE SPOOFS 🐘[/bold red]",
            border_style="bold red",
            box=box.ROUNDED
        )

    def build_slide_7_dev_compass(self) -> Panel:
        """Slide 7: DEV INTENT & THE 120° COMPASS."""
        banner = self.render_slide_banner("DEV COMPASS", color="bold yellow")
        from rich.console import Group
        from rich.text import Text
        banner_render = Text.from_ansi(banner) if "\x1b" in banner else Text.from_markup(banner)
        body = Group(banner_render, Text.from_markup("\n\n[bold white]Slide 7: DEV INTENT & THE 120° COMPASS.[/bold white]"))
        from rich.align import Align
        return Panel(Align.center(body),
            title="[bold yellow]🧭 7/12: DEV COMPASS 🐘[/bold yellow]",
            border_style="bold yellow",
            box=box.ROUNDED
        )

    def build_slide_8_guardian(self) -> Panel:
        """Slide 8: TRADER GUARDIAN — ANTI-TILT PROTOCOL."""
        banner = self.render_slide_banner("GUARDIAN", color="bold cyan")
        from rich.console import Group
        from rich.text import Text
        banner_render = Text.from_ansi(banner) if "\x1b" in banner else Text.from_markup(banner)
        body = Group(banner_render, Text.from_markup("\n\n[bold white]Slide 8: TRADER GUARDIAN — ANTI-TILT PROTOCOL.[/bold white]"))
        from rich.align import Align
        return Panel(Align.center(body),
            title="[bold cyan]🛡️ 8/12: GUARDIAN 🐘[/bold cyan]",
            border_style="bold cyan",
            box=box.ROUNDED
        )

    def build_slide_9_philosophy(self) -> Panel:
        """Slide 9: THE VALUE PHILOSOPHY & PRICING."""
        banner = self.render_slide_banner("TRUE VALUE", color="bold magenta")
        from rich.console import Group
        from rich.text import Text
        banner_render = Text.from_ansi(banner) if "\x1b" in banner else Text.from_markup(banner)
        body = Group(banner_render, Text.from_markup("\n\n[bold white]Slide 9: THE VALUE PHILOSOPHY & PRICING.[/bold white]"))
        from rich.align import Align
        return Panel(Align.center(body),
            title="[bold magenta]💎 9/12: TRUE VALUE 🐘[/bold magenta]",
            border_style="bold magenta",
            box=box.ROUNDED
        )

    def build_slide_10_expectancy(self) -> Panel:
        """Slide 10: LIVE ON-CHAIN EXPECTANCY."""
        banner = self.render_slide_banner("13.6x PAYOFF", color="bold green")
        from rich.console import Group
        from rich.text import Text
        banner_render = Text.from_ansi(banner) if "\x1b" in banner else Text.from_markup(banner)
        body = Group(banner_render, Text.from_markup("\n\n[bold white]Slide 10: LIVE ON-CHAIN EXPECTANCY.[/bold white]"))
        from rich.align import Align
        return Panel(Align.center(body),
            title="[bold green]🎯 10/12: 13.6x PAYOFF 🐘[/bold green]",
            border_style="bold green",
            box=box.ROUNDED
        )

    def build_slide_11_how_to_buy(self) -> Panel:
        """Slide 11: HOW TO GET ACCESS — DEAR MODS SATIRE."""
        banner = self.render_slide_banner("DEAR MODS", color="bold yellow")
        from rich.console import Group
        from rich.text import Text
        banner_render = Text.from_ansi(banner) if "\x1b" in banner else Text.from_markup(banner)
        body = Group(banner_render, Text.from_markup("\n\n[bold white]Slide 11: HOW TO GET ACCESS — DEAR MODS SATIRE.[/bold white]"))
        from rich.align import Align
        return Panel(Align.center(body),
            title="[bold yellow]🛡️ 11/12: DEAR MODS 🐘[/bold yellow]",
            border_style="bold yellow",
            box=box.ROUNDED
        )

    def build_slide_12_wallet(self) -> Panel:
        """Slide 12: OFFICIAL WALLET ADDRESS & SCANNABLE QR BILLBOARD."""
        from qr_wallet import render_qr_billboard_panel
        return render_qr_billboard_panel(wallet_addr=self.wallet)

    def build_slide_exclusive_wiring(self) -> Panel:
        """Slide: WIRED EXCLUSIVELY — bijection as exclusive wiring."""
        banner = self.render_slide_banner("WIRED EXCLUSIVELY", color="bold cyan")
        from rich.console import Group
        from rich.text import Text
        banner_render = Text.from_ansi(banner) if "\x1b" in banner else Text.from_markup(banner)
        body = Group(banner_render, Text.from_markup(
            "\n\n[bold white]An exclusive wire is a bijection: injective AND surjective. "
            "Every node has exactly one dedicated partner. STAND FIRM on whatever you say.\n\n"
            "[dim]" + EXCLUSIVE_WIRING_CONCEPT + "[/dim]"
        ))
        from rich.align import Align
        from rich.panel import Panel
        return Panel(Align.center(body),
            title="[bold cyan]🔗 WIRED EXCLUSIVELY 🐘[/bold cyan]",
            border_style="bold cyan",
            box=box.ROUNDED
        )

    def _build_jackpot_generic(self, title, subtitle, prize):
        banner = self.render_slide_banner(title, color="bold white on green")
        from rich.console import Group
        from rich.text import Text
        from rich.panel import Panel
        from rich.align import Align
        banner_render = Text.from_ansi(banner) if "\x1b" in banner else Text.from_markup(banner)
        rest = (
            f"[blink bold red]🚨 EVERYBODY STOP! WE HAVE A WINNER! 🚨[/blink bold red]\n\n"
            f"[bold green]{subtitle.upper()}[/bold green]\n\n"
            f"💰 [bold white on green] {prize} [/bold white on green] 💰\n\n"
            f"🐘 [bold yellow]WAKE UP. THE HOUSE ALWAYS WINS.[/bold yellow] 🐘"
        )
        body = Group(banner_render, Text.from_markup(rest))
        return Panel(Align.center(body), title=f"[blink bold red]🎰 {title} 🎰[/blink bold red]", border_style="bold green", box=box.HEAVY)

    def _build_religion_generic(self, banner_text, color, subtitle, quote, punchline, lore, icon):
        banner = self.render_slide_banner(banner_text, color=color)
        from rich.console import Group
        from rich.text import Text
        from rich.panel import Panel
        from rich.align import Align
        banner_render = Text.from_ansi(banner) if "\x1b" in banner else Text.from_markup(banner)
        rest = (
            f"[bold yellow]{icon} {subtitle.upper()} {icon}[/bold yellow]\n\n"
            f"[bold green]⚡ {punchline.upper()} ⚡[/bold green]\n\n"
        )
        body = Group(banner_render, Text.from_markup(rest))
        return Panel(Align.center(body), title=f"[{color.split(' ')[-1]}]{icon} {banner_text} {icon}[/{color.split(' ')[-1]}]", border_style=color.split(' ')[-1], box=box.ROUNDED)

    def build_religion_1(self) -> Panel: return self._build_religion_generic("ROAR OF THE LION", "bold white on red", "TRIBE OF JUDAH", "The wicked flee when no one pursues, but the righteous are bold as a lion.", "THE HONEYPOTS ARE SHATTERED", "The Shofar has sounded. We are marching on the liquidity pools of the corrupt. No scammer is safe from the roar of accountability.", "🦁")
    def build_religion_2(self) -> Panel: return self._build_religion_generic("JERICHO PROTOCOL", "bold black on yellow", "SOUND THE SHOFAR", "And when they make a long blast with the ram's horn... the wall of the city will fall flat.", "THE WALLED GARDENS COLLAPSE", "The centralized exchanges thought their walls were impenetrable. Seven trumpet blasts later, their order books are exposed to the light.", "🎺")
    def build_religion_3(self) -> Panel: return self._build_religion_generic("SWORD OF TRUTH", "bold white on magenta", "RIGHTEOUS WARFARE", "He trains my hands for war, so that my arms can bend a bow of bronze.", "SNIPER BOTS VANQUISHED", "We do not bring peace to the rug-pullers, we bring a sword. The smart contracts have been audited by divine fury.", "⚔️")
    def build_religion_4(self) -> Panel: return self._build_religion_generic("DIVINE RETRIBUTION", "bold white on green", "JUSTICE DELIVERED", "Vengeance is mine, I will repay, says the Lord.", "DEV WALLETS SEIZED", "You thought you could dump on the community and hide in the metaverse? The Lion of Judah tracks all transactions on the public ledger.", "🔥")
    def build_religion_5(self) -> Panel: return self._build_religion_generic("COVENANT OF IRON", "bold white on blue", "UNBREAKABLE SHIELD", "No weapon that is fashioned against you shall succeed.", "FLASH LOAN ATTACKS DEFLECTED", "The armor of truth protects our holdings. The enemy's algorithms shatter against the shield of our diamond-handed faith.", "🛡️")
    def build_religion_6(self) -> Panel: return self._build_religion_generic("HOLY CRUSADE", "bold white on red", "MARCH TO VICTORY", "Be strong and courageous. Do not be frightened, and do not be dismayed.", "THE BULL MARKET CONQUERED", "The war drums are beating. We march together to reclaim the blockchain for the honest, the builders, and the believers.", "🚩")
    def _build_jackpot_generic(self, title, subtitle, prize):
        banner = self.render_slide_banner(title, color="bold white on green")
        from rich.console import Group
        from rich.text import Text
        from rich.panel import Panel
        from rich.align import Align
        banner_render = Text.from_ansi(banner) if "\x1b" in banner else Text.from_markup(banner)
        rest = (
            f"[blink bold red]🚨 EVERYBODY STOP! WE HAVE A WINNER! 🚨[/blink bold red]\n\n"
            f"[bold green]{subtitle.upper()}[/bold green]\n\n"
            f"💰 [bold white on green] {prize} [/bold white on green] 💰\n\n"
            f"🐘 [bold yellow]WAKE UP. THE HOUSE ALWAYS WINS.[/bold yellow] 🐘"
        )
        body = Group(banner_render, Text.from_markup(rest))
        return Panel(Align.center(body), title=f"[blink bold red]🎰 {title} 🎰[/blink bold red]", border_style="bold green", box=box.HEAVY)

    def build_jackpot_1(self) -> Panel: return self._build_jackpot_generic("JACKPOT WINNER!", "YOU have been randomly selected as the 1,000,000th VIEWER!", "CLAIM YOUR FREE 500 SOL NOW!")
    def build_jackpot_2(self) -> Panel: return self._build_jackpot_generic("GAME SHOW GRAND PRIZE!", "You are our lucky studio audience member!", "STEP RIGHT UP FOR 1000x RETURNS!")
    def build_jackpot_3(self) -> Panel: return self._build_jackpot_generic("LOTTERY NUMBER MATCH!", "Your IP address matched the golden ticket!", "REDEEM YOUR MILLION DOLLAR AIRDROP!")
    def build_jackpot_4(self) -> Panel: return self._build_jackpot_generic("SPIN THE WHEEL WINNER!", "The wheel landed on the ultimate multiplier!", "CLICK TO SPIN FOR YOUR FREE TOKENS!")
    def build_jackpot_5(self) -> Panel: return self._build_jackpot_generic("HIGH SCORE UNLOCKED!", "You broke the algorithm and beat the system!", "MINT YOUR EXCLUSIVE REWARD NFT NOW!")
    def build_jackpot_6(self) -> Panel: return self._build_jackpot_generic("SYSTEM ERROR PAYOUT!", "A glitch in our smart contract favored YOU!", "URGENT: WITHDRAW FUNDS BEFORE PATCH!")

    def _build_lawyer_generic(self, subtitle, hook, promise, icon="⚖️"):
        banner = self.render_slide_banner("LAW FIRM", color="bold white on red")
        from rich.console import Group
        from rich.text import Text
        from rich.panel import Panel
        from rich.align import Align
        banner_render = Text.from_ansi(banner) if "\x1b" in banner else Text.from_markup(banner)
        rest = (
            f"[bold yellow]{icon} {subtitle.upper()} {icon}[/bold yellow]\n\n"
            f"[bold red]⚡ {hook.upper()} ⚡[/bold red]\n\n"
            f"[bold cyan]📞 CALL THE CRYPTO RUG FILTER TODAY! 📞[/bold cyan]"
        )
        body = Group(banner_render, Text.from_markup(rest))
        return Panel(Align.center(body), title="[bold red]⚖️ LAW FIRM ⚖️[/bold red]", border_style="bold red", box=box.HEAVY)

    def _build_alien_generic(self, subtitle, hook, truth, icon="🛸"):
        banner = self.render_slide_banner("GALACTIC TRUTH", color="bold black on cyan")
        from rich.console import Group
        from rich.text import Text
        from rich.panel import Panel
        from rich.align import Align
        banner_render = Text.from_ansi(banner) if "\x1b" in banner else Text.from_markup(banner)
        rest = (
            f"[bold yellow]{icon} {subtitle.upper()} {icon}[/bold yellow]\n\n"
            f"[bold cyan]🛸 {hook.upper()} 🛸[/bold cyan]\n\n"
            f"[bold magenta]⚡ {truth.upper()} ⚡[/bold magenta]"
        )
        body = Group(banner_render, Text.from_markup(rest))
        return Panel(Align.center(body), title="[bold cyan]👽 GALACTIC TRUTH 👽[/bold cyan]", border_style="bold cyan", box=box.HEAVY)

    def _build_news_generic(self, title, quote, punchline):
        from rich.panel import Panel
        from rich import box
        banner = self.render_slide_banner("BREAKING NEWS", color="bold black on white")
        from rich.console import Group
        from rich.text import Text
        from rich.align import Align
        banner_render = Text.from_ansi(banner) if "\x1b" in banner else Text.from_markup(banner)
        rest = (
            f"[bold yellow]📻 1980s SYNTH-WAVE UPDATE... 📻[/bold yellow]\n\n"
            f"[italic cyan]\"{quote}\"[/italic cyan]\n\n"
            f"[bold green]⚡ {punchline.upper()} ⚡[/bold green]"
        )
        body = Group(banner_render, Text.from_markup(rest))
        return Panel(Align.center(body), title=f"[bold white]📰 {title} 📰[/bold white]", border_style="bold white", box=box.HEAVY)

    def _build_singapore_generic(self, title, quote, punchline):
        from rich.panel import Panel
        from rich import box
        banner = self.render_slide_banner("SINGAPORE FINTECH", color="bold white on red")
        from rich.console import Group
        from rich.text import Text
        from rich.align import Align
        banner_render = Text.from_ansi(banner) if "\x1b" in banner else Text.from_markup(banner)
        rest = (
            f"[bold yellow]🇸🇬 MAS COMPLIANT SMART CONTRACT 🇸🇬[/bold yellow]\n\n"
            f"[italic cyan]\"{quote}\"[/italic cyan]\n\n"
            f"[bold green]⚡ {punchline.upper()} ⚡[/bold green]"
        )
        body = Group(banner_render, Text.from_markup(rest))
        return Panel(Align.center(body), title=f"[bold blue]🏙️ {title} 🏙️[/bold blue]", border_style="bold blue", box=box.HEAVY)

    def build_lawyer_1(self) -> Panel: return self._build_lawyer_generic("DEV DUMP INJURY", "I was promised a moon, but I woke up with bags.", "We will garnish the dev's meme tokens!")
    def build_lawyer_2(self) -> Panel: return self._build_lawyer_generic("BOT MANIPULATION", "The sniper bots took my liquidity!", "Sue the algorithm! Justice for meatbags!")
    def build_lawyer_3(self) -> Panel: return self._build_lawyer_generic("EMOTIONAL DISTRESS", "The green candles were an illusion.", "Compensation for your phantom gains!")
    def build_lawyer_4(self) -> Panel: return self._build_lawyer_generic("CLASS ACTION SETTLEMENT", "I bought the dip, but the dip kept dipping.", "Join the multi-wallet class action lawsuit today!")
    def build_lawyer_5(self) -> Panel: return self._build_lawyer_generic("SMART CONTRACT MALPRACTICE", "The audit said it was safe...", "We prosecute negligent auditors and their ChatGPT prompts!")
    def build_lawyer_6(self) -> Panel: return self._build_lawyer_generic("STAKING INJURY", "My locked tokens evaporated into the ether.", "Get compensated for unregistered security trauma!")

    def build_alien_1(self) -> Panel: return self._build_alien_generic("DARK MATTER YIELD", "My Earth yields are only 12% APY.", "Farm literal black holes for infinite APY!")
    def build_alien_2(self) -> Panel: return self._build_alien_generic("TELEPATHIC TRADING", "I missed the pump because of fat fingers.", "Execute trades before you even think them!")
    def build_alien_3(self) -> Panel: return self._build_alien_generic("QUANTUM LIQUIDITY", "The order book is too thin.", "Trade across infinite parallel universes!")

    def build_news_1(self) -> Panel: return self._build_news_generic("AI STRIKE", "We demand better prompts!", "AGI refuses to write another smart contract!")
    def build_news_2(self) -> Panel: return self._build_news_generic("MEME COIN INFLATION", "Dog tokens outnumber actual dogs.", "Federal Reserve to start printing doge!")
    def build_news_3(self) -> Panel: return self._build_news_generic("METAVERSE REAL ESTATE", "I bought a digital house.", "Market crash leaves users virtually homeless!")
    def build_news_4(self) -> Panel: return self._build_news_generic("BLOCKCHAIN CONGESTION", "Transactions stuck for 72 hours.", "Traffic cop deployed to Solana mainnet!")
    def build_news_5(self) -> Panel: return self._build_news_generic("DEV WALLET MOVEMENT", "They said they burned the keys.", "Local dev caught fleeing to the metaverse on a virtual yacht!")
    def build_news_6(self): return self._build_news_generic("CEX INSOLVENCY", "Funds are SAFU, trust us.", "CEO accidentally sent cold wallet to a burn address!")

    def build_singapore_1(self): return self._build_singapore_generic("MERLION LIQUIDITY", "The fountain of wealth is now an automated market maker.", "Stake in the Marina Bay Sands pool!")
    def build_singapore_2(self): return self._build_singapore_generic("FINTECH OPTIMIZATION", "Your latency is dishonorable.", "We execute trades before the block is even proposed!")
    def build_singapore_3(self): return self._build_singapore_generic("TAX HAVEN PROTOCOL", "Why pay taxes when you can pay gas fees?", "Relocate your digital assets to our sovereign rollup!")

    def get_slide_panel(self, idx: int) -> Panel:
        normal_slides = [
            self.build_slide_1_problem, self.build_slide_2_three_card_monte,
            self.build_slide_3_money_illusion, self.build_slide_4_master_it,
            self.build_slide_5_weapon, self.build_slide_6_whale_spoofs,
            self.build_slide_7_dev_compass, self.build_slide_8_guardian,
            self.build_slide_9_philosophy, self.build_slide_10_expectancy,
            self.build_slide_11_how_to_buy, self.build_slide_12_wallet,
            self.build_slide_exclusive_wiring,
        ]
        
        religion = [self.build_religion_1, self.build_religion_2, self.build_religion_3, self.build_religion_4, self.build_religion_5, self.build_religion_6]
        jackpot = [self.build_jackpot_1, self.build_jackpot_2, self.build_jackpot_3, self.build_jackpot_4, self.build_jackpot_5, self.build_jackpot_6]
        lawyer = [self.build_lawyer_1, self.build_lawyer_2, self.build_lawyer_3, self.build_lawyer_4, self.build_lawyer_5, self.build_lawyer_6]
        alien = [self.build_alien_1, self.build_alien_2, self.build_alien_3]
        news = [self.build_news_1, self.build_news_2, self.build_news_3, self.build_news_4, self.build_news_5, self.build_news_6]
        singapore = [self.build_singapore_1, self.build_singapore_2, self.build_singapore_3]
        
        if idx % 2 == 0:
            return normal_slides[(idx // 2) % len(normal_slides)]()
        else:
            ad_idx = idx // 2
            ad_type = ad_idx % 6
            if ad_type == 0: return religion[ad_idx % len(religion)]()
            elif ad_type == 1: return jackpot[ad_idx % len(jackpot)]()
            elif ad_type == 2: return lawyer[ad_idx % len(lawyer)]()
            elif ad_type == 3: return alien[ad_idx % len(alien)]()
            elif ad_type == 4: return news[ad_idx % len(news)]()
            else: return singapore[ad_idx % len(singapore)]()

    def get_slide_sound_type(self, idx: int) -> str:
        normal_sound_map = [
            "airlock", "footsteps", "yell", "pa_chime", "door", "running",
            "scanner", "scream", "coin", "fanfare", "airlock", "coin"
        ]
        
        if idx % 2 == 0:
            return normal_sound_map[(idx // 2) % len(normal_sound_map)]
        else:
            ad_idx = idx // 2
            ad_type = ad_idx % 6
            if ad_type == 0:
                religions = ["religion_1", "religion_2", "religion_3", "religion_4", "religion_5", "religion_6"]
                return religions[ad_idx % len(religions)]
            elif ad_type == 1:
                jackpots = ["jackpot_1", "jackpot_2", "jackpot_3", "jackpot_4", "jackpot_5", "jackpot_6"]
                return jackpots[ad_idx % len(jackpots)]
            elif ad_type == 2:
                return "rock_lawyer"
            elif ad_type == 3:
                return "alien_ad"
            elif ad_type == 4:
                return "news_ticker"
            else:
                return "singapore_ad"

    def render_marquee_bar(self, width: int = 76) -> str:
        """Render smooth scrolling marquee ticker."""
        txt = self.marquee_text
        n = len(txt)
        start = self.marquee_offset % n
        if start + width <= n:
            visible = txt[start:start+width]
        else:
            visible = txt[start:] + txt[:width - (n - start)]
        self.marquee_offset = (self.marquee_offset + 1) % n
        return f"[bold black on yellow]{visible}[/bold black on yellow]"

    def render_status_bar(self, width: int = 80) -> str:
        sound_status = "[bold green]🔊 SFX ON[/bold green]" if self.sound_enabled else "[bold red]🔇 SFX OFF[/bold red]"
        track_title = self.music_player.get_current_track_title()
        track_short = self.music_player.get_current_track_short()
        music_status = f"[bold green]🎵 {track_title}[/bold green]" if self.music_enabled else "[bold red]🔇 MUSIC OFF[/bold red]"
        pause_status = "[bold yellow]⏸️ PAUSED[/bold yellow]" if self.is_paused else "[bold green]▶️ LIVE[/bold green]"
        if width < 60:
            music_s = f"[bold green]{track_short}[/bold green]" if self.music_enabled else "[bold red]🔇m[/bold red]"
            sound_s = "🔊" if self.sound_enabled else "🔇"
            return (
                f" {pause_status} | {music_s} | {sound_s} | Slide [bold white]{self.current_slide_idx + 1}/{self.get_slide_count()}[/bold white]\n"
                f" [dim]\\[Space] Pause | \\[t] Track | \\[m] Mute | \\[s] SFX | \\[n] Next | \\[q] Quit[/dim]"
            )
        return (
            f" {pause_status} | {music_status} | {sound_status} | Slide [bold white]{self.current_slide_idx + 1}/{self.get_slide_count()}[/bold white] | "
            f"[dim]Hotkeys: \\[Space] Pause | \\[t] Track | \\[m] Mute | \\[s] SFX | \\[n] Next | \\[p] Prev | \\[q] Quit[/dim]"
        )

    def _handle_slide_audio(self):
        # Pause background music on interruptions (ad slides: idx % 2 == 1)
        if self.current_slide_idx % 2 == 1:
            if hasattr(self, 'music_player') and self.music_player and self.music_player.enabled and not self.music_player.is_paused:
                self.music_player.next_track()
                self.music_player.pause()
            if self.sound_enabled:
                self.ad_player.play(self.get_slide_sound_type(self.current_slide_idx))
        else:
            if hasattr(self, 'music_player') and self.music_player and self.music_player.enabled and self.music_player.is_paused:
                self.music_player.resume()
            self.ad_player.stop()
            self.play_slide_sound(self.get_slide_sound_type(self.current_slide_idx))

    def next_slide(self):
        self.current_slide_idx = (self.current_slide_idx + 1) % self.get_slide_count()
        self.last_transition_time = time.time()
        self._handle_slide_audio()

    def prev_slide(self):
        self.current_slide_idx = (self.current_slide_idx - 1) % self.get_slide_count()
        self.last_transition_time = time.time()
        self._handle_slide_audio()

    def run_stream_loop(self):
        """Main non-blocking streaming commercial loop."""
        # Setup raw terminal for hotkey interception
        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)
        try:
            tty.setcbreak(fd)
            # Start background soundtrack
            if self.music_enabled:
                self.music_player.start()
            # Play initial chime
            self._handle_slide_audio()

            while True:
                cols, _ = shutil.get_terminal_size((80, 24))
                term_w = max(34, min(100, cols - 2))

                # Clear screen and draw slide
                console.clear()

                # 1. Top Live Stream Header
                if cols < 55:
                    top_header = "[bold red]🔴 BIGO LIVE[/bold red] | [bold yellow]OFFICIAL BILLBOARD[/bold yellow] | [bold cyan]$10+[/bold cyan]"
                else:
                    top_header = (
                        f"[bold red]🔴 BIGO LIVE BROADCAST[/bold red] | [bold yellow]CRYPTO RUG FILTER OFFICIAL BILLBOARD[/bold yellow] | "
                        f"[bold cyan]VALUE SCALE: $10+[/bold cyan]"
                    )
                console.print(Panel(top_header, box=box.HORIZONTALS, border_style="bold red"))

                # 2. Main Slide Panel
                panel = self.get_slide_panel(self.current_slide_idx)
                console.print(panel)

                # 3. Dynamic Scrolling Marquee
                marquee = self.render_marquee_bar(width=term_w)
                console.print(marquee)

                # 3.5 Absurd Animation (Guy and Girl getting pulled back and forth non stop)
                anim_frames = [
                    "[yellow]         O     [|]     O        \n        /|\\    [|]    /|\\       \n        / \\    [|]    / \\       [/yellow]",
                    "[yellow]          O    [|]    O         \n         /|\\===[|]===/|\\        \n         < \\   [|]   />         [/yellow]",
                    "[yellow]           O   (()   O          \n          /|\\==(()==/|\\         \n          <<   (()   >>         [/yellow]",
                    "[yellow]           O   {*}   O          \n          /|\\=={*}==/|\\         \n          <<   {*}   >>         [/yellow]",
                    "[yellow]               { } O   O        \n               { }/|\\ /|\\       \n               { }/ \\ / \\       [/yellow]",
                    "[yellow]               { } !   !        \n               { } O   O        \n               { }/|\\ /|\\       \n               { }/ \\ / \\       [/yellow]",
                    "[yellow]       O       { }       O      \n      /|\\      { }      /|\\     \n      / \\      { }      / \\     [/yellow]",
                    "[yellow] O             { }             O\n/|\\            { }            /|\\ \n/ \\            { }            / \\ [/yellow]",
                    "[yellow]\\\\             { }             //\n \\\\            { }            // \n  O            { }            O  [/yellow]",
                    "[yellow]               { }              \n               { }              \n               { }              [/yellow]"
                ]
                from rich.align import Align
                # Play at ~6 frames per second for a frantic tug-of-war
                frame = anim_frames[int(time.time() * 6) % len(anim_frames)]
                console.print(Align.center(frame))

                # 4. Status Bar
                console.print(self.render_status_bar(width=cols))

                # Non-blocking key check with 0.18s tick
                rlist, _, _ = select.select([sys.stdin], [], [], 0.18)
                if rlist:
                    ch = sys.stdin.read(1)
                    if ch in ('q', 'Q', '\x03'):  # quit or Ctrl+C
                        break
                    elif ch == ' ':
                        self.is_paused = not self.is_paused
                        if self.is_paused:
                            self.music_player.pause()
                            self.ad_player.stop()
                        else:
                            if self.current_slide_idx % 2 == 0:
                                self.music_player.resume()
                            else:
                                if self.sound_enabled:
                                    self.ad_player.play(self.get_slide_sound_type(self.current_slide_idx))
                    elif ch in ('m', 'M'):
                        self.music_enabled = self.music_player.toggle()
                    elif ch in ('t', 'T'):
                        self.music_player.next_track()
                    elif ch in ('s', 'S'):
                        self.sound_enabled = not self.sound_enabled
                        if not self.sound_enabled:
                            self.ad_player.stop()
                        elif self.current_slide_idx % 2 == 1:
                            self.ad_player.play(self.get_slide_sound_type(self.current_slide_idx))
                    elif ch in ('n', 'N'):
                        self.next_slide()
                    elif ch in ('p', 'P'):
                        self.prev_slide()
                    elif ch in ('b', 'B'):
                        self.play_slide_sound(self.get_slide_sound_type(self.current_slide_idx))

                # Auto-transition slides if not paused
                now = time.time()
                current_duration = self.slide_duration
                if self.current_slide_idx % 2 == 1:
                    current_duration *= 1.8  # Make ad slides 80% longer

                if not self.is_paused and (now - self.last_transition_time >= current_duration):
                    self.next_slide()

        except KeyboardInterrupt:
            pass
        finally:
            self.music_player.stop()
            if hasattr(self, 'ad_player'):
                self.ad_player.stop()
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
            console.clear()
            console.print("[bold green]Commercial Billboard stopped cleanly. Thanks for watching![/bold green]")


def main():
    parser = argparse.ArgumentParser(description="Crypto Rug Filter — BIGO Live Commercial Streamer")
    parser.add_argument("--speed", type=float, default=7.0, help="Seconds per commercial slide (default: 7.0)")
    parser.add_argument("--track", type=int, default=1, help="Start on specific soundtrack (1: Mothership, 2: Nebula, 3: Hyperdrive)")
    parser.add_argument("--no-sound", action="store_true", help="Start commercial with SFX muted")
    parser.add_argument("--no-music", action="store_true", help="Start commercial with soundtrack music muted")
    parser.add_argument("--wallet", type=str, default=None, help="Custom Solana payment wallet address")
    args = parser.parse_args()

    wallet = args.wallet or get_public_wallet()
    sound_enabled = not args.no_sound
    music_enabled = not args.no_music

    billboard = CommercialBillboard(
        wallet_addr=wallet,
        slide_duration=args.speed,
        sound_enabled=sound_enabled,
        music_enabled=music_enabled,
        initial_track=args.track
    )
    billboard.run_stream_loop()


if __name__ == "__main__":
    main()
