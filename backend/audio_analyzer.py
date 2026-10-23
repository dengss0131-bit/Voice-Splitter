from dataclasses import dataclass
import json
import math
import subprocess
from pathlib import Path

@dataclass
class SplitSettings:
    min_segment: float = 1.2
    max_segment: float = 5.0
    silence_ms: int = 280
    silence_db: int = -35
    mode: str = "knowledge"

SENTENCE_MARKS = "。！？!?"
SOFT_MARKS = "，,；;、"

def split_script(text: str) -> list[str]:
    text = " ".join((text or "").split())
    if not text:
        return []
    result = []
    buffer = ""
    for char in text:
        buffer += char
        if char in SENTENCE_MARKS or char in SOFT_MARKS:
            result.append(buffer.strip())
            buffer = ""
    if buffer.strip():
        result.append(buffer.strip())
    return result

def get_duration(input_path: str) -> float:
    cmd = ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "json", input_path]
    result = subprocess.run(cmd, check=True, capture_output=True, text=True)
    return float(json.loads(result.stdout)["format"]["duration"])

def detect_silences(input_path: str, settings: SplitSettings) -> list[dict]:
    cmd = [
        "ffmpeg", "-hide_banner", "-nostats", "-i", input_path,
        "-af", f"silencedetect=noise={settings.silence_db}dB:d={settings.silence_ms / 1000}",
        "-f", "null", "-",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    silences = []
    current = None
    for line in result.stderr.splitlines():
        if "silence_start:" in line:
            try:
                current = float(line.split("silence_start:", 1)[1].strip())
            except ValueError:
                current = None
        elif "silence_end:" in line and current is not None:
            try:
                after = line.split("silence_end:", 1)[1]
                end = float(after.split("|", 1)[0].strip())
                silence_duration = end - current
                silences.append({
                    "start": round(current, 3),
                    "end": round(end, 3),
                    "mid": round((current + end) / 2, 3),
                    "duration": round(silence_duration, 3),
                    "type": classify_pause(silence_duration, settings.mode),
                })
            except ValueError:
                pass
            current = None
    return silences

def classify_pause(silence_duration: float, mode: str) -> str:
    if mode == "slow":
        if silence_duration >= 0.9:
            return "剪辑气口"
        if silence_duration >= 0.55:
            return "候选气口"
        return "语气停顿"
    if mode == "fast":
        if silence_duration >= 0.38:
            return "剪辑气口"
        if silence_duration >= 0.22:
            return "候选气口"
        return "语气停顿"
    if silence_duration >= 0.65:
        return "剪辑气口"
    if silence_duration >= 0.35:
        return "候选气口"
    return "语气停顿"

def choose_cut_points(duration: float, silences: list[dict], settings: SplitSettings) -> list[float]:
    if duration <= 0:
        return []
    if settings.mode == "slow":
        return choose_slow_cuts(duration, silences, settings)
    if settings.mode == "fast":
        return choose_fast_cuts(duration, silences, settings)
    return choose_knowledge_cuts(duration, silences, settings)

def choose_slow_cuts(duration: float, silences: list[dict], settings: SplitSettings) -> list[float]:
    cuts = []
    last = 0.0
    candidates = [s for s in silences if s["type"] in ["剪辑气口", "候选气口"]]
    for pause in candidates:
        seg_len = pause["mid"] - last
        remaining = duration - pause["mid"]
        if seg_len < settings.min_segment:
            continue
        if pause["type"] == "剪辑气口":
            cuts.append(pause["mid"])
            last = pause["mid"]
        elif seg_len >= settings.max_segment * 1.15 and remaining >= settings.min_segment:
            cuts.append(pause["mid"])
            last = pause["mid"]
    return review_cuts(duration, cuts, settings, silences)

def choose_knowledge_cuts(duration: float, silences: list[dict], settings: SplitSettings) -> list[float]:
    cuts = []
    last = 0.0
    candidates = [s for s in silences if s["type"] in ["剪辑气口", "候选气口"]]
    while last + settings.max_segment < duration:
        window = [s for s in candidates if last + settings.min_segment <= s["mid"] <= min(last + settings.max_segment, duration - 0.2)]
        if window:
            best = max(window, key=lambda s: (s["type"] == "剪辑气口", s["duration"], s["mid"]))
            cut = best["mid"]
        else:
            strong_later = [s for s in candidates if last + settings.min_segment <= s["mid"] <= min(last + settings.max_segment * 1.25, duration - 0.2)]
            if not strong_later:
                break
            cut = strong_later[-1]["mid"]
        cuts.append(cut)
        last = cut
    return review_cuts(duration, cuts, settings, silences)

def choose_fast_cuts(duration: float, silences: list[dict], settings: SplitSettings) -> list[float]:
    cuts = []
    last = 0.0
    candidates = [s for s in silences if s["type"] != "语气停顿"]
    while last + settings.max_segment < duration:
        window = [s for s in candidates if last + settings.min_segment <= s["mid"] <= min(last + settings.max_segment, duration - 0.15)]
        if window:
            best = max(window, key=lambda s: (s["duration"], s["mid"]))
            cut = best["mid"]
        else:
            cut = min(last + settings.max_segment, duration)
        if cut <= last + 0.2:
            break
        cuts.append(cut)
        last = cut
    return review_cuts(duration, cuts, settings, silences)

def review_cuts(duration: float, cuts: list[float], settings: SplitSettings, silences: list[dict]) -> list[float]:
    reviewed = []
    last = 0.0
    for cut in sorted(cuts):
        if cut - last < settings.min_segment:
            continue
        if duration - cut < settings.min_segment:
            continue
        pause = nearest_pause(cut, silences)
        if settings.mode == "slow" and pause and pause["type"] == "语气停顿":
            continue
        reviewed.append(round(cut, 3))
        last = cut
    return reviewed

def nearest_pause(cut: float, silences: list[dict]) -> dict | None:
    if not silences:
        return None
    nearest = min(silences, key=lambda s: abs(s["mid"] - cut))
    return nearest if abs(nearest["mid"] - cut) <= 0.25 else None

def build_segments(input_path: str, script: str, settings: SplitSettings) -> dict:
    duration = get_duration(input_path)
    silences = detect_silences(input_path, settings)
    cuts = choose_cut_points(duration, silences, settings)
    points = [0.0] + cuts + [duration]
    parts = split_script(script)
    segments = []
    for index in range(len(points) - 1):
        start = points[index]
        end = points[index + 1]
        if end - start < 0.15:
            continue
        pause = nearest_pause(end, silences) if index < len(points) - 2 else None
        segments.append({
            "id": len(segments) + 1,
            "start": round(start, 3),
            "end": round(end, 3),
            "text": parts[index] if index < len(parts) else f"片段 {len(segments) + 1}",
            "confidence": pause["type"] if pause else ("AI剪辑审核保留长段" if settings.mode == "slow" else "自动切分"),
        })
    return {"duration": round(duration, 3), "silences": silences, "cuts": cuts, "segments": segments, "review_mode": settings.mode}

def write_segments_json(output_dir: str, payload: dict) -> str:
    target = Path(output_dir) / "segments.json"
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return str(target)

def srt_time(seconds: float) -> str:
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int((seconds - math.floor(seconds)) * 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

def write_srt(output_dir: str, segments: list[dict]) -> str:
    lines = []
    for index, seg in enumerate(segments, start=1):
        lines.append(str(index))
        lines.append(f"{srt_time(seg['start'])} --> {srt_time(seg['end'])}")
        lines.append(seg.get("text") or f"片段 {index}")
        lines.append("")
    target = Path(output_dir) / "segments.srt"
    target.write_text("\n".join(lines), encoding="utf-8")
    return str(target)
