"""
Solana PumpPortal & DexScreener ML Rug Filtering Live Sniper Bot.
Main entry point orchestrating live WebSocket feeds, Rug Model V2 classification,
on-chain dev wallet profiling, real Helius RPC trade execution, and loud terminal streaming UI.
"""

import sys
import asyncio
import argparse
import aiohttp
import termios
import tty
import atexit
from typing import Dict, Any
from rich.panel import Panel
from rich import box

import config
from ml_engine import RugFilterML
from real_trader import RealTradingEngine
from trader import PaperTradingEngine
from dexscreener import DexScreenerClient
from onchain import OnChainReader
from metadata import fetch_token_metadata
from pumpportal import PumpPortalClient
from regime_guard import RegimeGuard
from market_psychology import MarketPsychology
from trader_guardian import TraderGuardian
from dev_gate import evaluate_dev_gate
from ui import (
    console,
    sound_alarm,
    print_stream_header,
    print_buy_signal,
    print_token_skip,
    print_exit_event,
    print_active_positions,
    print_psychology_radar,
    print_trades_momentum,
    print_expectancy,
    print_qr_billboard
)


class PumpSniperBot:
    def __init__(
        self,
        mode: str = config.TRADING_MODE,
        buy_amount: float = config.DEFAULT_BUY_AMOUNT_SOL,
        rug_threshold: float = config.ML_RUG_THRESHOLD,
        sound_enabled: bool = True,
        yolo: bool = config.YOLO_MODE,
        view_mode: str = getattr(config, "DEFAULT_DASHBOARD_VIEW", "stream")
    ):
        self.mode = mode.lower()
        self.buy_amount = buy_amount
        self.rug_threshold = rug_threshold
        self.yolo = yolo
        self.view_mode = view_mode
        self.psychology = MarketPsychology()
        self.guardian = TraderGuardian()
        if self.yolo:
            config.YOLO_MODE = True
        config.SOUND_ENABLED = sound_enabled

        # Initialize Rug Model V2 (loads parameters straight from rug_model_v2_devwallet.json)
        self.ml = RugFilterML(model_path=config.RUG_MODEL_FILE)
        # Use threshold from the JSON if not explicitly customized
        if self.rug_threshold is None:
            self.rug_threshold = self.ml.threshold

        self.session: aiohttp.ClientSession = None
        self.dex: DexScreenerClient = None
        self.onchain: OnChainReader = None
        self.portal: PumpPortalClient = None

        # Trader engine initialized in initialize()
        self.trader = None

        self.running = False
        self.tokens_scanned = 0
        self.tokens_skipped = 0

        self._old_termios = None
        self._stdin_reader_attached = False
        atexit.register(self.restore_terminal)

    def setup_keyboard_listener(self):
        """Set up non-blocking interactive keypress listener for 'y' toggle."""
        if not sys.stdin.isatty():
            return

        try:
            self._old_termios = termios.tcgetattr(sys.stdin.fileno())
            tty.setcbreak(sys.stdin.fileno())
        except Exception:
            self._old_termios = None
            return

        def _on_stdin():
            try:
                ch = sys.stdin.read(1)
                if not ch:
                    return
                if ch.lower() == 'y':
                    self.toggle_yolo_mode()
                elif ch.lower() == 'v':
                    self.cycle_view_mode()
                elif ch.lower() == 'b':
                    self.jump_to_billboard()
                elif ch.lower() == 'q':
                    console.print("\n[bold red]'q' pressed — stopping bot cleanly...[/bold red]")
                    self.running = False
            except Exception:
                pass

        try:
            loop = asyncio.get_running_loop()
            loop.add_reader(sys.stdin.fileno(), _on_stdin)
            self._stdin_reader_attached = True
        except Exception:
            self._stdin_reader_attached = False

    def restore_terminal(self):
        """Restore terminal settings to normal canonical mode."""
        if getattr(self, "_stdin_reader_attached", False):
            try:
                loop = asyncio.get_running_loop()
                loop.remove_reader(sys.stdin.fileno())
            except Exception:
                pass
            self._stdin_reader_attached = False

        if getattr(self, "_old_termios", None) and sys.stdin.isatty():
            try:
                termios.tcsetattr(sys.stdin.fileno(), termios.TCSADRAIN, self._old_termios)
            except Exception:
                pass
            self._old_termios = None

    def toggle_yolo_mode(self):
        """Toggle YOLO mode ON/OFF interactively when user presses 'y'."""
        self.yolo = not self.yolo
        config.YOLO_MODE = self.yolo

        if self.yolo:
            sound_alarm(1, sound_type="bell")
            console.print(Panel(
                "[bold red]🔥 YOLO / RISKY MODE ACTIVATED! 🔥[/bold red]\n\n"
                "[bold yellow]• Max position cap is now BYPASSED / REMOVED.[/bold yellow]\n"
                "[bold yellow]• The bot will continue buying passing tokens ALL THE WAY TO ZERO balance.[/bold yellow]\n\n"
                "[bold cyan]Tip: Press 'y' again at any time to switch back to SAFE mode and STOP new trades![/bold cyan]",
                title="[bold red]⚡ YOLO MODE: ON (KEYPRESS 'y')[/bold red]",
                border_style="bold red",
                box=box.DOUBLE
            ))
        else:
            sound_alarm(1, sound_type="dump")
            current_count = len(self.trader.positions) if self.trader else 0
            max_allowed = config.MAX_OPEN_POSITIONS
            if current_count >= max_allowed:
                status_note = (
                    f"[bold red]⚠️ TOO MANY TRADES ALREADY: Currently holding {current_count}/{max_allowed} positions.[/bold red]\n"
                    f"[bold yellow]⛔ NEW BUYING IS NOW STOPPED! The software will only monitor and exit open trades.[/bold yellow]"
                )
            else:
                status_note = (
                    f"[bold green]Enforcing safe cap of max {max_allowed} positions ({current_count} currently open).[/bold green]\n"
                    f"[bold cyan]Will only buy up to {max_allowed} total positions.[/bold cyan]"
                )

            console.print(Panel(
                "[bold green]🛡️ SAFE MODE RESTORED — YOLO MODE OFF 🛡️[/bold green]\n\n"
                f"{status_note}\n\n"
                "[bold cyan]Tip: Press 'y' again at any time to re-activate YOLO risky mode.[/bold cyan]",
                title="[bold green]🔒 SAFE MODE: ON (YOLO OFF)[/bold green]",
                border_style="bold green",
                box=box.DOUBLE
            ))

        # Immediately refresh stream header
        self.refresh_dashboard()

    def cycle_view_mode(self):
        """Cycle through dashboard views: stream -> psychology -> trades -> expectancy -> billboard -> stream."""
        modes = ["stream", "psychology", "trades", "expectancy", "billboard"]
        curr_idx = modes.index(self.view_mode) if self.view_mode in modes else 0
        self.view_mode = modes[(curr_idx + 1) % len(modes)]

        sound_alarm(1, sound_type="bell")
        mode_names = {
            "stream": "⚡ STREAM & LIVE HOLDINGS VIEW",
            "psychology": "🧠 MARKET PSYCHOLOGY & PVP RADAR VIEW",
            "trades": "🎯 TRADE PERFORMANCE & MOMENTUM VIEW",
            "expectancy": "🎯 EXPECTANCY & TRADE SHAPE VIEW",
            "billboard": "🐘 THE ELEPHANT IN THE ROOM (ELECTRONIC BILLBOARD)"
        }
        console.print(Panel(
            f"[bold yellow]Switched Dashboard View to:[/bold yellow]\n[bold white]{mode_names.get(self.view_mode)}[/bold white]\n\n"
            f"[dim]Tip: Press 'v' again to cycle to the next view mode anytime.[/dim]",
            title="[bold cyan]🖥️ DASHBOARD VIEW CHANGED ('v')[/bold cyan]",
            border_style="bold cyan",
            box=box.ROUNDED
        ))
        self.refresh_dashboard()

    def jump_to_billboard(self):
        """Jump directly to the QR code & value billboard view (hotkey 'b')."""
        self.view_mode = "billboard"
        sound_alarm(1, sound_type="coin")
        console.print(Panel(
            "[bold yellow]🐘 ELECTRONIC HIGHWAY BILLBOARD: THE ELEPHANT IN THE ROOM DISPLAYED 🐘[/bold yellow]\n\n"
            "[bold white]Ready for stream viewers & dual-phone QR scanning![/bold white]\n"
            "[dim]Press 'v' to return to normal trading views, or 'b' anytime to show this billboard.[/dim]",
            title="[bold cyan]📺 LIVE COMMERCIAL BILLBOARD ('b')[/bold cyan]",
            border_style="bold cyan",
            box=box.ROUNDED
        ))
        self.refresh_dashboard()

    def refresh_dashboard(self):
        """Refresh dashboard according to current view_mode."""
        if not self.trader:
            return
        from price_feed import get_cached_sol_price
        sol_usd = get_cached_sol_price() or 110.0
        summary = self.trader.get_portfolio_summary(sol_usd=sol_usd)
        print_stream_header(summary, ml_samples=self.ml.total_trained_samples, guardian=self.guardian)

        if self.view_mode == "stream":
            if self.trader.positions:
                print_active_positions(self.trader.positions, sol_usd=sol_usd)
        elif self.view_mode == "psychology":
            print_psychology_radar(self.psychology)
        elif self.view_mode == "trades":
            print_trades_momentum(self.psychology)
        elif self.view_mode == "expectancy":
            print_expectancy(self.psychology)
        elif self.view_mode == "billboard":
            print_qr_billboard(self.psychology)

    async def initialize(self):
        """Initialize HTTP sessions, network clients, and trading engine."""
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko)"
        }
        self.session = aiohttp.ClientSession(headers=headers)
        self.dex = DexScreenerClient(session=self.session)
        self.onchain = OnChainReader(session=self.session)
        self.portal = PumpPortalClient(on_new_token=self.handle_new_token)
        self.regime = RegimeGuard(self.dex, self.onchain)

        if self.mode == "real":
            self.trader = RealTradingEngine(
                private_key_b58=config.SOLANA_PRIVATE_KEY,
                helius_rpc_url=config.HELIUS_RPC_URL,
                session=self.session
            )
            await self.trader.refresh_balance()
            from price_feed import fetch_live_sol_price
            await fetch_live_sol_price(self.session)
            removed = await self.trader.reconcile_positions()
            if removed > 0:
                console.print(f"[bold yellow]🧹 Reconciled {removed} unheld ghost position(s) on-chain.[/bold yellow]")
        else:
            self.trader = PaperTradingEngine(
                initial_balance=config.DEMO_INITIAL_BALANCE_SOL,
                ml_engine=self.ml
            )
            from price_feed import fetch_live_sol_price
            await fetch_live_sol_price(self.session)

    async def handle_new_token(self, token_data: Dict[str, Any]):
        """
        Process incoming token creation event from PumpPortal WebSocket.
        Extracts 20-element feature vector, evaluates against Rug Model V2,
        and triggers trade execution if below threshold.
        """
        self.tokens_scanned += 1
        symbol = str(token_data.get("symbol", "TOKEN")).upper()
        name = str(token_data.get("name", "Unknown"))
        mint = token_data.get("mint", "")
        uri = token_data.get("uri", "")
        dev_wallet = token_data.get("traderPublicKey", "")

        # 0. Immediate Veto: Developer 0 SOL or Micro Buy (< MIN_DEV_BUY_SOL)
        raw_dev_buy = float(token_data.get("solAmount") if token_data.get("solAmount") is not None else (token_data.get("dev_buy_sol") or 0.0))
        min_dev_buy = float(getattr(config, "MIN_DEV_BUY_SOL", 0.08))
        if raw_dev_buy < min_dev_buy:
            self.tokens_skipped += 1
            print_token_skip(symbol, name, 0.999, f"DEV ZERO/MICRO BUY: Dev bought {raw_dev_buy:.4f} SOL (< {min_dev_buy:.2f} SOL required floor)")
            return

        # 1. Concurrently fetch IPFS metadata, DexScreener data, and Dev Wallet stats
        meta_task = fetch_token_metadata(self.session, uri)
        dex_task = self.dex.get_token_data(mint)
        dev_task = self.onchain.get_dev_wallet_stats(dev_wallet, page_cap=config.DEV_WALLET_PAGE_CAP)

        meta, dex_data, dev_stats = await asyncio.gather(
            meta_task, dex_task, dev_task, return_exceptions=True
        )

        if isinstance(meta, Exception):
            meta = {}
        if isinstance(dex_data, Exception):
            dex_data = {}
        if isinstance(dev_stats, Exception):
            dev_stats = {"has_data": False}

        # Market Psychology: record token event for dev intent & launch velocity tracking
        if hasattr(self, "psychology") and self.psychology:
            self.psychology.record_token_event(token_data, meta, dex_data, dev_stats)

        # Regime tape: record every sampled token that cleared the spam
        # floor (vetoed or not — the tape measures the market, not picks)
        self.regime.record_scan(token_data, dex_data
            if not isinstance(dex_data, Exception) else {})
        # Regime gate: applies even in YOLO mode (YOLO bypasses the
        # position cap, never the regime)
        if config.REGIME_GUARD_ENABLED and not self.regime.is_trade_allowed():
            self.tokens_skipped += 1
            self.guardian.record_regime_skip(self.buy_amount)
            console.print(
                f"[bold red][REGIME 🛑][/bold red] "
                f"[bold white]${symbol[:8]}[/bold white] "
                f"buy skipped — market dead "
                f"(score {self.regime.score*100:.2f}%, "
                f"{self.regime.window_tokens} tokens/3h)")
            return

        # Trader Guardian gate: psychological safeguards (daily loss limit, loss streak cooldown)
        allowed, guard_reason = self.guardian.entries_allowed()
        if not allowed:
            self.tokens_skipped += 1
            console.print(
                f"[bold red][GUARDIAN 🛑][/bold red] "
                f"[bold white]${symbol[:8]}[/bold white] "
                f"buy skipped — {guard_reason}")
            return

        # Multi-Factor Dev Gate: 0.08 SOL floor, wallet age/txns, genuine socials, 6% supply cap, spam blacklist
        gate_passed, gate_reason = evaluate_dev_gate(
            token_data, meta=meta, dex_data=dex_data, dev_stats=dev_stats
        )
        if not gate_passed:
            self.tokens_skipped += 1
            print_token_skip(symbol, name, 0.999, f"[DEV GATE] {gate_reason}")
            return

        # 2. Build 20-element feature vector (dev_buy, liquidity, top_holder, socials, age & txns buckets)
        features = self.ml.extract_features(token_data, meta, dex_data, dev_stats)

        # 3. Score Rug Probability using Rug Model V2
        p_rug = self.ml.predict(features)

        # 4. Veto Rule: ML model threshold + Hardened Multi-Factor Dev Gate
        vetoed, veto_reason = self.ml.is_vetoed(
            p_rug, features,
            token_data=token_data,
            meta=meta,
            dex_data=dex_data,
            dev_stats=dev_stats
        )
        if vetoed:
            self.tokens_skipped += 1
            insights = self.ml.explain(features, p_rug)
            danger_reasons = [det for cat, det, st in insights if st in ("DANGER", "WARN")]
            reason_str = veto_reason if veto_reason else (" | ".join(danger_reasons[:2]) if danger_reasons else f"Vetoed (P={p_rug*100:.1f}%)")
            print_token_skip(symbol, name, p_rug, reason_str)
            return

        # 5. Token passed ML filter (p_rug < threshold) -> Check capacity & wallet balance
        if not self.trader.can_buy(self.buy_amount):
            if self.yolo:
                skip_reason = "Insufficient SOL balance (wallet reached fee reserve limit)."
            else:
                skip_reason = f"Max positions reached ({len(self.trader.positions)}/{config.MAX_OPEN_POSITIONS}) — run with -y for YOLO mode."
            console.print(
                f"[bold yellow]⚠️  BUY SKIPPED FOR ${symbol}:[/bold yellow] {skip_reason}"
            )
            return

        # 6. Execute Trade (Real via Helius RPC or Paper)
        pos = None
        if self.mode == "real":
            console.print(f"[bold cyan]⚡ SENDING REAL BUY ORDER TO HELIUS RPC FOR ${symbol}...[/bold cyan]")
            pos = await self.trader.execute_real_buy(
                token_data=token_data,
                p_rug=p_rug,
                features=features,
                buy_amount=self.buy_amount
            )
        else:
            pos = self.trader.execute_demo_buy(
                token_data=token_data,
                p_rug=p_rug,
                features=features,
                buy_amount=self.buy_amount
            )

        if pos:
            insights = self.ml.explain(features, p_rug)
            print_buy_signal(token_data, p_rug, insights, pos, is_real=(self.mode == "real"))

    async def position_monitor_loop(self):
        """
        Continuously monitor open positions using Solana on-chain RPC & DexScreener.
        Checks for Take Profit (+50%), Stop Loss (-25%), and Dev Dumps.
        """
        monitor_cycles = 0
        while self.running:
            try:
                monitor_cycles += 1
                # Periodically reconcile positions against on-chain token balances
                if monitor_cycles % 15 == 0 and self.mode == "real" and self.trader:
                    await self.trader.reconcile_positions()

                active_mints = list(self.trader.positions.keys())
                for mint in active_mints:
                    pos = self.trader.positions.get(mint)
                    if not pos:
                        continue

                    # 1. Query on-chain pump.fun bonding curve reserves
                    if not pos.curve_key:
                        pos.curve_key = self.onchain.derive_bonding_curve(mint) or ""
                    curve_state = await self.onchain.get_bonding_curve_state(pos.curve_key, mint=mint)
                    curr_price = None
                    real_sol = None

                    if curve_state:
                        curr_price = curve_state["price_sol"]
                        real_sol = curve_state["real_sol"]

                    # 2. Fallback to DexScreener only if liquid pool exists (avoids illiquid price spikes)
                    if curr_price is None:
                        dex_info = await self.dex.get_token_data(mint)
                        liq = float(dex_info.get("liquidity_usd") or 0.0)
                        min_liq = getattr(config, "MIN_DEX_LIQUIDITY_USD", 1000.0)
                        if dex_info.get("has_pair") and dex_info.get("price_sol", 0) > 0 and liq >= min_liq:
                            curr_price = dex_info["price_sol"]

                    if curr_price is not None:
                        # Update price and check for exit conditions
                        trigger = self.trader.update_position_price(
                            mint=mint,
                            new_price_sol=curr_price,
                            real_sol_in_curve=real_sol
                        )

                        if trigger:
                            # Execute sell
                            exit_record = None
                            if self.mode == "real":
                                exit_record = await self.trader.execute_real_sell(
                                    mint=mint,
                                    reason=trigger,
                                    current_price_sol=curr_price
                                )
                            else:
                                exit_record = self.trader.execute_demo_sell(
                                    mint=mint,
                                    reason=trigger,
                                    current_price_sol=curr_price
                                )

                            if exit_record:
                                print_exit_event(exit_record)
                                pnl = float(exit_record.get("pnl_sol", 0.0))
                                self.guardian.record_trade_close(pnl)

                await asyncio.sleep(config.REFRESH_INTERVAL_SEC)
            except asyncio.CancelledError:
                break
            except Exception:
                await asyncio.sleep(config.REFRESH_INTERVAL_SEC)

    async def dashboard_loop(self):
        """
        Periodically print stream dashboard and active positions table.
        """
        while self.running:
            try:
                await asyncio.sleep(25)
                if not self.running:
                    break
                from price_feed import fetch_live_sol_price, get_cached_sol_price
                await fetch_live_sol_price(self.session)
                if self.mode == "real":
                    await self.trader.refresh_balance()
                    await self.trader.reconcile_positions()
                sol_usd = get_cached_sol_price() or 110.0
                self.refresh_dashboard()
            except asyncio.CancelledError:
                break

    async def start(self):
        """Start the bot."""
        self.running = True
        await self.initialize()
        self.setup_keyboard_listener()
        
        # Play pixelart logo reveal
        try:
            import config
            if getattr(config, 'USE_PIXEL_BANNERS', False):
                import pixelart
                pixelart.logo_reveal("PUMP ML")
        except Exception:
            pass

        # Display initial dashboard view
        from price_feed import get_cached_sol_price
        sol_usd = get_cached_sol_price() or 110.0
        self.refresh_dashboard()

        bal_usd = self.trader.balance_sol * sol_usd
        buy_usd = self.buy_amount * sol_usd
        mode_desc = f"[bold green]REAL LIVE TRADING (HELIUS RPC)[/bold green]" if self.mode == "real" else "[bold yellow]PAPER SIMULATION MODE[/bold yellow]"
        wallet_desc = f"Wallet: [bold cyan]{self.trader.pubkey}[/bold cyan] | Balance: [bold white]{self.trader.balance_sol:.4f} SOL (${bal_usd:.2f})[/bold white]" if self.mode == "real" else f"Demo Balance: {self.trader.balance_sol:.2f} SOL (${bal_usd:.2f})"

        yolo_banner = " | [bold red]🔥 YOLO MODE: ACTIVE (ALL THE WAY TO ZERO)[/bold red]" if self.yolo else f" | Max Positions: {config.MAX_OPEN_POSITIONS}"

        console.print(
            f"🚀 [bold green]LISTENING TO PUMPPORTAL WEBSOCKET...[/bold green]\n"
            f"[bold yellow]Mode:[/bold yellow] {mode_desc}{yolo_banner}\n"
            f"[bold yellow]Config:[/bold yellow] Buy Size: [bold white]{self.buy_amount} SOL (${buy_usd:.2f})[/bold white] | "
            f"Take Profit: [bold green]+{config.TAKE_PROFIT_PCT}%[/bold green] | "
            f"Stop Loss: [bold red]-{config.STOP_LOSS_PCT}%[/bold red] | "
            f"Rug Veto Threshold: [bold magenta]< {self.rug_threshold*100:.1f}%[/bold magenta]\n"
            f"[bold cyan]⌨️  HOTKEYS: Press 'y' to toggle YOLO Mode | 'v' to cycle Dashboard Views | 'b' for QR Billboard View![/bold cyan]\n"
            f"{wallet_desc}\n"
        )
        sound_alarm(1, sound_type="bell")

        # Start background tasks
        await self.portal.start()
        regime_task = asyncio.create_task(self.regime.run())
        monitor_task = asyncio.create_task(self.position_monitor_loop())
        dashboard_task = asyncio.create_task(self.dashboard_loop())

        try:
            while self.running:
                await asyncio.sleep(1)
        except (KeyboardInterrupt, asyncio.CancelledError):
            pass
        finally:
            await self.shutdown(monitor_task, dashboard_task, regime_task)

    async def shutdown(self, monitor_task=None, dashboard_task=None, regime_task=None):
        """Gracefully shut down all tasks."""
        self.running = False
        self.restore_terminal()
        console.print("\n[bold yellow]Shutting down bot cleanly...[/bold yellow]")
        if self.portal:
            await self.portal.stop()
        if regime_task:
            regime_task.cancel()
        if monitor_task:
            monitor_task.cancel()
        if dashboard_task:
            dashboard_task.cancel()

        if self.session and not self.session.closed:
            await self.session.close()

        # Print final portfolio summary
        if self.trader:
            summary = self.trader.get_portfolio_summary()
            print_stream_header(summary, ml_samples=self.ml.total_trained_samples, guardian=self.guardian)
        console.print("[bold green]✅ Bot stopped cleanly.[/bold green]")


def main():
    parser = argparse.ArgumentParser(
        description="Solana PumpPortal & DexScreener ML Rug-Filtering Sniper Bot (Real Helius RPC & Paper Trading)"
    )
    parser.add_argument("--mode", type=str, default=config.TRADING_MODE, choices=["real", "paper"], help="Trading mode: real or paper")
    parser.add_argument("--paper", action="store_true", help="Shortcut for paper trading mode")
    parser.add_argument("--buy-amount", type=float, default=config.DEFAULT_BUY_AMOUNT_SOL, help=f"SOL per buy trade (default {config.DEFAULT_BUY_AMOUNT_SOL})")
    parser.add_argument("--tp", type=float, default=config.TAKE_PROFIT_PCT, help="Take Profit percentage (e.g. 50)")
    parser.add_argument("--sl", type=float, default=config.STOP_LOSS_PCT, help="Stop Loss percentage (e.g. 25)")
    parser.add_argument("--threshold", type=float, default=None, help="Rug Model V2 veto threshold (default: loaded from JSON)")
    parser.add_argument("--max-dev-buy", type=float, default=config.MAX_DEV_BUY_SOL, help=f"Max dev buy in SOL before veto (default {config.MAX_DEV_BUY_SOL})")
    parser.add_argument("--allow-farmed", action="store_true", help="Allow aged wallets (>30d) with <10 txns (default: blocked)")
    parser.add_argument("--no-socials-ok", action="store_true", help="Allow tokens with 0 socials (default: blocked)")
    parser.add_argument("-y", "--yolo", action="store_true", help="Activate YOLO Mode: Relax max positions and buy all the way to zero balance")
    parser.add_argument("--view", type=str, default=getattr(config, "DEFAULT_DASHBOARD_VIEW", "stream"), choices=["stream", "psychology", "trades", "expectancy", "billboard"], help="Initial dashboard view mode (default: stream)")
    parser.add_argument("--quiet", action="store_true", help="Disable loud terminal bells")

    args = parser.parse_args()

    mode = "paper" if args.paper else args.mode
    config.DEFAULT_BUY_AMOUNT_SOL = args.buy_amount
    config.TAKE_PROFIT_PCT = args.tp
    config.STOP_LOSS_PCT = args.sl
    config.MAX_DEV_BUY_SOL = args.max_dev_buy
    if args.allow_farmed:
        config.BLOCK_FARMED_WALLETS = False
    if args.no_socials_ok:
        config.REQUIRE_SOCIALS = False
    if args.yolo:
        config.YOLO_MODE = True
    sound_enabled = not args.quiet

    bot = PumpSniperBot(
        mode=mode,
        buy_amount=args.buy_amount,
        rug_threshold=args.threshold,
        sound_enabled=sound_enabled,
        yolo=config.YOLO_MODE,
        view_mode=args.view
    )

    try:
        asyncio.run(bot.start())
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
