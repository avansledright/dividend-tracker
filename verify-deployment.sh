#!/bin/bash
# Kubernetes Deployment Verification Script for Dividend Tracker

set -e

echo "======================================"
echo "Dividend Tracker - Deployment Verification"
echo "======================================"
echo ""

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check kubectl access
echo "1. Checking kubectl access..."
if kubectl cluster-info &>/dev/null; then
    echo -e "${GREEN}✓${NC} kubectl access verified"
else
    echo -e "${RED}✗${NC} kubectl access failed"
    exit 1
fi
echo ""

# Check MongoDB
echo "2. Checking MongoDB deployment..."
MONGO_PODS=$(kubectl get pods -l app=dividend-tracker-mongodb -n default --no-headers 2>/dev/null | wc -l)
if [ "$MONGO_PODS" -gt 0 ]; then
    echo -e "${GREEN}✓${NC} MongoDB pods found: $MONGO_PODS"
    kubectl get pods -l app=dividend-tracker-mongodb -n default

    MONGO_READY=$(kubectl get pods -l app=dividend-tracker-mongodb -n default -o jsonpath='{.items[0].status.conditions[?(@.type=="Ready")].status}' 2>/dev/null)
    if [ "$MONGO_READY" = "True" ]; then
        echo -e "${GREEN}✓${NC} MongoDB is ready"
    else
        echo -e "${YELLOW}⚠${NC} MongoDB is not ready yet"
    fi
else
    echo -e "${YELLOW}⚠${NC} MongoDB pods not found (will be created on first deploy)"
fi
echo ""

# Check Application
echo "3. Checking Application deployment..."
APP_PODS=$(kubectl get pods -l app=dividend-tracker -n default --no-headers 2>/dev/null | wc -l)
if [ "$APP_PODS" -gt 0 ]; then
    echo -e "${GREEN}✓${NC} Application pods found: $APP_PODS"
    kubectl get pods -l app=dividend-tracker -n default

    APP_READY=$(kubectl get pods -l app=dividend-tracker -n default -o jsonpath='{.items[*].status.conditions[?(@.type=="Ready")].status}' 2>/dev/null)
    if [[ "$APP_READY" =~ "True" ]]; then
        echo -e "${GREEN}✓${NC} Application pods are ready"
    else
        echo -e "${YELLOW}⚠${NC} Application pods are not ready yet"
    fi
else
    echo -e "${YELLOW}⚠${NC} Application pods not found (not deployed yet)"
fi
echo ""

# Check Services
echo "4. Checking Services..."
if kubectl get svc dividend-tracker -n default &>/dev/null; then
    echo -e "${GREEN}✓${NC} Application service exists"
    kubectl get svc dividend-tracker -n default
else
    echo -e "${YELLOW}⚠${NC} Application service not found"
fi

if kubectl get svc mongodb -n default &>/dev/null; then
    echo -e "${GREEN}✓${NC} MongoDB service exists"
    kubectl get svc mongodb -n default
else
    echo -e "${YELLOW}⚠${NC} MongoDB service not found"
fi
echo ""

# Check Ingress
echo "5. Checking Ingress..."
if kubectl get ingress dividend-tracker -n default &>/dev/null; then
    echo -e "${GREEN}✓${NC} Ingress exists"
    kubectl get ingress dividend-tracker -n default
else
    echo -e "${YELLOW}⚠${NC} Ingress not found"
fi
echo ""

# Check PVC
echo "6. Checking Persistent Volume..."
if kubectl get pvc mongodb-pvc -n default &>/dev/null; then
    echo -e "${GREEN}✓${NC} MongoDB PVC exists"
    kubectl get pvc mongodb-pvc -n default
else
    echo -e "${YELLOW}⚠${NC} MongoDB PVC not found"
fi
echo ""

# Check Secrets
echo "7. Checking Secrets..."
if kubectl get secret dividend-tracker-secrets -n default &>/dev/null; then
    echo -e "${GREEN}✓${NC} Application secrets exist"
else
    echo -e "${YELLOW}⚠${NC} Application secrets not found (will be created on first deploy)"
fi
echo ""

# Test Health Endpoint
echo "8. Testing Health Endpoint..."
if [ "$APP_PODS" -gt 0 ]; then
    POD_NAME=$(kubectl get pod -l app=dividend-tracker -n default -o jsonpath='{.items[0].metadata.name}' 2>/dev/null)
    if [ -n "$POD_NAME" ]; then
        echo "Testing from pod: $POD_NAME"
        if kubectl exec -n default "$POD_NAME" -- wget -q -O- http://localhost:5000/finance/health 2>/dev/null; then
            echo -e "${GREEN}✓${NC} Health endpoint is responding"
        else
            echo -e "${RED}✗${NC} Health endpoint not responding"
        fi
    fi
else
    echo -e "${YELLOW}⚠${NC} No pods available to test health endpoint"
fi
echo ""

# Test External Access
echo "9. Testing External Access..."
if command -v curl &>/dev/null; then
    echo "Testing: http://home.home/finance/health"
    if curl -s -f http://home.home/finance/health &>/dev/null; then
        echo -e "${GREEN}✓${NC} External health endpoint is accessible"
        curl -s http://home.home/finance/health | python3 -m json.tool 2>/dev/null || curl -s http://home.home/finance/health
    else
        echo -e "${YELLOW}⚠${NC} External health endpoint not accessible (might be normal if not deployed yet)"
    fi
else
    echo -e "${YELLOW}⚠${NC} curl not available, skipping external test"
fi
echo ""

# Recent Events
echo "10. Recent Kubernetes Events..."
kubectl get events --sort-by=.lastTimestamp -n default --field-selector involvedObject.name!=coredns | tail -10
echo ""

echo "======================================"
echo "Verification Complete!"
echo "======================================"
echo ""
echo "Quick Commands:"
echo "  Logs:      kubectl logs -l app=dividend-tracker -n default -f"
echo "  MongoDB:   kubectl logs -l app=dividend-tracker-mongodb -n default -f"
echo "  Describe:  kubectl describe pod -l app=dividend-tracker -n default"
echo "  Events:    kubectl get events --sort-by=.lastTimestamp -n default"
echo "  Access:    http://home.home/finance/"
echo ""
