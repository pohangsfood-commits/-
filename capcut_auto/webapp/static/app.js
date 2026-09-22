const CONFIG_FIELDS = [
  { key: "min_silence", label: "최소 무음 길이(초)", type: "number", step: "0.05" },
  { key: "silence_noise_db", label: "무음 기준(dB)", type: "number", step: "1" },
  { key: "silence_pad", label: "무음 패딩(초)", type: "number", step: "0.01" },
  { key: "repeat_gap", label: "반복 판정 간격(초)", type: "number", step: "0.05" },
  { key: "hesitation_gap", label: "머뭇거림 판정 간격(초)", type: "number", step: "0.05" },
  { key: "filler_words", label: "제거할 추임새 (쉼표로 구분, 비워두면 미사용)", type: "text" },
  { key: "min_gap_between_cuts", label: "컷 병합 최소 간격(초)", type: "number", step: "0.05" },
  { key: "min_keep", label: "최소 유지 길이(초)", type: "number", step: "0.05" },
  { key: "max_chars", label: "자막 한 줄 최대 글자수", type: "number", step: "1" },
  { key: "max_line_seconds", label: "자막 한 줄 최대 노출 시간(초)", type: "number", step: "0.5" },
  { key: "whisper_model", label: "Whisper 모델", type: "select", options: ["tiny", "base", "small", "medium", "large-v3"] },
  { key: "whisper_device", label: "device", type: "select", options: ["auto", "cpu", "cuda"] },
];

const state = {
  jobId: null,
  duration: 0,
  allCuts: [],
  pollTimer: null,
};

const $ = (id) => document.getElementById(id);

function fmtTime(t) {
  const s = Math.max(0, t);
  const m = Math.floor(s / 60);
  const sec = (s % 60).toFixed(2);
  return `${String(m).padStart(2, "0")}:${sec.padStart(5, "0")}`;
}

async function loadDefaults() {
  const res = await fetch("/api/defaults");
  const data = await res.json();
  renderConfigGrid(data.config);
  if (data.drafts_dir) {
    $("drafts-dir").value = data.drafts_dir;
  }
}

function renderConfigGrid(defaults) {
  const grid = $("config-grid");
  grid.innerHTML = "";
  for (const field of CONFIG_FIELDS) {
    const wrapper = document.createElement("label");
    wrapper.textContent = field.label;
    let input;
    if (field.type === "select") {
      input = document.createElement("select");
      for (const opt of field.options) {
        const o = document.createElement("option");
        o.value = opt;
        o.textContent = opt;
        input.appendChild(o);
      }
      input.value = defaults[field.key];
    } else {
      input = document.createElement("input");
      input.type = field.type;
      if (field.step) input.step = field.step;
      input.value = Array.isArray(defaults[field.key]) ? defaults[field.key].join(",") : defaults[field.key];
    }
    input.id = `cfg-${field.key}`;
    wrapper.appendChild(input);
    grid.appendChild(wrapper);
  }
}

function collectConfig() {
  const cfg = {};
  for (const field of CONFIG_FIELDS) {
    const el = $(`cfg-${field.key}`);
    if (field.type === "number") {
      cfg[field.key] = parseFloat(el.value);
    } else {
      cfg[field.key] = el.value;
    }
  }
  return cfg;
}

function setupUpload() {
  const dropZone = $("drop-zone");
  const fileInput = $("file-input");

  dropZone.addEventListener("click", () => fileInput.click());
  dropZone.addEventListener("dragover", (e) => {
    e.preventDefault();
    dropZone.classList.add("dragover");
  });
  dropZone.addEventListener("dragleave", () => dropZone.classList.remove("dragover"));
  dropZone.addEventListener("drop", (e) => {
    e.preventDefault();
    dropZone.classList.remove("dragover");
    if (e.dataTransfer.files.length) uploadFile(e.dataTransfer.files[0]);
  });
  fileInput.addEventListener("change", () => {
    if (fileInput.files.length) uploadFile(fileInput.files[0]);
  });
}

async function uploadFile(file) {
  $("upload-info").textContent = `업로드 중... (${file.name})`;
  const form = new FormData();
  form.append("file", file);
  const res = await fetch("/api/upload", { method: "POST", body: form });
  const data = await res.json();
  if (!res.ok) {
    $("upload-info").textContent = `업로드 실패: ${data.error || res.status}`;
    return;
  }
  state.jobId = data.job_id;
  $("upload-info").textContent = `업로드 완료: ${data.original_filename}`;
  $("draft-name").value = data.original_filename.replace(/\.[^/.]+$/, "") + "_자동컷";
  $("step-config").classList.remove("hidden");
}

async function startAnalyze() {
  const config = collectConfig();
  $("btn-analyze").disabled = true;
  await fetch(`/api/jobs/${state.jobId}/analyze`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(config),
  });
  $("step-progress").classList.remove("hidden");
  pollStatus(onAnalyzeTick);
}

function pollStatus(onTick) {
  if (state.pollTimer) clearInterval(state.pollTimer);
  state.pollTimer = setInterval(async () => {
    const res = await fetch(`/api/jobs/${state.jobId}`);
    const job = await res.json();
    onTick(job);
  }, 1000);
}

function renderProgress(job) {
  $("progress-line").textContent = job.progress || "";
  $("log-box").textContent = (job.logs || []).join("\n");
  $("log-box").scrollTop = $("log-box").scrollHeight;
}

function onAnalyzeTick(job) {
  renderProgress(job);
  if (job.status === "analyzed") {
    clearInterval(state.pollTimer);
    $("btn-analyze").disabled = false;
    state.duration = job.duration;
    state.allCuts = job.cuts;
    renderReview(job);
    $("step-review").classList.remove("hidden");
    $("step-build").classList.remove("hidden");
  } else if (job.status === "error") {
    clearInterval(state.pollTimer);
    $("btn-analyze").disabled = false;
  }
}

function renderStats(stats) {
  const s = $("stats");
  if (!stats) { s.innerHTML = ""; return; }
  s.innerHTML = `
    <div>원본 길이<strong>${fmtTime(stats.duration)}</strong></div>
    <div>컷 편집 후<strong>${fmtTime(stats.keep_total)}</strong></div>
    <div>잘려나가는 길이<strong>${fmtTime(stats.cut_total)}</strong></div>
    <div>남는 구간 수<strong>${stats.keep_segment_count}</strong></div>
  `;
}

function renderReview(job) {
  renderStats(job.keep_stats);
  $("preview-srt").value = job.preview_srt || "";

  const tbody = document.querySelector("#cut-table tbody");
  tbody.innerHTML = "";
  job.cuts.forEach((cut, i) => {
    const tr = document.createElement("tr");
    tr.dataset.index = i;
    tr.innerHTML = `
      <td><input type="checkbox" checked /></td>
      <td>${i + 1}</td>
      <td>${fmtTime(cut.start)}</td>
      <td>${fmtTime(cut.end)}</td>
      <td>${(cut.end - cut.start).toFixed(2)}s</td>
      <td>${cut.reasons.join(", ")}</td>
      <td>${cut.confidence.toFixed(2)}</td>
    `;
    const checkbox = tr.querySelector("input");
    checkbox.addEventListener("change", () => tr.classList.toggle("excluded", !checkbox.checked));
    tbody.appendChild(tr);
  });
}

function checkedCuts() {
  const rows = document.querySelectorAll("#cut-table tbody tr");
  const result = [];
  rows.forEach((tr) => {
    const checkbox = tr.querySelector("input");
    if (checkbox.checked) {
      result.push(state.allCuts[parseInt(tr.dataset.index, 10)]);
    }
  });
  return result;
}

async function syncCutlist() {
  const res = await fetch(`/api/jobs/${state.jobId}/cutlist`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ cuts: checkedCuts() }),
  });
  const job = await res.json();
  renderStats(job.keep_stats);
  return job;
}

async function startBuild() {
  const draftName = $("draft-name").value.trim();
  if (!draftName) {
    alert("프로젝트 이름을 입력해주세요.");
    return;
  }
  $("btn-build").disabled = true;
  $("build-result").className = "";
  $("build-result").textContent = "";

  await syncCutlist();

  await fetch(`/api/jobs/${state.jobId}/build`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      draft_name: draftName,
      drafts_dir: $("drafts-dir").value.trim(),
      allow_replace: $("allow-replace").checked,
    }),
  });

  pollStatus(onBuildTick);
}

function onBuildTick(job) {
  $("build-result").textContent = job.progress || "";
  if (job.status === "done") {
    clearInterval(state.pollTimer);
    $("btn-build").disabled = false;
    $("build-result").className = "ok";
    $("build-result").textContent =
      `완료! CapCut에서 '${job.draft_result.draft_name}' 프로젝트를 여세요.\n경로: ${job.draft_result.path}`;
  } else if (job.status === "error") {
    clearInterval(state.pollTimer);
    $("btn-build").disabled = false;
    $("build-result").className = "error";
    $("build-result").textContent = `오류: ${job.error}`;
  }
}

function main() {
  setupUpload();
  loadDefaults();
  $("btn-analyze").addEventListener("click", startAnalyze);
  $("btn-recalc").addEventListener("click", syncCutlist);
  $("btn-build").addEventListener("click", startBuild);
}

main();
