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
            f"[bold green]✨ {punchline} ✨[/bold green]\\n\\n"
            f"[dim]{lore}[/dim]\\n\\n"
            f"{icon} [bold magenta]May our trades be blessed and mutually beneficial.[/bold magenta] {icon}"
        )
        return Panel(body, title=f"[{color.split(' ')[-1]}]{icon} {banner_text} {icon}[/{color.split(' ')[-1]}]", border_style=color.split(' ')[-1], box=box.ROUNDED)

    def build_religion_1(self) -> Panel: return self._build_religion_generic("BLESSED TRANSACTIONS", "bold white on blue", "ETHICAL COMMERCE", "A fair balance is a delight, and honest weights are pleasing.", "WIN-WIN TOKENOMICS ACHIEVED", "When both buyer and seller prosper, the ecosystem thrives. No hidden fees, no dumping. Just honest, transparent smart contracts.", "🕊️")
    def build_religion_2(self) -> Panel: return self._build_religion_generic("MINDFUL COMMERCE", "bold black on yellow", "RIGHT LIVELIHOOD", "Wealth gained with a pure mind brings harmony to the market.", "MUTUAL PROSPERITY ATTAINED", "Our liquidity pools are balanced with compassion. True wealth is generated when all participants achieve financial peace.", "☸️")
    def build_religion_3(self) -> Panel: return self._build_religion_generic("DHARMATIC EXCHANGE", "bold white on magenta", "KARMIC SYNERGY", "Wealth earned through righteousness multiplies endlessly.", "KARMIC DIVIDENDS DISTRIBUTED", "Every transaction generates positive karma. We build protocols where the community and the developers win together in harmony.", "🕉️")
    def build_religion_4(self) -> Panel: return self._build_religion_generic("HALAL PARTNERSHIPS", "bold white on green", "BLESSED BUSINESS", "God blesses the business of those who are honest and transparent.", "ETHICAL YIELD VERIFIED", "Risk and reward are shared equally. Zero usury, zero exploitation. A true win-win model for the modern blockchain.", "☪️")
    def build_religion_5(self) -> Panel: return self._build_religion_generic("COVENANT OF TRUST", "bold white on blue", "HONEST LEDGERS", "Love your neighbor's portfolio as your own.", "TRANSPARENT LEDGERS BLESSED", "Audited by ethics, secured by faith. We believe in building generational wealth through mutual respect and fair trade.", "✡️")
    def build_religion_6(self) -> Panel: return self._build_religion_generic("HARMONIOUS MARKETS", "bold white on red", "PEACEFUL PROTOCOLS", "The spirits favor those who trade with honor.", "SYNERGY PROTOCOL ACTIVATED", "Like a well-tended garden, our ecosystem grows organically. Respect the community, and the community will nourish the project.", "⛩️")
""")
    elif "def _build_lawyer_generic(" in line or "def build_lawyer_1(" in line:
        if skip:
            skip = False
            
    if not skip:
        new_lines.append(line)

with open("commercial_stream.py", "w") as f:
    f.writelines(new_lines)

print("done")
