"""
Loud & High-Visibility Terminal UI Engine.
Optimized for mobile screens (Termux) and live streaming (Bigo Live).
Uses huge ASCII block fonts (pyfiglet), high-contrast neon colors (rich),
and terminal audio beeps (\\a).
"""

import sys
import shutil
import pyfiglet
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich import box
from typing import Dict, Any, List, Tuple, Optional
import config
from config import SOUND_ENABLED, LOUD_TERMINAL_BELLS, TERMINAL_FONT
from sounds import play_audio_file
from price_feed import get_cached_sol_price

console = Console(highlight=False)


def sound_alarm(times: int = LOUD_TERMINAL_BELLS, sound_type: str = "buy"):
    """
    Produce loud audible audio through phone media speakers (via play-audio)
    and emit terminal bell character \\a.
    """
    if not SOUND_ENABLED:
        return
    play_audio_file(sound_type)
    if times > 1:
        sys.stdout.write("\a" * (times - 1))
        sys.stdout.flush()


def get_safe_figlet(text: str, font: str = TERMINAL_FONT) -> str:
    import config
    if getattr(config, 'USE_PIXEL_BANNERS', False):
        try:
            import pixelart
            lines = pixelart.render_text(text, px_height=14)
            return "\n".join(lines)
        except Exception:
            pass
    
    cols = shutil.get_terminal_size().columns
    try:
        rendered = pyfiglet.figlet_format(text, font=font).rstrip()
        lines = rendered.splitlines()
        max_len = max(len(l) for l in lines) if lines else 0
        if max_len > cols - 4:
            rendered = pyfiglet.figlet_format(text, font="term").rstrip()
        return rendered
    except Exception:
        return text


def get_regime_line():
    try:
        import json, time
        with open("regime_state.json") as f: s = json.load(f)
        age_min = (time.time() - s["updated_at"]) / 60
        color = "bold green" if s["state"] == "TRADE" else "bold red"
        stale = " [yellow](STALE)[/yellow]" if age_min > 30 else ""
        return (f" | [bold yellow]🛰️ REGIME:[/bold yellow] [{color}]"
                f"{s['state']}[/{color}]{stale} "
                f"[white]({s['score']*100:.2f}%, "
                f"{s['window_tokens']} tokens/3h)[/white]")
    except Exception:
        return " | [bold yellow]🛰️ REGIME:[/bold yellow] [dim]warming up[/dim]"


def print_stream_header(portfolio: Dict[str, Any], ml_samples: int = 0, guardian: Optional[Any] = None):
    """Render a loud, high-impact header for Bigo Live stream viewers."""
    # 0. Render TRADER GUARDIAN Panel FIRST in the dashboard
    try:
        from trader_guardian import TraderGuardian
        tg = guardian or TraderGuardian()
        console.print(tg.get_panel())
    except Exception:
        pass

    cols = shutil.get_terminal_size().columns
    
    # Large Title
    app_banner = get_safe_figlet("PUMP ML", font="small")
    
    # Mode & Identifiers
    mode = portfolio.get("mode", "REAL")
    pubkey = portfolio.get("pubkey", "")
    sol_price = portfolio.get("sol_usd_price") or get_cached_sol_price() or 110.0
    
    # Portfolio stats (both SOL and USD)
    bal_sol = portfolio.get("balance_sol", 0.0)
    bal_usd = portfolio.get("balance_usd", bal_sol * sol_price)
    equity_sol = portfolio.get("net_equity_sol", bal_sol)
    equity_usd = portfolio.get("net_equity_usd", equity_sol * sol_price)

    pnl_sol = portfolio.get("total_pnl_sol", 0.0)
    pnl_usd = portfolio.get("total_pnl_usd", pnl_sol * sol_price)
    pnl_pct = portfolio.get("total_pnl_pct", 0.0)

    realized_sol = portfolio.get("realized_pnl_sol", 0.0)
    realized_usd = portfolio.get("realized_pnl_usd", realized_sol * sol_price)
    unrealized_sol = portfolio.get("unrealized_pnl_sol", 0.0)
    unrealized_usd = portfolio.get("unrealized_pnl_usd", unrealized_sol * sol_price)
    open_count = portfolio.get("open_positions_count", 0)

    trades = portfolio.get("total_trades", 0)
    wins = portfolio.get("wins", 0)
    losses = portfolio.get("losses", 0)
    win_rate = portfolio.get("win_rate", 0.0)

    pnl_color = "bold green" if pnl_sol >= 0 else "bold red"
    pnl_sign = "+" if pnl_sol >= 0 else ""
    real_color = "bold green" if realized_sol >= 0 else "bold red"
    real_sign = "+" if realized_sol >= 0 else ""
    unreal_color = "bold green" if unrealized_sol >= 0 else "bold red"
    unreal_sign = "+" if unrealized_sol >= 0 else ""

    bal_label = "💰 REAL WALLET:" if mode == "REAL" else "💰 DEMO WALLET:"
    wallet_info = f" | [bold cyan]WALLET:[/bold cyan] [bold white]{pubkey[:5]}...{pubkey[-4:]}[/bold white]" if pubkey else ""

    # Guardian Light Line
    guardian_light = ""
    try:
        from trader_guardian import TraderGuardian
        tg = guardian or TraderGuardian()
        g_line = tg.get_light_line()
        if g_line:
            guardian_light = f"\n{g_line}"
    except Exception:
        pass

    stats_text = (
        f"[bold yellow]{bal_label}[/bold yellow] [bold white]{bal_sol:.4f} SOL (${bal_usd:.2f})[/bold white] | "
        f"[bold yellow]EQUITY:[/bold yellow] [bold white]{equity_sol:.4f} SOL (${equity_usd:.2f})[/bold white]{wallet_info}\n"
        f"[bold yellow]📈 TOTAL P&L:[/bold yellow] [{pnl_color}]{pnl_sign}${pnl_usd:.2f} USD ({pnl_sign}{pnl_sol:.4f} SOL, {pnl_sign}{pnl_pct:.1f}%)[/{pnl_color}] | "
        f"[bold yellow]SOL:[/bold yellow] [bold white]${sol_price:.2f}[/bold white]\n"
        f"[bold yellow]📊 REALIZED:[/bold yellow] [{real_color}]{real_sign}${realized_usd:.2f}[/{real_color}] | "
        f"[bold yellow]UNREALIZED:[/bold yellow] [{unreal_color}]{unreal_sign}${unrealized_usd:.2f}[/{unreal_color}] ({open_count} open) | "
        f"[bold yellow]🎯 WIN RATE:[/bold yellow] [bold cyan]{win_rate:.1f}%[/bold cyan] ({wins}W / {losses}L)\n"
        f"[bold yellow]🧠 ML SAMPLES:[/bold yellow] [bold magenta]{ml_samples}[/bold magenta]{get_regime_line()}{guardian_light}"
    )

    # Append Market Psychology Dashboard Light (Meters & Sparklines)
    if getattr(config, "PSYCHOLOGY_RADAR_ENABLED", True):
        try:
            from market_psychology import MarketPsychology
            engine = MarketPsychology()
            psych_line = engine.get_dashboard_light_line()
            if psych_line:
                stats_text += f"\n\n{psych_line}"
        except Exception:
            pass

    is_yolo = getattr(config, "YOLO_MODE", False) or portfolio.get("yolo", False)
    mode_tag = "[bold green]⚡ LIVE SOLANA REAL SNIPER (HELIUS RPC)[/bold green]" if mode == "REAL" else "[bold green]⚡ LIVE SOLANA RUG SNIPER (DEMO TRADING)[/bold green]"
    if is_yolo:
        mode_tag += " | [bold red]🔥 YOLO MODE: TO ZERO (-y)[/bold red]"

    from rich.console import Group
    from rich.text import Text
    
    if "\x1b" in app_banner:
        b = Text.from_ansi(app_banner)
    else:
        b = Text.from_markup(f"[bold cyan]{app_banner}[/bold cyan]")
        
    console.print(Panel(
        Group(
            b,
            Text.from_markup(f"{mode_tag}\n\n{stats_text}")
        ),
        title="[bold red]🔴 BIGO LIVE STREAM MODE[/bold red]",
        border_style="bold cyan",
        box=box.HEAVY
    ))


def print_psychology_radar(psych_engine: Optional[Any] = None):
    """Display full Market Psychology & PvP Radar View with ASCII charts & meters."""
    try:
        from market_psychology import MarketPsychology
        engine = psych_engine or MarketPsychology()
        console.print(engine.render_psychology_radar_panel())
    except Exception as e:
        console.print(f"[bold red]Failed to render psychology radar: {e}[/bold red]")


def print_trades_momentum(psych_engine: Optional[Any] = None):
    """Display Trade Performance & Momentum View with ASCII streak blocks & sparklines."""
    try:
        from market_psychology import MarketPsychology
        engine = psych_engine or MarketPsychology()
        console.print(engine.render_trades_momentum_panel())
    except Exception as e:
        console.print(f"[bold red]Failed to render trades momentum: {e}[/bold red]")


def print_expectancy(psych_engine: Optional[Any] = None):
    """Display full Expectancy & Trade Shape View with fee-adjusted math & confidence intervals."""
    try:
        from market_psychology import MarketPsychology
        engine = psych_engine or MarketPsychology()
        console.print(engine.render_expectancy_panel())
    except Exception as e:
        console.print(f"[bold red]Failed to render expectancy panel: {e}[/bold red]")


def print_qr_billboard(psych_engine: Optional[Any] = None):
    """Display full QR Code & Value Billboard View with scannable phone QR code."""
    try:
        from qr_wallet import render_qr_billboard_panel
        console.print(render_qr_billboard_panel())
    except Exception as e:
        console.print(f"[bold red]Failed to render QR billboard: {e}[/bold red]")


def print_buy_signal(token_data: Dict[str, Any], p_rug: float, insights: List[Tuple[str, str, str]], pos: Any, is_real: bool = True):
    """Render a massive, loud BUY signal with big text for viewers."""
    sound_alarm(times=3, sound_type="buy")  # Loud chime through speaker!
    
    symbol = str(token_data.get("symbol", "GEM")).upper()
    buy_banner = get_safe_figlet("BUY!", font="small")
    sym_banner = get_safe_figlet(f"${symbol}", font="small")

    sol_price = get_cached_sol_price() or 110.0
    buy_usd = pos.entry_sol_amount * sol_price

    safe_confidence = (1.0 - p_rug) * 100.0
    buy_type = "REAL LIVE BUY (HELIUS)" if is_real else "SIMULATED BUY"
    tx_link = f"https://solscan.io/tx/{pos.tx_hash}" if is_real and len(pos.tx_hash) > 50 else f"{pos.tx_hash[:24]}..."

    body = (
        f"[bold green]{buy_banner}[/bold green]\n"
        f"[bold yellow]{sym_banner}[/bold yellow]\n"
        f"[bold white]Token Name:[/bold white] [bold cyan]{token_data.get('name', 'Unknown')}[/bold cyan]\n"
        f"[bold white]Mint:[/bold white] [bold white]{token_data.get('mint', '')}[/bold white]\n\n"
        f"[bold white]🧠 ML RUG RISK:[/bold white] [bold green]{p_rug*100:.1f}% RUG RISK (CONFIDENCE: {safe_confidence:.1f}% SAFE)[/bold green]\n"
        f"[bold white]💸 {buy_type}:[/bold white] [bold yellow]{pos.entry_sol_amount:.4f} SOL (${buy_usd:.2f} USD)[/bold yellow] "
        f"-> [bold white]{pos.tokens_amount:,.0f} {symbol}[/bold white]\n"
        f"[bold white]Entry Price:[/bold white] [bold white]{pos.entry_price_sol:.10f} SOL[/bold white]\n"
        f"[bold white]Tx Hash:[/bold white] [bold cyan]{tx_link}[/bold cyan]\n\n"
        f"[bold yellow]🔍 MACHINE LEARNING VERIFICATION:[/bold yellow]\n"
    )

    for cat, detail, status in insights:
        if status == "GOOD":
            badge = "[bold green]✅ SAFE[/bold green]"
        elif status == "WARN":
            badge = "[bold yellow]⚠️  WARN[/bold yellow]"
        else:
            badge = "[bold red]❌ DANGER[/bold red]"
        body += f"  • {badge} [bold white]{cat}:[/bold white] {detail}\n"

    console.print(Panel(
        body,
        title="[bold green]🚀🚨 HIGH CONFIDENCE BUY EXECUTED 💎🚀[/bold green]",
        border_style="bold green",
        box=box.DOUBLE
    ))


def print_token_skip(symbol: str, name: str, p_rug: float, reason: str):
    """Compact 1-line badge for rejected tokens so stream viewers see active filtering."""
    risk_pct = p_rug * 100.0
    console.print(
        f"[bold red][RUG FILTER ❌][/bold red] [bold white]${symbol[:8]}[/bold white] "
        f"({name[:12]}) -> [bold red]Risk: {risk_pct:.0f}%[/bold red] | [dim]{reason}[/dim]"
    )


def print_exit_event(record: Dict[str, Any]):
    """Massive loud exit banner for Take-Profit, Stop-Loss, or Dev Dump."""
    pnl_pct = record.get("pnl_pct", 0.0)
    is_profit = pnl_pct >= 0
    sound_alarm(times=3, sound_type="profit" if is_profit else "dump")
    pnl_sol = record.get("pnl_sol", 0.0)
    sol_price = get_cached_sol_price() or 110.0
    pnl_usd = record.get("pnl_usd", pnl_sol * sol_price)
    symbol = record.get("symbol", "TOKEN")
    reason = record.get("reason", "EXIT")

    is_profit = pnl_pct >= 0
    pnl_color = "bold green" if is_profit else "bold red"
    banner_text = "PROFIT!" if is_profit else "STOP!"
    big_banner = get_safe_figlet(banner_text, font="small")
    sign = "+" if pnl_pct >= 0 else ""
    big_pct = get_safe_figlet(f"{sign}{pnl_pct:.1f}%", font="small")

    content = (
        f"[{pnl_color}]{big_banner}[/{pnl_color}]\n"
        f"[{pnl_color}]{big_pct}[/{pnl_color}]\n"
        f"[bold white]Token:[/bold white] [bold yellow]${symbol}[/bold yellow] | "
        f"[bold white]Trigger:[/bold white] [{pnl_color}]{reason}[/{pnl_color}]\n"
        f"[bold white]Realized P&L:[/bold white] [{pnl_color}]{sign}${pnl_usd:.2f} USD ({sign}{pnl_sol:.4f} SOL, {sign}{pnl_pct:.1f}%)[/{pnl_color}]\n"
        f"[bold white]Hold Time:[/bold white] [bold white]{record.get('hold_time_sec', 0)}s[/bold white]"
    )

    exit_tx = record.get("exit_tx_hash", "")
    if exit_tx and len(exit_tx) > 50:
        content += f"\n[bold white]Exit Tx:[/bold white] [bold cyan]https://solscan.io/tx/{exit_tx}[/bold cyan]"

    if record.get("ml_loss") is not None:
        content += f"\n[bold magenta]🧠 ML MODEL ADAPTED: Loss = {record['ml_loss']:.4f} (Weights updated!)[/bold magenta]"

    title = "[bold green]💰 TAKE PROFIT REACHED! 🚀[/bold green]" if is_profit else "[bold red]🛑 EXIT / STOP LOSS TRIGGERED 📉[/bold red]"
    console.print(Panel(
        content,
        title=title,
        border_style="bold green" if is_profit else "bold red",
        box=box.DOUBLE
    ))


def print_active_positions(positions: Dict[str, Any], sol_usd: Optional[float] = None):
    """Display clean live positions table with USD & SOL tracking for stream viewers."""
    if not positions:
        return

    sol_price = sol_usd or get_cached_sol_price() or 110.0

    table = Table(
        title=f"[bold yellow]⚡ LIVE ACTIVE HOLDINGS (SOL: ${sol_price:.2f})[/bold yellow]",
        box=box.ROUNDED,
        header_style="bold cyan",
        expand=True
    )
    table.add_column("Symbol", style="bold yellow", width=10)
    table.add_column("Invested", justify="right", width=16)
    table.add_column("Current Val", justify="right", width=16)
    table.add_column("P&L ($)", justify="right", width=11)
    table.add_column("P&L (%)", justify="right", width=10)
    table.add_column("Status", justify="center", width=12)

    for pos in positions.values():
        pnl = pos.current_pnl_pct
        pnl_color = "bold green" if pnl >= 0 else "bold red"
        pnl_sign = "+" if pnl >= 0 else ""

        invested_sol = pos.entry_sol_amount
        invested_usd = invested_sol * sol_price

        cur_val_sol = max(invested_sol * (1.0 + (pnl / 100.0)), 0.0)
        cur_val_usd = cur_val_sol * sol_price
        pnl_usd = cur_val_usd - invested_usd

        status = "[bold green]PUMPING 🚀[/bold green]" if pnl >= 15 else (
            "[bold red]DUMPING ⚠️[/bold red]" if pnl <= -10 else "[bold white]TRACKING[/bold white]"
        )
        table.add_row(
            f"${pos.symbol[:8]}",
            f"{invested_sol:.4f} (${invested_usd:.2f})",
            f"{cur_val_sol:.4f} (${cur_val_usd:.2f})",
            f"[{pnl_color}]{pnl_sign}${pnl_usd:.2f}[/{pnl_color}]",
            f"[{pnl_color}]{pnl_sign}{pnl:.1f}%[/{pnl_color}]",
            status
        )

    console.print(table)
