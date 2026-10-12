import pyfiglet
from rich.console import Console
from rich.align import Align
from rich.panel import Panel

console = Console()
text = pyfiglet.figlet_format("LARGE TEXT", font="standard")
console.print(Align.center(f"[bold cyan]{text}[/bold cyan]\n[bold yellow]THIS IS A SHORT SUBHEADING[/bold yellow]\n\n[bold white]Even shorter text here.[/bold white]"))
