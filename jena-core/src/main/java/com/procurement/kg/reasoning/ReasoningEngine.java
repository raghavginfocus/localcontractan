package com.procurement.kg.reasoning;

import org.apache.jena.ontology.OntModel;
import org.apache.jena.query.Dataset;
import org.apache.jena.rdf.model.InfModel;
import org.apache.jena.rdf.model.Model;
import org.apache.jena.rdf.model.ModelFactory;
import org.apache.jena.rdf.model.Resource;
import org.apache.jena.reasoner.Reasoner;
import org.apache.jena.reasoner.ReasonerRegistry;
import org.apache.jena.reasoner.rulesys.GenericRuleReasoner;
import org.apache.jena.reasoner.rulesys.Rule;
import org.apache.jena.vocabulary.RDF;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.io.BufferedReader;
import java.io.FileReader;
import java.io.IOException;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.List;
import java.util.stream.Collectors;

/**
 * Core reasoning engine using Apache Jena's inference capabilities.
 * 
 * Supports:
 * - OWL reasoning (OWL-DL subset)
 * - RDFS reasoning
 * - Custom rule-based reasoning
 * - Hybrid reasoning combining multiple approaches
 * 
 * Key Reasoning Scenarios for Procurement:
 * - Risk inference from clause attributes
 * - Compliance checking against policies
 * - Obligation derivation
 * - Contract classification
 */
public class ReasoningEngine {
    
    private static final Logger logger = LoggerFactory.getLogger(ReasoningEngine.class);
    
    private OntModel ontology;
    private List<Rule> customRules;
    private Reasoner owlReasoner;
    private GenericRuleReasoner customReasoner;
    
    public ReasoningEngine() {
        this.customRules = new ArrayList<>();
    }
    
    /**
     * Initialize the reasoning engine with an ontology
     */
    public void initialize(OntModel ontology) {
        this.ontology = ontology;
        
        // Create OWL reasoner (using Jena's OWL mini reasoner for performance)
        this.owlReasoner = ReasonerRegistry.getOWLMiniReasoner();
        this.owlReasoner = owlReasoner.bindSchema(ontology);
        
        logger.info("Reasoning engine initialized with OWL reasoner");
    }
    
    /**
     * Load custom rules from a file
     * 
     * Rules should be in Jena rule format:
     * [ruleName: (?x rdf:type proc:TerminationClause) (?x proc:noticePeriod ?days) 
     *            lessThan(?days, 30) -> (?x proc:introducesRisk proc:HighTerminationRisk)]
     */
    public void loadRules(String rulesPath) throws IOException {
        logger.info("Loading rules from: {}", rulesPath);
        
        List<Rule> rules;
        
        // Try file path first
        try (BufferedReader reader = new BufferedReader(new FileReader(rulesPath, StandardCharsets.UTF_8))) {
            String content = reader.lines().collect(Collectors.joining("\n"));
            rules = Rule.parseRules(content);
        } catch (IOException e) {
            // Try classpath
            try (InputStream is = getClass().getClassLoader().getResourceAsStream(rulesPath)) {
                if (is == null) {
                    throw new IOException("Rules file not found: " + rulesPath);
                }
                try (BufferedReader reader = new BufferedReader(new InputStreamReader(is, StandardCharsets.UTF_8))) {
                    String content = reader.lines().collect(Collectors.joining("\n"));
                    rules = Rule.parseRules(content);
                }
            }
        }
        
        this.customRules.addAll(rules);
        this.customReasoner = new GenericRuleReasoner(customRules);
        
        logger.info("Loaded {} custom rules", rules.size());
    }
    
    /**
     * Add rules programmatically
     */
    public void addRule(String ruleString) {
        Rule rule = Rule.parseRule(ruleString);
        customRules.add(rule);
        this.customReasoner = new GenericRuleReasoner(customRules);
        logger.debug("Added rule: {}", rule.getName());
    }
    
    /**
     * Add default procurement reasoning rules
     */
    public void loadDefaultRules() {
        String procNs = "http://procurement.kg/ontology#";
        
        // Risk inference rules
        addRule(String.format(
            "[HighTerminationRisk: " +
            "(?clause rdf:type <%sTerminationClause>) " +
            "(?clause <%snoticePeriod> ?days) " +
            "lessThan(?days, 30) " +
            "-> (?clause <%sintroducesRisk> <%sHighTerminationRisk>)]",
            procNs, procNs, procNs, procNs
        ));
        
        addRule(String.format(
            "[LowTerminationRisk: " +
            "(?clause rdf:type <%sTerminationClause>) " +
            "(?clause <%snoticePeriod> ?days) " +
            "ge(?days, 90) " +
            "-> (?clause <%sintroducesRisk> <%sLowTerminationRisk>)]",
            procNs, procNs, procNs, procNs
        ));
        
        // Contract classification rules
        addRule(String.format(
            "[HighValueContract: " +
            "(?contract rdf:type <%sContract>) " +
            "(?contract <%scontractValue> ?value) " +
            "ge(?value, 1000000) " +
            "-> (?contract rdf:type <%sHighValueContract>)]",
            procNs, procNs, procNs
        ));
        
        // Compliance rules
        addRule(String.format(
            "[EUCompliance: " +
            "(?contract rdf:type <%sContract>) " +
            "(?contract <%sgovernedBy> <%sEU>) " +
            "(?contract <%shasClause> ?clause) " +
            "(?clause rdf:type <%sTerminationClause>) " +
            "(?clause <%snoticePeriod> ?days) " +
            "lessThan(?days, 30) " +
            "-> (?contract <%shasComplianceIssue> <%sEUTerminationNotice>)]",
            procNs, procNs, procNs, procNs, procNs, procNs, procNs, procNs
        ));
        
        logger.info("Loaded {} default procurement rules", customRules.size());
    }
    
    /**
     * Apply reasoning to a dataset and return inferred model
     */
    public InfModel applyReasoning(Dataset dataset) {
        Model dataModel = dataset.getDefaultModel();
        return applyReasoning(dataModel);
    }
    
    /**
     * Apply reasoning to a model and return inferred model
     */
    public InfModel applyReasoning(Model dataModel) {
        logger.info("Applying reasoning to model with {} statements", dataModel.size());
        
        InfModel infModel;
        
        if (customReasoner != null) {
            // Combine OWL and custom rule reasoning
            Reasoner combinedReasoner = customReasoner;
            if (ontology != null) {
                combinedReasoner = combinedReasoner.bindSchema(ontology);
            }
            infModel = ModelFactory.createInfModel(combinedReasoner, dataModel);
        } else if (owlReasoner != null) {
            // OWL reasoning only
            infModel = ModelFactory.createInfModel(owlReasoner, dataModel);
        } else {
            // RDFS reasoning as fallback
            Reasoner rdfsReasoner = ReasonerRegistry.getRDFSReasoner();
            infModel = ModelFactory.createInfModel(rdfsReasoner, dataModel);
        }
        
        // Materialize inferences
        infModel.prepare();
        
        long inferredCount = infModel.size() - dataModel.size();
        logger.info("Reasoning complete. Inferred {} new statements", inferredCount);
        
        return infModel;
    }
    
    /**
     * Get all inferred risks for a contract
     */
    public List<Resource> getInferredRisks(InfModel model, Resource contract) {
        String procNs = "http://procurement.kg/ontology#";
        List<Resource> risks = new ArrayList<>();
        
        // Find all clauses of the contract
        var clauses = model.listObjectsOfProperty(
            contract, 
            model.getProperty(procNs + "hasClause")
        );
        
        // For each clause, find introduced risks
        clauses.forEachRemaining(clause -> {
            if (clause.isResource()) {
                var riskStatements = model.listObjectsOfProperty(
                    clause.asResource(),
                    model.getProperty(procNs + "introducesRisk")
                );
                riskStatements.forEachRemaining(risk -> {
                    if (risk.isResource()) {
                        risks.add(risk.asResource());
                    }
                });
            }
        });
        
        return risks;
    }
    
    /**
     * Check if reasoning produced any compliance issues
     */
    public List<Resource> getComplianceIssues(InfModel model, Resource contract) {
        String procNs = "http://procurement.kg/ontology#";
        List<Resource> issues = new ArrayList<>();
        
        var issueStatements = model.listObjectsOfProperty(
            contract,
            model.getProperty(procNs + "hasComplianceIssue")
        );
        
        issueStatements.forEachRemaining(issue -> {
            if (issue.isResource()) {
                issues.add(issue.asResource());
            }
        });
        
        return issues;
    }
    
    /**
     * Validate that the inferred model is consistent
     */
    public boolean validateConsistency(InfModel model) {
        var validity = model.validate();
        if (validity != null && !validity.isValid()) {
            logger.warn("Model inconsistency detected");
            validity.getReports().forEachRemaining(report -> {
                logger.warn("Validation issue: {}", report);
            });
            return false;
        }
        return true;
    }
}
