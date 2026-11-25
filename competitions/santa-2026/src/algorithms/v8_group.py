"""V8 Final: bounded destroy/repair with joint beam selection of cut-node expressions."""
import json, random
from collections import Counter
from . import v8_rewrite as core
from .v8_three import inverse, optimize as prior, exclusive
from .v8_register import schedule

def cut_repair(row, program, rounds=8, neutral=True):
    s=json.loads(row['starting_values']); start=set(s); ts=list(dict.fromkeys(json.loads(row['targets']))); L=int(row['value_limit'])
    g=core.v7.extract(row,program); cl,active=core.closures(g,s,ts);g={x:g[x] for x in active}; best=program
    initial=len(active); rng=random.Random(884); accepted=flat=trials=0
    for turn in range(rounds):
        if len(active)<4:break
        refs=Counter(ts)
        for v in active:
            _,a,b=g[v];refs[a]+=1;refs[b]+=1
        ranked=sorted(active,key=lambda v:(-len(exclusive(g,start,v,refs)),-len(cl[v]),v))
        ranked=[v for v in ranked if len(cl[v])>1]
        if not ranked:break
        anchor=ranked[turn%min(len(ranked),12)] if turn<4 else rng.choice(ranked[:min(24,len(ranked))])
        cuts=[anchor];size=2+turn%3
        eligible=[v for v in ranked if v!=anchor and anchor not in cl[v] and v not in cl[anchor]]
        eligible.sort(key=lambda v:(-len(cl[v]&cl[anchor]),abs(v.bit_length()-anchor.bit_length()),-len(cl[v]),v))
        if turn%3==2:rng.shuffle(eligible)
        for v in eligible:
            if all(v not in cl[w] and w not in cl[v] for w in cuts):cuts.append(v)
            if len(cuts)==size:break
        if len(cuts)<2:continue
        cs=set(cuts)
        _,fixed=core.closures(g,start|cs,ts)
        safe=[v for v in sorted(start|active) if not (cl[v]&cs)]
        safe.sort(key=lambda v:(len(cl[v]-fixed),len(cl[v]),v))
        vals=safe[:180]
        if len(safe)>180:vals+=rng.sample(safe[180:],min(32,len(safe)-180))
        vs=set(vals); pool=core.pairs(vals,L)
        fresh={x:min(es,key=lambda e:(len((cl[e[1]]|cl[e[2]])-fixed),e)) for x,es in pool.items() if x not in cl and x not in cs}
        alternatives={}
        for v in cuts:
            old=g[v]; opts=[(old,None,cl[v]-{v})];seen={(old,None)}
            for a in vals:
                for b,e in inverse(v,a,L):
                    if b in vs: aux=None;dep=cl[a]|cl[b]
                    elif b in fresh:
                        aux=(b,fresh[b]);_,c,d=aux[1];dep=cl[a]|cl[c]|cl[d]|{b}
                    else:continue
                    key=(e,aux)
                    if key not in seen:seen.add(key);opts.append((e,aux,dep))
            opts.sort(key=lambda o:(len(o[2]-fixed),len(o[2]),o[0]));alternatives[v]=opts
        share=Counter(x for opts in alternatives.values() for x in {o[1][0] for o in opts if o[1]})
        for v,opts in alternatives.items():
            orig=next(o for o in opts if o[0]==g[v] and o[1] is None)
            shared=sorted((o for o in opts if o[1] and share[o[1][0]]>1),key=lambda o:(len(o[2]-fixed)-share[o[1][0]]*.8,len(o[2]),o[0]))
            alternatives[v]=list(dict.fromkeys([orig]+opts[:14]+shared[:10]))
        beam=[(frozenset(fixed),{})];cuts.sort(key=lambda v:(len(alternatives[v]),v))
        for v in cuts:
            expanded=[]
            for used,patch in beam:
                for e,aux,dep in alternatives[v]:
                    new=patch|{v:e}
                    if aux:new[aux[0]]=aux[1]
                    u=used|dep|{v};expanded.append((u,new))
            expanded.sort(key=lambda z:(len(z[0]),len(z[1]),tuple(sorted(z[1].items()))))
            beam=[];seen=set()
            for u,p in expanded:
                sig=tuple(sorted(p.items()))
                if sig in seen:continue
                seen.add(sig);beam.append((u,p))
                if len(beam)>=10:break
        choices=[]
        for _,patch in beam:
            if all(g.get(v)==e for v,e in patch.items()):continue
            trial=g|patch
            try:tc,ta=core.closures(trial,s,ts)
            except (ValueError,KeyError,RecursionError):continue
            trials+=1
            if len(ta)>len(active)+(1 if neutral and turn%3==2 else 0):continue
            if len(ta)>initial+1:continue
            choices.append((len(ta),trial,tc,ta))
        if not choices:continue
        choices.sort(key=lambda x:x[0]);cost,trial,tc,ta=choices[0]
        for _,candidate,_,_ in choices[:3]:
            new=core.compile_graph(row,candidate,best)
            if len(new)<len(best):best=new
        if cost<len(active) or (neutral and turn%3==2 and cost<=len(active)+1):
            flat+=int(cost>=len(active));accepted+=1;g={v:trial[v] for v in ta};cl,active=tc,ta
    core.replay(row,best)
    return best,{'group_moves':accepted,'group_nonimproving':flat,'group_trials':trials}

def optimize(row):
    pid,base,m=prior(row)
    strict,a=cut_repair(row,base,rounds=6,neutral=False)
    mixed,b=cut_repair(row,strict,rounds=8,neutral=True)
    best,attempts,gap=schedule(row,mixed,tries=32)
    core.replay(row,best)
    m.update(v8group_strict=len(strict),v8group_neutral=len(mixed),v8final=len(best),group_moves=a['group_moves']+b['group_moves'],group_nonimproving=b['group_nonimproving'],group_trials=a['group_trials']+b['group_trials'],schedule_attempts=attempts,remat_gap=gap)
    return pid,best,m
