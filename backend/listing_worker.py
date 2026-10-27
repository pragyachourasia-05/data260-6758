"""HW8 Part 1 worker: consumes s6758_listing_requests, replies on the topic named by reply_to.

    python -u listing_worker.py        (runs in the s6758_listing_worker container)
"""
import asyncio
import json

from aiokafka import AIOKafkaConsumer, AIOKafkaProducer

from app.kafka_listings import BOOTSTRAP, REQUEST_TOPIC, log, make_response, process

listings: dict = {}  # in-memory store for this exercise


async def start_with_retry(client, name):
    for attempt in range(1, 31):
        try:
            await client.start()
            return
        except Exception as exc:  # Kafka may still be starting
            log("WORKER", f"{name} not ready, retry {attempt}", error=str(exc))
            await asyncio.sleep(2)
    raise RuntimeError(f"could not connect {name} to {BOOTSTRAP}")


async def handle(msg, producer):
    try:
        request = json.loads(msg.value.decode())
    except (UnicodeDecodeError, json.JSONDecodeError):
        log("WORKER", "skipped message that is not JSON", partition=msg.partition, offset=msg.offset)
        return
    cid, reply_to = request.get("correlation_id"), request.get("reply_to")
    operation, data = request.get("operation"), request.get("data")
    log("WORKER", f"received from {msg.topic}", correlation_id=cid, partition=msg.partition, offset=msg.offset,
        message=request)
    if not reply_to:
        log("WORKER", "no reply_to, cannot answer", correlation_id=cid)
        return

    if not cid:
        result = {"success": False, "error": "correlation_id is required"}
    else:
        result = process(listings, operation, data if data is not None else {})
    log("WORKER", "processed", correlation_id=cid, operation=operation, success=result["success"],
        stored_listings=len(listings))

    response = make_response(cid, result)
    log("WORKER", f"sending response to {reply_to}", correlation_id=cid, message=response)
    meta = await producer.send_and_wait(reply_to, json.dumps(response).encode())
    log("WORKER", "response delivered", correlation_id=cid, partition=meta.partition, offset=meta.offset)


async def main():
    consumer = AIOKafkaConsumer(REQUEST_TOPIC, bootstrap_servers=BOOTSTRAP, group_id="s6758-listing-worker",
                                auto_offset_reset="earliest", enable_auto_commit=False)
    producer = AIOKafkaProducer(bootstrap_servers=BOOTSTRAP)
    await start_with_retry(consumer, "consumer")
    await start_with_retry(producer, "producer")
    log("WORKER", f"subscribed to {REQUEST_TOPIC}", bootstrap=BOOTSTRAP)
    print("Consumer is ready and listening...", flush=True)
    try:
        async for msg in consumer:
            await handle(msg, producer)
            await consumer.commit()  # commit only after the reply was sent
    finally:
        await consumer.stop()
        await producer.stop()


if __name__ == "__main__":
    asyncio.run(main())
