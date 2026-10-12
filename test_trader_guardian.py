"""
Comprehensive Acceptance & Unit Test Suite for TRADER GUARDIAN.
Tests:
1. Streak Tracking & Cooldown Trigger (4 consecutive losses -> 30 min cooldown)
2. Daily Risk & Max Loss Limit (-0.08 SOL -> entries blocked)
3. Anti-FOMO Sheltered Capital Accounting (regime skip accumulates sheltered SOL)
4. UTC Day Rollover (resets daily PnL and today's sheltered, keeps all-time sheltered)
5. Crash-Safe Persistence & Recovery (JSON atomic file reload)
6. UI Rendering (Trader Guardian Panel & Dashboard Light Line)
7. End-to-End Bot Gate in handle_new_token
"""

import os
import sys
import time
import json
import asyncio
from unittest.mock import AsyncMock
from datetime import datetime, timezone, timedelta

import config
from trader_guardian import TraderGuardian
from bot import PumpSniperBot


def run_guardian_tests():
    print("=================================================================")
    print("       RUNNING TRADER GUARDIAN TEST SUITE                        ")
    print("=================================================================")

    test_state_file = "test_guardian_state.json"
    if os.path.exists(test_state_file):
        os.remove(test_state_file)

    # -----------------------------------------------------------------
    # TEST 1: Loss Streak & Cooldown Enforcement
    # -----------------------------------------------------------------
    print("\n--- TEST 1: Loss Streak & Cooldown Enforcement ---")
    guardian = TraderGuardian(state_file=test_state_file)
    
    # Initial state
    allowed, reason = guardian.entries_allowed()
    assert allowed, f"Initial state should allow entries, got: {reason}"
    assert guardian.state["consecutive_losses"] == 0

    # 3 consecutive losses: streak = 3, cooldown not yet triggered
    guardian.record_trade_close(-0.01)
    guardian.record_trade_close(-0.01)
    guardian.record_trade_close(-0.01)
    assert guardian.state["consecutive_losses"] == 3
    allowed, reason = guardian.entries_allowed()
    assert allowed, f"3 losses should still allow entries, got: {reason}"

    # Win resets streak
    guardian.record_trade_close(0.02)
    assert guardian.state["consecutive_losses"] == 0
    allowed, reason = guardian.entries_allowed()
    assert allowed

    # Now 4 consecutive losses
    guardian.record_trade_close(-0.005)
    guardian.record_trade_close(-0.005)
    guardian.record_trade_close(-0.005)
    guardian.record_trade_close(-0.005)
    assert guardian.state["consecutive_losses"] == 4

    # Cooldown must now be active!
    allowed, reason = guardian.entries_allowed()
    assert not allowed, "4 consecutive losses must activate cooldown and block entries!"
    assert "cooldown" in reason.lower(), f"Reason should mention cooldown, got: {reason}"
    print(f"  Streak 4 triggered cooldown: entries_allowed -> {allowed}, reason: '{reason}'")
    print("  ✅ [1] Passed: 4-loss streak triggers cooldown and blocks entries.")

    # -----------------------------------------------------------------
    # TEST 2: Daily Max Loss Limit (-0.08 SOL)
    # -----------------------------------------------------------------
    print("\n--- TEST 2: Daily Max Loss Limit ---")
    # Reset cooldown to isolate daily limit
    guardian.state["cooldown_until"] = 0.0
    guardian.state["consecutive_losses"] = 0
    guardian.state["day_realized_pnl_sol"] = -0.05
    allowed, _ = guardian.entries_allowed()
    assert allowed, "Loss of 0.05 should be under 0.08 limit"

    # Add another loss pushing day realized to -0.085 SOL
    guardian.record_trade_close(-0.035)
    assert guardian.state["day_realized_pnl_sol"] <= -config.DAILY_MAX_LOSS_SOL
    allowed, reason = guardian.entries_allowed()
    assert not allowed, "Daily loss <= -0.08 SOL must block entries!"
    assert reason == "daily limit", f"Expected reason 'daily limit', got: '{reason}'"
    print(f"  Day P&L {guardian.state['day_realized_pnl_sol']:.3f} SOL -> entries_allowed: {allowed}, reason: '{reason}'")
    print("  ✅ [2] Passed: Daily max loss limit (-0.08 SOL) halts trade entries.")

    # -----------------------------------------------------------------
    # TEST 3: Anti-FOMO Sheltered Capital Accounting
    # -----------------------------------------------------------------
    print("\n--- TEST 3: Sheltered Capital Accounting ---")
    guardian.state["sheltered_sol"] = 0.0
    guardian.state["sheltered_today"] = 0.0

    guardian.record_regime_skip(0.04)
    guardian.record_regime_skip(0.04)
    guardian.record_regime_skip(0.04)
    assert round(guardian.state["sheltered_sol"], 2) == 0.12
    assert round(guardian.state["sheltered_today"], 2) == 0.12
    print(f"  Sheltered accumulated: {guardian.state['sheltered_sol']:.2f} SOL all-time, {guardian.state['sheltered_today']:.2f} today")
    print("  ✅ [3] Passed: Regime skips correctly increment sheltered capital.")

    # -----------------------------------------------------------------
    # TEST 4: UTC Day Rollover
    # -----------------------------------------------------------------
    print("\n--- TEST 4: UTC Day Rollover ---")
    yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%d")
    guardian.state["day"] = yesterday
    guardian.state["day_realized_pnl_sol"] = -0.08
    guardian.state["sheltered_today"] = 0.50
    guardian.state["sheltered_sol"] = 1.25
    guardian._save_state_atomic()

    # Trigger rollover via entries_allowed
    allowed, _ = guardian.entries_allowed()
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    assert guardian.state["day"] == today, "Day must roll over to today"
    assert guardian.state["day_realized_pnl_sol"] == 0.0, "Day realized PnL must reset to 0.0 on rollover"
    assert guardian.state["sheltered_today"] == 0.0, "Sheltered today must reset to 0.0 on rollover"
    assert guardian.state["sheltered_sol"] == 1.25, "All-time sheltered SOL must be preserved on rollover"
    print(f"  Rollover complete: day={guardian.state['day']}, day_pnl={guardian.state['day_realized_pnl_sol']}, all_time_sheltered={guardian.state['sheltered_sol']}")
    print("  ✅ [4] Passed: UTC rollover resets daily metrics while retaining all-time capital sheltered.")

    # -----------------------------------------------------------------
    # TEST 5: Crash-Safe Persistence & Recovery
    # -----------------------------------------------------------------
    print("\n--- TEST 5: Crash-Safe Persistence & Recovery ---")
    guardian.record_regime_skip(0.10)
    guardian.state["consecutive_losses"] = 2
    guardian._save_state_atomic()

    # Re-instantiate a new TraderGuardian from disk
    restored = TraderGuardian(state_file=test_state_file)
    assert restored.state["consecutive_losses"] == 2
    assert round(restored.state["sheltered_sol"], 2) == 1.35
    print(f"  Restored successfully from disk: {restored.state}")
    print("  ✅ [5] Passed: State correctly restored from atomic disk file.")

    # -----------------------------------------------------------------
    # TEST 6: Visual Rendering (Panel & Light Line)
    # -----------------------------------------------------------------
    print("\n--- TEST 6: Visual Rendering ---")
    panel = restored.get_panel()
    assert panel is not None
    assert "TRADER GUARDIAN" in str(panel.title)
    
    light_line = restored.get_light_line()
    assert "GUARDIAN:" in light_line
    print(f"  Rendered light line:\n  {light_line}")
    print("  ✅ [6] Passed: Trader Guardian panel and light line render properly.")

    # -----------------------------------------------------------------
    # TEST 7: End-to-End Bot Gate in handle_new_token
    # -----------------------------------------------------------------
    print("\n--- TEST 7: End-to-End Bot Gate Execution ---")
    async def run_bot_gate():
        bot = PumpSniperBot(mode="paper")
        await bot.initialize()

        # Wire test guardian
        bot.guardian = TraderGuardian(state_file=test_state_file)
        # Force cooldown
        bot.guardian.state["cooldown_until"] = time.time() + 1800
        bot.guardian._save_state_atomic()

        # Regime is TRADE so regime gate won't trip
        bot.regime.state = "TRADE"
        bot.regime.score = 0.05
        bot.regime.window_tokens = 600

        skipped_before = bot.tokens_skipped
        positions_before = len(bot.trader.positions)

        fake_token = {
            "mint": "GuardianGateTestMint123456789ABCDE",
            "symbol": "SAFECOIN",
            "name": "Safe Guardian Token",
            "solAmount": 0.30,
            "uri": "https://example.com/safe.json"
        }
        bot.dex.get_token_data = AsyncMock(return_value={"price_sol": 1.0e-8, "volume_m5": 2000.0, "has_pair": True})
        bot.onchain.get_dev_wallet_stats = AsyncMock(return_value={"has_data": True, "txns": 100, "age_days": 10.0})

        await bot.handle_new_token(fake_token)

        assert bot.tokens_skipped == skipped_before + 1, "Token should be skipped by Guardian gate!"
        assert len(bot.trader.positions) == positions_before, "No position should be opened while Guardian gate is closed!"
        print("  ✅ [7] Passed: Bot handle_new_token halted by Guardian gate.")
        await bot.session.close()

    asyncio.run(run_bot_gate())

    # Cleanup test file
    if os.path.exists(test_state_file):
        os.remove(test_state_file)

    print("\n=================================================================")
    print("       ALL TRADER GUARDIAN TESTS PASSED SUCCESSFULLY!            ")
    print("=================================================================\n")


if __name__ == "__main__":
    run_guardian_tests()
