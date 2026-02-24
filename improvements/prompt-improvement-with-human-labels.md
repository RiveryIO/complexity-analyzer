# Plan: Improving the Complexity Prompt with Human-Labeled PRs

This document outlines a plan to improve the labeling prompt over time for your specific company using human-labeled PRs, aligned with the "Human labeled. AI trained." approach (e.g., GEPA framework via DSPy).

---

## Phase 1: Collect Human Labels (Foundation)

### 1.1 Define the labeling format

- Use the same 1–10 scale and JSON output as the current prompt.
- Add a `human_complexity` column (and optionally `human_explanation`) to distinguish human labels from LLM output.

### 1.2 Create a labeling dataset

- **Option A — CSV with human override column**  
  Add `human_complexity` to the schema. When present, treat it as the ground truth for evaluation and training.

- **Option B — Separate labeling file**  
  Maintain `human_labels.csv` with: `pr_url`, `human_complexity`, `human_explanation`, `labeler`, `labeled_at`.

### 1.3 Labeling workflow

- Sample PRs from `complexity-report.csv` (e.g., stratified by current LLM score and team).
- Use a simple UI (spreadsheet, internal tool, or lightweight Streamlit app) where reviewers see the PR diff + title and assign 1–10.
- Aim for **~500–1000 PRs** for initial calibration; **2000+** for GEPA-style optimization.
- Have at least 2 reviewers on a subset (e.g., 10–20%) to measure inter-rater agreement.

---

## Phase 2: Evaluate Current Prompt

### 2.1 Metrics

| Metric | Purpose |
|--------|---------|
| **MAE** (Mean Absolute Error) | Overall score accuracy |
| **Within-1 agreement** | % of PRs where AI is within ±1 of human |
| **Exact match** | % of exact score matches |
| **Per-band accuracy** | Performance by band (1–2, 3–4, 5–6, 7–8, 9–10) |

### 2.2 Baseline run

```bash
# Run current prompt on human-labeled PRs, compare to human_complexity
complexity-cli batch-analyze --input-file human_labeled_prs.txt --output baseline_eval.csv
# Then compute metrics: MAE, within-1, exact match
```

### 2.3 Error analysis

- Identify systematic biases (e.g., over-scoring infra PRs, under-scoring migrations).
- Group by: team, repo, PR type (feat/fix/refactor), lines changed.
- Use this to decide what to fix in the prompt or via optimization.

---

## Phase 3: Iterate (Two Paths)

### Path A: Manual Prompt Iteration (Simpler, No New Dependencies)

1. Add **company-specific guidance** to `default.txt` based on error analysis (e.g., "Rivery data pipeline changes: add +1 when multiple sources/targets are involved").
2. Re-run evaluation and compare metrics.
3. Repeat until MAE and within-1 agreement are acceptable.
4. Bump `Prompt-Version` in the prompt file when you make changes.

**Pros:** No new tools, fits current architecture.  
**Cons:** Manual, slower, no automatic prompt search.

---

### Path B: DSPy + GEPA (Automated Optimization)

1. **Add DSPy** to the project and define a signature:

```python
class PRComplexity(dspy.Signature):
    """Estimate implementation complexity of a PR on 1-10 scale."""
    diff_excerpt: str = dspy.InputField(desc="PR diff and metadata")
    stats_json: str = dspy.InputField(desc="Additions, deletions, file counts")
    title: str = dspy.InputField()
    complexity: int = dspy.OutputField(desc="1-10 integer")
    explanation: str = dspy.OutputField(desc="Short rationale")
```

2. **Build a training set** in DSPy format:

```python
# Convert human_labels.csv to dspy.Example with inputs + complexity as label
trainset = [dspy.Example(pr_url=..., diff_excerpt=..., stats_json=..., title=..., complexity=human_score).with_inputs(...)]
```

3. **Define a metric** (e.g., negative MAE or within-1 agreement).
4. **Run GEPA** to optimize the prompt:

```python
optimizer = dspy.GEPA(metric=lambda pred, gold: -abs(pred.complexity - gold.complexity))
optimized = optimizer.compile(complexity_module, trainset=trainset)
```

5. **Extract the optimized prompt** from the compiled module and save it as your new `default.txt` (or a company-specific prompt file).

**Pros:** Automatic prompt search, can improve over time with more data.  
**Cons:** New dependency, setup effort, need to wire diff fetching into DSPy.

---

## Phase 4: Ongoing Improvement

### 4.1 Continuous labeling

- Label a small batch of new PRs each sprint (e.g., 20–50).
- Prioritize PRs where AI and human disagree.
- Add them to the human-labeled set.

### 4.2 Periodic re-evaluation

- Every quarter (or when you add ~200+ new labels), re-run evaluation.
- If metrics degrade, re-optimize (Path B) or refine the prompt (Path A).

### 4.3 Versioning

- Keep `Prompt-Version` in the prompt file.
- Log which prompt version was used for each analysis (e.g., in CSV or metadata).

---

## Suggested Rollout

| Week | Action |
|------|--------|
| 1–2 | Define schema, create `human_labels.csv`, build a simple labeling workflow |
| 3 | Label 200–500 PRs (start with stratified sample) |
| 4 | Run baseline evaluation, compute MAE and within-1 |
| 5 | Error analysis: identify biases and failure modes |
| 6–8 | **Path A:** Add company-specific rules and re-evaluate, **or** **Path B:** Integrate DSPy + GEPA and run first optimization |
| 9+ | Ongoing labeling and quarterly re-evaluation |

---

## Quick Wins (No New Infrastructure)

1. **Export a sample for labeling**  
   Use `complexity-cli batch-analyze` to produce a CSV, then add a `human_complexity` column in a spreadsheet.

2. **Compare AI vs human**  
   Write a small script that computes MAE and within-1 between `complexity` and `human_complexity`.

3. **Add 3–5 company-specific rules**  
   Based on your domains (e.g., Rivery, Boomi, data pipelines), add short guidance to `default.txt` and re-run on a sample.
