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
from google.protobuf import text_format
import prometheus_remote_write_pb2

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
    Questo è l'endpoint che Prometheus chiamerà per inviare le metriche
    
    Prometheus configurato per remote write punterà a:
    http://localhost:5100/receive
    
    Il payload è tipicamente compresso con Snappy e contiene protobuf
    """
    try:
        logger.info(f"=== RICEVUTA RICHIESTA REMOTE WRITE ===")
        logger.info(f"Client IP: {request.remote_addr}")
        logger.info(f"Content-Type: {request.content_type}")
        logger.info(f"Content-Length: {len(request.data)} bytes")
        logger.info(f"Headers: {dict(request.headers)}")
        
        # Decomprimi i dati se necessario (Prometheus usa Snappy)
        if 'snappy' in request.content_type.lower():
            raw_data = snappy.uncompress(request.data)
            logger.info(f"Dati decompressi con Snappy: {len(raw_data)} bytes")
        else:
            raw_data = request.data
            logger.info(f"Dati grezzi (non compressi): {len(raw_data)} bytes")
        
        # Parsa le metriche Prometheus dal protobuf
        try:
            write_request = prometheus_remote_write_pb2.WriteRequest()
            write_request.ParseFromString(raw_data)
            
            logger.info(f"Parsed {len(write_request.timeseries)} timeseries from Prometheus")
            
            # Converti le metriche in punti InfluxDB
            influx_points = []
            
            for timeseries in write_request.timeseries:
                # Estrai il nome della metrica dalle labels
                metric_name = None
                labels_dict = {}
                
                for label in timeseries.labels:
                    labels_dict[label.name] = label.value
                    if label.name == '__name__':
                        metric_name = label.value
                
                if not metric_name:
                    logger.warning("Timeseries without __name__ label, skipping")
                    continue
                
                # Processa ogni sample nella timeseries
                for sample in timeseries.samples:
                    # Converti timestamp da millisecondi a secondi se necessario
                    timestamp = sample.timestamp
                    if timestamp > 1e10:  # Se è in millisecondi
                        timestamp = timestamp / 1000
                    
                    # Crea il punto InfluxDB
                    point = {
                        "measurement": metric_name,
                        "tags": labels_dict,
                        "fields": {
                            "value": sample.value
                        },
                        "time": datetime.fromtimestamp(timestamp)
                    }
                    
                    influx_points.append(point)
            
            # Scrivi tutti i punti in InfluxDB
            if influx_points:
                influx_client.write_points(influx_points)
                logger.info(f"Salvate {len(influx_points)} metriche in InfluxDB")
                
                # Log delle prime metriche per debugging
                for i, point in enumerate(influx_points[:3]):  # Solo le prime 3
                    logger.info(f"Metrica {i+1}: {point['measurement']} = {point['fields']['value']} (tags: {point['tags']})")
                
            else:
                logger.warning("Nessuna metrica valida trovata nel payload")
                
        except Exception as parse_error:
            logger.error(f"Errore nel parsing delle metriche Prometheus: {str(parse_error)}")
            # Fallback: salva metriche di debug come prima
            point = {
                "measurement": "prometheus_remote_write_debug",
                "tags": {
                    "source": request.remote_addr,
                    "content_type": request.content_type,
                    "endpoint": "/receive",
                    "compressed": "snappy" if 'snappy' in request.content_type.lower() else "none",
                    "parse_error": str(parse_error)
                },
                "fields": {
                    "raw_data_size": len(raw_data),
                    "compressed_data_size": len(request.data),
                    "timestamp": datetime.utcnow().timestamp(),
                    "request_count": 1
                },
                "time": datetime.utcnow()
            }
            influx_client.write_points([point])
        
        logger.info("=== FINE RICHIESTA REMOTE WRITE ===")
        
        return jsonify({
            'status': 'success',
            'message': 'Metriche ricevute e salvate in InfluxDB',
            'timestamp': datetime.now().isoformat(),
            'data_size': len(raw_data),
            'compressed_size': len(request.data),
            'timeseries_count': len(write_request.timeseries) if 'write_request' in locals() else 0,
            'metrics_saved': len(influx_points) if 'influx_points' in locals() else 0
        }), 200
        
    except Exception as e:
        logger.error(f"ERRORE durante il processing della metrica: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': str(e),
            'timestamp': datetime.now().isoformat()
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

@app.route('/prometheus-metrics', methods=['GET'])
def list_prometheus_metrics():
    """
    Lista delle metriche Prometheus reali salvate in InfluxDB
    Utile per verificare che le metriche reali arrivino correttamente
    """
    try:
        # Parametri di query
        limit = request.args.get('limit', '100')
        measurement = request.args.get('measurement', 'istio_requests_total')
        
        # Query per ottenere le ultime metriche Prometheus
        query = f"SELECT * FROM {measurement} ORDER BY time DESC LIMIT {limit}"
        result = influx_client.query(query)
        
        metrics = []
        for point in result.get_points():
            metrics.append({
                'time': point['time'],
                'measurement': measurement,
                'value': point.get('value', 0),
                'tags': {k: v for k, v in point.items() if k not in ['time', 'value']}
            })
        
        return jsonify({
            'status': 'success',
            'count': len(metrics),
            'measurement': measurement,
            'metrics': metrics,
            'message': f'Trovate {len(metrics)} metriche per {measurement}'
        }), 200
        
    except Exception as e:
        logger.error(f"Errore nel recupero metriche Prometheus: {str(e)}")
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
            'query': '/query - Query personalizzate',
            'prometheus_metrics': '/prometheus-metrics - Lista metriche Prometheus reali'
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
            'prometheus_metrics': '5. Visualizza metriche Prometheus: curl http://localhost:5100/prometheus-metrics',
            'grafana': '6. Visualizza in Grafana: http://localhost:3000'
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
    print("Endpoint principale per Prometheus: http://localhost:5001/receive")
    print("Health check: http://localhost:5001/health")
    print("=" * 60)
    
    app.run(host=host, port=port, debug=debug) 