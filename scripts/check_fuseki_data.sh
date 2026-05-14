#!/bin/bash
# Check if Fuseki has data

echo "=== Checking Fuseki Data ==="
echo ""

FUSEKI_URL="${FUSEKI_URL:-https://fuseki-contract-kg-demo.projects-common-openshift-ec3572340d8ad35365ef8b6eaad61087-0000.us-south.containers.appdomain.cloud/}"
DATASET="${FUSEKI_DATASET:-contract}"

echo "Fuseki URL: $FUSEKI_URL"
echo "Dataset: $DATASET"
echo ""

# Count total triples
echo "1. Total triples in dataset:"
curl -s -X POST "$FUSEKI_URL/$DATASET/query" \
  -H "Content-Type: application/sparql-query" \
  -H "Accept: application/sparql-results+json" \
  --data-binary "SELECT (COUNT(*) as ?count) WHERE { ?s ?p ?o }" | \
  jq -r '.results.bindings[0].count.value // "0"'

echo ""

# Count contracts
echo "2. Number of contracts:"
curl -s -X POST "$FUSEKI_URL/$DATASET/query" \
  -H "Content-Type: application/sparql-query" \
  -H "Accept: application/sparql-results+json" \
  --data-binary "PREFIX proc: <http://procurement.kg/ontology#>
SELECT (COUNT(DISTINCT ?contract) as ?count) 
WHERE { ?contract a proc:Contract }" | \
  jq -r '.results.bindings[0].count.value // "0"'

echo ""

# Sample contract IDs
echo "3. Sample contract IDs (first 5):"
curl -s -X POST "$FUSEKI_URL/$DATASET/query" \
  -H "Content-Type: application/sparql-query" \
  -H "Accept: application/sparql-results+json" \
  --data-binary "PREFIX proc: <http://procurement.kg/ontology#>
SELECT DISTINCT ?contractId 
WHERE { 
  ?contract a proc:Contract .
  ?contract proc:contractId ?contractId 
} LIMIT 5" | \
  jq -r '.results.bindings[].contractId.value'

echo ""

# Check for old namespace (ex:)
echo "4. Checking for old namespace (ex:):"
curl -s -X POST "$FUSEKI_URL/$DATASET/query" \
  -H "Content-Type: application/sparql-query" \
  -H "Accept: application/sparql-results+json" \
  --data-binary "PREFIX ex: <http://example.org/contract-intelligence#>
SELECT (COUNT(*) as ?count) 
WHERE { ?s a ex:Contract }" | \
  jq -r '.results.bindings[0].count.value // "0"'

echo ""
echo "=== Check Complete ==="

# Made with Bob
