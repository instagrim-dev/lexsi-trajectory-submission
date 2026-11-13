"""Check whether rejected witnesses were valid except for JSON field spelling.

No inference or new candidates are generated. Only renaming case and common
camel/snake variants is allowed; values, inputs and programs stay unchanged.
This diagnostic cannot reconstruct any downstream agent decisions.
"""
import json, sys, time
from pathlib import Path
from ambiguity_study import benchmark


def name(s): return ''.join(c for c in s.casefold() if c.isalnum()) if isinstance(s,str) else ''

def normalized(family,witness):
    if not isinstance(witness,dict):return None
    if len(witness)==1 and isinstance(witness.get('input'),dict):witness=witness['input']
    m={name(k):v for k,v in witness.items()}
    try:
        if family=='finance':
            return {'lines':[{'price':{name(k):v for k,v in x.items()}['price'],
                              'qty':{name(k):v for k,v in x.items()}['qty'],
                              'taxable':{name(k):v for k,v in x.items()}['taxable']} for x in m['lines']],
                    'discount_bp':m['discountbp'],'tax_bp':m['taxbp']}
        return {'events':[{'key':{name(k):v for k,v in x.items()}['key'],
                           'sequence':{name(k):v for k,v in x.items()}['sequence'],
                           'value':{name(k):v for k,v in x.items()}['value']} for x in m['events']]}
    except (KeyError,TypeError,AttributeError):return None


def main(root):
    root=Path(root);out=root/'offline-witness-recheck.jsonl'
    if out.exists():raise SystemExit('refusing to overwrite')
    tasks={t['id']:t for t in benchmark.tasks('eval')}; results=[]
    for arm in ('generic','trained','generic-adaption'):
        path=root/(arm+'-model.jsonl')
        if not path.exists():continue
        for row in map(json.loads,path.read_text().splitlines()):
            if row.get('event')!='finished':continue
            response=row.get('parsed') or {}
            if not all(k in response for k in ('left_code','right_code','witness')):continue
            taskid=row['call_id'].split(':')[1];task=tasks[taskid];original=response['witness']
            if benchmark.valid_input(task['family'],original):continue
            candidate=normalized(task['family'],original)
            if candidate is None or not benchmark.valid_input(task['family'],candidate):continue
            start=time.monotonic()
            result=benchmark.validate_witness(task,response['left_code'],response['right_code'],candidate)
            results.append({'arm':arm,'task':taskid,'call_id':row['call_id'],'normalized_witness':candidate,
                            'result':result,'elapsed_s':time.monotonic()-start})
    with out.open('x') as f:
        for result in results:f.write(json.dumps(result,sort_keys=True)+'\n')
    print('normalized witness candidates',len(results),'valid',sum(x['result']['valid'] for x in results),
          'go workers',sum(x['result']['workers'] for x in results),'seconds',round(sum(x['elapsed_s'] for x in results),4))

if __name__=='__main__':main(sys.argv[1])
