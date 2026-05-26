import os
import json
import time
import csv
import datetime
import threading
from kafka import KafkaAdminClient, KafkaConsumer

KAFKA_HOST = os.environ.get('KAFKA_HOST', 'kafka_broker:9092')
GROUP_ID = os.environ.get('KAFKA_GROUP_ID', 'grupo_consultas')
TOPIC_PRINCIPAL = 'consultas_principal'
TOPIC_RETRY = 'consultas_retry'
TOPIC_DLQ = 'consultas_dlq'

counts = {
    "principal": 0,
    "retry": 0,
    "dlq": 0
}
lock = threading.Lock()

def listen_topics():
    try:
        consumer = KafkaConsumer(
            TOPIC_PRINCIPAL,
            TOPIC_RETRY,
            TOPIC_DLQ,
            bootstrap_servers=[KAFKA_HOST],
            group_id='grupo_colector_metricas',
            auto_offset_reset='latest',
            enable_auto_commit=True,
            value_deserializer=lambda x: json.loads(x.decode('utf-8'))
        )
        for message in consumer:
            topic = message.topic
            with lock:
                if topic == TOPIC_PRINCIPAL:
                    counts["principal"] += 1
                elif topic == TOPIC_RETRY:
                    counts["retry"] += 1
                elif topic == TOPIC_DLQ:
                    counts["dlq"] += 1
    except Exception:
        pass

def collect_metrics(window_seconds=5):
    try:
        admin = KafkaAdminClient(bootstrap_servers=[KAFKA_HOST])
        consumer = KafkaConsumer(bootstrap_servers=[KAFKA_HOST])
    except Exception:
        admin = None
        consumer = None

    file_exists = os.path.isfile("system_metrics.csv")
    with open("system_metrics.csv", mode='a', newline='') as file:
        writer = csv.writer(file)
        if not file_exists:
            writer.writerow(['timestamp', 'throughput_msg_s', 'backlog_lag', 'recovered_retry_count', 'dlq_count'])

    while True:
        time.sleep(window_seconds)
        ahora = datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S.%f")
        
        with lock:
            current_principal = counts["principal"]
            current_retry = counts["retry"]
            current_dlq = counts["dlq"]
            counts["principal"] = 0
            counts["retry"] = 0
            counts["dlq"] = 0

        throughput = current_principal / window_seconds
        lag = 0

        if admin and consumer:
            try:
                group_offsets = admin.list_consumer_group_offsets(GROUP_ID)
                partitions = list(group_offsets.keys())
                if partitions:
                    end_offsets = consumer.end_offsets(partitions)
                    for tp in partitions:
                        current_offset = group_offsets[tp].offset
                        if current_offset is not None:
                            end_offset = end_offsets.get(tp, current_offset)
                            lag += max(0, end_offset - current_offset)
            except Exception:
                lag = -1
        else:
            lag = -1

        with open("system_metrics.csv", mode='a', newline='') as file:
            writer = csv.writer(file)
            writer.writerow([ahora, throughput, lag, current_retry, current_dlq])

if __name__ == "__main__":
    t = threading.Thread(target=listen_topics, daemon=True)
    t.start()
    collect_metrics()