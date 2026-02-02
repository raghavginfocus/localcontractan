# Medium and Complex Test Cases - Summary

## ✅ Completed: Test Cases Updated to Match Real Data

### Medium Test Cases (8 test cases)

**File**: `test_cases_medium.yaml`

1. **Jurisdiction Distribution Analysis** - Analyzes jurisdiction distribution (New Zealand, Hong Kong)
2. **Clause Type Coverage Analysis** - Analyzes clause type distribution across contracts
3. **Contract-Clause Relationships** - Analyzes contract-clause relationships and clause diversity
4. **Party-Contract Mapping** - Maps parties (IBM, CBRE) to contracts and roles
5. **Termination Clause Analysis** - Analyzes termination clauses presence and characteristics
6. **Governing Law and Jurisdiction Analysis** - Analyzes governing law clauses and jurisdictions
7. **Liability Clause Coverage** - Analyzes liability clause presence and types
8. **Intellectual Property Clause Analysis** - Analyzes IP clauses and their provisions

**Based on Real Data:**
- Contracts: Participation Attachment to Supplier Relationship Agreement
- Jurisdictions: NewZealand, HongKongSpecialAdministrativeRegion
- Parties: IBM, CBRE, IBM Corporation, etc.
- Clause Types: TerminationClause, GoverningLawClause, LiabilityClause, GeneralClause, IntellectualPropertyClause, etc.

### Complex Test Cases (9 test cases)

**File**: `test_cases_complex.yaml`

1. **Comprehensive Risk Profile Analysis** ⭐ - Multi-factor risk analysis (ORIGINAL_FAILURE tag)
2. **Cross-Contract Pattern Analysis** - Identifies patterns and similarities across contracts
3. **Jurisdiction-Clause Correlation Analysis** - Analyzes correlation between jurisdictions and clause types
4. **Contract Completeness Assessment** - Evaluates contract completeness by clause types
5. **Party Relationship Network Analysis** - Maps party-contract network relationships
6. **Clause Diversity Index** - Calculates and ranks contracts by clause diversity
7. **Contract Standardization Opportunities** - Identifies standardization opportunities
8. **Ontology Coverage Analysis** - Analyzes ontology coverage and identifies gaps
9. **Contract Similarity Clustering** - Groups contracts by similarity

**Based on Real Data:**
- Multi-hop queries requiring ReAct reasoning
- Cross-contract analysis
- Pattern detection
- Risk assessment combining multiple factors

## Test Case Characteristics

### Medium Test Cases
- **Complexity**: Medium
- **Strategy**: Enhanced hybrid or standard hybrid
- **Focus**: Analytical queries combining multiple data points
- **Expected**: 2-3 KG facts, some vector results

### Complex Test Cases
- **Complexity**: Complex
- **Strategy**: REACT_MULTI_STEP
- **Focus**: Multi-hop reasoning, pattern analysis, risk assessment
- **Expected**: 3+ KG facts, multiple vector results

## Data Alignment

All test cases are aligned with actual data:

✅ **Contracts**: "Participation Attachment to Supplier Relationship Agreement" (and variations)
✅ **Jurisdictions**: NewZealand, HongKongSpecialAdministrativeRegion
✅ **Parties**: IBM, CBRE, IBM Corporation, etc.
✅ **Clause Types**: 
   - TerminationClause
   - GoverningLawClause
   - LiabilityClause
   - GeneralClause
   - EthicalDealingsClause
   - IntellectualPropertyClause
   - ChoiceOfForumClause
   - LimitationOfActionClause
   - NoticeClause

## Running the Tests

### Medium Tests
```bash
make evaluate-yaml YAML=tests/test_cases_medium.yaml
```

### Complex Tests
```bash
make evaluate-yaml YAML=tests/test_cases_complex.yaml
```

## Expected Behavior

### Medium Tests
- Should use HYBRID strategy (smart hybrid with text search)
- Should retrieve 2-3 KG facts per query
- Should combine KG and vector results
- Should analyze patterns across contracts

### Complex Tests
- Should use REACT_MULTI_STEP strategy
- Should decompose queries into multiple steps
- Should retrieve 3+ KG facts
- Should perform multi-hop reasoning
- Should generate comprehensive analysis

## Notes

1. **Comprehensive Risk Profile** is marked with `ORIGINAL_FAILURE` tag - this was the original failing query that motivated ReAct implementation
2. All test cases use actual contract titles, jurisdictions, and clause types from ingested documents
3. Expectations are set to be realistic based on available data
4. Some queries may need refinement based on actual query results
