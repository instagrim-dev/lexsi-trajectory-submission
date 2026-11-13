# Multi-step experiment protocol

The training examples are 168 action decisions extracted from 24 complete scripted reference episodes in the synthetic export environment. At each decision, the model sees the task and the actual preceding tool responses, not the case's private scenario configuration. AgentTune's `Project.train` uses those authored/scripted state-action examples for supervised LoRA fine-tuning. It is not reinforcement learning or a teacher-model demonstration.

The separately frozen evaluation comprises 18 cases selected before training, three from each of the six simulator scenarios. They use held-out episode IDs and task wording but the same environment and scenario mechanisms as training. A scripted reference completed all 18. The frozen data and settings are in `data/multistep-v1/manifest.json` and `evaluation-plan.json`. The base and adapter are evaluated with the same prompt, decoding and episode limits.

Replay re-executes recorded actions through the same simulator, compares actual tool responses, and recalculates outcome and safety. AuditKIT scores the reconstructed records. This checks trace consistency, but is not an independently implemented behavioral oracle or evidence about a real export service.
