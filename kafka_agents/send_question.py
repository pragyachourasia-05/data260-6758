"""Sends one question to s6758_inbox and waits for its result on s6758_final.

    python send_question.py
    python send_question.py "your question"
"""
import asyncio
import json
import sys
import uuid

from aiokafka import AIOKafkaConsumer, AIOKafkaProducer, TopicPartition
from common import BOOTSTRAP, FINAL, INBOX, encode, log, now, start

QUESTION = "What should I check before signing a lease for an apartment listing near SJSU?"
TIMEOUT_SECONDS = 900


async def main(question: str):
    producer = await start(AIOKafkaProducer(bootstrap_servers=BOOTSTRAP), "SENDER")
    consumer = await start(AIOKafkaConsumer(bootstrap_servers=BOOTSTRAP, enable_auto_commit=False), "SENDER")
    parts = consumer.partitions_for_topic(FINAL) or {0}
    consumer.assign([TopicPartition(FINAL, p) for p in parts])
    await consumer.seek_to_end()  # only results that arrive after this question

    cid = str(uuid.uuid4())
    message = {"correlation_id": cid, "question": question, "sent_at": now(), "trace": [{"agent": "SENDER", "at": now()}]}
    meta = await producer.send_and_wait(INBOX, encode(message), key=cid.encode())
    log("SENDER", f"sent question to {INBOX}", correlation_id=cid, partition=meta.partition, offset=meta.offset,
        question=question)
    log("SENDER", f"waiting for the result on {FINAL}")
    try:
        async with asyncio.timeout(TIMEOUT_SECONDS):
            async for msg in consumer:
                result = json.loads(msg.value.decode())
                if result.get("correlation_id") != cid:
                    continue
                log("SENDER", f"received result from {FINAL}", correlation_id=cid, partition=msg.partition,
                    offset=msg.offset, status=result.get("status"))
                print("\nFinal message:")
                print(json.dumps(result, indent=2))
                return 0
    except TimeoutError:
        log("SENDER", "no result before timeout", correlation_id=cid)
        return 1
    finally:
        await consumer.stop()
        await producer.stop()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main(" ".join(sys.argv[1:]) or QUESTION)))
