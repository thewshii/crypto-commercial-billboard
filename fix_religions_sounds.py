import re

with open("sounds.py", "r") as f:
    content = f.read()

# We need to replace `def synthesize_gospel_1` all the way down to the end of `def synthesize_gospel_3`
start_idx = content.find("def synthesize_gospel_1")
end_idx = content.find("def save_wav_helper", start_idx)

new_sounds = """def synthesize_religion_1(filename="religion_1.wav"):
    # Christianity - Upbeat Gospel Organ
    import numpy as np, os
    filepath = os.path.join(SOUNDS_DIR, filename)
    if os.path.exists(filepath): return filepath
    SR = 44100; t_total = 16.0; N = int(SR * t_total); mix = np.zeros(N, dtype=np.float32)
    base_chords = [
        ([261.63, 329.63, 392.00, 523.25, 659.25], 1.0),
        ([349.23, 440.00, 523.25, 698.46, 880.00], 1.0),
        ([261.63, 329.63, 392.00, 523.25, 659.25], 1.0),
        ([392.00, 493.88, 587.33, 783.99, 987.77], 1.0),
    ]
    chords = base_chords * 4
    curr_time = 0
    for notes, dur in chords:
        chord = organ_chord(notes, dur, SR)
        start = int(curr_time * SR)
        if start+len(chord) < N: mix[start:start+len(chord)] += chord
        curr_time += dur
    for i in range(int(t_total * 2)):
        if i % 2 == 1:
            t_clap = np.linspace(0, 0.1, int(SR*0.1), endpoint=False)
            clap = np.random.uniform(-1, 1, len(t_clap)) * np.exp(-t_clap * 40.0)
            start = int(i * 0.5 * SR)
            if start+len(clap) < N: mix[start:start+len(clap)] += clap * 0.8
    return save_wav_helper(filename, mix)

def synthesize_religion_2(filename="religion_2.wav"):
    # Buddhist - Upbeat bells, bowls, and Mokugyo (woodblock)
    import numpy as np, os
    filepath = os.path.join(SOUNDS_DIR, filename)
    if os.path.exists(filepath): return filepath
    SR = 44100; t_total = 16.0; N = int(SR * t_total); mix = np.zeros(N, dtype=np.float32)
    notes = [261.63, 293.66, 329.63, 392.00, 440.00, 523.25, 587.33, 659.25] # Pentatonic
    for i in range(128):
        t_note = np.linspace(0, 0.25, int(SR * 0.25), endpoint=False)
        freq = np.random.choice(notes)
        f_c = freq; f_m = freq * 2.75; index = 3.0 * np.exp(-t_note * 5.0)
        tone = np.sin(2 * np.pi * f_c * t_note + index * np.sin(2 * np.pi * f_m * t_note)) * np.exp(-t_note * 8.0)
        start = int(i * 0.125 * SR)
        if start+len(tone) < N: mix[start:start+len(tone)] += tone * 0.5
    for i in range(64):
        t_drum = np.linspace(0, 0.2, int(SR * 0.2), endpoint=False)
        drum = np.sin(2 * np.pi * 150 * t_drum) * np.exp(-t_drum * 25.0)
        start = int(i * 0.25 * SR)
        if start+len(drum) < N: mix[start:start+len(drum)] += drum * 0.8
    return save_wav_helper(filename, mix)

def synthesize_religion_3(filename="religion_3.wav"):
    # Hindu - Upbeat Sitar and Tabla
    import numpy as np, os
    filepath = os.path.join(SOUNDS_DIR, filename)
    if os.path.exists(filepath): return filepath
    SR = 44100; t_total = 16.0; N = int(SR * t_total); mix = np.zeros(N, dtype=np.float32)
    notes = [261.63, 277.18, 329.63, 349.23, 392.00, 415.30, 493.88, 523.25] # Bhairav scale
    sequence = [0, 1, 2, 4, 3, 2, 1, 0, 4, 5, 6, 7, 6, 5, 4, 2]
    for i in range(64):
        t_note = np.linspace(0, 0.5, int(SR * 0.5), endpoint=False)
        freq = notes[sequence[i % len(sequence)]]
        f_c = freq; f_m = freq * 0.5; index = 5.0 * np.exp(-t_note * 15.0)
        tone = np.sin(2 * np.pi * f_c * t_note + index * np.sin(2 * np.pi * f_m * t_note)) * np.exp(-t_note * 5.0)
        start = int(i * 0.25 * SR)
        if start+len(tone) < N: mix[start:start+len(tone)] += tone * 0.5
    for i in range(128):
        t_drum = np.linspace(0, 0.15, int(SR * 0.15), endpoint=False)
        freq = 300 if i % 4 == 0 else 150
        drum = np.sin(2 * np.pi * freq * t_drum) * np.exp(-t_drum * 30.0)
        start = int(i * 0.125 * SR)
        if start+len(drum) < N: mix[start:start+len(drum)] += drum * 0.6
    return save_wav_helper(filename, mix)

def synthesize_religion_4(filename="religion_4.wav"):
    # Arabic/Islamic - Upbeat Oud and Darbuka
    import numpy as np, os
    filepath = os.path.join(SOUNDS_DIR, filename)
    if os.path.exists(filepath): return filepath
    SR = 44100; t_total = 16.0; N = int(SR * t_total); mix = np.zeros(N, dtype=np.float32)
    notes = [261.63, 277.18, 329.63, 349.23, 392.00, 415.30, 466.16, 523.25] # Hijaz scale
    for i in range(128):
        t_note = np.linspace(0, 0.2, int(SR * 0.2), endpoint=False)
        idx = (i * 3 + (i // 4)) % len(notes)
        freq = notes[idx]
        tone = np.sign(np.sin(2 * np.pi * freq * t_note)) * np.exp(-t_note * 15.0)
        start = int(i * 0.125 * SR)
        if start+len(tone) < N: mix[start:start+len(tone)] += tone * 0.3
    for i in range(64):
        t_drum = np.linspace(0, 0.2, int(SR * 0.2), endpoint=False)
        if i % 4 == 0:
            drum = np.sin(2 * np.pi * 80 * t_drum) * np.exp(-t_drum * 10.0)
        else:
            drum = (np.random.uniform(-1, 1, len(t_drum)) * np.exp(-t_drum * 40.0)) * 0.5
        start = int(i * 0.25 * SR)
        if start+len(drum) < N: mix[start:start+len(drum)] += drum * 0.7
    return save_wav_helper(filename, mix)

def synthesize_religion_5(filename="religion_5.wav"):
    # Judaism - Upbeat Klezmer Clarinet
    import numpy as np, os
    filepath = os.path.join(SOUNDS_DIR, filename)
    if os.path.exists(filepath): return filepath
    SR = 44100; t_total = 16.0; N = int(SR * t_total); mix = np.zeros(N, dtype=np.float32)
    notes = [392.00, 415.30, 493.88, 523.25, 587.33, 622.25, 698.46, 783.99] # Freygish scale
    for i in range(128):
        t_note = np.linspace(0, 0.15, int(SR * 0.15), endpoint=False)
        freq = notes[np.random.randint(0, len(notes))]
        tone = (np.sin(2*np.pi*freq*t_note) + 0.33*np.sin(2*np.pi*3*freq*t_note)) * np.exp(-t_note * 10.0)
        start = int(i * 0.125 * SR)
        if start+len(tone) < N: mix[start:start+len(tone)] += tone * 0.4
    for i in range(64):
        t_beat = np.linspace(0, 0.2, int(SR * 0.2), endpoint=False)
        if i % 2 == 0:
            beat = np.sin(2 * np.pi * 98.00 * t_beat) * np.exp(-t_beat * 15.0)
        else:
            beat = organ_chord([392.00, 493.88, 587.33], 0.2, SR) * 0.5
        start = int(i * 0.25 * SR)
        if start+len(beat) < N: mix[start:start+len(beat)] += beat
    return save_wav_helper(filename, mix)

def synthesize_religion_6(filename="religion_6.wav"):
    # Shinto - Upbeat Taiko and Koto
    import numpy as np, os
    filepath = os.path.join(SOUNDS_DIR, filename)
    if os.path.exists(filepath): return filepath
    SR = 44100; t_total = 16.0; N = int(SR * t_total); mix = np.zeros(N, dtype=np.float32)
    notes = [261.63, 293.66, 311.13, 392.00, 415.30, 523.25, 587.33] # Hirajoshi scale
    for i in range(128):
        t_drum = np.linspace(0, 0.3, int(SR * 0.3), endpoint=False)
        if i % 8 == 0:
            drum = np.sin(2 * np.pi * 60 * t_drum) * np.exp(-t_drum * 10.0) * 1.5
        elif i % 2 == 0:
            drum = np.sin(2 * np.pi * 100 * t_drum) * np.exp(-t_drum * 15.0)
        else:
            drum = (np.random.uniform(-1, 1, len(t_drum)) * np.exp(-t_drum * 30.0)) * 0.4
        start = int(i * 0.125 * SR)
        if start+len(drum) < N: mix[start:start+len(drum)] += drum
    for i in range(64):
        t_note = np.linspace(0, 0.4, int(SR * 0.4), endpoint=False)
        freq = notes[(i * 2 + (i//3)) % len(notes)]
        tone = np.sin(2 * np.pi * freq * t_note) * np.exp(-t_note * 12.0)
        tone += np.sin(2 * np.pi * freq * 2 * t_note) * np.exp(-t_note * 24.0) * 0.5
        start = int(i * 0.25 * SR)
        if start+len(tone) < N: mix[start:start+len(tone)] += tone * 0.6
    return save_wav_helper(filename, mix)

"""

content = content[:start_idx] + new_sounds + content[end_idx:]

with open("sounds.py", "w") as f:
    f.write(content)

print("done sounds update")
