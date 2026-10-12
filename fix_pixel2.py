import re

with open("pixelart.py", "r") as f:
    content = f.read()

new_logo_reveal = """def logo_reveal(text="PUMP ML"):
    if not HAS_PILLOW: return
    try:
        import shutil
        cols = shutil.get_terminal_size((80, 24)).columns
        px_height = 48
        font = _get_font(px_height)
        try:
            left, top, right, bottom = font.getbbox(text)
            w, h = right - left, px_height
        except AttributeError:
            w, h = font.getsize(text)
            h = px_height
            
        if w == 0: w = 10
        
        frames = []
        for i in range(6):
            fraction = (i + 1) / 6.0
            offset_x = int(w * (fraction - 1))
            img = Image.new("L", (w, h), 0)
            draw = ImageDraw.Draw(img)
            draw.text((offset_x, 0), text, fill=255, font=font)
            if w > cols:
                new_w = cols - 2
                new_h = int(h * (new_w / w))
                if new_h % 2 != 0: new_h += 1
                img = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
            frames.append(_render_img(img, (0, 255, 136)))
            
        for color in [(0, 180, 100), (0, 255, 136), (0, 180, 100)]:
            img = Image.new("L", (w, h), 0)
            draw = ImageDraw.Draw(img)
            draw.text((0, 0), text, fill=255, font=font)
            if w > cols:
                new_w = cols - 2
                new_h = int(h * (new_w / w))
                if new_h % 2 != 0: new_h += 1
                img = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
            frames.append(_render_img(img, color))
            
        max_lines = max(len(f) for f in frames)
        for i in range(len(frames)):
            while len(frames[i]) < max_lines: frames[i].append("")
        animate(frames, fps=12)
    except Exception:
        pass"""

content = re.sub(
    r'def logo_reveal\(text="PUMP ML"\):.*?except Exception:\n        pass',
    new_logo_reveal,
    content,
    flags=re.DOTALL
)

with open("pixelart.py", "w") as f:
    f.write(content)
