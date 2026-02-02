#!/bin/bash
# Docker entrypoint script for Contract Knowledge Graph Agents
# Starts both the API server and worker pool

set -e

echo "Starting Contract Knowledge Graph Agents..."

# Start workers in the background
echo "Starting worker pool..."
python -c "
import sys
sys.path.insert(0, '/app/src')
from message_queue.worker import WorkerPool
from message_queue.rabbitmq_client import RabbitMQClient
from message_queue.job_tracker import JobTracker
from logger import get_module_logger
import os
import asyncio

logger = get_module_logger('worker_startup')

async def start_workers():
    try:
        # Get worker pool size from environment
        pool_size = int(os.getenv('WORKER_POOL_SIZE', '3'))
        
        logger.info(f'Starting worker pool with {pool_size} workers...')
        
        # Initialize clients
        queue_client = RabbitMQClient()
        job_tracker = JobTracker()
        
        # Create and start worker pool
        worker_pool = WorkerPool(
            num_workers=pool_size,
            queue_client=queue_client,
            job_tracker=job_tracker
        )
        
        await worker_pool.start()
        logger.info('Worker pool started successfully')
        
        # Keep workers running
        while True:
            await asyncio.sleep(60)
            
    except Exception as e:
        logger.error(f'Failed to start workers: {e}')
        raise

if __name__ == '__main__':
    asyncio.run(start_workers())
" &

WORKER_PID=$!
echo "Workers started with PID: $WORKER_PID"

# Give workers a moment to initialize
sleep 2

# Start API server in foreground
echo "Starting API server..."
exec python -m uvicorn api.main:app --host 0.0.0.0 --port 8000


