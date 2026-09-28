\# HW4 Part 3 Metrics



\## Dataset



The database was seeded with 5,000 rental listings and 200 related detail rows using the deterministic seed value 6758. Re-running the seed script did not create duplicates.



\## Benchmark design



I compared two listing endpoints:



\- `naive`: retrieves the related details separately for each listing.

\- `fixed`: retrieves listings and related details using one combined database query.



Each endpoint was tested with page sizes 10, 50, and 200. Every case was executed 30 times, producing 180 total request measurements.



\## Results



| Endpoint | Page size | Requests | SQL statements/request | p50 (ms) | p95 (ms) | p99 (ms) |

|---|---:|---:|---:|---:|---:|---:|

| Naive | 10 | 30 | 11 | 2104.836 | 2129.820 | 2142.833 |

| Fixed | 10 | 30 | 1 | 2075.990 | 2095.114 | 2112.068 |

| Naive | 50 | 30 | 51 | 2194.628 | 2293.285 | 2339.411 |

| Fixed | 50 | 30 | 1 | 2076.815 | 2105.739 | 2114.048 |

| Naive | 200 | 30 | 201 | 2666.086 | 2849.806 | 2907.273 |

| Fixed | 200 | 30 | 1 | 2071.543 | 2118.028 | 2124.066 |



\## Interpretation



The naive endpoint demonstrates the N+1 query problem. Its database work increases with the number of returned records: 11 queries for 10 records, 51 queries for 50 records, and 201 queries for 200 records. The fixed endpoint uses one SQL statement for every page size because it loads the related information together with the listings.



The difference becomes more visible at page size 200. The naive endpoint has a p99 latency of 2907.273 ms, while the fixed endpoint has a p99 latency of 2124.066 ms. The fixed implementation also keeps database query volume constant, making it more scalable as the result page grows.



The raw measurements are stored in:



`reports/hw04/raw/nplus1\_results.json`

