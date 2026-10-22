#!/usr/bin/env python3
"""Build a 9:16 TikTok clip from official Manafall stills."""

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

    pan: False/'none' centered, 'ltr' left-to-right, 'rtl' right-to-left.
    """
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        text_files: list[Path] = []
        frames = max(int(duration * FPS), 1)
        if pan in (True, "ltr"):
            x_expr = f"min(n*(in_w-ow)/{frames}\\,in_w-ow)"
        elif pan == "rtl":
            x_expr = f"max((in_w-ow)-n*(in_w-ow)/{frames}\\,0)"
        else:
            x_expr = "(in_w-ow)/2"
        draws = [
            f"scale={W}:{H}:force_original_aspect_ratio=increase:flags=lanczos",
            f"crop={W}:{H}:{x_expr}:(in_h-oh)/2",
            "eq=contrast=1.05:saturation=1.08",
            "drawbox=y=ih-620:h=620:color=black@0.55:t=fill",
        ]
        for i, (text, size, y) in enumerate(lines):
            tf = tmp_path / f"line{i}.txt"
            tf.write_text(text, encoding="utf-8")
            text_files.append(tf)
            font = FONT_BOLD if i == 0 else FONT_MED
            draws.append(
                "drawtext="
                f"fontfile={font}:"
                f"textfile={tf}:"
                f"fontsize={size}:"
                "fontcolor=white:"
                "borderw=3:"
                "bordercolor=black@0.65:"
                "x=(w-text_w)/2:"
                f"y={y}:"
                "line_spacing=12"
            )
        draws.append(f"fps={FPS}")
        draws.append("format=yuv420p")
        filter_str = ",".join(draws)
        ff(
            "-loop",
            "1",
            "-i",
            str(image),
            "-t",
            str(duration),
            "-vf",
            filter_str,
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
        "[a0][a1]amix=inputs=2:duration=longest,afade=t=in:st=0:d=0.6,"
        f"afade=t=out:st={duration-0.8}:d=0.8[a]",
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


def render(tactic_id: str, outfile: Path) -> Path:
    tactic = load_tactic(tactic_id)
    splash = STILLS / "splash.png"
    cover = STILLS / "itch-cover.jpg"
    symbol = STILLS / "symbol.png"
    for path in (splash, cover, symbol):
        if not path.exists():
            raise SystemExit(f"Missing still: {path}")

    lines = tactic["onScreen"]
    hook, mid, close = (lines + ["Manafall", "Free playtest", "Play now"])[:3]
    CLIPS.mkdir(parents=True, exist_ok=True)
    outfile.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        s1 = tmp_path / "s1.mp4"
        s2 = tmp_path / "s2.mp4"
        s3 = tmp_path / "s3.mp4"
        audio = tmp_path / "a.m4a"
        concat = tmp_path / "concat.txt"

        still_clip(
            splash,
            s1,
            5.0,
            [
                (hook, 72, "h-520"),
                (mid, 44, "h-400"),
            ],
            pan="ltr",
        )
        still_clip(
            cover,
            s2,
            4.5,
            [
                (close, 56, "h-480"),
                ("Free dark-fantasy playtest", 36, "h-360"),
            ],
            pan="rtl",
        )
        still_clip(
            symbol,
            s3,
            4.5,
            [
                ("MANAFALL", 78, "h-560"),
                ("jla1190.github.io/manafall-website", 28, "h-430"),
                ("orangejuice90.itch.io/manafall", 28, "h-360"),
            ],
            pan=False,
        )

        concat.write_text(
            f"file '{s1}'\nfile '{s2}'\nfile '{s3}'\n",
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
        atmosphere(14.0, audio)
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
