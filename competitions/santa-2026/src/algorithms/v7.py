"""V7: feature-adaptive portfolio, multi-graph path selection and register-aware scheduling.

Only the official puzzle CSV is accepted as input. The V6 programme and every
extra candidate are regenerated in the current invocation.
"""
import json
from collections import defaultdict

from . import v5, v6
from .common import replay

def extract(row,program):
    s=json.loads(row['starting_values']);n=int(row['registers']);reg=s+[None]*(n-len(s));g={};start=set(s)
    for o,a,b,d in program:
        x,y=reg[a],reg[b];v=x+y if o=='+' else x-y if o=='-' else x*y if o=='*' else x//y
        reg[d]=v
        if v not in start and v not in g:g[v]=(o,x,y)
    return g

def schedule(row,program):
    """Cluster roots by shared dependencies and try last-use register overwrite."""
    s=json.loads(row['starting_values']);start=set(s);ts=list(dict.fromkeys(json.loads(row['targets'])));n=int(row['registers']);g=extract(row,program)
    closure={v:frozenset() for v in s};depth={v:0 for v in s}
    for v,(o,a,b) in g.items():
        closure[v]=closure[a]|closure[b]|{v};depth[v]=1+max(depth[a],depth[b])
    nodes=set().union(*(closure[t] for t in ts))
    if len(nodes)>=len(program):return program
    def cluster(reverse=False):
        todo=set(ts);out=[];prev=None;used=set()
        while todo:
            if prev is None:t=max(todo,key=lambda x:(len(closure[x]),x)) if reverse else min(todo,key=lambda x:(len(closure[x]),x))
            else:t=max(todo,key=lambda x:(len(closure[x]&closure[prev]),len(closure[x]&used),-len(closure[x]-used),-x))
            todo.remove(t);out.append(t);used|=closure[t];prev=t
        return out
    best=program
    for roots in [ts,ts[::-1],sorted(ts),sorted(ts,reverse=True),cluster(),cluster(True)]:
        for deep_first in (False,True):
            order=[];seen=set(s)
            def visit(v):
                if v in seen:return
                _,a,b=g[v]
                if deep_first and (depth[b],len(closure[b]))>(depth[a],len(closure[a])):a,b=b,a
                visit(a);visit(b);seen.add(v);order.append(v)
            for t in roots:visit(t)
            uses=defaultdict(list)
            for i,v in enumerate(order):
                _,a,b=g[v];uses[a].append(i);uses[b].append(i)
            for policy in ('distance','cost'):
                if len(order)>=len(best):return best
                live={v:i for i,v in enumerate(s)};out=[];at=0;ptr=defaultdict(int)
                def nextuse(v):return uses[v][ptr[v]] if ptr[v]<len(uses[v]) else 10**9
                def ensure(v,protect):
                    if v in live:return
                    o,a,b=g[v]
                    if deep_first and depth[b]>depth[a]:ensure(b,protect);ensure(a,protect|{b})
                    else:ensure(a,protect);ensure(b,protect|{a})
                    ai,bi=live[a],live[b]
                    disposable=[k for k in {a,b} if k not in start and k not in protect and v==order[at] and ptr[k]+(1 if a!=b else 2)==len(uses[k])]
                    if disposable:d=live.pop(min(disposable))
                    else:
                        free=set(range(n))-set(live.values())
                        if free:d=min(free)
                        else:
                            ev=[k for k in live if k not in start and k not in protect]
                            if not ev:raise ValueError('register pressure')
                            if policy=='distance':k=max(ev,key=lambda k:(nextuse(k),-len(closure[k]),k))
                            else:k=max(ev,key=lambda k:((nextuse(k)-at)/(1+len(closure[k])),nextuse(k),k))
                            d=live.pop(k)
                    out.append([o,ai,bi,d]);live[v]=d
                    if len(out)>=len(best):raise ValueError('not shorter')
                try:
                    for at,v in enumerate(order):
                        _,a,b=g[v];ensure(v,set());ptr[a]+=1;ptr[b]+=1
                        for k in list(live):
                            if k not in start and nextuse(k)==10**9:live.pop(k)
                    replay(row,out);best=out
                except (ValueError,RecursionError):pass
    return best

def plans(s,ts):
    maxbit=max(ts).bit_length();spread=maxbit-min(ts).bit_length();asc=sorted(ts)
    yield 'asc-seed5',asc,5,3
    if len(ts)>=20:
        if spread>=6:order=sorted(ts,key=lambda t:(-t.bit_length(),t))
        else:order=sorted(ts,key=lambda t:(t%256,t))
        yield 'feature-order',order,6,3
        if maxbit>=40:yield 'wide-asc',asc,7,4
    elif len(s)<=2 and maxbit>=25:
        yield 'small-start-wide',asc,7,4

def optimize(job):
    row,portfolio,path_rounds,do_schedule,retain=job
    pid,base,m,extra_graphs=v6.optimize_v6((row,180,True),trace=True);s=json.loads(row['starting_values']);ts=json.loads(row['targets']);L=int(row['value_limit'])
    best=base;graphs=[base];raw={};failed=[]
    if len(base)>len(set(ts)-set(s)):
        for name,order,seed,width in list(plans(s,ts))[:portfolio]:
            try:
                alt=v5.adaptive_v5(s,order,L,seed=seed,width=width)[2];replay(row,alt);raw[name]=len(alt)
                graphs.append(alt)
                if len(alt)<len(best):best=alt
            except (ValueError,AssertionError,KeyError,RecursionError):failed.append(name)
    selected=len(best);fused=selected
    if len(graphs)>1:
        new=v6.path_union(row,graphs,rounds=path_rounds)
        if len(new)<len(best):best=new
        fused=len(best)
        for alt in sorted(graphs,key=len)[:2]:
            if alt==best:continue
            new=v6.global_select(row,best,alt,rounds=120)
            if len(new)<len(best):best=new
    polished=len(best)
    if retain and len(base)>len(set(ts)-set(s)):
        extended=[best]+graphs+extra_graphs
        # Only unique in-memory current-run witnesses, retaining the existing best.
        unique=[]; signatures=set()
        for program in extended:
            signature=tuple(map(tuple,program))
            if signature not in signatures:signatures.add(signature);unique.append(program)
        if len(unique)>len(graphs):
            new=v6.path_union(row,unique,rounds=path_rounds)
            if len(new)<len(best):best=new
    retained=len(best)
    if do_schedule:best=schedule(row,best)
    replay(row,best)
    return pid,best,dict(v6=len(base),portfolio=selected,path_union=fused,polished=polished,retained=retained,v7=len(best),candidates=raw,failed=failed)
