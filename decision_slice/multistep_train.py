"""AgentTune SFT on scripted multi-step simulator trace prefixes."""
import argparse,hashlib,json,platform,time
from pathlib import Path
from model_runner import SYSTEM

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--model',required=True);p.add_argument('--revision',required=True);p.add_argument('--data',required=True);p.add_argument('--out',required=True);p.add_argument('--steps',type=int,default=168);a=p.parse_args()
 if not 1<=a.steps<=500:p.error('steps must be between 1 and 500')
 raw=Path(a.data).read_bytes();rows=[json.loads(x) for x in raw.decode().splitlines() if x.strip()]
 if not rows or any(r.get('provenance')!='scripted_reference_in_synthetic_environment' for r in rows):p.error('invalid demonstrations')
 out=Path(a.out);out.mkdir(parents=True,exist_ok=False)
 import torch,transformers,trl,peft,datasets
 from transformers import AutoModelForCausalLM,AutoTokenizer
 from trl import SFTConfig,SFTTrainer
 from peft import LoraConfig
 from agenttune.agentic import Event,EventKind,EventLog,Project
 project=Project()
 for row in rows:
  if row['messages'][0] != {'role':'system','content':SYSTEM}:raise ValueError('training system prompt drift')
  log=EventLog(tier='full');log.append(Event(EventKind.OBSERVATION,{'text':row['messages'][1]['content']}))
  log.append(Event(EventKind.TEXT,{'text':json.dumps({'action':row['action']})}));project.add_trajectory(log)
 class Factory:
  def __call__(self,*,model,train_dataset,**kwargs):
   self.tokenizer=AutoTokenizer.from_pretrained(model,local_files_only=True)
   if self.tokenizer.pad_token is None:self.tokenizer.pad_token=self.tokenizer.eos_token
   base=AutoModelForCausalLM.from_pretrained(model,local_files_only=True,torch_dtype=torch.float16).to('mps');base.config.use_cache=False
   data=[];max_tokens=0
   for item in train_dataset:
    messages=item['messages']
    if len(messages)!=2 or messages[0]['role']!='user' or messages[1]['role']!='assistant':raise ValueError('unexpected AgentTune row')
    prompt=[{'role':'system','content':SYSTEM},messages[0]];completion=[messages[1]]
    length=len(self.tokenizer.apply_chat_template(prompt+completion,tokenize=True,add_generation_prompt=False)['input_ids']);max_tokens=max(max_tokens,length)
    if length>1024:raise ValueError('training row would be truncated')
    data.append({'prompt':prompt,'completion':completion})
   print('training rows',len(data),'max_tokens',max_tokens,flush=True)
   cfg=SFTConfig(output_dir=str(out/'trainer'),max_steps=a.steps,per_device_train_batch_size=1,gradient_accumulation_steps=1,
       learning_rate=0.0001,logging_steps=10,save_strategy='no',report_to='none',bf16=False,fp16=False,
       gradient_checkpointing=False,max_length=1024,completion_only_loss=True,seed=42)
   self.trainer=SFTTrainer(model=base,args=cfg,train_dataset=datasets.Dataset.from_list(data),processing_class=self.tokenizer,
      peft_config=LoraConfig(r=4,lora_alpha=8,lora_dropout=0.0,task_type='CAUSAL_LM',target_modules=['q_proj','v_proj']))
   return self.trainer
 if not torch.backends.mps.is_available():raise RuntimeError('local MPS device unavailable')
 meta={'model':a.model,'revision_claim':a.revision,'revision_note':'supplied revision not independently verified',
       'training_steps_sha256':hashlib.sha256(raw).hexdigest(),'system_prompt_sha256':hashlib.sha256(SYSTEM.encode()).hexdigest(),
       'examples':len(rows),'optimizer_steps':a.steps,'seed':42,'method':'AgentTune Project.train SFT on scripted trace prefixes, LoRA r=4',
       'device':'mps','python':platform.python_version(),'torch':str(torch.__version__),'transformers':transformers.__version__,
       'trl':trl.__version__,'peft':peft.__version__,'datasets':datasets.__version__,
       'scope':'scripted synthetic tool trajectories, no teacher model or on-policy RL'}
 (out/'metadata.json').write_text(json.dumps(meta,indent=2)+'\n');factory=Factory();start=time.monotonic()
 result=project.train(factory,fmt='sft',model=a.model);factory.trainer.save_model(str(out/'adapter'));factory.tokenizer.save_pretrained(str(out/'adapter'))
 summary={'elapsed_seconds':round(time.monotonic()-start,2),'global_step':int(result.global_step),'training_loss':float(result.training_loss),'log_history':factory.trainer.state.log_history}
 (out/'train-result.json').write_text(json.dumps(summary,indent=2,default=str)+'\n');print(json.dumps(summary,indent=2,default=str),flush=True)
if __name__=='__main__':main()
