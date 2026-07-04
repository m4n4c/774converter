"""774converter(名無しコンバーター)のローカルWebサーバー。

起動:  .venv/bin/uvicorn app:app --port 8756
ブラウザで http://localhost:8756 を開く。外部への通信は一切行わない。
"""

from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel

import anonymizer
import detector
import extractor

app = FastAPI(title="774converter")

STATIC_DIR = Path(__file__).parent / "static"


class TextIn(BaseModel):
    text: str


class AnonymizeIn(BaseModel):
    text: str
    items: list[dict]  # [{"surface", "type"}]
    title: str = ""


class RestoreIn(BaseModel):
    text: str
    items: list[dict]  # [{"label", "original"}]


@app.get("/")
def index():
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/health")
def health():
    return {"ok": True, "ginza": detector.ginza_available()}


@app.post("/api/extract")
async def extract(file: UploadFile = File(...)):
    """添付ファイル(.docx / .xlsx / .pdf / テキスト系)からテキストを取り出す。"""
    from pathlib import PurePosixPath

    ext = PurePosixPath(file.filename or "").suffix.lower()
    if ext and ext not in extractor.SUPPORTED_EXTENSIONS:
        raise HTTPException(400, f"未対応のファイル形式です: {ext}")
    data = await file.read()
    try:
        text = extractor.extract_text(file.filename or "", data)
    except Exception:
        raise HTTPException(400, "ファイルの読み込みに失敗しました")
    return {"text": text, "filename": file.filename}


@app.post("/api/detect")
def detect(body: TextIn):
    return {"items": detector.detect(body.text)}


@app.post("/api/anonymize")
def anonymize(body: AnonymizeIn):
    mapping = anonymizer.build_mapping(body.text, body.items)
    result = anonymizer.anonymize(body.text, mapping)
    saved = anonymizer.save_mapping(mapping, body.title) if mapping else None
    return {"text": result, "mapping": mapping, "saved_as": saved}


@app.post("/api/restore")
def restore(body: RestoreIn):
    return {"text": anonymizer.restore(body.text, body.items)}


@app.get("/api/mappings")
def mappings():
    return {"mappings": anonymizer.list_mappings()}


@app.get("/api/mappings/{name}")
def mapping_detail(name: str):
    try:
        return {"items": anonymizer.load_mapping(name)}
    except ValueError:
        raise HTTPException(400, "invalid name")
    except FileNotFoundError:
        raise HTTPException(404, "not found")
