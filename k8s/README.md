# Configurazione Prometheus Istio per Remote Write

Questa directory contiene i file per configurare il Prometheus di Istio per inviare metriche al tuo backend Flask tramite remote write.

## Prerequisiti

- Cluster Kubernetes con Istio installato
- Backend Flask accessibile dal cluster K8s
- `kubectl` configurato per il cluster

## File Contenuti

- `prometheus-config.yaml` - Configurazione Prometheus con remote write
- `prometheus-patch.yaml` - Patch per il deployment Prometheus
- `istio-telemetry-config.yaml` - Configurazione IstioOperator
- `apply-config.sh` - Script per applicare la configurazione

## Metodo 1: Configurazione Manuale (Raccomandato)

### 1. Configura l'URL del Backend

Modifica il file `prometheus-config.yaml` e sostituisci:
```yaml
remote_write:
  - url: "http://your-backend-url:8000/api/v1/write"
```

Con l'URL del tuo backend:
```yaml
remote_write:
  - url: "http://your-backend-ip:8000/api/v1/write"
```

### 2. Applica la Configurazione

```bash
# Rendi eseguibile lo script
chmod +x apply-config.sh

# Applica la configurazione
BACKEND_URL="http://your-backend-ip:8000" ./apply-config.sh
```

### 3. Verifica l'Installazione

```bash
# Port-forward per accedere a Prometheus
kubectl port-forward svc/prometheus 9090:9090 -n istio-system

# Verifica i log
kubectl logs -f deployment/prometheus -n istio-system
```

## Metodo 2: Configurazione IstioOperator

Se stai installando Istio da zero:

```bash
# Modifica istio-telemetry-config.yaml con il tuo backend URL
# Poi applica:
istioctl install -f istio-telemetry-config.yaml
```

## Metriche Esportate

Con questa configurazione, Prometheus esporterà:

### Metriche Istio
- `istio_requests_total` - Richieste totali
- `istio_request_duration_milliseconds` - Durata richieste
- `istio_request_bytes` - Byte richieste
- `istio_response_bytes` - Byte risposte
- `istio_tcp_connections_opened_total` - Connessioni TCP aperte
- `istio_tcp_connections_closed_total` - Connessioni TCP chiuse

### Metriche Envoy
- `envoy_http_downstream_rq_total` - Richieste HTTP downstream
- `envoy_http_downstream_rq_time_bucket` - Tempo richieste
- `envoy_cluster_upstream_cx_total` - Connessioni upstream

### Metriche Kubernetes
- Metriche dei nodi
- Metriche dei pod
- Metriche dell'API server

## Filtri Personalizzati

Per esportare solo metriche specifiche, modifica `write_relabel_configs`:

```yaml
# Solo metriche Istio
- sourceLabels: [__name__]
  regex: 'istio_.*|envoy_.*'
  action: keep

# Escludi metriche Go
- sourceLabels: [__name__]
  regex: 'go_.*'
  action: drop
```

## Troubleshooting

### Prometheus non si avvia
```bash
kubectl describe pod -l app=prometheus -n istio-system
kubectl logs deployment/prometheus -n istio-system
```

### Remote Write non funziona
1. Verifica che il backend sia raggiungibile dal cluster
2. Controlla i log di Prometheus per errori di connessione
3. Verifica che il backend risponda su `/api/v1/write`

### Verifica Configurazione
```bash
# Controlla la configurazione attuale
kubectl get configmap prometheus-config -n istio-system -o yaml

# Verifica che il deployment usi la ConfigMap
kubectl describe deployment prometheus -n istio-system
```

## Note Importanti

- Il backend deve essere accessibile dal cluster Kubernetes
- Se il backend è esterno, assicurati che sia raggiungibile via rete
- Considera l'uso di un LoadBalancer o Ingress per il backend
- Monitora l'utilizzo di risorse di Prometheus con remote write abilitato 