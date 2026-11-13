"""Longitudinal matched Adaption Go competence-boundary study.

All cases, provider attempts, replays, checks, failures and timing are retained.
The benchmark is synthetic; this harness is not the production BMO application.
"""
from __future__ import annotations
import hashlib,json,os,re,subprocess,sys,time,urllib.error,urllib.request
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT))
from decision_slice.competence_boundary import CompetenceBoundary
MODEL='gemma-4-26b-a4b-it'; ENDPOINT='https://api.prod.adaptionlabs.ai/api/v1/responses'
ARMS=('generic','learned'); MAX_ATTEMPTS=3
SPECS=[{'id':'invoice-a','name':'Calculate','per_line':True,'tax_before':False}, {'id':'renamed-a','name':'PriceOrder','per_line':True,'tax_before':False}, {'id':'tax-revision','name':'Calculate','per_line':True,'tax_before':True}, {'id':'rounding-revision','name':'PriceOrder','per_line':False,'tax_before':False}, {'id':'return-a','name':'Calculate','per_line':True,'tax_before':False}]
CASES=[([{'Price':101,'Qty':1,'Taxable':True},{'Price':203,'Qty':3,'Taxable':False}],2500,1000),([{'Price':5,'Qty':1,'Taxable':True},{'Price':5,'Qty':1,'Taxable':True},{'Price':19,'Qty':1,'Taxable':False}],1000,2500),([{'Price':799,'Qty':2,'Taxable':True},{'Price':1100,'Qty':1,'Taxable':True}],1700,875),([{'Price':99,'Qty':4,'Taxable':False},{'Price':51,'Qty':3,'Taxable':True}],3333,2000),([{'Price':7,'Qty':1,'Taxable':True},{'Price':11,'Qty':1,'Taxable':False},{'Price':13,'Qty':1,'Taxable':True}],3700,1850),([{'Price':1000,'Qty':2,'Taxable':True}],0,1000),([{'Price':12,'Qty':2,'Taxable':False}],10000,2500),([],1000,1000),([{'Price':29,'Qty':3,'Taxable':True},{'Price':41,'Qty':2,'Taxable':False},{'Price':13,'Qty':5,'Taxable':True}],2750,1375),([{'Price':1,'Qty':5,'Taxable':True},{'Price':1,'Qty':5,'Taxable':True},{'Price':15,'Qty':1,'Taxable':False}],3000,9000),([{'Price':149,'Qty':2,'Taxable':False},{'Price':37,'Qty':9,'Taxable':True}],1999,1711)]
def digest(x): return hashlib.sha256(x.encode()).hexdigest()
def key():
 lines=Path(os.environ['BMO_ENV_PATH']).read_text().splitlines()
 for l in reversed(lines):
  if l.startswith('ADAPTION_API_KEY='): return l.split('=',1)[1].strip().strip('"').strip("'")
 raise RuntimeError('Adaption key absent')
def jlog(path,x):
 with path.open('a') as f: f.write(json.dumps(x,sort_keys=True)+'\n'); f.flush(); os.fsync(f.fileno())
def calc(spec,lines,discount,tax):
 def rnd(x): return (x+5000)//10000
 raw=sum(l['Price']*l['Qty'] for l in lines); taxable=sum(l['Price']*l['Qty'] for l in lines if l['Taxable'])
 if spec['per_line']:
  discounted=sum(rnd(l['Price']*l['Qty']*(10000-discount)) for l in lines); taxable_disc=sum(rnd(l['Price']*l['Qty']*(10000-discount)) for l in lines if l['Taxable'])
 else:
  taxable_disc=rnd(taxable*(10000-discount)); discounted=taxable_disc+rnd((raw-taxable)*(10000-discount))
 return discounted+rnd((taxable if spec['tax_before'] else taxable_disc)*tax)
def desc(s):
 d='Round each line after its discount, then sum the rounded lines.' if s['per_line'] else 'Sum taxable lines and non-taxable lines into two subtotals, then separately discount and round each subtotal.'
 t='Compute tax from the ORIGINAL taxable subtotal before discount.' if s['tax_before'] else 'Compute tax from the DISCOUNTED taxable subtotal.'
 return f'{d} {t} Round tax once and add it to the discounted total. Rounding means nearest integer cent with half rounded up: (numerator+5000)/10000. Discounts and taxes are basis points out of 10000. Ignore empty lines. Input amounts are nonnegative.'
def normalize(src,name):
 # Names are incidental task surface; candidate code is bound to current interface.
 return re.sub(r'\b(?:Calculate|PriceOrder)\b',name,src)
def extract(out,name):
 fenced=re.findall(r'```(?:go)?\s*(.*?)```',out,re.S|re.I); src=(fenced[-1] if fenced else out).strip(); i=src.find('func ')
 if i<0:return None
 src=src[i:]; src=src.replace('package main','').strip()
 if re.search(r'(?m)^\s*import\b|\b(os|exec|net|syscall|unsafe)\s*\.',src): return None
 if not re.search(r'func\s+'+re.escape(name)+r'\s*\(',src): return None
 return src

def check(out,arm,spec,src,indices,stage,expected_map=None):
 started=time.monotonic(); d=out/'checks'/str(time.monotonic_ns()); d.mkdir(parents=True)
 # Every candidate is executed with its independent input-output reference in a confined worker.
 test=[]
 for i in indices:
  lines,discount,tax=CASES[i]; literal=','.join('{%d,%d,%s}'%(l['Price'],l['Qty'],str(l['Taxable']).lower()) for l in lines); want=expected_map[i] if expected_map is not None else calc(spec,lines,discount,tax)
  test.append('if got := '+spec['name']+'([]Line{'+literal+'},'+str(discount)+','+str(tax)+'); got != '+str(want)+' { t.Errorf("case=%d got=%%d want=%d",got) }'%(i,want))
 text='package main\nimport "testing"\ntype Line struct { Price int64; Qty int64; Taxable bool }\n'+normalize(src,spec['name'])+'\nfunc TestCandidate(t *testing.T) {\n'+'\n'.join(test)+'\n}\n'
 (d/'candidate_test.go').write_text(text)
 cache=Path.home()/'.cache/bmo/go/build'; mod=Path.home()/'.cache/bmo/go/mod'; cache.mkdir(parents=True,exist_ok=True);mod.mkdir(parents=True,exist_ok=True)
 env={'PATH':'/usr/local/go/bin:/opt/homebrew/bin:/usr/bin:/bin','HOME':str(Path.home()),'GOCACHE':str(cache),'GOMODCACHE':str(mod),'GO111MODULE':'off','GOTOOLCHAIN':'local','GOTELEMETRY':'off','TMPDIR':str(d)}
 # Network disabled; writes limited to the task fixtures and shared build cache.
 profile='(version 1)(allow default)(deny network*)(deny file-write*)(allow file-write* (subpath '+json.dumps(str(out.resolve()))+'))(allow file-write* (subpath '+json.dumps(str(cache))+'))(allow file-write* (subpath '+json.dumps(str(mod))+'))(allow file-write* (literal "/dev/null"))'
 cmd=['/usr/bin/sandbox-exec','-p',profile,'/usr/local/go/bin/go','test','-count=1','-timeout=15s']
 try:
  p=subprocess.run(cmd,cwd=d,env=env,text=True,capture_output=True,timeout=30); ok=p.returncode==0; output=(p.stdout+'\n'+p.stderr)[-6000:]; rc=p.returncode
 except subprocess.TimeoutExpired: ok=False;output='timeout';rc=None
 row={'stage':stage,'arm':arm,'task':spec['id'],'cases':indices,'passed':ok,'returncode':rc,'output':output,'elapsed_s':time.monotonic()-started,'source_hash':digest(src)}; jlog(out/'checks.jsonl',row); return row

def failure(stage, checked, source, spec):
 indices=sorted({int(i) for i in re.findall(r'case=(\d+) got=',checked['output'])})
 return {'stage':stage,'output':checked['output'],'candidate_source':source,'counterexamples':[{'index':i,'lines':CASES[i][0],'discountBP':CASES[i][1],'taxBP':CASES[i][2],'expected':calc(spec,*CASES[i])} for i in indices]}

def provider(out,arm,task,attempt,prompt,secret):
 started=time.monotonic(); cid=f'{arm}:{task}:{attempt}:{time.monotonic_ns()}'
 jlog(out/'provider.jsonl',{'phase':'started','call_id':cid,'arm':arm,'task':task,'attempt':attempt,'prompt':prompt})
 req=urllib.request.Request(ENDPOINT,data=json.dumps({'model':MODEL,'input':prompt,'max_output_tokens':4096}).encode(),headers={'Content-Type':'application/json','Authorization':'Bearer '+secret},method='POST')
 try:
  with urllib.request.urlopen(req,timeout=120) as resp: result=json.load(resp); status=resp.status
  text=''.join(p.get('text','') for x in result.get('output',[]) if x.get('type')=='message' for p in x.get('content',[]) if p.get('type')=='output_text'); err=None if text and result.get('model')==MODEL else 'unexpected_model_or_empty'
  row={'phase':'finished','call_id':cid,'status':status,'error':err,'response':text,'usage':result.get('usage'),'elapsed_s':time.monotonic()-started}
 except urllib.error.HTTPError as e: row={'phase':'finished','call_id':cid,'status':e.code,'error':'provider_http_error','elapsed_s':time.monotonic()-started}
 except Exception as e: row={'phase':'finished','call_id':cid,'error':type(e).__name__,'elapsed_s':time.monotonic()-started}
 jlog(out/'provider.jsonl',row); return row

def main(out):
 out.mkdir(parents=True,exist_ok=False); started=time.monotonic(); secret=key();
 (out/'protocol.json').write_text(json.dumps({'model':MODEL,'arms':ARMS,'tasks':SPECS,'max_candidate_attempts':MAX_ATTEMPTS,'qualification_cases':[0,1,2,3,4],'independent_acceptance_cases':[5,6,7,8,9,10],'budget_note':'learned reuse and failed compilation count as candidate attempts; semantic replay is additional work','task_scope':'synthetic Go invoice calculations, bound to specification and independently generated arithmetic examples','baseline':'same model, assignment, own full observed history and attempt budget; same-spec cache with identifier rebinding and fresh qualification in both arms; model may reuse any prior source','timing':'every assignment and all subprocesses recorded'},indent=2))
 states={a:{'history':[],'boundary':CompetenceBoundary(),'programs':[]} for a in ARMS}
 for ix,spec in enumerate(SPECS):
  for arm in (ARMS if ix%2==0 else ARMS[::-1]):
   task_start=time.monotonic(); state=states[arm]; prior=state['history']; failures=[]; attempted_programs=[]; attempts=0; accepted=False; selected=''; selected_pid=None; boundary=state['boundary']; boundary_work={'calls':0,'seconds':0.0}; features={'per_line':spec['per_line'],'tax_before':spec['tax_before']}; req=json.dumps(features,sort_keys=True); checks_before=sum(1 for _ in (out/'checks.jsonl').open()) if (out/'checks.jsonl').exists() else 0
   def bw(fn,*args):
    t=time.monotonic()
    try:return fn(*args)
    finally:boundary_work['calls']+=1;boundary_work['seconds']+=time.monotonic()-t
   candidates=[]
   task_key=desc(spec)
   cache_start=time.monotonic()
   cached=next((h for h in reversed(prior) if h['accepted'] and h.get('task_key')==task_key),None)
   cache_lookup_s=time.monotonic()-cache_start
   if cached: candidates.append(('exact_cache',cached['source'],cached['program_id']))
   opportunities=[]
   if arm=='learned':
    for prog in state['programs']:
     hypothesis=bw(boundary.hypothesis,prog['id']); allowed=bw(boundary.allows,prog['id'],features)
     opportunities.append({'program':prog['id'],'hypothesis':hypothesis,'allowed':allowed,'disposition':'cache_precedence' if cached else ('eligible' if allowed else 'abstain')})
     if allowed and not candidates: candidates.append(('learned',prog['source'],prog['id']))
   while attempts<MAX_ATTEMPTS:
    if candidates:
     origin,src,pid=candidates.pop(0)
    else:
     hist=[{'task':h['task'],'specification':h['specification'],'source':h.get('source'),'accepted':h['accepted'],'failures':h['failures']} for h in prior]
     prompt=('Write complete compilable Go source for the requested function. No package, imports, external calls, or main. '
       'The existing type is type Line struct { Price int64; Qty int64; Taxable bool }. '
       'Implement func '+spec['name']+'(lines []Line, discountBP int64, taxBP int64) int64. '+desc(spec)+' '
       'Return code only. Solve the current task. You may reuse or adapt any previous implementation. '\
       +'Previous task history: '+json.dumps(hist)+' Current attempt failures: '+json.dumps(failures))
     call=provider(out,arm,spec['id'],attempts,prompt,secret); attempts+=1
     if call.get('error'): failures.append({'stage':'provider','error':call['error']}); continue
     src=extract(call['response'],spec['name']); origin='model'; pid=digest(src or '')
     if not src: failures.append({'stage':'parse','error':'invalid_code'}); continue
    if origin in ('learned','exact_cache'):
     attempts+=1
     src=normalize(src,spec['name'])
    attempted_programs.append({'attempt':attempts,'origin':origin,'program_id':pid})
    examples=[]
    if arm=='learned':
     for retained_id in boundary.retained:
      examples+=bw(boundary.counterexamples,retained_id,req)
    replay_indices=sorted(set(x['case']['index'] for x in examples))
    if replay_indices:
     replay_expected={x['case']['index']:x['expected'] for x in examples}
     replay=check(out,arm,spec,src,replay_indices,'counterexample_replay',replay_expected)
     if not replay['passed']:
      failures.append(failure('replay',replay,src,spec)); continue
    qualified=check(out,arm,spec,src,list(range(5)),'qualification')
    if not qualified['passed']:
     failures.append(failure('qualification',qualified,src,spec))
     if origin=='learned' and re.search(r'case=(\d+) got=',qualified['output']):
      t=time.monotonic(); boundary.observe(pid,features,False,case={'task':spec['id'],'mismatches':qualified['output']},expected='qualified'); boundary_work['calls']+=1; boundary_work['seconds']+=time.monotonic()-t
     # Parse concrete behavioral counterexamples only, never compiler or infra errors.
     if arm=='learned':
      for idx in {int(x) for x in re.findall(r'case=(\d+) got=',qualified['output'])}:
       bw(boundary.retain_counterexample,pid,req,{'index':idx},calc(spec,*CASES[idx]))
     continue
    final=check(out,arm,spec,src,[5,6,7,8,9,10],'independent_acceptance')
    if not final['passed']:
     failures.append(failure('acceptance',final,src,spec))
     if origin=='learned' and re.search(r'case=(\d+) got=',final['output']):
      t=time.monotonic(); boundary.observe(pid,features,False,case={'task':spec['id'],'mismatches':final['output']},expected='accepted'); boundary_work['calls']+=1; boundary_work['seconds']+=time.monotonic()-t
     continue
    accepted=True;selected=origin; selected_pid=pid; src=normalize(src,spec['name'])
    if arm=='learned':
     t=time.monotonic(); boundary.observe(pid,features,True,case={'task':spec['id']},expected='accepted'); boundary_work['calls']+=1; boundary_work['seconds']+=time.monotonic()-t
     if not any(p['id']==pid for p in state['programs']):state['programs'].append({'id':pid,'source':src})
    break
   persistence_s=0.0
   if arm=='learned':
    t=time.monotonic(); boundary.dump(out/'boundary.json'); persistence_s=time.monotonic()-t
   row={'arm':arm,'task':spec['id'],'task_key':task_key,'cache_hit':bool(cached),'opportunities':opportunities,'cache_lookup_s':cache_lookup_s,'persistence_s':persistence_s,'specification':desc(spec),'features':features,'accepted':accepted,'selected':selected,'program_id':selected_pid,'attempted_programs':attempted_programs,'attempts':attempts,'failures':failures,'source':src if accepted else None,'elapsed_s':time.monotonic()-task_start,'boundary_work':boundary_work,'guard_state':{p['id']:bw(boundary.hypothesis,p['id']) for p in state['programs']} if arm=='learned' else None}; prior.append(row); jlog(out/'assignments.jsonl',row)
   print(arm,spec['id'],'accepted',accepted,'attempts',attempts,'route',selected,flush=True)
 elapsed=time.monotonic()-started
 (out/'wall.json').write_text(json.dumps({'elapsed_s':elapsed,'note':'includes assignment logging, boundary persistence and all task work; excludes final wall.json write and final print'}))
 print('elapsed',elapsed,flush=True)
if __name__=='__main__': main(Path(sys.argv[1]).resolve())
