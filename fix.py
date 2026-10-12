with open("commercial_stream.py", "r") as f:
    lines = f.readlines()

out = []
skip = False
for line in lines:
    if "anim_frames = [" in line and "# 3.5" not in line:
        out.append(line)
        skip = True
        
        new_anim = """                    "[yellow]         O     [|]     O        \\n        /|\\\\    [|]    /|\\\\       \\n        / \\\\    [|]    / \\\\       [/yellow]",
                    "[yellow]          O    [|]    O         \\n         /|\\\\===[|]===/|\\\\        \\n         < \\\\   [|]   />         [/yellow]",
                    "[yellow]           O   (()   O          \\n          /|\\\\==(()==/|\\\\         \\n          <<   (()   >>         [/yellow]",
                    "[yellow]           O   {*}   O          \\n          /|\\\\=={*}==/|\\\\         \\n          <<   {*}   >>         [/yellow]",
                    "[yellow]               { } O   O        \\n               { }/|\\\\ /|\\\\       \\n               { }/ \\\\ / \\\\       [/yellow]",
                    "[yellow]               { } !   !        \\n               { } O   O        \\n               { }/|\\\\ /|\\\\       \\n               { }/ \\\\ / \\\\       [/yellow]",
                    "[yellow]       O       { }       O      \\n      /|\\\\      { }      /|\\\\     \\n      / \\\\      { }      / \\\\     [/yellow]",
                    "[yellow] O             { }             O\\n/|\\\\            { }            /|\\\\ \\n/ \\\\            { }            / \\\\ [/yellow]",
                    "[yellow]\\\\\\\\             { }             //\\n \\\\\\\\            { }            // \\n  O            { }            O  [/yellow]",
                    "[yellow]               { }              \\n               { }              \\n               { }              [/yellow]"
                ]
"""
        out.append(new_anim)
        continue
        
    if skip:
        if "]" in line and "anim_frames" not in line and line.strip() == "]":
            skip = False
        continue
        
    out.append(line)

with open("commercial_stream.py", "w") as f:
    f.writelines(out)
