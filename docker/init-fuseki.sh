#!/bin/bash
# Automatic Fuseki Initialization Script
# Creates dataset, loads ontology, and configures text indexing
# This script runs automatically when the Fuseki container starts

set -e

echo "=========================================="
echo "Contract KG - Fuseki Initialization"
echo "=========================================="

# Wait for Fuseki to be fully ready
echo "[INFO] Waiting for Fuseki to start..."
MAX_RETRIES=30
RETRY_COUNT=0

until curl -s http://localhost:3030/$/ping > /dev/null 2>&1; do
    RETRY_COUNT=$((RETRY_COUNT + 1))
    if [ $RETRY_COUNT -ge $MAX_RETRIES ]; then
        echo "[ERROR] Fuseki failed to start after ${MAX_RETRIES} attempts"
        exit 1
    fi
    echo "   Attempt $RETRY_COUNT/$MAX_RETRIES..."
    sleep 2
done

echo "[SUCCESS] Fuseki is ready!"
echo ""

# Check if dataset already exists
echo "[INFO] Checking for existing dataset..."
DATASET_EXISTS=$(curl -s -u admin:${ADMIN_PASSWORD:-admin123} \
    http://localhost:3030/$/datasets 2>/dev/null | grep -c '"ds.name" : "/contracts"' || true)

if [ "$DATASET_EXISTS" -gt 0 ]; then
    echo "[SUCCESS] Dataset 'contracts' already exists (skipping creation)"
else
    echo "[INFO] Creating 'contracts' dataset with TDB2 backend..."
    
    RESPONSE=$(curl -s -w "\n%{http_code}" -X POST http://localhost:3030/$/datasets \
        -u admin:${ADMIN_PASSWORD:-admin123} \
        -H "Content-Type: application/x-www-form-urlencoded" \
        -d "dbName=contracts&dbType=tdb2")
    
    HTTP_CODE=$(echo "$RESPONSE" | tail -n1)
    
    if [ "$HTTP_CODE" = "200" ] || [ "$HTTP_CODE" = "201" ]; then
        echo "[SUCCESS] Dataset 'contracts' created successfully"
    else
        echo "[WARNING] Dataset creation returned status: $HTTP_CODE"
        echo "          (This may be normal if dataset already exists)"
    fi
fi

echo ""

# Load ontology if available and not already loaded
echo "[INFO] Checking ontology..."
if [ -f /staging/ontology/procurement.owl ]; then
    # Check if ontology is already loaded (check for triples)
    TRIPLE_COUNT=$(curl -s -u admin:${ADMIN_PASSWORD:-admin123} \
        "http://localhost:3030/contracts/query" \
        -H "Accept: application/sparql-results+json" \
        --data-urlencode "query=SELECT (COUNT(*) as ?count) WHERE { ?s ?p ?o }" \
        2>/dev/null | grep -o '"value":"[0-9]*"' | head -1 | grep -o '[0-9]*' || echo "0")
    
    if [ "$TRIPLE_COUNT" -gt 100 ]; then
        echo "[SUCCESS] Ontology already loaded ($TRIPLE_COUNT triples found)"
    else
        echo "[INFO] Loading procurement ontology..."
        
        RESPONSE=$(curl -s -w "\n%{http_code}" -X POST \
            http://localhost:3030/contracts/data \
            -u admin:${ADMIN_PASSWORD:-admin123} \
            -H "Content-Type: application/rdf+xml" \
            --data-binary @/staging/ontology/procurement.owl)
        
        HTTP_CODE=$(echo "$RESPONSE" | tail -n1)
        
        if [ "$HTTP_CODE" = "200" ] || [ "$HTTP_CODE" = "201" ] || [ "$HTTP_CODE" = "204" ]; then
            echo "[SUCCESS] Ontology loaded successfully"
            
            # Verify load
            NEW_TRIPLE_COUNT=$(curl -s -u admin:${ADMIN_PASSWORD:-admin123} \
                "http://localhost:3030/contracts/query" \
                -H "Accept: application/sparql-results+json" \
                --data-urlencode "query=SELECT (COUNT(*) as ?count) WHERE { ?s ?p ?o }" \
                2>/dev/null | grep -o '"value":"[0-9]*"' | head -1 | grep -o '[0-9]*' || echo "0")
            
            echo "          Total triples: $NEW_TRIPLE_COUNT"
        else
            echo "[WARNING] Ontology load returned status: $HTTP_CODE"
        fi
    fi
else
    echo "[WARNING] Ontology file not found at /staging/ontology/procurement.owl"
fi

echo ""

# Load reasoning rules if available
echo "[INFO] Checking reasoning rules..."
if [ -f /staging/rules/procurement.rules ]; then
    echo "[SUCCESS] Reasoning rules found at /staging/rules/procurement.rules"
    echo "          (Rules will be loaded during ingestion pipeline)"
else
    echo "[WARNING] No reasoning rules found"
fi

echo ""
echo "=========================================="
echo "[SUCCESS] Fuseki Initialization Complete!"
echo "=========================================="
echo ""
echo "Service Information:"
echo "  - Fuseki UI:     http://localhost:3030"
echo "  - Dataset:       contracts"
echo "  - Query:         http://localhost:3030/contracts/query"
echo "  - Update:        http://localhost:3030/contracts/update"
echo "  - Credentials:   admin / ${ADMIN_PASSWORD:-admin123}"
echo ""
echo "Ready for ingestion pipeline!"
echo ""
