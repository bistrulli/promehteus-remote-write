# Installazione Istio con Prometheus Accessibile da Internet

Guida completa per installare Istio su GCP con Prometheus accessibile da internet e remote write configurato.

## Prerequisiti

- ✅ Cluster GKE configurato
- ✅ `kubectl` connesso al cluster
- ✅ `istioctl` installato (versione 1.23.2)
- ✅ Backend Flask in esecuzione e accessibile

## 🚀 Installazione Rapida

### 1. Configura l'IP del Backend

```bash
# Sostituisci con l'IP del tuo backend
export BACKEND_IP="192.168.1.100"  # Esempio
```

### 2. Esegui l'Installazione

```bash
cd k8s
chmod +x install-istio.sh
./install-istio.sh
```

## 📋 Cosa Viene Installato

### **Componenti Istio**
- ✅ **Istio Control Plane** (Pilot, Citadel, Galley)
- ✅ **Prometheus** con remote write configurato
- ✅ **Grafana** per visualizzazione
- ✅ **Kiali** per service mesh visualization

### **Configurazioni**
- ✅ **Prometheus** accessibile da internet (LoadBalancer)
- ✅ **Remote write** verso il tuo backend
- ✅ **Storage persistente** (10Gi)
- ✅ **Filtri metriche** (solo Istio/Envoy)
- ✅ **Resilienza** configurata

## 🌐 Accesso ai Servizi

Dopo l'installazione, otterrai IP esterni per:

### **Prometheus**
- **URL:** `http://<IP_PROMETHEUS>:9090`
- **Funzionalità:** Query metriche, configurazione, alerting

### **Grafana**
- **URL:** `http://<IP_GRAFANA>:3000`
- **Credenziali:** `admin/admin123`
- **Funzionalità:** Dashboard, visualizzazioni

### **Kiali**
- **URL:** `http://<IP_KIALI>:20001`
- **Funzionalità:** Service mesh visualization, traffico

## 🔍 Verifica Installazione

### **1. Controlla i Pod**
```bash
kubectl get pods -n istio-system
```

Dovresti vedere:
- `istiod-xxx` (Istio control plane)
- `prometheus-xxx` (Prometheus)
- `grafana-xxx` (Grafana)
- `kiali-xxx` (Kiali)

### **2. Controlla i Servizi**
```bash
kubectl get svc -n istio-system
```

Dovresti vedere LoadBalancer per:
- `prometheus` (porta 9090)
- `grafana` (porta 3000)
- `kiali` (porta 20001)

### **3. Ottieni IP Esterne**
```bash
kubectl get svc -n istio-system -o wide
```

## 📈 Verifica Remote Write

### **1. Controlla Log Prometheus**
```bash
kubectl logs -f deployment/prometheus -n istio-system
```

Cerca messaggi come:
- `Remote write successful`
- `Sending batch of X samples`

### **2. Controlla Configurazione**
```bash
# Port-forward Prometheus
kubectl port-forward svc/prometheus 9090:9090 -n istio-system

# Vai su http://localhost:9090/config
# Cerca la sezione "remote_write"
```

### **3. Controlla Backend**
```bash
# Verifica che il backend riceva metriche
curl http://localhost:8000/api/v1/metrics
```

## 🔧 Personalizzazioni

### **Modificare Filtri Metriche**
Modifica `istio-install-config.yaml`:

```yaml
writeRelabelConfigs:
  # Tutte le metriche (invece di solo Istio)
  - sourceLabels: [__name__]
    regex: '.*'
    action: keep
```

### **Modificare Risorse**
```yaml
resources:
  requests:
    memory: 200Mi  # Riduci se necessario
    cpu: 200m
  limits:
    memory: 400Mi
    cpu: 300m
```

### **Modificare Storage**
```yaml
storageSpec:
  volumeClaimTemplate:
    spec:
      resources:
        requests:
          storage: 5Gi  # Riduci se necessario
```

## 🚨 Troubleshooting

### **Prometheus non si avvia**
```bash
kubectl describe pod -l app=prometheus -n istio-system
kubectl logs deployment/prometheus -n istio-system
```

### **Remote write non funziona**
1. Verifica che l'IP del backend sia corretto
2. Controlla che il backend sia raggiungibile dal cluster
3. Verifica i log di Prometheus

### **IP esterni non assegnati**
```bash
# Aspetta alcuni minuti, poi controlla:
kubectl get svc -n istio-system
```

### **Storage non disponibile**
```bash
# Verifica storage class disponibili
kubectl get storageclass
```

## 🧹 Disinstallazione

```bash
# Disinstalla Istio
istioctl uninstall --purge

# Rimuovi namespace
kubectl delete namespace istio-system
```

## 📞 Supporto

Se hai problemi:
1. Controlla i log: `kubectl logs -n istio-system`
2. Verifica la configurazione: `istioctl analyze`
3. Controlla lo stato: `kubectl get all -n istio-system` 