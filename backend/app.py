"""
Prometheus Remote Write Backend - Test Script
=============================================

Questo script Flask serve per testare la connettività con Prometheus remote write.
È progettato per essere eseguito manualmente come script Python (non in container).

Configurazione:
- Si connette a InfluxDB su localhost:8086 (quando InfluxDB gira in docker-compose)
- Espone endpoint /receive per ricevere metriche da Prometheus
- Salva metriche di test in InfluxDB per verificare il flusso dati

Uso:
1. Avvia InfluxDB e Grafana: docker-compose up -d
2. Installa dipendenze: pip install -r requirements.txt  
3. Esegui questo script: python app.py
4. Configura Prometheus per remote write su http://localhost:5000/receive
5. Verifica i dati in Grafana (http://localhost:3000)

Endpoint disponibili:
- GET  /health     - Health check con stato InfluxDB
- POST /receive    - Riceve metriche da Prometheus remote write
- GET  /metrics    - Lista metriche salvate
- GET  /query      - Query metriche con filtri
- GET  /           - Info API
"""

from flask import Flask, request, jsonify
import logging
import json
from datetime import datetime
import os
import struct
import snappy
from influxdb_client import InfluxDBClient as InfluxDBClientV2, Point, WriteOptions
from influxdb_client.client.write_api import SYNCHRONOUS
import types_pb2  # Importa il nostro file generato

# Configurazione logging dettagliato per debugging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Configurazione InfluxDB per localhost (quando InfluxDB gira in docker-compose)
INFLUXDB_HOST = os.getenv('INFLUXDB_HOST', 'localhost')  # localhost per docker-compose
INFLUXDB_PORT = int(os.getenv('INFLUXDB_PORT', 8086))
INFLUXDB_DATABASE = os.getenv('INFLUXDB_DATABASE', 'prometheus_metrics')
INFLUXDB_USERNAME = os.getenv('INFLUXDB_USERNAME', 'admin')
INFLUXDB_PASSWORD = os.getenv('INFLUXDB_PASSWORD', 'adminpassword')
INFLUXDB_TOKEN = f"{INFLUXDB_USERNAME}:{INFLUXDB_PASSWORD}" # Token format for InfluxDB 1.8

# --- NEW CLIENT SETUP ---
# Client for InfluxDB 1.8+ with Flux
# The org parameter is required but not used for 1.8, so it can be anything.
influx_client_v2 = InfluxDBClientV2(
    url=f"http://{INFLUXDB_HOST}:{INFLUXDB_PORT}",
    token=INFLUXDB_TOKEN,
    org="prometheus" 
)

write_api = influx_client_v2.write_api(write_options=SYNCHRONOUS)
query_api = influx_client_v2.query_api()

@app.route('/health', methods=['GET'])
def health_check():
    """
    Health check endpoint per verificare la connettività con InfluxDB
    Utile per verificare che tutto sia configurato correttamente
    """
    try:
        # Test connessione InfluxDB
        if influx_client_v2.health().status == "pass":
             influx_status = "healthy"
             logger.info("Health check: InfluxDB v2 client connected successfully")
        else:
             influx_status = "unhealthy"
             logger.error("Health check: InfluxDB v2 client connection failed")
    except Exception as e:
        influx_status = f"error: {str(e)}"
        logger.error(f"Health check: Errore connessione InfluxDB - {str(e)}")
    
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'influxdb_status': influx_status,
        'influxdb_host': INFLUXDB_HOST,
        'influxdb_port': INFLUXDB_PORT,
        'influxdb_database': INFLUXDB_DATABASE,
        'message': 'Backend pronto per ricevere metriche da Prometheus'
    })

@app.route('/receive', methods=['POST'])
def receive_remote_write():
    """
    Endpoint principale per ricevere metriche da Prometheus remote write
    """
    try:
        # Decomprimi i dati se necessario (Prometheus usa Snappy via Content-Encoding)
        content_encoding = request.headers.get('Content-Encoding', '').lower()
        if 'snappy' in content_encoding:
            raw_data = snappy.uncompress(request.data)
        else:
            raw_data = request.data
        
        # Tenta di parsare, ma con un logging degli errori molto più dettagliato
        try:
            write_request = types_pb2.WriteRequest()
            write_request.ParseFromString(raw_data)
            
            # Se il parsing ha successo, procedi come prima
            influx_points = []
            for ts in write_request.timeseries:
                metric_name = ""
                labels = {}
                for label in ts.labels:
                    if label.name == "__name__":
                        metric_name = label.value
                    else:
                        labels[label.name] = label.value
                
                for sample in ts.samples:
                    point = Point(metric_name) \
                        .tag_from_dictionary(labels) \
                        .field("value", sample.value) \
                        .time(datetime.fromtimestamp(sample.timestamp / 1000.0))
                    influx_points.append(point)

            if influx_points:
                write_api.write(
                    bucket=f"{INFLUXDB_DATABASE}/autogen", 
                    org='-', # Not used in 1.8
                    record=influx_points
                )
            
            return jsonify({'status': 'success', 'metrics_received': len(influx_points)}), 200

        except Exception as e:
            # Errore nel parsing: log dettagliato e salvataggio del payload
            logger.error(f"DETAILED PARSE ERROR: {e}", exc_info=True)
            
            # Salva il payload grezzo in un file per l'analisi
            payload_filename = f"payload_error_{datetime.now().strftime('%Y%m%d_%H%M%S')}.bin"
            with open(payload_filename, "wb") as f:
                f.write(raw_data)
            logger.info(f"Payload grezzo salvato in: {payload_filename}")

            # Rispondi con un errore 500
            return jsonify({
                'status': 'error', 
                'message': 'Failed to parse Protobuf message.',
                'error_details': str(e)
            }), 500
            
    except Exception as e:
        logger.error(f"ERRORE GENERICO nel processing: {str(e)}", exc_info=True)
        return jsonify({
            'status': 'error',
            'message': 'Generic error during request processing.'
        }), 500

@app.route('/api/v1/write', methods=['POST'])
def remote_write():
    """
    Endpoint legacy per compatibilità con alcune configurazioni Prometheus
    Reindirizza a /receive
    """
    logger.info("Chiamata endpoint legacy /api/v1/write, reindirizzamento a /receive")
    return receive_remote_write()

@app.route('/metrics', methods=['GET'])
def list_metrics():
    """
    Lista delle metriche di debug salvate in InfluxDB
    Utile per verificare che le metriche arrivino correttamente
    """
    try:
        # Query per ottenere le ultime metriche di debug
        query = f"SELECT * FROM prometheus_remote_write_debug ORDER BY time DESC LIMIT 100"
        result = query_api.query(query)
        
        metrics = []
        for point in result.get_points():
            metrics.append({
                'time': point['time'],
                'measurement': 'prometheus_remote_write_debug',
                'source': point.get('source', 'unknown'),
                'data_size': point.get('raw_data_size', 0),
                'compressed_size': point.get('compressed_data_size', 0),
                'content_type': point.get('content_type', 'unknown')
            })
        
        return jsonify({
            'status': 'success',
            'count': len(metrics),
            'metrics': metrics,
            'message': f'Trovate {len(metrics)} metriche di debug'
        }), 200
        
    except Exception as e:
        logger.error(f"Errore nel recupero metriche: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@app.route('/query', methods=['GET'])
def query_metrics():
    """
    Query delle metriche con filtri personalizzabili
    Utile per debugging e analisi
    """
    try:
        # Parametri di query
        limit = request.args.get('limit', '100')
        measurement = request.args.get('measurement', 'prometheus_remote_write_debug')
        
        query = f"SELECT * FROM {measurement} ORDER BY time DESC LIMIT {limit}"
        result = query_api.query(query)
        
        metrics = []
        for point in result.get_points():
            metrics.append({
                'time': point['time'],
                'measurement': measurement,
                'source': point.get('source', 'unknown'),
                'data_size': point.get('raw_data_size', 0),
                'compressed_size': point.get('compressed_data_size', 0)
            })
        
        return jsonify({
            'status': 'success',
            'result': metrics,
            'query': query,
            'count': len(metrics)
        }), 200
        
    except Exception as e:
        logger.error(f"Errore nella query: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

# --- Custom SYDA K8s Queries ---

def _flux_format_for_grafana(result, target_name):
    """
    Format Flux query result for Grafana SimpleJSON datasource (time series).
    """
    series = []
    for table in result:
        # Each table can be a different series in Grafana
        if not table.records:
            continue

        # Determine the target name for this series
        if target_name and target_name in table.records[0].values:
             target_label = table.records[0].values[target_name]
        else:
             # Fallback if target_name is not a tag, use measurement
             target_label = table.records[0].get_measurement()

        datapoints = []
        for record in table.records:
            # Grafana expects [value, timestamp_ms]
            value = record.get_value()
            time = record.get_time()
            if value is not None and time is not None:
                timestamp_ms = int(time.timestamp() * 1000)
                datapoints.append([value, timestamp_ms])
        
        if datapoints:
            series.append({
                "target": target_label,
                "datapoints": datapoints
            })
    return series

@app.route('/query/arrivals', methods=['GET'])
def query_arrivals():
    """
    Calculates arrival rate based on istio_requests_total using Flux.
    """
    deployment_name = request.args.get('deployment', '.*')
    namespace = request.args.get('namespace', 'default')
    window = request.args.get('window', '1m')
    group_interval = request.args.get('interval', '10s')

    flux_query = f"""
        from(bucket: "{INFLUXDB_DATABASE}/autogen")
          |> range(start: -{window})
          |> filter(fn: (r) => r._measurement == "istio_requests_total")
          |> filter(fn: (r) => r.destination_workload_namespace == "{namespace}")
          |> filter(fn: (r) => r.reporter == "destination")
          |> filter(fn: (r) => r.destination_workload =~ /^{deployment_name}/)
          |> derivative(unit: 1s, nonNegative: true)
          |> aggregateWindow(every: {group_interval}, fn: sum, createEmpty: false)
          |> yield(name: "sum")
    """
    
    try:
        logger.info(f"Executing Flux arrivals query: {flux_query.strip()}")
        result = query_api.query(flux_query)
        grafana_data = _flux_format_for_grafana(result, None)
        return jsonify(grafana_data)
    except Exception as e:
        logger.error(f"Error executing arrivals query: {e}", exc_info=True)
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/query/completions', methods=['GET'])
def query_completions():
    """
    Calculates completion rate based on istio_requests_total for a given response_code using Flux.
    """
    deployment_name = request.args.get('deployment', '.*')
    namespace = request.args.get('namespace', 'default')
    window = request.args.get('window', '1m')
    group_interval = request.args.get('interval', '10s')
    response_code = request.args.get('response_code', '200')

    flux_query = f"""
        from(bucket: "{INFLUXDB_DATABASE}/autogen")
          |> range(start: -{window})
          |> filter(fn: (r) => r._measurement == "istio_requests_total")
          |> filter(fn: (r) => r.destination_workload_namespace == "{namespace}")
          |> filter(fn: (r) => r.reporter == "destination")
          |> filter(fn: (r) => r.response_code == "{response_code}")
          |> filter(fn: (r) => r.destination_workload =~ /^{deployment_name}/)
          |> derivative(unit: 1s, nonNegative: true)
          |> aggregateWindow(every: {group_interval}, fn: sum, createEmpty: false)
          |> yield(name: "sum")
    """

    try:
        logger.info(f"Executing Flux completions query: {flux_query.strip()}")
        result = query_api.query(flux_query)
        grafana_data = _flux_format_for_grafana(result, None)
        return jsonify(grafana_data)
    except Exception as e:
        logger.error(f"Error executing completions query: {e}", exc_info=True)
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/query/response_time', methods=['GET'])
def query_response_time():
    """
    Calculates response time using Flux.
    """
    deployment_name = request.args.get('deployment', '.*')
    namespace = request.args.get('namespace', 'default')
    window = request.args.get('window', '1m')
    group_interval = request.args.get('interval', '10s')

    flux_query = f"""
        sum_data = from(bucket: "{INFLUXDB_DATABASE}/autogen")
          |> range(start: -{window})
          |> filter(fn: (r) => r._measurement == "istio_request_duration_milliseconds_sum")
          |> filter(fn: (r) => r.destination_workload_namespace == "{namespace}")
          |> filter(fn: (r) => r.destination_workload =~ /^{deployment_name}/)
          |> derivative(unit: 1s, nonNegative: true)
          |> aggregateWindow(every: {group_interval}, fn: sum)
          
        count_data = from(bucket: "{INFLUXDB_DATABASE}/autogen")
          |> range(start: -{window})
          |> filter(fn: (r) => r._measurement == "istio_request_duration_milliseconds_count")
          |> filter(fn: (r) => r.destination_workload_namespace == "{namespace}")
          |> filter(fn: (r) => r.destination_workload =~ /^{deployment_name}/)
          |> derivative(unit: 1s, nonNegative: true)
          |> aggregateWindow(every: {group_interval}, fn: sum)

        join(tables: {{sum: sum_data, count: count_data}}, on: ["_time", "_start", "_stop"])
          |> map(fn: (r) => ({{
              _time: r._time,
              _value: if r._value_count > 0.0 then r._value_sum / r._value_count / 1000.0 else 0.0
          }}))
          |> yield(name: "response_time")
    """

    try:
        logger.info(f"Executing Flux response_time query: {flux_query.strip()}")
        result = query_api.query(flux_query)
        grafana_data = _flux_format_for_grafana(result, None)
        return jsonify(grafana_data)

    except Exception as e:
        logger.error(f"Error executing response_time query: {e}", exc_info=True)
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/query/cpu_usage', methods=['GET'])
def query_cpu_usage():
    """
    Calculates CPU usage rate per pod using Flux.
    """
    deployment_name = request.args.get('deployment', '.*')
    namespace = request.args.get('namespace', 'default')
    window = request.args.get('window', '1m')
    group_interval = request.args.get('interval', '10s')

    flux_query = f"""
        from(bucket: "{INFLUXDB_DATABASE}/autogen")
          |> range(start: -{window})
          |> filter(fn: (r) => r._measurement == "container_cpu_usage_seconds_total")
          |> filter(fn: (r) => r.namespace == "{namespace}")
          |> filter(fn: (r) => r.pod =~ /^{deployment_name}/)
          |> filter(fn: (r) => r.container != "POD" and r.container != "")
          |> derivative(unit: 1s, nonNegative: true)
          |> group(columns: ["pod", "_time"])
          |> sum()
          |> aggregateWindow(every: {group_interval}, fn: mean, createEmpty: false)
          |> yield(name: "cpu_usage")
    """
    
    try:
        logger.info(f"Executing Flux cpu_usage query: {flux_query.strip()}")
        result = query_api.query(flux_query)
        # Group results by pod name for the target label
        grafana_data = _flux_format_for_grafana(result, 'pod')
        return jsonify(grafana_data)
    except Exception as e:
        logger.error(f"Error executing cpu_usage query: {e}", exc_info=True)
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/query/replicas', methods=['GET'])
def query_replicas():
    """
    Counts the number of active pods (replicas) using Flux.
    """
    deployment_name = request.args.get('deployment', '.*')
    namespace = request.args.get('namespace', 'default')
    window = request.args.get('window', '1m')
    group_interval = request.args.get('interval', '10s')

    flux_query = f"""
        from(bucket: "{INFLUXDB_DATABASE}/autogen")
          |> range(start: -{window})
          |> filter(fn: (r) => r._measurement == "container_cpu_usage_seconds_total")
          |> filter(fn: (r) => r.namespace == "{namespace}")
          |> filter(fn: (r) => r.pod =~ /^{deployment_name}/)
          |> filter(fn: (r) => r.container != "POD" and r.container != "")
          |> group(columns: ["pod"])
          |> distinct(column: "pod")
          |> aggregateWindow(every: {group_interval}, fn: count, createEmpty: false)
          |> yield(name: "replicas")
    """
    
    try:
        logger.info(f"Executing Flux replicas query: {flux_query.strip()}")
        result = query_api.query(flux_query)
        grafana_data = _flux_format_for_grafana(result, None)
        return jsonify(grafana_data)
    except Exception as e:
        logger.error(f"Error executing replicas query: {e}", exc_info=True)
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/', methods=['GET'])
def index():
    """
    Pagina principale con informazioni sull'API e istruzioni per il testing
    """
    return jsonify({
        'service': 'Prometheus Remote Write Backend - Test Script',
        'version': '1.0.0',
        'database': 'InfluxDB 1.8',
        'mode': 'manual_testing',
        'endpoints': {
            'health': '/health - Verifica connettività InfluxDB',
            'remote_write': '/receive - Endpoint per Prometheus remote write',
            'legacy': '/api/v1/write - Endpoint legacy',
            'list_metrics': '/metrics - Lista metriche di debug',
            'query': '/query - Query personalizzate'
        },
        'status': 'running',
        'influxdb_config': {
            'host': INFLUXDB_HOST,
            'port': INFLUXDB_PORT,
            'database': INFLUXDB_DATABASE
        },
        'instructions': {
            'setup': '1. Avvia InfluxDB: docker-compose up -d',
            'test': '2. Testa connettività: curl http://localhost:5100/health',
            'prometheus': '3. Configura Prometheus remote write su http://localhost:5100/receive',
            'monitor': '4. Monitora metriche: curl http://localhost:5100/metrics',
            'grafana': '5. Visualizza in Grafana: http://localhost:3000'
        }
    })

if __name__ == '__main__':
    port = int(os.environ.get('FLASK_PORT', 5000))
    host = os.environ.get('FLASK_HOST', '0.0.0.0')
    debug = os.environ.get('FLASK_DEBUG', 'True').lower() == 'true'  # Debug attivo per testing
    
    print("=" * 60)
    print("PROMETHEUS REMOTE WRITE BACKEND - TEST SCRIPT")
    print("=" * 60)
    print(f"InfluxDB: {INFLUXDB_HOST}:{INFLUXDB_PORT}")
    print(f"Database: {INFLUXDB_DATABASE}")
    print(f"Backend: http://{host}:{port}")
    print(f"Debug mode: {debug}")
    print("=" * 60)
    print("Endpoint principale per Prometheus: http://localhost:5100/receive")
    print("Health check: http://localhost:5100/health")
    print("=" * 60)
    
    app.run(host=host, port=port, debug=debug) 