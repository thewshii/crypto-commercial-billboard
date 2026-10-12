with open("commercial_stream.py", "r") as f:
    lines = f.readlines()

new_lines = []
skip = False
for line in lines:
    if "                # 3.5 Absurd Animation (Guy and Girl at locked door)" in line:
        skip = True
        new_lines.append("                # 3.5 Absurd Animation (Guy and Girl at locked door)\n")
        new_lines.append("                anim_frames = [\n")
        new_lines.append("                    \"[yellow]  O    O   [|]\\n /|\\\\  /|\\\\  [|]\\n / \\\\  /_\\\\  [|][/yellow]\",\n")
        new_lines.append("                    \"[yellow]  O   \\\\O/  [|]\\n /|\\\\   |===[|]\\n / \\\\  /_\\\\  [|][/yellow]\",\n")
        new_lines.append("                    \"[yellow] \\\\O/  \\\\O/  [|]\\n  |====|===[|]\\n / \\\\  /_\\\\  [|][/yellow]\",\n")
        new_lines.append("                    \"[yellow] _O_  _O_  [|]\\n  |    |   [|]\\n / \\\\  /_\\\\  [|][/yellow]\"\n")
        new_lines.append("                ]\n")
        new_lines.append("                from rich.align import Align\n")
        new_lines.append("                frame = anim_frames[int(time.time() * 4) % len(anim_frames)]\n")
        new_lines.append("                console.print(Align.center(frame))\n")
    elif "console.print(Align.center(frame))" in line:
        if skip:
            skip = False
    else:
        if not skip:
            new_lines.append(line)

with open("commercial_stream.py", "w") as f:
    f.writelines(new_lines)
print("fixed")
