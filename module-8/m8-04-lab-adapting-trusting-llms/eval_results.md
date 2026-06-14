# Eval Results

## Task 2 — LLM-as-judge pass-rate table

Two variants scored against the same fixed test set (10 held-out support tickets)
with a judge LLM (`llama3.2:3b` via Ollama) and an explicit rubric.

| Variant | Cases | Passed | Pass rate |
|---------|-------|--------|-----------|
| Few-shot prompting   | 10 | 9  | 90% |
| Embeddings + NN      | 10 | 6 | 60% |

**Rubric used by the judge:**

> You are a strict grader for a support-ticket classifier. Valid labels are: billing, bug, feature_request, other. You are given the ticket text, the EXPECTED label, and the model's PREDICTED label. Reply with a single word: PASS if PREDICTED is the same category as EXPECTED, FAIL if they differ. Only the word PASS or FAIL, no explanation.

**Verdict (2-3 sentences):**

> Few-shot won (few-shot 90% vs embeddings 60%). On this run the
> judge's verdicts matched the true accuracy exactly (9/10 and 6/10),
> so it is trustworthy *here* — but only because it is essentially re-doing string
> equality on a closed label set, which a plain `==` does cheaper and with zero
> variance. I trust it as a sanity check, not as the ground-truth scorer.

**A case where the judge looked wrong:**

> The judge made no clear error on this run (it agreed with `==` on all 10 cases).
> The failure mode to watch — observed in an earlier run with a vaguer rubric — is
> soft grading: on a borderline ticket (a billing complaint phrased like a bug) the
> judge returned PASS for a *mismatched* label because it reasoned the prediction
> was "plausible" rather than strictly equal to the expected label. That tendency to
> reward defensible-but-wrong answers is exactly what makes LLM judges unreliable for
> strict accuracy metrics, and why the rubric here forces a same/differ decision.
