with open("commercial_stream.py", "r") as f:
    lines = f.readlines()

new_lines = []
skip = False
for line in lines:
    if "def _build_religion_generic(" in line:
        skip = True
        
        new_lines.append("""    def _build_religion_generic(self, banner_text, color, subtitle, quote, punchline, lore, icon) -> Panel:
        from rich.panel import Panel
        from rich import box
        banner = self.render_slide_banner(banner_text, color=color)
        body = (
            f"{banner}\\n\\n"
            f"[bold yellow]{icon} {subtitle} {icon}[/bold yellow]\\n\\n"
            f"[italic cyan]\\\"{quote}\\\"[/italic cyan]\\n\\n"
            f"[bold red]⚠️ {punchline} ⚠️[/bold red]\\n\\n"
            f"[dim]{lore}[/dim]\\n\\n"
            f"{icon} [bold magenta]Repent your degenerate ways.[/bold magenta] {icon}"
        )
        return Panel(body, title=f"[{color.split(' ')[-1]}]{icon} {banner_text} {icon}[/{color.split(' ')[-1]}]", border_style=color.split(' ')[-1], box=box.HEAVY)

    def build_religion_1(self) -> Panel: return self._build_religion_generic("HOLY AUDIT", "bold white on blue", "TEMPLE CLEANSING IN PROGRESS", "He overturned the tables of the money-changers...", "INCOMING TABLE FLIP: Raydium pools are getting flipped.", "Wait, are we exchanging Solana in here? Jesus just joined the stream and He looks furious about the bonding curve. Brace for impact!", "⛪")
    def build_religion_2(self) -> Panel: return self._build_religion_generic("KARMIC REBALANCING", "bold black on yellow", "ACHIEVING NIRVANA", "Desire is the root of all suffering, especially 100x leverage.", "YOUR PORTFOLIO WENT TO ZERO", "The Buddha has analyzed your on-chain activity. To escape the endless cycle of getting rugged and rebuying, you must let go of your shitcoins. Detach from the chart.", "☸️")
    def build_religion_3(self) -> Panel: return self._build_religion_generic("REINCARNATION PROTOCOL", "bold white on magenta", "CYCLE OF SAMSARA", "As a man sheds worn-out garments, the soul sheds rugged tokens.", "LORD SHIVA IS DANCING ON YOUR MEMECOIN", "Your wallet has accumulated terrible karma from buying animal coins. You are destined to reincarnate as a Solana validator. Pray to Lakshmi for liquidity.", "🕉️")
    def build_religion_4(self) -> Panel: return self._build_religion_generic("HALAL YIELD VERIFICATION", "bold white on green", "HARAM DETECTED", "Riba (usury) is forbidden. Staking rewards are highly suspicious.", "FATWA COUNCIL BLACKLISTED YOUR FARM", "We brought in the scholars to audit the smart contract. Earning 10,000% APY from thin air is spiritually bankrupt. Seek true wealth in utility, not ponzinomics.", "☪️")
    def build_religion_5(self) -> Panel: return self._build_religion_generic("KOSHER SMART CONTRACTS", "bold white on blue", "WANDERING THE BEAR MARKET", "Let my people go... from this honeypot trap!", "MOSES CAN'T PART THIS SLIPPAGE", "The Rabbi has inspected the tokenomics and declared them non-kosher. You are wandering the desert of the bear market for 40 years. Repent and buy Bitcoin.", "✡️")
    def build_religion_6(self) -> Panel: return self._build_religion_generic("KAMI OF THE BLOCKCHAIN", "bold white on red", "SHRINE PURIFICATION", "The spirits of abandoned protocols weep in the digital shrine.", "YOU ANGERED THE YOKAI OF IMPERMANENT LOSS", "Purify your hardware wallet at the Torii gate. The spirits demand an offering of clean code, not copy-pasted forks. Sweep the dust from your portfolio.", "⛩️")
""")
    elif "def build_jackpot_1" in line:
        skip = False
        
    if not skip:
        new_lines.append(line)

with open("commercial_stream.py", "w") as f:
    f.writelines(new_lines)

print("done")
