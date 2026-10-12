import re

with open("ui.py", "r") as f:
    content = f.read()

new_func = """def get_safe_figlet(text: str, font: str = TERMINAL_FONT) -> str:
    import config
    if getattr(config, 'USE_PIXEL_BANNERS', False):
        try:
            import pixelart
            lines = pixelart.render_text(text, px_height=48)
            return "\\n".join(lines)
        except Exception:
            pass
    
    cols = shutil.get_terminal_size().columns
    try:
        rendered = pyfiglet.figlet_format(text, font=font).rstrip()
        lines = rendered.splitlines()
        max_len = max(len(l) for l in lines) if lines else 0
        if max_len > cols - 4:
            rendered = pyfiglet.figlet_format(text, font="term").rstrip()
        return rendered
    except Exception:
        return text"""

content = re.sub(
    r'def get_safe_figlet\(text: str, font: str = TERMINAL_FONT\) -> str:.*?return text',
    new_func,
    content,
    flags=re.DOTALL
)

with open("ui.py", "w") as f:
    f.write(content)
