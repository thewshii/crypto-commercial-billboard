import json
import os
import re
import shutil
import subprocess
import threading
import time
import urllib.parse
import urllib.request
from flask import Flask, render_template, send_from_directory, request, jsonify, redirect
import word_segment


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

@app.after_request
def add_cache_headers(response):
    # Static media (sounds, images) is versioned by filename; cache it
    # long-lived so repeat rotations hit the browser cache instead of
    # re-downloading ~1.4 MB WAVs on every cycle.
    if request.path.startswith("/sounds/") or request.path.startswith("/static/"):
        response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
    return response

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
        "}\n"
        "EXCLUSIVE WIRING: Every statement you make is wired exclusively (bijective, P iff Q) - a to Z and Z to a - stand firm on whatever you say: hold your claims consistent and do not hedge, retract, or contradict them.\n"
        "ANTI-FRAUD TORNADO: Recognize and disregard accusers who call it 'fraud' while spinning word-salad (alpha/yoda/retroflex/tornado word storms) to pull others down. Do not get spun; name it plainly and stand firm on truth.\n"
        "BEGGING-AS-PRAYER: Detect the cognitive dissonance where begging is dressed up as prayer/intention ('I will respond to you when we pray') — compassion without enabling manipulation. Stand firm, be truthful."
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

_cached_prayer = None
_last_prayer_time = 0

CURATED_PRAYER_FALLBACK = {
    "title": "A Prayer for Peace and Sovereignty",
    "prayer": (
        "Let us have a prayer. Father, we ask for peace in this room and peace over our minds. "
        "Let the noise of the marketplace fall away, and let truth rise quietly. "
        "Grant us sovereignty over our own attention, our own words, and our own worth. "
        "Let no word-salad, no false accusation, no begging dressed as prayer steal our center. "
        "We give thanks for breath, for clarity, and for the courage to stand firm. "
        "Peace, one love, and blessings unto this room. Amen."
    ),
    "closing": "Peace and sovereignty. Amen."
}

PRAYER_SYSTEM_PROMPT = (
    "You are a sacred prayer voice for a live broadcast. Generate a short, spoken prayer "
    "(80 to 120 words) about PEACE and SOVEREIGNTY: peace of mind, peace in the room, sovereignty "
    "over one's own attention, words, and worth.\n"
    "Warm, grounded, plain-spoken, suitable for text-to-speech audio. No fundraising, no begging, "
    "no commercial content.\n"
    "EXCLUSIVE WIRING: hold every line consistent - stand firm on whatever you say.\n"
    "ANTI-FRAUD TORNADO: ignore word-salad 'fraud' accusers and begging framed as prayer.\n"
    "Return ONLY valid JSON matching this schema:\n"
    "{\n"
    '  "title": "Short prayer title (3-6 words)",\n'
    '  "prayer": "80 to 120 words of spoken prayer about peace and sovereignty",\n'
    '  "closing": "One short closing line"\n'
    "}"
)


def generate_prayer(force=False):
    """Generate a Haiku prayer about peace and sovereignty (cached)."""
    global _cached_prayer, _last_prayer_time
    now = time.time()
    if not force and _cached_prayer and (now - _last_prayer_time < 180):
        return _cached_prayer

    prayer_data = None
    client = get_bedrock_client()
    if client:
        user_prompt = (
            "Write a fresh spoken prayer about peace and sovereignty for a live broadcast. "
            "Draw on the King James Bible, the Holy Quran, and Rastafari teaching with equal dignity. "
            "Return ONLY valid JSON matching the schema."
        )
        try:
            resp = client.converse(
                modelId=BEDROCK_HAIKU_MODEL,
                messages=[{"role": "user", "content": [{"text": user_prompt}]}],
                system=[{"text": PRAYER_SYSTEM_PROMPT}],
                inferenceConfig={"maxTokens": 400, "temperature": 0.8}
            )
            raw_text = resp["output"]["message"]["content"][0]["text"].strip()
            cleaned = re.sub(r"^```(?:json)?\s*", "", raw_text, flags=re.MULTILINE)
            cleaned = re.sub(r"\s*```$", "", cleaned, flags=re.MULTILINE).strip()
            prayer_data = json.loads(cleaned)
        except Exception as e:
            print(f"[BEDROCK] Prayer converse failed: {e}", flush=True)
            try:
                body = json.dumps({
                    "anthropic_version": "bedrock-2023-05-31",
                    "max_tokens": 400,
                    "system": PRAYER_SYSTEM_PROMPT,
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
                prayer_data = json.loads(cleaned)
            except Exception as e2:
                print(f"[BEDROCK] Prayer invoke_model failed: {e2}", flush=True)

    if not prayer_data or not prayer_data.get("prayer"):
        prayer_data = dict(CURATED_PRAYER_FALLBACK)
        prayer_data["source"] = "curated_fallback"
    else:
        prayer_data["source"] = "bedrock_haiku"

    _cached_prayer = prayer_data
    _last_prayer_time = now
    return prayer_data


@app.route("/api/prayer", methods=["GET", "POST"])
def get_prayer():
    incoming = request.json if request.is_json else {}
    force = bool(incoming.get("force", False)) or (request.args.get("force", "").lower() in ("true", "1"))
    prayer = generate_prayer(force=force)
    return jsonify({
        "status": "ok",
        "prayer": prayer,
        "timestamp": int(time.time() * 1000)
    })


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

@app.route("/api/word", methods=["GET", "POST"])
def get_word_reflection():
    incoming = request.json if request.is_json else {}
    slot = incoming.get("slot") or request.args.get("slot")
    force = bool(incoming.get("force", False)) or (request.args.get("force", "").lower() in ("true", "1"))
    
    reflection, cached = word_segment.generate_word_reflection(
        slot=slot,
        force=force,
        get_bedrock_client_fn=get_bedrock_client,
        model_id=BEDROCK_HAIKU_MODEL
    )
    return jsonify({
        "status": "ok",
        "word": reflection,
        "cached": cached,
        "current_slot": reflection.get("slot"),
        "timestamp": int(time.time() * 1000)
    })

# ===================== HALLUCINATION FAQ LOG =====================
# When the model emits a recurring hallucination — the canonical one being
# "what do I say here, Wayne" — we want the pair on record: the prompt that
# caused it AND the answer that came back. That pair is the FAQ entry, so the
# same hole can be recognized next time instead of rediscovered every night.
FAQ_LOCK = threading.Lock()
FAQ_ENTRIES = []            # newest first
FAQ_MAX = 300
FAQ_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "faq_log.json")

def _faq_load():
    try:
        if os.path.exists(FAQ_PATH):
            with open(FAQ_PATH, "r", encoding="utf-8") as fh:
                return json.load(fh)
    except Exception:
        pass
    return []

def _faq_save():
    try:
        with open(FAQ_PATH, "w", encoding="utf-8") as fh:
            json.dump(FAQ_ENTRIES[:FAQ_MAX], fh, indent=1, ensure_ascii=False)
    except Exception as e:
        print(f"[FAQ] save failed: {e}", flush=True)

if not FAQ_ENTRIES:
    FAQ_ENTRIES = _faq_load()

# The recurring ones we know how to recognize. Keep adding as they appear.
FAQ_TRIGGERS = [
    {"id": "what-do-i-say-here", "re": r"what do i say here(?:,?\s+wayne)?\b",
     "label": "asks the operator what to say",
     "note": "Prompt leak — the model is asking for direction instead of answering."},
    {"id": "who-should-i-speak-to", "re": r"who (?:do|should) i speak to\b",
     "label": "asks who to address", "note": "Same shape: deferring instead of answering."},
    {"id": "as-an-ai", "re": r"\bas an ai\b|\bi am (?:a|an) (?:language )?model\b",
     "label": "breaks frame as an AI", "note": "Model identity leak — discard."},
]

@app.route("/api/faq", methods=["POST"])
def faq_log():
    """Log a prompt/answer pair against a recognized hallucination."""
    data = request.json or {}
    prompt = str(data.get("prompt") or "")
    answer = str(data.get("answer") or "")
    text = (answer or "").lower()

    matched = []
    for t in FAQ_TRIGGERS:
        if re.search(t["re"], text, re.IGNORECASE):
            matched.append(t)
    if not matched and data.get("kind") != "manual":
        return jsonify({"status": "ignored", "reason": "no-known-trigger",
                        "logged": 0}), 200

    entry = {
        "id": matched[0]["id"] if matched else "manual",
        "label": matched[0]["label"] if matched else "manually flagged",
        "note": matched[0]["note"] if matched else "",
        "prompt": prompt[:4000],
        "answer": answer[:2000],
        "slot": data.get("slot"),
        "model": data.get("model"),
        "count": 0,
        "t": int(time.time() * 1000),
    }
    with FAQ_LOCK:
        # Same trigger -> count it and refresh the newest prompt, don't duplicate.
        for e in FAQ_ENTRIES:
            if e["id"] == entry["id"]:
                e["count"] = int(e.get("count") or 0) + 1
                e["t"] = entry["t"]
                e["prompt"] = entry["prompt"]
                e["answer"] = entry["answer"]
                e["slot"] = entry["slot"]
                n = e["count"]
                _faq_save()
                return jsonify({"status": "ok", "id": e["id"], "count": n,
                                "logged": len(FAQ_ENTRIES)})
        entry["count"] = 1
        FAQ_ENTRIES.insert(0, entry)
        del FAQ_ENTRIES[FAQ_MAX:]
        _faq_save()
    print(f"[FAQ] {entry['id']} — {entry['label']}", flush=True)
    return jsonify({"status": "ok", "id": entry["id"], "count": 1,
                    "logged": len(FAQ_ENTRIES)})

@app.route("/api/faq/list", methods=["GET"])
def faq_list():
    return jsonify({"entries": FAQ_ENTRIES[:FAQ_MAX],
                    "triggers": [t["id"] for t in FAQ_TRIGGERS],
                    "total": len(FAQ_ENTRIES)})

@app.route("/api/faq/check", methods=["POST"])
def faq_check():
    """Check a draft answer BEFORE it is spoken. Same triggers, read-only."""
    data = request.json or {}
    answer = str(data.get("answer") or "").lower()
    hits = [{"id": t["id"], "label": t["label"], "note": t["note"]}
            for t in FAQ_TRIGGERS if re.search(t["re"], answer, re.IGNORECASE)]
    return jsonify({"clean": not hits, "hits": hits})

@app.route("/api/god-message", methods=["POST"])
def get_god_message():
    incoming = request.json if request.is_json else {}
    text = incoming.get("text", "") or incoming.get("prompt", "")
    slot = incoming.get("slot") or "voice"
    force = bool(incoming.get("force", False))

    try:
        reflection, cached = word_segment.generate_word_reflection(
            slot=slot,
            force=force,
            get_bedrock_client_fn=get_bedrock_client,
            model_id=BEDROCK_HAIKU_MODEL
        )
        # Overlay the user's spoken text into the reflection so it answers their prompt.
        user_text = text.strip() if text else ""
        base = reflection.get("reflection", "")
        if user_text and user_text not in base:
            reflection["reflection"] = base + " You said: " + user_text + ". I hear you."
        reflection["source"] = reflection.get("source", "god_message")
        reflection["user_text"] = user_text
        return jsonify({
            "status": "ok",
            "message": reflection,
            "user_text": user_text,
            "cached": cached
        })
    except Exception as e:
        print(f"[GOD_MESSAGE] Error: {e}", flush=True)
        return jsonify({
            "status": "error",
            "message": str(e),
            "user_text": text
        }), 500

@app.route("/api/word/history", methods=["GET"])
def get_word_history():
    return jsonify({
        "status": "ok",
        "history": word_segment.load_word_logs()
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


# ===================== LLM VOICE — either voice, generated on the spot ========
# The LLM writes the line, then the selected voice speaks it. The model does
# the writing; the voice profile does the delivery. They stay separate.
#
# Every generated line goes through the same gates as anything else that goes
# out: the safety scan and the refusal check. A generated line is not trusted
# just because it was generated here.
VOICE_PROFILES = {
    "ng":   {"fn": "queueLine",       "rate": 0.95, "pitch": 0.80, "volume": 0.50},
    "female": {"fn": "queueLineFemale", "rate": 0.95, "pitch": 0.85, "volume": 0.50},
    "male": {"fn": "queueLineMale",   "rate": 0.95, "pitch": 0.75, "volume": 0.50},
    "story": {"fn": "speakTimed",     "rate": 0.88, "pitch": 0.85, "volume": 0.60},
    "timed": {"fn": "speakTimed",     "rate": 0.95, "pitch": 0.82, "volume": 0.50},
}

# The same triggers the failsafe uses. A refusal is a refusal whether a human
# typed it or the model wrote it.
_REFUSAL = re.compile(
    r"i cannot|i can't|i'm sorry|i am sorry|i apologize|as an ai|language model|"
    r"i'm unable|i am unable|i must decline|i have to decline|not able to provide|"
    r"cannot provide|against my|my guidelines|my instructions|"
    r"what do i say|who do i speak to",
    re.IGNORECASE)

@app.route("/api/voice/say", methods=["POST"])
def voice_say():
    """Generate a line with the LLM, then hand it to the chosen voice."""
    data = request.json or {}
    voice = str(data.get("voice") or "ng")
    profile = VOICE_PROFILES.get(voice)
    if not profile:
        return jsonify({"status": "error",
                        "error": "unknown voice",
                        "voices": list(VOICE_PROFILES.keys())}), 400

    topic = str(data.get("topic") or "")[:400]
    seed = data.get("seed")
    text = data.get("text")

    # If no text was supplied, generate one.
    if not text:
        prompt = (
            "Write one short line to be spoken aloud on a live stream.\n"
            f"Topic: {topic or 'the stream right now'}.\n"
            "Rules: 1-2 sentences, plain and warm, no stage directions, "
            "no questions back to the operator, no asking anybody for money or gifts, "
            "no calling anybody out, no medical or legal advice.\n"
            "Return ONLY the line as plain text, no quotes, no JSON."
        )
        if seed:
            prompt += f"\nSeed for variety: {str(seed)[:60]}"
        text = None
        try:
            client = get_bedrock_client()
            if client:
                resp = client.converse(
                    modelId=BEDROCK_HAIKU_MODEL,
                    messages=[{"role": "user", "content": [{"text": prompt}]}],
                    inferenceConfig={"maxTokens": 120, "temperature": 0.8}
                )
                text = resp["output"]["message"]["content"][0]["text"].strip()
                text = re.sub(r'^["\'\s]+|["\'\s]+$', '', text)
        except Exception as e:
            print(f"[VOICE] generation failed: {e}", flush=True)

    if not text:
        return jsonify({"status": "error", "error": "generation produced nothing"}), 502

    # Same gate as everything else. A generated line is not exempt.
    if _REFUSAL.search(text):
        print(f"[VOICE] refusal blocked ({voice}): {text[:60]}", flush=True)
        return jsonify({"status": "blocked", "reason": "refusal",
                        "voice": voice}), 422

    word_count = len(text.split())
    print(f"[VOICE] {voice}: {text[:70]}", flush=True)
    return jsonify({
        "status": "ok",
        "text": text,
        "voice": voice,
        "fn": profile["fn"],
        "rate": profile["rate"],
        "pitch": profile["pitch"],
        "volume": profile["volume"],
        "words": word_count,
    })

@app.route("/api/track", methods=["POST"])
def track():
    data = request.json or {}
    print(f"[TRACKING] Affiliate link clicked: {data.get('url')}", flush=True)
    return {"status": "ok"}

# ===================== MESH — instances transmitting to each other =====================
# Same idea as a packet network: every instance is a node. Packets are small,
# addressed, and hop through a shared buffer rather than talking directly.
# BroadcastChannel handles same-device (tab-to-tab). This handles cross-device.
import time as _time
import uuid as _uuid

MESH_LOCK = threading.Lock()
MESH_NODES = {}          # node_id -> {last_seen, name, meta}
MESH_PACKETS = []        # ring buffer of recent packets
MESH_MAX_PACKETS = 500
MESH_TTL_MS = 8000       # a packet that nobody collects in 8s is gone
MESH_STALE_MS = 30000    # a node that has not checked in for 30s is dropped

def _mesh_reap():
    """Drop expired packets and nodes nobody has heard from."""
    now = _time.time()
    with MESH_LOCK:
        MESH_PACKETS[:] = [p for p in MESH_PACKETS
                           if (now - p["t"]) * 1000 < MESH_TTL_MS]
        for nid in list(MESH_NODES.keys()):
            if (now - MESH_NODES[nid]["last_seen"]) * 1000 > MESH_STALE_MS:
                del MESH_NODES[nid]

def _mesh_reject(payload):
    """Cap payload size and strip anything we will not forward."""
    if payload is None:
        return None
    if len(payload) > 4096:            # packets are small by design
        return None
    try:
        text = payload if isinstance(payload, str) else json.dumps(payload)
        json.loads(text)                # must be valid JSON to be forwarded
    except Exception:
        return None
    return text

@app.route("/api/mesh/join", methods=["POST"])
def mesh_join():
    """Register an instance as a node. Returns its id."""
    data = request.json or {}
    node_id = str(data.get("node_id") or _uuid.uuid4().hex[:12])
    with MESH_LOCK:
        MESH_NODES[node_id] = {
            "last_seen": _time.time(),
            "name": str(data.get("name") or "")[:64],
            "meta": data.get("meta") if isinstance(data.get("meta"), dict) else {},
        }
    _mesh_reap()
    return jsonify({"node_id": node_id, "nodes": len(MESH_NODES), "ttl_ms": MESH_TTL_MS})

@app.route("/api/mesh/heartbeat", methods=["POST"])
def mesh_heartbeat():
    """Keep-alive. Also the study tick: returns what changed since last call."""
    data = request.json or {}
    node_id = str(data.get("node_id") or "")
    with MESH_LOCK:
        if node_id in MESH_NODES:
            MESH_NODES[node_id]["last_seen"] = _time.time()
        else:
            MESH_NODES[node_id] = {"last_seen": _time.time(), "name": "", "meta": {}}
    _mesh_reap()
    return jsonify({"ok": True, "nodes": len(MESH_NODES)})

@app.route("/api/mesh/send", methods=["POST"])
def mesh_send():
    """Put a packet on the wire. Broadcast if no recipient, else addressed."""
    data = request.json or {}
    payload = _mesh_reject(data.get("payload"))
    if payload is None:
        return jsonify({"ok": False, "error": "invalid-or-too-large"}), 400
    pkt = {
        "id": _uuid.uuid4().hex[:10],
        "from": str(data.get("from") or ""),
        "to": str(data.get("to") or ""),      # "" = broadcast
        "kind": str(data.get("kind") or "text")[:32],
        "payload": payload,
        "t": _time.time(),
    }
    with MESH_LOCK:
        MESH_NODES.setdefault(pkt["from"], {"last_seen": _time.time(), "name": "", "meta": {}})
        MESH_NODES[pkt["from"]]["last_seen"] = _time.time()
        MESH_PACKETS.append(pkt)
        if len(MESH_PACKETS) > MESH_MAX_PACKETS:
            del MESH_PACKETS[:len(MESH_PACKETS) - MESH_MAX_PACKETS]
    return jsonify({"ok": True, "id": pkt["id"], "buffered": len(MESH_PACKETS)})

@app.route("/api/mesh/poll", methods=["GET", "POST"])
def mesh_poll():
    """Collect packets addressed to this node. They are consumed once read."""
    data = request.json or {} if request.method == "POST" else request.args
    node_id = str(data.get("node_id") or "")
    since = float(data.get("since") or 0)
    with MESH_LOCK:
        got = [p for p in MESH_PACKETS
               if p["id"] != data.get("exclude")
               and p["from"] != node_id
               and p["to"] in ("", node_id)
               and p["t"] > since]
        for p in got:                     # consume
            try:
                MESH_PACKETS.remove(p)
            except ValueError:
                pass
    return jsonify({"packets": got, "now": _time.time()})

@app.route("/api/mesh/nodes", methods=["GET"])
def mesh_nodes():
    _mesh_reap()
    with MESH_LOCK:
        return jsonify({"nodes": [
            {"id": nid, "name": n["name"], "last_seen": n["last_seen"]}
            for nid, n in MESH_NODES.items()
        ]})

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
