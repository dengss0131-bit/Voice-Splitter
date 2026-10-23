from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from pathlib import Path
import shutil
import uuid

from audio_analyzer import SplitSettings, build_segments, write_segments_json, write_srt
from audio_splitter import split_audio
from pause_editor import PauseSettings, analyze_pauses, render_with_pauses

BASE_DIR = Path(__file__).resolve().parents[1]
WORKSPACE = BASE_DIR / "workspace"
UPLOADS = WORKSPACE / "uploads"
OUTPUTS = WORKSPACE / "outputs"

app = FastAPI(title="Voice Splitter API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
OUTPUTS.mkdir(parents=True, exist_ok=True)
app.mount("/outputs", StaticFiles(directory=str(OUTPUTS)), name="outputs")

class Segment(BaseModel):
    id: int
    start: float
    end: float
    text: str = ""

class AutoSplitRequest(BaseModel):
    audio_path: str
    script: str = ""
    min_segment: float = 1.2
    max_segment: float = 5.0
    silence_ms: int = 280
    silence_db: int = -35
    mode: str = "knowledge"

class ExportRequest(BaseModel):
    audio_path: str
    segments: list[Segment]

class AnalyzePausesRequest(BaseModel):
    audio_path: str
    style: str = "natural"
    silence_ms: int = 180
    silence_db: int = -35

class RenderPausesRequest(BaseModel):
    audio_path: str
    pauses: list[dict]

@app.get("/health")
def health():
    return {"ok": True, "message": "voice splitter backend is ready"}

@app.post("/upload")
def upload_audio(file: UploadFile = File(...)):
    UPLOADS.mkdir(parents=True, exist_ok=True)
    suffix = Path(file.filename or "audio.wav").suffix
    safe_name = f"{uuid.uuid4().hex}{suffix}"
    target = UPLOADS / safe_name
    with target.open("wb") as f:
        shutil.copyfileobj(file.file, f)
    return {"audio_path": str(target), "filename": file.filename}

@app.post("/analyze-pauses")
def analyze_audio_pauses(payload: AnalyzePausesRequest):
    audio_path = Path(payload.audio_path)
    if not audio_path.exists():
        return {"ok": False, "message": "音频文件不存在，请重新上传。"}
    settings = PauseSettings(style=payload.style, silence_ms=payload.silence_ms, silence_db=payload.silence_db)
    analysis = analyze_pauses(str(audio_path), settings)
    job_id = uuid.uuid4().hex[:10]
    output_dir = OUTPUTS / f"pause_auto_{job_id}"
    rendered = render_with_pauses(str(audio_path), str(output_dir), analysis["pauses"])
    return {
        "ok": True,
        **analysis,
        "job_id": job_id,
        "output_dir": str(output_dir),
        "output_audio": rendered["output_audio"],
        "download_base": f"/outputs/pause_auto_{job_id}",
        "download_url": f"/outputs/pause_auto_{job_id}/edited_voice.wav",
    }

@app.post("/render-pauses")
def render_audio_pauses(payload: RenderPausesRequest):
    audio_path = Path(payload.audio_path)
    if not audio_path.exists():
        return {"ok": False, "message": "音频文件不存在，请重新上传。"}
    job_id = uuid.uuid4().hex[:10]
    output_dir = OUTPUTS / f"pause_{job_id}"
    result = render_with_pauses(str(audio_path), str(output_dir), payload.pauses)
    return {
        "ok": True,
        "job_id": job_id,
        "output_dir": str(output_dir),
        "output_audio": result["output_audio"],
        "download_base": f"/outputs/pause_{job_id}",
        "download_url": f"/outputs/pause_{job_id}/edited_voice.wav",
    }

@app.post("/auto-split")
def auto_split(payload: AutoSplitRequest):
    audio_path = Path(payload.audio_path)
    if not audio_path.exists():
        return {"ok": False, "message": "音频文件不存在，请重新上传。"}
    job_id = uuid.uuid4().hex[:10]
    output_dir = OUTPUTS / job_id
    output_dir.mkdir(parents=True, exist_ok=True)
    settings = SplitSettings(
        min_segment=payload.min_segment,
        max_segment=payload.max_segment,
        silence_ms=payload.silence_ms,
        silence_db=payload.silence_db,
        mode=payload.mode,
    )
    analysis = build_segments(str(audio_path), payload.script, settings)
    audio_files = split_audio(str(audio_path), str(output_dir), analysis["segments"])
    analysis["audio_files"] = audio_files
    analysis["job_id"] = job_id
    json_path = write_segments_json(str(output_dir), analysis)
    srt_path = write_srt(str(output_dir), analysis["segments"])
    return {
        "ok": True,
        "job_id": job_id,
        "duration": analysis["duration"],
        "silence_count": len(analysis["silences"]),
        "cut_count": len(analysis["cuts"]),
        "segments": analysis["segments"],
        "audio_files": audio_files,
        "json_path": json_path,
        "srt_path": srt_path,
        "output_dir": str(output_dir),
        "download_base": f"/outputs/{job_id}",
    }

@app.post("/export")
def export_segments(payload: ExportRequest):
    audio_path = Path(payload.audio_path)
    if not audio_path.exists():
        return {"ok": False, "message": "音频文件不存在，请重新上传。"}
    job_id = uuid.uuid4().hex[:10]
    output_dir = OUTPUTS / job_id
    output_dir.mkdir(parents=True, exist_ok=True)
    segments = [seg.model_dump() for seg in payload.segments]
    audio_files = split_audio(str(audio_path), str(output_dir), segments)
    result = {"segments": segments, "audio_files": audio_files, "job_id": job_id}
    json_path = write_segments_json(str(output_dir), result)
    srt_path = write_srt(str(output_dir), segments)
    return {"ok": True, "job_id": job_id, "audio_files": audio_files, "json_path": json_path, "srt_path": srt_path, "output_dir": str(output_dir), "download_base": f"/outputs/{job_id}"}
