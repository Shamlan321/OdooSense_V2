import os
import dotenv
import xmlrpc.client
from langchain.agents import initialize_agent, Tool
from langchain.memory import ConversationBufferMemory
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.agents.agent_types import AgentType
from langchain.chains import LLMChain
from langchain.prompts import PromptTemplate
import hashlib
from typing import Dict, Optional, Tuple
from datetime import datetime, timedelta

# Confirmation state tracking
class OperationState:
    def __init__(self):
        self.confirmed_operations = {}
        self.CONFIRMATION_TIMEOUT = timedelta(minutes=5)  # Confirmations expire after 5 minutes
        # Track the last user intent
        self.last_user_intent = None
        self.user_intent_timestamp = None
    
    def set_user_intent(self, intent_text):
        """Store the original user intent"""
        self.last_user_intent = intent_text
        self.user_intent_timestamp = datetime.now()
    
    def is_same_intent_session(self):
        """Check if we're still in the same intent session"""
        if not self.last_user_intent or not self.user_intent_timestamp:
            return False
        # Check if we're within the timeout window
        return datetime.now() - self.user_intent_timestamp < self.CONFIRMATION_TIMEOUT
    
    def is_operation_confirmed(self, model: str, operation_type: str, fields: dict) -> bool:
        """Check if an operation has been confirmed and is still valid"""
        # If we have a confirmed user intent session, return True
        if self.is_same_intent_session():
            return True
        return False
    
    def confirm_operation(self, model: str, operation_type: str, fields: dict):
        """Mark the current user intent as confirmed"""
        # We don't need to store specific operation details anymore
        # since we're tracking by user intent session
        pass
    
    def clear_expired_confirmations(self):
        """Clear expired intent sessions"""
        if self.user_intent_timestamp and datetime.now() - self.user_intent_timestamp >= self.CONFIRMATION_TIMEOUT:
            self.last_user_intent = None
            self.user_intent_timestamp = None

# Initialize the operation state tracker
operation_state = OperationState()

# Load env
dotenv.load_dotenv()

ODOO_URL = os.getenv("ODOO_URL")
ODOO_DB = os.getenv("ODOO_DB")
ODOO_USERNAME = os.getenv("ODOO_USERNAME")
ODOO_PASSWORD = os.getenv("ODOO_PASSWORD")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Setup XML-RPC Connection
common = xmlrpc.client.ServerProxy(f"{ODOO_URL}/xmlrpc/2/common", allow_none=True)
uid = common.authenticate(ODOO_DB, ODOO_USERNAME, ODOO_PASSWORD, {})
models = xmlrpc.client.ServerProxy(f"{ODOO_URL}/xmlrpc/2/object", allow_none=True)

# LLM
llm = ChatGoogleGenerativeAI(
    model="gemini-2.0-flash", 
    google_api_key=GEMINI_API_KEY, 
    temperature=0.3
)

# ========== Dynamic Gemini Parser ==========
def extract_json(text):
    """
    Extract JSON from LLM response.
    Handles code fences, smart quotes, and markdown junk.
    """
    import re, json
    try:
        # Remove code fences (```json or ``` or ```)
        text = re.sub(r"```(?:json)?\n?", "", text.strip(), flags=re.IGNORECASE).strip("` \n")
        # Replace smart quotes
        text = text.replace(""", '"').replace(""", '"').replace("'", "'").replace("'", "'")
        # Try to load the JSON
        return json.loads(text)
    except json.JSONDecodeError as e:
        # Try to fix common JSON errors
        try:
            # Sometimes the model adds trailing commas which are invalid in JSON
            fixed_text = re.sub(r',\s*}', '}', text)
            fixed_text = re.sub(r',\s*\]', ']', fixed_text)
            return json.loads(fixed_text)
        except:
            # If still failing, try to extract JSON-like structure
            try:
                # Look for patterns like {"key": "value"}
                match = re.search(r'\{[^\{\}]*\}', text)
                if match:
                    return json.loads(match.group(0))
            except:
                pass
        # If all attempts fail, provide a detailed error
        return {
            "error": f"Failed to parse JSON: {str(e)}",
            "raw_text": text
        }

def plan_with_gemini(input_text: str) -> dict:
    prompt = f"""
You are an AI assistant that receives a user's natural language query about their business data in Odoo ERP.
IMPORTANT: If the user asks to create a Sales order/ Purchse order with a specific product and for specific vendor, you should first get the ID for both vendor and product then proceed with the record making. The Odoo instance is running version 18. Optimize all queries, field names, and logic for Odoo version 18 compatibility.  When user asks you to fetch or create/update a record which includes: a customer, a partner,or  a product. You should first get their internal IDs for those records because that is how you communiate with Odoo API. So if any query invloves any operation which involves having to do something with these records, first get their Internal IDs and then use them to fetch, create or update any data.

IMPORTANT FIELD GUIDELINES:
- For res.partner (customers/partners): Use fields like [\"name\", \"email\", \"phone\", \"street\", \"city\", \"country_id\", \"is_company\", \"supplier_rank\", \"customer_rank\"]
- For sale.order (sales orders): Use fields like [\"name\", \"partner_id\", \"date_order\", \"amount_total\", \"state\", \"order_line\"]
- For account.move (invoices): Use fields like [\"name\", \"partner_id\", \"invoice_date\", \"amount_total\", \"amount_residual\", \"state\", \"move_type\"]
- For product.product: Use fields like [\"name\", \"default_code\", \"list_price\", \"standard_price\", \"categ_id\"]
- For hr.expense: Use fields like [\"name\", \"unit_amount\", \"employee_id\", \"product_id\", \"date\"]

NEVER use non-existent fields like \"invoice_count\" on res.partner model. If you need invoice information for a customer, query the account.move model separately with partner_id filter.

For customer queries involving invoices/orders:
1. First query res.partner to get customer info: [\"name\", \"email\", \"phone\"]
2. Then query sale.order with filter [[\"partner_id\", \"=\", customer_id]] for orders
3. Then query account.move with filter [[\"partner_id\", \"=\", customer_id], [\"move_type\", \"=\", \"out_invoice\"]] for invoices

Return a JSON object with the following fields:

- \"intent\": one of [\"get_info\", \"create\", \"update\", \"send_message\"]
- \"model\": the Odoo model name (e.g. \"crm.lead\", \"sale.order\", \"discuss.channel\")
- \"fields\": For get_info: list of fields to retrieve (e.g. [\"name\", \"amount_total\"])
           For create/update: dictionary of field values (e.g. {{\"name\": \"New Lead\", \"email\": \"test@example.com\"}})
- \"filters\": array of filters like [[\"field\", \"operator\", \"value\"]] (required for update to identify records)
- \"record_id\": optional int, specific record ID for update operations
- \"sort\": optional list of sort fields like [[\"date\", \"desc\"]]
- \"limit\": optional int
- \"channel\": for send_message intent, the name of the channel (e.g. \"general\")
- \"message\": for send_message intent, the message body to send

If the user is asking to send a message to a channel:
1. Set intent to \"send_message\"
2. Set channel to the channel name (default to \"general\" if not specified)
3. Generate a professional message body based on the user's request

User Query: {input_text}

Return JSON only.
"""
    response = llm.invoke(prompt)
    return extract_json(response.content.strip())

# ========== XML-RPC TOOL ==========
def odoo_rpc_exec(model, method, args=[], kwargs={}):
    return models.execute_kw(ODOO_DB, uid, ODOO_PASSWORD, model, method, args, kwargs)

# ========== TOOLS ==========

# Global variable to store the last query results
last_results = None

# Function to send message to a channel
def send_channel_message(channel_name, message_body):
    # Find the channel ID
    channel_ids = odoo_rpc_exec('discuss.channel', 'search', [[['name', '=', channel_name]]])
    if not channel_ids:
        return f"Error: Channel '{channel_name}' not found."
    
    channel_id = channel_ids[0]
    
    # Post the message to the channel
    try:
        message_id = odoo_rpc_exec('discuss.channel', 'message_post', 
                                  [channel_id], 
                                  {'body': message_body, 'message_type': 'comment'})
        return f"Message sent to {channel_name} channel successfully."
    except Exception as e:
        return f"Error sending message: {str(e)}"

def _handle_customer_comprehensive_query(query: str) -> str:
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
        
        # Find customer
        customers = odoo_rpc_exec("res.partner", "search_read", 
            [["name", "ilike", customer_name]], 
            {"fields": ["name", "id"], "limit": 1})
        
        if not customers:
            return f"Customer '{customer_name}' not found"
        
        customer = customers[0]
        customer_id = customer["id"]
        result_parts = [f"Customer: {customer['name']}"]
        
        # Get recent sales orders if requested
        if "order" in query.lower():
            orders = odoo_rpc_exec("sale.order", "search_read",
                [["partner_id", "=", customer_id]],
                {"fields": ["name", "date_order", "amount_total", "state"], "limit": 5, "order": "date_order desc"})
            
            if orders:
                result_parts.append(f"Recent Orders: {orders}")
            else:
                result_parts.append("No recent orders found")
        
        # Get outstanding invoices if requested
        if any(word in query.lower() for word in ["invoice", "outstanding"]):
            invoices = odoo_rpc_exec("account.move", "search_read",
                [["partner_id", "=", customer_id], ["move_type", "=", "out_invoice"], ["amount_residual", ">", 0]],
                {"fields": ["name", "invoice_date", "amount_total", "amount_residual", "state"], "limit": 10})
            
            if invoices:
                result_parts.append(f"Outstanding Invoices: {invoices}")
            else:
                result_parts.append("No outstanding invoices found")
        
        return "; ".join(result_parts)
        
    except Exception as e:
        return f"Error in comprehensive customer query: {str(e)}"

def get_info_tool_func(query: str) -> str:
    global last_results
    
    # Check if this is a customer query involving orders/invoices
    if any(word in query.lower() for word in ["customer", "partner"]) and any(word in query.lower() for word in ["order", "invoice", "outstanding", "recent"]):
        return _handle_customer_comprehensive_query(query)
    
    parsed = plan_with_gemini(query)
    if "error" in parsed:
        return parsed["error"]

    model = parsed["model"]
    fields = parsed.get("fields", ["name"])
    filters = parsed.get("filters", [])
    limit = parsed.get("limit", 5)
    sort = parsed.get("sort", [])
    
    # If query mentions "these" or "those" and we have previous results, use them
    if ("these" in query.lower() or "those" in query.lower() or "more info" in query.lower()) and last_results:
        if model == "sale.order" and isinstance(last_results, list):
            # Extract IDs from previous results
            ids = [r.get('id') for r in last_results if 'id' in r]
            if ids:
                filters.append(["id", "in", ids])
                # Add more fields for detailed information
                if "name" not in fields:
                    fields.append("name")
                if "state" not in fields:
                    fields.append("state")
                if "amount_total" not in fields:
                    fields.append("amount_total")
                if "partner_id" not in fields:
                    fields.append("partner_id")
                if "date_order" not in fields:
                    fields.append("date_order")

    # Special handling for overdue sales orders
    if "overdue" in query.lower() and model in ["sale.order", "sale.order.line"]:
        from datetime import datetime
        today = datetime.now().strftime("%Y-%m-%d")
        # Odoo's 'commitment_date' is often used for due dates
        filters.append(["commitment_date", "<", today])
        filters.append(["state", "not in", ["done", "cancel"]])
        if "commitment_date" not in fields:
            fields.append("commitment_date")
        if "state" not in fields:
            fields.append("state")

    # Remove None values from filters and fields
    filters = [f for f in filters if f is not None]
    fields = [f for f in fields if f is not None]

    try:
        results = odoo_rpc_exec(model, "search_read", [filters], {
            "fields": fields,
            "limit": limit
        })
        # Store results for future reference
        last_results = results
        return str(results)
    except Exception as e:
        return f"Error retrieving data: {str(e)}"

def create_tool_func(query: str) -> str:
    # Clear any expired confirmations first
    operation_state.clear_expired_confirmations()
    
    parsed = plan_with_gemini(query)
    if "error" in parsed:
        return parsed["error"]

    model = parsed["model"]
    fields = parsed.get("fields", {})
    
    # Validate fields is a dictionary
    if not isinstance(fields, dict):
        return "Error: 'fields' must be a dictionary for create operations."
    
    if not fields:
        return "Error: No fields provided for creating the record."

    # Check if this operation has already been confirmed (part of same user intent)
    if not operation_state.is_operation_confirmed(model, "create", fields):
        # If not confirmed, ask for confirmation
        confirmation_message = f"I am going to create a new record in {model} with the following data: {fields}. Do you want to confirm it? Yes or No"
        user_confirmation = input(confirmation_message + " ")
        if user_confirmation.strip().lower() not in ["yes", "y"]:
            return "Creation cancelled by user."
        # Store the user intent
        operation_state.set_user_intent(query)
    
    try:
        # Special handling for pricelist creation
        if model == "product.pricelist":
            # Get the company currency
            company_currency = odoo_rpc_exec("res.company", "search_read", [[]], {"fields": ["currency_id"]})[0]["currency_id"][0]
            
            # Set default currency if not provided
            if "currency_id" not in fields:
                fields["currency_id"] = company_currency
            
            # Create default pricelist item if not provided
            if "item_ids" not in fields:
                # Create pricelist first
                pricelist_id = odoo_rpc_exec(model, "create", [fields])
                
                # Create a default pricelist item (0% markup)
                item_vals = {
                    "pricelist_id": pricelist_id,
                    "compute_price": "formula",
                    "base": "list_price",  # Based on product's list price
                    "applied_on": "3_global",  # Apply on all products
                    "price_discount": 0,  # No discount
                }
                item_id = odoo_rpc_exec("product.pricelist.item", "create", [item_vals])
                
                return f"Pricelist created with ID: {pricelist_id} and default item ID: {item_id}"
            
        record_id = odoo_rpc_exec(model, "create", [fields])
        return f"Record created in {model} with ID: {record_id}"
    except Exception as e:
        return f"Error creating record: {str(e)}"

def update_tool_func(query: str) -> str:
    # Clear any expired confirmations first
    operation_state.clear_expired_confirmations()
    
    parsed = plan_with_gemini(query)
    if "error" in parsed:
        return parsed["error"]

    model = parsed["model"]
    fields = parsed.get("fields", {})
    filters = parsed.get("filters", [])
    record_id = parsed.get("record_id", None)
    
    # Validate fields is a dictionary
    if not isinstance(fields, dict):
        return "Error: 'fields' must be a dictionary for update operations."
    
    if not fields:
        return "Error: No fields provided for updating the record."
    
    # We need either filters or a specific record_id to identify which records to update
    if not record_id and not filters:
        return "Error: No filters or record_id provided to identify which records to update."

    # Check if this operation has already been confirmed (part of same user intent)
    if not operation_state.is_operation_confirmed(model, "update", fields):
        # If not confirmed, ask for confirmation
        summary = f"record_id: {record_id}, filters: {filters}, fields: {fields}"
        confirmation_message = f"I am going to update records in {model} with the following changes: {summary}. Do you want to confirm it? Yes or No"
        user_confirmation = input(confirmation_message + " ")
        if user_confirmation.strip().lower() not in ["yes", "y"]:
            return "Update cancelled by user."
        # Store the user intent
        operation_state.set_user_intent(query)
    
    try:
        # If we have a specific record_id, use that
        if record_id:
            result = odoo_rpc_exec(model, "write", [[record_id], fields])
            return f"Record with ID {record_id} updated in {model}."
        else:
            # Otherwise, search for records matching the filters
            record_ids = odoo_rpc_exec(model, "search", [filters])
            if not record_ids:
                return f"No records found matching the filters: {filters}"
            
            # Update all matching records
            result = odoo_rpc_exec(model, "write", [record_ids, fields])
            return f"Updated {len(record_ids)} records in {model}."
    except Exception as e:
        return f"Error updating record(s): {str(e)}"

def send_message_tool_func(query: str) -> str:
    parsed = plan_with_gemini(query)
    if "error" in parsed:
        return parsed["error"]
    
    # Check if this is a message sending intent
    if parsed.get("intent") != "send_message":
        return "Error: This query doesn't appear to be a message sending request."
    
    channel = parsed.get("channel", "general")  # Default to general channel if not specified
    message = parsed.get("message", "")
    
    if not message:
        return "Error: No message content provided."
    
    # Send the message to the specified channel
    return send_channel_message(channel, message)

# ========== Time Utility ==========
def get_current_time_info():
    from datetime import datetime
    current_time = datetime.now()
    return {
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

def time_tool_func(query: str) -> str:
    try:
        time_info = get_current_time_info()
        return str(time_info)
    except Exception as e:
        return f"Error getting time information: {str(e)}"

# ========== Tool Setup ==========
tools = [
    Tool(name="GetInfo", func=get_info_tool_func, description="Get info from Odoo like CRM or Sales data."),
    Tool(name="CreateRecord", func=create_tool_func, description="Create a record like a new lead or sale."),
    Tool(name="UpdateRecord", func=update_tool_func, description="Update existing records in Odoo."),
    Tool(name="SendMessage", func=send_message_tool_func, description="Send a message to a channel in Odoo Discuss."),
    Tool(name="GetTime", func=time_tool_func, description="Get current time information for temporal context in queries.")
]

# ========== Agent ==========
memory = ConversationBufferMemory(
    memory_key="chat_history", 
    return_messages=True,  # Important for better context handling
    # Give more weight to recent messages
    output_key="output"  
)

# Define custom prompt to better handle context
template = """You are an AI assistant that helps users access and manage their Odoo ERP system.

Previous conversation:
{chat_history}

Current Human Question: {input}
{agent_scratchpad}

IMPORTANT:
- Only output one of the following per step: an action (with Action/Action Input) OR a final answer (with Final Answer), never both in the same response.
- If you need to perform an action, do NOT provide a final answer in the same output.
- If you encounter an error parsing output, rephrase and try again.
- Always return output in the expected format for the agent executor.
"""
prompt = PromptTemplate(input_variables=["input", "chat_history", "agent_scratchpad"], template=template)

agent = initialize_agent(
    tools,
    llm,
    agent=AgentType.ZERO_SHOT_REACT_DESCRIPTION,
    memory=memory,
    verbose=True,  # Turn off verbose mode to hide intermediate steps
    agent_kwargs={
        "prefix": prompt.template,
        "handle_parsing_errors": True
    }
)

# ========== CLI Interface ==========
if __name__ == "__main__":
    print("Odoo AI Agent is ready. Ask a question:")
    while True:
        q = input("You: ")
        if q.lower() in ["exit", "quit"]:
            break
        
        try:
            # Store the original user query as the intent
            operation_state.set_user_intent(q)
            
            # Important: use invoke instead of run to make sure memory is updated
            result = agent.invoke({"input": q})
            a = result["output"]
            # Store this response in memory
            memory.save_context({"input": q}, {"output": a})
            
            # Display only the final answer without any chain output messages
            print(f"{a}")
        except Exception as e:
            print(f"Error occurred: {str(e)}")
            # Try a simpler approach if agent fails
            print("I encountered an error. Could you rephrase your question?")