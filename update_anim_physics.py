import re

with open("commercial_stream.py", "r") as f:
    stream = f.read()

anim_code = """                # 3.5 Absurd Animation (Guy and Girl at locked door)
                anim_frames = [
                    "[yellow]          O    O   [|]                  \\n         /|\\\\  /|\\\\  [|]                  \\n         / \\\\  /_\\\\  [|]                  [/yellow]",
                    "[yellow]          O   \\\\O/  [|]                  \\n         /|\\\\   |===[|]                  \\n         / \\\\  /_\\\\  [|]                  [/yellow]",
                    "[yellow]         \\\\O/  \\\\O/  [|]                  \\n          |====|===[|]                  \\n         / \\\\  /_\\\\  [|]                  [/yellow]",
                    "[yellow]         _O_  _O_  [|]                  \\n          |    |   [|]                  \\n         / \\\\  /_\\\\  [|]                  [/yellow]",
                    "[yellow]      O        O   [|]                  \\n     /|\\\\      /|\\\\  [|]                  \\n     < \\\\      /_\\\\  [|]                  [/yellow]",
                    "[yellow]  O            O   [|]                  \\n /|\\\\          /|\\\\  [|]                  \\n < \\\\          /_\\\\  [|]                  [/yellow]",
                    "[yellow]           O   O   [|]                  \\n         >>|/ /|\\\\  [|]                  \\n          />  /_\\\\  [|]                  [/yellow]",
                    "[yellow]               O   [|] O                \\n             ~~|/  [|]/|~~              \\n              /_\\\\  [|]/>                [/yellow]",
                    "[yellow]               O   [|]   O              \\n              /|\\\\  [|]  /|\\\\             \\n              /_\\\\  [|]  / \\\\             [/yellow]",
                    "[yellow]              !O!  [|]  !O!             \\n              \\\\ /  [|]  \\\\ /             \\n              /_\\\\  [|]  / \\\\             [/yellow]",
                    "[yellow]              !O!  [|]  !O!             \\n              \\\\ /  [|]  \\\\ /             \\n              /_\\\\  [|]  / \\\\             [/yellow]",
                    "[yellow]               O   [|]   O              \\n              /|\\\\  [|]  /|\\\\             \\n              /_\\\\  [|]  / \\\\             [/yellow]",
                    "[yellow]           O       [|]       O          \\n          /|\\\\      [|]      /|\\\\         \\n          /_\\\\      [|]      / \\\\         [/yellow]",
                    "[yellow]      \\\\O/          [|]          \\\\O/     \\n       |           [|]           |      \\n      / \\\\          [|]          / \\\\     [/yellow]",
                    "[yellow]   _O_             [|]             _O_  \\n    |              [|]              |   \\n   / \\\\             [|]             / \\\\  [/yellow]",
                    "[yellow]                   [|]                  \\n                   [|]                  \\n                   [|]                  [/yellow]",
                    "[yellow]                   [|]                  \\n                   [|]                  \\n                   [|]                  [/yellow]"
                ]
                from rich.align import Align
                # Play at ~3.5 frames per second
                frame = anim_frames[int(time.time() * 3.5) % len(anim_frames)]
                console.print(Align.center(frame))"""

# find and replace the old block
# old block starts at "# 3.5 Absurd Animation" and ends at "console.print(Align.center(frame))"
stream = re.sub(r"                # 3\.5 Absurd Animation.*?console\.print\(Align\.center\(frame\)\)\n", anim_code + "\n", stream, flags=re.DOTALL)

with open("commercial_stream.py", "w") as f:
    f.write(stream)
print("Animation updated to break physics!")
