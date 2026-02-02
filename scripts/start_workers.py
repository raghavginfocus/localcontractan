#!/usr/bin/env python3
"""
Start worker pool for async queue processing.

This script starts multiple worker processes that consume messages from RabbitMQ
and process queries asynchronously.
"""

import asyncio
import sys
from pathlib import Path

# Add agents/src to path
agents_src = Path(__file__).parent.parent / "agents" / "src"
sys.path.insert(0, str(agents_src))

from message_queue.worker import WorkerPool
from logger import get_module_logger

logger = get_module_logger(__name__)


async def main():
    """Start worker pool."""
    # Get worker pool size from environment or use default
    import os
    num_workers = int(os.getenv("WORKER_POOL_SIZE", "3"))
    
    logger.info(f"Starting worker pool with {num_workers} workers...")
    
    # Create and start worker pool
    pool = WorkerPool(num_workers=num_workers)
    
    try:
        await pool.start()
        logger.info("Worker pool started successfully")
        
        # Keep running until interrupted
        while True:
            await asyncio.sleep(1)
            
    except KeyboardInterrupt:
        logger.info("Shutting down worker pool...")
        await pool.stop()
        logger.info("Worker pool stopped")
    except Exception as e:
        logger.error(f"Error in worker pool: {e}", exc_info=True)
        await pool.stop()
        raise


if __name__ == "__main__":
    asyncio.run(main())


