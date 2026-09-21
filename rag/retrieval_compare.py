import argparse
import json
import time
from pathlib import Path

import fitz
import numpy as np
import yaml

from llama_index.core import Document, Settings, VectorStoreIndex
from llama_index.core.node_parser import (
    SemanticSplitterNodeParser,
    SentenceWindowNodeParser,
    TokenTextSplitter,
)
from llama_index.embeddings.huggingface import HuggingFaceEmbedding


ROOT = Path(__file__).resolve().parents[1]
CORPUS_DIR = ROOT / "reports" / "hw03" / "corpus"
QUESTIONS_FILE = ROOT / "reports" / "hw03" / "questions.yaml"
RAW_DIR = ROOT / "reports" / "hw03" / "raw"


def cosine_similarity(a, b):
    a = np.asarray(a, dtype=np.float32)
    b = np.asarray(b, dtype=np.float32)

    denominator = np.linalg.norm(a) * np.linalg.norm(b)

    if denominator == 0:
        return 0.0

    return float(np.dot(a, b) / denominator)


def load_questions():
    with QUESTIONS_FILE.open("r", encoding="utf-8") as file:
        return yaml.safe_load(file)["questions"]


def make_chunkers(embed_model):
    return {
        "token": TokenTextSplitter(
            chunk_size=512,
            chunk_overlap=64,
        ),
        "semantic": SemanticSplitterNodeParser.from_defaults(
            buffer_size=1,
            breakpoint_percentile_threshold=95,
            embed_model=embed_model,
        ),
        "sentence_window": SentenceWindowNodeParser.from_defaults(
            window_size=3,
            window_metadata_key="window",
            original_text_metadata_key="original_text",
        ),
    }


def source_name(node):
    metadata = node.metadata or {}

    return (
        metadata.get("file_name")
        or metadata.get("filename")
        or metadata.get("file_path")
        or ""
    )


def load_pdf_documents(max_chars_per_document=150000):
    documents = []

    for pdf_path in sorted(CORPUS_DIR.glob("*.pdf")):
        print(f"Reading {pdf_path.name}...")

        pdf = fitz.open(pdf_path)

        extracted_text = "\n".join(
            page.get_text("text")
            for page in pdf
        )

        pdf.close()

        documents.append(
            Document(
                text=extracted_text[:max_chars_per_document],
                metadata={
                    "file_name": pdf_path.name,
                    "source_file": pdf_path.name,
                },
            )
        )

    return documents


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--k",
        type=int,
        default=3,
    )

    parser.add_argument(
        "--model",
        default="sentence-transformers/all-MiniLM-L6-v2",
    )

    args = parser.parse_args()

    RAW_DIR.mkdir(parents=True, exist_ok=True)

    print("Loading embedding model...")

    embed_model = HuggingFaceEmbedding(
        model_name=args.model
    )

    Settings.embed_model = embed_model

    print("Loading corpus...")

    max_chars_per_document = 150000

    documents = load_pdf_documents(
        max_chars_per_document=max_chars_per_document
    )

    print(f"Documents loaded: {len(documents)}")
    print(
        "Maximum characters per document: "
        f"{max_chars_per_document}"
    )

    questions = load_questions()
    chunkers = make_chunkers(embed_model)

    all_results = []
    summaries = []

    for technique, chunker in chunkers.items():
        print(f"\n===== TECHNIQUE: {technique.upper()} =====")

        nodes = chunker.get_nodes_from_documents(documents)

        if not nodes:
            print("No nodes created.")
            continue

        print(f"Chunks created: {len(nodes)}")
        print("Building vector index...")

        index = VectorStoreIndex(
            nodes,
            embed_model=embed_model,
        )

        retriever = index.as_retriever(
            similarity_top_k=args.k
        )

        chunk_lengths = [
            len(node.get_content(metadata_mode="none"))
            for node in nodes
        ]

        technique_results = []

        for question in questions:
            query = question["question"]
            expected_source = question["expected_source"]

            print(
                f"\nRunning question {question['id']}: "
                f"{query}"
            )

            query_embedding = (
                embed_model.get_query_embedding(query)
            )

            start = time.perf_counter()

            retrieved = retriever.retrieve(query)

            latency_ms = (
                time.perf_counter() - start
            ) * 1000

            rows = []

            for rank, item in enumerate(
                retrieved,
                start=1,
            ):
                text = item.node.get_content(
                    metadata_mode="none"
                )

                document_embedding = (
                    embed_model.get_text_embedding(text)
                )

                cosine = cosine_similarity(
                    query_embedding,
                    document_embedding,
                )

                matched_source = source_name(item.node)

                rows.append(
                    {
                        "rank": rank,
                        "store_score": (
                            float(item.score)
                            if item.score is not None
                            else None
                        ),
                        "cosine_similarity": cosine,
                        "chunk_length": len(text),
                        "preview": text[:160].replace(
                            "\n",
                            " ",
                        ),
                        "source_file": matched_source,
                        "expected_source_match": (
                            expected_source in matched_source
                        ),
                    }
                )

            source_found = any(
                row["expected_source_match"]
                for row in rows
            )

            result = {
                "technique": technique,
                "question_id": question["id"],
                "question": query,
                "expected_source": expected_source,
                "query_embedding_dimension": len(
                    query_embedding
                ),
                "query_embedding_first_8": [
                    float(value)
                    for value in query_embedding[:8]
                ],
                "document_vector_shape": [
                    len(rows),
                    len(query_embedding),
                ],
                "retrieval_latency_ms": round(
                    latency_ms,
                    3,
                ),
                "source_recall_at_k": source_found,
                "results": rows,
            }

            technique_results.append(result)
            all_results.append(result)

            print(
                "Query vector dimension: "
                f"{len(query_embedding)}"
            )

            print(
                "Query vector first 8: "
                f"{query_embedding[:8]}"
            )

            print(
                "Document vector shape: "
                f"{len(rows)} x "
                f"{len(query_embedding)}"
            )

            print(
                "Retrieval latency: "
                f"{latency_ms:.2f} ms"
            )

            print(
                "rank | store_score | cosine_sim | "
                "chunk_len | preview"
            )

            for row in rows:
                print(
                    f"{row['rank']:>4} | "
                    f"{row['store_score']} | "
                    f"{row['cosine_similarity']:.4f} | "
                    f"{row['chunk_length']} | "
                    f"{row['preview']}"
                )

        all_cosines = [
            row["cosine_similarity"]
            for result in technique_results
            for row in result["results"]
        ]

        top1_cosines = [
            max(
                [
                    row["cosine_similarity"]
                    for row in result["results"]
                ],
                default=0.0,
            )
            for result in technique_results
        ]

        latencies = [
            result["retrieval_latency_ms"]
            for result in technique_results
        ]

        recalls = [
            result["source_recall_at_k"]
            for result in technique_results
        ]

        summaries.append(
            {
                "technique": technique,
                "chunks": len(nodes),
                "average_chunk_length": round(
                    float(np.mean(chunk_lengths)),
                    2,
                ),
                "top1_cosine": round(
                    float(np.mean(top1_cosines)),
                    4,
                ),
                "mean_at_k_cosine": round(
                    float(np.mean(all_cosines)),
                    4,
                ),
                "recall_at_k": round(
                    float(np.mean(recalls)),
                    4,
                ),
                "mean_retrieval_latency_ms": round(
                    float(np.mean(latencies)),
                    3,
                ),
            }
        )

    results_file = RAW_DIR / "retrieval_results.json"
    summary_file = RAW_DIR / "retrieval_summary.json"

    with results_file.open(
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            {
                "model": args.model,
                "k": args.k,
                "results": all_results,
            },
            file,
            indent=2,
        )

    with summary_file.open(
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            {
                "model": args.model,
                "k": args.k,
                "summaries": summaries,
            },
            file,
            indent=2,
        )

    print("\n===== SUMMARY =====")
    print(
        json.dumps(
            summaries,
            indent=2,
        )
    )

    print(f"\nSaved: {results_file}")
    print(f"Saved: {summary_file}")


if __name__ == "__main__":
    main()