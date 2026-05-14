#!/bin/bash
# Update Milvus Schema with Contract Metadata
# This script:
# 1. Drops the old Milvus collection
# 2. Rebuilds the Docker image with updated code
# 3. Restarts the services

set -e  # Exit on error

echo "================================================"
echo "Updating Milvus Schema with Contract Metadata"
echo "================================================"

# Change to docker directory
cd "$(dirname "$0")/../docker"

echo ""
echo "Step 1: Dropping old Milvus collection..."
echo "----------------------------------------"

# Drop collection using Python in the running container
docker exec contract-kg-ingestion-api python -c "
from pymilvus import connections, utility
try:
    connections.connect(host='milvus', port=19530)
    if utility.has_collection('contract_clauses_v2'):
        utility.drop_collection('contract_clauses_v2')
        print('✅ Dropped collection: contract_clauses_v2')
    else:
        print('ℹ️  Collection does not exist yet')
except Exception as e:
    print(f'⚠️  Could not drop collection: {e}')
    print('   (This is OK if collection does not exist)')
" || echo "⚠️  Could not connect to drop collection (will be created fresh)"

echo ""
echo "Step 2: Rebuilding Docker images with updated code..."
echo "-----------------------------------------------------"

# Rebuild the agents image (contains the updated milvus_store.py)
docker-compose build ingestion-api retrieval-api

echo ""
echo "Step 3: Restarting services..."
echo "------------------------------"

# Restart the services
docker-compose up -d ingestion-api retrieval-api

echo ""
echo "Step 4: Waiting for services to be ready..."
echo "-------------------------------------------"

# Wait for services to be healthy
sleep 10

echo ""
echo "✅ Update complete!"
echo ""
echo "The new Milvus collection will be created automatically with:"
echo "  - 29 total fields"
echo "  - 15 contract metadata fields (contract_id, supplier_name, owner_name, etc.)"
echo "  - 4 DocTags fields"
echo "  - 9 basic fields + 1 embedding field"
echo ""
echo "Next steps:"
echo "  1. Check Milvus UI: http://localhost:8081"
echo "  2. Run ingestion with cacheview_path parameter"
echo "  3. Verify metadata is populated in queries"
echo ""
echo "To check the schema:"
echo "  docker exec contract-kg-ingestion-api python -c \\"
echo "    \"from pymilvus import connections, Collection; \\"
echo "    connections.connect(host='milvus', port=19530); \\"
echo "    c = Collection('contract_clauses_v2'); \\"
echo "    print(f'Fields: {len(c.schema.fields)}'); \\"
echo "    [print(f'  - {f.name}') for f in c.schema.fields]\""
echo ""

# Made with Bob
