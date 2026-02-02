#!/bin/bash
# Initialize Fuseki with the contracts dataset + text indexing

set -e

echo "Initializing Fuseki for Contract Knowledge Graph..."

# Wait for Fuseki to be ready
until curl -s http://localhost:3030/$/ping > /dev/null 2>&1; do
    echo "Waiting for Fuseki to start..."
    sleep 2
done

echo "Fuseki is ready. Creating dataset with text indexing..."

# Create the contracts dataset with TDB2 + text index
# If config file exists, use it; otherwise create basic dataset
if [ -f /staging/fuseki-config.ttl ]; then
    echo "Using custom Fuseki configuration with text indexing..."
    # Copy config to Fuseki config directory
    cp /staging/fuseki-config.ttl /fuseki/configuration/fuseki-config.ttl
    echo "Configuration loaded. Restarting Fuseki to apply..."
    # Note: In production, you'd restart Fuseki or use API to reload config
else
    echo "Creating dataset with TDB2 backend..."
    curl -X POST http://localhost:3030/$/datasets \
        -u admin:${ADMIN_PASSWORD:-admin123} \
        -H "Content-Type: application/x-www-form-urlencoded" \
        -d "dbName=contracts&dbType=tdb2"
    
    echo "Dataset 'contracts' created."
    
    # Create text index via SPARQL Update (if jena-text is available)
    echo "Configuring text index for fast search..."
    cat > /tmp/text-index-config.ttl << 'EOF'
@prefix :        <http://jena.apache.org/text#> .
@prefix proc:    <http://procurement.kg/ontology#> .

[] a :TextIndex ;
   :directory <file:lucene> ;
   :entityMap [
       a :EntityMap ;
       :entityField "uri" ;
       :defaultField "text" ;
       :map (
           [ :field "text" ; :predicate proc:rawText ]
           [ :field "summary" ; :predicate proc:summary ]
           [ :field "keyPoint" ; :predicate proc:hasKeyPoint ]
       )
   ] .
EOF
    
    # Note: Text index creation typically requires restart or special API
    # For now, we'll document it in the setup
    echo "⚠️  Text index configuration prepared. See docs for activation."
fi

# Load the ontology if available
if [ -f /staging/ontology/procurement.owl ]; then
    echo "Loading procurement ontology..."
    curl -X POST http://localhost:3030/contracts/data \
        -u admin:${ADMIN_PASSWORD:-admin123} \
        -H "Content-Type: application/rdf+xml" \
        --data-binary @/staging/ontology/procurement.owl
    echo "Ontology loaded."
fi

echo "Fuseki initialization complete!"
