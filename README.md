# 🚀 Pump ML Rug Sniper (Demo Paper Trading Bot)

A high-speed **Solana PumpPortal & DexScreener Paper Trading Bot** running directly in **Termux on Android**, featuring **Machine Learning rug detection via NumPy**, on-chain bonding curve analysis, and **loud, massive text visuals designed for live streaming on Bigo Live**.

---

## 🌟 Key Highlights

- **⚡ Real-Time PumpPortal WebSocket**: Subscribes directly to `wss://pumpportal.fun/api/data` to capture new token creation events within milliseconds of launch.
- **🔍 DexScreener & IPFS Intelligence**: Automatically resolves metadata (Twitter/X, Telegram, Website, Description) and queries DexScreener for liquidity, pairs, volume, and paid boosts.
- **🧠 Pure NumPy Neural Network (`RugFilterML`)**: 
  - Predicts Rug Probability $P(\text{Rug}) \in [0.0, 1.0]$.
  - Filters out quick dev dumps, bundled tokens, zero-social clones, and spam naming patterns.
  - **Online Adaptive Learning**: Automatically executes backpropagation (`dW = np.dot(X.T, dZ)`) when simulated trades hit take-profit or stop-loss, continually refining weights in real time!
- **🔗 Solana On-Chain Binary Deserializer**: Queries live Solana RPC nodes and unpacks the 49-byte pump.fun bonding curve binary struct to read real-time SOL reserves, calculate live prices, and catch dev dumping instantly.
- **💰 100% Risk-Free Demo Trading**: Paper trading engine starts with 10.0 SOL demo balance (configurable). Simulates bonding curve buys, sells, take-profits (+50%), and stop-losses (-25%).
- **📢 Stream-Ready Loud UI for Bigo Live**:
  - **Huge ASCII FIGlet Banners**: Massive, bold block letters for `BUY!`, `PROFIT!`, and token symbols like `$OBRIA` that mobile stream viewers can easily read.
  - **Audible Beeps (`\a`)**: Rings the terminal bell loudly through the phone speaker whenever a trade or alert occurs.
  - **High-Contrast Neon Styling**: Formatted with Rich panels and tables tailored for mobile phone dimensions (40–80 columns).

---

## 📁 Project Architecture

```
/data/data/com.termux/files/home/crypto/
├── bot.py             # Main bot application & async orchestrator
├── ml_engine.py       # NumPy Neural Network Rug Classifier & Online Learner
├── pumpportal.py      # Real-time WebSocket client for pump.fun new launches
├── dexscreener.py     # DexScreener API client (pairs, liquidity, boosts)
├── metadata.py        # Asynchronous IPFS resolver (Twitter, TG, Website)
├── onchain.py         # On-chain Solana RPC pump.fun bonding curve reader
├── trader.py          # Paper trading engine (portfolio, positions, P&L)
├── ui.py              # Loud terminal UI, audio bells & big FIGlet banners
├── config.py          # Global configurations & thresholds
├── test_simulation.py # Offline visual & audio demo simulator
├── start.sh           # One-command shell launcher
└── requirements.txt   # Python package dependencies
```

---

## 🚀 Quick Start Guide

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Configure Environment Variables
Copy the template and configure your keys (optional for paper trading, required for live trading):
```bash
cp .env.example .env
# Edit .env with your Helius API key and optional Solana private key
```

### 3. Test the Visual & Audio Flow (Recommended before streaming)
Run the test simulation to see the loud bells, big banners, active trade tracking, and take-profit animations:
```bash
python3 test_simulation.py
```

### 4. Launch the Live Bot
Start listening to live Solana launches:
```bash
./start.sh
# or directly:
python3 bot.py
```

### 5. Custom CLI Options
You can customize demo parameters directly via command line flags:
```bash
# Start with 20 SOL demo balance, 1.0 SOL buy size, +75% TP, -20% SL:
python3 bot.py --balance 20.0 --buy-amount 1.0 --tp 75.0 --sl 20.0

# Adjust ML Rug Risk Threshold (default 0.35 = buy if <= 35% rug risk):
python3 bot.py --threshold 0.40

# Run in silent mode (no terminal beeps):
python3 bot.py --quiet
```

---

## 📱 Tips for Streaming on Bigo Live

1. **Volume**: Make sure your phone's media and system volume is turned up so viewers hear the loud alert bells (`\a`) when a gem is bought or sold.
2. **Font Size**: In Termux, you can pinch-to-zoom with two fingers to adjust font size to make the banners even bigger on your screen.
3. **Orientation**: The bot is optimized to fit within 50 to 80 character columns, so it displays cleanly in portrait mode without text wrapping.
