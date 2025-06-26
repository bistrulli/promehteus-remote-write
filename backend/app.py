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
from influxdb import InfluxDBClient
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

# Client InfluxDB
influx_client = InfluxDBClient(
    host=INFLUXDB_HOST,
    port=INFLUXDB_PORT,
    username=INFLUXDB_USERNAME,
    password=INFLUXDB_PASSWORD,
    database=INFLUXDB_DATABASE
)

@app.route('/health', methods=['GET'])
def health_check():
    """
    Health check endpoint per verificare la connettività con InfluxDB
    Utile per verificare che tutto sia configurato correttamente
    """
    try:
        # Test connessione InfluxDB
        influx_client.ping()
        influx_status = "healthy"
        logger.info("Health check: InfluxDB connesso correttamente")
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
        # Decomprimi i dati se necessario (Prometheus usa Snappy)
        if 'snappy' in request.content_type.lower():
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
                    point = {
                        "measurement": metric_name,
                        "tags": labels,
                        "fields": {"value": sample.value},
                        "time": datetime.fromtimestamp(sample.timestamp / 1000.0)
                    }
                    influx_points.append(point)

            if influx_points:
                influx_client.write_points(influx_points)
            
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
        result = influx_client.query(query)
        
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
        result = influx_client.query(query)
        
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