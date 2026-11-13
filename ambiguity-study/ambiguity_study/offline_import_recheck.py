"""Recheck recorded candidate functions with their declared safe stdlib imports.

This is an offline diagnostic, not a rerun of agent trajectories. It cannot
reconstruct feedback or later choices. Candidates remain network-denied and
filesystem-write-confined; unrecognized imports/directives are never executed.
"""
import hashlib, json, os, re, shutil, subprocess, sys, tempfile, time
from pathlib import Path
from ambiguity_study import benchmark
from ambiguity_study.model import parse_response

ALLOWED={'math','sort','strings','strconv','math/bits'}

def extract(raw):
    txt=raw.strip()
    if txt.startswith('```') and txt.endswith('```'):
        parts=txt.split('\n',1)
        if len(parts)<2:return None
        txt=parts[1].rsplit('```',1)[0].strip()
    try:
        obj=json.loads(txt)
        if not isinstance(obj,dict) or obj.get('action')!='solve' or not isinstance(obj.get('code'),str):return None
        txt=obj['code']
    except (ValueError,TypeError):
        pass
    if re.search(r'//go:|/\*go:',txt):return None
    matched=re.findall(r'(?ms)^\s*import\s*(?:\((.*?)\)|"([^"]+)")',txt)
    if not matched:return None
    imports=[]
    for group,single in matched:
        if single:imports.append(single)
        else:
            parts=group.splitlines()
            if any(not re.fullmatch(r'\s*"[A-Za-z0-9_/]+"\s*',p) for p in parts if p.strip()):return None
            imports.extend(re.findall(r'"([^"]+)"',group))
    if not imports or any(i not in ALLOWED for i in imports):return None
    first=re.search(r'(?m)^func\s+\w+\s*\(',txt)
    if not first:return None
    code=txt[first.start():].strip()
    if not re.search(r'\bfunc\s+Compute\s*\(',code) or re.search(r'(?m)^\s*(?:package|import)\b',code):return None
    return imports,code


def run(task,imports,code):
    family=task['family'];inputs=benchmark.cases(family,'plausibility')+benchmark.cases(family,'accept')
    t='type Line struct { Price, Qty int64; Taxable bool }' if family=='finance' else 'type Event struct { Key string; Sequence, Value int64 }'
    imp=';'.join(json.dumps(x) for x in sorted(set(['fmt','testing']+imports)))
    calls='\n'.join('fmt.Printf("VALUE:%%d\\n", Compute(%s))'%benchmark.go_input(family,c) for c in inputs)
    source='package main\nimport ('+imp+')\n'+t+'\n'+code+'\nfunc TestCandidate(t *testing.T){\n'+calls+'\n}\n'
    cache=Path.home()/'.cache/bmo/go/build';mod=Path.home()/'.cache/bmo/go/mod'
    with tempfile.TemporaryDirectory(prefix='amb-import-recheck-') as temp_dir:
        d=str(Path(temp_dir).resolve())
        p=Path(d); (p/'candidate_test.go').write_text(source)
        env={'PATH':'/usr/local/go/bin:/opt/homebrew/bin:/usr/bin:/bin','HOME':str(Path.home()),'GOCACHE':str(cache),'GOMODCACHE':str(mod),'GO111MODULE':'off','GOTOOLCHAIN':'local','GOTELEMETRY':'off','TMPDIR':d}
        profile='(version 1)(allow default)(deny network*)(deny file-write*)(allow file-write* (subpath '+json.dumps(d)+'))(allow file-write* (subpath '+json.dumps(str(cache))+'))(allow file-write* (subpath '+json.dumps(str(mod))+'))(allow file-write* (literal "/dev/null"))'
        go=shutil.which('go',path=env['PATH']) or '/usr/local/go/bin/go';start=time.monotonic()
        try:
            x=subprocess.run(['/usr/bin/sandbox-exec','-p',profile,go,'test','-v','-count=1','-timeout=15s'],cwd=d,env=env,text=True,capture_output=True,timeout=30)
            output=(x.stdout+'\n'+x.stderr)[-3000:]; vals=[int(v) for v in re.findall(r'^VALUE:(-?\d+)$',output,re.M)]
            modes=('line','subtotal') if family=='finance' else ('earliest','latest')
            matching=[m for m in modes if x.returncode==0 and vals==[benchmark.expected(family,m,c) for c in inputs]]
            return {'status':'ok' if x.returncode==0 else 'worker_failure','exit_code':x.returncode,'workers':1,'elapsed_s':time.monotonic()-start,
                    'matching_full_mode':matching,'matches_hidden':task['mode'] in matching,'output':output}
        except subprocess.TimeoutExpired:return {'status':'timeout','workers':1,'elapsed_s':time.monotonic()-start}


def main(root):
    out=Path(root)/'offline-import-recheck.jsonl'
    if out.exists():raise SystemExit('refusing to overwrite')
    tasks={t['id']:t for t in benchmark.tasks('eval')}
    seen={}; results=[]
    for arm in ('generic','trained','generic-adaption'):
        p=Path(root)/(arm+'-model.jsonl')
        if not p.exists():continue
        for row in map(json.loads,p.read_text().splitlines()):
            if row.get('event')!='finished':continue
            call=row['call_id'].split(':');taskid=call[1]
            parsed=extract(row.get('raw',''))
            if parsed is None:continue
            imports,code=parsed; task=tasks[taskid]; key=(task['family'],tuple(imports),code)
            start=time.monotonic()
            if key not in seen:seen[key]=run(task,imports,code)
            result=dict(seen[key]);result['matches_hidden']=task['mode'] in result.get('matching_full_mode',[])
            key_digest=hashlib.sha256(json.dumps(key).encode()).hexdigest()
            result.update({'arm':arm,'task':taskid,'call_id':row['call_id'],'imports':imports,'cache_reused':any(v.get('key')==key_digest for v in results),'key':key_digest})
            results.append(result)
    with out.open('x') as f:
        for result in results:f.write(json.dumps(result,sort_keys=True)+'\n')
    print('candidate occurrences',len(results),'unique worker executions',len(seen),'matching complete declared interpretation',sum(bool(x.get('matching_full_mode')) for x in results))

if __name__=='__main__':main(sys.argv[1])
