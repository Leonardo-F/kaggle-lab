/* Kaggle Lab Square Packing Studio — an original, dependency-free implementation.
   Coordinates and angles follow the Kaggle Squares in Squares submission schema. */
'use strict';
(() => {
  const $ = id => document.getElementById(id);
  const canvas = $('stage'), ctx = canvas.getContext('2d');
  const layouts = new Map();
  const {makeGrid,getBounds,collisions,evaluate,parseCsv,csvChunks,updateTile}=PackingCore;
  const tags=new Map();
  let viewL=32;
  const scoreFmt = v => Number.isFinite(v) ? v.toFixed(8) : '—';
  let n = 1000, selected = -1, dragging = null, dpr = 1;
  let zoom = 1, cameraX = 1.5, cameraY = 1.5, canvasW = 800, canvasH = 500;
  let layoutTag = '赛题网格基线', running = false;

  function current() { if(!layouts.has(n)) layouts.set(n,makeGrid(n)); return layouts.get(n); }
  function colorMessage(text){$('message').textContent=text;}
  function syncMetrics() {
    const e=evaluate(current());
    $('sideStat').textContent=e.bounds.L.toFixed(6);
    $('scoreStat').textContent=scoreFmt(e.score);
    $('densityStat').textContent=(e.density*100).toFixed(2)+'%';
    $('validStat').textContent=e.valid?'本地通过':e.hits.uncertainCount?'接触待核验':'存在重叠';
    $('validNote').textContent=e.valid?'本地几何检查；未调用官方认证':`${e.hits.count-e.hits.uncertainCount} 对重叠 / ${e.hits.uncertainCount} 对不确定`;
    $('validStat').closest('.stat').className='stat '+(e.valid?'good':'bad');
    $('selectedLabel').textContent=selected<0?'未选择':`#${selected}`;
    $('rotateLeft').disabled=selected<0||running;
    $('rotateRight').disabled=selected<0||running;
    $('layoutName').textContent=layoutTag;
    return e;
  }
  function fit() {
    const b=getBounds(current());viewL=b.L;cameraX=(b.minX+b.maxX)/2;cameraY=(b.minY+b.maxY)/2;zoom=1;draw();
  }
  function resize() {
    const r=canvas.getBoundingClientRect();canvasW=Math.max(200,r.width);canvasH=Math.max(200,r.height);
    dpr=Math.min(2,window.devicePixelRatio||1);canvas.width=Math.round(canvasW*dpr);canvas.height=Math.round(canvasH*dpr);draw();
  }
  function scale() {return Math.max(1,Math.min(canvasW,canvasH)/(viewL+2.4)*zoom);}
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
    const wasSaved=tags.has(value);
    n=value;selected=-1;layoutTag=tags.get(n)||'赛题网格基线';
    $('count').value=value;$('countRange').value=value;
    const m=Math.ceil(Math.sqrt(n));
    $('baselineTitle').textContent=`当前实例 n = ${n} · 网格基线参照 L₀ = ${m}`;
    $('baselineText').textContent=`${m} × ${m} 网格，放入 ${n} 个单位正方形，余 ${m*m-n} 个空位。基线可行，不代表最优解。`;
    document.querySelectorAll('.preset').forEach(b=>b.classList.toggle('active',Number(b.dataset.count)===n));
    fit();colorMessage(`n=${n}：${wasSaved?'已恢复此实例的编辑。':'已加载网格基线。'} 导出完整提交始终包含 1–1000。`);
  }
  function hitTest(p) {
    const placed=current();
    for(let i=placed.length-1;i>=0;i--){const q=placed[i],c=Math.cos(q.angle),t=Math.sin(q.angle),dx=p.x-q.x,dy=p.y-q.y;
      if(Math.abs(dx*c+dy*t)<=.5&&Math.abs(-dx*t+dy*c)<=.5)return i;
    }return -1;
  }
  function markEdited(){layoutTag='手动编辑';tags.set(n,layoutTag);}
  function changeAngle(delta){if(selected<0||running)return;const tile=current()[selected];updateTile(tile,{angle:tile.angle+delta});markEdited();draw();}
  function localPoint(evt){const box=canvas.getBoundingClientRect();return {x:evt.clientX-box.left,y:evt.clientY-box.top};}
  canvas.addEventListener('pointerdown',evt=>{
    if(running)return;const mouse=localPoint(evt),world=screenToWorld(mouse.x,mouse.y);
    if(evt.shiftKey||evt.button===1){dragging={type:'pan',startMouse:mouse,x:cameraX,y:cameraY};}
    else {selected=hitTest(world);if(selected>=0){const item=current()[selected];dragging={type:'square',i:selected,dx:item.x-world.x,dy:item.y-world.y};}else dragging=null;}
    canvas.classList.add('dragging');canvas.setPointerCapture(evt.pointerId);draw();
  });
  canvas.addEventListener('pointermove',evt=>{
    const mouse=localPoint(evt),p=screenToWorld(mouse.x,mouse.y);
    $('coordReadout').textContent=`x: ${p.x.toFixed(3)}  y: ${p.y.toFixed(3)}`;
    if(!dragging)return;
    if(dragging.type==='pan') {const s=scale();cameraX=dragging.x-(mouse.x-dragging.startMouse.x)/s;cameraY=dragging.y+(mouse.y-dragging.startMouse.y)/s;}
    else {const tile=current()[dragging.i];updateTile(tile,{x:p.x+dragging.dx,y:p.y+dragging.dy});markEdited();}
    draw();
  });
  function stopDrag(){if(dragging&&dragging.type==='square'){const e=evaluate(current());colorMessage(e.valid?'编辑布局通过本地检查。':'检测到重叠或不确定接触，请调整后再导出。');}dragging=null;canvas.classList.remove('dragging');}
  canvas.addEventListener('pointerup',stopDrag);canvas.addEventListener('pointercancel',stopDrag);
  canvas.addEventListener('wheel',evt=>{evt.preventDefault();zoom=Math.min(12,Math.max(.15,zoom*Math.exp(-evt.deltaY*.001)));draw();},{passive:false});
  window.addEventListener('keydown',evt=>{
    if(running||selected<0||['INPUT','TEXTAREA'].includes(document.activeElement.tagName))return;
    const delta=.05,sq=current()[selected];let changed=true;
    if(evt.key==='ArrowLeft')updateTile(sq,{x:sq.x-delta});else if(evt.key==='ArrowRight')updateTile(sq,{x:sq.x+delta});
    else if(evt.key==='ArrowUp')updateTile(sq,{y:sq.y+delta});else if(evt.key==='ArrowDown')updateTile(sq,{y:sq.y-delta});
    else if(evt.key==='[')updateTile(sq,{angle:sq.angle-Math.PI/36});else if(evt.key===']')updateTile(sq,{angle:sq.angle+Math.PI/36});else changed=false;
    if(changed){evt.preventDefault();markEdited();draw();}
  });
  function setBusy(value){
    running=value;dragging=null;
    document.querySelectorAll('button,input').forEach(el=>el.disabled=value);
    if(!value)syncMetrics();
  }
  const nextFrame=()=>new Promise(resolve=>setTimeout(resolve,0));
  async function downloadCsv(onlyN=null){
    if(running)return;setBusy(true);colorMessage('正在检查布局并生成 CSV…');
    try{
      await nextFrame();const parts=[];let bytes=0;
      for(const part of csvChunks(layouts,{onlyN})){
        parts.push(part);bytes+=part.length;
        colorMessage(`正在生成 CSV：${(bytes/1e6).toFixed(1)} MB…`);await nextFrame();
      }
      const blob=new Blob(parts,{type:'text/csv;charset=utf-8'}),url=URL.createObjectURL(blob),a=document.createElement('a');
      a.href=url;a.download=onlyN?`squares-n${String(onlyN).padStart(4,'0')}.csv`:'submission.csv';
      document.body.appendChild(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),60000);
      colorMessage(onlyN?`已导出 n=${onlyN} 的 ${onlyN} 行调试文件；完整参赛请使用 submission.csv。`:
        '已导出 submission.csv：1000 个实例、500,500 行。未编辑实例使用网格基线。');
    }catch(error){colorMessage('导出已阻止：'+error.message);}
    finally{setBusy(false);}
  }
  async function loadCsv(file){
    if(!file||running)return;setBusy(true);colorMessage('正在读取并检查 CSV…');
    try{
      if(file.size>100*1024*1024)throw Error('本地导入上限为 100 MB');
      const text=await file.text();await nextFrame();
      const temp=parseCsv(text); // Atomic: the existing work changes only after every puzzle passes.
      for(const [puzzle,placed] of temp){layouts.set(puzzle,placed);tags.set(puzzle,'导入的布局');}
      selected=-1;
      if(!temp.has(n))n=Math.min(...temp.keys());
      $('count').value=n;$('countRange').value=n;
      const m=Math.ceil(Math.sqrt(n));
      $('baselineTitle').textContent=`当前实例 n = ${n} · 网格基线参照 L₀ = ${m}`;
      $('baselineText').textContent=`${m} × ${m} 网格可容纳该实例；画布显示导入的布局。`;
      document.querySelectorAll('.preset').forEach(b=>b.classList.toggle('active',Number(b.dataset.count)===n));
      layoutTag=tags.get(n)||'赛题网格基线';fit();
      colorMessage(`已导入 ${temp.size} 个完整实例。未编辑的原始十进制精度会保留。完整导出自动补齐其余实例。`);
    }catch(error){colorMessage('导入已拒绝，原布局保留：'+error.message);}
    finally{setBusy(false);}
  }
  async function compactExperiment() {
    if(running)return;
    if(n>80){colorMessage('实验搜索仅用于 n ≤ 80，请先选择较小的实例。');return;}
    const original=current(),base=evaluate(original);
    if(!base.valid){colorMessage('请先解决重叠或不确定接触。');return;}
    if(base.bounds.L-Math.sqrt(n)<1e-7){colorMessage('当前布局已达到面积下界，无需继续压缩。');return;}
    setBusy(true);
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
          if(step%65===0){colorMessage(`探索目标 L=${target.toFixed(4)} · 第 ${attempt+1}/6 轮 · 步数 ${step+1}`);await awaitFrame();}
        }
        await awaitFrame();
      }
      const finalEval=evaluate(best);
      if(success>0&&finalEval.valid&&finalEval.bounds.L<base.bounds.L-1e-5){layouts.set(n,best);layoutTag='实验搜索候选';tags.set(n,layoutTag);fit();colorMessage(`L 从 ${base.bounds.L.toFixed(6)} 改进为 ${finalEval.bounds.L.toFixed(6)}。此候选仍需官方认证。`);}
      else colorMessage('本轮未找到可用改进，原布局已保留。');
    }finally{setBusy(false);draw();}
  }
  $('count').addEventListener('change',e=>changeCount(e.target.value));$('countRange').addEventListener('input',e=>changeCount(e.target.value));
  document.querySelectorAll('.preset').forEach(b=>b.addEventListener('click',()=>changeCount(b.dataset.count)));
  $('resetLayout').addEventListener('click',()=>{if(running)return;layouts.set(n,makeGrid(n));selected=-1;layoutTag='赛题网格基线';tags.delete(n);fit();colorMessage(`已将 n=${n} 恢复为无旋转网格基线。`);});
  $('rotateLeft').addEventListener('click',()=>changeAngle(-Math.PI/36));$('rotateRight').addEventListener('click',()=>changeAngle(Math.PI/36));
  $('fitView').addEventListener('click',fit);$('zoomIn').addEventListener('click',()=>{zoom=Math.min(12,zoom*1.25);draw();});$('zoomOut').addEventListener('click',()=>{zoom=Math.max(.15,zoom/1.25);draw();});
  $('exportOne').addEventListener('click',()=>{if(!running)downloadCsv(n);});$('exportAll').addEventListener('click',()=>{if(!running)downloadCsv();});
  $('exportTop').addEventListener('click',()=>downloadCsv());
  $('importCSV').addEventListener('click',()=>$('fileInput').click());$('fileInput').addEventListener('change',async e=>{try{await loadCsv(e.target.files[0]);}finally{e.target.value='';}});
  $('optimize').addEventListener('click',compactExperiment);
  window.addEventListener('resize',resize);changeCount(1000);resize();
})();
