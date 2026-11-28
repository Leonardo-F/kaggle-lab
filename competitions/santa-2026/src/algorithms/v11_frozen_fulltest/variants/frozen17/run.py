"""Fresh R16 portfolio runner for holdout or official full test. No prior-answer inputs."""
import argparse,csv,sqlite3,json,sys,hashlib,concurrent.futures,fcntl,time,os,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
import run8
from variants.basis12synth.run_basis import run as basis
from experiment import replay
from repo_verify import verify
ROUTES={'r8':run8.run,'basis':basis}
def work(group,row):
 r=ROUTES[group](row);assert r['programs'] and all(replay(row,p)==r['scores'][k] for k,p in r['programs'].items());return r

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('puzzles',type=Path);p.add_argument('--db',type=Path,required=True);p.add_argument('--split',choices=['dev','holdout','all'],default='holdout');p.add_argument('--jobs',type=int,default=4);p.add_argument('--limit',type=int,default=10000);p.add_argument('--export',type=Path);a=p.parse_args()
 raw=a.puzzles.resolve();split=json.loads((ROOT/'splits.json').read_text());sha=lambda f:hashlib.sha256(f.read_bytes()).hexdigest();assert sha(raw)==split['sha256'];by={r['id']:r for r in csv.DictReader(raw.open())};ids=split[a.split] if a.split!='all' else list(by)
 files=[Path(__file__),*ROOT.glob('*.py'),*map(lambda x:ROOT/x,['order','factor','bilayer','congruence/congruence','hyper','synth','variants/basis12free/basis','variants/synth9/synth9','variants/basis12synth/run_basis.py','splits.json'])];sig=json.dumps(dict(input=sha(raw),split=a.split,python=sys.version,files={str(f.relative_to(ROOT)):sha(f) for f in files}),sort_keys=True)
 a.db.parent.mkdir(parents=True,exist_ok=True)
 with open(str(a.db)+'.lock','a') as lock:
  fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB);db=sqlite3.connect(a.db);db.execute('create table if not exists meta(v text)');db.execute('create table if not exists groups(id text,route text,payload text,primary key(id,route))');prev=db.execute('select v from meta').fetchone();assert not prev or prev[0]==sig,'configuration changed'
  if not prev:db.execute('insert into meta values(?)',(sig,));db.commit()
  saved={}
  for i,g,z in db.execute('select id,route,payload from groups'):
   r=json.loads(z);assert i in ids and g in ROUTES and r['programs'] and all(replay(by[i],v)==r['scores'][k] for k,v in r['programs'].items());saved[i,g]=r
  # prioritise groups needed to complete partially solved IDs; otherwise original split order
  ordered=sorted(ids,key=lambda i: (-sum((i,g) in saved for g in ROUTES),ids.index(i)))
  tasks=[(i,g) for i in ordered for g in ROUTES if (i,g) not in saved][:a.limit]
  with concurrent.futures.ProcessPoolExecutor(max_workers=a.jobs) as ex:
   fs={ex.submit(work,g,by[i]):(i,g) for i,g in tasks}
   for f in concurrent.futures.as_completed(fs):
    i,g=fs[f]
    try:r=f.result()
    except Exception as e:print('FAIL',i,g,repr(e),flush=True);continue
    db.execute('insert into groups values(?,?,?)',(i,g,json.dumps(r,separators=(',',':'))));db.commit();saved[i,g]=r;print(i,g,min(r['scores'].values()),r['seconds'],flush=True)
  complete=[i for i in ids if all((i,g) in saved for g in ROUTES)];print('SUMMARY',len(complete),sum(min(len(p) for g in ROUTES for p in saved[i,g]['programs'].values()) for i in complete),flush=True)
  if a.export:
   if len(complete)!=len(ids):raise ValueError('refuse to export incomplete submission')
   with a.export.open('w',newline='') as f:
    w=csv.DictWriter(f,fieldnames=['id','program']);w.writeheader();w.writerows(dict(id=i,program=json.dumps(min((p for g in ROUTES for p in saved[i,g]['programs'].values()),key=len),separators=(',',':'))) for i in ids)
   with tempfile.TemporaryDirectory() as d:
    subset=Path(d)/'puzzles.csv';with_rows=[by[i] for i in ids]
    with subset.open('w',newline='') as f:w=csv.DictWriter(f,fieldnames=list(with_rows[0]));w.writeheader();w.writerows(with_rows)
    print(verify(subset,a.export),flush=True)
if __name__=='__main__':main()
