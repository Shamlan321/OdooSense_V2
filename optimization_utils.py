import re
import time
from typing import Dict, Any, Optional, Tuple
from functools import lru_cache
from dataclasses import dataclass
import hashlib
import json

@dataclass
class QueryCache:
    """Simple query result cache with TTL"""
    result: Any
    timestamp: float
    ttl: int = 300  # 5 minutes default TTL
    
    def is_expired(self) -> bool:
        return time.time() - self.timestamp > self.ttl

class FastPathRouter:
    """Fast-path routing for common queries without AI classification"""
    
    def __init__(self):
        # Regex patterns for common queries
        self.patterns = {
            'sales_orders_count': [
                r'how many sales orders?',
                r'count.*sales orders?',
                r'number.*sales orders?',
                r'total.*sales orders?'
            ],
            'invoices_count': [
                r'how many invoices?',
                r'count.*invoices?',
                r'number.*invoices?',
                r'total.*invoices?'
            ],
            'customers_count': [
                r'how many customers?',
                r'count.*customers?',
                r'number.*customers?',
                r'total.*customers?'
            ],
            'products_count': [
                r'how many products?',
                r'count.*products?',
                r'number.*products?',
                r'total.*products?'
            ],
            'recent_sales': [
                r'recent sales',
                r'latest sales',
                r'last.*sales orders?'
            ],
            'recent_invoices': [
                r'recent invoices',
                r'latest invoices',
                r'last.*invoices?'
            ]
        }
        
        # Compile regex patterns for better performance
        self.compiled_patterns = {}
        for intent, patterns in self.patterns.items():
            self.compiled_patterns[intent] = [
                re.compile(pattern, re.IGNORECASE) for pattern in patterns
            ]
    
    def detect_intent(self, query: str) -> Optional[str]:
        """Detect intent using regex patterns for fast routing"""
        query_lower = query.lower().strip()
        
        for intent, patterns in self.compiled_patterns.items():
            for pattern in patterns:
                if pattern.search(query_lower):
                    return intent
        
        return None
    
    def get_fast_query_config(self, intent: str) -> Optional[Dict[str, Any]]:
        """Get optimized query configuration for fast-path intents"""
        configs = {
            'sales_orders_count': {
                'model': 'sale.order',
                'method': 'search_count',
                'domain': [],
                'fields': [],
                'response_template': 'We have {count} sales orders in total.'
            },
            'invoices_count': {
                'model': 'account.move',
                'method': 'search_count',
                'domain': [('move_type', '=', 'out_invoice')],
                'fields': [],
                'response_template': 'We have {count} invoices in total.'
            },
            'customers_count': {
                'model': 'res.partner',
                'method': 'search_count',
                'domain': [('is_company', '=', True), ('customer_rank', '>', 0)],
                'fields': [],
                'response_template': 'We have {count} customers in total.'
            },
            'products_count': {
                'model': 'product.product',
                'method': 'search_count',
                'domain': [('active', '=', True)],
                'fields': [],
                'response_template': 'We have {count} active products in total.'
            },
            'recent_sales': {
                'model': 'sale.order',
                'method': 'search_read',
                'domain': [('state', 'in', ['sale', 'done'])],
                'fields': ['name', 'partner_id', 'amount_total', 'date_order'],
                'limit': 5,
                'order': 'date_order desc',
                'response_template': 'Here are the recent sales orders: {formatted_results}'
            },
            'recent_invoices': {
                'model': 'account.move',
                'method': 'search_read',
                'domain': [('move_type', '=', 'out_invoice'), ('state', '=', 'posted')],
                'fields': ['name', 'partner_id', 'amount_total', 'invoice_date'],
                'limit': 5,
                'order': 'invoice_date desc',
                'response_template': 'Here are the recent invoices: {formatted_results}'
            }
        }
        
        return configs.get(intent)

class QueryResultCache:
    """Thread-safe query result cache with TTL"""
    
    def __init__(self, max_size: int = 100, default_ttl: int = 300):
        self.cache: Dict[str, QueryCache] = {}
        self.max_size = max_size
        self.default_ttl = default_ttl
    
    def _generate_key(self, model: str, method: str, domain: list, fields: list, **kwargs) -> str:
        """Generate cache key from query parameters"""
        key_data = {
            'model': model,
            'method': method,
            'domain': domain,
            'fields': sorted(fields) if fields else [],
            'kwargs': sorted(kwargs.items()) if kwargs else []
        }
        key_str = json.dumps(key_data, sort_keys=True)
        return hashlib.md5(key_str.encode()).hexdigest()
    
    def get(self, model: str, method: str, domain: list, fields: list, **kwargs) -> Optional[Any]:
        """Get cached result if available and not expired"""
        key = self._generate_key(model, method, domain, fields, **kwargs)
        
        if key in self.cache:
            cached_item = self.cache[key]
            if not cached_item.is_expired():
                return cached_item.result
            else:
                # Remove expired item
                del self.cache[key]
        
        return None
    
    def set(self, model: str, method: str, domain: list, fields: list, result: Any, ttl: Optional[int] = None, **kwargs):
        """Cache query result with TTL"""
        key = self._generate_key(model, method, domain, fields, **kwargs)
        
        # Implement simple LRU by removing oldest items if cache is full
        if len(self.cache) >= self.max_size:
            # Remove oldest item (first item in dict)
            oldest_key = next(iter(self.cache))
            del self.cache[oldest_key]
        
        self.cache[key] = QueryCache(
            result=result,
            timestamp=time.time(),
            ttl=ttl or self.default_ttl
        )
    
    def clear(self):
        """Clear all cached results"""
        self.cache.clear()
    
    def cleanup_expired(self):
        """Remove expired cache entries"""
        expired_keys = [
            key for key, item in self.cache.items() 
            if item.is_expired()
        ]
        for key in expired_keys:
            del self.cache[key]

# Global instances
fast_path_router = FastPathRouter()
query_cache = QueryResultCache()