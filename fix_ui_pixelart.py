import re

with open("ui.py", "r") as f:
    content = f.read()

# 1. Update get_safe_figlet to use a smaller height (14px) and return a dict or just string
new_func = """def get_safe_figlet(text: str, font: str = TERMINAL_FONT) -> str:
    import config
    if getattr(config, 'USE_PIXEL_BANNERS', False):
        try:
            import pixelart
            # Smaller size so we fit more things on screen
            lines = pixelart.render_text(text, px_height=14)
            return "\\n".join(lines)
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
        return text"""

content = re.sub(
    r'def get_safe_figlet\(text: str, font: str = TERMINAL_FONT\) -> str:.*?return text',
    new_func,
    content,
    flags=re.DOTALL
)

# 2. Fix print_stream_header panel embedding
header_find = r'    console.print\(Panel\(\n        f"\[bold cyan\]\{app_banner\}\[/bold cyan\]\\n\{mode_tag\}\\n\\n\{stats_text\}",\n        title="\[bold red\]🔴 BIGO LIVE STREAM MODE\[/bold red\]",\n        border_style="bold cyan",\n        box=box.HEAVY\n    \)\)'

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
content = re.sub(header_find, header_repl, content)

# 3. Fix print_buy_signal panel embedding
buy_find = r'    content = \(\n        f"\[bold green\]\{buy_banner\}\[/bold green\]\\n"\n        f"\[bold yellow\]\{sym_banner\}\[/bold yellow\]\\n\\n"\n        f"\[bold white\]Target: {symbol}\[/bold white\] | \[bold cyan\]{pos.token_address}\[/bold cyan\]\\n"\n.*?        f"\[bold magenta\]AI Veto Confidence: {safe_confidence:.1f}% Safe\[/bold magenta\]"\n    \)'

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
    content_group = Group(bb, sb, Text.from_markup(rest_content))"""

content = re.sub(buy_find, buy_repl, content, flags=re.DOTALL)
# Also need to replace the Panel call to use content_group if defined, wait, I can just rename it to content so I don't have to touch the Panel call.
# Actually I'll name it content instead of content_group.
buy_repl = buy_repl.replace("content_group =", "content =")
content = re.sub(buy_find, buy_repl, content, flags=re.DOTALL)

# 4. Fix print_sell_signal
sell_find = r'    content = \(\n        f"\[\{pnl_color\}\]\{big_banner\}\[/{pnl_color}\]\\n"\n        f"\[\{pnl_color\}\]\{big_pct\}\[/{pnl_color}\]\\n"\n        f"\[bold white\]Token:\[/bold white\] \[bold yellow\]\${symbol}\[/bold yellow\] \| "\n        f"\[dim\]{pos.token_address}\[/dim\]\\n\\n"\n        f"\[bold cyan\]Reason: {reason}\[/bold cyan\]\\n"\n        f"Amount In: {pos.entry_sol_amount:.2f} SOL\\n"\n        f"Amount Out: {pos.exit_sol_amount:.2f} SOL\\n"\n        f"\[bold white\]Profit:\[/bold white\] \[{pnl_color}\]{sign}{pnl_sol:.4f} SOL \({sign}\${pnl_usd:.2f}\)\[/{pnl_color}\]"\n    \)'

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

content = re.sub(sell_find, sell_repl, content, flags=re.DOTALL)

with open("ui.py", "w") as f:
    f.write(content)
