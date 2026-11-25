const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");
const vm = require("node:vm");

const html = fs.readFileSync(path.join(__dirname, "../src/simulator.html"), "utf8");
const scripts = [...html.matchAll(/<script id="(?:solver|replay)-source">([\s\S]*?)<\/script>/g)];
const context = vm.createContext({ TextEncoder });
for (const [, source] of scripts) vm.runInContext(source, context);
const { readCSV, importedPuzzle, importedProgram, trace } = context;

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
