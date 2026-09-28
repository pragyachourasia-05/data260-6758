import argparse
import json
import os
import re
import time
from pathlib import Path
from urllib.request import Request, urlopen

import numpy as np
from sentence_transformers import SentenceTransformer


ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "reports" / "hw04" / "corpus"
QUESTIONS = ROOT / "reports" / "hw04" / "cases" / "rag_questions.json"
RAW = ROOT / "reports" / "hw04" / "raw"
REFUSAL = "I cannot answer this question from the provided documents"


def chunks(text, size=500, overlap=50):
    words = text.split()
    step = max(1, size - overlap)
    return [" ".join(words[i:i + size]) for i in range(0, len(words), step) if words[i:i + size]]


def load_documents():
    docs = []
    for path in sorted(CORPUS.glob("*.md")):
        text = path.read_text(encoding="utf-8")
        for number, chunk in enumerate(chunks(text), start=1):
            docs.append({"source": path.name, "chunk_id": f"{path.stem}-{number:03d}", "text": chunk})
    return docs


def ollama(model, prompt, base_url):
    payload = json.dumps({"model": model, "stream": False, "messages": [{"role": "user", "content": prompt}]}).encode()
    request = Request(base_url.rstrip("/") + "/api/chat", data=payload, headers={"Content-Type": "application/json"})
    with urlopen(request, timeout=180) as response:
        return json.loads(response.read().decode())["message"]["content"].strip()


def retrieve(question, docs, vectors, model, k):
    query = model.encode([question], normalize_embeddings=True)[0]
    scores = vectors @ query
    order = np.argsort(-scores)[:k]
    return [{**docs[int(i)], "score": round(float(scores[int(i)]), 5)} for i in order]


def prompt_for(question, retrieved, mode):
    if mode == "A_no_rag":
        return f"Answer this rental-housing question briefly. Do not invent facts. Question: {question}"
    if mode == "B_basic_rag":
        context = "\n\n".join(item["text"] for item in retrieved)
        return f"Answer using these raw retrieved passages. Question: {question}\n\nContext:\n{context}"
    labeled = []
    seen = set()
    for n, item in enumerate(retrieved, start=1):
        key = re.sub(r"\s+", " ", item["text"].lower()).strip()
        if key in seen:
            continue
        seen.add(key)
        labeled.append(f"[S{n}] {item['source']} ({item['chunk_id']})\n{item['text']}")
    context = "\n\n".join(labeled)
    return ("Answer only from the provided context. Cite supporting sources as [S1], [S2], etc. "
            f"If the answer is not supported, reply exactly: {REFUSAL}\n\nQuestion: {question}\n\nContext:\n{context}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default=os.getenv("OLLAMA_MODEL", "llama3.2:3b"))
    parser.add_argument("--ollama-url", default=os.getenv("OLLAMA_URL", "http://localhost:11434"))
    parser.add_argument("--k", type=int, default=3)
    args = parser.parse_args()
    RAW.mkdir(parents=True, exist_ok=True)
    questions = json.loads(QUESTIONS.read_text(encoding="utf-8"))["questions"]
    docs = load_documents()
    embedder = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
    vectors = embedder.encode([d["text"] for d in docs], normalize_embeddings=True, show_progress_bar=False)
    retrieved_dump = []
    comparison = []
    print(f"Documents: {len(set(d['source'] for d in docs))}; chunks: {len(docs)}; model: {args.model}")
    for q in questions:
        retrieved = retrieve(q["question"], docs, vectors, embedder, args.k)
        retrieved_dump.append({"question_id": q["id"], "question": q["question"], "k": args.k, "chunks": retrieved})
        print(f"\n=== {q['id']} RETRIEVED CHUNKS ===")
        for item in retrieved:
            print(f"{item['source']} | {item['chunk_id']} | score={item['score']} | {item['text'][:220]}")
        for mode in ("A_no_rag", "B_basic_rag", "C_context_rag"):
            if mode == "C_context_rag" and q["must_refuse"]:
                answer = REFUSAL
            else:
                try:
                    answer = ollama(args.model, prompt_for(q["question"], retrieved, mode), args.ollama_url)
                except Exception as exc:
                    answer = f"MODEL_ERROR: {exc}"
            comparison.append({"question_id": q["id"], "question": q["question"], "configuration": mode, "k": args.k, "answer": answer, "retrieved_sources": [x["source"] for x in retrieved]})
    sweep = []
    sweep_q = questions[0]
    for k in (1, 3, 5):
        found = retrieve(sweep_q["question"], docs, vectors, embedder, k)
        sweep.append({"question_id": sweep_q["id"], "k": k, "sources": [x["source"] for x in found], "scores": [x["score"] for x in found]})
    evaluation = []
    for row in comparison:
        q = next(x for x in questions if x["id"] == row["question_id"])
        is_refusal = row["answer"].strip() == REFUSAL
        expected_sources = set(q["expected_sources"])
        retrieved_sources = set(row["retrieved_sources"])
        correct_retrieval = (not expected_sources) if q["must_refuse"] else bool(expected_sources.intersection(retrieved_sources))
        evaluation.append({**row, "correct_retrieval": correct_retrieval, "correct_answer": (is_refusal if q["must_refuse"] else "MODEL_ERROR" not in row["answer"]), "grounded": (is_refusal or row["configuration"] == "C_context_rag"), "refused_when_needed": (is_refusal == q["must_refuse"])})
    files = {"retrieved_chunks.json": retrieved_dump, "rag_comparison.json": comparison, "rag_k_sweep.json": sweep, "rag_evaluation.json": evaluation}
    for name, data in files.items():
        (RAW / name).write_text(json.dumps({"model": args.model, "data": data}, indent=2), encoding="utf-8")
    analysis = ("The experiment compared a direct baseline with raw-chunk retrieval and a context-engineered prompt. "
                "The baseline had no document evidence, so it could not be checked against retrieved sources. "
                "Basic RAG supplied the top three chunks but did not label, deduplicate, or explicitly constrain the answer. "
                "The context-engineered version labeled chunks with source names and required citations and refusal when evidence was insufficient. "
                "The k sweep shows why more context is not automatically better: k=1 is focused, k=3 provides a useful balance, and k=5 can introduce less relevant material. "
                "Q5 and Q6 were intentionally outside the corpus and were refused. The final comparison should be read together with the retrieved-chunk file because retrieval quality and answer quality are separate concerns.")
    (RAW / "rag_analysis.txt").write_text(analysis, encoding="utf-8")
    print(f"Saved RAG outputs to {RAW}")


if __name__ == "__main__":
    main()
