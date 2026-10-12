import pixelart
for size in [24, 48, 96]:
    print(f"=== {size}px ===")
    lines = pixelart.render_text("PUMP ML", px_height=size)
    print("\n".join(lines))
print("=== LOGO REVEAL ===")
pixelart.logo_reveal("PUMP ML")
