"""Independent validation of a generated submission, using only the puzzle definitions and output CSV."""
import argparse,csv,json,hashlib
from pathlib import Path

def verify(puzzles,submission):
    with open(puzzles,newline='') as f: rows=list(csv.DictReader(f))
    with open(submission,newline='') as f:
        reader=csv.DictReader(f)
        if reader.fieldnames!=['id','program']:raise ValueError('wrong submission header')
        result=list(reader)
    pids=[r['id'] for r in rows]; ids=[r['id'] for r in result]
    if len(pids)!=len(set(pids)) or len(ids)!=len(set(ids)) or set(pids)!=set(ids):raise ValueError('wrong or duplicate puzzle IDs')
    programs={r['id']:r['program'] for r in result}; scores=[]
    for row in rows:
        pid=row['id'];raw=programs[pid];start=json.loads(row['starting_values']);target=set(json.loads(row['targets']));limit=int(row['value_limit']);n=int(row['registers'])
        if len(raw.encode('utf-8'))>131072:raise ValueError(f'{pid}: program bytes')
        prog=json.loads(raw)
        if type(prog) is not list or len(prog)>4096:raise ValueError(f'{pid}: program length')
        regs=dict(enumerate(start));missing=target-set(start)
        for i,ins in enumerate(prog,1):
            if type(ins) is not list or len(ins)!=4:raise ValueError(f'{pid}:{i}: invalid instruction')
            op,a,b,d=ins
            if any(type(k) is not int or not 0<=k<n for k in (a,b,d)):raise ValueError(f'{pid}:{i}: invalid register')
            if a not in regs or b not in regs:raise ValueError(f'{pid}:{i}: undefined register')
            x,y=regs[a],regs[b]
            if op=='+': z=x+y
            elif op=='-':z=x-y
            elif op=='*':z=x*y
            elif op=='/':
                z,rem=divmod(x,y)
                if rem:raise ValueError(f'{pid}:{i}: nonexact division')
            else:raise ValueError(f'{pid}:{i}: invalid operator')
            if not 1<=z<=limit:raise ValueError(f'{pid}:{i}: result out of range')
            regs[d]=z;missing.discard(z)
        if missing:raise ValueError(f'{pid}: missing {len(missing)} targets')
        scores.append(len(prog))
    return {'puzzles':len(rows),'validated':len(scores),'score':sum(scores),'max_steps':max(scores,default=0),'submission_sha256':hashlib.sha256(Path(submission).read_bytes()).hexdigest(),'puzzles_sha256':hashlib.sha256(Path(puzzles).read_bytes()).hexdigest()}

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('puzzles');p.add_argument('submission');p.add_argument('--report');a=p.parse_args();r=verify(a.puzzles,a.submission);print(json.dumps(r,indent=2));
    if a.report:Path(a.report).write_text(json.dumps(r,indent=2)+'\n')
