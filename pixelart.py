import os
import sys
import time

try:
    from PIL import Image, ImageDraw, ImageFont
    HAS_PILLOW = True
except ImportError:
    HAS_PILLOW = False

def _get_font(size):
    try:
        return ImageFont.truetype("DejaVuSans.ttf", size)
    except Exception:
        try:
            return ImageFont.truetype("/system/fonts/Roboto-Regular.ttf", size)
        except Exception:
            try:
                return ImageFont.load_default(size=size)
            except Exception:
                return ImageFont.load_default()

def _render_img(img, fg):
    w, h = img.width, img.height
    lines = []
    for y in range(0, h, 2):
        line_parts = []
        for x in range(w):
            t_val = img.getpixel((x, y)) if y < h else 0
            b_val = img.getpixel((x, y+1)) if y+1 < h else 0
            
            def get_c(v):
                if v > 170: return fg
                elif v < 85: return (0, 0, 0)
                else: return (fg[0]//2, fg[1]//2, fg[2]//2)
            
            tr, tg, tb = get_c(t_val)
            br, bg, bb = get_c(b_val)
            
            line_parts.append(f"\x1b[38;2;{tr};{tg};{tb}m\x1b[48;2;{br};{bg};{bb}m▀")
        lines.append("".join(line_parts) + "\x1b[0m")
    return lines

def render_text(text, px_height=48, fg=(0, 255, 136)):
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
        return [text]

def animate(frames, fps=12):
    if not frames: return
    try:
        sys.stdout.write("\x1b[?25l") # hide cursor
        sys.stdout.flush()
        
        for frame in frames:
            sys.stdout.write("\x1b[H") # cursor home
            for line in frame:
                sys.stdout.write(line + "\n")
            sys.stdout.flush()
            time.sleep(1.0 / fps)
    finally:
        sys.stdout.write("\x1b[?25h") # show cursor
        sys.stdout.flush()

def logo_reveal(text="PUMP ML"):
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
        pass

def buy_flash():
    pass

def profit_flash():
    pass


def buy_flash(text="BUY"):
    if not HAS_PILLOW: return
    try:
        f1 = render_text(text, px_height=48, fg=(255, 255, 255))
        f2 = render_text(text, px_height=48, fg=(0, 255, 136))
        animate([f1, f2], fps=4)
    except:
        pass

def profit_flash(text="PROFIT"):
    if not HAS_PILLOW: return
    try:
        f1 = render_text(text, px_height=48, fg=(255, 255, 255))
        f2 = render_text(text, px_height=48, fg=(255, 215, 0))
        animate([f1, f2], fps=4)
    except:
        pass
