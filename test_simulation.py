"""
Visual & Audio Test Simulator for Bigo Live Streaming.
Simulates a live sequence:
1. Stream Header display
2. Real-time token skips (Rugs rejected by NumPy ML)
3. High Confidence BUY signal with massive loud FIGlet banner & audio bell
4. Live P&L monitoring (+15% -> +35% -> +52% PUMP)
5. Take Profit triggered with massive profit banner and ML online training step!
"""

import sys
import time
from rich.console import Console

from ml_engine import RugFilterML
from trader import PaperTradingEngine
from ui import (
    print_stream_header,
    print_token_skip,
    print_buy_signal,
    print_exit_event,
    print_active_positions,
    sound_alarm
)

console = Console()


def run_stream_demo():
    console.clear()
    console.print("[bold cyan]Starting Bigo Live Visual & Audio Demo...[/bold cyan]\n")

    ml = RugFilterML()
    trader = PaperTradingEngine(initial_balance=10.0, ml_engine=ml)

    # 1. Print Stream Header
    summary = trader.get_portfolio_summary()
    print_stream_header(summary, ml_samples=ml.total_trained_samples)
    time.sleep(2)

    # 2. Simulate 3 incoming rug tokens
    console.print("\n[bold yellow]📡 Real-Time Token Scans Incoming from PumpPortal...[/bold yellow]\n")
    time.sleep(1)
    print_token_skip("SCAMCOIN", "Free Airdrop Claim", 0.998, "Dev held 18.5% supply | 0 Socials")
    time.sleep(1)
    print_token_skip("PUMPDUMP", "Pepe Clone 99", 0.965, "NO SOCIALS DETECTED (High rug risk)")
    time.sleep(1)
    print_token_skip("AIFAKE", "Fake Chat GPT", 0.820, "Spam copycat heuristic triggered")
    time.sleep(1.5)

    # 3. Simulate High Confidence GEM Launch
    console.print("\n[bold green]💎 GEM TOKEN DETECTED PASSING ALL ML CRITERIA![/bold green]\n")
    gem_token = {
        "symbol": "OBRIA",
        "name": "Obria Labs Autonomous AI",
        "mint": "8L7smrffLZogRsk3LC13ZEVVbJQvC73kMBNejKoLVfJ8",
        "solAmount": 0.45,
        "initialBuy": 14000000,
        "vTokensInBondingCurve": 1073000000,
        "vSolInBondingCurve": 30.45,
        "marketCapSol": 28.8,
        "is_mayhem_mode": False
    }
    gem_meta = {
        "twitter": "https://x.com/ObriaLabs",
        "website": "https://obrialabs.com",
        "telegram": "https://t.me/ObriaLabs",
        "description": "Autonomous AI Agent tokenized on Solana with live community roadmap"
    }
    gem_dex = {"has_pair": True, "boosts": 2, "liquidity_usd": 12000.0}
    gem_dev = {"has_data": True, "age_days": 400.0, "txns": 8, "hit_page_cap": False}

    feats = ml.extract_features(gem_token, gem_meta, gem_dex, gem_dev)
    p_rug = ml.predict(feats)
    insights = ml.explain(feats, p_rug)

    pos = trader.execute_demo_buy(gem_token, p_rug, feats, buy_amount=0.5)
    print_buy_signal(gem_token, p_rug, insights, pos, is_real=False)
    time.sleep(3)

    # 4. Simulate Live Price Action & Monitoring
    console.print("\n[bold yellow]📊 TRACKING ACTIVE ON-CHAIN BONDING CURVE RESERVES...[/bold yellow]\n")
    stages = [
        (pos.entry_price_sol * 1.12, "Price up +12% from early buyers"),
        (pos.entry_price_sol * 1.28, "Price surging +28%! High volume"),
        (pos.entry_price_sol * 1.52, "PUMP TARGET HIT (+52%)! Triggering Take Profit...")
    ]

    for new_price, status_desc in stages:
        time.sleep(1.8)
        trader.update_position_price(pos.mint, new_price, real_sol_in_curve=1.2)
        print_active_positions(trader.positions)
        console.print(f"[bold cyan]ℹ️  {status_desc}[/bold cyan]")

    time.sleep(1.5)

    # 5. Execute Take Profit
    exit_rec = trader.execute_demo_sell(pos.mint, "TAKE PROFIT (+52.0%)", pos.current_price_sol)
    print_exit_event(exit_rec)
    time.sleep(2)

    # 6. Final Dashboard Refresh
    console.print("\n[bold green]🏁 UPDATED STREAM WALLET & ML ADAPTIVE MODEL:[/bold green]\n")
    final_summary = trader.get_portfolio_summary()
    print_stream_header(final_summary, ml_samples=ml.total_trained_samples)


if __name__ == "__main__":
    run_stream_demo()
