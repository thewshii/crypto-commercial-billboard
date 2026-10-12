import re

with open("commercial_stream.py", "r") as f:
    stream = f.read()

new_religions = """    def build_religion_1(self) -> Panel: return self._build_religion_generic("ROAR OF THE LION", "bold white on red", "TRIBE OF JUDAH", "The wicked flee when no one pursues, but the righteous are bold as a lion.", "THE HONEYPOTS ARE SHATTERED", "The Shofar has sounded. We are marching on the liquidity pools of the corrupt. No scammer is safe from the roar of accountability.", "🦁")
    def build_religion_2(self) -> Panel: return self._build_religion_generic("JERICHO PROTOCOL", "bold black on yellow", "SOUND THE SHOFAR", "And when they make a long blast with the ram's horn... the wall of the city will fall flat.", "THE WALLED GARDENS COLLAPSE", "The centralized exchanges thought their walls were impenetrable. Seven trumpet blasts later, their order books are exposed to the light.", "🎺")
    def build_religion_3(self) -> Panel: return self._build_religion_generic("SWORD OF TRUTH", "bold white on magenta", "RIGHTEOUS WARFARE", "He trains my hands for war, so that my arms can bend a bow of bronze.", "SNIPER BOTS VANQUISHED", "We do not bring peace to the rug-pullers, we bring a sword. The smart contracts have been audited by divine fury.", "⚔️")
    def build_religion_4(self) -> Panel: return self._build_religion_generic("DIVINE RETRIBUTION", "bold white on green", "JUSTICE DELIVERED", "Vengeance is mine, I will repay, says the Lord.", "DEV WALLETS SEIZED", "You thought you could dump on the community and hide in the metaverse? The Lion of Judah tracks all transactions on the public ledger.", "🔥")
    def build_religion_5(self) -> Panel: return self._build_religion_generic("COVENANT OF IRON", "bold white on blue", "UNBREAKABLE SHIELD", "No weapon that is fashioned against you shall succeed.", "FLASH LOAN ATTACKS DEFLECTED", "The armor of truth protects our holdings. The enemy's algorithms shatter against the shield of our diamond-handed faith.", "🛡️")
    def build_religion_6(self) -> Panel: return self._build_religion_generic("HOLY CRUSADE", "bold white on red", "MARCH TO VICTORY", "Be strong and courageous. Do not be frightened, and do not be dismayed.", "THE BULL MARKET CONQUERED", "The war drums are beating. We march together to reclaim the blockchain for the honest, the builders, and the believers.", "🚩")"""

stream = re.sub(r"    def build_religion_1\(self\).*?def build_religion_6\(self\)[^\n]+", new_religions, stream, flags=re.DOTALL)

# Update the generic method to reflect a battle cry
new_generic = """    def _build_religion_generic(self, banner_text, color, subtitle, quote, punchline, lore, icon) -> Panel:
        from rich.panel import Panel
        from rich import box
        banner = self.render_slide_banner(banner_text, color=color)
        body = (
            f"{banner}\\n\\n"
            f"[bold yellow]{icon} {subtitle} {icon}[/bold yellow]\\n\\n"
            f"[italic cyan]\\\"{quote}\\\"[/italic cyan]\\n\\n"
            f"[bold green]⚡ {punchline} ⚡[/bold green]\\n\\n"
            f"[dim]{lore}[/dim]\\n\\n"
            f"{icon} [bold magenta]The Lion of Judah has sounded the warcall.[/bold magenta] {icon}"
        )
        return Panel(body, title=f"[{color.split(' ')[-1]}]{icon} {banner_text} {icon}[/{color.split(' ')[-1]}]", border_style=color.split(' ')[-1], box=box.ROUNDED)"""

stream = re.sub(r"    def _build_religion_generic\(self.*?(?=    def build_religion_1)", new_generic + "\n\n", stream, flags=re.DOTALL)

with open("commercial_stream.py", "w") as f:
    f.write(stream)

with open("sounds.py", "r") as f:
    sounds = f.read()

new_sound_logic = """def synthesize_warcall_generic(filename, seed):
    import numpy as np, os
    filepath = os.path.join(SOUNDS_DIR, filename)
    if os.path.exists(filepath): return filepath
    np.random.seed(seed)
    SR = 44100; t_total = 16.0; N = int(SR * t_total); mix = np.zeros(N, dtype=np.float32)
    
    roots = [146.83, 164.81, 196.00, 220.0, 246.94, 261.63] # Deep, resonant roots for war horns
    root = roots[seed % len(roots)]
    
    # Deep War Drums (Taiko / Timpani style)
    # Slow marching beat: BOOM ... BOOM BOOM
    t = np.linspace(0, t_total, N, endpoint=False)
    for i in range(32): # 2 beats per second
        t_drum = np.linspace(0, 0.5, int(SR * 0.5), endpoint=False)
        
        # Heavy BOOM on beats 1 and 4 of a 4-beat cycle
        if i % 4 == 0 or i % 4 == 3:
            freq_drop = np.exp(-t_drum * 15.0)
            drum_tone = np.sin(2 * np.pi * (40.0 + 50.0 * freq_drop) * t_drum) * np.exp(-t_drum * 4.0)
            drum_noise = np.random.uniform(-1, 1, len(t_drum)) * np.exp(-t_drum * 20.0) * 0.4
            drum = (drum_tone + drum_noise) * 2.0
        else:
            freq_drop = np.exp(-t_drum * 20.0)
            drum_tone = np.sin(2 * np.pi * (60.0 + 30.0 * freq_drop) * t_drum) * np.exp(-t_drum * 6.0)
            drum_noise = np.random.uniform(-1, 1, len(t_drum)) * np.exp(-t_drum * 30.0) * 0.15
            drum = (drum_tone + drum_noise) * 0.8
            
        start_idx = int(i * 0.5 * SR)
        if start_idx + len(drum) < N:
            mix[start_idx:start_idx+len(drum)] += drum
            
    # Epic Shofar / War Horn blasts
    def make_horn(freq, duration, intensity=1.0):
        t_h = np.linspace(0, duration, int(SR * duration), endpoint=False)
        # Pitch instability and slight rise at the end (like an animal horn)
        pitch_mod = 1.0 + 0.015 * np.sin(2 * np.pi * 7.0 * t_h) + 0.06 * (t_h / duration)**4
        
        f_c = freq * pitch_mod
        f_m = freq * pitch_mod
        # High index at attack for a raspy/brassy 'blat', decaying to a purer tone
        index = 5.0 * np.exp(-t_h * 3.0) + 0.5 
        
        horn = np.sin(2 * np.pi * np.cumsum(f_c)/SR + index * np.sin(2 * np.pi * np.cumsum(f_m)/SR))
        
        # Envelope: slow attack, held, then release
        attack_time = min(0.2, duration * 0.2)
        release_time = min(0.4, duration * 0.3)
        env = np.ones_like(t_h)
        attack_samples = int(attack_time * SR)
        release_samples = int(release_time * SR)
        if attack_samples > 0:
            env[:attack_samples] = np.linspace(0, 1, attack_samples)
        if release_samples > 0:
            env[-release_samples:] = np.linspace(1, 0, release_samples)
            
        return horn * env * intensity
        
    # Pattern of horn blasts
    horn1 = make_horn(root, 3.5, 1.2)       # Long opening call
    mix[0:len(horn1)] += horn1
    
    horn2 = make_horn(root * 1.498, 1.5, 0.9) # Perfect 5th short call
    start2 = int(4.5 * SR)
    if start2+len(horn2) < N: mix[start2:start2+len(horn2)] += horn2
    
    horn3 = make_horn(root, 2.5, 1.1)       # Medium call
    start3 = int(7.0 * SR)
    if start3+len(horn3) < N: mix[start3:start3+len(horn3)] += horn3
    
    horn4 = make_horn(root, 2.0, 1.0)       # Build up
    start4 = int(10.5 * SR)
    if start4+len(horn4) < N: mix[start4:start4+len(horn4)] += horn4
    
    horn5 = make_horn(root * 2.0, 3.0, 1.4) # Triumphant final octave blast!
    start5 = int(12.5 * SR)
    if start5+len(horn5) < N: mix[start5:start5+len(horn5)] += horn5
    
    # Background battle clamor/noise to make it sound like an army
    noise = np.random.uniform(-1, 1, N)
    clamor = np.convolve(noise, np.ones(100)/100, mode='same') * 0.15
    mix += clamor

    return save_wav_helper(filename, mix)

def synthesize_religion_1(filename="religion_1.wav"): return synthesize_warcall_generic(filename, 1)
def synthesize_religion_2(filename="religion_2.wav"): return synthesize_warcall_generic(filename, 2)
def synthesize_religion_3(filename="religion_3.wav"): return synthesize_warcall_generic(filename, 3)
def synthesize_religion_4(filename="religion_4.wav"): return synthesize_warcall_generic(filename, 4)
def synthesize_religion_5(filename="religion_5.wav"): return synthesize_warcall_generic(filename, 5)
def synthesize_religion_6(filename="religion_6.wav"): return synthesize_warcall_generic(filename, 6)"""

sounds = re.sub(r"def synthesize_arabic_generic\(filename, seed\):.*?def synthesize_religion_6\(filename=\"religion_6\.wav\"\): return synthesize_arabic_generic\(filename, 6\)", new_sound_logic, sounds, flags=re.DOTALL)

with open("sounds.py", "w") as f:
    f.write(sounds)

print("done warcall")
