## Example Document Extractions

This page summarizes how the system extracts structured knowledge from the example contracts in the `examples/` folder and how that data appears in the ontology (RDFS/OWL), RDF, and rules.

The goal is to give business users a clear view of:

- Which information is extracted from each example document
- How that information is represented in the knowledge graph
- Which rules and validations apply

### Example documents

The repository includes three example contracts:

- `CW3150589.NZ.(22Mar21)CBRE sig only.pdf`
- `P_SRA_SMA_PA_Hong_Kong-eEnglish_v6_17.docx`
- `P_SRA_SMA_PA_Hong_Kong-English_v6_17.docx`

These documents can be ingested using the ingestion scripts under `scripts/ingestion/` (for example, `run_ingestion_pipeline.py` or `ingest_single_document.py`). During ingestion, a synthetic `document_id` such as `doc_xxxxxxxx` is assigned; the ontology and RDF refer to that identifier (for example, `Contract_doc_ab12cd34`).

### What happens when a document arrives

When a new contract document (PDF/DOCX) arrives and you run the ingestion pipeline:

1. **Document intake**
   - Raw text and basic metadata are extracted.
   - A synthetic `document_id` is assigned, for example:
     - `doc_184ebdf5`
     - `doc_2abcc4b06a203937`
     - `doc_713e5600`
     - `doc_8636015b`
     - `doc_a6b1b5392e3fdd78`
     - `doc_b1cc9133`
   - The contract instance in RDF is typically named like `Contract_doc_184ebdf5`.

2. **Clause extraction**
   - Clauses are identified and typed, for example:
     - `proc:TerminationClause`
     - `proc:PaymentClause`
     - `proc:DataProtectionClause`
   - Attributes such as `proc:noticePeriod`, `proc:paymentTerms`, `proc:dataRetentionPeriod` are attached when available.

3. **Entity, obligation, and risk extraction**
   - Parties, dates, amounts, and jurisdictions are extracted and linked to the contract.
   - Obligations and risks are extracted as separate objects or attributes on clauses.

4. **Ontology alignment and RDF generation**
   - All extracted information is mapped into the ontology (`proc:Contract`, `proc:Clause`, etc.).
   - RDF/Turtle is generated and saved under `/app/artifacts/rdf` inside the agents container.

5. **Load into Fuseki (named graph)**
   - The RDF for that document is loaded into Fuseki under a document‑specific named graph:
     - `http://procurement.kg/contract#graph/doc_184ebdf5`
     - `http://procurement.kg/contract#graph/doc_2abcc4b06a203937`
     - `http://procurement.kg/contract#graph/doc_713e5600`
     - `http://procurement.kg/contract#graph/doc_8636015b`
     - `http://procurement.kg/contract#graph/doc_a6b1b5392e3fdd78`
     - `http://procurement.kg/contract#graph/doc_b1cc9133`

6. **Validation (SHACL)**
   - The data is validated against SHACL shapes (for example, contract must have a non‑negative `proc:contractValue` and at least one clause).

7. **Reasoning and rules**
   - Jena rules are run over the data:
     - Infer risk levels such as `proc:HighTerminationRisk` from termination clauses.
     - Classify contracts as `proc:HighValueContract` based on `proc:contractValue`.
     - Infer financial risks from penalty clauses.

The result is a rich named graph per document containing contracts, clauses, entities, obligations, risks, and all inferred classifications.

### What is extracted per document

For each ingested document, the ingestion pipeline extracts and stores:

- **Contract metadata**
  - Contract identifier and title
  - Effective and expiration dates
  - Contract value
  - Governing jurisdiction
  - Parties (names and roles)

- **Clauses**
  - Clause type (for example: `TerminationClause`, `PaymentClause`, `DataProtectionClause`)
  - Raw clause text
  - Key attributes per clause type (for example: notice period, payment terms, data retention period)

- **Obligations and risks**
  - Obligation entities (who must do what)
  - Risk entities (what risks are introduced)

This information is mapped into the ontology defined in `agents/src/schemas/ontology/procurement.owl`, the SHACL shapes in `agents/src/schemas/shacl/contract_shapes.ttl`, and the reasoning rules in `rules/procurement.rules`.

### How it appears in the ontology and RDF

At a high level, the extraction pipeline produces RDF triples of the form:

- A `proc:Contract` instance representing the contract:
  - `proc:contractValue` (numeric value)
  - `proc:effectiveDate` and `proc:expirationDate`
  - `proc:governedBy` a `proc:Jurisdiction`
  - `proc:hasClause` links to clause instances

- `proc:Clause` instances for each clause:
  - Typed as specific subclasses such as `proc:TerminationClause`, `proc:PaymentClause`, `proc:DataProtectionClause`
  - `proc:rawText` carrying the original clause text
  - Attributes such as `proc:noticePeriod`, `proc:paymentTerms`, `proc:dataRetentionPeriod`

- `proc:Risk` instances linked via `proc:introducesRisk` when rules fire (see below)

The ontology and rules are consistent with this structure:

- `proc:TerminationClause` is a subclass of `proc:Clause`
- `proc:noticePeriod` is a datatype property on termination clauses
- `proc:contractValue` is a datatype property on contracts

These are used by the inference rules in `rules/procurement.rules`, for example:

- If a `TerminationClause` has `noticePeriod < 30`, then it introduces `proc:HighTerminationRisk`
- If a contract has `contractValue >= 1,000,000`, it is inferred to be a `proc:HighValueContract`

### How ontology, SHACL, and rules work together

At a high level, three layers describe and check what you see in the graphs:

- **Ontology (OWL/RDFS)** – defines the **data model**  
  - Classes:
    - `proc:Contract`, `proc:Clause`, `proc:TerminationClause`, `proc:Risk`, `proc:Party`, etc.
  - Properties:
    - Contract‑level: `proc:contractValue`, `proc:effectiveDate`, `proc:expirationDate`, `proc:governedBy`, `proc:hasClause`, `proc:hasParty`, etc.
    - Clause‑level: `proc:rawText`, `proc:noticePeriod`, `proc:dataRetentionPeriod`, `proc:paymentTerms`, etc.

- **SHACL shapes** – validate that each contract and clause is **structurally correct**  
  - Contract must have at least one clause  
  - Contract value must be non‑negative  
  - Termination clauses should have a positive integer `noticePeriod`  
  - Clause must have raw text (`proc:rawText`) and sensible labels

- **Rules (Jena)** – infer **additional facts** from the data  
  - High/medium/low termination risk from `proc:noticePeriod`  
  - High/medium/low contract value from `proc:contractValue`  
  - High financial risk from `proc:penaltyAmount` on penalty clauses  

For each document graph:

1. The ingestion pipeline creates instances of these classes and properties.
2. SHACL shapes flag missing/incorrect fields.
3. Jena rules add new triples such as `proc:introducesRisk proc:HighTerminationRisk` or extra types like `proc:HighValueContract`.

### How to inspect what was extracted for a specific document

When you ingest an example contract, the system:

1. Assigns a `document_id` such as `doc_ab12cd34`
2. Generates RDF for the contract and clauses
3. Loads it into Fuseki under a named graph such as:
   - `http://procurement.kg/contract#graph/doc_ab12cd34`

You can inspect what was extracted in several ways:

- **SPARQL in Fuseki Web UI**
  - Open the Fuseki UI (default `http://localhost:3030`)
  - Select the `contracts` dataset
  - Run queries such as:

    ```sparql
    SELECT ?contract ?value ?effectiveDate ?jurisdiction
    WHERE {
      ?contract a proc:Contract ;
                proc:contractValue ?value ;
                proc:effectiveDate ?effectiveDate ;
                proc:governedBy ?jurisdiction .
    }
    ```

    ```sparql
    SELECT ?clause ?notice ?risk
    WHERE {
      ?clause a proc:TerminationClause ;
              proc:noticePeriod ?notice .
      OPTIONAL { ?clause proc:introducesRisk ?risk }
    }
    ```

- **SPARQL from the API**
  - Use the retrieval API to ask questions like:
    - “What are the termination clauses in the contracts?”
    - “Which contracts have high termination risk?”

These queries show exactly which clauses and contracts were extracted from the example files and how they are classified by the ontology and rules.

### Example SPARQL queries per document graph

The following SPARQL examples use the real graph URIs currently present in the `contracts` dataset:

- `http://procurement.kg/contract#graph/doc_184ebdf5`
- `http://procurement.kg/contract#graph/doc_2abcc4b06a203937`
- `http://procurement.kg/contract#graph/doc_713e5600`
- `http://procurement.kg/contract#graph/doc_8636015b`
- `http://procurement.kg/contract#graph/doc_a6b1b5392e3fdd78`
- `http://procurement.kg/contract#graph/doc_b1cc9133`

You can run these directly in the Fuseki Web UI (select the `contracts` dataset first).

#### 1. All contracts in all graphs

```sparql
PREFIX rdf:  <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX proc: <http://procurement.kg/ontology#>

SELECT DISTINCT ?g ?contract
WHERE {
  GRAPH ?g {
    ?contract rdf:type proc:Contract .
  }
}
ORDER BY ?g ?contract
```

#### 2. Contracts and clauses for a specific document

Example: `doc_184ebdf5`:

```sparql
PREFIX rdf:  <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX proc: <http://procurement.kg/ontology#>

SELECT ?contract ?clause ?clauseType ?label ?rawText
WHERE {
  GRAPH <http://procurement.kg/contract#graph/doc_184ebdf5> {
    ?contract rdf:type proc:Contract ;
              proc:hasClause ?clause .

    ?clause rdf:type ?clauseType .
    FILTER(?clauseType != proc:Clause)

    OPTIONAL { ?clause rdfs:label  ?label }
    OPTIONAL { ?clause proc:rawText ?rawText }
  }
}
ORDER BY ?contract ?clause
```

You can repeat the same pattern for other documents by changing the graph URI:

- `GRAPH <http://procurement.kg/contract#graph/doc_2abcc4b06a203937>`
- `GRAPH <http://procurement.kg/contract#graph/doc_713e5600>`
- `GRAPH <http://procurement.kg/contract#graph/doc_8636015b>`
- `GRAPH <http://procurement.kg/contract#graph/doc_a6b1b5392e3fdd78>`
- `GRAPH <http://procurement.kg/contract#graph/doc_b1cc9133>`

#### 3. Entities, obligations, and risks for a document

```sparql
PREFIX rdf:  <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX proc: <http://procurement.kg/ontology#>

SELECT ?contract ?party ?partyName ?role ?clause ?clauseType ?obligation ?risk
WHERE {
  GRAPH <http://procurement.kg/contract#graph/doc_a6b1b5392e3fdd78> {
    ?contract rdf:type proc:Contract .

    OPTIONAL {
      ?contract proc:hasParty ?party .
      OPTIONAL { ?party rdfs:label ?partyName }
      OPTIONAL { ?party proc:hasRole ?role }
    }

    OPTIONAL {
      ?contract proc:hasClause ?clause .
      ?clause rdf:type ?clauseType .
      FILTER(?clauseType != proc:Clause)
      OPTIONAL { ?clause proc:hasObligation ?obligation }
      OPTIONAL { ?clause proc:introducesRisk ?risk }
    }
  }
}
ORDER BY ?contract ?party ?clause
```

Change the graph URI to inspect other documents.

#### 4. Termination clauses and inferred risk levels

```sparql
PREFIX rdf:  <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX proc: <http://procurement.kg/ontology#>

SELECT ?contract ?clause ?notice ?risk
WHERE {
  GRAPH <http://procurement.kg/contract#graph/doc_b1cc9133> {
    ?contract rdf:type proc:Contract ;
              proc:hasClause ?clause .

    ?clause rdf:type proc:TerminationClause ;
            proc:noticePeriod ?notice .

    OPTIONAL { ?clause proc:introducesRisk ?risk }
  }
}
ORDER BY ?contract ?clause
```

This query shows where the rules in `rules/procurement.rules` have inferred risk levels (`proc:HighTerminationRisk`, `proc:MediumTerminationRisk`, etc.) for that document’s termination clauses.

#### 5. Detailed contract + termination properties (including notice period)

This query shows, for one document graph, the main contract‑level properties **and** the termination‑clause `noticePeriod` values that drive the risk rules:

```sparql
PREFIX rdf:  <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX proc: <http://procurement.kg/ontology#>

SELECT ?contract ?clause ?clauseType ?notice ?value ?eff ?exp ?jurisdiction
WHERE {
  GRAPH <http://procurement.kg/contract#graph/doc_184ebdf5> {
    ?contract rdf:type proc:Contract .

    OPTIONAL { ?contract proc:contractValue  ?value }
    OPTIONAL { ?contract proc:effectiveDate ?eff }
    OPTIONAL { ?contract proc:expirationDate ?exp }
    OPTIONAL { ?contract proc:governedBy    ?jurisdiction }

    OPTIONAL {
      ?contract proc:hasClause ?clause .
      ?clause rdf:type ?clauseType .
      FILTER(?clauseType = proc:TerminationClause)
      OPTIONAL { ?clause proc:noticePeriod ?notice }
    }
  }
}
ORDER BY ?contract ?clause
```

You can change the graph URI to inspect the same properties for any of the other document graphs.

#### 6. Cross-graph checks for properties (all named graphs)

Sometimes you want to look across **all documents at once** and see which properties exist where.  
These queries use `GRAPH ?g { ... }` so they scan all named graphs.

**(a) All contract properties across all graphs**

This query lists every triple attached to each `proc:Contract` in every named graph.  
You can use it to see all fields that were extracted for contracts (value, dates, jurisdiction, etc.).

```sparql
PREFIX rdf:  <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX proc: <http://procurement.kg/ontology#>

SELECT ?g ?contract ?property ?value
WHERE {
  GRAPH ?g {
    ?contract rdf:type proc:Contract .
    ?contract ?property ?value .
  }
}
ORDER BY ?g ?contract ?property
```

To focus only on “interesting” contract fields, you can add a `FILTER`:

```sparql
PREFIX rdf:  <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX proc: <http://procurement.kg/ontology#>

SELECT ?g ?contract ?property ?value
WHERE {
  GRAPH ?g {
    ?contract rdf:type proc:Contract .
    ?contract ?property ?value .

    FILTER(?property IN (
      proc:contractValue,
      proc:effectiveDate,
      proc:expirationDate,
      proc:governedBy,
      proc:hasClause,
      proc:hasParty
    ))
  }
}
ORDER BY ?g ?contract ?property
```

**(b) All clause properties across all graphs**

This query shows which fields were extracted for clauses (including subclass types such as `proc:TerminationClause`), in every document graph:

```sparql
PREFIX rdf:  <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX proc: <http://procurement.kg/ontology#>

SELECT ?g ?clause ?property ?value
WHERE {
  GRAPH ?g {
    ?clause rdf:type ?clauseType .
    FILTER(?clauseType = proc:Clause || EXISTS { ?clause rdf:type proc:Clause })

    ?clause ?property ?value .
  }
}
ORDER BY ?g ?clause ?property
```

To limit it to key attributes such as raw text, notice period, payment terms, and data retention:

```sparql
PREFIX rdf:  <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX proc: <http://procurement.kg/ontology#>

SELECT ?g ?clause ?property ?value
WHERE {
  GRAPH ?g {
    ?clause rdf:type ?clauseType .
    FILTER(?clauseType != proc:Contract)  # focus on clauses

    ?clause ?property ?value .

    FILTER(?property IN (
      proc:rawText,
      proc:noticePeriod,
      proc:dataRetentionPeriod,
      proc:paymentTerms
    ))
  }
}
ORDER BY ?g ?clause ?property
```

**(c) Everything in every graph (raw view)**

If you just want to see “what exists” everywhere (for debugging or exploration), you can dump triples from all graphs:

```sparql
SELECT ?g ?s ?p ?o
WHERE {
  GRAPH ?g {
    ?s ?p ?o .
  }
}
ORDER BY ?g ?s ?p
LIMIT 1000
```

This gives you a raw view of all subjects, properties, and values across all document graphs.

### 7. Risk in the ontology and in loaded data

**What the ontology defines**

- **Classes:** `proc:Risk` (and subclasses `TerminationRisk`, `FinancialRisk`, `ComplianceRisk`). Risk is not a clause; it is a separate entity.
- **Contract-risk relation (ingestion):** `proc:hasRisk` — domain `proc:Contract`, range `proc:Risk`. The ingestion pipeline writes **contract → hasRisk → risk**.
- **Clause-risk relation (rules):** `proc:introducesRisk` — domain `proc:Clause`, range `proc:Risk`. Jena rules infer **clause → introducesRisk → risk** (e.g. `proc:HighTerminationRisk`) when reasoning is run; this is not written by ingestion.
- **Risk properties:** On each risk the ontology uses `proc:severity` (e.g. "Low", "Medium", "High", "Critical"). The ingestion pipeline also writes `proc:riskType`, `proc:description`, `proc:likelihood` on risk entities.

So for **documents loaded by the pipeline**, risk data appears as: **Contract --hasRisk--> Risk**, and each Risk has **proc:severity** (and optionally riskType, description, likelihood). The clause-level link **Clause --introducesRisk--> Risk** only appears after Jena reasoning.

**Diagnostic: see if any risk data exists**

Run this across all named graphs to see every risk-related triple (hasRisk, introducesRisk, severity, riskType, etc.):

```sparql
PREFIX rdf:   <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX proc:  <http://procurement.kg/ontology#>

SELECT ?g ?s ?p ?o
WHERE {
  GRAPH ?g {
    { ?s proc:hasRisk ?o } UNION
    { ?s proc:introducesRisk ?o } UNION
    { ?s proc:severity ?o } UNION
    { ?s proc:riskType ?o } UNION
    { ?s rdf:type proc:Risk }
  }
}
ORDER BY ?g ?s ?p
```

If this returns no rows, then no risk triples have been loaded (obligation/risk extraction may have found no risks, or that step may not have run).

### 8. High risk contracts across all named graphs

Use these queries to list **high risk contracts** in every named graph. “High risk” here means contracts that have at least one clause introducing a risk with severity **High** (for example `proc:HighTerminationRisk`, `proc:HighFinancialRisk`), or that are classified as `proc:HighRiskContract` when the reasoner has run.

**(a) By contract-risk link and severity (use for ingested data)**

Contracts that have at least one risk linked via **proc:hasRisk** with severity High or Critical (case-insensitive):

```sparql
PREFIX rdf:   <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX rdfs:  <http://www.w3.org/2000/01/rdf-schema#>
PREFIX proc:  <http://procurement.kg/ontology#>

SELECT DISTINCT ?g ?contract ?risk ?severity ?riskType
WHERE {
  GRAPH ?g {
    ?contract rdf:type proc:Contract .
    ?contract proc:hasRisk ?risk .
    ?risk proc:severity ?severity .
    FILTER(LCASE(?severity) IN ("high", "critical"))
    OPTIONAL { ?risk proc:riskType ?riskType . }
  }
}
ORDER BY ?g ?contract ?risk
```

**(b) After Jena reasoning: clause introduces risk**

If you have run the Jena reasoner, you can find high risk via **proc:introducesRisk** (clause → risk). Match by risk URI (e.g. `proc:HighTerminationRisk`, `proc:HighFinancialRisk`):

```sparql
PREFIX rdf:   <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX rdfs:  <http://www.w3.org/2000/01/rdf-schema#>
PREFIX proc:  <http://procurement.kg/ontology#>

SELECT DISTINCT ?g ?contract ?risk ?riskLabel
WHERE {
  GRAPH ?g {
    ?contract rdf:type proc:Contract .
    ?contract proc:hasClause ?clause .
    ?clause proc:introducesRisk ?risk .
    FILTER(CONTAINS(STR(?risk), "High"))
    OPTIONAL { ?risk rdfs:label ?riskLabel . }
  }
}
ORDER BY ?g ?contract ?risk
```

**(c) Contracts typed as HighRiskContract (reasoner only)**

When the Jena reasoner has run, contracts with multiple high risks are typed as `proc:HighRiskContract`. To list only those:

```sparql
PREFIX rdf:   <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX rdfs:  <http://www.w3.org/2000/01/rdf-schema#>
PREFIX proc:  <http://procurement.kg/ontology#>

SELECT DISTINCT ?g ?contract
WHERE {
  GRAPH ?g {
    ?contract rdf:type proc:HighRiskContract .
  }
}
ORDER BY ?g ?contract
```

**(d) One row per high-risk contract (ingested data)**

If you only need the set of contracts that have at least one high risk, without listing each risk (use **proc:hasRisk** for ingested data):

```sparql
PREFIX rdf:   <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX proc:  <http://procurement.kg/ontology#>

SELECT DISTINCT ?g ?contract
WHERE {
  GRAPH ?g {
    ?contract rdf:type proc:Contract .
    ?contract proc:hasRisk ?risk .
    ?risk proc:severity ?severity .
    FILTER(LCASE(?severity) IN ("high", "critical"))
  }
}
ORDER BY ?g ?contract
```

### Quick SPARQL primer (for non‑experts)

When you read the example queries above, it helps to know what the main SPARQL keywords mean:

- **PREFIX**: Shortcuts for long URLs.  
  - Example: `PREFIX proc: <http://procurement.kg/ontology#>` lets you write `proc:Contract` instead of the full URI.

- **SELECT**: Which columns you want back.  
  - Example: `SELECT ?contract ?clause ?notice` means “return a table with these three columns.”

- **WHERE { … }**: The pattern of triples you are looking for.  
  - Example:  
    `?contract rdf:type proc:Contract` means “find resources that are of type `proc:Contract`.”

- **GRAPH <…> { … }**: Look only inside a specific named graph (one document’s data).  
  - Example:  
    `GRAPH <http://procurement.kg/contract#graph/doc_184ebdf5> { … }`
    means “only use triples from that document’s graph.”

- **OPTIONAL { … }**: Extra data if it exists; do not drop the row if it is missing.  
  - Example:  
    `OPTIONAL { ?clause proc:introducesRisk ?risk }` means “show the risk if present, otherwise leave the cell empty.”

- **FILTER( … )**: Apply conditions to limit results.  
  - Example:  
    `FILTER(?clauseType != proc:Clause)` removes the generic base type and shows only specific subclasses.

- **ORDER BY**: Sort the result table (for example, by contract, by clause).

With just these pieces you can read and slightly modify all the queries on this page.

### How this page is intended to be used

This page is meant to be a user‑facing explanation that you can show in the documentation server:

- Demonstrate, for each example contract, the kinds of data that will appear in the knowledge graph
- Explain how ontology, RDF, SHACL, and rules work together
- Provide example queries that users can run themselves to see the extracted structure

If you ingest new documents, you can follow the same pattern:

- Use the ingestion pipeline to load them
- Inspect the generated RDF and inferred triples via Fuseki
- Optionally extend this page with specific examples and screenshots from your environment

