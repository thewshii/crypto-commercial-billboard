import re

with open("sounds.py", "r") as f:
    sounds = f.read()

# Replace synthesize_religion_1 through synthesize_religion_6 with Arabic variations
start = sounds.find("def synthesize_religion_1")
end = sounds.find("def save_wav_helper")

new_rel = """def synthesize_arabic_generic(filename, seed):
    import numpy as np, os
    filepath = os.path.join(SOUNDS_DIR, filename)
    if os.path.exists(filepath): return filepath
    np.random.seed(seed)
    SR = 44100; t_total = 16.0; N = int(SR * t_total); mix = np.zeros(N, dtype=np.float32)
    # Hijaz scale in different roots based on seed
    roots = [261.63, 293.66, 329.63, 349.23, 392.00, 440.00]
    root = roots[seed % len(roots)]
    notes = [root, root*1.059, root*1.26, root*1.335, root*1.498, root*1.587, root*1.782, root*2]
    
    # Darbuka beat (Doum and Tek)
    for i in range(128):
        t_drum = np.linspace(0, 0.15, int(SR * 0.15), endpoint=False)
        if i % 8 == 0 or i % 8 == 3:
            drum = np.sin(2 * np.pi * 90 * t_drum) * np.exp(-t_drum * 12.0)
        else:
            drum = (np.random.uniform(-1, 1, len(t_drum)) * np.exp(-t_drum * 40.0)) * 0.4
        start_idx = int(i * 0.125 * SR)
        if start_idx+len(drum) < N: mix[start_idx:start_idx+len(drum)] += drum * 0.6
        
    # Oud Melody
    seq = [np.random.choice(notes) for _ in range(16)]
    for i in range(128):
        t_note = np.linspace(0, 0.25, int(SR * 0.25), endpoint=False)
        freq = seq[i % len(seq)]
        if i % 4 == 0: freq = notes[0] # resolve to root
        tone = np.sign(np.sin(2 * np.pi * freq * t_note)) * np.exp(-t_note * 20.0)
        start_idx = int(i * 0.125 * SR)
        if start_idx+len(tone) < N: mix[start_idx:start_idx+len(tone)] += tone * 0.3
        
    return save_wav_helper(filename, mix)

def synthesize_religion_1(filename="religion_1.wav"): return synthesize_arabic_generic(filename, 1)
def synthesize_religion_2(filename="religion_2.wav"): return synthesize_arabic_generic(filename, 2)
def synthesize_religion_3(filename="religion_3.wav"): return synthesize_arabic_generic(filename, 3)
def synthesize_religion_4(filename="religion_4.wav"): return synthesize_arabic_generic(filename, 4)
def synthesize_religion_5(filename="religion_5.wav"): return synthesize_arabic_generic(filename, 5)
def synthesize_religion_6(filename="religion_6.wav"): return synthesize_arabic_generic(filename, 6)

def synthesize_singapore_ad(filename="singapore_ad.wav"):
    import numpy as np, os
    filepath = os.path.join(SOUNDS_DIR, filename)
    if os.path.exists(filepath): return filepath
    SR = 44100; t_total = 16.0; N = int(SR * t_total); mix = np.zeros(N, dtype=np.float32)
    # Pentatonic Asian Synth (Singapore vibe)
    notes = [392.00, 440.00, 493.88, 587.33, 659.25, 783.99, 880.00] # G major pentatonic
    for i in range(128):
        t_note = np.linspace(0, 0.3, int(SR * 0.3), endpoint=False)
        freq = notes[(i * 3 + i//2) % len(notes)]
        # Guzheng/Koto style pluck
        tone = np.sin(2 * np.pi * freq * t_note) * np.exp(-t_note * 10.0)
        tone += np.sin(2 * np.pi * freq * 2 * t_note) * np.exp(-t_note * 20.0) * 0.5
        start_idx = int(i * 0.125 * SR)
        if start_idx+len(tone) < N: mix[start_idx:start_idx+len(tone)] += tone * 0.7
        
    # Futuristic tech beat
    for i in range(64):
        t_drum = np.linspace(0, 0.1, int(SR * 0.1), endpoint=False)
        if i % 2 == 0:
            drum = (np.random.uniform(-1, 1, len(t_drum)) * np.exp(-t_drum * 50.0))
            start_idx = int(i * 0.25 * SR)
            if start_idx+len(drum) < N: mix[start_idx:start_idx+len(drum)] += drum * 0.5
    return save_wav_helper(filename, mix)

"""

sounds = sounds[:start] + new_rel + sounds[end:]

# ensure synthesize_singapore_ad is added to ensure_sound_files
if "synthesize_singapore_ad()" not in sounds:
    sounds = sounds.replace("synthesize_alien_ad()", "synthesize_alien_ad()\n    synthesize_singapore_ad()")

with open("sounds.py", "w") as f:
    f.write(sounds)

print("sounds fixed")
