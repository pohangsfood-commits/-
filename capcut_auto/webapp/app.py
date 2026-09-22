"""로컬에서 실행하는 CapCut 자동 컷편집 웹 UI.

실행: python -m capcut_auto.webapp
브라우저에서 http://127.0.0.1:8765 로 접속.

CapCut/ffmpeg/Whisper가 모두 이 서버를 실행하는 컴퓨터에 있어야 하므로,
반드시 사용자 본인의 PC/Mac에서 실행해야 한다 (외부에 배포하는 용도가 아님).
"""

from __future__ import annotations

import webbrowser
from pathlib import Path
from threading import Timer

from flask import Flask, jsonify, request, send_from_directory

from ..config import Config
from ..drafts_dir import default_drafts_dir
from .jobs import manager

STATIC_DIR = Path(__file__).parent / "static"

app = Flask(__name__, static_folder=None)


@app.get("/")
def index():
    return send_from_directory(STATIC_DIR, "index.html")


@app.get("/static/<path:filename>")
def static_files(filename: str):
    return send_from_directory(STATIC_DIR, filename)


@app.get("/api/defaults")
def api_defaults():
    drafts_dir = default_drafts_dir()
    return jsonify({"config": Config().to_dict(), "drafts_dir": str(drafts_dir) if drafts_dir else None})


@app.post("/api/upload")
def api_upload():
    if "file" not in request.files:
        return jsonify({"error": "file 필드가 필요합니다"}), 400
    upload = request.files["file"]
    if not upload.filename:
        return jsonify({"error": "파일이 비어있습니다"}), 400

    job = manager.create_job(upload.stream, upload.filename)
    return jsonify({"job_id": job.id, "original_filename": job.original_filename})


@app.get("/api/jobs/<job_id>")
def api_job_status(job_id: str):
    job = manager.get(job_id)
    if job is None:
        return jsonify({"error": "존재하지 않는 작업입니다"}), 404
    return jsonify(job.to_status_dict())


@app.post("/api/jobs/<job_id>/analyze")
def api_job_analyze(job_id: str):
    job = manager.get(job_id)
    if job is None:
        return jsonify({"error": "존재하지 않는 작업입니다"}), 404
    if job.status in ("analyzing", "building"):
        return jsonify({"error": "이미 처리 중입니다"}), 409

    body = request.get_json(silent=True) or {}
    config = Config.from_dict(body)
    manager.start_analyze(job, config)
    return jsonify({"status": "started"})


@app.post("/api/jobs/<job_id>/cutlist")
def api_job_cutlist(job_id: str):
    job = manager.get(job_id)
    if job is None:
        return jsonify({"error": "존재하지 않는 작업입니다"}), 404
    if job.status not in ("analyzed", "done", "error"):
        return jsonify({"error": "분석이 아직 끝나지 않았습니다"}), 409

    body = request.get_json(silent=True) or {}
    cuts = body.get("cuts")
    if cuts is None:
        return jsonify({"error": "cuts 필드가 필요합니다"}), 400

    manager.update_cutlist(job, cuts)
    return jsonify(job.to_status_dict())


@app.post("/api/jobs/<job_id>/build")
def api_job_build(job_id: str):
    job = manager.get(job_id)
    if job is None:
        return jsonify({"error": "존재하지 않는 작업입니다"}), 404
    if job.status not in ("analyzed", "done", "error"):
        return jsonify({"error": "먼저 분석을 완료해주세요"}), 409

    body = request.get_json(silent=True) or {}
    draft_name = (body.get("draft_name") or "").strip()
    if not draft_name:
        return jsonify({"error": "draft_name이 필요합니다"}), 400
    drafts_dir = (body.get("drafts_dir") or "").strip() or None
    allow_replace = bool(body.get("allow_replace", False))

    manager.start_build(job, draft_name, drafts_dir, allow_replace)
    return jsonify({"status": "started"})


def main() -> None:
    port = 8765
    url = f"http://127.0.0.1:{port}"
    print(f"CapCut 자동화 웹 UI 시작: {url}")
    print("이 창을 닫지 말고 브라우저에서 접속하세요. 종료하려면 Ctrl+C를 누르세요.")
    Timer(0.8, lambda: webbrowser.open(url)).start()
    app.run(host="127.0.0.1", port=port, debug=False)


if __name__ == "__main__":
    main()
