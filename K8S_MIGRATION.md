# Kubernetes Migration Guide - Dividend Tracker

## Overview

This application has been migrated from Docker Swarm to k3s Kubernetes cluster.

## Architecture

### Before (Docker Swarm)
```
pfSense HAProxy → Docker Swarm → nginx proxy → dividend-tracker + mongodb
```

### After (k3s)
```
pfSense HAProxy → k3s Nodes → Traefik Ingress → dividend-tracker pods
                                              → mongodb pod (with PVC)
```

## Prerequisites

### Jenkins Credentials Required
- `k3s-kubeconfig` - Kubeconfig file for k3s cluster access
- `docker-registry-credentials` - Docker registry credentials (username/password)
- `alpha-vantage-key` - Alpha Vantage API key (optional, for stock data fallback)

### k3s Registry Configuration
Ensure k3s nodes can pull from the insecure registry at `192.168.1.23:5000`.

Verify with:
```bash
sudo crictl pull 192.168.1.23:5000/test:latest
```

## Deployment

### Manual Deployment

1. **Create secrets (if not exists):**
```bash
kubectl create secret generic dividend-tracker-secrets \
  --from-literal=alpha-vantage-key="YOUR_KEY_HERE" \
  --from-literal=secret-key="$(openssl rand -hex 32)" \
  -n default
```

2. **Deploy MongoDB:**
```bash
kubectl apply -f kubernetes/mongodb-pvc.yaml
kubectl apply -f kubernetes/mongodb-service.yaml
kubectl apply -f kubernetes/mongodb-deployment.yaml
```

3. **Wait for MongoDB:**
```bash
kubectl wait --for=condition=ready pod -l app=dividend-tracker-mongodb -n default --timeout=120s
```

4. **Deploy application:**
```bash
# Set BUILD_NUMBER
export BUILD_NUMBER=latest

# Deploy app
envsubst < kubernetes/deployment.yaml | kubectl apply -f -
kubectl apply -f kubernetes/service.yaml
kubectl apply -f kubernetes/ingress.yaml
```

5. **Verify deployment:**
```bash
kubectl get pods -l app=dividend-tracker -n default
kubectl get pods -l app=dividend-tracker-mongodb -n default
kubectl get ingress dividend-tracker -n default
```

### Automatic Deployment (Jenkins)

Simply push to the repository:
```bash
git add .
git commit -m "Update dividend tracker"
git push origin main
```

Jenkins will automatically:
1. Build Docker image
2. Push to registry
3. Deploy MongoDB (if not exists)
4. Deploy application with rolling update
5. Verify health checks

## Application Details

### URL
- **Production:** `http://home.home/finance/`
- **Health Check:** `http://home.home/finance/health`

### Environment Variables
- `APPLICATION_ROOT=/finance` - Base path for Flask app
- `MONGO_URI=mongodb://mongodb:27017/` - MongoDB connection string
- `ALPHA_VANTAGE_KEY` - Optional API key for stock data fallback
- `SECRET_KEY` - Flask session secret (auto-generated if not provided)

### Health Endpoint

The health endpoint (`/finance/health`) checks:
- Flask application is running
- MongoDB connection is active

Returns:
```json
{
  "status": "healthy",
  "app": "dividend-tracker",
  "database": "connected"
}
```

## MongoDB Storage

MongoDB uses a PersistentVolumeClaim (PVC) for data persistence:
- **Storage Class:** `local-path` (k3s default)
- **Size:** 5Gi
- **Access Mode:** ReadWriteOnce
- **Mount Path:** `/data/db`

### Backup MongoDB Data

```bash
# Get MongoDB pod name
POD_NAME=$(kubectl get pod -l app=dividend-tracker-mongodb -n default -o jsonpath='{.items[0].metadata.name}')

# Create backup
kubectl exec -n default $POD_NAME -- mongodump --archive --gzip > backup-$(date +%Y%m%d).gz

# Restore backup
kubectl exec -i -n default $POD_NAME -- mongorestore --archive --gzip < backup-20260208.gz
```

## Troubleshooting

### Check Pod Status
```bash
# Application pods
kubectl get pods -l app=dividend-tracker -n default
kubectl describe pod -l app=dividend-tracker -n default

# MongoDB pod
kubectl get pods -l app=dividend-tracker-mongodb -n default
kubectl describe pod -l app=dividend-tracker-mongodb -n default
```

### Check Logs
```bash
# Application logs
kubectl logs -l app=dividend-tracker -n default --tail=50
kubectl logs -l app=dividend-tracker -n default -f

# MongoDB logs
kubectl logs -l app=dividend-tracker-mongodb -n default --tail=50
```

### Check Services
```bash
kubectl get svc dividend-tracker -n default
kubectl get svc mongodb -n default
kubectl get ingress dividend-tracker -n default
```

### Test Health Endpoint
```bash
# From within cluster
POD_NAME=$(kubectl get pod -l app=dividend-tracker -n default -o jsonpath='{.items[0].metadata.name}')
kubectl exec -n default $POD_NAME -- wget -q -O- http://localhost:5000/finance/health

# From outside cluster
curl http://home.home/finance/health
```

### Common Issues

#### ImagePullBackOff
```bash
# Verify registry access from k3s nodes
sudo crictl pull 192.168.1.23:5000/dividend-tracker:latest
```

#### CrashLoopBackOff
```bash
# Check logs for errors
kubectl logs -l app=dividend-tracker -n default

# Common causes:
# - MongoDB not ready
# - Database connection issues
# - Application startup errors
```

#### MongoDB Connection Issues
```bash
# Check MongoDB is running
kubectl get pods -l app=dividend-tracker-mongodb -n default

# Test MongoDB connectivity
POD_NAME=$(kubectl get pod -l app=dividend-tracker -n default -o jsonpath='{.items[0].metadata.name}')
kubectl exec -n default $POD_NAME -- wget -q -O- http://mongodb:27017
```

#### Health Check Failures
```bash
# Check if health endpoint responds
kubectl exec -n default $POD_NAME -- curl -v http://localhost:5000/finance/health

# Check MongoDB from app pod
kubectl exec -n default $POD_NAME -- python3 -c "from pymongo import MongoClient; print(MongoClient('mongodb://mongodb:27017/').admin.command('ping'))"
```

## Resource Usage

### Application
- **Requests:** 256Mi memory, 200m CPU
- **Limits:** 512Mi memory, 1000m CPU
- **Replicas:** 2 (for high availability)

### MongoDB
- **Requests:** 256Mi memory, 200m CPU
- **Limits:** 512Mi memory, 500m CPU
- **Replicas:** 1 (single instance with PVC)

## Scaling

### Scale application pods
```bash
kubectl scale deployment dividend-tracker --replicas=3 -n default
```

**Note:** MongoDB uses a PVC with ReadWriteOnce access mode, so it can only have 1 replica. For high availability, consider MongoDB replica sets.

## Migration Checklist

- [x] Create Kubernetes manifests
- [x] Add health endpoint to application
- [x] Configure MongoDB with persistent storage
- [x] Update Jenkinsfile for k3s deployment
- [x] Configure secrets management
- [ ] Deploy to k3s cluster
- [ ] Verify application functionality
- [ ] Test rolling updates
- [ ] Remove old Docker Swarm service
- [ ] Update monitoring/alerting

## Rollback Plan

If issues occur, rollback to Docker Swarm:

1. **Redeploy to Swarm:**
```bash
# SSH to swarm manager
ssh jenkins@SWARM_MANAGER

# Deploy stack
docker stack deploy --with-registry-auth -c docker-compose.yml dividend-tracker
```

2. **Remove k8s resources:**
```bash
kubectl delete ingress dividend-tracker -n default
kubectl delete service dividend-tracker -n default
kubectl delete deployment dividend-tracker -n default
```

3. **Keep MongoDB data:**
Do NOT delete the PVC if you want to preserve data:
```bash
# Keep these for data preservation:
# kubectl delete deployment dividend-tracker-mongodb -n default
# kubectl delete pvc mongodb-pvc -n default
```

## Next Steps

1. Push changes to repository to trigger Jenkins build
2. Monitor deployment in Jenkins console
3. Verify application at `http://home.home/finance/`
4. Test all features (add asset, import CSV, view monthly breakdown)
5. Monitor logs for any errors
6. Once stable, remove Docker Swarm service:
   ```bash
   docker stack rm dividend-tracker
   ```
