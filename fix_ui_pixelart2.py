with open("ui.py", "r") as f:
    content = f.read()

# 1. Update get_safe_figlet to use a smaller height (14px) and return a dict or just string
old_func_part = """def get_safe_figlet(text: str, font: str = TERMINAL_FONT) -> str:
    import config
    if getattr(config, 'USE_PIXEL_BANNERS', False):
        try:
            import pixelart
            lines = pixelart.render_text(text, px_height=48)
            return "\\n".join(lines)
        except Exception:
            pass"""

new_func_part = """def get_safe_figlet(text: str, font: str = TERMINAL_FONT) -> str:
    import config
    if getattr(config, 'USE_PIXEL_BANNERS', False):
        try:
            import pixelart
            # Smaller size so we fit more things on screen
            lines = pixelart.render_text(text, px_height=14)
            return "\\n".join(lines)
        except Exception:
            pass"""
content = content.replace(old_func_part, new_func_part)


# 2. Fix print_stream_header panel embedding
header_find = """    console.print(Panel(
        f"[bold cyan]{app_banner}[/bold cyan]\\n{mode_tag}\\n\\n{stats_text}",
        title="[bold red]🔴 BIGO LIVE STREAM MODE[/bold red]",
        border_style="bold cyan",
        box=box.HEAVY
    ))"""

header_repl = """    from rich.console import Group
    from rich.text import Text
    
    if "\\x1b" in app_banner:
        b = Text.from_ansi(app_banner)
    else:
        b = Text.from_markup(f"[bold cyan]{app_banner}[/bold cyan]")
        
    console.print(Panel(
        Group(
            b,
            Text.from_markup(f"{mode_tag}\\n\\n{stats_text}")
        ),
        title="[bold red]🔴 BIGO LIVE STREAM MODE[/bold red]",
        border_style="bold cyan",
        box=box.HEAVY
    ))"""
content = content.replace(header_find, header_repl)

# 3. Fix print_buy_signal panel embedding
buy_find = """    content = (
        f"[bold green]{buy_banner}[/bold green]\\n"
        f"[bold yellow]{sym_banner}[/bold yellow]\\n\\n"
        f"[bold white]Target: {symbol}[/bold white] | [bold cyan]{pos.token_address}[/bold cyan]\\n"
        f"Amount: [bold green]{pos.entry_sol_amount:.2f} SOL (${buy_usd:.2f})[/bold green]\\n\\n"
        f"🎯 [bold yellow]AI LOGIC GATE METRICS:[/bold yellow]\\n"
    )
    for k, v, state in insights:
        c = "green" if state == "PASS" else "yellow" if state == "WARN" else "red"
        content += f"  - {k}: [{c}]{v}[/{c}]\\n"
    content += f"\\n[bold magenta]AI Veto Confidence: {safe_confidence:.1f}% Safe[/bold magenta]"
"""

buy_repl = """    from rich.console import Group
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
    content = Group(bb, sb, Text.from_markup(rest_content))
"""
content = content.replace(buy_find, buy_repl)

# 4. Fix print_sell_signal
sell_find = """    content = (
        f"[{pnl_color}]{big_banner}[/{pnl_color}]\\n"
        f"[{pnl_color}]{big_pct}[/{pnl_color}]\\n"
        f"[bold white]Token:[/bold white] [bold yellow]${symbol}[/bold yellow] | "
        f"[dim]{pos.token_address}[/dim]\\n\\n"
        f"[bold cyan]Reason: {reason}[/bold cyan]\\n"
        f"Amount In: {pos.entry_sol_amount:.2f} SOL\\n"
        f"Amount Out: {pos.exit_sol_amount:.2f} SOL\\n"
        f"[bold white]Profit:[/bold white] [{pnl_color}]{sign}{pnl_sol:.4f} SOL ({sign}${pnl_usd:.2f})[/{pnl_color}]"
    )"""

sell_repl = """    from rich.console import Group
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

content = content.replace(sell_find, sell_repl)

with open("ui.py", "w") as f:
    f.write(content)
