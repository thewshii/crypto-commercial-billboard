import json
import os
import shutil
import subprocess
import time
import urllib.parse
import urllib.request
from flask import Flask, render_template, send_from_directory, request, jsonify, redirect

app = Flask(__name__)

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/sounds/<path:filename>")
def get_sound(filename):
    return send_from_directory("sounds", filename)

@app.route("/static/<path:filename>")
def get_static(filename):
    return send_from_directory("static", filename)

@app.route("/api/generate-image", methods=["POST"])
def generate_image():
    fal_key = os.environ.get("FAL_KEY", "fal_sk_af08e82663704fb486f8b1b30982eea0:b8a65b3ec856e8a0b00ae9fdf9085f21")
    data = request.json or {}
    prompt = data.get("prompt", "mysterious man in black agent in dark suit, cinematic noir")
    try:
        req = urllib.request.Request(
            "https://fal.run/fal-ai/flux/schnell",
            data=json.dumps({
                "prompt": prompt,
                "image_size": "square_hd",
                "num_inference_steps": 4
            }).encode("utf-8"),
            headers={
                "Authorization": f"Key {fal_key}",
                "Content-Type": "application/json",
                "User-Agent": "Mozilla/5.0"
            }
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            result = json.loads(resp.read().decode())
            image_url = result["images"][0]["url"]
            return jsonify({"status": "ok", "url": image_url})
    except Exception as e:
        return jsonify({"status": "error", "error": str(e)}), 500

@app.route("/api/klines")
def get_klines():
    """Proxy 1m BTC candles from Coinbase (unrestricted globally) with failover to Binance."""
    # 1. Primary: Coinbase Exchange (100% US/global friendly, CORS compatible)
    try:
        req = urllib.request.Request(
            "https://api.exchange.coinbase.com/products/BTC-USD/candles?granularity=60",
            headers={"User-Agent": "Mozilla/5.0"}
        )
        with urllib.request.urlopen(req, timeout=4) as resp:
            data = json.loads(resp.read().decode())
            if isinstance(data, list) and len(data) > 0:
                # Coinbase returns: [time, low, high, open, close, volume]
                candles = [
                    {
                        "time": int(k[0]) * 1000,
                        "open": float(k[3]),
                        "high": float(k[2]),
                        "low": float(k[1]),
                        "close": float(k[4])
                    }
                    for k in reversed(data[:40])
                ]
                return jsonify({"status": "ok", "candles": candles, "source": "coinbase"})
    except Exception as e:
        print(f"[KLINES] Coinbase fetch failed: {e}", flush=True)

    # 2. Secondary: Binance Spot klines
    try:
        req = urllib.request.Request(
            "https://api.binance.com/api/v3/klines?symbol=BTCUSDT&interval=1m&limit=40",
            headers={"User-Agent": "Mozilla/5.0"}
        )
        with urllib.request.urlopen(req, timeout=4) as resp:
            data = json.loads(resp.read().decode())
            if isinstance(data, list) and len(data) > 0:
                candles = [
                    {
                        "time": int(k[0]),
                        "open": float(k[1]),
                        "high": float(k[2]),
                        "low": float(k[3]),
                        "close": float(k[4])
                    }
                    for k in data
                ]
                return jsonify({"status": "ok", "candles": candles, "source": "binance"})
    except Exception as e:
        print(f"[KLINES] Binance fetch failed: {e}", flush=True)

    return jsonify({"status": "error", "candles": []}), 500

@app.route("/api/speak", methods=["POST"])
def speak():
    data = request.json or {}
    text = data.get("text", "")
    if text and shutil.which("termux-tts-speak"):
        try:
            subprocess.run(["termux-tts-speak", text], timeout=25)
        except subprocess.TimeoutExpired:
            print("[WARNING] TTS timed out after 25 seconds.", flush=True)
        except Exception as e:
            print(f"[WARNING] TTS failed: {e}", flush=True)
    return {"status": "ok"}

@app.route("/api/track", methods=["POST"])
def track():
    data = request.json or {}
    print(f"[TRACKING] Affiliate link clicked: {data.get('url')}", flush=True)
    return {"status": "ok"}

@app.route("/moon")
@app.route("/moondev")
def moon_redirect():
    """Vanity redirect that routes visitors directly to Moon Dev affiliate tracking link."""
    target_url = "https://moondev.com/t/wshii"
    print(f"[REDIRECT] Routing visitor to Moon Dev affiliate tracker: {target_url}", flush=True)
    return redirect(target_url, code=302)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port, debug=False)
