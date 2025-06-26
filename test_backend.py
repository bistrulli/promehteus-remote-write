#!/usr/bin/env python3
"""
Script di test per il backend Prometheus Remote Write
=====================================================

Questo script testa la connettività e le funzionalità del backend
prima di configurare Prometheus per remote write.

Uso:
    python test_backend.py
"""

import requests
import json
import time
from datetime import datetime

# Configurazione
BACKEND_URL = "http://localhost:5100"
HEALTH_ENDPOINT = f"{BACKEND_URL}/health"
METRICS_ENDPOINT = f"{BACKEND_URL}/metrics"
RECEIVE_ENDPOINT = f"{BACKEND_URL}/receive"

def test_health_check():
    """Testa l'endpoint di health check"""
    print("🔍 Testando health check...")
    try:
        response = requests.get(HEALTH_ENDPOINT, timeout=5)
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Health check OK")
            print(f"   InfluxDB Status: {data.get('influxdb_status')}")
            print(f"   InfluxDB Host: {data.get('influxdb_host')}:{data.get('influxdb_port')}")
            return True
        else:
            print(f"❌ Health check fallito: {response.status_code}")
            return False
    except requests.exceptions.RequestException as e:
        print(f"❌ Errore di connessione: {e}")
        return False

def test_metrics_endpoint():
    """Testa l'endpoint delle metriche"""
    print("\n📊 Testando endpoint metriche...")
    try:
        response = requests.get(METRICS_ENDPOINT, timeout=5)
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Endpoint metriche OK")
            print(f"   Metriche trovate: {data.get('count', 0)}")
            return True
        else:
            print(f"❌ Endpoint metriche fallito: {response.status_code}")
            return False
    except requests.exceptions.RequestException as e:
        print(f"❌ Errore di connessione: {e}")
        return False

def test_receive_endpoint():
    """Testa l'endpoint di ricezione con dati di test"""
    print("\n📤 Testando endpoint receive con dati di test...")
    
    # Dati di test (simula payload Prometheus)
    test_data = b"test_prometheus_remote_write_data"
    headers = {
        'Content-Type': 'application/x-protobuf',
        'Content-Encoding': 'snappy',
        'X-Prometheus-Remote-Write-Version': '0.1.0'
    }
    
    try:
        response = requests.post(RECEIVE_ENDPOINT, data=test_data, headers=headers, timeout=5)
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Endpoint receive OK")
            print(f"   Data size: {data.get('data_size')}")
            print(f"   Status: {data.get('status')}")
            return True
        else:
            print(f"❌ Endpoint receive fallito: {response.status_code}")
            print(f"   Response: {response.text}")
            return False
    except requests.exceptions.RequestException as e:
        print(f"❌ Errore di connessione: {e}")
        return False

def test_info_endpoint():
    """Testa l'endpoint di informazioni"""
    print("\nℹ️  Testando endpoint info...")
    try:
        response = requests.get(BACKEND_URL, timeout=5)
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Endpoint info OK")
            print(f"   Service: {data.get('service')}")
            print(f"   Mode: {data.get('mode')}")
            return True
        else:
            print(f"❌ Endpoint info fallito: {response.status_code}")
            return False
    except requests.exceptions.RequestException as e:
        print(f"❌ Errore di connessione: {e}")
        return False

def main():
    """Esegue tutti i test"""
    print("=" * 60)
    print("TEST BACKEND PROMETHEUS REMOTE WRITE")
    print("=" * 60)
    print(f"Backend URL: {BACKEND_URL}")
    print(f"Timestamp: {datetime.now().isoformat()}")
    print("=" * 60)
    
    # Esegui test
    tests = [
        ("Health Check", test_health_check),
        ("Info Endpoint", test_info_endpoint),
        ("Metrics Endpoint", test_metrics_endpoint),
        ("Receive Endpoint", test_receive_endpoint)
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"❌ Errore nel test {test_name}: {e}")
            results.append((test_name, False))
    
    # Risultati finali
    print("\n" + "=" * 60)
    print("RISULTATI TEST")
    print("=" * 60)
    
    passed = 0
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{test_name}: {status}")
        if result:
            passed += 1
    
    print(f"\nTest passati: {passed}/{len(results)}")
    
    if passed == len(results):
        print("\n🎉 TUTTI I TEST PASSATI!")
        print("Il backend è pronto per ricevere metriche da Prometheus")
        print("\nProssimi passi:")
        print("1. Configura Prometheus remote write su:")
        print(f"   {RECEIVE_ENDPOINT}")
        print("2. Monitora le metriche in Grafana: http://localhost:3000")
        print("3. Verifica i dati con: curl http://localhost:5100/metrics")
    else:
        print("\n⚠️  ALCUNI TEST FALLITI")
        print("Verifica che:")
        print("1. Il backend sia in esecuzione: python app.py")
        print("2. InfluxDB sia attivo: docker-compose up -d")
        print("3. Le porte siano libere (5000, 8086, 3000)")
    
    print("=" * 60)

if __name__ == "__main__":
    main() 