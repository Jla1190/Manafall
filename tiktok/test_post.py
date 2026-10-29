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
        self.assertTrue(CONFIG["androidDownloadPage"].startswith("https://"))
        self.assertIn("#download", CONFIG["androidDownloadPage"])

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
        self.assertIn("save_this", ids)
        self.assertIn("phone_first", ids)
        self.assertIn("breath_pick", ids)
        self.assertIn("home_claim", ids)
        self.assertIn("curse_pick", ids)
        self.assertEqual(ids[-1], "fyp_broad")
        self.assertLessEqual(len(ids), 16)

    def test_blocked_retry_prefers_new_gameplay(self) -> None:
        import post
        from pathlib import Path

        log = [
            {
                "tacticId": "curiosity_gap",
                "clip": "manafall-stills-curiosity-gap.mp4",
                "status": "blocked_no_credentials",
            }
        ]
        stills = Path("manafall-stills-curiosity-gap.mp4")
        gameplay = Path("tavern-first-night.mp4")
        chosen = post.next_clip(log, [stills, gameplay])
        self.assertEqual(chosen.name, "tavern-first-night.mp4")
        chosen_stills_only = post.next_clip(log, [stills])
        self.assertEqual(chosen_stills_only.name, "manafall-stills-curiosity-gap.mp4")

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

    def test_phone_first_sells_android_without_mega_links(self) -> None:
        tactic = next(t for t in TACTICS if t["id"] == "phone_first")
        caption = tactic["caption"]
        self.assertIn("Android", caption)
        self.assertIn("Windows", caption)
        self.assertIn("#AndroidGames", tactic["hashtags"])
        self.assertNotIn("mega.nz", caption.lower())
        self.assertIn("jla1190.github.io/manafall-website", caption)

    def test_breath_pick_is_a_four_option_magic_poll(self) -> None:
        tactic = next(t for t in TACTICS if t["id"] == "breath_pick")
        caption = tactic["caption"]
        for breath in ("Ember", "Rime", "Verdure", "Hollow"):
            self.assertIn(breath, caption)
        self.assertIn("A =", caption)
        self.assertIn("D =", caption)
        self.assertIn("#MagicSystem", tactic["hashtags"])
        self.assertNotIn("mega.nz", caption.lower())

    def test_home_claim_sells_base_building(self) -> None:
        tactic = next(t for t in TACTICS if t["id"] == "home_claim")
        caption = tactic["caption"]
        self.assertIn("house", caption.lower())
        self.assertIn("Warden Core", caption)
        self.assertIn("#BaseBuilding", tactic["hashtags"])
        self.assertIn("Comment", caption)
        self.assertNotIn("mega.nz", caption.lower())
        self.assertIn("jla1190.github.io/manafall-website", caption)
        self.assertIn("orangejuice90.itch.io/manafall", caption)

    def test_curse_pick_is_vampire_werewolf_poll(self) -> None:
        tactic = next(t for t in TACTICS if t["id"] == "curse_pick")
        caption = tactic["caption"]
        self.assertIn("Vampire", caption)
        self.assertIn("Werewolf", caption)
        self.assertIn("mutually exclusive", caption.lower())
        self.assertIn("Comment A or B", caption)
        self.assertIn("#Werewolf", tactic["hashtags"])
        self.assertIn("#Vampire", tactic["hashtags"])
        self.assertNotIn("mega.nz", caption.lower())
        self.assertIn("jla1190.github.io/manafall-website", caption)
        self.assertIn("orangejuice90.itch.io/manafall", caption)


if __name__ == "__main__":
    unittest.main()
