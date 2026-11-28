import argparse,csv,json,subprocess,time,random,concurrent.futures
from collections import defaultdict
from pathlib import Path
ROOT=Path(__file__).resolve().parent

def arithmetic(op,a,b):
    if op=='+':return a+b
    if op=='-':return a-b
    if op=='*':return a*b
    if op=='/' and a%b==0:return a//b
    raise ValueError('illegal operation')

def replay(row,program):
    s=json.loads(row['starting_values']);ts=set(json.loads(row['targets']));L=int(row['value_limit']);R=int(row['registers']);regs=s+[None]*(R-len(s));seen=set(s)
    if len(program)>4096 or len(json.dumps(program,separators=(',',':')).encode())>131072:raise ValueError('program too long')
    for op,i,j,d in program:
        if not all(isinstance(k,int) and 0<=k<R for k in (i,j,d)) or regs[i] is None or regs[j] is None:raise ValueError('register')
        v=arithmetic(op,regs[i],regs[j]);
        if not 1<=v<=L:raise ValueError('value bounds')
        regs[d]=v;seen.add(v)
    if not ts<=seen:raise ValueError('missing targets')
    return len(program)

def compile_graph(row,graph,tries=8):
    s=json.loads(row['starting_values']);ts=list(dict.fromkeys(json.loads(row['targets'])));L=int(row['value_limit']);R=int(row['registers']);start=set(s);cl={v:set() for v in s}
    def closure(v,stack=frozenset()):
        if v in cl:return cl[v]
        if v in stack:raise ValueError('cycle')
        op,a,b=graph[v]
        if not 1<=v<=L or arithmetic(op,a,b)!=v:raise ValueError('invalid graph')
        cl[v]=closure(a,stack|{v})|closure(b,stack|{v})|{v};return cl[v]
    for v in ts:closure(v)
    rng=random.Random(919);best=None
    for turn in range(tries):
        roots=ts.copy()
        if turn%4==1:roots.reverse()
        elif turn%4==2:roots.sort(key=lambda v:len(cl[v]),reverse=turn%8==6)
        elif turn%4==3:rng.shuffle(roots)
        done=set(s);order=[]
        def visit(v):
            if v in done:return
            _,a,b=graph[v]
            if (len(cl[a])<len(cl[b]))==(turn%2==0):a,b=b,a
            visit(a);visit(b);done.add(v);order.append(v)
        for t in roots:visit(t)
        future=defaultdict(list)
        for k,v in enumerate(order):
            for x in set(graph[v][1:]):future[x].append(k)
        live={x:i for i,x in enumerate(s)};p=[];index=0
        def ensure(v,protect):
            if v in live:return
            op,a,b=graph[v];ensure(a,protect);ensure(b,protect|{a});i,j=live[a],live[b]
            free=set(range(R))-set(live.values())
            if free:d=min(free)
            else:
                options=[x for x in live if x not in start and x not in protect]
                if not options:raise ValueError('register pressure')
                def rank(x):
                    nxt=next((k for k in future[x] if k>index),len(order)+10000)
                    return (nxt-index)/(1+len(cl[x]) if turn%2 else 1),nxt,-len(cl[x]),x
                x=max(options,key=rank);d=live.pop(x)
            p.append([op,i,j,d]);live[v]=d
        try:
            for index,v in enumerate(order):
                ensure(v,set())
                for x in list(live):
                    if x not in start and not any(k>index for k in future[x]):live.pop(x)
            replay(row,p)
        except (ValueError,KeyError,RecursionError):continue
        if best is None or len(p)<len(best):best=p
        if best is not None and len(best)==len(order):break
    if best is None:raise ValueError('no valid schedule')
    return best,len(order)

def construct(row,width,mode,exe='constructor'):
    s=json.loads(row['starting_values']);t=json.loads(row['targets']);data=' '.join(map(str,[row['value_limit'],len(s),len(t),*s,*t]))
    p=subprocess.run([str(ROOT/exe),str(width),str(mode)],input=data,text=True,capture_output=True,timeout=45,check=True)
    lines=p.stdout.splitlines();g={}
    for line in lines[1:]:
        v,op,a,b=line.split();g[int(v)]=(op,int(a),int(b))
    assert len(g)==int(lines[0]);return g

def solve(job):
    row,configs=job;st=time.monotonic();results=[];best=None
    for exe,w,m in configs:
        start=time.monotonic()
        try:
            g=construct(row,w,m,exe.removesuffix('_polish'));p,n=compile_graph(row,g);
            if exe.endswith('_polish'):
                from polish import polish
                gp,moves=polish(g,json.loads(row['starting_values']),json.loads(row['targets']),int(row['value_limit']));pp,nn=compile_graph(row,gp)
                if len(pp)<len(p):p,n=pp,nn
            score=replay(row,p);results.append({'config':[exe,w,m],'nodes':n,'score':score,'seconds':round(time.monotonic()-start,3)})
            if best is None or len(p)<len(best):best=p
        except Exception as e:results.append({'config':[exe,w,m],'error':str(e),'seconds':round(time.monotonic()-start,3)})
    return {'id':row['id'],'score':len(best) if best is not None else None,'seconds':round(time.monotonic()-st,3),'results':results,'program':best}

def main():
    a=argparse.ArgumentParser();a.add_argument('csv');a.add_argument('--n',type=int,default=32);a.add_argument('--offset',type=int,default=0);a.add_argument('--random-seed',type=int);a.add_argument('--jobs',type=int,default=4);a.add_argument('--configs',default='constructor:4:1');a.add_argument('--out',required=True);args=a.parse_args()
    rows=list(csv.DictReader(open(args.csv)));configs=[(e,int(w),int(m)) for e,w,m in (c.split(':') for c in args.configs.split(','))];rows=random.Random(args.random_seed).sample(rows[args.offset:],args.n) if args.random_seed is not None else rows[args.offset:args.offset+args.n];st=time.monotonic();out=Path(args.out);out.parent.mkdir(exist_ok=True,parents=True)
    records=[]
    with out.open('w') as f,concurrent.futures.ProcessPoolExecutor(max_workers=args.jobs) as ex:
        for r in ex.map(solve,[(row,configs) for row in rows]):
            records.append(r);f.write(json.dumps(r,separators=(',',':'))+'\n');f.flush();print(r['id'],r['score'],[x.get('score','FAIL') for x in r['results']],flush=True)
    print('SUMMARY',len(records),sum(r['score'] is not None for r in records),sum(r['score'] or 0 for r in records),round(time.monotonic()-st,2),flush=True)
if __name__=='__main__':main()
