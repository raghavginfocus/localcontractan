package com.procurement.kg.sparql;

import com.procurement.kg.store.TripleStoreManager;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.util.List;
import java.util.Map;

/**
 * Service for executing common SPARQL queries for procurement contracts.
 * 
 * This service provides:
 * - Pre-built queries for common operations
 * - Query templates for dynamic construction
 * - Integration with the triple store
 */
public class SPARQLQueryService {
    
    private static final Logger logger = LoggerFactory.getLogger(SPARQLQueryService.class);
    
    private final TripleStoreManager store;
    
    public SPARQLQueryService(TripleStoreManager store) {
        this.store = store;
    }
    
    /**
     * Get all contracts
     */
    public List<Map<String, String>> getAllContracts() {
        String query = """
            SELECT ?contract ?value ?effectiveDate ?jurisdiction
            WHERE {
                ?contract rdf:type proc:Contract .
                OPTIONAL { ?contract proc:contractValue ?value }
                OPTIONAL { ?contract proc:effectiveDate ?effectiveDate }
                OPTIONAL { ?contract proc:governedBy ?jurisdiction }
            }
            ORDER BY ?contract
            """;
        return store.executeSelect(query);
    }
    
    /**
     * Get contracts with high termination risk
     */
    public List<Map<String, String>> getHighRiskTerminationContracts() {
        String query = """
            SELECT ?contract ?clause ?noticePeriod ?risk
            WHERE {
                ?contract rdf:type proc:Contract .
                ?contract proc:hasClause ?clause .
                ?clause rdf:type proc:TerminationClause .
                ?clause proc:noticePeriod ?noticePeriod .
                ?clause proc:introducesRisk ?risk .
                FILTER(?noticePeriod < 30)
            }
            ORDER BY ?noticePeriod
            """;
        return store.executeSelect(query);
    }
    
    /**
     * Get contracts by jurisdiction
     */
    public List<Map<String, String>> getContractsByJurisdiction(String jurisdictionUri) {
        String query = String.format("""
            SELECT ?contract ?value ?clause
            WHERE {
                ?contract rdf:type proc:Contract .
                ?contract proc:governedBy <%s> .
                OPTIONAL { ?contract proc:contractValue ?value }
                OPTIONAL { ?contract proc:hasClause ?clause }
            }
            ORDER BY ?contract
            """, jurisdictionUri);
        return store.executeSelect(query);
    }
    
    /**
     * Get all clauses of a contract
     */
    public List<Map<String, String>> getContractClauses(String contractUri) {
        String query = String.format("""
            SELECT ?clause ?clauseType ?rawText
            WHERE {
                <%s> proc:hasClause ?clause .
                ?clause rdf:type ?clauseType .
                FILTER(?clauseType != owl:NamedIndividual)
                OPTIONAL { ?clause proc:rawText ?rawText }
            }
            ORDER BY ?clause
            """, contractUri);
        return store.executeSelect(query);
    }
    
    /**
     * Get compliance issues for a contract
     */
    public List<Map<String, String>> getComplianceIssues(String contractUri) {
        String query = String.format("""
            SELECT ?issue ?description
            WHERE {
                <%s> proc:hasComplianceIssue ?issue .
                OPTIONAL { ?issue rdfs:label ?description }
            }
            """, contractUri);
        return store.executeSelect(query);
    }
    
    /**
     * Get all high-value contracts (value >= threshold)
     */
    public List<Map<String, String>> getHighValueContracts(double threshold) {
        String query = String.format("""
            SELECT ?contract ?value ?party
            WHERE {
                ?contract rdf:type proc:Contract .
                ?contract proc:contractValue ?value .
                FILTER(?value >= %f)
                OPTIONAL { ?contract proc:hasParty ?party }
            }
            ORDER BY DESC(?value)
            """, threshold);
        return store.executeSelect(query);
    }
    
    /**
     * Get obligations created by contract clauses
     */
    public List<Map<String, String>> getContractObligations(String contractUri) {
        String query = String.format("""
            SELECT ?clause ?obligation ?obligationType
            WHERE {
                <%s> proc:hasClause ?clause .
                ?clause proc:createsObligation ?obligation .
                OPTIONAL { ?obligation rdf:type ?obligationType }
            }
            """, contractUri);
        return store.executeSelect(query);
    }
    
    /**
     * Search contracts by text in clause raw text
     */
    public List<Map<String, String>> searchContractsByClauseText(String searchText) {
        String query = String.format("""
            SELECT DISTINCT ?contract ?clause ?rawText
            WHERE {
                ?contract rdf:type proc:Contract .
                ?contract proc:hasClause ?clause .
                ?clause proc:rawText ?rawText .
                FILTER(CONTAINS(LCASE(?rawText), LCASE("%s")))
            }
            """, searchText);
        return store.executeSelect(query);
    }
    
    /**
     * Get contracts expiring within days
     */
    public List<Map<String, String>> getExpiringContracts(int days) {
        String query = String.format("""
            SELECT ?contract ?expirationDate ?party
            WHERE {
                ?contract rdf:type proc:Contract .
                ?contract proc:expirationDate ?expirationDate .
                BIND(NOW() as ?now)
                FILTER(?expirationDate <= ?now + "P%dD"^^xsd:duration)
                FILTER(?expirationDate >= ?now)
                OPTIONAL { ?contract proc:hasParty ?party }
            }
            ORDER BY ?expirationDate
            """, days);
        return store.executeSelect(query);
    }
    
    /**
     * Count contracts by jurisdiction
     */
    public List<Map<String, String>> countContractsByJurisdiction() {
        String query = """
            SELECT ?jurisdiction (COUNT(?contract) as ?count)
            WHERE {
                ?contract rdf:type proc:Contract .
                ?contract proc:governedBy ?jurisdiction .
            }
            GROUP BY ?jurisdiction
            ORDER BY DESC(?count)
            """;
        return store.executeSelect(query);
    }
    
    /**
     * Get risk summary for all contracts
     */
    public List<Map<String, String>> getRiskSummary() {
        String query = """
            SELECT ?risk (COUNT(?clause) as ?count)
            WHERE {
                ?clause proc:introducesRisk ?risk .
            }
            GROUP BY ?risk
            ORDER BY DESC(?count)
            """;
        return store.executeSelect(query);
    }
    
    /**
     * Check if a contract exists
     */
    public boolean contractExists(String contractUri) {
        String query = String.format("""
            ASK {
                <%s> rdf:type proc:Contract .
            }
            """, contractUri);
        return store.executeAsk(query);
    }
    
    /**
     * Get contract details with all properties
     */
    public List<Map<String, String>> getContractDetails(String contractUri) {
        String query = String.format("""
            SELECT ?property ?value
            WHERE {
                <%s> ?property ?value .
            }
            """, contractUri);
        return store.executeSelect(query);
    }
}
