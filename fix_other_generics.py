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

fix_func("_build_news_generic", r'''    def _build_news_generic(self, title, quote, punchline):
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
        return Panel(Align.center(body),''')

fix_func("_build_singapore_generic", r'''    def _build_singapore_generic(self, title, quote, punchline):
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
        return Panel(Align.center(body),''')

with open("commercial_stream.py", "w") as f:
    f.write(content)
