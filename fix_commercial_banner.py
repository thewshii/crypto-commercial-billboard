import re

with open("commercial_stream.py", "r") as f:
    content = f.read()

new_banner = """    def render_slide_banner(self, text: str, color: str = "bold yellow", font: str = "standard") -> str:
        clean = text.replace("\\n", " ").strip().upper()
        
        # Color mapping
        rgb = (255, 255, 50) # default yellow
        if "red" in color: rgb = (255, 50, 50)
        elif "cyan" in color: rgb = (50, 255, 255)
        elif "green" in color: rgb = (50, 255, 50)
        elif "magenta" in color: rgb = (255, 50, 255)
        
        try:
            import pixelart
            # 20px height takes 10 terminal lines. Large enough to read, compact enough to fit things.
            lines = pixelart.render_text(clean, px_height=20, fg=rgb)
            fig = "\\n".join(lines)
            return fig
        except Exception:
            try:
                fig = pyfiglet.figlet_format(clean, font=font)
                return f"[{color}]{fig}[/{color}]"
            except:
                return clean"""

content = re.sub(
    r'    def render_slide_banner\(self, text: str, color: str = "bold yellow", font: str = "standard"\) -> str:.*?return f"\[bold \{bg_style\}\]\{fig\}\[/bold \{bg_style\}\]"""',
    new_banner,
    content,
    flags=re.DOTALL
)

with open("commercial_stream.py", "w") as f:
    f.write(content)

