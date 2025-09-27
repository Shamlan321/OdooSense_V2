#!/usr/bin/env python3
"""
Dynamic Agent Node

This module implements a dynamic replacement for the hardcoded DataLookupNode,
demonstrating how to integrate the dynamic components into the existing agent architecture.
"""

import logging
import asyncio
from typing import Dict, Any, Optional
from datetime import datetime
from dataclasses import asdict

from agent_state import AgentState, StateManager
from dynamic_components import (
    schema_discovery,
    query_analyzer,
    query_executor,
    QueryPlan,
    QueryResult
)
from gemini_client import gemini_client
from config import config
from performance_monitor import performance_tracker, performance_monitor

logger = logging.getLogger(__name__)

class DynamicDataLookupNode:
    """
    Dynamic replacement for DataLookupNode that can handle any Odoo query
    without hardcoded patterns or models.
    """
    
    def __init__(self):
        self.schema_discovery = schema_discovery
        self.query_analyzer = query_analyzer
        self.query_executor = query_executor
        self._fallback_enabled = True  # Enable fallback to original logic if needed
    
    @performance_tracker("dynamic_data_lookup", performance_monitor)
    def process(self, state: AgentState) -> AgentState:
        """Process data lookup requests dynamically"""
        try:
            if state is None:
                logger.error("Dynamic data lookup failed: state is None")
                return state
            
            # Get user message
            try:
                user_message = StateManager.get_last_user_message(state)
            except Exception as e:
                logger.warning(f"Could not extract user message for dynamic lookup: {e}")
                user_message = ""
            
            logger.info(f"Processing dynamic data lookup for: {user_message}")
            
            # Check if we should use dynamic processing
            if self._should_use_dynamic_processing(user_message, state):
                return self._process_dynamic_query(user_message, state)
            else:
                # Fallback to original logic if dynamic processing is not suitable
                logger.info("Using fallback to original data lookup logic")
                return self._fallback_to_original(state)
        
        except Exception as e:
            logger.error(f"Dynamic data lookup failed: {str(e)}")
            StateManager.set_error(state, f"Dynamic data lookup failed: {str(e)}", "dynamic_lookup_error")
            return state
    
    def _should_use_dynamic_processing(self, user_message: str, state: AgentState) -> bool:
        """
        Determine if we should use dynamic processing or fall back to original logic
        """
        # Use dynamic processing if:
        # 1. The query is not a simple fast-path query
        # 2. The query contains complex requirements
        # 3. The query mentions custom fields or models
        
        # Check for fast-path patterns first
        fast_path_patterns = [
            'how many', 'count', 'total', 'recent', 'latest', 'last'
        ]
        
        user_lower = user_message.lower()
        
        # If it's a simple count/recent query, might be better to use fast-path
        is_simple_query = any(pattern in user_lower for pattern in fast_path_patterns)
        
        # Use dynamic processing for complex queries or when fast-path fails
        has_complex_requirements = any(keyword in user_lower for keyword in [
            'where', 'filter', 'between', 'greater than', 'less than',
            'group by', 'aggregate', 'sum', 'average', 'custom field'
        ])
        
        # Always use dynamic for queries that mention specific business terms
        has_business_context = any(term in user_lower for term in [
            'department', 'project', 'campaign', 'workflow', 'process'
        ])
        
        # Use dynamic processing if it's complex or has business context
        # or if fast-path intent is not detected
        fast_path_intent = state.get("entities", {}).get("fast_path_intent")
        
        return (has_complex_requirements or 
                has_business_context or 
                not fast_path_intent or
                len(user_message.split()) > 10)  # Complex queries tend to be longer
    
    def _process_dynamic_query(self, user_message: str, state: AgentState) -> AgentState:
        """
        Process query using dynamic components
        """
        try:
            # Prepare context from state
            context = {
                'session_id': state.get('session_id'),
                'user_id': state.get('user_id', 1),
                'timestamp': datetime.now().isoformat(),
                'previous_queries': state.get('conversation_history', [])[-3:],  # Last 3 for context
            }
            
            # Run async analysis in sync context
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            try:
                # Analyze query
                query_plan = loop.run_until_complete(
                    self.query_analyzer.analyze_query(user_message, context)
                )
                
                logger.info(f"Generated query plan: intent='{query_plan.intent}', confidence={query_plan.confidence}")
                
                # Execute query if confidence is sufficient
                if query_plan.confidence >= 0.3:
                    query_result = loop.run_until_complete(
                        self.query_executor.execute_query(query_plan)
                    )
                    
                    if query_result.success:
                        # Generate response
                        formatted_response = self._format_dynamic_response(
                            user_message, query_plan, query_result
                        )
                        
                        # Update state
                        state["data_lookup_result"] = {
                            "success": True,
                            "data": query_result.data,
                            "query_plan": asdict(query_plan),
                            "response": formatted_response,
                            "dynamic": True,
                            "execution_time": query_result.execution_time
                        }
                        state["response"] = formatted_response
                        state["current_step"] = "data_lookup_completed"
                        state["next_action"] = "generate_response"
                        
                        logger.info(f"Dynamic query completed successfully in {query_result.execution_time:.2f}s")
                        return state
                    else:
                        # Query execution failed
                        error_msg = query_result.error or "Query execution failed"
                        logger.error(f"Dynamic query execution failed: {error_msg}")
                        StateManager.set_error(state, error_msg, "dynamic_query_execution_error")
                        return state
                else:
                    # Low confidence, try fallback
                    logger.warning(f"Low confidence query plan ({query_plan.confidence}), trying fallback")
                    return self._fallback_to_original(state)
                    
            finally:
                loop.close()
                
        except Exception as e:
            logger.error(f"Dynamic query processing failed: {str(e)}")
            # Try fallback on error
            if self._fallback_enabled:
                logger.info("Attempting fallback to original logic due to error")
                return self._fallback_to_original(state)
            else:
                StateManager.set_error(state, f"Dynamic query processing failed: {str(e)}", "dynamic_processing_error")
                return state
    
    def _format_dynamic_response(self, user_message: str, query_plan: QueryPlan, query_result: QueryResult) -> str:
        """
        Format the query result into a conversational response
        """
        try:
            data = query_result.data
            
            # Determine response format based on data type and query plan
            if isinstance(data, int):
                # Count result
                return self._format_count_response(user_message, data, query_plan)
            elif isinstance(data, list):
                # List of records
                return self._format_records_response(user_message, data, query_plan)
            elif isinstance(data, dict):
                # Single record or aggregation
                return self._format_dict_response(user_message, data, query_plan)
            else:
                return f"Found result: {str(data)}"
                
        except Exception as e:
            logger.error(f"Failed to format dynamic response: {e}")
            return "✅ Query completed successfully, but there was an issue formatting the response."
    
    def _format_count_response(self, user_message: str, count: int, query_plan: QueryPlan) -> str:
        """Format count responses"""
        model_name = query_plan.models[0] if query_plan.models else "records"
        model_display = model_name.replace('_', ' ').replace('.', ' ').title()
        
        if count == 0:
            return f"No {model_display.lower()} found matching your criteria."
        elif count == 1:
            return f"Found 1 {model_display.lower().rstrip('s')} matching your criteria."
        else:
            return f"Found {count} {model_display.lower()} matching your criteria."
    
    def _format_records_response(self, user_message: str, records: list, query_plan: QueryPlan) -> str:
        """Format list of records response"""
        if not records:
            return "No records found matching your criteria."
        
        count = len(records)
        model_name = query_plan.models[0] if query_plan.models else "records"
        model_display = model_name.replace('_', ' ').replace('.', ' ').title()
        
        # Create summary
        summary = f"Found {count} {model_display.lower()}:\n\n"
        
        # Show first few records
        display_count = min(5, len(records))
        
        for i, record in enumerate(records[:display_count]):
            if isinstance(record, dict):
                # Format record fields
                record_info = []
                
                # Prioritize common display fields
                priority_fields = ['name', 'display_name', 'title', 'subject']
                other_fields = []
                
                for field, value in record.items():
                    if field in priority_fields and value:
                        record_info.append(f"{field.replace('_', ' ').title()}: {value}")
                    elif field not in ['id', '__last_update'] and value:
                        other_fields.append(f"{field.replace('_', ' ').title()}: {value}")
                
                # Add other important fields (limit to avoid clutter)
                record_info.extend(other_fields[:3])
                
                if record_info:
                    summary += f"{i+1}. {' | '.join(record_info)}\n"
                else:
                    summary += f"{i+1}. Record ID: {record.get('id', 'Unknown')}\n"
            else:
                summary += f"{i+1}. {str(record)}\n"
        
        if len(records) > display_count:
            summary += f"\n... and {len(records) - display_count} more records."
        
        return summary
    
    def _format_dict_response(self, user_message: str, data: dict, query_plan: QueryPlan) -> str:
        """Format dictionary response (single record or aggregation)"""
        if not data:
            return "No data found."
        
        # Check if it's an aggregation result
        if any(key.endswith(('_sum', '_avg', '_count', '_max', '_min')) for key in data.keys()):
            return self._format_aggregation_response(data, query_plan)
        else:
            return self._format_single_record_response(data, query_plan)
    
    def _format_aggregation_response(self, data: dict, query_plan: QueryPlan) -> str:
        """Format aggregation results"""
        summary = "Aggregation Results:\n\n"
        
        for field, value in data.items():
            if field.endswith('_sum'):
                field_name = field[:-4].replace('_', ' ').title()
                summary += f"Total {field_name}: {value}\n"
            elif field.endswith('_avg'):
                field_name = field[:-4].replace('_', ' ').title()
                summary += f"Average {field_name}: {value:.2f}\n"
            elif field.endswith('_count'):
                field_name = field[:-6].replace('_', ' ').title()
                summary += f"Count of {field_name}: {value}\n"
            elif field.endswith('_max'):
                field_name = field[:-4].replace('_', ' ').title()
                summary += f"Maximum {field_name}: {value}\n"
            elif field.endswith('_min'):
                field_name = field[:-4].replace('_', ' ').title()
                summary += f"Minimum {field_name}: {value}\n"
            else:
                field_display = field.replace('_', ' ').title()
                summary += f"{field_display}: {value}\n"
        
        return summary.strip()
    
    def _format_single_record_response(self, data: dict, query_plan: QueryPlan) -> str:
        """Format single record response"""
        model_name = query_plan.models[0] if query_plan.models else "record"
        model_display = model_name.replace('_', ' ').replace('.', ' ').title()
        
        summary = f"{model_display} Details:\n\n"
        
        # Prioritize display fields
        priority_fields = ['name', 'display_name', 'title', 'subject']
        
        for field in priority_fields:
            if field in data and data[field]:
                summary += f"{field.replace('_', ' ').title()}: {data[field]}\n"
        
        # Add other fields
        for field, value in data.items():
            if field not in priority_fields and field not in ['id', '__last_update'] and value:
                field_display = field.replace('_', ' ').title()
                summary += f"{field_display}: {value}\n"
        
        return summary.strip()
    
    def _fallback_to_original(self, state: AgentState) -> AgentState:
        """
        Fallback to original DataLookupNode logic when dynamic processing fails
        """
        try:
            # Import original DataLookupNode to use as fallback
            from agent_nodes import DataLookupNode
            
            original_node = DataLookupNode()
            return original_node.process(state)
            
        except Exception as e:
            logger.error(f"Fallback to original logic failed: {e}")
            StateManager.set_error(state, "Both dynamic and fallback processing failed", "total_lookup_failure")
            return state

# Helper function to convert dataclass to dict for JSON serialization
def asdict(obj):
    """Convert dataclass to dictionary"""
    if hasattr(obj, '__dict__'):
        return {k: v for k, v in obj.__dict__.items()}
    else:
        return obj