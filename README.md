# CapCut 자동 컷편집 + 자막 도구

말하다가 버벅이거나 멈추는 구간, 무음(침묵) 구간을 자동으로 찾아 잘라내고,
한국어 음성인식으로 자막까지 자동 생성해서 **CapCut에서 바로 열어 이어서 편집**할 수 있는
CapCut 프로젝트(draft)를 만들어주는 파이썬 도구입니다.

영상 자체를 렌더링해서 넘기는 방식이 아니라, CapCut이 이해하는 프로젝트 파일
(`draft_content.json`)을 생성합니다. 그래서 CapCut을 열면 컷 편집과 자막이 이미 타임라인에
올라가 있는 상태로 시작하고, 이펙트·색보정·트랜지션 같은 마무리 작업은 평소처럼 CapCut에서
하시면 됩니다.

> 이 저장소는 CapCut이 설치되어 있는 **내 PC/Mac에서 실행**하는 용도입니다.
> (클라우드 컨테이너에는 CapCut이 없으므로 여기서는 직접 실행/검증하지 않았습니다 — 아래
> "동작 확인 방법"을 참고해 로컬에서 검증해주세요.)

## 동작 원리 (파이프라인)

1. **오디오 추출 + 무음 구간 탐지** — `ffmpeg silencedetect`로 지정한 데시벨/길이 기준보다
   조용한 구간을 찾습니다. (`audio.py`)
2. **한국어 음성인식** — `faster-whisper`로 단어 단위 타임스탬프까지 포함해 전사합니다.
   (`transcribe.py`)
3. **버벅임(더듬는 구간) 탐지** — 같은 단어가 짧은 간격으로 반복되는 구간("그 그 그거는"),
   문장 중간의 비정상적으로 긴 머뭇거림을 찾아냅니다. (`stutter.py`)
4. **컷 리스트 생성** — 무음 구간 + 버벅임 구간을 합치고, 패딩을 적용해 최종적으로 잘라낼
   구간(cutlist)과 남길 구간(keep segments)을 계산합니다. (`cutlist.py`)
5. **자막 재동기화** — 잘라낸 구간에 걸친 단어는 제거하고, 남은 구간을 기준으로 자막
   타임스탬프를 새 타임라인에 맞게 다시 계산해 SRT를 만듭니다. (`subtitles.py`)
6. **CapCut 프로젝트 생성** — [`pycapcut`](https://github.com/GuanYixuan/pyCapCut) 라이브러리로
   남길 구간들을 순서대로 이어붙인 비디오 트랙과, 재동기화된 자막 트랙을 가진 CapCut draft를
   생성합니다. (`draft_writer.py`)

버벅임/무음 탐지는 완벽하지 않을 수 있기 때문에, **기본 워크플로는 2단계(analyze → build)** 로
나뉘어 있어서 CapCut에 반영하기 전에 무엇을 잘랐는지 검토하고 필요하면 수정할 수 있습니다.
바로 한 번에 처리하고 싶다면 `run` 명령을 쓰면 됩니다.

## 설치

- Python 3.9 이상
- [ffmpeg](https://ffmpeg.org/download.html) (PATH에 등록되어 `ffmpeg`, `ffprobe` 명령이
  실행되어야 합니다)
- CapCut 데스크톱 앱

```bash
pip install -r requirements.txt
```

GPU가 있으면 `faster-whisper`가 자동으로 활용하며(CUDA), 없으면 CPU로도 동작합니다(느릴 수
있음). 처음 실행 시 Whisper 모델 가중치를 자동으로 내려받습니다.

## 웹 UI로 사용하기 (권장)

브라우저에서 영상을 업로드하고, 컷 리스트를 체크박스로 검토/수정한 뒤 CapCut draft를
만들 수 있는 로컬 웹 UI가 포함되어 있습니다.

```bash
python -m capcut_auto.webapp
```

브라우저가 자동으로 열리며 `http://127.0.0.1:8765` 로 접속됩니다(안 열리면 직접 접속).
서버는 이 명령을 실행한 컴퓨터에서만 접속 가능하며(외부 공개 아님), **CapCut이 설치된
바로 그 PC/Mac에서 실행해야** 업로드한 영상과 생성된 draft를 CapCut이 정상적으로 찾을 수
있습니다. 종료하려면 터미널에서 `Ctrl+C`를 누르세요.

사용 흐름:

1. 영상을 드래그 앤 드롭(또는 클릭해서 선택)해서 업로드
2. 필요하면 "고급 옵션"에서 임계값을 조정하고 **분석 시작**
3. 분석이 끝나면 컷 리스트 표에서 원치 않는 구간의 체크를 해제해 제외 (체크 해제 = 자르지
   않고 남김), **다시 계산**으로 결과 미리보기 갱신
4. 프로젝트 이름을 입력하고 **CapCut Draft 만들기** 클릭 → 완료되면 CapCut에서 해당
   프로젝트를 열면 됩니다

업로드한 영상 원본은 `~/.capcut_auto/webapp/jobs/<작업ID>/source.*` 에 보관되며, 생성된
draft가 이 파일을 참조하므로 **CapCut에서 편집을 마칠 때까지 이 폴더를 지우지 마세요.**

같은 파이프라인을 커맨드라인에서 스크립팅하고 싶다면 아래 CLI를 사용하세요.

## CLI 사용법

### 1) 분석만 하기 (권장 — 먼저 결과를 확인)

```bash
python -m capcut_auto analyze "내영상.mp4" -o ./work
```

`./work` 폴더에 다음이 생성됩니다.

- `transcript.json` — 단어 단위 인식 결과
- `cutlist.json` — 잘라낼 구간 목록 (이유: `silence` / `stutter`, 시작/끝 시간, 신뢰도)
- `preview.srt` — 원본(컷 편집 전) 타임라인 기준 자막 — 인식이 잘 되었는지 확인용
- `report.md` — 사람이 읽기 쉬운 요약 (전체 길이, 잘려나가는 시간, 구간 목록)

`cutlist.json`을 열어 원치 않는 항목을 지우거나 시간을 조정할 수 있습니다.

### 2) CapCut 프로젝트로 빌드

```bash
python -m capcut_auto build ./work --video "내영상.mp4" \
  --draft-name "내영상_자동컷" \
  --drafts-dir "C:\Users\사용자이름\AppData\Local\CapCut\User Data\Projects\com.lveditor.draft"
```

`--drafts-dir`를 생략하면 OS별 기본 CapCut draft 폴더를 자동으로 사용합니다
(Windows: `%LOCALAPPDATA%\CapCut\User Data\Projects\com.lveditor.draft`,
macOS: `~/Movies/CapCut/User Data/Projects/com.lveditor.draft`). 실제 경로는 CapCut의
설정 > 환경설정 > draft 저장 위치에서 확인할 수 있습니다.

빌드가 끝나면 CapCut을 열고 프로젝트 목록에서 `내영상_자동컷`을 선택하면 됩니다.

### 3) 한 번에 처리 (분석 + 빌드)

검토 없이 바로 처리하고 싶다면:

```bash
python -m capcut_auto run "내영상.mp4" --draft-name "내영상_자동컷"
```

## 주요 옵션

| 옵션 | 기본값 | 설명 |
|---|---|---|
| `--min-silence` | `0.7` | 이 길이(초) 이상 조용해야 무음 구간으로 인정 |
| `--silence-noise-db` | `-30` | 이 값보다 조용하면 무음으로 판단 (dB) |
| `--silence-pad` | `0.12` | 무음 구간 잘라낼 때 앞뒤로 남겨둘 여유(초), 말이 뚝 끊기는 느낌 방지 |
| `--repeat-gap` | `0.5` | 이 간격(초) 이내에 같은 단어가 반복되면 버벅임으로 간주 |
| `--hesitation-gap` | `0.8` | 문장 중간 단어 사이 간격이 이 값(초)보다 크면 머뭇거림으로 간주 |
| `--min-keep` | `0.3` | 컷 후 남는 조각이 이 길이(초)보다 짧으면 앞/뒤 구간에 합쳐서 지나치게 잘게 쪼개지지 않게 함 |
| `--whisper-model` | `large-v3` | faster-whisper 모델 크기 (`small`/`medium`/`large-v3` 등) |
| `--device` | `auto` | `cpu` / `cuda` / `auto` |
| `--max-chars` | `24` | 자막 한 줄 최대 글자수 (한국어 기준 대략치) |

## 동작 확인 방법 (로컬에서 꼭 해보세요)

이 코드는 CapCut/ffmpeg/GPU가 없는 클라우드 환경에서 작성되어, `cutlist.py` 등 순수
파이썬 로직은 `tests/`의 단위 테스트로 검증했고 웹 UI/CLI의 요청 흐름(업로드→분석→컷
리스트 수정→draft 생성)도 ffmpeg/Whisper/pycapcut을 스텁으로 대체해 엔드투엔드로
검증했지만, **실제 ffmpeg 무음 탐지, Whisper 인식 품질, 그리고 생성된 CapCut draft가
CapCut 앱에서 정상적으로 열리는지는 로컬 환경에서 직접 확인이 필요합니다.**

1. `pip install -r requirements.txt` 후 `python -m capcut_auto.webapp` 실행 → 브라우저에서
   샘플 영상을 업로드해 분석 결과(컷 리스트, 자막 미리보기)가 그럴듯한지 확인
2. **CapCut Draft 만들기**로 draft 생성 → CapCut 실행 → 프로젝트가 열리는지, 컷과 자막이
   맞게 배치됐는지 확인
3. 문제가 있으면 이슈로 남겨주시면 로직을 조정하겠습니다 (특히 `--silence-noise-db`,
   `--repeat-gap`, `--hesitation-gap`은 영상/목소리 특성에 따라 튜닝이 필요할 수 있습니다).

## 알려진 한계

- CapCut 6.x 이상은 draft 파일을 암호화하는 버전이 있어 일부 기존 프로젝트를
  **템플릿으로 불러와 수정**하는 기능은 제한될 수 있습니다. 이 도구는 항상 **새 draft를
  생성**하므로 이 문제의 영향을 받지 않습니다.
- 버벅임 탐지는 "동일 단어의 짧은 간격 반복"과 "문장 중간의 비정상적으로 긴 침묵"만
  탐지하는 보수적인 휴리스틱입니다. 추임새(예: "음", "어", "그니까")까지 자동으로 지우고
  싶다면 `--filler-words` 옵션으로 직접 제거할 단어 목록을 지정하세요 (기본은 비활성화 —
  의미 있는 단어까지 잘못 지워질 위험이 있기 때문입니다).
- 자막은 Whisper 인식 결과를 그대로 사용하므로 고유명사/전문용어는 오탈자가 있을 수
  있습니다. CapCut에서 자막 트랙을 최종 검수하시길 권장합니다.
