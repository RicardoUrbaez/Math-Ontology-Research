"""Run a local rapid pilot collector for the MathOntoSpeak user study.

This server collects real participant responses. It does not generate or
simulate study data.
"""

from __future__ import annotations

import csv
import json
import mimetypes
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse


ROOT = Path(__file__).resolve().parents[1]
STUDY_DIR = ROOT / "study"
RAPID_DIR = STUDY_DIR / "rapid_pilot"
RESPONSES_PATH = RAPID_DIR / "responses.jsonl"
HOST = "127.0.0.1"
PORT = 8765


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def load_payload() -> dict[str, object]:
    stimuli = {row["stimulus_id"]: row for row in read_csv(STUDY_DIR / "stimuli" / "study_stimuli.csv")}
    questions = read_csv(STUDY_DIR / "instruments" / "mcq_comprehension_test.csv")
    questions_by_stimulus: dict[str, list[dict[str, str]]] = {}
    for question in questions:
        questions_by_stimulus.setdefault(question["stimulus_id"], []).append(question)

    schedule = read_csv(STUDY_DIR / "protocol" / "counterbalance_schedule.csv")
    notation_manifest = read_json(STUDY_DIR / "audio" / "notation_only" / "notation_only_manifest.json")
    semantic_manifest = read_json(
        STUDY_DIR / "audio" / "mathontospeak_semantic" / "week4_latex_audio_gtts_manifest.json"
    )

    audio: dict[str, dict[str, str]] = {}
    for row in notation_manifest:
        audio.setdefault(row["stimulus_id"], {})["notation_only"] = media_url(row["audio_path"])
    for row in semantic_manifest:
        audio.setdefault(row["arxiv_id"], {})["mathontospeak_semantic"] = media_url(row["audio_path"])

    completed = completed_participants()
    return {
        "stimuli": stimuli,
        "questionsByStimulus": questions_by_stimulus,
        "schedule": schedule,
        "audio": audio,
        "completedParticipants": completed,
    }


def read_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def media_url(path_text: str) -> str:
    normalized = Path(path_text.replace("\\", "/"))
    return "/media/" + normalized.as_posix()


def completed_participants() -> list[str]:
    if not RESPONSES_PATH.exists():
        return []
    participants: list[str] = []
    for line in RESPONSES_PATH.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        pid = row.get("participant_id")
        if isinstance(pid, str) and pid not in participants:
            participants.append(pid)
    return participants


def validate_session(data: dict[str, object]) -> list[str]:
    errors: list[str] = []
    participant_id = str(data.get("participant_id", "")).strip()
    if not participant_id.startswith("P"):
        errors.append("Missing participant ID.")
    conditions = data.get("conditions")
    if not isinstance(conditions, list) or len(conditions) != 2:
        errors.append("Both conditions must be completed.")
    responses = data.get("responses")
    if not isinstance(responses, list) or len(responses) < 12:
        errors.append("MCQ responses are incomplete.")
    nasa = data.get("nasa")
    if not isinstance(nasa, dict) or len(nasa) < 2:
        errors.append("NASA-TLX ratings are incomplete.")
    interview = data.get("interview")
    if not isinstance(interview, dict) or not any(str(value).strip() for value in interview.values()):
        errors.append("Interview notes are required.")
    return errors


def append_session(data: dict[str, object]) -> None:
    RAPID_DIR.mkdir(parents=True, exist_ok=True)
    data["submitted_at_utc"] = datetime.now(timezone.utc).isoformat()
    with RESPONSES_PATH.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(data, ensure_ascii=True) + "\n")


class Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/":
            self.send_html(index_html())
            return
        if parsed.path == "/study":
            query = parse_qs(parsed.query)
            participant = query.get("participant", [""])[0]
            self.send_html(study_html(participant))
            return
        if parsed.path == "/data":
            self.send_json(load_payload())
            return
        if parsed.path.startswith("/media/"):
            self.send_media(parsed.path.removeprefix("/media/"))
            return
        self.send_error(404)

    def do_POST(self) -> None:
        if self.path != "/api/session":
            self.send_error(404)
            return
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length)
        try:
            data = json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError:
            self.send_json({"ok": False, "errors": ["Invalid JSON."]}, status=400)
            return
        errors = validate_session(data)
        if errors:
            self.send_json({"ok": False, "errors": errors}, status=400)
            return
        append_session(data)
        self.send_json({"ok": True, "message": "Session saved."})

    def send_html(self, html: str) -> None:
        body = html.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def send_json(self, payload: object, status: int = 200) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def send_media(self, relative_path: str) -> None:
        target = (ROOT / unquote(relative_path)).resolve()
        if ROOT not in target.parents or not target.exists():
            self.send_error(404)
            return
        content_type = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
        body = target.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: object) -> None:
        print(f"{self.address_string()} - {format % args}")


def index_html() -> str:
    payload = load_payload()
    rows = []
    completed = set(payload["completedParticipants"])
    for row in payload["schedule"]:
        pid = row["participant_id"]
        status = "saved" if pid in completed else "ready"
        rows.append(
            f"<tr><td>{pid}</td><td>{row['order']}</td><td>{status}</td>"
            f"<td><a href='/study?participant={pid}'>Open session</a></td></tr>"
        )
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>MathOntoSpeak Rapid Pilot</title>
  <style>{css()}</style>
</head>
<body>
  <main class="shell">
    <h1>MathOntoSpeak Rapid Pilot</h1>
    <p class="lede">Use one participant link per person. Do not enter names. Each session takes about 10-15 minutes.</p>
    <section class="panel">
      <h2>Participant Links</h2>
      <table>
        <thead><tr><th>ID</th><th>Order</th><th>Status</th><th>Link</th></tr></thead>
        <tbody>{''.join(rows)}</tbody>
      </table>
    </section>
    <section class="panel">
      <h2>After Sessions</h2>
      <p>Run <code>python scripts/finalize_rapid_pilot.py</code> to build the workbook and regenerate Week 6 results.</p>
      <p>Responses save to <code>study/rapid_pilot/responses.jsonl</code>.</p>
    </section>
  </main>
</body>
</html>"""


def study_html(participant: str) -> str:
    safe_participant = json.dumps(participant)
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>MathOntoSpeak Pilot Session</title>
  <style>{css()}</style>
</head>
<body>
  <main id="app" class="shell"></main>
  <script>
    const PARTICIPANT_ID = {safe_participant};
{client_js()}
  </script>
</body>
</html>"""


def css() -> str:
    return """
    :root { color-scheme: light; font-family: Inter, Arial, sans-serif; }
    body { margin: 0; background: #f6f7f9; color: #172033; }
    .shell { max-width: 980px; margin: 0 auto; padding: 32px 20px 56px; }
    h1 { margin: 0 0 8px; font-size: 34px; }
    h2 { margin: 0 0 16px; font-size: 22px; }
    h3 { margin: 18px 0 10px; }
    .lede { color: #516070; font-size: 17px; }
    .panel { background: white; border: 1px solid #dbe2ea; border-radius: 8px; padding: 22px; margin-top: 18px; }
    table { width: 100%; border-collapse: collapse; }
    th, td { text-align: left; border-bottom: 1px solid #e7edf3; padding: 10px 8px; }
    button, .button { background: #245f93; color: white; border: 0; border-radius: 6px; padding: 11px 16px; cursor: pointer; font-weight: 700; }
    button.secondary { background: #687585; }
    button:disabled { background: #aeb8c2; cursor: not-allowed; }
    .choice { display: block; border: 1px solid #dce4ed; border-radius: 6px; padding: 10px 12px; margin: 8px 0; background: #fbfcfe; }
    .choice input { margin-right: 8px; }
    .expression { font-size: 22px; font-family: Georgia, serif; background: #f4f7fb; padding: 12px; border-radius: 6px; }
    .meta { color: #687585; font-size: 14px; }
    .actions { display: flex; gap: 10px; margin-top: 18px; }
    input[type=range] { width: 100%; }
    textarea { width: 100%; min-height: 92px; resize: vertical; border: 1px solid #d4dde8; border-radius: 6px; padding: 10px; font: inherit; }
    .error { color: #9b1c1c; background: #fff0f0; border: 1px solid #f0b4b4; padding: 10px; border-radius: 6px; }
    .success { color: #155724; background: #eef8f0; border: 1px solid #b8dfc1; padding: 10px; border-radius: 6px; }
    code { background: #eef2f6; padding: 2px 5px; border-radius: 4px; }
    """


def client_js() -> str:
    return r"""
const app = document.getElementById("app");
let payload;
let state = {
  participant_id: PARTICIPANT_ID,
  step: "intro",
  conditionIndex: 0,
  stimulusIndex: 0,
  responses: [],
  nasa: {},
  interview: {},
};

const tlx = ["Mental", "Physical", "Temporal", "Performance", "Effort", "Frustration"];

fetch("/data").then(r => r.json()).then(data => {
  payload = data;
  render();
});

function scheduleRow() {
  return payload.schedule.find(row => row.participant_id === state.participant_id) || payload.schedule[0];
}

function conditionOrder() {
  const row = scheduleRow();
  return [row.condition_1, row.condition_2];
}

function stimuliForCondition(index) {
  const row = scheduleRow();
  const key = index === 0 ? "condition_1_stimuli" : "condition_2_stimuli";
  return row[key].split("-");
}

function conditionLabel(condition) {
  return condition === "notation_only" ? "Version A" : "Version B";
}

function render() {
  if (!payload) return;
  if (state.step === "intro") return renderIntro();
  if (state.step === "stimulus") return renderStimulus();
  if (state.step === "nasa") return renderNasa();
  if (state.step === "interview") return renderInterview();
  if (state.step === "done") return renderDone();
}

function renderIntro() {
  const row = scheduleRow();
  app.innerHTML = `
    <h1>MathOntoSpeak Pilot</h1>
    <p class="lede">Participant ${state.participant_id}. Order ${row.order}. No names are collected.</p>
    <section class="panel">
      <h2>Before You Start</h2>
      <p>This is a short usability pilot for a math accessibility tool. You may stop at any time.</p>
      <p>You will hear two audio versions of the same three math expressions. After each version, answer short comprehension questions and workload ratings.</p>
      <label class="choice"><input id="consent" type="checkbox"> I understand and agree to continue.</label>
      <div class="actions"><button onclick="startStudy()">Start</button></div>
    </section>`;
}

function startStudy() {
  if (!document.getElementById("consent").checked) {
    alert("Please confirm before starting.");
    return;
  }
  state.step = "stimulus";
  render();
}

function renderStimulus() {
  const conditions = conditionOrder();
  const condition = conditions[state.conditionIndex];
  const stimulusIds = stimuliForCondition(state.conditionIndex);
  const stimulusId = stimulusIds[state.stimulusIndex];
  const stimulus = payload.stimuli[stimulusId];
  const questions = payload.questionsByStimulus[stimulusId];
  const audioUrl = payload.audio[stimulusId][condition];
  app.innerHTML = `
    <h1>${conditionLabel(condition)}</h1>
    <p class="meta">Expression ${state.stimulusIndex + 1} of ${stimulusIds.length}</p>
    <section class="panel">
      <div class="expression">${escapeHtml(stimulus.display_expression)}</div>
      <p class="meta">${escapeHtml(stimulus.domain)} · ${escapeHtml(stimulus.difficulty)}</p>
      <audio controls src="${audioUrl}" style="width: 100%; margin: 12px 0;"></audio>
      ${questions.map(q => questionHtml(q, condition)).join("")}
      <div class="actions">
        <button onclick="saveStimulus()">Continue</button>
      </div>
    </section>`;
}

function questionHtml(q, condition) {
  const name = `${condition}_${q.question_id}`;
  return `<div class="question" data-question="${q.question_id}" data-stimulus="${q.stimulus_id}" data-condition="${condition}" data-correct="${q.correct_choice}">
    <h3>${escapeHtml(q.condition_independent_prompt)}</h3>
    ${["a", "b", "c", "d"].map(letter => {
      const value = letter.toUpperCase();
      return `<label class="choice"><input type="radio" name="${name}" value="${value}"> ${value}. ${escapeHtml(q["choice_" + letter])}</label>`;
    }).join("")}
  </div>`;
}

function saveStimulus() {
  const blocks = [...document.querySelectorAll(".question")];
  const newResponses = [];
  for (const block of blocks) {
    const checked = block.querySelector("input:checked");
    if (!checked) {
      alert("Please answer every question on this page.");
      return;
    }
    newResponses.push({
      participant_id: state.participant_id,
      condition: block.dataset.condition,
      stimulus_id: block.dataset.stimulus,
      question_id: block.dataset.question,
      response: checked.value,
      correct_choice: block.dataset.correct,
    });
  }
  state.responses.push(...newResponses);
  const stimuli = stimuliForCondition(state.conditionIndex);
  if (state.stimulusIndex < stimuli.length - 1) {
    state.stimulusIndex += 1;
  } else {
    state.step = "nasa";
  }
  render();
}

function renderNasa() {
  const condition = conditionOrder()[state.conditionIndex];
  app.innerHTML = `
    <h1>${conditionLabel(condition)} Workload</h1>
    <section class="panel">
      <p>Rate how demanding this audio version felt. 0 means low, 100 means high.</p>
      ${tlx.map(name => `
        <label><strong>${name}</strong>: <span id="${name}_value">50</span></label>
        <input type="range" min="0" max="100" value="50" id="${name}" oninput="document.getElementById('${name}_value').textContent=this.value">
      `).join("<br>")}
      <div class="actions"><button onclick="saveNasa()">Continue</button></div>
    </section>`;
}

function saveNasa() {
  const condition = conditionOrder()[state.conditionIndex];
  const ratings = {};
  for (const name of tlx) ratings[name.toLowerCase()] = Number(document.getElementById(name).value);
  state.nasa[condition] = ratings;
  if (state.conditionIndex === 0) {
    state.conditionIndex = 1;
    state.stimulusIndex = 0;
    state.step = "stimulus";
  } else {
    state.step = "interview";
  }
  render();
}

function renderInterview() {
  app.innerHTML = `
    <h1>Final Questions</h1>
    <section class="panel">
      <label><strong>Which version helped you understand the math better, and why?</strong></label>
      <textarea id="q1"></textarea>
      <label><strong>What made Version A harder or easier?</strong></label>
      <textarea id="q2"></textarea>
      <label><strong>What made Version B harder or easier?</strong></label>
      <textarea id="q3"></textarea>
      <div class="actions"><button onclick="submitSession()">Submit Session</button></div>
      <div id="message"></div>
    </section>`;
}

function submitSession() {
  state.interview = {
    preference: document.getElementById("q1").value.trim(),
    version_a: document.getElementById("q2").value.trim(),
    version_b: document.getElementById("q3").value.trim(),
  };
  if (!Object.values(state.interview).some(Boolean)) {
    alert("Please enter at least one interview note.");
    return;
  }
  fetch("/api/session", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      participant_id: state.participant_id,
      order: scheduleRow().order,
      conditions: conditionOrder(),
      responses: state.responses,
      nasa: state.nasa,
      interview: state.interview,
    })
  }).then(async response => {
    const data = await response.json();
    if (!response.ok) throw new Error((data.errors || [data.message]).join("\n"));
    state.step = "done";
    render();
  }).catch(error => {
    document.getElementById("message").innerHTML = `<p class="error">${escapeHtml(error.message)}</p>`;
  });
}

function renderDone() {
  app.innerHTML = `
    <h1>Session Saved</h1>
    <section class="panel">
      <p class="success">Thank you. The session has been recorded.</p>
      <p><a href="/">Return to participant links</a></p>
    </section>`;
}

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, ch => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#039;" }[ch]));
}
"""


def main() -> None:
    RAPID_DIR.mkdir(parents=True, exist_ok=True)
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"Rapid pilot server running at http://{HOST}:{PORT}")
    print(f"Responses will save to {RESPONSES_PATH}")
    server.serve_forever()


if __name__ == "__main__":
    main()
