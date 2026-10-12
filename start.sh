#!/data/data/com.termux/files/usr/bin/bash
# ==============================================================================
# Solana PumpPortal & DexScreener ML Demo Sniper Bot
# Designed for Termux on Android & Bigo Live Screen Streaming
# ==============================================================================

echo "========================================================"
echo "  🚀 STARTING PUMP ML SNIPER (HELIUS RPC REAL TRADING)"
echo "  🧠 RUG MODEL V2 + ON-CHAIN DEV WALLET PROFILING"
echo "  📱 OPTIMIZED FOR BIGO LIVE PHONE STREAMING"
echo "========================================================"
echo "Tip: Make sure your phone's media & alert volume is UP"
echo "so your stream viewers can hear the loud trade bells!"
echo "Tip: Run './start.sh -y' to activate YOLO MODE (trade all the way to zero)!"
echo "--------------------------------------------------------"

# Run bot with any passed arguments (e.g., --balance 10.0 --buy-amount 0.5)
python3 /data/data/com.termux/files/home/crypto/bot.py "$@"
