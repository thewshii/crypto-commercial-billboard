with open("commercial_stream.py", "r") as f:
    c = f.read()

import re
# find broken Text.from_markup(" \n\n[bold white]...[/bold white]") and fix it
c = re.sub(r'body = Group\(banner_render, Text\.from_markup\("\n\n\[bold white\](.*?)\[/bold white\]"\)\)',
           r'body = Group(banner_render, Text.from_markup("\\n\\n[bold white]\1[/bold white]"))', c)

with open("commercial_stream.py", "w") as f:
    f.write(c)
