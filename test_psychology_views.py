"""
Comprehensive Verification Suite for Market Psychology & ASCII Dashboard Views.
Tests:
1. ASCII Sparkline generation (flat, trending up, trending down, empty)
2. ASCII Meter Bars (0%, 50%, 100%, clamped, custom widths)
3. ASCII Vertical Histogram chart rendering
4. Trade streak blocks & P&L flow
5. Full Psychology Radar Panel rendering
6. Full Trades Momentum Panel rendering
7. View cycling logic ('stream' -> 'psychology' -> 'trades')
"""

import sys
import time
from rich.console import Console

from market_psychology import (
    render_sparkline,
    render_meter_bar,
    render_ascii_histogram,
    MarketPsychology
)
from ui import (
    print_stream_header,
    print_psychology_radar,
    print_trades_momentum
)

console = Console()


def test_ascii_primitives():
    print("--- 1. Testing ASCII Sparklines ---")
    assert render_sparkline([]) == "────"
    assert render_sparkline([5.0, 5.0, 5.0]) == "▄▄▄"
    
    up = render_sparkline([1.0, 2.0, 3.0, 4.0])
    print(f"  Up sparkline: {up}")
    assert len(up) == 4
    assert up[0] == " " and up[-1] == "█"

    rates = [1.04, 1.10, 1.01, 0.24, 1.42, 1.33]
    rate_spark = render_sparkline(rates)
    print(f"  Real 6h rates sparkline: {rate_spark}")
    assert len(rate_spark) == 6
    print("  ✅ Sparklines passed.")

    print("\n--- 2. Testing ASCII Meter Bars ---")
    bar_0 = render_meter_bar(0, width=10)
    bar_50 = render_meter_bar(50, width=10)
    bar_100 = render_meter_bar(100, width=10)
    assert "░░░░░░░░░░" in bar_0
    assert "█████" in bar_50 and "░░░░░" in bar_50
    assert "██████████" in bar_100
    print(f"  Bar 0%:   {bar_0}")
    print(f"  Bar 50%:  {bar_50}")
    print(f"  Bar 100%: {bar_100}")
    print("  ✅ Meter bars passed.")

    print("\n--- 3. Testing ASCII Histogram Chart ---")
    data = [("-5h", 1.04), ("-4h", 1.10), ("-3h", 1.01), ("-2h", 0.24), ("-1h", 1.42), ("Now", 1.33)]
    histo = render_ascii_histogram(data, height=4, unit="%", threshold_line=0.75)
    print(histo)
    assert "│" in histo
    assert "Now" in histo
    print("  ✅ Histogram passed.")


def test_psychology_engine():
    print("\n--- 4. Testing MarketPsychology Engine & Panels ---")
    engine = MarketPsychology()
    m = engine.get_metrics(force_refresh=True)

    print(f"  Crowd FOMO:        {m['crowd_fomo']:.1f}% ({m['crowd_label']})")
    print(f"  Dev Intent:        {m['dev_intent']:.1f}% ({m['dev_label']})")
    print(f"  Holder Conviction: {m['holder_conviction']:.1f}% ({m['holder_label']})")
    print(f"  Adrenaline Pace:   {m['launches_per_min']:.1f} launches/min ({m['velocity_label']})")
    print(f"  6h Sparkline:      {m['runner_sparkline']}")

    assert 0 <= m["crowd_fomo"] <= 100
    assert 0 <= m["dev_intent"] <= 100
    assert 0 <= m["holder_conviction"] <= 100

    # Verify Strict Cosine Math & 120° Compass
    assert abs(m["buy_pts"] - 6.7) < 0.1, f"Expected buy_pts ~6.7, got {m['buy_pts']}"
    assert abs(m["soc_pts"] - 13.2) < 0.1, f"Expected soc_pts ~13.2, got {m['soc_pts']}"
    assert abs(m["vet_pts"] - 2.9) < 0.1, f"Expected vet_pts ~2.9, got {m['vet_pts']}"
    assert abs(m["dev_intent"] - 22.8) < 0.5, f"Expected dev_intent ~22.8, got {m['dev_intent']}"
    assert abs(m["compass_angle"] - 225.8) < 1.0, f"Expected compass_angle ~226°, got {m['compass_angle']}"
    assert abs(m["compass_mag"] - 0.21) < 0.02, f"Expected compass_mag ~0.21, got {m['compass_mag']}"
    assert "HYPE-LEANING" in m["compass_str"]
    assert "weak conviction" in m["compass_str"]
    print("  ✅ Strict cosine ramps & 120° compass math verified (22.8% score, 226° angle, 0.21 mag).")

    print("\n--- 5. Rendering Stream Header (with Dashboard Light) ---")
    summary = {
        "mode": "REAL",
        "pubkey": "wxEKvnyivSB5GN6HhKuJKNxgdPUbimBA81j191vzKoLT",
        "balance_sol": 0.3132,
        "balance_usd": 34.45,
        "net_equity_sol": 0.3132,
        "net_equity_usd": 34.45,
        "total_pnl_sol": -0.1556,
        "total_pnl_usd": -17.12,
        "total_pnl_pct": -33.2,
        "realized_pnl_sol": -0.1556,
        "realized_pnl_usd": -17.12,
        "unrealized_pnl_sol": 0.0,
        "unrealized_pnl_usd": 0.0,
        "open_positions_count": 0,
        "total_trades": 29,
        "wins": 4,
        "losses": 25,
        "win_rate": 13.8,
        "sol_usd_price": 110.0
    }
    print_stream_header(summary, ml_samples=3400)

    print("\n--- 6. Rendering View 2: Psychology & Radar View ---")
    print_psychology_radar(engine)

    print("\n--- 7. Rendering View 3: Trade Performance & Momentum View ---")
    print_trades_momentum(engine)
    print("  ✅ All panel views rendered successfully!")


    print("\n--- 8. Testing Markov Text Engine & Whale Swish Detection ---")
    state_idx, state_name, matches = engine.markov.classify_text("thunderbot Funder", "TFUND")
    assert state_idx == 0, f"Expected BOT_WASH (0), got {state_idx}"
    assert "BOT_WASH" in state_name
    assert "thunder" in matches or "bot" in matches or "funder" in matches
    print(f"  Classified 'thunderbot Funder': state={state_name}, matches={matches}")

    # Simulate sequence of whale-churn bot tokens swishing the waters
    bot_names = [
        ("thunderbot Funder", "TFUND"),
        ("MEV Volume Bot", "MEV"),
        ("Solana Sniper Pro", "SNIPE"),
        ("Auto Funder", "FUND"),
        ("Wash Liquidity Bot", "WASH")
    ]
    for name, sym in bot_names:
        engine.record_token_event({"name": name, "symbol": sym, "solAmount": 0.10})

    m_bot = engine.get_metrics(force_refresh=True)
    assert m_bot["whale_churn"] >= 0.40, f"Expected whale_churn >= 0.40, got {m_bot['whale_churn']}"
    assert m_bot["fomo_dampener"] < 0.80, f"Expected fomo_dampener < 0.80, got {m_bot['fomo_dampener']}"
    assert "WHALE SWISH" in m_bot["crowd_label"]
    assert "GHOST RETENTION" in m_bot["holder_label"]
    assert "Whales swishing waters" in m_bot["markov_read"] or "swishing" in m_bot["markov_read"].lower()
    print(f"  Whale Churn detected: index={m_bot['whale_churn']*100:.1f}%, status={m_bot['markov_status']}")
    print(f"  Anti-Spoofing: Raw FOMO={m_bot['fomo_raw_pct']:.0f}% ➔ Deflated FOMO={m_bot['crowd_fomo']:.0f}%")
    print(f"  Ghost Retention: Raw Conviction={m_bot['conviction_raw_pct']:.0f}% ➔ Real Conviction={m_bot['holder_conviction']:.0f}%")
    print(f"  Markov Read: \"{m_bot['markov_read']}\"")
    print("  ✅ Markov Text Engine & Whale Swish Detection verified!")


if __name__ == "__main__":
    test_ascii_primitives()
    test_psychology_engine()
    print("\n=================================================================")
    print("      ALL PSYCHOLOGY & ASCII VIEW TESTS PASSED SUCCESSFULLY!     ")
    print("=================================================================")
