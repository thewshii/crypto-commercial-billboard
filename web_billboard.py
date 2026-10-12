import json
import os
import re
import shutil
import subprocess
import time
import urllib.parse
import urllib.request
from flask import Flask, render_template, send_from_directory, request, jsonify, redirect

def _load_env():
    """Load variables from .env file into os.environ if available."""
    try:
        from dotenv import load_dotenv
        load_dotenv()
        return
    except ImportError:
        pass

    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    if os.path.exists(env_path):
        try:
            with open(env_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    k, v = line.split("=", 1)
                    k = k.strip()
                    v = v.strip().strip("'\"")
                    if k and k not in os.environ:
                        os.environ[k] = v
        except Exception:
            pass

_load_env()

# Amazon Bedrock client & model setup
try:
    import boto3
except ImportError:
    boto3 = None

AWS_ACCESS_KEY_ID = os.environ.get("AWS_ACCESS_KEY_ID", "")
AWS_SECRET_ACCESS_KEY = os.environ.get("AWS_SECRET_ACCESS_KEY", "")
AWS_DEFAULT_REGION = os.environ.get("AWS_DEFAULT_REGION", "us-east-1")
BEDROCK_HAIKU_MODEL = os.environ.get("BEDROCK_HAIKU_MODEL", "us.anthropic.claude-haiku-4-5-20251001-v1:0")

_bedrock_client = None

def get_bedrock_client():
    global _bedrock_client
    if _bedrock_client is not None:
        return _bedrock_client
    if boto3 is None:
        return None
    try:
        kwargs = {"region_name": AWS_DEFAULT_REGION}
        if AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY:
            kwargs["aws_access_key_id"] = AWS_ACCESS_KEY_ID
            kwargs["aws_secret_access_key"] = AWS_SECRET_ACCESS_KEY
        _bedrock_client = boto3.client("bedrock-runtime", **kwargs)
        return _bedrock_client
    except Exception as e:
        print(f"[BEDROCK] Failed to init client: {e}", flush=True)
        return None

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

def fetch_recent_candles(limit=40):
    """Proxy 1m BTC candles from Coinbase (unrestricted globally) with failover to Binance."""
    # 1. Primary: Coinbase Exchange (100% US/global friendly, CORS compatible)
    try:
        req = urllib.request.Request(
            f"https://api.exchange.coinbase.com/products/BTC-USD/candles?granularity=60",
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
                    for k in reversed(data[:limit])
                ]
                return candles
    except Exception as e:
        print(f"[KLINES] Coinbase fetch failed: {e}", flush=True)

    # 2. Secondary: Binance Spot klines
    try:
        req = urllib.request.Request(
            f"https://api.binance.com/api/v3/klines?symbol=BTCUSDT&interval=1m&limit={limit}",
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
                return candles
    except Exception as e:
        print(f"[KLINES] Binance fetch failed: {e}", flush=True)

    return []

def calculate_rsi(candles, period=14):
    """Wilder's smoothed RSI calculation over candle closes."""
    if len(candles) < period + 1:
        return 50.0
    closes = [c["close"] for c in candles]
    gains = []
    losses = []
    for i in range(1, period + 1):
        diff = closes[i] - closes[i - 1]
        gains.append(max(0, diff))
        losses.append(max(0, -diff))
    avg_gain = sum(gains) / period
    avg_loss = sum(losses) / period
    for i in range(period + 1, len(closes)):
        diff = closes[i] - closes[i - 1]
        g = max(0, diff)
        l = max(0, -diff)
        avg_gain = (avg_gain * (period - 1) + g) / period
        avg_loss = (avg_loss * (period - 1) + l) / period
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return round(100.0 - (100.0 / (1.0 + rs)), 1)

def compute_35m_metrics(candles, incoming_telemetry=None):
    telemetry = incoming_telemetry or {}
    if not candles:
        cur_p = float(str(telemetry.get("btcPrice", 83800)).replace("$", "").replace(",", ""))
        return {
            "btc_price": cur_p,
            "btc_35m_open": cur_p - 150.0,
            "change_usd": 150.0,
            "change_pct": 0.18,
            "high_35m": cur_p + 250.0,
            "low_35m": cur_p - 200.0,
            "mom_5m_pct": 0.08,
            "rsi": float(telemetry.get("rsi", 54.2)),
            "hawkes_score": float(telemetry.get("hawkesScore", 100.0)),
            "hawkes_eta": float(telemetry.get("hawkesEta", 0.67)),
            "sol_price": telemetry.get("solPrice", "$192.40"),
            "hype_price": telemetry.get("hypePrice", "$24.10")
        }

    c35 = candles[-35:] if len(candles) >= 35 else candles
    cur_p = c35[-1]["close"]
    open_35m = c35[0]["open"]
    change_usd = round(cur_p - open_35m, 2)
    change_pct = round((change_usd / open_35m) * 100, 2) if open_35m else 0.0
    high_35m = max(c["high"] for c in c35)
    low_35m = min(c["low"] for c in c35)
    
    c5_open = c35[-5]["open"] if len(c35) >= 5 else open_35m
    mom_5m_pct = round(((cur_p - c5_open) / c5_open) * 100, 2) if c5_open else 0.0
    rsi = calculate_rsi(candles)

    return {
        "btc_price": round(cur_p, 2),
        "btc_35m_open": round(open_35m, 2),
        "change_usd": change_usd,
        "change_pct": change_pct,
        "high_35m": round(high_35m, 2),
        "low_35m": round(low_35m, 2),
        "mom_5m_pct": mom_5m_pct,
        "rsi": rsi,
        "hawkes_score": float(telemetry.get("hawkesScore", 100.0)),
        "hawkes_eta": float(telemetry.get("hawkesEta", 0.67)),
        "sol_price": telemetry.get("solPrice", ""),
        "hype_price": telemetry.get("hypePrice", "")
    }

_cached_newscast = None
_last_newscast_time = 0

def generate_bedrock_newscast(metrics, force=False):
    global _cached_newscast, _last_newscast_time
    now = time.time()
    # Cache for 90 seconds unless explicitly forced by user
    if not force and _cached_newscast and (now - _last_newscast_time < 90):
        return _cached_newscast, True

    client = get_bedrock_client()

    system_prompt = (
        "You are a fast-paced, high-intensity financial TV news anchor (like Bloomberg Surveillance "
        "or BBC World Business Report meets cyberpunk quant terminal).\n"
        "You analyze the last 35 minutes of cryptocurrency market action (price movement, momentum, RSI, "
        "high/low range, and Hawkes liquidation tension).\n"
        "Speak with authoritative punch, sharp market realism, and visceral urgency.\n"
        "Your goal is to give a 3-4 sentence rapid newscast for live video billboard viewers. Include a call to "
        "action for viewers to recharge diamonds, top up beans, or ring the bell.\n"
        "Always return ONLY valid JSON matching this schema:\n"
        "{\n"
        '  "banner": "BLOOMBERG CYBER-TERMINAL: 35-MIN MARKET SCAN",\n'
        '  "subtitle": "short summary with BTC price and RSI (e.g. BTC $83,420 • RSI 61.2 • MOMENTUM +0.8%)",\n'
        '  "headline": "all-caps punchy news headline",\n'
        '  "quote": "one sentence market observation",\n'
        '  "punchline": "call to action punchline in all caps (recharge diamonds, buy beans, ring bell)",\n'
        '  "speech": "3-4 sentences rapid spoken broadcast script for TTS",\n'
        '  "regime": "e.g. BULLISH EXPANSION, CONSOLIDATION LULL, LIQUIDATION SQUEEZE, or VOLATILITY BREAKOUT"\n'
        "}"
    )

    sign = "+" if metrics["change_usd"] >= 0 else ""
    mom_sign = "+" if metrics["mom_5m_pct"] >= 0 else ""
    user_prompt = (
        f"Live market telemetry over the last 35 minutes:\n"
        f"- BTC Current Price: ${metrics['btc_price']:,.2f}\n"
        f"- 35m Open: ${metrics['btc_35m_open']:,.2f}\n"
        f"- 35m Range: High ${metrics['high_35m']:,.2f} / Low ${metrics['low_35m']:,.2f}\n"
        f"- 35m Net Move: {sign}${metrics['change_usd']:,.2f} ({sign}{metrics['change_pct']}%)\n"
        f"- 5m Short-Term Momentum: {mom_sign}{metrics['mom_5m_pct']}%\n"
        f"- 14-period Wilder RSI: {metrics['rsi']}\n"
        f"- Hawkes Liquidation Tension S(t): {metrics['hawkes_score']:.1f}\n"
        f"- Hawkes Branching Ratio η: {metrics['hawkes_eta']:.2f}\n"
        f"{f'- SOL Price: ' + str(metrics['sol_price']) if metrics.get('sol_price') else ''}\n"
        f"Generate the live 35-minute market newscast now."
    )

    newscast_data = None

    if client:
        try:
            resp = client.converse(
                modelId=BEDROCK_HAIKU_MODEL,
                messages=[{"role": "user", "content": [{"text": user_prompt}]}],
                system=[{"text": system_prompt}],
                inferenceConfig={"maxTokens": 450, "temperature": 0.7}
            )
            raw_text = resp["output"]["message"]["content"][0]["text"].strip()
            cleaned = re.sub(r"^```(?:json)?\s*", "", raw_text, flags=re.MULTILINE)
            cleaned = re.sub(r"\s*```$", "", cleaned, flags=re.MULTILINE).strip()
            newscast_data = json.loads(cleaned)
        except Exception as e:
            print(f"[BEDROCK] Converse call failed: {e}", flush=True)
            try:
                body = json.dumps({
                    "anthropic_version": "bedrock-2023-05-31",
                    "max_tokens": 450,
                    "system": system_prompt,
                    "messages": [{"role": "user", "content": user_prompt}]
                })
                resp = client.invoke_model(
                    modelId=BEDROCK_HAIKU_MODEL,
                    body=body,
                    contentType="application/json",
                    accept="application/json"
                )
                res_body = json.loads(resp["body"].read())
                raw_text = res_body["content"][0]["text"].strip()
                cleaned = re.sub(r"^```(?:json)?\s*", "", raw_text, flags=re.MULTILINE)
                cleaned = re.sub(r"\s*```$", "", cleaned, flags=re.MULTILINE).strip()
                newscast_data = json.loads(cleaned)
            except Exception as e2:
                print(f"[BEDROCK] invoke_model fallback failed: {e2}", flush=True)

    # Fallback synthesizer if Bedrock was offline or returned non-JSON
    if not newscast_data:
        direction = "EXPANSION" if metrics["change_usd"] >= 0 else "CONTRACTION"
        regime = "LIQUIDATION SQUEEZE" if metrics["hawkes_score"] >= 140 else f"35M {direction}"
        headline = (
            f"35-MINUTE {direction}: BTC TRACKING ${metrics['btc_price']:,.0f} • "
            f"RSI AT {metrics['rsi']} • HAWKES TENSION {metrics['hawkes_score']:.0f}"
        )
        subtitle = f"BTC ${metrics['btc_price']:,.0f} • RSI {metrics['rsi']} • 35M {sign}{metrics['change_pct']}% • RANGE ${metrics['low_35m']:,.0f} - ${metrics['high_35m']:,.0f}"
        quote = f"Trailing thirty-five minute order flow shows {sign}{metrics['change_pct']}% movement while Hawkes cascade tension reads {metrics['hawkes_score']:.1f}."
        punchline = "RECHARGE YOUR DIAMONDS 💎 • RING THE BELL 🔔 • STAY AHEAD OF THE HERD"
        speech = (
            f"Terminal market desk update: In the last thirty-five minutes, Bitcoin has printed a net move of {sign}{metrics['change_pct']} percent, "
            f"holding a price of ${metrics['btc_price']:,.0f} with Wilder RSI at {metrics['rsi']}. "
            f"Hawkes liquidation tension stands at {metrics['hawkes_score']:.0f} with branching ratio at {metrics['hawkes_eta']:.2f}. "
            f"Do not trade on emotional noise. Step one: recharge your diamonds. Step two: top up your beans. Step three: ring the bell to wake up the room."
        )
        newscast_data = {
            "banner": "BLOOMBERG CYBER-TERMINAL: 35-MIN MARKET SCAN",
            "subtitle": subtitle,
            "headline": headline,
            "quote": quote,
            "punchline": punchline,
            "speech": speech,
            "regime": regime
        }

    _cached_newscast = newscast_data
    _last_newscast_time = now
    return newscast_data, False

@app.route("/api/klines")
def get_klines():
    candles = fetch_recent_candles(limit=40)
    if candles:
        return jsonify({"status": "ok", "candles": candles, "source": "feed"})
    return jsonify({"status": "error", "candles": []}), 500

@app.route("/api/bedrock-newscast", methods=["GET", "POST"])
def get_bedrock_newscast():
    incoming = request.json if request.is_json else {}
    force = bool(incoming.get("force", False)) or (request.args.get("force", "").lower() in ("true", "1"))
    
    candles = fetch_recent_candles(limit=40)
    metrics = compute_35m_metrics(candles, incoming)
    newscast, cached = generate_bedrock_newscast(metrics, force=force)
    
    return jsonify({
        "status": "ok",
        "newscast": newscast,
        "metrics": metrics,
        "cached": cached,
        "timestamp": int(time.time() * 1000)
    })

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
