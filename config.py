"""
Configuration settings for PumpPortal & DexScreener ML Live Sniper Bot.
Optimized for Termux on Android & Bigo Live streaming.
"""

import os


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

# Helius RPC configuration
HELIUS_API_KEY = os.getenv("HELIUS_API_KEY", "")
HELIUS_RPC_URL = os.getenv(
    "HELIUS_RPC_URL",
    f"https://mainnet.helius-rpc.com/?api-key={HELIUS_API_KEY}" if HELIUS_API_KEY else "https://api.mainnet-beta.solana.com"
)

# Solana Wallet configuration
SOLANA_PRIVATE_KEY = os.getenv("SOLANA_PRIVATE_KEY", "")

# Trading Execution Settings
# 'real' executes live trades using Helius RPC & Solana wallet key
# 'paper' runs safe simulated paper trades
TRADING_MODE = os.getenv("TRADING_MODE", "paper")

DEFAULT_BUY_AMOUNT_SOL = float(os.getenv("DEFAULT_BUY_AMOUNT_SOL", "0.006"))    # SOL spent per trade (~$0.65 per trade at current SOL price)
YOLO_MODE = os.getenv("YOLO_MODE", "false").lower() in ("true", "1", "yes")     # YOLO mode: bypass max positions and trade all the way to zero balance
MAX_OPEN_POSITIONS = int(os.getenv("MAX_OPEN_POSITIONS", "3"))                # Max concurrent holdings (ignored when YOLO_MODE is active)
TAKE_PROFIT_PCT = float(os.getenv("TAKE_PROFIT_PCT", "50.0"))                 # Take profit at +50% gain
STOP_LOSS_PCT = float(os.getenv("STOP_LOSS_PCT", "25.0"))                     # Stop loss at -25% loss
SLIPPAGE_PCT = float(os.getenv("SLIPPAGE_PCT", "15.0"))                       # Slippage tolerance %
PRIORITY_FEE_SOL = float(os.getenv("PRIORITY_FEE_SOL", "0.0005"))              # Priority fee for fast transaction inclusion
DEV_WALLET_PAGE_CAP = int(os.getenv("DEV_WALLET_PAGE_CAP", "5"))              # Max pages of 1,000 txns to query for dev wallet

# Paper Trading Fallback Balance
DEMO_INITIAL_BALANCE_SOL = 10.0

# Machine Learning / Rug Filter Settings
RUG_MODEL_FILE = "rug_model_v2_devwallet.json"
ML_RUG_THRESHOLD = 0.15           # Default from JSON (veto if p_rug >= threshold)

# Anti-Rug Guardrails & Hardened Dev Buy Multi-Factor Gate
MIN_DEV_BUY_SOL = 0.08                  # Raised baseline minimum dev buy floor (blocks < 0.08 SOL)
DEV_BUY_SCRUTINY_THRESHOLD_SOL = 0.25   # Buys below 0.25 SOL require strict multi-factor verification
MIN_DEV_WALLET_TXNS_LOW_BUY = 15        # Minimum transactions required if dev buy < 0.25 SOL
MIN_DEV_WALLET_AGE_DAYS_LOW_BUY = 1.0   # Minimum wallet age in days if dev buy < 0.25 SOL
MAX_DEV_SUPPLY_PCT_LOW_BUY = 0.060      # Max supply share dev can hold if dev buy < 0.25 SOL (6.0%)
REQUIRE_MULTI_SOCIALS_LOW_BUY = True    # Require >= 2 valid socials for micro-buys
BLOCK_SPAM_KEYWORDS = True              # Block phishing/test/copycat keywords (test, airdrop, claim, etc.)
STRICT_SOCIAL_URL_VALIDATION = True     # Block placeholder root domains (x.com, t.me, pump.fun, etc.)
BLOCK_FARMED_WALLETS = True             # Veto aged wallets (> 30 days) with < 10 transactions
MAX_DEV_BUY_SOL = 0.40                  # Veto dev buy >= 0.40 SOL on low-activity wallets (< 50 txns)
REQUIRE_SOCIALS = True                  # Veto tokens with zero verified social links

# On-Chain Confirmation & Liquidity Sanity
CONFIRM_TIMEOUT_SEC = 12.0        # Seconds to wait for Helius RPC confirmation
MIN_DEX_LIQUIDITY_USD = 1000.0    # Min DexScreener liquidity required to trust fallback price
MAX_PRICE_SPIKE_RATIO = 3.0       # Max single-tick price multiple allowed without liquid depth

# Market Regime Guard Settings
REGIME_WINDOW_HOURS = 3           # Trailing window in hours for regime calculation
REGIME_MIN_VOL_USD = 1000         # Min USD volume required for a 30m runner (+10%)
REGIME_STAND_DOWN_THRESHOLD = 0.0075 # Stand down if runners / completed < 0.75%
REGIME_MIN_TOKENS = 500           # Min completed tokens required in window to trade
REGIME_RECOMPUTE_SEC = 900        # Recompute regime score every 15 minutes
REGIME_TAPE_FILE = "regime_tape.jsonl" # Tape file recording sampled scans & outcomes
REGIME_STATE_FILE = "regime_state.json" # Cached regime state file
REGIME_SAMPLE_EVERY = 3           # Record every 3rd scanned token
REGIME_GUARD_ENABLED = True       # Enable market regime guard gate

# API & WebSocket Endpoints
PUMPPORTAL_WS_URL = "wss://pumpportal.fun/api/data"
PUMPPORTAL_TRADE_URL = "https://pumpportal.fun/api/trade-local"
DEXSCREENER_API_BASE = "https://api.dexscreener.com/latest/dex"
DEXSCREENER_ORDERS_BASE = "https://api.dexscreener.com/orders/v1/solana"

# Solana RPC Endpoints (Helius RPC is primary)
SOLANA_RPC_ENDPOINTS = [
    HELIUS_RPC_URL,
    "https://api.mainnet-beta.solana.com",
    "https://solana-rpc.publicnode.com"
]

# Fast IPFS Gateways for metadata resolution
IPFS_GATEWAYS = [
    "https://ipfs.filebase.io/ipfs/",
    "https://gateway.pinata.cloud/ipfs/",
    "https://dweb.link/ipfs/"
]

# UI & Sound
SOUND_ENABLED = True
LOUD_TERMINAL_BELLS = 3          # Number of \a bells for big events
TERMINAL_FONT = "small"          # Figlet font: 'small' or 'slant' (great for mobile)
REFRESH_INTERVAL_SEC = 2.0       # Position monitor refresh interval

# Market Psychology & ASCII Dashboard Settings
PSYCHOLOGY_RADAR_ENABLED = True
DEFAULT_DASHBOARD_VIEW = "stream"  # "stream", "psychology", "trades"
PSYCHOLOGY_CACHE_TTL_SEC = 12.0

# Trader Guardian Settings (Psychological Safeguards)
DAILY_MAX_LOSS_SOL = 0.08
LOSS_STREAK_LIMIT = 4
COOLDOWN_MINUTES = 30
SESSION_NUDGE_HOURS = 4
SESSION_WARN_HOURS = 8
GUARDIAN_STATE_FILE = "guardian_state.json"
USE_PIXEL_BANNERS = True
