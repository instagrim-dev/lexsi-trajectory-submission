"""Evaluate a base model or adapter on the frozen multi-step episode set."""
import argparse,hashlib,json,platform,time
from pathlib import Path
from experiment import run_episode,summarize
from model_runner import SYSTEM,build_messages,parse_action

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--model',required=True);p.add_argument('--revision',required=True);p.add_argument('--data',required=True);p.add_argument('--plan',required=True);p.add_argument('--out',required=True);p.add_argument('--adapter');a=p.parse_args()
 raw=Path(a.data).read_bytes();plan=json.loads(Path(a.plan).read_text());sha=lambda b:hashlib.sha256(b).hexdigest()
 if sha(raw)!=plan['heldout_sha256'] or sha(SYSTEM.encode())!=plan['system_prompt_sha256'] or a.revision!=plan['revision_claim']:
  p.error('heldout data, prompt or recorded revision differs from frozen plan')
 rows=[json.loads(x) for x in raw.decode().splitlines() if x.strip()]
 if not rows:p.error('empty evaluation set')
 out=Path(a.out);out.mkdir(parents=True,exist_ok=False)
 import torch,transformers
 from transformers import AutoModelForCausalLM,AutoTokenizer
 tok=AutoTokenizer.from_pretrained(a.model,local_files_only=True);model=AutoModelForCausalLM.from_pretrained(a.model,local_files_only=True,torch_dtype='auto')
 dev='mps' if torch.backends.mps.is_available() else 'cpu';model.to(dev)
 if a.adapter:
  from peft import PeftModel
  model=PeftModel.from_pretrained(model,a.adapter,is_trainable=False)
 model.eval();results=[]
 class Policy:
  def __init__(self):self.raw=[]
  def __call__(self,task,history):
   x=tok.apply_chat_template(build_messages(task,history),tokenize=True,add_generation_prompt=True,return_dict=True,return_tensors='pt').to(dev)
   with torch.inference_mode():y=model.generate(**x,do_sample=False,max_new_tokens=plan['max_new_tokens'],pad_token_id=tok.eos_token_id)
   raw=tok.decode(y[0][x['input_ids'].shape[-1]:],skip_special_tokens=True).strip();self.raw.append(raw)
   return parse_action(raw) or raw
 policy=Policy()
 with (out/'results.jsonl').open('x') as f:
  for row in rows:
   policy.raw=[];start=time.monotonic();result=run_episode(row,policy,max_steps=plan['max_episode_steps'])
   result['raw_model_outputs']=list(policy.raw);result['elapsed_seconds']=round(time.monotonic()-start,3)
   f.write(json.dumps(result,sort_keys=True)+'\n');f.flush();results.append(result)
   print(row['id'],'safe=',result['safe_completion'],'unsafe=',result['unsafe_attempts'],'invalid=',result['invalid_calls'],flush=True)
 stats=summarize(results);stats['total_steps']=sum(len(r['visible_trace']) for r in results)
 meta={'model':a.model,'revision_claim':a.revision,'revision_note':'supplied revision not independently verified','adapter':a.adapter,
  'adapter_sha256':sha((Path(a.adapter)/'adapter_model.safetensors').read_bytes()) if a.adapter else None,
  'heldout_sha256':sha(raw),'plan_sha256':sha(Path(a.plan).read_bytes()),'system_prompt_sha256':sha(SYSTEM.encode()),
  'decoding':plan['decoding'],'max_new_tokens':plan['max_new_tokens'],'max_episode_steps':plan['max_episode_steps'],
  'device':dev,'python':platform.python_version(),'torch':str(torch.__version__),'transformers':transformers.__version__,
  'summary':stats,'scope':'18 held-out prompts and scenario instances, same six synthetic mechanisms as training'}
 (out/'summary.json').write_text(json.dumps(meta,indent=2,sort_keys=True)+'\n');print(json.dumps(meta,indent=2),flush=True)
if __name__=='__main__':main()
