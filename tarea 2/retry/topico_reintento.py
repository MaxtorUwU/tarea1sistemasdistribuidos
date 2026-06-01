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
MAX_RETRIES            = int(os.getenv("MAX_RETRIES", "3"))


RETRY_BASE_DELAY = int(os.getenv("RETRY_BASE_DELAY", "2"))

TTL_CONFIG = {
    "q1": int(os.getenv("TTL_Q1", "60")),
    "q2": int(os.getenv("TTL_Q2", "120")),
    "q3": int(os.getenv("TTL_Q3", "180")),
    "q4": int(os.getenv("TTL_Q4", "300")),
    "q5": int(os.getenv("TTL_Q5", "60")),
}

def wait_for_redis():
    print("[retry] Esperando a Redis...")
    while True:
        try:  
            r = redis.Redis(host=REDIS_HOST, port=6379, decode_responses=True)
            r.ping()  
            print("[retry] Redis listo.")
            return r
        except Exception:
            time.sleep(2)

def wait_for_kafka():
    print("[retry] Esperando a Kafka...")
    while True:
        try:
            p = Producer({"bootstrap.servers": KAFKA_BROKER})
            p.flush(timeout=3)
            print("[retry] Kafka listo.")
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

    consumer = Consumer({
        "bootstrap.servers":  KAFKA_BROKER,
        "group.id":           "retry-consumers",
        "auto.offset.reset":  "earliest",
        "enable.auto.commit": True,
    })
    
    consumer.subscribe(["queries-retry"])

    producer = Producer({
        "bootstrap.servers": KAFKA_BROKER,
        "acks":              "all",  
    })

    stats = {
        "procesados":  0,  
        "recuperados": 0,  
        "dlq":         0,  
        "reencolados": 0,  
    }

    print(f"[retry] Escuchando tópico 'queries-retry' | MAX_RETRIES={MAX_RETRIES} | base_delay={RETRY_BASE_DELAY}s")

    try:
        while True:
            msg = consumer.poll(timeout=1.0)

            if msg is None:
                continue

            if msg.error():
                print(f"[retry] Error Kafka: {msg.error()}, continuando...")
                time.sleep(2)
                continue


            payload = msg.value() or b"{}"
            query = json.loads(payload.decode("utf-8"))
            query_id    = query.get("id", "?")
            query_type  = query.get("query_type", "q1")
            cache_key   = query.get("cache_key")
            retry_count = query.get("retry_count", 1)

          
            delay = min(RETRY_BASE_DELAY * (2 ** (retry_count - 1)), 10)
            print(f"[retry] Esperando {delay}s antes de reintentar {query_id} (intento {retry_count})")
            time.sleep(delay)

         
            cached = None
            try:
                cached = cache.get(cache_key)
            except Exception:
                pass  

            if cached:
               
                stats["recuperados"] += 1
                stats["procesados"]  += 1

                publish_metric(producer, {
                    "event":       "recovered",   
                    "query_id":    query_id,
                    "query_type":  query_type,
                    "retry_count": retry_count,
                    "cache_hit":   True,           
                    "timestamp":   time.time(),
                })
                print(f"[retry] Recuperado desde caché: {query_id}")
                continue  
            
            result = call_response_generator(query)

            if result:
               
                ttl = TTL_CONFIG.get(query_type, 60)
                try:
                   
                    cache.setex(cache_key, ttl, json.dumps(result))
                except Exception:
                    pass  

                stats["recuperados"] += 1
                stats["procesados"]  += 1

                publish_metric(producer, {
                    "event":       "recovered",   
                    "query_id":    query_id,
                    "query_type":  query_type,
                    "retry_count": retry_count,
                    "cache_hit":   False,          
                    "timestamp":   time.time(),
                })
                print(f"[retry] Recuperado: {query_id} (intento {retry_count})")

            else:
               
                query["retry_count"] = retry_count + 1

                if query["retry_count"] > MAX_RETRIES:
                   
                    stats["dlq"] += 1

                    producer.produce(
                        "queries-dlq",
                        value=json.dumps(query).encode("utf-8")
                    )
                    publish_metric(producer, {
                        "event":       "dlq",        
                        "query_id":    query_id,
                        "query_type":  query_type,
                        "retry_count": query["retry_count"],
                        "timestamp":   time.time(),
                    })
                    print(f"[retry] DLQ: {query_id} (superó {MAX_RETRIES} reintentos)")

                else:
                   
                    stats["reencolados"] += 1

                    producer.produce(
                        "queries-retry",
                        value=json.dumps(query).encode("utf-8")
                    )
                    publish_metric(producer, {
                        "event":       "retry",      
                        "query_id":    query_id,
                        "query_type":  query_type,
                        "retry_count": query["retry_count"],
                        "timestamp":   time.time(),
                    })
                    print(f"[retry] Re-encolado: {query_id} (próximo intento {query['retry_count']})")

       
            if (stats["procesados"] + stats["dlq"]) % 20 == 0 and \
               (stats["procesados"] + stats["dlq"]) > 0:
                print(f"[retry] stats={stats}")

    except KeyboardInterrupt:
        pass
    finally:
        consumer.close()
        print(f"[retry] Consumer cerrado. stats finales={stats}")

if __name__ == "__main__":
    main()