"""
TRADER GUARDIAN — Psychological safeguards for the Termux sniper bot.
Monitors daily risk, enforces loss streak cooldowns, tracks capital sheltered
from dead market regimes, and monitors trading session fatigue.
"""

import os
import time
import json
from datetime import datetime, timezone
from typing import Dict, Any, Tuple, Optional
from rich.panel import Panel
from rich.console import Console
from rich import box

import config
from market_psychology import render_meter_bar

console = Console(highlight=False)


class TraderGuardian:
    """
    Trader Guardian enforcing daily max loss, loss streak cooldowns,
    anti-FOMO capital sheltering accounting, and session duration health nudges.
    """

    def __init__(self, state_file: Optional[str] = None):
        self.state_file = state_file or getattr(config, "GUARDIAN_STATE_FILE", "guardian_state.json")
        self.daily_max_loss_sol = float(getattr(config, "DAILY_MAX_LOSS_SOL", 0.08))
        self.loss_streak_limit = int(getattr(config, "LOSS_STREAK_LIMIT", 4))
        self.cooldown_minutes = int(getattr(config, "COOLDOWN_MINUTES", 30))
        self.session_nudge_hours = float(getattr(config, "SESSION_NUDGE_HOURS", 4))
        self.session_warn_hours = float(getattr(config, "SESSION_WARN_HOURS", 8))

        self.state: Dict[str, Any] = {}
        self._load_state()

    def _get_utc_day(self) -> str:
        return datetime.now(timezone.utc).strftime("%Y-%m-%d")

    def _load_state(self):
        """Load state from guardian_state.json or initialize defaults."""
        today = self._get_utc_day()
        now = time.time()

        if os.path.exists(self.state_file):
            try:
                with open(self.state_file, "r", encoding="utf-8") as f:
                    self.state = json.load(f)
            except Exception:
                self.state = {}

        if not self.state:
            self.state = {
                "day": today,
                "day_realized_pnl_sol": 0.0,
                "consecutive_losses": 0,
                "cooldown_until": 0.0,
                "sheltered_sol": 0.0,
                "sheltered_today": 0.0,
                "session_start": now
            }
            self._save_state_atomic()
        else:
            # Check day rollover
            if self.state.get("day") != today:
                self.state["day"] = today
                self.state["day_realized_pnl_sol"] = 0.0
                self.state["sheltered_today"] = 0.0
            if not self.state.get("session_start"):
                self.state["session_start"] = now
            self._save_state_atomic()

    def _save_state_atomic(self):
        """Persist state crash-safely via temp file + os.replace."""
        try:
            tmp = f"{self.state_file}.tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(self.state, f, indent=2)
            os.replace(tmp, self.state_file)
        except Exception:
            pass

    def _check_day_rollover(self):
        """Rollover daily counters if UTC day changed."""
        today = self._get_utc_day()
        if self.state.get("day") != today:
            self.state["day"] = today
            self.state["day_realized_pnl_sol"] = 0.0
            self.state["sheltered_today"] = 0.0
            self._save_state_atomic()

    def record_trade_close(self, pnl_sol: float):
        """
        Record a closed trade P&L in SOL.
        Updates daily realized loss, streak counters, and triggers cooldowns or daily stops.
        """
        self._check_day_rollover()
        now = time.time()

        # Update daily P&L
        cur_pnl = float(self.state.get("day_realized_pnl_sol", 0.0))
        self.state["day_realized_pnl_sol"] = round(cur_pnl + float(pnl_sol), 6)

        # Update streak
        if float(pnl_sol) < 0:
            self.state["consecutive_losses"] = int(self.state.get("consecutive_losses", 0)) + 1
        else:
            self.state["consecutive_losses"] = 0

        # Check consecutive loss cooldown
        losses = self.state["consecutive_losses"]
        cooldown_until = float(self.state.get("cooldown_until", 0.0))
        if losses >= self.loss_streak_limit and cooldown_until <= now:
            self.state["cooldown_until"] = now + (self.cooldown_minutes * 60)
            console.print(Panel(
                f"[bold cyan]❄️ COOLDOWN — {losses} straight losses. Bot paused {self.cooldown_minutes}:00. Walk away.[/bold cyan]",
                title="[bold cyan]❄️ TRADER GUARDIAN COOLDOWN[/bold cyan]",
                border_style="bold cyan",
                box=box.HEAVY
            ))

        # Check daily loss limit
        if self.state["day_realized_pnl_sol"] <= -self.daily_max_loss_sol:
            console.print(Panel(
                "[bold red]🛑 DAILY LIMIT HIT — entries stopped until 00:00 UTC. The bot is protecting tomorrow's bankroll.[/bold red]",
                title="[bold red]🛑 TRADER GUARDIAN DAILY LIMIT[/bold red]",
                border_style="bold red",
                box=box.HEAVY
            ))

        self._save_state_atomic()

    def record_regime_skip(self, buy_amount_sol: float):
        """
        Record capital sheltered from entering during dead/stand-down market regimes.
        """
        self._check_day_rollover()
        amount = float(buy_amount_sol)
        self.state["sheltered_sol"] = round(float(self.state.get("sheltered_sol", 0.0)) + amount, 4)
        self.state["sheltered_today"] = round(float(self.state.get("sheltered_today", 0.0)) + amount, 4)
        self._save_state_atomic()

    def entries_allowed(self) -> Tuple[bool, str]:
        """
        Verify if guardian permits new trade entries.
        Returns:
            (is_allowed: bool, reason: str)
        """
        self._check_day_rollover()
        now = time.time()

        # 1. Check cooldown
        cooldown_until = float(self.state.get("cooldown_until", 0.0))
        if cooldown_until > now:
            rem = int(cooldown_until - now)
            m = rem // 60
            s = rem % 60
            return False, f"cooldown {m:02d}:{s:02d} remaining"

        # 2. Check daily limit
        day_pnl = float(self.state.get("day_realized_pnl_sol", 0.0))
        if day_pnl <= -self.daily_max_loss_sol:
            return False, "daily limit"

        return True, ""

    def get_panel(self) -> Panel:
        """
        Generate the prominent TRADER GUARDIAN visual panel for the dashboard.
        Body items in order:
        1. DAILY RISK meter
        2. LOSS STREAK / COOLDOWN
        3. SHELTERED SOL
        4. SESSION duration & fatigue nudge
        """
        self._check_day_rollover()
        now = time.time()

        # 1. DAILY RISK meter (width 20)
        day_pnl = float(self.state.get("day_realized_pnl_sol", 0.0))
        loss = abs(min(0.0, day_pnl))
        limit = self.daily_max_loss_sol
        pct = min(100.0, max(0.0, (loss / limit) * 100.0))

        if pct > 85.0:
            color = "bold red"
        elif pct >= 60.0:
            color = "bold yellow"
        else:
            color = "bold green"

        meter_20 = render_meter_bar(pct, width=20, color=color)
        if day_pnl <= -limit:
            line1 = f"[bold red]🛑 DAILY RISK  {meter_20} {loss:.3f}/{limit:.3f} SOL (LIMIT HIT)[/bold red]"
        else:
            line1 = f"[bold white]DAILY RISK[/bold white]  {meter_20} [{color}]{loss:.3f}/{limit:.3f} SOL[/{color}]"

        # 2. LOSS STREAK or COOLDOWN
        cooldown_until = float(self.state.get("cooldown_until", 0.0))
        if cooldown_until > now:
            rem = int(cooldown_until - now)
            m = rem // 60
            s = rem % 60
            line2 = f"❄️ COOLDOWN  [bold cyan]{m:02d}:{s:02d}[/bold cyan] [bold white]remaining — entries paused[/bold white]"
        else:
            losses = int(self.state.get("consecutive_losses", 0))
            filled = min(losses, self.loss_streak_limit)
            empty = max(0, self.loss_streak_limit - filled)
            blocks = f"[bold red]{'■' * filled}[/bold red][dim]{'□' * empty}[/dim]"
            losses_text = f"{losses} straight losses" if losses != 1 else "1 straight loss"
            line2 = f"🔥 STREAK  {blocks} [bold white]{losses_text}[/bold white]"

        # 3. SHELTERED (big green number, anti-FOMO)
        sheltered = float(self.state.get("sheltered_sol", 0.0))
        sheltered_today = float(self.state.get("sheltered_today", 0.0))
        line3 = f"💰 SHELTERED  [bold green]{sheltered:.2f} SOL[/bold green] [bold white]kept out of dead markets[/bold white]  [dim]({sheltered_today:.2f} today)[/dim]"

        # 4. SESSION LIVE
        session_start = float(self.state.get("session_start", now))
        elapsed = max(0.0, now - session_start)
        h = int(elapsed // 3600)
        m = int((elapsed % 3600) // 60)
        line4 = f"⏱️ LIVE  [bold white]{h}h {m:02d}m[/bold white]"

        if elapsed >= self.session_warn_hours * 3600:
            line4 += " [bold red]— you are trading tired. Strongly consider stopping.[/bold red]"
        elif elapsed >= self.session_nudge_hours * 3600:
            line4 += " [bold yellow]— long session, tired brains chase. Consider a break.[/bold yellow]"

        body = f"{line1}\n{line2}\n{line3}\n{line4}"

        return Panel(
            body,
            title="[bold red]🧠 TRADER GUARDIAN[/bold red]",
            border_style="bold red",
            box=box.HEAVY
        )

    def get_light_line(self) -> str:
        """
        One-liner summary for stream header.
        """
        self._check_day_rollover()
        now = time.time()

        day_pnl = float(self.state.get("day_realized_pnl_sol", 0.0))
        loss = abs(min(0.0, day_pnl))
        limit = self.daily_max_loss_sol
        pct = min(100.0, max(0.0, (loss / limit) * 100.0))

        color = "bold red" if pct > 85.0 else ("bold yellow" if pct >= 60.0 else "bold green")
        meter_10 = render_meter_bar(pct, width=10, color=color)

        cooldown_until = float(self.state.get("cooldown_until", 0.0))
        losses = int(self.state.get("consecutive_losses", 0))
        sheltered_today = float(self.state.get("sheltered_today", 0.0))

        if cooldown_until > now:
            rem = int(cooldown_until - now)
            status = f"[bold cyan]❄️ {rem//60:02d}:{rem%60:02d}[/bold cyan]"
        elif day_pnl <= -limit:
            status = "[bold red]🛑 LIMIT[/bold red]"
        elif losses > 0:
            status = f"[bold yellow]🔥 {losses}L[/bold yellow]"
        else:
            status = "[bold green]🛡️ OK[/bold green]"

        return f"[bold red]🧠 GUARDIAN:[/bold red] {meter_10} [{color}]{loss:.3f}/{limit:.3f}[/{color}] | {status} | [bold green]💰 +{sheltered_today:.2f} SOL saved[/bold green]"
