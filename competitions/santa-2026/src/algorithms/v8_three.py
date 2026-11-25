"""V8.1: bounded three-operation subgraph rewriting on a fresh V8.0 graph."""
import json,random
from collections import Counter,defaultdict
from . import v8_rewrite as core

def inverse(t,a,L):
    for op,b,rev in (('+',t-a,False),('-',a-t,False),('-',t+a,True),('*',t//a if t%a==0 else 0,False),('/',t*a,True),('/',a//t if a%t==0 else 0,False)):
        if 0<b<=L:
            yield b,(op,b,a) if rev else (op,a,b)

def exclusive(g,start,v,refs):
    ref=refs.copy();removed=set()
    def drop(x):
        ref[x]-=1
        if ref[x]==0 and x not in start:
            removed.add(x);_,a,b=g[x];drop(a);drop(b)
    _,a,b=g[v];drop(a);drop(b);return removed

def three(row,program,sweeps=2,budget=10,neutral=False):
    s=json.loads(row['starting_values']);ts=list(dict.fromkeys(json.loads(row['targets'])));L=int(row['value_limit']);start=set(s)
    g=core.v7.extract(row,program);cl,active=core.closures(g,s,ts);g={x:g[x] for x in active};best=program;accepted=0;equal=0
    rng=random.Random(832)
    for _ in range(sweeps):
        refs=Counter(ts)
        for v in active:
            _,a,b=g[v];refs[a]+=1;refs[b]+=1
        targets=[]
        for v in sorted(active):
            removed=exclusive(g,start,v,refs)
            if len(removed)>= (2 if neutral else 3):targets.append((len(removed),v,removed))
        targets.sort(key=lambda x:(-x[0],-x[1]));changed=False
        for _,v,removed in targets[:budget]:
            kept=active-removed
            vals=sorted((kept|start)-{v},key=lambda x:(len(cl[x]),x))
            vals=[x for x in vals if v not in cl[x]]
            if not vals:continue
            pool=core.pairs(vals,L)
            pool={x:es[0] for x,es in pool.items() if x not in cl and x!=v}
            if not pool:continue
            bins=defaultdict(list)
            for x in pool:bins[x.bit_length()].append(x)
            probes=[]
            for bit,xs in sorted(bins.items()):
                xs.sort();probes.extend(rng.sample(xs,min(96,len(xs))))
            proposals=[]
            for x in probes:
                for y,e in inverse(v,x,L):
                    if y in pool:proposals.append({x:pool[x],y:pool[y],v:e})
                if len(proposals)>=4:break
            short=vals[:48]
            if len(vals)>48:short+=rng.sample(vals[48:],min(24,len(vals)-48))
            for a in short:
                for b,e in inverse(v,a,L):
                    if b in cl or b==v:continue
                    for c in short:
                        for d,eb in inverse(b,c,L):
                            if d in pool and d!=b:proposals.append({d:pool[d],b:eb,v:e})
                            if len(proposals)>=8:break
                        if len(proposals)>=8:break
                    if len(proposals)>=8:break
                if len(proposals)>=8:break
            candidate=None;bestsize=len(active)+int(neutral)
            for p in proposals:
                trial=g|p
                try:tc,ta=core.closures(trial,s,ts)
                except (ValueError,KeyError,RecursionError):continue
                if len(ta)<bestsize:bestsize=len(ta);candidate=(trial,tc,ta)
            if candidate:
                g,cl,newactive=candidate;equal+=int(len(newactive)==len(active));active=newactive;g={x:g[x] for x in active};accepted+=1;changed=True;break
        if not changed:break
    best=core.compile_graph(row,g,best)
    if neutral and accepted and len(best)==len(program):
        try:
            witness=core.compile_graph(row,g,program+[None]*8)
            if None not in witness:
                alt,_,_=core.rewrite(row,witness,2)
                if len(alt)<len(best):best=alt
        except (ValueError,KeyError,RecursionError,AssertionError):pass
    core.replay(row,best)
    return best,accepted,equal

def optimize(row):
    pid,base,m=core.optimize(row);strict,a,_=three(row,base);neutral,b,c=three(row,strict,neutral=True);core.replay(row,neutral)
    m.update(v81=len(strict),v82=len(neutral),three_moves=a,neutral_moves=b,neutral_equal=c);return pid,neutral,m
