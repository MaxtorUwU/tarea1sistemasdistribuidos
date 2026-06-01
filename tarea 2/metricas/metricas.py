import os
import time
import json
import threading
from collections import defaultdict, deque
from http.server import HTTPServer, BaseHTTPRequestHandler
from confluent_kafka import Consumer, KafkaException

KAFKA_BROKER = os.getenv("KAFKA_BROKER", "localhost:9092")
REDIS_HOST   = os.getenv("REDIS_HOST",   "redis-cache")
PORT         = int(os.getenv("PORT", "8080"))

metrics = {
    "processed":  0,    
    "cache_hits": 0,    
    "cache_misses": 0,  
    "retried":    0,   
    "recovered":  0,    
    "dlq":        0,    
    "backlog_size":  0,     
    "recovery_time": 0.0,   
    "falla_start_time": None, 
    "latencies": deque(maxlen=10000),
    "throughput_window": deque(maxlen=60),
    "query_counts": defaultdict(int),
    "start_time": time.time(),
}

lock = threading.Lock()

def percentile(data, p):
    if not data:
        return 0
    sorted_data = sorted(data)
    idx = int(len(sorted_data) * p / 100)
    return round(sorted_data[min(idx, len(sorted_data) - 1)], 2)

def consume_metrics():
    while True:
        try:
            consumer = Consumer({
                "bootstrap.servers":  KAFKA_BROKER,
                "group.id":           "metrics-aggregator",
                "auto.offset.reset":  "earliest",
                "enable.auto.commit": True,
            })
            consumer.subscribe(["metrics"])
            print("[metrics] Consumiendo tópico 'metrics'...")

            while True:
                msg = consumer.poll(timeout=1.0)
                if msg is None:
                    continue
                if msg.error():
                    raise KafkaException(msg.error())

                raw_value = msg.value()
                if raw_value is not None:
                    try:
                        evt = json.loads(raw_value.decode("utf-8"))
                
                        with lock:
                            event_type = evt.get("event")

                            if event_type == "processed":
                                metrics["processed"] += 1
                                if evt.get("cache_hit"):
                                    metrics["cache_hits"] += 1
                                else:
                                    metrics["cache_misses"] += 1

                                lat = evt.get("latency_ms", 0)
                                metrics["latencies"].append(lat)
                                metrics["query_counts"][evt.get("query_type", "?")] += 1

                            elif event_type == "retry":
                                metrics["retried"] += 1
                                
                                if metrics["backlog_size"] == 0 and metrics["falla_start_time"] is None:
                                    metrics["falla_start_time"] = time.time()
                                
                                metrics["backlog_size"] += 1

                            elif event_type == "recovered":
                                metrics["recovered"] += 1
                                if metrics["backlog_size"] > 0:
                                    metrics["backlog_size"] -= 1
                                
                                if metrics["backlog_size"] == 0 and metrics["falla_start_time"] is not None:
                                    metrics["recovery_time"] = round(time.time() - metrics["falla_start_time"], 2)
                                    metrics["falla_start_time"] = None 

                            elif event_type == "dlq":
                                metrics["dlq"] += 1
                                if metrics["backlog_size"] > 0:
                                    metrics["backlog_size"] -= 1
                                
                                if metrics["backlog_size"] == 0 and metrics["falla_start_time"] is not None:
                                    metrics["recovery_time"] = round(time.time() - metrics["falla_start_time"], 2)
                                    metrics["falla_start_time"] = None

                    except Exception as e:
                        print(f"Error al decodificar o procesar el JSON: {e}")

        except Exception as e:
            print(f"[metrics] Error en consumer: {e}, reconectando en 5s...")
            time.sleep(5)

def throughput_tracker():
    last_processed = 0
    while True:
        time.sleep(1)
        with lock:
            current = metrics["processed"]
            tps = current - last_processed
            last_processed = current
            metrics["throughput_window"].append(tps)

class MetricsHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass

    def do_GET(self):
        if self.path == "/health":
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b'{"status": "ok"}')
            return

        if self.path == "/metrics":
            with lock:
                lats    = list(metrics["latencies"])
                tps     = list(metrics["throughput_window"])
                elapsed = time.time() - metrics["start_time"]
                total   = metrics["processed"]

                throughput_avg = round(total / max(elapsed, 1), 2)
                last_10 = tps[-10:] if tps else []
                throughput_10s = round(sum(last_10) / max(len(last_10), 1), 2)
                hit_rate = round(metrics["cache_hits"] / max(total, 1) * 100, 1)

                total_intentos = total + metrics["retried"]
                retry_rate = round(metrics["retried"] / max(total_intentos, 1) * 100, 2)
                recovery_rate = round(metrics["recovered"] / max(metrics["retried"], 1) * 100, 2)
                dlq_rate = round(metrics["dlq"] / max(metrics["retried"], 1) * 100, 2)

                current_rec_time = metrics["recovery_time"]
                if metrics["backlog_size"] > 0 and metrics["falla_start_time"] is not None:
                    current_rec_time = round(time.time() - metrics["falla_start_time"], 2)

                snapshot = {
                    "uptime_seconds":      round(elapsed, 1),
                    "total_processed":     total,
                    "throughput_avg":      throughput_avg,
                    "throughput_last_10s": throughput_10s,
                    "throughput_history":  tps,
                    "cache_hits":          metrics["cache_hits"],
                    "cache_misses":        metrics["cache_misses"],
                    "cache_hit_rate":      hit_rate,
                    "retried":             metrics["retried"],
                    "recovered":           metrics["recovered"],
                    "dlq":                 metrics["dlq"],
                    "retry_rate":          retry_rate,
                    "recovery_rate":       recovery_rate,
                    "dlq_rate":            dlq_rate,
                    "backlog_size":        metrics["backlog_size"],
                    "recovery_time_sec":   current_rec_time,
                    "latency_p50":         percentile(lats, 50),
                    "latency_p95":         percentile(lats, 95),
                    "latency_p99":         percentile(lats, 99),
                    "query_distribution":  dict(metrics["query_counts"]),
                }

            body = json.dumps(snapshot, indent=2).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(body)
            return

        if self.path in ("/", "/dashboard"):
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(DASHBOARD_HTML.encode("utf-8"))
            return

DASHBOARD_HTML = """<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>Kafka Metrics Dashboard</title>
  <style>
    body { font-family: monospace; background: #0d1117; color: #c9d1d9; padding: 24px; margin: 0; }
    h1 { color: #58a6ff; margin: 0 0 4px; }
    p  { color: #8b949e; margin: 0 0 16px; font-size: 13px; }
    .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(190px, 1fr)); gap: 12px; margin-bottom: 20px; }
    .card { background: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 16px; }
    .label { font-size: 11px; color: #8b949e; margin-bottom: 6px; text-transform: uppercase; }
    .value { font-size: 26px; font-weight: 700; color: #58a6ff; }
    .green  { color: #3fb950; }
    .yellow { color: #d29922; }
    .red    { color: #f85149; }
    .bar-wrap { background: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 16px; margin-bottom: 16px; }
    .bar-title { font-size: 11px; color: #8b949e; margin-bottom: 10px; text-transform: uppercase; }
    .bar-row   { display: flex; align-items: center; margin-bottom: 6px; font-size: 12px; }
    .bar-label { width: 30px; color: #8b949e; }
    .bar-bg    { flex: 1; background: #21262d; border-radius: 3px; height: 14px; margin: 0 10px; }
    .bar-fill  { height: 100%; border-radius: 3px; background: #58a6ff; transition: width 0.4s; }
    .bar-val   { width: 80px; text-align: right; color: #c9d1d9; }
  </style>
</head>
<body>
  <h1>⚡ Kafka Metrics Dashboard</h1>
  <p id="ts">Cargando...</p>
  <div class="grid" id="cards"></div>
  <div class="bar-wrap">
    <div class="bar-title">Distribución de Queries</div>
    <div id="dist"></div>
  </div>

  <script>
    async function refresh() {
      try {
        const r = await fetch('/metrics');
        const d = await r.json();

        document.getElementById('ts').textContent =
          'Actualizado: ' + new Date().toLocaleTimeString() +
          ' | Uptime: ' + d.uptime_seconds + 's';

        const cards = [
          { l: 'Procesadas',          v: d.total_processed,     c: 'green'  },
          { l: 'Throughput avg (QPS)', v: d.throughput_avg,      c: ''       },
          { l: 'Throughput 10s (QPS)', v: d.throughput_last_10s, c: ''       },
          { l: 'Cache Hit Rate',       v: d.cache_hit_rate + '%', c: d.cache_hit_rate > 50 ? 'green' : 'yellow' },
          { l: 'Backlog Size (Kafka)', v: d.backlog_size,        c: d.backlog_size > 0 ? 'red' : 'green' },
          { l: 'Recovery Time (s)',    v: d.recovery_time_sec + 's', c: d.backlog_size > 0 ? 'yellow' : 'green' },
          { l: 'Latencia p50 (ms)',    v: d.latency_p50,         c: ''       },
          { l: 'Latencia p95 (ms)',    v: d.latency_p95,          c: d.latency_p95 > 500 ? 'red' : 'yellow' },
          { l: 'Reintentos',           v: d.retried,             c: d.retried > 0 ? 'yellow' : 'green' },
          { l: 'Retry Rate',           v: d.retry_rate + '%',     c: d.retry_rate > 10 ? 'red' : 'yellow' },
          { l: 'Recuperadas',          v: d.recovered,           c: 'green'  },
          { l: 'DLQ',                  v: d.dlq,                 c: d.dlq > 0 ? 'red' : 'green' },
        ];

        document.getElementById('cards').innerHTML = cards.map(c =>
          '<div class="card">' +
            '<div class="label">' + c.l + '</div>' +
            '<div class="value ' + c.c + '">' + c.v + '</div>' +
          '</div>'
        ).join('');

        const dist  = d.query_distribution;
        const total = Object.values(dist).reduce((a, b) => a + b, 0) || 1;
        document.getElementById('dist').innerHTML = Object.entries(dist)
          .sort()
          .map(([k, v]) => {
            const pct = Math.round(v / total * 100);
            return '<div class="bar-row">' +
              '<span class="bar-label">' + k + '</span>' +
              '<div class="bar-bg">' +
                '<div class="bar-fill" style="width:' + pct + '%"></div>' +
              '</div>' +
              '<span class="bar-val">' + v + ' (' + pct + '%)</span>' +
            '</div>';
          }).join('');

      } catch(e) {
        document.getElementById('ts').textContent = 'Error conectando al servidor...';
      }
    }

    refresh();
    setInterval(refresh, 3000);
  </script>
</body>
</html>"""

def main():
    t1 = threading.Thread(target=consume_metrics, daemon=True)
    t1.start()
    print("[metrics] Thread de Kafka iniciado.")
    t2 = threading.Thread(target=throughput_tracker, daemon=True)
    t2.start()
    print("[metrics] Thread de throughput iniciado.")
    print(f"[metrics] Servidor HTTP en puerto {PORT}")
    print(f"[metrics] Dashboard → http://localhost:{PORT}/dashboard")
    print(f"[metrics] Métricas  → http://localhost:{PORT}/metrics")

    server = HTTPServer(("0.0.0.0", PORT), MetricsHandler)
    server.serve_forever()

if __name__ == "__main__":
    main()