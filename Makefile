# Contract Knowledge Graph - Makefile
# Unified interface for all project operations

.PHONY: help
.DEFAULT_GOAL := help

# Colors for output
BLUE := \033[0;34m
GREEN := \033[0;32m
YELLOW := \033[0;33m
RED := \033[0;31m
NC := \033[0m # No Color

# Project paths
PROJECT_ROOT := $(shell pwd)
AGENTS_DIR := $(PROJECT_ROOT)/agents
DOCKER_DIR := $(PROJECT_ROOT)/docker
SCRIPTS_DIR := $(PROJECT_ROOT)/scripts

# Python environment
PYTHON := uv run python
PYTEST := uv run pytest
PYTHONPATH := PYTHONPATH=src

##@ Help

help: ## Display this help message
	@echo "$(BLUE)Contract Knowledge Graph - Available Commands$(NC)"
	@echo ""
	@awk 'BEGIN {FS = ":.*##"; printf "\nUsage:\n  make $(GREEN)<target>$(NC)\n"} /^[a-zA-Z_0-9-]+:.*?##/ { printf "  $(GREEN)%-25s$(NC) %s\n", $$1, $$2 } /^##@/ { printf "\n$(BLUE)%s$(NC)\n", substr($$0, 5) } ' $(MAKEFILE_LIST)

##@ Setup & Installation

install: ## Install Python dependencies using uv
	@echo "$(BLUE)Installing Python dependencies...$(NC)"
	cd $(AGENTS_DIR) && uv sync
	@echo "$(GREEN)✓ Dependencies installed$(NC)"

setup-env: ## Copy environment template
	@echo "$(BLUE)Setting up environment...$(NC)"
	@if [ ! -f $(AGENTS_DIR)/.env ]; then \
		cp $(AGENTS_DIR)/env.example $(AGENTS_DIR)/.env; \
		echo "$(GREEN)✓ Created .env file from template$(NC)"; \
	else \
		echo "$(YELLOW)⚠ .env file already exists$(NC)"; \
	fi

setup: install setup-env ## Complete setup (install + env)
	@echo "$(GREEN)✓ Setup complete!$(NC)"

##@ Service Management

services-up: ## Start all Docker services (Fuseki, Milvus, Ollama, API, etc.)
	@echo "$(BLUE)Starting all services...$(NC)"
	cd $(DOCKER_DIR) && docker-compose up -d
	@echo "$(GREEN)✓ Services started$(NC)"
	@echo "$(YELLOW)Waiting for services to be ready...$(NC)"
	@sleep 15
	@$(MAKE) health

services-up-ui: ## Start services with UI (includes Attu for Milvus)
	@echo "$(BLUE)Starting services with UI...$(NC)"
	cd $(DOCKER_DIR) && docker-compose --profile with-ui up -d
	@echo "$(GREEN)✓ Services with UI started$(NC)"

services-down: ## Stop all Docker services
	@echo "$(BLUE)Stopping services...$(NC)"
	cd $(DOCKER_DIR) && docker-compose down
	@echo "$(GREEN)✓ Services stopped$(NC)"

services-restart: services-down services-up ## Restart all services

services-logs: ## View logs from all services
	cd $(DOCKER_DIR) && docker-compose logs -f

services-logs-fuseki: ## View Fuseki logs
	cd $(DOCKER_DIR) && docker-compose logs -f fuseki

services-logs-milvus: ## View Milvus logs
	cd $(DOCKER_DIR) && docker-compose logs -f milvus

services-status: ## Check status of all services
	cd $(DOCKER_DIR) && docker-compose ps

health: ## Check health of all services
	@echo "$(BLUE)Checking service health...$(NC)"
	cd $(AGENTS_DIR) && $(PYTHONPATH) $(PYTHON) ../scripts/utilities/health_check.py

##@ Agents API (Docker)

api-build: ## Build agents API Docker image
	@echo "$(BLUE)Building agents API image...$(NC)"
	cd $(DOCKER_DIR) && docker-compose build agents-api
	@echo "$(GREEN)✓ API image built$(NC)"

api-up: ## Start agents API service
	@echo "$(BLUE)Starting agents API...$(NC)"
	cd $(DOCKER_DIR) && docker-compose up -d agents-api
	@echo "$(GREEN)✓ API started at http://localhost:8001$(NC)"

api-down: ## Stop agents API service
	@echo "$(BLUE)Stopping agents API...$(NC)"
	cd $(DOCKER_DIR) && docker-compose stop agents-api
	@echo "$(GREEN)✓ API stopped$(NC)"

api-restart: api-down api-up ## Restart agents API service

api-logs: ## View agents API logs
	cd $(DOCKER_DIR) && docker-compose logs -f agents-api

api-shell: ## Open shell in agents API container
	cd $(DOCKER_DIR) && docker-compose exec agents-api /bin/bash

api-health: ## Check agents API health
	@curl -f http://localhost:8001/health || echo "$(RED)API not healthy$(NC)"

api-test: ## Run tests in API container
	cd $(DOCKER_DIR) && docker-compose exec agents-api pytest tests/ -v

##@ Data Management

data-load-all: ## Load ontology and sample data into Fuseki
	@echo "$(BLUE)Loading all data...$(NC)"
	cd $(AGENTS_DIR) && $(PYTHONPATH) $(PYTHON) ../scripts/data/load_data.py --all
	@echo "$(GREEN)✓ Data loaded$(NC)"

data-load-ontology: ## Load ontology only
	@echo "$(BLUE)Loading ontology...$(NC)"
	cd $(AGENTS_DIR) && $(PYTHONPATH) $(PYTHON) ../scripts/data/load_data.py --ontology

data-setup-text-index: ## Setup Fuseki with text indexing
	@echo "$(BLUE)Setting up Fuseki text index...$(NC)"
	cd $(AGENTS_DIR) && $(PYTHONPATH) $(PYTHON) ../scripts/setup/setup_fuseki_with_text_index.py

data-load-sample: ## Load sample data only
	@echo "$(BLUE)Loading sample data...$(NC)"
	cd $(AGENTS_DIR) && $(PYTHONPATH) $(PYTHON) ../scripts/data/load_data.py --sample

data-setup-fuseki: ## Setup Fuseki dataset
	@echo "$(BLUE)Setting up Fuseki dataset...$(NC)"
	cd $(AGENTS_DIR) && $(PYTHONPATH) $(PYTHON) ../scripts/setup/setup_fuseki.py

data-index-clauses: ## Index clauses in Milvus
	@echo "$(BLUE)Indexing clauses...$(NC)"
	cd $(AGENTS_DIR) && $(PYTHONPATH) $(PYTHON) ../scripts/index_clauses.py
	@echo "$(GREEN)✓ Clauses indexed$(NC)"

data-migrate-milvus: ## Migrate Milvus schema
	@echo "$(BLUE)Migrating Milvus schema...$(NC)"
	cd $(AGENTS_DIR) && $(PYTHONPATH) $(PYTHON) ../scripts/setup/migrate_milvus_schema.py

##@ Ingestion Pipeline

ingest: ## Run complete ingestion pipeline on all documents
	@echo "$(BLUE)Running pre-ingestion checks...$(NC)"
	cd $(AGENTS_DIR) && $(PYTHONPATH) $(PYTHON) ../scripts/ingestion/pre_ingestion_check.py
	@echo "$(BLUE)Running ingestion pipeline...$(NC)"
	cd $(AGENTS_DIR) && $(PYTHONPATH) $(PYTHON) ../scripts/ingestion/run_ingestion_pipeline.py
	@echo "$(GREEN)✓ Ingestion complete$(NC)"

ingest-override: ## Force reprocess all documents (skip duplicate detection)
	@echo "$(BLUE)Running pre-ingestion checks...$(NC)"
	cd $(AGENTS_DIR) && $(PYTHONPATH) $(PYTHON) ../scripts/ingestion/pre_ingestion_check.py
	@echo "$(BLUE)Running ingestion with override...$(NC)"
	cd $(AGENTS_DIR) && $(PYTHONPATH) $(PYTHON) ../scripts/ingestion/run_ingestion_pipeline.py --override
	@echo "$(GREEN)✓ Ingestion complete$(NC)"

ingest-single: ## Ingest single document (usage: make ingest-single FILE=path/to/doc.pdf)
	@if [ -z "$(FILE)" ]; then \
		echo "$(RED)Error: FILE parameter required$(NC)"; \
		echo "Usage: make ingest-single FILE=path/to/document.pdf"; \
		exit 1; \
	fi
	@echo "$(BLUE)Ingesting $(FILE)...$(NC)"
	cd $(AGENTS_DIR) && $(PYTHONPATH) $(PYTHON) ../scripts/ingestion/ingest_single_document.py $(FILE)

ingest-test: ## Run full ingestion test
	@echo "$(BLUE)Running ingestion test...$(NC)"
	cd $(AGENTS_DIR) && $(PYTHONPATH) $(PYTHON) tests/ingestion/test_full_ingestion.py

ingest-benchmark: ## Benchmark ingestion performance
	@echo "$(BLUE)Running ingestion benchmark...$(NC)"
	cd $(AGENTS_DIR) && $(PYTHONPATH) $(PYTHON) ../scripts/benchmark_ingestion.py

##@ Retrieval

retrieval-test: ## Test retrieval pipeline
	@echo "$(BLUE)Testing retrieval pipeline...$(NC)"
	cd $(AGENTS_DIR) && $(PYTHONPATH) $(PYTHON) tests/retrieval/test_react_retrieval.py --test react

##@ Querying

query-custom: ## Run custom SPARQL query (usage: make query-custom SPARQL="SELECT * WHERE { ?s ?p ?o } LIMIT 10")
	@if [ -z "$(SPARQL)" ]; then \
		echo "$(RED)Error: SPARQL parameter required$(NC)"; \
		echo "Usage: make query-custom SPARQL=\"SELECT * WHERE { ?s ?p ?o } LIMIT 10\""; \
		exit 1; \
	fi
	cd $(AGENTS_DIR) && $(PYTHONPATH) $(PYTHON) ../scripts/analysis/query_data.py --query "$(SPARQL)"
##@ API Testing

api-query: ## Query API directly (usage: make api-query Q="What are the termination clauses?")
	@if [ -z "$(Q)" ]; then \
		echo "$(RED)Error: Q parameter required$(NC)"; \
		echo "Usage: make api-query Q=\"What are the termination clauses in the contracts?\""; \
		exit 1; \
	fi
	@echo "$(BLUE)Querying API...$(NC)"
	@echo "$(YELLOW)Question: $(Q)$(NC)"
	@echo ""
	@curl -s -X POST http://localhost:8001/api/v1/query \
		-H "Content-Type: application/json" \
		-d "{\"query\": \"$(Q)\", \"max_results\": 10, \"include_reasoning\": true}" | \
		python3 -m json.tool || echo "$(RED)Error: API not responding or invalid response$(NC)"

api-test-simple: ## Test API with simple test cases
	@echo "$(BLUE)Testing API with simple test cases...$(NC)"
	$(PYTHON) $(SCRIPTS_DIR)/test_api_queries.py --yaml agents/tests/test_cases/test_cases_simple.yaml
	@echo "$(GREEN)✓ Simple API tests complete$(NC)"

api-test-medium: ## Test API with medium complexity test cases
	@echo "$(BLUE)Testing API with medium test cases...$(NC)"
	$(PYTHON) $(SCRIPTS_DIR)/test_api_queries.py --yaml agents/tests/test_cases/test_cases_medium.yaml
	@echo "$(GREEN)✓ Medium API tests complete$(NC)"

api-test-complex: ## Test API with complex test cases
	@echo "$(BLUE)Testing API with complex test cases...$(NC)"
	$(PYTHON) $(SCRIPTS_DIR)/test_api_queries.py --yaml agents/tests/test_cases/test_cases_complex.yaml
	@echo "$(GREEN)✓ Complex API tests complete$(NC)"

api-test-all: ## Test API with all test case levels
	@echo "$(BLUE)Running all API tests...$(NC)"
	@$(MAKE) api-test-simple
	@$(MAKE) api-test-medium
	@$(MAKE) api-test-complex
	@echo "$(GREEN)✓ All API tests complete$(NC)"

api-test-custom: ## Test API with custom YAML file (usage: make api-test-custom YAML=path/to/test.yaml)
	@if [ -z "$(YAML)" ]; then \
		echo "$(RED)Error: YAML parameter required$(NC)"; \
		echo "Usage: make api-test-custom YAML=path/to/test_cases.yaml"; \
		exit 1; \
	fi
	@echo "$(BLUE)Testing API with $(YAML)...$(NC)"
	$(PYTHON) $(SCRIPTS_DIR)/test_api_queries.py --yaml $(YAML)


##@ Testing

test: ## Run all tests
	@echo "$(BLUE)Running all tests...$(NC)"
	cd $(AGENTS_DIR) && $(PYTHONPATH) $(PYTEST) tests/ -v

test-verbose: ## Run tests with verbose output
	cd $(AGENTS_DIR) && $(PYTHONPATH) $(PYTEST) tests/ -vv

test-coverage: ## Run tests with coverage report
	cd $(AGENTS_DIR) && $(PYTHONPATH) $(PYTEST) tests/ --cov=src --cov-report=html --cov-report=term

test-fuseki: ## Test Fuseki client
	cd $(AGENTS_DIR) && $(PYTHONPATH) $(PYTEST) tests/storage/test_fuseki_client.py -v

test-complexity: ## Test query complexity detection
	@echo "$(BLUE)Testing complexity detection...$(NC)"
	cd $(AGENTS_DIR) && $(PYTHONPATH) $(PYTHON) tests/retrieval/test_react_retrieval.py --test complexity

##@ Verification

verify: ## Verify complete pipeline
	@echo "$(BLUE)Verifying pipeline...$(NC)"
	cd $(AGENTS_DIR) && $(PYTHONPATH) $(PYTHON) ../scripts/data/verify_complete_pipeline.py

verify-fuseki: ## Verify Fuseki data
	cd $(AGENTS_DIR) && $(PYTHONPATH) $(PYTHON) ../scripts/data/verify_fuseki_data.py

verify-milvus: ## Verify Milvus-Fuseki connection
	cd $(AGENTS_DIR) && $(PYTHONPATH) $(PYTHON) ../scripts/data/verify_milvus_fuseki_connection.py

check-milvus-data: ## Check Milvus collection data and dimension
	@echo "$(BLUE)Checking Milvus collection data...$(NC)"
	cd $(AGENTS_DIR) && $(PYTHONPATH) $(PYTHON) ../scripts/data/check_milvus_data.py

check-fuseki-data: ## Check if Fuseki has data
	@echo "$(BLUE)Checking Fuseki data...$(NC)"
	cd $(AGENTS_DIR) && $(PYTHONPATH) $(PYTHON) ../scripts/data/check_fuseki_data.py

##@ Evaluation & Benchmarking

evaluate: ## Run evaluation with test cases
	@echo "$(BLUE)Running evaluation...$(NC)"
	cd $(AGENTS_DIR) && $(PYTHONPATH) $(PYTHON) ../scripts/evaluation/evaluate_enhanced.py

evaluate-verbose: ## Run evaluation with verbose output
	cd $(AGENTS_DIR) && $(PYTHONPATH) $(PYTHON) ../scripts/evaluation/evaluate_enhanced.py --verbose

evaluate-yaml: ## Evaluate using YAML test file (usage: make evaluate-yaml YAML=tests/test_cases/test_cases_retrieval.yaml)
	@if [ -z "$(YAML)" ]; then \
		echo "$(RED)Error: YAML parameter required$(NC)"; \
		echo "Usage: make evaluate-yaml YAML=tests/test_cases/test_cases_retrieval.yaml"; \
		exit 1; \
	fi
	cd $(AGENTS_DIR) && $(PYTHONPATH) $(PYTHON) ../scripts/evaluation/evaluate_enhanced.py --yaml $(YAML)

evaluate-yaml-verbose: ## Evaluate YAML with verbose output (usage: make evaluate-yaml-verbose YAML=tests/test_cases/test_cases_retrieval.yaml)
	@if [ -z "$(YAML)" ]; then \
		echo "$(RED)Error: YAML parameter required$(NC)"; \
		echo "Usage: make evaluate-yaml-verbose YAML=tests/test_cases_retrieval.yaml"; \
		exit 1; \
	fi
	cd $(AGENTS_DIR) && $(PYTHONPATH) $(PYTHON) ../scripts/evaluation/evaluate_enhanced.py --yaml $(YAML) --verbose

evaluate-case: ## Evaluate specific test case (usage: make evaluate-case CASE=termination_analysis)
	@if [ -z "$(CASE)" ]; then \
		echo "$(RED)Error: CASE parameter required$(NC)"; \
		echo "Usage: make evaluate-case CASE=termination_analysis"; \
		exit 1; \
	fi
	cd $(AGENTS_DIR) && $(PYTHONPATH) $(PYTHON) ../scripts/evaluation/evaluate_enhanced.py --case-id $(CASE)

evaluate-case-yaml: ## Evaluate specific case from YAML (usage: make evaluate-case-yaml YAML=tests/test_cases/test_cases_retrieval.yaml CASE=termination_analysis)
	@if [ -z "$(YAML)" ] || [ -z "$(CASE)" ]; then \
		echo "$(RED)Error: YAML and CASE parameters required$(NC)"; \
		echo "Usage: make evaluate-case-yaml YAML=tests/test_cases_retrieval.yaml CASE=termination_analysis"; \
		exit 1; \
	fi
	cd $(AGENTS_DIR) && $(PYTHONPATH) $(PYTHON) ../scripts/evaluation/evaluate_enhanced.py --yaml $(YAML) --case-id $(CASE)

evaluate-category: ## Evaluate specific category (usage: make evaluate-category CAT=risk)
	@if [ -z "$(CAT)" ]; then \
		echo "$(RED)Error: CAT parameter required$(NC)"; \
		echo "Usage: make evaluate-category CAT=risk"; \
		exit 1; \
	fi
	cd $(AGENTS_DIR) && $(PYTHONPATH) $(PYTHON) ../scripts/evaluation/evaluate_enhanced.py --category $(CAT)

evaluate-category-yaml: ## Evaluate category from YAML (usage: make evaluate-category-yaml YAML=tests/test_cases/test_cases_retrieval.yaml CAT=risk)
	@if [ -z "$(YAML)" ] || [ -z "$(CAT)" ]; then \
		echo "$(RED)Error: YAML and CAT parameters required$(NC)"; \
		echo "Usage: make evaluate-category-yaml YAML=tests/test_cases_retrieval.yaml CAT=risk"; \
		exit 1; \
	fi
	cd $(AGENTS_DIR) && $(PYTHONPATH) $(PYTHON) ../scripts/evaluation/evaluate_enhanced.py --yaml $(YAML) --category $(CAT)

evaluate-retrieval-tests: ## Evaluate retrieval test cases from YAML
	@echo "$(BLUE)Evaluating retrieval test cases...$(NC)"
	cd $(AGENTS_DIR) && $(PYTHONPATH) $(PYTHON) ../scripts/evaluation/evaluate_enhanced.py --yaml tests/test_cases/test_cases_retrieval.yaml --verbose

test-evaluate: ## Quick test evaluation with Phoenix (default: tests/test_cases/test_cases_retrieval.yaml)
	@echo "$(BLUE)Running quick evaluation test with Phoenix observability...$(NC)"
	@if [ -z "$(YAML)" ]; then \
		YAML_FILE=tests/test_cases/test_cases_retrieval.yaml; \
		echo "$(YELLOW)⚠ No YAML file specified, using default: $$YAML_FILE$(NC)"; \
	else \
		YAML_FILE=$(YAML); \
	fi; \
	echo "$(BLUE)Using YAML file: $$YAML_FILE$(NC)"; \
	echo "$(BLUE)Phoenix observability: Enabled (view at http://localhost:6006)$(NC)"; \
	echo ""; \
	cd $(AGENTS_DIR) && $(PYTHONPATH) $(PYTHON) ../scripts/evaluation/evaluate_enhanced.py --yaml $$YAML_FILE --verbose; \
	echo ""; \
	echo "$(GREEN)✓ Evaluation complete!$(NC)"; \
	echo "$(YELLOW)📊 View Phoenix traces at: http://localhost:6006$(NC)"

test-evaluate-simple: ## Evaluate simple YAML test cases (tests/test_cases/test_cases_simple.yaml)
	$(MAKE) test-evaluate YAML=tests/test_cases/test_cases_simple.yaml

test-evaluate-medium: ## Evaluate medium YAML test cases (tests/test_cases/test_cases_medium.yaml)
	$(MAKE) test-evaluate YAML=tests/test_cases/test_cases_medium.yaml

test-evaluate-complex: ## Evaluate complex YAML test cases (tests/test_cases/test_cases_complex.yaml)
	$(MAKE) test-evaluate YAML=tests/test_cases/test_cases_complex.yaml

benchmark: ## Run system benchmark
	@echo "$(BLUE)Running benchmark...$(NC)"
	cd $(AGENTS_DIR) && $(PYTHONPATH) $(PYTHON) ../scripts/benchmark.py

##@ Logs & Analysis

logs-view: ## View latest logs
	cd $(AGENTS_DIR) && $(PYTHONPATH) $(PYTHON) ../scripts/analysis/view_logs.py --last

logs-view-all: ## View all logs
	cd $(AGENTS_DIR) && $(PYTHONPATH) $(PYTHON) ../scripts/analysis/view_logs.py --all

logs-centralize: ## Centralize logs
	cd $(AGENTS_DIR) && $(PYTHONPATH) $(PYTHON) ../scripts/utilities/centralize_logs.py

logs-analyze-ingestion: ## Analyze ingestion logs
	cd $(AGENTS_DIR) && $(PYTHONPATH) $(PYTHON) ../scripts/analysis/analyze_ingestion_logs.py

logs-analyze-ingestion-last: ## Analyze last N ingestion runs (usage: make logs-analyze-ingestion-last N=5)
	@if [ -z "$(N)" ]; then \
		cd $(AGENTS_DIR) && $(PYTHONPATH) $(PYTHON) ../scripts/analysis/analyze_ingestion_logs.py --last 5; \
	else \
		cd $(AGENTS_DIR) && $(PYTHONPATH) $(PYTHON) ../scripts/analysis/analyze_ingestion_logs.py --last $(N); \
	fi

logs-analyze-ingestion-save: ## Analyze ingestion logs and save to file
	cd $(AGENTS_DIR) && $(PYTHONPATH) $(PYTHON) ../scripts/analysis/analyze_ingestion_logs.py --output logs/ingestion/analysis_report.md

logs-analyze-retrieval: ## Analyze retrieval logs
	cd $(AGENTS_DIR) && $(PYTHONPATH) $(PYTHON) ../scripts/analysis/analyze_retrieval_logs.py

logs-analyze-retrieval-last: ## Analyze last N retrieval sessions (usage: make logs-analyze-retrieval-last N=10)
	@if [ -z "$(N)" ]; then \
		cd $(AGENTS_DIR) && $(PYTHONPATH) $(PYTHON) ../scripts/analysis/analyze_retrieval_logs.py --last 10; \
	else \
		cd $(AGENTS_DIR) && $(PYTHONPATH) $(PYTHON) ../scripts/analysis/analyze_retrieval_logs.py --last $(N); \
	fi

logs-analyze-retrieval-save: ## Analyze retrieval logs and save to file
	cd $(AGENTS_DIR) && $(PYTHONPATH) $(PYTHON) ../scripts/analysis/analyze_retrieval_logs.py --last 10 --output logs/retrieval/analysis_report.md

##@ Java/Maven (Jena Core)

maven-clean: ## Clean Maven build
	mvn clean

maven-compile: ## Compile Java code
	mvn compile

maven-test: ## Run Java tests
	mvn test

maven-package: ## Package Java modules
	mvn package

maven-install: ## Install to local Maven repository
	mvn install

##@ Quick Workflows

quickstart: services-up data-load-all data-index-clauses ingest verify ## Complete quickstart workflow
	@echo "$(GREEN)✓ Quickstart complete! System is ready.$(NC)"

daily-dev: services-up test ingest ## Daily development workflow
	@echo "$(GREEN)✓ Daily development tasks complete$(NC)"

full-reset: services-down services-up data-load-all data-index-clauses ## Full system reset
	@echo "$(GREEN)✓ System reset complete$(NC)"

##@ Utilities

clean: ## Clean temporary files and caches
	@echo "$(BLUE)Cleaning temporary files...$(NC)"
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	@echo "$(GREEN)✓ Cleaned$(NC)"

clean-logs: ## Clean log files
	@echo "$(BLUE)Cleaning logs...$(NC)"
	rm -rf $(AGENTS_DIR)/logs/*
	@echo "$(GREEN)✓ Logs cleaned$(NC)"

clean-cache: ## Clean all caches (Redis LLM, embedding, SPARQL query cache)
	@echo "$(BLUE)Cleaning all caches...$(NC)"
	@echo "$(YELLOW)Flushing Redis cache...$(NC)"
	@docker exec contract-jena-redis redis-cli FLUSHALL || echo "$(YELLOW)⚠ Redis not running or not accessible$(NC)"
	@echo "$(GREEN)✓ All caches cleared$(NC)"

clean-all: clean clean-logs clean-cache ## Clean everything (files, logs, and caches)
	@echo "$(GREEN)✓ Everything cleaned$(NC)"

urls: ## Display service URLs
	@echo "$(BLUE)Service URLs:$(NC)"
	@echo "  $(GREEN)API:$(NC)         http://localhost:8001"
	@echo "  $(GREEN)API Docs:$(NC)    http://localhost:8001/docs"
	@echo "  $(GREEN)Fuseki:$(NC)      http://localhost:3030 (admin/admin123)"
	@echo "  $(GREEN)Milvus:$(NC)      http://localhost:19530"
	@echo "  $(GREEN)Attu (UI):$(NC)   http://localhost:8080"
	@echo "  $(GREEN)MinIO:$(NC)       http://localhost:9001"
	@echo "  $(GREEN)Ollama:$(NC)      http://localhost:11434"
	@echo "  $(GREEN)Phoenix:$(NC)     http://localhost:6006"
	@echo "  $(GREEN)Docs:$(NC)        http://localhost:8000"

check-deps: ## Check if required tools are installed
	@echo "$(BLUE)Checking dependencies...$(NC)"
	@command -v docker >/dev/null 2>&1 || { echo "$(RED)✗ Docker not found$(NC)"; exit 1; }
	@echo "$(GREEN)✓ Docker$(NC)"
	@command -v uv >/dev/null 2>&1 || { echo "$(RED)✗ uv not found$(NC)"; exit 1; }
	@echo "$(GREEN)✓ uv$(NC)"
	@command -v python3 >/dev/null 2>&1 || { echo "$(RED)✗ Python3 not found$(NC)"; exit 1; }
	@echo "$(GREEN)✓ Python3$(NC)"
	@command -v mvn >/dev/null 2>&1 || { echo "$(YELLOW)⚠ Maven not found (optional)$(NC)"; }
	@echo "$(GREEN)✓ All required dependencies found$(NC)"

##@ Documentation

docs-serve: ## Serve documentation locally with live reload (native Python)
	@echo "$(BLUE)Starting documentation server...$(NC)"
	cd $(PROJECT_ROOT) && cd $(AGENTS_DIR) && uv run --with mkdocs-material --with mkdocs-mermaid2-plugin mkdocs serve -f ../mkdocs.yml
	@echo "$(GREEN)✓ Documentation available at http://127.0.0.1:8000$(NC)"

docs-docker-up: ## Start MkDocs documentation server in Docker (auto-reload enabled)
	@echo "$(BLUE)Starting MkDocs Docker service...$(NC)"
	cd $(DOCKER_DIR) && docker-compose up -d mkdocs
	@echo "$(GREEN)✓ MkDocs server started$(NC)"
	@echo "$(YELLOW)📚 Documentation available at: http://localhost:8000$(NC)"
	@echo "$(YELLOW)⚡ Auto-reload enabled - changes will be detected automatically$(NC)"

docs-docker-down: ## Stop MkDocs documentation server
	@echo "$(BLUE)Stopping MkDocs Docker service...$(NC)"
	cd $(DOCKER_DIR) && docker-compose stop mkdocs
	@echo "$(GREEN)✓ MkDocs server stopped$(NC)"

docs-docker-restart: docs-docker-down docs-docker-up ## Restart MkDocs documentation server

docs-docker-logs: ## View MkDocs server logs
	@echo "$(BLUE)Viewing MkDocs logs...$(NC)"
	cd $(DOCKER_DIR) && docker-compose logs -f mkdocs

docs-build: ## Build documentation for production
	@echo "$(BLUE)Building documentation...$(NC)"
	cd $(PROJECT_ROOT) && cd $(AGENTS_DIR) && uv run --with mkdocs-material --with mkdocs-mermaid2-plugin mkdocs build -f ../mkdocs.yml
	@echo "$(GREEN)✓ Documentation built in site/$(NC)"

docs-deploy: ## Deploy documentation to GitHub Pages
	@echo "$(BLUE)Deploying documentation to GitHub Pages...$(NC)"
	cd $(PROJECT_ROOT) && cd $(AGENTS_DIR) && uv run --with mkdocs-material --with mkdocs-mermaid2-plugin mkdocs gh-deploy -f ../mkdocs.yml
	@echo "$(GREEN)✓ Documentation deployed$(NC)"

info: ## Display project information
	@echo "$(BLUE)Contract Knowledge Graph - Project Information$(NC)"
	@echo ""
	@echo "$(GREEN)Project Root:$(NC) $(PROJECT_ROOT)"
	@echo "$(GREEN)Agents Dir:$(NC)   $(AGENTS_DIR)"
	@echo "$(GREEN)Docker Dir:$(NC)   $(DOCKER_DIR)"
	@echo "$(GREEN)Scripts Dir:$(NC)  $(SCRIPTS_DIR)"
	@echo ""
	@echo "$(BLUE)Quick Commands:$(NC)"
	@echo "  make quickstart       - Complete setup and first run"
	@echo "  make ingest           - Run ingestion pipeline"
	@echo "  make test             - Run all tests"
	@echo "  make docs-docker-up   - Start documentation server (Docker)"
	@echo "  make docs-serve       - Start documentation server (local)"
	@echo ""
	@echo "For full command list, run: $(GREEN)make help$(NC)"