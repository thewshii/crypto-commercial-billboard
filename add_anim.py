import re

with open("commercial_stream.py", "r") as f:
    stream = f.read()

anim_code = """                # 3. Dynamic Scrolling Marquee
                marquee = self.render_marquee_bar(width=term_w)
                console.print(marquee)

                # 3.5 Absurd Animation (Guy and Girl at locked door)
                anim_frames = [
                    "[bold yellow]  O    O   [|]\\n /|\\\\  /|\\\\  [|]\\n / \\\\  / \\\\  [|][/bold yellow]",
                    "[bold yellow]  O   \\\\O/  [|]\\n /|\\\\   |===[|]\\n / \\\\  / \\\\  [|][/bold yellow]",
                    "[bold yellow] \\\\O/  \\\\O/  [|]\\n  |====|===[|]\\n / \\\\  / \\\\  [|][/bold yellow]",
                    "[bold yellow] _O_  _O_  [|]\\n  |    |   [|]\\n / \\\\  / \\\\  [|][/bold yellow]"
                ]
                from rich.align import Align
                frame = anim_frames[int(time.time() * 4) % len(anim_frames)]
                console.print(Align.center(frame))"""

stream = stream.replace("""                # 3. Dynamic Scrolling Marquee
                marquee = self.render_marquee_bar(width=term_w)
                console.print(marquee)""", anim_code)

with open("commercial_stream.py", "w") as f:
    f.write(stream)
print("Animation injected!")
