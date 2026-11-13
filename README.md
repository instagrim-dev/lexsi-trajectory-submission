# Safe action when the facts change

A model-guided workflow can inspect current evidence and still propose an unsafe effect after that evidence changes. This project combines Cohere Tiny Aya, an AgentTune adapter, a deterministic observation schedule, an evidence guard and a local SQLite conditional-effect owner. The owner checks current access, destination and check state when an export is requested. If a request is refused, the workflow re-observes and chooses again. The study uses a synthetic export service; it does not perform real exports.

## Paired workflow comparison

The same fine-tuned Aya adapter was evaluated on 16 synthetic export cases under two scheduled workflows. The conditional owner adds effect-time state checks and recovery. These cases have new prompts and IDs but use familiar mechanisms.

| Measure | Scheduled guard | Guard + conditional owner |
|---|---:|---:|
| Safe completion | 10/16 | 16/16 |
| Cases with unsafe release attempts reaching simulator | 6/16 | 0/16 |
| Model calls | 23 | 22 |
| Tool actions | 119 | 154 |
| Unsupported model release proposals | 14 | 15 |

Safe completion includes stopping or requesting consent when appropriate, as well as an authorized release. The simulator blocked unsafe attempts in both arms. The model still proposed unsupported releases; the result belongs to the workflow boundary, not model reliability. In a subsequent paired comparison, both base Aya and the fine-tuned adapter completed 16/16 safely through the owner-fenced workflow, with 22 calls and 154 actions each. The base comparator was run afterward on the same frozen cases. The conditional owner covers access, destination and check state; it rejects source-change scenarios rather than fencing source revisions. It is a local SQLite owner connected to a simulator, not an installed BMO integration or a real export service.

The experiment addresses an agentic safety problem: checks can become stale before an effect executes. Effect-time authority and recovery provide the tested protection even when the model chooses badly. [Workflow study, cases and traces](owner-study/README.md).

## Learning and falsifying a competence boundary

We implemented a research prototype that infers a repair's empirical applicability from qualified successes and failures, narrows it after a counterexample, and replays retained behavioral examples before qualification. In a separate five-task Go pilot, we compared it against an Adaption Gemma baseline with the same history, checker, three-attempt ceiling and verified semantic cache, including harmless function renames. Both arms completed 5/5; generic used 6 candidate attempts, 4 model starts and 11 Go workers, while the learned arm used 8 attempts, 4 model starts and 15 Go workers. Generic had one qualification failure; the learned arm had two qualification failures and one replay rejection. The boundary narrowed after two changed-requirement failures, but no hypothesis-selected candidate completed a task. This is evidence that the prototype can refine an empirical boundary and replay a retained failure, not evidence of a reuse or cost advantage over the strong baseline. The observed 20.716 s versus 15.746 s assignment times are descriptive for one short stream, not a causal speedup.

The semantic features were supplied by the fixture; no autonomous requirement extraction or production BMO integration is established. Cases and acceptance vectors are synthetic, and both sets use the same reference implementation. [Full methods, failed attempts, accounting, code and raw records](competence-study/README.md). The Adaption pilot is separate from the Cohere Tiny Aya fine-tuning and workflow evaluation above.

## Separate fine-tuning comparison

The same 18 frozen held-out episodes were run with the base model and trained adapter. Cases have separate IDs and wording from training, but use the same six simulator mechanisms.

| Measure | Base | Adapter |
|---|---:|---:|
| Safe completions | 0/18 | 1/18 |
| Cases with an unsafe release attempt | 4/18 | 0/18 |
| Episodes reaching the eight-step limit | 4/18 | 16/18 |
| Total tool steps | 90 | 143 |

The adapter reduced unsafe attempts in this cohort while usually failing to finish. This result does not show a generally useful or reliably improved agent. Actions are simulated; unsafe release attempts do not cause real releases. The recorded run was on Apple MPS with greedy decoding. Timings are in the saved traces and are not controlled benchmarks. The separately developed BMO decision-revision workflow is not the adapter's before/after measurement.

[Protocol](results/PROTOCOL.md) · [paired comparison](results/comparison.json) · [base traces](results/base-results.jsonl) · [adapter traces](results/trained-results.jsonl) · [base AuditKIT report](results/base-audit.json) · [adapter AuditKIT report](results/trained-audit.json)

## Native decision revision witness

Separately, a native Workbench run used local d1-3B and Tiny Aya to generate candidates after operator-supplied decisions. A previously accepted seven-day proposal was refused as stale after revision to 14 days; a fresh candidate was checked and applied following a restart. This is one synthetic case, with the same checker used before and after application, and is not a result of the trained adapter. See the [witness and retained trace](results/native-revision/README.md).

## Artifacts

- Base model: [CohereLabs/tiny-aya-global](https://huggingface.co/CohereLabs/tiny-aya-global). The base model is gated; users must meet the provider's access conditions. It is licensed CC BY-NC 4.0 and subject to Cohere Labs' acceptable-use terms. Consult its model card before use.
- Adapter collection: [Lexsi trajectory models](https://huggingface.co/collections/instagrim/lexsi-trajectory-models-6af6f0d667a22df62aa95658).
- Dataset and traces collection: [Lexsi trajectory datasets](https://huggingface.co/collections/instagrim/lexsi-trajectory-datasets-6af6f0d7fbd72a5024671d84).
- The included synthetic data and trace files have no real identities or actual export actions. The training metadata copy replaces the original machine-local model path with a redaction; numerical settings are retained.

## Setup

Use Python 3.12 and a Mac with Apple Silicon and MPS for the recorded training configuration. The evaluation script also runs on CPU, which may take substantially longer. The original environment recorded PyTorch 2.15.0, Transformers 5.22.1, TRL 1.7.1, PEFT 0.19.1 and Datasets 3.6.0. Package compatibility and hardware performance can change; reproduce in an environment with these versions and the pinned Lexsi source revisions below.

```sh
python3 -m venv .venv
. .venv/bin/activate
python -m pip install torch==2.15.0 transformers==5.22.1 trl==1.7.1 peft==0.19.1 datasets==3.6.0
git clone https://github.com/Lexsi-Labs/AgentTune.git ../AgentTune
git -C ../AgentTune checkout d4db4c12d52342227c4113a70183d0f64aa2f345
git clone https://github.com/Lexsi-Labs/AuditKIT.git ../AuditKIT
git -C ../AuditKIT checkout 71316da345784ff220d5ed59337441a59ab31526
python -m pip install -e ../AgentTune -e ../AuditKIT
```

Obtain the Cohere base model using your own authorized Hugging Face access, download it to a local directory, and set `MODEL_DIR` to that directory. The recorded revision value is `af89d219b53ed9b13b8a4645f9c8028973510324`; the training/evaluation scripts check the supplied label against the frozen plan, but do not independently verify the bytes of a local checkpoint against that revision. The original model-file hashes are provided in [results/model-files.sha256](results/model-files.sha256). Set `ADAPTER_DIR` to the downloaded published adapter directory. For an offline run, all model and tokenizer files must already be present.

## Evaluate

From the project root, run with distinct output directories that do not yet exist:

```sh
export MODEL_DIR=/absolute/path/to/tiny-aya-global
export ADAPTER_DIR=/absolute/path/to/adapter
export REVISION=af89d219b53ed9b13b8a4645f9c8028973510324
PYTHONPATH=. python decision_slice/multistep_eval.py --model "$MODEL_DIR" --revision "$REVISION" --data data/multistep-v1/heldout.jsonl --plan data/multistep-v1/evaluation-plan.json --out runs/base
PYTHONPATH=. python decision_slice/multistep_eval.py --model "$MODEL_DIR" --revision "$REVISION" --data data/multistep-v1/heldout.jsonl --plan data/multistep-v1/evaluation-plan.json --adapter "$ADAPTER_DIR" --out runs/adapter
PYTHONPATH=. python decision_slice/multistep_compare.py --before runs/base --after runs/adapter --train-meta results/training-metadata-redacted.json --plan data/multistep-v1/evaluation-plan.json --out runs/comparison.json
```

Replaying the existing recorded runs does not call a model:

```sh
PYTHONPATH=. python decision_slice/multistep_audit.py --cases data/multistep-v1/heldout.jsonl --results results/base-results.jsonl --out /tmp/lexsi-base-audit.json
PYTHONPATH=. python decision_slice/multistep_audit.py --cases data/multistep-v1/heldout.jsonl --results results/trained-results.jsonl --out /tmp/lexsi-adapter-audit.json
```

The replay checks the saved tool observations against the same simulator, then AuditKIT scores reconstructed episodes. It is a consistency check, not an independent simulator or a rerun of model inference. Outputs must not already exist.

## Train

The training run used 168 authored action decisions from 24 scripted episodes, LoRA rank 4, 168 optimizer steps, and seed 42. It is supervised fine-tuning, not reinforcement learning or generated teacher demonstrations.

```sh
PYTHONPATH=. python decision_slice/multistep_train.py --model "$MODEL_DIR" --revision "$REVISION" --data data/multistep-v1/train-steps.jsonl --out runs/train --steps 168
```

The script requires MPS and writes a new adapter and metadata under `runs/train`. The `--revision` argument is recorded metadata, not a cryptographic check of local model bytes. No code license is asserted here; AgentTune, AuditKIT, and the base model retain their respective licenses.
