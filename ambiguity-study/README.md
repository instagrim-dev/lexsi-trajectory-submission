# Executable ambiguity witnesses: research package

This package contains an experimental Tiny Aya and AgentTune study of whether an agent can distinguish genuinely underspecified Go requests from fully specified requests and, when asking a question, construct two plausible Go implementations that disagree on a concrete input. It is a synthetic study, not a production BMO integration.

The two held-out task families are invoice rounding and event deduplication. Each ambiguous public prompt has two assignments with byte-identical visible requests and opposite hidden requirements; resolved controls state the missing requirement. A documented, conservative phrase-based simulated user answers recognizable questions. The witness checker compiles and executes both candidate functions under a network-denied macOS worker, checks their consistency with the two candidate interpretations, and checks that they disagree on the submitted input. Qualification and independent acceptance use different cases but share one Python reference implementation. A passing finite check is not a proof of universal equivalence.

All model arms use the same prompt, free-form questions, executable probes, checker, and budgets. The held-out tasks do not expose their hidden IDs or correct decisions in the prompt. See `ambiguity_study/benchmark.py`, `prompt.py`, `evaluate.py`, and `runs/ambiguity-eval-v2/` for the precise protocol and recorded results.

## Matched evaluation results

The 12 assigned opportunities comprise eight ambiguous assignments and four explicitly specified controls across two held-out families. The table counts every assignment. Go worker counts include qualification, acceptance, and witness executions; checker counts also include checks rejected before a worker starts. Outcome labels refer to candidate submission in the simulator, not a physical workspace mutation.

| Measure | Base Tiny Aya | AgentTune adapter | Strong generic Adaption Gemma |
|---|---:|---:|---:|
| Accepted tasks | 0/12 | 0/12 | 5/12 |
| Incorrect submitted repairs | 0 | 0 | 1 |
| Turn-budget exhausted | 11 | 12 | 6 |
| Question-budget exhausted | 1 | 0 | 0 |
| Questions / useful questions | 4 / 0 | 9 / 0 | 5 / 4 |
| Valid witnesses under strict interface | 0 | 0 | 0 |
| Model starts | 48 | 48 | 44 |
| Responses hitting output cap | 25 | 5 | 11 |
| Invalid model outputs | 5 | 1 | 0 |
| Input / output tokens | 73,825 / 14,165 | 71,205 / 11,539 | 47,379 / 12,854 |
| Checker calls / failures | 42 / 42 | 45 / 45 | 50 / 39 |
| Go workers | 34 | 27 | 28 |
| Recorded end-to-end arm wall time | 562.796 s | 504.367 s | 73.472 s |

The adapted model did not improve completion over base Tiny Aya on this sample. Both exhausted the available turns on almost every case. The hosted model is a useful stronger generic comparator, not an isolated measure of the fine-tuning effect. Runs occurred sequentially with different model hosting, and timings are descriptive. All three arms used the same interface and budgets; candidate-level feedback and tool outcomes are in the logs.

**Protocol limitation and offline diagnostics.** The prompt did not specify that the Go worker rejects imports or the exact witness JSON field spelling. After the recorded trajectories, a diagnostic normalized field-name spelling only for five supplied witness inputs; three Adaption event witnesses then satisfied the independent checker. The diagnostic used ten additional Go workers and 2.199 seconds; it did not invoke a model or reconstruct subsequent decisions. An initial safe-import recheck examined 49 candidate occurrences, including 26 unique workers that were blocked by the temporary-path sandbox (1.081 seconds); its outcome is not informative. A corrected recheck used 26 additional workers (3.160 seconds): all failed compilation under the bounded import extraction, so none matched a complete interpretation. These are diagnostic observations, not replacement trajectory scores. The 126 failed strict checks across the three arms include invalid witnesses, compilation failures and verifier failures; they are not all semantic counterexamples. The sandbox controls used three subprocesses (about 0.031 seconds).

Training took 99.101 seconds and 24,141 input tokens in one successful run. Before the corrected evaluation, an initial evaluation was interrupted after two completed calls (1,628 input and 233 output tokens) and one additional call with unknown usage. The setup ledger also records a failed dependency installation and a cancelled attempt whose elapsed time was not measured. The final arm wall times include their model initialization; checker and model times are nested in those totals and must not be added again. Sandbox controls and post-run diagnostics are additional work. Thus no exact total development duration or token total including the interrupted call is available.

Across the three final arms and the interrupted development run there were 143 model dispatches, 142 completed; one additional response has unknown usage. Those completed inference calls used 194,037 input and 38,791 output tokens; the AgentTune run additionally processed 24,141 training input tokens. The known Go work includes 89 final-arm workers, 26 initial sandbox-denied import rechecks, 26 corrected import rechecks, 10 witness rechecks and one teacher-validation worker: 152 workers before benchmark preflight tests. Three separate sandbox-control subprocesses are also recorded. Benchmark preflight Go worker counts were not comprehensively captured, so 152 is a lower bound on study Go work, not a complete development total.

The `runs/ambiguity-eval-v1/` and `runs/ambiguity-eval-v2/` records preserve per-call inputs and outputs, per-task outcomes and checker results, as well as diagnostic observations. Machine-local temporary path strings were replaced with `<temporary-path>` in this public copy; the records' substantive values are unchanged.

## Training

Tiny Aya Global was adapted using AgentTune `Project.train` with rank-4 LoRA for 32 optimizer steps over 24 hand-authored examples. The teacher data uses surcharge-rounding and even-median Go tasks; evaluation uses separate invoice and event tasks. Exact prompts, programs and witness inputs do not overlap, while general rounding and selection concepts do. No teacher model calls were used. Training wall time was 99.101 seconds; the recorded training loop took 83.949 seconds, with 24,141 input tokens seen. See `training/` for configuration, metrics, two unsuccessful/cancelled dependency setup attempts, and the explicitly unmeasured setup time. The base model is gated, not bundled, and requires compliance with [Cohere's terms](https://huggingface.co/CohereLabs/tiny-aya-global); the adapter has separate research-distribution terms.

## Local setup and checks

Use Python 3.12, macOS and Go. The recorded version set was PyTorch 2.15.0, Transformers 5.22.1, TRL 1.7.1, Datasets 5.2.0, and PEFT 0.19.1. The run used AgentTune commit `d4db4c12d52342227c4113a70183d0f64aa2f345` from https://github.com/Lexsi-Labs/AgentTune. An Apple Silicon machine with MPS was used for recorded training and local inference. Dependencies and model access must be installed separately.

```sh
python -m unittest discover -s tests -p 'test_ambiguity_benchmark.py'
python -m unittest ambiguity_study.test_teacher
```

To train in a fresh output directory, download the authorized Tiny Aya Global checkpoint, set `MODEL_DIR` to its path, and run:

```sh
python -m ambiguity_study.train --model "$MODEL_DIR" --data data/teacher.jsonl --out runs/train --steps 32
```

To rerun each evaluation arm, use `python -m ambiguity_study.evaluate --help` and provide distinct outputs. The hosted Adaption control reads its credential from the file specified by `BMO_ENV_PATH`; do not publish credentials. This release changes the original hard-coded credential-file location to that environment variable for portability; the evaluation logic is otherwise retained. Do not infer an inference rerun from the retained training metadata.
