/* Kaggle Lab Square Packing Studio — an original, dependency-free implementation.
   Coordinates and angles follow the Kaggle Squares in Squares submission schema. */
'use strict';
(() => {
  const $ = id => document.getElementById(id);
  const canvas = $('stage'), ctx = canvas.getContext('2d');
  const layouts = new Map();
  const SQRT2 = Math.SQRT2;
  const scoreFmt = v => Number.isFinite(v) ? v.toFixed(8) : '—';
  let n = 5, selected = -1, dragging = null, dpr = 1;
  let zoom = 1, cameraX = 1.5, cameraY = 1.5, canvasW = 800, canvasH = 500;
  let layoutTag = 'grid baseline', running = false;

  function makeGrid(count) {
    const columns = Math.ceil(Math.sqrt(count));
    return Array.from({length:count}, (_,i) => ({x:(i%columns)+0.5, y:Math.floor(i/columns)+0.5, angle:0}));
  }
  function current() { if(!layouts.has(n)) layouts.set(n,makeGrid(n)); return layouts.get(n); }
  function corners(s) {
    const c = Math.cos(s.angle), t = Math.sin(s.angle);
    return [[-0.5,-0.5],[0.5,-0.5],[0.5,0.5],[-0.5,0.5]].map(([u,v])=>[s.x+u*c-v*t,s.y+u*t+v*c]);
  }
  function getBounds(placed) {
    let minX=Infinity,maxX=-Infinity,minY=Infinity,maxY=-Infinity;
    for (const s of placed) {
      const h=(Math.abs(Math.cos(s.angle))+Math.abs(Math.sin(s.angle)))*0.5;
      minX=Math.min(minX,s.x-h);maxX=Math.max(maxX,s.x+h);
      minY=Math.min(minY,s.y-h);maxY=Math.max(maxY,s.y+h);
    }
    const width=maxX-minX,height=maxY-minY;
    return {minX,maxX,minY,maxY,width,height,L:Math.max(width,height)};
  }
  function penetration(a,b) {
    // SAT: test both edge-normal directions of each square.
    const dx=b.x-a.x,dy=b.y-a.y;
    if (Math.abs(dx)>=SQRT2+1e-9 || Math.abs(dy)>=SQRT2+1e-9) return null;
    const ca=Math.cos(a.angle),sa=Math.sin(a.angle),cb=Math.cos(b.angle),sb=Math.sin(b.angle);
    const axes=[[ca,sa],[-sa,ca],[cb,sb],[-sb,cb]];
    let best=Infinity,normalX=0,normalY=0;
    for (const [ax,ay] of axes) {
      const ra=0.5*(Math.abs(ca*ax+sa*ay)+Math.abs(-sa*ax+ca*ay));
      const rb=0.5*(Math.abs(cb*ax+sb*ay)+Math.abs(-sb*ax+cb*ay));
      const along=dx*ax+dy*ay,depth=ra+rb-Math.abs(along);
      if (depth<=1e-9) return null; // edge touch is allowed; numerical tolerance is not certification
      if (depth<best) {best=depth;const sign=along<0?-1:1;normalX=ax*sign;normalY=ay*sign;}
    }
    return {depth:best,nx:normalX,ny:normalY};
  }
  function collisions(placed,withPairs=false) {
    // Square centers of overlapping unit tiles are at most sqrt(2) apart on either axis.
    const buckets=new Map(),pairs=[],colliding=new Set();let count=0;
    for (let i=0;i<placed.length;i++) {
      const s=placed[i],gx=Math.floor(s.x/2),gy=Math.floor(s.y/2);
      for(let ox=-1;ox<=1;ox++)for(let oy=-1;oy<=1;oy++){
        for(const j of buckets.get(`${gx+ox},${gy+oy}`)||[]) {
          const p=penetration(placed[j],s);
          if(p){count++;colliding.add(i);colliding.add(j);if(withPairs)pairs.push([j,i,p]);}
        }
      }
      const key=`${gx},${gy}`;
      if(!buckets.has(key))buckets.set(key,[]);
      buckets.get(key).push(i);
    }
    return {count,colliding,pairs};
  }
  function evaluate(placed) {
    const bounds=getBounds(placed),hits=collisions(placed);
    const valid=hits.count===0&&Number.isFinite(bounds.L)&&placed.every(s=>Number.isFinite(s.x)&&Number.isFinite(s.y)&&Number.isFinite(s.angle));
    return {bounds,valid,hits,score:bounds.L/Math.sqrt(placed.length)-1,density:placed.length/(bounds.L*bounds.L)};
  }
  function colorMessage(text){$('message').textContent=text;}
  function syncMetrics() {
    const e=evaluate(current());
    $('sideStat').textContent=e.bounds.L.toFixed(6);
    $('scoreStat').textContent=scoreFmt(e.score);
    $('densityStat').textContent=(e.density*100).toFixed(2)+'%';
    $('validStat').textContent=e.valid?'VALID':'OVERLAP';
    $('validNote').textContent=e.valid?'local SAT check passed':`${e.hits.count} overlapping pairs`;
    $('validStat').closest('.stat').className='stat '+(e.valid?'good':'bad');
    $('selectedLabel').textContent=selected<0?'none':`#${selected}`;
    $('rotateLeft').disabled=selected<0||running;
    $('rotateRight').disabled=selected<0||running;
    $('layoutName').textContent=layoutTag;
    return e;
  }
  function fit() {
    const b=getBounds(current());cameraX=(b.minX+b.maxX)/2;cameraY=(b.minY+b.maxY)/2;zoom=1;draw();
  }
  function resize() {
    const r=canvas.getBoundingClientRect();canvasW=Math.max(200,r.width);canvasH=Math.max(200,r.height);
    dpr=Math.min(2,window.devicePixelRatio||1);canvas.width=Math.round(canvasW*dpr);canvas.height=Math.round(canvasH*dpr);draw();
  }
  function scale() {return Math.max(1,Math.min(canvasW,canvasH)/(getBounds(current()).L+2.4)*zoom);}
  function worldToScreen(x,y,s=scale()) {return [canvasW/2+(x-cameraX)*s,canvasH/2-(y-cameraY)*s];}
  function screenToWorld(px,py,s=scale()) {return {x:cameraX+(px-canvasW/2)/s,y:cameraY-(py-canvasH/2)/s};}
  function draw() {
    if(!ctx)return;
    const placed=current(),e=syncMetrics(),s=scale();
    ctx.setTransform(dpr,0,0,dpr,0,0);ctx.clearRect(0,0,canvasW,canvasH);
    ctx.lineWidth=1;ctx.strokeStyle='rgba(110,145,180,0.065)';
    const step=Math.max(1,Math.ceil(24/s));
    const topLeft=screenToWorld(0,0,s),bottomRight=screenToWorld(canvasW,canvasH,s);
    const firstX=Math.floor(topLeft.x/step)*step,lastX=bottomRight.x;
    const firstY=Math.floor(bottomRight.y/step)*step,lastY=topLeft.y;
    for(let x=firstX;x<=lastX;x+=step){const [xx]=worldToScreen(x,0,s);ctx.beginPath();ctx.moveTo(xx,0);ctx.lineTo(xx,canvasH);ctx.stroke();}
    for(let y=firstY;y<=lastY;y+=step){const [,yy]=worldToScreen(0,y,s);ctx.beginPath();ctx.moveTo(0,yy);ctx.lineTo(canvasW,yy);ctx.stroke();}
    const b=e.bounds,L=b.L,x0=(b.minX+b.maxX-L)/2,y0=(b.minY+b.maxY-L)/2;
    const [bx,by]=worldToScreen(x0,y0+L,s);
    ctx.fillStyle='rgba(93,233,205,0.024)';ctx.fillRect(bx,by,L*s,L*s);
    ctx.setLineDash([8,6]);ctx.strokeStyle='#edb777';ctx.lineWidth=1.8;ctx.strokeRect(bx,by,L*s,L*s);ctx.setLineDash([]);
    ctx.fillStyle='#e9bb7d';ctx.font='11px ui-monospace,monospace';ctx.fillText(`L = ${L.toFixed(4)}`,bx+8,by-12);
    for (let i=0;i<placed.length;i++) {
      const sq=placed[i],pt=worldToScreen(sq.x,sq.y,s),isBad=e.hits.colliding.has(i),sel=i===selected;
      if(pt[0]<-s*2||pt[0]>canvasW+s*2||pt[1]<-s*2||pt[1]>canvasH+s*2)continue;
      ctx.save();ctx.translate(pt[0],pt[1]);ctx.rotate(-sq.angle);
      ctx.fillStyle=isBad?'rgba(225,75,109,.56)':sel?'rgba(83,197,244,.6)':(i%5===0?'rgba(48,123,132,.79)':'rgba(42,114,119,.72)');
      ctx.fillRect(-s/2,-s/2,s,s);
      ctx.lineWidth=sel?2.5:(s>=10?1.2:.7);
      ctx.strokeStyle=isBad?'#ff8da4':sel?'#b2ebff':'#77ebd2';
      ctx.strokeRect(-s/2,-s/2,s,s);
      if(sel){ctx.strokeStyle='rgba(180,236,255,.8)';ctx.lineWidth=1;ctx.strokeRect(-s/2-4,-s/2-4,s+8,s+8);}
      if(placed.length<=90&&s>22){ctx.fillStyle='#d4fff7';ctx.font=`${Math.min(12,Math.max(8,s*.23))}px ui-monospace,monospace`;ctx.textAlign='center';ctx.textBaseline='middle';ctx.fillText(i,0,1);}
      ctx.restore();
    }
    // Crosshair at origin is a display-only reference.
    const [ox,oy]=worldToScreen(0,0,s);
    ctx.strokeStyle='#6885a3';ctx.lineWidth=1;ctx.beginPath();ctx.moveTo(ox-6,oy);ctx.lineTo(ox+6,oy);ctx.moveTo(ox,oy-6);ctx.lineTo(ox,oy+6);ctx.stroke();
  }
  function changeCount(next) {
    if(running)return;
    const value=Math.max(1,Math.min(1000,Math.round(Number(next)||1)));
    n=value;selected=-1;layoutTag=layouts.has(n)?'saved layout':'grid baseline';
    $('count').value=value;$('countRange').value=value;
    document.querySelectorAll('.preset').forEach(b=>b.classList.toggle('active',Number(b.dataset.count)===n));
    fit();colorMessage(`Puzzle n=${n}. ${layouts.has(n)?'Saved edits restored.':'Grid baseline loaded.'}`);
  }
  function hitTest(p) {
    const placed=current();
    for(let i=placed.length-1;i>=0;i--){const q=placed[i],c=Math.cos(q.angle),t=Math.sin(q.angle),dx=p.x-q.x,dy=p.y-q.y;
      if(Math.abs(dx*c+dy*t)<=.5&&Math.abs(-dx*t+dy*c)<=.5)return i;
    }return -1;
  }
  function changeAngle(delta){if(selected<0||running)return;current()[selected].angle+=delta;layoutTag='manually edited';draw();}
  function localPoint(evt){const box=canvas.getBoundingClientRect();return {x:evt.clientX-box.left,y:evt.clientY-box.top};}
  canvas.addEventListener('pointerdown',evt=>{
    if(running)return;const mouse=localPoint(evt),world=screenToWorld(mouse.x,mouse.y);
    if(evt.shiftKey||evt.button===1){dragging={type:'pan',startMouse:mouse,x:cameraX,y:cameraY};}
    else {selected=hitTest(world);if(selected>=0){const item=current()[selected];dragging={type:'square',i:selected,dx:item.x-world.x,dy:item.y-world.y};layoutTag='manually edited';}else dragging=null;}
    canvas.classList.add('dragging');canvas.setPointerCapture(evt.pointerId);draw();
  });
  canvas.addEventListener('pointermove',evt=>{
    const mouse=localPoint(evt),p=screenToWorld(mouse.x,mouse.y);
    $('coordReadout').textContent=`x: ${p.x.toFixed(3)}  y: ${p.y.toFixed(3)}`;
    if(!dragging)return;
    if(dragging.type==='pan') {const s=scale();cameraX=dragging.x-(mouse.x-dragging.startMouse.x)/s;cameraY=dragging.y+(mouse.y-dragging.startMouse.y)/s;}
    else {const tile=current()[dragging.i];tile.x=p.x+dragging.dx;tile.y=p.y+dragging.dy;}
    draw();
  });
  function stopDrag(){if(dragging&&dragging.type==='square'){const e=evaluate(current());colorMessage(e.valid?'Edited layout is locally feasible.':'Overlapping squares detected — resolve before exporting.');}dragging=null;canvas.classList.remove('dragging');}
  canvas.addEventListener('pointerup',stopDrag);canvas.addEventListener('pointercancel',stopDrag);
  canvas.addEventListener('wheel',evt=>{evt.preventDefault();zoom=Math.min(12,Math.max(.15,zoom*Math.exp(-evt.deltaY*.001)));draw();},{passive:false});
  window.addEventListener('keydown',evt=>{
    if(running||selected<0||['INPUT','TEXTAREA'].includes(document.activeElement.tagName))return;
    const delta=.05,sq=current()[selected];let changed=true;
    if(evt.key==='ArrowLeft')sq.x-=delta;else if(evt.key==='ArrowRight')sq.x+=delta;
    else if(evt.key==='ArrowUp')sq.y+=delta;else if(evt.key==='ArrowDown')sq.y-=delta;
    else if(evt.key==='[')sq.angle-=Math.PI/36;else if(evt.key===']')sq.angle+=Math.PI/36;else changed=false;
    if(changed){evt.preventDefault();layoutTag='manually edited';draw();}
  });
  function decimal(value) {if(!Number.isFinite(value))throw Error('Non-finite coordinate');return String(Object.is(value,-0)?0:value);}
  function csvParts(limit,onlyN=null) {
    const parts=['id,n,square_id,x,y,angle\n'];let section='',id=0;
    const start=onlyN||1,end=onlyN||limit;
    for(let puzzle=start;puzzle<=end;puzzle++){
      const placed=layouts.get(puzzle)||makeGrid(puzzle);
      if(placed.length!==puzzle)throw Error(`n=${puzzle}: unexpected square count`);
      const e=evaluate(placed);if(!e.valid)throw Error(`n=${puzzle}: ${e.hits.count} overlapping pairs. Export blocked.`);
      for(let k=0;k<placed.length;k++){
        const p=placed[k];section+=`${id++},${puzzle},${k},${decimal(p.x)},${decimal(p.y)},${decimal(p.angle)}\n`;
        if(section.length>650000){parts.push(section);section='';}
      }
    }
    if(section)parts.push(section);
    return {parts,rows:id};
  }
  function downloadCsv(limit,onlyN=null) {
    try{
      const {parts,rows}=csvParts(limit,onlyN);
      const blob=new Blob(parts,{type:'text/csv;charset=utf-8'}),url=URL.createObjectURL(blob),a=document.createElement('a');
      a.href=url;a.download=onlyN?`squares-n${String(onlyN).padStart(4,'0')}.csv`:'submission.csv';
      document.body.appendChild(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),1500);
      colorMessage(`${rows.toLocaleString()} rows exported. Validate using the official Kaggle metric before submission.`);
    }catch(error){colorMessage('Export refused: '+error.message);}
  }
  async function loadCsv(file) {
    if(!file)return;
    const text=await file.text(),lines=text.replace(/^\uFEFF/,'').split(/\r?\n/);
    if(lines[0].trim()!=='id,n,square_id,x,y,angle')throw Error('Invalid header; expected id,n,square_id,x,y,angle');
    const temp=new Map();let rows=0;
    for(let i=1;i<lines.length;i++){
      const line=lines[i].trim();if(!line)continue;
      const fields=line.split(',');if(fields.length!==6)throw Error(`Line ${i+1}: expected six columns`);
      const puzzle=Number(fields[1]),idx=Number(fields[2]),x=Number(fields[3]),y=Number(fields[4]),angle=Number(fields[5]);
      if(!Number.isInteger(puzzle)||puzzle<1||puzzle>1000||!Number.isInteger(idx)||idx<0||idx>=puzzle||![x,y,angle].every(Number.isFinite))throw Error(`Line ${i+1}: invalid values`);
      if(!temp.has(puzzle))temp.set(puzzle,Array(puzzle));
      if(temp.get(puzzle)[idx])throw Error(`Line ${i+1}: duplicate square_id`);
      temp.get(puzzle)[idx]={x,y,angle};rows++;
    }
    for(const [puzzle,placed] of temp){
      if(placed.some(v=>!v)||placed.filter(Boolean).length!==puzzle)throw Error(`n=${puzzle}: incomplete layout`);
      const check=evaluate(placed);if(!check.valid)throw Error(`n=${puzzle}: ${check.hits.count} overlaps`);
    }
    for(const [puzzle,placed] of temp)layouts.set(puzzle,placed);
    selected=-1;layoutTag='imported CSV';fit();colorMessage(`Imported ${rows.toLocaleString()} rows covering ${temp.size} complete valid puzzles.`);
  }
  async function compactExperiment() {
    if(running)return;
    if(n>80){colorMessage('Experimental compaction is limited to n ≤ 80. Change n to run it.');return;}
    const original=current(),base=evaluate(original);
    if(!base.valid){colorMessage('First fix any overlap: experimental search starts from a locally valid layout.');return;}
    if(base.bounds.L-Math.sqrt(n)<1e-7){colorMessage('Already at the area lower bound; no further compaction is possible.');return;}
    running=true;$('optimize').disabled=true;
    let best=original.map(s=>({...s})),bestL=base.bounds.L,success=0;
    const awaitFrame=()=>new Promise(resolve=>requestAnimationFrame(resolve));
    try{
      for(let attempt=0;attempt<6;attempt++){
        // Candidate search uses reduced containment and independent repulsion of overlapping tiles.
        // The final candidate is accepted only if a fresh SAT validation confirms feasibility.
        const target=bestL-(bestL-Math.sqrt(n))*Math.min(.22,.035+.023*attempt);
        if(target<=Math.sqrt(n)+1e-6)continue;
        const bbox=getBounds(best),srcCenterX=(bbox.minX+bbox.maxX)/2,srcCenterY=(bbox.minY+bbox.maxY)/2;
        const candidate=best.map(q=>({x:target/2+(q.x-srcCenterX)*(target/bestL),y:target/2+(q.y-srcCenterY)*(target/bestL),angle:q.angle}));
        for(let step=0;step<440;step++){
          const cooling=1-step/440;
          if(step%7===0){const j=Math.floor(Math.random()*n);candidate[j].angle+=(Math.random()-.5)*(.06*cooling);}
          // Repeatedly separate overlapping pairs along their least penetration axis.
          const hits=collisions(candidate,true);
          if(hits.count===0){const proposed=getBounds(candidate);if(proposed.L<bestL-1e-5){best=candidate.map(q=>({...q}));bestL=proposed.L;success++;}break;}
          for(const [i,j,p] of hits.pairs){const strength=Math.min(.36,p.depth*.34+0.00008);candidate[i].x-=p.nx*strength;candidate[i].y-=p.ny*strength;candidate[j].x+=p.nx*strength;candidate[j].y+=p.ny*strength;}
          for(const q of candidate){const half=.5*(Math.abs(Math.cos(q.angle))+Math.abs(Math.sin(q.angle)));
            q.x=Math.max(half,Math.min(target-half,q.x));q.y=Math.max(half,Math.min(target-half,q.y));}
          if(step%65===0){colorMessage(`Exploring target L=${target.toFixed(4)} · attempt ${attempt+1}/6 · iteration ${step+1}`);await awaitFrame();}
        }
        await awaitFrame();
      }
      const finalEval=evaluate(best);
      if(success>0&&finalEval.valid&&finalEval.bounds.L<base.bounds.L-1e-5){layouts.set(n,best);layoutTag='experimental candidate';fit();colorMessage(`Improved L from ${base.bounds.L.toFixed(6)} to ${finalEval.bounds.L.toFixed(6)}. Revalidate with Kaggle.`);}
      else colorMessage('No feasible improvement found in this short search. Original layout preserved.');
    }finally{running=false;$('optimize').disabled=false;draw();}
  }
  $('count').addEventListener('change',e=>changeCount(e.target.value));$('countRange').addEventListener('input',e=>changeCount(e.target.value));
  document.querySelectorAll('.preset').forEach(b=>b.addEventListener('click',()=>changeCount(b.dataset.count)));
  $('resetLayout').addEventListener('click',()=>{if(running)return;layouts.set(n,makeGrid(n));selected=-1;layoutTag='grid baseline';fit();colorMessage(`Reset n=${n} to a guaranteed-feasible grid baseline.`);});
  $('rotateLeft').addEventListener('click',()=>changeAngle(-Math.PI/36));$('rotateRight').addEventListener('click',()=>changeAngle(Math.PI/36));
  $('fitView').addEventListener('click',fit);$('zoomIn').addEventListener('click',()=>{zoom*=1.25;draw();});$('zoomOut').addEventListener('click',()=>{zoom/=1.25;draw();});
  $('exportOne').addEventListener('click',()=>{if(!running)downloadCsv(n,n);});$('exportAll').addEventListener('click',()=>{if(!running)downloadCsv(1000);});
  $('importCSV').addEventListener('click',()=>$('fileInput').click());$('fileInput').addEventListener('change',async e=>{try{await loadCsv(e.target.files[0]);}catch(err){colorMessage(`Import rejected: ${err.message}`);}finally{e.target.value='';}});
  $('optimize').addEventListener('click',compactExperiment);
  window.addEventListener('resize',resize);fit();resize();
})();
