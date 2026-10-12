import re

with open("commercial_stream.py", "r") as f:
    content = f.read()

# 1. Jackpot generic
jackpot_old = """    def _build_jackpot_generic(self, title, subtitle, prize) -> Panel:
        banner = self.render_slide_banner(title, color="bold white on green")
        body = (
            f"{banner}\\n\\n"
            f"[blink bold red]🚨 EVERYBODY STOP! WE HAVE A WINNER! 🚨[/blink bold red]\\n\\n"
            f"🎉 [bold yellow]CONGRATULATIONS![/bold yellow] 🎉\\n"
            f"[bold green]{subtitle}[/bold green]\\n"
            f"💰 [bold white on green] {prize} [/bold white on green] 💰\\n\\n"
            f"[bold cyan]...Just kidding.[/bold cyan]\\n"
            f"[dim]Nobody wins anything randomly. This is exactly how the scammers operate.\\n"
            f"They use flashing lights, fake sirens, and fabricated urgency to shut down\\n"
            f"your critical thinking so you'll click their malicious link or buy their token.[/dim]\\n\\n"
            f"[bold magenta]The truth?[/bold magenta]\\n"
            f"The only guaranteed profit in crypto is from people who build the tools,\\n"
            f"or the scammers running the games. Stop playing 3-card monte.\\n\\n"
            f"🐘 [bold yellow]WAKE UP. THE HOUSE ALWAYS WINS.[/bold yellow] 🐘"
        )"""

jackpot_new = """    def _build_jackpot_generic(self, title, subtitle, prize) -> Panel:
        banner = self.render_slide_banner(title, color="bold white on green")
        body = (
            f"{banner}\\n\\n"
            f"[blink bold red]🚨 EVERYBODY STOP! WE HAVE A WINNER! 🚨[/blink bold red]\\n\\n"
            f"[bold green]{subtitle.upper()}[/bold green]\\n\\n"
            f"💰 [bold white on green] {prize} [/bold white on green] 💰\\n\\n"
            f"🐘 [bold yellow]WAKE UP. THE HOUSE ALWAYS WINS.[/bold yellow] 🐘"
        )"""
content = content.replace(jackpot_old, jackpot_new)

# 2. Lawyer generic
lawyer_old = """    def _build_lawyer_generic(self, subtitle, hook, promise, icon="⚖️") -> Panel:
        from rich.panel import Panel
        from rich import box
        banner = self.render_slide_banner("LAW FIRM", color="bold white on red")
        body = (
            f"{banner}\\n\\n"
            f"[bold yellow]{icon} {subtitle} {icon}[/bold yellow]\\n\\n"
            f"[bold red]{hook}[/bold red]\\n\\n"
            f"[italic cyan]\"{promise}\"[/italic cyan]\\n\\n"
            f"[dim]They told you the liquidity was locked. They told you the dev was doxxed.\\n"
            f"They lied. And now you're holding a bag of worthless tokens.\\n"
            f"Our AI lawyers will sue the scammers in the metaverse court of law.[/dim]\\n\\n"
            f"[bold cyan]Call the Crypto Rug Filter today! 1-800-RUG-FILTER...[/bold cyan]"
        )"""

lawyer_new = """    def _build_lawyer_generic(self, subtitle, hook, promise, icon="⚖️") -> Panel:
        from rich.panel import Panel
        from rich import box
        banner = self.render_slide_banner("LAW FIRM", color="bold white on red")
        body = (
            f"{banner}\\n\\n"
            f"[bold yellow]{icon} {subtitle.upper()} {icon}[/bold yellow]\\n\\n"
            f"[bold red]⚡ {hook.upper()} ⚡[/bold red]\\n\\n"
            f"[bold cyan]📞 CALL THE CRYPTO RUG FILTER TODAY! 📞[/bold cyan]"
        )"""
content = content.replace(lawyer_old, lawyer_new)

# 3. Alien generic
alien_old = """    def _build_alien_generic(self, subtitle, hook, truth, icon="🛸") -> Panel:
        from rich.panel import Panel
        from rich import box
        banner = self.render_slide_banner("GALACTIC TRUTH", color="bold black on cyan")
        body = (
            f"{banner}\\n\\n"
            f"[bold yellow]{icon} {subtitle} {icon}[/bold yellow]\\n\\n"
            f"[bold cyan]{hook}[/bold cyan]\\n\\n"
            f"[dim]The Earth is flat? No. But the order books are.\\n"
            f"They are manipulating the charts with quantum algorithms.\\n"
            f"The extraterrestrials have already solved the MEV crisis.\\n"
            f"Are you ready for the truth?[/dim]\\n\\n"
            f"[bold magenta]⚡ {truth} ⚡[/bold magenta]"
        )"""

alien_new = """    def _build_alien_generic(self, subtitle, hook, truth, icon="🛸") -> Panel:
        from rich.panel import Panel
        from rich import box
        banner = self.render_slide_banner("GALACTIC TRUTH", color="bold black on cyan")
        body = (
            f"{banner}\\n\\n"
            f"[bold yellow]{icon} {subtitle.upper()} {icon}[/bold yellow]\\n\\n"
            f"[bold cyan]🛸 {hook.upper()} 🛸[/bold cyan]\\n\\n"
            f"[bold magenta]⚡ {truth.upper()} ⚡[/bold magenta]"
        )"""
content = content.replace(alien_old, alien_new)

with open("commercial_stream.py", "w") as f:
    f.write(content)
