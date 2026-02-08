# Deployment Checklist - Dividend Tracker k3s Migration

## ✅ Pre-Deployment (Completed)

- [x] Health endpoint added to Flask app (`/finance/health`)
- [x] Health endpoint checks MongoDB connectivity
- [x] Kubernetes manifests created (6 files)
- [x] MongoDB configured with PersistentVolumeClaim (5Gi)
- [x] Jenkinsfile updated for k3s deployment
- [x] Documentation created (migration guide, summary, this checklist)
- [x] Verification script created (`verify-deployment.sh`)
- [x] Base path handling verified (`APPLICATION_ROOT='/finance'`)
- [x] All stylesheets inline (no external file issues)

## 📋 Pre-Deployment Verification

### Jenkins Prerequisites
- [ ] Jenkins credential `k3s-kubeconfig` exists (file)
- [ ] Jenkins credential `docker-registry-credentials` exists (username/password)
- [ ] Jenkins credential `alpha-vantage-key` exists (string, optional)
- [ ] jenkins-sentinel library configured

Verify at: `https://your-jenkins/credentials/`

### k3s Prerequisites
- [ ] k3s cluster is accessible via kubectl
  ```bash
  kubectl get nodes
  ```
- [ ] k3s registry configured for insecure registry
  ```bash
  sudo crictl pull 192.168.1.23:5000/test:latest
  ```
- [ ] kubectl has access to default namespace
  ```bash
  kubectl get pods -n default
  ```

## 🚀 Deployment Steps

### Step 1: Commit Changes
```bash
cd /Users/aaron/projects/dividend-tracker

# Review changes
git status
git diff app.py
git diff Jenkinsfile

# Add all migration files
git add kubernetes/ \
        app.py \
        Jenkinsfile \
        K8S_MIGRATION.md \
        MIGRATION_SUMMARY.md \
        DEPLOYMENT_CHECKLIST.md \
        verify-deployment.sh

# Commit with descriptive message
git commit -m "Migrate dividend-tracker to k3s

- Add health endpoint with MongoDB connectivity check
- Create Kubernetes manifests (deployment, service, ingress)
- Configure MongoDB with persistent storage (PVC)
- Update Jenkinsfile for k3s deployment with rolling updates
- Add comprehensive health checks and probes
- Document migration and troubleshooting
- Add deployment verification script

Migrating from Docker Swarm to k3s native deployment.

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"

# Push to trigger Jenkins
git push origin main
```

### Step 2: Monitor Jenkins Build
- [ ] Navigate to Jenkins dashboard
- [ ] Find dividend-tracker job
- [ ] Watch console output
- [ ] Verify all stages pass:
  - [ ] Checkout
  - [ ] Build Docker Image
  - [ ] Push to Registry
  - [ ] Deploy to k3s
  - [ ] Verify Health

### Step 3: Verify Deployment
```bash
# Run verification script
./verify-deployment.sh

# Or manually check:
kubectl get pods -l app=dividend-tracker -n default
kubectl get pods -l app=dividend-tracker-mongodb -n default
kubectl get svc -n default
kubectl get ingress -n default
```

Expected output:
```
NAME                                      READY   STATUS    RESTARTS   AGE
dividend-tracker-mongodb-xxxxxxxxx-xxxxx   1/1     Running   0          5m
dividend-tracker-xxxxxxxxx-xxxxx           1/1     Running   0          3m
dividend-tracker-xxxxxxxxx-xxxxx           1/1     Running   0          3m
```

### Step 4: Test Health Endpoint
```bash
# From within cluster
POD=$(kubectl get pod -l app=dividend-tracker -n default -o jsonpath='{.items[0].metadata.name}')
kubectl exec -n default $POD -- wget -q -O- http://localhost:5000/finance/health

# From outside cluster
curl http://home.home/finance/health
```

Expected response:
```json
{
  "status": "healthy",
  "app": "dividend-tracker",
  "database": "connected"
}
```

### Step 5: Test Application
- [ ] Open browser: `http://home.home/finance/`
- [ ] Verify UI loads correctly
- [ ] Add a test asset (e.g., AAPL with 10 shares)
- [ ] Verify asset appears in list
- [ ] Check monthly breakdown shows correct data
- [ ] Verify portfolio value calculates correctly
- [ ] Test edit functionality
- [ ] Test delete functionality
- [ ] Test CSV import (optional)

### Step 6: Test Rolling Update
```bash
# Make a small change to app (e.g., update a log message)
# Commit and push
git add .
git commit -m "Test rolling update"
git push origin main

# Watch rollout
kubectl rollout status deployment/dividend-tracker -n default

# Verify zero downtime - check pods
kubectl get pods -l app=dividend-tracker -n default -w
```

Expected: Old pods stay running until new pods are ready

## 🔍 Post-Deployment Monitoring (First 24-48 Hours)

### Monitor Logs
```bash
# Application logs
kubectl logs -l app=dividend-tracker -n default -f

# MongoDB logs
kubectl logs -l app=dividend-tracker-mongodb -n default -f

# Recent events
kubectl get events --sort-by=.lastTimestamp -n default
```

### Check Metrics
```bash
# Resource usage
kubectl top pods -l app=dividend-tracker -n default

# Pod status over time
watch kubectl get pods -l app=dividend-tracker -n default
```

### Things to Watch For
- [ ] No CrashLoopBackOff errors
- [ ] No ImagePullBackOff errors
- [ ] Health checks passing consistently
- [ ] No MongoDB connection errors
- [ ] Response times acceptable
- [ ] Data persists across restarts

## 🧪 Data Persistence Test

```bash
# Add an asset via UI
# Note the asset name (e.g., TEST)

# Delete application pods (data should persist in MongoDB)
kubectl delete pod -l app=dividend-tracker -n default

# Wait for pods to restart
kubectl wait --for=condition=ready pod -l app=dividend-tracker -n default --timeout=120s

# Verify asset still exists
# Open http://home.home/finance/ and check for TEST asset
```

- [ ] Data persists after app pod restart
- [ ] MongoDB data is on PVC

## 📊 Performance Testing

### Load Test (Optional)
```bash
# Simple load test
for i in {1..100}; do
  curl -s http://home.home/finance/health > /dev/null &
done
wait

# Check pod status
kubectl get pods -l app=dividend-tracker -n default
```

- [ ] Application handles concurrent requests
- [ ] No pod restarts during load
- [ ] Response times remain reasonable

## 🔄 Rollback Plan (If Needed)

If critical issues occur:

### Option 1: Rollback k8s Deployment
```bash
# View deployment history
kubectl rollout history deployment/dividend-tracker -n default

# Rollback to previous version
kubectl rollout undo deployment/dividend-tracker -n default

# Or rollback to specific revision
kubectl rollout undo deployment/dividend-tracker -n default --to-revision=1
```

### Option 2: Revert to Docker Swarm
```bash
# Revert git commit
git revert HEAD
git push origin main

# SSH to swarm manager and redeploy
ssh jenkins@SWARM_MANAGER
docker stack deploy --with-registry-auth -c docker-compose.yml dividend-tracker
```

## ✨ Success Criteria

Mark deployment as successful when:

- [ ] All Jenkins stages pass
- [ ] All pods are in Running state (1/1 or 2/2 Ready)
- [ ] Health endpoint returns 200 OK
- [ ] Application accessible at `http://home.home/finance/`
- [ ] All features work (add, edit, delete, import)
- [ ] Data persists across pod restarts
- [ ] Rolling updates work without downtime
- [ ] No errors in logs for 24 hours
- [ ] MongoDB PVC is bound and working

## 🧹 Cleanup (After Stable for 1 Week)

When k3s deployment is proven stable:

### Remove Docker Swarm Service
```bash
ssh jenkins@SWARM_MANAGER

# Stop and remove stack
docker stack rm dividend-tracker

# Verify removal
docker stack ls
docker service ls | grep dividend

# Optional: Clean up old images
docker image prune -a
```

### Archive Old Configuration
```bash
# In repository
mkdir -p archive/swarm
git mv docker-compose.yml archive/swarm/
git commit -m "Archive Docker Swarm configuration"
git push origin main
```

- [ ] Docker Swarm service removed
- [ ] Old configuration archived
- [ ] Update documentation to remove Swarm references

## 📞 Support & Troubleshooting

If issues occur, refer to:

1. **K8S_MIGRATION.md** - Comprehensive troubleshooting guide
2. **Jenkins Console** - Build output and error messages
3. **Kubernetes Events** - `kubectl get events --sort-by=.lastTimestamp -n default`
4. **Application Logs** - `kubectl logs -l app=dividend-tracker -n default`
5. **MongoDB Logs** - `kubectl logs -l app=dividend-tracker-mongodb -n default`

### Common Issues

| Issue | Check | Fix |
|-------|-------|-----|
| ImagePullBackOff | Registry access | Verify k3s registry config |
| CrashLoopBackOff | App logs | Check MongoDB connection |
| MongoDB not starting | PVC status | Check storage availability |
| Health checks failing | Health endpoint | Test endpoint manually |
| 404 errors | Ingress config | Verify path and host |

## 📝 Notes

- **MongoDB Data:** Stored in PVC `mongodb-pvc` (5Gi)
- **Backup Strategy:** Document in `K8S_MIGRATION.md` backup section
- **Scaling:** Can scale app to 3+ replicas, MongoDB limited to 1 (PVC limitation)
- **Updates:** Git push triggers automatic deployment via Jenkins
- **Access:** Application at `http://home.home/finance/`

---

**Last Updated:** 2026-02-08
**Migration Status:** Ready for Deployment
**Next Step:** Commit and push changes to trigger Jenkins build
