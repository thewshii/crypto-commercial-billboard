door = "[|]"

def f(lines):
    # lines is a list of 3 strings (top, mid, bot)
    # each line should be 40 chars total.
    res = []
    for line in lines:
        res.append(line.ljust(40))
    return "\\n".join(res)

frames = [
    # 0: Pulling
    f([
        "          O    O   [|]",
        "         /|\\  /|\\  [|]",
        "         / \\  /_\\  [|]"
    ]),
    # 1: Pulling harder
    f([
        "          O   \\O/  [|]",
        "         /|\\   |===[|]",
        "         / \\  /_\\  [|]"
    ]),
    # 2: Both pulling
    f([
        "         \\O/  \\O/  [|]",
        "          |====|===[|]",
        "         / \\  /_\\  [|]"
    ]),
    # 3: Falling back
    f([
        "         _O_  _O_  [|]",
        "          |    |   [|]",
        "         / \\  /_\\  [|]"
    ]),
    # 4: Guy runs backward
    f([
        "      O        O   [|]",
        "     /|\\      /|\\  [|]",
        "     < \\      /_\\  [|]"
    ]),
    # 5: Guy runs backward more
    f([
        "  O            O   [|]",
        " /|\\          /|\\  [|]",
        " < \\          /_\\  [|]"
    ]),
    # 6: Guy runs at door
    f([
        "           O   O   [|]",
        "         >>|/ /|\\  [|]",
        "          />  /_\\  [|]"
    ]),
    # 7: Guy phases through
    f([
        "               O   [|] O",
        "             ~~|/  [|]/|~~",
        "              /_\\  [|]/>"
    ]),
    # 8: Guy successfully on other side
    f([
        "               O   [|]   O",
        "              /|\\  [|]  /|\\",
        "              /_\\  [|]  / \\"
    ]),
    # 9: Mind blown!
    f([
        "              !O!  [|]  !O!",
        "              \\ /  [|]  \\ /",
        "              /_\\  [|]  / \\"
    ]),
    # 10: Still mind blown
    f([
        "              !O!  [|]  !O!",
        "              \\ /  [|]  \\ /",
        "              /_\\  [|]  / \\"
    ]),
    # 11: Turn around
    f([
        "               O   [|]   O",
        "              /|\\  [|]  /|\\",
        "              /_\\  [|]  / \\"
    ]),
    # 12: Run away
    f([
        "           O       [|]       O",
        "          /|\\      [|]      /|\\",
        "          /_\\      [|]      / \\"
    ]),
    # 13: Jump off edge
    f([
        "      \\O/          [|]          \\O/",
        "       |           [|]           |",
        "      / \\          [|]          / \\"
    ]),
    # 14: Mid air
    f([
        "   _O_             [|]             _O_",
        "    |              [|]              |",
        "   / \\             [|]             / \\"
    ]),
    # 15: Gone
    f([
        "                   [|]",
        "                   [|]",
        "                   [|]"
    ]),
    # 16: Gone
    f([
        "                   [|]",
        "                   [|]",
        "                   [|]"
    ]),
]

for frame in frames:
    print(frame)
    print("-" * 40)
