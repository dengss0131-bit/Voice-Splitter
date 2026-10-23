from dataclasses import dataclass
from pathlib import Path
import json
import subprocess
import uuid

@dataclass
class PauseSettings:
    silence_ms: int = 180
    silence_db: int = -35
    style: str = "natural"

STYLE_TARGETS = {
    "short": {"micro": 0.22, "phrase": 0.38, "sentence": 0.62, "paragraph": 0.9},
    "natural": {"micro": 0.25, "phrase": 0.55, "sentence": 0.9, "paragraph": 1.3},
    "slow": {"micro": 0.35, "phrase": 0.8, "sentence": 1.25, "paragraph": 1.8},
}

def get_duration(input_path: str) -> float:
    cmd = ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "json", input_path]
    result = subprocess.run(cmd, check=True, capture_output=True, text=True)
    return float(json.loads(result.stdout)["format"]["duration"])

def detect_pauses(input_path: str, settings: PauseSettings) -> list[dict]:
    cmd = [
        "ffmpeg", "-hide_banner", "-nostats", "-i", input_path,
        "-af", f"silencedetect=noise={settings.silence_db}dB:d={settings.silence_ms / 1000}",
        "-f", "null", "-",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    pauses = []
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
                original = max(0, end - current)
                kind = classify_pause(original, settings.style)
                suggested = suggest_duration(original, kind, settings.style)
                pauses.append({
                    "id": len(pauses) + 1,
                    "start": round(current, 3),
                    "end": round(end, 3),
                    "position": round((current + end) / 2, 3),
                    "original_duration": round(original, 3),
                    "target_duration": round(suggested, 3),
                    "kind": kind,
                    "action": "加长" if suggested > original + 0.03 else ("缩短" if suggested < original - 0.03 else "保留"),
                })
            except ValueError:
                pass
            current = None
    return pauses

def classify_pause(duration: float, style: str = "natural") -> str:
    if style == "short":
        if duration < 0.22:
            return "微停顿"
        if duration < 0.48:
            return "短语停顿"
        if duration < 0.9:
            return "句尾停顿"
        return "段落停顿"
    if duration < 0.28:
        return "微停顿"
    if duration < 0.6:
        return "短语停顿"
    if duration < 1.05:
        return "句尾停顿"
    return "段落停顿"

def suggest_duration(original: float, kind: str, style: str) -> float:
    key = {"微停顿": "micro", "短语停顿": "phrase", "句尾停顿": "sentence", "段落停顿": "paragraph"}[kind]
    targets = STYLE_TARGETS.get(style, STYLE_TARGETS["natural"])
    target = targets[key]
    if style == "short":
        if kind == "微停顿":
            target = max(original, target)
        else:
            target = max(original, target)
        return max(0.1, min(target, 1.2))
    if kind == "微停顿" and style != "slow":
        target = min(target, max(original, 0.16))
    return max(0.08, min(target, 3.0))

def analyze_pauses(input_path: str, settings: PauseSettings) -> dict:
    duration = get_duration(input_path)
    pauses = detect_pauses(input_path, settings)
    if settings.style == "short":
        pauses = refine_short_video_pauses(pauses)
    return {"duration": round(duration, 3), "pauses": pauses, "style": settings.style}

def refine_short_video_pauses(pauses: list[dict]) -> list[dict]:
    if not pauses:
        return pauses
    refined = []
    for pause in pauses:
        if refined and pause["start"] - refined[-1]["end"] < 0.18:
            prev = refined[-1]
            merged_original = pause["end"] - prev["start"]
            prev["end"] = pause["end"]
            prev["position"] = round((prev["start"] + prev["end"]) / 2, 3)
            prev["original_duration"] = round(merged_original, 3)
            prev["kind"] = classify_pause(merged_original, "short")
            prev["target_duration"] = round(suggest_duration(merged_original, prev["kind"], "short"), 3)
            prev["action"] = "加长" if prev["target_duration"] > prev["original_duration"] + 0.03 else "保留"
        else:
            refined.append(dict(pause))
    for index, pause in enumerate(refined, start=1):
        pause["id"] = index
    return refined

def render_with_pauses(input_path: str, output_dir: str, pauses: list[dict]) -> dict:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    work = output / "parts"
    work.mkdir(parents=True, exist_ok=True)
    duration = get_duration(input_path)
    concat_items = []
    cursor = 0.0
    part_index = 1
    for pause in sorted(pauses, key=lambda p: float(p["start"])):
        start = float(pause["start"])
        end = float(pause["end"])
        target = max(0.02, float(pause.get("target_duration", end - start)))
        if start > cursor + 0.01:
            audio_part = work / f"{part_index:04d}_audio.wav"
            extract_audio(input_path, str(audio_part), cursor, start - cursor)
            concat_items.append(audio_part)
            part_index += 1
        silence_part = work / f"{part_index:04d}_silence.wav"
        create_silence(str(silence_part), target)
        concat_items.append(silence_part)
        part_index += 1
        cursor = end
    if cursor < duration - 0.01:
        audio_part = work / f"{part_index:04d}_audio.wav"
        extract_audio(input_path, str(audio_part), cursor, duration - cursor)
        concat_items.append(audio_part)
    list_file = output / "concat.txt"
    list_file.write_text("\n".join([f"file '{str(p).replace(chr(92), '/')}'" for p in concat_items]), encoding="utf-8")
    final = output / "edited_voice.wav"
    cmd = ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(list_file), "-c", "copy", str(final)]
    subprocess.run(cmd, check=True, capture_output=True, text=True)
    metadata = {"output_audio": str(final), "pauses": pauses}
    (output / "pause_plan.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    return metadata

def extract_audio(input_path: str, output_path: str, start: float, duration: float) -> None:
    cmd = ["ffmpeg", "-y", "-i", input_path, "-ss", str(start), "-t", str(max(duration, 0.01)), "-ac", "1", "-ar", "44100", "-acodec", "pcm_s16le", output_path]
    subprocess.run(cmd, check=True, capture_output=True, text=True)

def create_silence(output_path: str, duration: float) -> None:
    cmd = ["ffmpeg", "-y", "-f", "lavfi", "-i", f"anullsrc=r=44100:cl=mono", "-t", str(max(duration, 0.02)), "-acodec", "pcm_s16le", output_path]
    subprocess.run(cmd, check=True, capture_output=True, text=True)
