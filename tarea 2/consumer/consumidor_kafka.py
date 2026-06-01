import os
import time
import json
import urllib.request
import urllib.error
import redis
from confluent_kafka import Consumer, Producer, KafkaException

KAFKA_BROKER           = os.getenv("KAFKA_BROKER", "localhost:9092")
REDIS_HOST             = os.getenv("REDIS_HOST", "redis-cache")
RESPONSE_GENERATOR_URL = os.getenv("RESPONSE_GENERATOR_URL", "http://generador_respuestas:8001")
CONSUMER_ID            = os.getenv("CONSUMER_ID", "consumer-1")
GROUP_ID               = os.getenv("GROUP_ID", "query-consumers")
MAX_RETRIES            = int(os.getenv("MAX_RETRIES", "3"))

TTL_CONFIG = {
    "q1": int(os.getenv("TTL_Q1", "60")),
    "q2": int(os.getenv("TTL_Q2", "120")),
    "q3": int(os.getenv("TTL_Q3", "180")),
    "q4": int(os.getenv("TTL_Q4", "300")),
    "q5": int(os.getenv("TTL_Q5", "60")),
}

def wait_for_redis():
    print(f"[{CONSUMER_ID}] Esperando a Redis")
    while True:
        try:
            r = redis.Redis(host=REDIS_HOST, port=6379, decode_responses=True)
            r.ping()
            print(f"[{CONSUMER_ID}] Redis listo.")
            return r
        except Exception:
            time.sleep(2)

def wait_for_kafka():
    print(f"[{CONSUMER_ID}] Esperando a Kafka")
    while True:
        try:
            p = Producer({"bootstrap.servers": KAFKA_BROKER})
            p.flush(timeout=3)
            print(f"[{CONSUMER_ID}] Kafka listo.")
            return
        except Exception:
            time.sleep(2)

def call_response_generator(query):
    data = json.dumps(query).encode("utf-8")
    req  = urllib.request.Request(
        RESPONSE_GENERATOR_URL,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            if resp.status == 200:
                return json.loads(resp.read())
            return None
    except Exception:
        return None

def publish_metric(producer, event):
    producer.produce("metrics", value=json.dumps(event).encode("utf-8"))
    producer.poll(0)

def main():
    cache = wait_for_redis()
    wait_for_kafka()
    time.sleep(3)

    try:
        cache.config_set("maxmemory-policy", "allkeys-lfu")
        print(f"[{CONSUMER_ID}] Redis configurado: allkeys-lfu")
    except Exception as e:
        print(f"[{CONSUMER_ID}] No se pudo configurar Redis: {e}")

    consumer = Consumer({
        "bootstrap.servers": KAFKA_BROKER,
        "group.id":          GROUP_ID,
        "auto.offset.reset": "earliest",
        "enable.auto.commit": True,
    })
    consumer.subscribe(["queries"])

    producer = Producer({
        "bootstrap.servers": KAFKA_BROKER,
        "acks": "all",
    })

    stats = {"procesadas": 0, "hits": 0, "misses": 0, "reintentos": 0, "dlq": 0}
    print(f"[{CONSUMER_ID}] Escuchando tópico 'queries'")

    try:
        while True:
            msg = consumer.poll(timeout=1.0)

            if msg is None:
                continue

            if msg.error():
                print(f"[{CONSUMER_ID}] Error Kafka: {msg.error()}, continuando...")
                time.sleep(2)
                continue

            payload = msg.value() or b"{}"
            query = json.loads(payload.decode("utf-8"))

            query_id   = query.get("id", "?")
            query_type = query.get("query_type", "q1")
            cache_key  = query.get("cache_key")
            start_time = time.time()

            cached = None
            try:
                cached = cache.get(cache_key)
            except Exception:
                pass

            if cached:
                stats["hits"] += 1
                latency = round((time.time() - start_time) * 1000, 2)
                publish_metric(producer, {
                    "event":       "processed",
                    "consumer":    CONSUMER_ID,
                    "query_id":    query_id,
                    "query_type":  query_type,
                    "cache_hit":   True,
                    "latency_ms":  latency,
                    "retry_count": query.get("retry_count", 0),
                    "timestamp":   time.time(),
                })
                stats["procesadas"] += 1
                continue

            stats["misses"] += 1
            result = call_response_generator(query)

            if result is None:
               
                query["retry_count"] = query.get("retry_count", 0) + 1

                if query["retry_count"] > MAX_RETRIES:
                   
                    stats["dlq"] += 1
                    producer.produce(
                        "queries-dlq",
                        value=json.dumps(query).encode("utf-8")
                    )
                    publish_metric(producer, {
                        "event":       "dlq",
                        "consumer":    CONSUMER_ID,
                        "query_id":    query_id,
                        "query_type":  query_type,
                        "retry_count": query["retry_count"],
                        "timestamp":   time.time(),
                    })
                    print(f"[{CONSUMER_ID}] DLQ: {query_id} tras {query['retry_count']} intentos")

                else:
                  
                    stats["reintentos"] += 1
                    producer.produce(
                        "queries-retry",
                        value=json.dumps(query).encode("utf-8")
                    )
                    publish_metric(producer, {
                        "event":       "retry",
                        "consumer":    CONSUMER_ID,
                        "query_id":    query_id,
                        "query_type":  query_type,
                        "retry_count": query["retry_count"],
                        "timestamp":   time.time(),
                    })
                    print(f"[{CONSUMER_ID}] Retry {query['retry_count']}/{MAX_RETRIES}: {query_id}")

                continue  
          
            ttl = TTL_CONFIG.get(query_type, 60)
            try:
                cache.setex(cache_key, ttl, json.dumps(result))
            except Exception:
                pass

            latency = round((time.time() - start_time) * 1000, 2)
            publish_metric(producer, {
                "event":       "processed",
                "consumer":    CONSUMER_ID,
                "query_id":    query_id,
                "query_type":  query_type,
                "cache_hit":   False,
                "latency_ms":  latency,
                "retry_count": query.get("retry_count", 0),
                "timestamp":   time.time(),
            })
            stats["procesadas"] += 1

            if stats["procesadas"] % 50 == 0:
                print(f"[{CONSUMER_ID}] stats={stats}")

    except KeyboardInterrupt:
        pass
    finally:
        consumer.close()
        print(f"[{CONSUMER_ID}] Consumer cerrado. stats finales={stats}")

if __name__ == "__main__":
    main()