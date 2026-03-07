# DSPy Prompt Evolver — powered by `dspy.GEPA`

Evolves your creative/ideation prompts using **GEPA (Genetic-Pareto)**, the newest DSPy optimizer.

---

## Why GEPA over COPRO/MIPROv2?

| | COPRO/MIPROv2 | **GEPA** |
|---|---|---|
| Learning signal | Scalar score | **Natural language reflection** on traces |
| Sample efficiency | High rollout count | Up to **35x fewer rollouts** |
| Feedback quality | "score: 0.6" | "The prompt still hedges with 'assume minimal' — remove that constraint framing entirely" |
| Improvement vs prior SOTA | baseline | **+10–20% over MIPROv2** |

GEPA reads *why* a prompt scored badly and proposes targeted text fixes — not random mutations.

---

## Install

```bash
pip install -e .
```

---

## Setup

1. **Create a `.env` file** in the project root:
```
MISTRAL_API_KEY=your-mistral-api-key-here
```

2. **Get your Mistral API key** from [Mistral AI Console](https://console.mistral.ai/api-keys/)

3. **Replace** `your-mistral-api-key-here` with your actual API key

---

## Run

```bash
# Default (uses Mistral models from .env)
python evolve_prompts.py

# Use different Mistral models
python evolve_prompts.py \
  --task-model mistral/mistral-small-latest \
  --reflection-model mistral/mistral-large-latest

# Fast/cheap test (~$0.20)
python evolve_prompts.py --max-metric-calls 30

# Full quality run (~$0.50-1)
python evolve_prompts.py --max-metric-calls 150
```

---

## How it works

```
Your 7 prompts  (trainset — no labels needed)
       │
       ▼
 ┌─────────────────────────────────────────┐
 │  dspy.GEPA optimizer loop               │
 │                                         │
 │  1. Runs EvolvePrompt on a prompt       │
 │  2. Scores via gepa_metric()            │
 │     → returns ScoreWithFeedback(        │
 │         score=0.61,                     │
 │         feedback="Still hedging with    │
 │           'assume minimal' — remove"    │
 │       )                                 │
 │  3. Reflection LM reads that feedback   │
 │     and proposes a better signature     │
 │  4. Pareto frontier tracks best         │
 │     candidates across all prompts       │
 │  5. Repeat for max_metric_calls         │
 └─────────────────────────────────────────┘
       │
       ▼
 Optimized EvolvePrompt signature
 applied to all 7 prompts
       │
       ▼
 evolved_prompts.md + evolved_prompts.json
```

---

## What the metric scores

| Axis | Penalizes | Rewards |
|---|---|---|
| **Novelty** | Incremental, safe framing | 10x, cross-domain, unexpected combinations |
| **Boldness** | "constraints:", "feasible", "assume minimal", "avoid complex" | Sovereign, unhedged, electric voice |
| **Generativity** | Vague instructions | Demands specificity, vividness, format discipline |

The metric also pattern-matches surviving hedge phrases directly (fast heuristic penalty on top of LLM score).

---

## Mistral Models Available

- **mistral-small-latest**: Fast and cost-effective, good for task execution
- **mistral-medium-latest**: Balanced performance and cost
- **mistral-large-latest**: Most capable, best for reflection and complex reasoning

For best results, use `mistral-small-latest` as task model and `mistral-large-latest` as reflection model (default).

---

## Estimated cost

| `--max-metric-calls` | Approx cost (Mistral) | Quality |
|---|---|---|
| 30 | ~$0.20 | Good baseline |
| 80 (default) | ~$0.50–1 | Strong |
| 150 | ~$1–2 | Best results |