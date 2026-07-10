import fs from "node:fs/promises";
import path from "node:path";
import { SpreadsheetFile, Workbook } from "@oai/artifact-tool";

const root = process.cwd();
const outputDir = path.join(root, "study", "analysis");
const outputPath = path.join(outputDir, "mathontospeak_study_analysis_template.xlsx");
const previewDir = path.join(outputDir, "previews");

function parseCsv(text) {
  const rows = [];
  let row = [];
  let cell = "";
  let quoted = false;
  for (let i = 0; i < text.length; i += 1) {
    const ch = text[i];
    const next = text[i + 1];
    if (quoted && ch === '"' && next === '"') {
      cell += '"';
      i += 1;
    } else if (ch === '"') {
      quoted = !quoted;
    } else if (ch === "," && !quoted) {
      row.push(cell);
      cell = "";
    } else if ((ch === "\n" || ch === "\r") && !quoted) {
      if (ch === "\r" && next === "\n") i += 1;
      row.push(cell);
      if (row.some((v) => v !== "")) rows.push(row);
      row = [];
      cell = "";
    } else {
      cell += ch;
    }
  }
  if (cell || row.length) {
    row.push(cell);
    if (row.some((v) => v !== "")) rows.push(row);
  }
  const [headers, ...data] = rows;
  return data.map((values) => Object.fromEntries(headers.map((h, i) => [h, values[i] ?? ""])));
}

async function readCsv(relativePath) {
  const text = await fs.readFile(path.join(root, relativePath), "utf8");
  return parseCsv(text);
}

function setTitle(sheet, title, subtitle = "") {
  sheet.getRange("A1:H1").merge();
  sheet.getRange("A1").values = [[title]];
  sheet.getRange("A1").format = {
    fill: "#1F4E79",
    font: { bold: true, color: "#FFFFFF", size: 16 },
  };
  if (subtitle) {
    sheet.getRange("A2:H2").merge();
    sheet.getRange("A2").values = [[subtitle]];
    sheet.getRange("A2").format = { fill: "#D9EAF7", font: { italic: true, color: "#1F2937" } };
  }
}

function writeTable(sheet, startCell, headers, rows) {
  const start = sheet.getRange(startCell);
  const matrix = [headers, ...rows];
  start.resize(matrix.length, headers.length).values = matrix;
  const headerRange = start.resize(1, headers.length);
  headerRange.format = { fill: "#5B9BD5", font: { bold: true, color: "#FFFFFF" } };
  const whole = start.resize(matrix.length, headers.length);
  whole.format.borders = { preset: "all", style: "thin", color: "#D9E2F3" };
  whole.format.wrapText = true;
  return whole;
}

function styleSheet(sheet) {
  sheet.showGridLines = false;
  sheet.freezePanes.freezeRows(3);
  sheet.getRange("A:H").format.columnWidth = 20;
}

function setWidths(sheet, widths) {
  widths.forEach((width, idx) => {
    const col = columnName(idx);
    sheet.getRange(`${col}:${col}`).format.columnWidth = width;
  });
}

function columnName(index) {
  let n = index + 1;
  let name = "";
  while (n > 0) {
    const rem = (n - 1) % 26;
    name = String.fromCharCode(65 + rem) + name;
    n = Math.floor((n - 1) / 26);
  }
  return name;
}

const stimuli = await readCsv("study/stimuli/study_stimuli.csv");
const questions = await readCsv("study/instruments/mcq_comprehension_test.csv");
const schedule = await readCsv("study/protocol/counterbalance_schedule.csv");

const comprehensionEntryRows = schedule.flatMap((participant) =>
  [participant.condition_1, participant.condition_2].flatMap((condition) =>
    questions.map((question) => [
      participant.participant_id,
      condition,
      question.stimulus_id,
      question.question_id,
      "",
      question.correct_choice,
      "",
      "",
    ]),
  ),
);

const nasaEntryRows = schedule.flatMap((participant) =>
  [participant.condition_1, participant.condition_2].map((condition) => [
    participant.participant_id,
    condition,
    "",
    "",
    "",
    "",
    "",
    "",
    "pending participant data",
    "",
  ]),
);

const interviewEntryRows = schedule.map((participant) => [
  participant.participant_id,
  "pending interview transcript",
  "",
  "",
  "",
  "",
  "",
  "Not collected yet; enter notes after the 5-minute interview.",
]);

const workbook = Workbook.create();

const summary = workbook.worksheets.add("Summary");
setTitle(summary, "MathOntoSpeak Study Analysis Template", "Enter participant data in the scoring sheets; summary formulas update automatically.");
styleSheet(summary);
summary.getRange("A4:B14").values = [
  ["Metric", "Value"],
  ["Target expressions", stimuli.length],
  ["MCQ items", questions.length],
  ["Planned participants", schedule.length],
  ["Conditions", "Notation-only and MathOntoSpeak semantic"],
  ["Design", "Within-subjects, counterbalanced AB/BA"],
  ["Notation-only score mean", ""],
  ["Semantic score mean", ""],
  ["Notation-only NASA mean", ""],
  ["Semantic NASA mean", ""],
  ["Manual status", "Ready for pilot data entry"],
];
summary.getRange("B10").formulas = [["=IFERROR(AVERAGEIFS('Comprehension Scores'!$H:$H,'Comprehension Scores'!$B:$B,\"notation_only\"),\"\")"]];
summary.getRange("B11").formulas = [["=IFERROR(AVERAGEIFS('Comprehension Scores'!$H:$H,'Comprehension Scores'!$B:$B,\"mathontospeak_semantic\"),\"\")"]];
summary.getRange("B12").formulas = [["=IFERROR(AVERAGEIFS('NASA TLX'!$J:$J,'NASA TLX'!$B:$B,\"notation_only\"),\"\")"]];
summary.getRange("B13").formulas = [["=IFERROR(AVERAGEIFS('NASA TLX'!$J:$J,'NASA TLX'!$B:$B,\"mathontospeak_semantic\"),\"\")"]];
summary.getRange("A4:B14").format.borders = { preset: "all", style: "thin", color: "#D9E2F3" };
summary.getRange("A4:A14").format = { fill: "#EAF2F8", font: { bold: true } };
summary.getRange("B10:B13").format.numberFormat = "0.00";
setWidths(summary, [36, 78, 18, 18, 18, 18, 18, 18]);

const stimSheet = workbook.worksheets.add("Stimuli");
setTitle(stimSheet, "Study Stimuli");
styleSheet(stimSheet);
writeTable(
  stimSheet,
  "A4",
  ["Stimulus ID", "Domain", "Difficulty", "LaTeX", "Display Expression", "Notation Reading", "Semantic Target", "Source Rationale"],
  stimuli.map((r) => [
    r.stimulus_id,
    r.domain,
    r.difficulty,
    r.latex,
    r.display_expression,
    r.notation_reading,
    r.semantic_target,
    r.source_rationale,
  ]),
);
setWidths(stimSheet, [16, 18, 14, 36, 36, 50, 54, 58]);

const scheduleSheet = workbook.worksheets.add("Counterbalance");
setTitle(scheduleSheet, "Counterbalance Schedule");
styleSheet(scheduleSheet);
writeTable(
  scheduleSheet,
  "A4",
  ["Participant ID", "Order", "Condition 1", "Condition 2", "Condition 1 Stimuli", "Condition 2 Stimuli", "Notes"],
  schedule.map((r) => [r.participant_id, r.order, r.condition_1, r.condition_2, r.condition_1_stimuli, r.condition_2_stimuli, r.notes]),
);
setWidths(scheduleSheet, [20, 12, 30, 34, 32, 32, 40]);

const compSheet = workbook.worksheets.add("Comprehension Scores");
setTitle(compSheet, "Comprehension Score Entry");
styleSheet(compSheet);
writeTable(
  compSheet,
  "A4",
  ["Participant ID", "Condition", "Stimulus ID", "Question ID", "Response", "Correct Choice", "Correct", "Score"],
  comprehensionEntryRows,
);
compSheet.getRange("H5").formulas = [["=IF(G5=\"Yes\",1,IF(G5=\"No\",0,\"\"))"]];
compSheet.getRange(`H5:H${4 + comprehensionEntryRows.length}`).fillDown();
compSheet.getRange(`H5:H${4 + comprehensionEntryRows.length}`).format.numberFormat = "0";
setWidths(compSheet, [20, 24, 18, 20, 14, 16, 12, 12]);

const nasaSheet = workbook.worksheets.add("NASA TLX");
setTitle(nasaSheet, "NASA-TLX Entry");
styleSheet(nasaSheet);
writeTable(
  nasaSheet,
  "A4",
  ["Participant ID", "Condition", "Mental", "Physical", "Temporal", "Performance", "Effort", "Frustration", "Notes", "Raw TLX Mean"],
  nasaEntryRows,
);
nasaSheet.getRange("J5").formulas = [["=IF(COUNT(C5:H5)=6,AVERAGE(C5:H5),\"\")"]];
nasaSheet.getRange(`J5:J${4 + nasaEntryRows.length}`).fillDown();
nasaSheet.getRange(`C5:H${4 + nasaEntryRows.length}`).format.numberFormat = "0";
nasaSheet.getRange(`J5:J${4 + nasaEntryRows.length}`).format.numberFormat = "0.00";
setWidths(nasaSheet, [20, 26, 12, 12, 12, 14, 12, 14, 42, 16]);

const questionsSheet = workbook.worksheets.add("MCQ Items");
setTitle(questionsSheet, "MCQ Comprehension Items");
styleSheet(questionsSheet);
writeTable(
  questionsSheet,
  "A4",
  ["Question ID", "Stimulus ID", "Prompt", "A", "B", "C", "D", "Correct", "Construct"],
  questions.map((r) => [
    r.question_id,
    r.stimulus_id,
    r.condition_independent_prompt,
    r.choice_a,
    r.choice_b,
    r.choice_c,
    r.choice_d,
    r.correct_choice,
    r.construct,
  ]),
);
setWidths(questionsSheet, [18, 16, 58, 34, 34, 34, 34, 12, 28]);

const interviewSheet = workbook.worksheets.add("Interview Coding");
setTitle(interviewSheet, "Interview Transcription and Coding");
styleSheet(interviewSheet);
writeTable(
  interviewSheet,
  "A4",
  ["Participant ID", "Excerpt / Summary", "Code 1", "Code 2", "Code 3", "Valence", "Condition Mentioned", "Researcher Notes"],
  interviewEntryRows,
);
setWidths(interviewSheet, [18, 58, 28, 28, 28, 16, 28, 48]);

await fs.mkdir(outputDir, { recursive: true });
await fs.mkdir(previewDir, { recursive: true });

for (const sheetName of ["Summary", "Stimuli", "Comprehension Scores", "NASA TLX", "Interview Coding"]) {
  const preview = await workbook.render({ sheetName, autoCrop: "all", scale: 1, format: "png" });
  await fs.writeFile(path.join(previewDir, `${sheetName.replaceAll(" ", "_")}.png`), new Uint8Array(await preview.arrayBuffer()));
}

const errors = await workbook.inspect({
  kind: "match",
  searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A",
  options: { useRegex: true, maxResults: 300 },
  summary: "final formula error scan",
});
console.log(errors.ndjson);

const xlsx = await SpreadsheetFile.exportXlsx(workbook);
await xlsx.save(outputPath);
console.log(`Saved ${outputPath}`);
