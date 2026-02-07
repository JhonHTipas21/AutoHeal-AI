# AutoHeal AI - Makefile
# Common operations for development and deployment

.PHONY: help setup build test lint run stop clean

# Default target
help:
	@echo "AutoHeal AI - Available Commands"
	@echo "================================="
	@echo "  make setup        - Setup development environment"
	@echo "  make build        - Build all Docker images"
	@echo "  make test         - Run all tests"
	@echo "  make test-coverage- Run tests with coverage"
	@echo "  make lint         - Run linters"
	@echo "  make run          - Start all services"
	@echo "  make stop         - Stop all services"
	@echo "  make clean        - Clean up containers and images"
	@echo "  make logs         - Follow service logs"

# Setup development environment
setup:
	@echo "Setting up development environment..."
	python -m venv .venv
	. .venv/bin/activate && pip install --upgrade pip
	. .venv/bin/activate && pip install -r requirements-dev.txt
	@echo "Setup complete! Activate with: source .venv/bin/activate"

# Build all Docker images
build:
	@echo "Building all Docker images..."
	docker-compose build

# Run all tests
test:
	@echo "Running tests..."
	@for service in monitoring log-intelligence incident-manager autoheal-agent k8s-executor audit-service; do \
		echo "Testing $$service..."; \
		cd services/$$service && pytest tests/ -v || exit 1; \
		cd ../..; \
	done

# Run tests with coverage
test-coverage:
	@echo "Running tests with coverage..."
	pytest --cov=services --cov-report=html --cov-report=term-missing

# Lint all code
lint:
	@echo "Running linters..."
	ruff check services/ shared/
	mypy services/ shared/ --ignore-missing-imports

# Start all services
run:
	@echo "Starting all services..."
	docker-compose up -d
	@echo "Services started. Access Grafana at http://localhost:3000"

# Stop all services
stop:
	@echo "Stopping all services..."
	docker-compose down

# Follow logs
logs:
	docker-compose logs -f

# Clean up
clean:
	@echo "Cleaning up..."
	docker-compose down -v --rmi local
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .mypy_cache -exec rm -rf {} + 2>/dev/null || true
	rm -rf .coverage htmlcov/
	@echo "Cleanup complete!"

# Development helpers
.PHONY: dev-monitoring dev-agent simulate-incident

# Run monitoring service in dev mode
dev-monitoring:
	cd services/monitoring && uvicorn src.main:app --reload --port 8000

# Run autoheal agent in dev mode
dev-agent:
	cd services/autoheal-agent && uvicorn src.main:app --reload --port 8003

# Simulate an incident for testing
simulate-incident:
	./scripts/simulate-incident.sh
