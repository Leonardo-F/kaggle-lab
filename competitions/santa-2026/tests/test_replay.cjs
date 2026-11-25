const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");
const vm = require("node:vm");

const html = fs.readFileSync(path.join(__dirname, "../src/simulator.html"), "utf8");
const scripts = [...html.matchAll(/<script id="(?:solver|replay)-source">([\s\S]*?)<\/script>/g)];
const context = vm.createContext({ TextEncoder });
for (const [, source] of scripts) vm.runInContext(source, context);
const { readCSV, importedPuzzle, importedProgram, trace, graphStats,
  normalizeSlotLabel, nextSlotKey, summarizeVersion } = context;

test("CSV import preserves quoted fields, BOM, doubled quotes and CRLF", () => {
  const rows = readCSV('\uFEFFid,program\r\nfoo,"[[""+"" ,0,0,1]]"\r\n', ["id", "program"]);
  assert.equal(rows.get("foo").program, '[["+" ,0,0,1]]');
  assert.throws(() => readCSV('id,program\na,[]\na,[]', ["id", "program"]), /重复/);
  assert.throws(() => readCSV('id,program\na,"unfinished', ["id", "program"]), /CSV/);
});

test("replay keeps integers above Number.MAX_SAFE_INTEGER exact", () => {
  const puzzle = importedPuzzle({
    starting_values: "[9007199254740993,1]", targets: "[9007199254740994]",
    value_limit: "1000000000000000000", registers: "48",
  });
  const program = importedProgram('[["+",0,1,2]]');
  assert.equal(trace(puzzle, program)[0].value, 9007199254740994n);
  assert.equal(trace(puzzle, program)[0].hit, true);
  assert.throws(() => trace(puzzle, importedProgram('[["/",0,1,2]]')), /覆盖/);
  assert.throws(() => trace(puzzle, importedProgram('[["+",48,1,2]]')), /编号/);
  assert.throws(() => trace(puzzle, importedProgram('[["+",47,1,2]]')), /空寄存器/);
  assert.throws(() => trace(puzzle, importedProgram('[["/",1,0,2]]')), /整除/);
});

test("replay rejects invalid instructions and enforces file limits", () => {
  assert.throws(() => importedProgram('[["+",0,1,2,3]]'), /四项/);
  for (const token of ["0.0", "0e0", "1.0000000000000000001"]) {
    assert.throws(() => importedProgram(`[["+",${token},1,2]]`), /整数/);
  }
  assert.throws(() => importedProgram(" ".repeat(131073)), /128/);
  assert.throws(() => importedProgram("[" + Array(4097).fill('["+",0,0,1]').join(",") + "]"), /4096/);
});

test("graph comparison counts unique nodes, shared values and recomputation", () => {
  const puzzle = importedPuzzle({
    starting_values: "[3]", targets: "[9,27,81]", value_limit: "100", registers: "48",
  });
  const rows = trace(puzzle, importedProgram('[["*",0,0,1],["*",1,0,2],["*",1,1,3]]'));
  assert.deepEqual(
    [graphStats(puzzle, rows).steps, graphStats(puzzle, rows).nodes, graphStats(puzzle, rows).shared],
    [3, 3, 1],
  );
  const repeated = trace(puzzle, importedProgram('[["*",0,0,1],["*",0,0,2],["+",1,2,3]]'), false);
  assert.deepEqual(
    [graphStats(puzzle, repeated).steps, graphStats(puzzle, repeated).nodes, graphStats(puzzle, repeated).shared],
    [3, 2, 0],
  );
});

test("custom result labels are trimmed, limited and unique", () => {
  assert.equal(normalizeSlotLabel("  V8-draft  ", ["V1", "V2"]), "V8-draft");
  assert.throws(() => normalizeSlotLabel("   ", []), /请输入/);
  assert.throws(() => normalizeSlotLabel("x".repeat(41), []), /40/);
  assert.equal(normalizeSlotLabel("x".repeat(40), []), "x".repeat(40));
  assert.throws(() => normalizeSlotLabel("v1", ["V1"]), /重复/);
  assert.throws(() => normalizeSlotLabel("V8,2", []), /逗号/);
  assert.throws(() => normalizeSlotLabel("a\u0007b", []), /控制/);
  // Labels are rendered with textContent, so markup stays literal text.
  assert.equal(normalizeSlotLabel("<img src=x onerror=alert(1)>", []),
    "<img src=x onerror=alert(1)>");
  assert.equal(nextSlotKey(["v1", "custom-1", "custom-3"]), "custom-2");
  assert.equal(nextSlotKey([]), "custom-1");
});

test("version summaries expose unknown, invalid and missing programs", () => {
  const puzzles = new Set(["a", "b", "c"]);
  const rows = new Map([
    ["a", {program: '[["+",0,0,1]]'}],
    ["b", {program: "not json"}],
    ["z", {program: '[["+",0,0,1]]'}],
  ]);
  const summary = summarizeVersion(puzzles, rows);
  assert.deepEqual({...summary},
    {total: 1, valid: 1, invalid: 1, unknown: 1, missing: 1, puzzles: 3, imported: true});
  assert.equal(summarizeVersion(new Set(), rows).valid, 2);
  assert.equal(summarizeVersion(puzzles, undefined).imported, false);
  assert.equal(summarizeVersion(puzzles, undefined).missing, 3);
});

test("every simulator script parses as JavaScript", () => {
  const blocks = [...html.matchAll(/<script([^>]*)>([\s\S]*?)<\/script>/g)];
  assert.ok(blocks.length >= 3);
  for (const [, attributes, source] of blocks) {
    if (/type="application\/json"/.test(attributes)) continue;
    assert.doesNotThrow(() => new vm.Script(source));
  }
});
