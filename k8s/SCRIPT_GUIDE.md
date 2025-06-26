# 🚀 Guida agli Script di Automazione

Questa guida spiega come utilizzare gli script di automazione per il setup completo di Prometheus Remote Write.

## 📋 Prerequisiti

Prima di eseguire gli script, assicurati di avere:

```bash
# Verifica kubectl
kubectl version --client

# Verifica istioctl
istioctl version

# Verifica Docker
docker --version

# Verifica connessione al cluster
kubectl cluster-info
```

## 🎯 Script Disponibili

### 1. `setup-complete.sh` - Setup Completo

**Funzionalità:**
- ✅ Installazione Istio con demo profile
- ✅ Installazione Prometheus addon
- ✅ Configurazione remote write
- ✅ Build e deploy del backend Flask
- ✅ Deploy di InfluxDB
- ✅ Esposizione Prometheus via LoadBalancer
- ✅ Verifica automatica del setup

**Utilizzo:**
```bash
cd k8s
./setup-complete.sh
```

**Output atteso:**
```
=============================================================================
🚀 PROMETHEUS REMOTE WRITE COMPLETE SETUP
=============================================================================

[INFO] Checking cluster connectivity...
[SUCCESS] Connected to cluster: your-cluster-name
[INFO] Installing Istio...
[SUCCESS] Istio installed successfully
[INFO] Installing Prometheus addon...
[SUCCESS] Prometheus addon installed successfully
[INFO] Configuring Prometheus remote write...
[SUCCESS] Prometheus remote write configured successfully
[INFO] Creating LoadBalancer service for Prometheus...
[SUCCESS] Prometheus exposed at: http://34.123.45.67:9090
[INFO] Building backend Docker image...
[SUCCESS] Backend image built and loaded successfully
[INFO] Deploying metrics backend...
[SUCCESS] Backend deployed successfully
[INFO] Verifying setup...
[SUCCESS] Setup verification completed

=============================================================================
🎉 SETUP COMPLETED SUCCESSFULLY! 🎉
=============================================================================
```

### 2. `cleanup.sh` - Cleanup Completo

**Funzionalità:**
- 🧹 Rimozione backend e InfluxDB
- 🧹 Rimozione Prometheus LoadBalancer
- 🧹 Rimozione Prometheus addon
- 🧹 Rimozione Istio service mesh
- 🧹 Pulizia file di configurazione

**Utilizzo:**
```bash
cd k8s
./cleanup.sh
```

**Output atteso:**
```
=============================================================================
🧹 PROMETHEUS REMOTE WRITE CLEANUP
=============================================================================

[INFO] Checking cluster connectivity...
[SUCCESS] Connected to cluster: your-cluster-name
[INFO] Cleaning up backend and InfluxDB...
[SUCCESS] Backend namespace deleted
[INFO] Cleaning up Prometheus LoadBalancer...
[SUCCESS] Prometheus LoadBalancer deleted
[INFO] Cleaning up Prometheus addon...
[SUCCESS] Prometheus addon deleted
[INFO] Cleaning up Istio...
[SUCCESS] Istio uninstalled
[INFO] Cleaning up local files...
[SUCCESS] Local files cleaned up

=============================================================================
🧹 CLEANUP COMPLETED! 🧹
=============================================================================
```

## 🔧 Configurazione Personalizzata

### Modificare i Namespace

Se vuoi usare namespace diversi, modifica le variabili negli script:

```bash
# In setup-complete.sh e cleanup.sh
NAMESPACE="istio-system"           # Namespace per Istio/Prometheus
BACKEND_NAMESPACE="metrics-backend" # Namespace per il backend
```

### Modificare la Porta Prometheus

```bash
# In setup-complete.sh
PROMETHEUS_PORT="9090"  # Porta per il LoadBalancer
```

### Modificare l'URL del Backend

Se il backend è su un cluster diverso, modifica l'URL in `prometheus-patch.yaml`:

```yaml
remote_write:
  - url: "http://your-backend-url:5000/receive"
```

## 🚨 Troubleshooting

### Errore: "istioctl not found"
```bash
# Installa istioctl
curl -L https://istio.io/downloadIstio | sh -
export PATH=$PWD/istio-1.23.2/bin:$PATH
```

### Errore: "Cannot connect to Kubernetes cluster"
```bash
# Verifica kubeconfig
kubectl config current-context
kubectl config get-contexts

# Se necessario, imposta il context
kubectl config use-context your-cluster-context
```

### Errore: "Backend image not found"
```bash
# Verifica che Docker sia in esecuzione
docker ps

# Rebuild l'immagine manualmente
cd backend
docker build -t metrics-backend:latest .
```

### Prometheus non invia metriche
```bash
# Controlla la configurazione
kubectl get configmap prometheus -n istio-system -o yaml

# Controlla i log
kubectl logs -l app=prometheus -n istio-system -f

# Verifica connettività
kubectl exec -it deployment/prometheus -n istio-system -- wget -qO- http://metrics-backend-service.metrics-backend.svc.cluster.local:5000/metrics
```

## 📊 Verifica del Setup

Dopo l'esecuzione dello script, verifica che tutto funzioni:

### 1. Controlla i Pod
```bash
kubectl get pods -n istio-system
kubectl get pods -n metrics-backend
```

### 2. Controlla i Servizi
```bash
kubectl get services -n istio-system
kubectl get services -n metrics-backend
```

### 3. Test del Backend
```bash
# Port-forward
kubectl port-forward service/metrics-backend-service 5000:5000 -n metrics-backend

# Test endpoint
curl http://localhost:5000/metrics
curl http://localhost:5000/query?metric=istio_requests_total
```

### 4. Accesso a Prometheus
```bash
# Ottieni IP LoadBalancer
kubectl get service prometheus-loadbalancer -n istio-system

# Accedi via browser: http://<EXTERNAL_IP>:9090
```

## 🔄 Workflow Completo

### Setup Iniziale
```bash
# 1. Clona il repository
git clone <repository-url>
cd promehteus-remote-write

# 2. Esegui setup completo
cd k8s
./setup-complete.sh

# 3. Verifica il setup
kubectl get pods -A
kubectl logs -l app=prometheus -n istio-system -f
```

### Aggiornamento Backend
```bash
# 1. Modifica il codice backend
cd backend
# ... modifica app.py ...

# 2. Rebuild e redeploy
docker build -t metrics-backend:latest .
kubectl rollout restart deployment/metrics-backend -n metrics-backend

# 3. Verifica
kubectl logs -l app=metrics-backend -n metrics-backend -f
```

### Cleanup Completo
```bash
# 1. Rimuovi tutto
cd k8s
./cleanup.sh

# 2. Verifica rimozione
kubectl get namespaces | grep -E "(istio-system|metrics-backend)"
```

## 📝 Note Importanti

- **Cluster Requirements**: Il cluster deve supportare LoadBalancer services
- **Istio Version**: Gli script sono testati con Istio 1.23.x
- **Storage**: InfluxDB usa storage temporaneo (emptyDir)
- **Security**: In produzione, configura HTTPS e autenticazione
- **Monitoring**: Monitora l'uso delle risorse del cluster

## 🆘 Supporto

Se incontri problemi:

1. **Controlla i log**: Tutti i componenti hanno logging dettagliato
2. **Verifica connettività**: Usa `kubectl exec` per testare la rete
3. **Controlla risorse**: Verifica CPU/memory del cluster
4. **Reinstalla**: Usa `cleanup.sh` e poi `setup-complete.sh` 