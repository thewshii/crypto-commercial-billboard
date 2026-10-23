# Coding Agent Instructions: Cyber Yellow AR Scheme & Spatial Telemetry

## Rule 234: Visual Presentation, Optical Acuity & Mobile Interface Directive

All coding agents operating on this codebase must strictly enforce and apply the **Cyber Yellow AR Color Scheme** to all augmented reality rendering pipelines, interface overlays, and visual data presentations within the mobile interface (`templates/mobile_ar.html`) and terminal spatial overlays (`templates/index.html`).

### 1. Pre-Attentive Namespace & Color Standard
Color serves first as an unambiguous subsystem namespace before numbers are read:
* `--matrix: #00ff66` — In-Game Matrix Inventory Loop (Rule 232).
* `--rdp: #00e5ff` — Remote Desktop Protocol screen sync and host tools (Rule 231).
* `--ar-primary: #ffdd00` — Live spatial telemetry and fresh 802.11 Wi-Fi ACK stream (<150 μs).
* `--ar-bright: #ffea00` — Active/locked reticle states and highlight readouts only.
* `--ar-dim: #ffaa00` — Advisory horizon ladders, secondary metrics, and aging telemetry (150–500 μs).
* `--ar-stale: #886600` — Aged/stale packets (>500 μs).
* `--hazard: #ff003c` — High-G physical drop impact or ACK packet loss only. Strictly reserved; never decorative.
* `--ar-bg: #0b0902` — Deep obsidian backdrop (90%+ unlit subpixels for AMOLED mobile power savings).
* `--ar-panel: rgba(18, 14, 3, 0.92)` — Semi-transparent dark gold/obsidian panels.

### 2. The Obsidian Stroke Rule (Bright Background Protection)
When 3D reticles, horizon ladders, or vector labels are composited directly over pass-through camera video or bright environments (white walls, sunlit concrete, blown-out sky), `#ffdd00` without backing drops to ~1.4:1 contrast.
* **Canvas / PIL Rendering Invariant**: Every reticle circle, line, and horizon ladder MUST carry a crisp 1.5–2px obsidian under-stroke (`fill=(0,0,0)` / `ctx.strokeStyle="#000000"`, 2–4px width) before drawing the yellow stroke. Text labels must carry 1px black outline offsets.
* **CSS Typography Invariant**: All floating pills and labels must include crisp obsidian stroke shadowing:
  `text-shadow: 0 0 3px #0b0902, -1px -1px 0 #0b0902, 1px -1px 0 #0b0902, -1px 1px 0 #0b0902, 1px 1px 0 #0b0902;`

### 3. Mobile Performance & Low Overhead
* Avoid heavy multi-layer `box-shadow` halos or `filter: blur()` effects on 15–30 FPS mobile video loops to eliminate frame repaints.
* Use crisp single-stroke layers and hardware-accelerated `transform` / `opacity`.
* Maintain low vector pixel fill (5–10%) over obsidian backdrops to preserve battery and subpixel lifespan.
