# Helm Deployment Issues and Fixes for Milvus Data Ingestion

## 🔴 Critical Issues Found

### Issue 1: Missing Namespace in milvus-pvc (Line 16)
**Problem**: The `milvus-pvc` PersistentVolumeClaim is missing the `namespace: contract-kg` field.
**Impact**: PVC will be created in the default namespace, but Milvus deployment expects it in `contract-kg` namespace.
**Fix**: Add namespace field to milvus-pvc metadata.

### Issue 2: Conflicting/Duplicate Configuration in ConfigMap
**Problem**: The `agents-env-config` ConfigMap has duplicate and conflicting settings:
- Lines 38-42: First set of Fuseki config
- Lines 190-252: Commented duplicate config with different values
- Line 59: `WATSONX_MODEL_ID=meta-llama/llama-3-3-70b-instruct` (SLOW model)
- Line 200: Commented `WATSONX_MODEL_ID=openai/gpt-oss-120b`

**Impact**: 
- Using the slow Llama-3.3-70B model (4+ hours for 178 files)
- Confusion about which settings are active
- Potential runtime errors from conflicting values

### Issue 3: Wrong Ontology Path in ConfigMap
**Problem**: Line 86 and 224 reference old ontology path:
```
ONTOLOGY_PATH=minio://procurement-contracts/ontology/base/procurement.owl
```
**Impact**: System will try to load old ontology from MinIO instead of new custom ontology files.
**Required**: Update to use new ontology files from container image.

### Issue 4: Schema Evolution Still Enabled
**Problem**: Lines 133-134 in ConfigMap:
```
GENERATE_OWL_EXTENSIONS=true
GENERATE_RULES=true
```
**Impact**: System will still try to generate dynamic ontology files, contradicting user's requirement.
**Required**: Set both to `false`.

### Issue 5: Missing Custom Ontology Files in Container
**Problem**: The new ontology files (`contract.owl` and `contract-clauses.ttl`) are in the local codebase but may not be in the container image `us.icr.io/projects-common-registry-ns/grag-contract-analysis-docling:v3`.
**Impact**: Even with correct paths, files won't exist in the running container.
**Required**: Rebuild container image with new ontology files.

### Issue 6: Milvus Collection Name Mismatch
**Problem**: Multiple collection names used inconsistently:
- Line 70: `MILVUS_COLLECTION=contract_clauses`
- Line 71: `MILVUS_COLLECTION_V2=contract_clauses_v2`
- Line 99: `RETRIEVAL_MILVUS_COLLECTION=contract_clauses_v2`
- Line 102: `DOCLING_MILVUS_COLLECTION=contract_clauses_docling`

**Impact**: Data might be written to one collection but read from another.

### Issue 7: Etcd Connection String Inconsistency
**Problem**: Line 23 in milvus.yaml uses full FQDN:
```
ETCD_ENDPOINTS=http://etcd.contract-kg.svc.cluster.local:2379
```
But etcd advertises itself as just `http://etcd:2379` (line 30 in etcd.yaml).

**Impact**: Milvus might fail to connect to etcd, preventing startup.

## ✅ Required Fixes

### Fix 1: Update pvc.yaml
```yaml
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: milvus-pvc
  namespace: contract-kg  # ADD THIS LINE
spec:
  accessModes:
    - ReadWriteOnce
  resources:
    requests:
      storage: 20Gi  # Increase from 2Gi to match values.yaml
```

### Fix 2: Clean Up and Update ConfigMap
Remove all commented duplicate config (lines 190-252) and update active config:

```yaml
# LLM Configuration - USE FASTER MODEL
WATSONX_MODEL_ID=mistralai/mistral-small-3-1-24b-instruct-2503  # 5-10x faster than Llama-3.3-70B
# OR if you prefer OpenAI model:
# WATSONX_MODEL_ID=openai/gpt-oss-120b

# Ontology Configuration - USE NEW CUSTOM ONTOLOGY
ONTOLOGY_PATH=src/agents/ingestion/new_ontology/contract.owl
ONTOLOGY_TTL_PATH=src/agents/ingestion/new_ontology/contract-clauses.ttl

# Schema Evolution - DISABLE DYNAMIC GENERATION
GENERATE_OWL_EXTENSIONS=false
GENERATE_RULES=false
ONTOLOGY_EVOLUTION_MODE=conservative  # Change from adaptive

# Milvus Collection - USE CONSISTENT NAME
MILVUS_COLLECTION=contract_clauses_v2
RETRIEVAL_MILVUS_COLLECTION=contract_clauses_v2
DOCLING_MILVUS_COLLECTION=contract_clauses_v2
```

### Fix 3: Update Milvus Deployment
```yaml
env:
  - name: ETCD_ENDPOINTS
    value: http://etcd:2379  # Simplified, matches etcd advertise URL
```

### Fix 4: Rebuild Container Image
The container image must include the new ontology files. Update your Dockerfile or build process:

```dockerfile
# In your Dockerfile, ensure these files are copied:
COPY agents/src/agents/ingestion/new_ontology/contract.owl /app/src/agents/ingestion/new_ontology/
COPY agents/src/agents/ingestion/new_ontology/contract-clauses.ttl /app/src/agents/ingestion/new_ontology/
```

Then rebuild and push:
```bash
docker build -t us.icr.io/projects-common-registry-ns/grag-contract-analysis-docling:v4 .
docker push us.icr.io/projects-common-registry-ns/grag-contract-analysis-docling:v4
```

Update ingestion-api.yaml to use new image:
```yaml
image: us.icr.io/projects-common-registry-ns/grag-contract-analysis-docling:v4
```

## 🔍 Why Data Isn't Reaching Milvus

Based on the configuration analysis, here are the likely reasons:

1. **Milvus Can't Start**: Etcd connection failure due to FQDN mismatch
2. **Wrong Collection**: Data written to `contract_clauses_docling` but you're checking `contract_clauses_v2`
3. **Ontology Loading Fails**: System tries to load old ontology from MinIO, fails, and ingestion stops
4. **PVC Namespace Mismatch**: Milvus can't mount storage, fails to start
5. **Container Missing Files**: New ontology files don't exist in v3 image

## 📋 Deployment Checklist

- [ ] Fix milvus-pvc namespace in `templates/pvc.yaml`
- [ ] Increase milvus-pvc storage to 20Gi
- [ ] Clean up ConfigMap - remove duplicate config
- [ ] Update WATSONX_MODEL_ID to faster model
- [ ] Update ONTOLOGY_PATH to new custom ontology
- [ ] Set GENERATE_OWL_EXTENSIONS=false
- [ ] Set GENERATE_RULES=false
- [ ] Standardize MILVUS_COLLECTION names
- [ ] Fix ETCD_ENDPOINTS in milvus.yaml
- [ ] Rebuild container image with new ontology files
- [ ] Update ingestion-api.yaml to use new image tag
- [ ] Deploy updated Helm chart
- [ ] Verify all pods are running: `kubectl get pods -n contract-kg`
- [ ] Check Milvus logs: `kubectl logs -n contract-kg deployment/milvus`
- [ ] Check ingestion-api logs: `kubectl logs -n contract-kg deployment/ingestion-api`
- [ ] Verify Milvus collection exists: Connect to Attu UI or use Milvus CLI

## 🚀 Recommended Deployment Steps

1. **Update Helm Charts** (apply all fixes above)
2. **Rebuild Container Image** with new ontology files
3. **Deploy to OpenShift**:
   ```bash
   helm upgrade --install contract-kg ./helm-grag -n contract-kg --create-namespace
   ```
4. **Verify Deployment**:
   ```bash
   kubectl get pods -n contract-kg
   kubectl get pvc -n contract-kg
   ```
5. **Check Logs**:
   ```bash
   kubectl logs -n contract-kg deployment/milvus -f
   kubectl logs -n contract-kg deployment/ingestion-api -f
   ```
6. **Test Ingestion**: Upload a test document and verify data appears in Milvus

## 📊 Expected Performance (After Fixes)

With proper configuration and faster model:
- **Local Docker**: 60-70 minutes for 178 files
- **OpenShift (3 replicas)**: 15-20 minutes for 178 files
- **Processing Rate**: 3-5 files/minute per pod

## 🔧 Debugging Commands

```bash
# Check if Milvus is running
kubectl get pods -n contract-kg | grep milvus

# Check Milvus logs for errors
kubectl logs -n contract-kg deployment/milvus --tail=100

# Check if etcd is accessible from Milvus pod
kubectl exec -n contract-kg deployment/milvus -- curl http://etcd:2379/health

# Check if PVCs are bound
kubectl get pvc -n contract-kg

# Check ingestion API logs
kubectl logs -n contract-kg deployment/ingestion-api --tail=100 | grep -i milvus

# Port-forward to Attu UI to inspect Milvus
kubectl port-forward -n contract-kg svc/attu 8080:80
# Then open http://localhost:8080 in browser