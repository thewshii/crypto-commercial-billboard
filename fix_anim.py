import re

with open("commercial_stream.py", "r") as f:
    content = f.read()

# Fix any literal newlines inside string literals in the animation
import ast
try:
    ast.parse(content)
except SyntaxError as e:
    print(f"Error: {e}")

# Just manually fix lines 642 onwards by replacing the literal newlines inside quotes.
# Actually, let's just replace the whole anim_frames array safely.

new_anim = '''                anim_frames = [
                    "[yellow]         O     [|]     O        \\n        /|\\\\    [|]    /|\\\\       \\n        / \\\\    [|]    / \\\\       [/yellow]",
                    "[yellow]          O    [|]    O         \\n         /|\\\\===[|]===/|\\\\        \\n         < \\\\   [|]   />         [/yellow]",
                    "[yellow]           O   (()   O          \\n          /|\\\\==(()==/|\\\\         \\n          <<   (()   >>         [/yellow]",
                    "[yellow]           O   {*}   O          \\n          /|\\\\=={*}==/|\\\\         \\n          <<   {*}   >>         [/yellow]",
                    "[yellow]               { } O   O        \\n               { }/|\\\\ /|\\\\       \\n               { }/ \\\\ / \\\\       [/yellow]",
                    "[yellow]               { } !   !        \\n               { } O   O        \\n               { }/|\\\\ /|\\\\       \\n               { }/ \\\\ / \\\\       [/yellow]",
                    "[yellow]       O       { }       O      \\n      /|\\\\      { }      /|\\\\     \\n      / \\\\      { }      / \\\\     [/yellow]",
                    "[yellow] O             { }             O\\n/|\\\\            { }            /|\\\\ \\n/ \\\\            { }            / \\\\ [/yellow]",
                    "[yellow]\\\\\\\\             { }             //\\n \\\\\\\\            { }            // \\n  O            { }            O  [/yellow]",
                    "[yellow]               { }              \\n               { }              \\n               { }              [/yellow]"
                ]'''

# Let's use regex to find the anim_frames = [ ... ] and replace it
content = re.sub(r'                anim_frames = \[\n.*?(?=\n                \])\n                \]', new_anim, content, flags=re.DOTALL)

with open("commercial_stream.py", "w") as f:
    f.write(content)

