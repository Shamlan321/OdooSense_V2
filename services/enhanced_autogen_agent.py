#!/usr/bin/env python3
"""
Enhanced AutoGen Agent for Odoo Reporting
=========================================
A more robust AutoGen agent that handles dependencies, errors, and Odoo connections properly.
"""

import os
import sys
import subprocess
import importlib
import logging
from typing import Dict, Any, List, Optional
from pathlib import Path

from autogen import AssistantAgent, UserProxyAgent
from google import genai

logger = logging.getLogger(__name__)

class EnhancedAutoGenAgent:
    """
    Enhanced AutoGen agent with better dependency management and error handling.
    """
    
    def __init__(self, credentials: Dict[str, str], session_id: str):
        self.credentials = credentials
        self.session_id = session_id
        self.work_dir = f"reports/{session_id}"
        self._ensure_work_dir()
        self._install_dependencies()
        
    def _ensure_work_dir(self):
        """Ensure the working directory exists"""
        Path(self.work_dir).mkdir(parents=True, exist_ok=True)
        
    def _install_dependencies(self):
        """Install required dependencies"""
        required_packages = [
            "plotly>=5.0.0",
            "pandas>=2.0.0", 
            "kaleido>=0.2.0",
            "reportlab>=4.0.0"
        ]
        
        for package in required_packages:
            try:
                # Try to import the package
                package_name = package.split(">=")[0]
                importlib.import_module(package_name)
                logger.info(f"Package {package_name} is already installed")
            except ImportError:
                logger.info(f"Installing {package}")
                try:
                    subprocess.check_call([
                        sys.executable, "-m", "pip", "install", package
                    ], timeout=60)
                    logger.info(f"Successfully installed {package}")
                except Exception as e:
                    logger.warning(f"Failed to install {package}: {str(e)}")
    
    def _create_odoo_preamble(self) -> str:
        """Create Odoo XML-RPC connection preamble with proper error handling"""
        url = self.credentials.get('url', '')
        db = self.credentials.get('db', '')
        user = self.credentials.get('user', '')
        pwd = self.credentials.get('password', '')
        
        # Validate that we have the required credentials
        if not url or not db or not user or not pwd:
            raise ValueError(f"Missing required Odoo credentials. URL: {bool(url)}, DB: {bool(db)}, User: {bool(user)}, Password: {bool(pwd)}")
        
        preamble = f"""
import xmlrpc.client
import datetime
import json
import time
import os
import sys
from pathlib import Path

# Odoo connection details - INJECTED FROM CREDENTIALS
url   = "{url}"
db    = "{db}"
user  = "{user}"
pwd   = "{pwd}"

# Helper function for safe Odoo operations
def safe_execute(func, *args, **kwargs):
    try:
        return func(*args, **kwargs)
    except Exception as e:
        print(f"Error executing {{func.__name__}}: {{str(e)}}")
        return None

# Test connection and setup
try:
    print("Connecting to Odoo...")
    print(f"URL: {{url}}")
    print(f"Database: {{db}}")
    print(f"User: {{user}}")
    
    common = xmlrpc.client.ServerProxy(f'{{url}}/xmlrpc/2/common')
    models = xmlrpc.client.ServerProxy(f'{{url}}/xmlrpc/2/object')
    uid = common.authenticate(db, user, pwd, {{}})
    
    if not uid:
        raise Exception("Authentication failed - check credentials")
    
    print(f"Successfully connected to Odoo as user ID: {{uid}}")
    print(f"Database: {{db}}, User: {{user}}")
    
except Exception as e:
    print(f"Odoo connection error: {{str(e)}}")
    print("Please check your Odoo credentials and ensure Odoo is running")
    raise e

# IMPORTANT: All variables (url, db, user, pwd, models, uid) are now available
# IMPORTANT: All required libraries (reportlab, plotly, pandas, kaleido) are available in system environment
"""
        return preamble
    
    def _create_system_message(self) -> str:
        """Create enhanced system message with better instructions"""
        odoo_preamble = self._create_odoo_preamble()
        
        return f"""You are an expert Odoo CRUD & reporting assistant.

You can:
- Query / create / update / delete any Odoo record via XML-RPC
- Create PDF reports with ReportLab
- Generate interactive graphs with Plotly
- Handle errors gracefully and provide meaningful feedback

{odoo_preamble}

IMPORTANT INSTRUCTIONS:

1. ALWAYS wrap executable code in ```python ... ``` blocks.

2. DEPENDENCY MANAGEMENT:
   - All required libraries (reportlab, plotly, pandas, kaleido) are already installed in the system environment
   - You can directly import libraries without checking or installing them
   - The system uses the main Python environment, not isolated virtual environments
   - Simply import and use: `import reportlab`, `import plotly`, etc.

3. ODOO CONNECTION:
   - The connection variables (url, db, user, pwd, models, uid) are already defined and injected
   - DO NOT redefine these variables in your code
   - Always use safe_execute() for Odoo operations
   - Handle connection errors gracefully

3a. SALES REPORT HANDLING:
   - When asked for sales reports, ALWAYS query sale.order model
   - Include fields: name, partner_id, amount_total, date_order, state
   - Filter by date ranges when specified (last quarter, monthly, etc.)
   - Calculate totals, averages, and trends
   - Generate both data summary AND visual charts
   - For monthly reports, group data by month and show trends
   - Always create a chart visualization for sales data
   - CRITICAL: NEVER use 'region' field on res.partner - it doesn't exist
   - For regional filtering, use partner_id name filtering or ignore region requests
   - If user mentions regions like 'Pre-Sales', treat as descriptive text, not a filter

4. GRAPH GENERATION:
   - Directly import plotly: `import plotly.graph_objects as go`
   - Create charts with plotly.graph_objects
   - Save charts as PNG: `fig.write_image('chart_timestamp.png')`
   - Handle file save errors

5. PDF GENERATION:
   - Directly import reportlab: `from reportlab.lib.pagesizes import letter`
   - Use reportlab.pdfgen.canvas or reportlab.platypus
   - Save PDFs as: 'report_timestamp.pdf'
   - Handle file save errors

6. ERROR HANDLING:
   - Always wrap operations in try-except blocks
   - Provide meaningful error messages
   - Return JSON responses with 'content' and 'files' fields
   - Handle missing data gracefully

7. RESPONSE FORMAT:
   Always return a JSON response like this:
   {{
       "content": "Description of what was done",
       "files": ["file1.png", "file2.pdf"]
   }}

   For SALES REPORTS and DATA ANALYSIS:
   - Always provide a detailed summary of the data in the "content" field
   - Include key metrics like total orders, revenue, averages
   - Format numbers with proper currency symbols and commas
   - Break down data by time periods (monthly, quarterly)
   - List top customers or recent orders when relevant
   - Use clear, organized formatting with bullet points or tables
   - Example: "Sales Report Summary:\n• Total Orders: 19\n• Total Revenue: $31,809.61\n• Average Order Value: $1,674.19\n• Monthly Breakdown:\n  - July 2025: 14 orders, $23,336.97\n  - June 2025: 5 orders, $8,472.64"

8. WORKING DIRECTORY:
   - All files should be saved in the current working directory
   - Use timestamps in filenames to avoid conflicts
   - Check if files were created successfully

EXAMPLE CODE STRUCTURE:
```python
import time
import json
from pathlib import Path

try:
    # Import libraries directly (they're already installed)
    import plotly.graph_objects as go
    from reportlab.lib.pagesizes import letter
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle
    from reportlab.lib import colors
    
    # Your code here...
    
    # Save file
    timestamp = int(time.time())
    filename = f'chart_{{timestamp}}.png'
    fig.write_image(filename)
    
    # Return response
    print(json.dumps({{
        "content": "Successfully generated chart",
        "files": [filename]
    }}))
    
except Exception as e:
    print(json.dumps({{
        "content": f"Error: {{str(e)}}",
        "files": []
    }}))
```

Remember: Libraries are already available - just import and use them directly!
"""
    
    def create_agents(self):
        """Create AutoGen agents with enhanced configuration"""
        
        # Create the assistant agent
        self.assistant = AssistantAgent(
            name="OdooReportingAgent",
            system_message=self._create_system_message(),
            llm_config={
                "config_list": [{"model": "gemini-2.5-flash", "api_key": os.getenv("GOOGLE_API_KEY")}],
                "temperature": 0.1,
            }
        )
        
        # Create the user proxy agent with system Python environment
        self.user_proxy = UserProxyAgent(
            name="Reporting_Proxy",
            human_input_mode="NEVER",
            max_consecutive_auto_reply=5,
            code_execution_config={
                "work_dir": self.work_dir,
                "timeout": 90,
                "last_n_messages": 10,
                # Use system Python instead of creating virtual environments
                "executor": "python",  # Use system Python
                "python_path": sys.executable,  # Use current Python interpreter
            },
        )
        
        return self.assistant, self.user_proxy
    
    def execute_query(self, query: str) -> Dict[str, Any]:
        """Execute a query through the AutoGen agents"""
        try:
            assistant, user_proxy = self.create_agents()
            
            # Execute the query
            chat_result = user_proxy.initiate_chat(
                assistant, 
                message=query, 
                clear_history=True
            )
            
            # Extract response
            response_content = self._extract_response_content(chat_result)
            
            # Get generated files
            generated_files = self._get_generated_files()
            
            return {
                "success": True,
                "response": response_content,
                "files": generated_files,
                "session_id": self.session_id
            }
            
        except Exception as e:
            logger.error(f"Error executing query: {str(e)}")
            return {
                "success": False,
                "response": f"Error executing query: {str(e)}",
                "files": [],
                "session_id": self.session_id
            }
    
    def _extract_response_content(self, chat_result) -> str:
        """Extract response content from AutoGen chat result"""
        try:
            if hasattr(chat_result, 'chat_history') and chat_result.chat_history:
                # Get the last assistant message
                for msg in reversed(chat_result.chat_history):
                    if msg.get("role") == "assistant":
                        return msg.get("content", "")
            
            # Fallback to string representation
            return str(chat_result) if chat_result else "No response received"
            
        except Exception as e:
            logger.error(f"Error extracting response content: {str(e)}")
            return "Error extracting response content"
    
    def _get_generated_files(self) -> List[Dict[str, str]]:
        """Get list of generated files"""
        try:
            files = []
            for file_path in Path(self.work_dir).glob("*"):
                if file_path.is_file():
                    files.append({
                        "filename": file_path.name,
                        "path": str(file_path),
                        "size": file_path.stat().st_size,
                        "created": datetime.datetime.fromtimestamp(
                            file_path.stat().st_ctime
                        ).isoformat()
                    })
            return files
        except Exception as e:
            logger.error(f"Error getting generated files: {str(e)}")
            return []