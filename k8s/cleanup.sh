#!/bin/bash

# =============================================================================
# CLEANUP SCRIPT FOR PROMETHEUS REMOTE WRITE SETUP
# =============================================================================
# Questo script rimuove il setup di:
# 1. Prometheus LoadBalancer
# 2. Prometheus addon
# 3. Istio service mesh
# =============================================================================

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
NAMESPACE="istio-system"

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

# Function to cleanup Prometheus LoadBalancer
cleanup_prometheus_lb() {
    print_status "Cleaning up Prometheus LoadBalancer..."
    
    # Delete LoadBalancer service
    if kubectl get service prometheus-loadbalancer -n $NAMESPACE &> /dev/null; then
        kubectl delete service prometheus-loadbalancer -n $NAMESPACE
        print_success "Prometheus LoadBalancer deleted"
    else
        print_warning "Prometheus LoadBalancer not found"
    fi
}

# Function to cleanup Prometheus addon
cleanup_prometheus() {
    print_status "Cleaning up Prometheus addon..."
    
    # Delete Prometheus addon
    if kubectl get deployment prometheus -n $NAMESPACE &> /dev/null; then
        kubectl delete -f https://raw.githubusercontent.com/istio/istio/release-1.23/samples/addons/prometheus.yaml
        print_success "Prometheus addon deleted"
    else
        print_warning "Prometheus addon not found"
    fi
}

# Function to cleanup Istio
cleanup_istio() {
    print_status "Cleaning up Istio..."
    
    # Check if istioctl is available
    if ! command -v istioctl &> /dev/null; then
        print_warning "istioctl not found, skipping Istio cleanup"
        return
    fi
    
    # Uninstall Istio
    if kubectl get deployment istiod -n $NAMESPACE &> /dev/null; then
        istioctl uninstall --purge -y
        print_success "Istio uninstalled"
    else
        print_warning "Istio not found"
    fi
}

# Function to cleanup local files
cleanup_files() {
    print_status "Cleaning up local files..."
    
    # Remove generated files
    rm -f prometheus-config-patched.yaml
    rm -f prometheus-loadbalancer.yaml
    
    print_success "Local files cleaned up"
}

# Function to show cleanup summary
show_cleanup_summary() {
    echo ""
    echo "============================================================================="
    echo "🧹 CLEANUP COMPLETED! 🧹"
    echo "============================================================================="
    echo ""
    echo "The following components have been removed:"
    echo "✅ Prometheus LoadBalancer service"
    echo "✅ Prometheus addon"
    echo "✅ Istio service mesh"
    echo "✅ Generated configuration files"
    echo ""
    echo "Your cluster is now clean and ready for a fresh setup!"
    echo "============================================================================="
}

# Main execution
main() {
    echo "============================================================================="
    echo "🧹 PROMETHEUS REMOTE WRITE CLEANUP"
    echo "============================================================================="
    echo ""
    
    # Check cluster
    check_cluster
    
    # Execute cleanup steps
    cleanup_prometheus_lb
    cleanup_prometheus
    cleanup_istio
    cleanup_files
    show_cleanup_summary
}

# Run main function
main "$@" 