package com.procurement.kg.store;

import org.apache.jena.query.Dataset;
import org.apache.jena.query.Query;
import org.apache.jena.query.QueryExecution;
import org.apache.jena.query.QueryExecutionFactory;
import org.apache.jena.query.QueryFactory;
import org.apache.jena.query.QuerySolution;
import org.apache.jena.query.ReadWrite;
import org.apache.jena.query.ResultSet;
import org.apache.jena.rdf.model.Model;
import org.apache.jena.rdf.model.ModelFactory;
import org.apache.jena.riot.Lang;
import org.apache.jena.riot.RDFDataMgr;
import org.apache.jena.tdb2.TDB2Factory;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.io.StringWriter;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.function.Consumer;
import java.util.function.Function;

/**
 * Manages the TDB2 triple store for persistent RDF storage.
 * 
 * Features:
 * - ACID transactions
 * - Persistent storage with TDB2
 * - SPARQL query execution
 * - RDF import/export in multiple formats
 * - Named graph support
 */
public class TripleStoreManager {
    
    private static final Logger logger = LoggerFactory.getLogger(TripleStoreManager.class);
    
    private final String storePath;
    private Dataset dataset;
    
    // Common namespace prefixes for SPARQL
    private static final String SPARQL_PREFIXES = """
        PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        PREFIX owl: <http://www.w3.org/2002/07/owl#>
        PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
        PREFIX proc: <http://procurement.kg/ontology#>
        PREFIX contract: <http://procurement.kg/contract#>
        """;
    
    public TripleStoreManager(String storePath) {
        this.storePath = storePath;
        initializeStore();
    }
    
    /**
     * Initialize or open the TDB2 store
     */
    private void initializeStore() {
        try {
            Path path = Paths.get(storePath);
            if (!Files.exists(path)) {
                Files.createDirectories(path);
                logger.info("Created new TDB2 store at: {}", storePath);
            }
            
            this.dataset = TDB2Factory.connectDataset(storePath);
            logger.info("Connected to TDB2 store at: {}", storePath);
            
        } catch (IOException e) {
            throw new RuntimeException("Failed to initialize triple store", e);
        }
    }
    
    /**
     * Execute a read operation within a transaction
     */
    public <T> T read(Function<Dataset, T> operation) {
        dataset.begin(ReadWrite.READ);
        try {
            T result = operation.apply(dataset);
            dataset.commit();
            return result;
        } catch (Exception e) {
            dataset.abort();
            throw e;
        } finally {
            dataset.end();
        }
    }
    
    /**
     * Execute a write operation within a transaction
     */
    public void write(Consumer<Dataset> operation) {
        dataset.begin(ReadWrite.WRITE);
        try {
            operation.accept(dataset);
            dataset.commit();
            logger.debug("Write transaction committed");
        } catch (Exception e) {
            dataset.abort();
            logger.error("Write transaction aborted", e);
            throw e;
        } finally {
            dataset.end();
        }
    }
    
    /**
     * Execute operation with dataset (manages transaction)
     */
    public void withDataset(Consumer<Dataset> operation) {
        write(operation);
    }
    
    /**
     * Load RDF data from a file
     */
    public void loadRDF(String filePath, Lang format) {
        write(ds -> {
            Model model = ds.getDefaultModel();
            RDFDataMgr.read(model, filePath, format);
            logger.info("Loaded RDF from {} ({} triples)", filePath, model.size());
        });
    }
    
    /**
     * Load RDF from Turtle format
     */
    public void loadTurtle(String filePath) {
        loadRDF(filePath, Lang.TURTLE);
    }
    
    /**
     * Load RDF from an input stream
     */
    public void loadRDF(InputStream inputStream, Lang format) {
        write(ds -> {
            Model model = ds.getDefaultModel();
            RDFDataMgr.read(model, inputStream, format);
            logger.info("Loaded RDF from stream ({} triples)", model.size());
        });
    }
    
    /**
     * Load RDF into a named graph
     */
    public void loadRDFToGraph(String filePath, String graphUri, Lang format) {
        write(ds -> {
            Model model = ds.getNamedModel(graphUri);
            RDFDataMgr.read(model, filePath, format);
            logger.info("Loaded RDF to graph {} from {} ({} triples)", 
                graphUri, filePath, model.size());
        });
    }
    
    /**
     * Export RDF data to a file
     */
    public void exportRDF(String filePath, Lang format) throws IOException {
        read(ds -> {
            try (FileOutputStream out = new FileOutputStream(filePath)) {
                RDFDataMgr.write(out, ds.getDefaultModel(), format);
                logger.info("Exported RDF to {}", filePath);
            } catch (IOException e) {
                throw new RuntimeException(e);
            }
            return null;
        });
    }
    
    /**
     * Execute a SPARQL SELECT query and return results as list of maps
     */
    public List<Map<String, String>> executeSelect(String sparqlQuery) {
        return read(ds -> {
            String fullQuery = SPARQL_PREFIXES + sparqlQuery;
            Query query = QueryFactory.create(fullQuery);
            
            List<Map<String, String>> results = new ArrayList<>();
            
            try (QueryExecution qexec = QueryExecutionFactory.create(query, ds)) {
                ResultSet resultSet = qexec.execSelect();
                List<String> vars = resultSet.getResultVars();
                
                while (resultSet.hasNext()) {
                    QuerySolution solution = resultSet.next();
                    Map<String, String> row = new HashMap<>();
                    
                    for (String var : vars) {
                        if (solution.get(var) != null) {
                            row.put(var, solution.get(var).toString());
                        }
                    }
                    results.add(row);
                }
            }
            
            logger.debug("SPARQL query returned {} results", results.size());
            return results;
        });
    }
    
    /**
     * Execute a SPARQL CONSTRUCT query and return the resulting model
     */
    public Model executeConstruct(String sparqlQuery) {
        return read(ds -> {
            String fullQuery = SPARQL_PREFIXES + sparqlQuery;
            Query query = QueryFactory.create(fullQuery);
            
            try (QueryExecution qexec = QueryExecutionFactory.create(query, ds)) {
                Model resultModel = qexec.execConstruct();
                logger.debug("CONSTRUCT query returned {} triples", resultModel.size());
                return resultModel;
            }
        });
    }
    
    /**
     * Execute a SPARQL ASK query
     */
    public boolean executeAsk(String sparqlQuery) {
        return read(ds -> {
            String fullQuery = SPARQL_PREFIXES + sparqlQuery;
            Query query = QueryFactory.create(fullQuery);
            
            try (QueryExecution qexec = QueryExecutionFactory.create(query, ds)) {
                return qexec.execAsk();
            }
        });
    }
    
    /**
     * Execute a SPARQL UPDATE query
     */
    public void executeUpdate(String sparqlUpdate) {
        write(ds -> {
            String fullUpdate = SPARQL_PREFIXES + sparqlUpdate;
            org.apache.jena.update.UpdateAction.parseExecute(fullUpdate, ds);
            logger.debug("SPARQL update executed");
        });
    }
    
    /**
     * Add a single triple to the default graph
     */
    public void addTriple(String subject, String predicate, String object) {
        write(ds -> {
            Model model = ds.getDefaultModel();
            model.add(
                model.createResource(subject),
                model.createProperty(predicate),
                model.createResource(object)
            );
        });
    }
    
    /**
     * Add a triple with a literal object
     */
    public void addTripleWithLiteral(String subject, String predicate, Object value) {
        write(ds -> {
            Model model = ds.getDefaultModel();
            model.add(
                model.createResource(subject),
                model.createProperty(predicate),
                model.createTypedLiteral(value)
            );
        });
    }
    
    /**
     * Get triple count in the default graph
     */
    public long getTripleCount() {
        return read(ds -> ds.getDefaultModel().size());
    }
    
    /**
     * Clear all data from the default graph
     */
    public void clearDefaultGraph() {
        write(ds -> {
            ds.getDefaultModel().removeAll();
            logger.info("Cleared default graph");
        });
    }
    
    /**
     * Get the underlying dataset (use with caution - manage transactions yourself)
     */
    public Dataset getDataset() {
        return dataset;
    }
    
    /**
     * Close the triple store connection
     */
    public void close() {
        if (dataset != null) {
            dataset.close();
            logger.info("Closed TDB2 store");
        }
    }
    
    /**
     * Export default graph as Turtle string
     */
    public String exportAsTurtle() {
        return read(ds -> {
            StringWriter writer = new StringWriter();
            RDFDataMgr.write(writer, ds.getDefaultModel(), Lang.TURTLE);
            return writer.toString();
        });
    }
}
