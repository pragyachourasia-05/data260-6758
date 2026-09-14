\# AI Use Disclosure



\## 1. How I used an AI assistant



I used an AI assistant to help understand the Homework 2 requirements, plan the LangGraph state flow, explain validation and retry behavior, troubleshoot local FastAPI and Ollama setup issues, and interpret experiment results.



I wrote, ran, and verified the code locally. I also performed the terminal commands, checked the outputs, captured the screenshots, and decided which evidence belonged in the report.



\## 2. Incorrect or unsuitable AI output



One unsuitable result was the Planner repeatedly generating tags longer than the required 30-character maximum. The retry loop initially continued to produce invalid tags and eventually abandoned the run at the validation ceiling.



\## 3. How I detected the problem



The Pydantic validation error explicitly identified tags longer than 30 characters. I also inspected the raw JSON experiment results and confirmed that all 30 Part 4b runs were classified as abandoned at the ceiling.



\## 4. What I changed and why it works



I kept the strict schema validation and retry mechanism instead of silently accepting invalid output. I compared retry ceilings of 2 and 10. The ceiling of 2 completed 0% of runs, while the ceiling of 10 completed 100% of runs. I selected ceiling 10 for deployment because it allowed the Planner enough attempts to correct its output.

