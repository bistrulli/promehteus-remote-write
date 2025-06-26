# Prometheus Remote Write Setup

Questo progetto implementa un setup completo per **Prometheus Remote Write** con un backend personalizzato in Flask e storage InfluxDB, progettato per funzionare con cluster Kubernetes con Istio.

## 🏗️ Architettura

```
┌─────────────────┐    Remote Write    ┌─────────────────┐    ┌─────────────┐
│   Prometheus    │ ──────────────────► │  Flask Backend  │ ──► │  InfluxDB   │
│   (Istio)       │                     │                 │     │             │
└─────────────────┘                     └─────────────────┘     └─────────────┘
```

## 📋 Prerequisiti

- **Kubernetes cluster** (GKE, EKS, AKS, o locale con minikube/kind)
- **kubectl** configurato per il cluster
- **istioctl** (versione 1.23.x)
- **Docker** per build dell'immagine backend
- **curl** per test

## 🚀 Setup Automatico

### 1. Clona il repository
```bash
git clone <repository-url>
cd promehteus-remote-write
```

### 2. Esegui lo script di setup completo
```bash
cd k8s
./setup-complete.sh
```

Lo script automatizza completamente:
- ✅ Installazione Istio con demo profile
- ✅ Installazione Prometheus addon
- ✅ Configurazione remote write
- ✅ Build e deploy del backend Flask
- ✅ Deploy di InfluxDB
- ✅ Esposizione Prometheus via LoadBalancer
- ✅ Verifica del setup

### 3. Verifica il setup
Dopo l'esecuzione dello script, verifica che tutto funzioni:

```bash
# Controlla i pod
kubectl get pods -n istio-system
kubectl get pods -n metrics-backend

# Controlla i servizi
kubectl get services -n istio-system
kubectl get services -n metrics-backend

# Controlla i log di Prometheus
kubectl logs -l app=prometheus -n istio-system -f

# Controlla i log del backend
kubectl logs -l app=metrics-backend -n metrics-backend -f
```

## 🔧 Configurazione

### Prometheus Remote Write
Il Prometheus è configurato per inviare metriche al backend con:
- **URL**: `http://metrics-backend-service.metrics-backend.svc.cluster.local:5000/receive`
- **Filtro**: Solo metriche `istio_*`, `envoy_*`, `kubernetes_*`
- **Resilienza**: Retry automatico con backoff esponenziale
- **Queue**: Configurazione ottimizzata per alta throughput

### Backend Flask
Il backend fornisce:
- **Endpoint `/receive`**: Riceve dati remote write da Prometheus
- **Endpoint `/metrics`**: Lista tutte le metriche ricevute
- **Endpoint `/query`**: Query delle metriche con filtri
- **Storage**: InfluxDB per persistenza

### InfluxDB
Configurazione InfluxDB:
- **Database**: `prometheus_metrics`
- **User**: `admin`
- **Password**: `adminpassword`
- **Port**: `8086`

## 📊 Monitoraggio

### Accesso a Prometheus
```bash
# Ottieni l'IP del LoadBalancer
kubectl get service prometheus-loadbalancer -n istio-system

# Accedi via browser: http://<EXTERNAL_IP>:9090
```

### Test del Backend
```bash
# Port-forward del backend
kubectl port-forward service/metrics-backend-service 5000:5000 -n metrics-backend

# Test endpoint
curl http://localhost:5000/metrics
curl http://localhost:5000/query?metric=istio_requests_total
```

### Accesso a InfluxDB
```bash
# Port-forward di InfluxDB
kubectl port-forward service/influxdb-service 8086:8086 -n metrics-backend

# Query InfluxDB
curl -G "http://localhost:8086/query" --data-urlencode "db=prometheus_metrics" --data-urlencode "q=SHOW MEASUREMENTS"
```

## 🧹 Cleanup

Per rimuovere completamente il setup:

```bash
cd k8s
./cleanup.sh
```

Questo script rimuove:
- ✅ Backend e InfluxDB
- ✅ Prometheus LoadBalancer
- ✅ Prometheus addon
- ✅ Istio service mesh
- ✅ File di configurazione generati

## 📁 Struttura del Progetto

```
promehteus-remote-write/
├── backend/                    # Backend Flask
│   ├── app.py                 # Applicazione principale
│   ├── Dockerfile             # Build dell'immagine
│   ├── gunicorn.conf.py       # Configurazione Gunicorn
│   └── requirements.txt       # Dipendenze Python
├── k8s/                       # Configurazioni Kubernetes
│   ├── setup-complete.sh      # Script setup automatico
│   ├── cleanup.sh             # Script cleanup
│   ├── prometheus-patch.yaml  # Config Prometheus
│   └── README.md              # Documentazione K8s
└── README.md                  # Questo file
```

## 🔍 Troubleshooting

### Prometheus non invia metriche
```bash
# Controlla la configurazione
kubectl get configmap prometheus -n istio-system -o yaml

# Controlla i log
kubectl logs -l app=prometheus -n istio-system -f
```

### Backend non riceve metriche
```bash
# Controlla la connettività
kubectl exec -it deployment/prometheus -n istio-system -- wget -qO- http://metrics-backend-service.metrics-backend.svc.cluster.local:5000/metrics

# Controlla i log del backend
kubectl logs -l app=metrics-backend -n metrics-backend -f
```

### InfluxDB non risponde
```bash
# Controlla i pod
kubectl get pods -n metrics-backend

# Controlla i log
kubectl logs -l app=influxdb -n metrics-backend -f
```

## 🎯 Metriche Raccolte

Con Istio, Prometheus raccoglie automaticamente:
- **Metriche Istio**: `istio_requests_total`, `istio_request_duration_milliseconds`
- **Metriche Envoy**: `envoy_http_requests_total`, `envoy_http_request_duration_milliseconds`
- **Metriche Kubernetes**: `kubernetes_pod_container_status_running`
- **Metriche sistema**: `node_cpu_seconds_total`, `node_memory_MemAvailable_bytes`

## 🔄 Aggiornamenti

Per aggiornare il backend:
```bash
cd backend
docker build -t metrics-backend:latest .
kubectl rollout restart deployment/metrics-backend -n metrics-backend
```

## 📝 Note

- Il setup è ottimizzato per **Istio 1.23.x**
- Le metriche sono filtrate per ridurre il volume di dati
- Il backend è configurato per alta resilienza
- InfluxDB usa storage temporaneo (emptyDir) - per produzione usare PersistentVolume