
def synthesize_rock(filename="rock_lawyer.wav"):
    import numpy as np, os
    filepath = os.path.join(SOUNDS_DIR, filename)
    if os.path.exists(filepath): return filepath
    SR = 44100; t_total = 16.0; N = int(SR * t_total); mix = np.zeros(N, dtype=np.float32)
    t = np.linspace(0, t_total, N, endpoint=False)
    guitar = np.sign(np.sin(2 * np.pi * 82.41 * t) + np.sin(2 * np.pi * 123.47 * t))
    gate = np.where(np.sin(2 * np.pi * 4.0 * t) > 0.3, 1.0, 0.0)
    guitar *= gate
    guitar = np.convolve(guitar, np.ones(10)/10, mode='same')
    for i in range(int(t_total * 2)):
        if i % 2 == 1:
            t_snare = np.linspace(0, 0.2, int(SR*0.2), endpoint=False)
            snare = (np.random.uniform(-1, 1, len(t_snare)) + np.sin(2*np.pi*200*t_snare)) * np.exp(-t_snare * 15.0)
            start = int(i * 0.5 * SR)
            if start+len(snare) < N: mix[start:start+len(snare)] += snare * 1.5
    mix += guitar * 0.7
    return save_wav_helper(filename, mix)

def synthesize_alien_ad(filename="alien_ad.wav"):
    import numpy as np, os
    filepath = os.path.join(SOUNDS_DIR, filename)
    if os.path.exists(filepath): return filepath
    SR = 44100; t_total = 16.0; N = int(SR * t_total); mix = np.zeros(N, dtype=np.float32)
    t = np.linspace(0, t_total, N, endpoint=False)
    pitch = 400.0 + 300.0 * np.exp(- (t % 0.5) * 10.0) * np.sin(2 * np.pi * 8.0 * t)
    theremin = np.sin(2 * np.pi * np.cumsum(pitch) / SR)
    mix += theremin * 0.5
    for i in range(20):
        t_zap = np.linspace(0, 0.3, int(SR*0.3), endpoint=False)
        zap_pitch = 2000.0 * np.exp(-t_zap * 15.0)
        zap = np.sin(2 * np.pi * np.cumsum(zap_pitch) / SR) * np.exp(-t_zap * 5.0)
        start = int(np.random.uniform(0, t_total - 0.5) * SR)
        if start+len(zap) < N: mix[start:start+len(zap)] += zap * 0.6
    return save_wav_helper(filename, mix)

def synthesize_news(filename="news_ticker.wav"):
    import numpy as np, os
    filepath = os.path.join(SOUNDS_DIR, filename)
    if os.path.exists(filepath): return filepath
    SR = 44100; t_total = 16.0; N = int(SR * t_total); mix = np.zeros(N, dtype=np.float32)
    t = np.linspace(0, t_total, N, endpoint=False)
    ticker = np.sign(np.sin(2 * np.pi * 15.0 * t)) * np.sin(2 * np.pi * 2500.0 * t)
    mix += ticker * 0.15
    base_chords = [([261.63, 329.63, 392.00], 1.5), ([349.23, 440.00, 523.25], 1.0), ([392.00, 493.88, 587.33], 1.5)]
    chords = base_chords * 4
    curr = 0
    for notes, dur in chords:
        t_chord = np.linspace(0, dur, int(SR*dur), endpoint=False)
        chord_mix = np.zeros_like(t_chord)
        for freq in notes:
            for harm in range(1, 5):
                chord_mix += (1.0/harm) * np.sin(2 * np.pi * freq * harm * t_chord)
        env = (1.0 - np.exp(-t_chord * 10.0)) * np.exp(-t_chord * 0.5)
        chord_mix *= env
        start = int(curr * SR)
        if start+len(chord_mix) < N: mix[start:start+len(chord_mix)] += chord_mix * 0.6
        curr += dur
    return save_wav_helper(filename, mix)


def organ_chord(notes, duration, SR=44100):
    import numpy as np
    t = np.linspace(0, duration, int(SR * duration), endpoint=False)
    mix = np.zeros_like(t)
    for freq in notes:
        f1 = np.sin(2 * np.pi * freq * t)
        f2 = np.sin(2 * np.pi * freq * 2.0 * t) * 0.5
        f3 = np.sin(2 * np.pi * freq * 3.0 * t) * 0.33
        lfo = 1.0 + 0.2 * np.sin(2 * np.pi * 6.0 * t)
        mix += (f1 + f2 + f3) * lfo
    mix *= np.clip(t * 10, 0, 1) * np.exp(-t * 0.15)
    return mix

def synthesize_warcall_generic(filename, seed):
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
def synthesize_religion_6(filename="religion_6.wav"): return synthesize_warcall_generic(filename, 6)

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

def save_wav_helper(filename, mix, SR=44100):
    import numpy as np, wave, os
    max_val = np.max(np.abs(mix))
    if max_val > 0: mix = mix / max_val * 0.9
    audio_data = (mix * 32767).astype(np.int16)
    filepath = os.path.join(SOUNDS_DIR, filename)
    with wave.open(filepath, "w") as wf:
        wf.setnchannels(1); wf.setsampwidth(2); wf.setframerate(SR)
        wf.writeframes(audio_data.tobytes())
    return filepath

def coin_shower(N, SR, num_coins=30):
    import numpy as np
    mix = np.zeros(N, dtype=np.float32)
    for i in range(num_coins):
        t_coin = np.linspace(0, 0.1, int(SR * 0.1), endpoint=False)
        freq = np.random.uniform(1300, 1600)
        coin = np.sin(2 * np.pi * freq * t_coin + 2.0 * np.sin(2 * np.pi * freq * 1.5 * t_coin))
        coin *= np.exp(-t_coin * 25.0)
        start = int(np.random.uniform(0, (N/SR)-0.1) * SR)
        mix[start:start+len(coin)] += coin * 0.3
    return mix

def siren(N, SR, speed=2.0):
    import numpy as np
    t = np.linspace(0, N/SR, N, endpoint=False)
    return np.sin(2 * np.pi * (500.0 + 200.0 * np.sin(2 * np.pi * speed * t))) * 0.15

def synthesize_jackpot_1(filename="jackpot_1.wav"):
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

def synthesize_pa_chime(filename="pa_chime.wav"):
    import numpy as np
    filepath = os.path.join(SOUNDS_DIR, filename)
    if os.path.exists(filepath): return filepath
    SR = 44100
    notes = [659.25, 523.25, 783.99]
    t_note = 0.4
    N = int(SR * (len(notes) * t_note + 1.5))
    mix = np.zeros(N, dtype=np.float32)
    for i, freq in enumerate(notes):
        t = np.linspace(0, t_note, int(SR * t_note), endpoint=False)
        f_c = freq; f_m = freq * 2.0; index = 1.5 * np.exp(-t * 5.0)
        tone = np.sin(2 * np.pi * f_c * t + index * np.sin(2 * np.pi * f_m * t))
        env = np.exp(-t * 2.0); tone = (tone * env).astype(np.float32)
        start = int(i * t_note * SR); mix[start:start+len(tone)] += tone
        mix[start+int(SR*0.15):start+int(SR*0.15)+len(tone)] += tone * 0.4
        mix[start+int(SR*0.3):start+int(SR*0.3)+len(tone)] += tone * 0.2
        mix[start+int(SR*0.45):start+int(SR*0.45)+len(tone)] += tone * 0.1
    max_val = np.max(np.abs(mix))
    if max_val > 0: mix = mix / max_val * 0.75
    audio_data = (mix * 32767).astype(np.int16)
    with wave.open(filepath, "w") as wf:
        wf.setnchannels(1); wf.setsampwidth(2); wf.setframerate(SR)
        wf.writeframes(audio_data.tobytes())
    return filepath

def synthesize_scanner(filename="scanner.wav"):
    import numpy as np
    filepath = os.path.join(SOUNDS_DIR, filename)
    if os.path.exists(filepath): return filepath
    SR = 44100
    N = int(SR * 1.5)
    mix = np.zeros(N, dtype=np.float32)
    for i in range(8):
        t_blip = np.linspace(0, 0.05, int(SR * 0.05), endpoint=False)
        freq = np.random.uniform(2000, 3000)
        blip = (np.sin(2 * np.pi * freq * t_blip) * np.exp(-t_blip * 30.0)).astype(np.float32)
        start = int(i * 0.08 * SR)
        mix[start:start+len(blip)] += blip * 0.3
    t_beep1 = np.linspace(0, 0.1, int(SR * 0.1), endpoint=False)
    beep1 = (np.sin(2 * np.pi * 1200 * t_beep1)).astype(np.float32)
    t_beep2 = np.linspace(0, 0.25, int(SR * 0.25), endpoint=False)
    beep2 = (np.sin(2 * np.pi * 1600 * t_beep2)).astype(np.float32)
    start_b1 = int(8 * 0.08 * SR)
    mix[start_b1:start_b1+len(beep1)] += beep1 * 0.6
    start_b2 = start_b1 + int(0.12 * SR)
    mix[start_b2:start_b2+len(beep2)] += beep2 * 0.6
    max_val = np.max(np.abs(mix))
    if max_val > 0: mix = mix / max_val * 0.8
    audio_data = (mix * 32767).astype(np.int16)
    with wave.open(filepath, "w") as wf:
        wf.setnchannels(1); wf.setsampwidth(2); wf.setframerate(SR)
        wf.writeframes(audio_data.tobytes())
    return filepath

def synthesize_airlock(filename="airlock.wav"):
    import numpy as np
    filepath = os.path.join(SOUNDS_DIR, filename)
    if os.path.exists(filepath): return filepath
    SR = 44100
    t = np.linspace(0, 1.5, int(SR * 1.5), endpoint=False)
    freq_rumble = 40.0 + 10.0 * np.sin(2 * np.pi * 5.0 * t)
    rumble = (np.sin(2 * np.pi * np.cumsum(freq_rumble) / SR) * np.exp(-t * 1.5)).astype(np.float32)
    noise = np.random.uniform(-1, 1, len(t))
    hiss = (noise * np.exp(-t * 2.0) * 0.4).astype(np.float32)
    mix = rumble + hiss
    N = int(SR * 2.5)
    full_mix = np.zeros(N, dtype=np.float32)
    full_mix[:len(mix)] += mix
    delay = int(SR * 0.2)
    full_mix[delay:delay+len(mix)] += mix * 0.4
    full_mix[delay*2:delay*2+len(mix)] += mix * 0.2
    max_val = np.max(np.abs(full_mix))
    if max_val > 0: full_mix = full_mix / max_val * 0.9
    audio_data = (full_mix * 32767).astype(np.int16)
    with wave.open(filepath, "w") as wf:
        wf.setnchannels(1); wf.setsampwidth(2); wf.setframerate(SR)
        wf.writeframes(audio_data.tobytes())
    return filepath

def synthesize_running(filename="running.wav"):
    import numpy as np
    filepath = os.path.join(SOUNDS_DIR, filename)
    if os.path.exists(filepath): return filepath
    SR = 44100
    num_steps = 10
    step_interval = 0.22
    N = int(SR * (num_steps * step_interval + 0.5))
    mix = np.zeros(N, dtype=np.float32)
    for i in range(num_steps):
        t_step = np.linspace(0, 0.1, int(SR * 0.1), endpoint=False)
        noise = np.random.uniform(-1, 1, len(t_step))
        filtered_noise = np.convolve(noise, np.ones(15)/15, mode='same')
        vol = np.random.uniform(0.6, 1.0)
        step_sound = (filtered_noise * np.exp(-t_step * 45.0) * vol).astype(np.float32)
        echo_delay = int(SR * 0.05)
        echo_sound = (step_sound * 0.25).astype(np.float32)
        start = int(i * step_interval * SR)
        mix[start:start+len(step_sound)] += step_sound
        if start + echo_delay + len(echo_sound) < N:
            mix[start+echo_delay:start+echo_delay+len(echo_sound)] += echo_sound
    max_val = np.max(np.abs(mix))
    if max_val > 0: mix = mix / max_val * 0.8
    audio_data = (mix * 32767).astype(np.int16)
    with wave.open(filepath, "w") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(SR)
        wf.writeframes(audio_data.tobytes())
    return filepath

def synthesize_scream(filename="scream.wav"):
    import numpy as np
    filepath = os.path.join(SOUNDS_DIR, filename)
    if os.path.exists(filepath): return filepath
    SR = 44100
    t = np.linspace(0, 1.2, int(SR * 1.2), endpoint=False)
    f_c = 800.0 + 150.0 * np.sin(2 * np.pi * 12.0 * t) - 400.0 * t
    f_m = 400.0
    index = 3.0 + 2.0 * t
    fm_scream = np.sin(2 * np.pi * np.cumsum(f_c)/SR + index * np.sin(2 * np.pi * f_m * t))
    noise = np.random.uniform(-1, 1, len(t))
    rasp = np.convolve(noise, np.ones(5)/5, mode='same') * 0.4
    scream = fm_scream + rasp
    env = np.clip(t * 50.0, 0, 1) * np.exp(-t * 2.5)
    scream = (scream * env).astype(np.float32)
    max_val = np.max(np.abs(scream))
    if max_val > 0: scream = scream / max_val * 0.9
    audio_data = (scream * 32767).astype(np.int16)
    with wave.open(filepath, "w") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(SR)
        wf.writeframes(audio_data.tobytes())
    return filepath

def synthesize_yell(filename="yell.wav"):
    import numpy as np
    filepath = os.path.join(SOUNDS_DIR, filename)
    if os.path.exists(filepath): return filepath
    SR = 44100
    t = np.linspace(0, 1.5, int(SR * 1.5), endpoint=False)
    f_c = 250.0 + 30.0 * np.sin(2 * np.pi * 8.0 * t) - 50.0 * t
    f_m = 120.0
    index = 2.0 + np.sin(2 * np.pi * 3.0 * t)
    yell = np.sin(2 * np.pi * np.cumsum(f_c)/SR + index * np.sin(2 * np.pi * f_m * t))
    yell = np.clip(yell * 2.0, -1, 1)
    muffled = np.convolve(yell, np.ones(30)/30, mode='same')
    env = np.sin(2 * np.pi * 2.0 * t)
    env = np.clip(env * 2.0, 0, 1) * np.exp(-t * 1.0)
    final_yell = (muffled * env).astype(np.float32)
    max_val = np.max(np.abs(final_yell))
    if max_val > 0: final_yell = final_yell / max_val * 0.9
    audio_data = (final_yell * 32767).astype(np.int16)
    with wave.open(filepath, "w") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(SR)
        wf.writeframes(audio_data.tobytes())
    return filepath

def synthesize_door(filename="door.wav"):
    import numpy as np
    filepath = os.path.join(SOUNDS_DIR, filename)
    if os.path.exists(filepath): return filepath
    SR = 44100
    t = np.linspace(0, 0.4, int(SR * 0.4), endpoint=False)
    freq_thud = 60.0 * np.exp(-t * 20.0) + 20.0
    thud = (np.sin(2 * np.pi * np.cumsum(freq_thud) / SR) * np.exp(-t * 15.0)).astype(np.float32)
    t_clank = np.linspace(0, 0.15, int(SR * 0.15), endpoint=False)
    clank_noise = np.random.uniform(-1, 1, len(t_clank))
    clank = (clank_noise * np.exp(-t_clank * 30.0) * 0.5).astype(np.float32)
    t_hiss = np.linspace(0, 0.5, int(SR * 0.5), endpoint=False)
    hiss_noise = np.random.uniform(-1, 1, len(t_hiss))
    hiss = (hiss_noise * np.exp(-t_hiss * 5.0) * 0.15).astype(np.float32)
    N = int(SR * 1.0)
    mix = np.zeros(N, dtype=np.float32)
    mix[:len(thud)] += thud * 1.5
    mix[int(SR*0.05):int(SR*0.05)+len(clank)] += clank * 0.8
    mix[int(SR*0.2):int(SR*0.2)+len(hiss)] += hiss * 0.6
    max_val = np.max(np.abs(mix))
    if max_val > 0: mix = mix / max_val * 0.9
    audio_data = (mix * 32767).astype(np.int16)
    with wave.open(filepath, "w") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(SR)
        wf.writeframes(audio_data.tobytes())
    return filepath

def synthesize_footsteps(filename="footsteps.wav"):
    import numpy as np
    filepath = os.path.join(SOUNDS_DIR, filename)
    if os.path.exists(filepath): return filepath
    SR = 44100
    num_steps = 4
    step_interval = 0.6
    N = int(SR * (num_steps * step_interval + 1.0))
    mix = np.zeros(N, dtype=np.float32)
    for i in range(num_steps):
        t_step = np.linspace(0, 0.15, int(SR * 0.15), endpoint=False)
        noise = np.random.uniform(-1, 1, len(t_step))
        filtered_noise = np.convolve(noise, np.ones(20)/20, mode='same')
        step_sound = (filtered_noise * np.exp(-t_step * 35.0) * 0.8).astype(np.float32)
        echo_delay = int(SR * 0.08)
        echo_sound = (step_sound * 0.3).astype(np.float32)
        start = int(i * step_interval * SR)
        mix[start:start+len(step_sound)] += step_sound
        if start + echo_delay + len(echo_sound) < N:
            mix[start+echo_delay:start+echo_delay+len(echo_sound)] += echo_sound
    max_val = np.max(np.abs(mix))
    if max_val > 0: mix = mix / max_val * 0.7
    audio_data = (mix * 32767).astype(np.int16)
    with wave.open(filepath, "w") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(SR)
        wf.writeframes(audio_data.tobytes())
    return filepath

import os
import sys
import wave
import struct
import math
import shutil
import subprocess
import threading
import time

SOUNDS_DIR = os.path.join(os.path.dirname(__file__), "sounds")
SOUNDTRACK_FILENAME = "commercial_soundtrack.wav"

SOUNDTRACK_TRACKS = [
    {
        "id": "mothership",
        "title": "🛸 Track 1: Mothership Arrival (126 BPM)",
        "short": "🛸 T1: Mothership",
        "filename": "soundtrack_1_mothership.wav",
        "bpm": 126.0,
    },
    {
        "id": "nebula",
        "title": "🌌 Track 2: Cosmic Nebula Groove (120 BPM)",
        "short": "🌌 T2: Nebula",
        "filename": "soundtrack_2_nebula.wav",
        "bpm": 120.0,
    },
    {
        "id": "hyperdrive",
        "title": "⚡ Track 3: Warp Speed Hyperdrive (134 BPM)",
        "short": "⚡ T3: Hyperdrive",
        "filename": "soundtrack_3_hyperdrive.wav",
        "bpm": 134.0,
    },
    {
        "id": "track_4",
        "title": "👽 Track 4: Alien Transmission (110.0 BPM)",
        "short": "👽 T4: Alien",
        "filename": "soundtrack_4_alien_transmission.wav",
        "bpm": 110.0,
    },
    {
        "id": "track_5",
        "title": "🛰️ Track 5: Cosmic Pulse (112.0 BPM)",
        "short": "🛰️ T5: Cosmic",
        "filename": "soundtrack_5_cosmic_pulse.wav",
        "bpm": 112.0,
    },
    {
        "id": "track_6",
        "title": "🚀 Track 6: Quantum Drift (114.0 BPM)",
        "short": "🚀 T6: Quantum",
        "filename": "soundtrack_6_quantum_drift.wav",
        "bpm": 114.0,
    },
    {
        "id": "track_7",
        "title": "🪐 Track 7: Cyber Echo (116.0 BPM)",
        "short": "🪐 T7: Cyber",
        "filename": "soundtrack_7_cyber_echo.wav",
        "bpm": 116.0,
    },
    {
        "id": "track_8",
        "title": "🌠 Track 8: Astro Wave (118.0 BPM)",
        "short": "🌠 T8: Astro",
        "filename": "soundtrack_8_astro_wave.wav",
        "bpm": 118.0,
    },
    {
        "id": "track_9",
        "title": "☄️ Track 9: Neon Core (120.0 BPM)",
        "short": "☄️ T9: Neon",
        "filename": "soundtrack_9_neon_core.wav",
        "bpm": 120.0,
    },
    {
        "id": "track_10",
        "title": "🛸 Track 10: Neural Grid (122.0 BPM)",
        "short": "🛸 T10: Neural",
        "filename": "soundtrack_10_neural_grid.wav",
        "bpm": 122.0,
    },
    {
        "id": "track_11",
        "title": "🌌 Track 11: Void Signal (124.0 BPM)",
        "short": "🌌 T11: Void",
        "filename": "soundtrack_11_void_signal.wav",
        "bpm": 124.0,
    },
    {
        "id": "track_12",
        "title": "⚡ Track 12: Solar Rift (126.0 BPM)",
        "short": "⚡ T12: Solar",
        "filename": "soundtrack_12_solar_rift.wav",
        "bpm": 126.0,
    },
    {
        "id": "track_13",
        "title": "🔮 Track 13: Lunar Drive (128.0 BPM)",
        "short": "🔮 T13: Lunar",
        "filename": "soundtrack_13_lunar_drive.wav",
        "bpm": 128.0,
    },
    {
        "id": "track_14",
        "title": "✨ Track 14: Stellar Matrix (130.0 BPM)",
        "short": "✨ T14: Stellar",
        "filename": "soundtrack_14_stellar_matrix.wav",
        "bpm": 130.0,
    },
    {
        "id": "track_15",
        "title": "📡 Track 15: Plasma Code (132.0 BPM)",
        "short": "📡 T15: Plasma",
        "filename": "soundtrack_15_plasma_code.wav",
        "bpm": 132.0,
    },
    {
        "id": "track_16",
        "title": "👾 Track 16: Mecha Engine (134.0 BPM)",
        "short": "👾 T16: Mecha",
        "filename": "soundtrack_16_mecha_engine.wav",
        "bpm": 134.0,
    },
    {
        "id": "track_17",
        "title": "🤖 Track 17: Synth Phase (136.0 BPM)",
        "short": "🤖 T17: Synth",
        "filename": "soundtrack_17_synth_phase.wav",
        "bpm": 136.0,
    },
    {
        "id": "track_18",
        "title": "🚀 Track 18: Flux Protocol (138.0 BPM)",
        "short": "🚀 T18: Flux",
        "filename": "soundtrack_18_flux_protocol.wav",
        "bpm": 138.0,
    },
    {
        "id": "track_19",
        "title": "🛰️ Track 19: Nova Realm (140.0 BPM)",
        "short": "🛰️ T19: Nova",
        "filename": "soundtrack_19_nova_realm.wav",
        "bpm": 140.0,
    },
    {
        "id": "track_20",
        "title": "🛸 Track 20: Zero Sphere (142.0 BPM)",
        "short": "🛸 T20: Zero",
        "filename": "soundtrack_20_zero_sphere.wav",
        "bpm": 142.0,
    },
    {
        "id": "track_21",
        "title": "👽 Track 21: Warp Orbit (144.0 BPM)",
        "short": "👽 T21: Warp",
        "filename": "soundtrack_21_warp_orbit.wav",
        "bpm": 144.0,
    },
    {
        "id": "track_22",
        "title": "☄️ Track 22: Hyper Zone (111.0 BPM)",
        "short": "☄️ T22: Hyper",
        "filename": "soundtrack_22_hyper_zone.wav",
        "bpm": 111.0,
    },
]


def synthesize_tone(filename: str, notes: list) -> str:
    """
    Synthesize high-volume, clean chime tones using standard library wave.
    notes: list of (frequency_hz, duration_seconds)
    """
    os.makedirs(SOUNDS_DIR, exist_ok=True)
    filepath = os.path.join(SOUNDS_DIR, filename)
    if os.path.exists(filepath):
        return filepath

    sample_rate = 44100
    with wave.open(filepath, "w") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)

        for freq, dur in notes:
            total_samples = int(sample_rate * dur)
            for i in range(total_samples):
                t = i / sample_rate
                attack = min(i / (sample_rate * 0.005), 1.0)
                decay = max(1.0 - (i / total_samples), 0.0)
                env = attack * (decay ** 0.5)

                fundamental = math.sin(2 * math.pi * freq * t)
                harmonic = 0.3 * math.sin(4 * math.pi * freq * t)
                val = int(32767 * 0.85 * env * (fundamental + harmonic) / 1.3)
                wf.writeframesraw(struct.pack("<h", max(min(val, 32767), -32768)))

    return filepath


def place_sound(buf, sound, pos, vol=1.0):
    """Helper to mix sound into buffer at sample position pos."""
    p = int(pos)
    if p >= len(buf):
        return
    end = min(p + len(sound), len(buf))
    buf[p:end] += sound[:end - p] * vol


def write_soundtrack_wav(out_path: str, mix, sample_rate: int = 44100) -> str:
    """Master compression with tanh soft limiter and 16-bit WAV export."""
    import numpy as np
    mix = np.tanh(mix * 1.25)
    peak = np.max(np.abs(mix))
    if peak > 0:
        mix = (mix / peak) * 0.92

    int16_data = (mix * 32767.0).astype(np.int16)
    with wave.open(out_path, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(int16_data.tobytes())
    return out_path


def synthesize_soundtrack_1(filename: str = "soundtrack_1_mothership.wav") -> str:
    """
    Track 1: 126 BPM Alien Mothership Arrival (Original Favorite).
    Features:
      - Continuous 52 Hz warp engine sub-drone (3.5 Hz LFO)
      - Phrygian-dominant FM alien bassline (A -> Bb -> C# -> D)
      - Flying saucer theremin vibrato glides
      - Extraterrestrial telemetry blips & sample-and-hold FM chatter
      - Integrated echo radar, crystal coin chimes, buy triads, laser sweeps
      - Close Encounters transmission melody chorus (Bars 8-14)
    """
    os.makedirs(SOUNDS_DIR, exist_ok=True)
    out_path = os.path.join(SOUNDS_DIR, filename)
    if os.path.exists(out_path):
        return out_path

    try:
        import numpy as np

        SR = 44100
        bpm = 126.0
        beat = 60.0 / bpm
        bar = beat * 4.0
        bars = 16
        total_sec = bar * bars
        N = int(SR * total_sec)
        mix = np.zeros(N, dtype=np.float32)

        # 1. Percussion
        t_k = np.linspace(0, 0.28, int(SR * 0.28), endpoint=False)
        f_k = 180.0 * np.exp(-t_k * 25.0) + 40.0
        kick = (np.sin(2.0 * np.pi * np.cumsum(f_k) / SR) * np.exp(-t_k * 10.0) * 1.15).astype(np.float32)

        t_s = np.linspace(0, 0.20, int(SR * 0.20), endpoint=False)
        noise_s = np.random.uniform(-1, 1, len(t_s))
        snare = ((noise_s * 0.65 + np.sin(2 * np.pi * 220.0 * t_s) * 0.35) * np.exp(-t_s * 22.0) * 0.85).astype(np.float32)

        t_h = np.linspace(0, 0.045, int(SR * 0.045), endpoint=False)
        fm_h = np.sin(2 * np.pi * 3500.0 * t_h + 2.5 * np.sin(2 * np.pi * 1450.0 * t_h))
        hat = (fm_h * np.exp(-t_h * 75.0) * 0.35).astype(np.float32)

        t_ho = np.linspace(0, 0.18, int(SR * 0.18), endpoint=False)
        fm_ho = np.sin(2 * np.pi * 4200.0 * t_ho + 3.0 * np.sin(2 * np.pi * 1600.0 * t_ho))
        hat_open = (fm_ho * np.exp(-t_ho * 18.0) * 0.40).astype(np.float32)

        for b in range(bars):
            b_start = int(b * bar * SR)
            for step in range(16):
                pos = b_start + int(step * (bar / 16.0) * SR)
                if step % 4 == 2:
                    place_sound(mix, hat_open, pos, 0.45)
                else:
                    place_sound(mix, hat, pos, 0.30)

                if b < 4:
                    if step in (0, 8):
                        place_sound(mix, kick, pos, 0.90)
                else:
                    if step in (0, 4, 8, 12):
                        place_sound(mix, kick, pos, 0.95)
                    if step in (10, 14) and b in (7, 11, 15):
                        place_sound(mix, kick, pos, 0.70)

                if step in (4, 12):
                    place_sound(mix, snare, pos, 0.85)

        # 2. Warp Engine Sub-Drone
        t_all = np.linspace(0, total_sec, N, endpoint=False)
        engine_lfo = np.sin(2 * np.pi * 3.5 * t_all)
        engine_drone = np.sin(2 * np.pi * (52.0 + 6.0 * engine_lfo) * t_all) * (0.15 + 0.05 * engine_lfo)
        mix += engine_drone.astype(np.float32)

        # 3. Phrygian Alien Bassline
        def make_alien_bass(freq, dur):
            t = np.linspace(0, dur, int(SR * dur), endpoint=False)
            mod = np.sin(2 * np.pi * (freq * 2.0) * t) * 2.0 * np.exp(-t * 15.0)
            sub = np.sin(2 * np.pi * (freq * 0.5) * t) * 0.45
            car = np.sin(2 * np.pi * freq * t + mod) * 0.75
            harm = np.sin(2 * np.pi * freq * 3.0 * t) * 0.20
            env = np.exp(-t * 8.0)
            return ((sub + car + harm) * env * 0.65).astype(np.float32)

        bass_roots = [
            110.0, 110.0, 116.54, 116.54, 138.59, 138.59, 146.83, 110.0,
            110.0, 116.54, 138.59, 146.83, 110.0, 138.59, 116.54, 110.0
        ]
        bass_step = bar / 8.0
        for b in range(bars):
            root = bass_roots[b]
            b_start = int(b * bar * SR)
            for s in range(8):
                pos = b_start + int(s * bass_step * SR)
                f = root * 2.0 if (s % 2 == 1 and b >= 4) else root
                place_sound(mix, make_alien_bass(f, bass_step * 0.9), pos, 0.65)

        # 4. Flying Saucer Theremin Glides
        def make_saucer(f_start, f_end, dur, vib_freq=8.0, vib_depth=60.0):
            t = np.linspace(0, dur, int(SR * dur), endpoint=False)
            f_base = np.linspace(f_start, f_end, len(t))
            vibrato = np.sin(2 * np.pi * vib_freq * t) * vib_depth
            phase = 2.0 * np.pi * np.cumsum(f_base + vibrato) / SR
            env = np.sin(np.pi * (t / dur)) ** 0.8
            sig = np.sin(phase) + 0.3 * np.sin(2.0 * phase)
            return (sig * env * 0.45).astype(np.float32)

        saucer_up = make_saucer(700.0, 1400.0, beat * 3.5, vib_freq=7.5)
        saucer_down = make_saucer(1500.0, 600.0, beat * 3.5, vib_freq=9.0)
        for sb in (1, 5, 9, 13):
            place_sound(mix, saucer_up, int((sb * bar + beat * 0.5) * SR), 0.45)
        for sb in (3, 7, 11, 15):
            place_sound(mix, saucer_down, int((sb * bar + beat * 0.5) * SR), 0.45)

        # 5. Extraterrestrial Telemetry
        np.random.seed(42)
        for b in range(bars):
            for _ in range(4):
                t_rand = b * bar + np.random.uniform(0.1, bar - 0.2)
                freq_rand = np.random.choice([880, 1175, 1320, 1568, 1760, 2093, 2349])
                dur_b = 0.08
                t_blip = np.linspace(0, dur_b, int(SR * dur_b), endpoint=False)
                blip = (np.sin(2 * np.pi * freq_rand * t_blip + 3.0 * np.sin(2 * np.pi * freq_rand * 1.5 * t_blip)) * np.exp(-t_blip * 50.0) * 0.25).astype(np.float32)
                place_sound(mix, blip, int(t_rand * SR), 0.30)

        # 6. Integrated Sound Effects
        def make_sonar(freq=2200.0, dur=0.6):
            t = np.linspace(0, dur, int(SR * dur), endpoint=False)
            p = np.sin(2 * np.pi * freq * t + 1.5 * np.sin(2 * np.pi * (freq * 0.5) * t)) * np.exp(-t * 6.0)
            return (p * 0.45).astype(np.float32)

        sonar = make_sonar(2200.0, 0.6)
        for rb in (0, 2, 4, 8, 12):
            p0 = int(rb * bar * SR)
            place_sound(mix, sonar, p0, 0.45)
            place_sound(mix, sonar, p0 + int(beat * 0.5 * SR), 0.22)
            place_sound(mix, sonar, p0 + int(beat * 1.0 * SR), 0.11)

        def make_alien_crystal(f1=987.0, f2=1318.0):
            d1, d2 = 0.07, 0.25
            t1 = np.linspace(0, d1, int(SR * d1), endpoint=False)
            t2 = np.linspace(0, d2, int(SR * d2), endpoint=False)
            s1 = np.sin(2 * np.pi * f1 * t1 + 2.0 * np.sin(2 * np.pi * f1 * 2 * t1)) * np.exp(-t1 * 15.0)
            s2 = np.sin(2 * np.pi * f2 * t2 + 2.0 * np.sin(2 * np.pi * f2 * 2 * t2)) * np.exp(-t2 * 8.0)
            return s1.astype(np.float32), s2.astype(np.float32)

        cr1, cr2 = make_alien_crystal()
        for cb in (2, 4, 6, 10, 14):
            p1 = int((cb * bar + beat * 1.5) * SR)
            place_sound(mix, cr1, p1, 0.55)
            place_sound(mix, cr2, p1 + int(0.07 * SR), 0.60)

        def make_buy_beam():
            d = 0.32
            t = np.linspace(0, d, int(SR * d), endpoint=False)
            b1 = np.sin(2 * np.pi * 880.0 * t[:int(SR * 0.10)]) * np.exp(-t[:int(SR * 0.10)] * 10.0)
            b2 = np.sin(2 * np.pi * 1320.0 * t[:int(SR * 0.12)]) * np.exp(-t[:int(SR * 0.12)] * 8.0)
            b3 = np.sin(2 * np.pi * 1760.0 * t) * np.exp(-t * 6.0)
            return b1.astype(np.float32), b2.astype(np.float32), b3.astype(np.float32)

        bb1, bb2, bb3 = make_buy_beam()
        for byb in (3, 5, 7, 11, 15):
            bp = int((byb * bar + beat * 2.0) * SR)
            place_sound(mix, bb1, bp, 0.55)
            place_sound(mix, bb2, bp + int(0.10 * SR), 0.55)
            place_sound(mix, bb3, bp + int(0.22 * SR), 0.60)

        def make_plasma_beam():
            dur = 0.35
            t = np.linspace(0, dur, int(SR * dur), endpoint=False)
            f_sw = 2200.0 * np.exp(-t * 5.5) + 250.0
            mod = 4.0 * np.sin(2 * np.pi * 120.0 * t)
            phase = 2.0 * np.pi * np.cumsum(f_sw) / SR + mod
            env = np.maximum(1.0 - t / dur, 0.0) ** 0.7
            return (np.sin(phase) * env * 0.75).astype(np.float32)

        plasma = make_plasma_beam()
        place_sound(mix, plasma, int((7 * bar + beat * 3.2) * SR), 0.75)
        place_sound(mix, plasma, int((15 * bar + beat * 3.2) * SR), 0.75)

        t_sir = np.linspace(0, 0.12, int(SR * 0.12), endpoint=False)
        s1 = (np.sin(2 * np.pi * 800.0 * t_sir + 3.0 * np.sin(2 * np.pi * 200.0 * t_sir)) * np.exp(-t_sir * 8.0) * 0.55).astype(np.float32)
        s2 = (np.sin(2 * np.pi * 1200.0 * t_sir + 3.0 * np.sin(2 * np.pi * 300.0 * t_sir)) * np.exp(-t_sir * 8.0) * 0.55).astype(np.float32)
        for s_step in range(4):
            place_sound(mix, s1 if s_step % 2 == 0 else s2, int((7 * bar + beat * s_step) * SR), 0.55)

        # 7. Transmission Melody Chorus (Bars 8-14)
        def make_alien_lead(freq, dur):
            t = np.linspace(0, dur, int(SR * dur), endpoint=False)
            vibrato = np.sin(2 * np.pi * 6.5 * t) * (freq * 0.035) * np.minimum(t / 0.1, 1.0)
            phase = 2.0 * np.pi * np.cumsum(freq + vibrato) / SR
            fm_mod = 2.2 * np.sin(2 * np.pi * (freq * 1.5) * t) * np.exp(-t * 6.0)
            sig = np.sin(phase + fm_mod) + 0.35 * np.sin(2.0 * phase)
            attack = np.minimum(t / 0.01, 1.0)
            decay = np.maximum(1.0 - (t / dur), 0.0) ** 0.5
            return (sig * attack * decay * 0.65).astype(np.float32)

        lead_notes = [
            (8 * bar + beat * 0.0, 440.00, beat * 0.9),   # A4
            (8 * bar + beat * 1.0, 554.37, beat * 0.9),   # C#5
            (8 * bar + beat * 2.0, 659.25, beat * 0.9),   # E5
            (8 * bar + beat * 3.0, 880.00, beat * 1.8),   # A5
            (9 * bar + beat * 1.0, 1108.73, beat * 0.9),  # C#6
            (9 * bar + beat * 2.0, 987.77, beat * 0.9),   # B5
            (9 * bar + beat * 3.0, 880.00, beat * 1.8),   # A5
            (10 * bar + beat * 0.0, 739.99, beat * 0.9),  # F#5
            (10 * bar + beat * 1.0, 783.99, beat * 0.9),  # G5
            (10 * bar + beat * 2.0, 880.00, beat * 0.9),  # A5
            (10 * bar + beat * 3.0, 1108.73, beat * 1.5), # C#6
            (11 * bar + beat * 1.0, 987.77, beat * 0.9),  # B5
            (11 * bar + beat * 2.0, 880.00, beat * 0.9),  # A5
            (11 * bar + beat * 3.0, 659.25, beat * 1.8),  # E5
            (12 * bar + beat * 0.0, 440.00, beat * 0.9),  # A4
            (12 * bar + beat * 1.0, 554.37, beat * 0.9),  # C#5
            (12 * bar + beat * 2.0, 659.25, beat * 0.9),  # E5
            (12 * bar + beat * 3.0, 880.00, beat * 1.8),  # A5
            (13 * bar + beat * 1.0, 1108.73, beat * 0.9), # C#6
            (13 * bar + beat * 2.0, 1318.51, beat * 0.9), # E6
            (13 * bar + beat * 3.0, 1760.00, beat * 2.0), # A6
        ]
        for t_start, f_note, d_note in lead_notes:
            place_sound(mix, make_alien_lead(f_note, d_note), int(t_start * SR), 0.75)

        return write_soundtrack_wav(out_path, mix, SR)
    except Exception:
        return synthesize_tone(filename, [(440, 1.0)])


def synthesize_soundtrack_2(filename: str = "soundtrack_2_nebula.wav") -> str:
    """
    Track 2: 120 BPM Cosmic Nebula Groove.
    Features:
      - 44 Hz deep pulsar gravity-wave sub-drone (1.6 Hz cosmic pulse)
      - Hypnotic 303-style alien acid squelch bassline in D Minor / Dorian
      - Lush Stargate interstellar synth pad chords (Dm9 -> Bbmaj7 -> Gm9 -> A7sus4)
      - Sparkling 16th-note cosmic crystal bell arpeggio
      - Soaring extraterrestrial vocaloid/theremin solo lead (Bars 8-15)
      - Integrated echo radar pings, crystal coin chimes, buy triads, laser sweeps
    """
    os.makedirs(SOUNDS_DIR, exist_ok=True)
    out_path = os.path.join(SOUNDS_DIR, filename)
    if os.path.exists(out_path):
        return out_path

    try:
        import numpy as np

        SR = 44100
        bpm = 120.0
        beat = 60.0 / bpm
        bar = beat * 4.0
        bars = 16
        total_sec = bar * bars
        N = int(SR * total_sec)
        mix = np.zeros(N, dtype=np.float32)

        # 1. Percussion
        t_k = np.linspace(0, 0.30, int(SR * 0.30), endpoint=False)
        f_k = 170.0 * np.exp(-t_k * 22.0) + 45.0
        kick = (np.sin(2.0 * np.pi * np.cumsum(f_k) / SR) * np.exp(-t_k * 8.5) * 1.10).astype(np.float32)

        t_s = np.linspace(0, 0.22, int(SR * 0.22), endpoint=False)
        noise_s = np.random.uniform(-1, 1, len(t_s))
        snare = ((noise_s * 0.70 + np.sin(2 * np.pi * 380.0 * t_s) * 0.30) * np.exp(-t_s * 18.0) * 0.85).astype(np.float32)

        t_h = np.linspace(0, 0.045, int(SR * 0.045), endpoint=False)
        fm_h = np.sin(2 * np.pi * 4500.0 * t_h + 2.5 * np.sin(2 * np.pi * 1800.0 * t_h))
        hat = (fm_h * np.exp(-t_h * 75.0) * 0.35).astype(np.float32)

        t_ho = np.linspace(0, 0.18, int(SR * 0.18), endpoint=False)
        fm_ho = np.sin(2 * np.pi * 5000.0 * t_ho + 3.0 * np.sin(2 * np.pi * 2100.0 * t_ho))
        hat_open = (fm_ho * np.exp(-t_ho * 18.0) * 0.40).astype(np.float32)

        for b in range(bars):
            b_start = int(b * bar * SR)
            for step in range(16):
                pos = b_start + int(step * (bar / 16.0) * SR)
                if step in (2, 6, 10, 14):
                    place_sound(mix, hat_open, pos, 0.40)
                else:
                    place_sound(mix, hat, pos, 0.28)

                if b < 2:
                    if step in (0, 8):
                        place_sound(mix, kick, pos, 0.90)
                else:
                    if step in (0, 6, 8, 14):
                        place_sound(mix, kick, pos, 0.95)
                    if step == 10 and b in (7, 11, 15):
                        place_sound(mix, kick, pos, 0.70)

                if step in (4, 12):
                    place_sound(mix, snare, pos, 0.85)
                if b in (7, 15) and step in (13, 14, 15):
                    place_sound(mix, snare, pos, 0.65)

        # 2. Pulsar Gravity Sub-Drone
        t_all = np.linspace(0, total_sec, N, endpoint=False)
        pulsar_lfo = np.sin(2 * np.pi * 1.6 * t_all)
        drone = np.sin(2 * np.pi * (44.0 + 3.0 * pulsar_lfo) * t_all) * (0.14 + 0.04 * pulsar_lfo)
        mix += drone.astype(np.float32)

        # 3. Alien Acid Bassline
        def make_acid_note(freq, dur):
            t = np.linspace(0, dur, int(SR * dur), endpoint=False)
            cutoff = 3.5 * np.exp(-t * 14.0) + 1.2
            mod = np.sin(2 * np.pi * (freq * 2.0) * t) * cutoff * 2.2
            saw = 2.0 * ((np.cumsum(np.full(len(t), freq)) / SR) % 1.0) - 1.0
            sig = np.sin(2 * np.pi * freq * t + mod) * 0.6 + saw * 0.4
            env = np.exp(-t * 7.5)
            return (sig * env * 0.62).astype(np.float32)

        acid_roots = [
            73.42, 73.42, 87.31, 98.00, 73.42, 73.42, 103.83, 110.00,
            73.42, 87.31, 98.00, 110.00, 130.81, 110.00, 103.83, 73.42
        ]
        step_sec = bar / 16.0
        for b in range(bars):
            root = acid_roots[b]
            b_start = int(b * bar * SR)
            pattern = [0, 2, 4, 6, 8, 10, 12, 14] if b >= 2 else [0, 4, 8, 12]
            for s in pattern:
                f = root * 2.0 if s in (6, 14) else root
                if s == 10 and b % 2 == 1:
                    f = root * 1.5
                pos = b_start + int(s * step_sec * SR)
                place_sound(mix, make_acid_note(f, step_sec * 1.8), pos, 0.65)

        # 4. Stargate Interstellar Synth Chords (Bars 4-15)
        def make_pad_chord(freqs, dur):
            t = np.linspace(0, dur, int(SR * dur), endpoint=False)
            chord = np.zeros(len(t), dtype=np.float32)
            for f in freqs:
                phase = 2 * np.pi * f * t
                sig = np.sin(phase) + 0.3 * np.sin(2 * phase + 0.5) + 0.15 * np.sin(3 * phase)
                chord += sig.astype(np.float32)
            env = (np.minimum(t / 0.15, 1.0) * np.maximum(1.0 - (t / dur), 0.0) ** 0.6).astype(np.float32)
            return (chord / len(freqs)) * env * 0.45

        chord_map = {
            4: [293.66, 349.23, 440.00, 523.25, 659.25], # Dm9
            5: [293.66, 349.23, 440.00, 523.25, 659.25],
            6: [233.08, 293.66, 349.23, 440.00],         # Bbmaj7
            7: [233.08, 293.66, 349.23, 440.00],
            8: [196.00, 293.66, 349.23, 440.00],         # Gm9
            9: [196.00, 293.66, 349.23, 440.00],
            10: [220.00, 293.66, 329.63, 392.00],        # A7sus4
            11: [220.00, 277.18, 329.63, 392.00],        # A7
            12: [293.66, 349.23, 440.00, 523.25, 659.25],
            13: [293.66, 349.23, 440.00, 523.25, 659.25],
            14: [277.18, 329.63, 392.00, 466.16],        # C#dim7
            15: [220.00, 277.18, 329.63, 440.00],        # A turnaround
        }
        for cb, c_freqs in chord_map.items():
            place_sound(mix, make_pad_chord(c_freqs, bar * 0.9), int(cb * bar * SR), 0.45)

        # 5. Cosmic Crystal Bell Arpeggio (Bars 6-15)
        arp_scale = [587.33, 698.46, 783.99, 880.00, 1046.50, 1174.66]
        def make_crystal_bell(freq, dur=0.20):
            t = np.linspace(0, dur, int(SR * dur), endpoint=False)
            sig = np.sin(2 * np.pi * freq * t + 1.8 * np.sin(2 * np.pi * freq * 2.5 * t)) * np.exp(-t * 18.0)
            return (sig * 0.35).astype(np.float32)

        for b in range(6, bars):
            b_start = int(b * bar * SR)
            for s in range(16):
                if s % 2 == 0:
                    note_idx = (b * 4 + (s // 2)) % len(arp_scale)
                    bell = make_crystal_bell(arp_scale[note_idx])
                    place_sound(mix, bell, b_start + int(s * step_sec * SR), 0.32)

        # 6. Extraterrestrial Vocaloid / Solo Lead (Bars 8-15)
        def make_vocal_lead(freq, dur):
            t = np.linspace(0, dur, int(SR * dur), endpoint=False)
            vib = np.sin(2 * np.pi * 5.8 * t) * (freq * 0.04) * np.minimum(t / 0.12, 1.0)
            phase = 2.0 * np.pi * np.cumsum(freq + vib) / SR
            formant = 1.8 * np.sin(2 * np.pi * (freq * 2.2) * t) * np.exp(-t * 5.0)
            sig = np.sin(phase + formant) + 0.3 * np.sin(2 * phase)
            env = np.minimum(t / 0.02, 1.0) * np.maximum(1.0 - (t / dur), 0.0) ** 0.5
            return (sig * env * 0.65).astype(np.float32)

        lead_notes = [
            (8 * bar + beat * 0.0, 440.00, beat * 1.8),  # A4
            (8 * bar + beat * 2.0, 523.25, beat * 0.9),  # C5
            (8 * bar + beat * 3.0, 587.33, beat * 1.5),  # D5
            (9 * bar + beat * 1.0, 698.46, beat * 0.9),  # F5
            (9 * bar + beat * 2.0, 659.25, beat * 0.9),  # E5
            (9 * bar + beat * 3.0, 587.33, beat * 1.8),  # D5
            (10 * bar + beat * 0.0, 523.25, beat * 0.9), # C5
            (10 * bar + beat * 1.0, 587.33, beat * 0.9), # D5
            (10 * bar + beat * 2.0, 440.00, beat * 0.9), # A4
            (10 * bar + beat * 3.0, 392.00, beat * 1.5), # G4
            (11 * bar + beat * 1.0, 440.00, beat * 0.9), # A4
            (11 * bar + beat * 2.0, 523.25, beat * 0.9), # C5
            (11 * bar + beat * 3.0, 587.33, beat * 2.0), # D5
            (12 * bar + beat * 0.0, 698.46, beat * 0.9), # F5
            (12 * bar + beat * 1.0, 783.99, beat * 0.9), # G5
            (12 * bar + beat * 2.0, 880.00, beat * 1.8), # A5
            (13 * bar + beat * 1.0, 1046.50, beat * 0.9),# C6
            (13 * bar + beat * 2.0, 880.00, beat * 0.9), # A5
            (13 * bar + beat * 3.0, 1174.66, beat * 2.0),# D6
        ]
        for t_start, f_n, d_n in lead_notes:
            place_sound(mix, make_vocal_lead(f_n, d_n), int(t_start * SR), 0.70)

        # 7. Integrated Sound Effects
        def make_sonar(freq=2200.0, dur=0.6):
            t = np.linspace(0, dur, int(SR * dur), endpoint=False)
            p = np.sin(2 * np.pi * freq * t + 1.5 * np.sin(2 * np.pi * (freq * 0.5) * t)) * np.exp(-t * 6.0)
            return (p * 0.45).astype(np.float32)

        sonar = make_sonar(2200.0, 0.6)
        for rb in (0, 4, 8, 12):
            p0 = int(rb * bar * SR)
            place_sound(mix, sonar, p0, 0.40)
            place_sound(mix, sonar, p0 + int(beat * 0.5 * SR), 0.20)

        def make_crystal_chime():
            d = 0.25
            t = np.linspace(0, d, int(SR * d), endpoint=False)
            s = np.sin(2 * np.pi * 1318.51 * t + 2.0 * np.sin(2 * np.pi * 2637.0 * t)) * np.exp(-t * 10.0)
            return (s * 0.50).astype(np.float32)

        c_chime = make_crystal_chime()
        for cb in (3, 7, 11, 15):
            place_sound(mix, c_chime, int((cb * bar + beat * 1.5) * SR), 0.55)

        def make_plasma_laser():
            dur = 0.32
            t = np.linspace(0, dur, int(SR * dur), endpoint=False)
            f_sw = 2200.0 * np.exp(-t * 5.0) + 250.0
            phase = 2.0 * np.pi * np.cumsum(f_sw) / SR
            env = np.maximum(1.0 - t / dur, 0.0) ** 0.7
            return (np.sin(phase) * env * 0.65).astype(np.float32)

        laser = make_plasma_laser()
        place_sound(mix, laser, int((7 * bar + beat * 3.2) * SR), 0.70)
        place_sound(mix, laser, int((15 * bar + beat * 3.2) * SR), 0.70)

        return write_soundtrack_wav(out_path, mix, SR)
    except Exception:
        return synthesize_tone(filename, [(440, 1.0)])


def synthesize_soundtrack_3(filename: str = "soundtrack_3_hyperdrive.wav") -> str:
    """
    Track 3: 134 BPM Warp Speed Hyperdrive.
    Features:
      - 88 Hz tachyon reactor engine core (12 Hz ring modulation)
      - High-energy four-on-the-floor electro/psy kick & sizzling offbeat open hats
      - Galloping 16th-note alien psytrance bassline in F# Phrygian / Minor
      - Rapid 16th-note hyperdrive synth arpeggio racing across hyperspace
      - Anthemic, high-octane alien lead hook with pitch glides & 7.2 Hz vibrato
      - Integrated siren alerts, laser zaps, crystal coins, buy triads, victory fanfare
    """
    os.makedirs(SOUNDS_DIR, exist_ok=True)
    out_path = os.path.join(SOUNDS_DIR, filename)
    if os.path.exists(out_path):
        return out_path

    try:
        import numpy as np

        SR = 44100
        bpm = 134.0
        beat = 60.0 / bpm
        bar = beat * 4.0
        bars = 16
        total_sec = bar * bars
        N = int(SR * total_sec)
        mix = np.zeros(N, dtype=np.float32)

        # 1. Percussion
        t_k = np.linspace(0, 0.22, int(SR * 0.22), endpoint=False)
        f_k = 200.0 * np.exp(-t_k * 28.0) + 50.0
        kick = (np.sin(2.0 * np.pi * np.cumsum(f_k) / SR) * np.exp(-t_k * 12.0) * 1.20).astype(np.float32)

        t_s = np.linspace(0, 0.18, int(SR * 0.18), endpoint=False)
        snare = ((np.random.uniform(-1, 1, len(t_s)) * 0.75 + np.sin(2 * np.pi * 420.0 * t_s) * 0.25) * np.exp(-t_s * 22.0) * 0.90).astype(np.float32)

        t_h = np.linspace(0, 0.04, int(SR * 0.04), endpoint=False)
        hat = (np.sin(2 * np.pi * 5000.0 * t_h + 3.0 * np.sin(2 * np.pi * 2000.0 * t_h)) * np.exp(-t_h * 80.0) * 0.35).astype(np.float32)

        t_ho = np.linspace(0, 0.14, int(SR * 0.14), endpoint=False)
        hat_open = (np.sin(2 * np.pi * 5500.0 * t_ho + 3.0 * np.sin(2 * np.pi * 2200.0 * t_ho)) * np.exp(-t_ho * 20.0) * 0.45).astype(np.float32)

        for b in range(bars):
            b_start = int(b * bar * SR)
            for step in range(16):
                pos = b_start + int(step * (bar / 16.0) * SR)
                if step in (2, 6, 10, 14):
                    place_sound(mix, hat_open, pos, 0.50)
                else:
                    place_sound(mix, hat, pos, 0.30)

                if step in (0, 4, 8, 12):
                    place_sound(mix, kick, pos, 1.00)

                if step in (4, 12):
                    place_sound(mix, snare, pos, 0.85)

                if b in (7, 11, 15) and step in (12, 13, 14, 15):
                    place_sound(mix, snare, pos, 0.75)

        # 2. Tachyon Reactor Engine Drone
        t_all = np.linspace(0, total_sec, N, endpoint=False)
        tachyon = np.sin(2 * np.pi * 88.0 * t_all) * (0.12 + 0.04 * np.sin(2 * np.pi * 12.0 * t_all))
        mix += tachyon.astype(np.float32)

        # 3. Galloping Psytrance Alien Bass (F# Minor / Phrygian)
        def make_psy_bass(freq, dur):
            t = np.linspace(0, dur, int(SR * dur), endpoint=False)
            f_sw = freq * (1.0 + 0.8 * np.exp(-t * 40.0))
            phase = 2.0 * np.pi * np.cumsum(f_sw) / SR
            fm = np.sin(2.0 * phase) * 1.5 * np.exp(-t * 22.0)
            sig = np.sin(phase + fm) + 0.35 * np.sin(2.0 * phase)
            env = np.exp(-t * 15.0)
            return (sig * env * 0.72).astype(np.float32)

        psy_roots = [
            92.50, 92.50, 98.00, 92.50, 92.50, 110.00, 123.47, 92.50,
            92.50, 98.00, 110.00, 123.47, 138.59, 123.47, 110.00, 92.50
        ]
        step_sec = bar / 16.0
        for b in range(bars):
            root = psy_roots[b]
            b_start = int(b * bar * SR)
            for s in range(16):
                if s not in (0, 4, 8, 12):
                    pos = b_start + int(s * step_sec * SR)
                    f = root * 2.0 if s % 4 == 2 else root
                    place_sound(mix, make_psy_bass(f, step_sec * 0.95), pos, 0.70)

        # 4. Warp Speed 16th Arpeggio (Bars 4-15)
        arp_scale = [369.99, 440.00, 554.37, 659.25, 739.99, 880.00, 1108.73, 1318.51]
        def make_fast_arp(freq, dur=0.10):
            t = np.linspace(0, dur, int(SR * dur), endpoint=False)
            sig = np.sin(2 * np.pi * freq * t + 2.0 * np.sin(2 * np.pi * (freq * 1.5) * t)) * np.exp(-t * 25.0)
            return (sig * 0.35).astype(np.float32)

        for b in range(4, bars):
            b_start = int(b * bar * SR)
            for s in range(16):
                note_idx = (b * 2 + s) % len(arp_scale)
                arp_note = make_fast_arp(arp_scale[note_idx])
                place_sound(mix, arp_note, b_start + int(s * step_sec * SR), 0.32)

        # 5. Anthemic Hyperdrive Lead Hook (Bars 8-15)
        def make_hyper_lead(freq, dur):
            t = np.linspace(0, dur, int(SR * dur), endpoint=False)
            vib = np.sin(2 * np.pi * 7.2 * t) * (freq * 0.045) * np.minimum(t / 0.08, 1.0)
            phase = 2.0 * np.pi * np.cumsum(freq + vib) / SR
            fm = 2.5 * np.sin(2 * np.pi * (freq * 1.5) * t) * np.exp(-t * 8.0)
            sig = np.sin(phase + fm) + 0.4 * np.sin(2 * phase)
            env = np.minimum(t / 0.015, 1.0) * np.maximum(1.0 - (t / dur), 0.0) ** 0.5
            return (sig * env * 0.75).astype(np.float32)

        lead_notes = [
            (8 * bar + beat * 0.0, 739.99, beat * 1.5),  # F#5
            (8 * bar + beat * 2.0, 880.00, beat * 0.9),  # A5
            (8 * bar + beat * 3.0, 1108.73, beat * 1.5), # C#6
            (9 * bar + beat * 1.0, 987.77, beat * 0.9),  # B5
            (9 * bar + beat * 2.0, 880.00, beat * 0.9),  # A5
            (9 * bar + beat * 3.0, 739.99, beat * 1.8),  # F#5
            (10 * bar + beat * 0.0, 659.25, beat * 0.9), # E5
            (10 * bar + beat * 1.0, 739.99, beat * 0.9), # F#5
            (10 * bar + beat * 2.0, 880.00, beat * 0.9), # A5
            (10 * bar + beat * 3.0, 1108.73, beat * 1.5),# C#6
            (11 * bar + beat * 1.0, 1318.51, beat * 0.9),# E6
            (11 * bar + beat * 2.0, 1108.73, beat * 0.9),# C#6
            (11 * bar + beat * 3.0, 1479.98, beat * 2.0),# F#6
            (12 * bar + beat * 0.0, 739.99, beat * 0.9), # F#5
            (12 * bar + beat * 1.0, 880.00, beat * 0.9), # A5
            (12 * bar + beat * 2.0, 1108.73, beat * 0.9),# C#6
            (12 * bar + beat * 3.0, 1479.98, beat * 1.8),# F#6
            (13 * bar + beat * 1.0, 1318.51, beat * 0.9),# E6
            (13 * bar + beat * 2.0, 1108.73, beat * 0.9),# C#6
            (13 * bar + beat * 3.0, 1760.00, beat * 2.0),# A6
        ]
        for t_start, f_n, d_n in lead_notes:
            place_sound(mix, make_hyper_lead(f_n, d_n), int(t_start * SR), 0.75)

        # 6. Integrated Sound Effects
        # Emergency Siren Build at Bar 7 turnaround
        t_sir = np.linspace(0, 0.10, int(SR * 0.10), endpoint=False)
        s1 = (np.sin(2 * np.pi * 900.0 * t_sir) * np.exp(-t_sir * 10.0) * 0.55).astype(np.float32)
        s2 = (np.sin(2 * np.pi * 1350.0 * t_sir) * np.exp(-t_sir * 10.0) * 0.55).astype(np.float32)
        for s_idx in range(4):
            place_sound(mix, s1 if s_idx % 2 == 0 else s2, int((7 * bar + beat * (2.0 + s_idx * 0.5)) * SR), 0.60)

        # Laser Zaps
        def make_laser_zap():
            d = 0.20
            t = np.linspace(0, d, int(SR * d), endpoint=False)
            f = 2400.0 * np.exp(-t * 18.0) + 300.0
            phase = 2.0 * np.pi * np.cumsum(f) / SR
            return (np.sin(phase) * np.exp(-t * 10.0) * 0.60).astype(np.float32)

        zap = make_laser_zap()
        for zb in (3, 7, 11, 15):
            place_sound(mix, zap, int((zb * bar + beat * 3.5) * SR), 0.65)

        # Victory Fanfare Flourish at Bars 14-15
        fanfare_notes = [
            (14 * bar + beat * 2.0, 523.25, 0.10),
            (14 * bar + beat * 2.5, 659.25, 0.10),
            (14 * bar + beat * 3.0, 783.99, 0.12),
            (14 * bar + beat * 3.5, 1046.50, 0.40),
        ]
        for t_fn, f_fn, d_fn in fanfare_notes:
            t_ff = np.linspace(0, d_fn, int(SR * d_fn), endpoint=False)
            sig_ff = (np.sin(2 * np.pi * f_fn * t_ff) * np.exp(-t_ff * 6.0) * 0.50).astype(np.float32)
            place_sound(mix, sig_ff, int(t_fn * SR), 0.60)

        return write_soundtrack_wav(out_path, mix, SR)
    except Exception:
        return synthesize_tone(filename, [(440, 1.0)])



def synthesize_procedural_track(track_num: int, filename: str, bpm: float, seed: int) -> str:
    """Procedurally synthesize tracks 4-22."""
    os.makedirs(SOUNDS_DIR, exist_ok=True)
    out_path = os.path.join(SOUNDS_DIR, filename)
    if os.path.exists(out_path):
        return out_path

    try:
        import numpy as np

        np.random.seed(seed)
        SR = 44100
        beat = 60.0 / bpm
        bar = beat * 4.0
        bars = 16
        total_sec = bar * bars
        N = int(SR * total_sec)
        mix = np.zeros(N, dtype=np.float32)

        # 1. Percussion
        t_k = np.linspace(0, 0.25, int(SR * 0.25), endpoint=False)
        kick_freq = np.random.uniform(150, 220)
        f_k = kick_freq * np.exp(-t_k * 25.0) + 45.0
        kick = (np.sin(2.0 * np.pi * np.cumsum(f_k) / SR) * np.exp(-t_k * 10.0) * 1.15).astype(np.float32)

        t_h = np.linspace(0, 0.05, int(SR * 0.05), endpoint=False)
        hat = (np.random.uniform(-1, 1, len(t_h)) * np.exp(-t_h * 60.0) * 0.3).astype(np.float32)

        for b in range(bars * 4):
            # Kick on every beat
            k_start = int(b * beat * SR)
            k_end = k_start + len(kick)
            if k_end < N:
                mix[k_start:k_end] += kick

            # Hat on offbeats
            h_start = int((b * beat + beat/2) * SR)
            h_end = h_start + len(hat)
            if h_end < N:
                mix[h_start:h_end] += hat

        # 2. Bassline
        bass_freq = np.random.choice([44.0, 55.0, 65.41, 73.42, 82.41]) # different root notes
        t_b = np.linspace(0, beat/2, int(SR * beat/2), endpoint=False)
        bass_notes = [bass_freq, bass_freq * 1.2, bass_freq * 1.5, bass_freq * 0.8]
        
        for b in range(bars * 8):
            if np.random.random() > 0.3:
                note_freq = bass_notes[b % len(bass_notes)]
                bass_wave = (np.sin(2 * np.pi * note_freq * t_b) + 0.5 * np.sin(2 * np.pi * note_freq * 2 * t_b)) * np.exp(-t_b * 5.0) * 0.6
                
                b_start = int(b * (beat/2) * SR)
                b_end = b_start + len(bass_wave)
                if b_end < N:
                    mix[b_start:b_end] += bass_wave
                    
        # Normalize and save
        max_val = np.max(np.abs(mix))
        if max_val > 0:
            mix = mix / max_val * 0.85
            
        audio_data = (mix * 32767).astype(np.int16)
        with wave.open(out_path, "w") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(SR)
            wf.writeframes(audio_data.tobytes())

        return out_path
    except ImportError:
        return out_path


def synthesize_soundtrack(filename: str = SOUNDTRACK_FILENAME) -> str:
    """Ensure soundtrack exists (defaults to Song 1 / Mothership)."""
    return synthesize_soundtrack_1(filename)


def ensure_soundtrack_file() -> str:
    """Ensure default background soundtrack WAV file exists."""
    out_path = os.path.join(SOUNDS_DIR, SOUNDTRACK_FILENAME)
    if not os.path.exists(out_path):
        return synthesize_soundtrack_1(SOUNDTRACK_FILENAME)
    return out_path


def ensure_all_soundtracks():
    """Ensure all extraterrestrial soundtrack tracks exist on disk."""
    os.makedirs(SOUNDS_DIR, exist_ok=True)
    # Track 1
    synthesize_soundtrack_1("soundtrack_1_mothership.wav")
    # Track 2
    synthesize_soundtrack_2("soundtrack_2_nebula.wav")
    # Track 3
    synthesize_soundtrack_3("soundtrack_3_hyperdrive.wav")
    
    # Tracks 4-22
    for i in range(3, len(SOUNDTRACK_TRACKS)):
        t = SOUNDTRACK_TRACKS[i]
        synthesize_procedural_track(i+1, t["filename"], t["bpm"], seed=i)

    # Also ensure commercial_soundtrack.wav exists
    comm_path = os.path.join(SOUNDS_DIR, SOUNDTRACK_FILENAME)
    t1_path = os.path.join(SOUNDS_DIR, "soundtrack_1_mothership.wav")
    if not os.path.exists(comm_path) and os.path.exists(t1_path):
        try:
            shutil.copy2(t1_path, comm_path)
        except Exception:
            pass


def ensure_sound_files():
    """Ensure all required sound effects and soundtrack files exist."""
    os.makedirs(SOUNDS_DIR, exist_ok=True)
    synthesize_tone("buy.wav", [(880, 0.12), (1320, 0.14), (1760, 0.35)])
    synthesize_tone("profit.wav", [(587, 0.10), (740, 0.10), (880, 0.12), (1175, 0.40)])
    synthesize_tone("dump.wav", [(350, 0.15), (250, 0.25), (350, 0.15), (250, 0.30)])
    synthesize_tone("bell.wav", [(1046, 0.25)])
    synthesize_tone("coin.wav", [(987, 0.08), (1318, 0.35)])
    synthesize_tone("radar.wav", [(2200, 0.40)])
    synthesize_tone("siren.wav", [(800, 0.15), (1200, 0.15), (800, 0.15), (1200, 0.25)])
    synthesize_tone("fanfare.wav", [(523, 0.10), (659, 0.10), (783, 0.12), (1046, 0.45)])
    synthesize_tone("laser.wav", [(1600, 0.08), (1100, 0.08), (700, 0.12)])
    
    synthesize_door()
    synthesize_footsteps()
    synthesize_running()
    synthesize_scream()
    synthesize_yell()
    synthesize_pa_chime()
    synthesize_scanner()
    synthesize_airlock()
    synthesize_jackpot_1()
    synthesize_jackpot_2()
    synthesize_jackpot_3()
    synthesize_jackpot_4()
    synthesize_jackpot_5()
    synthesize_jackpot_6()
    synthesize_religion_1()
    synthesize_religion_2()
    synthesize_religion_3()
    synthesize_religion_4()
    synthesize_religion_5()
    synthesize_religion_6()
    synthesize_rock()
    synthesize_alien_ad()
    synthesize_singapore_ad()
    synthesize_news()

    ensure_all_soundtracks()


def play_audio_file(sound_type: str = "buy"):
    """
    Play the requested sound effect via play-audio in non-blocking background process
    and emit terminal bell character \\a.
    """
    sys.stdout.write("\a")
    sys.stdout.flush()

    wav_filename = f"{sound_type}.wav"
    wav_path = os.path.join(SOUNDS_DIR, wav_filename)

    if not os.path.exists(wav_path):
        ensure_sound_files()

    if os.path.exists(wav_path) and shutil.which("play-audio"):
        try:
            subprocess.Popen(
                ["play-audio", "-s", "media", wav_path],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
        except Exception:
            pass


class BackgroundMusicPlayer:
    """
    Non-blocking background music player for Termux that loops through a 3-track
    extraterrestrial sci-fi soundtrack playlist smoothly in a background thread via play-audio.
    Supports live track switching, pause, resume, and auto-rotation through all 3 songs.
    """
    def __init__(self, initial_track_idx: int = 0):
        self.tracks = SOUNDTRACK_TRACKS
        self.current_track_idx = initial_track_idx % len(self.tracks)
        self.enabled = True
        self.is_paused = False
        self._proc = None
        self._thread = None
        self._stop_event = threading.Event()
        self._lock = threading.Lock()
        self._manual_skip = False

    def start(self):
        """Start looped background music playback in a daemon thread."""
        with self._lock:
            if self._thread and self._thread.is_alive():
                return
            self._stop_event.clear()
            self._thread = threading.Thread(target=self._playback_worker, daemon=True)
            self._thread.start()

    def _playback_worker(self):
        ensure_all_soundtracks()
        while not self._stop_event.is_set():
            if not self.enabled or self.is_paused:
                time.sleep(0.15)
                continue

            with self._lock:
                track = self.tracks[self.current_track_idx]
                filepath = os.path.join(SOUNDS_DIR, track["filename"])

            if not os.path.exists(filepath) or not shutil.which("play-audio"):
                time.sleep(1.0)
                continue

            try:
                proc = subprocess.Popen(
                    ["play-audio", "-s", "media", filepath],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
                with self._lock:
                    self._proc = proc

                user_interrupted = False
                while proc.poll() is None:
                    if self._stop_event.is_set() or not self.enabled or self.is_paused:
                        user_interrupted = True
                        proc.terminate()
                        try:
                            proc.wait(timeout=0.3)
                        except Exception:
                            proc.kill()
                        break
                    time.sleep(0.1)

                with self._lock:
                    self._proc = None
                    if self._manual_skip:
                        self._manual_skip = False
                    elif not user_interrupted and not self._stop_event.is_set() and self.enabled and not self.is_paused:
                        # Auto-advance to next song on natural track completion!
                        self.current_track_idx += 1
                        if self.current_track_idx >= len(self.tracks):
                            self._generate_new_track()

            except Exception:
                time.sleep(0.5)

    def pause(self):
        """Pause playback immediately."""
        with self._lock:
            self.is_paused = True
            if self._proc:
                try:
                    self._proc.terminate()
                except Exception:
                    pass

    def resume(self):
        """Resume playback immediately."""
        with self._lock:
            self.is_paused = False

    def toggle(self) -> bool:
        """Toggle music playback on/off. Returns new enabled state."""
        with self._lock:
            self.enabled = not self.enabled
            if not self.enabled and self._proc:
                try:
                    self._proc.terminate()
                except Exception:
                    pass
            return self.enabled

    def _generate_new_track(self):
        import random
        i = len(self.tracks) + 1
        emojis = ["👽", "🛰️", "🚀", "🪐", "🌠", "☄️", "🛸", "🌌", "⚡", "🔮", "✨", "📡", "👾", "🤖"]
        adjectives = ["Infinite", "Procedural", "Algorithmic", "Stellar", "Cosmic", "Synth", "Quantum", "Cyber"]
        nouns = ["Loop", "Sequence", "Wave", "Pulse", "Rift", "Matrix", "Protocol"]
        emoji = random.choice(emojis)
        adj = random.choice(adjectives)
        noun = random.choice(nouns)
        bpm = float(random.randint(110, 145))
        filename = f"soundtrack_{i}_{adj.lower()}_{noun.lower()}.wav"
        
        synthesize_procedural_track(i, filename, bpm, seed=i*100)
        
        new_track = {
            "id": f"track_{i}",
            "title": f"{emoji} Track {i}: {adj} {noun} ({bpm} BPM)",
            "short": f"{emoji} T{i}: {adj}",
            "filename": filename,
            "bpm": bpm,
        }
        self.tracks.append(new_track)

    def next_track(self) -> dict:
        """Advance immediately to next track, generating infinitely if needed."""
        with self._lock:
            self.current_track_idx += 1
            if self.current_track_idx >= len(self.tracks):
                self._generate_new_track()
                
            self._manual_skip = True
            if self._proc:
                try:
                    self._proc.terminate()
                except Exception:
                    pass
            return self.tracks[self.current_track_idx]

    def prev_track(self) -> dict:
        """Go to previous track."""
        with self._lock:
            self.current_track_idx = (self.current_track_idx - 1) % len(self.tracks)
            self._manual_skip = True
            if self._proc:
                try:
                    self._proc.terminate()
                except Exception:
                    pass
            return self.tracks[self.current_track_idx]

    def prev_track(self) -> dict:
        """Go to previous track in 3-song playlist."""
        with self._lock:
            self.current_track_idx = (self.current_track_idx - 1) % len(self.tracks)
            self._manual_skip = True
            if self._proc:
                try:
                    self._proc.terminate()
                except Exception:
                    pass
            return self.tracks[self.current_track_idx]

    def set_track(self, index: int) -> dict:
        """Switch directly to a track index (0: Mothership, 1: Nebula, 2: Hyperdrive)."""
        with self._lock:
            self.current_track_idx = index % len(self.tracks)
            self._manual_skip = True
            if self._proc:
                try:
                    self._proc.terminate()
                except Exception:
                    pass
            return self.tracks[self.current_track_idx]

    def get_current_track_title(self) -> str:
        with self._lock:
            return self.tracks[self.current_track_idx]["title"]

    def get_current_track_short(self) -> str:
        with self._lock:
            return self.tracks[self.current_track_idx]["short"]

    def get_current_track_info(self) -> dict:
        with self._lock:
            return dict(self.tracks[self.current_track_idx])

    def stop(self):
        """Cleanly terminate child processes and stop playback loop."""
        self._stop_event.set()
        with self._lock:
            if self._proc:
                try:
                    self._proc.terminate()
                    self._proc.wait(timeout=0.3)
                except Exception:
                    self._proc.kill()
                self._proc = None
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=0.5)

    def is_playing(self) -> bool:
        with self._lock:
            return self.enabled and not self.is_paused and (self._proc is not None)


# Ensure files exist upon import
ensure_sound_files()

if __name__ == "__main__":
    print("Testing audio & soundtrack engine...")
    if "--song" in sys.argv or "-m" in sys.argv:
        track_arg = 0
        for i, a in enumerate(sys.argv):
            if a in ("--track", "-t") and i + 1 < len(sys.argv):
                try:
                    track_arg = int(sys.argv[i + 1]) - 1
                except Exception:
                    pass

        player = BackgroundMusicPlayer(initial_track_idx=track_arg)
        info = player.get_current_track_info()
        print(f"Playing 3-Song Alien Playlist (Starting on {info['title']})...")
        player.start()
        try:
            for sec in range(12, 0, -1):
                cur = player.get_current_track_title()
                print(f"🎵 [{cur}] playing... {sec}s remaining (Ctrl+C to stop)")
                time.sleep(1.0)
        finally:
            player.stop()
            print("Soundtrack stopped cleanly.")
    else:
        for s in ["buy", "profit", "dump", "bell", "coin", "radar", "siren", "fanfare", "laser"]:
            print(f"Playing '{s}' sound...")
            play_audio_file(s)
            time.sleep(0.4)
        print("Sound effects test complete!")
