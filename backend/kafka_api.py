"""HW8 Part 1 FastAPI wrapper: HTTP in, Kafka request/response out.

    uvicorn kafka_api:app --host 0.0.0.0 --port 8458     (runs in the s6758_listing_api container)

POST /kafka/listings  {"operation": "...", "data": {...}, "correlation_id": optional}
The client's correlation_id is forwarded unchanged; a new one is made only if the client sent none.
"""
import asyncio
import json
import os
import uuid
from contextlib import asynccontextmanager

from aiokafka import AIOKafkaConsumer, AIOKafkaProducer, TopicPartition
from fastapi import FastAPI
from pydantic import BaseModel

from app.kafka_listings import BOOTSTRAP, REQUEST_TOPIC, RESPONSE_TOPIC, log, make_request

PORT = int(os.getenv("PORT", "8458"))
TIMEOUT_SECONDS = 15


class ListingRequest(BaseModel):
    operation: str
    data: dict = {}
    correlation_id: str | None = None


class KafkaRPC:
    def __init__(self):
        self.producer = AIOKafkaProducer(bootstrap_servers=BOOTSTRAP)
        self.consumer = AIOKafkaConsumer(bootstrap_servers=BOOTSTRAP, enable_auto_commit=False)
        self.pending: dict[str, asyncio.Future] = {}
        self.task = None

    async def start(self):
        for attempt in range(1, 31):
            try:
                await self.producer.start()
                await self.consumer.start()
                break
            except Exception as exc:
                log("API", f"Kafka not ready, retry {attempt}", error=str(exc))
                await asyncio.sleep(2)
        # Read every partition of the response topic from its current end; no consumer-group rebalance wait.
        parts = self.consumer.partitions_for_topic(RESPONSE_TOPIC) or {0}
        self.consumer.assign([TopicPartition(RESPONSE_TOPIC, p) for p in parts])
        await self.consumer.seek_to_end()
        self.task = asyncio.create_task(self.read_responses())
        log("API", f"listening for responses on {RESPONSE_TOPIC}", bootstrap=BOOTSTRAP)

    async def stop(self):
        if self.task:
            self.task.cancel()
        await self.consumer.stop()
        await self.producer.stop()

    async def read_responses(self):
        async for msg in self.consumer:
            try:
                response = json.loads(msg.value.decode())
            except (UnicodeDecodeError, json.JSONDecodeError):
                continue
            cid = response.get("correlation_id")
            future = self.pending.pop(cid, None)
            log("API", f"received response from {msg.topic}", correlation_id=cid, partition=msg.partition,
                offset=msg.offset, matched=future is not None)
            if future and not future.done():
                future.set_result(response)

    async def request(self, correlation_id: str, operation: str, data: dict) -> dict:
        message = make_request(correlation_id, operation, data)
        future = asyncio.get_running_loop().create_future()
        self.pending[correlation_id] = future
        log("API", f"sending request to {REQUEST_TOPIC}", correlation_id=correlation_id, message=message)
        meta = await self.producer.send_and_wait(REQUEST_TOPIC, json.dumps(message).encode())
        log("API", "request delivered", correlation_id=correlation_id, partition=meta.partition, offset=meta.offset)
        try:
            return await asyncio.wait_for(future, timeout=TIMEOUT_SECONDS)
        except asyncio.TimeoutError:
            self.pending.pop(correlation_id, None)
            return {"correlation_id": correlation_id, "success": False, "error": "Timed out waiting for worker"}


rpc = KafkaRPC()


@asynccontextmanager
async def lifespan(app: FastAPI):
    await rpc.start()
    log("API", f"FastAPI server started at http://127.0.0.1:{PORT}")
    yield
    await rpc.stop()


app = FastAPI(title="s6758 Listing service over Kafka", lifespan=lifespan)


@app.get("/health")
async def health():
    return {"status": "ok", "request_topic": REQUEST_TOPIC, "response_topic": RESPONSE_TOPIC}


@app.post("/kafka/listings")
async def listing_operation(body: ListingRequest):
    cid = body.correlation_id or str(uuid.uuid4())
    log("API", "received from client", correlation_id=cid, operation=body.operation)
    response = await rpc.request(cid, body.operation, body.data)
    log("API", "returned response to client", correlation_id=cid, success=response.get("success"))
    return response
