# Learning a competence boundary: matched Go pilot

This is an executable research prototype, not an integration in the production BMO application. It learns an empirical applicability predicate for a Go implementation from verified successes and counterexamples and replays retained behavioral examples before qualification. It is a small synthetic pilot of business calculation, with no claims about deployed invoices or financial correctness.

## Matched comparison

Each arm received the same five sequential task opportunities and the same Adaption `gemma-4-26b-a4b-it` model, three candidate attempts per task, its own full prior history, complete failing inputs and expected outputs on retry, and the same Go checker. Both arms had the same verified semantic-spec cache and harmless function-name rebinding. The learned arm additionally formed and refined applicability hypotheses and replayed retained examples. Arms ran in alternating order on one machine. Qualification used five input vectors; acceptance used six separate vectors from the same reference implementation. There was no independent implementation of the oracle and no repeated matched trials. Code, source outputs, all provider attempts, qualified candidates and checker traces are under `runs/competence-matched-v4/`.

| Measure | Generic | Learned |
|---|---:|---:|
| Accepted tasks | 5/5 | 5/5 |
| Candidate attempts | 6 | 8 |
| Failed candidate attempts | 1 qualification | 2 qualification, 1 replay |
| Provider starts | 4 | 4 |
| Input / output tokens | 5,801 / 2,746 | 11,002 / 1,554 |
| Go workers: qualification / replay / acceptance | 6 / 0 / 5 | 7 / 3 / 5 |
| Summed assignment time | 20.716 s | 15.746 s |

The generic arm's rounding-revision task needed two model candidates; its first failed qualification on cases 1 and 4. The learned arm first tried its previously accepted program against changed tax ordering: qualification rejected it on cases 0, 2, 3 and 4, and a model-generated alternative passed. On the subsequent rounding change, the previously learned program again failed qualification on cases 1 and 4; its revised boundary included both `tax_before=false` and `per_line=true`. A model candidate repeating those errors was then rejected by counterexample replay, and a second model candidate passed. Every other assignment passed on its first attempt. Both arms reused their same-spec cache on the renamed and return cases; both otherwise completed via a model-generated candidate. No hypothesis-selected candidate completed a task, so this pilot does **not** demonstrate a reusable-learning benefit over the cache-equipped baseline. Replay prevented one known-failing candidate from reaching qualification, while the learned arm did more total Go worker calls and model input work. The observed single-run time difference is descriptive and does not isolate the cause or establish a performance improvement.

Measured total study wall time was 36.467 s, including logging and boundary persistence, excluding only the final wall-record write and terminal print. Summed assignment times are 36.462 s; the remaining roughly 0.005 s is shared setup/reporting work. The learned arm recorded 42 boundary operations (0.000548 s) and 0.002536 s for persistence. These times are nested within assignment times; model and checker seconds must not be added to them again. Provider times were 15.921 s generic and 10.288 s learned; Go worker times 4.787 s and 5.420 s, respectively. Cache lookup times were approximately 0.000024 s and 0.000023 s. Unattributed internal work remains in task and wall elapsed rather than being estimated away.

## Development and all-work accounting

The following work preceded the final comparison; it was not charged to either final arm. Earlier data is not pooled into the matched outcome.

| Activity | Provider starts / completed | Known input / output tokens | Go workers / failed |
|---|---:|---:|---:|
| Simple qwen provider smoke | 1 / 1 | 57 / 25 | 0 / 0 |
| Two deterministic Go controls | 0 / 0 | 0 / 0 | 2 / 1 intentional negative |
| Real-task Gemma smoke | 1 / 1 | 169 / 405 | 1 / 0 |
| Qwen v1, stopped after empty-output failure | 3 / 2 | 479 / 8,192 | 0 / 0 |
| Gemma v2 development comparison | 13 / 13 | 21,675 / 4,670 | 25 / 10 |
| Gemma v3 development comparison | 11 / 11 | 23,574 / 3,676 | 24 / 7 |
| Retained-expectation controls | 0 / 0 | 0 / 0 | 2 / 1 intentional negative |
| Final matched v4 | 8 / 8 | 16,803 / 4,300 | 26 / 4 |
| Total | 37 / 36 | at least 62,757 / 21,268 | 80 / 23 |

One v1 provider request was interrupted after dispatch; its usage and final provider outcome are unknown, so the token totals are lower bounds. The two completed v1 requests exhausted their output budgets as reasoning and returned no usable text. v2 exposed insufficient retry feedback; v3 supplied full failing inputs but lacked the final comparator's shared semantic cache and replayed case inputs without consuming their stored expected values. Consequently neither is treated as the final comparison. Development setup wall time outside recorded per-call/check timings was not measured; do not infer a complete end-to-end development duration.

## Reproduce

Run the mechanism checks with `python3 -m unittest discover -s tests -p 'test_competence_boundary.py'`. To repeat the model comparison, use macOS, Go and an Adaption credential in an environment file. Set `BMO_ENV_PATH` to the path of that file, which must contain `ADAPTION_API_KEY`, then run `python3 competence_study/run.py runs/new-comparison`. The output directory must not already exist. The script uses macOS `sandbox-exec`, denies network in candidate Go workers, and uses `~/.cache/bmo` for Go caches; the provider call itself requires network access. This release copy changes only the original hard-coded credential-file path to `BMO_ENV_PATH` and redacts local paths in records. `ORIGINAL_RUN_SHA256` records the run script's original local hash. Credentials are not present in the release.
