package com.procurement.kg.ontology;

import org.apache.jena.ontology.OntModel;
import org.apache.jena.ontology.OntModelSpec;
import org.apache.jena.rdf.model.ModelFactory;
import org.apache.jena.riot.RDFDataMgr;
import org.apache.jena.vocabulary.OWL;
import org.apache.jena.vocabulary.RDF;
import org.apache.jena.vocabulary.RDFS;
import org.apache.jena.vocabulary.XSD;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.nio.file.Path;

/**
 * Manages OWL ontologies for the procurement contract domain.
 * 
 * Responsibilities:
 * - Load and save ontologies (OWL/RDF formats)
 * - Validate ontology consistency
 * - Provide ontology introspection for agents
 * - Support ontology versioning and evolution
 */
public class OntologyManager {
    
    private static final Logger logger = LoggerFactory.getLogger(OntologyManager.class);
    
    // Procurement ontology namespace
    public static final String PROCUREMENT_NS = "http://procurement.kg/ontology#";
    public static final String CONTRACT_NS = "http://procurement.kg/contract#";
    
    private OntModel ontology;
    
    public OntologyManager() {
        // Create ontology model with OWL_MEM_RDFS_INF for RDFS inference
        this.ontology = ModelFactory.createOntologyModel(OntModelSpec.OWL_MEM_RDFS_INF);
        setupNamespaces();
    }
    
    /**
     * Set up common namespace prefixes
     */
    private void setupNamespaces() {
        ontology.setNsPrefix("proc", PROCUREMENT_NS);
        ontology.setNsPrefix("contract", CONTRACT_NS);
        ontology.setNsPrefix("owl", OWL.getURI());
        ontology.setNsPrefix("rdf", RDF.getURI());
        ontology.setNsPrefix("rdfs", RDFS.getURI());
        ontology.setNsPrefix("xsd", XSD.getURI());
    }
    
    /**
     * Load ontology from file
     */
    public void loadOntology(String path) throws IOException {
        logger.info("Loading ontology from: {}", path);
        
        try (InputStream is = new FileInputStream(path)) {
            ontology.read(is, PROCUREMENT_NS, "RDF/XML");
            logger.info("Ontology loaded with {} statements", ontology.size());
        } catch (IOException e) {
            // Try loading from classpath
            try (InputStream is = getClass().getClassLoader().getResourceAsStream(path)) {
                if (is != null) {
                    ontology.read(is, PROCUREMENT_NS, "RDF/XML");
                    logger.info("Ontology loaded from classpath with {} statements", ontology.size());
                } else {
                    logger.warn("Ontology file not found: {}. Creating empty ontology.", path);
                    createBaseOntology();
                }
            }
        }
    }
    
    /**
     * Create the base procurement ontology if none exists
     */
    public void createBaseOntology() {
        logger.info("Creating base procurement ontology...");
        
        // Create core classes
        var contractClass = ontology.createClass(PROCUREMENT_NS + "Contract");
        contractClass.addLabel("Contract", "en");
        contractClass.addComment("A procurement contract document", "en");
        
        var clauseClass = ontology.createClass(PROCUREMENT_NS + "Clause");
        clauseClass.addLabel("Clause", "en");
        clauseClass.addComment("A clause within a contract", "en");
        
        var terminationClause = ontology.createClass(PROCUREMENT_NS + "TerminationClause");
        terminationClause.addSuperClass(clauseClass);
        terminationClause.addLabel("Termination Clause", "en");
        
        var paymentClause = ontology.createClass(PROCUREMENT_NS + "PaymentClause");
        paymentClause.addSuperClass(clauseClass);
        paymentClause.addLabel("Payment Clause", "en");
        
        var penaltyClause = ontology.createClass(PROCUREMENT_NS + "PenaltyClause");
        penaltyClause.addSuperClass(clauseClass);
        penaltyClause.addLabel("Penalty Clause", "en");
        
        var partyClass = ontology.createClass(PROCUREMENT_NS + "Party");
        partyClass.addLabel("Party", "en");
        partyClass.addComment("A party to a contract (buyer, supplier, etc.)", "en");
        
        var obligationClass = ontology.createClass(PROCUREMENT_NS + "Obligation");
        obligationClass.addLabel("Obligation", "en");
        obligationClass.addComment("A contractual obligation", "en");
        
        var riskClass = ontology.createClass(PROCUREMENT_NS + "Risk");
        riskClass.addLabel("Risk", "en");
        riskClass.addComment("A risk identified in a contract", "en");
        
        var jurisdictionClass = ontology.createClass(PROCUREMENT_NS + "Jurisdiction");
        jurisdictionClass.addLabel("Jurisdiction", "en");
        
        // Create object properties
        var hasClause = ontology.createObjectProperty(PROCUREMENT_NS + "hasClause");
        hasClause.addDomain(contractClass);
        hasClause.addRange(clauseClass);
        hasClause.addLabel("has clause", "en");
        
        var hasParty = ontology.createObjectProperty(PROCUREMENT_NS + "hasParty");
        hasParty.addDomain(contractClass);
        hasParty.addRange(partyClass);
        hasParty.addLabel("has party", "en");
        
        var governedBy = ontology.createObjectProperty(PROCUREMENT_NS + "governedBy");
        governedBy.addDomain(contractClass);
        governedBy.addRange(jurisdictionClass);
        governedBy.addLabel("governed by", "en");
        
        var createsObligation = ontology.createObjectProperty(PROCUREMENT_NS + "createsObligation");
        createsObligation.addDomain(clauseClass);
        createsObligation.addRange(obligationClass);
        createsObligation.addLabel("creates obligation", "en");
        
        var introducesRisk = ontology.createObjectProperty(PROCUREMENT_NS + "introducesRisk");
        introducesRisk.addDomain(clauseClass);
        introducesRisk.addRange(riskClass);
        introducesRisk.addLabel("introduces risk", "en");
        
        // Create datatype properties
        var noticePeriod = ontology.createDatatypeProperty(PROCUREMENT_NS + "noticePeriod");
        noticePeriod.addDomain(terminationClause);
        noticePeriod.addRange(XSD.integer);
        noticePeriod.addLabel("notice period (days)", "en");
        
        var contractValue = ontology.createDatatypeProperty(PROCUREMENT_NS + "contractValue");
        contractValue.addDomain(contractClass);
        contractValue.addRange(XSD.decimal);
        contractValue.addLabel("contract value", "en");
        
        var effectiveDate = ontology.createDatatypeProperty(PROCUREMENT_NS + "effectiveDate");
        effectiveDate.addDomain(contractClass);
        effectiveDate.addRange(XSD.date);
        effectiveDate.addLabel("effective date", "en");
        
        var expirationDate = ontology.createDatatypeProperty(PROCUREMENT_NS + "expirationDate");
        expirationDate.addDomain(contractClass);
        expirationDate.addRange(XSD.date);
        expirationDate.addLabel("expiration date", "en");
        
        var rawText = ontology.createDatatypeProperty(PROCUREMENT_NS + "rawText");
        rawText.addDomain(clauseClass);
        rawText.addRange(XSD.xstring);
        rawText.addLabel("raw text", "en");
        
        logger.info("Base ontology created with {} statements", ontology.size());
    }
    
    /**
     * Save ontology to file
     */
    public void saveOntology(String path, String format) throws IOException {
        logger.info("Saving ontology to: {} (format: {})", path, format);
        
        try (FileOutputStream out = new FileOutputStream(path)) {
            ontology.write(out, format);
        }
    }
    
    /**
     * Save ontology in OWL/RDF-XML format
     */
    public void saveOntology(String path) throws IOException {
        saveOntology(path, "RDF/XML");
    }
    
    /**
     * Get the ontology model
     */
    public OntModel getOntology() {
        return ontology;
    }
    
    /**
     * Get all class names in the ontology
     */
    public java.util.List<String> getClassNames() {
        return ontology.listClasses()
                .filterDrop(c -> c.isAnon())
                .mapWith(c -> c.getLocalName())
                .toList();
    }
    
    /**
     * Get all property names in the ontology
     */
    public java.util.List<String> getPropertyNames() {
        var props = new java.util.ArrayList<String>();
        ontology.listObjectProperties()
                .filterDrop(p -> p.isAnon())
                .mapWith(p -> p.getLocalName())
                .forEachRemaining(props::add);
        ontology.listDatatypeProperties()
                .filterDrop(p -> p.isAnon())
                .mapWith(p -> p.getLocalName())
                .forEachRemaining(props::add);
        return props;
    }
    
    /**
     * Validate ontology consistency
     */
    public boolean isConsistent() {
        // Basic consistency check - more advanced checking would use a DL reasoner
        var validity = ontology.validate();
        if (validity != null && !validity.isValid()) {
            logger.warn("Ontology validation issues found");
            return false;
        }
        return true;
    }
}
