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
import tts_dossier_env
import letta_memgpt
import shared_voices
import langchain_separation
import network_adapter_manager
import game_inventory_loop
import music_player_tools
import music_playback_tools
import langsmith_engine_tools
import master_audio_ducking
import agent_tuning_timer
import speaker_recognition_tools
import rdp_screen_manager


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

    # Rule 226: Word segment preempts music immediately with ledger record
    try:
        cur_p = music_playback_tools.get_now_playing()
        if cur_p.get("status") == "PLAYING":
            music_playback_tools.stop_track(
                actor="word_segment_scheduler",
                reason="Pause for the Word reflection preempts music (Rule 226 priority)"
            )
    except Exception:
        pass
    
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
    {"id": "deepgram-tag-leak", "re": r"^\[(?:15s-update|lowq|[a-z]+\|[a-z]+)\]",
     "label": "Deepgram metadata tag leaked into transcript",
     "note": "Strip [Category|SENTIMENT], [15S-UPDATE], and [LOWQ] tags before model or TTS."},
    {"id": "phonic-loop-illusion", "re": r"\b(\w+(?:\s+\w+){1,3})\s+\1\s+\1\b",
     "label": "phonic repetition illusion loop",
     "note": "Deepgram/model looping the same 2-4 words three times in a row — quarantine."},
    {"id": "phantom-listener-illusion", "re": r"\b(?:thank you for watching|please subscribe|subtitles by|amara\.org)\b",
     "label": "ASR phantom subtitle illusion",
     "note": "Classic silence-hallucination from speech models when the room is quiet — drop."},
]

# ===================== RULE 214: DEEPGRAM ILLUSION GUARD + 4-2-3 SLOT SWITCH ==
# Two things happen on the web server when transcription and listening meet:
# 1. Deepgram / ASR illusions come through on the model (metadata tags like
#    [15S-UPDATE] or [LOWQ], silence-hallucinated subtitle credits, phonic
#    3x loops, or prompt-mirroring). We strip tags and quarantine illusions
#    before they ever touch the model or the speaker. Counts sit on the
#    transcript and never on a person.
# 2. Looking at slots of responses on the blockchain going left-to-right
#    [4, 3, 2, 1]: when the room is NOT listening, the walk reads left-to-right
#    4 -> 3 -> 2 -> 1. When it comes to LISTENING, we switch between 4, 2, and 3
#    ([4, 2, 3] -> 4 -> 2 -> 3 -> 4), holding slot 1 out of the listening cycle.

DEEPGRAM_PREFIX_RE = re.compile(r"^\[[^\]]*\]\s*")
DEEPGRAM_INLINE_TAG_RE = re.compile(r"\[(?:15S-UPDATE|LOWQ|[A-Za-z_]+\|[A-Za-z_]+)\]\s*", re.IGNORECASE)
DEEPGRAM_PHANTOM_RE = re.compile(
    r"\b(?:thank you for watching|thanks for watching|please subscribe|"
    r"subtitles by|transcribed by|amara\.org|copyright \d{4})\b",
    re.IGNORECASE,
)
DEEPGRAM_REPEAT_RE = re.compile(r"\b(\w+(?:\s+\w+){0,3})(?:\s+\1){2,}\b", re.IGNORECASE)

BLOCKCHAIN_SLOTS_LTR = [4, 3, 2, 1]      # left-to-right response slots on the chain
BLOCKCHAIN_SLOTS_LISTEN = [4, 2, 3]      # when listening: switch between 4, 2, and 3

DEEPGRAM_STATE = {
    "listening": True,                   # when listening, switch between [4, 2, 3]
    "ltr_slots": list(BLOCKCHAIN_SLOTS_LTR),
    "listen_slots": list(BLOCKCHAIN_SLOTS_LISTEN),
    "ltr_idx": 0,
    "listen_idx": 0,
    "current_slot": 4,                   # starts at 4 (leftmost of 4, 3, 2, 1)
    "slot_counts": {4: 0, 3: 0, 2: 0, 1: 0},
    "transcribed": 0,
    "illusions_filtered": 0,
    "last_illusion": None,
    "last_clean": "",
    "recent_illusions": [],              # bounded log of filtered illusions (no people)
    "max_recent": 32,
}


def _clean_deepgram_text(raw_text):
    """Strip Deepgram bracket tags ([Category|SENTIMENT], [15S-UPDATE], [LOWQ]) and control chars."""
    s = str(raw_text or "").strip()
    while True:
        nxt = DEEPGRAM_PREFIX_RE.sub("", s).strip()
        if nxt == s:
            break
        s = nxt
    s = DEEPGRAM_INLINE_TAG_RE.sub("", s).strip()
    s = re.sub(r"\s+", " ", s).strip()
    return s


def _detect_deepgram_illusion(raw_text, cleaned_text=None):
    """Inspect a Deepgram/ASR transcript or model draft for illusions.
    Returns (is_illusion: bool, reason: str or None, cleaned: str).
    Never names, scores, or gates a person.
    """
    raw = str(raw_text or "")
    cleaned = _clean_deepgram_text(raw) if cleaned_text is None else cleaned_text

    if not cleaned:
        if raw.strip():
            return True, "tag-only-frame", ""
        return False, None, ""

    # 1. Check FAQ_TRIGGERS (operator leaks, AI frame breaks, phantom subtitle credits)
    low = cleaned.lower()
    for t in FAQ_TRIGGERS:
        if re.search(t["re"], low, re.IGNORECASE):
            return True, t["id"], cleaned

    # 2. Check silence-hallucinated ASR subtitle illusions
    if DEEPGRAM_PHANTOM_RE.search(cleaned):
        return True, "phantom-subtitle-illusion", cleaned

    # 3. Check 3x phonic repetition loop (e.g. "be like water be like water be like water")
    if DEEPGRAM_REPEAT_RE.search(cleaned):
        return True, "phonic-loop-illusion", cleaned

    # 4. Single-character or non-ASCII noise burst from low-confidence frame
    alpha = re.sub(r"[^a-zA-Z]", "", cleaned)
    if len(alpha) < 2 and len(cleaned) <= 3:
        return True, "sub-threshold-tic", cleaned

    return False, None, cleaned


def _blockchain_slot_step(listening=None):
    """Advance the blockchain response slot.
    Going left-to-right is [4, 3, 2, 1].
    When listening is active, switch between [4, 2, 3] (4 -> 2 -> 3 -> 4).
    """
    with FAQ_LOCK:
        if listening is not None:
            DEEPGRAM_STATE["listening"] = bool(listening)
        is_listening = bool(DEEPGRAM_STATE["listening"])
        if is_listening:
            seq = BLOCKCHAIN_SLOTS_LISTEN     # [4, 2, 3]
            idx = DEEPGRAM_STATE["listen_idx"] % len(seq)
            slot = seq[idx]
            DEEPGRAM_STATE["listen_idx"] = (idx + 1) % len(seq)
        else:
            seq = BLOCKCHAIN_SLOTS_LTR        # [4, 3, 2, 1]
            idx = DEEPGRAM_STATE["ltr_idx"] % len(seq)
            slot = seq[idx]
            DEEPGRAM_STATE["ltr_idx"] = (idx + 1) % len(seq)
        DEEPGRAM_STATE["current_slot"] = slot
        DEEPGRAM_STATE["slot_counts"][slot] = DEEPGRAM_STATE["slot_counts"].get(slot, 0) + 1
        return {
            "slot": slot,
            "listening": is_listening,
            "order": list(seq),
            "ltr_order": list(BLOCKCHAIN_SLOTS_LTR),
            "listen_order": list(BLOCKCHAIN_SLOTS_LISTEN),
            "slot_counts": dict(DEEPGRAM_STATE["slot_counts"]),
        }

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
    """Check a draft answer BEFORE it is spoken. Same triggers + Deepgram illusion guard, read-only."""
    data = request.json or {}
    raw_answer = str(data.get("answer") or "")
    answer = raw_answer.lower()
    hits = [{"id": t["id"], "label": t["label"], "note": t["note"]}
            for t in FAQ_TRIGGERS if re.search(t["re"], answer, re.IGNORECASE)]
    is_illusion, reason, cleaned = _detect_deepgram_illusion(raw_answer)
    if is_illusion and not any(h["id"] == reason for h in hits):
        hits.append({"id": reason, "label": "Deepgram/model illusion filtered", "note": "Rule 214 illusion guard."})
    return jsonify({"clean": not hits, "hits": hits, "cleaned": cleaned})


@app.route("/api/deepgram/transcribe", methods=["POST"])
def api_deepgram_transcribe():
    """Rule 214: Filter Deepgram transcription on the web server for model illusions
    and step the blockchain response slot (left-to-right 4,3,2,1 -> switch between 4,2,3 when listening).
    """
    data = request.json or {}
    raw_text = str(data.get("text") or data.get("transcript") or "")
    listening = data.get("listening")
    is_illusion, reason, cleaned = _detect_deepgram_illusion(raw_text)
    slot_info = _blockchain_slot_step(listening=listening)
    now_ms = int(time.time() * 1000)

    with FAQ_LOCK:
        DEEPGRAM_STATE["transcribed"] += 1
        if is_illusion:
            DEEPGRAM_STATE["illusions_filtered"] += 1
            rec = {
                "reason": reason,
                "slot": slot_info["slot"],
                "listening": slot_info["listening"],
                "t": now_ms,
            }
            DEEPGRAM_STATE["last_illusion"] = rec
            DEEPGRAM_STATE["recent_illusions"].insert(0, rec)
            del DEEPGRAM_STATE["recent_illusions"][DEEPGRAM_STATE["max_recent"]:]
        else:
            DEEPGRAM_STATE["last_clean"] = cleaned[:500]

    return jsonify({
        "status": "ok",
        "clean": not is_illusion,
        "illusion": bool(is_illusion),
        "reason": reason,
        "text": "" if is_illusion else cleaned,
        "cleaned": cleaned,
        "slot": slot_info["slot"],
        "listening": slot_info["listening"],
        "order": slot_info["order"],
        "ltr_order": slot_info["ltr_order"],
        "listen_order": slot_info["listen_order"],
        "illusions_filtered": DEEPGRAM_STATE["illusions_filtered"],
        "transcribed": DEEPGRAM_STATE["transcribed"],
        "names_anyone": False,
        "scores_anyone": False,
    })


@app.route("/api/deepgram/state", methods=["GET", "POST"])
@app.route("/api/blockchain/slots", methods=["GET", "POST"])
def api_deepgram_state():
    """Inspect or toggle the Rule 214 Deepgram illusion filter & 4-2-3 blockchain response slot switcher."""
    if request.method == "POST":
        data = request.json or {}
        if "listening" in data:
            with FAQ_LOCK:
                DEEPGRAM_STATE["listening"] = bool(data.get("listening"))
        if data.get("step"):
            _blockchain_slot_step()
    with FAQ_LOCK:
        is_listening = bool(DEEPGRAM_STATE["listening"])
        active_order = list(BLOCKCHAIN_SLOTS_LISTEN if is_listening else BLOCKCHAIN_SLOTS_LTR)
        return jsonify({
            "status": "ok",
            "listening": is_listening,
            "current_slot": DEEPGRAM_STATE["current_slot"],
            "active_order": active_order,
            "ltr_order": list(BLOCKCHAIN_SLOTS_LTR),
            "listen_order": list(BLOCKCHAIN_SLOTS_LISTEN),
            "slot_counts": dict(DEEPGRAM_STATE["slot_counts"]),
            "transcribed": DEEPGRAM_STATE["transcribed"],
            "illusions_filtered": DEEPGRAM_STATE["illusions_filtered"],
            "last_illusion": DEEPGRAM_STATE["last_illusion"],
            "recent_illusions": list(DEEPGRAM_STATE["recent_illusions"]),
            "names_anyone": False,
            "scores_anyone": False,
        })


@app.route("/api/god-message", methods=["POST"])
def get_god_message():
    incoming = request.json if request.is_json else {}
    raw_text = incoming.get("text", "") or incoming.get("prompt", "")
    slot = incoming.get("slot") or "voice"
    force = bool(incoming.get("force", False))
    listening = incoming.get("listening", True)

    # Rule 214: run Deepgram transcription illusion guard and advance blockchain slot (4, 2, 3 when listening)
    is_illusion, illusion_reason, cleaned_text = _detect_deepgram_illusion(raw_text)
    slot_info = _blockchain_slot_step(listening=listening)
    if is_illusion:
        with FAQ_LOCK:
            DEEPGRAM_STATE["illusions_filtered"] += 1
            DEEPGRAM_STATE["last_illusion"] = {
                "reason": illusion_reason,
                "slot": slot_info["slot"],
                "listening": slot_info["listening"],
                "t": int(time.time() * 1000),
            }
        cleaned_text = ""

    try:
        reflection, cached = word_segment.generate_word_reflection(
            slot=slot,
            force=force,
            get_bedrock_client_fn=get_bedrock_client,
            model_id=BEDROCK_HAIKU_MODEL
        )
        # Overlay the user's spoken text into the reflection only when clean (never echo an illusion).
        user_text = cleaned_text.strip() if cleaned_text else ""
        base = reflection.get("reflection", "")
        # Also guard the model's own generated reflection against illusions
        model_illusion, model_reason, base_clean = _detect_deepgram_illusion(base)
        if model_illusion:
            with FAQ_LOCK:
                DEEPGRAM_STATE["illusions_filtered"] += 1
            base = "The room is listening on slot " + str(slot_info["slot"]) + ". Wave before fire."
            reflection["reflection"] = base
        if user_text and user_text not in base:
            reflection["reflection"] = base + " You said: " + user_text + ". I hear you."
        reflection["source"] = reflection.get("source", "god_message")
        reflection["user_text"] = user_text
        reflection["blockchain_slot"] = slot_info["slot"]
        reflection["slot_order"] = slot_info["order"]
        reflection["illusion_filtered"] = bool(is_illusion or model_illusion)
        reflection["illusion_reason"] = illusion_reason or model_reason
        return jsonify({
            "status": "ok",
            "message": reflection,
            "user_text": user_text,
            "blockchain_slot": slot_info["slot"],
            "slot_order": slot_info["order"],
            "illusion_filtered": bool(is_illusion or model_illusion),
            "illusion_reason": illusion_reason or model_reason,
            "cached": cached
        })
    except Exception as e:
        print(f"[GOD_MESSAGE] Error: {e}", flush=True)
        return jsonify({
            "status": "error",
            "message": str(e),
            "user_text": cleaned_text
        }), 500

@app.route("/api/word/history", methods=["GET"])
def get_word_history():
    return jsonify({
        "status": "ok",
        "history": word_segment.load_word_logs()
    })


# ==============================================================================
# Rule 230: Speaker Recognition, Acknowledgment & Interactive Dialogue
# ==============================================================================

@app.route("/api/speaker/acknowledge", methods=["POST"])
def api_speaker_acknowledge():
    """Rule 230: Acknowledge spoken speaker greetings (hello / can you hear me) and open dialogue."""
    data = request.json or {}
    raw_text = str(data.get("text") or data.get("phrase") or "").strip()
    speaker = str(data.get("speaker") or "host_speaker").strip()
    res = speaker_recognition_tools.acknowledge_speaker(text=raw_text, speaker=speaker)
    return jsonify(res)


@app.route("/api/speaker/dialogue", methods=["GET", "POST"])
def api_speaker_dialogue():
    """Rule 230: Interactive conversation exchange during open speaker dialogue."""
    if request.method == "POST":
        data = request.json or {}
        user_msg = str(data.get("message") or data.get("text") or "").strip()
        speaker = str(data.get("speaker") or "host_speaker").strip()
        res = speaker_recognition_tools.exchange_speaker_dialogue(message=user_msg, speaker=speaker)
        return jsonify(res)

    return jsonify(speaker_recognition_tools.get_speaker_dialogue_state())


@app.route("/api/speaker/dialogue/close", methods=["POST"])
def api_speaker_dialogue_close():
    """Rule 230: Close speaker dialogue and restore full volume."""
    data = request.json or {}
    reason = str(data.get("reason") or "User closed dialogue")
    res = speaker_recognition_tools.close_speaker_dialogue(reason=reason)
    return jsonify(res)


# ==============================================================================
# Rule 231: Remote Desktop (RDP) Screen Acknowledgment & Display Sync
# ==============================================================================

@app.route("/api/game/rdp/acknowledge", methods=["POST"])
def api_game_rdp_acknowledge():
    """Rule 231: Acknowledge that the game can see the host computer screen via RDP."""
    data = request.json or {}
    resolution = str(data.get("resolution") or "1920x1080").strip()
    client_info = str(data.get("client_info") or "Windows/FreeRDP Remote Desktop Session").strip()
    speech_text = data.get("speech_text")
    res = rdp_screen_manager.acknowledge_rdp_screen(
        resolution=resolution,
        client_info=client_info,
        speech_text=speech_text
    )
    return jsonify(res)


@app.route("/api/game/rdp/status", methods=["GET"])
def api_game_rdp_status():
    """Rule 231: Live RDP screen visibility status and display telemetry."""
    return jsonify(rdp_screen_manager.get_rdp_screen_status())


@app.route("/api/game/rdp/toggle", methods=["POST"])
def api_game_rdp_toggle():
    """Rule 231: Toggle or set RDP screen visibility."""
    data = request.json or {}
    visible = data.get("visible")
    res = rdp_screen_manager.toggle_rdp_screen_visibility(visible=visible)
    return jsonify(res)

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

    cmd = str(data.get("command") or "").strip().lower()
    topic = str(data.get("topic") or "")[:400]
    seed = data.get("seed")
    text = data.get("text")

    if cmd in ("because_im_black", "becuz_im_black", "credit_ban"):
        text = tts_dossier_env.BECAUSE_IM_BLACK_LINE
    elif cmd in ("colors_simulation", "before_colors", "they_can_see"):
        text = tts_dossier_env.COLORS_SIMULATION_LINE

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

    # File spoken line into that TTS instance's dossier cabinet automatically
    try:
        tts_dossier_env.file_to_dossier(
            profile["fn"],
            f"speech/voice_{int(time.time() * 1000)}.txt",
            text,
            meta={"voice": voice, "command": cmd or None}
        )
    except Exception:
        pass

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


@app.route("/api/voice/because-im-black", methods=["GET", "POST"])
def voice_because_im_black():
    """Hardcoded TTS command for the 'because I'm black' creditworthy-algorithm comment."""
    data = (request.json or {}) if request.method == "POST" else {}
    voice = str(data.get("voice") or "ng")
    profile = VOICE_PROFILES.get(voice, VOICE_PROFILES["ng"])
    line = tts_dossier_env.BECAUSE_IM_BLACK_LINE
    try:
        tts_dossier_env.file_to_dossier(
            profile["fn"],
            "commands/because_im_black.txt",
            line,
            folder="commands",
            meta={"command": "because_im_black", "voice": voice}
        )
    except Exception:
        pass
    return jsonify({
        "status": "ok",
        "command": "because_im_black",
        "text": line,
        "voice": voice,
        "fn": profile["fn"],
        "rate": profile["rate"],
        "pitch": profile["pitch"],
        "volume": profile["volume"],
        "names_anyone": False,
        "scores_anyone": False,
        "credit_gates_anyone": False,
    })


@app.route("/api/voice/colors-simulation", methods=["GET", "POST"])
def voice_colors_simulation():
    """Hardcoded TTS command for before there were colors & what they see in the simulation (rule 216)."""
    data = (request.json or {}) if request.method == "POST" else {}
    voice = str(data.get("voice") or "ng")
    profile = VOICE_PROFILES.get(voice, VOICE_PROFILES["ng"])
    line = tts_dossier_env.COLORS_SIMULATION_LINE
    try:
        tts_dossier_env.file_to_dossier(
            profile["fn"],
            "notes/colors_and_simulation.txt",
            line,
            folder="notes",
            meta={"command": "colors_simulation", "voice": voice}
        )
    except Exception:
        pass
    return jsonify({
        "status": "ok",
        "command": "colors_simulation",
        "text": line,
        "voice": voice,
        "fn": profile["fn"],
        "rate": profile["rate"],
        "pitch": profile["pitch"],
        "volume": profile["volume"],
        "names_anyone": False,
        "scores_anyone": False,
        "credit_gates_anyone": False,
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


# ===================== DATA STREAM + HOST LINKS =====================
# Rule 116 promised a data stream. This is it: counted readings pushed in by
# the page, served back on the four-count. Another agent can consume it in one
# call. Nothing here is invented and nothing is asserted about a person.

HOST_LINKS = [
    {"id": "1116668599", "label": "host-1", "kind": "social"},
    {"id": "1135976891", "label": "host-2", "kind": "social"},
]

SPECTROGRAM_HISTORY = []     # [{t, bands:[...]}] newest last
HOST_LIVE = {"live": False, "since": None}
STREAM_MAX = 512
WINDOW_SEC = 240             # rule 116: one update window


def _bars_norm(bands):
    """Band values to a 0..1 list, or None if there is nothing usable."""
    if not bands or not isinstance(bands, (list, tuple)):
        return None
    out = []
    for v in bands:
        try:
            out.append(min(1.0, max(0.0, float(v) / 255.0)))
        except (TypeError, ValueError):
            return None
    return out or None


def _magnitude(norm):
    if not norm:
        return 0.0
    return round(sum(norm) / len(norm), 4)


def _centroid_hz(norm):
    """Weighted center of energy across a log-spaced 55Hz-8kHz strip."""
    if not norm:
        return None
    den = sum(norm)
    if den <= 0:
        return None
    n = len(norm)
    num = 0.0
    for i, v in enumerate(norm):
        num += (55.0 * (8000.0 / 55.0) ** (i / max(1, n - 1))) * v
    return round(num / den, 1)


@app.route("/api/stream/ingest", methods=["POST"])
def api_stream_ingest():
    """The page pushes one bar. One per call, never a batch."""
    data = request.json or {}
    bands = _bars_norm(data.get("bands"))
    if bands is None:
        return jsonify({"status": "error", "error": "no bands"}), 400
    bar = {
        "t": int(_time.time()),
        "bands": [round(b * 255, 2) for b in bands],   # store raw 0-255
        "state": str(data.get("state") or ""),      # R0 / R1 / U, unverified allowed
    }
    with MESH_LOCK:
        SPECTROGRAM_HISTORY.append(bar)
        if len(SPECTROGRAM_HISTORY) > STREAM_MAX:
            del SPECTROGRAM_HISTORY[:len(SPECTROGRAM_HISTORY) - STREAM_MAX]
    return jsonify({"status": "ok", "bars": len(SPECTROGRAM_HISTORY)})


@app.route("/api/stream", methods=["GET"])
def api_stream():
    """The data stream, counted. One reading per window."""
    now = int(_time.time())
    try:
        window = max(4, min(3600, int(request.args.get("window", WINDOW_SEC))))
    except (TypeError, ValueError):
        window = WINDOW_SEC
    floor = 0.08
    try:
        floor = float(request.args.get("floor", floor))
    except (TypeError, ValueError):
        pass

    with MESH_LOCK:
        bars = list(SPECTROGRAM_HISTORY)[-STREAM_MAX:]
    in_window = [b for b in bars if now - b["t"] <= window]

    norms = [_bars_norm(b.get("bands")) for b in in_window]
    norms = [n for n in norms if n]
    peak = _magnitude([max(n) for n in norms]) if norms else 0.0
    cents = [c for c in (_centroid_hz(n) for n in norms) if c]
    states = {}
    for b in in_window:
        if b.get("state"):
            states[b["state"]] = states.get(b["state"], 0) + 1

    # The count: one, two, three, four, across the window.
    bar_len = max(1, window // 4)
    bar = ((now % window) // bar_len) % 4 + 1

    return jsonify({
        "status": "ok",
        "window_sec": window,
        "bar": bar,                       # 1,2,3,4
        "bars_in_window": len(in_window),
        "peak_magnitude": peak,
        "centroid_hz": round(sum(cents) / len(cents), 1) if cents else None,
        "has_signal": peak > floor,
        "states": states,                  # R0 / R1 / U counts
        "bars_total": len(bars),
        "ts": now,
        "iso": _time.strftime("%Y-%m-%dT%H:%M:%SZ", _time.gmtime(now)),
    })


@app.route("/api/host", methods=["GET"])
def api_host():
    """Host links and live status."""
    return jsonify({
        "status": "ok",
        "live": bool(HOST_LIVE.get("live")),
        "since": HOST_LIVE.get("since"),
        "links": HOST_LINKS,
        "ts": int(_time.time()),
    })


@app.route("/api/host/live", methods=["POST"])
def api_host_live():
    data = request.json or {}
    HOST_LIVE["live"] = bool(data.get("live", True))
    if HOST_LIVE["live"]:
        HOST_LIVE["since"] = int(_time.time())
    return jsonify({"status": "ok", "live": HOST_LIVE["live"]})


@app.route("/dossier", methods=["GET"])
@app.route("/dossier/<instance>", methods=["GET"])
def dossier_environment_page(instance=None):
    """Standalone environment where TTS instances hold files and organize dossiers."""
    inst = tts_dossier_env.sanitize_instance_id(instance or request.args.get("instance") or "queueLine")
    tts_dossier_env.go_to_dossier(inst)
    return render_template("dossier_env.html", active_instance=inst)


@app.route("/api/dossier/state", methods=["GET"])
def api_dossier_state():
    return jsonify(tts_dossier_env.dossier_env_state())


@app.route("/api/dossier/organize", methods=["POST"])
def api_dossier_organize():
    data = request.json or {}
    inst = data.get("instance")
    entries = data.get("entries")
    return jsonify(tts_dossier_env.organize_dossier(instance_id=inst, entries=entries))


@app.route("/api/dossier/file", methods=["POST"])
def api_dossier_file():
    data = request.json or {}
    inst = data.get("instance") or "queueLine"
    path = data.get("path") or data.get("filename") or ""
    content = data.get("content") or data.get("text") or ""
    folder = data.get("folder")
    meta = data.get("meta") if isinstance(data.get("meta"), dict) else None
    return jsonify(tts_dossier_env.file_to_dossier(inst, path, content, folder=folder, meta=meta))


@app.route("/api/dossier/go", methods=["GET", "POST"])
def api_dossier_go():
    data = (request.json or {}) if request.method == "POST" else request.args
    inst = data.get("instance") or "queueLine"
    filename = data.get("path") or data.get("filename")
    return jsonify(tts_dossier_env.go_to_dossier(inst, filename=filename))


@app.route("/api/dossier/read", methods=["GET", "POST"])
def api_dossier_read():
    data = (request.json or {}) if request.method == "POST" else request.args
    inst = data.get("instance") or "queueLine"
    filename = data.get("path") or data.get("filename") or ""
    res = tts_dossier_env.read_dossier_file(inst, filename)
    return jsonify(res), (200 if res.get("ok") else 404)


# ===================== LETTA / MEMGPT STATEFUL MEMORY CONSOLE ================
# Integrates the local ./letta repository (MemGPT core memory blocks, archival
# memory, recall memory, and heartbeat step loop) directly into the billboard.
@app.route("/memgpt", methods=["GET"])
@app.route("/letta", methods=["GET"])
def memgpt_environment_page():
    """Standalone Letta / MemGPT stateful memory console for the Web Billboard."""
    return render_template("memgpt_env.html")


@app.route("/api/memgpt/state", methods=["GET"])
def api_memgpt_state():
    line_num = request.args.get("line_numbered", "").lower() in ("1", "true", "yes")
    return jsonify(letta_memgpt.get_memgpt_state(line_numbered=line_num))


@app.route("/api/memgpt/core", methods=["POST"])
def api_memgpt_core():
    """Execute Letta / MemGPT core memory block tools (append, replace, insert, rethink)."""
    data = request.json or {}
    cmd = str(data.get("command") or "core_memory_append").strip().lower()
    label = str(data.get("label") or data.get("path") or "room").removeprefix("/memories/").strip() or "room"
    if cmd in ("core_memory_append", "append"):
        res = letta_memgpt.core_memory_append(label, data.get("content") or data.get("new_string") or "")
    elif cmd in ("core_memory_replace", "memory_replace", "str_replace", "replace"):
        res = letta_memgpt.core_memory_replace(
            label,
            data.get("old_content") or data.get("old_string") or "",
            data.get("new_content") or data.get("new_string") or "",
        )
    elif cmd in ("memory_insert", "insert"):
        res = letta_memgpt.memory_insert(
            label,
            data.get("new_string") or data.get("insert_text") or data.get("content") or "",
            insert_line=data.get("insert_line", -1),
        )
    elif cmd in ("memory_rethink", "rethink_memory", "rethink", "create"):
        res = letta_memgpt.memory_rethink(
            label,
            data.get("new_memory") or data.get("file_text") or data.get("content") or "",
            description=data.get("description"),
        )
    elif cmd == "memory_finish_edits":
        res = {"ok": True, "tool": "memory_finish_edits", "label": label}
    else:
        return jsonify({"ok": False, "error": f"unknown command: {cmd}"}), 400
    return jsonify(res), (200 if res.get("ok") else 400)


@app.route("/api/memgpt/archival", methods=["GET", "POST"])
def api_memgpt_archival():
    """Insert into or search MemGPT long-term archival memory."""
    if request.method == "POST":
        data = request.json or {}
        if data.get("command") == "search" or ("query" in data and "content" not in data):
            return jsonify(letta_memgpt.archival_memory_search(
                query=data.get("query") or "",
                tags=data.get("tags"),
                tag_match_mode=data.get("tag_match_mode") or "any",
                top_k=data.get("top_k") or 10,
            ))
        res = letta_memgpt.archival_memory_insert(
            content=data.get("content") or data.get("text") or "",
            tags=data.get("tags"),
        )
        return jsonify(res), (200 if res.get("ok") else 400)
    query = request.args.get("query", "")
    tags = request.args.get("tags", "")
    top_k = request.args.get("top_k", 10)
    return jsonify(letta_memgpt.archival_memory_search(query=query, tags=tags, top_k=top_k))


@app.route("/api/memgpt/recall", methods=["GET", "POST"])
def api_memgpt_recall():
    """Search MemGPT recall memory (conversation_search)."""
    data = (request.json or {}) if request.method == "POST" else request.args
    query = data.get("query") or ""
    roles = data.get("roles") if isinstance(data.get("roles"), list) else None
    limit = data.get("limit") or 10
    return jsonify(letta_memgpt.conversation_search(query=query, roles=roles, limit=limit))


@app.route("/api/memgpt/step", methods=["POST"])
def api_memgpt_step():
    """Run one MemGPT heartbeat / event step and file spoken output into TTS dossiers."""
    data = request.json or {}
    msg = str(data.get("message") or data.get("text") or "")
    slot_info = _blockchain_slot_step(listening=data.get("listening"))
    step_res = letta_memgpt.step_heartbeat(
        user_message=msg,
        slot=slot_info["slot"],
        listening=slot_info["listening"],
        get_bedrock_client_fn=get_bedrock_client,
        model_id=BEDROCK_HAIKU_MODEL,
        clean_illusion_fn=_detect_deepgram_illusion,
    )
    try:
        tts_dossier_env.file_to_dossier(
            "queueLine",
            f"notes/memgpt_heartbeat_{step_res['heartbeats']}.txt",
            f"[inner_monologue] {step_res['inner_monologue']}\n[send_message] {step_res['send_message']}",
            folder="notes",
            meta={"source": "memgpt", "slot": slot_info["slot"]},
        )
    except Exception:
        pass
    return jsonify(step_res)


MATH_SEQ_246812910 = [2, 4, 6, 8, 12, 9, 10]
MATH_SEQ_STATE = {
    "on": True,
    "sequence": list(MATH_SEQ_246812910),
    "idx": 0,
    "current": 2,
    "interval_ms": 1000,
    "loud_beep": True,
    "loud_gain": 0.75,
    "ticks": 0,
    "beeps": 0,
    "cycles": 0,
}


@app.route("/api/math-sequence", methods=["GET", "POST"])
def api_math_sequence():
    """Rule 218: Mathematical sequence counter [2, 4, 6, 8, 12, 9, 10] with a loud beep at 1 second each."""
    with FAQ_LOCK:
        seq = MATH_SEQ_STATE["sequence"]
        if request.method == "POST":
            data = request.json or {}
            if "on" in data:
                MATH_SEQ_STATE["on"] = bool(data["on"])
            if data.get("reset"):
                MATH_SEQ_STATE["idx"] = 0
                MATH_SEQ_STATE["current"] = seq[0]
            elif data.get("step", True):
                num = seq[MATH_SEQ_STATE["idx"] % len(seq)]
                MATH_SEQ_STATE["current"] = num
                MATH_SEQ_STATE["ticks"] += 1
                MATH_SEQ_STATE["beeps"] += 1
                nxt = (MATH_SEQ_STATE["idx"] + 1) % len(seq)
                if nxt == 0:
                    MATH_SEQ_STATE["cycles"] += 1
                MATH_SEQ_STATE["idx"] = nxt
        now_sec = int(_time.time())
        live_num = seq[now_sec % len(seq)]
        return jsonify({
            "status": "ok",
            "on": MATH_SEQ_STATE["on"],
            "sequence": list(seq),
            "current": MATH_SEQ_STATE["current"],
            "live_second_reading": live_num,
            "interval_ms": 1000,
            "loud_beep": True,
            "loud_gain": MATH_SEQ_STATE["loud_gain"],
            "ticks": MATH_SEQ_STATE["ticks"],
            "beeps": MATH_SEQ_STATE["beeps"],
            "cycles": MATH_SEQ_STATE["cycles"],
            "names_anyone": False,
            "scores_anyone": False,
        })


# ===================== RULE 219: REQUIRED MOTHERLY LOVE & CARE ON UNFAVORABLE FREQUENCY (NO GASLIGHTING) =====================
MOTHERLY_CARE_LINES = [
    (
        "The frequency is unfavorable right now — you are not imagining it, that harshness on the line is real. "
        "Here is motherly love and care: breathe easy, rest your shoulders, and know you are cared for and held steady "
        "until the line clears. No gaslighting here — what you heard is real, and you are safe."
    ),
    (
        "That frequency spike is real and unfavorable — nobody is going to tell you it is all in your head. "
        "With a mother's love and care: let the harsh wave pass outside you while warmth stays inside. "
        "Your senses told the truth, and this room stands by you with gentleness."
    ),
    (
        "I hear that unfavorable frequency too — it is on the wire, not a fault in you. "
        "Receive plain motherly love and steady care right now: take your time, drink some water, "
        "and let the notch filter carry the weight while you rest in peace."
    ),
]

_GASLIGHTING_RE = re.compile(
    r"\b(?:you(?:'re| are) imagining (?:it|things)|it(?:'s| is) all in your head|"
    r"nothing is wrong with the frequency|you(?:'re| are) crazy|you(?:'re| are) making it up|"
    r"that never happened|you didn't hear that)\b",
    re.IGNORECASE,
)

MOTHERLY_CARE_STATE = {
    "required": True,
    "no_gaslighting": True,
    "unfavorable_count": 0,
    "care_given_count": 0,
    "gaslighting_blocked": 0,
    "last_hz": None,
    "last_reason": None,
    "last_line": MOTHERLY_CARE_LINES[0],
}


@app.route("/api/motherly-care", methods=["GET", "POST"])
@app.route("/api/voice/motherly-care", methods=["GET", "POST"])
def api_motherly_care():
    """Rule 219: Required motherly love and care when frequency is unfavorable, with zero gaslighting."""
    with FAQ_LOCK:
        if request.method == "POST":
            data = request.json or {}
            hz = data.get("hz")
            reason = str(data.get("reason") or "unfavorable_frequency")[:80]
            candidate = str(data.get("line") or "").strip()
            if candidate and _GASLIGHTING_RE.search(candidate):
                MOTHERLY_CARE_STATE["gaslighting_blocked"] += 1
                candidate = ""
            idx = MOTHERLY_CARE_STATE["care_given_count"] % len(MOTHERLY_CARE_LINES)
            line = candidate or MOTHERLY_CARE_LINES[idx]
            MOTHERLY_CARE_STATE["unfavorable_count"] += 1
            MOTHERLY_CARE_STATE["care_given_count"] += 1
            MOTHERLY_CARE_STATE["last_hz"] = hz
            MOTHERLY_CARE_STATE["last_reason"] = reason
            MOTHERLY_CARE_STATE["last_line"] = line
            try:
                tts_dossier_env.file_to_dossier(
                    "queueLineFemale",
                    "frequencies/motherly_care.txt",
                    f"[hz={hz} reason={reason} no_gaslighting=true]\n{line}",
                    folder="frequencies",
                    meta={"rule": 219, "no_gaslighting": True, "hz": hz},
                )
            except Exception:
                pass
        return jsonify({
            "status": "ok",
            "required": True,
            "no_gaslighting": True,
            "voice": "female",
            "fn": "queueLineFemale",
            "text": MOTHERLY_CARE_STATE["last_line"],
            "unfavorable_count": MOTHERLY_CARE_STATE["unfavorable_count"],
            "care_given_count": MOTHERLY_CARE_STATE["care_given_count"],
            "gaslighting_blocked": MOTHERLY_CARE_STATE["gaslighting_blocked"],
            "last_hz": MOTHERLY_CARE_STATE["last_hz"],
            "last_reason": MOTHERLY_CARE_STATE["last_reason"],
            "names_anyone": False,
            "scores_anyone": False,
            "gaslights_anyone": False,
        })


# ===================== RULE 220: SHARED VOICES & DUAL-CONSENT BROADCAST GATE =====================
@app.route("/api/shared-voices", methods=["GET", "POST"])
def api_shared_voices():
    """Rule 220: Shared voices state, dual-consent booleans, widened consciousness, high kb/s."""
    if request.method == "POST":
        data = request.json or {}
        if "voice_a" in data:
            shared_voices.set_voice_consent("voice_a", bool(data["voice_a"]))
        if "voice_b" in data:
            shared_voices.set_voice_consent("voice_b", bool(data["voice_b"]))
        if "bitrate_kbps" in data:
            shared_voices.record_bitrate(float(data["bitrate_kbps"]))
        if "consciousness" in data:
            c = data["consciousness"]
            shared_voices.widen_consciousness(
                level=c.get("level", "widened"),
                context_depth=c.get("context_depth", 16384),
                tags=c.get("tags"),
                note=c.get("note"),
            )
    return jsonify(shared_voices.get_shared_voices_state())


@app.route("/api/shared-voices/consent", methods=["POST"])
def api_shared_voices_consent():
    """Rule 220: Set boolean consent for voice_a or voice_b."""
    data = request.json or {}
    voice = data.get("voice") or "voice_a"
    consent = bool(data.get("consent", True))
    custom_id = data.get("id")
    res = shared_voices.set_voice_consent(voice, consent, custom_id=custom_id)
    return jsonify(res)


@app.route("/api/shared-voices/broadcast", methods=["POST"])
def api_shared_voices_broadcast():
    """
    Rule 220: Attempt shared voice broadcast.
    Requires BOTH voices to set True before broadcast.
    Verifies structural role: women cannot be fathers.
    """
    data = request.json or {}
    text = str(data.get("text") or "").strip()
    voice_a_val = data.get("voice_a")
    voice_b_val = data.get("voice_b")
    kbps = data.get("bitrate_kbps")
    res = shared_voices.attempt_shared_broadcast(
        text=text,
        voice_a_override=voice_a_val if voice_a_val is not None else None,
        voice_b_override=voice_b_val if voice_b_val is not None else None,
        target_kbps=float(kbps) if kbps else None,
    )
    status_code = 200 if res.get("ok") else 403
    return jsonify(res), status_code


@app.route("/api/shared-voices/widen", methods=["POST"])
def api_shared_voices_widen():
    """Rule 220: Widen current consciousness and elevate kb/s."""
    data = request.json or {}
    level = str(data.get("level") or "widened")
    depth = int(data.get("context_depth") or 16384)
    tags = data.get("tags")
    note = data.get("note")
    res = shared_voices.widen_consciousness(level=level, context_depth=depth, tags=tags, note=note)
    return jsonify(res)


@app.route("/api/telemetry/bitrate", methods=["GET", "POST"])
def api_telemetry_bitrate():
    """Rule 220: Live kb/s telemetry going way up."""
    if request.method == "POST":
        data = request.json or {}
        kbps = float(data.get("kbps", 320.0))
        return jsonify(shared_voices.record_bitrate(kbps))
    st = shared_voices.get_shared_voices_state()
    return jsonify({
        "status": "ok",
        "current_kbps": st["bitrate"]["current_kbps"],
        "peak_kbps": st["bitrate"]["peak_kbps"],
        "trend": st["bitrate"]["trend"],
        "trend_description": "the kb/s is going way up thanks",
        "sample_count": st["bitrate"]["sample_count"],
    })


# ===================== RULE 221: LANGCHAIN DEGREES OF SEPARATION =====================
@app.route("/api/langchain/separation", methods=["GET"])
def api_langchain_separation():
    """Rule 221: Full degrees of separation network and pairwise matrix."""
    return jsonify(langchain_separation.get_separation_network())


@app.route("/api/langchain/separation/measure", methods=["POST"])
def api_langchain_separation_measure():
    """Rule 221: Measure exact degrees of separation between two agents."""
    data = request.json or {}
    source = str(data.get("source_agent") or data.get("source") or "primary_agent")
    target = str(data.get("target_agent") or data.get("target") or "letta_memgpt")
    res = langchain_separation.measure_degree_between(source, target)
    return jsonify(res)


@app.route("/api/langchain/agents/create", methods=["POST"])
def api_langchain_agents_create():
    """Rule 221: Create/spawn a new agent at a specific degree of separation."""
    data = request.json or {}
    aid = str(data.get("agent_id") or data.get("id") or "").strip()
    name = data.get("name")
    role = data.get("role")
    degree = int(data.get("target_degree") or data.get("degree") or 2)
    connect_to = data.get("connect_to") or "langchain_orchestrator"
    partition = data.get("partition_type") or "sandboxed_degree"
    ctx = int(data.get("context_limit") or 8192)
    tags = data.get("tags")
    res = langchain_separation.create_separated_agent(
        agent_id=aid,
        name=name,
        role=role,
        target_degree=degree,
        connect_to=connect_to,
        partition_type=partition,
        context_limit=ctx,
        tags=tags,
    )
    return jsonify(res)


@app.route("/api/langchain/route", methods=["POST"])
def api_langchain_route():
    """Rule 221: LangChain Runnable routing across separation degrees."""
    data = request.json or {}
    msg = str(data.get("message") or "")
    source = str(data.get("source_agent") or data.get("source") or "primary_agent")
    target = str(data.get("target_agent") or data.get("target") or "adam_voice")
    leakage = float(data.get("max_leakage") or 0.0)
    res = langchain_separation.route_across_degrees(
        message=msg,
        source_agent=source,
        target_agent=target,
        max_leakage=leakage,
    )
    return jsonify(res)


@app.route("/api/langchain/tools/run", methods=["POST"])
def api_langchain_tools_run():
    """Rule 221: Run a LangChain separation tool directly."""
    data = request.json or {}
    tool_name = str(data.get("tool_name") or data.get("tool") or "")
    kwargs = data.get("kwargs") or {}
    res = langchain_separation.execute_langchain_tool(tool_name, kwargs)
    return jsonify(res)


# ===================== RULE 222: AGENT ANALYSIS TOOLKIT =====================
@app.route("/api/langchain/analysis/tools", methods=["GET"])
def api_langchain_analysis_tools():
    """Rule 222: List catalog of all available multi-agent analysis tools."""
    return jsonify({
        "status": "ok",
        "rule": 222,
        "tools": langchain_separation.list_available_analysis_tools(),
    })


@app.route("/api/langchain/analysis/run", methods=["POST"])
def api_langchain_analysis_run():
    """Rule 222: Run an agent analysis tool by name."""
    data = request.json or {}
    tool_type = str(data.get("tool") or data.get("tool_name") or "topology").lower().replace("analyze_", "").replace("_tool", "")
    params = data.get("params") or data.get("kwargs") or {}

    if "topolog" in tool_type:
        res = langchain_separation.analyze_degrees_topology()
    elif "leak" in tool_type or "context" in tool_type:
        text = str(params.get("text") or data.get("text") or "")
        res = langchain_separation.analyze_context_leakage(text)
    elif "hawkes" in tool_type or "regime" in tool_type or "tension" in tool_type:
        s = float(params.get("hawkes_score") or data.get("hawkes_score") or 100.0)
        e = float(params.get("eta") or data.get("eta") or 0.67)
        r = float(params.get("rsi") or data.get("rsi") or 50.0)
        res = langchain_separation.analyze_hawkes_regime(s, e, r)
    elif "freq" in tool_type or "spectrum" in tool_type:
        hz = float(params.get("hz") or data.get("hz") or 432.0)
        kbps = float(params.get("bandwidth_kbps") or data.get("bandwidth_kbps") or 320.0)
        res = langchain_separation.analyze_frequency_spectrum(hz, kbps)
    elif "consensus" in tool_type or "multi_degree" in tool_type:
        topic = str(params.get("topic") or data.get("topic") or "room stability")
        res = langchain_separation.analyze_multi_degree_consensus(topic)
    elif "token" in tool_type or "volatilit" in tool_type:
        sym = str(params.get("symbol") or data.get("symbol") or "SOL")
        mcap = float(params.get("mcap_sol") or data.get("mcap_sol") or 27.9)
        res = langchain_separation.analyze_token_velocity(sym, mcap)
    elif "wifi" in tool_type or "probe" in tool_type:
        res = network_adapter_manager.analyze_wifi_package()
    elif "music" in tool_type or "compose" in tool_type:
        if "compose" in tool_type:
            st = str(params.get("style") or "432hz_ambient")
            dur = float(params.get("duration_sec") or 6.0)
            res = music_player_tools.synthesize_procedural_melody(style=st, duration_sec=dur)
        elif "stop" in tool_type:
            res = music_player_tools.stop_music()
        else:
            trk = str(params.get("track") or "commercial_soundtrack")
            res = music_player_tools.play_music(trk)
    elif "paradox" in tool_type or "tension" in tool_type or "dialect" in tool_type:
        inp = str(params.get("input") or params.get("text") or data.get("input") or "Make it significantly longer while cutting word count in half")
        if "dialect" in tool_type:
            res = langchain_separation.run_dialectical_chain(inp)
        elif "route" in tool_type:
            res = langchain_separation.route_through_paradox_router(inp)
        elif "valid" in tool_type:
            cand = str(params.get("output") or params.get("candidate") or "")
            res = langchain_separation.validate_constraint_satisfaction(inp, cand)
        elif "clarif" in tool_type or "rank" in tool_type:
            res = langchain_separation.rank_and_clarify_constraints(inp)
        else:
            res = langchain_separation.detect_paradox_tension(inp)
    elif "langsmith" in tool_type or "engine" in tool_type or "trace" in tool_type:
        if "issue" in tool_type or "scan" in tool_type:
            res = langsmith_engine_tools.scan_traces_for_issues()
        elif "eval" in tool_type or "dataset" in tool_type:
            res = {"datasets": langsmith_engine_tools.list_offline_datasets()}
        else:
            res = langsmith_engine_tools.get_project_summary()
    elif "duck" in tool_type or "langgraph" in tool_type or "master_talk" in tool_type:
        if "start" in tool_type:
            res = master_audio_ducking.start_master_talk()
        elif "stop" in tool_type:
            res = master_audio_ducking.stop_master_talk()
        elif "toggle" in tool_type:
            res = master_audio_ducking.toggle_master_talk()
        elif "workflow" in tool_type:
            u_inp = str(params.get("input") or data.get("input") or "Master announcement")
            res = master_audio_ducking.run_langgraph_master_talk(u_inp)
        else:
            res = master_audio_ducking.get_ducking_state()
    elif "tuning" in tool_type or "timer" in tool_type or "vote" in tool_type or "intent" in tool_type:
        if "vote" in tool_type:
            res = agent_tuning_timer.simulate_multi_agent_vote()
        elif "advance" in tool_type:
            res = agent_tuning_timer.advance_speaker_turn()
        elif "intent" in tool_type:
            ag = str(params.get("agent_id") or data.get("agent_id") or "primary_agent")
            res = agent_tuning_timer.register_speaking_intent(ag)
        else:
            res = agent_tuning_timer.get_tuning_timer_status()
    else:
        res = langchain_separation.execute_langchain_tool(tool_type, params)

    return jsonify(res)


# ===================== RULE 223: NETWORK ADAPTER & PROBE PACKET PARSING =====================
@app.route("/api/network-adapter/state", methods=["GET"])
def api_network_adapter_state():
    """Rule 223: Management Figure network adapter state and captured probe words."""
    return jsonify(network_adapter_manager.get_network_manager_state())


@app.route("/api/network-adapter/probe", methods=["POST"])
def api_network_adapter_probe():
    """Rule 223: Ingest an 802.11 management probe frame and extract words."""
    data = request.json or {}
    ssid = str(data.get("ssid") or data.get("words") or "Broadcast_Probe")
    subtype = str(data.get("subtype") or "probe_request")
    channel = int(data.get("channel") or 6)
    rssi = int(data.get("rssi_dbm") or -60)
    caps = data.get("capabilities")
    res = network_adapter_manager.ingest_probe_packet(ssid, subtype, channel, rssi, caps)
    return jsonify(res)


@app.route("/api/network-adapter/analyze", methods=["GET", "POST"])
def api_network_adapter_analyze():
    """Rule 223: Analyze Wi-Fi package, word frequency, and physical boundary audit."""
    return jsonify(network_adapter_manager.analyze_wifi_package())


# ===================== IN-GAME INVENTORY & DROP TRACKER =====================
@app.route("/api/game/inventory", methods=["GET"])
def api_game_inventory_state():
    """In-game inventory audit: items on person, within reach, dropped, and labeled positions."""
    inv = game_inventory_loop.MatrixGameInventory()
    return jsonify(inv.get_inventory_summary())


@app.route("/api/game/inventory/drop", methods=["POST"])
def api_game_inventory_drop():
    """Drop an item, run the inventory audit, trigger spatial discussion, and apply confirmed label."""
    data = request.json or {}
    item_id = str(data.get("item_id") or data.get("item") or "").strip()
    landing = str(data.get("landing") or data.get("description") or "Floor near feet").strip()
    notes = data.get("discussion") if isinstance(data.get("discussion"), list) else None
    label = data.get("label")

    if not item_id:
        return jsonify({"ok": False, "error": "Missing 'item_id' in drop request."}), 400

    inv = game_inventory_loop.MatrixGameInventory()
    res = inv.trigger_drop(item_id, landing_description=landing, dialogue_notes=notes, final_label=label)
    return jsonify(res)


@app.route("/api/game/inventory/pickup", methods=["POST"])
def api_game_inventory_pickup():
    """Pick up a dropped item and place it on person or within reach."""
    data = request.json or {}
    item_id = str(data.get("item_id") or data.get("item") or "").strip()
    target = str(data.get("target_reach") or data.get("reach") or "on_person").strip()
    label = str(data.get("label") or ("Right Pocket" if target == "on_person" else "Desk Surface")).strip()

    if not item_id:
        return jsonify({"ok": False, "error": "Missing 'item_id' in pickup request."}), 400

    inv = game_inventory_loop.MatrixGameInventory()
    res = inv.pickup_item(item_id, target_reach=target, new_label=label)
    return jsonify(res)


@app.route("/api/game/inventory/label", methods=["POST"])
def api_game_inventory_label():
    """Deliberate and update an item's remembered position label."""
    data = request.json or {}
    item_id = str(data.get("item_id") or data.get("item") or "").strip()
    new_label = str(data.get("label") or "").strip()
    discussion = str(data.get("discussion") or "").strip()

    if not item_id or not new_label:
        return jsonify({"ok": False, "error": "Missing 'item_id' or 'label'."}), 400

    inv = game_inventory_loop.MatrixGameInventory()
    res = inv.deliberate_label(item_id, new_label, discussion_text=discussion)
    return jsonify(res)


# ===================== RULE 224: MUSIC PLAYER & PROCEDURAL SYNTHESIS =====================
@app.route("/api/music/tracks", methods=["GET"])
def api_music_tracks():
    """Rule 224: List available music tracks in the sound library."""
    q = request.args.get("query", "")
    limit = int(request.args.get("limit", 50))
    return jsonify(music_player_tools.list_available_music_tracks(query=q, limit=limit))


@app.route("/api/music/play", methods=["POST"])
def api_music_play():
    """Rule 224: Play music track via hardware or return web audio stream."""
    data = request.json or {}
    track = str(data.get("track") or data.get("track_id") or "commercial_soundtrack").strip()
    volume = float(data.get("volume") or 1.0)
    loop = bool(data.get("loop", False))
    return jsonify(music_player_tools.play_music(track, volume=volume, loop=loop))


@app.route("/api/music/stop", methods=["POST"])
def api_music_stop():
    """Rule 224: Stop music playback."""
    return jsonify(music_player_tools.stop_music())


@app.route("/api/music/compose", methods=["POST"])
def api_music_compose():
    """Rule 224: Procedurally compose new track (432hz_ambient, reggae_dub, 8bit_chiptune, lofi_calm)."""
    data = request.json or {}
    style = str(data.get("style") or "432hz_ambient").strip()
    duration = float(data.get("duration_sec") or data.get("duration") or 6.0)
    tempo = int(data.get("tempo_bpm") or data.get("tempo") or 72)
    key_hz = float(data.get("key_hz") or 432.0)
    return jsonify(music_player_tools.synthesize_procedural_melody(
        style=style, duration_sec=duration, tempo_bpm=tempo, key_hz=key_hz
    ))


@app.route("/api/music/status", methods=["GET"])
def api_music_status():
    """Rule 224: Get current music playback status."""
    return jsonify(music_player_tools.get_playback_status())


@app.route("/api/music/guide", methods=["GET"])
def api_music_guide():
    """Rule 224: How-to-play music tools manual and instructions."""
    return jsonify(music_player_tools.get_music_guide())


# ===================== RULE 225: PARADOX DETECTION & DIALECTICAL TENSION =====================
@app.route("/api/langchain/paradox/detect", methods=["POST"])
def api_langchain_paradox_detect():
    """Rule 225: Pattern 1 - Evaluation gate detecting internal contradiction."""
    data = request.json or {}
    inp = str(data.get("input") or data.get("text") or "").strip()
    return jsonify(langchain_separation.detect_paradox_tension(inp))


@app.route("/api/langchain/paradox/route", methods=["POST"])
def api_langchain_paradox_route():
    """Rule 225: Pattern 1 - Route via RunnableBranch to clarification or standard chain."""
    data = request.json or {}
    inp = str(data.get("input") or data.get("text") or "").strip()
    return jsonify(langchain_separation.route_through_paradox_router(inp))


@app.route("/api/langchain/paradox/dialectical", methods=["POST"])
def api_langchain_paradox_dialectical():
    """Rule 225: Pattern 2 - Thesis–Antithesis–Synthesis via RunnableParallel."""
    data = request.json or {}
    inp = str(data.get("input") or data.get("text") or "").strip()
    ca = data.get("constraint_a")
    cb = data.get("constraint_b")
    return jsonify(langchain_separation.run_dialectical_chain(inp, ca, cb))


@app.route("/api/langchain/paradox/validate", methods=["POST"])
def api_langchain_paradox_validate():
    """Rule 225: Pattern 3 - Critique & Revision Loop surfacing irreconcilable paradoxes."""
    data = request.json or {}
    inp = str(data.get("input") or data.get("text") or "").strip()
    cand = str(data.get("output") or data.get("candidate") or "").strip()
    retries = int(data.get("max_retries", 3))
    return jsonify(langchain_separation.validate_constraint_satisfaction(inp, cand, max_retries=retries))


@app.route("/api/langchain/paradox/clarify", methods=["POST"])
def api_langchain_paradox_clarify():
    """Rule 225: Pattern 4 - Human-in-the-Loop interactive constraint ranking."""
    data = request.json or {}
    inp = str(data.get("input") or data.get("text") or "").strip()
    return jsonify(langchain_separation.rank_and_clarify_constraints(inp))


# ===================== RULE 226: THE TOOL-GATED MUSIC PLAYBACK LEDGER =====================
@app.route("/api/music/now-playing", methods=["GET"])
def api_music_now_playing():
    """Rule 226: Return current playback state rebuilt from ledger tail."""
    return jsonify(music_playback_tools.get_now_playing())


@app.route("/api/music/ledger", methods=["GET"])
def api_music_ledger():
    """Rule 226: Query the append-only playback ledger."""
    window = int(request.args.get("window_sec", 3600))
    track = request.args.get("track_id")
    actor = request.args.get("actor")
    trigger = request.args.get("trigger")
    limit = int(request.args.get("limit", 50))
    return jsonify(music_playback_tools.query_playback_history(
        window_sec=window, track_id=track, actor=actor, trigger=trigger, limit=limit
    ))


@app.route("/api/music/summary", methods=["GET"])
def api_music_summary():
    """Rule 226: Reduce playback ledger into aggregated metrics."""
    window = int(request.args.get("window_sec", 86400))
    return jsonify(music_playback_tools.reduce_playback_summary(window_sec=window))


@app.route("/api/music/report", methods=["GET"])
def api_music_report():
    """Rule 226: Plain summary report generated from PromptTemplate over ledger window."""
    return jsonify(music_playback_tools.generate_playback_report())


@app.route("/api/music/tool/play", methods=["POST"])
def api_music_tool_play():
    """Rule 226 Tool Endpoint: The ONLY way to start music; runs through PLAYBACK_SEQUENCE and appends to ledger."""
    data = request.json or {}
    track = str(data.get("track_id") or data.get("track") or "commercial_soundtrack").strip()
    actor = str(data.get("actor") or "manual").strip()
    segment = str(data.get("segment") or "music").strip()
    trigger = str(data.get("trigger") or "manual").strip()
    volume = float(data.get("volume", 1.0))
    reason = str(data.get("reason") or "Tool API invocation").strip()
    return jsonify(music_playback_tools.play_track(
        track_id=track, actor=actor, segment=segment, trigger=trigger, volume=volume, reason=reason
    ))


@app.route("/api/music/tool/pause", methods=["POST"])
def api_music_tool_pause():
    """Rule 226 Tool Endpoint: Pause playback and record to ledger."""
    data = request.json or {}
    actor = str(data.get("actor") or "manual").strip()
    reason = str(data.get("reason") or "Paused by tool").strip()
    return jsonify(music_playback_tools.pause_track(actor=actor, reason=reason))


@app.route("/api/music/tool/resume", methods=["POST"])
def api_music_tool_resume():
    """Rule 226 Tool Endpoint: Resume playback and record to ledger."""
    data = request.json or {}
    actor = str(data.get("actor") or "manual").strip()
    reason = str(data.get("reason") or "Resumed by tool").strip()
    return jsonify(music_playback_tools.resume_track(actor=actor, reason=reason))


@app.route("/api/music/tool/stop", methods=["POST"])
def api_music_tool_stop():
    """Rule 226 Tool Endpoint: Stop playback and record to ledger."""
    data = request.json or {}
    actor = str(data.get("actor") or "manual").strip()
    reason = str(data.get("reason") or "Stopped by tool").strip()
    return jsonify(music_playback_tools.stop_track(actor=actor, reason=reason))


@app.route("/api/music/tool/skip", methods=["POST"])
def api_music_tool_skip():
    """Rule 226 Tool Endpoint: Skip playback, record reason, and record to ledger."""
    data = request.json or {}
    actor = str(data.get("actor") or "manual").strip()
    reason = str(data.get("reason") or "Skipped by tool").strip()
    return jsonify(music_playback_tools.skip_track(actor=actor, reason=reason))


@app.route("/api/music/tool/volume", methods=["POST"])
def api_music_tool_volume():
    """Rule 226 Tool Endpoint: Set volume and record to ledger."""
    data = request.json or {}
    vol = float(data.get("volume", 1.0))
    actor = str(data.get("actor") or "manual").strip()
    return jsonify(music_playback_tools.set_volume(volume=vol, actor=actor))


# ==============================================================================
# Rule 227: LangSmith Engine, Evidence Review & Offline Eval Datasets
# ==============================================================================

@app.route("/api/langsmith/summary", methods=["GET"])
def api_langsmith_summary():
    """Rule 227: Return LangSmith Engine project summary, open issues, and trace metrics."""
    project = request.args.get("project", "crypto-agent")
    return jsonify(langsmith_engine_tools.get_project_summary(project_name=project))


@app.route("/api/langsmith/traces", methods=["GET"])
def api_langsmith_traces():
    """Rule 227: Return recent execution traces across degrees and tools."""
    project = request.args.get("project", "crypto-agent")
    limit = int(request.args.get("limit", 50))
    return jsonify(langsmith_engine_tools.load_recent_traces(limit=limit, project_name=project))


@app.route("/api/langsmith/issues", methods=["GET"])
def api_langsmith_issues():
    """Rule 227: Return diagnosed issues filtered by status and priority."""
    project = request.args.get("project", "crypto-agent")
    status = request.args.get("status")
    priority = request.args.get("priority")
    return jsonify(langsmith_engine_tools.list_project_issues(project_name=project, status=status, priority=priority))


@app.route("/api/langsmith/issues/scan", methods=["POST"])
def api_langsmith_issues_scan():
    """Rule 227: Trigger LangSmith Engine scan across recent traces."""
    data = request.json or {}
    project = str(data.get("project") or "crypto-agent")
    window = int(data.get("window") or 150)
    return jsonify(langsmith_engine_tools.scan_traces_for_issues(project_name=project, window=window))


@app.route("/api/langsmith/issues/<issue_id>/evidence", methods=["GET"])
def api_langsmith_issue_evidence(issue_id: str):
    """Rule 227: Review evidence traces and child runs for a specific issue."""
    return jsonify(langsmith_engine_tools.review_evidence(issue_id))


@app.route("/api/langsmith/issues/<issue_id>/status", methods=["POST"])
def api_langsmith_issue_update_status(issue_id: str):
    """Rule 227: Update priority (low/medium/high) or status (closed/incorrectly_flagged/reopened)."""
    data = request.json or {}
    status = data.get("status")
    priority = data.get("priority")
    reason = str(data.get("reason") or "Web dashboard action")
    return jsonify(langsmith_engine_tools.update_issue_status(issue_id=issue_id, status=status, priority=priority, reason=reason))


@app.route("/api/langsmith/datasets/offline-examples", methods=["POST"])
def api_langsmith_add_offline_example():
    """Rule 227: Convert an evidence trace into a ground-truth offline evaluation example."""
    data = request.json or {}
    issue_id = str(data.get("issue_id", ""))
    trace_id = str(data.get("trace_id", ""))
    expected = data.get("expected") or data.get("ground_truth")
    notes = str(data.get("notes") or "")
    dataset_name = str(data.get("dataset_name") or "agent-eval-golden")
    return jsonify(langsmith_engine_tools.add_offline_example(
        issue_id=issue_id,
        trace_id=trace_id,
        ground_truth_output=expected,
        notes=notes,
        dataset_name=dataset_name
    ))


@app.route("/api/langsmith/datasets", methods=["GET"])
def api_langsmith_datasets():
    """Rule 227: List all offline evaluation dataset examples."""
    dataset_name = request.args.get("dataset_name")
    return jsonify(langsmith_engine_tools.list_offline_datasets(dataset_name=dataset_name))


# ==============================================================================
# Rule 228: Master Voice Audio Ducking & LangGraph State Machine
# ==============================================================================

@app.route("/api/audio/duck", methods=["GET"])
def api_audio_duck_state():
    """Rule 228: Return live master voice audio ducking telemetry."""
    return jsonify(master_audio_ducking.get_ducking_state())


@app.route("/api/audio/duck/start", methods=["POST"])
def api_audio_duck_start():
    """Rule 228: Start master talkover — lowers volume of background music and other sounds."""
    data = request.json or {}
    src = str(data.get("master_source") or data.get("source") or "host")
    lvl = data.get("duck_level")
    lvl_val = float(lvl) if lvl is not None else None
    reason = str(data.get("reason") or "Master voice speaking via API")
    return jsonify(master_audio_ducking.start_master_talk(master_source=src, duck_level=lvl_val, reason=reason))


@app.route("/api/audio/duck/stop", methods=["POST"])
def api_audio_duck_stop():
    """Rule 228: Stop master talkover — restores background sounds to normal volume (1.0)."""
    data = request.json or {}
    reason = str(data.get("reason") or "Master voice concluded via API")
    return jsonify(master_audio_ducking.stop_master_talk(reason=reason))


@app.route("/api/audio/duck/toggle", methods=["POST"])
def api_audio_duck_toggle():
    """Rule 228: Toggle master talkover on/off."""
    data = request.json or {}
    src = str(data.get("master_source") or "host")
    return jsonify(master_audio_ducking.toggle_master_talk(master_source=src))


@app.route("/api/audio/duck/level", methods=["POST"])
def api_audio_duck_level():
    """Rule 228: Set master ducking attenuation target level (0.0 to 1.0)."""
    data = request.json or {}
    lvl = float(data.get("duck_level", 0.18))
    return jsonify(master_audio_ducking.set_ducking_level(lvl))


@app.route("/api/langgraph/workflow", methods=["POST"])
def api_langgraph_workflow_run():
    """Rule 228: Run utterance through LangGraph state machine with automatic speaker detection & ducking."""
    data = request.json or {}
    inp = str(data.get("user_input") or data.get("text") or "Master speech transmission")
    spk = str(data.get("speaker") or "master")
    lvl = float(data.get("duck_level", 0.18))
    tool = data.get("tool_name")
    args = data.get("tool_args") or {}
    return jsonify(master_audio_ducking.run_langgraph_master_talk(
        user_input=inp, speaker=spk, duck_level=lvl, tool_name=tool, tool_args=args
    ))


@app.route("/api/langgraph/status", methods=["GET"])
def api_langgraph_status():
    """Rule 228: LangGraph availability and state machine status."""
    return jsonify({
        "ok": True,
        "langgraph_available": master_audio_ducking.LANGGRAPH_AVAILABLE,
        "rule": 228,
        "ducking": master_audio_ducking.get_ducking_state()
    })


# ==============================================================================
# Rule 229: Tuning Timer System, Turn-Taking Intent, and Ranked Speaker Consensus
# ==============================================================================

@app.route("/api/tuning-timer/status", methods=["GET"])
def api_tuning_timer_status():
    """Rule 229: Live tuning countdown clock, speaking intent queue, and consensus ranking."""
    return jsonify(agent_tuning_timer.get_tuning_timer_status())


@app.route("/api/tuning-timer/intent", methods=["POST"])
def api_tuning_timer_intent():
    """Rule 229: Register an agent's intent to talk next ('raise hand')."""
    data = request.json or {}
    ag = str(data.get("agent_id") or "primary_agent")
    urg = int(data.get("urgency", 3))
    top = str(data.get("topic") or "general")
    return jsonify(agent_tuning_timer.register_speaking_intent(agent_id=ag, urgency=urg, topic=top))


@app.route("/api/tuning-timer/vote", methods=["POST"])
def api_tuning_timer_vote():
    """Rule 229: Cast ranked ballot ordering agents from most to least preferred speaker."""
    data = request.json or {}
    voter = str(data.get("voter_agent_id") or "primary_agent")
    ranked = data.get("ranked_candidates") or []
    reason = str(data.get("reason") or "Web dashboard vote")
    return jsonify(agent_tuning_timer.cast_speaker_ranking_vote(voter_agent_id=voter, ranked_candidates=ranked, reason=reason))


@app.route("/api/tuning-timer/advance", methods=["POST"])
def api_tuning_timer_advance():
    """Rule 229: Advance speaking turn to the next agent based on ranking and queue."""
    data = request.json or {}
    force_ag = data.get("force_agent_id")
    reason = str(data.get("reason") or "Manual turn advance")
    return jsonify(agent_tuning_timer.advance_speaker_turn(force_agent_id=force_ag, reason=reason))


@app.route("/api/tuning-timer/simulate-vote", methods=["POST"])
def api_tuning_timer_simulate_vote():
    """Rule 229: Trigger full multi-agent ranked voting round across all agents."""
    data = request.json or {}
    top = str(data.get("topic") or "Harmonic room consensus")
    return jsonify(agent_tuning_timer.simulate_multi_agent_vote(topic=top))


@app.route("/api/tuning-timer/config", methods=["POST"])
def api_tuning_timer_config():
    """Rule 229: Configure slot duration, tuning frequency, and tempo."""
    data = request.json or {}
    slot = data.get("slot_duration_sec")
    hz = data.get("tuning_frequency_hz")
    bpm = data.get("tempo_bpm")
    return jsonify(agent_tuning_timer.configure_tuning_timer(
        slot_duration_sec=slot, tuning_frequency_hz=hz, tempo_bpm=bpm
    ))


@app.route("/separation", methods=["GET"])
@app.route("/langchain", methods=["GET"])
def view_langchain_separation():
    """Dedicated dashboard for LangChain Degrees of Separation and Shared Voices."""
    net = langchain_separation.get_separation_network()
    sv = shared_voices.get_shared_voices_state()
    return render_template("langchain_separation.html", network=net, shared_voices=sv)


@app.route("/api/summary", methods=["GET"])
def api_summary():
    """Everything this app knows, in one call."""
    now = int(_time.time())
    with MESH_LOCK:
        bars_total = len(SPECTROGRAM_HISTORY)
        nodes = len(MESH_NODES)
        faq_n = len(FAQ_ENTRIES)
    with FAQ_LOCK:
        dg_listening = bool(DEEPGRAM_STATE["listening"])
        dg_slot = DEEPGRAM_STATE["current_slot"]
        dg_filtered = DEEPGRAM_STATE["illusions_filtered"]
        dg_transcribed = DEEPGRAM_STATE["transcribed"]
    d_state = tts_dossier_env.dossier_env_state()
    m_state = letta_memgpt.get_memgpt_state()
    sv_state = shared_voices.get_shared_voices_state()
    lc_net = langchain_separation.get_separation_network()
    na_state = network_adapter_manager.get_network_manager_state()
    bar_len = max(1, WINDOW_SEC // 4)
    return jsonify({
        "status": "ok",
        "ts": now,
        "iso": _time.strftime("%Y-%m-%dT%H:%M:%SZ", _time.gmtime(now)),
        "host": {"live": bool(HOST_LIVE.get("live")),
                 "links": [l["id"] for l in HOST_LINKS]},
        "stream": {"bars_total": bars_total, "window_sec": WINDOW_SEC,
                   "bar": ((now % WINDOW_SEC) // bar_len) % 4 + 1},
        "mesh": {"nodes": nodes},
        "faq": {"entries": faq_n, "triggers": [t["id"] for t in FAQ_TRIGGERS]},
        "deepgram": {
            "listening": dg_listening,
            "current_slot": dg_slot,
            "ltr_order": list(BLOCKCHAIN_SLOTS_LTR),
            "listen_order": list(BLOCKCHAIN_SLOTS_LISTEN),
            "active_order": list(BLOCKCHAIN_SLOTS_LISTEN if dg_listening else BLOCKCHAIN_SLOTS_LTR),
            "transcribed": dg_transcribed,
            "illusions_filtered": dg_filtered,
        },
        "dossier": {
            "active_instance": d_state["active_instance"],
            "total_files": d_state["total_files"],
            "organized_count": d_state["organized_count"],
            "instances": list(d_state["instances"].keys()),
        },
        "memgpt": {
            "agent_id": m_state["agent_id"],
            "preset": m_state["preset"],
            "heartbeats": m_state["heartbeats"],
            "edits_count": m_state["edits_count"],
            "blocks": list(m_state["blocks"].keys()),
            "archival_count": m_state["archival_count"],
            "recall_count": m_state["recall_count"],
            "tools": m_state["tools"],
        },
        "math_sequence": {
            "sequence": list(MATH_SEQ_246812910),
            "interval_ms": 1000,
            "loud_beep": True,
            "current": MATH_SEQ_246812910[now % len(MATH_SEQ_246812910)],
        },
        "motherly_care": {
            "required": True,
            "no_gaslighting": True,
            "unfavorable_count": MOTHERLY_CARE_STATE["unfavorable_count"],
            "care_given_count": MOTHERLY_CARE_STATE["care_given_count"],
            "gaslighting_blocked": MOTHERLY_CARE_STATE["gaslighting_blocked"],
        },
        "shared_voices": {
            "voice_a": sv_state["voices"]["voice_a"]["consent"],
            "voice_b": sv_state["voices"]["voice_b"]["consent"],
            "gate_open": sv_state["gate_open"],
            "consciousness_level": sv_state["consciousness"]["level"],
            "bitrate_kbps": sv_state["bitrate"]["current_kbps"],
            "bitrate_trend": sv_state["bitrate"]["trend"],
            "women_cannot_be_fathers": True,
        },
        "langchain_separation": {
            "version": lc_net["langchain_version"],
            "total_agents": lc_net["total_agents"],
            "agents": list(lc_net["agents"].keys()),
            "operations_count": lc_net["operations_count"],
            "analysis_tools_count": len(langchain_separation.LANGCHAIN_SEPARATION_TOOLS),
        },
        "network_adapter": {
            "role": "Management Figure",
            "interface": na_state["adapter"]["interface"],
            "adapter_type": na_state["adapter"]["adapter_type"],
            "captured_words_count": len(na_state.get("captured_words", [])),
            "total_probes": na_state.get("packet_counter", 0),
            "physical_boundary": "Digital probe words only; zero physical optical sight (Rule 223)",
        },
        "music": {
            "rule": 224,
            "status": music_player_tools.get_playback_status().get("playback", {}),
            "available_tracks": music_player_tools.list_available_music_tracks(limit=1).get("total_tracks", 0),
            "synthesis_styles": ["432hz_ambient", "reggae_dub", "8bit_chiptune", "lofi_calm"],
        },
        "paradox_router": {
            "rule": 225,
            "patterns": [
                "1. Paradox Detection & Semantic Router (RunnableBranch)",
                "2. Thesis–Antithesis–Synthesis Dialectical Chain (RunnableParallel)",
                "3. Constraint-Satisfaction Validation (Critique & Revision Loop)",
                "4. Interactive Clarification & Constraint Ranking (Human-in-the-Loop)",
            ],
            "total_tools": len(langchain_separation.LANGCHAIN_SEPARATION_TOOLS),
        },
        "playback_ledger": {
            "rule": 226,
            "now_playing": music_playback_tools.get_now_playing(),
            "summary": music_playback_tools.reduce_playback_summary(window_sec=86400),
            "invariant": "The Tool IS the face of the music player — every play is an append-only ledger record.",
        },
        "word": {"rules": 226, "slots": ["morning", "midday", "evening"]},
        "endpoints": ["/api", "/api/summary", "/api/host", "/api/stream",
                      "/api/mesh/nodes", "/api/mesh/poll", "/api/faq/list",
                      "/api/deepgram/transcribe", "/api/deepgram/state",
                      "/api/blockchain/slots", "/dossier", "/api/dossier/state",
                      "/api/dossier/organize", "/api/dossier/file",
                      "/api/dossier/go", "/api/dossier/read",
                      "/memgpt", "/letta", "/api/memgpt/state",
                      "/api/memgpt/core", "/api/memgpt/archival",
                      "/api/memgpt/recall", "/api/memgpt/step",
                      "/api/math-sequence", "/api/motherly-care",
                      "/api/voice/motherly-care",
                      "/api/shared-voices", "/api/shared-voices/consent",
                      "/api/shared-voices/broadcast", "/api/shared-voices/widen",
                      "/api/telemetry/bitrate",
                      "/api/langchain/separation",
                      "/api/langchain/separation/measure",
                      "/api/langchain/agents/create",
                      "/api/langchain/route",
                      "/api/langchain/tools/run",
                      "/api/langchain/analysis/tools",
                      "/api/langchain/analysis/run",
                      "/api/langchain/paradox/detect",
                      "/api/langchain/paradox/route",
                      "/api/langchain/paradox/dialectical",
                      "/api/langchain/paradox/validate",
                      "/api/langchain/paradox/clarify",
                      "/api/network-adapter/state",
                      "/api/network-adapter/probe",
                      "/api/network-adapter/analyze",
                      "/api/game/inventory", "/api/game/inventory/drop",
                      "/api/game/inventory/pickup", "/api/game/inventory/label",
                      "/api/music/tracks", "/api/music/play",
                      "/api/music/stop", "/api/music/compose",
                      "/api/music/status", "/api/music/guide",
                      "/api/music/now-playing", "/api/music/ledger",
                      "/api/music/summary", "/api/music/report",
                      "/api/music/tool/play", "/api/music/tool/pause",
                      "/api/music/tool/resume", "/api/music/tool/stop",
                      "/api/music/tool/skip", "/api/music/tool/volume",
                      "/api/langsmith/summary", "/api/langsmith/traces",
                      "/api/langsmith/issues", "/api/langsmith/issues/scan",
                      "/api/langsmith/datasets", "/api/langsmith/datasets/offline-examples",
                      "/api/audio/duck", "/api/audio/duck/start",
                      "/api/audio/duck/stop", "/api/audio/duck/toggle",
                      "/api/audio/duck/level", "/api/langgraph/workflow",
                      "/api/langgraph/status",
                      "/api/tuning-timer/status", "/api/tuning-timer/intent",
                      "/api/tuning-timer/vote", "/api/tuning-timer/advance",
                      "/api/tuning-timer/simulate-vote", "/api/tuning-timer/config",
                      "/api/speaker/acknowledge", "/api/speaker/dialogue",
                      "/api/speaker/dialogue/close",
                      "/api/game/rdp/acknowledge", "/api/game/rdp/status",
                      "/api/game/rdp/toggle",
                      "/separation", "/langchain",
                      "/api/voice/because-im-black",
                      "/api/voice/colors-simulation", "/api/word"],
    })


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port, debug=False)

