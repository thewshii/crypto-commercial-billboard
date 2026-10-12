from rich.console import Console
from rich.align import Align
import time

console = Console()

anim_frames = [
    "[yellow]         O     [|]     O        \n        /|\\    [|]    /|\\       \n        / \\    [|]    / \\       [/yellow]",
    "[yellow]          O    [|]    O         \n         /|\\===[|]===/|\\        \n         < \\   [|]   />         [/yellow]",
    "[yellow]           O   (()   O          \n          /|\\==(()==/|\\         \n          <<   (()   >>         [/yellow]",
    "[yellow]           O   {*}   O          \n          /|\\=={*}==/|\\         \n          <<   {*}   >>         [/yellow]",
    "[yellow]               { } O   O        \n               { }/|\\ /|\\       \n               { }/ \\ / \\       [/yellow]",
    "[yellow]               { } !   !        \n               { } O   O        \n               { }/|\\ /|\\       \n               { }/ \\ / \\       [/yellow]",
    "[yellow]       O       { }       O      \n      /|\\      { }      /|\\     \n      / \\      { }      / \\     [/yellow]",
    "[yellow] O             { }             O\n/|\\            { }            /|\\ \n/ \\            { }            / \\ [/yellow]",
    "[yellow]\\\\             { }             //\n \\\\            { }            // \n  O            { }            O  [/yellow]",
    "[yellow]               { }              \n               { }              \n               { }              [/yellow]"
]

for frame in anim_frames:
    console.clear()
    console.print(Align.center(frame))
    time.sleep(0.5)
