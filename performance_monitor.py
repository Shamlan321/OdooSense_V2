import time
import logging
from functools import wraps
from typing import Dict, List, Optional
from dataclasses import dataclass, field
from threading import Lock

logger = logging.getLogger(__name__)

@dataclass
class PerformanceMetric:
    """Performance metric data"""
    name: str
    duration: float
    timestamp: float
    cache_hit: bool = False
    fast_path: bool = False
    ai_calls: int = 0
    metadata: Dict = field(default_factory=dict)

class PerformanceMonitor:
    """Monitor and track performance metrics"""
    
    def __init__(self, max_metrics: int = 1000):
        self.metrics: List[PerformanceMetric] = []
        self.max_metrics = max_metrics
        self._lock = Lock()
    
    def record_metric(self, metric: PerformanceMetric):
        """Record a performance metric"""
        with self._lock:
            self.metrics.append(metric)
            
            # Keep only the most recent metrics
            if len(self.metrics) > self.max_metrics:
                self.metrics = self.metrics[-self.max_metrics:]
    
    def get_stats(self, last_n: Optional[int] = None) -> Dict:
        """Get performance statistics"""
        with self._lock:
            metrics = self.metrics[-last_n:] if last_n else self.metrics
            
            if not metrics:
                return {
                    'total_requests': 0,
                    'avg_duration': 0,
                    'cache_hit_rate': 0,
                    'fast_path_rate': 0,
                    'avg_ai_calls': 0
                }
            
            total_requests = len(metrics)
            avg_duration = sum(m.duration for m in metrics) / total_requests
            cache_hits = sum(1 for m in metrics if m.cache_hit)
            fast_path_hits = sum(1 for m in metrics if m.fast_path)
            total_ai_calls = sum(m.ai_calls for m in metrics)
            
            return {
                'total_requests': total_requests,
                'avg_duration': round(avg_duration, 3),
                'cache_hit_rate': round((cache_hits / total_requests) * 100, 1),
                'fast_path_rate': round((fast_path_hits / total_requests) * 100, 1),
                'avg_ai_calls': round(total_ai_calls / total_requests, 2),
                'min_duration': round(min(m.duration for m in metrics), 3),
                'max_duration': round(max(m.duration for m in metrics), 3)
            }
    
    def clear_metrics(self):
        """Clear all metrics"""
        with self._lock:
            self.metrics.clear()

def performance_tracker(name: str, monitor: PerformanceMonitor):
    """Decorator to track performance of functions"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.time()
            ai_calls = 0
            cache_hit = False
            fast_path = False
            metadata = {}
            
            try:
                result = func(*args, **kwargs)
                
                # Extract performance info from result if available
                if isinstance(result, dict):
                    cache_hit = result.get('_cache_hit', False)
                    fast_path = result.get('_fast_path', False)
                    ai_calls = result.get('_ai_calls', 0)
                    metadata = result.get('_metadata', {})
                
                return result
            
            finally:
                duration = time.time() - start_time
                metric = PerformanceMetric(
                    name=name,
                    duration=duration,
                    timestamp=time.time(),
                    cache_hit=cache_hit,
                    fast_path=fast_path,
                    ai_calls=ai_calls,
                    metadata=metadata
                )
                monitor.record_metric(metric)
                
                # Log slow operations
                if duration > 5.0:  # Log operations taking more than 5 seconds
                    logger.warning(f"Slow operation detected: {name} took {duration:.2f}s")
        
        return wrapper
    return decorator

# Global performance monitor instance
performance_monitor = PerformanceMonitor()