/* Generate an n-square packing from two bands without a starting layout. */
'use strict';
const fs = require('node:fs');
const core = require('../simulator/packing-core.js');
const bands = require('../simulator/bands.js');

function checkInputs(n, leftWidth, bottomWidth, bottomAngle, leftAngle) {
  const whole = Math.floor(Math.sqrt(n));
  if (!Number.isInteger(n) || n < 2 || n > core.MAX_N || n === whole ** 2 ||
      ![leftWidth, bottomWidth].every(v => Number.isInteger(v) && v > 0 && v < whole) ||
      ![bottomAngle, leftAngle].every(v => v >= 0 && v < 90)) {
    throw Error('Use a nonsquare n, integer widths in (0, floor(sqrt(n))), and angles in [0, 90)');
  }
  return whole;
}

function search(n, leftWidth, bottomWidth, bottomAngle, leftAngle) {
  const whole = checkInputs(n,leftWidth,bottomWidth,bottomAngle,leftAngle);
  const nearby = angle => angle === 0 ? [] : Array.from({length:101}, (_, i) => angle + (.1*i-5))
    .filter(value => value > 0 && value < 90);
  const bottomAngles = nearby(bottomAngle);
  const leftAngles = nearby(leftAngle);
  const gridCount = (whole - leftWidth) * (whole - bottomWidth);

  function fit(extra) {
    const lower = bands.scanRectangle(whole + extra, bottomWidth + extra, bottomAngles, 0);
    const left = bands.scanRectangle(whole - bottomWidth, leftWidth + extra, leftAngles, 0);
    const count = gridCount + lower.count + left.count;
    if (count < n) return null;
    const recipe = [whole, extra, leftWidth, bottomWidth, lower.witness, left.witness];
    return {count, recipe};
  }

  let high = 1 - 1e-6;
  let low = Math.sqrt(n) - whole;
  let result = fit(high);
  if (!result) return null;
  for (let step = 0; step < 26; step++) {
    const extra = (low + high) / 2;
    const current = fit(extra);
    if (current) {
      high = extra;
      result = current;
    } else {
      low = extra;
    }
  }
  result.recipe[1] += 1e-8;
  const all = bands.construct(result.recipe);
  if (all.length !== result.count) throw Error('The formula and construction disagree on square count');
  const checked = core.evaluate(all);
  if (!checked.valid) throw Error('Construction failed the simulator check');
  const tiles = all.slice(0,n);
  return {...result, tiles, side:core.getBounds(tiles).L};
}

function dock(n, a, b, bottomAngle, leftAngle, fraction, overlap) {
  const k = checkInputs(n,a,b,bottomAngle,leftAngle);
  if (!(fraction > 0 && fraction < 1 && overlap > 0 && overlap <= b + fraction))
    throw Error('Use fractional side in (0, 1) and overlap in (0, bottom band height]');
  const bottomAngles = bottomAngle ? [bottomAngle] : [];
  const leftAngles = leftAngle ? [leftAngle] : [];
  let best = null;
  for (const phases of [16,32,0]) {
    const bottom = bands.scanRectangle(k + fraction,b + fraction,bottomAngles,phases);
    const left = bands.scanRectangle(k - b + overlap,a + fraction,leftAngles,phases);
    const recipe = [k,fraction,a,b,bottom.witness,left.witness,overlap];
    const all = bands.construct(recipe);
    if (all.length < n) continue;
    const tiles = all.slice(0,n), checked = core.evaluate(tiles);
    if (checked.valid && (!best || checked.bounds.L < best.side))
      best = {count:all.length, recipe, tiles, side:checked.bounds.L};
  }
  return best;
}

function joint(n,a,b,bottomAngle,leftAngle,fraction,overlap) {
  const k = checkInputs(n,a,b,bottomAngle,leftAngle);
  if (!(fraction > 0 && fraction < 1 && overlap > 0 && overlap <= b + fraction))
    throw Error('Use fractional side in (0, 1) and overlap in (0, bottom band height]');
  const nearby = angle => angle === 0 ? [] : [-1.25,-.75,-.5,-.25,0,.25,.5,.75,1.25]
    .map(offset=>angle+offset).filter(value=>value>0&&value<90);
  const result = bands.searchSeam(k,fraction,a,b,overlap,nearby(bottomAngle),nearby(leftAngle),24,22);
  if (result.count < n || !result.recipe) return null;
  const all = bands.construct(result.recipe);
  if (all.length !== result.count) throw Error('The seam search and construction disagree on square count');
  const tiles = all.slice(0,n), checked = core.evaluate(tiles);
  if (!checked.valid) throw Error('Construction failed the simulator check');
  return {...result, tiles, side:checked.bounds.L};
}

if (require.main === module) {
  const args = process.argv.slice(2);
  const method = args[0];
  const overlapping = method === '--dock' || method === '--joint';
  if (overlapping) args.shift();
  const output = args.pop();
  if (!output || args.length !== (overlapping ? 7 : 5))
    throw Error('Usage: node experiments/band_phase_search.cjs [--dock|--joint] n a b bottom-deg left-deg [fraction overlap] output.csv');
  const generate = method === '--joint' ? joint : overlapping ? dock : search;
  const result = generate(...args.map(Number));
  if (!result) throw Error('These parameters do not fit the requested square count');
  const {tiles, recipe, side} = result;
  const n = Number(args[0]);
  const rows = tiles.map((t,i) => [i,n,i,t.x,t.y,t.angle].join(','));
  fs.writeFileSync(output, [core.HEADER,...rows].join('\n')+'\n', {flag:'wx'});
  console.log(JSON.stringify({n:Number(n),side,recipe}));
}
module.exports = {search, dock, joint};
