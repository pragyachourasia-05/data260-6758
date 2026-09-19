\# HW3 Retrieval Metrics



Model: `sentence-transformers/all-MiniLM-L6-v2`



Top-k: `3`



Corpus: California tenant guide and HUD fair-housing guide.



\## Retrieval Comparison



| Technique | Chunks | Average chunk length | Top-1 cosine | Mean@3 cosine | Recall@3 | Mean latency |

|---|---:|---:|---:|---:|---:|---:|

| Token | 88 | 2290.20 | 0.6283 | 0.5765 | 1.00 | 132.392 ms |

| Semantic | 51 | 3454.65 | 0.6310 | 0.5510 | 0.80 | 19.030 ms |

| Sentence-window | 951 | 185.26 | 0.7490 | 0.6902 | 0.80 | 50.191 ms |



Recall@3 is source-level recall: a question counts as retrieved when its expected source document appears in the top three results.



\## Observations



The sentence-window technique achieved the strongest similarity scores, with a top-1 cosine of 0.7490 and a mean@3 cosine of 0.6902. Its smaller chunks preserved focused sentence-level context, which helped the embedding model match questions to relevant passages.



Semantic chunking was the fastest technique at 19.030 milliseconds on average. However, its larger chunks produced slightly lower mean similarity and 0.80 recall. Token chunking achieved perfect source-level recall for these five questions but had the highest average retrieval latency.



\## False Positive



The security-deposit question produced a high-scoring result related to military-service deposit rules. Although the topic contained the words “security deposit,” it did not directly answer the expected 21-day return requirement. This shows that embedding similarity can identify related language without guaranteeing that the retrieved passage contains the exact answer.



\## Conclusion



Sentence-window chunking was the strongest overall technique for this corpus because it produced the highest top-1 and mean@3 cosine scores. Token chunking provided the best source-level recall in this experiment, while semantic chunking offered the lowest retrieval latency. I would select sentence-window chunking when answer relevance is more important than the smallest possible latency.

