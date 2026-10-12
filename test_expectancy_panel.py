"""
Verification and Acceptance Test Suite for Expectancy Dashboard & Dev Gate Wiring.
Tests:
1. Synthetic History Math:
   - 3 wins (+$1.42), 7 losses (-$0.03), fee $0.11
   - Expected: avg_win = +$1.31, avg_loss = -$0.14, win_rate = 30.0%,
     Wilson 95% CI = 10.8–60.3%, breakeven = 9.7%, EV = +$0.295,
     profit_factor ≈ 4.0x, cushion = +20.3 pts
2. All-Unconfirmed History:
   - 5 unconfirmed exits -> displays ⚠️ line and 'n=0 confirmed'.
3. Empty History:
   - [] -> displays 'No closed trades yet' without crashing.
4. 'v' View Cycle Navigation:
   - stream -> psychology -> trades -> expectancy -> stream.
5. Dev Gate Wiring in bot handle_new_token:
   - Ensures evaluate_dev_gate is executed and skips tokens failing multi-factor criteria.
6. Live trade_history.json rendering:
   - Renders panel with live data and extracts honest metrics.
"""

import os
import json
import asyncio
from rich.console import Console

from market_psychology import MarketPsychology, render_ev_meter
from ui import print_expectancy
from dev_gate import evaluate_dev_gate
import config

console = Console()


def test_synthetic_expectancy_math():
    print("\n=================================================================")
    print("      TEST 1: SYNTHETIC EXPECTANCY & HONEST MATH TEST            ")
    print("=================================================================")

    synthetic_trades = []
    # 3 wins: +$1.42, +198%
    for i in range(3):
        synthetic_trades.append({
            "mint": f"MintWin{i}",
            "symbol": f"WIN{i}",
            "pnl_usd": 1.42,
            "pnl_sol": 0.0129,
            "pnl_pct": 198.0,
            "exit_tx_hash": "44gVZ6zZc5AejJZLvyC5tF6YACp31SbN5pBxa1SZmRaNqkEWHGESaMGBc9Lpj3JiSwJbsjSroq4FNUp69s1q3UVP"
        })
    # 7 losses: -$0.03, -4%
    for i in range(7):
        synthetic_trades.append({
            "mint": f"MintLoss{i}",
            "symbol": f"LOSS{i}",
            "pnl_usd": -0.03,
            "pnl_sol": -0.0003,
            "pnl_pct": -4.0,
            "exit_tx_hash": "5NyaG4eUY8By7dEF19563EydTugQjQoaD6WRC6ra8G23gi2WU1KeZkBHRCewMFpBvQZwfF3nubZ9p6ecx2yLpu34"
        })

    engine = MarketPsychology()
    panel = engine.render_expectancy_panel(trades_list=synthetic_trades, fee_override_usd=0.11)
    console.print(panel)

    # Render panel to text to verify exact strings and math
    import io
    buf = io.StringIO()
    test_console = Console(file=buf, force_terminal=False, width=100)
    test_console.print(panel)
    output = buf.getvalue()

    # Hand-verify assertions
    assert "Closed Trades: 10 (3W / 7L)" in output, "Expected 10 closed trades (3W / 7L)"
    assert "30.0%" in output, "Expected 30.0% win rate"
    assert "95% CI 10.8–60.3%" in output, "Expected Wilson 95% CI 10.8–60.3%"
    assert ("small sample" in output or ("small" in output and "expect wobble" in output)), "Expected small sample warning for n=10 < 30"

    assert "+$1.31" in output, "Expected avg win +$1.31"
    assert "+198%" in output, "Expected avg win pct +198%"
    assert "−$0.14" in output, "Expected avg all-in loss -$0.14"
    assert "$1.10 total ($0.11/trade)" in output, "Expected $1.10 total fee drag ($0.11/trade)"

    assert "+$0.30" in output or "+$0.29" in output, "Expected EV +$0.30 (or +$0.295)"
    assert "9.7%" in output, "Expected breakeven win rate 9.7%"
    assert "+20.3 pts" in output, "Expected cushion +20.3 pts"

    assert "4.0x" in output, "Expected profit factor ~4.0x"
    assert "9.4x" in output, "Expected payoff ratio ~9.4x"

    assert "App-Logged: +$4.05" in output, "Expected app-logged +$4.05"
    assert "Fee-Adjusted: +$2.95" in output, "Expected fee-adjusted +$2.95"
    assert "all exits confirmed on-chain" in output.lower(), "Expected all exits confirmed message"

    print("  ✅ [TEST 1 PASSED]: All synthetic math and metrics hand-verified!")


def test_unconfirmed_and_empty_history():
    print("\n=================================================================")
    print("      TEST 2: UNCONFIRMED EXITS & EMPTY HISTORY AUDIT            ")
    print("=================================================================")

    engine = MarketPsychology()

    # Case A: Empty history
    p_empty = engine.render_expectancy_panel(trades_list=[])
    import io
    buf = io.StringIO()
    c = Console(file=buf, force_terminal=False)
    c.print(p_empty)
    out_empty = buf.getvalue()
    assert "No closed trades yet" in out_empty, "Expected 'No closed trades yet' for empty list"
    print("  ✅ [TEST 2A PASSED]: Empty history handled gracefully.")

    # Case B: All-unconfirmed history
    unconfirmed_trades = [
        {"pnl_usd": 1.0, "pnl_pct": 50.0, "exit_tx_hash": "broadcast_submitted"},
        {"pnl_usd": -0.5, "pnl_pct": -25.0, "exit_tx_hash": ""},
        {"pnl_usd": 0.2, "pnl_pct": 10.0, "exit_tx_hash": "short_hash_30_chars_only"}
    ]
    p_unconf = engine.render_expectancy_panel(trades_list=unconfirmed_trades)
    buf2 = io.StringIO()
    c2 = Console(file=buf2, force_terminal=False)
    c2.print(p_unconf)
    out_unconf = buf2.getvalue()

    assert "3 exits unconfirmed" in out_unconf
    assert "n=0 confirmed" in out_unconf
    print("  ✅ [TEST 2B PASSED]: All-unconfirmed exits flagged with ⚠️ and 'n=0 confirmed'.")


def test_view_cycle():
    print("\n=================================================================")
    print("      TEST 3: 'v' KEY CYCLE NAVIGATION                           ")
    print("=================================================================")

    from bot import PumpSniperBot
    bot = PumpSniperBot(mode="demo")

    assert bot.view_mode == "stream"
    print(f"  Initial view: {bot.view_mode}")

    bot.cycle_view_mode()
    assert bot.view_mode == "psychology", f"Expected 'psychology', got {bot.view_mode}"
    print(f"  Cycle 1 -> {bot.view_mode}")

    bot.cycle_view_mode()
    assert bot.view_mode == "trades", f"Expected 'trades', got {bot.view_mode}"
    print(f"  Cycle 2 -> {bot.view_mode}")

    bot.cycle_view_mode()
    assert bot.view_mode == "expectancy", f"Expected 'expectancy', got {bot.view_mode}"
    print(f"  Cycle 3 -> {bot.view_mode}")

    bot.cycle_view_mode()
    assert bot.view_mode == "billboard", f"Expected 'billboard', got {bot.view_mode}"
    print(f"  Cycle 4 -> {bot.view_mode}")

    bot.cycle_view_mode()
    assert bot.view_mode == "stream", f"Expected 'stream', got {bot.view_mode}"
    print(f"  Cycle 5 -> {bot.view_mode}")

    # Test jump_to_billboard hotkey ('b')
    bot.jump_to_billboard()
    assert bot.view_mode == "billboard", f"Expected 'billboard', got {bot.view_mode}"
    print("  Hotkey 'b' -> jump_to_billboard verified.")

    # Test refresh_dashboard in expectancy mode without crashing
    bot.view_mode = "expectancy"
    bot.refresh_dashboard()
    print("  ✅ [TEST 3 PASSED]: 'v' cycle smoothly loops stream -> psychology -> trades -> expectancy -> billboard -> stream!")


def test_dev_gate_wiring():
    print("\n=================================================================")
    print("      TEST 4: DEV GATE WIRING IN HANDLE_NEW_TOKEN                ")
    print("=================================================================")

    from bot import PumpSniperBot
    bot = PumpSniperBot(mode="demo")

    # Construct token that clears raw 0.08 SOL floor but fails dev_gate
    # Reason: micro-buy (0.10 SOL < 0.25 SOL scrutiny threshold) on burner wallet (age 0.1d < 1.0d)
    token_failing_gate = {
        "mint": "ScamDevGateMint1111111111111111111111111111",
        "symbol": "BURNRUG",
        "name": "Burner Rug Coin",
        "uri": "https://metadata.example.com/token.json",
        "traderPublicKey": "BurnerDevWallet1111111111111111111111111111",
        "solAmount": 0.10,  # passes 0.08 floor
        "initialBuy": 50000000,
        "vTokensInBondingCurve": 1000000000
    }

    # Verify evaluate_dev_gate rejects it directly
    dev_stats_burner = {"has_data": True, "age_days": 0.1, "txns": 2}
    passed, reason = evaluate_dev_gate(
        token_failing_gate,
        meta={"description": "Test coin"},
        dex_data={},
        dev_stats=dev_stats_burner
    )
    assert not passed, "Expected dev_gate to reject burner wallet"
    assert "BURNER DEV WALLET" in reason or "SPAM" in reason or "ZERO SOCIALS" in reason
    print(f"  evaluate_dev_gate correctly vetoed: {reason}")

    # Now verify bot.handle_new_token catches it via evaluate_dev_gate
    async def run_handle():
        from unittest.mock import AsyncMock
        test_bot = PumpSniperBot(mode="paper")
        await test_bot.initialize()

        # Mock dex and onchain readers
        test_bot.dex.get_token_data = AsyncMock(return_value={"price_sol": 1.0e-8, "volume_m5": 2000.0, "has_pair": True})
        test_bot.onchain.get_dev_wallet_stats = AsyncMock(return_value=dev_stats_burner)

        initial_skipped = test_bot.tokens_skipped
        await test_bot.handle_new_token(token_failing_gate)

        assert test_bot.tokens_skipped == initial_skipped + 1, "Expected tokens_skipped to increment on dev_gate veto"
        await test_bot.session.close()

    asyncio.run(run_handle())
    print("  ✅ [TEST 4 PASSED]: dev_gate is actively wired into handle_new_token and stops bad tokens!")


def test_live_expectancy_render():
    print("\n=================================================================")
    print("      TEST 5: LIVE TRADE_HISTORY.JSON EXPECTANCY PANEL           ")
    print("=================================================================")

    engine = MarketPsychology()
    panel = engine.render_expectancy_panel()
    console.print(panel)
    print("  ✅ [TEST 5 PASSED]: Live expectancy panel rendered successfully!")


if __name__ == "__main__":
    test_synthetic_expectancy_math()
    test_unconfirmed_and_empty_history()
    test_view_cycle()
    test_dev_gate_wiring()
    test_live_expectancy_render()
    print("\n=================================================================")
    print("      ALL EXPECTANCY DASHBOARD & DEV GATE TESTS PASSED!          ")
    print("=================================================================")
