/* Independent geometry and CSV implementation for the organizer-described grid
   baseline. Floating-point SAT is deliberately conservative near rotated contact;
   it is NOT the official interval-arithmetic certifier. MIT, Kaggle Lab. */
'use strict';
((root, factory) => {
  const api=factory();
  if(typeof module==='object' && module.exports) module.exports=api;
  else root.PackingCore=api;
})(typeof globalThis!=='undefined'?globalThis:this, () => {
  const MAX_N=1000, HEADER='id,n,square_id,x,y,angle';
  const DECIMAL=/^[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?$/;
  const CONTACT_EPS=1e-9;
  function checkN(n){if(!Number.isInteger(n)||n<1||n>MAX_N)throw Error('n 必须是 1–1000 的整数');}
  function makeGrid(n){
    checkN(n);const m=Math.ceil(Math.sqrt(n));
    return Array.from({length:n},(_,i)=>({x:i%m+.5,y:Math.floor(i/m)+.5,angle:0}));
  }
  let constructiveTemplates;
  function makeConstructive(n){
    checkN(n);
    if(!constructiveTemplates){
      constructiveTemplates=[];
      const finish=(tiles,L,method,parameters)=>{
        tiles=tiles.map(t=>({x:(t.x-L/2)*1.00000004,y:(t.y-L/2)*1.00000004,angle:t.angle}));
        tiles.sort((a,b)=>(a.x*a.x+a.y*a.y)-(b.x*b.x+b.y*b.y)||a.x-b.x||a.y-b.y||a.angle-b.angle);
        let minX=Infinity,minY=Infinity,maxX=-Infinity,maxY=-Infinity;
        const prefix=tiles.map(t=>{const h=(Math.abs(Math.cos(t.angle))+Math.abs(Math.sin(t.angle)))/2;
          minX=Math.min(minX,t.x-h);maxX=Math.max(maxX,t.x+h);minY=Math.min(minY,t.y-h);maxY=Math.max(maxY,t.y+h);
          return Math.max(maxX-minX,maxY-minY);});
        constructiveTemplates.push({tiles,prefix,method,parameters});
      };
      const corners=(tiles,x,y,L)=>{for(const [a,b] of [[x,y],[L-x,y],[x,L-y],[L-x,L-y]])tiles.push({x:a,y:b,angle:0});};
      // Same independently derived corner/core families as constructions.py.
      for(let k=1;4*k*k+1<=1089;k++){
        const L=2*k+Math.SQRT1_2,tiles=[{x:L/2,y:L/2,angle:Math.PI/4}];
        for(let i=0;i<k;i++)for(let j=0;j<k;j++)corners(tiles,i+.5,j+.5,L);
        finish(tiles,L,'four-corners',{k});
      }
      for(let m=2;2*m*(m-1)<1089;m++)for(let b=1;b*b<=2*m*m;b++){
        if(b*b<2*(m-2)**2||2*m*(m-1)+b*b>1089)continue;
        const L=m+b/Math.SQRT2,tiles=[];
        for(let i=0;i<b;i++)for(let j=0;j<b;j++){
          const u=i-(b-1)/2,v=j-(b-1)/2;
          tiles.push({x:L/2+(u-v)/Math.SQRT2,y:L/2+(u+v)/Math.SQRT2,angle:Math.PI/4});
        }
        for(let i=0;i<m-1;i++)for(let j=0;j<m-1-i;j++)corners(tiles,i+.5,j+.5,L);
        finish(tiles,L,'diamond-staircase',{m,b});
      }
    }
    let best={tiles:makeGrid(n),method:'grid',sourceN:n,parameters:{},L:Math.ceil(Math.sqrt(n))};
    for(const c of constructiveTemplates)if(c.tiles.length>=n&&c.prefix[n-1]<best.L-1e-12){
      best={tiles:c.tiles.slice(0,n).map(t=>({...t})),method:c.method+(c.tiles.length===n?'':'/drop'),sourceN:c.tiles.length,parameters:{...c.parameters},L:c.prefix[n-1]};
    }
    return best;
  }
  function decimal(value){if(!Number.isFinite(value))throw Error('坐标必须为有限数');return String(Object.is(value,-0)?0:value);}
  function numericText(tile,key){
    const raw=tile.raw?.[key];
    return raw!==undefined&&Number(raw)===tile[key]?raw:decimal(tile[key]);
  }
  function updateTile(tile,changes){
    for(const key of ['x','y','angle'])if(key in changes&&changes[key]!==tile[key]){
      if(tile.raw)delete tile.raw[key];
      tile[key]=changes[key];
    }
  }
  // Decimal arithmetic is only needed near a zero-angle contact. Ordinary grids
  // use exactly representable half-integers. Retained source strings also detect
  // a positive overlap smaller than a double's unit in the last place.
  function decimalParts(text){
    const [mantissa,exp='0']=text.toLowerCase().split('e');
    const negative=mantissa.startsWith('-'),digits=mantissa.replace(/^[+-]/,'').split('.');
    return {v:BigInt((negative?'-':'')+(digits[0]||'0')+(digits[1]||'')),e:Number(exp)-(digits[1]||'').length};
  }
  function separatedExactly(a,b,key){
    const aa=decimalParts(numericText(a,key)),bb=decimalParts(numericText(b,key));
    const e=Math.min(aa.e,bb.e,0);
    const d=aa.v*10n**BigInt(aa.e-e)-bb.v*10n**BigInt(bb.e-e);
    return (d<0n?-d:d)>=10n**BigInt(-e);
  }
  function getBounds(placed){
    let minX=Infinity,maxX=-Infinity,minY=Infinity,maxY=-Infinity;
    for(const s of placed){
      const h=(Math.abs(Math.cos(s.angle))+Math.abs(Math.sin(s.angle)))*.5;
      minX=Math.min(minX,s.x-h);maxX=Math.max(maxX,s.x+h);
      minY=Math.min(minY,s.y-h);maxY=Math.max(maxY,s.y+h);
    }
    return {minX,maxX,minY,maxY,width:maxX-minX,height:maxY-minY,L:Math.max(maxX-minX,maxY-minY)};
  }
  function penetration(a,b){
    const dx=b.x-a.x,dy=b.y-a.y;
    if(Math.abs(dx)>Math.SQRT2+CONTACT_EPS||Math.abs(dy)>Math.SQRT2+CONTACT_EPS)return null;
    // Exact zero rotation must mean exact zero in the submitted text too.
    const axisAligned=a.angle===0&&b.angle===0&&decimalParts(numericText(a,'angle')).v===0n&&decimalParts(numericText(b,'angle')).v===0n;
    if(axisAligned){
      const px=1-Math.abs(dx),py=1-Math.abs(dy);
      if(px < -CONTACT_EPS || py < -CONTACT_EPS)return null;
      if(Math.abs(px)<=CONTACT_EPS&&separatedExactly(a,b,'x'))return null;
      if(Math.abs(py)<=CONTACT_EPS&&separatedExactly(a,b,'y'))return null;
      return px<=py?{depth:Math.max(px,Number.EPSILON),nx:dx<0?-1:1,ny:0,uncertain:false}
        :{depth:Math.max(py,Number.EPSILON),nx:0,ny:dy<0?-1:1,uncertain:false};
    }
    const ca=Math.cos(a.angle),sa=Math.sin(a.angle),cb=Math.cos(b.angle),sb=Math.sin(b.angle);
    let best=Infinity,nx=0,ny=0;
    for(const [ax,ay] of [[ca,sa],[-sa,ca],[cb,sb],[-sb,cb]]){
      const ra=.5*(Math.abs(ca*ax+sa*ay)+Math.abs(-sa*ax+ca*ay));
      const rb=.5*(Math.abs(cb*ax+sb*ay)+Math.abs(-sb*ax+cb*ay));
      const along=dx*ax+dy*ay,depth=ra+rb-Math.abs(along);
      if(depth < -CONTACT_EPS)return null;
      if(depth<best){best=depth;const sign=along<0?-1:1;nx=ax*sign;ny=ay*sign;}
    }
    return {depth:Math.max(best,0),nx,ny,uncertain:best<=CONTACT_EPS};
  }
  function collisions(placed,withPairs=false){
    const buckets=new Map(),pairs=[],colliding=new Set();let count=0,uncertainCount=0;
    for(let i=0;i<placed.length;i++){
      const s=placed[i],gx=Math.floor(s.x/2),gy=Math.floor(s.y/2);
      for(let ox=-1;ox<=1;ox++)for(let oy=-1;oy<=1;oy++)for(const j of buckets.get(`${gx+ox},${gy+oy}`)||[]){
        const p=penetration(placed[j],s);
        if(p){count++;if(p.uncertain)uncertainCount++;colliding.add(i);colliding.add(j);if(withPairs)pairs.push([j,i,p]);}
      }
      const key=`${gx},${gy}`;if(!buckets.has(key))buckets.set(key,[]);buckets.get(key).push(i);
    }
    return {count,uncertainCount,colliding,pairs};
  }
  function evaluate(placed){
    const finite=placed.length>0&&placed.every(s=>s&&[s.x,s.y,s.angle].every(Number.isFinite)&&Math.abs(s.x)<=1e6&&Math.abs(s.y)<=1e6&&Math.abs(s.angle)<=1000);
    if(!finite)return {valid:false,score:null,density:null,bounds:{L:NaN},hits:{count:0,uncertainCount:0,colliding:new Set(),pairs:[]}};
    const bounds=getBounds(placed),hits=collisions(placed);
    const valid=hits.count===0&&Number.isFinite(bounds.L)&&bounds.L>=Math.sqrt(placed.length)-1e-9;
    return {bounds,hits,valid,score:valid?Math.max(0,bounds.L/Math.sqrt(placed.length)-1):null,density:placed.length/bounds.L**2};
  }
  function parseLine(line,lineNo){
    const cells=[];let field='',quoted=false,ended=false;
    for(let i=0;i<line.length;i++){
      const c=line[i];
      if(quoted){if(c==='"'){if(line[i+1]==='"'){field+='"';i++;}else{quoted=false;ended=true;}}else field+=c;}
      else if(c===','){cells.push(field);field='';ended=false;}
      else if(c==='"'&&field===''&&!ended)quoted=true;
      else if(c==='"'||ended)throw Error(`第 ${lineNo} 行 CSV 引号格式错误`);
      else field+=c;
    }
    if(quoted)throw Error(`第 ${lineNo} 行 CSV 引号未闭合`);
    cells.push(field);return cells;
  }
  function readDecimal(text,lineNo){
    const raw=text.trim();
    // Local resource limits prevent hostile exponents from allocating huge BigInts.
    if(!DECIMAL.test(raw)||raw.length>2048||Math.abs(Number(raw.split(/[eE]/)[1]||0))>2048||!Number.isFinite(Number(raw)))
      throw Error(`第 ${lineNo} 行：需有限十进制数（最多 2048 字符，指数绝对值 ≤ 2048）`);
    return raw;
  }
  function parseCsv(text){
    const lines=text.replace(/^\uFEFF/,'').split(/\r?\n/);
    if(parseLine(lines[0],1).join(',')!==HEADER)throw Error(`CSV 表头应为 ${HEADER}`);
    const temp=new Map();let rowId=0;
    for(let i=1;i<lines.length;i++){
      if(!lines[i].trim())continue;
      const f=parseLine(lines[i],i+1);
      if(f.length!==6)throw Error(`第 ${i+1} 行应有六列`);
      if(!f.slice(0,3).every(s=>/^\d+$/.test(s.trim())))throw Error(`第 ${i+1} 行：id、n、square_id 必须是非负整数`);
      const id=Number(f[0]),n=Number(f[1]),sid=Number(f[2]);checkN(n);
      if(id!==rowId++)throw Error(`第 ${i+1} 行：id 应从 0 连续递增`);
      if(!Number.isInteger(sid)||sid>=n)throw Error(`第 ${i+1} 行：square_id 超出范围`);
      const raw={x:readDecimal(f[3],i+1),y:readDecimal(f[4],i+1),angle:readDecimal(f[5],i+1)};
      const tile={x:Number(raw.x),y:Number(raw.y),angle:Number(raw.angle),raw};
      // Very large translations/angles make double precision unsuitable for editing.
      if(Math.abs(tile.x)>1e6||Math.abs(tile.y)>1e6||Math.abs(tile.angle)>1000)
        throw Error(`第 ${i+1} 行超出本地编辑器数值范围：|x|、|y| ≤ 10⁶，|angle| ≤ 1000`);
      if(!temp.has(n))temp.set(n,Array(n).fill(null));
      if(temp.get(n)[sid])throw Error(`第 ${i+1} 行：重复 square_id`);
      temp.get(n)[sid]=tile;
    }
    if(!rowId)throw Error('CSV 没有数据行');
    for(const [n,placed] of temp){
      if(placed.some(s=>s===null))throw Error(`n=${n}：必须恰好有 ${n} 个正方形`);
      assertExportable(n,placed);
    }
    return temp;
  }
  function assertExportable(n,placed){
    if(placed.length!==n)throw Error(`n=${n}：正方形数量错误`);
    const e=evaluate(placed);
    if(!e.valid)throw Error(`n=${n}：存在重叠或无法确定的接触（${e.hits.uncertainCount} 对不确定接触），请调整后再导出`);
    return e;
  }
  function* csvChunks(layouts=new Map(),{maxN=MAX_N,onlyN=null}={}){
    checkN(maxN);if(onlyN!==null)checkN(onlyN);
    const start=onlyN??1,end=onlyN??maxN;
    // Validate every edit before yielding any file content. Unchanged grids have
    // an exact construction proof and need no expensive pairwise revalidation.
    for(const [n,placed] of layouts)if(n>=start&&n<=end)assertExportable(n,placed);
    yield HEADER+'\n';let id=0,chunk='';
    for(let n=start;n<=end;n++){
      const placed=layouts.get(n)||makeGrid(n);
      for(let k=0;k<n;k++){
        const s=placed[k];chunk+=`${id++},${n},${k},${numericText(s,'x')},${numericText(s,'y')},${numericText(s,'angle')}\n`;
      }
      if(chunk.length>500000){yield chunk;chunk='';}
    }
    if(chunk)yield chunk;
  }
  return {MAX_N,HEADER,makeGrid,makeConstructive,getBounds,penetration,collisions,evaluate,parseCsv,csvChunks,numericText,updateTile};
});
