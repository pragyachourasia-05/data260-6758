\# AI Use Disclosure



I used an AI assistant as a study and debugging partner while completing this homework. I asked for help understanding the requirements, organizing the project into Parts 1–4, fixing errors, and deciding what evidence and screenshots were needed. I also used it to clarify concepts such as HTTP-only cookies, MySQL sessions, React routing, N+1 queries, indexes, EXPLAIN plans, embeddings, retrieval, and context engineering.



I performed the actual work on my computer. I created the folders, copied the application files, installed the packages, started Docker and MySQL, tested the FastAPI endpoints, logged in through the React application, added and modified rental listings, seeded the database, ran the benchmark, created the RAG corpus, and captured the screenshots for my report.



One issue I found during the RAG experiment was that some retrieved text looked incomplete in the terminal. For example, a line ended with “but the s”. I checked the Python code and found that the terminal was printing only the first 220 characters of each chunk. The stored JSON file contained the retrieved data, so I used that file to confirm that the output had not actually been lost.



I also checked the N+1 experiment instead of relying only on the program finishing. The naive endpoint used 11, 51, and 201 SQL statements for page sizes 10, 50, and 200. The fixed endpoint used one SQL statement for each page size. This confirmed that the comparison was testing the intended database behavior.



The AI assistant helped me understand and troubleshoot the work, but I made the implementation decisions, ran the commands, reviewed the results, and prepared the final evidence and report.

