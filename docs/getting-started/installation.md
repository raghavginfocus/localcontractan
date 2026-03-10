# Installation Guide

Complete installation instructions for Contract-Jena on different platforms.

## System Requirements

### Minimum Requirements
- **CPU**: 4 cores
- **RAM**: 8GB
- **Disk**: 20GB free space
- **OS**: macOS, Linux, or Windows (WSL2)

### Recommended Requirements
- **CPU**: 8+ cores
- **RAM**: 16GB+
- **Disk**: 50GB+ SSD
- **GPU**: Optional (for local LLM inference)

## Prerequisites

### 1. Install Python 3.11+

=== "macOS"
    ```bash
    # Using Homebrew
    brew install python@3.11
    
    # Verify installation
    python3 --version
    ```

=== "Linux (Ubuntu/Debian)"
    ```bash
    # Add deadsnakes PPA
    sudo add-apt-repository ppa:deadsnakes/ppa
    sudo apt update
    
    # Install Python 3.11
    sudo apt install python3.11 python3.11-venv python3.11-dev
    
    # Verify installation
    python3.11 --version
    ```

=== "Windows (WSL2)"
    ```bash
    # Install WSL2 first
    wsl --install
    
    # Then follow Linux instructions
    ```

### 2. Install uv Package Manager

```bash
# Install uv (recommended)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Verify installation
uv --version
```

### 3. Install Docker & Docker Compose

=== "macOS"
    ```bash
    # Install Docker Desktop
    brew install --cask docker
    
    # Start Docker Desktop
    open -a Docker
    ```

=== "Linux"
    ```bash
    # Install Docker
    curl -fsSL https://get.docker.com | sh
    
    # Install Docker Compose
    sudo apt install docker-compose-plugin
    
    # Add user to docker group
    sudo usermod -aG docker $USER
    newgrp docker
    ```

=== "Windows"
    Download and install [Docker Desktop for Windows](https://www.docker.com/products/docker-desktop/)

### 4. Install Git

```bash
# macOS
brew install git

# Linux
sudo apt install git

# Verify
git --version
```

## Installation Steps

### 1. Clone Repository

```bash
git clone https://github.com/your-org/contract-jena.git
cd contract-jena
```

### 2. Install Python Dependencies

```bash
# Navigate to agents directory
cd agents

# Sync dependencies with uv
uv sync

# Or with pip
pip install -e ".[dev]"
```

### 3. Setup Environment

```bash
# Copy environment template
cp env.example .env

# Edit configuration
nano .env  # or use your preferred editor
```

See [Configuration Guide](configuration.md) for detailed environment setup.

### 4. Start Services

```bash
# Return to project root
cd ..

# Start all services
make services-up

# Wait for services to be ready (15-30 seconds)
make health
```

This starts:
- **Apache Fuseki** (SPARQL store) on port 3030
- **Milvus** (vector database) on port 19530
- **Ollama** (local LLM) on port 11434
- **Phoenix** (observability) on port 6006
- **MinIO** (object storage) on port 9000/9001

### 5. Verify Installation

```bash
# Check service status
make services-status

# Check service health
make health

# View service URLs
make urls
```

Expected output:
```
✓ Fuseki is healthy
✓ Milvus is healthy
✓ Ollama is healthy
✓ Phoenix is healthy
```

## Optional Components

### Install Ollama Models

```bash
# Pull recommended model
ollama pull llama3.1:8b

# Or faster model for testing
ollama pull qwen2.5-coder:7b

# List installed models
ollama list
```

### Install with UI Components

```bash
# Start services with Attu (Milvus UI)
make services-up-ui
```

Access UIs:
- **Fuseki UI**: http://localhost:3030
- **Attu (Milvus)**: http://localhost:8081
- **MinIO Console**: http://localhost:9001
- **Phoenix**: http://localhost:6006

## Platform-Specific Notes

### macOS

**Apple Silicon (M1/M2/M3)**
```bash
# Some packages may need Rosetta
softwareupdate --install-rosetta

# Docker may need more memory
# Docker Desktop → Settings → Resources → Memory: 8GB+
```

### Linux

**Ubuntu/Debian**
```bash
# Install additional dependencies
sudo apt install build-essential libssl-dev libffi-dev python3-dev

# Increase file descriptor limit
echo "* soft nofile 65536" | sudo tee -a /etc/security/limits.conf
echo "* hard nofile 65536" | sudo tee -a /etc/security/limits.conf
```

**RHEL/CentOS/Fedora**
```bash
# Install dependencies
sudo dnf install gcc openssl-devel bzip2-devel libffi-devel
```

### Windows (WSL2)

```bash
# Increase WSL2 memory limit
# Create/edit ~/.wslconfig
[wsl2]
memory=8GB
processors=4

# Restart WSL
wsl --shutdown
```

## Troubleshooting

### Port Conflicts

```bash
# Check if ports are in use
lsof -i :3030  # Fuseki
lsof -i :19530 # Milvus
lsof -i :11434 # Ollama
lsof -i :6006  # Phoenix

# Kill process using port
kill -9 $(lsof -t -i:3030)
```

### Docker Issues

```bash
# Reset Docker
docker system prune -a

# Restart Docker daemon
sudo systemctl restart docker  # Linux
# Or restart Docker Desktop (macOS/Windows)
```

### Permission Errors

```bash
# Fix file permissions
chmod -R 755 agents/
chmod -R 755 scripts/

# Fix Docker permissions (Linux)
sudo usermod -aG docker $USER
newgrp docker
```

### Memory Issues

```bash
# Increase Docker memory
# Docker Desktop → Settings → Resources → Memory: 8GB+

# Check system memory
free -h  # Linux
vm_stat  # macOS
```

## Uninstallation

### Remove Services

```bash
# Stop and remove containers
make services-down

# Remove volumes (WARNING: deletes all data)
cd docker
docker-compose down -v
```

### Remove Python Environment

```bash
# With uv
cd agents
rm -rf .venv

# With pip
pip uninstall contract-kg-agents
```

### Remove Repository

```bash
cd ..
rm -rf contract-jena
```

## Next Steps

- **[Configuration Guide](configuration.md)**: Configure environment variables
- **[Quick Start](quickstart.md)**: Run your first ingestion and query
- **[Architecture Overview](../architecture/overview.md)**: Understand the system

## Getting Help

- **Documentation**: Browse the full documentation
- **GitHub Issues**: [Report bugs or request features](https://github.com/your-org/contract-jena/issues)
- **Logs**: Check `agents/logs/` for detailed error messages