'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const P = require('../simulator/packing-core.js');
const tile = (x,y=.5,angle=0)=>({x,y,angle});
const header = 'id,n,square_id,x,y,angle\n';

test('constructive family improves n=5 and n=65; all counts stay feasible and no worse than grid',()=>{
  assert.equal(typeof P.makeConstructive,'function');
  for(let n=1;n<=1000;n++){
    const c=P.makeConstructive(n),e=P.evaluate(c.tiles);
    assert.equal(c.tiles.length,n);assert.equal(e.valid,true,`n=${n}`);
    assert.ok(e.bounds.L<=Math.ceil(Math.sqrt(n)),`n=${n}`);
  }
  assert.ok(P.makeConstructive(5).L<2.708);
  assert.ok(P.makeConstructive(65).L<8.54);
  assert.equal(P.makeConstructive(64).method,'grid');
  const a=P.makeConstructive(5);a.tiles[0].x=100;
  assert.ok(P.makeConstructive(5).L<2.708,'returned layouts must not share mutable tiles');
});

test('all 1000 grid layouts contain n distinct unrotated unit cells within ceil(sqrt(n))',()=>{
  let score=0, rows=0;
  for(let n=1;n<=1000;n++){
    const grid=P.makeGrid(n),e=P.evaluate(grid);
    assert.equal(grid.length,n);assert.equal(new Set(grid.map(s=>`${s.x},${s.y}`)).size,n);
    assert.ok(grid.every(s=>s.angle===0&&Number.isInteger(s.x-.5)&&Number.isInteger(s.y-.5)));
    assert.equal(e.bounds.L,Math.ceil(Math.sqrt(n)));assert.equal(e.valid,true);
    score+=e.score;rows+=n;
  }
  assert.equal(rows,500500);assert.ok(Math.abs(score-28.937669916550586)<1e-11);
});
test('zero-angle edge and corner touches are allowed; positive 5e-10 overlap is not',()=>{
  assert.equal(P.evaluate([tile(.5),tile(1.5)]).valid,true);
  assert.equal(P.evaluate([tile(.5),tile(1.5,1.5)]).valid,true);
  assert.equal(P.evaluate([tile(.5),tile(1.5-5e-10)]).valid,false);
});
test('rotated overlap fails; borderline rotated contact is uncertain and blocked',()=>{
  assert.equal(P.evaluate([tile(0,0,Math.PI/4),tile(.1,0,Math.PI/4)]).valid,false);
  const e=P.evaluate([tile(0,0,Math.PI/4),tile(Math.SQRT1_2,Math.SQRT1_2,Math.PI/4)]);
  assert.equal(e.valid,false);assert.ok(e.hits.uncertainCount>0);
  assert.equal(P.evaluate([tile(0,0,Math.PI/4),tile(2,0,Math.PI/4)]).valid,true);
});
test('invalid placements do not expose misleading negative or improved scores',()=>{
  assert.equal(P.evaluate(Array.from({length:4},()=>tile(.5))).score,null);
  assert.equal(P.evaluate([]).valid,false);
  assert.equal(P.evaluate([tile(NaN)]).valid,false);
});
test('CSV rejects blanks, hex, NaN, infinity, duplicate ids, incomplete puzzles and empty files',()=>{
  for(const value of ['', '0x10','NaN','Infinity','1e9999'])
    assert.throws(()=>P.parseCsv(header+`0,1,0,${value},0.5,0\n`));
  assert.throws(()=>P.parseCsv(header+'0,2,0,0.5,0.5,0\n0,2,1,1.5,0.5,0\n'));
  assert.throws(()=>P.parseCsv(header+'0,2,0,0.5,0.5,0\n'));
  assert.throws(()=>P.parseCsv(header));
});
test('quoted columns, BOM and CRLF work and unchanged long decimals survive export',()=>{
  const source='\uFEFF"id","n","square_id","x","y","angle"\r\n"0","1","0","0.500000000000000000000000000001","0.5","0"\r\n';
  const layouts=P.parseCsv(source);
  assert.equal([...P.csvChunks(layouts,{onlyN:1})].join(''),header+'0,1,0,0.500000000000000000000000000001,0.5,0\n');
  layouts.get(1)[0].x=2.5;
  assert.match([...P.csvChunks(layouts,{onlyN:1})].join(''),/,2.5,0.5,0\n/);
});
test('sub-ULP decimal overlap is caught before a high-precision import can be called valid',()=>{
  assert.throws(()=>P.parseCsv(header+'0,2,0,0.5,0.5,0\n1,2,1,1.499999999999999999999999999999,0.5,0\n'));
});
test('editing a coordinate or rotation preserves the other imported decimal fields',()=>{
  const rawX='.500000000000000000001',rawY='.500000000000000000002';
  const t=P.parseCsv(header+`0,1,0,${rawX},${rawY},0\n`).get(1)[0];
  P.updateTile(t,{angle:Math.PI/36});
  assert.equal(P.numericText(t,'x'),rawX);assert.equal(P.numericText(t,'y'),rawY);
  P.updateTile(t,{x:.55,y:.5});
  assert.equal(P.numericText(t,'x'),'0.55');assert.equal(P.numericText(t,'y'),rawY);
});
test('default export has every required row and sequential ids',()=>{
  let rows=0,expectedN=1,sid=0;
  for(const chunk of P.csvChunks(new Map()))for(const line of chunk.trimEnd().split('\n')){
    if(line==='id,n,square_id,x,y,angle')continue;
    const a=line.split(',');assert.equal(a.length,6);
    assert.equal(+a[0],rows++);assert.equal(+a[1],expectedN);assert.equal(+a[2],sid++);
    assert.equal(+a[5],0);
    if(sid===expectedN){expectedN++;sid=0;}
  }
  assert.equal(rows,500500);assert.equal(expectedN,1001);
});
test('one-puzzle export is separate; full export incorporates edits and blocks invalid edits',()=>{
  const layouts=new Map([[2,[tile(3.5),tile(4.5)]]]);
  assert.equal([...P.csvChunks(layouts,{onlyN:2})].join(''),header+'0,2,0,3.5,0.5,0\n1,2,1,4.5,0.5,0\n');
  assert.match([...P.csvChunks(layouts,{maxN:2})].join(''),/1,2,0,3.5/);
  layouts.set(2,[tile(0),tile(0)]);
  assert.throws(()=>[...P.csvChunks(layouts)]);
});
