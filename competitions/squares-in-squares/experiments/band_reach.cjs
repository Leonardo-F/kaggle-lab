/* Measure how many public per-puzzle sides the two-band family can meet. */
'use strict';
const fs = require('node:fs');
const path = require('node:path');
const bands = require('../simulator/bands.js');

function main() {
  const [reference, step = '3'] = process.argv.slice(2);
  if (!reference) throw Error('Usage: node experiments/band_reach.cjs REFERENCE.json [ANGLE_STEP]');
  const angles = [];
  for (let degrees = Number(step); degrees <= 44; degrees += Number(step)) angles.push(degrees);
  const rows = JSON.parse(fs.readFileSync(path.resolve(reference), 'utf8')).puzzles;
  let tested = 0, reach = 0, near = 0;
  const short = [];
  for (const row of rows) {
    const n = row.n, side = Number(row.L);
    const k = Math.floor(Math.sqrt(n)), fraction = side - k;
    if (fraction <= 0.02) continue;
    const result = bands.search(k, fraction, angles, 8);
    tested++;
    if (result.count >= n) reach++;
    else {
      if (result.count >= n - 4) near++;
      short.push({n, k, fraction: Number(fraction.toFixed(6)), capacity: result.count,
                  shortfall: n - result.count});
    }
  }
  short.sort((a, b) => a.shortfall - b.shortfall);
  console.log(JSON.stringify({tested, reach, withinFour: near, closest: short.slice(0, 5)}));
}

main();
