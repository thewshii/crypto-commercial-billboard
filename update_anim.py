import re

with open("commercial_stream.py", "r") as f:
    stream = f.read()

anim_code = """                # 3.5 Absurd Animation (Guy and Girl at locked door)
                anim_frames = [
                    "[bold yellow]  O    O   [|]\\n /|\\\\  /|\\\\  [|]\\n / \\\\  /_\\\\  [|][/bold yellow]",
                    "[bold yellow]  O   \\\\O/  [|]\\n /|\\\\   |===[|]\\n / \\\\  /_\\\\  [|][/bold yellow]",
                    "[bold yellow] \\\\O/  \\\\O/  [|]\\n  |====|===[|]\\n / \\\\  /_\\\\  [|][/bold yellow]",
                    "[bold yellow] _O_  _O_  [|]\\n  |    |   [|]\\n / \\\\  /_\\\\  [|][/bold yellow]"
                ]
                from rich.align import Align
                frame = anim_frames[int(time.time() * 4) % len(anim_frames)]
                console.print(Align.center(frame))"""

stream = re.sub(r"                # 3\.5 Absurd Animation.*?console\.print\(Align\.center\(frame\)\)", anim_code, stream, flags=re.DOTALL)

with open("commercial_stream.py", "w") as f:
    f.write(stream)
print("Animation updated with dress!")
