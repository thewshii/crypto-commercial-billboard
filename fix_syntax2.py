with open("commercial_stream.py", "r") as f:
    lines = f.readlines()

new_lines = []
skip = False
for line in lines:
    if "                # 3.5 Absurd Animation" in line:
        skip = True
        new_lines.append("                # 3.5 Absurd Animation (Guy and Girl getting pulled back and forth non stop)\n")
        new_lines.append("                anim_frames = [\n")
        new_lines.append("                    \"[yellow]              O   [|]   O               \\n             /|\\\\==[|]==/|\\\\              \\n             / \\\\  [|]  /_\\\\              [/yellow]\",\n")
        new_lines.append("                    \"[yellow]            O     [|] O                 \\n           /|\\\\====[|]/|\\\\                \\n           < \\\\    [|]/>                 [/yellow]\",\n")
        new_lines.append("                    \"[yellow]          O       [|]O                  \\n         /|\\\\======[|]|\\\\                 \\n         < \\\\      [|]>                  [/yellow]\",\n")
        new_lines.append("                    \"[yellow]            O     [|] O                 \\n           /|\\\\====[|]/|\\\\                \\n           < \\\\    [|]/>                 [/yellow]\",\n")
        new_lines.append("                    \"[yellow]              O   [|]   O               \\n             /|\\\\==[|]==/|\\\\              \\n             / \\\\  [|]  /_\\\\              [/yellow]\",\n")
        new_lines.append("                    \"[yellow]                O [|]     O             \\n              /|\\\\[|]====/|\\\\             \\n              <\\\\ [|]    />              [/yellow]\",\n")
        new_lines.append("                    \"[yellow]                 O[|]       O           \\n                /|[|]======/|\\\\          \\n                <[|]      />            [/yellow]\",\n")
        new_lines.append("                    \"[yellow]                O [|]     O             \\n              /|\\\\[|]====/|\\\\             \\n              <\\\\ [|]    />              [/yellow]\"\n")
        new_lines.append("                ]\n")
        new_lines.append("                from rich.align import Align\n")
        new_lines.append("                # Play at ~6 frames per second for a frantic tug-of-war\n")
        new_lines.append("                frame = anim_frames[int(time.time() * 6) % len(anim_frames)]\n")
        new_lines.append("                console.print(Align.center(frame))\n")
    elif "console.print(Align.center(frame))" in line:
        if skip:
            skip = False
    else:
        if not skip:
            new_lines.append(line)

with open("commercial_stream.py", "w") as f:
    f.writelines(new_lines)
print("fixed syntax")
