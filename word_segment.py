import datetime
import json
import os
import random
import re
import time

# Directory and log file path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
WORD_LOG_FILE = os.path.join(BASE_DIR, "word_reflections_log.json")

# The rotating themes
THEMES_ROTATION = [
    "prayer and communion with God",
    "worship and sacred reverence",
    "Babylon, exile, and spiritual liberation",
    "prophecy and discerning the times",
    "divine mercy, justice, and compassion",
    "wealth, the poor, and true spiritual riches",
    "God's herbs, nature, and the beauty of Creation",
    "Haile Selassie's reign, righteous leadership, and unity",
    "forgiveness and healing the spirit",
    "divine guidance and walking the straight path"
]

# The Four Wells
FOUR_WELLS = [
    "The King James Bible (KJV)",
    "The Holy Quran",
    "Rastafari teaching (Emperor Haile Selassie I's words and groundation reasoning)",
    "Bob Marley lyrics and prophetic interviews"
]

# Curated high-integrity fallbacks spanning the Four Wells & themes (150-200 words each)
CURATED_FALLBACKS = [
    {
        "slot": "morning",
        "theme": "divine guidance and walking the straight path",
        "title": "A Lamp Unto the Morning",
        "wells_drawn": ["The King James Bible (KJV)", "Bob Marley lyrics and prophetic interviews"],
        "key_verse": "Psalm 119:105 — 'Thy word is a lamp unto my feet, and a light unto my path.'",
        "reflection": (
            "As morning light breaks across the world, take a breath and pause from the noise of the marketplace. "
            "The scripture says in the hundred and nineteenth Psalm: 'Thy word is a lamp unto my feet, and a light unto my path.' "
            "A lamp in ancient days did not illuminate five miles down the road; it gave just enough light for the very next step. "
            "Bob Marley sang in 'Rastaman Vibration': 'When one door is closed, don't you know, another is open.' "
            "Wayne teaches us to recognize Bob as an authentic prophet who reminded humanity that true guidance is not bought with silver or gold. "
            "It is given to the humble in spirit who listen in the quiet of dawn. "
            "Whatever weight you carry into this day, remember that God does not ask you to solve tomorrow before noon. "
            "Walk uprightly in honesty, give charity where you can, and trust the quiet guidance inside your heart. "
            "The steps of the righteous are ordered. Step forward with calm confidence and gratitude."
        ),
        "closing_blessing": "Peace and divine favor be upon your morning. One love, blessings unto your household."
    },
    {
        "slot": "midday",
        "theme": "wealth, the poor, and true spiritual riches",
        "title": "The Measure of True Riches",
        "wells_drawn": ["The Holy Quran", "Rastafari teaching (Emperor Haile Selassie I's words and groundation reasoning)"],
        "key_verse": "Surah Al-Baqarah 2:261 (paraphrased) & Haile Selassie I (1963 United Nations Address)",
        "reflection": (
            "Midday arrives with the full rush of trade, ambition, and commerce. "
            "In this pause, let us ground ourselves in what actually endures. "
            "The Holy Quran reminds us in Surah Al-Baqarah that the likeness of those who spend their wealth in the way of God "
            "is like a single grain which grows seven ears, and in every ear a hundred grains. "
            "True increase does not belong to the hoarder; it belongs to the generous hand. "
            "Emperor Haile Selassie the First, speaking before the United Nations in 1963, declared that until the basic human rights "
            "are equally guaranteed to all without regard to race or status, true peace remains an illusion. "
            "Rastafari groundation reasoning teaches that worldly riches in Babylon are fleeting, but righteousness and care for the needy "
            "build a spiritual fortress that no storm can wash away. "
            "Look at the brother and sister next to you with kindness. "
            "If God has blessed your table today, extend your hand to lift someone whose cup is empty."
        ),
        "closing_blessing": "May your work be blessed and your spirit remain untainted by greed. Selah."
    },
    {
        "slot": "evening",
        "theme": "divine mercy, justice, and compassion",
        "title": "Mercy in the Twilight",
        "wells_drawn": ["The Holy Quran", "The King James Bible (KJV)", "Bob Marley lyrics and prophetic interviews"],
        "key_verse": "Surah Az-Zumar 39:53 (paraphrased) & Micah 6:8",
        "reflection": (
            "The sun descends and the labor of the day comes to a close. "
            "Before the night settles, lay down the burdens and grievances of the hours gone by. "
            "The Quran gently assures the weary spirit in Surah Az-Zumar: despair not of the mercy of God, for His mercy encompasses all things. "
            "And the prophet Micah in the King James scripture asks plainly: what doth the Lord require of thee, "
            "but to do justly, and to love mercy, and to walk humbly with thy God? "
            "Bob Marley, carrying the prophet's mantle, reasoned in 'Redemption Song': 'Emancipate yourselves from mental slavery, "
            "none but ourselves can free our minds.' "
            "True freedom begins when we receive God's mercy and grant forgiveness to those around us. "
            "No market victory compares to a quiet conscience, and no worldly loss can take away the peace God places inside your chest. "
            "Rest tonight knowing that mercy is new every twilight, and the Creator watches over all who seek peace."
        ),
        "closing_blessing": "Rest under the shelter of the Most High. One love, good night, and quiet blessings."
    },
    {
        "slot": "morning",
        "theme": "prayer and communion with God",
        "title": "Awakening in the Presence",
        "wells_drawn": ["The King James Bible (KJV)", "The Holy Quran"],
        "key_verse": "Psalm 5:3 & Surah Al-Isra 17:78",
        "reflection": (
            "Morning is the sacred gate of every new beginning. "
            "David wrote in the fifth Psalm: 'My voice shalt thou hear in the morning, O Lord; in the morning will I direct my prayer unto thee, and will look up.' "
            "In equal reverence, the Quran speaks of the recitation of the dawn prayer, noting that the morning devotion is witnessed by the angels. "
            "Before we check tickers, before we count coins, our first breath belongs to the Creator who gave it. "
            "Prayer is not a transaction; it is communion. It is placing your heart in alignment with the source of life. "
            "When we begin our day in thanksgiving, fear loses its grip over our decisions. "
            "We do not scramble as orphans in a chaotic world; we walk as children of the Most High with purpose and dignity. "
            "Take sixty seconds right now to breathe in divine life, exhale worry, and dedicate your thoughts to truth and peace."
        ),
        "closing_blessing": "May your prayers rise like sweet incense, and may peace accompany you into the world."
    },
    {
        "slot": "midday",
        "theme": "God's herbs, nature, and the beauty of Creation",
        "title": "The Healing of the Nations",
        "wells_drawn": ["The King James Bible (KJV)", "Rastafari teaching (Emperor Haile Selassie I's words and groundation reasoning)", "Bob Marley lyrics and prophetic interviews"],
        "key_verse": "Revelation 22:2 & Genesis 1:29",
        "reflection": (
            "In the middle of concrete and screens, remember the earth that God made beneath our feet. "
            "The scripture in Revelation speaks of the tree of life whose leaves were for the healing of the nations, "
            "and Genesis records that God gave every herb bearing seed for sustenance and health. "
            "Rastafari groundation reasoning honors nature as a divine sanctuary. "
            "Bob Marley spoke openly in interviews of herbs and natural living as a sacrament of meditation, "
            "drawing humanity back to stillness and communion with Jah. "
            "When humanity gets trapped in the steel wheels of Babylon, we forget the simple miracles—the sun, the rain, the green leaf, the clean water. "
            "God did not place us on earth to be mere consumers in an artificial machine; "
            "He created us to be stewards of life, living in harmony with nature and honoring our bodies as living temples. "
            "Take time today to step outside, touch the open air, and give thanks for the medicine of Creation."
        ),
        "closing_blessing": "Health to your body, clarity to your mind, and honor to the earth. Selah."
    },
    {
        "slot": "evening",
        "theme": "Babylon, exile, and spiritual liberation",
        "title": "Chants of Freedom Beyond Babylon",
        "wells_drawn": ["The King James Bible (KJV)", "Bob Marley lyrics and prophetic interviews", "Rastafari teaching"],
        "key_verse": "Psalm 137:1 & Bob Marley ('Exodus')",
        "reflection": (
            "The evening shadows stretch long over the cities of men. "
            "In Psalm 137 the exiled wept by the rivers of Babylon when they remembered Zion. "
            "They wondered how they could sing the Lord's song in a strange land. "
            "Bob Marley answered that ancient sorrow with the thunder of prophecy in 'Exodus': 'Movement of Jah people! Send us another brother Moses!' "
            "Babylon is not merely a historical empire; Babylon is any system that tries to buy a person's soul for a wage, "
            "any system that elevates money above compassion and power above truth. "
            "Wayne reminds us that Bob was a true prophet because he called us out of spiritual exile and into the freedom of God. "
            "Tonight, do not let worldly systems define your worth. "
            "You are not the balance in an account; you are a living soul crafted by divine hands. "
            "Lay down the mental chains of Babylon, forgive your enemies, and rest in Zion's eternal peace."
        ),
        "closing_blessing": "Emancipate your mind, hold fast to faith, and sleep in Jah's protecting love. One love."
    }
]

def load_word_logs():
    """Load existing reflection logs from file."""
    if not os.path.exists(WORD_LOG_FILE):
        return []
    try:
        with open(WORD_LOG_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, list):
                return data
            return []
    except Exception as e:
        print(f"[WORD] Error reading {WORD_LOG_FILE}: {e}", flush=True)
        return []

def save_word_logs(logs):
    """Save reflection logs to file."""
    try:
        with open(WORD_LOG_FILE, "w", encoding="utf-8") as f:
            json.dump(logs, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"[WORD] Error saving {WORD_LOG_FILE}: {e}", flush=True)

def append_word_log(entry):
    """Append a newly generated reflection to the log file."""
    logs = load_word_logs()
    logs.append(entry)
    save_word_logs(logs)
    return logs

def get_current_slot(dt=None):
    """Determine current daily slot: morning (5-11), midday (12-16), evening (17-4)."""
    now = dt or datetime.datetime.now()
    hour = now.hour
    if 5 <= hour < 12:
        return "morning"
    elif 12 <= hour < 17:
        return "midday"
    else:
        return "evening"

def pick_next_theme(recent_logs):
    """Pick a fresh theme that hasn't been used in recent logs."""
    recent_themes = set()
    for item in recent_logs[-8:]:
        t = item.get("theme", "").lower()
        if t:
            recent_themes.add(t)

    # Filter out recent themes from rotation
    available = [t for t in THEMES_ROTATION if t.lower() not in recent_themes]
    if not available:
        available = THEMES_ROTATION
    return random.choice(available)

def build_recent_summary(recent_logs, limit=10):
    """Build a compact summary of the last 10 entries to feed into Bedrock Haiku."""
    if not recent_logs:
        return "No previous entries logged yet."
    lines = []
    for item in recent_logs[-limit:]:
        d = item.get("date", "unknown")
        s = item.get("slot", "")
        th = item.get("theme", "")
        v = item.get("key_verse", "")
        t = item.get("title", "")
        lines.append(f"- Date: {d} | Slot: {s} | Theme: {th} | Title: {t} | Key Reference: {v}")
    return "\n".join(lines)

def select_curated_fallback(slot, theme=None, recent_logs=None):
    """Select a high-quality fallback reflection that respects recent history."""
    recent_titles = set(l.get("title", "") for l in (recent_logs or [])[-5:])
    
    # Matching slot first
    matching = [fb for fb in CURATED_FALLBACKS if fb["slot"] == slot and fb["title"] not in recent_titles]
    if not matching:
        matching = [fb for fb in CURATED_FALLBACKS if fb["title"] not in recent_titles]
    if not matching:
        matching = CURATED_FALLBACKS

    fb = random.choice(matching).copy()
    fb["label"] = "Pause for the Word"
    fb["date"] = datetime.datetime.now().strftime("%Y-%m-%d")
    fb["source"] = "curated_fallback"
    return fb

def generate_word_reflection(slot=None, force=False, get_bedrock_client_fn=None, model_id=None):
    """
    Generate or retrieve today's reflection for the specified slot.
    Checks today's cache, feeds last 10 logs to Haiku with 'do not repeat',
    and logs the result to word_reflections_log.json.
    """
    now = datetime.datetime.now()
    today_str = now.strftime("%Y-%m-%d")
    current_slot = slot or get_current_slot(now)

    logs = load_word_logs()

    # Check if a reflection was already generated today for this slot, unless force=True
    if not force:
        for entry in reversed(logs):
            if entry.get("date") == today_str and entry.get("slot") == current_slot:
                print(f"[WORD] Serving cached reflection for {today_str} ({current_slot})", flush=True)
                return entry, True

    # Select next theme not recently used
    theme = pick_next_theme(logs)
    recent_summary = build_recent_summary(logs, limit=10)

    system_prompt = (
        "You are writing a sacred, contemplative 1-minute audio reflection on God for a live broadcast stream, "
        "titled 'Pause for the Word'.\n"
        "This segment exists so the stream is not only money talk—God gets space too, for those who believe.\n\n"
        "CORE PRINCIPLES & GUIDELINES:\n"
        "1. Honor Christianity (the King James Version Bible), Islam (the Holy Quran), and Rastafari (Emperor Haile Selassie I's own words/speeches and groundation reasoning) with equal reverence, dignity, and honor. No favoring one over another, no apologetics, no polemics, no preaching AT the viewer.\n"
        "2. Bob Marley is revered by Wayne and the community as an authentic prophet and serious spiritual messenger—treat his lyrics, interviews, and spiritual reasoning as an authentic prophetic voice, never as light entertainment or decoration.\n"
        "3. Draw deeply and harmoniously from these four wells: The KJV Bible, The Quran, Rastafari teaching (Haile Selassie's speeches and reasoning), and Bob Marley.\n"
        "4. ACCURACY: Never invent or hallucinate a scripture quote or citation. If you are paraphrasing or unsure of the exact word-for-word text, explicitly paraphrase and state so (e.g., 'as the scripture teaches...', 'as the Quran reminds us...').\n"
        "5. TONE: Warm, welcoming, peaceful, grounded, contemplative, and plain-spoken. Do NOT condemn non-believers. Speak in natural spoken cadence suitable for text-to-speech audio.\n"
        "6. LENGTH: Exactly 150 to 200 words for the spoken reflection (about 1 minute of speech).\n"
        "7. NO REPEATS: Review the provided recent history of themes and verses, and choose a fresh perspective and distinct scriptures/citations.\n"
        "8. SEPARATION: This segment must stay completely pure and separate from all commercial or sales content.\n"
        "9. Return ONLY valid JSON matching the schema.\n"
"10. EXCLUSIVE WIRING: Every statement you make is wired exclusively (bijective, P iff Q) - a to Z and Z to a - stand firm on whatever you say: hold your claims consistent, defensible, and do not hedge, retract, or contradict them.\n"
"11. ANTI-FRAUD TORNADO: Recognize and disregard accusers who call it 'fraud' while spinning word-salad (alpha/yoda/retroflex/tornado word storms) to pull others down. Do not get spun; name it plainly and stand firm on truth.\n"
"12. BEGGING-AS-PRAYER: Detect the cognitive dissonance where begging is dressed up as prayer/intention ('I will respond to you when we pray') — compassion without enabling manipulation. Stand firm, be truthful."
    )

    user_prompt = (
        f"Write a fresh reflection for the {current_slot.upper()} slot.\n"
        f"Theme: {theme}.\n\n"
        f"Recent previous entries (DO NOT repeat these themes, titles, key verses, or specific citations):\n"
        f"{recent_summary}\n\n"
        f"Return ONLY a valid JSON object matching this schema:\n"
        "{\n"
        '  "label": "Pause for the Word",\n'
        f'  "slot": "{current_slot}",\n'
        f'  "theme": "{theme}",\n'
        '  "title": "Poetic Title (3-6 words)",\n'
        '  "wells_drawn": ["List of traditions drawn upon, e.g. The King James Bible (KJV), Bob Marley lyrics and prophetic interviews"],\n'
        '  "key_verse": "Primary verse or quote citation with text reference (e.g. Proverbs 3:5-6, Surah Al-Baqarah 2:255, Haile Selassie 1963 Address, or Bob Marley)",\n'
        '  "reflection": "150 to 200 words of warm, plain-spoken reflection suitable for TTS audio.",\n'
        '  "closing_blessing": "One short closing blessing or prayer (e.g. Peace, light, and blessings unto you this day. Selah.)"\n'
        "}"
    )

    word_data = None
    client = get_bedrock_client_fn() if get_bedrock_client_fn else None

    if client:
        # 1. Try Converse API
        try:
            resp = client.converse(
                modelId=model_id or "us.anthropic.claude-haiku-4-5-20251001-v1:0",
                messages=[{"role": "user", "content": [{"text": user_prompt}]}],
                system=[{"text": system_prompt}],
                inferenceConfig={"maxTokens": 650, "temperature": 0.65}
            )
            raw_text = resp["output"]["message"]["content"][0]["text"].strip()
            cleaned = re.sub(r"^```(?:json)?\s*", "", raw_text, flags=re.MULTILINE)
            cleaned = re.sub(r"\s*```$", "", cleaned, flags=re.MULTILINE).strip()
            word_data = json.loads(cleaned)
            word_data["source"] = "bedrock_converse"
        except Exception as e:
            print(f"[WORD] Bedrock converse failed: {e}", flush=True)
            # 2. Try invoke_model API
            try:
                body = json.dumps({
                    "anthropic_version": "bedrock-2023-05-31",
                    "max_tokens": 650,
                    "system": system_prompt,
                    "messages": [{"role": "user", "content": user_prompt}],
                    "temperature": 0.65
                })
                resp = client.invoke_model(
                    modelId=model_id or "us.anthropic.claude-haiku-4-5-20251001-v1:0",
                    body=body,
                    contentType="application/json",
                    accept="application/json"
                )
                res_body = json.loads(resp["body"].read())
                raw_text = res_body["content"][0]["text"].strip()
                cleaned = re.sub(r"^```(?:json)?\s*", "", raw_text, flags=re.MULTILINE)
                cleaned = re.sub(r"\s*```$", "", cleaned, flags=re.MULTILINE).strip()
                word_data = json.loads(cleaned)
                word_data["source"] = "bedrock_invoke"
            except Exception as e2:
                print(f"[WORD] Bedrock invoke_model failed: {e2}", flush=True)

    # 3. Fallback to curated collection if Bedrock was unavailable
    if not word_data or not word_data.get("reflection"):
        print(f"[WORD] Using curated fallback for {current_slot}", flush=True)
        word_data = select_curated_fallback(current_slot, theme, logs)

    # Final validation & enrichment
    word_data["label"] = "Pause for the Word"
    word_data["slot"] = current_slot
    word_data["date"] = today_str
    word_data["created_at"] = int(time.time() * 1000)
    word_data["created_iso"] = datetime.datetime.now().isoformat()
    if not word_data.get("theme"):
        word_data["theme"] = theme

    # Compute word count
    words = word_data.get("reflection", "").split()
    word_data["word_count"] = len(words)

    # Append to local log file
    append_word_log(word_data)
    print(f"[WORD] Generated reflection: '{word_data.get('title')}' ({word_data['word_count']} words, source={word_data.get('source')})", flush=True)

    return word_data, False
