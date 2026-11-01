# HW8 run steps

Install the Python packages (Part 2 also needs Ollama with llama3.2:3b):

    pip install -r backend/requirements.txt

Start Kafka, the worker and FastAPI on port 8458:

    docker compose up -d --build kafka kafka-init listing-worker listing-api

## Part 1

    python homework_demo.py
    python homework_demo.py --sequence

## Part 2

Create the topics:

    docker exec s6758_kafka /opt/kafka/bin/kafka-topics.sh --create --topic s6758_inbox --partitions 1 --replication-factor 1 --bootstrap-server localhost:9092
    docker exec s6758_kafka /opt/kafka/bin/kafka-topics.sh --create --topic s6758_tasks --partitions 2 --replication-factor 1 --bootstrap-server localhost:9092
    docker exec s6758_kafka /opt/kafka/bin/kafka-topics.sh --create --topic s6758_drafts --partitions 1 --replication-factor 1 --bootstrap-server localhost:9092
    docker exec s6758_kafka /opt/kafka/bin/kafka-topics.sh --create --topic s6758_final --partitions 1 --replication-factor 1 --bootstrap-server localhost:9092

Run each one in its own terminal, from `kafka_agents/`:

    python planner.py
    python writer.py
    python reviewer.py
    python send_question.py

## Part 3

Stop the agents first, then run from `kafka_agents/` (this recreates the topics):

    python failure_tests.py all

## Self-check

    make verify-hw08

or `python verify_hw08.py`. It writes `reports/hw08/verification.json`.
