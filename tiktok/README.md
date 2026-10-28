# Manafall TikTok poster

Posts one clip from `media/clips/` to **@manafalltiktoc** using TikTok's Content Posting API (Direct Post, `video.publish`).

Each run:

1. Picks the next unposted clip (or renders a 9:16 stills clip if `media/clips/` is empty)
2. Rotates a caption tactic from `tactics.json`
3. Always includes the website and itch.io URLs, plus a tight hashtag set
4. Publishes when TikTok tokens are present; otherwise writes a ready-to-post package under `outbox/`

```bash
python3 -m pip install -r tiktok/requirements.txt
python3 tiktok/post.py            # live post when tokens exist
python3 tiktok/post.py --dry-run  # always skip the API
```

## Tokens (keep off git)

Set these on the Cursor automation environment, not in the repo:

- `TIKTOK_ACCESS_TOKEN` — user token with `video.publish` (starts with `act.`)
- `TIKTOK_REFRESH_TOKEN`, `TIKTOK_CLIENT_KEY`, `TIKTOK_CLIENT_SECRET` — optional refresh

You can also copy `tokens.example.json` to gitignored `tiktok/.tokens.json`. Environment variables win.

Login Kit + sandbox helpers already live on the website Content Studio:

https://jla1190.github.io/manafall-website/content-studio/

Unaudited TikTok apps can only post as private (`SELF_ONLY`). After TikTok audits the app, posts can be public.

## Links every caption must carry

- Site: https://jla1190.github.io/manafall-website/
- itch.io: https://orangejuice90.itch.io/manafall

## Schedule

This automation currently fires once daily at **14:00 UTC** (US late morning / EU afternoon). Add a second Cursor cron at **23:00 UTC** so it actually posts twice a day (US evening peak). Tactics retry the same package until a post publishes, then rotate:

curiosity gap → lore drop → feature flex → honest playtest → class pick → night warning → three-thing list → POV wash-ashore → weekend session → stitch-this → save-this → phone-first Android → Four Breaths poll → home/claim `#BaseBuilding` → broad `#fyp` test.

Saturday/Sunday runs jump to the weekend session invite once a post has actually gone live. Unposted stills packages retry the same tactic, but a new gameplay `.mp4` in `media/clips/` wins immediately.
