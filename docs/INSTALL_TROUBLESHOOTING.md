# Installation Troubleshooting Guide

This guide helps resolve common installation issues, especially on macOS with Apple Silicon.

## Common Issues and Solutions

### 1. PyArrow, grpcio, grpcio-tools Build Failures

**Error Message:**
```
Failed to build pyarrow grpcio grpcio-tools
error: failed-wheel-build-for-install
× Failed to build installable wheels for some pyproject.toml based projects
```

**Root Cause:**
These packages require compilation and may not have pre-built wheels for your specific Python/macOS combination.

**Solutions (try in order):**

#### Solution 1: Use Conda (Recommended for macOS)
```bash
# Install conda if not already installed
# Download from: https://docs.conda.io/en/latest/miniconda.html

# Create a new environment
conda create -n finops python=3.11
conda activate finops

# Install problematic packages via conda first
conda install -c conda-forge pyarrow grpcio grpcio-tools

# Then install remaining packages with pip
pip install -r requirements.txt
```

#### Solution 2: Use Homebrew Dependencies (macOS)
```bash
# Install system dependencies
brew install apache-arrow grpc protobuf

# Set environment variables
export GRPC_PYTHON_BUILD_SYSTEM_OPENSSL=1
export GRPC_PYTHON_BUILD_SYSTEM_ZLIB=1
export ARROW_HOME=$(brew --prefix)
export PARQUET_HOME=$(brew --prefix)

# Install packages
pip install -r requirements.txt
```

#### Solution 3: Use Pre-built Wheels
```bash
# Upgrade pip and wheel first
pip install --upgrade pip wheel setuptools

# Install with pre-built wheels only
pip install --only-binary=all -r requirements.txt

# If specific packages fail, install them separately with older versions
pip install pyarrow==14.0.0  # Older version with more wheel support
pip install grpcio==1.60.0 grpcio-tools==1.60.0
```

#### Solution 4: Docker Development (Cross-platform)
```dockerfile
# Use our provided Dockerfile for development
docker build -t finops-dev .
docker run -it -v $(pwd):/workspace finops-dev bash

# Inside container:
cd /workspace
pip install -r requirements.txt
```

### 2. Apple Silicon (M1/M2/M3) Specific Issues

**For Apple Silicon Macs:**

```bash
# Set architecture explicitly
export ARCHFLAGS="-arch arm64"

# Use Rosetta for Intel compatibility if needed
arch -x86_64 pip install -r requirements.txt
```

### 3. Python Version Compatibility

**Recommended Python Versions:**
- Python 3.10 or 3.11 (best compatibility)
- Avoid Python 3.12+ for now (limited package support)

**Check Python Version:**
```bash
python --version
# Should be 3.10.x or 3.11.x
```

### 4. Alternative Requirements for Local Development

If you're still having issues, use this minimal requirements file for local development:

```bash
# Create requirements-local.txt
cat > requirements-local.txt << EOF
# Core Azure Functions (older compatible versions)
azure-functions>=1.20.0,<1.25.0
azure-functions-worker>=1.0.0,<1.2.0

# Essential Azure SDK only
azure-identity>=1.24.0,<2.0.0
azure-monitor-query>=1.2.0,<2.0.0
azure-storage-blob>=12.18.0,<13.0.0

# Simplified data processing
pandas>=2.2.0,<2.4.0
numpy>=1.24.0,<2.0.0
# Skip pyarrow for local dev - pandas will work without it

# Configuration
pydantic>=2.8.0,<3.0.0
python-dotenv>=1.0.0,<2.0.0
requests>=2.31.0,<3.0.0

# Development tools
pytest>=7.4.0,<8.0.0
black>=23.0.0,<24.0.0
EOF

# Install with local requirements
pip install -r requirements-local.txt
```

### 5. Virtual Environment Best Practices

**Create Clean Environment:**
```bash
# Remove existing venv if problematic
rm -rf venv

# Create new virtual environment
python -m venv venv
source venv/bin/activate  # Linux/macOS
# or
venv\Scripts\activate  # Windows

# Upgrade pip first
pip install --upgrade pip setuptools wheel

# Install requirements
pip install -r requirements.txt
```

### 6. Azure Functions Core Tools

**Install Azure Functions Core Tools:**

**macOS (Homebrew):**
```bash
brew tap azure/functions
brew install azure-functions-core-tools@4
```

**macOS (Manual):**
```bash
# Download and install from:
# https://docs.microsoft.com/en-us/azure/azure-functions/functions-run-local
```

### 7. VS Code Development Container

**Use Dev Container (Recommended):**

Create `.devcontainer/devcontainer.json`:
```json
{
    "name": "FinOps Python Development",
    "image": "mcr.microsoft.com/vscode/devcontainers/python:3.11",
    "features": {
        "ghcr.io/devcontainers/features/azure-cli:1": {}
    },
    "postCreateCommand": "pip install -r requirements.txt",
    "customizations": {
        "vscode": {
            "extensions": [
                "ms-python.python",
                "ms-azuretools.vscode-azurefunctions"
            ]
        }
    }
}
```

## Testing Installation

After successful installation, test with:

```bash
# Test imports
python -c "import pandas, numpy, azure.functions; print('✅ Core packages installed')"

# Test Azure Functions
cd src/functions/finops-data-collector
func start

# Test configuration
python -c "from shared.config import get_config; print('✅ Config loading works')"
```

## Production Deployment

**For Azure deployment, these build issues don't matter because:**

1. **Azure Functions uses Linux containers** with pre-built wheels
2. **Consumption plan** handles package installation automatically  
3. **Docker deployment** eliminates local build issues

**Deploy directly:**
```bash
# Deploy without local installation
func azure functionapp publish your-function-app-name --python
```

## Getting Help

If you're still experiencing issues:

1. **Check Python version**: Ensure you're using Python 3.10 or 3.11
2. **Try conda environment**: Most reliable for scientific packages
3. **Use Docker development**: Eliminates platform-specific issues
4. **Deploy to Azure directly**: Bypass local installation entirely

**Report Issues:**
Create an issue in the repository with:
- Operating system and version
- Python version (`python --version`)  
- Full error message
- Installation method attempted