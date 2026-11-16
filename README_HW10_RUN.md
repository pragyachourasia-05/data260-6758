# HW10 run steps

Install the packages (needs Ollama with llama3.2:3b):

    pip install -r backend/requirements.txt

Start Kafka, MySQL and Redis:

    docker start s6758_kafka s6758-mysql s6758_redis

## Agents and evaluator

Run each one in its own terminal, from `kafka_agents/` (spans go to `reports/hw10/raw/spans.jsonl`):

    python planner.py
    python writer.py
    python reviewer.py
    python ../evaluation/evaluator.py

## Part 2 and Part 4

From the repository root:

    python backend/run_hw10.py examples      cache miss, cache hit, failed request
    python backend/run_hw10.py latency       50 new questions, all cache misses
    python backend/run_hw10.py report        p50 / p95 per stage

## Part 3

`evaluation/eval_cases.json` and `evaluation/human_labels.csv` are committed first. Then:

    python evaluation/validate_judge.py run
    python evaluation/validate_judge.py stats

## Part 1 dashboard

    streamlit run dashboard/app.py --server.port 8459

## Self-check

    make verify-hw10
