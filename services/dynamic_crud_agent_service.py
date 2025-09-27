#!/usr/bin/env python3
"""
Dynamic CRUD Agent Service
==========================
Service wrapper for the dynamic CRUD agent that handles all data lookup, 
create, read, update operations for Odoo.
"""

import logging
import os
from typing import Dict, Any, Optional
from datetime import datetime
import uuid

# Import the dynamic CRUD agent
import sys
import importlib.util

# Import langchain components
from langchain_core.tools import Tool

logger = logging.getLogger(__name__)

class DynamicCRUDAgentService:
    """
    Service that manages the dynamic CRUD agent for handling all Odoo data operations.
    This agent can handle natural language queries for data lookup, creation, and updates.
    """
    
    def __init__(self):
        self.agents = {}  # Session-specific agent instances
        self.credentials = {}  # Session-specific credentials
        self.agent_module = None
        self._load_agent_module()
    
    def _load_agent_module(self):
        """Load the agent functions from the final_langchain_agent.py file"""
        try:
            # Instead of importing the module (which tries to connect to Odoo),
            # we'll implement the agent functionality directly here
            self.agent_module = type('AgentModule', (), {})()
            
            # Add the essential functions to our agent module
            self._add_agent_functions()
            
            logger.info("Dynamic CRUD agent module functions loaded successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to load dynamic CRUD agent module: {str(e)}")
            return False
    
    def _add_agent_functions(self):
        """Add the essential agent functions to the module - now simplified since functions are defined in process_query"""
        # This method is now simplified since we define functions directly in process_query
        # where they have access to session-specific variables
        pass

    def _handle_customer_comprehensive_query(self, query: str) -> str:
        """Handle customer queries that involve orders and invoices"""
        try:
            # Extract customer name from query
            import re
            customer_match = re.search(r"customer\s+([^'\s]+(?:\s+[^'\s]+)*)", query.lower())
            if not customer_match:
                customer_match = re.search(r"([^'\s]+(?:\s+[^'\s]+)*)(?:'s|\s+recent|\s+outstanding)", query.lower())
            
            if not customer_match:
                return "Could not identify customer name in the query"
            
            customer_name = customer_match.group(1).strip()
            
            # Find customer using the odoo_rpc_exec function
            customers = self.models.execute_kw(
                os.environ.get('ODOO_DB'), 
                self.uid, 
                os.environ.get('ODOO_PASSWORD'), 
                "res.partner", "search_read", 
                [["name", "ilike", customer_name]], 
                {"fields": ["name", "id"], "limit": 1}
            )
            
            if not customers:
                return f"Customer '{customer_name}' not found"
            
            customer = customers[0]
            customer_id = customer["id"]
            result_parts = [f"Customer: {customer['name']}"]
            
            # Get recent sales orders if requested
            if "order" in query.lower():
                orders = self.models.execute_kw(
                    os.environ.get('ODOO_DB'), 
                    self.uid, 
                    os.environ.get('ODOO_PASSWORD'), 
                    "sale.order", "search_read",
                    [["partner_id", "=", customer_id]],
                    {"fields": ["name", "date_order", "amount_total", "state"], "limit": 5, "order": "date_order desc"}
                )
                
                if orders:
                    result_parts.append(f"Recent Orders: {orders}")
                else:
                    result_parts.append("No recent orders found")
            
            # Get outstanding invoices if requested
            if any(word in query.lower() for word in ["invoice", "outstanding"]):
                invoices = self.models.execute_kw(
                    os.environ.get('ODOO_DB'), 
                    self.uid, 
                    os.environ.get('ODOO_PASSWORD'), 
                    "account.move", "search_read",
                    [["partner_id", "=", customer_id], ["move_type", "=", "out_invoice"], ["amount_residual", ">", 0]],
                    {"fields": ["name", "invoice_date", "amount_total", "amount_residual", "state"], "limit": 10}
                )
                
                if invoices:
                    result_parts.append(f"Outstanding Invoices: {invoices}")
                else:
                    result_parts.append("No outstanding invoices found")
            
            return "; ".join(result_parts)
            
        except Exception as e:
            return f"Error in comprehensive customer query: {str(e)}"
    
    def initialize_agent(self, credentials: Dict[str, str], session_id: str) -> bool:
        """
        Initialize a session-specific agent instance with credentials
        
        Args:
            credentials: Dictionary containing Odoo connection details
            session_id: Session identifier
            
        Returns:
            bool: True if initialization successful
        """
        try:
            if not self.agent_module:
                logger.error("Agent module not loaded")
                return False
            
            # Store credentials for this session
            self.credentials[session_id] = credentials
            
            # Set environment variables for the agent
            os.environ['ODOO_URL'] = credentials.get('url', '')
            os.environ['ODOO_DB'] = credentials.get('database', '')
            os.environ['ODOO_USERNAME'] = credentials.get('username', '')
            os.environ['ODOO_PASSWORD'] = credentials.get('password', '')
            os.environ['GEMINI_API_KEY'] = credentials.get('gemini_api_key', os.getenv('GEMINI_API_KEY', ''))
            
            # Create a new agent instance for this session
            # Note: The agent is initialized when the module is loaded
            # We just need to store the session info
            self.agents[session_id] = {
                'initialized': True,
                'credentials': credentials,
                'created_at': datetime.now()
            }
            
            logger.info(f"Dynamic CRUD agent initialized for session {session_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize dynamic CRUD agent for session {session_id}: {str(e)}")
            return False
    
    def process_query(self, query: str, session_id: str) -> Dict[str, Any]:
        """
        Process a query through the dynamic CRUD agent
        
        Args:
            query: User's natural language query
            session_id: Session identifier
            
        Returns:
            Dict containing response and metadata
        """
        try:
            if session_id not in self.agents:
                return {
                    "success": False,
                    "error": "Agent not initialized for this session. Please set up your Odoo connection first.",
                    "agent_type": "dynamic_crud_agent"
                }
            
            if not self.agent_module:
                return {
                    "success": False,
                    "error": "Dynamic CRUD agent module not loaded",
                    "agent_type": "dynamic_crud_agent"
                }
            
            # Set environment variables for this session
            session_creds = self.credentials.get(session_id, {})
            os.environ['ODOO_URL'] = session_creds.get('url', '')
            os.environ['ODOO_DB'] = session_creds.get('database', '')
            os.environ['ODOO_USERNAME'] = session_creds.get('username', '')
            os.environ['ODOO_PASSWORD'] = session_creds.get('password', '')
            os.environ['GEMINI_API_KEY'] = session_creds.get('gemini_api_key', os.getenv('GEMINI_API_KEY', ''))
            
            # Import the required modules and create a session-specific agent instance
            import xmlrpc.client
            from langchain_google_genai import ChatGoogleGenerativeAI
            from langchain.agents import initialize_agent, AgentType
            from langchain.memory import ConversationBufferMemory
            
            # Create session-specific LLM
            llm = ChatGoogleGenerativeAI(
                model="gemini-2.0-flash",
                google_api_key=os.environ.get('GEMINI_API_KEY'),
                temperature=0.3
            )
            
            # Store LLM for the agent functions to use
            self.llm = llm
            
            # Setup XML-RPC Connection for this session
            common = xmlrpc.client.ServerProxy(f"{os.environ['ODOO_URL']}/xmlrpc/2/common", allow_none=True)
            uid = common.authenticate(os.environ['ODOO_DB'], os.environ['ODOO_USERNAME'], os.environ['ODOO_PASSWORD'], {})
            models = xmlrpc.client.ServerProxy(f"{os.environ['ODOO_URL']}/xmlrpc/2/object", allow_none=True)
            
            if not uid:
                return {
                    "success": False,
                    "error": "Failed to authenticate with Odoo",
                    "agent_type": "dynamic_crud_agent"
                }
            
            # Store connection details for the agent functions to use
            self.common = common
            self.uid = uid
            self.models = models
            
            # Set up environment variables and global state needed by the original agent
            self._setup_agent_environment(session_creds)
            
            # Create the tools with session-specific context
            from langchain.tools import Tool
            
            # Define helper functions with access to session variables
            def extract_json(text):
                """Extract JSON from LLM response"""
                import re, json
                try:
                    text = re.sub(r"```(?:json)?\n?", "", text.strip(), flags=re.IGNORECASE).strip("` \n")
                    # Remove any remaining formatting
                    text = text.strip()
                    return json.loads(text)
                except json.JSONDecodeError as e:
                    return {"error": f"JSON parsing error: {str(e)}"}
                except Exception as e:
                    return {"error": f"Unexpected error: {str(e)}"}
            
            def plan_with_gemini(query, llm_instance):
                """Plan query execution using Gemini"""
                try:
                    prompt = f"""Parse this Odoo query and return a JSON response with the appropriate action:
                    Query: {query}
                    
                    Return JSON in this format:
                    {{
                        "model": "odoo_model_name",
                        "action": "search"|"count"|"create"|"update"|"message",
                        "fields": {{"field_name": "value"}},
                        "filters": [["field", "operator", "value"]],
                        "limit": number_or_null
                    }}
                    """
                    response = llm_instance.invoke(prompt)
                    return extract_json(response.content)
                except Exception as e:
                    return {"error": f"Planning error: {str(e)}"}
            
            def odoo_rpc_exec(model, method, args=None, kwargs=None):
                """Execute Odoo RPC call"""
                try:
                    if args is None:
                        args = []
                    if kwargs is None:
                        kwargs = {}
                    return models.execute_kw(
                        os.environ.get('ODOO_DB'), 
                        uid, 
                        os.environ.get('ODOO_PASSWORD'), 
                        model, method, args, kwargs
                    )
                except Exception as e:
                    return f"RPC Error: {str(e)}"
            
            # Define tool functions with access to session variables
            def get_info_func(query: str) -> str:
                """Get information from Odoo"""
                try:
                    parsed = plan_with_gemini(query, llm)
                    if "error" in parsed:
                        return parsed["error"]
                    
                    model = parsed["model"]
                    action = parsed.get("action", "search")
                    filters = parsed.get("filters", [])
                    fields = parsed.get("fields", [])
                    limit = parsed.get("limit", None)
                    
                    if action == "count":
                        count = odoo_rpc_exec(model, "search_count", [filters])
                        return f"Found {count} records in {model}"
                    else:
                        kwargs = {"fields": fields} if fields else {}
                        if limit:
                            kwargs["limit"] = limit
                        records = odoo_rpc_exec(model, "search_read", [filters], kwargs)
                        return str(records)
                except Exception as e:
                    return f"Error retrieving information: {str(e)}"
            
            def create_func(query: str) -> str:
                """Create new record in Odoo"""
                try:
                    parsed = plan_with_gemini(query, llm)
                    if "error" in parsed:
                        return parsed["error"]
                    
                    model = parsed["model"]
                    fields = parsed.get("fields", {})
                    
                    if not isinstance(fields, dict) or not fields:
                        return "Error: No fields provided for creating the record."
                    
                    record_id = odoo_rpc_exec(model, "create", [fields])
                    return f"Created record with ID {record_id} in {model}"
                except Exception as e:
                    return f"Error creating record: {str(e)}"
            
            def update_func(query: str) -> str:
                """Update existing record in Odoo"""
                try:
                    parsed = plan_with_gemini(query, llm)
                    if "error" in parsed:
                        return parsed["error"]
                    
                    model = parsed["model"]
                    fields = parsed.get("fields", {})
                    filters = parsed.get("filters", [])
                    record_id = parsed.get("record_id", None)
                    
                    if not isinstance(fields, dict) or not fields:
                        return "Error: No fields provided for updating the record."
                    
                    if record_id:
                        result = odoo_rpc_exec(model, "write", [[record_id], fields])
                        return f"Record with ID {record_id} updated in {model}."
                    elif filters:
                        record_ids = odoo_rpc_exec(model, "search", [filters])
                        if not record_ids:
                            return f"No records found matching the filters: {filters}"
                        result = odoo_rpc_exec(model, "write", [record_ids, fields])
                        return f"Updated {len(record_ids)} records in {model}."
                    else:
                        return "Error: No filters or record_id provided to identify which records to update."
                except Exception as e:
                    return f"Error updating record(s): {str(e)}"
            
            def send_message_func(query: str) -> str:
                """Send message to Odoo channel"""
                try:
                    parsed = plan_with_gemini(query, llm)
                    if "error" in parsed:
                        return parsed["error"]
                    
                    channel = parsed.get("channel", "general")
                    message = parsed.get("message", "")
                    
                    if not message:
                        return "Error: No message content provided."
                    
                    # Find the channel ID
                    channel_ids = odoo_rpc_exec('discuss.channel', 'search', [[["name", "=", channel]]])
                    if not channel_ids:
                        return f"Error: Channel '{channel}' not found."
                    
                    channel_id = channel_ids[0]
                    # Post the message to the channel
                    message_id = odoo_rpc_exec('discuss.channel', 'message_post', 
                                              [channel_id], 
                                              {'body': message, 'message_type': 'comment'})
                    return f"Message sent to {channel} channel successfully."
                except Exception as e:
                    return f"Error sending message: {str(e)}"
            
            def time_func(query: str) -> str:
                """Get current time information"""
                from datetime import datetime
                try:
                    current_time = datetime.now()
                    time_info = {
                        "year": current_time.year,
                        "month": current_time.month,
                        "day": current_time.day,
                        "hour": current_time.hour,
                        "minute": current_time.minute,
                        "date": current_time.strftime("%Y-%m-%d"),
                        "datetime": current_time.strftime("%Y-%m-%d %H:%M:%S"),
                        "month_start": current_time.replace(day=1).strftime("%Y-%m-%d"),
                        "month_name": current_time.strftime("%B")
                    }
                    return str(time_info)
                except Exception as e:
                    return f"Error getting time information: {str(e)}"
            
            # Create the tools list
            tools = [
                Tool(
                    name="GetInfo",
                    func=get_info_func,
                    description="Use this tool to retrieve, count, or search for data in Odoo. Provide a natural language query about what data you want to find."
                ),
                Tool(
                    name="CreateRecord",
                    func=create_func,
                    description="Use this tool to create new records in Odoo. Provide details about what record you want to create."
                ),
                Tool(
                    name="UpdateRecord",
                    func=update_func,
                    description="Use this tool to update existing records in Odoo. Provide details about what record to update and what changes to make."
                ),
                Tool(
                    name="SendMessage",
                    func=send_message_func,
                    description="Use this tool to send messages to Odoo Discuss channels. Specify the channel and message content."
                ),
                Tool(
                    name="GetTime",
                    func=time_func,
                    description="Use this tool to get current time and date information."
                )
            ]
            
            # Create session-specific memory
            memory = ConversationBufferMemory(
                memory_key="chat_history",
                return_messages=True,
                output_key="output"
            )
            
            # Create session-specific agent with better configuration
            agent = initialize_agent(
                tools,
                llm,
                agent=AgentType.ZERO_SHOT_REACT_DESCRIPTION,
                memory=memory,
                verbose=True,  # Enable verbosity for debugging
                handle_parsing_errors=True,
                max_iterations=5,
                early_stopping_method="generate",
                agent_kwargs={
                    "prefix": """You are an AI assistant that helps users access and manage their Odoo ERP system.
                    
You have access to the following tools to help you answer questions about Odoo data:
- GetInfo: Use this to retrieve, count, or search for data in Odoo (customers, sales orders, products, etc.)
- CreateRecord: Use this to create new records in Odoo
- UpdateRecord: Use this to modify existing records in Odoo
- SendMessage: Use this to send messages in Odoo Discuss channels
- GetTime: Use this to get current time information

Always use the appropriate tool to answer the user's question. For data lookup questions like "How many sales orders do we have?", use the GetInfo tool.

**IMPORTANT - Data Formatting for Reports:**
When users request reports or data analysis (without specifying PDF, Excel, or chart formats), you MUST format your response in a well-organized, professional manner:

1. **Use clear headings and sections** to organize different types of information
2. **Present data in structured tables** when showing multiple records
3. **Include summary statistics** at the beginning or end (totals, counts, averages)
4. **Use bullet points or numbered lists** for key findings or recommendations
5. **Group related data together** (e.g., group sales by month, department, etc.)
6. **Include relevant context** such as date ranges, filters applied, or data sources
7. **Format numbers appropriately** (currency symbols, thousands separators, percentages)
8. **Highlight important insights** or trends in the data

Example format for a sales report:
```
# Sales Report Summary

## Overview
- Total Sales: $X,XXX
- Number of Orders: XX
- Period: [Date Range]

## Sales by Month
| Month | Orders | Revenue |
|-------|--------|---------|
| Jan   | XX     | $X,XXX  |
| Feb   | XX     | $X,XXX  |

## Key Insights
- Highest performing month: [Month]
- Growth trend: [Description]
```

**IMPORTANT - For Pending Tasks Queries:**
When users ask about "pending tasks", "my tasks", "assigned tasks", or similar requests, ALWAYS use this exact approach to avoid errors:

1. FIRST: Use GetInfo tool with these specifications:
   - Model: "project.task"
   - Action: "search"
   - Filters: [["stage_id.fold", "=", false]]
   - Fields: ["id", "name", "project_id", "stage_id", "date_deadline", "priority", "user_ids"]
   - Order by: "priority desc, date_deadline, id"

2. This retrieves ALL pending tasks with user assignment information included in the user_ids field.

**DO NOT attempt these approaches as they will cause RPC errors:**
- Do NOT use ["user_ids", "in", [current_user_id]] - this causes "invalid input syntax for type integer" errors
- Do NOT use ["user_ids", "in", [user.id]] - this also causes parsing errors
- Do NOT use ["message_follower_ids", "in", [user.id]] - this causes similar errors

The working approach retrieves all pending tasks and includes user assignment data, allowing you to identify which tasks are relevant to the user from the returned user_ids field.

"""
                }
            )
            
            # Directly process the query with the agent
            response = agent.run(query)
            
            return {
                "success": True,
                "response": response,
                "agent_type": "dynamic_crud_agent"
            }
            
        except Exception as e:
            logger.error(f"Error processing query with dynamic CRUD agent: {str(e)}")
            return {
                "success": False,
                "error": f"Query processing failed: {str(e)}",
                "agent_type": "dynamic_crud_agent"
            }
    

    def _setup_agent_environment(self, session_creds: Dict[str, str]):
        """Set up the agent module's global environment and state"""
        try:
            # Ensure the agent module has the necessary global variables initialized
            if hasattr(self.agent_module, 'ODOO_URL'):
                self.agent_module.ODOO_URL = session_creds.get('url', '')
            if hasattr(self.agent_module, 'ODOO_DB'):
                self.agent_module.ODOO_DB = session_creds.get('database', '')
            if hasattr(self.agent_module, 'ODOO_USERNAME'):
                self.agent_module.ODOO_USERNAME = session_creds.get('username', '')
            if hasattr(self.agent_module, 'ODOO_PASSWORD'):
                self.agent_module.ODOO_PASSWORD = session_creds.get('password', '')
            if hasattr(self.agent_module, 'GEMINI_API_KEY'):
                self.agent_module.GEMINI_API_KEY = session_creds.get('gemini_api_key', '')
            
            # Initialize XML-RPC connections in the agent module if needed
            if hasattr(self.agent_module, 'common') and hasattr(self.agent_module, 'models'):
                import xmlrpc.client
                self.agent_module.common = xmlrpc.client.ServerProxy(f"{session_creds.get('url', '')}/xmlrpc/2/common", allow_none=True)
                uid = self.agent_module.common.authenticate(
                    session_creds.get('database', ''), 
                    session_creds.get('username', ''), 
                    session_creds.get('password', ''), 
                    {}
                )
                if uid:
                    self.agent_module.uid = uid
                    self.agent_module.models = xmlrpc.client.ServerProxy(f"{session_creds.get('url', '')}/xmlrpc/2/object", allow_none=True)
                    logger.info("Agent module environment set up successfully")
                else:
                    logger.error("Failed to authenticate in agent module setup")
            
        except Exception as e:
            logger.error(f"Error setting up agent environment: {str(e)}")
    
    def cleanup_session(self, session_id: str):
        """Clean up resources for a session"""
        try:
            if session_id in self.agents:
                del self.agents[session_id]
            if session_id in self.credentials:
                del self.credentials[session_id]
            logger.info(f"Cleaned up dynamic CRUD agent session: {session_id}")
        except Exception as e:
            logger.error(f"Error cleaning up session {session_id}: {str(e)}")

# Global instance
dynamic_crud_agent_service = DynamicCRUDAgentService()