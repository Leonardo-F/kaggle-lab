import sys,json,time,sqlite3,csv,concurrent.futures,hashlib,fcntl,argparse
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from run7 import native
from experiment import compile_graph,replay
from scheduler import schedule
from scheduler8 import schedule8

def run(row):
 st=time.monotonic();s=json.loads(row['starting_values']);t=json.loads(row['targets']);L=row['value_limit'];data=' '.join(map(str,[L,len(s),len(t),*s,*t]));g,_=native('order',[6,3],data);ps={};nodes={};stats={}
 def evaluate(k,g):
  p,n=compile_graph(row,g,tries=4);p,_=schedule(row,g,p,tries=16);p,_=schedule8(row,g,p);replay(row,p);ps[k]=p;nodes[k]=n
 evaluate('order',g)
 h,info=native('variants/basis12free/basis',[6,3],data);evaluate('basis',h);stats['basis']=info
 inp=' '.join(map(str,[L,len(s),len(t),len(h),*s,*t]))+'\n'+''.join(f'{v} {o} {a} {b}\n' for v,(o,a,b) in h.items())
 for k,exe,m in [('basis3','synth',3),('basis4','variants/synth9/synth9',4)]:
  hh,info=native(exe,[m],inp);evaluate(k,hh);stats[k]=info
 scores={k:len(v) for k,v in ps.items()};return dict(id=row['id'],scores=scores,programs=ps,nodes=nodes,stats=stats,seconds=round(time.monotonic()-st,3))
def main():
 p=argparse.ArgumentParser();p.add_argument('--limit',type=int,default=12);p.add_argument('--jobs',type=int,default=4);p.add_argument('--split',choices=['dev','holdout'],default='dev');a=p.parse_args();raw=ROOT.parent/'puzzles.csv';splits=json.loads((ROOT/'splits.json').read_text());assert hashlib.sha256(raw.read_bytes()).hexdigest()==splits['sha256'];by={r['id']:r for r in csv.DictReader(raw.open())};ids=splits[a.split];dbpath=Path(__file__).parent/(a.split+'.sqlite');files=[Path(__file__),*map(lambda x:ROOT/x,['order','synth','scheduler.py','scheduler8.py','experiment.py','run7.py','variants/basis12free/basis','variants/synth9/synth9'])];sig=json.dumps({str(f.relative_to(ROOT)):hashlib.sha256(f.read_bytes()).hexdigest() for f in files},sort_keys=True)
 with open(str(dbpath)+'.lock','a') as lock:
  fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB);db=sqlite3.connect(dbpath);db.execute('create table if not exists meta(v text)');db.execute('create table if not exists records(id text primary key,payload text)');old=db.execute('select v from meta').fetchone();assert not old or old[0]==sig
  if not old:db.execute('insert into meta values(?)',(sig,));db.commit()
  done={i:json.loads(r) for i,r in db.execute('select id,payload from records')};assert all(replay(by[i],v)==r['scores'][k] for i,r in done.items() for k,v in r['programs'].items());todo=[i for i in ids if i not in done][:a.limit]
  with concurrent.futures.ProcessPoolExecutor(max_workers=a.jobs) as ex:
   fs={ex.submit(run,by[i]):i for i in todo}
   for f in concurrent.futures.as_completed(fs):
    i=fs[f]
    try:r=f.result();assert all(replay(by[i],v)==r['scores'][k] for k,v in r['programs'].items())
    except Exception as e:print('FAIL',i,repr(e),flush=True);continue
    db.execute('insert into records values(?,?)',(i,json.dumps(r,separators=(',',':'))));db.commit();done[i]=r;print(len(done),i,r['scores'],r['stats'],flush=True)
  print('SUMMARY',len(done),{k:sum(r['scores'][k] for r in done.values()) for k in ('order','basis','basis3','basis4')},flush=True)
if __name__=='__main__':main()
