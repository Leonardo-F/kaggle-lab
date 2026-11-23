/* Run the same two-band construction as the browser, keeping only strict wins. */
'use strict';
const fs = require('node:fs');
const path = require('node:path');
const core = require('../simulator/packing-core.js');
const bands = require('../simulator/bands.js');

function run() {
  const [input, output] = process.argv.slice(2);
  if (!input || !output || path.resolve(input) === path.resolve(output))
    throw Error('Usage: node algorithms/double_band.cjs INPUT.csv NEW.csv');
  const records = require('../simulator/band-witnesses.js');
  const candidate = bands.portfolio(records);
  const original = core.indexSubmission(fs.readFileSync(input, 'utf8'));
  const out = fs.openSync(output, 'wx');
  let improved = 0, gain = 0;
  try {
    fs.writeSync(out, core.HEADER + '\r\n');
    for (let n = 1; n <= core.MAX_N; n++) {
      let tiles = original.tiles(n);
      const next = candidate(n), before = core.getBounds(tiles).L;
      if (next && core.getBounds(next).L < before - 1e-6) {
        const result = core.evaluate(next);
        if (!result.valid || next.length !== n) throw Error('Invalid double band at n=' + n);
        improved++;
        gain += (before - result.bounds.L) / Math.sqrt(n);
        tiles = next;
      }
      const start = n*(n-1)/2;
      fs.writeSync(out, tiles.map((t,i) => [start+i,n,i,...['x','y','angle'].map(key =>
        core.numericText(t,key))].join(',')+'\r\n').join(''));
    }
  } finally {
    fs.closeSync(out);
  }
  console.log(JSON.stringify({improved, gain}));
}
run();
