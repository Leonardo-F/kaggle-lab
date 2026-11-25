"""V8 Final: liveness-ranked register scheduling with real program length selection."""
import json,random
from collections import Counter,defaultdict
from . import v8_rewrite as core
from .v8_three import optimize as prior

def schedule(row,program,tries=32):
    s=json.loads(row['starting_values']);start=set(s);ts=list(dict.fromkeys(json.loads(row['targets'])));n=int(row['registers']);g=core.v7.extract(row,program)
    cl,active=core.closures(g,s,ts)
    if len(active)>=len(program):return program,0,len(program)-len(active)
    rng=random.Random(833);best=program;attempts=0;orders={}
    def dfs(roots,deep):
        seen=set(start);order=[]
        def visit(v):
            if v in seen:return
            _,a,b=g[v]
            if deep and len(cl[a])<len(cl[b]):a,b=b,a
            visit(a);visit(b);seen.add(v);order.append(v)
        for t in roots:visit(t)
        return order
    def pressure(order):
        remaining=Counter(x for v in order for x in set(g[v][1:]));live=0;peak=0;overflow=0;area=0
        for v in order:
            for x in set(g[v][1:]):
                remaining[x]-=1
                if remaining[x]==0 and x not in start:live-=1
            if remaining[v]:live+=1
            peak=max(peak,live);overflow+=max(0,live+len(start)-n);area+=live
        return overflow,peak,area
    roots=ts[:]
    for k in range(tries):
        if k%4==0:roots=ts[:];rng.shuffle(roots)
        elif k%4==1:roots=sorted(ts,key=lambda t:(len(cl[t]),t),reverse=bool(k%8))
        elif k%4==2:
            roots=[];todo=set(ts);used=set();prev=set()
            while todo:
                t=max(todo,key=lambda x:(len(cl[x]&prev)+.5*len(cl[x]&used)-.25*len(cl[x]-used),-x));todo.remove(t);roots.append(t);prev=cl[t];used|=prev
        else:
            roots=roots[:]
            if len(roots)>1:i,j=rng.sample(range(len(roots)),2);roots[i],roots[j]=roots[j],roots[i]
        order=dfs(roots,bool(k%2));orders[tuple(order)]=pressure(order)
    for order in sorted(orders,key=lambda o:orders[o])[:8]:
        if len(best)==len(active):break
        attempts+=1;uses=defaultdict(list);ptr=defaultdict(int)
        for j,v in enumerate(order):
            for x in set(g[v][1:]):uses[x].append(j)
        live={v:i for i,v in enumerate(s)};out=[]
        def nextuse(v):return uses[v][ptr[v]] if ptr[v]<len(uses[v]) else 10**9
        def ensure(v,protect):
            if v in live:return
            op,a,b=g[v]
            if (a not in live,len(cl[a]))<(b not in live,len(cl[b])):ensure(b,protect);ensure(a,protect|{b})
            else:ensure(a,protect);ensure(b,protect|{a})
            ai,bi=live[a],live[b]
            dead=[x for x in {a,b} if x not in start and x not in protect and nextuse(x)==at and ptr[x]+1==len(uses[x]) and order[at]==v]
            if dead:d=live.pop(min(dead))
            else:
                free=set(range(n))-set(live.values())
                if free:d=min(free)
                else:
                    candidates=[x for x in live if x not in start and x not in protect]
                    if not candidates:raise ValueError('register pressure')
                    x=max(candidates,key=lambda x:(nextuse(x)==10**9,(nextuse(x)-at)/(1+len(cl[x]-set(live))),nextuse(x),x));d=live.pop(x)
            out.append([op,ai,bi,d]);live[v]=d
            if len(out)>=len(best):raise ValueError('not shorter')
        try:
            for at,v in enumerate(order):
                ensure(v,set())
                for x in set(g[v][1:]):ptr[x]+=1
                for x in list(live):
                    if x not in start and nextuse(x)==10**9:live.pop(x)
            core.replay(row,out);best=out
        except (ValueError,AssertionError,RecursionError,KeyError):pass
    return best,attempts,len(program)-len(active)

def optimize(row):
    pid,pr,m=prior(row);best,attempts,gap=schedule(row,pr);core.replay(row,best);m.update(v83=len(best),schedule_attempts=attempts,remat_gap=gap);return pid,best,m
