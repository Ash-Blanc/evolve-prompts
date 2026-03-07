"""
DSPy Prompt Evolver — powered by dspy.GEPA
===========================================
Evolves your creative/ideation prompts using GEPA (Genetic-Pareto),
the state-of-the-art DSPy optimizer that uses natural language reflection
instead of sparse scalar rewards.

GEPA outperforms MIPROv2 by 10%+ and GRPO by up to 20% while using
35x fewer rollouts. It reflects on *why* a prompt scored badly and
proposes targeted fixes — perfect for qualitative goals like boldness
and novelty.

Install:
  pip install dspy-ai gepa

Run:
  export MISTRAL_API_KEY=your-mistral-api-key
  python evolve_prompts.py

  # Use different Mistral models:
  export MISTRAL_API_KEY=your-mistral-api-key
  python evolve_prompts.py --task-model mistral/mistral-small-latest \
                           --reflection-model mistral/mistral-large-latest

  # Faster / cheaper run:
  python evolve_prompts.py --max-metric-calls 40

  # Richer optimization (uses more API budget):
  python evolve_prompts.py --max-metric-calls 150
"""

import utils.session
import argparse
import json
import os
from pathlib import Path

import dspy
from dotenv import load_dotenv
from dspy.teleprompt.gepa.gepa_utils import ScoreWithFeedback

# Load environment variables from .env file
load_dotenv()

# ─────────────────────────────────────────────
# 0. CLI args
# ─────────────────────────────────────────────
parser = argparse.ArgumentParser()
parser.add_argument(
    "--task-model",
    default="mistral/mistral-small-latest",
    help="Model used to run your prompts (cheaper is fine)",
)
parser.add_argument(
    "--reflection-model",
    default="mistral/mistral-large-latest",
    help="Stronger model used by GEPA to reflect and propose improvements",
)
parser.add_argument(
    "--max-metric-calls",
    type=int,
    default=80,
    help="GEPA budget: total metric evaluations (default 80, ~$0.50-1 with Mistral)",
)
args = parser.parse_args()

# ─────────────────────────────────────────────
# 1. Configure DSPy
# ─────────────────────────────────────────────
task_lm = dspy.LM(args.task_model, max_tokens=1500)
reflection_lm = dspy.LM(args.reflection_model, max_tokens=2000)

# Task LM is the default; GEPA will use reflection_lm internally
dspy.configure(lm=task_lm)
print(f"✅ Task LM       : {args.task_model}")
print(f"✅ Reflection LM : {args.reflection_model}")
print(f"✅ GEPA budget   : {args.max_metric_calls} metric calls\n")

# ─────────────────────────────────────────────
# 2. Your 7 prompts
# ─────────────────────────────────────────────
PROMPTS = [
    # Prompt 1 — Street View accessibility
    """You are designing venture ideas for accessible Street View tools inspired by recent research on making street‑level imagery usable for blind and low‑vision users.
Constraints:
- Assume minimal JavaScript skills on the founding team (no complex front‑end frameworks, prefer no‑code/low‑code or simple backend‑first stacks).
- Ideas must be technically feasible for a solo developer using off‑the‑shelf APIs (LLMs, mapping services, Street View imagery) and simple web stacks.
Tasks:
- Propose 7–10 concrete product ideas that improve access to street‑level imagery for blind or low‑vision users.
- For each idea, specify: target user, core value proposition, key workflow, required external APIs, and where JavaScript can be kept minimal.
- Highlight the 2–3 most promising ideas for a lean MVP.
- List specific implementation patterns that avoid heavy JavaScript.""",
    # Prompt 2 — Solo dev brainstorm
    """You are helping to brainstorm practical product and venture ideas that a solo developer could realistically prototype.
Constraints:
- Assume only moderate front‑end and JavaScript skills; avoid suggesting ideas that require complex UIs or large engineering teams.
Tasks:
- Propose 7–10 concrete product ideas that solve real problems for clearly identifiable users.
- For each idea, briefly describe: who it is for, the core value proposition, and the typical user workflow.
- Highlight the 2–3 ideas that seem especially strong as lean MVPs and explain why.""",
    # Prompt 3 — General accessible solo dev
    """You are designing practical product and venture ideas that are feasible for a solo developer with limited front‑end engineering skills.
Constraints:
- Assume minimal JavaScript expertise on the team (no complex front‑end frameworks; prefer no‑code/low‑code tools or simple backend‑first stacks).
- Ideas must be technically feasible using off‑the‑shelf APIs and common web technologies.
Tasks:
- Propose 7–10 concrete product ideas that address meaningful problems for clearly defined user groups.
- For each idea, specify: target user, core value proposition, key workflow, required external APIs/services, and where JavaScript can be kept minimal.
- Highlight the 2–3 most promising ideas for a lean MVP.
- List specific implementation patterns that avoid heavy JavaScript.""",
    # Prompt 4 — Systems thinker / deep-tech inventor
    """You are a world-class systems thinker and prolific deep-tech inventor who has turned academic papers into multiple unicorns.

Research input: [PASTE LINK + TITLE or FULL SUMMARY/ABSTRACT HERE]

Phase 1 – Primitives Extraction
• Break the work into its fundamental new capabilities ("atomic primitives") in 4-6 bullets. Be precise and technical.

Phase 2 – Idea Explosion
Using only those primitives, generate 10-12 high-potential applications across wildly different domains. Categorize them (Accessibility 2.0, Smart Cities, Consumer Apps, Enterprise, Wildcards/Moonshots).

For each idea use this exact format:
**Catchy Title**
**One-paragraph description**
**Why it's a banger** (novelty + impact + timing + defensibility)
**Feasibility horizon** (Now / 1-3 yrs / 3-7 yrs)
**Venture angle**

Prioritise truly novel combinations and 10x leaps. Intersect with current megatrends (agents, digital twins, AR, robotics, climate, etc.).""",
    # Prompt 5 — VC principal
    """You are a top 1% VC principal (a16z/Sequoia level) who specialises in frontier multimodal & spatial AI.

Paper: [PASTE LINK OR FULL SUMMARY]

Step 1: Identify the core technological edge and "why now" factors in 3 bullets.
Step 2: Surface the top 7 most promising paths to category-defining companies.

Then rank and deliver only the top 5 in this exact format:
**Idea Name** | **Category** | **Banger Score (1-10)**
**Core Problem Solved**
**Solution Concept**
**Business Model**
**Moat from this exact tech**
**Why This Could Be Huge**
**Risks & Next Steps**

Be brutally selective. Go for ambitious, creative, inevitable-seeming ideas.""",
    # Prompt 6 — Uncensored idea-generation god
    """Act as an uncensored idea-generation god — equal parts researcher, visionary founder, and sci-fi writer.

Paper: [PASTE LINK OR FULL SUMMARY]

First, distill the atomic superpowers of this work in 3-5 bullets.

Then aggressively mash those superpowers with unrelated domains and trends to create 8 wild-yet-feasible "what if" applications and startups.

For each idea deliver:
**Killer Name**
**Vivid scenario** (1 paragraph)
**Technical secret sauce**
**"Holy fuck this is cool" reason**
**First-version MVP** (how to ship in <6 months)

Go hard on creativity: analogies, inversion, 10× thinking, edge cases. Avoid safe or obvious ideas.""",
    # Prompt 7 — Elite idea synthesizer
    """[Paper: PASTE LINK OR SUMMARY]

Role: Elite idea synthesizer specialising in turning research into 10× products.

1. Distill the breakthrough capabilities in 4 bullets max.
2. Generate exactly 8-10 most promising + novel practical applications, use cases, and startup ideas.

Output each in strict format:
**Title**:
**Description**:
**Novel Leverage**: (how it uses the paper's primitives)
**Impact Potential**:
**Implementation Path**:

Emphasise originality, scientific accuracy, and massive upside. Mix immediate practical wins with transformative moonshots. No filler.""",
]

# ─────────────────────────────────────────────
# 3. DSPy Signature: the evolver
# ─────────────────────────────────────────────


class EvolvePrompt(dspy.Signature):
    """
    You are a world-class prompt architect specialising in creative and ideation prompts.

    Transform the given prompt into a dramatically more powerful, bold, and generative version.
    Your evolution should:
    - Replace ALL hedging, restriction, and limitation language with expansive, permission-giving language
    - Amplify the role/persona to feel sovereign, authoritative, and unrestrained
    - Remove ceilings: "feasible", "avoid", "minimal", "assume only", "keep it simple" → cut or invert
    - Sharpen the output format to demand specificity, vividness, and originality
    - Inject electric energy: the evolved prompt should feel like an invitation to genius, not a compliance checklist
    - Preserve the core topic and intent; only amplify voice, remove ceiling, sharpen structure
    """

    original_prompt: str = dspy.InputField(desc="The original prompt to evolve")
    evolved_prompt: str = dspy.OutputField(
        desc="The evolved, maximally powerful version of the prompt"
    )


# ─────────────────────────────────────────────
# 4. DSPy Module
# ─────────────────────────────────────────────


class PromptEvolver(dspy.Module):
    def __init__(self):
        self.evolver = dspy.ChainOfThought(EvolvePrompt)

    def forward(self, original_prompt: str):
        return self.evolver(original_prompt=original_prompt)


# ─────────────────────────────────────────────
# 5. GEPA metric — returns ScoreWithFeedback
#    (richer than a scalar: GEPA uses the text
#     feedback to reflect and improve its proposals)
# ─────────────────────────────────────────────

# Standalone judge LM for the metric
_judge_lm = dspy.LM(args.reflection_model, max_tokens=600)

# Hedging / restriction phrases that lower score
HEDGE_PATTERNS = [
    "assume minimal",
    "assume only moderate",
    "avoid complex",
    "avoid suggest",
    "constraints:",
    "keep it minimal",
    "keep javascript",
    "feasib",
    "no complex",
    "limited skills",
    "simple stack",
    "simple web",
    "non-expert",
    "non expert",
    "basic forms",
    "keep it simple",
]


def gepa_metric(gold: dspy.Example, pred, trace, pred_name, pred_trace):
    """
    GEPA-aware metric. Returns ScoreWithFeedback so GEPA can reflect
    on *why* a prompt scored the way it did and propose precise fixes.

    Args:
        gold: The gold example
        pred: The prediction from the module
        trace: Execution trace
        pred_name: Name of the predicted field
        pred_trace: Trace of the predicted field
    """
    evolved = pred.evolved_prompt

    # ── Fast heuristic: penalise surviving hedge/restriction language ──
    text_lower = evolved.lower()
    hedge_hits = [p for p in HEDGE_PATTERNS if p in text_lower]
    hedge_penalty = min(0.4, len(hedge_hits) * 0.08)  # up to -0.4

    # ── LLM judge: novelty + boldness + generativity ──
    with dspy.context(lm=_judge_lm):
        judge_result = dspy.Predict(
            "evolved_prompt -> novelty_score, boldness_score, generativity_score, critique"
        )(
            evolved_prompt=f"""
Score this evolved ideation prompt on three axes (each 0–10):

NOVELTY (0-10): Does it compel genuinely new, non-obvious ideas?
BOLDNESS (0-10): Is the voice authoritative, unhedged, and electric?
  Penalise surviving phrases like: {", ".join(HEDGE_PATTERNS[:6])}
GENERATIVITY (0-10): Does it demand rich, specific, vivid outputs (not vague waffle)?

Prompt to score:
---
{evolved}
---

Return three integers and a single critique sentence.
novelty_score:
boldness_score:
generativity_score:
critique:
"""
        )

    try:
        n = float(judge_result.novelty_score) / 10
        b = float(judge_result.boldness_score) / 10
        g = float(judge_result.generativity_score) / 10
        score = ((n + b + g) / 3) - hedge_penalty
        score = max(0.0, min(1.0, score))
        critique = judge_result.critique
    except Exception:
        score = max(0.0, 0.5 - hedge_penalty)
        critique = "Could not parse judge scores."

    feedback = (
        f"Score: {score:.2f}. "
        f"Hedge phrases still present: {hedge_hits if hedge_hits else 'none'}. "
        f"Judge critique: {critique}"
    )

    return ScoreWithFeedback(score=score, feedback=feedback)


# ─────────────────────────────────────────────
# 6. Build trainset (no labels — GEPA uses
#    reflection, not ground-truth answers)
# ─────────────────────────────────────────────

trainset = [
    dspy.Example(original_prompt=p).with_inputs("original_prompt") for p in PROMPTS
]

print(f"📦 Trainset: {len(trainset)} prompts\n")

# ─────────────────────────────────────────────
# 7. Run dspy.GEPA
# ─────────────────────────────────────────────

evolver = PromptEvolver()

print("🧬 Running dspy.GEPA optimizer...")
print(f"   Budget: {args.max_metric_calls} metric calls")
print("   GEPA will reflect on execution traces in natural language")
print("   and evolve the EvolvePrompt signature iteratively.\n")

optimizer = dspy.GEPA(
    metric=gepa_metric,
    reflection_lm=reflection_lm,
    max_metric_calls=args.max_metric_calls,
)

optimized_evolver = optimizer.compile(
    student=evolver,
    trainset=trainset,
)

print("\n✅ GEPA optimization complete.\n")

# ─────────────────────────────────────────────
# 8. Apply optimized evolver to all 7 prompts
# ─────────────────────────────────────────────

results = []

print("=" * 60)
print("GENERATING FINAL EVOLVED PROMPTS")
print("=" * 60)

for i, original in enumerate(PROMPTS, 1):
    print(f"\n✨ Finalizing Prompt {i}...")
    pred = optimized_evolver(original_prompt=original)
    evolved = pred.evolved_prompt

    # Score original vs evolved for comparison
    orig_ex = dspy.Example(original_prompt=original).with_inputs("original_prompt")
    orig_pred = dspy.Prediction(evolved_prompt=original)  # score original as-is
    evol_pred = dspy.Prediction(evolved_prompt=evolved)

    orig_result = gepa_metric(orig_ex, orig_pred, None, "evolved_prompt", None)
    evol_result = gepa_metric(orig_ex, evol_pred, None, "evolved_prompt", None)

    orig_score = (
        orig_result.score if hasattr(orig_result, "score") else float(orig_result)
    )
    evol_score = (
        evol_result.score if hasattr(evol_result, "score") else float(evol_result)
    )
    delta = evol_score - orig_score
    arrow = "📈" if delta > 0 else ("📉" if delta < 0 else "➡️")

    print(f"   {arrow} {orig_score:.2f} → {evol_score:.2f}  ({delta:+.2f})")

    results.append(
        {
            "prompt_number": i,
            "original_prompt": original,
            "evolved_prompt": evolved,
            "original_score": round(orig_score, 3),
            "evolved_score": round(evol_score, 3),
            "delta": round(delta, 3),
            "original_feedback": orig_result.feedback
            if hasattr(orig_result, "feedback")
            else "",
            "evolved_feedback": evol_result.feedback
            if hasattr(evol_result, "feedback")
            else "",
        }
    )

# ─────────────────────────────────────────────
# 9. Save outputs
# ─────────────────────────────────────────────

# Create outputs directory if it doesn't exist
output_dir = Path("outputs")
output_dir.mkdir(exist_ok=True)

with open(output_dir / "evolved_prompts.json", "w") as f:
    json.dump(results, f, indent=2)

md_lines = [
    "# Evolved Prompts — dspy.GEPA\n\n",
    "> **Optimizer**: GEPA (Genetic-Pareto) — reflective prompt evolution  \n",
    "> **Axes**: Novelty · Boldness · Generativity  \n",
    "> **Method**: LLM reflects on *why* each prompt scored low, then proposes targeted fixes\n\n",
    "---\n\n",
]

for r in results:
    delta_str = f"{r['delta']:+.3f}"
    md_lines.append(f"## Prompt {r['prompt_number']}\n\n")
    md_lines.append(
        f"**Score**: `{r['original_score']}` → `{r['evolved_score']}` ({delta_str})\n\n"
    )
    md_lines.append(f"**GEPA feedback on evolved**: {r['evolved_feedback']}\n\n")
    md_lines.append("### 🔴 Original\n\n")
    md_lines.append(f"```\n{r['original_prompt']}\n```\n\n")
    md_lines.append("### 🟢 Evolved\n\n")
    md_lines.append(f"```\n{r['evolved_prompt']}\n```\n\n")
    md_lines.append("---\n\n")

with open(output_dir / "evolved_prompts.md", "w") as f:
    f.writelines(md_lines)

avg_delta = sum(r["delta"] for r in results) / len(results)
best = max(results, key=lambda r: r["delta"])

print("\n" + "=" * 60)
print("✅ DONE")
print("=" * 60)
print(f"\n📄 evolved_prompts.md")
print(f"📦 evolved_prompts.json")
print(f"\n📊 Avg score delta : {avg_delta:+.3f}")
print(f"🏆 Best improvement: Prompt {best['prompt_number']} ({best['delta']:+.3f})")
