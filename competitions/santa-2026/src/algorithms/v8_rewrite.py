"""V8.0 core: two-operation subgraph rewriting and DAG compilation.

Every candidate is derived from a V7 programme regenerated in the same call;
no historical answer is read.
"""
import json,random
from collections import Counter,defaultdict
from . import v7
from .common import replay

def closures(g,s,roots):
    memo={x:frozenset() for x in s};visiting=set()
    def visit(v):
        if v in memo:return memo[v]
        if v in visiting:raise ValueError('cycle')
        visiting.add(v);_,a,b=g[v];c=visit(a)|visit(b)|{v};visiting.remove(v);memo[v]=c;return c
    active=set().union(*(visit(t) for t in roots));return memo,active

def compile_graph(row,g,best):
    s=json.loads(row['starting_values']);ts=list(dict.fromkeys(json.loads(row['targets'])));n=int(row['registers']);start=set(s)
    cl,active=closures(g,s,ts)
    if len(active)>=len(best):return best
    children=defaultdict(list);deps={};original=Counter();rng=random.Random(808)
    for v in active:
        _,a,b=g[v];deps[v]=len({a,b}-start)
        for x in {a,b}:children[x].append(v);original[x]+=1
    for mode in range(8):
        order=[]
        if mode>=4:
            roots=ts.copy()
            if mode==5:roots.reverse()
            elif mode==6:roots.sort(key=lambda t:(len(cl[t]),t))
            elif mode==7:roots.sort(key=lambda t:(-len(cl[t]),t))
            seen=set(start)
            def visit(v):
                if v in seen:return
                _,a,b=g[v]
                if mode%2 and len(cl[b])>len(cl[a]):a,b=b,a
                visit(a);visit(b);seen.add(v);order.append(v)
            for t in roots:visit(t)
        else:
            remaining=original.copy();indeg=deps.copy();ready={v for v,d in indeg.items() if d==0};priority={v:rng.random() for v in sorted(active)}
            while ready:
                def score(v):
                    _,a,b=g[v];release=sum(x not in start and remaining[x]==1 for x in {a,b});birth=bool(remaining[v]);reuse=sum(x not in start for x in {a,b})
                    return (release-birth,release,(-len(cl[v]),len(cl[v]),priority[v],-remaining[v])[mode],reuse,-v)
                v=max(ready,key=score);ready.remove(v);order.append(v);_,a,b=g[v]
                for x in {a,b}:remaining[x]-=1
                for w in children[v]:
                    indeg[w]-=1
                    if indeg[w]==0:ready.add(w)
        if len(order)!=len(active):raise ValueError('bad order')
        uses=defaultdict(list);ptr=defaultdict(int)
        for j,v in enumerate(order):
            _,a,b=g[v]
            for x in {a,b}:uses[x].append(j)
        live={v:i for i,v in enumerate(s)};out=[]
        def nextuse(v):return uses[v][ptr[v]] if ptr[v]<len(uses[v]) else 10**9
        def ensure(v,protect):
            if v in live:return
            op,a,b=g[v]
            if len(cl[b])>len(cl[a]):ensure(b,protect);ensure(a,protect|{b})
            else:ensure(a,protect);ensure(b,protect|{a})
            ai,bi=live[a],live[b]
            disposable=[x for x in {a,b} if x not in start and x not in protect and nextuse(x)==at and ptr[x]+1==len(uses[x]) and order[at]==v]
            if disposable:d=live.pop(min(disposable))
            else:
                free=set(range(n))-set(live.values())
                if free:d=min(free)
                else:
                    ev=[x for x in live if x not in start and x not in protect]
                    if not ev:raise ValueError('register pressure')
                    d=live.pop(max(ev,key=lambda x:(nextuse(x),-len(cl[x]),x)))
            out.append([op,ai,bi,d]);live[v]=d
            if len(out)>=len(best):raise ValueError('not shorter')
        try:
            for at,v in enumerate(order):
                ensure(v,set());_,a,b=g[v]
                for x in {a,b}:ptr[x]+=1
                for x in list(live):
                    if x not in start and nextuse(x)==10**9:live.pop(x)
            replay(row,out);best=out
            if len(best)==len(active):break
        except (ValueError,RecursionError,AssertionError):pass
    return best

def pairs(values,L):
    pool={}
    def put(x,e):
        if 0<x<=L:
            b=pool.setdefault(x,[])
            if len(b)<3 and e not in b:b.append(e)
    for i,a in enumerate(values):
        for b in values[:i+1]:
            put(a+b,('+',a,b));put(a*b,('*',a,b))
            if a>b:put(a-b,('-',a,b))
            if b>a:put(b-a,('-',b,a))
            if a%b==0:put(a//b,('/',a,b))
            if b%a==0:put(b//a,('/',b,a))
    return pool

def rewrite(row,program,sweeps=2):
    s=json.loads(row['starting_values']);ts=list(dict.fromkeys(json.loads(row['targets'])));L=int(row['value_limit']);start=set(s)
    g=v7.extract(row,program);best=program;accepted=0;novel=0
    cl,active=closures(g,s,ts);g={x:g[x] for x in active}
    for sweep in range(sweeps):
        changed=0;values=sorted(active|start,key=lambda x:(len(cl[x]),x));pool=pairs(values,L)
        for v in sorted(active,key=lambda x:(-len(cl[x]),-x)):
            if v not in active:continue
            refs=Counter(ts)
            for x in active:
                _,a,b=g[x];refs[a]+=1;refs[b]+=1
            removed=set()
            def drop(x):
                refs[x]-=1
                if refs[x]==0 and x not in start:
                    removed.add(x);_,a,b=g[x];drop(a);drop(b)
            _,a,b=g[v];drop(a);drop(b)
            if not removed:continue
            kept=active-removed;best_delta=0;chosen=None
            for a in values:
                if a not in cl or v in cl[a] or a==v:continue
                opts=(('+',v-a,False),('-',a-v,False),('-',v+a,True),('*',v//a if v%a==0 else 0,False),('/',v*a,True),('/',a//v if a%v==0 else 0,False))
                for op,b,rev in opts:
                    if b<=0 or b>L or b==v:continue
                    e=(op,b,a) if rev else (op,a,b)
                    if b in cl:
                        if v in cl[b]:continue
                        delta=len((cl[a]|cl[b])-kept)-len(removed)
                        if delta<best_delta:best_delta=delta;chosen=(e,None)
                    elif len(removed)>1:
                        for eb in pool.get(b,()):
                            _,c,d=eb
                            if c not in cl or d not in cl or c==v or d==v or v in cl[c] or v in cl[d]:continue
                            delta=1+len((cl[a]|cl[c]|cl[d])-kept)-len(removed)
                            if delta<best_delta:best_delta=delta;chosen=(e,(b,eb))
            if chosen is None:continue
            e,extra=chosen;old=g[v];g[v]=e
            if extra:g[extra[0]]=extra[1]
            nc,na=closures(g,s,ts)
            if len(na)>=len(active):
                g[v]=old
                if extra:g.pop(extra[0])
                continue
            g={x:g[x] for x in na};cl,active=nc,na;changed+=1;accepted+=1;novel+=int(extra is not None)
        if not changed:break
    return compile_graph(row,g,best),accepted,novel

def optimize(row,sweeps=2):
    pid,base,m=v7.optimize((row,3,400,True,False));best=base
    best=compile_graph(row,v7.extract(row,base),best);schedule=len(best)
    best,rewrites,novel=rewrite(row,best,sweeps);replay(row,best)
    return pid,best,{'v7':len(base),'list_schedule':schedule,'v8':len(best),'rewrites':rewrites,'novel':novel}
