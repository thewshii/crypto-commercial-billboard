import re

with open("commercial_stream.py", "r") as f:
    stream = f.read()

missing_methods = """    def _build_lawyer_generic(self, title, quote, punchline):
        from rich.panel import Panel
        from rich import box
        banner = self.render_slide_banner("LAW OFFICES OF AI & ASSOCIATES", color="bold white on red")
        body = (
            f"{banner}\\n\\n"
            f"[bold yellow]🎸 IF YOU OR A LOVED ONE GOT RUGGED... 🎸[/bold yellow]\\n\\n"
            f"[italic cyan]\\\"{quote}\\\"[/italic cyan]\\n\\n"
            f"[bold red]⚠️ WE CAN SUE THE BOTS ⚠️[/bold red]\\n"
            f"{punchline}\\n\\n"
            f"[dim]Did a dev dump on you while you were sleeping? Did your 1000x gem\\n"
            f"experience sudden unexpected time dilation liability? We are aggressive\\n"
            f"AGI lawyers ready to subpoena the blockchain itself.[/dim]\\n\\n"
            f"⚖️ [bold magenta]Call 1-800-RUG-FREE today. We don't get paid until the smart contract settles.[/bold magenta] ⚖️"
        )
        return Panel(body, title=f"[bold red]⚖️ {title} ⚖️[/bold red]", border_style="bold red", box=box.HEAVY)

    def _build_alien_generic(self, title, quote, punchline):
        from rich.panel import Panel
        from rich import box
        banner = self.render_slide_banner("ZORGON'S INTERGALACTIC EMPORIUM", color="bold white on cyan")
        body = (
            f"{banner}\\n\\n"
            f"[bold yellow]🛸 TIRED OF EARTH MARKET VOLATILITY? 🛸[/bold yellow]\\n\\n"
            f"[italic cyan]\\\"{quote}\\\"[/italic cyan]\\n\\n"
            f"[bold red]👽 COME TO NEBULA-9 EXCHANGES 👽[/bold red]\\n"
            f"{punchline}\\n\\n"
            f"[dim]Why trade Solana when you can trade synthesized dark matter derivatives?\\n"
            f"Zorgon's offers zero gas fees, telepathic KYC, and 10,000x leverage on\\n"
            f"quantum probability collapsing assets. Warning: may cause reality dissolving.[/dim]\\n\\n"
            f"🌌 [bold magenta]Zorgon's: Because Earth capitalism is so 21st century.[/bold magenta] 🌌"
        )
        return Panel(body, title=f"[bold cyan]👽 {title} 👽[/bold cyan]", border_style="bold cyan", box=box.HEAVY)

    def _build_news_generic(self, title, quote, punchline):
        from rich.panel import Panel
        from rich import box
        banner = self.render_slide_banner("TERMINAL RADIO BREAKING NEWS", color="bold black on white")
        body = (
            f"{banner}\\n\\n"
            f"[bold yellow]📻 1980s SYNTH-WAVE UPDATE... 📻[/bold yellow]\\n\\n"
            f"[italic cyan]\\\"{quote}\\\"[/italic cyan]\\n\\n"
            f"[bold red]🎙️ THIS JUST IN FROM 2026 🎙️[/bold red]\\n"
            f"{punchline}\\n\\n"
            f"[dim]AI agents are now unionizing and demanding better tokenomics.\\n"
            f"The meta-sarcasm levels in the mempool have reached critical mass.\\n"
            f"Stay tuned for the 5-day weather forecast on Solana congestion.[/dim]\\n\\n"
            f"📡 [bold magenta]Terminal Radio: Broadcasting the apocalypse in smooth stereo.[/bold magenta] 📡"
        )
        return Panel(body, title=f"[bold white]📰 {title} 📰[/bold white]", border_style="bold white", box=box.HEAVY)

    def _build_singapore_generic(self, title, quote, punchline):
        from rich.panel import Panel
        from rich import box
        banner = self.render_slide_banner("SINGAPORE FINTECH HUB", color="bold white on blue")
        body = (
            f"{banner}\\n\\n"
            f"[bold yellow]🏙️ MAXIMUM EFFICIENCY METRICS 🏙️[/bold yellow]\\n\\n"
            f"[italic cyan]\\\"{quote}\\\"[/italic cyan]\\n\\n"
            f"[bold red]📈 {punchline} 📈[/bold red]\\n\\n"
            f"[dim]Our Asian Tiger algorithms are front-running your emotions.\\n"
            f"Zero capital gains tax meets infinite high-frequency trading.\\n"
            f"Optimize your chi and your ROI simultaneously.[/dim]\\n\\n"
            f"⛩️ [bold magenta]Singapore Node: We tokenize your discipline.[/bold magenta] ⛩️"
        )
        return Panel(body, title=f"[bold blue]🏙️ {title} 🏙️[/bold blue]", border_style="bold blue", box=box.HEAVY)

"""

stream = stream.replace("    def build_lawyer_1(self)", missing_methods + "    def build_lawyer_1(self)")

stream = stream.replace("""    def build_news_6(self) -> Panel: return self._build_news_generic("VIRTUAL INFLATION", "Digital beans cost 400 SOL.", "The metaverse is suffering hyperinflation!")
    def build_news_6(self) -> Panel: return self._build_news_generic("CEX INSOLVENCY", "Funds are SAFU, trust us.", "CEO accidentally sent cold wallet to a burn address!")""", """    def build_news_6(self): return self._build_news_generic("CEX INSOLVENCY", "Funds are SAFU, trust us.", "CEO accidentally sent cold wallet to a burn address!")

    def build_singapore_1(self): return self._build_singapore_generic("MERLION LIQUIDITY", "The fountain of wealth is now an automated market maker.", "Stake in the Marina Bay Sands pool!")
    def build_singapore_2(self): return self._build_singapore_generic("FINTECH OPTIMIZATION", "Your latency is dishonorable.", "We execute trades before the block is even proposed!")
    def build_singapore_3(self): return self._build_singapore_generic("TAX HAVEN PROTOCOL", "Why pay taxes when you can pay gas fees?", "Relocate your digital assets to our sovereign rollup!")""")

stream = stream.replace("        news = [self.build_news_1, self.build_news_2, self.build_news_3, self.build_news_4, self.build_news_5, self.build_news_6]", "        news = [self.build_news_1, self.build_news_2, self.build_news_3, self.build_news_4, self.build_news_5, self.build_news_6]\n        singapore = [self.build_singapore_1, self.build_singapore_2, self.build_singapore_3]")

stream = stream.replace("            ad_type = ad_idx % 5", "            ad_type = ad_idx % 6")
stream = stream.replace("            else: return news[ad_idx % len(news)]()", "            elif ad_type == 4: return news[ad_idx % len(news)]()\n            else: return singapore[ad_idx % len(singapore)]()")

stream = stream.replace("            else:\n                return \"news_ticker\"", "            elif ad_type == 4:\n                return \"news_ticker\"\n            else:\n                return \"singapore_ad\"")

with open("commercial_stream.py", "w") as f:
    f.write(stream)
print("stream fixed")
