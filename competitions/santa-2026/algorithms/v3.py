"""Independent Santa solver: reads only the puzzle input, no reference programs."""

import json
import random
from functools import lru_cache
from .common import ops, replay, sparse


def adaptive(s,ts,L,seed=0,width=2,wide=False,bidir=False):
    rng=random.Random(seed)
    expr={v:None for v in s}; anc={v:frozenset() for v in s};
    def add(v,e):
        a,b=e[1:]; deps=anc[a]|anc[b]|{v}
        if v not in anc or len(deps)<len(anc[v]):
            # first create only: changing ancestors of existing expressions invalidates cache
            if v not in anc: expr[v]=e; anc[v]=deps
    for _ in range(2):
        old=list(expr)
        for i,a in enumerate(old):
            for b in old[:i+1]:
                for v,e in ops(a,b,L): add(v,e)
    if len(s)==1:
        for v in range(2,min(L,48)+1):
            add(v,('+',v//2,v-v//2))
        for v in (64,128,256,512,1024,2048,4096,8192,16384,32768,65536):
            if v<=L: add(v,('+',v//2,v//2))
    l2=list(expr); l1=[v for v in l2 if len(anc[v])<=1]
    # broad cheap pool, one operation over L2 and L1
    # Limit expansion to stratified low-cost values (deterministic budget).
    def stratified(values, count):
        buckets={}
        for v in values:buckets.setdefault(v.bit_length(),[]).append(v)
        for vv in buckets.values(): vv.sort(key=lambda v:(len(anc[v]),rng.random()))
        return [v for vv in buckets.values() for v in vv[:count]]
    limited_l1=stratified(l1,8)
    for a in stratified(l2,18):
        for b in limited_l1:
            for v,e in ops(a,b,L): add(v,e)
    # supplement small dense dictionary with additions of L2 values
    small=stratified([v for v in l2 if v<4096],12)
    for i,a in enumerate(small):
        for b in small[:i+1]:
            for v,e in ops(a,b,min(L,65536)): add(v,e)
    # get a set of varied divisors: prioritize 1-3 step bases
    maxbit=max(ts).bit_length()
    bins={}
    for v in l2:
        if v>1 and v.bit_length()<=min(22,maxbit//2+3): bins.setdefault(v.bit_length(),[]).append(v)
    l2set=set(l2)
    extra={}
    for v in expr:
        if v>1 and v not in l2set and len(anc[v])<=3 and v.bit_length()<=min(24,maxbit//2+3):
            extra.setdefault(v.bit_length(),[]).append(v)
    bases=[]
    for k,vs in extra.items():
        vs.sort(key=lambda v:(len(anc[v]),rng.random()))
        bases.extend(vs[:5 if wide else 3])
    for k,vs in bins.items():
        vs.sort(key=lambda v:(len(anc[v]),rng.random()))
        bases.extend(vs[:10 if wide else 7])
    # powers and other bases chosen by coverage; use L2 cheaply
    bases=sorted(set(bases),reverse=True)
    used=set()
    probe = stratified(list(expr), 6) if bidir else []
    # per target beam recursion, expressions are immutable (tuple trees), cost union
    def leaf(v): return (anc[v],())
    def build_fallback(v):
        if v in expr: return
        if v<=1: raise ValueError("missing unit")
        # Guaranteed recursive construction from 1; use existing inexpensive nodes.
        b=16 if v<4096 else 256
        if v<=b:
            a=v//2;c=v-a
            build_fallback(a);build_fallback(c);add(v,('+',a,c));return
        q,r=divmod(v,b)
        build_fallback(b);build_fallback(q)
        p=q*b;add(p,('*',q,b))
        if r:
            build_fallback(r);add(v,('+',p,r))
    for t in ts:
        @lru_cache(None)
        def rec(v,depth):
            if v in expr: return leaf(v)
            if depth<=0 or v<=1: return None
            cand=[]
            direct=None; direct_cost=10**9
            if bidir:
                # Reverse operation with a known operand; hash lookup of its complement.
                for a in dict.fromkeys(probe + sorted(used)):
                    for o,b,rev in (('+',v-a,False),('-',a-v,False),('-',v+a,True),('*',v//a if v%a==0 else 0,False),('/',v*a,True),('/',a//v if a%v==0 else 0,False)):
                        if b not in expr or not 0<b<=L: continue
                        ds=anc[a]|anc[b]|{v}; c=len(ds-used)
                        if c<direct_cost:
                            direct=(ds,((v,(o,b,a) if rev else (o,a,b)),)); direct_cost=c
                if direct_cost==1: return direct
            for a in bases:
                if a>=v: continue
                q,r=divmod(v,a)
                for qq,rr,sign in ((q,r,'+'),(q+1,a-r,'-')):
                    if qq>=v or a*qq>L: continue
                    if rr and rr not in expr: continue
                    # rank split by residual + base cost + estimated remaining magnitude
                    c=len((anc[a]|(anc[rr] if rr else set()))-used)+(1 if not rr else 2)
                    est=c+(len(anc[qq]-used) if qq in expr else max(2,(qq.bit_length()-9)*.30))
                    cand.append((est, a,qq,rr,sign))
            cand.sort()
            best=direct; bc=direct_cost
            for _,a,q,r,sign in cand[:width]:
                sub=rec(q,depth-1)
                if sub is None: continue
                p=a*q; ds=sub[0]|anc[a]|{p}; es=sub[1]+((p,('*',a,q)),)
                if r: ds=ds|anc[r]|{v};es=es+((v,(sign,p,r)),)
                cost=len(ds-used)
                if cost<bc: best=(ds,es);bc=cost
            return best
        out=rec(t,4)
        if out is None:
            build_fallback(t);used|=anc[t];continue
        for v,e in out[1]:
            if v not in expr:
                expr[v]=e;anc[v]=anc[e[1]]|anc[e[2]]|{v}
        used|=anc[t]
    # Compile the value DAG in depth-first order.
    order=[]; visited=set(s)
    def visit(v):
        if v in visited: return
        o,a,b=expr[v]; visit(a);visit(b);visited.add(v);order.append(v)
    for t in ts: visit(t)
    from collections import Counter
    remaining=Counter(x for v in order for x in expr[v][1:])
    live={v:i for i,v in enumerate(s)}; prog=[]; achieved=set(s); regs=list(s)+[None]*(48-len(s))
    def ensure(v,protect):
        if v in live: return
        o,a,b=expr[v];ensure(a,protect);ensure(b,protect|{a})
        ai,bi=live[a],live[b]
        free=set(range(48))-set(live.values())
        if free: d=min(free)
        else:
            cand=[k for k in live if k not in protect and k not in s]
            if not cand: raise ValueError('pressure')
            k=min(cand,key=lambda k:(remaining[k]>0,len(anc[k]),remaining[k]));d=live.pop(k)
        prog.append([o,ai,bi,d]);live[v]=d
        x,y=regs[ai],regs[bi]
        z=x+y if o=='+' else x-y if o=='-' else x*y if o=='*' else x//y
        assert o!='/' or x%y==0
        assert z==v and 0<z<=L
        regs[d]=z;achieved.add(z)
    for v in order:
        ensure(v,set())
        for x in expr[v][1:]: remaining[x]-=1
        for k in list(live):
            if k not in s and remaining[k]==0: live.pop(k)
    assert set(ts)<=achieved and len(prog)<=4096
    return len(prog),len(order),prog

def joint_polish(row, program, alternate=None, rounds=0):
    """Greedy shared dependency optimization of the current run's generated DAG."""
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
        for i in range(j):
            a=vals[i]
            for o,b,rev in (('+',v-a,False),('-',a-v,False),('-',a+v,True),('*',v//a if v%a==0 else 0,False),('/',v*a,True),('/',a//v if a%v==0 else 0,False)):
                k=get(b,-1)
                if not 0<=k<j:continue
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
    def change(i,k):
        if k==choice[i]:return
        active=refs[i]>0
        if active:_,a,b=opts[i][choice[i]];rem(a);rem(b)
        choice[i]=k
        if active:_,a,b=opts[i][k];add(a);add(b)
    for i in roots:add(i)
    original_cost=cost;best_cost=cost;best_choice=choice.copy();rng=random.Random(123)
    mutable=[i for i in range(ns,N) if len(opts[i])>1]
    for sweep in range(6):
        rng.shuffle(mutable)
        for i in mutable:
            if not refs[i]:continue
            bk=choice[i];bc=cost
            for k in range(len(opts[i])):
                change(i,k)
                if cost<bc or (cost==bc and rng.random()<.12):bk=k;bc=cost
            change(i,bk)
        if cost<best_cost:best_cost=cost;best_choice=choice.copy()
    if rounds:
        import math
        for step in range(rounds):
            active=[i for i in mutable if refs[i]]
            if not active:break
            sub=rng.sample(active,min(len(active),rng.choice((2,3,5))))
            saved=[(i,choice[i]) for i in sub];before=cost
            for i in sub:
                if rng.random()<.5:change(i,rng.randrange(len(opts[i])))
            for i in sub:
                bk=choice[i];bc=cost
                for k in range(len(opts[i])):
                    change(i,k)
                    if cost<bc or (cost==bc and rng.random()<.1):bk=k;bc=cost
                change(i,bk)
            temp=max(.15,1.4*(1-step/rounds))
            if cost>before and rng.random()>math.exp((before-cost)/temp):
                for i,k in reversed(saved):change(i,k)
            if cost<best_cost:best_cost=cost;best_choice=choice.copy()
    choice=best_choice
    if alternate is None and not rounds and best_cost>=original_cost:return program
    if best_cost>=len(program):return program
    best=program
    for mode in range(3):
        order=[];seen=set(range(ns))
        def visit(i):
            if i in seen:return
            _,a,b=opts[i][choice[i]];visit(a);visit(b);seen.add(i);order.append(i)
        for i in sorted(roots,key=(lambda i:vals[i]) if mode==2 else None,reverse=mode==1):visit(i)
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

def optimize_v2(job):
    row,thorough=job
    s=json.loads(row['starting_values']);ts=json.loads(row['targets']);L=int(row['value_limit']);best=None;method=None
    def consider(result,name):
        nonlocal best,method
        if result is not None:
            p=result[2]
            if best is None or len(p)<len(best):
                replay(row,p);best=p;method=name
    for b,d in [(2,2),(16,8),(64,8),(128,16),(256,16),(512,16),(1024,32),(2048,32),(4096,32),(4096,64),(8192,64),(16384,64),(32768,128),(65536,256),(1000,10),(10000,100)]:
        for rev in (False,True):
            try:consider(sparse(s,ts,L,b,d,rev),f'radix-{b}-{d}-{int(rev)}')
            except (ValueError,AssertionError,KeyError,RecursionError):pass
    if best is None:raise RuntimeError('no valid candidate: '+row['id'])
    if thorough and len(best)>len(set(ts)-set(s)):
        try:consider(adaptive(s,ts,L,0),'adaptive-0')
        except (ValueError,AssertionError,KeyError,RecursionError):pass
    baseline=len(best)
    if thorough and len(best)>len(set(ts)-set(s)):
        try:consider(adaptive(s,list(reversed(ts)),L,1,3,True),'adaptive-wide-reverse')
        except (ValueError,AssertionError,KeyError,RecursionError):pass
    before_joint=len(best)
    if thorough and len(best)>len(set(ts)-set(s)):
        try:
            new=joint_polish(row,best)
            if len(new)<len(best):
                replay(row,new);best=new;method+=' + joint'
        except (ValueError,AssertionError,KeyError,RecursionError):pass
    return row['id'],best,method,baseline,before_joint

def optimize(job):
    row,thorough=job
    pid,best,method,_,_=optimize_v2(job)
    v2=len(best)
    s=json.loads(row['starting_values']);ts=json.loads(row['targets']);L=int(row['value_limit'])
    alt=None
    if thorough and len(best)>len(set(ts)-set(s)):
        try:
            alt=adaptive(s,sorted(ts,reverse=True),L,2,3,True,True)[2]
            replay(row,alt)
        except (ValueError,AssertionError,KeyError,RecursionError):alt=None
    previous=best
    if alt is not None and len(alt)<len(best):best=alt;method='bidirectional'
    bidir=len(best)
    if thorough and len(best)>len(set(ts)-set(s)):
        try:
            other=previous if best is alt else alt
            new=joint_polish(row,best,other,rounds=100)
            if len(new)<len(best):replay(row,new);best=new;method+=' + fusion-LNS'
        except (ValueError,AssertionError,KeyError,RecursionError):pass
    return pid,best,method,v2,bidir
