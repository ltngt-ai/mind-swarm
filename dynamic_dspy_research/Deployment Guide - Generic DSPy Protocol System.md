# Deployment Guide - Generic DSPy Protocol System

This guide covers deploying the Generic DSPy Protocol System in production environments.

## System Requirements

### Server Side
- Python 3.8+
- DSPy library (`pip install dspy-ai`)
- Access to LLM provider (OpenAI, Anthropic, etc.)
- File system access for communication directories
- Sufficient memory for signature caching

### Client Side (Sandbox)
- Python 3.8+
- File system access for communication directories
- Network isolation (communication via files only)

## Production Deployment

### 1. Server Setup

#### Install Dependencies
```bash
# Create virtual environment
python -m venv dspy_server_env
source dspy_server_env/bin/activate

# Install required packages
pip install dspy-ai openai anthropic
```

#### Configure DSPy
```python
# server_config.py
import dspy
import os

# Configure your LLM provider
def configure_dspy():
    # Option 1: OpenAI
    if os.getenv('OPENAI_API_KEY'):
        lm = dspy.OpenAI(
            model="gpt-3.5-turbo",
            api_key=os.getenv('OPENAI_API_KEY')
        )
    
    # Option 2: Anthropic
    elif os.getenv('ANTHROPIC_API_KEY'):
        lm = dspy.Claude(
            model="claude-3-sonnet-20240229",
            api_key=os.getenv('ANTHROPIC_API_KEY')
        )
    
    # Option 3: Local model
    else:
        lm = dspy.HFClientTGI(
            model="microsoft/DialoGPT-medium",
            url="http://localhost:8080"
        )
    
    dspy.settings.configure(lm=lm)
```

#### Production Server Script
```python
# production_server.py
import os
import sys
import logging
import signal
from pathlib import Path

from server_config import configure_dspy
from dspy_signature_server import DSPySignatureServer, BrainFileProcessor

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/var/log/dspy_server.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

class ProductionServer:
    def __init__(self):
        self.server = None
        self.processor = None
        self.running = False
    
    def start(self):
        try:
            # Configure DSPy
            configure_dspy()
            
            # Create server with production settings
            self.server = DSPySignatureServer(
                cache_size=500,  # Larger cache for production
                cache_ttl=7200   # 2 hour TTL
            )
            
            # Set up communication directories
            comm_dir = Path(os.getenv('BRAIN_COMM_DIR', '/opt/brain_comm'))
            self.processor = BrainFileProcessor(
                self.server,
                input_dir=str(comm_dir / 'input'),
                output_dir=str(comm_dir / 'output')
            )
            
            logger.info("Starting DSPy signature server...")
            self.running = True
            
            # Start processing (this blocks)
            self.processor.watch_and_process(poll_interval=0.1)
            
        except Exception as e:
            logger.error(f"Server startup failed: {e}")
            sys.exit(1)
    
    def stop(self):
        logger.info("Stopping DSPy signature server...")
        self.running = False
        # Graceful shutdown logic here

def signal_handler(signum, frame):
    logger.info(f"Received signal {signum}")
    server.stop()
    sys.exit(0)

if __name__ == "__main__":
    server = ProductionServer()
    
    # Set up signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    server.start()
```

### 2. Systemd Service

Create `/etc/systemd/system/dspy-server.service`:

```ini
[Unit]
Description=DSPy Signature Server
After=network.target

[Service]
Type=simple
User=dspy
Group=dspy
WorkingDirectory=/opt/dspy_server
Environment=PYTHONPATH=/opt/dspy_server
Environment=OPENAI_API_KEY=your_api_key_here
Environment=BRAIN_COMM_DIR=/opt/brain_comm
ExecStart=/opt/dspy_server/dspy_server_env/bin/python production_server.py
Restart=always
RestartSec=10

# Security settings
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=/opt/brain_comm /var/log

[Install]
WantedBy=multi-user.target
```

Enable and start the service:
```bash
sudo systemctl enable dspy-server
sudo systemctl start dspy-server
sudo systemctl status dspy-server
```

### 3. Directory Structure

```
/opt/dspy_server/
├── dspy_server_env/          # Virtual environment
├── generic_brain_protocol.py
├── dspy_signature_server.py
├── production_server.py
├── server_config.py
└── logs/

/opt/brain_comm/
├── input/                    # Request files from clients
└── output/                   # Response files to clients

/var/log/
└── dspy_server.log          # Server logs
```

### 4. Security Considerations

#### File Permissions
```bash
# Create dedicated user
sudo useradd -r -s /bin/false dspy

# Set up directories
sudo mkdir -p /opt/dspy_server /opt/brain_comm/{input,output}
sudo chown -R dspy:dspy /opt/dspy_server /opt/brain_comm
sudo chmod 755 /opt/brain_comm
sudo chmod 770 /opt/brain_comm/{input,output}
```

#### Network Isolation
- Server should not have direct network access from sandboxes
- Communication only through file system
- Consider using separate file systems or containers

#### API Key Management
```bash
# Use environment variables or secret management
export OPENAI_API_KEY="sk-..."

# Or use systemd environment files
echo "OPENAI_API_KEY=sk-..." | sudo tee /etc/dspy-server.env
sudo chmod 600 /etc/dspy-server.env
```

## Docker Deployment

### Dockerfile
```dockerfile
FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Create app user
RUN useradd -r -s /bin/false dspy

# Set up directories
WORKDIR /app
RUN mkdir -p /app/comm/{input,output} && \
    chown -R dspy:dspy /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY *.py ./
RUN chown -R dspy:dspy /app

# Switch to app user
USER dspy

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import os; exit(0 if os.path.exists('/app/comm/input') else 1)"

# Run the server
CMD ["python", "production_server.py"]
```

### Docker Compose
```yaml
version: '3.8'

services:
  dspy-server:
    build: .
    environment:
      - OPENAI_API_KEY=${OPENAI_API_KEY}
      - BRAIN_COMM_DIR=/app/comm
    volumes:
      - brain_comm:/app/comm
      - ./logs:/app/logs
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "python", "-c", "import os; exit(0 if os.path.exists('/app/comm/input') else 1)"]
      interval: 30s
      timeout: 10s
      retries: 3

volumes:
  brain_comm:
    driver: local
```

## Monitoring and Maintenance

### 1. Health Monitoring

```python
# health_check.py
import time
import json
from pathlib import Path
from generic_brain_protocol import quick_request
from dspy_signature_server import DSPySignatureServer

def health_check():
    try:
        server = DSPySignatureServer()
        
        # Simple test request
        test_request = quick_request(
            task="Health check test",
            inputs={"test": "Test input"},
            outputs={"result": "Test result"},
            input_values={"test": "ping"}
        )
        
        start_time = time.time()
        response = server.process_request(test_request)
        response_time = time.time() - start_time
        
        # Check cache stats
        cache_stats = server.get_cache_stats()
        
        return {
            "status": "healthy",
            "response_time": response_time,
            "cache_size": cache_stats["size"],
            "timestamp": time.time()
        }
        
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e),
            "timestamp": time.time()
        }

if __name__ == "__main__":
    result = health_check()
    print(json.dumps(result, indent=2))
    exit(0 if result["status"] == "healthy" else 1)
```

### 2. Log Monitoring

```bash
# Monitor server logs
tail -f /var/log/dspy_server.log

# Check for errors
grep ERROR /var/log/dspy_server.log

# Monitor cache performance
grep "cache" /var/log/dspy_server.log | tail -20
```

### 3. Performance Metrics

```python
# metrics_collector.py
import time
import json
from dspy_signature_server import DSPySignatureServer

def collect_metrics():
    server = DSPySignatureServer()
    stats = server.get_cache_stats()
    
    metrics = {
        "timestamp": time.time(),
        "cache": {
            "size": stats["size"],
            "max_size": stats["max_size"],
            "hit_rate": calculate_hit_rate(stats),
            "signatures": len(stats["signatures"])
        },
        "memory": get_memory_usage(),
        "disk": get_disk_usage()
    }
    
    return metrics

def calculate_hit_rate(stats):
    total_uses = sum(sig["use_count"] for sig in stats["signatures"])
    unique_signatures = len(stats["signatures"])
    return (total_uses - unique_signatures) / total_uses if total_uses > 0 else 0
```

## Scaling Considerations

### 1. Horizontal Scaling

- Deploy multiple server instances
- Use load balancer for request distribution
- Shared file system for communication directories
- Consider message queue for better distribution

### 2. Cache Optimization

```python
# Optimized cache settings for high load
server = DSPySignatureServer(
    cache_size=1000,    # Larger cache
    cache_ttl=14400     # 4 hour TTL
)
```

### 3. Performance Tuning

- Monitor signature creation vs cache hits
- Optimize frequently used signatures
- Consider signature pre-warming
- Tune polling intervals based on load

## Backup and Recovery

### 1. Configuration Backup
```bash
# Backup configuration
tar -czf dspy_server_backup.tar.gz \
    /opt/dspy_server/*.py \
    /etc/systemd/system/dspy-server.service \
    /etc/dspy-server.env
```

### 2. Cache Persistence
```python
# Optional: Implement cache persistence
class PersistentSignatureCache(SignatureCache):
    def __init__(self, cache_file="/opt/dspy_server/cache.json", **kwargs):
        super().__init__(**kwargs)
        self.cache_file = cache_file
        self.load_cache()
    
    def save_cache(self):
        # Implement cache serialization
        pass
    
    def load_cache(self):
        # Implement cache deserialization
        pass
```

## Troubleshooting

### Common Issues

1. **Permission Denied**: Check file permissions on communication directories
2. **API Rate Limits**: Implement rate limiting and retry logic
3. **Memory Issues**: Monitor cache size and adjust limits
4. **Disk Space**: Monitor communication directories for cleanup

### Debug Mode

```bash
# Enable debug logging
export PYTHONPATH=/opt/dspy_server
export LOG_LEVEL=DEBUG
python production_server.py
```

This deployment guide provides a production-ready setup for the Generic DSPy Protocol System with proper security, monitoring, and scaling considerations.

