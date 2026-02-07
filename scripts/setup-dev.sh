#!/bin/bash
# AutoHeal AI - Development Setup Script
# Sets up the local development environment

set -e

echo "======================================"
echo "AutoHeal AI - Development Setup"
echo "======================================"

# Check for required tools
check_tool() {
    if ! command -v "$1" &> /dev/null; then
        echo "❌ $1 is not installed. Please install it first."
        exit 1
    else
        echo "✅ $1 found"
    fi
}

echo ""
echo "Checking required tools..."
check_tool "python3"
check_tool "docker"
check_tool "docker-compose"

# Check Python version
PYTHON_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
echo "✅ Python version: $PYTHON_VERSION"

# Create virtual environment if it doesn't exist
if [ ! -d ".venv" ]; then
    echo ""
    echo "Creating Python virtual environment..."
    python3 -m venv .venv
fi

# Activate virtual environment
source .venv/bin/activate

# Upgrade pip
echo ""
echo "Upgrading pip..."
pip install --upgrade pip

# Install development dependencies
echo ""
echo "Installing development dependencies..."
pip install -r requirements-dev.txt

# Install shared library in development mode
echo ""
echo "Installing shared library..."
pip install -e ./shared 2>/dev/null || echo "Shared library will be available via PYTHONPATH"

# Create necessary directories
echo ""
echo "Creating directories..."
mkdir -p infrastructure/grafana/dashboards
mkdir -p infrastructure/grafana/provisioning/datasources
mkdir -p infrastructure/grafana/provisioning/dashboards
mkdir -p scripts
mkdir -p docs/runbooks
mkdir -p docs/api-contracts

# Set up pre-commit hooks (if pre-commit is installed)
if command -v pre-commit &> /dev/null; then
    echo ""
    echo "Setting up pre-commit hooks..."
    pre-commit install 2>/dev/null || echo "Pre-commit setup skipped"
fi

echo ""
echo "======================================"
echo "✅ Development setup complete!"
echo "======================================"
echo ""
echo "Next steps:"
echo "  1. Activate the virtual environment:"
echo "     source .venv/bin/activate"
echo ""
echo "  2. Start the development stack:"
echo "     docker-compose up -d"
echo ""
echo "  3. Access the services:"
echo "     - Grafana:     http://localhost:3000 (admin/admin)"
echo "     - Prometheus:  http://localhost:9090"
echo "     - Monitoring:  http://localhost:8000/docs"
echo ""
