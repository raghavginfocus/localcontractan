package com.procurement.kg;

import com.procurement.kg.ontology.OntologyManager;
import com.procurement.kg.reasoning.ReasoningEngine;
import com.procurement.kg.store.TripleStoreManager;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

/**
 * Main application entry point for the Contract Knowledge Graph system.
 * 
 * This application provides:
 * - OWL ontology management for procurement contracts
 * - Rule-based and OWL reasoning
 * - TDB2 triple store management
 * - SPARQL query execution
 */
public class Application {
    
    private static final Logger logger = LoggerFactory.getLogger(Application.class);
    
    public static void main(String[] args) {
        logger.info("Starting Contract Knowledge Graph System...");
        
        try {
            // Initialize components
            TripleStoreManager storeManager = new TripleStoreManager("data/tdb2");
            OntologyManager ontologyManager = new OntologyManager();
            ReasoningEngine reasoningEngine = new ReasoningEngine();
            
            // Load procurement ontology
            ontologyManager.loadOntology("ontology/procurement.owl");
            logger.info("Ontology loaded successfully");
            
            // Initialize reasoning with ontology
            reasoningEngine.initialize(ontologyManager.getOntology());
            logger.info("Reasoning engine initialized");
            
            // Example: Apply reasoning to the knowledge graph
            storeManager.withDataset(dataset -> {
                reasoningEngine.applyReasoning(dataset);
                logger.info("Reasoning applied to dataset");
            });
            
            logger.info("Contract Knowledge Graph System started successfully");
            
        } catch (Exception e) {
            logger.error("Failed to start application", e);
            System.exit(1);
        }
    }
}
