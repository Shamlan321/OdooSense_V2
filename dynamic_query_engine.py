#!/usr/bin/env python3
"""
Dynamic Query Engine for Odoo Data Lookup

This module provides safe, flexible data lookup capabilities that can handle
various natural language queries without code generation risks.
"""

import re
import time
import logging
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
import hashlib
import json

logger = logging.getLogger(__name__)

@dataclass
class QueryResult:
    """Result of a dynamic query execution"""
    success: bool
    data: Any = None
    count: int = 0
    error: str = None
    method: str = None  # 'code_based', 'template', 'safe_dynamic', 'llm_fallback'
    execution_time: float = 0
    cached: bool = False

class QueryValidator:
    """Ensure all queries are safe for business operations"""
    
    def __init__(self):
        self.max_records = 1000
        self.allowed_operations = ['search', 'read', 'search_count', 'search_read']
        self.blocked_fields = ['password', 'access_token', 'api_key', 'login', 'oauth_access_token']
        self.blocked_models = [
            'ir.config_parameter', 'ir.attachment', 'ir.mail_server',
            'base.import.tests.models.char', 'res.users'  # Sensitive models
        ]
        self.safe_models = {
            'account.move', 'res.partner', 'product.template', 'product.product',
            'sale.order', 'purchase.order', 'stock.quant', 'stock.picking',
            'crm.lead', 'hr.employee', 'hr.department', 'project.project',
            'project.task', 'stock.warehouse', 'stock.location'
        }
    
    def validate_query(self, query_params: Dict[str, Any]) -> Tuple[bool, str]:
        """Validate query is safe for execution"""
        
        model = query_params.get('model', '')
        
        # Check model whitelist
        if model not in self.safe_models:
            return False, f"Access to model '{model}' is not allowed"
        
        # Check field restrictions
        fields = query_params.get('fields', [])
        for field in fields:
            if any(blocked in field.lower() for blocked in self.blocked_fields):
                return False, f"Access to field '{field}' is restricted"
        
        # Check record limits
        limit = query_params.get('limit', 50)
        if limit > self.max_records:
            return False, f"Record limit exceeded (max: {self.max_records})"
        
        # Validate domain filters
        domain = query_params.get('domain', [])
        if not self._validate_domain(domain):
            return False, "Invalid or unsafe domain filters"
        
        return True, "Query validated"
    
    def _validate_domain(self, domain: List) -> bool:
        """Validate domain filters are safe"""
        try:
            for clause in domain:
                if isinstance(clause, (list, tuple)) and len(clause) >= 3:
                    field, operator, value = clause[0], clause[1], clause[2]
                    
                    # Check for dangerous field access
                    if any(blocked in field.lower() for blocked in self.blocked_fields):
                        return False
                    
                    # Ensure field doesn't access dangerous relations
                    if 'user_id.login' in field or 'create_uid.login' in field:
                        return False
            
            return True
        except Exception:
            return False

class QueryCache:
    """Smart caching system for frequent queries"""
    
    def __init__(self):
        self.cache = {}
        self.cache_ttl = {
            'res.partner': 300,          # 5 minutes - customer data changes moderately
            'account.move': 60,          # 1 minute - financial data changes frequently
            'product.template': 600,     # 10 minutes - product data is relatively stable
            'stock.quant': 30,           # 30 seconds - inventory changes frequently
            'sale.order': 120,           # 2 minutes - sales data changes moderately
            'purchase.order': 120,       # 2 minutes - purchase data changes moderately
            'crm.lead': 180,             # 3 minutes - CRM data changes moderately
            'hr.employee': 1800,         # 30 minutes - employee data is stable
        }
        self.max_cache_size = 1000
    
    def _generate_cache_key(self, query_params: Dict[str, Any]) -> str:
        """Generate a unique cache key for the query"""
        # Create a normalized version of the query for consistent caching
        normalized = {
            'model': query_params.get('model', ''),
            'domain': str(sorted(query_params.get('domain', []))),
            'fields': sorted(query_params.get('fields', [])),
            'limit': query_params.get('limit', 50),
            'order': query_params.get('order', '')
        }
        cache_string = json.dumps(normalized, sort_keys=True)
        return hashlib.md5(cache_string.encode()).hexdigest()
    
    def get_cached_result(self, query_params: Dict[str, Any]) -> Optional[QueryResult]:
        """Get cached result if still valid"""
        cache_key = self._generate_cache_key(query_params)
        model = query_params.get('model', '')
        
        if cache_key in self.cache:
            cached_time, result = self.cache[cache_key]
            ttl = self.cache_ttl.get(model, 300)
            
            if time.time() - cached_time < ttl:
                result.cached = True
                logger.debug(f"Cache hit for query: {cache_key[:8]}...")
                return result
            else:
                # Remove expired cache entry
                del self.cache[cache_key]
        
        return None
    
    def cache_result(self, query_params: Dict[str, Any], result: QueryResult):
        """Cache the query result"""
        if not result.success:
            return  # Don't cache failed queries
        
        cache_key = self._generate_cache_key(query_params)
        
        # Manage cache size
        if len(self.cache) >= self.max_cache_size:
            # Remove oldest entries (simple FIFO)
            oldest_keys = list(self.cache.keys())[:100]
            for key in oldest_keys:
                del self.cache[key]
        
        self.cache[cache_key] = (time.time(), result)
        logger.debug(f"Cached result for query: {cache_key[:8]}...")

class QueryPatternEngine:
    """Extract structured components from natural language queries"""
    
    def __init__(self):
        self.entity_patterns = [
            # Customer/Partner patterns
            (r'(?:invoices?|bills?)\s+for\s+(?:customer|client|partner)\s+([A-Za-z0-9\s&.-]+)', 'customer_name'),
            (r'(?:customer|client|partner)\s+([A-Za-z0-9\s&.-]+)', 'customer_name'),
            
            # Product patterns
            (r'(?:stock|inventory|quantity)\s+(?:of|for)\s+([A-Za-z0-9\s&.-]+)', 'product_name'),
            (r'product\s+([A-Za-z0-9\s&.-]+)', 'product_name'),
            
            # Date patterns
            (r'(?:last|past)\s+(\d+)\s+(days?|weeks?|months?)', 'date_range'),
            (r'(?:this|current)\s+(week|month|year)', 'date_period'),
            (r'(?:from|since)\s+([0-9-/]+)', 'date_from'),
            
            # Warehouse patterns
            (r'(?:warehouse|location)\s+([A-Za-z0-9\s&.-]+)', 'warehouse_name'),
        ]
        
        self.operation_keywords = {
            'search': ['show', 'list', 'find', 'get', 'display', 'view'],
            'count': ['how many', 'count', 'number of', 'total number'],
            'sum': ['total', 'sum', 'amount of', 'total amount'],
            'filter_open': ['open', 'unpaid', 'outstanding', 'pending'],
            'filter_closed': ['closed', 'paid', 'completed', 'done'],
            'filter_draft': ['draft', 'quotation', 'quote'],
        }
        
        self.model_keywords = {
            'account.move': ['invoice', 'bill', 'payment', 'accounting'],
            'res.partner': ['customer', 'client', 'partner', 'contact', 'vendor', 'supplier'],
            'product.template': ['product', 'item', 'goods'],
            'stock.quant': ['stock', 'inventory', 'quantity', 'warehouse'],
            'sale.order': ['sales order', 'sale', 'quotation', 'quote'],
            'purchase.order': ['purchase order', 'purchase', 'po'],
            'crm.lead': ['lead', 'opportunity', 'prospect'],
            'hr.employee': ['employee', 'staff', 'worker', 'team member'],
        }
    
    def parse_query(self, query: str) -> Dict[str, Any]:
        """Parse natural language query into structured components"""
        query_lower = query.lower().strip()
        
        components = {
            'entities': {},
            'operations': [],
            'model': None,
            'filters': [],
            'original_query': query
        }
        
        # Extract entities
        for pattern, entity_type in self.entity_patterns:
            matches = re.findall(pattern, query_lower, re.IGNORECASE)
            if matches:
                if entity_type == 'customer_name':
                    components['entities']['customer_name'] = matches[0].strip()
                elif entity_type == 'product_name':
                    components['entities']['product_name'] = matches[0].strip()
                elif entity_type == 'warehouse_name':
                    components['entities']['warehouse_name'] = matches[0].strip()
        
        # Detect operations
        for operation, keywords in self.operation_keywords.items():
            if any(keyword in query_lower for keyword in keywords):
                components['operations'].append(operation)
        
        # Detect model
        for model, keywords in self.model_keywords.items():
            if any(keyword in query_lower for keyword in keywords):
                components['model'] = model
                break
        
        # Default to search if no operation specified
        if not components['operations']:
            components['operations'] = ['search']
        
        logger.debug(f"Parsed query components: {components}")
        return components

class SafeQueryBuilder:
    """Build safe Odoo queries using whitelisted components"""
    
    def __init__(self):
        self.model_config = {
            'account.move': {
                'fields': ['name', 'partner_id', 'amount_total', 'invoice_date', 'date', 'state', 'payment_state', 'move_type', 'currency_id'],
                'default_fields': ['name', 'partner_id', 'amount_total', 'invoice_date', 'payment_state'],
                'relations': {'partner_id': 'res.partner', 'currency_id': 'res.currency'},
                'filters': {
                    'open': [('payment_state', 'in', ['not_paid', 'partial'])],
                    'paid': [('payment_state', '=', 'paid')],
                    'customer': [('move_type', '=', 'out_invoice')],
                    'vendor': [('move_type', '=', 'in_invoice')],
                }
            },
            'res.partner': {
                'fields': ['name', 'email', 'phone', 'customer_rank', 'supplier_rank', 'city', 'country_id', 'category_id'],
                'default_fields': ['name', 'email', 'phone', 'city'],
                'relations': {'country_id': 'res.country'},
                'filters': {
                    'customer': [('customer_rank', '>', 0)],
                    'supplier': [('supplier_rank', '>', 0)],
                    'company': [('is_company', '=', True)],
                }
            },
            'product.template': {
                'fields': ['name', 'list_price', 'categ_id', 'sale_ok', 'purchase_ok', 'default_code', 'type'],
                'default_fields': ['name', 'list_price', 'categ_id', 'default_code'],
                'relations': {'categ_id': 'product.category'},
                'filters': {
                    'saleable': [('sale_ok', '=', True)],
                    'purchaseable': [('purchase_ok', '=', True)],
                }
            },
            'stock.quant': {
                'fields': ['product_id', 'quantity', 'location_id', 'lot_id', 'package_id'],
                'default_fields': ['product_id', 'quantity', 'location_id'],
                'relations': {'product_id': 'product.product', 'location_id': 'stock.location'},
                'filters': {}
            },
            'sale.order': {
                'fields': ['name', 'partner_id', 'amount_total', 'date_order', 'state', 'user_id'],
                'default_fields': ['name', 'partner_id', 'amount_total', 'date_order', 'state'],
                'relations': {'partner_id': 'res.partner', 'user_id': 'res.users'},
                'filters': {
                    'draft': [('state', 'in', ['draft', 'sent'])],
                    'confirmed': [('state', '=', 'sale')],
                    'done': [('state', '=', 'done')],
                }
            }
        }
    
    def build_query(self, components: Dict[str, Any]) -> Dict[str, Any]:
        """Build safe Odoo query from parsed components"""
        model = components.get('model')
        if not model or model not in self.model_config:
            return {'error': f'Unsupported or unknown model: {model}'}
        
        config = self.model_config[model]
        
        # Build domain
        domain = []
        
        # Add entity filters
        entities = components.get('entities', {})
        if 'customer_name' in entities:
            domain.append(('partner_id.name', 'ilike', entities['customer_name']))
        
        if 'product_name' in entities:
            domain.append(('product_id.name', 'ilike', entities['product_name']))
        
        # Add operation filters
        operations = components.get('operations', [])
        for operation in operations:
            if operation in config['filters']:
                domain.extend(config['filters'][operation])
        
        # Select appropriate fields
        fields = config['default_fields'].copy()
        
        # Determine operation type and limit
        query_type = 'search'
        limit = 50
        
        if 'count' in operations:
            query_type = 'count'
            limit = 0
        
        return {
            'model': model,
            'domain': domain,
            'fields': fields,
            'limit': limit,
            'query_type': query_type,
            'order': self._get_default_order(model)
        }
    
    def _get_default_order(self, model: str) -> str:
        """Get default ordering for model"""
        order_mapping = {
            'account.move': 'invoice_date desc',
            'res.partner': 'name asc',
            'product.template': 'name asc',
            'stock.quant': 'product_id asc',
            'sale.order': 'date_order desc',
        }
        return order_mapping.get(model, 'id desc') 