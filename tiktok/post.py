#!/usr/bin/env python3
"""Pick one Manafall clip, rotate a caption tactic, and Direct Post to TikTok."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
HERE = Path(__file__).resolve().parent
MEDIA_CLIPS = ROOT / "media" / "clips"
LOG_PATH = HERE / "log.json"
OUTBOX = HERE / "outbox"
CONFIG = json.loads((HERE / "config.json").read_text(encoding="utf-8"))
TACTICS = json.loads((HERE / "tactics.json").read_text(encoding="utf-8"))["tactics"]

INIT_URL = "https://open.tiktokapis.com/v2/post/publish/video/init/"
STATUS_URL = "https://open.tiktokapis.com/v2/post/publish/status/fetch/"
CREATOR_URL = "https://open.tiktokapis.com/v2/post/publish/creator_info/query/"
TOKEN_URL = "https://open.tiktokapis.com/v2/oauth/token/"


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def load_log() -> list[dict]:
    if not LOG_PATH.exists():
        return []
    return json.loads(LOG_PATH.read_text(encoding="utf-8"))


def save_log(entries: list[dict]) -> None:
    LOG_PATH.write_text(json.dumps(entries, indent=2) + "\n", encoding="utf-8")


def next_tactic(log: list[dict]) -> dict:
    if log and log[-1].get("status") == "blocked_no_credentials" and log[-1].get("tacticId"):
        for tactic in TACTICS:
            if tactic["id"] == log[-1]["tacticId"]:
                return tactic
    used = [
        row.get("tacticId")
        for row in log
        if row.get("tacticId") and row.get("status") == "posted"
    ]
    for tactic in TACTICS:
        if tactic["id"] not in used:
            return tactic
    last = used[-1] if used else None
    ids = [t["id"] for t in TACTICS]
    if last in ids:
        return TACTICS[(ids.index(last) + 1) % len(TACTICS)]
    return TACTICS[0]


def list_clips() -> list[Path]:
    if not MEDIA_CLIPS.exists():
        return []
    return sorted(
        [p for p in MEDIA_CLIPS.iterdir() if p.suffix.lower() in {".mp4", ".mov", ".webm"}],
        key=lambda p: p.stat().st_mtime,
    )


def next_clip(log: list[dict], clips: list[Path]) -> Path | None:
    if log and log[-1].get("status") == "blocked_no_credentials" and log[-1].get("clip"):
        retry = MEDIA_CLIPS / log[-1]["clip"]
        if retry.exists():
            return retry
    posted = {row.get("clip") for row in log if row.get("status") == "posted"}
    for clip in clips:
        if clip.name not in posted:
            return clip
    return clips[0] if clips else None


def ensure_clip(log: list[dict], tactic_id: str) -> Path:
    clips = list_clips()
    chosen = next_clip(log, clips)
    if chosen:
        return chosen
    MEDIA_CLIPS.mkdir(parents=True, exist_ok=True)
    out = MEDIA_CLIPS / f"manafall-stills-{tactic_id}.mp4"
    render = HERE / "render.py"
    subprocess.run(
        [sys.executable, str(render), "--tactic", tactic_id, "--out", str(out)],
        check=True,
    )
    return out


def refresh_access_token() -> str | None:
    refresh = os.environ.get("TIKTOK_REFRESH_TOKEN", "").strip()
    client_key = os.environ.get("TIKTOK_CLIENT_KEY", "").strip()
    client_secret = os.environ.get("TIKTOK_CLIENT_SECRET", "").strip()
    if not (refresh and client_key and client_secret):
        return None
    res = requests.post(
        TOKEN_URL,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        data={
            "client_key": client_key,
            "client_secret": client_secret,
            "grant_type": "refresh_token",
            "refresh_token": refresh,
        },
        timeout=30,
    )
    body = res.json()
    token = body.get("access_token")
    if not token:
        print("Token refresh failed:", json.dumps(body, indent=2), file=sys.stderr)
        return None
    return token


def access_token() -> str | None:
    token = os.environ.get("TIKTOK_ACCESS_TOKEN", "").strip()
    if token:
        return token
    return refresh_access_token()


def chunk_plan(size: int) -> tuple[int, int]:
    if size < 5 * 1024 * 1024:
        return size, 1
    chunk = 10 * 1024 * 1024
    count = (size + chunk - 1) // chunk
    return chunk, count


def privacy_level(token: str) -> str:
    res = requests.post(
        CREATOR_URL,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json; charset=UTF-8",
        },
        timeout=30,
    )
    body = res.json()
    options = (body.get("data") or {}).get("privacy_level_options") or []
    preferred = CONFIG["privacyPreference"]
    fallback = CONFIG["privacyFallback"]
    if preferred in options:
        return preferred
    if fallback in options:
        return fallback
    if options:
        return options[0]
    return fallback


def direct_post(token: str, clip: Path, caption: str, privacy: str) -> dict:
    size = clip.stat().st_size
    chunk_size, chunk_count = chunk_plan(size)
    init = requests.post(
        INIT_URL,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json; charset=UTF-8",
        },
        json={
            "post_info": {
                "title": caption,
                "privacy_level": privacy,
                "disable_duet": CONFIG["disableDuet"],
                "disable_comment": CONFIG["disableComment"],
                "disable_stitch": CONFIG["disableStitch"],
                "video_cover_timestamp_ms": CONFIG["coverTimestampMs"],
                "brand_content_toggle": CONFIG["brandContent"],
                "brand_organic_toggle": CONFIG["brandOrganic"],
            },
            "source_info": {
                "source": "FILE_UPLOAD",
                "video_size": size,
                "chunk_size": chunk_size,
                "total_chunk_count": chunk_count,
            },
        },
        timeout=60,
    )
    init_body = init.json()
    if (init_body.get("error") or {}).get("code") != "ok":
        return {"ok": False, "stage": "init", "response": init_body}

    upload_url = init_body["data"]["upload_url"]
    publish_id = init_body["data"]["publish_id"]
    mime = "video/mp4" if clip.suffix.lower() == ".mp4" else "video/quicktime"

    with clip.open("rb") as handle:
        sent = 0
        index = 0
        while sent < size:
            remaining = size - sent
            this = remaining if index == chunk_count - 1 else min(chunk_size, remaining)
            chunk = handle.read(this)
            start = sent
            end = sent + this - 1
            put = requests.put(
                upload_url,
                headers={
                    "Content-Type": mime,
                    "Content-Length": str(this),
                    "Content-Range": f"bytes {start}-{end}/{size}",
                },
                data=chunk,
                timeout=300,
            )
            if put.status_code >= 300:
                return {
                    "ok": False,
                    "stage": "upload",
                    "status": put.status_code,
                    "body": put.text[:2000],
                    "publish_id": publish_id,
                }
            sent += this
            index += 1

    status_body = None
    for _ in range(8):
        time.sleep(3)
        status = requests.post(
            STATUS_URL,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json; charset=UTF-8",
            },
            json={"publish_id": publish_id},
            timeout=30,
        )
        status_body = status.json()
        state = ((status_body.get("data") or {}).get("status") or "").upper()
        if state in {"PUBLISH_COMPLETE", "FAILED", "SEND_TO_USER_INBOX"}:
            break

    return {
        "ok": True,
        "stage": "done",
        "publish_id": publish_id,
        "init": init_body,
        "status": status_body,
    }


def write_outbox(package: dict) -> Path:
    OUTBOX.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d-%H%M%SZ")
    path = OUTBOX / f"{stamp}-{package['tacticId']}.json"
    path.write_text(json.dumps(package, indent=2) + "\n", encoding="utf-8")
    return path


def main() -> int:
    parser = argparse.ArgumentParser(description="Post one Manafall video to TikTok")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    log = load_log()
    tactic = next_tactic(log)
    clip = ensure_clip(log, tactic["id"])
    caption = tactic["caption"].strip()
    package = {
        "at": utc_now(),
        "account": CONFIG["account"],
        "tacticId": tactic["id"],
        "tacticName": tactic["name"],
        "goal": tactic["goal"],
        "clip": clip.name,
        "clipBytes": clip.stat().st_size,
        "websiteUrl": CONFIG["websiteUrl"],
        "itchUrl": CONFIG["itchUrl"],
        "hashtags": tactic["hashtags"],
        "caption": caption,
    }

    token = None if args.dry_run else access_token()
    if not token:
        package["status"] = "blocked_no_credentials"
        package["detail"] = (
            "No TIKTOK_ACCESS_TOKEN (or refresh trio) in this environment. "
            "Clip and caption are ready; publishing is blocked until TikTok "
            "Login Kit tokens are added to the automation environment."
        )
        outbox = write_outbox(package)
        log.append(
            {
                "at": package["at"],
                "tacticId": tactic["id"],
                "clip": clip.name,
                "status": package["status"],
                "outbox": outbox.name,
            }
        )
        save_log(log)
        print(json.dumps(package, indent=2))
        return 2

    privacy = privacy_level(token)
    package["privacy"] = privacy
    result = direct_post(token, clip, caption, privacy)
    package["tiktok"] = result
    package["status"] = "posted" if result.get("ok") else "publish_failed"
    outbox = write_outbox(package)
    log.append(
        {
            "at": package["at"],
            "tacticId": tactic["id"],
            "clip": clip.name,
            "status": package["status"],
            "privacy": privacy,
            "publishId": (result.get("publish_id") or (result.get("init") or {}).get("data", {}).get("publish_id")),
            "outbox": outbox.name,
        }
    )
    save_log(log)
    print(json.dumps(package, indent=2))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
