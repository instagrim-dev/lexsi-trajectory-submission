"""Tiny Aya supervised LoRA via AgentTune on disjoint scripted clarification families."""
import argparse, hashlib, json, platform, time, traceback
from pathlib import Path
from ambiguity_study.prompt import SYSTEM

def main():
 p=argparse.ArgumentParser();p.add_argument('--model',required=True);p.add_argument('--data',required=True);p.add_argument('--out',required=True);p.add_argument('--steps',type=int,default=32);a=p.parse_args()
 out=Path(a.out);out.mkdir(parents=True,exist_ok=False);started=time.monotonic()
 try:
  raw=Path(a.data).read_bytes();rows=[json.loads(x) for x in raw.splitlines() if x.strip()]
  import torch,transformers,trl,peft,datasets
  from transformers import AutoModelForCausalLM,AutoTokenizer
  from trl import SFTConfig,SFTTrainer
  from peft import LoraConfig
  from agenttune.agentic import Event,EventKind,EventLog,Project
  if not torch.backends.mps.is_available():raise RuntimeError('MPS unavailable')
  project=Project()
  for row in rows:
   if row['system']!=SYSTEM: raise ValueError('prompt drift')
   log=EventLog(tier='full');log.append(Event(EventKind.OBSERVATION,{'text':row['prompt']}));log.append(Event(EventKind.TEXT,{'text':row['response']}));project.add_trajectory(log)
  class Factory:
   def __call__(self,*,model,train_dataset,**kwargs):
    self.tokenizer=AutoTokenizer.from_pretrained(model,local_files_only=True)
    if self.tokenizer.pad_token is None:self.tokenizer.pad_token=self.tokenizer.eos_token
    base=AutoModelForCausalLM.from_pretrained(model,local_files_only=True,torch_dtype=torch.float16).to('mps');base.config.use_cache=False
    data=[];token_lengths=[]
    for item in train_dataset:
     messages=item['messages']
     if len(messages)!=2 or messages[0]['role']!='user' or messages[1]['role']!='assistant':raise ValueError('unexpected AgentTune row')
     prompt=[{'role':'system','content':SYSTEM},messages[0]];completion=[messages[1]]
     length=len(self.tokenizer.apply_chat_template(prompt+completion,tokenize=True,add_generation_prompt=False)['input_ids']);token_lengths.append(length)
     if length>1024:raise ValueError('training row exceeds 1024 tokens')
     data.append({'prompt':prompt,'completion':completion})
    print('training rows',len(data),'max tokens',max(token_lengths),'total example tokens',sum(token_lengths),flush=True)
    cfg=SFTConfig(output_dir=str(out/'trainer'),max_steps=a.steps,per_device_train_batch_size=1,gradient_accumulation_steps=1,learning_rate=0.0001,logging_steps=4,save_strategy='no',report_to='none',bf16=False,fp16=False,gradient_checkpointing=False,max_length=1024,completion_only_loss=True,seed=42,include_num_input_tokens_seen=True)
    transformers.set_seed(42)
    self.trainer=SFTTrainer(model=base,args=cfg,train_dataset=datasets.Dataset.from_list(data),processing_class=self.tokenizer,peft_config=LoraConfig(r=4,lora_alpha=8,lora_dropout=0.0,task_type='CAUSAL_LM',target_modules=['q_proj','v_proj']))
    self.lengths=token_lengths
    return self.trainer
  meta={'training_sha256':hashlib.sha256(raw).hexdigest(),'system_sha256':hashlib.sha256(SYSTEM.encode()).hexdigest(),'examples':len(rows),'training_families':sorted(set(r['family'] for r in rows)),'steps_requested':a.steps,'method':'AgentTune Project.train supervised LoRA r=4, scripted Go demonstrations','device':'mps','seed':42,'python':platform.python_version(),'torch':str(torch.__version__),'transformers':transformers.__version__,'trl':trl.__version__,'datasets':datasets.__version__,'peft':peft.__version__,'split':'training surcharge and median; held-out invoice and event families'}
  (out/'metadata.json').write_text(json.dumps(meta,indent=2)+'\n')
  factory=Factory();result=project.train(factory,fmt='sft',model=a.model);factory.trainer.save_model(str(out/'adapter'));factory.tokenizer.save_pretrained(str(out/'adapter'))
  if torch.backends.mps.is_available():torch.mps.synchronize()
  summary={'status':'completed','wall_seconds':time.monotonic()-started,'global_step':int(result.global_step),'training_loss':float(result.training_loss),'metrics':result.metrics,'token_lengths':factory.lengths,'log_history':factory.trainer.state.log_history}
  (out/'train-result.json').write_text(json.dumps(summary,indent=2,default=str)+'\n'); print(json.dumps(summary,default=str),flush=True)
 except BaseException as e:
  (out/'train-result.json').write_text(json.dumps({'status':'failed','wall_seconds':time.monotonic()-started,'error':type(e).__name__,'detail':str(e)},indent=2)+'\n'); traceback.print_exc();raise
if __name__=='__main__':main()
