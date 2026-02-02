# Deployment Guide

Guide for deploying the Contract Knowledge Graph system to production.

## Deployment Options

### 1. Docker Compose (Recommended for Development)

Simple deployment using Docker Compose.

**Prerequisites:**
- Docker 20.10+
- Docker Compose 2.0+

**Steps:**

```bash
# Clone repository
git clone https://github.com/your-org/contract-jena.git
cd contract-jena

# Configure environment
cp agents/env.example agents/.env
# Edit .env with production settings

# Start services
docker-compose up -d

# Verify services
docker-compose ps
```

**Services:**
- Fuseki: http://localhost:3030
- Milvus: localhost:19530
- Phoenix: http://localhost:6006

### 2. Kubernetes (Recommended for Production)

Scalable deployment using Kubernetes.

**Prerequisites:**
- Kubernetes cluster
- kubectl configured
- Helm 3.0+

**Deployment:**

```bash
# Add Helm repositories
helm repo add bitnami https://charts.bitnami.com/bitnami
helm repo update

# Deploy Fuseki
helm install fuseki bitnami/apache \
  --set service.type=LoadBalancer \
  --set persistence.enabled=true

# Deploy Milvus
helm install milvus milvus/milvus \
  --set cluster.enabled=true \
  --set persistence.enabled=true

# Deploy application
kubectl apply -f k8s/
```

### 3. Cloud Platforms

#### AWS

```bash
# Use ECS/EKS for container orchestration
# RDS for PostgreSQL (if needed)
# S3 for document storage
# CloudWatch for monitoring
```

#### Azure

```bash
# Use AKS for Kubernetes
# Azure Database for PostgreSQL
# Blob Storage for documents
# Application Insights for monitoring
```

#### IBM Cloud

```bash
# Use IBM Cloud Kubernetes Service
# IBM Cloud Databases
# IBM Cloud Object Storage
# IBM Cloud Monitoring
```

## Configuration

### Environment Variables

```bash
# .env for production
# LLM Provider
LLM_PROVIDER=watsonx
WATSONX_API_KEY=your_production_key
WATSONX_PROJECT_ID=your_project_id
WATSONX_URL=https://us-south.ml.cloud.ibm.com
WATSONX_MODEL=ibm/granite-13b-chat-v2

# Fuseki
FUSEKI_ENDPOINT=http://fuseki:3030/contracts
FUSEKI_USERNAME=admin
FUSEKI_PASSWORD=secure_password

# Milvus
MILVUS_HOST=milvus
MILVUS_PORT=19530

# Phoenix
PHOENIX_ENDPOINT=http://phoenix:6006
ENABLE_PHOENIX_TRACING=true

# Performance
ENABLE_QUERY_CACHE=true
CACHE_TTL_SECONDS=300
CONNECTION_POOL_SIZE=10
LAZY_LOAD_EMBEDDINGS=true

# Logging
LOG_LEVEL=INFO
LOG_FORMAT=json
```

### Docker Compose Production

```yaml
# docker-compose.prod.yml
version: '3.8'

services:
  fuseki:
    image: stain/jena-fuseki:latest
    ports:
      - "3030:3030"
    volumes:
      - fuseki-data:/fuseki
      - ./docker/fuseki-config.ttl:/fuseki/config.ttl
    environment:
      - ADMIN_PASSWORD=${FUSEKI_PASSWORD}
      - JVM_ARGS=-Xmx4g
    restart: always
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:3030/$/ping"]
      interval: 30s
      timeout: 10s
      retries: 3

  milvus:
    image: milvusdb/milvus:latest
    ports:
      - "19530:19530"
    volumes:
      - milvus-data:/var/lib/milvus
    environment:
      - ETCD_ENDPOINTS=etcd:2379
    restart: always
    depends_on:
      - etcd

  etcd:
    image: quay.io/coreos/etcd:latest
    volumes:
      - etcd-data:/etcd
    command: etcd -advertise-client-urls=http://127.0.0.1:2379 -listen-client-urls http://0.0.0.0:2379
    restart: always

  phoenix:
    image: arizephoenix/phoenix:latest
    ports:
      - "6006:6006"
    environment:
      - PHOENIX_PORT=6006
    restart: always

  app:
    build:
      context: .
      dockerfile: Dockerfile
    ports:
      - "8000:8000"
    volumes:
      - ./agents:/app/agents
      - app-logs:/app/logs
    environment:
      - FUSEKI_ENDPOINT=http://fuseki:3030/contracts
      - MILVUS_HOST=milvus
      - PHOENIX_ENDPOINT=http://phoenix:6006
    depends_on:
      - fuseki
      - milvus
      - phoenix
    restart: always

volumes:
  fuseki-data:
  milvus-data:
  etcd-data:
  app-logs:
```

## Scaling

### Horizontal Scaling

```yaml
# docker-compose.scale.yml
services:
  app:
    deploy:
      replicas: 3
      resources:
        limits:
          cpus: '2'
          memory: 4G
        reservations:
          cpus: '1'
          memory: 2G
```

### Load Balancing

```yaml
# nginx.conf
upstream app_servers {
    least_conn;
    server app1:8000;
    server app2:8000;
    server app3:8000;
}

server {
    listen 80;
    
    location / {
        proxy_pass http://app_servers;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

### Auto-scaling (Kubernetes)

```yaml
# k8s/hpa.yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: app-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: app
  minReplicas: 2
  maxReplicas: 10
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
  - type: Resource
    resource:
      name: memory
      target:
        type: Utilization
        averageUtilization: 80
```

## Monitoring

### Prometheus

```yaml
# prometheus.yml
global:
  scrape_interval: 15s

scrape_configs:
  - job_name: 'app'
    static_configs:
      - targets: ['app:8000']
  
  - job_name: 'fuseki'
    static_configs:
      - targets: ['fuseki:3030']
  
  - job_name: 'milvus'
    static_configs:
      - targets: ['milvus:9091']
```

### Grafana Dashboards

```yaml
# grafana-dashboard.json
{
  "dashboard": {
    "title": "Contract KG Metrics",
    "panels": [
      {
        "title": "Query Latency",
        "targets": [
          {
            "expr": "histogram_quantile(0.95, rate(query_duration_seconds_bucket[5m]))"
          }
        ]
      },
      {
        "title": "Cache Hit Rate",
        "targets": [
          {
            "expr": "rate(cache_hits_total[5m]) / rate(cache_requests_total[5m])"
          }
        ]
      }
    ]
  }
}
```

### Health Checks

```python
# health.py
from fastapi import FastAPI
from storage.sparql.fuseki_store import FusekiStore
from storage.vector.milvus_store import MilvusStore

app = FastAPI()

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    checks = {
        "fuseki": check_fuseki(),
        "milvus": check_milvus(),
        "phoenix": check_phoenix()
    }
    
    all_healthy = all(checks.values())
    
    return {
        "status": "healthy" if all_healthy else "unhealthy",
        "checks": checks
    }

def check_fuseki():
    try:
        store = FusekiStore()
        store.query("SELECT * WHERE { ?s ?p ?o } LIMIT 1")
        return True
    except:
        return False
```

## Backup and Recovery

### Fuseki Backup

```bash
# Backup script
#!/bin/bash
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="/backups/fuseki"

# Stop Fuseki
docker-compose stop fuseki

# Backup data
tar -czf $BACKUP_DIR/fuseki_$DATE.tar.gz /fuseki/databases

# Start Fuseki
docker-compose start fuseki

# Keep last 7 days
find $BACKUP_DIR -name "fuseki_*.tar.gz" -mtime +7 -delete
```

### Milvus Backup

```bash
# Backup Milvus
#!/bin/bash
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="/backups/milvus"

# Create backup
docker exec milvus /bin/bash -c "milvus-backup create --name backup_$DATE"

# Export backup
docker cp milvus:/var/lib/milvus/backup $BACKUP_DIR/
```

### Automated Backups

```yaml
# k8s/cronjob-backup.yaml
apiVersion: batch/v1
kind: CronJob
metadata:
  name: backup-job
spec:
  schedule: "0 2 * * *"  # Daily at 2 AM
  jobTemplate:
    spec:
      template:
        spec:
          containers:
          - name: backup
            image: backup-image:latest
            command: ["/backup.sh"]
            volumeMounts:
            - name: backup-volume
              mountPath: /backups
          restartPolicy: OnFailure
          volumes:
          - name: backup-volume
            persistentVolumeClaim:
              claimName: backup-pvc
```

## Security

### SSL/TLS

```yaml
# nginx-ssl.conf
server {
    listen 443 ssl http2;
    server_name api.example.com;
    
    ssl_certificate /etc/nginx/ssl/cert.pem;
    ssl_certificate_key /etc/nginx/ssl/key.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
    
    location / {
        proxy_pass http://app_servers;
    }
}
```

### Authentication

```python
# auth.py
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

security = HTTPBearer()

async def verify_token(
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """Verify JWT token."""
    token = credentials.credentials
    
    if not validate_token(token):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials"
        )
    
    return token
```

### Secrets Management

```bash
# Use Kubernetes secrets
kubectl create secret generic app-secrets \
  --from-literal=watsonx-api-key=your_key \
  --from-literal=fuseki-password=your_password

# Reference in deployment
env:
  - name: WATSONX_API_KEY
    valueFrom:
      secretKeyRef:
        name: app-secrets
        key: watsonx-api-key
```

## Performance Tuning

### JVM Settings (Fuseki)

```bash
# Increase heap size
JVM_ARGS="-Xmx8g -Xms4g -XX:+UseG1GC"
```

### Milvus Configuration

```yaml
# milvus.yaml
dataCoord:
  segment:
    maxSize: 1024  # MB
    sealProportion: 0.25

queryNode:
  cacheSize: 32  # GB
  
indexNode:
  buildParallel: 4
```

### Application Tuning

```python
# config.py
class ProductionSettings(Settings):
    # Connection pools
    fuseki_pool_size: int = 20
    milvus_pool_size: int = 20
    
    # Caching
    enable_query_cache: bool = True
    cache_ttl_seconds: int = 600
    cache_max_size: int = 2000
    
    # Performance
    lazy_load_embeddings: bool = True
    batch_size: int = 100
```

## Troubleshooting

### Common Issues

**1. Out of Memory**
```bash
# Increase container memory
docker-compose up -d --scale app=1 --memory=8g
```

**2. Slow Queries**
```bash
# Check Fuseki statistics
curl http://localhost:3030/$/stats

# Enable query logging
LOG_LEVEL=DEBUG
```

**3. Connection Timeouts**
```bash
# Increase timeouts
FUSEKI_TIMEOUT=60
MILVUS_TIMEOUT=60
```

## Rollback

### Docker Compose

```bash
# Rollback to previous version
docker-compose down
docker-compose pull app:previous-tag
docker-compose up -d
```

### Kubernetes

```bash
# Rollback deployment
kubectl rollout undo deployment/app

# Rollback to specific revision
kubectl rollout undo deployment/app --to-revision=2
```

## See Also

- [Contributing Guide](../development/contributing.md)
- [Testing Guide](../development/testing.md)
- [Performance Optimizations](../performance/optimizations.md)