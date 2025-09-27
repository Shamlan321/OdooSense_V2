#!/usr/bin/env python3
"""
Dynamic Odoo Agent Components

This module implements the core components for making the Odoo AI Agent dynamic,
replacing hardcoded query patterns with intelligent, adaptive processing.
"""

import logging
import json
import time
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
import hashlib
from functools import lru_cache

from odoo_client import odoo_client
from gemini_client import gemini_client
from config import config

logger = logging.getLogger(__name__)

@dataclass
class ModelSchema:
    """Represents an Odoo model schema"""
    name: str
    model: str
    description: str
    fields: Dict[str, Dict[str, Any]]
    relationships: Dict[str, str]
    access_rights: Dict[str, bool]
    
@dataclass
class QueryPlan:
    """Represents a dynamic query execution plan"""
    intent: str
    models: List[str]
    operations: List[Dict[str, Any]]
    filters: List[Dict[str, Any]]
    fields: List[str]
    aggregations: List[Dict[str, Any]]
    output_format: str
    confidence: float
    
@dataclass
class QueryResult:
    """Represents the result of a dynamic query execution"""
    success: bool
    data: Any
    metadata: Dict[str, Any]
    execution_time: float
    query_plan: QueryPlan
    error: Optional[str] = None

class OdooSchemaDiscovery:
    """Dynamically discovers and caches Odoo model schemas"""
    
    def __init__(self, client=None):
        self.client = client or odoo_client
        self._schema_cache = {}
        self._cache_timestamp = None
        self._cache_ttl = 3600  # 1 hour cache TTL
        
    def get_all_models(self, force_refresh: bool = False, limit: int = 50) -> Dict[str, ModelSchema]:
        """Get all available Odoo models with their schemas"""
        if not force_refresh and self._is_cache_valid():
            return self._schema_cache
            
        try:
            logger.info("Discovering Odoo models and schemas...")
            
            # Get common/important models first to avoid timeout
            important_models = [
                'res.partner', 'product.product', 'sale.order', 'purchase.order',
                'account.move', 'stock.picking', 'project.project', 'hr.employee',
                'crm.lead', 'res.users', 'product.template', 'account.account'
            ]
            
            # Get all models but limit processing
            models = self.client.search_read(
                'ir.model',
                [('transient', '=', False)],  # Exclude transient models
                ['name', 'model', 'info'],
                limit=limit * 2  # Get more than we need to filter
            )
            
            logger.info(f"Found {len(models)} models, processing up to {limit}...")
            
            # Prioritize important models
            prioritized_models = []
            remaining_models = []
            
            for model_info in models:
                if model_info['model'] in important_models:
                    prioritized_models.append(model_info)
                else:
                    remaining_models.append(model_info)
            
            # Process prioritized models first, then fill up to limit
            models_to_process = prioritized_models + remaining_models[:limit - len(prioritized_models)]
            
            schema_dict = {}
            processed_count = 0
            
            for model_info in models_to_process:
                model_name = model_info['model']
                try:
                    schema = self._get_model_schema(model_name, model_info)
                    if schema:
                        schema_dict[model_name] = schema
                        processed_count += 1
                        
                        # Add progress logging
                        if processed_count % 10 == 0:
                            logger.info(f"Processed {processed_count}/{len(models_to_process)} models...")
                            
                except Exception as e:
                    logger.warning(f"Failed to get schema for model {model_name}: {e}")
                    continue
            
            self._schema_cache = schema_dict
            self._cache_timestamp = time.time()
            
            logger.info(f"Discovered {len(schema_dict)} Odoo models")
            return schema_dict
            
        except Exception as e:
            logger.error(f"Failed to discover Odoo models: {e}")
            return {}
    
    def _get_model_schema(self, model_name: str, model_info: Dict) -> Optional[ModelSchema]:
        """Get detailed schema for a specific model"""
        try:
            # Get model fields
            fields = self.client.search_read(
                'ir.model.fields',
                [('model', '=', model_name)],
                ['name', 'field_description', 'ttype', 'relation', 'required', 'readonly']
            )
            
            # Process fields into schema format
            field_dict = {}
            relationships = {}
            
            for field in fields:
                field_name = field['name']
                field_dict[field_name] = {
                    'type': field['ttype'],
                    'description': field['field_description'],
                    'required': field['required'],
                    'readonly': field['readonly']
                }
                
                # Track relationships
                if field['relation']:
                    relationships[field_name] = field['relation']
            
            # Get access rights (simplified)
            access_rights = {
                'read': True,  # Assume read access if we can query the model
                'write': True,  # Would need more sophisticated checking
                'create': True,
                'unlink': True
            }
            
            return ModelSchema(
                name=model_info['name'],
                model=model_name,
                description=model_info.get('info', ''),
                fields=field_dict,
                relationships=relationships,
                access_rights=access_rights
            )
            
        except Exception as e:
            logger.error(f"Failed to get schema for model {model_name}: {e}")
            return None
    
    def find_relevant_models(self, query_intent: str, limit: int = 10) -> List[Tuple[str, float]]:
        """Find models relevant to a query using semantic matching"""
        models = self.get_all_models()
        if not models:
            return []
        
        # Use LLM to find relevant models
        model_descriptions = []
        for model_name, schema in models.items():
            # Create searchable description
            field_names = list(schema.fields.keys())[:10]  # Limit for prompt size
            description = f"Model: {model_name}\nName: {schema.name}\nDescription: {schema.description}\nKey fields: {', '.join(field_names)}"
            model_descriptions.append((model_name, description))
        
        # Batch process to avoid token limits
        relevant_models = []
        batch_size = 20
        
        for i in range(0, len(model_descriptions), batch_size):
            batch = model_descriptions[i:i+batch_size]
            batch_results = self._find_relevant_models_batch(query_intent, batch)
            relevant_models.extend(batch_results)
        
        # Sort by relevance score and return top results
        relevant_models.sort(key=lambda x: x[1], reverse=True)
        return relevant_models[:limit]
    
    def _find_relevant_models_batch(self, query_intent: str, model_batch: List[Tuple[str, str]]) -> List[Tuple[str, float]]:
        """Find relevant models in a batch using LLM"""
        try:
            models_text = "\n\n".join([f"{i+1}. {desc}" for i, (_, desc) in enumerate(model_batch)])
            
            prompt = f"""
Analyze this user query and identify which Odoo models are most relevant:

User Query: "{query_intent}"

Available Models:
{models_text}

For each model, provide a relevance score from 0.0 to 1.0 based on how likely it is to contain the data needed to answer the user's query.

Respond with JSON format:
{{
    "relevant_models": [
        {{"model_number": 1, "relevance_score": 0.9}},
        {{"model_number": 2, "relevance_score": 0.3}}
    ]
}}

Only include models with relevance_score > 0.2.
"""
            
            response = gemini_client.generate_text(prompt)
            if not response:
                return []
            
            # Parse response
            try:
                response_clean = response.strip()
                if response_clean.startswith('```json'):
                    response_clean = response_clean[7:]
                if response_clean.endswith('```'):
                    response_clean = response_clean[:-3]
                response_clean = response_clean.strip()
                
                result = json.loads(response_clean)
                relevant_models = []
                
                for item in result.get('relevant_models', []):
                    model_idx = item['model_number'] - 1
                    if 0 <= model_idx < len(model_batch):
                        model_name = model_batch[model_idx][0]
                        score = float(item['relevance_score'])
                        relevant_models.append((model_name, score))
                
                return relevant_models
                
            except (json.JSONDecodeError, KeyError, ValueError) as e:
                logger.warning(f"Failed to parse model relevance response: {e}")
                return []
                
        except Exception as e:
            logger.error(f"Failed to find relevant models: {e}")
            return []
    
    def _is_cache_valid(self) -> bool:
        """Check if schema cache is still valid"""
        if not self._cache_timestamp or not self._schema_cache:
            return False
        return time.time() - self._cache_timestamp < self._cache_ttl

class DynamicQueryAnalyzer:
    """Analyzes user queries and generates execution plans dynamically"""
    
    def __init__(self, schema_discovery: OdooSchemaDiscovery):
        self.schema_discovery = schema_discovery
    
    async def analyze_query(self, user_query: str, context: Dict = None) -> QueryPlan:
        """Analyze user query and generate execution plan"""
        context = context or {}
        
        try:
            # Find relevant models
            relevant_models = self.schema_discovery.find_relevant_models(user_query)
            top_models = [model for model, score in relevant_models[:5]]
            
            if not top_models:
                return QueryPlan(
                    intent="unknown",
                    models=[],
                    operations=[],
                    filters=[],
                    fields=[],
                    aggregations=[],
                    output_format="text",
                    confidence=0.0
                )
            
            # Get detailed schemas for top models
            model_schemas = {}
            all_schemas = self.schema_discovery.get_all_models()
            for model_name in top_models:
                if model_name in all_schemas:
                    model_schemas[model_name] = all_schemas[model_name]
            
            # Generate query plan using LLM
            query_plan = await self._generate_query_plan(user_query, model_schemas, context)
            return query_plan
            
        except Exception as e:
            logger.error(f"Failed to analyze query: {e}")
            return QueryPlan(
                intent="error",
                models=[],
                operations=[],
                filters=[],
                fields=[],
                aggregations=[],
                output_format="text",
                confidence=0.0
            )
    
    async def _generate_query_plan(self, user_query: str, model_schemas: Dict[str, ModelSchema], context: Dict) -> QueryPlan:
        """Generate detailed query execution plan using LLM"""
        try:
            # Prepare model information for prompt
            models_info = []
            for model_name, schema in model_schemas.items():
                # Limit fields to avoid token overflow
                key_fields = list(schema.fields.keys())[:15]
                field_info = {name: schema.fields[name] for name in key_fields}
                
                models_info.append({
                    "model": model_name,
                    "name": schema.name,
                    "description": schema.description,
                    "fields": field_info,
                    "relationships": dict(list(schema.relationships.items())[:5])
                })
            
            prompt = f"""
Analyze this user query and generate a detailed execution plan for querying Odoo data.

User Query: "{user_query}"

Available Models:
{json.dumps(models_info, indent=2)}

Generate a JSON execution plan with this structure:
{{
    "intent": "Brief description of what user wants",
    "models": ["primary_model", "secondary_model"],
    "operations": [
        {{
            "type": "search|count|aggregate",
            "model": "model_name",
            "method": "search_read|search_count|read_group"
        }}
    ],
    "filters": [
        {{
            "field": "field_name",
            "operator": "=",
            "value": "filter_value"
        }}
    ],
    "fields": ["field1", "field2", "field3"],
    "aggregations": [
        {{
            "field": "amount_total",
            "function": "sum|avg|count|max|min"
        }}
    ],
    "output_format": "table|summary|chart|list",
    "confidence": 0.85
}}

Rules:
1. Choose the most appropriate model(s) for the query
2. Use proper Odoo field names and operators
3. Include relevant filters based on the query context
4. Select appropriate fields for the output
5. Set confidence based on query clarity and model relevance
6. For counting queries, use search_count method
7. For aggregations, use read_group method
8. For data retrieval, use search_read method

Return only valid JSON.
"""
            
            response = gemini_client.generate_text(prompt)
            if not response:
                raise ValueError("Empty response from LLM")
            
            # Parse and validate response
            response_clean = response.strip()
            if response_clean.startswith('```json'):
                response_clean = response_clean[7:]
            if response_clean.endswith('```'):
                response_clean = response_clean[:-3]
            response_clean = response_clean.strip()
            
            plan_data = json.loads(response_clean)
            
            # Create QueryPlan object
            query_plan = QueryPlan(
                intent=plan_data.get('intent', 'unknown'),
                models=plan_data.get('models', []),
                operations=plan_data.get('operations', []),
                filters=plan_data.get('filters', []),
                fields=plan_data.get('fields', []),
                aggregations=plan_data.get('aggregations', []),
                output_format=plan_data.get('output_format', 'text'),
                confidence=float(plan_data.get('confidence', 0.5))
            )
            
            return query_plan
            
        except Exception as e:
            logger.error(f"Failed to generate query plan: {e}")
            return QueryPlan(
                intent="error",
                models=[],
                operations=[],
                filters=[],
                fields=[],
                aggregations=[],
                output_format="text",
                confidence=0.0
            )

class DynamicQueryExecutor:
    """Executes dynamic queries against Odoo"""
    
    def __init__(self, client=None):
        self.client = client or odoo_client
    
    async def execute_query(self, query_plan: QueryPlan) -> QueryResult:
        """Execute a dynamic query plan"""
        start_time = time.time()
        
        try:
            if query_plan.confidence < 0.3:
                return QueryResult(
                    success=False,
                    data=None,
                    metadata={},
                    execution_time=time.time() - start_time,
                    query_plan=query_plan,
                    error="Query confidence too low"
                )
            
            results = []
            
            for operation in query_plan.operations:
                try:
                    result = await self._execute_operation(operation, query_plan)
                    results.append(result)
                except Exception as e:
                    logger.error(f"Failed to execute operation {operation}: {e}")
                    return QueryResult(
                        success=False,
                        data=None,
                        metadata={},
                        execution_time=time.time() - start_time,
                        query_plan=query_plan,
                        error=str(e)
                    )
            
            # Combine results if multiple operations
            final_data = results[0] if len(results) == 1 else results
            
            return QueryResult(
                success=True,
                data=final_data,
                metadata={
                    "operations_count": len(query_plan.operations),
                    "models_used": query_plan.models,
                    "confidence": query_plan.confidence
                },
                execution_time=time.time() - start_time,
                query_plan=query_plan
            )
            
        except Exception as e:
            logger.error(f"Failed to execute query plan: {e}")
            return QueryResult(
                success=False,
                data=None,
                metadata={},
                execution_time=time.time() - start_time,
                query_plan=query_plan,
                error=str(e)
            )
    
    async def _execute_operation(self, operation: Dict[str, Any], query_plan: QueryPlan) -> Any:
        """Execute a single operation"""
        model = operation['model']
        method = operation['method']
        op_type = operation['type']
        
        # Build domain from filters
        domain = []
        for filter_item in query_plan.filters:
            if isinstance(filter_item, dict) and 'field' in filter_item:
                domain.append([
                    filter_item['field'],
                    filter_item.get('operator', '='),
                    filter_item['value']
                ])
        
        # Execute based on method
        if method == 'search_count':
            return self.client.search_count(model, domain)
        
        elif method == 'search_read':
            fields = query_plan.fields if query_plan.fields else []
            limit = 50  # Default limit
            return self.client.search_read(model, domain, fields, limit=limit)
        
        elif method == 'read_group':
            # Handle aggregations
            groupby = []
            fields_to_read = query_plan.fields[:]
            
            for agg in query_plan.aggregations:
                field = agg['field']
                function = agg.get('function', 'sum')
                if function in ['sum', 'avg', 'count', 'max', 'min']:
                    fields_to_read.append(f"{field}:{function}")
            
            return self.client.read_group(model, domain, fields_to_read, groupby)
        
        else:
            raise ValueError(f"Unsupported method: {method}")

# Global instances for easy import
schema_discovery = OdooSchemaDiscovery()
query_analyzer = DynamicQueryAnalyzer(schema_discovery)
query_executor = DynamicQueryExecutor()