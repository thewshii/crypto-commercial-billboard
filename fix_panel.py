import re

with open("commercial_stream.py", "r") as f:
    content = f.read()

# Replace Panel(Align.center(body), \n            body,
content = re.sub(
    r'Panel\(Align\.center\(body\),\s*body,',
    r'Panel(Align.center(body),',
    content
)

with open("commercial_stream.py", "w") as f:
    f.write(content)
