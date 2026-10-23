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
* `--ar-video: #ffee55` — MJPEG chroma-bleed compensation & high-acuity vector stroke.
* `--hazard: #ff003c` — High-G physical drop impact or ACK packet loss only. Strictly reserved; never decorative.
* `--ar-bg: #0b0902` — Deep obsidian backdrop (90%+ unlit subpixels for AMOLED mobile power savings).
* `--ar-panel: rgba(18, 14, 3, 0.92)` — Semi-transparent dark gold/obsidian panels.

### 2. The Obsidian Split (Raster vs. DOM)
* **Raster / Video Pipeline (`PIL` / Canvas)**: MUST use `#000000` / `(0, 0, 0)` for under-strokes (3–4px width). In MJPEG (YUV 4:2:0 subsampling), yellow chroma is quarter-resolution and smears; maximum luminance contrast against the black backing is what preserves symbology legibility.
* **DOM / CSS UI Layer**: MUST use `#0b0902` / `rgba(18, 14, 3, 0.92)` for warm obsidian aesthetic and AMOLED subpixel power saving.
* **CSS Typography Invariant**: All floating pills and labels must include crisp obsidian stroke shadowing:
  `text-shadow: 0 0 3px #0b0902, -1px -1px 0 #0b0902, 1px -1px 0 #0b0902, -1px 1px 0 #0b0902, 1px 1px 0 #0b0902;`

### 3. Anti-Flicker Asymmetric ACK State Switching (Hysteresis Rule)
Hard thresholds at 150 μs and 500 μs will strobe if jitter hovers near the boundary:
* **Promote to Fresh instantly** when latency is ≤150 μs.
* **Demote to Aging / Stale only after 3 consecutive samples** (sustained ~150ms hold).
* Never switch temporal warning colors on a single borderline packet.

### 4. Lane Decoupling & Mobile Performance
* **Lane Split**: Keep video/canvas spatial geometry running at 15–30 FPS. Throttle DOM coordinate text updates and multi-part text-shadow elements to ~10 Hz (100–150 ms) to eliminate unnecessary mobile GPU layout repaints.
* Avoid heavy multi-layer `box-shadow` halos or `filter: blur()` effects on 15–30 FPS mobile video loops.
* Maintain low vector pixel fill (5–10%) over obsidian backdrops to preserve battery and subpixel lifespan.
