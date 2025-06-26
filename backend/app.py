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
    http://localhost:5000/receive
    
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
        
        # NOTA: In una implementazione completa, qui parseresti il protobuf di Prometheus
        # e creeresti punti InfluxDB per ogni metrica ricevuta.
        # Per ora salviamo solo informazioni di debug per verificare il flusso.
        
        # Crea un punto di debug per InfluxDB
        point = {
            "measurement": "prometheus_remote_write_debug",
            "tags": {
                "source": request.remote_addr,
                "content_type": request.content_type,
                "endpoint": "/receive",
                "compressed": "snappy" if 'snappy' in request.content_type.lower() else "none"
            },
            "fields": {
                "raw_data_size": len(raw_data),
                "compressed_data_size": len(request.data),
                "timestamp": datetime.utcnow().timestamp(),
                "request_count": 1  # Per contare le richieste
            },
            "time": datetime.utcnow()
        }
        
        # Scrivi in InfluxDB
        influx_client.write_points([point])
        
        logger.info(f"Metrica di debug salvata in InfluxDB: {point}")
        logger.info("=== FINE RICHIESTA REMOTE WRITE ===")
        
        return jsonify({
            'status': 'success',
            'message': 'Metrica ricevuta e salvata in InfluxDB',
            'timestamp': datetime.now().isoformat(),
            'data_size': len(raw_data),
            'compressed_size': len(request.data)
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
            'test': '2. Testa connettività: curl http://localhost:5001/health',
            'prometheus': '3. Configura Prometheus remote write su http://localhost:5001/receive',
            'monitor': '4. Monitora metriche: curl http://localhost:5001/metrics',
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
    print("Endpoint principale per Prometheus: http://localhost:5001/receive")
    print("Health check: http://localhost:5001/health")
    print("=" * 60)
    
    app.run(host=host, port=port, debug=debug) 