# HW8 Part 3 - Fixes and comparison with HW2

## What I fixed

- **Duplicate delivery:** each agent saves the correlation_ids it has finished in a small SQLite table. If the same correlation_id comes again, the agent skips it and commits the offset.
- **Consumer death:** I turned off auto-commit. The offset is committed only after the outgoing message is delivered, so a Writer killed mid-work gets the message again after restart.
- **Poison message:** a failing message is tried 3 times. After that it goes to s6758_dead_letter with the error, and the offset is committed so later messages can continue.
- **Ordering:** messages are sent with the listing id as the key. All messages for one listing go to one partition, and one Writer reads that partition in order.

## Limits

- This gives at-least-once delivery. If an agent dies after sending its output but before saving the correlation_id, a redelivery can still produce a duplicate.
- The SQLite table only works when the agents run on one machine. Agents on different machines would need a shared database.
- A key keeps order per listing only. Messages for different listings can still finish in any order.
- The failure tests use --mock mode (no LLM call) so they run quickly. The Part 2 journey uses the real model.

## Comparison with the HW2 graph

In HW2 my LangGraph workflow ran as function calls in one process, so each step waited directly on the previous step.

**Benefits of Kafka**

1. Independent scaling: I ran two Writers in one consumer group and they shared the s6758_tasks partitions without changing the Planner or Reviewer.
2. Decoupled failure: when Writer was killed, the message stayed in Kafka and was finished after restart. In HW2 a crash would stop the whole run.

**New responsibilities**

1. Duplicate delivery: Kafka can deliver the same message again, so I have to make the agents idempotent. In HW2 each step ran once.
2. Ordering: order is only kept inside a partition, so I have to choose the message key. In HW2 the steps always ran in sequence.
