#!/usr/bin/env python3
"""
Code-Based Query Library

This module contains proven, working code patterns for common Odoo queries.
These are adapted from your existing CRUD Autogen Agent patterns.
"""

import re
import time
import logging
from typing import Dict, List, Any, Optional
from dynamic_query_engine import QueryResult

logger = logging.getLogger(__name__)

class CodeBasedQueryLibrary:
    """Library of proven, working query functions"""
    
    def __init__(self, odoo_client=None):
        self.odoo_client = odoo_client
        self.query_functions = {}
        self._register_queries()
    
    def _register_queries(self):
        """Register proven working code patterns"""
        
        # Pattern 1: Finding Open invoices for a Customer
        self.query_functions['customer_open_invoices'] = {
            'patterns': [
                r'(?:open|unpaid|outstanding)\s+(?:invoices?|bills?)\s+for\s+(?:customer|client|partner)\s+(.+)',
                r'show.*(?:invoices?|bills?).*for.*(.+)',
                r'(?:invoices?|bills?).*(?:customer|client).*(.+)',
            ],
            'function': self.get_customer_open_invoices,
            'description': 'Get open/unpaid invoices for a specific customer'
        }
        
        # Pattern 2: Finding Warehouses for a product
        self.query_functions['product_warehouses'] = {
            'patterns': [
                r'(?:warehouses?|locations?)\s+for\s+(.+)',
                r'where.*(?:is|located).*(.+)',
                r'(?:find|show).*(?:warehouses?|locations?).*(.+)',
            ],
            'function': self.get_product_warehouses,
            'description': 'Find warehouses/locations where a product is stored'
        }
        
        # Pattern 3: Stock quantity for a product in warehouse
        self.query_functions['product_stock_quantity'] = {
            'patterns': [
                r'(?:stock|inventory|quantity)\s+(?:of|for)\s+(.+)',
                r'how\s+(?:much|many).*(.+).*(?:in\s+stock|available)',
                r'(?:quantity|stock\s+level).*(.+)',
            ],
            'function': self.get_product_stock_quantity,
            'description': 'Get stock quantity for a product'
        }
        
        # Additional common patterns
        self.query_functions['customer_all_invoices'] = {
            'patterns': [
                r'(?:all\s+)?(?:invoices?|bills?)\s+for\s+(?:customer|client|partner)\s+(.+)',
                r'(?:customer|client)\s+(.+)\s+(?:invoices?|bills?)',
            ],
            'function': self.get_customer_all_invoices,
            'description': 'Get all invoices for a specific customer'
        }
        
        self.query_functions['product_details'] = {
            'patterns': [
                r'(?:details|info|information)\s+(?:about|for)\s+(?:product\s+)?(.+)',
                r'(?:show|find)\s+(?:product\s+)?(.+)(?:\s+details)?',
            ],
            'function': self.get_product_details,
            'description': 'Get detailed information about a product'
        }
    
    def match_query(self, user_query: str) -> Optional[Dict[str, Any]]:
        """Try to match user query against registered patterns"""
        query_lower = user_query.lower().strip()
        
        for query_name, config in self.query_functions.items():
            for pattern in config['patterns']:
                match = re.search(pattern, query_lower, re.IGNORECASE)
                if match:
                    # Extract parameters from the match
                    params = {'entity_name': match.group(1).strip()}
                    
                    logger.info(f"Matched query '{user_query}' to pattern '{query_name}'")
                    return {
                        'function': config['function'],
                        'params': params,
                        'description': config['description'],
                        'pattern_name': query_name
                    }
        
        return None
    
    def execute_matched_query(self, match_result: Dict[str, Any]) -> QueryResult:
        """Execute a matched query function"""
        try:
            start_time = time.time()
            function = match_result['function']
            params = match_result['params']
            
            # Execute the function
            result_data = function(**params)
            execution_time = time.time() - start_time
            
            if isinstance(result_data, dict) and 'error' in result_data:
                return QueryResult(
                    success=False,
                    error=result_data['error'],
                    method='code_based',
                    execution_time=execution_time
                )
            
            # Determine count
            count = 0
            if isinstance(result_data, dict):
                if 'data' in result_data:
                    count = len(result_data['data']) if isinstance(result_data['data'], list) else 1
                    data = result_data
                else:
                    count = 1
                    data = result_data
            elif isinstance(result_data, list):
                count = len(result_data)
                data = {'data': result_data, 'count': count}
            else:
                count = 1
                data = result_data
            
            return QueryResult(
                success=True,
                data=data,
                count=count,
                method='code_based',
                execution_time=execution_time
            )
            
        except Exception as e:
            logger.error(f"Error executing code-based query: {str(e)}")
            return QueryResult(
                success=False,
                error=f"Query execution failed: {str(e)}",
                method='code_based'
            )
    
    # ==================== PROVEN QUERY FUNCTIONS ====================
    # These are adapted from your working CRUD Autogen Agent code
    
    def get_customer_open_invoices(self, entity_name: str) -> Dict[str, Any]:
        """
        Get open/unpaid invoices for a customer
        Adapted from your working code
        """
        try:
            if not self.odoo_client:
                return {'error': 'Odoo client not available'}
            
            # Find the partner ID for the customer
            partner_search = self.odoo_client.env['res.partner'].search([
                ('name', 'ilike', entity_name)
            ])
            
            if not partner_search:
                return {'error': f'Customer "{entity_name}" not found'}
            
            partner_id = partner_search[0]
            
            # Search for open invoices for the partner (your proven logic)
            invoices = self.odoo_client.env['account.move'].search_read([
                ('partner_id', '=', partner_id),
                ('move_type', '=', 'out_invoice'),
                ('payment_state', 'in', ['not_paid', 'partial'])
            ], [
                'name', 'invoice_date', 'amount_total', 'currency_id', 'payment_state', 'state'
            ])
            
            # Format the results
            formatted_invoices = []
            for invoice in invoices:
                formatted_invoices.append({
                    'invoice_number': invoice['name'],
                    'invoice_date': invoice['invoice_date'],
                    'total_amount': invoice['amount_total'],
                    'currency': invoice['currency_id'][1] if invoice['currency_id'] else 'USD',
                    'payment_state': invoice['payment_state'],
                    'state': invoice['state']
                })
            
            return {
                'success': True,
                'customer_name': entity_name,
                'data': formatted_invoices,
                'count': len(formatted_invoices),
                'total_amount': sum(inv['total_amount'] for inv in formatted_invoices)
            }
            
        except Exception as e:
            logger.error(f"Error getting customer open invoices: {str(e)}")
            return {'error': f'Failed to retrieve invoices: {str(e)}'}
    
    def get_product_warehouses(self, entity_name: str) -> Dict[str, Any]:
        """
        Find warehouses where a product is located
        Adapted from your working code
        """
        try:
            if not self.odoo_client:
                return {'error': 'Odoo client not available'}
            
            # Find the product ID
            product_search = self.odoo_client.env['product.product'].search([
                ('name', 'ilike', entity_name)
            ])
            
            if not product_search:
                return {'error': f'Product "{entity_name}" not found'}
            
            product_id = product_search[0]
            
            # Find stock quant records for the product (your proven logic)
            quants = self.odoo_client.env['stock.quant'].search_read([
                ('product_id', '=', product_id),
                ('quantity', '>', 0)  # Only locations with stock
            ], ['location_id', 'quantity'])
            
            if not quants:
                return {
                    'success': True,
                    'product_name': entity_name,
                    'data': [],
                    'message': f'Product "{entity_name}" is not available in any warehouse'
                }
            
            # Get warehouse information for each location
            warehouses = {}
            for quant in quants:
                location_id = quant['location_id'][0]
                
                # Get the warehouse for the location
                location = self.odoo_client.env['stock.location'].browse(location_id)
                if location.warehouse_id:
                    warehouse_name = location.warehouse_id.name
                    if warehouse_name not in warehouses:
                        warehouses[warehouse_name] = {
                            'warehouse_name': warehouse_name,
                            'total_quantity': 0,
                            'locations': []
                        }
                    
                    warehouses[warehouse_name]['total_quantity'] += quant['quantity']
                    warehouses[warehouse_name]['locations'].append({
                        'location_name': quant['location_id'][1],
                        'quantity': quant['quantity']
                    })
            
            warehouse_list = list(warehouses.values())
            
            return {
                'success': True,
                'product_name': entity_name,
                'data': warehouse_list,
                'count': len(warehouse_list),
                'total_quantity': sum(w['total_quantity'] for w in warehouse_list)
            }
            
        except Exception as e:
            logger.error(f"Error getting product warehouses: {str(e)}")
            return {'error': f'Failed to retrieve warehouse information: {str(e)}'}
    
    def get_product_stock_quantity(self, entity_name: str) -> Dict[str, Any]:
        """
        Get stock quantity for a product across all locations
        """
        try:
            if not self.odoo_client:
                return {'error': 'Odoo client not available'}
            
            # Find the product ID
            product_search = self.odoo_client.env['product.product'].search([
                ('name', 'ilike', entity_name)
            ])
            
            if not product_search:
                return {'error': f'Product "{entity_name}" not found'}
            
            product_id = product_search[0]
            
            # Get stock quantities
            quants = self.odoo_client.env['stock.quant'].search_read([
                ('product_id', '=', product_id)
            ], ['location_id', 'quantity', 'reserved_quantity'])
            
            total_quantity = 0
            available_quantity = 0
            locations = []
            
            for quant in quants:
                total_quantity += quant['quantity']
                available_quantity += (quant['quantity'] - quant['reserved_quantity'])
                
                if quant['quantity'] > 0:  # Only show locations with stock
                    locations.append({
                        'location': quant['location_id'][1],
                        'quantity': quant['quantity'],
                        'reserved': quant['reserved_quantity'],
                        'available': quant['quantity'] - quant['reserved_quantity']
                    })
            
            return {
                'success': True,
                'product_name': entity_name,
                'total_quantity': total_quantity,
                'available_quantity': available_quantity,
                'reserved_quantity': total_quantity - available_quantity,
                'locations': locations,
                'count': len(locations)
            }
            
        except Exception as e:
            logger.error(f"Error getting product stock: {str(e)}")
            return {'error': f'Failed to retrieve stock information: {str(e)}'}
    
    def get_customer_all_invoices(self, entity_name: str) -> Dict[str, Any]:
        """Get all invoices (paid and unpaid) for a customer"""
        try:
            if not self.odoo_client:
                return {'error': 'Odoo client not available'}
            
            # Find the partner ID
            partner_search = self.odoo_client.env['res.partner'].search([
                ('name', 'ilike', entity_name)
            ])
            
            if not partner_search:
                return {'error': f'Customer "{entity_name}" not found'}
            
            partner_id = partner_search[0]
            
            # Get all customer invoices
            invoices = self.odoo_client.env['account.move'].search_read([
                ('partner_id', '=', partner_id),
                ('move_type', '=', 'out_invoice')
            ], [
                'name', 'invoice_date', 'amount_total', 'currency_id', 'payment_state', 'state'
            ], order='invoice_date desc')
            
            # Categorize invoices
            paid_invoices = []
            unpaid_invoices = []
            total_paid = 0
            total_unpaid = 0
            
            for invoice in invoices:
                invoice_data = {
                    'invoice_number': invoice['name'],
                    'invoice_date': invoice['invoice_date'],
                    'total_amount': invoice['amount_total'],
                    'currency': invoice['currency_id'][1] if invoice['currency_id'] else 'USD',
                    'payment_state': invoice['payment_state'],
                    'state': invoice['state']
                }
                
                if invoice['payment_state'] == 'paid':
                    paid_invoices.append(invoice_data)
                    total_paid += invoice['amount_total']
                else:
                    unpaid_invoices.append(invoice_data)
                    total_unpaid += invoice['amount_total']
            
            return {
                'success': True,
                'customer_name': entity_name,
                'all_invoices': invoices,
                'paid_invoices': paid_invoices,
                'unpaid_invoices': unpaid_invoices,
                'total_invoices': len(invoices),
                'total_paid': total_paid,
                'total_unpaid': total_unpaid,
                'count': len(invoices)
            }
            
        except Exception as e:
            logger.error(f"Error getting customer all invoices: {str(e)}")
            return {'error': f'Failed to retrieve invoices: {str(e)}'}
    
    def get_product_details(self, entity_name: str) -> Dict[str, Any]:
        """Get detailed information about a product"""
        try:
            if not self.odoo_client:
                return {'error': 'Odoo client not available'}
            
            # Find the product
            product_search = self.odoo_client.env['product.template'].search([
                ('name', 'ilike', entity_name)
            ])
            
            if not product_search:
                return {'error': f'Product "{entity_name}" not found'}
            
            product = self.odoo_client.env['product.template'].browse(product_search[0])
            
            # Get stock information
            variants = product.product_variant_ids
            total_stock = sum(variant.qty_available for variant in variants)
            
            product_data = {
                'name': product.name,
                'default_code': product.default_code,
                'list_price': product.list_price,
                'cost_price': product.standard_price,
                'category': product.categ_id.name if product.categ_id else 'No Category',
                'sale_ok': product.sale_ok,
                'purchase_ok': product.purchase_ok,
                'type': product.type,
                'uom': product.uom_id.name if product.uom_id else 'Unit',
                'description': product.description_sale or 'No description',
                'qty_available': total_stock,
                'variants_count': len(variants)
            }
            
            return {
                'success': True,
                'product_name': entity_name,
                'data': product_data,
                'count': 1
            }
            
        except Exception as e:
            logger.error(f"Error getting product details: {str(e)}")
            return {'error': f'Failed to retrieve product details: {str(e)}'} 