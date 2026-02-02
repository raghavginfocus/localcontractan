package com.procurement.kg;

import com.procurement.kg.ontology.OntologyManager;
import org.apache.jena.ontology.OntClass;
import org.apache.jena.ontology.OntModel;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

import java.io.IOException;
import java.nio.file.Path;
import java.util.List;

import static org.junit.jupiter.api.Assertions.*;

/**
 * Tests for OntologyManager.
 */
class OntologyManagerTest {

    private OntologyManager ontologyManager;

    @BeforeEach
    void setUp() {
        ontologyManager = new OntologyManager();
    }

    @Test
    void testCreateBaseOntology() {
        // When
        ontologyManager.createBaseOntology();
        OntModel ontology = ontologyManager.getOntology();

        // Then
        assertNotNull(ontology);
        assertTrue(ontology.size() > 0, "Ontology should have statements");

        // Check core classes exist
        OntClass contractClass = ontology.getOntClass(OntologyManager.PROCUREMENT_NS + "Contract");
        assertNotNull(contractClass, "Contract class should exist");

        OntClass clauseClass = ontology.getOntClass(OntologyManager.PROCUREMENT_NS + "Clause");
        assertNotNull(clauseClass, "Clause class should exist");

        OntClass terminationClause = ontology.getOntClass(OntologyManager.PROCUREMENT_NS + "TerminationClause");
        assertNotNull(terminationClause, "TerminationClause class should exist");
        assertTrue(terminationClause.hasSuperClass(clauseClass), 
            "TerminationClause should be subclass of Clause");
    }

    @Test
    void testGetClassNames() {
        // Given
        ontologyManager.createBaseOntology();

        // When
        List<String> classNames = ontologyManager.getClassNames();

        // Then
        assertNotNull(classNames);
        assertTrue(classNames.contains("Contract"), "Should contain Contract class");
        assertTrue(classNames.contains("Clause"), "Should contain Clause class");
        assertTrue(classNames.contains("TerminationClause"), "Should contain TerminationClause class");
    }

    @Test
    void testGetPropertyNames() {
        // Given
        ontologyManager.createBaseOntology();

        // When
        List<String> propertyNames = ontologyManager.getPropertyNames();

        // Then
        assertNotNull(propertyNames);
        assertTrue(propertyNames.contains("hasClause"), "Should contain hasClause property");
        assertTrue(propertyNames.contains("noticePeriod"), "Should contain noticePeriod property");
        assertTrue(propertyNames.contains("governedBy"), "Should contain governedBy property");
    }

    @Test
    void testSaveAndLoadOntology(@TempDir Path tempDir) throws IOException {
        // Given
        ontologyManager.createBaseOntology();
        Path ontologyFile = tempDir.resolve("test_ontology.owl");

        // When - Save
        ontologyManager.saveOntology(ontologyFile.toString());

        // Then - File should exist
        assertTrue(ontologyFile.toFile().exists(), "Ontology file should be created");

        // When - Load into new manager
        OntologyManager newManager = new OntologyManager();
        newManager.loadOntology(ontologyFile.toString());

        // Then - Should have same classes
        List<String> originalClasses = ontologyManager.getClassNames();
        List<String> loadedClasses = newManager.getClassNames();
        
        assertTrue(loadedClasses.containsAll(originalClasses), 
            "Loaded ontology should have all original classes");
    }

    @Test
    void testOntologyNamespaces() {
        // Given
        ontologyManager.createBaseOntology();
        OntModel ontology = ontologyManager.getOntology();

        // Then
        assertEquals("proc", ontology.getNsURIPrefix(OntologyManager.PROCUREMENT_NS).replace(":", ""));
        assertEquals("contract", ontology.getNsURIPrefix(OntologyManager.CONTRACT_NS).replace(":", ""));
    }

    @Test
    void testIsConsistent() {
        // Given
        ontologyManager.createBaseOntology();

        // When
        boolean isConsistent = ontologyManager.isConsistent();

        // Then
        assertTrue(isConsistent, "Base ontology should be consistent");
    }
}
