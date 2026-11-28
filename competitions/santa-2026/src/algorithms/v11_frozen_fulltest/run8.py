import argparse,concurrent.futures,csv,fcntl,hashlib,json,sqlite3,subprocess,sys,time
from pathlib import Path
from experiment import compile_graph,replay
from scheduler import schedule
from exact_graph import optimize
from scheduler8 import schedule8
ROOT=Path(__file__).resolve().parent
ROUTES=[('order',6,3),('factor',6,3),('bilayer',6,3),('congruence/congruence',6,3)]
def native(exe,args,data):
 z=subprocess.run([str(ROOT/exe),*map(str,args)],input=data,text=True,capture_output=True,check=True,timeout=45); lines=z.stdout.splitlines();g={int(v):(o,int(a),int(b)) for v,o,a,b in (line.split() for line in lines[1:])};assert len(g)==int(lines[0]);return g,z.stderr.strip()
def run(row):
 st=time.monotonic();s=json.loads(row['starting_values']);t=json.loads(row['targets']);data=' '.join(map(str,[row['value_limit'],len(s),len(t),*s,*t]));gs=[];programs={};nodes={};errors={};stats={};graphs={}
 def evaluate(name,g):
  p,n=compile_graph(row,g,tries=4);p,_=schedule(row,g,p,tries=16);replay(row,p);programs[name]=p;nodes[name]=n;graphs[name]=g
 for exe,w,m in ROUTES:
  try:g,_=native(exe,[w,m],data);evaluate(exe,g);gs.append(g)
  except Exception as e:errors[exe]=repr(e)
 if not gs:raise ValueError('no fresh graph')
 inp=' '.join(map(str,[row['value_limit'],len(s),len(t),len(gs),*s,*t]))+'\n'+''.join(str(len(g))+'\n'+''.join(f'{v} {o} {a} {b}\n' for v,(o,a,b) in g.items()) for g in gs)
 for name,exe,h in [('union', 'hyper',0)]:
  try:g,info=native(exe,[h,8],inp);evaluate(name,g);stats[name]=info
  except Exception as e:errors[name]=repr(e)
 base=min(programs,key=lambda k:len(programs[k]))
 try:
  g,info=optimize(row,list(graphs.values()),graphs[base],seconds=0.7);evaluate('milp',g);stats['milp']=info
 except Exception as e:errors['milp']=repr(e)
 baseline=min(programs,key=lambda k:len(programs[k])); seed=graphs[baseline]
 for mode in (2,3):
  try:
   inp=' '.join(map(str,[row['value_limit'],len(s),len(t),len(seed),*s,*t]))+'\n'+''.join(f'{v} {o} {a} {b}\n' for v,(o,a,b) in seed.items())
   g,info=native('synth',[mode],inp);evaluate(f'synth{mode}',g);stats[f'synth{mode}']=info
  except Exception as e:errors[f'synth{mode}']=repr(e)
 base8=min(programs,key=lambda k:len(programs[k]))
 for name in list(programs):
  if len(programs[name])<=len(programs[base8])+12 and len(programs[name])>nodes[name]:
   try:
    p,info=schedule8(row,graphs[name],programs[name]);stats['sched8_'+name]=info
    if len(p)<len(programs[name]):programs['sched8_'+name]=p;nodes['sched8_'+name]=nodes[name];graphs['sched8_'+name]=graphs[name]
   except Exception as e:errors['sched8_'+name]=repr(e)
 scores={k:len(v) for k,v in programs.items()};winner=min(scores,key=scores.get)
 return dict(id=row['id'],scores=scores,nodes=nodes,errors=errors,stats=stats,programs=programs,winner=winner,score=scores[winner],seconds=round(time.monotonic()-st,3))
def main():
 p=argparse.ArgumentParser();p.add_argument('puzzles',type=Path);p.add_argument('--db',type=Path,required=True);p.add_argument('--split',choices=['dev','holdout','all'],default='dev');p.add_argument('--jobs',type=int,default=4);p.add_argument('--limit',type=int);a=p.parse_args();sha=lambda x:hashlib.sha256(x.read_bytes()).hexdigest();m=json.loads((ROOT/'splits.json').read_text());assert sha(a.puzzles)==m['sha256'];by={r['id']:r for r in csv.DictReader(a.puzzles.open())};ids=m[a.split] if a.split!='all' else list(by);meta=json.dumps(dict(input=sha(a.puzzles),split=a.split,python=sys.version,files={x.name:sha(x) for x in [*ROOT.glob('*.py'),*ROOT.glob('*.cpp'),*[ROOT/n for n in ('order','wide','factor','hyper','bilayer','hyperunion','modular','scaled','splits.json','congruence/congruence','synth')]]}),sort_keys=True)
 with open(str(a.db)+'.lock','a') as lock:
  fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB);db=sqlite3.connect(a.db);db.execute('create table if not exists meta(v text)');db.execute('create table if not exists records(id text primary key,payload text)');old=db.execute('select v from meta').fetchone()
  if old and old[0]!=meta:raise ValueError('fingerprint mismatch')
  if not old:db.execute('insert into meta values(?)',(meta,));db.commit()
  done={}
  for i,payload in db.execute('select id,payload from records'):
   r=json.loads(payload);assert i in ids and all(replay(by[i],v)==r['scores'][k] for k,v in r['programs'].items());done[i]=r
  todo=[i for i in ids if i not in done][:a.limit]
  with concurrent.futures.ProcessPoolExecutor(max_workers=a.jobs) as ex:
   fs={ex.submit(run,by[i]):i for i in todo}
   for f in concurrent.futures.as_completed(fs):
    i=fs[f]
    try:r=f.result();assert all(replay(by[i],v)==r['scores'][k] for k,v in r['programs'].items())
    except Exception as e:print('FAIL',i,repr(e),flush=True);continue
    db.execute('insert into records values(?,?)',(i,json.dumps(r,separators=(',',':'))));db.commit();done[i]=r;print(len(done),i,r['scores'],r['errors'],r['seconds'],flush=True)
  print('SUMMARY',len(done),sum(r['score'] for r in done.values()),flush=True);db.close()
if __name__=='__main__':main()
