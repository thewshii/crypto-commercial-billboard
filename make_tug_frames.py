def f(lines):
    # lines is a list of 3 strings (top, mid, bot)
    # each line should be 40 chars total.
    res = []
    for line in lines:
        res.append(line.ljust(40))
    return "\\n".join(res)

frames = [
    # 0: Center
    f([
        "              O   [|]   O",
        "             /|\\==[|]==/|\\",
        "             / \\  [|]  /_\\"
    ]),
    # 1: Pull Left 1
    f([
        "            O     [|] O",
        "           /|\\====[|]/|\\",
        "           < \\    [|]/>"
    ]),
    # 2: Pull Left 2
    f([
        "          O       [|]O",
        "         /|\\======[|]|\\",
        "         < \\      [|]>"
    ]),
    # 3: Pull Left 1 (returning)
    f([
        "            O     [|] O",
        "           /|\\====[|]/|\\",
        "           < \\    [|]/>"
    ]),
    # 4: Center
    f([
        "              O   [|]   O",
        "             /|\\==[|]==/|\\",
        "             / \\  [|]  /_\\"
    ]),
    # 5: Pull Right 1
    f([
        "                O [|]     O",
        "              /|\\[|]====/|\\",
        "              <\\ [|]    />"
    ]),
    # 6: Pull Right 2
    f([
        "                 O[|]       O",
        "                /|[|]======/|\\",
        "                <[|]      />"
    ]),
    # 7: Pull Right 1 (returning)
    f([
        "                O [|]     O",
        "              /|\\[|]====/|\\",
        "              <\\ [|]    />"
    ]),
]

for frame in frames:
    print(frame)
    print("-" * 40)
