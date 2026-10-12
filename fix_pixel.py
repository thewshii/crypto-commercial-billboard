import re

with open("pixelart.py", "r") as f:
    content = f.read()

# I will replace the text drawing logic in render_text and logo_reveal to include resize

new_render_text = """def render_text(text, px_height=48, fg=(0, 255, 136)):
    if not HAS_PILLOW:
        return [text]
    try:
        import shutil
        cols = shutil.get_terminal_size((80, 24)).columns
        
        font = _get_font(px_height)
        try:
            left, top, right, bottom = font.getbbox(text)
            w, h = right - left, px_height
        except AttributeError:
            w, h = font.getsize(text)
            h = px_height
            
        if w == 0: w = 10
            
        img = Image.new("L", (w, h), 0)
        draw = ImageDraw.Draw(img)
        draw.text((0, 0), text, fill=255, font=font)
        
        if w > cols:
            new_w = cols - 2
            new_h = int(h * (new_w / w))
            if new_h % 2 != 0: new_h += 1
            img = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
            
        return _render_img(img, fg)
    except Exception:
        return [text]"""

content = re.sub(
    r'def render_text\(text, px_height=48, fg=\(0, 255, 136\)\):.*?except Exception:\n        return \[text\]',
    new_render_text,
    content,
    flags=re.DOTALL
)

with open("pixelart.py", "w") as f:
    f.write(content)
