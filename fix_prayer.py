import re

with open("commercial_stream.py", "r") as f:
    stream = f.read()

# Replace the text for build_religion_1 through 6
new_religions = """    def build_religion_1(self) -> Panel: return self._build_religion_generic("BLESSED TRANSACTIONS", "bold white on blue", "ETHICAL COMMERCE", "A fair balance is a delight, and honest weights are pleasing.", "WIN-WIN TOKENOMICS ACHIEVED", "When both buyer and seller prosper, the ecosystem thrives. No hidden fees, no dumping. Just honest, transparent smart contracts.", "🕊️")
    def build_religion_2(self) -> Panel: return self._build_religion_generic("MINDFUL COMMERCE", "bold black on yellow", "RIGHT LIVELIHOOD", "Wealth gained with a pure mind brings harmony to the market.", "MUTUAL PROSPERITY ATTAINED", "Our liquidity pools are balanced with compassion. True wealth is generated when all participants achieve financial peace.", "☸️")
    def build_religion_3(self) -> Panel: return self._build_religion_generic("DHARMATIC EXCHANGE", "bold white on magenta", "KARMIC SYNERGY", "Wealth earned through righteousness multiplies endlessly.", "KARMIC DIVIDENDS DISTRIBUTED", "Every transaction generates positive karma. We build protocols where the community and the developers win together in harmony.", "🕉️")
    def build_religion_4(self) -> Panel: return self._build_religion_generic("HALAL PARTNERSHIPS", "bold white on green", "BLESSED BUSINESS", "God blesses the business of those who are honest and transparent.", "ETHICAL YIELD VERIFIED", "Risk and reward are shared equally. Zero usury, zero exploitation. A true win-win model for the modern blockchain.", "☪️")
    def build_religion_5(self) -> Panel: return self._build_religion_generic("COVENANT OF TRUST", "bold white on blue", "HONEST LEDGERS", "Love your neighbor's portfolio as your own.", "TRANSPARENT LEDGERS BLESSED", "Audited by ethics, secured by faith. We believe in building generational wealth through mutual respect and fair trade.", "✡️")
    def build_religion_6(self) -> Panel: return self._build_religion_generic("HARMONIOUS MARKETS", "bold white on red", "PEACEFUL PROTOCOLS", "The spirits favor those who trade with honor.", "SYNERGY PROTOCOL ACTIVATED", "Like a well-tended garden, our ecosystem grows organically. Respect the community, and the community will nourish the project.", "⛩️")"""

stream = re.sub(r"    def build_religion_1\(self\).*?def build_religion_6\(self\)[^\n]+", new_religions, stream, flags=re.DOTALL)

# Update the generic method to reflect blessings rather than repentance
new_generic = """    def _build_religion_generic(self, banner_text, color, subtitle, quote, punchline, lore, icon) -> Panel:
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
        return Panel(body, title=f"[{color.split(' ')[-1]}]{icon} {banner_text} {icon}[/{color.split(' ')[-1]}]", border_style=color.split(' ')[-1], box=box.ROUNDED)"""

stream = re.sub(r"    def _build_religion_generic\(self.*?(?=    def build_religion_1)", new_generic + "\n\n", stream, flags=re.DOTALL)

with open("commercial_stream.py", "w") as f:
    f.write(stream)

with open("sounds.py", "r") as f:
    sounds = f.read()

new_sound_logic = """def synthesize_arabic_generic(filename, seed):
    import numpy as np, os
    filepath = os.path.join(SOUNDS_DIR, filename)
    if os.path.exists(filepath): return filepath
    np.random.seed(seed)
    SR = 44100; t_total = 16.0; N = int(SR * t_total); mix = np.zeros(N, dtype=np.float32)
    
    roots = [261.63, 293.66, 329.63, 349.23, 392.00, 440.00]
    root = roots[seed % len(roots)]
    
    ratios_bayati = [1.0, 1.0905, 1.1892, 1.3348, 1.4983, 1.5874, 1.7818, 2.0]
    ratios_hijaz = [1.0, 1.0594, 1.2599, 1.3348, 1.4983, 1.5874, 1.7818, 2.0]
    ratios = ratios_bayati if seed % 2 == 0 else ratios_hijaz
    notes = [root * r for r in ratios]
    
    # Ambient Drone (Pedal point on root and 5th)
    t = np.linspace(0, t_total, N, endpoint=False)
    drone_root = np.sin(2 * np.pi * (root/2) * t) * 0.15
    drone_fifth = np.sin(2 * np.pi * (root * ratios[4] / 2) * t) * 0.08
    mix += drone_root + drone_fifth
    
    # Slow Ney (Flute) / Dua vocal style
    num_phrases = 4
    phrase_duration = t_total / num_phrases
    current_freq = notes[0]
    
    for i in range(num_phrases):
        # Pick a target note, prioritizing 1st, 2nd, and 4th degrees of the maqam
        target_freq = notes[np.random.choice([0, 1, 2, 3, 4])]
        
        t_note = np.linspace(0, phrase_duration, int(SR * phrase_duration), endpoint=False)
        
        # Slow glide (portamento) between phrases
        glide = np.linspace(current_freq, target_freq, len(t_note))
        
        # Add breathy noise and reverent vibrato
        vibrato = 1.0 + 0.01 * np.sin(2 * np.pi * 4.5 * t_note)
        f_inst = glide * vibrato
        
        # Breathy flute synthesis (sine + filtered noise)
        tone = np.sin(2 * np.pi * np.cumsum(f_inst) / SR)
        noise = np.random.uniform(-1, 1, len(t_note)) * 0.05
        
        # Very slow attack and release envelope (Dua style)
        env = np.sin(np.pi * t_note / phrase_duration)
        tone = (tone + noise) * env
        
        start_idx = int(i * phrase_duration * SR)
        if start_idx+len(tone) < N: mix[start_idx:start_idx+len(tone)] += tone * 0.4
        
        current_freq = target_freq
        
    return save_wav_helper(filename, mix)"""

sounds = re.sub(r"def synthesize_arabic_generic\(filename, seed\):.*?return save_wav_helper\(filename, mix\)", new_sound_logic, sounds, flags=re.DOTALL)

with open("sounds.py", "w") as f:
    f.write(sounds)

print("done")
