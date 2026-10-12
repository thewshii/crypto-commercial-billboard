from rich.console import Console
from rich.panel import Panel
from rich.align import Align
import pixelart

console = Console()
banner = "\n".join(pixelart.render_text("WARNING", px_height=20, fg=(255, 50, 50)))
body = f"{banner}\n\n[bold yellow]This is a test.[/bold yellow]"

console.print(Panel(Align.center(body), title="Test"))
