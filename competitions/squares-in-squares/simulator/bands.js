/* Two tilted bands beside an upright grid. Shared by the browser and Node CLI. */
'use strict';
const PackingBands = (core => {
  const eps = 1e-10;
  const floor = value => Math.floor(value + eps);

  function cornerDistances(width, height, sine, cosine) {
    const distances = [];
    for (let x = 1; x <= floor(width); x++)
      for (let y = 1; y <= floor(height); y++)
        distances.push(x * sine + y * cosine);
    return distances.sort((a, b) => a - b);
  }

  // Between these offsets, the integer row lengths and corner counts are
  // constant. At an endpoint a square can become exactly tangent to a seam.
  function phaseEvents(span, product, corners, wallLimit) {
    const periodic = value => value - Math.floor(value);
    const result = [0, periodic(span - 1)];
    for (const distance of corners)
      result.push(periodic(distance), periodic(span - 1 - distance));
    for (let length = 1; length <= wallLimit; length++) {
      const distance = length * product;
      result.push(periodic(distance), periodic(span - 1 - distance));
    }
    return result;
  }

  // For row coordinate v (measured from the lower right corner), the two
  // corner triangles and the two opposite wall pairs bound its length.
  function scanRectangle(width, height, angles, phases, visit) {
    let count = floor(width) * floor(height), witness = null;
    for (const degrees of angles) {
      const angle = degrees * Math.PI / 180, s = Math.sin(angle), c = Math.cos(angle);
      const span = width * s + height * c, product = s * c;
      const wallLimit = Math.min(floor((width - s) / c), floor((height - c) / s));
      if (wallLimit <= 0) continue;
      const corners = cornerDistances(width, height, s, c);
      const offsets = phases === 0
        ? phaseEvents(span, product, corners, wallLimit)
        : Array.from({length:phases}, (_, i) => i / phases);
      for (const phase of offsets) {
        const firstV = .5 + phase;
        let left = 0, right = corners.length, sum = 0, offset = -Infinity, start = 0;
        let phaseCount = 0, phaseWitness = null;
        for (let j = 0; firstV + j <= span - .5 + eps; j++) {
          const lower = firstV + j - .5, upper = span - firstV - j - .5;
          while (left < corners.length && corners[left] <= lower + eps) left++;
          while (right > 0 && corners[right - 1] > upper + eps) right--;
          if (left - sum > offset) { offset = left - sum; start = j; }
          sum += Math.min(wallLimit, floor(lower / product), floor(upper / product));
          if (visit && offset + sum + right > phaseCount) {
            phaseCount = offset + sum + right;
            phaseWitness = [degrees, phase, start, j];
          }
          if (offset + sum + right > count) {
            count = offset + sum + right;
            witness = [degrees, phase, start, j];
          }
        }
        if (visit && phaseWitness) visit(phaseCount,phaseWitness);
      }
    }
    return {count, witness};
  }

  function rectangle(width, height, spec) {
    const tiles = [];
    const [degrees, phase, first, last] = spec || [0, 0, 0, -1];
    const angle = degrees * Math.PI / 180, s = Math.sin(angle), c = Math.cos(angle);
    const span = width * s + height * c;
    for (let x = 1; x <= floor(width); x++) {
      for (let y = 1; y <= floor(height); y++) {
        const distance = x * s + y * c;
        if (!spec || distance <= phase + first + eps)
          tiles.push({x:width - x + .5, y:y - .5, angle:0});
        if (spec && distance <= span - 1 - phase - last + eps)
          tiles.push({x:x - .5, y:height - y + .5, angle:0});
      }
    }
    const half = (s + c) / 2;
    for (let j = first; j <= last; j++) {
      const v = .5 + phase + j - s * width;
      const low = Math.max((half + s*v) / c, (half - c*v) / s);
      const high = Math.min((width - half + s*v) / c, (height - half - c*v) / s);
      const length = Math.max(0, 1 + floor(high - low));
      for (let i = 0; i < length; i++) {
        const u = (low + high - length + 1) / 2 + i;
        tiles.push({x:c*u - s*v, y:s*u + c*v, angle});
      }
    }
    return tiles;
  }

  // The bands are feasible individually. Across their seam, maximum matching
  // gives a minimum vertex cover of the collision graph. Keep its complement.
  function maximumMatching(edges, rightSize) {
    const partner = new Int32Array(rightSize).fill(-1);
    const visited = new Int32Array(rightSize);
    function augment(i, seen) {
      for (const j of edges[i]) {
        if (visited[j] === seen) continue;
        visited[j] = seen;
        if (partner[j] < 0 || augment(partner[j], seen)) {
          partner[j] = i;
          return true;
        }
      }
      return false;
    }
    const unmatched = edges.map((_,i) => i).filter(i => !augment(i,i+1));
    return {partner, unmatched};
  }

  function joinBands(bottom, left) {
    const size = bottom.length;
    const edges = Array.from({length:size}, () => []);
    for (const [i,j] of core.collisions(bottom.concat(left),true).pairs)
      if (i < size && j >= size) edges[i].push(j - size);
    const {partner, unmatched} = maximumMatching(edges,left.length);
    const reachableBottom = new Set(), reachableLeft = new Set();
    function visit(i) {
      if (reachableBottom.has(i)) return;
      reachableBottom.add(i);
      for (const j of edges[i]) {
        if (partner[j] === i || reachableLeft.has(j)) continue;
        reachableLeft.add(j);
        if (partner[j] >= 0) visit(partner[j]);
      }
    }
    unmatched.forEach(visit);
    return bottom.filter((_,i) => reachableBottom.has(i))
      .concat(left.filter((_,j) => !reachableLeft.has(j)));
  }

  // Retain multiple row offsets at each angle. A band can lose a square on
  // its own and still gain one after both bands are fitted at their seam.
  function rectangleOptions(width,height,angles,phases,limit) {
    const groups = new Map();
    const consider = (count,witness) => {
      const key = witness ? `${witness[0]}:${Math.floor(8*witness[1])}` : 'grid';
      if (!groups.has(key) || groups.get(key).count < count)
        groups.set(key,{count,witness});
    };
    scanRectangle(width,height,angles,phases,consider);
    consider(floor(width)*floor(height),null);
    return [...groups.values()].sort((a,b)=>b.count-a.count).slice(0,limit);
  }

  function searchSeam(k,fraction,a,b,overlap,bottomAngles,leftAngles,phases=24,limit=20) {
    const side = k + fraction, seam = b + fraction, leftWidth = a + fraction;
    if (overlap <= 0 || overlap > seam) return {count:k*k,recipe:null};
    const scale = 1.000000012;
    const bottom = rectangleOptions(side,seam,bottomAngles,phases,limit);
    const left = rectangleOptions(k-b+overlap,leftWidth,leftAngles,phases,limit);
    const gridCount = (k-a)*(k-b);
    let count = k*k, recipe = null;
    if (bottom[0].count+left[0].count+gridCount<=count) return {count,recipe};
    const shift = (x,y,angle)=>({x:(x-side/2)*scale,y:(y-side/2)*scale,angle});
    for (const band of bottom) {
      band.edge = rectangle(side,seam,band.witness)
        .filter(t=>t.x<leftWidth+1 && t.y>seam-overlap-1)
        .map(t=>shift(t.x,t.y,t.angle));
    }
    for (const band of left) {
      band.edge = rectangle(k-b+overlap,leftWidth,band.witness)
        .filter(t=>t.x<overlap+1)
        .map(t=>shift(t.y,t.x+seam-overlap,-t.angle));
    }
    for (const lower of bottom) {
      if (lower.count+left[0].count+gridCount<=count) break;
      for (const upper of left) {
        const capacity = lower.count+upper.count+gridCount;
        if (capacity<=count) break;
        const graph = lower.edge.map(t=>[]);
        for (let i=0;i<lower.edge.length;i++) {
          for (let j=0;j<upper.edge.length;j++) {
            if (core.penetration(lower.edge[i],upper.edge[j])) graph[i].push(j);
          }
        }
        const {unmatched} = maximumMatching(graph,upper.edge.length);
        const combined = capacity - graph.length + unmatched.length;
        if (combined>count) {
          count = combined;
          recipe = [k,fraction,a,b,lower.witness,upper.witness,overlap];
        }
      }
    }
    return {count,recipe};
  }

  function construct([k, fraction, a, b, bottomSpec, leftSpec, overlap = 0]) {
    const side = k + fraction;
    const seam = b + fraction;
    const scale = 1.000000012;
    const center = (x,y,angle) => ({x:(x-side/2)*scale, y:(y-side/2)*scale, angle});
    const bottom = rectangle(side, seam, bottomSpec).map(t => center(t.x,t.y,t.angle));
    const left = rectangle(k - b + overlap, a + fraction, leftSpec)
      .map(t => center(t.y,t.x + seam - overlap,-t.angle));
    const tiles = overlap ? joinBands(bottom,left) : bottom.concat(left);
    for (let x = a; x < k; x++)
      for (let y = b; y < k; y++)
        tiles.push(center(x + fraction + .5,y + fraction + .5,0));
    return tiles.sort((a,b) => Math.hypot(a.x,a.y) - Math.hypot(b.x,b.y));
  }

  function search(k, fraction, angles, phases) {
    let best = {count:k*k, recipe:null};
    for (let b = 1; b < k; b++) {
      const bottom = scanRectangle(k + fraction, b + fraction, angles, phases);
      for (let a = 1; a < k; a++) {
        const left = scanRectangle(k - b, a + fraction, angles, phases);
        const count = (k - a) * (k - b) + bottom.count + left.count;
        if (count > best.count)
          best = {count, recipe:[k, fraction, a, b, bottom.witness, left.witness]};
      }
    }
    return best;
  }

  // Enlarge an existing seed by adding a right column and a top row per unit.
  // The integer excess above k² is preserved under this construction.
  function portfolio(records) {
    const choices = new Map();
    for (const [capacity, recipe] of records) {
      const [k, fraction] = recipe;
      for (let width = 0; (k+width)**2 < 1000; width++) {
        const outer = k + width;
        const count = Math.min(1000, outer**2 + capacity - k*k);
        const bound = (outer + fraction) * 1.00000003;
        for (let n = outer**2 + 1; n <= count; n++)
          if (!choices.has(n) || bound < choices.get(n).bound)
            choices.set(n, {recipe, width, bound});
      }
    }
    return function candidate(n) {
      const choice = choices.get(n);
      if (!choice) return null;
      const {recipe, width} = choice, [k, fraction] = recipe;
      const tiles = construct(recipe), side = k + fraction;
      const step = 1.000000012, origin = -step * side / 2;
      const start = origin + step * side + (step - 1);
      for (let i = 0; i < width; i++) {
        for (let j = 0; j < k + width; j++)
          tiles.push({x:start + i*step + .5, y:origin + j*step + .5, angle:0});
        for (let j = 0; j < k; j++)
          tiles.push({x:origin + j*step + .5, y:start + i*step + .5, angle:0});
      }
      if (width) {
        const center = width / 2;
        tiles.sort((a,b) => Math.hypot(a.x-center,a.y-center) - Math.hypot(b.x-center,b.y-center));
      }
      return tiles.slice(0,n);
    };
  }

  return {construct, search, scanRectangle, searchSeam, portfolio};
})(typeof module === 'object' && module.exports ? require('./packing-core.js') : globalThis.PackingCore);
if (typeof module === 'object' && module.exports) module.exports = PackingBands;
