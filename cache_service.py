import threading
import time
import logging
from typing import Optional
from optimization_utils import query_cache
from config import config

logger = logging.getLogger(__name__)

class CacheService:
    """Service for managing cache lifecycle and cleanup"""
    
    def __init__(self):
        self.cleanup_thread: Optional[threading.Thread] = None
        self.running = False
        self.cleanup_interval = 300  # 5 minutes
    
    def start(self):
        """Start the cache cleanup service"""
        if self.running:
            return
        
        self.running = True
        self.cleanup_thread = threading.Thread(target=self._cleanup_loop, daemon=True)
        self.cleanup_thread.start()
        logger.info("Cache cleanup service started")
    
    def stop(self):
        """Stop the cache cleanup service"""
        self.running = False
        if self.cleanup_thread:
            self.cleanup_thread.join(timeout=5)
        logger.info("Cache cleanup service stopped")
    
    def _cleanup_loop(self):
        """Main cleanup loop"""
        while self.running:
            try:
                # Clean up expired cache entries
                query_cache.cleanup_expired()
                
                # Log cache statistics
                cache_size = len(query_cache.cache)
                logger.debug(f"Cache cleanup completed. Current cache size: {cache_size}")
                
                # Sleep for cleanup interval
                time.sleep(self.cleanup_interval)
                
            except Exception as e:
                logger.error(f"Cache cleanup error: {str(e)}")
                time.sleep(60)  # Wait 1 minute before retrying
    
    def clear_cache(self):
        """Manually clear all cache entries"""
        query_cache.clear()
        logger.info("Cache manually cleared")
    
    def get_cache_stats(self) -> dict:
        """Get cache statistics"""
        return {
            "cache_size": len(query_cache.cache),
            "max_cache_size": query_cache.max_size,
            "cleanup_interval": self.cleanup_interval,
            "running": self.running
        }

# Global cache service instance
cache_service = CacheService()