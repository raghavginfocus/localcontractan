package com.procurement.kg.server;

import com.procurement.kg.ontology.OntologyManager;
import com.procurement.kg.reasoning.ReasoningEngine;
import org.apache.jena.fuseki.main.FusekiServer;
import org.apache.jena.query.Dataset;
import org.apache.jena.tdb2.TDB2Factory;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;

/**
 * Embedded Fuseki SPARQL Server for the Contract Knowledge Graph.
 * 
 * This server exposes:
 * - SPARQL Query endpoint: http://localhost:3030/contracts/query
 * - SPARQL Update endpoint: http://localhost:3030/contracts/update
 * - Graph Store Protocol: http://localhost:3030/contracts/data
 * 
 * Python agents can connect to these endpoints using:
 * - pyfuseki library
 * - SPARQLWrapper
 * - Direct HTTP requests
 */
public class EmbeddedFusekiServer {
    
    private static final Logger logger = LoggerFactory.getLogger(EmbeddedFusekiServer.class);
    
    private static final int DEFAULT_PORT = 3030;
    private static final String DATASET_NAME = "contracts";
    private static final String TDB_PATH = "data/fuseki-tdb2";
    
    private FusekiServer server;
    private Dataset dataset;
    private OntologyManager ontologyManager;
    private ReasoningEngine reasoningEngine;
    
    public static void main(String[] args) {
        int port = DEFAULT_PORT;
        
        // Parse command line arguments
        for (int i = 0; i < args.length; i++) {
            if ("--port".equals(args[i]) && i + 1 < args.length) {
                port = Integer.parseInt(args[++i]);
            }
        }
        
        EmbeddedFusekiServer fusekiServer = new EmbeddedFusekiServer();
        fusekiServer.start(port);
        
        // Add shutdown hook
        Runtime.getRuntime().addShutdownHook(new Thread(() -> {
            logger.info("Shutting down Fuseki server...");
            fusekiServer.stop();
        }));
    }
    
    /**
     * Start the Fuseki server
     */
    public void start(int port) {
        try {
            logger.info("Initializing Fuseki server on port {}...", port);
            
            // Ensure TDB directory exists
            Path tdbPath = Paths.get(TDB_PATH);
            if (!Files.exists(tdbPath)) {
                Files.createDirectories(tdbPath);
                logger.info("Created TDB2 directory: {}", TDB_PATH);
            }
            
            // Create persistent dataset
            dataset = TDB2Factory.connectDataset(TDB_PATH);
            
            // Initialize ontology and reasoning
            initializeOntologyAndReasoning();
            
            // Build and start Fuseki server
            server = FusekiServer.create()
                .port(port)
                .add("/" + DATASET_NAME, dataset)
                .enableCors(true)  // Allow cross-origin requests from Python
                .build();
            
            server.start();
            
            logger.info("========================================");
            logger.info("Fuseki server started successfully!");
            logger.info("========================================");
            logger.info("SPARQL Query:  http://localhost:{}/{}/query", port, DATASET_NAME);
            logger.info("SPARQL Update: http://localhost:{}/{}/update", port, DATASET_NAME);
            logger.info("Graph Store:   http://localhost:{}/{}/data", port, DATASET_NAME);
            logger.info("Web UI:        http://localhost:{}/", port);
            logger.info("========================================");
            
            // Keep server running
            server.join();
            
        } catch (Exception e) {
            logger.error("Failed to start Fuseki server", e);
            throw new RuntimeException(e);
        }
    }
    
    /**
     * Initialize ontology and reasoning engine
     */
    private void initializeOntologyAndReasoning() {
        try {
            ontologyManager = new OntologyManager();
            
            // Try to load existing ontology, or create base ontology
            try {
                ontologyManager.loadOntology("ontology/procurement.owl");
            } catch (Exception e) {
                logger.info("Creating base ontology...");
                ontologyManager.createBaseOntology();
                
                // Save the created ontology
                Path ontologyDir = Paths.get("ontology");
                if (!Files.exists(ontologyDir)) {
                    Files.createDirectories(ontologyDir);
                }
                ontologyManager.saveOntology("ontology/procurement.owl");
            }
            
            // Initialize reasoning engine
            reasoningEngine = new ReasoningEngine();
            reasoningEngine.initialize(ontologyManager.getOntology());
            reasoningEngine.loadDefaultRules();
            
            logger.info("Ontology and reasoning engine initialized");
            
        } catch (IOException e) {
            logger.warn("Could not save ontology: {}", e.getMessage());
        }
    }
    
    /**
     * Stop the Fuseki server
     */
    public void stop() {
        if (server != null) {
            server.stop();
            logger.info("Fuseki server stopped");
        }
        if (dataset != null) {
            dataset.close();
            logger.info("Dataset closed");
        }
    }
    
    /**
     * Get the dataset for direct access
     */
    public Dataset getDataset() {
        return dataset;
    }
    
    /**
     * Get the ontology manager
     */
    public OntologyManager getOntologyManager() {
        return ontologyManager;
    }
    
    /**
     * Get the reasoning engine
     */
    public ReasoningEngine getReasoningEngine() {
        return reasoningEngine;
    }
}
