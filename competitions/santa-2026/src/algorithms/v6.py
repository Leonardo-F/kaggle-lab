"""Experimental V6: cycle-safe global shared path selection.
Only official puzzle CSV is accepted as input.
"""
import argparse,csv,json,random,time
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor,as_completed
from . import v5
from .common import replay

def global_select(row, program, alternate=None, rounds=180):
    """Cycle-safe global shared path selection over fresh candidate graphs."""
    s=json.loads(row['starting_values']); ts=json.loads(row['targets'])
    regs=list(s)+[None]*(48-len(s)); vals=list(dict.fromkeys(s)); idx={v:i for i,v in enumerate(vals)}; ns=len(vals); opts=[[] for _ in vals]
    def trace(prog):
        regs=list(s)+[None]*(48-len(s));out=[]
        for op,i,j,d in prog:
            a,b=regs[i],regs[j]
            v=a+b if op=='+' else a-b if op=='-' else a*b if op=='*' else a//b
            regs[d]=v;out.append((op,a,b,v))
        return out
    traces=[trace(program)]
    if alternate is not None:traces.append(trace(alternate))
    # Interleave fresh traces; only retain edges to earlier nodes (no cycles).
    from itertools import zip_longest
    for items in zip_longest(*traces):
        for item in items:
            if item is None:continue
            op,a,b,v=item
            if v not in idx:
                idx[v]=len(vals);vals.append(v);opts.append([(op,idx[a],idx[b])])
            elif alternate is not None and idx[v]>=ns and max(idx[a],idx[b])<idx[v]:
                edge=(op,idx[a],idx[b])
                if edge not in opts[idx[v]]:opts[idx[v]].append(edge)
    N=len(vals);roots={idx[t] for t in ts};choice=[0]*N;refs=[0]*N;cost=0
    for j in range(ns,N):
        v=vals[j]; edges=set(opts[j]);get=idx.get
        for i in range(N):
            if i==j:continue
            a=vals[i]
            for o,b,rev in (('+',v-a,False),('-',a-v,False),('-',a+v,True),('*',v//a if v%a==0 else 0,False),('/',v*a,True),('/',a//v if a%v==0 else 0,False)):
                k=get(b,-1)
                if k<0 or k==j:continue
                e=(o,k,i) if rev else (o,i,k)
                if o in ('+','*') and e[1]>e[2]:e=(o,e[2],e[1])
                if e not in edges:opts[j].append(e);edges.add(e)
    def add(i):
        nonlocal cost
        refs[i]+=1
        if refs[i]!=1 or i<ns:return
        cost+=1;_,a,b=opts[i][choice[i]];add(a);add(b)
    def rem(i):
        nonlocal cost
        refs[i]-=1
        if refs[i]!=0 or i<ns:return
        cost-=1;_,a,b=opts[i][choice[i]];rem(a);rem(b)
    def cycle(i,a,b):
        stack=[a,b];seen=set()
        while stack:
            x=stack.pop()
            if x==i:return True
            if x<ns or x in seen:continue
            seen.add(x);_,a,b=opts[x][choice[x]];stack.extend((a,b))
        return False
    def change(i,k,check=True):
        if k==choice[i]:return True
        _,a,b=opts[i][k]
        if check and cycle(i,a,b):return False
        active=refs[i]>0
        if active:_,a,b=opts[i][choice[i]];rem(a);rem(b)
        choice[i]=k
        if active:_,a,b=opts[i][k];add(a);add(b)
        return True
    for i in roots:add(i)
    original_cost=cost;best_cost=cost;best_choice=choice.copy();rng=random.Random(606)
    mutable=[i for i in range(ns,N) if len(opts[i])>1]
    for sweep in range(6):
        rng.shuffle(mutable)
        for i in mutable:
            if not refs[i]:continue
            bk=choice[i];bc=cost
            for k in range(len(opts[i])):
                if not change(i,k):continue
                if cost<bc or (cost==bc and rng.random()<.12):bk=k;bc=cost
            change(i,bk)
        if cost<best_cost:best_cost=cost;best_choice=choice.copy()
    if rounds:
        import math
        for step in range(rounds):
            active=[i for i in mutable if refs[i]]
            if not active:break
            # Perturb a target dependency subtree, not just unrelated nodes.
            root=rng.choice(sorted(roots) if rng.random()<.65 else active)
            stack=[root];seen=set();near=[]
            while stack and len(seen)<32:
                i=stack.pop()
                if i<ns or i in seen:continue
                seen.add(i)
                if len(opts[i])>1:near.append(i)
                _,a,b=opts[i][choice[i]];stack.extend((a,b))
            pool=near if len(near)>=2 else active
            sub=rng.sample(pool,min(len(pool),rng.choice((2,3,5,8))))
            saved=[];before=cost
            for i in sub:
                old=choice[i]
                if change(i,rng.randrange(len(opts[i]))):saved.append((i,old))
            for i in sub:
                saved.append((i,choice[i]))
                bk=choice[i];bc=cost
                for k in range(len(opts[i])):
                    if not change(i,k):continue
                    if cost<bc or (cost==bc and rng.random()<.1):bk=k;bc=cost
                change(i,bk)
            temp=max(.15,1.4*(1-step/rounds))
            if cost>before and rng.random()>math.exp((before-cost)/temp):
                for i,k in reversed(saved):change(i,k,False)
                assert cost==before
            if cost<best_cost:best_cost=cost;best_choice=choice.copy()
    choice=best_choice
    if alternate is None and not rounds and best_cost>=original_cost:return program
    if best_cost>=len(program):return program
    best=program
    for mode in range(4):
        order=[];seen=set(range(ns))
        def visit(i):
            if i in seen:return
            _,a,b=opts[i][choice[i]];visit(a);visit(b);seen.add(i);order.append(i)
        for i in sorted(roots,key=(lambda i:vals[i]) if mode in (2,3) else None,reverse=mode in (1,3)):visit(i)
        uses=[[] for _ in vals];ptr=[0]*N
        for j,i in enumerate(order):
            _,a,b=opts[i][choice[i]];uses[a].append(j);uses[b].append(j)
        live={idx[v]:i for i,v in enumerate(s)};out=[]
        def nextuse(i):return uses[i][ptr[i]] if ptr[i]<len(uses[i]) else 10**9
        def ensure(i,protect):
            if i in live:return
            op,a,b=opts[i][choice[i]];ensure(a,protect);ensure(b,protect|{a});ai,bi=live[a],live[b]
            free=set(range(48))-set(live.values())
            if free:d=min(free)
            else:
                ev=[k for k in live if k>=ns and k not in protect]
                if not ev:raise ValueError('register pressure')
                d=live.pop(max(ev,key=nextuse))
            out.append([op,ai,bi,d]);live[i]=d
            if len(out)>4096:raise ValueError('too long')
        try:
            for i in order:
                _,a,b=opts[i][choice[i]];ensure(i,set());ptr[a]+=1;ptr[b]+=1
                for k in list(live):
                    if k>=ns and nextuse(k)==10**9:live.pop(k)
            if len(out)<len(best):replay(row,out);best=out
        except (ValueError,RecursionError):pass
    return best


def path_union(row, programs, rounds=300):
    """Choose complete target dependency paths jointly across current-run graphs.
    The union of value sets is a lower-bound proxy. Rebuild a feasible DAG from
    selected edges by forward reachability; accept only replayed instruction wins.
    """
    import math
    rng=random.Random(6606)
    s=json.loads(row['starting_values']);ts=list(dict.fromkeys(json.loads(row['targets'])))
    n=int(row['registers']);start=set(s);pool={v:i for i,v in enumerate(s)}
    graphs=[]
    for program in programs:
        g={};reg=s+[None]*(n-len(s))
        for o,a,b,d in program:
            x,y=reg[a],reg[b];v=x+y if o=='+' else x-y if o=='-' else x*y if o=='*' else x//y
            reg[d]=v
            if v not in start and v not in g:g[v]=(o,x,y)
            if v not in pool:pool[v]=len(pool)
        graphs.append(g)
    if len(graphs)<2:return programs[0]
    # A complete witness path is an immutable dependency closure in a source DAG.
    options=[]
    for t in ts:
        arr=[]; seen=set()
        for j,g in enumerate(graphs):
            stack=[t];path=set();bits=0
            while stack:
                v=stack.pop()
                if v in start or v in path:continue
                path.add(v);bits|=1<<pool[v];_,a,b=g[v];stack.extend((a,b))
            signature=(bits,tuple(sorted((v,g[v]) for v in path)))
            if signature in seen:continue
            seen.add(signature);arr.append((bits,j,path))
        options.append(arr)
    m=len(ts);active=[i for i,x in enumerate(options) if len(x)>1]
    if not active:return min(programs,key=len)
    # Full target path swaps, objective is cardinality of the union of all paths.
    def cost(ch):
        bits=0
        for i,k in enumerate(ch):bits|=options[i][k][0]
        return bits.bit_count()
    best_configs={}
    def record(ch,c):
        key=tuple(ch);best_configs[key]=c
        if len(best_configs)>12:
            worst=max(best_configs,key=lambda k:(best_configs[k],k));best_configs.pop(worst)
    def sweep(ch):
        order=active.copy();rng.shuffle(order)
        for i in order:
            prev=ch[i];scores=[]
            for k in range(len(options[i])):
                ch[i]=k;scores.append((cost(ch),k))
            bc=min(x[0] for x in scores);ch[i]=rng.choice([k for c,k in scores if c==bc])
        return cost(ch)
    # Start from each source graph, plus randomized path choices.
    for j in range(len(graphs)+3):
        ch=[next((k for k,o in enumerate(x) if o[1]==j),0) if j<len(graphs) else rng.randrange(len(x)) for x in options]
        c=cost(ch);record(ch,c)
        for _ in range(4):c=sweep(ch);record(ch,c)
    ch=list(min(best_configs,key=best_configs.get));c=cost(ch)
    for step in range(rounds):
        sub=rng.sample(active,min(len(active),rng.choice((1,2,3,5,8))))
        old=ch.copy();before=c
        for i in sub:ch[i]=rng.randrange(len(options[i]))
        c=cost(ch);record(ch,c)
        if step%5==0:c=sweep(ch);record(ch,c)
        temp=max(.15,3*(1-step/max(1,rounds)))
        if c>before and rng.random()>math.exp((before-c)/temp):ch=old;c=before
    best=min(programs,key=len)
    # Forward reachability resolves conflicting producers without introducing cycles.
    for ch,proxy in sorted(best_configs.items(),key=lambda x:x[1]):
        if proxy>=len(best):continue
        edges=set()
        for i,k in enumerate(ch):
            _,j,path=options[i][k]
            edges.update((v,graphs[j][v]) for v in path)
        for reverse in (False,True):
            ready=set(start);g={};pending=sorted(edges,reverse=reverse)
            while pending:
                remaining=[];progress=False
                for v,e in pending:
                    if v in ready:continue
                    if e[1] in ready and e[2] in ready:g[v]=e;ready.add(v);progress=True
                    else:remaining.append((v,e))
                if not progress:break
                pending=remaining
            if not set(ts)<=ready:continue
            # Compile only selected producers reachable from targets. Evict by next use.
            for root_order in (ts,ts[::-1],sorted(ts),sorted(ts,reverse=True)):
                order=[];seen=set(start)
                def visit(v):
                    if v in seen:return
                    _,a,b=g[v];visit(a);visit(b);seen.add(v);order.append(v)
                for t in root_order:visit(t)
                if len(order)>=len(best):continue
                from collections import defaultdict
                uses=defaultdict(list);ptr=defaultdict(int)
                for j,v in enumerate(order):
                    _,a,b=g[v];uses[a].append(j);uses[b].append(j)
                live={v:i for i,v in enumerate(s)};out=[]
                def nextuse(v):return uses[v][ptr[v]] if ptr[v]<len(uses[v]) else 10**9
                def ensure(v,protect):
                    if v in live:return
                    o,a,b=g[v];ensure(a,protect);ensure(b,protect|{a});ai,bi=live[a],live[b]
                    free=set(range(n))-set(live.values())
                    if free:d=min(free)
                    else:
                        ev=[k for k in live if k not in start and k not in protect]
                        if not ev:raise ValueError('register pressure')
                        d=live.pop(max(ev,key=nextuse))
                    out.append([o,ai,bi,d]);live[v]=d
                    if len(out)>=len(best):raise ValueError('not shorter')
                try:
                    for v in order:
                        _,a,b=g[v];ensure(v,set());ptr[a]+=1;ptr[b]+=1
                        for k in list(live):
                            if k not in start and nextuse(k)==10**9:live.pop(k)
                    replay(row,out);best=out
                except (ValueError,RecursionError):pass
    return best


def optimize_v6(job, trace=False):
    """Run V6. With ``trace=True`` also return every in-memory candidate programme,
    the optional interface V7 uses to fuse current-run graphs without a duplicate
    V6 implementation."""
    row,rounds,extra=job
    pid,baseline,*_=v5.optimize_v5((row,True,True))
    s=json.loads(row['starting_values']);ts=json.loads(row['targets']);L=int(row['value_limit'])
    if len(baseline)==len(set(ts)-set(s)):
        metrics={'v5':len(baseline),'single':len(baseline),'alternate':None,'pre_path':len(baseline),'v6':len(baseline)}
        return (pid,baseline,metrics,[baseline]) if trace else (pid,baseline,metrics)
    best=global_select(row,baseline,rounds=rounds);single=len(best);candidates=[baseline,best];alt=None;raw=None
    if extra:
        try:
            alt=v5.adaptive_v5(s,sorted(ts),L,seed=4)[2];replay(row,alt);raw=len(alt)
        except (ValueError,AssertionError,KeyError,RecursionError):alt=None
        if alt is not None:
            candidates.append(alt)
            if len(alt)<len(best):best,alt=alt,best
            new=global_select(row,best,alt,rounds=rounds)
            if len(new)<len(best):best=new
    pre_path=len(best)
    candidates.append(best)
    new=path_union(row,candidates,rounds=300)
    if len(new)<len(best):best=new
    replay(row,best)
    metrics={'v5':len(baseline),'single':single,'alternate':raw,'pre_path':pre_path,'v6':len(best)}
    return (pid,best,metrics,candidates) if trace else (pid,best,metrics)
