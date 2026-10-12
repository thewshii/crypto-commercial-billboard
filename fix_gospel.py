with open("sounds.py", "r") as f:
    content = f.read()

# gospel_1 replacement
old_g1 = """    base_chords = [
        ([261.63, 329.63, 392.00, 523.25], 1.0),
        ([349.23, 440.00, 523.25, 698.46], 1.0),
        ([261.63, 329.63, 392.00, 523.25], 1.0),
        ([392.00, 493.88, 587.33, 783.99], 1.0),
    ]"""

new_g1 = """    # Brighter, energetic gospel: I - IV - I - V with higher inversions
    base_chords = [
        ([261.63, 329.63, 392.00, 523.25, 659.25], 1.0), # C Maj 9
        ([349.23, 440.00, 523.25, 698.46, 880.00], 1.0), # F Maj 9
        ([261.63, 329.63, 392.00, 523.25, 659.25], 1.0), # C Maj 9
        ([392.00, 493.88, 587.33, 783.99, 987.77], 1.0), # G Maj 9
    ]"""

content = content.replace(old_g1, new_g1)

# gospel_2 replacement
old_g2 = """    base_chords = [
        ([220.00, 261.63, 329.63, 440.00], 1.0),
        ([174.61, 261.63, 349.23, 440.00], 1.0),
        ([130.81, 261.63, 329.63, 392.00], 1.0),
        ([164.81, 329.63, 415.30, 493.88], 1.0),
    ]"""

new_g2 = """    # Uplifting walk-up progression: IV - I/III - ii - I/V - V
    base_chords = [
        ([349.23, 440.00, 523.25, 698.46], 0.8), # F Maj
        ([329.63, 392.00, 523.25, 659.25], 0.8), # C/E
        ([293.66, 349.23, 440.00, 587.33], 0.8), # D min
        ([392.00, 493.88, 587.33, 783.99], 1.6), # G Maj
    ]"""

content = content.replace(old_g2, new_g2)

# gospel_3 replacement
old_g3 = """    mix += organ_chord([261.63, 329.63, 392.00, 523.25, 659.25], 16.0, SR)
    base_notes = [523.25, 587.33, 659.25, 783.99, 880.00, 1046.50, 1174.66, 1318.51]"""

new_g3 = """    # Very bright, triumphant sustained chord (F Major 9) and faster arpeggios
    mix += organ_chord([349.23, 440.00, 523.25, 698.46, 783.99, 880.00], 16.0, SR)
    base_notes = [523.25, 698.46, 783.99, 880.00, 1046.50, 1396.91, 1567.98, 1760.00]"""

content = content.replace(old_g3, new_g3)

with open("sounds.py", "w") as f:
    f.write(content)
print("Updated gospel logic")
