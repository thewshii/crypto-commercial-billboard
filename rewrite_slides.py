import re

with open("commercial_stream.py", "r") as f:
    content = f.read()

# 1. Update render_slide_banner
banner_old = """    def render_slide_banner(self, text: str, color: str = "bold yellow", font: str = "small") -> str:
        \"\"\"Render zoom-proof high-contrast block banner badge (no wrapping ASCII figlet soup).\"\"\"
        clean = text.replace("\\n", " ").strip().upper()
        bg_style = "black on yellow"
        if "red" in color:
            bg_style = "white on red"
        elif "cyan" in color:
            bg_style = "black on cyan"
        elif "green" in color:
            bg_style = "black on green"
        elif "magenta" in color:
            bg_style = "white on magenta"
        return f"[bold {bg_style}]  ⚡ {clean} ⚡  [/bold {bg_style}]\"\"\""""

banner_new = """    def render_slide_banner(self, text: str, color: str = "bold yellow", font: str = "standard") -> str:
        clean = text.replace("\\n", " ").strip().upper()
        fig = pyfiglet.figlet_format(clean, font=font)
        bg_style = "yellow"
        if "red" in color: bg_style = "red"
        elif "cyan" in color: bg_style = "cyan"
        elif "green" in color: bg_style = "green"
        elif "magenta" in color: bg_style = "magenta"
        return f"[bold {bg_style}]{fig}[/bold {bg_style}]\"\"\""""
if banner_old in content:
    content = content.replace(banner_old, banner_new)
else:
    # Use regex
    content = re.sub(
        r'    def render_slide_banner\(self, text: str, color: str = "bold yellow", font: str = "small"\) -> str:.*?return f"\[bold \{bg_style\}\].*?"',
        """    def render_slide_banner(self, text: str, color: str = "bold yellow", font: str = "standard") -> str:
        clean = text.replace("\\n", " ").strip().upper()
        try:
            fig = pyfiglet.figlet_format(clean, font=font)
        except:
            fig = clean
        bg_style = "yellow"
        if "red" in color: bg_style = "red"
        elif "cyan" in color: bg_style = "cyan"
        elif "green" in color: bg_style = "green"
        elif "magenta" in color: bg_style = "magenta"
        return f"[bold {bg_style}]{fig}[/bold {bg_style}]\"\"\"""",
        content,
        flags=re.DOTALL
    )

# 2. Update all panels to use Align.center and simplify text
# I'll just regex replace `return Panel(body,` with `from rich.align import Align\n        return Panel(Align.center(body),`
# but only if it's not already aligned.
content = re.sub(
    r'return Panel\(body,',
    r'from rich.align import Align\n        return Panel(Align.center(body),',
    content
)

# 3. Simplify text in _build_religion_generic
content = re.sub(
    r'            f"\[bold yellow\]\{icon\} \{subtitle\} \{icon\}\[/bold yellow\]\\n\\n"\n            f"\[italic cyan\]\\\"\{quote\}\\\"\[/italic cyan\]\\n\\n"\n            f"\[bold green\]⚡ \{punchline\} ⚡\[/bold green\]\\n\\n"\n            f"\[dim\]\{lore\}\[/dim\]\\n\\n"\n            f"\{icon\} \[bold magenta\]The Lion of Judah has sounded the warcall\.\[/bold magenta\] \{icon\}"',
    r'            f"[bold yellow]{icon} {subtitle.upper()} {icon}[/bold yellow]\\n\\n"\n            f"[bold green]⚡ {punchline.upper()} ⚡[/bold green]\\n\\n"',
    content
)

# 4. Simplify _build_jackpot_generic
content = re.sub(
    r'            f"\[blink bold red\]🚨 EVERYBODY STOP! WE HAVE A WINNER! 🚨\[/blink bold red\]\\n\\n"\n            f"\[bold green\]\{subtitle\}\[/bold green\]\\n"\n            f"💰 \[bold white on green\] \{prize\} \[/bold white on green\] 💰\\n\\n"\n            f"\[bold cyan\].*?The truth\?\[/bold magenta\]\\n"\n.*?\[bold yellow\]WAKE UP.*?\[/bold yellow\] 🐘"',
    r'            f"[blink bold red]🚨 EVERYBODY STOP! WE HAVE A WINNER! 🚨[/blink bold red]\\n\\n"\n            f"[bold green]{subtitle.upper()}[/bold green]\\n\\n"\n            f"💰 [bold white on green] {prize} [/bold white on green] 💰\\n\\n"\n            f"🐘 [bold yellow]WAKE UP. THE HOUSE ALWAYS WINS.[/bold yellow] 🐘"',
    content,
    flags=re.DOTALL
)

# 5. Simplify _build_lawyer_generic
content = re.sub(
    r'            f"\[bold yellow\]\{icon\} \{subtitle\} \{icon\}\[/bold yellow\]\\n\\n"\n            f"\[bold red\]\{hook\}\[/bold red\]\\n\\n"\n.*?\[bold cyan\]Call.*?\.\.\.\[/bold cyan\]"',
    r'            f"[bold yellow]{icon} {subtitle.upper()} {icon}[/bold yellow]\\n\\n"\n            f"[bold red]⚡ {hook.upper()} ⚡[/bold red]\\n\\n"\n            f"[bold cyan]📞 CALL THE CRYPTO RUG FILTER TODAY! 📞[/bold cyan]"',
    content,
    flags=re.DOTALL
)

# 6. Simplify _build_alien_generic
content = re.sub(
    r'            f"\[bold yellow\]\{icon\} \{subtitle\} \{icon\}\[/bold yellow\]\\n\\n"\n            f"\[bold cyan\]\{hook\}\[/bold cyan\]\\n\\n"\n.*?\[bold magenta\].*?\[/bold magenta\]"',
    r'            f"[bold yellow]{icon} {subtitle.upper()} {icon}[/bold yellow]\\n\\n"\n            f"[bold cyan]🛸 {hook.upper()} 🛸[/bold cyan]\\n\\n"',
    content,
    flags=re.DOTALL
)

# 7. Update the animation
new_anim = """                anim_frames = [
                    "[yellow]         O     [|]     O        \\n        /|\\\\    [|]    /|\\\\       \\n        / \\\\    [|]    / \\\\       [/yellow]",
                    "[yellow]          O    [|]    O         \\n         /|\\\\===[|]===/|\\\\        \\n         < \\\\   [|]   />         [/yellow]",
                    "[yellow]           O   (()   O          \\n          /|\\\\==(()==/|\\\\         \\n          <<   (()   >>         [/yellow]",
                    "[yellow]           O   {*}   O          \\n          /|\\\\=={*}==/|\\\\         \\n          <<   {*}   >>         [/yellow]",
                    "[yellow]               { } O   O        \\n               { }/|\\\\ /|\\\\       \\n               { }/ \\\\ / \\\\       [/yellow]",
                    "[yellow]               { } !   !        \\n               { } O   O        \\n               { }/|\\\\ /|\\\\       \\n               { }/ \\\\ / \\\\       [/yellow]",
                    "[yellow]       O       { }       O      \\n      /|\\\\      { }      /|\\\\     \\n      / \\\\      { }      / \\\\     [/yellow]",
                    "[yellow] O             { }             O\\n/|\\\\            { }            /|\\\\ \\n/ \\\\            { }            / \\\\ [/yellow]",
                    "[yellow]\\\\\\\\             { }             //\\n \\\\\\\\            { }            // \\n  O            { }            O  [/yellow]",
                    "[yellow]               { }              \\n               { }              \\n               { }              [/yellow]"
                ]"""

content = re.sub(
    r'                anim_frames = \[\n.*?\]',
    new_anim,
    content,
    flags=re.DOTALL
)

# Replace all the build_slide_* specific texts with huge bold text as well
# e.g. "Slide 1: THE BRUTAL TRUTH / PROBLEM."
content = re.sub(
    r'    def build_slide_([a-z0-9_]+)\(self\) -> Panel:\n        """(.*?)"""\n        banner = self\.render_slide_banner\("(.*?)", color="(.*?)"\)\n        body = \(\n            f"\{banner\}\\n"\n.*?        \)\n        return Panel\(',
    r'''    def build_slide_\1(self) -> Panel:
        """\2"""
        banner = self.render_slide_banner("\3", color="\4")
        body = f"{banner}\\n\\n[bold white]\2[/bold white]"
        from rich.align import Align
        return Panel(Align.center(body),''',
    content,
    flags=re.DOTALL
)


with open("commercial_stream.py", "w") as f:
    f.write(content)

