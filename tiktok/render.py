#!/usr/bin/env python3
"""Build a 9:16 TikTok clip from official Manafall stills and screenshots."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STILLS = ROOT / "media" / "stills"
CLIPS = ROOT / "media" / "clips"
TACTICS_PATH = Path(__file__).resolve().parent / "tactics.json"

W, H, FPS = 1080, 1920, 30
FONT_BOLD = "/usr/share/fonts/truetype/macos/Inter-Bold.ttf"
FONT_MED = "/usr/share/fonts/truetype/macos/Inter-SemiBold.ttf"
FONT_REG = "/usr/share/fonts/truetype/macos/Inter-Medium.ttf"


def load_tactic(tactic_id: str) -> dict:
    data = json.loads(TACTICS_PATH.read_text(encoding="utf-8"))
    for tactic in data["tactics"]:
        if tactic["id"] == tactic_id:
            return tactic
    raise SystemExit(f"Unknown tactic: {tactic_id}")


def ff(*args: str) -> None:
    subprocess.run(["ffmpeg", "-y", *args], check=True)


def still_clip(
    image: Path,
    out: Path,
    duration: float,
    lines: list[tuple[str, int, str]],
    pan: str | bool,
) -> None:
    """Render one vertical scene. lines = [(text, fontsize, y_expr)].

    pan: False/'none' centered, 'ltr' left-to-right, 'rtl' right-to-left,
    'zoom' slow push-in.
    """
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        frames = max(int(duration * FPS), 1)
        if pan in (True, "ltr"):
            x_expr = f"min(n*(in_w-ow)/{frames}\\,in_w-ow)"
            y_expr = "(in_h-oh)/2"
            scale = f"scale={W}:{H}:force_original_aspect_ratio=increase:flags=lanczos"
        elif pan == "rtl":
            x_expr = f"max((in_w-ow)-n*(in_w-ow)/{frames}\\,0)"
            y_expr = "(in_h-oh)/2"
            scale = f"scale={W}:{H}:force_original_aspect_ratio=increase:flags=lanczos"
        elif pan == "zoom":
            scale = f"scale={int(W * 1.22)}:{int(H * 1.22)}:force_original_aspect_ratio=increase:flags=lanczos"
            x_expr = f"(in_w-ow)/2+n*((in_w-ow)/4)/{frames}"
            y_expr = f"(in_h-oh)/2-n*((in_h-oh)/5)/{frames}"
        elif pan == "right":
            # Bias to the right so top-left host debug HUD stays out of a 9:16 crop.
            x_expr = f"min(in_w-ow\\,(in_w-ow)*0.92-n*((in_w-ow)*0.12)/{frames})"
            y_expr = "(in_h-oh)/2"
            scale = f"scale={W}:{H}:force_original_aspect_ratio=increase:flags=lanczos"
        else:
            x_expr = "(in_w-ow)/2"
            y_expr = "(in_h-oh)/2"
            scale = f"scale={W}:{H}:force_original_aspect_ratio=increase:flags=lanczos"
        draws = [
            scale,
            f"crop={W}:{H}:{x_expr}:{y_expr}",
            "eq=contrast=1.06:saturation=1.1",
            "drawbox=y=0:h=170:color=black@0.35:t=fill",
            "drawbox=y=ih-560:h=560:color=black@0.58:t=fill",
        ]
        for i, (text, size, y) in enumerate(lines):
            tf = tmp_path / f"line{i}.txt"
            tf.write_text(text, encoding="utf-8")
            font = FONT_BOLD if i == 0 else FONT_MED if i == 1 else FONT_REG
            draws.append(
                "drawtext="
                f"fontfile={font}:"
                f"textfile={tf}:"
                f"fontsize={size}:"
                "fontcolor=white:"
                "borderw=3:"
                "bordercolor=black@0.7:"
                "x=(w-text_w)/2:"
                f"y={y}:"
                "line_spacing=10"
            )
        draws.append(f"fps={FPS}")
        draws.append("format=yuv420p")
        ff(
            "-loop",
            "1",
            "-i",
            str(image),
            "-t",
            str(duration),
            "-vf",
            ",".join(draws),
            "-an",
            "-c:v",
            "libx264",
            "-preset",
            "medium",
            "-crf",
            "19",
            "-pix_fmt",
            "yuv420p",
            str(out),
        )


def atmosphere(duration: float, out: Path) -> None:
    """Original low drone + wind. Not licensed stock music."""
    ff(
        "-f",
        "lavfi",
        "-i",
        f"anoisesrc=color=brown:amplitude=0.25:sample_rate=48000:duration={duration}",
        "-f",
        "lavfi",
        "-i",
        f"sine=frequency=58:sample_rate=48000:duration={duration}",
        "-filter_complex",
        "[0:a]lowpass=f=220,volume=0.55[a0];"
        "[1:a]volume=0.04[a1];"
        "[a0][a1]amix=inputs=2:duration=longest,afade=t=in:st=0:d=0.45,"
        f"afade=t=out:st={max(duration - 0.7, 0.2)}:d=0.7[a]",
        "-map",
        "[a]",
        "-c:a",
        "aac",
        "-b:a",
        "128k",
        "-ar",
        "48000",
        str(out),
    )


PREFERRED_BODY = (
    "splash.png",
    "itch-cover.jpg",
    "shot-01.png",
    "shot-05.png",
    "shot-06.png",
)


def pick_images() -> tuple[list[Path], Path]:
    """Clean key art first. Skip debug-heavy host screenshots when cropping 9:16."""
    splash = STILLS / "splash.png"
    cover = STILLS / "itch-cover.jpg"
    symbol = STILLS / "symbol.png"
    trailer = STILLS / "trailer-frame.jpg"
    body: list[Path] = []
    for name in PREFERRED_BODY:
        path = STILLS / name
        if path.exists():
            body.append(path)
    if trailer.exists() and trailer not in body:
        body.append(trailer)
    if not body:
        raise SystemExit("No stills found under media/stills/")
    closer = symbol if symbol.exists() else body[-1]
    return body, closer


def render(tactic_id: str, outfile: Path) -> Path:
    tactic = load_tactic(tactic_id)
    body, closer = pick_images()
    lines = tactic["onScreen"]
    hook, mid, close = (lines + ["Manafall", "Free playtest", "Play now"])[:3]
    extras = tactic.get("beatLines") or [
        "Breath magic. Land claims.",
        "Free dark-fantasy playtest",
    ]
    CLIPS.mkdir(parents=True, exist_ok=True)
    outfile.parent.mkdir(parents=True, exist_ok=True)

    sequence = body[:5]
    pans = ["zoom", "ltr", "none", "zoom", "zoom"]
    beats = [
        [(hook, 78, "h-470")],
        [(mid, 58, "h-430")],
        [(close, 54, "h-430")],
        [(extras[0], 46, "h-430")],
        [(extras[-1], 46, "h-430")],
    ]
    scene_len = 2.15
    end_len = 3.4
    total = scene_len * min(len(sequence), 5) + end_len

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        parts: list[Path] = []
        for i, image in enumerate(sequence[:5]):
            out = tmp_path / f"s{i}.mp4"
            still_clip(image, out, scene_len, beats[i], pans[i])
            parts.append(out)
        end = tmp_path / "end.mp4"
        still_clip(
            closer,
            end,
            end_len,
            [
                ("MANAFALL", 76, "h-520"),
                ("jla1190.github.io/manafall-website", 28, "h-400"),
                ("orangejuice90.itch.io/manafall", 28, "h-330"),
            ],
            pan=False,
        )
        parts.append(end)

        concat = tmp_path / "concat.txt"
        concat.write_text(
            "".join(f"file '{p}'\n" for p in parts),
            encoding="utf-8",
        )
        joined = tmp_path / "joined.mp4"
        ff(
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(concat),
            "-c",
            "copy",
            str(joined),
        )
        audio = tmp_path / "a.m4a"
        atmosphere(total, audio)
        ff(
            "-i",
            str(joined),
            "-i",
            str(audio),
            "-c:v",
            "copy",
            "-c:a",
            "aac",
            "-b:a",
            "128k",
            "-shortest",
            "-movflags",
            "+faststart",
            str(outfile),
        )

    return outfile


def main() -> None:
    parser = argparse.ArgumentParser(description="Render a Manafall TikTok stills clip")
    parser.add_argument("--tactic", default="curiosity_gap")
    parser.add_argument(
        "--out",
        default=str(CLIPS / "manafall-stills-curiosity-gap.mp4"),
    )
    args = parser.parse_args()
    out = Path(args.out)
    if not shutil.which("ffmpeg"):
        raise SystemExit("ffmpeg is required")
    path = render(args.tactic, out)
    print(path)


if __name__ == "__main__":
    main()
