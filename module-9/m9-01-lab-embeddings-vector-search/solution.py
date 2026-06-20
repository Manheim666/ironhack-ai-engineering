import json
import os
import numpy as np


GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY", "")

EMBED_BACKEND = os.environ.get(
    "EMBED_BACKEND", "gemini" if GOOGLE_API_KEY else "local"
)

KB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "knowledge_base.json")

TEST_QUERIES = [
    "my laptop won't switch on",
    "how do I stop being billed every month?",
    "access denied error when saving a file",
    "where do I leave my car in the evening?",
    "what's the wifi password?",
]

def _gemini_embedder():
    from google import genai

    client = genai.Client(api_key=GOOGLE_API_KEY)

    def embed(texts):
        resp = client.models.embed_content(
            model="gemini-embedding-001", contents=texts
        )
        return [np.array(e.values, dtype=np.float32) for e in resp.embeddings]

    return embed


def _local_embedder():
    from sentence_transformers import SentenceTransformer

    model = SentenceTransformer("all-MiniLM-L6-v2")

    def embed(texts):
        vecs = model.encode(texts, convert_to_numpy=True)
        return [v.astype(np.float32) for v in vecs]

    return embed


def get_embedder():
    if EMBED_BACKEND == "gemini":
        if not GOOGLE_API_KEY:
            raise SystemExit(
                "EMBED_BACKEND=gemini but GOOGLE_API_KEY is empty. "
                "Set the key or use EMBED_BACKEND=local."
            )
        print("Embedding backend: Gemini gemini-embedding-001")
        return _gemini_embedder()
    print("Embedding backend: local sentence-transformers all-MiniLM-L6-v2")
    return _local_embedder()



def cosine_similarity(query_vec, matrix):
    q_norm = query_vec / (np.linalg.norm(query_vec) + 1e-10)
    m_norms = matrix / (np.linalg.norm(matrix, axis=1, keepdims=True) + 1e-10)
    return m_norms @ q_norm  # dot product of unit vectors == cosine


def main():
    with open(KB_PATH) as f:
        kb = json.load(f)

    embed = get_embedder()

    passage_vecs = np.vstack(embed([p["text"] for p in kb]))

    print(f"\nIndexed {len(kb)} passages -> {passage_vecs.shape[1]}-dim vectors\n")

    for query in TEST_QUERIES:
        q_vec = embed([query])[0]
        scores = cosine_similarity(q_vec, passage_vecs)
        top3 = np.argsort(scores)[::-1][:3]

        print("=" * 70)
        print(f"QUERY: {query}")
        for rank, idx in enumerate(top3, 1):
            p = kb[idx]
            print(f"  {rank}. score={scores[idx]:.4f}  [{p['id']} | {p['source']}]")
            print(f"     {p['text'][:90]}...")
        print()


if __name__ == "__main__":
    main()


# ==========================================================================
# REFLECTION
# ==========================================================================
# Q: For each query, did the best match share any words with the query?
#
# A: 
# 1. "my laptop won't switch on" → "To power up a device that won't turn on..."
#    YES - shares "won't" and "on"
#
# 2. "how do I stop being billed every month?" → "To cancel your subscription..."
#    NO - uses completely different words! "stop being billed" ≠ "cancel subscription"
#    but the embedding correctly matched them by meaning.
#
# 3. "access denied error when saving a file" → "The error code 0x80070005 means 'access denied'..."
#    YES - shares "access denied" and "error"
#
# 4. "where do I leave my car in the evening?" → "Employees may park in lot B after 6pm..."
#    PARTIAL - shares "car" and "evening" is close to "6pm"
#
# 5. "what's the wifi password?" → "Reset your password from the login screen..."
#    YES - shares "password"
#
# CONCLUSION: The embeddings captured *semantic meaning*, not just keyword matching.
# Query #2 proves it best—"stop being billed" and "cancel subscription" have zero overlapping words
# but were matched with a 0.5408 score because the embedding understands they express the same intent.
# This shows embeddings can retrieve relevant documents even when queries use completely different terminology.
#
# For the stretch goal ("what's the wifi password?" with 0.3186 top score):
# The score of 0.32 is moderate-to-low. A threshold around 0.4-0.5 would be reasonable
# to filter out "not found" results. Queries with no relevant passage would score much lower.
#
# - "my laptop won't switch on"        -> kb-02 ("...device that won't turn on,
#   hold the power button..."). Shares almost nothing: "switch on" vs "turn on",
#   "laptop" vs "device". The embedding matched the MEANING (power problem), not
#   the words.
# - "how do I stop being billed every month?" -> the subscription/cancel passage.
#   "billed every month" never appears literally; the model linked it to
#   recurring payment / cancellation.
# - "access denied error when saving a file" -> the permissions / 0x80070005
#   passage. Matched on the concept of a permission error, not shared tokens.
# - "where do I leave my car in the evening?" -> kb-01 about parking in lot B
#   after 6pm. "car"/"evening" vs "park"/"6pm" -- pure meaning overlap.
#
# What this tells us: the embedding captured SEMANTICS, not surface words. A
# plain keyword search would miss all four because the query and the answer use
# different vocabulary for the same idea. The hand-written dot product is enough
# to retrieve by meaning.
#
# Stretch -- "what's the wifi password?": this is NOT in the knowledge base, so
# the top cosine score is noticeably LOWER than the answerable queries. That gap
# is exactly what a similarity THRESHOLD exploits: if the best score falls below
# a cutoff (tuned on known-good queries), the system can answer "I don't have
# information on that" instead of forcing a wrong passage to the top.
