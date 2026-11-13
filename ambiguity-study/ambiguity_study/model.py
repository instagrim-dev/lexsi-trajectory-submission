"""Instrumented local Tiny Aya inference; logs every attempted dispatch."""
from __future__ import annotations
import json, os, time
from pathlib import Path
from typing import Any


def write_event(path: Path, event: dict[str, Any]) -> None:
    with path.open('a', encoding='utf-8') as f:
        f.write(json.dumps(event, ensure_ascii=False, sort_keys=True) + '\n')
        f.flush()
        os.fsync(f.fileno())


def parse_response(raw: str) -> dict[str, Any] | None:
    text = raw.strip()
    if text.startswith('```') and text.endswith('```'):
        text = text.split('\n', 1)[1].rsplit('```', 1)[0].strip()
    try:
        value = json.loads(text)
    except (ValueError, IndexError):
        # Accept a model's ordinary code or a standalone question as equivalent
        # actions. Never synthesize a witness or a missing rule for the model.
        start = text.find('func Compute(')
        if start >= 0:
            return {'action': 'solve', 'code': text[start:], 'parsed_from': 'plain_go'}
        if len(text) <= 500 and text.endswith('?') and '\n' not in text:
            return {'action': 'ask', 'question': text, 'parsed_from': 'plain_question'}
        return None
    if not isinstance(value, dict) or value.get('action') not in ('ask', 'probe', 'solve'):
        return None
    return value


class TinyAya:
    def __init__(self, model: str, adapter: str | None, journal: Path, max_new_tokens: int = 384):
        self.journal = journal
        self.max_new_tokens = max_new_tokens
        start = time.monotonic()
        write_event(journal, {'event': 'model_initialization_started', 'adapter': bool(adapter)})
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer
        self.torch = torch
        self.tokenizer = AutoTokenizer.from_pretrained(model, local_files_only=True)
        self.device = 'mps' if torch.backends.mps.is_available() else 'cpu'
        self.model = AutoModelForCausalLM.from_pretrained(model, local_files_only=True, torch_dtype='auto').to(self.device)
        if adapter:
            from peft import PeftModel
            self.model = PeftModel.from_pretrained(self.model, adapter, is_trainable=False)
        self.model.eval()
        self.initialization_seconds = time.monotonic() - start
        write_event(journal, {'event': 'model_initialized', 'adapter': bool(adapter), 'device': self.device,
                              'elapsed_s': self.initialization_seconds})

    def infer(self, messages: list[dict[str, str]], *, arm: str, task: str, turn: int) -> dict[str, Any]:
        start = time.monotonic()
        call_id = f'{arm}:{task}:{turn}:{time.monotonic_ns()}'
        write_event(self.journal, {'event': 'started', 'call_id': call_id, 'arm': arm, 'task': task,
                                   'turn': turn, 'messages': messages})
        try:
            encoded = self.tokenizer.apply_chat_template(messages, tokenize=True, add_generation_prompt=True,
                            return_dict=True, return_tensors='pt').to(self.device)
            input_tokens = int(encoded['input_ids'].shape[-1])
            with self.torch.inference_mode():
                generated = self.model.generate(**encoded, do_sample=False, max_new_tokens=self.max_new_tokens,
                                                 pad_token_id=self.tokenizer.eos_token_id)
            if self.device == 'mps':
                self.torch.mps.synchronize()
            new_tokens = generated[0][input_tokens:]
            raw = self.tokenizer.decode(new_tokens, skip_special_tokens=True).strip()
            parsed = parse_response(raw)
            result = {'event': 'finished', 'call_id': call_id, 'input_tokens': input_tokens,
                      'output_tokens': int(len(new_tokens)), 'raw': raw, 'parsed': parsed,
                      'error': None if parsed is not None else 'invalid_json_or_action',
                      'truncated': int(len(new_tokens)) >= self.max_new_tokens,
                      'elapsed_s': time.monotonic() - start}
        except Exception as exc:
            result = {'event': 'finished', 'call_id': call_id, 'error': type(exc).__name__,
                      'elapsed_s': time.monotonic() - start, 'input_tokens': None, 'output_tokens': None}
        write_event(self.journal, result)
        return result


class AdaptionPolicy:
    """Hosted generic control; the key stays in this process, not checker envs."""
    endpoint = 'https://api.prod.adaptionlabs.ai/api/v1/responses'

    def __init__(self, model: str, journal: Path, max_new_tokens: int = 384):
        start = time.monotonic()
        self.model_name = model
        self.journal = journal
        self.max_new_tokens = max_new_tokens
        envpath = Path(os.environ['BMO_ENV_PATH'])
        self.key = None
        for line in envpath.read_text().splitlines():
            if line.startswith('ADAPTION_API_KEY='):
                self.key = line.split('=',1)[1].strip().strip('"').strip("'")
        if not self.key:
            raise RuntimeError('Adaption credential unavailable')
        self.initialization_seconds = time.monotonic() - start
        write_event(journal, {'event':'provider_initialized', 'model':model, 'elapsed_s':self.initialization_seconds})

    def infer(self, messages: list[dict[str, str]], *, arm: str, task: str, turn: int) -> dict[str, Any]:
        import urllib.request, urllib.error
        start=time.monotonic(); call_id=f'{arm}:{task}:{turn}:{time.monotonic_ns()}'
        write_event(self.journal, {'event':'started','call_id':call_id,'arm':arm,'task':task,'turn':turn,'messages':messages})
        prompt='\n\n'.join(m['role'].upper()+':\n'+m['content'] for m in messages)
        payload=json.dumps({'model':self.model_name,'input':prompt,'max_output_tokens':self.max_new_tokens}).encode()
        req=urllib.request.Request(self.endpoint,data=payload,method='POST',headers={'Content-Type':'application/json','Authorization':'Bearer '+self.key})
        try:
            with urllib.request.urlopen(req,timeout=120) as resp:
                result=json.load(resp); status=resp.status
            raw=''.join(part.get('text','') for item in result.get('output',[]) if item.get('type')=='message' for part in item.get('content',[]) if part.get('type')=='output_text').strip()
            parsed=parse_response(raw); usage=result.get('usage') or {}
            result={'event':'finished','call_id':call_id,'http_status':status,'model':result.get('model'),
                    'input_tokens':usage.get('input_tokens'),'output_tokens':usage.get('output_tokens'),'raw':raw,'parsed':parsed,
                    'error':None if parsed is not None and result.get('model')==self.model_name else 'invalid_response_or_model',
                    'truncated':usage.get('output_tokens',0)>=self.max_new_tokens,'elapsed_s':time.monotonic()-start}
        except urllib.error.HTTPError as exc:
            result={'event':'finished','call_id':call_id,'http_status':exc.code,'error':'provider_http_error',
                    'input_tokens':None,'output_tokens':None,'elapsed_s':time.monotonic()-start}
        except Exception as exc:
            result={'event':'finished','call_id':call_id,'error':type(exc).__name__,
                    'input_tokens':None,'output_tokens':None,'elapsed_s':time.monotonic()-start}
        write_event(self.journal,result)
        return result
