#!/usr/bin/env python3
"""Guardrails for captions, tactics, and clip selection."""

from __future__ import annotations

import json
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
CONFIG = json.loads((HERE / "config.json").read_text(encoding="utf-8"))
TACTICS = json.loads((HERE / "tactics.json").read_text(encoding="utf-8"))["tactics"]


class CaptionTests(unittest.TestCase):
    def test_every_tactic_points_at_site_and_itch(self) -> None:
        for tactic in TACTICS:
            caption = tactic["caption"]
            with self.subTest(tactic=tactic["id"]):
                self.assertIn("jla1190.github.io/manafall-website", caption)
                self.assertIn("orangejuice90.itch.io/manafall", caption)
                self.assertLessEqual(len(tactic["hashtags"]), 5)
                self.assertIn("#Manafall", tactic["hashtags"])
                self.assertLessEqual(len(caption), 2200)

    def test_config_urls(self) -> None:
        self.assertEqual(CONFIG["account"], "@manafalltiktoc")
        self.assertTrue(CONFIG["websiteUrl"].startswith("https://"))
        self.assertTrue(CONFIG["itchUrl"].startswith("https://"))

    def test_retry_blocked_post_keeps_tactic(self) -> None:
        import post

        log = [
            {
                "tacticId": "curiosity_gap",
                "clip": "manafall-stills-curiosity-gap.mp4",
                "status": "blocked_no_credentials",
            }
        ]
        tactic = post.next_tactic(log)
        self.assertEqual(tactic["id"], "curiosity_gap")

    def test_posted_tactics_rotate(self) -> None:
        import post

        log = [{"tacticId": "curiosity_gap", "status": "posted"}]
        tactic = post.next_tactic(log, weekday=2)
        self.assertEqual(tactic["id"], "lore_drop")

    def test_new_experiment_tactics_exist(self) -> None:
        ids = [t["id"] for t in TACTICS]
        self.assertIn("listicle_three", ids)
        self.assertIn("pov_ash", ids)
        self.assertIn("weekend_island", ids)
        self.assertIn("stitch_this", ids)
        self.assertEqual(ids[-1], "fyp_broad")
        self.assertLessEqual(len(ids), 12)

    def test_weekend_prefers_session_invite_after_a_real_post(self) -> None:
        import post

        log = [{"tacticId": "curiosity_gap", "status": "posted"}]
        tactic = post.next_tactic(log, weekday=5)
        self.assertEqual(tactic["id"], "weekend_island")
        weekday_run = post.next_tactic(log, weekday=2)
        self.assertEqual(weekday_run["id"], "lore_drop")

    def test_ab_poll_sits_in_first_caption(self) -> None:
        first = TACTICS[0]
        self.assertEqual(first["id"], "curiosity_gap")
        self.assertIn("Comment A or B", first["caption"])


if __name__ == "__main__":
    unittest.main()
