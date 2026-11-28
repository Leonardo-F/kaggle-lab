"""Restricted acyclic hypergraph MILP; fresh candidate graphs only."""
import numpy as np
from scipy.optimize import milp, Bounds, LinearConstraint
from scipy.sparse import coo_matrix
from collections import defaultdict

def optimize(row, graphs, seed, seconds=0.7):
    import json
    S=set(json.loads(row['starting_values'])); T=set(json.loads(row['targets']))
    rank={v:0 for v in S}
    def visit(v):
        if v in rank:return
        _,a,b=seed[v];visit(a);visit(b);rank[v]=len(rank)*2
    for v in sorted(T):visit(v)
    pool=S|T|set().union(*(set(g) for g in graphs))|set(seed)
    edges=defaultdict(set)
    def add(v,o,a,b):
        if v in S or v==a or v==b or v not in pool:return
        if o in '+*' and a>b:a,b=b,a
        edges[v].add((o,a,b))
    for g in [*graphs,seed]:
        for v,(o,a,b) in g.items():add(v,o,a,b)
    vals=sorted(pool)
    for i,a in enumerate(vals):
        for b in vals[:i+1]:
            add(a+b,'+',a,b);add(a*b,'*',a,b)
            if a>b:add(a-b,'-',a,b)
            if a%b==0:add(a//b,'/',a,b)
    missing=pool-rank.keys()
    while missing:
        changed=False
        for v in sorted(missing):
            r=min((max(rank[a],rank[b])+.5 for _,a,b in edges[v] if a in rank and b in rank),default=float('inf'))
            if r<float('inf'):rank[v]=r;changed=True
        missing=pool-rank.keys()
        if not changed:break
    E=[];by=defaultdict(list);uses=defaultdict(list)
    for v in sorted(rank):
        for o,a,b in sorted(edges[v]):
            if a in rank and b in rank and max(rank[a],rank[b])<rank[v]:
                j=len(E);E.append((v,o,a,b));by[v].append(j)
                for x in {a,b}-S:uses[x].append(j)
    rr=[];cc=[];vv=[];lo=[];hi=[]
    def constraint(pos,neg,lb,ub):
        k=len(lo);lo.append(lb);hi.append(ub)
        for j in pos:rr.append(k);cc.append(j);vv.append(1.)
        for j in neg:rr.append(k);cc.append(j);vv.append(-1.)
    for v in by:constraint(by[v],[],1 if v in T else 0,1)
    for v,js in uses.items():
        for j in js:constraint([j],by[v],-np.inf,0)
    n=len(E)
    if not n:return seed,{'edges':0,'status':0}
    constraint(list(range(n)),[],0,len(seed))
    A=coo_matrix((vv,(rr,cc)),shape=(len(lo),n)).tocsc()
    res=milp(np.ones(n),integrality=np.ones(n),bounds=Bounds(0,1),constraints=LinearConstraint(A,lo,hi),options={'time_limit':seconds,'mip_rel_gap':0.0,'presolve':True})
    info={'edges':n,'values':len(rank),'status':int(res.status),'gap':getattr(res,'mip_gap',None),'bound':getattr(res,'mip_dual_bound',None),'incumbent':getattr(res,'fun',None)}
    if res.x is None:return seed,info
    out={v:(o,a,b) for (v,o,a,b),x in zip(E,res.x) if x>.5}
    clean={};seen=set(S)
    def keep(v):
        if v in seen:return
        o,a,b=out[v];keep(a);keep(b);seen.add(v);clean[v]=(o,a,b)
    try:
        for v in sorted(T):keep(v)
    except (KeyError,RecursionError):return seed,info
    return (clean if len(clean)<=len(seed) else seed),info
