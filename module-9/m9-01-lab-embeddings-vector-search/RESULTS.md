# Lab 1 — Results (local `all-MiniLM-L6-v2` backend)

Run: `EMBED_BACKEND=local python3 solution.py`. Same model embeds passages and queries. Cosine computed by hand in NumPy (`cosine_similarity` in `solution.py`).

| Query | Top match | Score | Word overlap? |
| --- | --- | --- | --- |
| my laptop won't switch on | kb-02 "power up a device that won't turn on…" | 0.4369 | none ("switch on"≠"turn on", "laptop"≠"device") |
| how do I stop being billed every month? | kb-05 "cancel your subscription… End Plan" | 0.5408 | none ("billed/month"≠"cancel/subscription") |
| access denied error when saving a file | kb-08 "0x80070005 means 'access denied'…" | 0.5437 | "access denied" only |
| where do I leave my car in the evening? | kb-01 "park in lot B after 6pm…" | 0.3257 | none ("car/evening"≠"park/6pm") |
| what's the wifi password? *(not in KB)* | kb-07 "Reset your password…" | 0.3186 | weak — see below |

## Reflection

Three of the four answerable queries share **no** words with their correct passage, yet the hand-written dot product surfaces them first. The embedding captured **meaning**, not surface tokens — a keyword search would have missed all of them.

**Threshold (stretch):** the uncovered "wifi password" query peaks at **0.319**, below every answerable query's top score (0.44–0.54). A similarity cutoff in that gap lets the system answer *"I don't have that"* instead of returning a wrong passage with false confidence.