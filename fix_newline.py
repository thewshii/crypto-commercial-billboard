with open("commercial_stream.py", "r") as f:
    c = f.read()
c = c.replace('fig = "\n".join(lines)', 'fig = "\\n".join(lines)')
with open("commercial_stream.py", "w") as f:
    f.write(c)
