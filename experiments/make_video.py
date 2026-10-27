"""Edit authentic Studio screen captures into a silent, reproducible launch clip.

Usage: python experiments/make_video.py --assets docs/media/launch-v1 \
    --output docs/media/morphproof-demo-v1.mp4
Requires FFmpeg/ffprobe with libx264 and drawtext. No network or model service.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
import subprocess
import tempfile

SHOTS = [
    ("01-overview.png", 4, "PYTHON → RUST / INDEPENDENT EVIDENCE", "Python to Rust. Behavioral evidence stays visible.", "Real execution. Declared contracts. Recorded limitations."),
    ("02-seeded-failure-v2.png", 4, "01 / CHALLENGE A DISCLOSED SEEDED DEFECT", "Seeded defect. 393 checks. 51 observed differences.", "The off-by-one defect was intentionally injected for this demonstration."),
    ("03-minimized-counterexample.png", 6, "02 / INSPECT THE COUNTEREXAMPLE", "Minimal discovered input [1]. Python: 1. Rust: 0.", "Independent input selection and bounded counterexample minimization."),
    ("04-repaired-rust.png", 5, "03 / REPAIR, THEN VERIFY AGAIN", "Agent repair. 777 fresh checks. No mismatch observed.", "768 positional comparisons + 9 bounded keyword API checks."),
    ("05-benchmark.png", 5, "04 / MEASURE THE ACTUAL PYTHON API", "1.96× on sum_squares. 100,000 floats. 11 repeats.", "Includes API conversion. Results vary by function and input size."),
]


def execute(args):
    subprocess.run([str(x) for x in args], check=True, stdout=subprocess.DEVNULL)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--assets", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--font", type=Path)
    a = p.parse_args()
    output = a.output.resolve()
    if output.exists() or output.is_symlink():
        raise SystemExit("Choose a new output path; existing renders are never overwritten")
    assets = a.assets.resolve()
    for filename, *_ in SHOTS:
        if not (assets / filename).is_file():
            raise SystemExit(f"Missing authentic screenshot: {filename}")
    ffmpeg = shutil.which("ffmpeg")
    ffprobe = shutil.which("ffprobe")
    if not ffmpeg or not ffprobe:
        raise SystemExit("FFmpeg and ffprobe must be available on PATH")
    font = a.font or next((p for p in [Path('/System/Library/Fonts/Supplemental/Arial.ttf'), Path('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf')] if p.exists()), None)
    if not font or not font.is_file():
        raise SystemExit("Pass --font with a readable TrueType font")
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="morphproof-video-", dir=output.parent) as temp:
        temp = Path(temp)
        segments = []
        for index, (filename, duration, label, title, note) in enumerate(SHOTS):
            files = []
            for number, text in enumerate((label, title, note)):
                f = temp / f"caption-{index}-{number}.txt"
                f.write_text(text, encoding="utf-8")
                files.append(f)
            filters = ["scale=1280:720:flags=lanczos", "setsar=1", "format=yuv420p",
                       "drawbox=x=0:y=617:w=1280:h=103:color=0x242923@0.98:t=fill",
                       "drawbox=x=0:y=617:w=8:h=103:color=0xd84f24:t=fill"]
            for f, size, y, color in zip(files, [12, 25, 15], [630, 650, 689], ['aab9a5', 'fffefa', 'c6cfc0']):
                filters.append(f"drawtext=fontfile='{font}':textfile='{f}':fontsize={size}:fontcolor=0x{color}:x=31:y={y}")
            segment = temp / f"shot-{index}.mp4"
            execute([ffmpeg, "-v", "error", "-nostdin", "-n", "-loop", "1", "-framerate", "30", "-t", str(duration), "-i", assets / filename,
                     "-vf", ",".join(filters), "-an", "-c:v", "libx264", "-preset", "medium", "-crf", "17", "-pix_fmt", "yuv420p", "-r", "30", segment])
            segments.append(segment)
        endtext = ["MORPHPROOF", "Change code.", "Keep the contract.", "A finite test suite is evidence, not universal proof.", "Local execution  /  Reproducible experiments  /  Open source"]
        filters = ["drawbox=x=76:y=74:w=26:h=26:color=0xd84f24:t=fill", "drawbox=x=111:y=109:w=26:h=26:color=0xd84f24:t=fill", "drawbox=x=76:y=163:w=1128:h=1:color=0x485344:t=fill"]
        for i, (text, size, y, color) in enumerate(zip(endtext, [29, 78, 78, 23, 16], [85, 221, 313, 469, 566], ['f5f3ec', 'f5f3ec', 'e56438', 'd2dacb', 'aab9a5'])):
            f = temp / f"end-{i}.txt"
            f.write_text(text, encoding="utf-8")
            x = 164 if i == 0 else 76
            filters.append(f"drawtext=fontfile='{font}':textfile='{f}':fontsize={size}:fontcolor=0x{color}:x={x}:y={y}")
        end = temp / "shot-end.mp4"
        execute([ffmpeg, "-v", "error", "-nostdin", "-n", "-f", "lavfi", "-i", "color=c=0x242923:s=1280x720:r=30:d=4", "-vf", ",".join(filters), "-an", "-c:v", "libx264", "-preset", "medium", "-crf", "17", "-pix_fmt", "yuv420p", end])
        segments.append(end)
        # Short dips to black retain legibility; transition timing is editorial,
        # not a representation of tool execution speed.
        inputs = []
        for segment in segments:
            inputs += ["-i", segment]
        timeline = []
        durations = [x[1] for x in SHOTS] + [4]
        elapsed = durations[0]
        previous = "0:v"
        for i in range(1, len(segments)):
            elapsed -= 0.3
            label = f"x{i}"
            timeline.append(f"[{previous}][{i}:v]xfade=transition=fadeblack:duration=0.3:offset={elapsed:.3f}[{label}]")
            previous = label
            elapsed += durations[i]
        staged = temp / "verified-master.mp4"
        execute([ffmpeg, "-v", "error", "-nostdin", "-n", *inputs, "-filter_complex_threads", "1", "-filter_complex", ";".join(timeline), "-map", f"[{previous}]", "-an", "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p", "-movflags", "+faststart", staged])
        probe = json.loads(subprocess.check_output([ffprobe, "-v", "error", "-show_streams", "-show_format", "-of", "json", str(staged)]))
        video = next(s for s in probe['streams'] if s['codec_type'] == 'video')
        assert (video['width'], video['height']) == (1280, 720)
        assert not any(s['codec_type'] == 'audio' for s in probe['streams'])
        assert abs(float(probe['format']['duration']) - 26.5) < 0.1
        execute([ffmpeg, "-v", "error", "-nostdin", "-i", staged, "-f", "null", "-"])
        staged.rename(output)
        print(json.dumps({"output":str(output),"duration_seconds":float(probe['format']['duration']),"width":1280,"height":720,"audio":False,"full_decode":"passed"}, indent=2))


if __name__ == "__main__":
    main()
