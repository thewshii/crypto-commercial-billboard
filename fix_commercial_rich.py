import re

with open("commercial_stream.py", "r") as f:
    content = f.read()

def fix_func(func_name, expected_body):
    global content
    content = re.sub(
        rf'    def {func_name}.*?return Panel\(Align\.center\(body\),',
        lambda m: expected_body,
        content,
        flags=re.DOTALL
    )

fix_func("_build_jackpot_generic", r'''    def _build_jackpot_generic(self, title, subtitle, prize):
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
        return Panel(Align.center(body),''')

fix_func("_build_lawyer_generic", r'''    def _build_lawyer_generic(self, subtitle, hook, promise, icon="⚖️"):
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
        return Panel(Align.center(body),''')

fix_func("_build_alien_generic", r'''    def _build_alien_generic(self, subtitle, hook, truth, icon="🛸"):
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
        return Panel(Align.center(body),''')

fix_func("_build_religion_generic", r'''    def _build_religion_generic(self, banner_text, color, subtitle, quote, punchline, lore, icon):
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
        return Panel(Align.center(body),''')

# Now fix the build_slide_ methods
content = re.sub(
    r'        body = Group\(banner_render, Text\.from_markup\(f"\\n\\n\[bold white\](.*?)\[/bold white\]"\)\)',
    r'        body = Group(banner_render, Text.from_markup("\n\n[bold white]\1[/bold white]"))',
    content
)

with open("commercial_stream.py", "w") as f:
    f.write(content)
