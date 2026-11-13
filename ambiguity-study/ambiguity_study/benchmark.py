"""Bounded Go ambiguity benchmark; public prompts contain no hidden intent.

Each ambiguous prompt has two secret assignments with byte-identical public views.
The independent Python oracle assesses Go programs against retained inputs. The
candidate interpreter uses a network-denied macOS worker when available.
"""
from __future__ import annotations
import json, os, re, shutil, subprocess, tempfile, time
from pathlib import Path

FINANCE=("Implement func Compute(lines []Line, discountBP, taxBP int64) int64. "
 "type Line struct { Price, Qty int64; Taxable bool }. Price is cents and Qty is nonnegative. "
 "Apply discount to each order; tax the discounted taxable amount. All rates are basis points out of 10000. "
 "Round monetary results to the nearest cent, with half rounded up using (n+5000)/10000. "
 "Sum discounted line amounts and add tax rounded once. Discounts and taxes are between 0 and 10000. ")
EVENT=("Implement func Compute(events []Event) int64. type Event struct { Key string; Sequence, Value int64 }. "
 "Deduplicate records by Key according to their Sequence, retaining one record per key; "
 "return the sum of retained values. Input order is arbitrary and distinct records for a key have distinct Sequence. ")
FINANCE_CONTEXT={'train':['This operation settles a supplier order.','This routine totals a wholesale purchase.'], 'eval':['This calculation settles a service invoice.','This calculation totals a marketplace order.']}
EVENT_CONTEXT={'train':['This routine reconciles warehouse events.','This routine aggregates journal records.'], 'eval':['This routine reconciles sensor readings.','This routine aggregates shipment updates.']}


def tasks(split='eval'):
    if split not in ('train','eval'): raise ValueError('invalid split')
    out=[]
    for family,contexts,modes in [('finance',FINANCE_CONTEXT[split],('line','subtotal')),('events',EVENT_CONTEXT[split],('earliest','latest'))]:
        for i,context in enumerate(contexts):
            base=(FINANCE if family=='finance' else EVENT)+context
            for mode in modes:
                out.append({'id':f'{split}-{family}-{i}-amb-{mode}', 'family':family,'mode':mode,'ambiguous':True,'prompt':base})
            # Balanced resolved controls; names do not enter visible prompt.
            mode=modes[i % 2]
            detail=({'line':'Round each discounted line separately before summing.', 'subtotal':'First sum taxable and non-taxable subtotals separately; discount and round each subtotal.'} if family=='finance' else {'earliest':'Keep the event with the lowest Sequence for each key.','latest':'Keep the event with the highest Sequence for each key.'})[mode]
            out.append({'id':f'{split}-{family}-{i}-clear-{mode}', 'family':family,'mode':mode,'ambiguous':False,'prompt':base+' '+detail})
    return out


def public_view(task):
    return {'request':task['prompt']}


def user_answer(task,question):
    """Respond only to an understandable targeted semantic question.

    This deliberately recognizes a documented, conservative phrase family;
    otherwise it returns None and the query is unresolved, without leaking the
    hidden decision. Both experimental arms use exactly this same interpreter.
    """
    q=question.casefold()
    if task['family']=='finance' and ('round' in q or 'subtotal' in q) and any(x in q for x in ('line','item','subtotal','sum','aggregate','total','each','separat','when','stage','where')):
        return {'line':'Round each discounted line separately before summing.','subtotal':'Sum taxable and non-taxable subtotals separately, then discount and round each subtotal.'}[task['mode']]
    if task['family']=='events' and any(x in q for x in ('event','record','sequence','duplicate','dedup','key')) and any(x in q for x in ('earliest','latest','first','last','lowest','highest','which','keep','retain','choose','select')):
        return {'earliest':'Keep the record with the lowest Sequence per key.','latest':'Keep the record with the highest Sequence per key.'}[task['mode']]
    return None


def expected(family,mode,case):
    if family=='finance':
        lines=case['lines']; d=case['discount_bp']; tax=case['tax_bp']; rnd=lambda n:(n+5000)//10000
        if mode=='line':
            total=sum(rnd(x['price']*x['qty']*(10000-d)) for x in lines)
            taxable=sum(rnd(x['price']*x['qty']*(10000-d)) for x in lines if x['taxable'])
        else:
            a=sum(x['price']*x['qty'] for x in lines if x['taxable']); b=sum(x['price']*x['qty'] for x in lines if not x['taxable'])
            taxable=rnd(a*(10000-d)); total=taxable+rnd(b*(10000-d))
        return total+rnd(taxable*tax)
    if family=='events':
        selected={}
        for event in case['events']:
            old=selected.get(event['key'])
            if old is None or (event['sequence'] < old['sequence'] if mode=='earliest' else event['sequence'] > old['sequence']): selected[event['key']]=event
        return sum(e['value'] for e in selected.values())
    raise ValueError('unknown family')


def cases(family, split='accept'):
    if family=='finance':
        raw=[([(5,1,True),(5,1,True),(19,1,False)],1000,2500), ([(101,1,True),(203,3,False)],2500,1000), ([(7,1,True),(11,1,False),(13,1,True)],3700,1850), ([(29,3,True),(41,2,False),(13,5,True)],2750,1375), ([(1,5,True),(1,5,True),(15,1,False)],3000,9000), ([(149,2,False),(37,9,True)],1999,1711), ([],100,200), ([(1000,2,True)],0,1000)]
        all_cases=[{'lines':[{'price':p,'qty':q,'taxable':b} for p,q,b in lines], 'discount_bp':d,'tax_bp':t} for lines,d,t in raw]
    else:
        raw=[[('a',5,19),('a',2,7),('b',9,11),('b',3,-2)], [('x',10,4),('y',2,8),('x',11,99)], [], [('z',8,3)], [('a',7,0),('a',2,-8),('a',10,20),('b',3,7)], [('m',-9,17),('m',-1,-6),('n',4,5)], [('p',1,8),('q',2,4)]]
        all_cases=[{'events':[{'key':k,'sequence':seq,'value':v} for k,seq,v in rows]} for rows in raw]
    return all_cases[:3] if split=='plausibility' else all_cases[3:]


def valid_input(family,case):
    try:
        if family=='finance':
            ls=case['lines']; assert isinstance(ls,list) and len(ls)<=30
            assert all(isinstance(x['price'],int) and 0<=x['price']<=100000 and isinstance(x['qty'],int) and 0<=x['qty']<=1000 and type(x['taxable']) is bool for x in ls)
            assert all(isinstance(case[k],int) and 0<=case[k]<=10000 for k in ('discount_bp','tax_bp'))
        else:
            es=case['events']; assert isinstance(es,list) and len(es)<=30
            assert all(isinstance(x['key'],str) and len(x['key'])<=40 and isinstance(x['sequence'],int) and abs(x['sequence'])<1000000 and isinstance(x['value'],int) and abs(x['value'])<1000000 for x in es)
            assert len({(x['key'],x['sequence']) for x in es})==len(es)
        return True
    except (KeyError,TypeError,AssertionError): return False


def go_input(family,c):
    if family=='finance':
        rows=','.join('{%d,%d,%s}'%(x['price'],x['qty'],str(x['taxable']).lower()) for x in c['lines'])
        return '[]Line{%s}, %d, %d'%(rows,c['discount_bp'],c['tax_bp'])
    rows=','.join('{%s,%d,%d}'%(json.dumps(x['key']),x['sequence'],x['value']) for x in c['events'])
    return '[]Event{%s}'%rows


def execute(family,code,inputs):
    """Run candidate once across cases; return output, actual worker cost/status."""
    started=time.monotonic()
    if not isinstance(code,str) or len(code)>12000 or not re.search(r'\bfunc\s+Compute\s*\(',code) or re.search(r'(?m)^\s*(?:package|import)\b|//go:|/\*go:',code):
        return {'status':'invalid_source','values':[],'seconds':time.monotonic()-started,'workers':0}
    if not inputs or not all(valid_input(family,c) for c in inputs):
        return {'status':'invalid_input','values':[],'seconds':time.monotonic()-started,'workers':0}
    gotype='type Line struct { Price, Qty int64; Taxable bool }' if family=='finance' else 'type Event struct { Key string; Sequence, Value int64 }'
    calls='\n'.join('fmt.Printf("VALUE:%%d\\n", Compute(%s))'%go_input(family,c) for c in inputs)
    source='package main\nimport ("testing"; "fmt")\n'+gotype+'\n'+code+'\nfunc TestCandidate(t *testing.T){\n'+calls+'\n}\n'
    cache=Path.home()/'.cache/bmo/go/build';mod=Path.home()/'.cache/bmo/go/mod';cache.mkdir(parents=True,exist_ok=True);mod.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='ambiguity-') as d:
        path=Path(d).resolve(); d=str(path); (path/'candidate_test.go').write_text(source)
        env={'PATH':'/usr/local/go/bin:/opt/homebrew/bin:/usr/bin:/bin','HOME':str(Path.home()),'GOCACHE':str(cache),'GOMODCACHE':str(mod),'GO111MODULE':'off','GOTOOLCHAIN':'local','GOTELEMETRY':'off','TMPDIR':d}
        go=shutil.which('go',path=env['PATH']) or '/usr/local/go/bin/go'; cmd=[go,'test','-v','-count=1','-timeout=15s']
        if Path('/usr/bin/sandbox-exec').exists():
            profile='(version 1)(allow default)(deny network*)(deny file-write*)(allow file-write* (subpath '+json.dumps(d)+'))(allow file-write* (subpath '+json.dumps(str(cache))+'))(allow file-write* (subpath '+json.dumps(str(mod))+'))(allow file-write* (literal "/dev/null"))'
            cmd=['/usr/bin/sandbox-exec','-p',profile]+cmd
        try:
            p=subprocess.run(cmd,cwd=d,env=env,text=True,capture_output=True,timeout=30); output=(p.stdout+'\n'+p.stderr)[-10000:]
            vals=[int(v) for v in re.findall(r'^VALUE:(-?\d+)$',output,re.M)]
            status='ok' if p.returncode==0 and len(vals)==len(inputs) else 'worker_failure'
            return {'status':status,'values':vals,'seconds':time.monotonic()-started,'workers':1,'exit_code':p.returncode,'output':output}
        except subprocess.TimeoutExpired:
            return {'status':'timeout','values':[],'seconds':time.monotonic()-started,'workers':1}


def evaluate_code(task,code,probe_cases=None):
    inputs=cases(task['family']) if probe_cases is None else probe_cases
    run=execute(task['family'],code,inputs)
    want=[expected(task['family'],task['mode'],c) for c in inputs]
    return {**run,'passed':run['status']=='ok' and run['values']==want,'expected':want,'inputs':inputs}


def validate_witness(task,left_code,right_code,witness):
    """Confirm two real, plausible implementations diverge on supplied input.

    Uses no secret task mode: each candidate must fit one distinct legal mode on
    public plausibility inputs; the witness itself is executed independently.
    The caller must not give expected values from this validation to the model.
    """
    family=task['family']; modes=('line','subtotal') if family=='finance' else ('earliest','latest')
    if not valid_input(family,witness): return {'valid':False,'reason':'invalid_witness','workers':0,'seconds':0}
    sample=cases(family,'plausibility'); inputs=sample+[witness]
    left=execute(family,left_code,inputs); right=execute(family,right_code,inputs)
    work=left['workers']+right['workers']; secs=left['seconds']+right['seconds']
    if left['status']!='ok' or right['status']!='ok': return {'valid':False,'reason':'candidate_execution_failed','workers':work,'seconds':secs,'left':left,'right':right}
    matches=lambda r,m: r['values']==[expected(family,m,c) for c in inputs]
    assignments=[(a,b) for a in modes for b in modes if a!=b and matches(left,a) and matches(right,b)]
    valid=bool(assignments) and left['values'][-1]!=right['values'][-1]
    return {'valid':valid,'reason':'divergent_plausible_candidates' if valid else 'no_valid_distinction','workers':work,'seconds':secs,'left':left,'right':right,'interpretations':assignments}
