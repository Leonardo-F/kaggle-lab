"""V4: independent quotient-neighbor matching and fresh DAG fusion."""

import json
import random
from functools import lru_cache

from . import v3
from .common import ops, replay
from .v3 import joint_polish

def adaptive_v4(s,ts,L,seed=3,width=3,wide=True,bidir=True):
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
    # Expand a stratified subset of cheap values into products and differences.
    mid=stratified([v for v in l2 if len(anc[v])<=3], 4)
    for i,a in enumerate(mid):
        for b in mid[:i+1]:
            for v,e in ops(a,b,L): add(v,e)
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
    from bisect import bisect_left
    for t in ts:
        current_bases=sorted(set(bases)|set(stratified([v for v in used if v>1],3)),reverse=True)
        known=sorted(expr)
        probes=list(dict.fromkeys(probe+sorted(used)))
        @lru_cache(None)
        def rec(v,depth):
            if v in expr: return leaf(v)
            if depth<=0 or v<=1: return None
            cand=[]
            direct=None; direct_cost=10**9
            if bidir:
                # Reverse operation with a known operand; hash lookup of its complement.
                for a in probes:
                    for o,b,rev in (('+',v-a,False),('-',a-v,False),('-',v+a,True),('*',v//a if v%a==0 else 0,False),('/',v*a,True),('/',a//v if a%v==0 else 0,False)):
                        if b not in expr or not 0<b<=L: continue
                        ds=anc[a]|anc[b]|{v}; c=len(ds-used)
                        if c<direct_cost:
                            direct=(ds,((v,(o,b,a) if rev else (o,a,b)),)); direct_cost=c
                if direct_cost==1: return direct
            for a in current_bases:
                if a>=v: continue
                q,r=divmod(v,a)
                splits=[(q,r,'+'),(q+1,a-r,'-')]
                # Match a nearby already constructible quotient; the residue
                # need not be the conventional remainder modulo a.
                pos=bisect_left(known,q)
                for qq in known[max(0,pos-1):pos+2]:
                    p=a*qq
                    if p<=L and p!=v:
                        splits.append((qq,abs(v-p),'+' if p<v else '-'))
                for qq,rr,sign in dict.fromkeys(splits):
                    if qq<1 or qq>=v or a*qq>L: continue
                    if rr and rr not in expr: continue
                    # rank split by residual + base cost + estimated remaining magnitude
                    c=len((anc[a]|(anc[rr] if rr else set()))-used)+(1 if not rr else 2)
                    if qq in expr:
                        p=a*qq
                        ds=anc[a]|anc[qq]|(anc[rr] if rr else set())|{p,v}
                        if p in expr:ds=anc[p]|(anc[rr] if rr else set())|{v}
                        est=len(ds-used)
                    else:
                        est=c+max(2,(qq.bit_length()-9)*.30)
                    cand.append((est, a,qq,rr,sign))
            cand.sort()
            best=direct; bc=direct_cost
            for _,a,q,r,sign in cand[:width]:
                sub=rec(q,depth-1)
                if sub is None: continue
                p=a*q
                if p in expr:
                    ds=anc[p];es=()
                else:
                    ds=sub[0]|anc[a]|{p}; es=sub[1]+((p,('*',a,q)),)
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


def optimize_v4(job):
    row,full=job
    s=json.loads(row['starting_values']);ts=json.loads(row['targets']);L=int(row['value_limit'])
    if full:pid,best,method,_,_=v3.optimize((row,True))
    else:pid,best,method,_,_=v3.optimize_v2((row,True))
    baseline=len(best)
    if baseline==len(set(ts)-set(s)):return pid,best,method,baseline,baseline,False
    try:
        alt=adaptive_v4(s,sorted(ts,reverse=True),L)[2];replay(row,alt)
    except (ValueError,AssertionError,KeyError,RecursionError):return pid,best,method,baseline,baseline,False
    raw=len(alt)
    if raw<len(best):best,alt=alt,best;method='v4-mitm'
    try:
        new=joint_polish(row,best,alt,rounds=100)
        if len(new)<len(best):replay(row,new);best=new;method+=' + v4-fusion'
    except (ValueError,AssertionError,KeyError,RecursionError):pass
    return pid,best,method,baseline,raw,True
