#!/usr/bin/env python3
"""
Dynamic Odoo Agent - Truly Dynamic Query Processing

This agent can handle ANY Odoo query by:
1. Understanding the user's intent with LLM
2. Generating appropriate Odoo API calls dynamically
3. Self-correcting when errors occur
4. Retrying with improved requests
"""

import json
import logging
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass
from gemini_client import GeminiClient

logger = logging.getLogger(__name__)

@dataclass
class OdooAPICall:
    """Represents an Odoo API call"""
    model: str
    method: str
    domain: List = None
    fields: List = None
    values: Dict = None
    limit: int = None
    order: str = None
    args: List = None

@dataclass
class ExecutionResult:
    """Result of API call execution"""
    success: bool
    data: Any = None
    error: str = None
    api_call: OdooAPICall = None

class DynamicOdooAgent:
    """Truly dynamic agent that can handle any Odoo query"""
    
    def __init__(self, odoo_client, gemini_client: GeminiClient):
        self.odoo_client = odoo_client
        self.gemini_client = gemini_client
        
        # Initialize Gemini client if not already done
        if not hasattr(self.gemini_client, 'client') or not self.gemini_client.client:
            self.gemini_client.initialize()
            
        self.max_retries = 3
        
        # Common Odoo models for reference
        self.common_models = {
            'customers': 'res.partner',
            'contacts': 'res.partner', 
            'partners': 'res.partner',
            'invoices': 'account.move',
            'bills': 'account.move',
            'payments': 'account.payment',
            'products': 'product.template',
            'items': 'product.product',
            'sales': 'sale.order',
            'orders': 'sale.order',
            'quotations': 'sale.order',
            'purchases': 'purchase.order',
            'employees': 'hr.employee',
            'staff': 'hr.employee',
            'departments': 'hr.department',
            'projects': 'project.project',
            'tasks': 'project.task',
            'leads': 'crm.lead',
            'opportunities': 'crm.lead',
            'inventory': 'stock.quant',
            'stock': 'stock.quant',
            'warehouses': 'stock.warehouse',
            'locations': 'stock.location',
            'companies': 'res.company'
        }
    
    def process_query(self, user_query: str) -> Dict[str, Any]:
        """
        Process any query dynamically by generating appropriate Odoo API calls
        """
        logger.info(f"Processing dynamic query: {user_query}")
        
        attempt = 0
        last_error = None
        
        while attempt < self.max_retries:
            try:
                # Generate API call using LLM
                api_call = self._generate_api_call(user_query, last_error, attempt)
                
                if not api_call:
                    return {
                        'success': False,
                        'error': 'Could not generate valid API call for the query',
                        'query': user_query
                    }
                
                # Execute the API call
                result = self._execute_api_call(api_call)
                
                if result.success:
                    # Format and return successful result
                    formatted_response = self._format_response(result, user_query)
                    
                    return {
                        'success': True,
                        'data': result.data,
                        'response': formatted_response,
                        'api_call': api_call.__dict__,
                        'attempts': attempt + 1,
                        'query': user_query
                    }
                else:
                    # API call failed, prepare for retry
                    last_error = result.error
                    logger.warning(f"API call failed (attempt {attempt + 1}): {result.error}")
                    attempt += 1
                    
            except Exception as e:
                last_error = str(e)
                logger.error(f"Exception in attempt {attempt + 1}: {e}")
                attempt += 1
        
        # All attempts failed
        return {
            'success': False,
            'error': f'Failed after {self.max_retries} attempts. Last error: {last_error}',
            'query': user_query
        }
    
    def _generate_api_call(self, user_query: str, last_error: str = None, attempt: int = 0) -> Optional[OdooAPICall]:
        """Generate Odoo API call using LLM"""
        
        system_prompt = """You are an expert Odoo developer. Generate the appropriate Odoo API call for the user's query.

IMPORTANT INSTRUCTIONS:
1. Respond with ONLY a valid JSON object
2. Use the exact structure shown below
3. Choose the correct Odoo model and method
4. Use proper domain filters, fields, and parameters

Available Methods:
- search_read: Get records with data (most common)
- search: Get only record IDs
- search_count: Count records
- read: Read specific records by ID
- create: Create new records
- write: Update existing records

Common Odoo Models:
- res.partner (customers, contacts, vendors)
- account.move (invoices, bills) 
- product.template/product.product (products)
- sale.order (sales orders, quotations)
- purchase.order (purchase orders)
- hr.employee (employees)
- hr.department (departments)
- stock.quant (inventory/stock)
- crm.lead (leads, opportunities)
- project.project (projects)
- project.task (tasks)

Required JSON Structure:
{
    "model": "model_name",
    "method": "search_read|search|create|write|search_count",
    "domain": [["field", "operator", "value"], ...],
    "fields": ["field1", "field2", ...],
    "limit": 50,
    "order": "field_name desc"
}

For CREATE operations:
{
    "model": "model_name", 
    "method": "create",
    "values": {"field1": "value1", "field2": "value2"}
}

For UPDATE operations:
{
    "model": "model_name",
    "method": "write", 
    "args": [record_ids],
    "values": {"field1": "new_value"}
}

Examples:
Query: "Show me all customers"
{
    "model": "res.partner",
    "method": "search_read",
    "domain": [["customer_rank", ">", 0]],
    "fields": ["name", "email", "phone", "city"],
    "limit": 50
}

Query: "How many employees do we have?"
{
    "model": "hr.employee", 
    "method": "search_count",
    "domain": []
}

Query: "Show headcount by department"
{
    "model": "hr.employee",
    "method": "search_read", 
    "domain": [],
    "fields": ["name", "department_id"],
    "limit": 200
}"""

        if last_error and attempt > 0:
            system_prompt += f"""

PREVIOUS ATTEMPT FAILED with error: {last_error}
Please fix the API call. Common issues:
- Wrong model name 
- Invalid field names
- Incorrect domain syntax
- Missing required fields
- Wrong method for the operation

Generate a corrected API call."""

        user_prompt = f"""Generate the Odoo API call for this query:
"{user_query}"

Respond with ONLY the JSON object, no explanation."""

        try:
            response = self.gemini_client.generate_text(
                f"{system_prompt}\n\n{user_prompt}"
            )
            
            if not response:
                return None
                
            # Clean response
            response = response.strip()
            if response.startswith('```json'):
                response = response.replace('```json', '').replace('```', '').strip()
            elif response.startswith('```'):
                response = response.replace('```', '').strip()
            
            # Parse JSON
            api_data = json.loads(response)
            
            # Create OdooAPICall object
            api_call = OdooAPICall(
                model=api_data.get('model'),
                method=api_data.get('method', 'search_read'),
                domain=api_data.get('domain', []),
                fields=api_data.get('fields'),
                values=api_data.get('values'),
                limit=api_data.get('limit'),
                order=api_data.get('order'),
                args=api_data.get('args')
            )
            
            # Validate required fields
            if not api_call.model or not api_call.method:
                logger.error(f"Invalid API call: missing model or method")
                return None
            
            logger.info(f"Generated API call: {api_call}")
            return api_call
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM response as JSON: {e}")
            logger.error(f"Response was: {response}")
            return None
        except Exception as e:
            logger.error(f"Error generating API call: {e}")
            return None
    
    def _execute_api_call(self, api_call: OdooAPICall) -> ExecutionResult:
        """Execute the generated API call against Odoo"""
        
        try:
            method = api_call.method
            model = api_call.model
            
            if method == 'search_read':
                kwargs = {}
                if api_call.fields:
                    kwargs['fields'] = api_call.fields
                if api_call.limit:
                    kwargs['limit'] = api_call.limit
                # Note: OdooClient.search_read doesn't support 'order' parameter
                    
                data = self.odoo_client.search_read(
                    model, 
                    api_call.domain or [], 
                    **kwargs
                )
                
                return ExecutionResult(
                    success=True,
                    data=data,
                    api_call=api_call
                )
                
            elif method == 'search_count':
                count = self.odoo_client.search_count(model, api_call.domain or [])
                
                return ExecutionResult(
                    success=True,
                    data={'count': count, 'model': model},
                    api_call=api_call
                )
                
            elif method == 'search':
                kwargs = {}
                if api_call.limit:
                    kwargs['limit'] = api_call.limit
                if api_call.order:
                    kwargs['order'] = api_call.order
                    
                ids = self.odoo_client.search(model, api_call.domain or [], **kwargs)
                
                return ExecutionResult(
                    success=True,
                    data={'ids': ids, 'count': len(ids), 'model': model},
                    api_call=api_call
                )
                
            elif method == 'read':
                if not api_call.args:
                    return ExecutionResult(
                        success=False,
                        error="Read method requires record IDs in 'args'",
                        api_call=api_call
                    )
                    
                data = self.odoo_client.read(model, api_call.args, api_call.fields)
                
                return ExecutionResult(
                    success=True,
                    data=data,
                    api_call=api_call
                )
                
            elif method == 'create':
                if not api_call.values:
                    return ExecutionResult(
                        success=False,
                        error="Create method requires 'values' dictionary",
                        api_call=api_call
                    )
                    
                record_id = self.odoo_client.create(model, api_call.values)
                
                return ExecutionResult(
                    success=True,
                    data={'id': record_id, 'model': model, 'values': api_call.values},
                    api_call=api_call
                )
                
            elif method == 'write':
                if not api_call.args or not api_call.values:
                    return ExecutionResult(
                        success=False,
                        error="Write method requires 'args' (record IDs) and 'values'",
                        api_call=api_call
                    )
                    
                success = self.odoo_client.write(model, api_call.args, api_call.values)
                
                return ExecutionResult(
                    success=True,
                    data={'updated': success, 'ids': api_call.args, 'values': api_call.values},
                    api_call=api_call
                )
                
            else:
                return ExecutionResult(
                    success=False,
                    error=f"Unsupported method: {method}",
                    api_call=api_call
                )
                
        except Exception as e:
            error_msg = str(e)
            logger.error(f"API execution failed: {error_msg}")
            
            return ExecutionResult(
                success=False,
                error=error_msg,
                api_call=api_call
            )
    
    def _format_response(self, result: ExecutionResult, user_query: str) -> str:
        """Format the successful result for user presentation"""
        
        data = result.data
        api_call = result.api_call
        
        if api_call.method == 'search_count':
            count = data.get('count', 0)
            model_name = api_call.model.replace('_', ' ').title()
            return f"✅ **Count Result:**\n\n📊 **Total {model_name}:** {count}"
        
        elif api_call.method in ['search_read', 'read']:
            records = data if isinstance(data, list) else []
            
            if not records:
                return f"✅ **No records found** for your query"
            
            # Smart formatting based on model
            model = api_call.model
            
            if model == 'hr.employee' and 'department_id' in (api_call.fields or []):
                # Special formatting for headcount by department
                dept_count = {}
                for emp in records:
                    dept = emp.get('department_id')
                    dept_name = dept[1] if dept else 'No Department'
                    dept_count[dept_name] = dept_count.get(dept_name, 0) + 1
                
                response = f"✅ **Headcount by Department:**\n\n"
                total = 0
                for dept, count in sorted(dept_count.items()):
                    response += f"👥 **{dept}:** {count} employees\n"
                    total += count
                response += f"\n📊 **Total Employees:** {total}"
                return response
            
            else:
                # Generic formatting
                response = f"✅ **Found {len(records)} record(s):**\n\n"
                
                for record in records[:10]:  # Show first 10
                    if 'name' in record:
                        response += f"• **{record['name']}**"
                        # Add additional info if available
                        if 'email' in record and record['email']:
                            response += f" - {record['email']}"
                        if 'phone' in record and record['phone']:
                            response += f" - {record['phone']}"
                        if 'amount_total' in record:
                            response += f" - ${record['amount_total']:.2f}"
                        response += "\n"
                    else:
                        # Show first few fields
                        fields_to_show = []
                        for key, value in record.items():
                            if key != 'id' and value:
                                if isinstance(value, list) and len(value) == 2:
                                    fields_to_show.append(str(value[1]))
                                else:
                                    fields_to_show.append(str(value))
                                if len(fields_to_show) >= 3:
                                    break
                        response += f"• {' - '.join(fields_to_show)}\n"
                
                if len(records) > 10:
                    response += f"\n... and {len(records) - 10} more records"
                
                return response
        
        elif api_call.method == 'create':
            return f"✅ **Record Created Successfully:**\n\n📝 **ID:** {data.get('id')}\n📊 **Model:** {api_call.model}"
        
        elif api_call.method == 'write':
            return f"✅ **Records Updated Successfully:**\n\n📝 **Updated:** {len(api_call.args)} record(s)\n📊 **Model:** {api_call.model}"
        
        else:
            return f"✅ **Operation completed successfully**" 