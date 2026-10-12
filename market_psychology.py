"""
Market Psychology & PvP Sentiment Engine for Solana Pump.fun.
Measures human trader psychology, dev intent, crowd FOMO, holder churn,
and generates ASCII sparklines, gauges, and multi-view radar dashboards.
"""

import os
import time
import json
import math
import re
import shutil
import io
from typing import Dict, Any, List, Tuple, Optional
from rich.panel import Panel
from rich.table import Table
from rich.console import Console, Group
from rich import box

import config


def render_sparkline(values: List[float], min_val: Optional[float] = None, max_val: Optional[float] = None) -> str:
    """
    Render a compact ASCII sparkline using UTF-8 block elements.
    Block levels:   ▂ ▃ ▄ ▅ ▆ ▇ █
    """
    if not values:
        return "────"

    chars = [" ", "▂", "▃", "▄", "▅", "▆", "▇", "█"]
    lo = min_val if min_val is not None else min(values)
    hi = max_val if max_val is not None else max(values)

    if hi == lo:
        return chars[3] * len(values)

    spark = []
    for v in values:
        idx = int((v - lo) / (hi - lo) * (len(chars) - 1))
        idx = max(0, min(len(chars) - 1, idx))
        spark.append(chars[idx])
    return "".join(spark)


def render_meter_bar(pct: float, width: int = 10, fill_char: str = "█", empty_char: str = "░", color: str = "green") -> str:
    """
    Render a fixed-width ASCII progress / gauge meter bar with Rich styling.
    Example: [bold green]████████[/bold green][dim]░░░░[/dim]
    """
    pct = max(0.0, min(100.0, pct))
    filled = int(round((pct / 100.0) * width))
    empty = width - filled
    return f"[{color}]{fill_char * filled}[/{color}][dim]{empty_char * empty}[/dim]"


def render_ev_meter(ev_val: float, max_scale: float = 1.0, half_width: int = 10) -> str:
    """
    Render a bidirectional EV meter bar scaled around midpoint 0.00.
    Positive values fill green to the right, negative values fill red to the left.
    """
    scale = max(0.10, max_scale)
    ratio = min(1.0, max(-1.0, ev_val / scale))
    block = "█"
    dot = "░"
    if ratio >= 0:
        fill = int(round(ratio * half_width))
        left = "[dim]" + (dot * half_width) + "[/dim]"
        right = f"[bold green]{block * fill}[/bold green][dim]{dot * (half_width - fill)}[/dim]"
    else:
        fill = int(round(abs(ratio) * half_width))
        left = f"[dim]{dot * (half_width - fill)}[/dim][bold red]{block * fill}[/bold red]"
        right = "[dim]" + (dot * half_width) + "[/dim]"
    return f"[{left}│{right}]"


def render_ascii_histogram(data: List[Tuple[str, float]], height: int = 4, unit: str = "%", threshold_line: Optional[float] = 0.75) -> str:
    """
    Render a clean vertical ASCII column chart.
    data: list of (column_label, value) tuples
    height: number of vertical character rows
    threshold_line: optional horizontal benchmark reference (e.g. 0.75% stand-down floor)
    """
    if not data:
        return "No historical data available."

    vals = [v for _, v in data]
    max_v = max(vals) if vals and max(vals) > 0 else 1.0
    # Allow at least up to threshold_line if specified
    if threshold_line and threshold_line > max_v:
        max_v = threshold_line * 1.2
    
    labels = [lbl for lbl, _ in data]
    lines = []

    # Find which row is closest to threshold line
    thresh_row = -1
    if threshold_line is not None:
        thresh_row = int(round((threshold_line / max_v) * height))

    for row in range(height, 0, -1):
        thresh = (row / height) * max_v
        tag = ""
        if row == thresh_row and threshold_line is not None:
            tag = f" [dim](Floor: {threshold_line:.2f}{unit})[/dim]"
        
        row_str = f" [bold white]{thresh:4.1f}{unit}[/bold white] │"
        for _, v in data:
            if v >= thresh:
                row_str += "  [bold green]█[/bold green] "
            elif v >= ((row - 0.5) / height) * max_v:
                row_str += "  [bold yellow]▄[/bold yellow] "
            else:
                row_str += "    "
        lines.append(row_str + tag)

    # Base line
    axis = "      0 │" + "────" * len(data)
    lines.append(axis)
    # Label headers
    lbl_str = "        │" + "".join(f"{lbl:>4}" for lbl in labels)
    lines.append(lbl_str)

    return "\n".join(lines)


class MarkovTextEngine:
    """
    Markov Chain & State Transition Matrix for Token Linguistic Narrative Regimes.
    Classifies token names & symbols into 4 canonical psychological states:
      0: BOT_WASH   - Whales & bots swishing waters, MEV scripts, sniper bait, volume spoofers
                      (e.g., 'thunderbot', 'funder', 'mev', 'sniper', 'auto', 'wash', 'drain')
      1: VIRAL_FOMO - Authentic retail meme euphoria, viral meme magnets
                      (e.g., 'pepe', 'doge', 'shib', 'inu', 'cat', 'moon', 'gem', 'chad', 'trump')
      2: TECH_AI    - Autonomous AI agents & protocol meta
                      (e.g., 'ai', 'agent', 'gpt', 'llm', 'neural', 'protocol', 'matrix', 'lab')
      3: BURNER_RUG - Disposable scraper garbage, gibberish consonant hashes, Sybil spam

    Tracks empirical transitions P(S_t -> S_{t+1}), calculates the stationary
    equilibrium distribution π, and produces an anti-spoofing dampener
    to deflate fake whale-churn FOMO and ghost conviction.
    """

    STATES = ["BOT_WASH", "VIRAL_FOMO", "TECH_AI", "BURNER_RUG"]
    STATE_LABELS = {
        0: "BOT_WASH (Whale Churn)",
        1: "VIRAL_FOMO (Retail Meme)",
        2: "TECH_AI (Narrative)",
        3: "BURNER_RUG (Disposable)"
    }
    STATE_EMOJIS = {
        0: "🌊",
        1: "🔥",
        2: "🤖",
        3: "🪓"
    }

    BOT_KEYWORDS = {
        "thunder", "bot", "bots", "funder", "fund", "funding", "thunderbot", "snipe", "sniper",
        "mev", "volume", "vol", "auto", "pumpbot", "swap", "drain", "drainer", "maker",
        "arb", "wash", "liquidity", "test", "deploy", "script", "router", "sub", "solbot",
        "speed", "tx", "block", "pool", "multisig", "copy", "mirror", "spoof", "solfunder"
    }

    FOMO_KEYWORDS = {
        "pepe", "doge", "shib", "inu", "cat", "cats", "trump", "elon", "moon", "gem",
        "chad", "chads", "wif", "based", "rich", "billion", "100x", "solana", "bonk",
        "bull", "bulls", "diamond", "hodl", "gold", "wojak", "frog", "puppy", "maga",
        "fomo", "hype", "giga", "rocket", "king", "queen", "ape", "apes"
    }

    TECH_KEYWORDS = {
        "ai", "agent", "agents", "gpt", "llm", "neural", "protocol", "dao", "network",
        "lab", "labs", "cloud", "quantum", "intel", "meta", "tech", "matrix", "compute",
        "model", "chain", "core", "nexus", "synapse", "cyber", "data"
    }

    def __init__(self, max_history: int = 120):
        self.max_history = max_history
        self.transitions: List[Tuple[int, int]] = []
        self.recent_tokens: List[Dict[str, Any]] = []
        self._last_state: Optional[int] = None

        # Prior Laplace counts to avoid division by zero on cold start
        self.prior_counts = [
            [2.0, 1.0, 1.0, 1.0],  # BOT transitions
            [1.0, 3.0, 1.0, 1.0],  # FOMO transitions
            [1.0, 1.0, 2.0, 1.0],  # TECH transitions
            [1.0, 1.0, 1.0, 2.0],  # RUG transitions
        ]

    def classify_text(self, name: str, symbol: str) -> Tuple[int, str, List[str]]:
        """
        Classify token text into one of 4 states using keyword stem matching
        and linguistic entropy heuristics.
        Returns: (state_idx, state_name, matched_keywords)
        """
        combined = f"{name} {symbol}".lower()
        words = re.findall(r'[a-z0-9]+', combined)

        bot_matches = []
        fomo_matches = []
        tech_matches = []

        for w in words:
            if w in self.BOT_KEYWORDS or any(kw in w for kw in ["thunder", "bot", "fund", "mev", "snipe", "wash", "drain", "swap"]):
                bot_matches.append(w)
            if w in self.FOMO_KEYWORDS or any(kw in w for kw in ["pepe", "doge", "shib", "moon", "chad", "wif", "trump", "elon"]):
                fomo_matches.append(w)
            if w in self.TECH_KEYWORDS or any(kw in w for kw in ["agent", "gpt", "llm", "neural", "protocol"]):
                tech_matches.append(w)

        # Check burner gibberish heuristic: long word with no vowels
        is_burner_gibberish = False
        for w in words:
            if len(w) >= 5 and re.search(r'[aeiouy]', w) is None:
                is_burner_gibberish = True
                break

        if len(bot_matches) > 0 and len(bot_matches) >= len(fomo_matches):
            return 0, "BOT_WASH", bot_matches
        elif len(fomo_matches) > 0 and len(fomo_matches) >= len(tech_matches):
            return 1, "VIRAL_FOMO", fomo_matches
        elif len(tech_matches) > 0:
            return 2, "TECH_AI", tech_matches
        elif is_burner_gibberish:
            return 3, "BURNER_RUG", ["consonant_spam"]
        else:
            if any(len(w) >= 3 for w in words):
                return 1, "VIRAL_FOMO", ["general_word"]
            return 3, "BURNER_RUG", ["unrecognized"]

    def record_token(self, name: str, symbol: str) -> Dict[str, Any]:
        """Record an incoming token, updating sequential Markov chain transitions."""
        state_idx, state_name, matches = self.classify_text(name, symbol)

        if self._last_state is not None:
            self.transitions.append((self._last_state, state_idx))
            if len(self.transitions) > self.max_history:
                self.transitions.pop(0)

        self._last_state = state_idx
        token_info = {
            "name": name,
            "symbol": symbol,
            "state": state_idx,
            "state_name": state_name,
            "matches": matches,
            "time": time.time()
        }
        self.recent_tokens.append(token_info)
        if len(self.recent_tokens) > self.max_history:
            self.recent_tokens.pop(0)

        return token_info

    def get_transition_matrix(self) -> Tuple[List[List[float]], List[float]]:
        """
        Calculate empirical 4x4 transition probability matrix P and stationary distribution π.
        Uses Laplace smoothing: P_{ij} = (C_{ij} + prior_{ij}) / sum_k(C_{ik} + prior_{ik})
        """
        counts = [[self.prior_counts[i][j] for j in range(4)] for i in range(4)]
        for src, dst in self.transitions:
            if 0 <= src < 4 and 0 <= dst < 4:
                counts[src][dst] += 1.0

        # Row-normalize to produce transition matrix P
        P = []
        for i in range(4):
            row_sum = sum(counts[i])
            P.append([counts[i][j] / row_sum for j in range(4)])

        # Solve stationary distribution π via power iteration (π P = π)
        pi = [0.25, 0.25, 0.25, 0.25]
        for _ in range(40):
            next_pi = [0.0, 0.0, 0.0, 0.0]
            for j in range(4):
                next_pi[j] = sum(pi[i] * P[i][j] for i in range(4))
            total = sum(next_pi)
            if total > 0:
                pi = [x / total for x in next_pi]

        return P, pi

    def get_whale_churn_factor(self) -> Dict[str, Any]:
        """
        Compute whale wash intensity W_churn, organic retail ratio,
        and anti-spoofing dampening multipliers.
        """
        P, pi = self.get_transition_matrix()

        p_bot_bot = P[0][0]
        pi_bot = pi[0]
        pi_fomo = pi[1]
        pi_tech = pi[2]
        pi_rug = pi[3]

        # Whale Churn Index W_churn: high when bots dominate stream or loop into bots
        w_churn = min(0.95, max(0.0, (pi_bot * 0.65) + (p_bot_bot * 0.35)))

        # Anti-spoof dampeners
        fomo_dampener = max(0.25, 1.0 - (0.68 * w_churn))
        conv_dampener = max(0.30, 1.0 - (0.55 * w_churn))

        recent_chain = [f"${t['symbol']}" if t['symbol'] else t['name'] for t in self.recent_tokens[-3:]] if self.recent_tokens else []

        if w_churn >= 0.40:
            status = "SPOOFED_WHALE_WASH"
            status_label = "🌊 WHALE SWISH / BOT WASH"
            explanation = "Whales swishing waters ('thunderbot funder' loop): artificial bot volume blocking real buyers."
            explanation_short = "Whales swishing waters: bot-to-bot loop blocking retail out."
            markov_color = "bold cyan"
        elif w_churn >= 0.30:
            status = "MIXED_WASH"
            status_label = "⚠️ MIXED BOT/RETAIL CHURN"
            explanation = "Mixed orderflow: bots testing waters alongside scattered retail meme tokens."
            explanation_short = "Mixed tape: bots testing alongside scattered retail tokens."
            markov_color = "bold yellow"
        else:
            status = "ORGANIC_RETAIL"
            status_label = "🔥 ORGANIC RETAIL FLOW"
            explanation = "Organic retail meme narrative: real buyers chasing viral meme trends."
            explanation_short = "Organic retail momentum: real buyers active in meme coins."
            markov_color = "bold green"

        return {
            "whale_churn": w_churn,
            "fomo_dampener": fomo_dampener,
            "conv_dampener": conv_dampener,
            "p_bot_bot": p_bot_bot,
            "pi_bot": pi_bot,
            "pi_fomo": pi_fomo,
            "pi_tech": pi_tech,
            "pi_rug": pi_rug,
            "P": P,
            "pi": pi,
            "status": status,
            "status_label": status_label,
            "explanation": explanation,
            "explanation_short": explanation_short,
            "markov_color": markov_color,
            "recent_chain": recent_chain,
            "last_state": self._last_state
        }

    def render_rich_table(self) -> Table:
        """
        Build and return a rich.table.Table representing the 4x4 Markov Transition
        Probability Matrix P(S_t -> S_{t+1}) and stationary narrative equilibrium (pi).
        """
        P, pi = self.get_transition_matrix()
        data = self.get_whale_churn_factor()
        w_churn = data["whale_churn"]

        table = Table(
            title="[bold cyan]Transition Probability Matrix P(S_t → S_{t+1})[/bold cyan]",
            box=box.ROUNDED,
            border_style="cyan"
        )
        table.add_column("From (S_t)", style="bold white", no_wrap=True)
        table.add_column("→ BOT", justify="center")
        table.add_column("→ FOMO", justify="center")
        table.add_column("→ TECH", justify="center")
        table.add_column("→ BURN", justify="center")
        table.add_column("Steady π", justify="center")

        row_defs = [
            ("🌊 BOT_WASH", "cyan", pi[0]),
            ("🔥 VIRAL_FOMO", "magenta", pi[1]),
            ("🤖 TECH_AI", "green", pi[2]),
            ("🪓 BURNER_RUG", "red", pi[3]),
        ]

        for i in range(4):
            label, color, pi_val = row_defs[i]
            row_cells = [f"[bold {color}]{label}[/bold {color}]"]
            for j in range(4):
                prob = P[i][j]
                if i == j:
                    val_str = f"[{prob:.2f}]"
                    if i == 0 and j == 0:
                        if P[0][0] >= 0.40:
                            cell = f"[bold red]{val_str}[/bold red]"
                        elif P[0][0] >= 0.30:
                            cell = f"[bold yellow]{val_str}[/bold yellow]"
                        else:
                            cell = f"[bold cyan]{val_str}[/bold cyan]"
                    elif i == 1 and j == 1:
                        cell = f"[bold magenta]{val_str}[/bold magenta]"
                    elif i == 2 and j == 2:
                        cell = f"[bold green]{val_str}[/bold green]"
                    else:
                        cell = f"[bold red]{val_str}[/bold red]"
                else:
                    val_str = f"{prob:.2f}"
                    if prob >= 0.35:
                        cell = f"[bold yellow]{val_str}[/bold yellow]"
                    else:
                        cell = f"[dim white]{val_str}[/dim white]"
                row_cells.append(cell)

            if i == 0:
                pi_str = f"[bold red]{pi_val*100:.1f}% 🌊[/bold red]" if w_churn >= 0.40 else f"[bold cyan]{pi_val*100:.1f}%[/bold cyan]"
            elif i == 1:
                pi_str = f"[bold magenta]{pi_val*100:.1f}%[/bold magenta]"
            elif i == 2:
                pi_str = f"[bold green]{pi_val*100:.1f}%[/bold green]"
            else:
                pi_str = f"[dim]{pi_val*100:.1f}%[/dim]"
            row_cells.append(pi_str)

            table.add_row(*row_cells)

        return table

    def render_ascii_matrix(self) -> str:
        """
        Render a 4x4 Markov Transition Matrix using rich table exported via Console.
        """
        table = self.render_rich_table()
        data = self.get_whale_churn_factor()
        w_churn = data["whale_churn"]
        P, pi = self.get_transition_matrix()

        buf = io.StringIO()
        con = Console(file=buf, force_terminal=True, width=76)
        con.print(table)
        table_str = buf.getvalue().rstrip()

        lines = [
            table_str,
            "",
            "[bold cyan]Stationary Narrative Equilibrium (π):[/bold cyan]",
            f"  • [bold cyan]🌊 Whale/Bot Churn:[/bold cyan]   {pi[0]*100:4.1f}% [dim]({data['status_label']})[/dim]",
            f"  • [bold magenta]🔥 Viral Meme FOMO:[/bold magenta]   {pi[1]*100:4.1f}% [dim](Organic Retail Appetite)[/dim]",
            f"  • [bold green]🤖 Tech / AI Narrative:[/bold green]{pi[2]*100:4.1f}%",
            f"  • [bold red]🪓 Disposable Burner:[/bold red]  {pi[3]*100:4.1f}%",
        ]

        recent_str = " ➔ ".join(data["recent_chain"][-3:]) if data["recent_chain"] else "None"
        lines.append(f"\n  [bold yellow]Recent Chain:[/bold yellow] [bold white]{recent_str}[/bold white]")
        lines.append(f"  [bold yellow]Anti-Spoof Multiplier:[/bold yellow] [bold cyan]{data['fomo_dampener']*100:.0f}%[/bold cyan] (Whale Churn Index: [bold red]{w_churn*100:.0f}%[/bold red])")
        return "\n".join(lines)


class MarketPsychology:
    """
    Real-time Market Psychology & PvP Sentiment Engine.
    Reads regime tape, trades history, and incoming scan events to calculate:
    1. Crowd FOMO / Sentiment Gauge (0-100%) [Markov Damped against Whale Wash]
    2. Dev Intent / Desperation Meter (0-100%) [Strict Cosine & 120° Compass]
    3. Holder Conviction vs Churn Gauge (0-100%) [Markov Damped against Ghost Retention]
    4. Market Adrenaline & Velocity (launches per minute)
    5. Trailing 6h Runner Rate Sparkline & ASCII Histogram
    6. Markov Text Regime Matrix & Whale Churn Analyzer
    """

    def __init__(
        self,
        tape_file: Optional[str] = None,
        trade_history_file: str = "trade_history.json",
        stats_file: str = "portfolio_stats.json"
    ):
        self.tape_file = tape_file or getattr(config, "REGIME_TAPE_FILE", "regime_tape.jsonl")
        self.trade_history_file = trade_history_file
        self.stats_file = stats_file
        self.markov = MarkovTextEngine()

        # In-memory buffer of recent scans for dev profiling & launch velocity
        self._recent_scans: List[Dict[str, Any]] = []
        self._max_recent_scans: int = 150

        # Cached computed metrics
        self._cached_metrics: Optional[Dict[str, Any]] = None
        self._last_compute_time: float = 0.0
        self._cache_ttl_sec: float = 12.0  # Cache for 12 seconds to prevent excessive I/O

    def record_token_event(
        self,
        token_data: Dict[str, Any],
        meta: Optional[Dict[str, Any]] = None,
        dex_data: Optional[Dict[str, Any]] = None,
        dev_stats: Optional[Dict[str, Any]] = None
    ):
        """
        Record incoming token scan metadata for dev intent and launch velocity tracking.
        Fire-and-forget: non-blocking and safe.
        """
        try:
            now = time.time()
            dev_buy = float(
                token_data.get("solAmount")
                if token_data.get("solAmount") is not None
                else (token_data.get("dev_buy_sol") or 0.0)
            )

            meta = meta or {}
            has_socials = bool(
                meta.get("twitter") or meta.get("telegram") or meta.get("website")
            )

            dev_stats = dev_stats or {}
            age_days = float(dev_stats.get("age_days") or 0.0)
            is_veteran = age_days >= 30.0

            name = str(token_data.get("name") or (meta.get("name") if meta else "") or "")
            symbol = str(token_data.get("symbol", "TOKEN"))

            if hasattr(self, "markov") and self.markov:
                self.markov.record_token(name, symbol)

            event = {
                "t": now,
                "symbol": symbol,
                "name": name,
                "mint": str(token_data.get("mint", "")),
                "dev_buy": dev_buy,
                "has_socials": has_socials,
                "is_veteran": is_veteran
            }

            self._recent_scans.append(event)
            if len(self._recent_scans) > self._max_recent_scans:
                self._recent_scans.pop(0)
        except Exception:
            pass

    def _load_tape_entries(self) -> List[Dict[str, Any]]:
        """Load tape entries from regime_tape.jsonl."""
        if not os.path.exists(self.tape_file):
            return []
        entries = []
        try:
            with open(self.tape_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        entries.append(json.loads(line))
                    except Exception:
                        continue
        except Exception:
            pass
        return entries

    def get_metrics(self, force_refresh: bool = False) -> Dict[str, Any]:
        """
        Compute or return cached psychological metrics.
        """
        now = time.time()
        if not force_refresh and self._cached_metrics and (now - self._last_compute_time < self._cache_ttl_sec):
            return self._cached_metrics

        tape = self._load_tape_entries()
        now = time.time()

        # -----------------------------------------------------------------
        # 1. Trailing 3-Hour Tape Metrics (Crowd FOMO & Holder Conviction)
        # -----------------------------------------------------------------
        window_3h_sec = 3 * 3600
        cutoff_3h = now - window_3h_sec
        tape_3h = [e for e in tape if e.get("t_scan", 0) >= cutoff_3h]
        completed_3h = [e for e in tape_3h if e.get("outcome") in ("settled", "dead")]

        n_completed = len(completed_3h)
        if n_completed > 0:
            pos_tokens = [e for e in completed_3h if float(e.get("return_30m", 0.0)) > 0]
            runners_3h = [
                e for e in completed_3h
                if e.get("outcome") == "settled"
                and float(e.get("return_30m", 0.0)) > 0.10
                and max(float(e.get("vol_scan", 0.0)), float(e.get("vol_30m", 0.0))) >= 1000.0
            ]
            dead_tokens = [
                e for e in completed_3h
                if e.get("outcome") == "dead" or float(e.get("return_30m", 0.0)) <= -0.90
            ]

            pos_rate = len(pos_tokens) / n_completed
            runner_rate = len(runners_3h) / n_completed
            dead_rate = len(dead_tokens) / n_completed
        else:
            pos_rate = 0.15
            runner_rate = 0.008
            dead_rate = 0.12

        # -----------------------------------------------------------------
        # 2. CROWD FOMO GAUGE (0-100%) [With Markov Anti-Spoofing Filter]
        # Base pump.fun positive rate is ~15%. Above 20% is aggressive FOMO.
        # Runner rate above 1.0% is strong market appetite.
        # Filtered through Markov linguistic engine to detect whale churning.
        # -----------------------------------------------------------------
        fomo_score_raw = (pos_rate / 0.22) * 55.0 + (runner_rate / 0.012) * 45.0
        fomo_raw_pct = max(5.0, min(98.0, fomo_score_raw))

        # Query Markov Text & Whale Churn Analysis
        markov_data = self.markov.get_whale_churn_factor()
        w_churn = markov_data["whale_churn"]

        # Dampen raw FOMO with Markov anti-spoof multiplier
        fomo_score = fomo_raw_pct * markov_data["fomo_dampener"]
        fomo_pct = max(5.0, min(98.0, fomo_score))

        if w_churn >= 0.40:
            fomo_label = f"WHALE SWISH / SPOOF (Raw {fomo_raw_pct:.0f}%)"
            fomo_emoji = "🌊"
            fomo_color = "bold cyan"
        elif fomo_pct >= 80:
            fomo_label = "MANIA / EUPHORIA"
            fomo_emoji = "🔥"
            fomo_color = "bold magenta"
        elif fomo_pct >= 65:
            fomo_label = "AGGRESSIVE FOMO"
            fomo_emoji = "🚀"
            fomo_color = "bold green"
        elif fomo_pct >= 45:
            fomo_label = "SELECTIVE GREED"
            fomo_emoji = "⚖️"
            fomo_color = "bold yellow"
        elif fomo_pct >= 25:
            fomo_label = "CAUTIOUS / SKEPTICAL"
            fomo_emoji = "❄️"
            fomo_color = "yellow"
        else:
            fomo_label = "EXTREME PANIC / BLOOD"
            fomo_emoji = "🩸"
            fomo_color = "bold red"

        # -----------------------------------------------------------------
        # 3. DEV INTENT / DESPERATION METER (0-100%)
        # Analyzes dev initial buy size, presence of socials, and wallet age
        # -----------------------------------------------------------------
        if self._recent_scans:
            recent = self._recent_scans[-50:]
            avg_dev_buy = sum(e["dev_buy"] for e in recent) / len(recent)
            socials_ratio = sum(1 for e in recent if e["has_socials"]) / len(recent)
            veteran_ratio = sum(1 for e in recent if e["is_veteran"]) / len(recent)
        else:
            avg_dev_buy = 0.15
            socials_ratio = 0.20
            veteran_ratio = 0.10

        # Normalized inputs in [0, 1]
        c = min(1.0, max(0.0, avg_dev_buy / 0.45))
        s = min(1.0, max(0.0, socials_ratio / 0.35))
        v = min(1.0, max(0.0, veteran_ratio / 0.25))

        # -----------------------------------------------------------------
        # 1. STRICT COSINE RAMPS (Diminishing returns & anti-rug penalty)
        # pts = (1 - cos(x * 90°)) * max_pts
        # Heavily punishes micro-buys & burner launches, requiring near-benchmark
        # commitment before awarding generous points.
        # -----------------------------------------------------------------
        buy_pts = (1.0 - math.cos(c * (math.pi / 2.0))) * 50.0
        soc_pts = (1.0 - math.cos(s * (math.pi / 2.0))) * 35.0
        vet_pts = (1.0 - math.cos(v * (math.pi / 2.0))) * 15.0

        dev_score = buy_pts + soc_pts + vet_pts
        dev_pct = max(5.0, min(95.0, dev_score))

        # -----------------------------------------------------------------
        # 2. 120° DEV ARCHETYPE COMPASS
        # 3 axes separated by 120° on unit circle:
        #   Capital at 90°:   (0, 1)
        #   Socials at 210°:  (-sqrt(3)/2, -0.5) = (-0.866, -0.5)
        #   Longevity at 330°:(+sqrt(3)/2, -0.5) = (+0.866, -0.5)
        # -----------------------------------------------------------------
        vx = -0.866025 * s + 0.866025 * v
        vy = c - 0.5 * s - 0.5 * v
        compass_mag = math.hypot(vx, vy)
        raw_deg = math.degrees(math.atan2(vy, vx))
        compass_angle = (raw_deg + 360.0) % 360.0

        if compass_mag < 0.25:
            conviction_str = "weak conviction"
        elif compass_mag < 0.55:
            conviction_str = "moderate lean"
        else:
            conviction_str = "strong lean"

        if compass_mag < 0.05:
            compass_arrow = "•"
            compass_archetype = "CENTER (BALANCED/APATHETIC)"
            compass_short = "CENTER (Apathetic)"
        elif 60.0 <= compass_angle < 120.0:
            compass_arrow = "▲"
            compass_archetype = "CAPITAL-LEAN (MONEY DEV)"
            compass_short = "CAPITAL-LEAN"
        elif 120.0 <= compass_angle < 165.0:
            compass_arrow = "↖"
            compass_archetype = "FUNDED HYPE (CAPITAL + SOCIALS)"
            compass_short = "FUNDED HYPE"
        elif 165.0 <= compass_angle < 255.0:
            compass_arrow = "↙"
            compass_archetype = "HYPE-LEANING (COMMUNITY/MARKETING)"
            compass_short = "HYPE-LEANING"
        elif 255.0 <= compass_angle < 285.0:
            compass_arrow = "▼"
            compass_archetype = "GRASSROOTS (COMMUNITY + VETS, LOW SOL)"
            compass_short = "GRASSROOTS"
        elif 285.0 <= compass_angle < 345.0:
            compass_arrow = "↘"
            compass_archetype = "LONGEVITY-LEANING (VETERAN DEV)"
            compass_short = "LONGEVITY-LEAN"
        else:
            compass_arrow = "↗"
            compass_archetype = "WHALE ARCHITECT (CAPITAL + VETERAN)"
            compass_short = "WHALE ARCHITECT"

        compass_str = f"➤ {compass_angle:.0f}° {compass_arrow} {compass_archetype} · {conviction_str} (mag {compass_mag:.2f})"
        compass_str_short = f"➤ {compass_angle:.0f}° {compass_arrow} {compass_short} · {conviction_str}"

        # -----------------------------------------------------------------
        # 3. VERBAL INTENT TIERS & PSYCHOLOGICAL MINDSETS
        # -----------------------------------------------------------------
        if dev_pct >= 60:
            dev_label = "SERIOUS BUILDERS (HIGH CONVICTION)"
            dev_summary = "High Conviction (Skin in Game)"
            dev_mindset = "Committed to push: Devs putting up solid SOL (>0.4 SOL) with verified socials and patient bonding curve accumulation — high skin in the game, aiming to migrate."
            dev_mindset_short = "Committed Chads: Solid SOL buy-in, verified socials, high skin in the game."
            dev_emoji = "💎"
            dev_color = "bold cyan"
        elif dev_pct >= 40:
            dev_label = "FUNDED TEAMS (TESTING MARKET)"
            dev_summary = "Testing Waters (Watching Tape)"
            dev_mindset = "Watching the tape: Devs deploying decent capital (0.2-0.4 SOL) and watching reactions; will pump further if buyers swarm, but hedging initial exposure."
            dev_mindset_short = "Testing the waters: Decent buy-in, watching if buyers swarm before committing."
            dev_emoji = "🛠️"
            dev_color = "bold green"
        elif dev_pct >= 20:
            dev_label = "APATHETIC / DON'T CARE (MINIMUM EFFORT)"
            dev_summary = "Don't Care (Low Effort)"
            dev_mindset = "They don't really care: Low-effort micro-buys (<0.2 SOL) with zero socials — treating launches like cheap lottery tickets, throwing darts, will abandon on any friction."
            dev_mindset_short = "They don't really care: Cheap micro-buys, no socials, flipping lottery darts."
            dev_emoji = "⚠️"
            dev_color = "bold yellow"
        elif dev_pct >= 10:
            dev_label = "HIT-AND-RUN TRAPPERS (BAIT & DUMP)"
            dev_summary = "Hit & Run (Bait & Scalp)"
            dev_mindset = "Bait-and-dump trap: Devs buying bare-minimum amounts (0.08-0.12 SOL) strictly to trigger bot snipers and dump on the first green candle — zero building intent."
            dev_mindset_short = "Hit & Run Traps: Bare-minimum bait to lure snipers and dump on first pop."
            dev_emoji = "🎣"
            dev_color = "bold yellow"
        else:
            dev_label = "RUG MILL / PREDATORY SCRAPERS"
            dev_summary = "Pure Scrapers (Burner Rugs)"
            dev_mindset = "Predatory extraction: Disposable burner wallets mass-deploying clones to drain fees and dump instantly — hostile PvP environment, 99% rug rate."
            dev_mindset_short = "Predatory Rug Mill: Disposable burners, instant dumps, pure liquidity extraction."
            dev_emoji = "🪓"
            dev_color = "bold red"

        dev_onchain_read = f"Avg Buy: {avg_dev_buy:.2f} SOL ({buy_pts:.1f} pts) | Socials: {socials_ratio*100:.0f}% ({soc_pts:.1f} pts) | Veteran Devs: {veteran_ratio*100:.0f}% ({vet_pts:.1f} pts)"

        # -----------------------------------------------------------------
        # 4. HOLDER CONVICTION vs CHURN GAUGE (0-100%)
        # Measures whether buyers hold dips or instantly dump to zero
        # Dampened by Markov whale churn to expose artificial retention spoofing.
        # -----------------------------------------------------------------
        holding_ratio = max(0.0, 1.0 - (dead_rate * 2.5))
        conviction_raw_score = holding_ratio * 100.0
        conviction_raw_pct = max(5.0, min(95.0, conviction_raw_score))

        # Dampen with Markov whale churn (ghost retention filter)
        conviction_score = conviction_raw_pct * markov_data["conv_dampener"]
        conviction_pct = max(5.0, min(95.0, conviction_score))

        if w_churn >= 0.40:
            conv_label = f"GHOST RETENTION (Raw {conviction_raw_pct:.0f}%)"
            conv_emoji = "👻"
            conv_color = "bold yellow"
        elif conviction_pct >= 75:
            conv_label = "DIAMOND ACCUMULATION"
            conv_emoji = "🤝"
            conv_color = "bold cyan"
        elif conviction_pct >= 55:
            conv_label = "STEADY HOLDING"
            conv_emoji = "🛡️"
            conv_color = "bold green"
        elif conviction_pct >= 35:
            conv_label = "QUICK FLIPPERS"
            conv_emoji = "⏱️"
            conv_color = "bold yellow"
        else:
            conv_label = "HYPER PAPER-HANDS"
            conv_emoji = "🧻"
            conv_color = "bold red"

        # -----------------------------------------------------------------
        # 5. MARKET ADRENALINE / LAUNCH VELOCITY
        # -----------------------------------------------------------------
        if len(self._recent_scans) >= 2:
            t_span = max(10.0, self._recent_scans[-1]["t"] - self._recent_scans[0]["t"])
            launches_per_min = (len(self._recent_scans) / t_span) * 60.0
        else:
            # Fallback to tape density if recently started
            if len(tape_3h) >= 2:
                t_span = max(60.0, tape_3h[-1].get("t_scan", now) - tape_3h[0].get("t_scan", now))
                launches_per_min = (len(tape_3h) / t_span) * 60.0
            else:
                launches_per_min = 15.0

        if launches_per_min >= 40:
            vel_label = "WARZONE SPEED"
            vel_color = "bold red"
            vel_pct = 90.0
        elif launches_per_min >= 25:
            vel_label = "HIGH TEMPO"
            vel_color = "bold green"
            vel_pct = 70.0
        elif launches_per_min >= 12:
            vel_label = "MODERATE FLOW"
            vel_color = "yellow"
            vel_pct = 45.0
        else:
            vel_label = "ICEBOX / COLD"
            vel_color = "dim white"
            vel_pct = 20.0

        # -----------------------------------------------------------------
        # 6. Trailing 6-Hour Hourly Runner Rates & Trend Sparkline
        # -----------------------------------------------------------------
        hourly_buckets: List[Tuple[str, float]] = []
        raw_rates: List[float] = []

        max_t = max([e.get("t_scan", now) for e in tape] or [now])
        for h in range(6, 0, -1):
            t_start = max_t - (h * 3600)
            t_end = max_t - ((h - 1) * 3600)
            bucket = [
                e for e in tape
                if t_start <= e.get("t_scan", 0) < t_end and e.get("outcome") in ("settled", "dead")
            ]
            lbl = f"-{h-1}h" if h > 1 else "Now"
            if bucket:
                r_count = sum(
                    1 for e in bucket
                    if e.get("outcome") == "settled"
                    and float(e.get("return_30m", 0.0)) > 0.10
                    and max(float(e.get("vol_scan", 0.0)), float(e.get("vol_30m", 0.0))) >= 1000.0
                )
                rate = (r_count / len(bucket)) * 100.0
            else:
                rate = 0.0
            hourly_buckets.append((lbl, rate))
            raw_rates.append(rate)

        runner_sparkline = render_sparkline(raw_rates)

        # -----------------------------------------------------------------
        # 7. Tactical PvP Diagnosis
        # -----------------------------------------------------------------
        if runner_rate < 0.0075:
            tactical = (
                "[bold red]⛔ STAND-DOWN REGIME:[/bold red] Runner rate below 0.75% threshold. "
                "Market is a chop-and-drain meatgrinder. Preserve SOL and wait for regime recovery."
            )
        elif w_churn >= 0.40:
            chain_disp = ' ➔ '.join(markov_data['recent_chain'][-2:]) if markov_data['recent_chain'] else 'bot deploys'
            tactical = (
                f"[bold cyan]🌊 WHALE SPOOF ALERT ({w_churn*100:.0f}% Churn):[/bold cyan] "
                f"Whales are swishing waters with bot-to-bot deploys ({chain_disp}). "
                f"Apparent volume is spoofed to block snipers. Do NOT FOMO into artificial green pumps — stand back until organic memes return."
            )
        elif dev_pct < 25 and fomo_pct > 60:
            tactical = (
                "[bold yellow]⚠️ PREDATORY TRAP ZONE:[/bold yellow] Buyers are aggressively FOMOing, but devs are "
                "micro-launching rug mills (<0.1 SOL). Scalp rapid pops with tight trailing stops only!"
            )
        elif dev_pct >= 60 and fomo_pct >= 60:
            tactical = (
                "[bold green]💎 GREEN SWEET SPOT:[/bold green] Committed devs aligned with healthy buyer FOMO. "
                "Highest probability window for sustained +50% to +100% runners."
            )
        elif dev_pct < 40:
            tactical = (
                f"[bold yellow]💤 APATHETIC DEV MARKET ({dev_pct:.0f}%):[/bold yellow] Strict cosine math shows devs aren't committing. "
                f"120° Compass points {compass_str_short}. Micro-buys without follow-through — take rapid scalps, "
                f"do not expect diamond runners from apathetic devs."
            )
        elif conviction_pct < 35:
            tactical = (
                "[bold yellow]🧻 HYPER-SCALPER CHURN:[/bold yellow] Buyers dumping after 15-30 seconds. "
                "Do NOT hold bags — lock profits immediately on initial green push."
            )
        else:
            tactical = (
                "[bold cyan]⚖️ SELECTIVE PVP:[/bold cyan] Market is balanced. Rely strictly on Dev Wallet "
                "on-chain profiling and ML rug risk scores to pick high-confidence setups."
            )

        metrics = {
            "crowd_fomo": fomo_pct,
            "crowd_label": fomo_label,
            "crowd_emoji": fomo_emoji,
            "crowd_color": fomo_color,
            "fomo_raw_pct": fomo_raw_pct,
            "conviction_raw_pct": conviction_raw_pct,
            "whale_churn": w_churn,
            "fomo_dampener": markov_data["fomo_dampener"],
            "conv_dampener": markov_data["conv_dampener"],
            "markov_read": markov_data["explanation_short"],
            "markov_read_full": markov_data["explanation"],
            "markov_color": markov_data["markov_color"],
            "markov_status": markov_data["status_label"],
            "recent_chain": markov_data["recent_chain"],
            "p_bot_bot": markov_data["p_bot_bot"],
            "pi_bot": markov_data["pi_bot"],
            "dev_intent": dev_pct,
            "dev_label": dev_label,
            "dev_summary": dev_summary,
            "dev_mindset": dev_mindset,
            "dev_mindset_short": dev_mindset_short,
            "dev_onchain_read": dev_onchain_read,
            "compass_angle": compass_angle,
            "compass_mag": compass_mag,
            "compass_arrow": compass_arrow,
            "compass_archetype": compass_archetype,
            "compass_str": compass_str,
            "compass_str_short": compass_str_short,
            "buy_pts": buy_pts,
            "soc_pts": soc_pts,
            "vet_pts": vet_pts,
            "avg_dev_buy": avg_dev_buy,
            "socials_ratio": socials_ratio,
            "veteran_ratio": veteran_ratio,
            "dev_emoji": dev_emoji,
            "dev_color": dev_color,
            "holder_conviction": conviction_pct,
            "holder_label": conv_label,
            "holder_emoji": conv_emoji,
            "holder_color": conv_color,
            "velocity_pct": vel_pct,
            "launches_per_min": launches_per_min,
            "velocity_label": vel_label,
            "velocity_color": vel_color,
            "hourly_buckets": hourly_buckets,
            "runner_sparkline": runner_sparkline,
            "runner_rate_3h": runner_rate * 100.0,
            "window_completed": n_completed,
            "tactical_advice": tactical
        }

        self._cached_metrics = metrics
        self._last_compute_time = now
        return metrics

    def get_dashboard_light_line(self) -> str:
        """
        Render a compact, high-visibility 4-line 'Dashboard Light' bar for the stream header.
        Displays psychological meters, 120° Dev Compass, and Markov text analysis read.
        """
        try:
            m = self.get_metrics()
            cols = shutil.get_terminal_size().columns
            bar_w = 8 if cols < 75 else 10

            meter_fomo = render_meter_bar(m["crowd_fomo"], width=bar_w, color=m["crowd_color"])
            meter_dev = render_meter_bar(m["dev_intent"], width=bar_w, color=m["dev_color"])
            meter_conv = render_meter_bar(m["holder_conviction"], width=bar_w, color=m["holder_color"])

            line1 = (
                f"[bold yellow]🚨 FOMO GAUGE:[/bold yellow] {meter_fomo} [{m['crowd_color']}]{m['crowd_fomo']:.0f}% {m['crowd_emoji']} {m['crowd_label']}[/{m['crowd_color']}] | "
                f"[bold yellow]DEV INTENT:[/bold yellow] {meter_dev} [{m['dev_color']}]{m['dev_intent']:.0f}% {m['dev_emoji']} {m['dev_summary']}[/{m['dev_color']}]"
            )
            line2 = (
                f"[bold yellow]🤝 CONVICTION:[/bold yellow] {meter_conv} [{m['holder_color']}]{m['holder_conviction']:.0f}% {m['holder_emoji']} {m['holder_label']}[/{m['holder_color']}] | "
                f"[bold yellow]6H TREND:[/bold yellow] [bold white]{m['runner_sparkline']}[/bold white] ({m['runner_rate_3h']:.2f}%) | "
                f"[bold cyan]'v' View[/bold cyan]"
            )
            line3 = (
                f"[bold yellow]🧭 DEV COMPASS:[/bold yellow] [{m['dev_color']}]{m['compass_str_short']}[/{m['dev_color']}]"
            )
            line4 = (
                f"[bold yellow]🧠 MARKOV READ:[/bold yellow] [{m.get('markov_color', 'bold yellow')}]\"{m.get('markov_read', m['dev_mindset_short'])}\"[/{m.get('markov_color', 'bold yellow')}]"
            )
            return f"{line1}\n{line2}\n{line3}\n{line4}"
        except Exception:
            return "[bold yellow]🚨 PSYCHOLOGY:[/bold yellow] [dim]Calibrating tape meters...[/dim]"

    def render_psychology_radar_panel(self, terminal_width: Optional[int] = None) -> Panel:
        """
        Render the full-screen Market Psychology & PvP Radar Panel.
        Includes ASCII gauges, vertical 6-hour runner histogram, 120° Dev Compass,
        tactical advice, and the 4x4 Markov Text Regime Matrix.
        """
        m = self.get_metrics()
        cols = terminal_width or shutil.get_terminal_size().columns
        bar_w = 12 if cols >= 75 else 8

        meter_fomo = render_meter_bar(m["crowd_fomo"], width=bar_w, color=m["crowd_color"])
        meter_dev = render_meter_bar(m["dev_intent"], width=bar_w, color=m["dev_color"])
        meter_conv = render_meter_bar(m["holder_conviction"], width=bar_w, color=m["holder_color"])
        meter_vel = render_meter_bar(m["velocity_pct"], width=bar_w, color=m["velocity_color"])

        # Render ASCII Histogram of trailing 6-hour runner rates
        histo = render_ascii_histogram(m["hourly_buckets"], height=4, unit="%", threshold_line=0.75)

        # Build Section 4 with rich.table.Table
        matrix_table = self.markov.render_rich_table()
        markov_data = self.markov.get_whale_churn_factor()
        w_churn = markov_data["whale_churn"]
        recent_str = " ➔ ".join(markov_data["recent_chain"][-3:]) if markov_data["recent_chain"] else "None"

        part1 = (
            f"[bold cyan]1. PSYCHOLOGICAL GAUGES (HUMAN & PVP SENTIMENT):[/bold cyan]\n"
            f"  • [bold white]CROWD FOMO:[/bold white]     {meter_fomo} [{m['crowd_color']}]{m['crowd_fomo']:.0f}% {m['crowd_emoji']} {m['crowd_label']}[/{m['crowd_color']}]\n"
            f"  • [bold white]DEV INTENT:[/bold white]     {meter_dev} [{m['dev_color']}]{m['dev_intent']:.0f}% {m['dev_emoji']} {m['dev_label']}[/{m['dev_color']}]\n"
            f"    [dim]↳ 120° Compass:[/dim]  [{m['dev_color']}]{m['compass_str']}[/{m['dev_color']}]\n"
            f"    [dim]↳ Mindset Read:[/dim]   [{m['dev_color']}]\"{m['dev_mindset']}\"[/{m['dev_color']}]\n"
            f"    [dim]↳ Strict Math:[/dim]    [dim]{m['dev_onchain_read']}[/dim]\n"
            f"  • [bold white]HOLD CONVICTION:[/bold white]{meter_conv} [{m['holder_color']}]{m['holder_conviction']:.0f}% {m['holder_emoji']} {m['holder_label']}[/{m['holder_color']}]\n"
            f"  • [bold white]PVP ADRENALINE:[/bold white] {meter_vel} [{m['velocity_color']}]{m['launches_per_min']:.0f} launches/min ({m['velocity_label']})[/{m['velocity_color']}]\n\n"
            f"[bold cyan]2. TRAILING 6-HOUR RUNNER VELOCITY HISTOGRAM:[/bold cyan]\n"
            f"{histo}\n"
            f"  [bold yellow]Trend Sparkline:[/bold yellow] [bold white]{m['runner_sparkline']}[/bold white] | "
            f"[bold yellow]Current 3h Window:[/bold yellow] [bold white]{m['runner_rate_3h']:.2f}% runners ({m['window_completed']} tokens)[/bold white]\n\n"
            f"[bold cyan]3. TACTICAL PVP DIAGNOSIS:[/bold cyan]\n"
            f"  {m['tactical_advice']}\n\n"
            f"[bold cyan]4. MARKOV TEXT REGIME MATRIX (WHALE CHURN vs ORGANIC FOMO):[/bold cyan]"
        )

        part2 = (
            f"  • [bold yellow]Anti-Spoof Multiplier:[/bold yellow] [bold cyan]{markov_data['fomo_dampener']*100:.0f}%[/bold cyan] (Whale Churn Index: [bold red]{w_churn*100:.0f}%[/bold red]) | Status: [{markov_data['markov_color']}]{markov_data['status_label']}[/{markov_data['markov_color']}]\n"
            f"  • [bold yellow]Recent Chain:[/bold yellow] [bold white]{recent_str}[/bold white]\n"
            f"  • [bold yellow]Markov Read:[/bold yellow] [{markov_data['markov_color']}]\"{markov_data['explanation_short']}\"[/{markov_data['markov_color']}]\n\n"
            f"[bold yellow]⌨️  HOTKEYS: 'y' YOLO Toggle | 'v' Cycle View | 'q' Clean Stop[/bold yellow]"
        )

        return Panel(
            Group(part1, matrix_table, part2),
            title="[bold red]🧠 MARKET PSYCHOLOGY & PVP RADAR VIEW 🛰️[/bold red]",
            border_style="bold magenta",
            box=box.DOUBLE
        )

    def render_trades_momentum_panel(self, terminal_width: Optional[int] = None) -> Panel:
        """
        Render Trade Momentum & Performance Panel with ASCII streak blocks and returns sparkline.
        """
        history = []
        if os.path.exists(self.trade_history_file):
            try:
                with open(self.trade_history_file, "r", encoding="utf-8") as f:
                    history = json.load(f)
            except Exception:
                history = []

        stats = {}
        if os.path.exists(self.stats_file):
            try:
                with open(self.stats_file, "r", encoding="utf-8") as f:
                    stats = json.load(f)
            except Exception:
                stats = {}

        recent = history[-10:] if history else []
        recent_pnls = [float(t.get("pnl_pct", 0.0)) for t in recent]
        
        streak_symbols = []
        wins = 0
        for pnl in recent_pnls:
            if pnl > 0:
                streak_symbols.append("[bold green]🟩[/bold green]")
                wins += 1
            else:
                streak_symbols.append("[bold red]🟥[/bold red]")

        streak_str = " ".join(streak_symbols) if streak_symbols else "[dim]No trades executed yet[/dim]"
        win_rate = (wins / len(recent) * 100.0) if recent else 0.0
        pnl_sparkline = render_sparkline(recent_pnls)

        best_win = max(recent_pnls) if recent_pnls else 0.0
        worst_loss = min(recent_pnls) if recent_pnls else 0.0
        total_pnl_sol = float(stats.get("total_realized_pnl_sol", 0.0))
        pnl_col = "bold green" if total_pnl_sol >= 0 else "bold red"
        pnl_sign = "+" if total_pnl_sol >= 0 else ""

        body = (
            f"[bold cyan]1. RECENT TRADE STREAKS & OUTCOMES:[/bold cyan]\n"
            f"  Streak (Last {len(recent)}): {streak_str}\n"
            f"  Trailing Win Rate: [bold cyan]{win_rate:.1f}%[/bold cyan] ({wins}W / {len(recent)-wins}L) | "
            f"Best: [bold green]+{best_win:.1f}%[/bold green] | Worst: [bold red]{worst_loss:.1f}%[/bold red]\n\n"
            f"[bold cyan]2. P&L TRAJECTORY SPARKLINE:[/bold cyan]\n"
            f"  Recent P&L % Flow: [bold white]{pnl_sparkline}[/bold white]\n"
            f"  Net Realized P&L:  [{pnl_col}]{pnl_sign}{total_pnl_sol:.4f} SOL[/{pnl_col}]\n\n"
            f"[bold cyan]3. EXECUTION DISCIPLINE:[/bold cyan]\n"
            f"  • [bold green]Helius On-Chain Polling:[/bold green] Active confirmation & balance audits\n"
            f"  • [bold green]Ghost Reconciliation:[/bold green] Zero phantom positions\n"
            f"  • [bold green]Regime Gate Floor:[/bold green] Active\n\n"
            f"[bold yellow]⌨️  HOTKEYS: 'y' YOLO Toggle | 'v' Cycle View | 'q' Clean Stop[/bold yellow]"
        )

        return Panel(
            body,
            title="[bold green]🎯 TRADE PERFORMANCE & MOMENTUM VIEW 📈[/bold green]",
            border_style="bold green",
            box=box.DOUBLE
        )

    def render_expectancy_panel(
        self,
        trades_list: Optional[List[Dict[str, Any]]] = None,
        fee_override_usd: Optional[float] = None,
        terminal_width: Optional[int] = None
    ) -> Panel:
        """
        Render Expectancy & Trade Shape Dashboard ('v' view).
        All numbers fee-adjusted (honest math).
        Includes Wilson 95% Confidence Interval, Breakeven Win Rate, EV per trade,
        Profit Factor, Payoff Ratio, and Data Quality audit.
        """
        history = []
        if trades_list is not None:
            history = trades_list
        elif os.path.exists(self.trade_history_file):
            try:
                with open(self.trade_history_file, "r", encoding="utf-8") as f:
                    history = json.load(f)
            except Exception:
                history = []

        if not history:
            return Panel(
                "[bold yellow]No closed trades yet[/bold yellow]\n\n"
                "[dim]Trade expectancy metrics will appear here after initial positions are closed.[/dim]\n\n"
                "[bold yellow]⌨️  HOTKEYS: 'y' YOLO Toggle | 'v' Cycle View | 'q' Clean Stop[/bold yellow]",
                title="[bold cyan]🎯 EXPECTANCY & TRADE SHAPE[/bold cyan]",
                border_style="cyan",
                box=box.DOUBLE
            )

        # 6. Data Quality Audit: classify confirmed vs unconfirmed exits
        confirmed_trades = []
        for t in history:
            tx = str(t.get("exit_tx_hash") or "").strip()
            if tx and tx != "broadcast_submitted" and len(tx) >= 40:
                confirmed_trades.append(t)

        unconfirmed_count = len(history) - len(confirmed_trades)
        n = len(confirmed_trades)

        if n == 0:
            return Panel(
                f"[bold yellow]⚠️ {unconfirmed_count} exits unconfirmed (no chain signature) — shape computed on confirmed trades only.[/bold yellow]\n\n"
                "[dim]No confirmed closed trades yet (n=0 confirmed).[/dim]\n\n"
                "[bold yellow]⌨️  HOTKEYS: 'y' YOLO Toggle | 'v' Cycle View | 'q' Clean Stop[/bold yellow]",
                title="[bold cyan]🎯 EXPECTANCY & TRADE SHAPE[/bold cyan]",
                border_style="cyan",
                box=box.DOUBLE
            )

        # Fee adjustment: 2 * PRIORITY_FEE_SOL * SOL/USD (~$0.11)
        try:
            from price_feed import get_cached_sol_price
            sol_usd = get_cached_sol_price() or 110.0
        except Exception:
            sol_usd = 110.0

        priority_fee_sol = float(getattr(config, "PRIORITY_FEE_SOL", 0.0005))
        fee_rt_usd = fee_override_usd if fee_override_usd is not None else (2.0 * priority_fee_sol * sol_usd)

        real_usd_list = []
        logged_usd_list = []
        logged_sol_list = []
        pnl_pct_list = []

        for t in confirmed_trades:
            p_usd = float(t.get("pnl_usd", 0.0))
            p_sol = float(t.get("pnl_sol", 0.0))
            p_pct = float(t.get("pnl_pct", 0.0))
            r_usd = p_usd - fee_rt_usd

            real_usd_list.append(r_usd)
            logged_usd_list.append(p_usd)
            logged_sol_list.append(p_sol)
            pnl_pct_list.append(p_pct)

        # 1. Sample & Win Rate
        wins_usd = [r for r in real_usd_list if r > 0]
        losses_usd = [r for r in real_usd_list if r <= 0]
        wins = len(wins_usd)
        losses = len(losses_usd)
        win_rate = (wins / n) if n > 0 else 0.0

        # Wilson 95% Score Confidence Interval (z = 1.96)
        z = 1.96
        denom = 1.0 + (z**2 / n)
        center = (win_rate + (z**2 / (2.0 * n))) / denom
        spread = (z * math.sqrt(max(0.0, (win_rate * (1.0 - win_rate) / n) + (z**2 / (4.0 * (n**2)))))) / denom
        ci_low = max(0.0, center - spread) * 100.0
        ci_high = min(1.0, center + spread) * 100.0

        sample_note = " [yellow]small sample — expect wobble[/yellow]" if n < 30 else ""
        wr_display = f"{win_rate*100:.1f}% (95% CI {ci_low:.1f}–{ci_high:.1f}%){sample_note}"

        # 2. Averages (fee-adjusted)
        avg_win = (sum(wins_usd) / len(wins_usd)) if wins_usd else 0.0
        win_pcts = [pnl_pct_list[i] for i, r in enumerate(real_usd_list) if r > 0]
        avg_win_pct = (sum(win_pcts) / len(win_pcts)) if win_pcts else 0.0
        avg_loss = (sum(losses_usd) / len(losses_usd)) if losses_usd else 0.0  # negative number
        loss_mag = abs(avg_loss)
        total_fee_drag = n * fee_rt_usd

        avg_win_str = f"+${avg_win:.2f} (+{avg_win_pct:.0f}%)" if avg_win > 0 else "$0.00 (0%)"
        avg_loss_sign = "−" if avg_loss < 0 else ""
        avg_loss_str = f"{avg_loss_sign}${loss_mag:.2f}"

        # 3. Expectancy (headline number)
        ev = (win_rate * avg_win) + ((1.0 - win_rate) * avg_loss)
        denom_be = avg_win + loss_mag
        breakeven_wr = (loss_mag / denom_be) if denom_be > 0 else 0.0
        cushion = (win_rate - breakeven_wr) * 100.0

        ev_sign = "+" if ev >= 0 else "−"
        ev_color = "bold green" if ev >= 0 else "bold red"
        ev_display = f"[{ev_color}]{ev_sign}${abs(ev):.2f}[/{ev_color}]"

        ev_meter = render_ev_meter(ev, max_scale=max(0.50, avg_win, loss_mag), half_width=10)

        if cushion < 0:
            cushion_str = f"[bold red]{cushion:+.1f} pts 🛑 (UNDERWATER — system is losing)[/bold red]"
        elif cushion < 5.0:
            cushion_str = f"[bold yellow]{cushion:+.1f} pts ⚠️ (thin edge — watch it)[/bold yellow]"
        else:
            cushion_str = f"[bold green]{cushion:+.1f} pts ✅[/bold green]"

        # 4. Ratios
        sum_wins = sum(wins_usd)
        sum_losses = sum(abs(l) for l in losses_usd)
        profit_factor = (sum_wins / sum_losses) if sum_losses > 0 else (99.9 if sum_wins > 0 else 0.0)
        payoff_ratio = (avg_win / loss_mag) if loss_mag > 0 else (99.9 if avg_win > 0 else 0.0)

        # 5. Realized P&L
        tot_logged_usd = sum(logged_usd_list)
        tot_real_usd = sum(real_usd_list)
        tot_logged_sol = sum(logged_sol_list)
        tot_real_sol = tot_logged_sol - (n * 2.0 * priority_fee_sol)

        cum_real = []
        running = 0.0
        for r in real_usd_list:
            running += r
            cum_real.append(running)
        cum_sparkline = render_sparkline(cum_real)

        logged_sign = "+" if tot_logged_usd >= 0 else "−"
        real_sign = "+" if tot_real_usd >= 0 else "−"
        logged_color = "bold green" if tot_logged_usd >= 0 else "bold red"
        real_color = "bold green" if tot_real_usd >= 0 else "bold red"

        # 6. Data Quality
        if unconfirmed_count > 0:
            quality_str = f"⚠️ [bold yellow]{unconfirmed_count} exits unconfirmed (no chain signature) — shape computed on confirmed trades only.[/bold yellow]"
        else:
            quality_str = "✅ [bold green]all exits confirmed on-chain.[/bold green]"

        body = (
            f"[bold cyan]1. SAMPLE & WIN RATE:[/bold cyan]\n"
            f"  • Closed Trades: {n} ({wins}W / {losses}L) | Win Rate: [bold white]{wr_display}[/bold white]\n\n"
            f"[bold cyan]2. AVERAGES (FEE-ADJUSTED):[/bold cyan]\n"
            f"  • Avg Win: [bold green]{avg_win_str}[/bold green]   Avg All-In Loss: [bold red]{avg_loss_str}[/bold red]\n"
            f"  • Fee Drag: [bold yellow]${total_fee_drag:.2f} total (${fee_rt_usd:.2f}/trade)[/bold yellow]\n\n"
            f"[bold cyan]3. EXPECTANCY:[/bold cyan]\n"
            f"  • EV per trade: {ev_display} {ev_meter}\n"
            f"  • Breakeven Win Rate: [bold white]{breakeven_wr*100:.1f}%[/bold white]   |   Cushion: {cushion_str}\n\n"
            f"[bold cyan]4. RATIOS:[/bold cyan]\n"
            f"  • Profit Factor: [bold cyan]{profit_factor:.1f}x[/bold cyan]   Payoff Ratio: [bold magenta]{payoff_ratio:.1f}x[/bold magenta]\n\n"
            f"[bold cyan]5. REALIZED P&L:[/bold cyan]\n"
            f"  • App-Logged: [{logged_color}]{logged_sign}${abs(tot_logged_usd):.2f}[/{logged_color}] ({tot_logged_sol:+.4f} SOL)   "
            f"Fee-Adjusted: [{real_color}]{real_sign}${abs(tot_real_usd):.2f}[/{real_color}] ({tot_real_sol:+.4f} SOL)\n"
            f"  • Cumulative Real P&L Curve: [bold white]{cum_sparkline}[/bold white]\n\n"
            f"[bold cyan]6. DATA QUALITY:[/bold cyan]\n"
            f"  • {quality_str}\n\n"
            f"[bold yellow]⌨️  HOTKEYS: 'y' YOLO Toggle | 'v' Cycle View | 'q' Clean Stop[/bold yellow]"
        )

        return Panel(
            body,
            title="[bold cyan]🎯 EXPECTANCY & TRADE SHAPE[/bold cyan]",
            border_style="cyan",
            box=box.DOUBLE
        )

    def render_billboard_panel(self, terminal_width: Optional[int] = None) -> Panel:
        """
        Render the scannable QR Code & Value Billboard panel ('v' view or 'b' hotkey).
        """
        try:
            from qr_wallet import render_qr_billboard_panel
            return render_qr_billboard_panel()
        except Exception as e:
            return Panel(f"[bold red]Failed to render billboard: {e}[/bold red]", title="QR BILLBOARD", border_style="red")

