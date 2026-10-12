import os
import re

with open("sounds.py", "r") as f:
    content = f.read()

old_generic = """def synthesize_arabic_generic(filename, seed):
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
        
    return save_wav_helper(filename, mix)"""

new_generic = """def synthesize_arabic_generic(filename, seed):
    import numpy as np, os
    filepath = os.path.join(SOUNDS_DIR, filename)
    if os.path.exists(filepath): return filepath
    np.random.seed(seed)
    SR = 44100; t_total = 16.0; N = int(SR * t_total); mix = np.zeros(N, dtype=np.float32)
    
    roots = [261.63, 293.66, 329.63, 349.23, 392.00, 440.00]
    root = roots[seed % len(roots)]
    
    # Arabic Maqam system implementation (using true microtonal ratios)
    # Bayati: 1, 2 half-flat, 3 minor, 4 perfect, 5 perfect, 6 minor, 7 minor
    # Hijaz: 1, 2 minor, 3 major, 4 perfect, 5 perfect, 6 minor, 7 minor
    ratios_bayati = [1.0, 1.0905, 1.1892, 1.3348, 1.4983, 1.5874, 1.7818, 2.0] # 150 cents for 2nd
    ratios_hijaz = [1.0, 1.0594, 1.2599, 1.3348, 1.4983, 1.5874, 1.7818, 2.0] # 100 cents for 2nd, 400 for 3rd
    
    # Alternate between Bayati and Hijaz based on seed
    ratios = ratios_bayati if seed % 2 == 0 else ratios_hijaz
    notes = [root * r for r in ratios]
    
    # Intricate Darbuka rhythm (Masmoudi / Baladi style variation)
    for i in range(128):
        t_drum = np.linspace(0, 0.15, int(SR * 0.15), endpoint=False)
        pos = i % 8
        if pos in [0, 3]: # Doum
            drum = np.sin(2 * np.pi * 90 * t_drum) * np.exp(-t_drum * 12.0)
        elif pos in [1, 5, 7]: # Tek
            drum = (np.random.uniform(-1, 1, len(t_drum)) * np.exp(-t_drum * 40.0)) * 0.4
        else: # Silence or very light ghost note
            drum = (np.random.uniform(-1, 1, len(t_drum)) * np.exp(-t_drum * 60.0)) * 0.1
            
        start_idx = int(i * 0.125 * SR)
        if start_idx+len(drum) < N: mix[start_idx:start_idx+len(drum)] += drum * 0.7
        
    # Microtonal Oud Melody
    seq = []
    # Create a wandering melody that highlights the maqam's signature intervals
    for _ in range(32):
        if np.random.random() > 0.7:
            seq.append(notes[1]) # heavily feature the 2nd degree (half-flat in Bayati)
        else:
            seq.append(np.random.choice(notes))
            
    for i in range(128):
        t_note = np.linspace(0, 0.3, int(SR * 0.3), endpoint=False)
        freq = seq[(i // 2) % len(seq)] if i % 4 != 0 else notes[0] # pulse on the root
        
        # Ornate trills on longer notes
        if i % 8 == 7:
            # Trill to the second degree
            trill_freq = notes[1]
            mod = 1.0 + 0.05 * np.sin(2 * np.pi * 15.0 * t_note) # fast vibrato/trill
            tone = np.sign(np.sin(2 * np.pi * trill_freq * mod * t_note)) * np.exp(-t_note * 12.0)
        else:
            tone = np.sign(np.sin(2 * np.pi * freq * t_note)) * np.exp(-t_note * 18.0)
            
        start_idx = int(i * 0.125 * SR)
        if start_idx+len(tone) < N: mix[start_idx:start_idx+len(tone)] += tone * 0.35
        
    return save_wav_helper(filename, mix)"""

if old_generic in content:
    content = content.replace(old_generic, new_generic)
    with open("sounds.py", "w") as f:
        f.write(content)
    print("Replaced maqam logic.")
else:
    print("Could not find old logic to replace.")
