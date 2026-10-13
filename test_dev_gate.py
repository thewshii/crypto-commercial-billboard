"""
Unit & Acceptance Test Suite for Multi-Factor Dev Buy Security Gate.
Tests all vectors tightened against sneaky micro-buy rugs (< 0.25 SOL):
1. Hard floor enforcement (< 0.08 SOL)
2. Burner wallet age check (< 24 hours on micro-buys)
3. Burner wallet txns check (< 15 txns on micro-buys)
4. Unconfirmed on-chain wallet history
5. Dummy / placeholder URL blocking (x.com, t.me, pump.fun, etc.)
6. Multi-social depth requirement (>= 2 channels for micro-buys)
7. Supply hoarding cap (> 6.0% supply on micro-buys)
8. Spam & phishing keyword blacklist (test, airdrop, claim, official, etc.)
9. Metadata description quality check
10. Valid micro-buy passing criteria
11. High-capital launch passing criteria
"""

import unittest
from dev_gate import evaluate_dev_gate, validate_social_urls, check_spam_keywords
import config


class TestDevBuyGate(unittest.TestCase):

    def test_social_url_validation(self):
        # Dummy links must fail
        dummy_meta = {
            "twitter": "https://x.com",
            "telegram": "https://t.me",
            "website": "https://pump.fun"
        }
        res = validate_social_urls(dummy_meta)
        self.assertEqual(res["valid_count"], 0)
        self.assertFalse(res["has_twitter"])
        self.assertFalse(res["has_telegram"])
        self.assertFalse(res["has_website"])

        # Navigation URLs must fail
        nav_meta = {"twitter": "https://x.com/search", "telegram": "https://t.me/share"}
        res2 = validate_social_urls(nav_meta)
        self.assertEqual(res2["valid_count"], 0)

        # Real URLs must pass
        real_meta = {
            "twitter": "https://x.com/SolanaGem2026",
            "telegram": "https://t.me/SolanaGemPortal",
            "website": "https://solanagem.io"
        }
        res3 = validate_social_urls(real_meta)
        self.assertEqual(res3["valid_count"], 3)
        self.assertTrue(res3["has_twitter"])
        self.assertTrue(res3["has_telegram"])
        self.assertTrue(res3["has_website"])

    def test_spam_keywords(self):
        # Flagged keywords
        self.assertTrue(check_spam_keywords("Test Token", "TEST")[0])
        self.assertTrue(check_spam_keywords("Pepe Airdrop", "PEPE")[0])
        self.assertTrue(check_spam_keywords("Trump Claim", "CLAIM")[0])
        self.assertTrue(check_spam_keywords("Presale Token", "PRESALE")[0])
        self.assertTrue(check_spam_keywords("Solana Official", "OFFICIAL")[0])

        # Clean keywords
        self.assertFalse(check_spam_keywords("Obria Autonomous AI", "OBRIA")[0])
        self.assertFalse(check_spam_keywords("Cyber Quantum Cat", "CQCAT")[0])

    def test_hard_dev_buy_floor(self):
        # 0.05 SOL buy (the sneak from earlier) must be rejected!
        tok_05 = {"symbol": "SNEAK", "name": "Sneaky Gem", "solAmount": 0.05}
        passed, reason = evaluate_dev_gate(tok_05)
        self.assertFalse(passed)
        self.assertIn("DEV ZERO/MICRO BUY", reason)

        # 0.075 SOL buy must be rejected by 0.08 floor
        tok_075 = {"symbol": "SNEAK", "name": "Sneaky Gem", "solAmount": 0.075}
        passed, reason = evaluate_dev_gate(tok_075)
        self.assertFalse(passed)
        self.assertIn("DEV ZERO/MICRO BUY", reason)

    def test_micro_buy_burner_wallet(self):
        tok = {"symbol": "BURNER", "name": "Burner Token", "solAmount": 0.12}
        meta = {
            "twitter": "https://x.com/BurnerProject",
            "telegram": "https://t.me/BurnerPortal",
            "description": "Legitimate decentralized protocol launch on Solana"
        }

        # Case A: 2 hours old (< 24h)
        stats_young = {"has_data": True, "age_days": 0.08, "txns": 30}
        passed, reason = evaluate_dev_gate(tok, meta, {}, stats_young)
        self.assertFalse(passed)
        self.assertIn("BURNER DEV WALLET", reason)
        self.assertIn("< 24h", reason)

        # Case B: 3 transactions (< 15 required)
        stats_few_txns = {"has_data": True, "age_days": 5.0, "txns": 3}
        passed, reason = evaluate_dev_gate(tok, meta, {}, stats_few_txns)
        self.assertFalse(passed)
        self.assertIn("BURNER DEV WALLET", reason)
        self.assertIn("< 15 required", reason)

        # Case C: Unconfirmed on-chain stats (has_data = False)
        stats_no_data = {"has_data": False}
        passed, reason = evaluate_dev_gate(tok, meta, {}, stats_no_data)
        self.assertFalse(passed)
        self.assertIn("UNVERIFIED DEV WALLET", reason)

    def test_micro_buy_social_requirements(self):
        tok = {"symbol": "COMM", "name": "Community Token", "solAmount": 0.10}
        stats = {"has_data": True, "age_days": 5.0, "txns": 25}

        # Only 1 social link on non-veteran wallet (<30d) -> MUST VETO
        meta_1_social = {
            "twitter": "https://x.com/CommunityToken",
            "description": "Legitimate decentralized protocol launch on Solana"
        }
        passed, reason = evaluate_dev_gate(tok, meta_1_social, {}, stats)
        self.assertFalse(passed)
        self.assertIn("WEAK SOCIALS", reason)

        # 2 verified social links on same wallet -> PASS
        meta_2_socials = {
            "twitter": "https://x.com/CommunityToken",
            "telegram": "https://t.me/CommunityPortal",
            "description": "Legitimate decentralized protocol launch on Solana"
        }
        passed, reason = evaluate_dev_gate(tok, meta_2_socials, {}, stats)
        self.assertTrue(passed)

    def test_supply_hoarding_veto(self):
        # Dev holding 12% supply with only 0.10 SOL buy
        tok = {
            "symbol": "HOARD",
            "name": "Hoarder Token",
            "solAmount": 0.10,
            "top_holder_pct": 0.12
        }
        meta = {
            "twitter": "https://x.com/HoarderCoin",
            "telegram": "https://t.me/HoarderCoin",
            "description": "Legitimate decentralized protocol launch on Solana"
        }
        stats = {"has_data": True, "age_days": 10.0, "txns": 30}
        passed, reason = evaluate_dev_gate(tok, meta, {}, stats)
        self.assertFalse(passed)
        self.assertIn("SUPPLY HOARDING", reason)

    def test_legitimate_tokens_pass(self):
        # Legitimate micro-buy (0.15 SOL with seasoned dev & multi-socials)
        tok_micro = {
            "symbol": "VALID",
            "name": "Valid Community Token",
            "solAmount": 0.15,
            "top_holder_pct": 0.03
        }
        meta_valid = {
            "twitter": "https://x.com/ValidToken",
            "telegram": "https://t.me/ValidPortal",
            "website": "https://validtoken.io",
            "description": "Next generation decentralized intelligence on Solana"
        }
        stats_valid = {"has_data": True, "age_days": 14.0, "txns": 65}
        passed, reason = evaluate_dev_gate(tok_micro, meta_valid, {}, stats_valid)
        self.assertTrue(passed, f"Valid token should pass: {reason}")

        # Legitimate high-capital buy (0.45 SOL, seasoned wallet)
        tok_high = {
            "symbol": "OBRIA",
            "name": "Obria Autonomous AI",
            "solAmount": 0.45,
            "top_holder_pct": 0.02
        }
        stats_high = {"has_data": True, "age_days": 400.0, "txns": 80}
        passed, reason = evaluate_dev_gate(tok_high, meta_valid, {}, stats_high)
        self.assertTrue(passed, f"High-capital token should pass: {reason}")

    def test_incubated_farmed_wallet_guardrail(self):
        meta_valid = {
            "twitter": "https://x.com/ValidToken",
            "telegram": "https://t.me/ValidPortal",
            "website": "https://validtoken.io",
            "description": "Legitimate protocol launch on Solana"
        }

        # Case 1: 0.50 SOL dev buy on 15d old account (matches 0.30-2.0 SOL / 7-30d pattern)
        tok_05 = {"symbol": "INCUB", "name": "Incubated Rug", "solAmount": 0.50}
        stats_15d = {"has_data": True, "age_days": 15.0, "txns": 20}
        passed, reason = evaluate_dev_gate(tok_05, meta_valid, {}, stats_15d)
        self.assertFalse(passed)
        self.assertIn("INCUBATED FARMED WALLET", reason)
        self.assertIn("0.30-2.0 SOL / 7-30d", reason)

        # Case 2: 1.80 SOL dev buy on 28d old account
        tok_18 = {"symbol": "INCUB2", "name": "Incubated Whale", "solAmount": 1.80}
        stats_28d = {"has_data": True, "age_days": 28.0, "txns": 40}
        passed, reason = evaluate_dev_gate(tok_18, meta_valid, {}, stats_28d)
        self.assertFalse(passed)
        self.assertIn("INCUBATED FARMED WALLET", reason)

        # Case 3: Boundaries (0.30 SOL and 7.0 days)
        tok_boundary = {"symbol": "BOUND", "name": "Boundary Token", "solAmount": 0.30}
        stats_7d = {"has_data": True, "age_days": 7.0, "txns": 30}
        passed, reason = evaluate_dev_gate(tok_boundary, meta_valid, {}, stats_7d)
        self.assertFalse(passed)
        self.assertIn("INCUBATED FARMED WALLET", reason)

        # Case 4: Boundaries (2.00 SOL and 30.0 days)
        tok_boundary2 = {"symbol": "BOUND2", "name": "Boundary Token 2", "solAmount": 2.00}
        stats_30d = {"has_data": True, "age_days": 30.0, "txns": 55}
        passed, reason = evaluate_dev_gate(tok_boundary2, meta_valid, {}, stats_30d)
        self.assertFalse(passed)
        self.assertIn("INCUBATED FARMED WALLET", reason)

    def test_incubated_scrutiny_mode(self):
        meta_valid = {
            "twitter": "https://x.com/ValidToken",
            "telegram": "https://t.me/ValidPortal",
            "website": "https://validtoken.io",
            "description": "Legitimate protocol launch on Solana"
        }
        tok = {"symbol": "SCRUT", "name": "Scrutiny Token", "solAmount": 0.80, "top_holder_pct": 0.05}

        # Temporarily disable outright blocking to test scrutiny requirements
        orig_outright = getattr(config, "INCUBATED_BLOCK_OUTRIGHT", True)
        try:
            config.INCUBATED_BLOCK_OUTRIGHT = False

            # Low txns (< 60) -> must fail
            stats_low_txns = {"has_data": True, "age_days": 14.0, "txns": 25}
            passed, reason = evaluate_dev_gate(tok, meta_valid, {}, stats_low_txns)
            self.assertFalse(passed)
            self.assertIn("< 60 required", reason)

            # High txns (>= 60), valid socials, normal supply -> passes scrutiny!
            stats_high_txns = {"has_data": True, "age_days": 14.0, "txns": 75}
            passed, reason = evaluate_dev_gate(tok, meta_valid, {}, stats_high_txns)
            self.assertTrue(passed, f"High activity wallet should pass scrutiny: {reason}")
        finally:
            config.INCUBATED_BLOCK_OUTRIGHT = orig_outright


if __name__ == "__main__":
    unittest.main()
