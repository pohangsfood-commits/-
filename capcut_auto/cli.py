"""capcut_auto 커맨드라인 인터페이스.

사용 예:
    python -m capcut_auto analyze video.mp4 -o work
    python -m capcut_auto build work --video video.mp4 --draft-name my_edit
    python -m capcut_auto run video.mp4 --draft-name my_edit
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import audio, draft_writer, report, stutter, subtitles, transcribe
from .config import Config
from .cutlist import CutRegion, build_cut_regions, build_keep_segments
from .drafts_dir import default_drafts_dir
from .remap import TimelineMapper
from .transcribe import Word


def _add_config_args(parser: argparse.ArgumentParser) -> None:
    defaults = Config()
    g = parser.add_argument_group("탐지/컷 옵션")
    g.add_argument("--min-silence", type=float, default=defaults.min_silence)
    g.add_argument("--silence-noise-db", type=float, default=defaults.silence_noise_db)
    g.add_argument("--silence-pad", type=float, default=defaults.silence_pad)
    g.add_argument("--repeat-gap", type=float, default=defaults.repeat_gap)
    g.add_argument("--hesitation-gap", type=float, default=defaults.hesitation_gap)
    g.add_argument("--filler-words", type=str, default="", help="쉼표로 구분된 제거할 추임새 목록 (예: '음,어,그니까')")
    g.add_argument("--min-gap-between-cuts", type=float, default=defaults.min_gap_between_cuts)
    g.add_argument("--min-keep", type=float, default=defaults.min_keep)
    g.add_argument("--max-chars", type=int, default=defaults.max_chars)
    g.add_argument("--max-line-seconds", type=float, default=defaults.max_line_seconds)
    g.add_argument("--whisper-model", type=str, default=defaults.whisper_model)
    g.add_argument("--device", dest="whisper_device", type=str, default=defaults.whisper_device, choices=["auto", "cpu", "cuda"])
    g.add_argument("--language", dest="whisper_language", type=str, default=defaults.whisper_language)


def _config_from_args(args: argparse.Namespace) -> Config:
    filler = tuple(w.strip() for w in args.filler_words.split(",") if w.strip())
    return Config(
        min_silence=args.min_silence,
        silence_noise_db=args.silence_noise_db,
        silence_pad=args.silence_pad,
        repeat_gap=args.repeat_gap,
        hesitation_gap=args.hesitation_gap,
        filler_words=filler,
        min_gap_between_cuts=args.min_gap_between_cuts,
        min_keep=args.min_keep,
        max_chars=args.max_chars,
        max_line_seconds=args.max_line_seconds,
        whisper_model=args.whisper_model,
        whisper_device=args.whisper_device,
        whisper_language=args.whisper_language,
    )


def _run_analyze(video_path: str, out_dir: str, config: Config) -> None:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    print(f"[1/5] 영상 정보 확인 중... ({video_path})")
    duration = audio.probe_duration(video_path)

    print("[2/5] 오디오 추출 및 무음 구간 탐지 중...")
    wav_path = str(out / "audio.wav")
    audio.extract_audio(video_path, wav_path)
    silence = audio.detect_silence(
        wav_path,
        noise_db=config.silence_noise_db,
        min_duration=config.min_silence,
        total_duration=duration,
    )
    print(f"       무음 구간 {len(silence)}개 발견")

    print(f"[3/5] 한국어 음성 인식 중... (모델: {config.whisper_model}, device: {config.whisper_device})")
    words = transcribe.transcribe(
        wav_path,
        model_size=config.whisper_model,
        device=config.whisper_device,
        language=config.whisper_language,
    )
    print(f"       단어 {len(words)}개 인식")

    print("[4/5] 버벅임(반복/머뭇거림) 탐지 중...")
    stutter_candidates = stutter.find_stutters(words, config)
    print(f"       버벅임 후보 {len(stutter_candidates)}개 발견")

    cuts = build_cut_regions(silence, stutter_candidates, duration, config)
    print(f"[5/5] 컷 리스트 {len(cuts)}개 구간으로 병합 완료")

    keeps = build_keep_segments(cuts, duration, config)

    (out / "meta.json").write_text(
        json.dumps({"video": str(Path(video_path).resolve()), "duration": duration}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (out / "transcript.json").write_text(
        json.dumps([w.to_dict() for w in words], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (out / "cutlist.json").write_text(
        json.dumps([c.to_dict() for c in cuts], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    preview_cues = subtitles.words_to_cues(words, config, mapper=None)
    subtitles.write_srt(preview_cues, str(out / "preview.srt"))

    report_text = report.build_report(video_path=video_path, duration=duration, cuts=cuts, keeps=keeps)
    (out / "report.md").write_text(report_text, encoding="utf-8")

    print()
    print(f"분석 완료 → {out}/report.md 를 확인해주세요.")
    print(f"필요하면 {out}/cutlist.json 을 직접 수정한 뒤 build 명령을 실행하세요.")


def _run_build(
    work_dir: str,
    video_path: str | None,
    draft_name: str,
    drafts_dir: str | None,
    config: Config,
    allow_replace: bool,
) -> None:
    work = Path(work_dir)
    meta = json.loads((work / "meta.json").read_text(encoding="utf-8"))
    video_path = video_path or meta["video"]
    duration = meta["duration"]

    words = [Word(**w) for w in json.loads((work / "transcript.json").read_text(encoding="utf-8"))]
    cuts = [CutRegion.from_dict(c) for c in json.loads((work / "cutlist.json").read_text(encoding="utf-8"))]

    keeps = build_keep_segments(cuts, duration, config)
    if not keeps:
        print("오류: 남는 구간이 없습니다. cutlist.json 또는 임계값을 조정해주세요.", file=sys.stderr)
        sys.exit(1)

    mapper = TimelineMapper(keeps)
    cues = subtitles.words_to_cues(words, config, mapper=mapper)
    srt_path = str(work / "final.srt")
    subtitles.write_srt(cues, srt_path)

    resolved_drafts_dir = Path(drafts_dir) if drafts_dir else default_drafts_dir()
    if resolved_drafts_dir is None:
        print(
            "오류: CapCut draft 폴더를 자동으로 찾지 못했습니다. --drafts-dir 옵션으로 직접 지정해주세요.",
            file=sys.stderr,
        )
        sys.exit(1)

    width, height, fps = audio.probe_video_info(video_path)

    print(f"CapCut draft 생성 중... ({resolved_drafts_dir / draft_name})")
    result_path = draft_writer.write_capcut_draft(
        video_path,
        keeps,
        srt_path,
        str(resolved_drafts_dir),
        draft_name,
        width=width,
        height=height,
        fps=round(fps),
        allow_replace=allow_replace,
    )
    print(f"완료! CapCut을 열고 '{draft_name}' 프로젝트를 선택하세요.")
    print(f"  경로: {result_path}")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="capcut_auto", description="버벅임/무음 자동 컷 + 자막 → CapCut draft 생성")
    sub = parser.add_subparsers(dest="command", required=True)

    p_analyze = sub.add_parser("analyze", help="영상을 분석해 cutlist/transcript/report를 생성 (draft는 만들지 않음)")
    p_analyze.add_argument("video", help="입력 영상 파일 경로")
    p_analyze.add_argument("-o", "--out", required=True, help="분석 결과를 저장할 폴더")
    _add_config_args(p_analyze)

    p_build = sub.add_parser("build", help="analyze 결과로 CapCut draft를 생성")
    p_build.add_argument("work_dir", help="analyze 명령으로 만든 폴더")
    p_build.add_argument("--video", default=None, help="원본 영상 경로 (기본: meta.json에 저장된 경로)")
    p_build.add_argument("--draft-name", required=True, help="CapCut에 생성할 프로젝트 이름")
    p_build.add_argument("--drafts-dir", default=None, help="CapCut draft 폴더 경로 (기본: OS별 자동 탐지)")
    p_build.add_argument("--allow-replace", action="store_true", help="같은 이름의 draft가 있으면 덮어쓰기")
    _add_config_args(p_build)

    p_run = sub.add_parser("run", help="analyze + build를 한 번에 실행")
    p_run.add_argument("video", help="입력 영상 파일 경로")
    p_run.add_argument("--draft-name", required=True, help="CapCut에 생성할 프로젝트 이름")
    p_run.add_argument("--drafts-dir", default=None, help="CapCut draft 폴더 경로 (기본: OS별 자동 탐지)")
    p_run.add_argument("--work-dir", default=None, help="중간 결과 저장 폴더 (기본: <영상이름>_work)")
    p_run.add_argument("--allow-replace", action="store_true", help="같은 이름의 draft가 있으면 덮어쓰기")
    _add_config_args(p_run)

    args = parser.parse_args(argv)
    config = _config_from_args(args)

    if args.command == "analyze":
        _run_analyze(args.video, args.out, config)
    elif args.command == "build":
        _run_build(args.work_dir, args.video, args.draft_name, args.drafts_dir, config, args.allow_replace)
    elif args.command == "run":
        work_dir = args.work_dir or f"{Path(args.video).stem}_work"
        _run_analyze(args.video, work_dir, config)
        _run_build(work_dir, args.video, args.draft_name, args.drafts_dir, config, args.allow_replace)


if __name__ == "__main__":
    main()
