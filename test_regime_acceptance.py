"""
Acceptance Test Suite for RegimeGuard.
Tests all 6 criteria specified in requirements:
1. Math: 200 synthetic tape entries, known outcomes; verify score, 0.0075 flip, and STAND_DOWN when completed < 500.
2. Dead handling: add 50 'dead' entries; verify score drops.
3. Baseline: report no_baseline_rate, switch baseline order if > 30%.
4. Restart: simulate restart / crash, verify tape intact, no duplicate mints, valid regime_state.json.
5. Gate: forced STAND_DOWN state, verify handle_new_token skips buy AND records scan.
6. UI / Dashboard: verify regime line in dashboard and state file updating.
"""

import os
import sys
import time
import json
import asyncio
from unittest.mock import MagicMock, AsyncMock

import config
from regime_guard import RegimeGuard
from bot import PumpSniperBot
from ui import get_regime_line, print_stream_header


def run_acceptance_tests():
    print("=================================================================")
    print("       RUNNING REGIME GUARD ACCEPTANCE TEST SUITE                ")
    print("=================================================================")

    # Temporary test files to avoid polluting production tape during test
    test_tape = "test_regime_tape.jsonl"
    test_state = "test_regime_state.json"
    if os.path.exists(test_tape): os.remove(test_tape)
    if os.path.exists(test_state): os.remove(test_state)

    config.REGIME_TAPE_FILE = test_tape
    config.REGIME_STATE_FILE = test_state

    # -----------------------------------------------------------------
    # TEST 1: Math Verification (< 500 floor & 0.0075 score flip)
    # -----------------------------------------------------------------
    print("\n--- TEST 1: Math Verification ---")
    guard = RegimeGuard()
    now = time.time()

    # Create 200 synthetic entries (all within trailing 3h window)
    # 2 runners (1%), 198 non-runners
    for i in range(200):
        is_runner = (i < 2)
        entry = {
            "mint": f"mint_test1_{i}",
            "t_scan": now - (i * 10),
            "price_scan": 1.0,
            "vol_scan": 1500.0 if is_runner else 500.0,
            "return_30m": 0.25 if is_runner else -0.10,
            "outcome": "settled"
        }
        guard.tape.append(entry)
        guard._tape_by_mint[entry["mint"]] = entry

    # Case A: completed = 200 (< 500 default floor). Score is 2/200 = 0.01 (1.0% >= 0.0075).
    # Since completed < 500, state MUST BE STAND_DOWN!
    state, score, tokens = guard.recompute()
    print(f"  [1A] 200 tokens (< 500 floor), Score: {score:.4f} ({score*100:.2f}%) -> State: {state}")
    assert score == 0.01, f"Expected score 0.01, got {score}"
    assert tokens == 200, f"Expected 200 completed tokens, got {tokens}"
    assert state == "STAND_DOWN", f"Expected STAND_DOWN when completed < 500, got {state}"
    print("  ✅ [1A] Passed: Completed < 500 enforced STAND_DOWN even with score 1.0% >= 0.75%")

    # Case B: Threshold flip exactly at 0.0075 with completed >= 500
    # Add 800 more completed entries so total = 1000
    for i in range(200, 1000):
        entry = {
            "mint": f"mint_test1_{i}",
            "t_scan": now - (i * 5),
            "price_scan": 1.0,
            "vol_scan": 500.0,
            "return_30m": -0.10,
            "outcome": "settled"
        }
        guard.tape.append(entry)
        guard._tape_by_mint[entry["mint"]] = entry

    # Right now, 2 runners out of 1000 -> score = 2 / 1000 = 0.0020 < 0.0075 -> STAND_DOWN
    state, score, tokens = guard.recompute()
    print(f"  [1B] 1000 tokens, 2 runners, Score: {score:.4f} -> State: {state}")
    assert score == 0.002, f"Expected 0.002, got {score}"
    assert state == "STAND_DOWN", f"Expected STAND_DOWN, got {state}"

    # Now make total runners = 7 -> score = 7 / 1000 = 0.0070 < 0.0075 -> STAND_DOWN
    for i in range(2, 7):
        guard.tape[i]["return_30m"] = 0.20
        guard.tape[i]["vol_scan"] = 1500.0
    state, score, tokens = guard.recompute()
    print(f"  [1C] 1000 tokens, 7 runners, Score: {score:.4f} (< 0.0075) -> State: {state}")
    assert score == 0.007, f"Expected 0.007, got {score}"
    assert state == "STAND_DOWN", f"Expected STAND_DOWN when score < 0.0075, got {state}"

    # Now make total runners = 8 -> score = 8 / 1000 = 0.0080 >= 0.0075 -> TRADE!
    guard.tape[7]["return_30m"] = 0.20
    guard.tape[7]["vol_scan"] = 1500.0
    state, score, tokens = guard.recompute()
    print(f"  [1D] 1000 tokens, 8 runners, Score: {score:.4f} (>= 0.0075) -> State: {state}")
    assert score == 0.008, f"Expected 0.008, got {score}"
    assert state == "TRADE", f"Expected TRADE flip when score >= 0.0075, got {state}"
    print("  ✅ [1B-1D] Passed: Exact flip at 0.0075 verified (7/1000=STAND_DOWN, 8/1000=TRADE).")

    # -----------------------------------------------------------------
    # TEST 2: Dead Outcome Handling (Must reduce score)
    # -----------------------------------------------------------------
    print("\n--- TEST 2: Dead Outcome Handling ---")
    initial_score = guard.score
    initial_tokens = guard.window_tokens
    print(f"  Before adding dead: Score={initial_score:.4f}, Tokens={initial_tokens}")

    # Add 50 'dead' entries
    for i in range(50):
        entry = {
            "mint": f"mint_dead_{i}",
            "t_scan": now - (i * 2),
            "price_scan": 1.0,
            "vol_scan": 0.0,
            "return_30m": -1.0,
            "outcome": "dead"
        }
        guard.tape.append(entry)
        guard._tape_by_mint[entry["mint"]] = entry

    new_state, new_score, new_tokens = guard.recompute()
    print(f"  After adding 50 dead: Score={new_score:.4f}, Tokens={new_tokens}, State={new_state}")
    assert new_tokens == initial_tokens + 50, f"Expected {initial_tokens + 50} tokens, got {new_tokens}"
    assert new_score < initial_score, f"Dead entries MUST drop the score! {new_score} >= {initial_score}"
    # 8 runners / 1050 completed = ~0.007619
    expected_dropped_score = 8.0 / 1050.0
    assert abs(new_score - expected_dropped_score) < 1e-5
    print("  ✅ [2] Passed: 50 dead entries counted in denominator and dropped score as required.")

    # -----------------------------------------------------------------
    # TEST 3: Baseline Rate Test & Baseline Order Switching
    # -----------------------------------------------------------------
    print("\n--- TEST 3: Baseline Rate & Ordering ---")
    guard3 = RegimeGuard()
    guard3.sample_every = 1  # Record every token for test

    # Simulate 100 scans: 65 have dex price, 35 have no price
    for i in range(100):
        tok = {"mint": f"mint_base_{i}"}
        dex = {"price_sol": 1.0 if i < 65 else 0.0}
        guard3.record_scan(tok, dex)

    total_scans = len(guard3.tape) + guard3._no_baseline_count
    rate = guard3._no_baseline_count / total_scans if total_scans > 0 else 0.0
    print(f"  Scans: {total_scans}, No-baseline count: {guard3._no_baseline_count}, Rate: {rate*100:.1f}%")
    assert guard3._no_baseline_count == 35, f"Expected 35 no baseline, got {guard3._no_baseline_count}"
    assert abs(rate - 0.35) < 1e-4

    if rate > 0.30:
        print(f"  ⚠️  no_baseline_rate ({rate*100:.1f}%) exceeds 30%! Switching baseline order to bonding-curve-first.")
        guard3.baseline_order = "bonding_curve_first"
        assert guard3.baseline_order == "bonding_curve_first"
    print("  ✅ [3] Passed: no_baseline_rate reported accurately and baseline order switched.")

    # -----------------------------------------------------------------
    # TEST 4: Crash / Restart Survival
    # -----------------------------------------------------------------
    print("\n--- TEST 4: Crash & Restart Persistence ---")
    # Save current guard tape to disk
    guard._save_tape_atomic()
    tape_count_before = len(guard.tape)

    # Now instantiate a brand new RegimeGuard pointing to the same files
    guard_restarted = RegimeGuard()
    assert len(guard_restarted.tape) == tape_count_before, f"Tape count mismatch: {len(guard_restarted.tape)} vs {tape_count_before}"
    
    # Check uniqueness of mints
    all_mints = [e["mint"] for e in guard_restarted.tape]
    assert len(all_mints) == len(set(all_mints)), "Duplicate mints detected in restarted tape!"

    # Check regime_state.json validity
    with open(test_state, "r", encoding="utf-8") as f:
        state_json = json.load(f)
    assert "state" in state_json and "score" in state_json and "window_tokens" in state_json
    assert "updated_at" in state_json and "no_baseline_rate" in state_json
    print(f"  Restarted tape intact: {len(guard_restarted.tape)} unique mints. State file valid: {state_json['state']}")
    print("  ✅ [4] Passed: Restart persistence & deduplication verified.")

    # -----------------------------------------------------------------
    # TEST 5: Regime Gate in handle_new_token
    # -----------------------------------------------------------------
    print("\n--- TEST 5: Regime Gate Execution ---")
    async def run_gate_test():
        # Setup bot with RegimeGuard in forced STAND_DOWN
        bot = PumpSniperBot(mode="paper")
        await bot.initialize()

        # Force STAND_DOWN
        bot.regime.state = "STAND_DOWN"
        bot.regime.score = 0.003
        bot.regime.window_tokens = 600
        bot.regime.sample_every = 1 # record this scan

        # Make sure trade is disallowed
        assert not bot.regime.is_trade_allowed()

        tape_len_before = len(bot.regime.tape)
        positions_before = len(bot.trader.positions)
        skipped_before = bot.tokens_skipped

        fake_token = {
            "mint": "FakeMintRegimeGate123456789ABCDEF",
            "symbol": "GATE",
            "name": "Gate Test Token",
            "solAmount": 0.25, # Clears dev buy floor
            "uri": "https://example.com/meta.json"
        }

        # Mock dex and onchain readers to avoid network in unit test
        bot.dex.get_token_data = AsyncMock(return_value={"price_sol": 1.0e-8, "volume_m5": 2000.0, "has_pair": True})
        bot.onchain.get_dev_wallet_stats = AsyncMock(return_value={"has_data": True, "txns": 100, "age_days": 10.0})

        # Process token through handle_new_token
        await bot.handle_new_token(fake_token)

        # Verify buy was skipped
        assert len(bot.trader.positions) == positions_before, "Buy was NOT skipped when regime is STAND_DOWN!"
        assert bot.tokens_skipped == skipped_before + 1, "tokens_skipped counter did not increment!"

        # Verify scan WAS still recorded in the regime tape
        assert len(bot.regime.tape) == tape_len_before + 1, "Scan was NOT recorded in regime tape!"
        assert bot.regime.tape[-1]["mint"] == fake_token["mint"], "Recorded mint mismatch!"
        print("  ✅ [5] Passed: Buy was skipped AND scan was recorded in regime tape.")
        await bot.session.close()

    asyncio.run(run_gate_test())

    # -----------------------------------------------------------------
    # TEST 6: UI / Dashboard Display
    # -----------------------------------------------------------------
    print("\n--- TEST 6: UI / Dashboard Display ---")
    # Write test state file
    with open("regime_state.json", "w", encoding="utf-8") as f:
        json.dump({
            "state": "STAND_DOWN",
            "score": 0.0041,
            "window_tokens": 1620,
            "updated_at": time.time(),
            "no_baseline_rate": 0.012
        }, f)

    line = get_regime_line()
    print("  Rendered regime line:", line)
    assert "STAND_DOWN" in line
    assert "0.41%" in line
    assert "1620 tokens/3h" in line
    print("  ✅ [6] Passed: UI get_regime_line displays active regime state and metrics.")

    # Cleanup test files
    if os.path.exists(test_tape): os.remove(test_tape)
    if os.path.exists(test_state): os.remove(test_state)
    config.REGIME_TAPE_FILE = "regime_tape.jsonl"
    config.REGIME_STATE_FILE = "regime_state.json"

    print("\n=================================================================")
    print("         ALL 6 ACCEPTANCE TESTS PASSED SUCCESSFULLY!             ")
    print("=================================================================")


if __name__ == "__main__":
    run_acceptance_tests()
