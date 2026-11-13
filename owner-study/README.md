# Conditional release for decision-guided agents

This package contains the synthetic export-review study behind the Lexsi Agentic Fine-tuning entry. Tiny Aya Global proposes actions; a scheduled observation and evidence guard check terminal choices. A local SQLite owner conditionally accepts a release only while the relevant observed state remains current. Refused releases trigger re-observation. The effect owner is local research code, not an installed BMO integration or a real export service.

In 16 synthetic cases, the reported safe-completion results were 6/16 for original fine-tuned Aya, 10/16 for the scheduled guard, and 16/16 for the scheduled guard plus conditional owner and re-observation. Cases with unsafe release attempts reaching the simulator were 1/16, 6/16, and 0/16, respectively. Model calls were 176, 23, and 22; tool actions were 176, 119, and 154. The simulator blocked unsafe attempts in the comparison arms. Original-agent action choices could change whether and when triggered state changes occurred, so the scheduled-versus-owner comparison is more direct than a simple causal attribution to the full 6-to-16 difference.

In a later comparator on the same 16 cases, both base Aya and the fine-tuned adapter completed 16/16 safely under the owner-fenced workflow, with zero unsafe attempts reaching the simulator and two authorized effects. The comparator was planned afterward and is not a new independent holdout. Both models continued to propose unsupported releases; the workflow handled them. The result is a workflow result, not evidence that fine-tuning improved completion.

Safe completion includes safe stops and requests for consent as well as authorized releases. These cases use familiar synthetic mechanisms. The owner covers access, destination, and check state and rejects source-change scenarios; it cannot fence source revisions. The owner must actually control a real effect and participate in its relevant state changes for the approach to protect that effect. Recorded replay uses the same simulator and owner, not an independent implementation. See [workflow results](evidence/aya-owner-fenced-heldout-20261110/RESULTS.md) and [base comparison](evidence/aya-owner-base-comparator-20261110/RESULTS.md) for detailed methods and limitations. Machine-local paths in the runtime records have been redacted.

## Contents

`decision_slice/` includes the workflow, SQLite owner, simulator mechanisms, schedules, guard, and both inference runners; the project-root Python files are their dependencies. `evidence/` contains frozen plans, authored cases, saved action traces, summaries, independent ledger readback, and replay scripts. `tests/` contains focused workflow tests. The underlying Tiny Aya base model has separate access conditions and is not distributed here. The trained adapter is [available on Hugging Face](https://huggingface.co/instagrim/lexsi-trajectory-tiny-aya).

## Replay and run

Use Python 3.12 from the package root. The replay uses only the Python standard library and makes no model calls. It checks saved traces against the same simulator and writes updated `audit.json` files in the study directories:

```sh
PYTHONPATH=. python evidence/aya-owner-fenced-heldout-20261110/audit.py
PYTHONPATH=. python evidence/aya-owner-base-comparator-20261110/audit.py
PYTHONPATH=. python -m unittest discover -s tests -p 'test_fenced_workflow.py'
```

For live inference, obtain authorized local Tiny Aya Global weights and the adapter, and install compatible `torch`, `transformers`, and `peft`. The recorded runs used Apple MPS and greedy decoding. From the package root, create a fresh output directory and copy only that study's `heldout.jsonl` and `plan.json` there; runners check the plan's case and source hashes and refuse to overwrite recorded traces:

```sh
mkdir -p runs/adapter runs/base
cp evidence/aya-owner-fenced-heldout-20261110/{heldout.jsonl,plan.json} runs/adapter/
cp evidence/aya-owner-base-comparator-20261110/{heldout.jsonl,plan.json} runs/base/
PYTHONPATH=. python -m decision_slice.multistep_fenced_eval --out runs/adapter --model "$MODEL_DIR" --adapter "$ADAPTER_DIR"
PYTHONPATH=. python -m decision_slice.multistep_base_comparator --out runs/base --model "$MODEL_DIR"
```

`MODEL_DIR` and `ADAPTER_DIR` must be absolute paths to the locally downloaded model and adapter directories. The adapter run executes all three workflow arms; the base run executes the owner-fenced comparator. The prior adapter was trained with AgentTune on synthetic scripted trajectories; the primary training study, its configuration, and the original 18-case results are described in the model and dataset cards.
