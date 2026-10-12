import re

with open("commercial_stream.py", "r") as f:
    stream = f.read()

anim_code = """                # 3.5 Absurd Animation (Guy and Girl getting pulled back and forth non stop)
                anim_frames = [
                    \"[yellow]              O   [|]   O               \\n             /|\\\\==[|]==/|\\\\              \\n             / \\\\  [|]  /_\\\\              [/yellow]\",
                    \"[yellow]            O     [|] O                 \\n           /|\\\\====[|]/|\\\\                \\n           < \\\\    [|]/>                 [/yellow]\",
                    \"[yellow]          O       [|]O                  \\n         /|\\\\======[|]|\\\\                 \\n         < \\\\      [|]>                  [/yellow]\",
                    \"[yellow]            O     [|] O                 \\n           /|\\\\====[|]/|\\\\                \\n           < \\\\    [|]/>                 [/yellow]\",
                    \"[yellow]              O   [|]   O               \\n             /|\\\\==[|]==/|\\\\              \\n             / \\\\  [|]  /_\\\\              [/yellow]\",
                    \"[yellow]                O [|]     O             \\n              /|\\\\[|]====/|\\\\             \\n              <\\\\ [|]    />              [/yellow]\",
                    \"[yellow]                 O[|]       O           \\n                /|[|]======/|\\\\          \\n                <[|]      />            [/yellow]\",
                    \"[yellow]                O [|]     O             \\n              /|\\\\[|]====/|\\\\             \\n              <\\\\ [|]    />              [/yellow]\"
                ]
                from rich.align import Align
                # Play at ~6 frames per second for a frantic tug-of-war
                frame = anim_frames[int(time.time() * 6) % len(anim_frames)]
                console.print(Align.center(frame))"""

stream = re.sub(r"                # 3\.5 Absurd Animation.*?console\.print\(Align\.center\(frame\)\)", anim_code, stream, flags=re.DOTALL)

with open("commercial_stream.py", "w") as f:
    f.write(stream)
print("Tug of war animation updated!")
