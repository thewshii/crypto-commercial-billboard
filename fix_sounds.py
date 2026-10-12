import re
with open("sounds.py", "r") as f:
    content = f.read()

# We want to replace everything from `def synthesize_jackpot_1` to `def synthesize_pa_chime` (exclusive)
start_idx = content.find("def synthesize_jackpot_1")
end_idx = content.find("def synthesize_pa_chime")

new_jackpot_code = """def synthesize_jackpot_1(filename="jackpot_1.wav"):
    import numpy as np, os
    filepath = os.path.join(SOUNDS_DIR, filename)
    if os.path.exists(filepath): return filepath
    SR = 44100; t_total = 16.0; N = int(SR * t_total); mix = np.zeros(N, dtype=np.float32)
    notes = [523.25, 587.33, 659.25, 783.99, 880.00, 1046.50]; speed = 0.08
    for i in range(int(t_total / speed)):
        freq = notes[i % len(notes)]
        if i % (len(notes)*2) >= len(notes): freq *= 2.0
        t_note = np.linspace(0, speed, int(SR * speed), endpoint=False)
        f_c = freq; f_m = freq * 1.5; index = 2.0 * np.exp(-t_note * 10.0)
        tone = np.sin(2 * np.pi * f_c * t_note + index * np.sin(2 * np.pi * f_m * t_note)) * np.exp(-t_note * 15.0)
        start = int(i * speed * SR); mix[start:start+len(tone)] += tone * 0.5
    mix += coin_shower(N, SR, 160)
    mix += siren(N, SR, 2.0)
    return save_wav_helper(filename, mix)

def synthesize_jackpot_2(filename="jackpot_2.wav"):
    import numpy as np, os
    filepath = os.path.join(SOUNDS_DIR, filename)
    if os.path.exists(filepath): return filepath
    SR = 44100; t_total = 16.0; N = int(SR * t_total); mix = np.zeros(N, dtype=np.float32)
    t = np.linspace(0, t_total, N, endpoint=False)
    for freq in [261.63, 329.63, 392.00, 523.25]:
        pulse = 0.5 + 0.5 * np.sin(2 * np.pi * 8.0 * t)
        tone = np.sin(2 * np.pi * freq * t) * pulse
        mix += tone * np.exp(-t * 0.1) * 0.4
    mix += coin_shower(N, SR, 240)
    return save_wav_helper(filename, mix)

def synthesize_jackpot_3(filename="jackpot_3.wav"):
    import numpy as np, os
    filepath = os.path.join(SOUNDS_DIR, filename)
    if os.path.exists(filepath): return filepath
    SR = 44100; t_total = 16.0; N = int(SR * t_total); mix = np.zeros(N, dtype=np.float32)
    mix += siren(N, SR, 3.0)
    for i in range(64):
        t_ding = np.linspace(0, 0.25, int(SR * 0.25), endpoint=False)
        ding = np.sin(2 * np.pi * 1046.50 * t_ding) * np.exp(-t_ding * 15.0)
        start = int(i * 0.25 * SR)
        if start+len(ding) < N: mix[start:start+len(ding)] += ding * 0.6
    mix += coin_shower(N, SR, 80)
    return save_wav_helper(filename, mix)

def synthesize_jackpot_4(filename="jackpot_4.wav"):
    import numpy as np, os
    filepath = os.path.join(SOUNDS_DIR, filename)
    if os.path.exists(filepath): return filepath
    SR = 44100; t_total = 16.0; N = int(SR * t_total); mix = np.zeros(N, dtype=np.float32)
    for i in range(32):
        t_clunk = np.linspace(0, 0.1, int(SR * 0.1), endpoint=False)
        clunk = np.random.uniform(-1, 1, len(t_clunk)) * np.exp(-t_clunk * 40.0)
        start = int(i * 0.5 * SR)
        if start+len(clunk) < N: mix[start:start+len(clunk)] += clunk * 0.8
    t_bell = np.linspace(0, 16.0, N, endpoint=False)
    bell = np.sin(2 * np.pi * 880.0 * t_bell + np.sin(2 * np.pi * 440.0 * t_bell)) * np.exp(-t_bell * 0.5)
    mix += bell * 0.6
    mix += coin_shower(N, SR, 160)
    return save_wav_helper(filename, mix)

def synthesize_jackpot_5(filename="jackpot_5.wav"):
    import numpy as np, os
    filepath = os.path.join(SOUNDS_DIR, filename)
    if os.path.exists(filepath): return filepath
    SR = 44100; t_total = 16.0; N = int(SR * t_total); mix = np.zeros(N, dtype=np.float32)
    t = np.linspace(0, t_total, N, endpoint=False)
    saw = 0
    for freq in [440, 554.37, 659.25]:
        saw += np.sign(np.sin(2 * np.pi * freq * t)) * 0.2
        saw += np.sign(np.sin(2 * np.pi * (freq+2) * t)) * 0.2
    gate = np.where(np.sin(2 * np.pi * 6.0 * t) > 0, 1.0, 0.0)
    mix += saw * gate * np.exp(-t * 0.2)
    mix += coin_shower(N, SR, 200)
    return save_wav_helper(filename, mix)

def synthesize_jackpot_6(filename="jackpot_6.wav"):
    import numpy as np, os
    filepath = os.path.join(SOUNDS_DIR, filename)
    if os.path.exists(filepath): return filepath
    SR = 44100; t_total = 16.0; N = int(SR * t_total); mix = np.zeros(N, dtype=np.float32)
    notes = [261.63, 293.66, 329.63, 349.23, 392.00, 440.00, 493.88, 523.25]
    for i in range(len(notes)*8):
        freq = notes[i % len(notes)]
        if i >= len(notes): freq *= 2.0
        t_note = np.linspace(0, 0.2, int(SR * 0.2), endpoint=False)
        tone = np.sin(2 * np.pi * freq * t_note) * np.exp(-t_note * 8.0)
        start = int(i * 0.15 * SR)
        if start+len(tone) < N: mix[start:start+len(tone)] += tone * 0.6
    t = np.linspace(0, t_total, N, endpoint=False)
    mix += np.sin(2 * np.pi * 1046.50 * t) * np.exp(-t * 0.1) * 0.3
    mix += coin_shower(N, SR, 320)
    return save_wav_helper(filename, mix)

"""

new_content = content[:start_idx] + new_jackpot_code + content[end_idx:]

with open("sounds.py", "w") as f:
    f.write(new_content)

print("done replacing")
