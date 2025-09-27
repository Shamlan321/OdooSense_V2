#!/usr/bin/env python3
"""
Dynamic Query Processor - Main Orchestrator

This module integrates all dynamic query components and provides the main
interface for processing natural language queries safely and efficiently.
"""

import time
import logging
from typing import Dict, List, Any, Optional
from dynamic_query_engine import QueryValidator, QueryCache, QueryPatternEngine, SafeQueryBuilder, QueryResult
from code_based_queries import CodeBasedQueryLibrary

logger = logging.getLogger(__name__)

class TemplateQueryEngine:
    """Template-based query processing for common patterns"""
    
    def __init__(self):
        self.templates = {
            'customer_invoices_open': {
                'patterns': [
                    r'(?:open|unpaid|outstanding)\s+(?:invoices?|bills?)\s+for\s+(?:customer|client)\s+(.+)',
                ],
                'template': {
                    'model': 'account.move',
                    'domain_template': [
                        ('partner_id.name', 'ilike', '{customer_name}'),
                        ('move_type', '=', 'out_invoice'),
                        ('payment_state', 'in', ['not_paid', 'partial'])
                    ],
                    'fields': ['name', 'partner_id', 'amount_total', 'invoice_date', 'payment_state', 'currency_id'],
                    'order': 'invoice_date desc'
                }
            },
            'product_stock': {
                'patterns': [
                    r'(?:stock|inventory|quantity)\s+(?:of|for)\s+(?:product\s+)?(.+)',
                ],
                'template': {
                    'model': 'stock.quant',
                    'domain_template': [('product_id.name', 'ilike', '{product_name}')],
                    'fields': ['product_id', 'quantity', 'location_id', 'reserved_quantity'],
                    'order': 'product_id asc'
                }
            },
            'customer_list': {
                'patterns': [
                    r'(?:list|show|find)\s+(?:all\s+)?(?:customers?|clients?)',
                    r'(?:customers?|clients?)\s+(?:list|directory)',
                ],
                'template': {
                    'model': 'res.partner',
                    'domain_template': [('customer_rank', '>', 0)],
                    'fields': ['name', 'email', 'phone', 'city', 'country_id'],
                    'order': 'name asc',
                    'limit': 100
                }
            },
            'sales_orders_recent': {
                'patterns': [
                    r'(?:recent|latest)\s+(?:sales?\s+)?orders?',
                    r'(?:sales?\s+)?orders?\s+(?:recent|latest|today)',
                ],
                'template': {
                    'model': 'sale.order',
                    'domain_template': [],
                    'fields': ['name', 'partner_id', 'amount_total', 'date_order', 'state'],
                    'order': 'date_order desc',
                    'limit': 20
                }
            }
        }
    
    def match_template(self, query: str) -> Optional[Dict[str, Any]]:
        """Try to match query against templates"""
        import re
        
        query_lower = query.lower().strip()
        
        for template_name, config in self.templates.items():
            for pattern in config['patterns']:
                match = re.search(pattern, query_lower, re.IGNORECASE)
                if match:
                    # Extract parameters
                    params = {}
                    if match.groups():
                        if 'customer' in pattern:
                            params['customer_name'] = match.group(1).strip()
                        elif 'product' in pattern:
                            params['product_name'] = match.group(1).strip()
                    
                    logger.info(f"Matched query '{query}' to template '{template_name}'")
                    return {
                        'template': config['template'],
                        'params': params,
                        'template_name': template_name
                    }
        
        return None
    
    def build_query_from_template(self, match_result: Dict[str, Any]) -> Dict[str, Any]:
        """Build query parameters from template"""
        template = match_result['template'].copy()
        params = match_result['params']
        
        # Replace placeholders in domain
        domain = []
        for clause in template.get('domain_template', []):
            if isinstance(clause, tuple) and len(clause) == 3:
                field, operator, value = clause
                # Replace parameter placeholders
                if isinstance(value, str) and value.startswith('{') and value.endswith('}'):
                    param_name = value[1:-1]
                    if param_name in params:
                        value = params[param_name]
                    else:
                        continue  # Skip this clause if parameter not found
                domain.append((field, operator, value))
        
        return {
            'model': template['model'],
            'domain': domain,
            'fields': template['fields'],
            'order': template.get('order', ''),
            'limit': template.get('limit', 50),
            'query_type': 'search'
        }

class DynamicQueryProcessor:
    """Main orchestrator for dynamic query processing"""
    
    def __init__(self, odoo_client=None):
        self.odoo_client = odoo_client
        
        # Initialize components
        self.validator = QueryValidator()
        self.cache = QueryCache()
        self.pattern_engine = QueryPatternEngine()
        self.safe_builder = SafeQueryBuilder()
        self.code_library = CodeBasedQueryLibrary(odoo_client)
        self.template_engine = TemplateQueryEngine()
        
        # Performance tracking
        self.stats = {
            'total_queries': 0,
            'cache_hits': 0,
            'code_based_hits': 0,
            'template_hits': 0,
            'safe_dynamic_hits': 0,
            'llm_fallbacks': 0
        }
    
    def process_query(self, user_query: str) -> QueryResult:
        """
        Main entry point for processing natural language queries
        Uses multi-layer approach for maximum reliability and performance
        """
        start_time = time.time()
        self.stats['total_queries'] += 1
        
        logger.info(f"Processing dynamic query: '{user_query}'")
        
        try:
            # Layer 1: Try code-based patterns (fastest, most reliable)
            result = self._try_code_based_query(user_query)
            if result.success:
                self.stats['code_based_hits'] += 1
                result.execution_time = time.time() - start_time
                logger.info(f"Query resolved via code-based pattern in {result.execution_time:.2f}s")
                return result
            
            # Layer 2: Try template-based queries (fast, safe)
            result = self._try_template_query(user_query)
            if result.success:
                self.stats['template_hits'] += 1
                result.execution_time = time.time() - start_time
                logger.info(f"Query resolved via template in {result.execution_time:.2f}s")
                return result
            
            # Layer 3: Try safe dynamic building (flexible, still safe)
            result = self._try_safe_dynamic_query(user_query)
            if result.success:
                self.stats['safe_dynamic_hits'] += 1
                result.execution_time = time.time() - start_time
                logger.info(f"Query resolved via safe dynamic building in {result.execution_time:.2f}s")
                return result
            
            # Layer 4: Return structured error for LLM fallback
            self.stats['llm_fallbacks'] += 1
            execution_time = time.time() - start_time
            
            return QueryResult(
                success=False,
                error="Query could not be processed by dynamic engine - requires LLM fallback",
                method='dynamic_failed',
                execution_time=execution_time
            )
            
        except Exception as e:
            logger.error(f"Dynamic query processing failed: {str(e)}")
            execution_time = time.time() - start_time
            
            return QueryResult(
                success=False,
                error=f"Dynamic query processing error: {str(e)}",
                method='error',
                execution_time=execution_time
            )
    
    def _try_code_based_query(self, user_query: str) -> QueryResult:
        """Try to match against proven code patterns"""
        try:
            match_result = self.code_library.match_query(user_query)
            if match_result:
                return self.code_library.execute_matched_query(match_result)
            
            return QueryResult(success=False, error="No code pattern matched")
            
        except Exception as e:
            logger.error(f"Code-based query failed: {str(e)}")
            return QueryResult(success=False, error=f"Code-based query error: {str(e)}")
    
    def _try_template_query(self, user_query: str) -> QueryResult:
        """Try template-based query processing"""
        try:
            match_result = self.template_engine.match_template(user_query)
            if not match_result:
                return QueryResult(success=False, error="No template matched")
            
            query_params = self.template_engine.build_query_from_template(match_result)
            
            # Check cache first
            cached_result = self.cache.get_cached_result(query_params)
            if cached_result:
                self.stats['cache_hits'] += 1
                return cached_result
            
            # Validate query
            is_valid, validation_msg = self.validator.validate_query(query_params)
            if not is_valid:
                return QueryResult(success=False, error=f"Query validation failed: {validation_msg}")
            
            # Execute query
            result = self._execute_odoo_query(query_params)
            if result.success:
                # Cache the result
                self.cache.cache_result(query_params, result)
            
            return result
            
        except Exception as e:
            logger.error(f"Template query failed: {str(e)}")
            return QueryResult(success=False, error=f"Template query error: {str(e)}")
    
    def _try_safe_dynamic_query(self, user_query: str) -> QueryResult:
        """Try safe dynamic query building"""
        try:
            # Parse the query
            components = self.pattern_engine.parse_query(user_query)
            
            if not components.get('model'):
                return QueryResult(success=False, error="Could not determine data model from query")
            
            # Build safe query
            query_params = self.safe_builder.build_query(components)
            
            if 'error' in query_params:
                return QueryResult(success=False, error=query_params['error'])
            
            # Check cache first
            cached_result = self.cache.get_cached_result(query_params)
            if cached_result:
                self.stats['cache_hits'] += 1
                return cached_result
            
            # Validate query
            is_valid, validation_msg = self.validator.validate_query(query_params)
            if not is_valid:
                return QueryResult(success=False, error=f"Query validation failed: {validation_msg}")
            
            # Execute query
            result = self._execute_odoo_query(query_params)
            if result.success:
                # Cache the result
                self.cache.cache_result(query_params, result)
            
            return result
            
        except Exception as e:
            logger.error(f"Safe dynamic query failed: {str(e)}")
            return QueryResult(success=False, error=f"Safe dynamic query error: {str(e)}")
    
    def _execute_odoo_query(self, query_params: Dict[str, Any]) -> QueryResult:
        """Execute validated query against Odoo"""
        try:
            if not self.odoo_client:
                return QueryResult(success=False, error="Odoo client not available")
            
            model = query_params['model']
            domain = query_params['domain']
            fields = query_params['fields']
            limit = query_params.get('limit', 50)
            order = query_params.get('order', '')
            query_type = query_params.get('query_type', 'search')
            
            start_time = time.time()
            
            if query_type == 'count':
                # Count query
                count = self.odoo_client.env[model].search_count(domain)
                execution_time = time.time() - start_time
                
                return QueryResult(
                    success=True,
                    data={'count': count, 'model': model, 'domain': domain},
                    count=count,
                    method='safe_dynamic',
                    execution_time=execution_time
                )
            
            else:
                # Search query
                search_kwargs = {'limit': limit}
                if order:
                    search_kwargs['order'] = order
                
                records = self.odoo_client.env[model].search_read(
                    domain, fields, **search_kwargs
                )
                
                execution_time = time.time() - start_time
                
                return QueryResult(
                    success=True,
                    data={
                        'records': records,
                        'model': model,
                        'domain': domain,
                        'fields': fields
                    },
                    count=len(records),
                    method='safe_dynamic',
                    execution_time=execution_time
                )
                
        except Exception as e:
            logger.error(f"Odoo query execution failed: {str(e)}")
            return QueryResult(
                success=False,
                error=f"Odoo query execution failed: {str(e)}",
                method='safe_dynamic'
            )
    
    def format_result_for_user(self, result: QueryResult, original_query: str) -> str:
        """Format query result for user presentation"""
        if not result.success:
            return f"❌ **Query Failed:** {result.error}"
        
        if result.method == 'code_based':
            return self._format_code_based_result(result, original_query)
        else:
            return self._format_dynamic_result(result, original_query)
    
    def _format_code_based_result(self, result: QueryResult, original_query: str) -> str:
        """Format code-based query results"""
        data = result.data
        
        if isinstance(data, dict):
            if 'customer_name' in data and 'data' in data:
                # Customer invoice results
                customer = data['customer_name']
                invoices = data['data']
                
                if not invoices:
                    return f"✅ **No open invoices found** for customer '{customer}'"
                
                response = f"✅ **Open Invoices for {customer}:**\n\n"
                total = 0
                
                for inv in invoices[:10]:  # Limit display
                    response += f"• **{inv['invoice_number']}** - {inv['total_amount']} {inv['currency']} ({inv['invoice_date']})\n"
                    total += inv['total_amount']
                
                if len(invoices) > 10:
                    response += f"\n... and {len(invoices) - 10} more invoices"
                
                response += f"\n**Total Outstanding:** {total:.2f}"
                return response
            
            elif 'product_name' in data and 'data' in data:
                # Product warehouse results
                product = data['product_name']
                warehouses = data['data']
                
                if not warehouses:
                    return f"✅ **Product '{product}' not found in any warehouse**"
                
                response = f"✅ **Warehouses for {product}:**\n\n"
                for wh in warehouses:
                    response += f"• **{wh['warehouse_name']}** - {wh['total_quantity']} units\n"
                
                return response
        
        return f"✅ **Query completed** - {result.count} records found"
    
    def _format_dynamic_result(self, result: QueryResult, original_query: str) -> str:
        """Format dynamic query results"""
        data = result.data
        count = result.count
        
        if count == 0:
            return f"✅ **No records found** for your query"
        
        response = f"✅ **Found {count} records:**\n\n"
        
        if isinstance(data, dict) and 'records' in data:
            records = data['records']
            model = data.get('model', '')
            
            # Format based on model type
            if model == 'account.move':
                for record in records[:10]:
                    partner_name = record['partner_id'][1] if record['partner_id'] else 'Unknown'
                    response += f"• **{record['name']}** - {partner_name} - {record['amount_total']}\n"
            
            elif model == 'res.partner':
                for record in records[:10]:
                    response += f"• **{record['name']}** - {record.get('email', 'No email')}\n"
            
            elif model == 'stock.quant':
                for record in records[:10]:
                    product_name = record['product_id'][1] if record['product_id'] else 'Unknown'
                    location_name = record['location_id'][1] if record['location_id'] else 'Unknown'
                    response += f"• **{product_name}** - {record['quantity']} units at {location_name}\n"
            
            else:
                # Generic formatting
                for record in records[:10]:
                    name = record.get('name', record.get('id', 'Unknown'))
                    response += f"• **{name}**\n"
            
            if len(records) > 10:
                response += f"\n... and {len(records) - 10} more records"
        
        return response
    
    def get_performance_stats(self) -> Dict[str, Any]:
        """Get performance statistics"""
        total = self.stats['total_queries']
        if total == 0:
            return self.stats
        
        return {
            **self.stats,
            'cache_hit_rate': (self.stats['cache_hits'] / total) * 100,
            'code_based_rate': (self.stats['code_based_hits'] / total) * 100,
            'template_rate': (self.stats['template_hits'] / total) * 100,
            'dynamic_rate': (self.stats['safe_dynamic_hits'] / total) * 100,
            'fallback_rate': (self.stats['llm_fallbacks'] / total) * 100
        } 