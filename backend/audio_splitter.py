from pathlib import Path
import subprocess

def split_audio(input_path: str, output_dir: str, segments: list[dict]) -> list[str]:
    """Split audio with ffmpeg. This is prepared for the next integration step."""
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    outputs = []
    for segment in segments:
        index = int(segment["id"])
        start = float(segment["start"])
        end = float(segment["end"])
        duration = max(0.01, end - start)
        output = Path(output_dir) / f"{index:03d}.wav"
        cmd = [
            "ffmpeg",
            "-y",
            "-i",
            input_path,
            "-ss",
            str(start),
            "-t",
            str(duration),
            "-acodec",
            "pcm_s16le",
            str(output),
        ]
        subprocess.run(cmd, check=True, capture_output=True)
        outputs.append(str(output))
    return outputs
