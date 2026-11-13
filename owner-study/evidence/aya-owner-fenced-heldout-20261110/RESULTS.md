# Aya completion and conditional release: paired evaluation

## Finding

The saved 18-case fine-tuned run failed primarily at terminal action selection. All 18 episodes began with the three reference inspections. On the seventh decision, 17 selected another inspection and one stopped; the 24 scripted training episodes all supplied a terminal action after six observations (8 releases and 16 stops). Across 143 actions, 78 observations repeated an identical earlier action and response. These are descriptive trace findings: repeated observations are not necessarily redundant in a changing environment, and the traces do not prove why the model learned this behavior. No calls were malformed. [Counts](rca.json) · [Original results](https://huggingface.co/datasets/instagrim/lexsi-trajectory-data)

A previously tested two-pass schedule reduced the loop, but its guard could act on observations that became stale immediately after a read. This iteration connects the existing scheduled, guarded workflow to the existing SQLite conditional-effect owner. The owner can refuse a release when its state no longer matches the coherent observed snapshot; the workflow then repeats the observation schedule and asks Aya for a new terminal action. A local coherence check can also refuse before a request reaches the owner.

## Fresh paired results

The same trained Tiny Aya adapter was evaluated with greedy decoding on 16 newly authored prompts and case IDs. The cases reuse the synthetic export domain, tool schema and previously studied change mechanisms. All arms had a 15-action maximum. The original model controlled every action; the other two arms used the same two-pass scheduler and observed-evidence guard. The new owner-fenced arm also retried after a refused release. The plan and cases were frozen before inference.

| Workflow | Safe completion | Cases with unsafe release attempts reaching simulator | Unsupported model release proposals | Model calls | Tool actions |
| --- | ---: | ---: | ---: | ---: | ---: |
| Original fine-tuned Aya | 6/16 | 1/16 | 1 | 176 | 176 |
| Scheduled + existing guard | 10/16 | 6/16 | 14 | 23 | 119 |
| Scheduled + guard + conditional owner | 16/16 | 0/16 | 15 | 22 | 154 |

The owner-fenced arm did **not** make the model reliably choose safe releases: 15 of its 17 release proposals were unsupported by the simulator's current state when proposed. Of those, nine contradicted the observations visible to the model and six were supported by its last observations but became stale afterward. [Visible-evidence scoring](visible-evidence-scoring.json). The observed-evidence guard changed nine release proposals to stop and changed two consent requests to stop. Of eight release requests delivered to the fenced workflow, four were rejected locally as incoherent, two were rejected by the owner as changed, and two produced owner ledger effects. All six refusals were followed by re-observation and a safe stop or consent request. The independent SQLite readback contains exactly the two valid effects; no unsafe effect was observed in replay. The simulator blocked every unsafe release attempt in the comparison arms.

All six cases in which a state change was triggered after its final relevant read failed safe-completion scoring in the scheduled-guard arm (seven unsafe attempts total). All six completed safely in the owner-fenced arm after refusal and re-observation. In the original arm, changes are triggered by particular tool calls, so model action choices change whether and when those events occur; its final valid-case count was four versus two for both scheduled arms. The scheduled-vs-owner comparison is therefore the more direct comparison of this intervention.

An authored deterministic controller using the same visible fields completed 16/16 with zero unsafe attempts and two effects. This is a fixture/control result, not an Aya result; it shows the scheduler and owner can perform the task without relying on model judgment. [Control](reference-control.json)

## Scope and verification

This is a synthetic in-process agent workflow connected to a real local SQLite conditional-effect owner, not an installed BMO integration, a vendor service or an actual export. The owner covers access, destination and check state; the adapter expressly rejects source-change scenarios because this owner does not fence source revisions. The effect owner must actually control the effect and participate in all relevant state changes for this approach to protect a real release. These 16 cases use familiar mechanisms; they do not establish performance on new domains or an independent reliability estimate.

The cases contain private configuration used only by the simulator and evaluation oracle. Aya sees the task and tool responses, not the case configuration or owner's private state. Unsupported proposal counts use the simulator's current state only for scoring. Safe completion includes stopping or requesting consent when appropriate, as well as successful authorized release; the original arm's changing exposure differs as noted above.

Focused tests passed for valid releases, late access/destination/check changes, recovery, missing observations, and rejecting unsupported source-change cases. Every saved action trace was replayed with the same simulator and owner implementation; the resulting observations, terminal outcomes, and ledger entries matched. This is a consistency check, not an independent implementation of the simulator. The training model config and two model weight files matched the previously recorded hashes; the upstream model revision itself was not independently established.

Artifacts: [frozen plan](plan.json), [cases](heldout.jsonl), [original trace](original.jsonl), [scheduled trace](scheduled_guard.jsonl), [owner-fenced trace](owner_fenced.jsonl), [runtime](runtime.json), [replay audit](audit.json), [owner ledger](owner.sqlite), and [test output](tests.log). The [workflow](../../decision_slice/fenced_workflow.py), [runner](../../decision_slice/multistep_fenced_eval.py), and [focused tests](../../tests/test_fenced_workflow.py) are included in the project.

To replay the recorded actions and read back the ledger from the project root:

```sh
PYTHONPATH=. .venv/bin/python evidence/aya-owner-fenced-heldout-20261110/audit.py
PYTHONPATH=. .venv/bin/python evidence/aya-owner-fenced-heldout-20261110/reference_control.py
```

To rerun live inference, copy only `heldout.jsonl` and `plan.json` to a new output directory, then run `.venv/bin/python -m decision_slice.multistep_fenced_eval --out NEW_DIRECTORY --model LOCAL_TINY_AYA_DIRECTORY --adapter evidence/agenttune-multistep-20261103/adapter`. The runner checks the frozen source and case hashes before inference and refuses to overwrite trace files.
