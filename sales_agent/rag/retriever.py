"""Hybrid RAG Retriever combining BM25 lexical scoring, scikit-learn TF-IDF cosine similarity, and synonym expansion."""

from __future__ import annotations

import json
import math
import re
import time
from collections import Counter
from pathlib import Path
from typing import Any

try:
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity

    HAS_SKLEARN = True
except ImportError:  # pragma: no cover - stdlib fallback
    HAS_SKLEARN = False

_STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "can", "do", "for", "from",
    "how", "i", "in", "is", "it", "me", "my", "of", "on", "or", "our", "that",
    "the", "this", "to", "us", "we", "what", "when", "where", "which", "who",
    "why", "will", "with", "you", "your",
}

_SYNONYM_MAP: dict[str, list[str]] = {
    "cost": ["price", "pricing", "tier", "plan", "budget", "expensive", "kitna", "precio", "prix", "kosten"],
    "price": ["cost", "pricing", "tier", "plan", "discount", "annual"],
    "security": ["soc2", "gdpr", "privacy", "encryption", "compliance", "safe", "suraksha", "seguridad", "sicherheit"],
    "crm": ["salesforce", "hubspot", "zoho", "integration", "calendar", "sync"],
    "demo": ["pilot", "trial", "poc", "meeting", "book", "schedule", "slot"],
    "setup": ["onboarding", "timeline", "implementation", "how long", "deploy"],
    "roi": ["payback", "savings", "case study", "value", "results", "metrics"],
    "language": ["multilingual", "hindi", "spanish", "french", "german", "voice"],
}


def _tokenize(text: str) -> list[str]:
    return [
        tok
        for tok in re.findall(r"[^\W_]+", (text or "").lower())
        if len(tok) > 1 and tok not in _STOPWORDS
    ]


def _expand_tokens(tokens: list[str]) -> list[str]:
    expanded = set(tokens)
    for tok in tokens:
        for key, synonyms in _SYNONYM_MAP.items():
            if tok == key or tok in synonyms:
                expanded.add(key)
                expanded.update(synonyms)
    return list(expanded)


def _char_trigrams(text: str) -> Counter[str]:
    clean = f"  {re.sub(r'\\s+', ' ', (text or '').lower())}  "
    return Counter(clean[i : i + 3] for i in range(max(0, len(clean) - 2)))


def _counter_cosine(a: Counter[str], b: Counter[str]) -> float:
    norm_a = sum(v * v for v in a.values())
    norm_b = sum(v * v for v in b.values())
    if not norm_a or not norm_b:
        return 0.0
    dot = sum(v * b[k] for k, v in a.items() if k in b)
    return dot / (math.sqrt(norm_a) * math.sqrt(norm_b))


class HybridRetriever:
    """Hybrid BM25 + TF-IDF Cosine RAG Retriever with runtime chunk ingestion."""

    def __init__(self, kb_path: str | Path) -> None:
        self.kb_path = Path(kb_path)
        self.company = "NexaCloud AI"
        self.product = "NexaOps"
        self.chunks: list[dict[str, Any]] = []
        self.idf: dict[str, float] = {}
        self.avg_doc_len = 1.0
        self._vectorizer = None
        self._tfidf_matrix = None
        self.load()

    def load(self) -> None:
        data = json.loads(self.kb_path.read_text(encoding="utf-8"))
        self.company = data.get("company", self.company)
        self.product = data.get("product", self.product)
        self.chunks = [self._index_chunk(c) for c in data.get("chunks", [])]
        self._rebuild_indexes()

    def _index_chunk(self, chunk: dict[str, Any]) -> dict[str, Any]:
        combined = f"{chunk['title']} {' '.join(chunk.get('tags', []))} {chunk['content']}"
        tokens = _tokenize(combined)
        return {
            **chunk,
            "_combined": combined,
            "_tokens": tokens,
            "_tf": Counter(tokens),
            "_trigrams": _char_trigrams(combined),
            "_doc_len": max(1, len(tokens)),
        }

    def _rebuild_indexes(self) -> None:
        n = max(1, len(self.chunks))
        df: Counter[str] = Counter()
        total_len = 0
        for chunk in self.chunks:
            total_len += chunk["_doc_len"]
            for term in set(chunk["_tokens"]):
                df[term] += 1
        self.avg_doc_len = total_len / n
        self.idf = {
            term: math.log(1.0 + (n - freq + 0.5) / (freq + 0.5))
            for term, freq in df.items()
        }

        if HAS_SKLEARN and self.chunks:
            self._vectorizer = TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 4), lowercase=True)
            self._tfidf_matrix = self._vectorizer.fit_transform([c["_combined"] for c in self.chunks])
        else:
            self._vectorizer = None
            self._tfidf_matrix = None

    def add_chunk(
        self,
        title: str,
        content: str,
        category: str = "custom",
        tags: list[str] | None = None,
    ) -> dict[str, Any]:
        """Index a new document at runtime and persist it to the JSON knowledge base."""
        new_chunk = {
            "id": f"kb-custom-{int(time.time() * 1000)}",
            "category": category,
            "title": title,
            "tags": tags or [],
            "content": content,
        }
        self.chunks.append(self._index_chunk(new_chunk))
        self._rebuild_indexes()

        self.kb_path.parent.mkdir(parents=True, exist_ok=True)
        self.kb_path.write_text(
            json.dumps(
                {
                    "company": self.company,
                    "product": self.product,
                    "chunks": self.list_chunks(),
                },
                indent=2,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        return new_chunk

    def list_chunks(self) -> list[dict[str, Any]]:
        return [
            {
                "id": c["id"],
                "category": c["category"],
                "title": c["title"],
                "tags": c.get("tags", []),
                "content": c["content"],
            }
            for c in self.chunks
        ]

    def retrieve(self, query: str, top_k: int = 3, min_score: float = 0.08) -> list[dict[str, Any]]:
        """Return top-k relevant chunks scored via BM25 + TF-IDF char n-gram cosine similarity."""
        if not self.chunks:
            return []

        base_tokens = _tokenize(query)
        expanded_tokens = _expand_tokens(base_tokens)
        expanded_query = f"{query} {' '.join(expanded_tokens)}"

        if HAS_SKLEARN and self._vectorizer is not None and self._tfidf_matrix is not None:
            q_vec = self._vectorizer.transform([expanded_query])
            sim_scores = cosine_similarity(q_vec, self._tfidf_matrix)[0]
        else:
            q_tri = _char_trigrams(expanded_query)
            sim_scores = [_counter_cosine(q_tri, c["_trigrams"]) for c in self.chunks]

        k1, b = 1.5, 0.75
        q_lower = (query or "").lower()
        scored: list[dict[str, Any]] = []

        for idx, chunk in enumerate(self.chunks):
            bm25 = 0.0
            for term in expanded_tokens:
                tf = chunk["_tf"].get(term, 0)
                if not tf:
                    continue
                idf = self.idf.get(term, 0.5)
                weight = 1.0 if term in base_tokens else 0.45
                bm25 += weight * idf * ((tf * (k1 + 1)) / (tf + k1 * (1 - b + b * (chunk["_doc_len"] / self.avg_doc_len))))

            bm25_norm = min(1.0, bm25 / 6.0)
            semantic = float(sim_scores[idx])
            tag_boost = 0.15 if any(t.lower() in q_lower for t in chunk.get("tags", [])) else 0.0
            score = round(min(0.99, bm25_norm * 0.65 + semantic * 0.35 + tag_boost), 3)

            if score >= min_score:
                scored.append(
                    {
                        "id": chunk["id"],
                        "category": chunk["category"],
                        "title": chunk["title"],
                        "content": chunk["content"],
                        "score": score,
                    }
                )

        scored.sort(key=lambda item: item["score"], reverse=True)
        return scored[:top_k]
