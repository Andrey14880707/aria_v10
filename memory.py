# memory.py — семантический поиск по памяти ARIA (TF-IDF cosine similarity)
import math
import re
from collections import Counter
from typing import Any, Dict, List, Tuple


def _tokenize(text: str) -> List[str]:
    return re.findall(r"\w+", text.lower())


def _tfidf_scores(query: str, documents: List[str]) -> List[Tuple[int, float]]:
    """Возвращает (индекс, оценка) отсортировано по убыванию."""
    if not documents:
        return []

    query_tokens = _tokenize(query)
    if not query_tokens:
        return [(i, 0.0) for i in range(len(documents))]

    doc_tokens = [_tokenize(doc) for doc in documents]
    N = len(documents)

    # IDF
    df: Counter = Counter()
    for tokens in doc_tokens:
        for term in set(tokens):
            df[term] += 1

    idf = {term: math.log((N + 1) / (freq + 1)) + 1 for term, freq in df.items()}

    # Query vector
    q_tf = Counter(query_tokens)
    q_vec = {t: c * idf.get(t, 1.0) for t, c in q_tf.items()}
    q_norm = math.sqrt(sum(v ** 2 for v in q_vec.values())) or 1.0

    results: List[Tuple[int, float]] = []
    for i, tokens in enumerate(doc_tokens):
        tf = Counter(tokens)
        d_vec = {t: c * idf.get(t, 1.0) for t, c in tf.items()}
        d_norm = math.sqrt(sum(v ** 2 for v in d_vec.values())) or 1.0

        dot = sum(q_vec.get(t, 0.0) * d_vec.get(t, 0.0) for t in q_vec)
        score = dot / (q_norm * d_norm)
        results.append((i, score))

    return sorted(results, key=lambda x: x[1], reverse=True)


class SemanticMemory:
    """Семантический поиск по фактам, заметкам и истории сообщений."""

    def __init__(self, db: Any):
        self.db = db

    def search(self, query: str, limit: int = 8) -> List[Dict[str, Any]]:
        candidates: List[Dict[str, str]] = []

        # Факты
        try:
            facts = self.db.search_facts("", limit=200)
            for f in facts:
                candidates.append({"source": "факт", "text": f["fact"]})
        except Exception:
            pass

        # Заметки
        try:
            notes = self.db.recent_notes(100)
            for n in notes:
                candidates.append({"source": "заметка", "text": n["note"]})
        except Exception:
            pass

        # История сообщений
        try:
            messages = self.db.recent_messages(limit=100)
            for m in messages:
                role = "ты" if m["role"] == "user" else "ARIA"
                candidates.append({"source": f"история({role})", "text": m["content"]})
        except Exception:
            pass

        if not candidates:
            return []

        docs = [c["text"] for c in candidates]
        scored = _tfidf_scores(query, docs)

        results = []
        for idx, score in scored[:limit]:
            if score < 0.05:
                break
            item = dict(candidates[idx])
            item["score"] = round(score, 3)
            results.append(item)

        return results

    def relevant_context(self, query: str, max_chars: int = 800) -> str:
        """Возвращает строку с релевантными воспоминаниями для добавления в промпт."""
        results = self.search(query, limit=5)
        if not results:
            return ""

        lines = []
        total = 0
        for item in results:
            line = f"[{item['source']}] {item['text']}"
            if total + len(line) > max_chars:
                break
            lines.append(line)
            total += len(line)

        return "\n".join(lines)
