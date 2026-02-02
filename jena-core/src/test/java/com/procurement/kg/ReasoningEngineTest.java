package com.procurement.kg;

import com.procurement.kg.ontology.OntologyManager;
import com.procurement.kg.reasoning.ReasoningEngine;
import org.apache.jena.rdf.model.InfModel;
import org.apache.jena.rdf.model.Model;
import org.apache.jena.rdf.model.ModelFactory;
import org.apache.jena.rdf.model.Resource;
import org.apache.jena.vocabulary.RDF;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

import java.util.List;

import static org.junit.jupiter.api.Assertions.*;

/**
 * Tests for ReasoningEngine.
 */
class ReasoningEngineTest {

    private static final String PROC_NS = "http://procurement.kg/ontology#";
    private static final String CONTRACT_NS = "http://procurement.kg/contract#";

    private ReasoningEngine reasoningEngine;
    private OntologyManager ontologyManager;

    @BeforeEach
    void setUp() {
        ontologyManager = new OntologyManager();
        ontologyManager.createBaseOntology();
        
        reasoningEngine = new ReasoningEngine();
        reasoningEngine.initialize(ontologyManager.getOntology());
        reasoningEngine.loadDefaultRules();
    }

    @Test
    void testHighTerminationRiskInference() {
        // Given - A contract with 15-day termination notice (< 30)
        Model data = createTestDataWithTerminationClause(15);

        // When - Apply reasoning
        InfModel infModel = reasoningEngine.applyReasoning(data);

        // Then - Should infer high termination risk
        Resource clause = infModel.getResource(CONTRACT_NS + "Clause_001");
        Resource highRisk = infModel.getResource(PROC_NS + "HighTerminationRisk");
        
        assertTrue(
            infModel.contains(clause, infModel.getProperty(PROC_NS + "introducesRisk"), highRisk),
            "Should infer HighTerminationRisk for 15-day notice"
        );
    }

    @Test
    void testLowTerminationRiskInference() {
        // Given - A contract with 90-day termination notice (>= 90)
        Model data = createTestDataWithTerminationClause(90);

        // When - Apply reasoning
        InfModel infModel = reasoningEngine.applyReasoning(data);

        // Then - Should infer low termination risk
        Resource clause = infModel.getResource(CONTRACT_NS + "Clause_001");
        Resource lowRisk = infModel.getResource(PROC_NS + "LowTerminationRisk");
        
        assertTrue(
            infModel.contains(clause, infModel.getProperty(PROC_NS + "introducesRisk"), lowRisk),
            "Should infer LowTerminationRisk for 90-day notice"
        );
    }

    @Test
    void testHighValueContractInference() {
        // Given - A contract with value >= 1,000,000
        Model data = createTestDataWithContractValue(1500000);

        // When - Apply reasoning
        InfModel infModel = reasoningEngine.applyReasoning(data);

        // Then - Should infer HighValueContract type
        Resource contract = infModel.getResource(CONTRACT_NS + "Contract_001");
        Resource highValueClass = infModel.getResource(PROC_NS + "HighValueContract");
        
        assertTrue(
            infModel.contains(contract, RDF.type, highValueClass),
            "Should infer HighValueContract for value >= 1M"
        );
    }

    @Test
    void testEUComplianceIssueInference() {
        // Given - An EU contract with 15-day termination notice
        Model data = createEUContractWithShortNotice(15);

        // When - Apply reasoning
        InfModel infModel = reasoningEngine.applyReasoning(data);

        // Then - Should infer EU compliance issue
        Resource contract = infModel.getResource(CONTRACT_NS + "Contract_001");
        Resource complianceIssue = infModel.getResource(PROC_NS + "EUTerminationNotice");
        
        assertTrue(
            infModel.contains(contract, infModel.getProperty(PROC_NS + "hasComplianceIssue"), complianceIssue),
            "Should infer EUTerminationNotice compliance issue"
        );
    }

    @Test
    void testNoComplianceIssueFor30DayNotice() {
        // Given - An EU contract with 30-day termination notice (compliant)
        Model data = createEUContractWithShortNotice(30);

        // When - Apply reasoning
        InfModel infModel = reasoningEngine.applyReasoning(data);

        // Then - Should NOT infer EU compliance issue
        Resource contract = infModel.getResource(CONTRACT_NS + "Contract_001");
        Resource complianceIssue = infModel.getResource(PROC_NS + "EUTerminationNotice");
        
        assertFalse(
            infModel.contains(contract, infModel.getProperty(PROC_NS + "hasComplianceIssue"), complianceIssue),
            "Should NOT infer compliance issue for 30-day notice"
        );
    }

    @Test
    void testGetInferredRisks() {
        // Given - A contract with high-risk clause
        Model data = createTestDataWithTerminationClause(10);
        InfModel infModel = reasoningEngine.applyReasoning(data);
        Resource contract = infModel.getResource(CONTRACT_NS + "Contract_001");

        // When
        List<Resource> risks = reasoningEngine.getInferredRisks(infModel, contract);

        // Then
        assertFalse(risks.isEmpty(), "Should have inferred risks");
        assertTrue(
            risks.stream().anyMatch(r -> r.getLocalName().contains("TerminationRisk")),
            "Should include termination risk"
        );
    }

    @Test
    void testValidateConsistency() {
        // Given - Valid model
        Model data = createTestDataWithTerminationClause(30);
        InfModel infModel = reasoningEngine.applyReasoning(data);

        // When
        boolean isConsistent = reasoningEngine.validateConsistency(infModel);

        // Then
        assertTrue(isConsistent, "Model should be consistent");
    }

    // Helper methods

    private Model createTestDataWithTerminationClause(int noticePeriod) {
        Model model = ModelFactory.createDefaultModel();
        
        Resource contract = model.createResource(CONTRACT_NS + "Contract_001");
        Resource clause = model.createResource(CONTRACT_NS + "Clause_001");
        Resource terminationClause = model.createResource(PROC_NS + "TerminationClause");
        
        model.add(contract, RDF.type, model.createResource(PROC_NS + "Contract"));
        model.add(clause, RDF.type, terminationClause);
        model.add(contract, model.createProperty(PROC_NS + "hasClause"), clause);
        model.add(clause, model.createProperty(PROC_NS + "noticePeriod"), 
            model.createTypedLiteral(noticePeriod));
        
        return model;
    }

    private Model createTestDataWithContractValue(double value) {
        Model model = ModelFactory.createDefaultModel();
        
        Resource contract = model.createResource(CONTRACT_NS + "Contract_001");
        
        model.add(contract, RDF.type, model.createResource(PROC_NS + "Contract"));
        model.add(contract, model.createProperty(PROC_NS + "contractValue"),
            model.createTypedLiteral(value));
        
        return model;
    }

    private Model createEUContractWithShortNotice(int noticePeriod) {
        Model model = createTestDataWithTerminationClause(noticePeriod);
        
        Resource contract = model.getResource(CONTRACT_NS + "Contract_001");
        Resource eu = model.createResource(PROC_NS + "EU");
        
        model.add(contract, model.createProperty(PROC_NS + "governedBy"), eu);
        
        return model;
    }
}
