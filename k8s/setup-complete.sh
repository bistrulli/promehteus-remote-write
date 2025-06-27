#!/bin/bash

# =============================================================================
# PROMETHEUS REMOTE WRITE SETUP SCRIPT
# =============================================================================
# Questo script automatizza il setup di:
# 1. Istio con Prometheus addon
# 2. Configurazione Prometheus per remote write
# 3. Esposizione Prometheus via LoadBalancer
# =============================================================================

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
CLUSTER_NAME="cluster-1"
NAMESPACE="istio-system"
PROMETHEUS_PORT="9090"

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Function to check if command exists
check_command() {
    if ! command -v $1 &> /dev/null; then
        print_error "$1 is not installed. Please install it first."
        exit 1
    fi
}

# Function to check cluster connectivity
check_cluster() {
    print_status "Checking cluster connectivity..."
    if ! kubectl cluster-info &> /dev/null; then
        print_error "Cannot connect to Kubernetes cluster. Please check your kubeconfig."
        exit 1
    fi
    
    CLUSTER_NAME=$(kubectl config current-context)
    print_success "Connected to cluster: $CLUSTER_NAME"
}

# Function to install Istio
install_istio() {
    print_status "Installing Istio..."
    
    # Check if istioctl is available
    check_command istioctl
    
    # Install Istio with demo profile
    istioctl install --set profile=demo -y
    
    # Wait for Istio to be ready
    print_status "Waiting for Istio to be ready..."
    kubectl wait --for=condition=ready pod -l app=istiod -n istio-system --timeout=300s
    
    print_success "Istio installed successfully"
}

# Function to install Prometheus addon
install_prometheus() {
    print_status "Installing Prometheus addon..."
    
    # Create namespace if it doesn't exist
    kubectl create namespace $NAMESPACE --dry-run=client -o yaml | kubectl apply -f -
    
    # Install Prometheus addon
    kubectl apply -f https://raw.githubusercontent.com/istio/istio/release-1.23/samples/addons/prometheus.yaml
    
    # Wait for Prometheus to be ready with retry logic
    print_status "Waiting for Prometheus to be ready..."
    for i in {1..10}; do
        if kubectl wait --for=condition=ready pod -l app.kubernetes.io/name=prometheus -n $NAMESPACE --timeout=60s 2>/dev/null; then
            print_success "Prometheus addon installed successfully"
            return 0
        else
            print_warning "Prometheus not ready yet, waiting... (attempt $i/10)"
            sleep 30
        fi
    done
    
    print_error "Prometheus failed to become ready after 10 attempts"
    exit 1
}

# Function to configure Prometheus remote write
configure_prometheus_remote_write() {
    print_status "Configuring Prometheus remote write..."
    
    # Create a temporary file with the placeholder replaced
    BACKEND_URL="http://your-victoriametrics-host:8428"
    
    # Replace placeholder in the template file
    sed "s|{{BACKEND_URL}}|$BACKEND_URL|g" prometheus-config-patched.yaml > prometheus-config-temp.yaml
    
    # Apply the patched config
    kubectl apply -f prometheus-config-temp.yaml
    
    # Clean up temporary file
    rm -f prometheus-config-temp.yaml
    
    # Restart Prometheus to pick up the new config
    print_status "Restarting Prometheus to apply new configuration..."
    kubectl rollout restart deployment/prometheus -n $NAMESPACE
    
    # Wait for Prometheus to be ready again (new pod after restart)
    print_status "Waiting for new Prometheus pod to be ready..."
    kubectl rollout status deployment/prometheus -n $NAMESPACE --timeout=300s
    
    print_success "Prometheus remote write configured successfully"
}

# Function to create LoadBalancer service for Prometheus
expose_prometheus() {
    print_status "Creating LoadBalancer service for Prometheus..."
    
    cat > prometheus-loadbalancer.yaml << EOF
apiVersion: v1
kind: Service
metadata:
  name: prometheus-loadbalancer
  namespace: $NAMESPACE
spec:
  type: LoadBalancer
  ports:
  - port: $PROMETHEUS_PORT
    targetPort: 9090
    protocol: TCP
  selector:
    app.kubernetes.io/name: prometheus
EOF

    kubectl apply -f prometheus-loadbalancer.yaml
    
    print_status "Waiting for LoadBalancer IP..."
    sleep 30
    
    # Get the external IP
    EXTERNAL_IP=$(kubectl get service prometheus-loadbalancer -n $NAMESPACE -o jsonpath='{.status.loadBalancer.ingress[0].ip}' 2>/dev/null || echo "")
    if [ -z "$EXTERNAL_IP" ]; then
        EXTERNAL_IP=$(kubectl get service prometheus-loadbalancer -n $NAMESPACE -o jsonpath='{.status.loadBalancer.ingress[0].hostname}' 2>/dev/null || echo "")
    fi
    
    if [ -n "$EXTERNAL_IP" ]; then
        print_success "Prometheus exposed at: http://$EXTERNAL_IP:$PROMETHEUS_PORT"
    else
        print_warning "LoadBalancer IP not yet available. Check with: kubectl get service prometheus-loadbalancer -n $NAMESPACE"
    fi
}

# Function to update backend URL
update_backend_url() {
    local new_url=$1
    
    if [ -z "$new_url" ]; then
        print_error "Please provide a backend URL"
        echo "Usage: $0 update-backend <backend-url>"
        echo "Example: $0 update-backend http://my-victoriametrics-host:8428"
        exit 1
    fi
    
    print_status "Updating backend URL to: $new_url"
    
    # Replace placeholder in the template file
    sed "s|{{BACKEND_URL}}|$new_url|g" prometheus-config-patched.yaml > prometheus-config-temp.yaml
    
    # Apply the updated config
    kubectl apply -f prometheus-config-temp.yaml
    
    # Clean up temporary file
    rm -f prometheus-config-temp.yaml
    
    # Restart Prometheus to pick up the new config
    print_status "Restarting Prometheus to apply new configuration..."
    kubectl rollout restart deployment/prometheus -n $NAMESPACE
    
    # Wait for Prometheus to be ready again
    print_status "Waiting for new Prometheus pod to be ready..."
    kubectl rollout status deployment/prometheus -n $NAMESPACE --timeout=300s
    
    print_success "Backend URL updated successfully"
}

# Function to verify setup
verify_setup() {
    print_status "Verifying setup..."
    
    # Check Prometheus logs
    print_status "Checking Prometheus logs..."
    kubectl logs -l app.kubernetes.io/name=prometheus -n $NAMESPACE --tail=20
    
    # Check Prometheus configuration
    print_status "Checking Prometheus configuration..."
    kubectl get configmap prometheus -n $NAMESPACE -o yaml | grep -A 5 "remote_write:"
    
    print_success "Setup verification completed"
}

# Function to show next steps
show_next_steps() {
    echo ""
    echo "============================================================================="
    echo "🎉 SETUP COMPLETED SUCCESSFULLY! 🎉"
    echo "============================================================================="
    echo ""
    echo "What's been configured:"
    echo "✅ Istio with demo profile"
    echo "✅ Prometheus addon with remote write"
    echo "✅ Prometheus exposed via LoadBalancer"
    echo ""
    echo "Next steps:"
    echo "1. Access Prometheus UI:"
    echo "   kubectl get service prometheus-loadbalancer -n $NAMESPACE"
    echo ""
    echo "2. Check Prometheus remote write status:"
    echo "   kubectl logs -l app.kubernetes.io/name=prometheus -n $NAMESPACE -f"
    echo ""
    echo "3. Update backend URL when ready:"
    echo "   ./setup-complete.sh update-backend http://your-actual-victoriametrics-host:8428"
    echo ""
    echo "4. Manual update (alternative):"
    echo "   Edit prometheus-config-patched.yaml and change {{BACKEND_URL}}"
    echo ""
    echo "============================================================================="
}

# Main execution
main() {
    # Check if this is an update-backend command
    if [ "$1" = "update-backend" ]; then
        check_command kubectl
        check_cluster
        update_backend_url "$2"
        return 0
    fi
    
    echo "============================================================================="
    echo "🚀 PROMETHEUS REMOTE WRITE SETUP"
    echo "============================================================================="
    echo ""
    
    # Check prerequisites
    check_command kubectl
    check_command istioctl
    
    # Check cluster
    check_cluster
    
    # Execute setup steps
    install_istio
    install_prometheus
    configure_prometheus_remote_write
    expose_prometheus
    verify_setup
    show_next_steps
}

# Run main function
main "$@" 