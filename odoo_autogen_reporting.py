#!/usr/bin/env python3
"""
Advanced Odoo Reporting Agent with AutoGen
==========================================
Specialized agent for generating advanced reports, charts, and graphs from Odoo data
Integrates with the main LangGraph agent architecture
"""

import json
import os
import sys
import datetime
import re
from pathlib import Path
from typing import TypedDict, Literal, Dict, Any, List

from langgraph.graph import StateGraph, END
from autogen import AssistantAgent, UserProxyAgent
from google import genai
from google.genai import types

# Import from main agent
from agent_state import AgentState, StateManager, ProcessingResult
from odoo_client import odoo_client
from agent_nodes import get_odoo_client_for_session
from config import config
import logging

logger = logging.getLogger(__name__)

# ------------------------------------------------------------
# Configuration
# ------------------------------------------------------------
ODOO_CONFIG = {
    "url": config.odoo.url,
    "database": config.odoo.database,
    "username": config.odoo.username,
    "password": config.odoo.password
}

GEMINI_CONFIG = {
    "api_key": config.gemini.api_key,
    "model_name": config.gemini.model_name
}

GOOGLE_API_KEY = config.gemini.api_key
if not GOOGLE_API_KEY:
    logger.warning("GOOGLE_API_KEY not found. Some features may not work.")

# ------------------------------------------------------------
# Odoo XML-RPC preamble for AutoGen agents
# ------------------------------------------------------------
ODOO_PREAMBLE = f"""
import xmlrpc.client, datetime, json, pandas as pd, numpy as np
url   = "{ODOO_CONFIG['url']}"
db    = "{ODOO_CONFIG['database']}"
user  = "{ODOO_CONFIG['username']}"
pwd   = "{ODOO_CONFIG['password']}"

common = xmlrpc.client.ServerProxy(f'{{url}}/xmlrpc/2/common')
models = xmlrpc.client.ServerProxy(f'{{url}}/xmlrpc/2/object')
uid    = common.authenticate(db, user, pwd, {{}})

def odoo_search_read(model, domain=[], fields=[], limit=None):
    \"\"\"Helper function to search and read Odoo records\"\"\"
    return models.execute_kw(db, uid, pwd, model, 'search_read', [domain], {{'fields': fields, 'limit': limit}})

def odoo_search(model, domain=[], limit=None):
    \"\"\"Helper function to search Odoo records\"\"\"
    return models.execute_kw(db, uid, pwd, model, 'search', [domain], {{'limit': limit}})

def odoo_read(model, ids, fields=[]):
    \"\"\"Helper function to read Odoo records\"\"\"
    return models.execute_kw(db, uid, pwd, model, 'read', [ids], {{'fields': fields}})
"""

# ------------------------------------------------------------
# AutoGen LLM Configuration
# ------------------------------------------------------------
llm_cfg = {
    "config_list": [{
        "model": GEMINI_CONFIG["model_name"],
        "api_key": GEMINI_CONFIG["api_key"],
        "base_url": "https://generativelanguage.googleapis.com/v1beta/",
        "api_type": "google"
    }],
    "temperature": 0.1,
}

# ------------------------------------------------------------
# Advanced Reporting Agent
# ------------------------------------------------------------
reporting_assistant = AssistantAgent(
    name="OdooAdvancedReportingAgent",
    llm_config=llm_cfg,
    system_message=(
        "You are an advanced Odoo reporting and data visualization specialist.\n"
        "You excel at creating comprehensive reports, interactive charts, and data analysis from Odoo data.\n\n"
        "CAPABILITIES:\n"
        "  - Generate detailed business reports (sales, financial, inventory, HR, CRM)\n"
        "  - Create interactive charts and graphs using Plotly\n"
        "  - Perform advanced data analysis with Pandas and NumPy\n"
        "  - Export reports as PDF, Excel, CSV, or image formats\n"
        "  - Generate executive dashboards and KPI summaries\n"
        "  - Create time-series analysis and trend reports\n\n"
        + ODOO_PREAMBLE +
        "\n\nIMPORTANT INSTRUCTIONS:\n"
        "1. ALWAYS wrap executable code in ```python ... ``` blocks.\n"
        "2. For shell commands (pip install), use ```bash ... ``` blocks.\n"
        "3. For charts and graphs:\n"
        "   - Use plotly.graph_objects or plotly.express for interactive charts\n"
        "   - Save charts as HTML for interactivity: fig.write_html('chart_<timestamp>.html')\n"
        "   - Also save as PNG/JPG for static viewing: fig.write_image('chart_<timestamp>.png')\n"
        "   - Include chart titles, axis labels, and legends\n"
        "   - Use appropriate color schemes and styling\n"
        "4. For PDF reports:\n"
        "   - Use reportlab for professional PDF generation\n"
        "   - Include company branding, headers, and footers\n"
        "   - Add charts as images within the PDF\n"
        "   - Save as 'report_<timestamp>.pdf'\n"
        "5. For Excel reports:\n"
        "   - Use pandas.to_excel() with multiple sheets\n"
        "   - Include summary sheets and detailed data\n"
        "   - Apply formatting and conditional formatting where appropriate\n"
        "6. Data Analysis Best Practices:\n"
        "   - Always validate data before analysis\n"
        "   - Handle missing or null values appropriately\n"
        "   - Provide statistical summaries and insights\n"
        "   - Include data quality metrics in reports\n"
        "7. Performance Optimization:\n"
        "   - Use appropriate limits for large datasets\n"
        "   - Implement pagination for very large reports\n"
        "   - Cache frequently accessed data when possible\n"
        "8. Security:\n"
        "   - Never expose passwords or sensitive credentials\n"
        "   - Validate user permissions before generating reports\n"
        "   - Sanitize all user inputs\n\n"
        "REPORT TYPES YOU CAN GENERATE:\n"
        "- Sales Performance Reports (revenue, trends, top products/customers)\n"
        "- Financial Reports (P&L, cash flow, aging reports)\n"
        "- Inventory Reports (stock levels, movements, valuation)\n"
        "- HR Reports (headcount, attendance, payroll summaries)\n"
        "- CRM Reports (lead conversion, pipeline analysis)\n"
        "- Custom KPI Dashboards\n"
        "- Comparative Analysis Reports\n"
        "- Forecasting and Trend Analysis\n"
    ),
)

reporting_proxy = UserProxyAgent(
    name="REPORTING_Proxy",
    human_input_mode="NEVER",
    max_consecutive_auto_reply=5,
    code_execution_config={"work_dir": "reports", "use_docker": False},
)

# ------------------------------------------------------------
# Chart Generation Agent
# ------------------------------------------------------------
chart_assistant = AssistantAgent(
    name="OdooChartGenerationAgent",
    llm_config=llm_cfg,
    system_message=(
        "You are a specialized data visualization expert for Odoo data.\n"
        "You create stunning, interactive charts and graphs that tell compelling data stories.\n\n"
        "CHART TYPES YOU EXCEL AT:\n"
        "  - Line charts (trends, time series)\n"
        "  - Bar charts (comparisons, rankings)\n"
        "  - Pie charts (proportions, distributions)\n"
        "  - Scatter plots (correlations, relationships)\n"
        "  - Heatmaps (patterns, intensity)\n"
        "  - Box plots (statistical distributions)\n"
        "  - Funnel charts (conversion processes)\n"
        "  - Gauge charts (KPIs, targets)\n"
        "  - Treemaps (hierarchical data)\n"
        "  - Sankey diagrams (flow analysis)\n\n"
        + ODOO_PREAMBLE +
        "\n\nCHART CREATION GUIDELINES:\n"
        "1. ALWAYS wrap code in ```python ... ``` blocks\n"
        "2. Use plotly.graph_objects for maximum customization\n"
        "3. Apply professional styling:\n"
        "   - Consistent color schemes\n"
        "   - Clear titles and labels\n"
        "   - Appropriate fonts and sizing\n"
        "   - Responsive layouts\n"
        "4. Make charts interactive:\n"
        "   - Add hover information\n"
        "   - Include zoom and pan capabilities\n"
        "   - Add selection and filtering options\n"
        "5. Export in multiple formats:\n"
        "   - HTML for web viewing (interactive)\n"
        "   - PNG for presentations\n"
        "   - SVG for scalable graphics\n"
        "6. Include data insights:\n"
        "   - Add annotations for key points\n"
        "   - Highlight trends and outliers\n"
        "   - Provide context and explanations\n"
        "7. Optimize for different audiences:\n"
        "   - Executive summaries (high-level)\n"
        "   - Operational reports (detailed)\n"
        "   - Technical analysis (comprehensive)\n"
    ),
)

chart_proxy = UserProxyAgent(
    name="CHART_Proxy",
    human_input_mode="NEVER",
    max_consecutive_auto_reply=3,
    code_execution_config={"work_dir": "charts", "use_docker": False},
)

# ------------------------------------------------------------
# LangGraph State for Reporting
# ------------------------------------------------------------
class ReportingState(TypedDict):
    user_input: str
    report_type: str
    chart_type: str
    data_filters: Dict[str, Any]
    output_format: str
    agent_output: str
    file_paths: List[str]
    next: Literal["analyze_request", "generate_report", "create_chart", "end"]

# ------------------------------------------------------------
# Node Functions
# ------------------------------------------------------------
def analyze_request_node(state: ReportingState) -> ReportingState:
    """Analyze the user request to determine report type and requirements"""
    msg = state["user_input"].lower()
    
    # Determine report type
    if any(keyword in msg for keyword in ["sales", "revenue", "order"]):
        state["report_type"] = "sales"
    elif any(keyword in msg for keyword in ["financial", "invoice", "payment", "accounting"]):
        state["report_type"] = "financial"
    elif any(keyword in msg for keyword in ["inventory", "stock", "product"]):
        state["report_type"] = "inventory"
    elif any(keyword in msg for keyword in ["hr", "employee", "headcount", "payroll"]):
        state["report_type"] = "hr"
    elif any(keyword in msg for keyword in ["crm", "lead", "opportunity", "customer"]):
        state["report_type"] = "crm"
    else:
        state["report_type"] = "general"
    
    # Determine if chart is requested
    if any(keyword in msg for keyword in ["chart", "graph", "plot", "visualization", "visual"]):
        state["next"] = "create_chart"
        # Determine chart type
        if any(keyword in msg for keyword in ["line", "trend", "time"]):
            state["chart_type"] = "line"
        elif any(keyword in msg for keyword in ["bar", "column", "comparison"]):
            state["chart_type"] = "bar"
        elif any(keyword in msg for keyword in ["pie", "donut", "proportion"]):
            state["chart_type"] = "pie"
        elif any(keyword in msg for keyword in ["scatter", "correlation"]):
            state["chart_type"] = "scatter"
        else:
            state["chart_type"] = "auto"  # Let the agent decide
    else:
        state["next"] = "generate_report"
    
    # Determine output format
    if "pdf" in msg:
        state["output_format"] = "pdf"
    elif "excel" in msg or "xlsx" in msg:
        state["output_format"] = "excel"
    elif "csv" in msg:
        state["output_format"] = "csv"
    else:
        state["output_format"] = "html"  # Default
    
    state["file_paths"] = []
    
    return state

def generate_report_node(state: ReportingState) -> ReportingState:
    """Generate comprehensive reports using the reporting agent"""
    try:
        # Construct detailed prompt for the reporting agent
        prompt = f"""
Generate a comprehensive {state['report_type']} report based on this request: {state['user_input']}

Requirements:
- Output format: {state['output_format']}
- Include data analysis and insights
- Add statistical summaries
- Provide actionable recommendations
- Save the report file with timestamp

Please fetch relevant data from Odoo and create a professional report.
"""
        
        chat_result = reporting_proxy.initiate_chat(
            reporting_assistant, 
            message=prompt, 
            clear_history=True
        )
        
        # Extract response
        if hasattr(reporting_proxy, 'last_message') and reporting_proxy.last_message():
            state["agent_output"] = reporting_proxy.last_message()["content"]
        else:
            state["agent_output"] = "Report generated successfully."
            
    except Exception as e:
        state["agent_output"] = f"Error generating report: {str(e)}"
    
    state["next"] = "end"
    return state

def create_chart_node(state: ReportingState) -> ReportingState:
    """Generate charts and visualizations using the chart agent"""
    try:
        # Construct detailed prompt for the chart agent
        prompt = f"""
Create a {state['chart_type']} chart for {state['report_type']} data based on this request: {state['user_input']}

Requirements:
- Chart type: {state['chart_type']} (or choose the most appropriate if 'auto')
- Make it interactive and professional
- Include proper titles, labels, and legends
- Save as both HTML (interactive) and PNG (static)
- Add data insights and annotations
- Use appropriate color schemes

Please fetch relevant data from Odoo and create a compelling visualization.
"""
        
        chat_result = chart_proxy.initiate_chat(
            chart_assistant, 
            message=prompt, 
            clear_history=True
        )
        
        # Extract response
        if hasattr(chart_proxy, 'last_message') and chart_proxy.last_message():
            state["agent_output"] = chart_proxy.last_message()["content"]
        else:
            state["agent_output"] = "Chart generated successfully."
            
    except Exception as e:
        state["agent_output"] = f"Error generating chart: {str(e)}"
    
    state["next"] = "end"
    return state

# ------------------------------------------------------------
# Build LangGraph Workflow
# ------------------------------------------------------------
workflow = StateGraph(ReportingState)

workflow.add_node("analyze_request", analyze_request_node)
workflow.add_node("generate_report", generate_report_node)
workflow.add_node("create_chart", create_chart_node)

workflow.set_entry_point("analyze_request")
workflow.add_conditional_edges(
    "analyze_request",
    lambda s: s["next"],
    {
        "generate_report": "generate_report",
        "create_chart": "create_chart",
        "end": END
    }
)
workflow.add_edge("generate_report", END)
workflow.add_edge("create_chart", END)

reporting_graph = workflow.compile()

# ------------------------------------------------------------
# Integration with Main Agent
# ------------------------------------------------------------
class AutoGenReportingNode:
    """Node for handling advanced reporting with AutoGen agents"""
    
    def __init__(self):
        self.graph = reporting_graph
        
    def process(self, state: AgentState) -> AgentState:
        """Process advanced reporting requests using AutoGen agents"""
        try:
            if state is None:
                logger.error("AutoGen reporting failed: state is None")
                return state
            
            try:
                user_message = StateManager.get_last_user_message(state)
            except Exception as e:
                logger.warning(f"Could not extract user message for AutoGen reporting: {e}")
                user_message = ""
            
            logger.info(f"Processing AutoGen reporting request: {user_message[:100]}...")
            
            # Get session-specific Odoo client
            session_id = state.get("session_id")
            current_odoo_client = get_odoo_client_for_session(session_id)
            
            # Ensure Odoo connection
            if not current_odoo_client.test_connection()["status"] == "success":
                return StateManager.set_error(state, "Odoo connection failed")
            
            # Create initial state for reporting graph
            reporting_state = {
                "user_input": user_message,
                "report_type": "",
                "chart_type": "",
                "data_filters": {},
                "output_format": "",
                "agent_output": "",
                "file_paths": [],
                "next": ""
            }
            
            # Run the reporting workflow
            result = self.graph.invoke(reporting_state)
            
            # Update main agent state with results
            state["response"] = result["agent_output"]
            state["response_type"] = "autogen_report"
            
            # Add file paths if any were generated
            if result.get("file_paths"):
                state["generated_files"] = result["file_paths"]
            
            return state
            
        except Exception as e:
            logger.error(f"AutoGen reporting failed: {str(e)}")
            return StateManager.set_error(state, f"AutoGen reporting failed: {str(e)}")
    
    def supports_request(self, user_message: str) -> bool:
        """Check if this node can handle the request"""
        message_lower = user_message.lower()
        
        # Keywords that indicate advanced reporting needs
        advanced_keywords = [
            "chart", "graph", "plot", "visualization", "dashboard",
            "trend analysis", "comparative", "interactive", "excel report",
            "pdf report", "advanced report", "detailed analysis",
            "kpi", "metrics", "performance analysis"
        ]
        
        return any(keyword in message_lower for keyword in advanced_keywords)

# ------------------------------------------------------------
# CLI for Testing
# ------------------------------------------------------------
if __name__ == "__main__":
    print("🚀 AutoGen Advanced Reporting Agent ready!")
    print("Examples:")
    print("  - 'Create a sales trend chart for the last 6 months'")
    print("  - 'Generate a detailed financial report in PDF format'")
    print("  - 'Show me an interactive dashboard for inventory levels'")
    print("  - 'Create a bar chart comparing top customers by revenue'")
    print("\nType 'exit' to quit.\n")
    
    while True:
        prompt = input("📊 > ").strip()
        if prompt.lower() in {"exit", "quit"}:
            break
        
        try:
            # Test the reporting workflow
            initial_state = {
                "user_input": prompt,
                "report_type": "",
                "chart_type": "",
                "data_filters": {},
                "output_format": "",
                "agent_output": "",
                "file_paths": [],
                "next": ""
            }
            
            result = reporting_graph.invoke(initial_state)
            print(f"\n📈 Result:\n{result['agent_output']}\n")
            
            if result.get("file_paths"):
                print(f"📁 Generated files: {', '.join(result['file_paths'])}\n")
                
        except Exception as e:
            print(f"\n❌ Error: {str(e)}\n")