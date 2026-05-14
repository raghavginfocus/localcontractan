# 🚨 CRITICAL: Ontology Namespace Mismatch

## The Problem

Your ontology and RDF generator use **different namespaces**:

| Component | Namespace | Prefix |
|-----------|-----------|--------|
| **contract-clauses.ttl** | `http://example.org/contract-intelligence#` | `ex:` |
| **contract.owl** | `http://example.org/contract-intelligence#` | (default) |
| **RDF Generator** | `http://procurement.kg/ontology#` | `PROC` |

## Why This Breaks Everything

1. RDF Generator creates: `proc:contractId "CW3166453"`
2. Ontology defines: `ex:contractId`
3. Fuseki sees undefined property `proc:contractId`
4. Fuseki rejects/ignores the triple
5. Database stays empty
6. SPARQL queries find nothing
7. Retrieval fails

## The Fix

You have **2 options**:

### Option 1: Change Ontology Namespace (RECOMMENDED)

**In `contract-clauses.ttl` line 1:**
```turtle
# CHANGE FROM:
@prefix ex: <http://example.org/contract-intelligence#> .

# TO:
@prefix proc: <http://procurement.kg/ontology#> .
```

**Then replace ALL `ex:` with `proc:` throughout the file**

**In `contract.owl` line 5-6:**
```xml
<!-- CHANGE FROM: -->
<rdf:RDF xmlns="http://example.org/contract-intelligence#"
     xml:base="http://example.org/contract-intelligence"

<!-- TO: -->
<rdf:RDF xmlns="http://procurement.kg/ontology#"
     xml:base="http://procurement.kg/ontology"
```

### Option 2: Change RDF Generator Namespace

**In `agents/src/agents/ingestion/rdf_generator.py` line 38:**
```python
# CHANGE FROM:
PROC = Namespace("http://procurement.kg/ontology#")

# TO:
PROC = Namespace("http://example.org/contract-intelligence#")
```

**⚠️ WARNING**: This requires re-ingesting ALL existing data!

## Recommendation

**Use Option 1** (change ontology) because:
- ✅ No code changes needed
- ✅ Less risky
- ✅ Matches existing RDF data structure
- ✅ Standard practice (ontology adapts to implementation)

## After the Fix

1. ✅ RDF Generator creates: `proc:contractId "CW3166453"`
2. ✅ Ontology defines: `proc:contractId`
3. ✅ Fuseki accepts the triple
4. ✅ Database gets populated
5. ✅ SPARQL queries work
6. ✅ Retrieval returns results

## Quick Test

After fixing, verify with:

```bash
# 1. Restart services
docker-compose restart fuseki ingestion-api

# 2. Ingest a contract
curl -X POST http://localhost:8001/ingest \
  -H "Content-Type: application/json" \
  -d '{"file_path": "/app/examples/contract.pdf", "cacheview_path": "/app/data/cacheview.json"}'

# 3. Check Fuseki has data
curl "http://localhost:3030/procurement/sparql?query=SELECT%20(COUNT(*))%20WHERE%20{%20?s%20a%20<http://procurement.kg/ontology%23Contract>%20}"

# Should return a count > 0
```

## Files to Update

If using Option 1 (recommended):
- [ ] `agents/src/agents/ingestion/new_ontology/contract-clauses.ttl`
- [ ] `agents/src/agents/ingestion/new_ontology/contract.owl`

If using Option 2:
- [ ] `agents/src/agents/ingestion/rdf_generator.py`