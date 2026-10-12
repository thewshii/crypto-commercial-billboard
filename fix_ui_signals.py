import re

with open("ui.py", "r") as f:
    content = f.read()

new_buy = """    from rich.console import Group
    from rich.text import Text
    bb = Text.from_ansi(buy_banner) if "\\x1b" in buy_banner else Text.from_markup(f"[bold green]{buy_banner}[/bold green]")
    sb = Text.from_ansi(sym_banner) if "\\x1b" in sym_banner else Text.from_markup(f"[bold yellow]{sym_banner}[/bold yellow]")
    
    rest_content = (
        f"[bold white]Target: {symbol}[/bold white] | [bold cyan]{pos.token_address}[/bold cyan]\\n"
        f"Amount: [bold green]{pos.entry_sol_amount:.2f} SOL (${buy_usd:.2f})[/bold green]\\n\\n"
        f"🎯 [bold yellow]AI LOGIC GATE METRICS:[/bold yellow]\\n"
    )
    for k, v, state in insights:
        c = "green" if state == "PASS" else "yellow" if state == "WARN" else "red"
        rest_content += f"  - {k}: [{c}]{v}[/{c}]\\n"
    rest_content += f"\\n[bold magenta]AI Veto Confidence: {safe_confidence:.1f}% Safe[/bold magenta]"
    content = Group(bb, sb, Text.from_markup(rest_content))"""

content = re.sub(
    r'    content = \(\n        f"\[bold green\].*?AI Veto Confidence: \{safe_confidence:\.1f\}% Safe\[/bold magenta\]"\n    \)',
    lambda m: new_buy,
    content,
    flags=re.DOTALL
)

new_sell = """    from rich.console import Group
    from rich.text import Text
    bb = Text.from_ansi(big_banner) if "\\x1b" in big_banner else Text.from_markup(f"[{pnl_color}]{big_banner}[/{pnl_color}]")
    bp = Text.from_ansi(big_pct) if "\\x1b" in big_pct else Text.from_markup(f"[{pnl_color}]{big_pct}[/{pnl_color}]")
    
    rest_content = (
        f"[bold white]Token:[/bold white] [bold yellow]${symbol}[/bold yellow] | "
        f"[dim]{pos.token_address}[/dim]\\n\\n"
        f"[bold cyan]Reason: {reason}[/bold cyan]\\n"
        f"Amount In: {pos.entry_sol_amount:.2f} SOL\\n"
        f"Amount Out: {pos.exit_sol_amount:.2f} SOL\\n"
        f"[bold white]Profit:[/bold white] [{pnl_color}]{sign}{pnl_sol:.4f} SOL ({sign}${pnl_usd:.2f})[/{pnl_color}]"
    )
    content = Group(bb, bp, Text.from_markup(rest_content))"""

content = re.sub(
    r'    content = \(\n        f"\[\{pnl_color\}\].*?Profit:\[/bold white\] \[{pnl_color}\]\{sign\}\{pnl_sol:\.4f\} SOL \(\{sign\}\$\{pnl_usd:\.2f\}\)\[/\{pnl_color\}\]"\n    \)',
    lambda m: new_sell,
    content,
    flags=re.DOTALL
)

with open("ui.py", "w") as f:
    f.write(content)
