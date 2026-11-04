# HW9 run steps

Install the Python packages (the agents also need Ollama with llama3.2:3b):

    pip install -r backend/requirements.txt

Start Redis, MySQL and Kafka:

    docker compose up -d redis kafka kafka-init
    docker start s6758-mysql

## Part 1

    python backend/run_hw09_counter.py

## Part 2

Run each one in its own terminal, from `kafka_agents/`:

    python planner.py
    python writer.py
    python reviewer.py

Then, from `backend/` and from the repository root:

    uvicorn qa_api:app --port 8458
    python backend/run_hw09_semantic.py

## Part 3

Keep the agents running. Misses in the sweep replay recorded agent answers, so `memo` runs first:

    python backend/run_hw09_sweep.py memo
    python backend/run_hw09_sweep.py sweep
    python backend/run_hw09_sweep.py stale

## Part 4

Needs Ollama only:

    python self_improving_agents/build_datasets.py
    python self_improving_agents/run_experiment.py demo
    python self_improving_agents/run_experiment.py train
    python self_improving_agents/run_experiment.py validate
    python self_improving_agents/run_experiment.py test

## Self-check

    python backend/make_hw09_metrics.py
    make verify-hw09
