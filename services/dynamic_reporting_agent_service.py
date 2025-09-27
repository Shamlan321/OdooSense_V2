#!/usr/bin/env python3
"""
Dynamic Reporting Agent Service
==============================
LangChain-based agent for Odoo reporting with comprehensive export capabilities:
- PDF reports with professional formatting
- Interactive HTML charts and visualizations
- CSV data exports for spreadsheet analysis
- Excel (.xlsx) files with formatting and auto-sizing
Integrates with the main platform while maintaining separation of concerns.
"""

import json
import os
import sys
import datetime
import re
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional, Union
import uuid
import tempfile
import shutil
from dotenv import load_dotenv
import xmlrpc.client
import pandas as pd
import base64
import io
from datetime import datetime

# LangChain & Gemini
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.agents import initialize_agent, AgentType
from langchain.tools import BaseTool
from pydantic import BaseModel, Field
from typing import Type, Optional, ClassVar

# Plotly
import plotly.express as px
import plotly.graph_objects as go

# ReportLab
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors
from reportlab.lib.units import inch

# Load environment variables from .env file
load_dotenv('rag_config_enhanced.env')

logger = logging.getLogger(__name__)

# Excel/CSV support
try:
    import openpyxl
    EXCEL_AVAILABLE = True
except ImportError:
    EXCEL_AVAILABLE = False
    logger.warning("openpyxl not available. Excel export will be limited.")

import csv

class DynamicReportingAgentService:
    """
    Dedicated service for LangChain-based reporting and CRUD operations.
    Handles dynamic credentials, file generation, and chat integration.
    """
    
    def __init__(self):
        self.llm = None
        self.credentials_cache = {}
        self.file_storage_path = "reports/"
        self.tools = {}
        self._ensure_storage_path()
        
    def _ensure_storage_path(self):
        """Ensure the file storage directory exists"""
        # Use absolute path to avoid working directory issues
        base_path = Path(__file__).parent.parent  # Go up from services/ to project root
        storage_path = base_path / self.file_storage_path
        storage_path.mkdir(parents=True, exist_ok=True)
        
    def initialize_agent(self, credentials: Dict[str, str], session_id: str) -> bool:
        """
        Initialize LangChain agent with user credentials
        
        Args:
            credentials: Odoo connection credentials
            session_id: Session identifier for caching
            
        Returns:
            bool: True if initialization successful
        """
        try:
            # Cache credentials for this session
            self.credentials_cache[session_id] = credentials
            
            # Initialize LLM
            google_api_key = os.getenv("GOOGLE_API_KEY")
            if not google_api_key:
                logger.error("GOOGLE_API_KEY not found in environment")
                return False
            
            self.llm = ChatGoogleGenerativeAI(
                model="gemini-1.5-flash-latest",
                google_api_key=google_api_key,
                temperature=0.3,
                convert_system_message_to_human=True
            )
            
            # Create tools for this session
            self.tools[session_id] = {
                'odoo_query': OdooQueryTool(credentials),
                'pdf_report': PDFReportTool(session_id),
                'chart': ChartTool(session_id),
                'csv_export': CSVExportTool(session_id),
                'excel_export': ExcelExportTool(session_id)
            }
            
            logger.info(f"Dynamic reporting agent initialized for session {session_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize dynamic reporting agent: {str(e)}")
            return False
    
    def generate_report(self, query: str, session_id: str) -> Dict[str, Any]:
        """
        Generate report using the dynamic reporting agent
        
        Args:
            query: User query
            session_id: Session identifier
            
        Returns:
            Dict containing response and metadata
        """
        try:
            if session_id not in self.tools:
                return {
                    "success": False,
                    "error": "Agent not initialized for this session",
                    "agent_type": "dynamic_reporting_agent"
                }
            
            # Get tools for this session
            tools = self.tools[session_id]
            
            # Simple keyword-based routing instead of LLM parsing
            query_lower = query.lower()
            
            # First, always get data from Odoo
            data_result = tools['odoo_query']._run(query)
            if not data_result.get('success'):
                return {
                    "success": False,
                    "error": data_result.get('error', 'Failed to retrieve data'),
                    "agent_type": "dynamic_reporting_agent"
                }
            
            # Convert data to JSON
            data_json = json.dumps(data_result['data'])
            
            # Determine output type based on keywords
            if 'pdf' in query_lower and ('generate pdf' in query_lower or 'create pdf' in query_lower or 'export pdf' in query_lower or 'save as pdf' in query_lower):
                # Generate PDF only when explicitly requested
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                unique_id = str(uuid.uuid4())[:8]
                filename = f"report_{session_id}_{timestamp}_{unique_id}.pdf"
                pdf_result = tools['pdf_report']._run(data_json, f"Report: {query}", filename)
                return {
                    "success": True,
                    "response": f"PDF report generated: {pdf_result}",
                    "files": self._get_specific_files(session_id, [filename]),
                    "agent_type": "dynamic_reporting_agent"
                }
            elif 'chart' in query_lower or 'graph' in query_lower or 'visualization' in query_lower:
                # Generate interactive HTML chart with unique filename
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                unique_id = str(uuid.uuid4())[:8]
                filename = f"chart_{session_id}_{timestamp}_{unique_id}.html"
                
                # Analyze data structure to determine appropriate fields
                try:
                    data_df = pd.DataFrame(data_result['data'])
                    available_columns = list(data_df.columns)
                    
                    logger.info(f"Available columns in data: {available_columns}")
                    logger.info(f"Data sample: {data_df.head(2).to_dict('records')}")
                    logger.info(f"Data shape: {data_df.shape}")
                    logger.info(f"Data types: {data_df.dtypes.to_dict()}")
                    
                    # Find appropriate x and y fields
                    x_field = None
                    y_field = None
                    
                    # Look for common field patterns with better matching
                    for col in available_columns:
                        col_lower = col.lower()
                        # X-axis fields (categorical) - prioritize more meaningful fields
                        if any(keyword in col_lower for keyword in ['partner', 'customer', 'department', 'category', 'type', 'group']):
                            x_field = col
                        elif any(keyword in col_lower for keyword in ['name', 'order']):
                            # Only use name/order if no better categorical field found
                            if not x_field:
                                x_field = col
                        # Y-axis fields (numerical)
                        elif any(keyword in col_lower for keyword in ['count', 'total', 'amount', 'number', 'quantity', 'value', 'price', 'sum']):
                            y_field = col
                    
                    # If no specific fields found, use more generic approach
                    if not x_field and len(available_columns) > 0:
                        # Use first column as X
                        x_field = available_columns[0]
                    if not y_field and len(available_columns) > 1:
                        # Look for any numeric column for Y
                        for col in available_columns[1:]:
                            if pd.api.types.is_numeric_dtype(data_df[col]):
                                y_field = col
                                break
                        # If no numeric column found, use second column
                        if not y_field and len(available_columns) > 1:
                            y_field = available_columns[1]
                    elif not y_field and len(available_columns) == 1:
                        # If only one column, use it for both (count of occurrences)
                        x_field = available_columns[0]
                        y_field = 'count'
                        # Add count column
                        data_df['count'] = 1
                        data_result['data'] = data_df.to_dict('records')
                        data_json = json.dumps(data_result['data'])
                    
                    # Validate that the fields actually exist in the data
                    if x_field and x_field not in available_columns:
                        logger.warning(f"X field '{x_field}' not found in columns: {available_columns}")
                        x_field = available_columns[0] if available_columns else None
                    if y_field and y_field not in available_columns:
                        logger.warning(f"Y field '{y_field}' not found in columns: {available_columns}")
                        y_field = available_columns[1] if len(available_columns) > 1 else None
                    
                    logger.info(f"Chart fields - X: {x_field}, Y: {y_field}, Available columns: {available_columns}")
                    
                    if not x_field or not y_field:
                        raise Exception(f"Cannot determine chart fields. Available columns: {available_columns}")
                    
                    # Debug: Log the data being passed to chart tool
                    logger.info(f"Data being passed to chart tool: {data_json[:500]}...")
                    logger.info(f"Chart tool call: _run(data_json, 'bar', 'Chart: {query}', '{x_field}', '{y_field}', filename='{filename}')")
                    
                    chart_result = tools['chart']._run(data_json, "bar", f"Chart: {query}", x_field, y_field, filename=filename)
                    
                    # Read the HTML content for direct display
                    base_path = Path(__file__).parent.parent  # Go up from services/ to project root
                    html_filepath = base_path / self.file_storage_path / session_id / filename
                    html_content = ""
                    if html_filepath.exists():
                        with open(html_filepath, 'r', encoding='utf-8') as f:
                            html_content = f.read()
                    
                    return {
                        "success": True,
                        "response": f"Interactive chart generated: {chart_result}",
                        "files": self._get_specific_files(session_id, [filename]),
                        "html_content": html_content,  # Add HTML content for direct display
                        "agent_type": "dynamic_reporting_agent"
                    }
                
                except Exception as e:
                    logger.error(f"Error in chart field detection: {str(e)}")
                    # Fallback to PDF if chart generation fails with unique filename
                    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                    unique_id = str(uuid.uuid4())[:8]
                    filename = f"report_{session_id}_{timestamp}_{unique_id}.pdf"
                    pdf_result = tools['pdf_report']._run(data_json, f"Report: {query}", filename)
                    return {
                        "success": True,
                        "response": f"Chart generation failed, generated PDF instead: {pdf_result}",
                        "files": self._get_specific_files(session_id, [filename]),
                        "agent_type": "dynamic_reporting_agent"
                    }
                
            elif 'csv' in query_lower:
                # Generate CSV with unique filename
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                unique_id = str(uuid.uuid4())[:8]
                filename = f"data_{session_id}_{timestamp}_{unique_id}.csv"
                csv_result = tools['csv_export']._run(data_json, filename)
                return {
                    "success": True,
                    "response": f"CSV file generated: {csv_result}",
                    "files": self._get_specific_files(session_id, [filename]),
                    "agent_type": "dynamic_reporting_agent"
                }
                
            elif 'excel' in query_lower or 'xlsx' in query_lower or 'spreadsheet' in query_lower:
                # Generate Excel with unique filename
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                unique_id = str(uuid.uuid4())[:8]
                filename = f"data_{session_id}_{timestamp}_{unique_id}.xlsx"
                excel_result = tools['excel_export']._run(data_json, filename)
                return {
                    "success": True,
                    "response": f"Excel file generated: {excel_result}",
                    "files": self._get_specific_files(session_id, [filename]),
                    "agent_type": "dynamic_reporting_agent"
                }

            else:
                # Default to formatted text response
                formatted_response = self._format_data_as_text(data_result['data'], query)
                return {
                    "success": True,
                    "response": formatted_response,
                    "files": [],
                    "agent_type": "dynamic_reporting_agent"
                }
            
        except Exception as e:
            logger.error(f"Error generating report: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "agent_type": "dynamic_reporting_agent"
            }
    
    def _format_data_as_text(self, data: List[Dict], query: str) -> str:
        """Format data as a well-structured text response"""
        try:
            if not data:
                return "No data found for your query."
            
            # Create a summary header
            total_records = len(data)
            response_lines = []
            response_lines.append(f"📊 **Data Report Results**")
            response_lines.append(f"Found {total_records} record(s)\n")
            
            # Convert to DataFrame for easier processing
            df = pd.DataFrame(data)
            
            # Generate summary statistics if numeric columns exist
            numeric_cols = df.select_dtypes(include=['number']).columns
            if len(numeric_cols) > 0:
                response_lines.append("📈 **Summary Statistics:**")
                for col in numeric_cols:
                    if 'total' in col.lower() or 'amount' in col.lower() or 'price' in col.lower():
                        total_val = df[col].sum()
                        avg_val = df[col].mean()
                        response_lines.append(f"• {col}: Total = {total_val:,.2f}, Average = {avg_val:,.2f}")
                response_lines.append("")
            
            # Show detailed records (limit to first 10 for readability)
            response_lines.append("📋 **Detailed Records:**")
            display_limit = min(10, total_records)
            
            for i, record in enumerate(data[:display_limit]):
                response_lines.append(f"\n**Record {i+1}:**")
                for key, value in record.items():
                    if value:  # Only show non-empty values
                        response_lines.append(f"• {key}: {value}")
            
            if total_records > display_limit:
                response_lines.append(f"\n... and {total_records - display_limit} more records")
                response_lines.append("\n💡 *Tip: Use 'generate PDF' or 'export to Excel' to get the complete dataset*")
            
            return "\n".join(response_lines)
            
        except Exception as e:
            logger.error(f"Error formatting data as text: {str(e)}")
            return f"Data retrieved successfully, but formatting failed. Found {len(data) if data else 0} records. Use 'generate PDF' for a formatted report."

    def _get_generated_files(self, session_id: str) -> List[Dict[str, str]]:
        """Get list of ALL generated files for the session"""
        try:
            files = []
            # Use absolute path to avoid working directory issues
            base_path = Path(__file__).parent.parent  # Go up from services/ to project root
            session_dir = base_path / self.file_storage_path / session_id
            if session_dir.exists():
                for file_path in session_dir.glob("*"):
                    if file_path.is_file():
                        files.append({
                            "filename": file_path.name,
                            "path": str(file_path),
                            "size": file_path.stat().st_size,
                            "type": file_path.suffix.lower()
                        })
            return files
        except Exception as e:
            logger.error(f"Error getting generated files: {str(e)}")
            return []
    
    def _get_specific_files(self, session_id: str, filenames: List[str]) -> List[Dict[str, str]]:
        """Get list of specific files for the current request only"""
        try:
            files = []
            # Use absolute path to avoid working directory issues
            base_path = Path(__file__).parent.parent  # Go up from services/ to project root
            session_dir = base_path / self.file_storage_path / session_id
            
            if session_dir.exists():
                for filename in filenames:
                    file_path = session_dir / filename
                    if file_path.exists() and file_path.is_file():
                        files.append({
                            "filename": file_path.name,
                            "path": str(file_path),
                            "size": file_path.stat().st_size,
                            "type": file_path.suffix.lower()
                        })
            return files
        except Exception as e:
            logger.error(f"Error getting specific files: {str(e)}")
            return []
    
    def get_file_download_url(self, filename: str, session_id: str) -> str:
        """Get download URL for a generated file"""
        # Use absolute path to avoid working directory issues
        base_path = Path(__file__).parent.parent  # Go up from services/ to project root
        session_dir = base_path / self.file_storage_path / session_id
        file_path = session_dir / filename
        if file_path.exists():
            return str(file_path)
        return None
    
    def cleanup_session_files(self, session_id: str) -> bool:
        """Clean up files for a session"""
        try:
            # Use absolute path to avoid working directory issues
            base_path = Path(__file__).parent.parent  # Go up from services/ to project root
            session_dir = base_path / self.file_storage_path / session_id
            if session_dir.exists():
                shutil.rmtree(session_dir)
            return True
        except Exception as e:
            logger.error(f"Error cleaning up session files: {str(e)}")
            return False
    
    def health_check(self) -> Dict[str, Any]:
        """Health check for the reporting agent"""
        return {
            "status": "healthy" if self.llm else "uninitialized",
            "agent_type": "dynamic_reporting_agent",
            "sessions_initialized": len(self.tools)
        }


# =========================
# HELPER: Clean Records
# =========================
def clean_record(rec):
    """Clean Odoo record for JSON serialization"""
    cleaned = {}
    for k, v in rec.items():
        if isinstance(v, list) and len(v) == 2 and isinstance(v[0], int):
            cleaned[k] = v[1]
        elif isinstance(v, datetime):
            cleaned[k] = v.strftime("%Y-%m-%d %H:%M:%S")
        elif isinstance(v, (dict, list)):
            cleaned[k] = str(v)
        else:
            cleaned[k] = v
    return cleaned


# =========================
# TOOL 1: Query Odoo
# =========================
class OdooQueryInput(BaseModel):
    natural_language: str = Field(..., description="Natural language query")

class OdooQueryTool:
    """Custom Odoo query tool that implements LangChain tool interface"""
    
    def __init__(self, credentials: Dict[str, str]):
        self.name = "query_odoo_data"
        self.description = "Fetch data from Odoo using natural language."
        self.args_schema = OdooQueryInput
        self.args = {"natural_language": "string"}
        self.credentials = credentials
        self._connect_to_odoo()
    
    def _connect_to_odoo(self):
        """Connect to Odoo using credentials"""
        try:
            url = self.credentials.get('url')
            # Handle both 'db' and 'database' keys
            db = self.credentials.get('db') or self.credentials.get('database')
            # Handle both 'user' and 'username' keys
            username = self.credentials.get('user') or self.credentials.get('username')
            password = self.credentials.get('password')
            
            # Validate required fields
            if not all([url, db, username, password]):
                missing_fields = []
                if not url: missing_fields.append('url')
                if not db: missing_fields.append('db/database')
                if not username: missing_fields.append('user/username')
                if not password: missing_fields.append('password')
                raise Exception(f"Missing required credentials: {', '.join(missing_fields)}")
            
            logger.info(f"Connecting to Odoo at {url} with database {db} as user {username}")
            
            common = xmlrpc.client.ServerProxy(f'{url}/xmlrpc/2/common')
            self.uid = common.authenticate(db, username, password, {})
            
            if not self.uid:
                raise Exception(f"Authentication failed for user {username} on database {db}")
                
            self.models = xmlrpc.client.ServerProxy(f'{url}/xmlrpc/2/object')
            self.db = db
            self.password = password
            
            logger.info(f"Successfully connected to Odoo as user ID: {self.uid}")
            
        except Exception as e:
            logger.error(f"Failed to connect to Odoo: {str(e)}")
            logger.error(f"Credentials provided: url={self.credentials.get('url')}, db={self.credentials.get('db') or self.credentials.get('database')}, user={self.credentials.get('user') or self.credentials.get('username')}")
            raise Exception(f"Failed to connect to Odoo: {e}")

    def _run(self, natural_language: str) -> dict:
        prompt = f"""
        You are an expert Odoo 18 analyst. Given a query, determine the appropriate:
        - model: Choose the correct Odoo model based on the query type
        - fields: Relevant fields to retrieve 
        - domain: Filters to apply
        - related_query: Optional - if the query needs data from related models

        IMPORTANT MODEL MAPPING:
        - Employee/HR queries (headcount, department breakdown) → use "hr.employee"
        - Sales queries (orders, quotations) → use "sale.order" 
        - Customer queries → use "res.partner"
        - Product queries → use "product.product"
        - Invoice queries → use "account.move"
        - Lead queries → use "crm.lead"
        - Sales order lines/products → use "sale.order.line"

        FIELD GUIDELINES:
        - For hr.employee: use ["name", "department_id", "job_id", "work_email", "active"]
        - For sale.order: use ["name", "partner_id", "amount_total", "state", "date_order"]
        - For sale.order.line: use ["product_id", "name", "product_uom_qty", "price_unit", "price_subtotal", "order_id"]
        - NEVER use dot notation like 'partner_id.name' — just use 'partner_id'
        - CRITICAL: NEVER use 'region' field - it doesn't exist on any model
        - For regional queries (like 'Pre-sales region'), ignore the region filter completely
        - Focus on date ranges and standard fields only

        RELATIONSHIP HANDLING:
        If query asks for "products in orders" or "order lines", set related_query to:
        {{
          "main_model": "sale.order", 
          "related_model": "sale.order.line",
          "relationship_field": "order_id",
          "include_related": true
        }}

        Respond in strict JSON format:
        {{
          "model": "appropriate_model_name",
          "fields": ["relevant", "field", "names"],
          "domain": [["field","operator","value"]],
          "related_query": null_or_relationship_object
        }}

        IMPORTANT EXAMPLES:
        - "sales report for Pre-sales region" → ignore 'Pre-sales region', use standard sale.order query
        - "monthly sales for last quarter" → use date_order field with date range filter
        - "sales by region" → ignore region completely, return all sales data
        
        Query: {natural_language}
        """
        try:
            # Use a simple LLM call for this analysis
            from langchain_google_genai import ChatGoogleGenerativeAI
            google_api_key = os.getenv("GOOGLE_API_KEY")
            llm = ChatGoogleGenerativeAI(
                model="gemini-1.5-flash-latest",
                google_api_key=google_api_key,
                temperature=0.1
            )
            
            response = llm.invoke(prompt)
            content = response.content.strip()
            
            # More robust JSON extraction
            try:
                # Try to find JSON in the response
                start_idx = content.find('{')
                end_idx = content.rfind('}') + 1
                
                if start_idx == -1 or end_idx == 0:
                    # No JSON found, try to determine model from query keywords
                    query_lower = natural_language.lower()
                    if any(keyword in query_lower for keyword in ['headcount', 'employee', 'department', 'hr', 'staff']):
                        analysis = {
                            "model": "hr.employee",
                            "fields": ["name", "department_id", "job_id", "work_email", "active"],
                            "domain": [["active", "=", True]]
                        }
                    elif any(keyword in query_lower for keyword in ['quotation', 'quote', 'draft']):
                        analysis = {
                            "model": "sale.order",
                            "fields": ["name", "partner_id", "amount_total", "state", "date_order"],
                            "domain": [["state", "=", "draft"]]
                        }
                    else:
                        # Default fallback to sale orders
                        analysis = {
                            "model": "sale.order",
                            "fields": ["name", "partner_id", "amount_total", "state", "date_order"],
                            "domain": [["state", "=", "sale"]]
                        }
                    
                    # Apply smart fallback to detect related queries
                    analysis = self._apply_smart_fallback(analysis, natural_language)
                else:
                    json_str = content[start_idx:end_idx]
                    analysis = json.loads(json_str)
                    
                    # Apply smart fallback to detect related queries
                    analysis = self._apply_smart_fallback(analysis, natural_language)
                    
            except json.JSONDecodeError:
                # If JSON parsing fails, try to determine model from query keywords
                query_lower = natural_language.lower()
                if any(keyword in query_lower for keyword in ['headcount', 'employee', 'department', 'hr', 'staff']):
                    analysis = {
                        "model": "hr.employee",
                        "fields": ["name", "department_id", "job_id", "work_email", "active"],
                        "domain": [["active", "=", True]]
                    }
                elif any(keyword in query_lower for keyword in ['quotation', 'quote', 'draft']):
                    analysis = {
                        "model": "sale.order",
                        "fields": ["name", "partner_id", "amount_total", "state", "date_order"],
                        "domain": [["state", "=", "draft"]]
                    }
                else:
                    # Default fallback to sale orders
                    analysis = {
                        "model": "sale.order",
                        "fields": ["name", "partner_id", "amount_total", "state", "date_order"],
                        "domain": [["state", "=", "sale"]]
                    }

            model = analysis.get("model", "sale.order")
            fields = analysis.get("fields", ["name", "date_order", "amount_total", "partner_id"])
            domain = analysis.get("domain", [["state", "=", "sale"]])
            related_query = analysis.get("related_query")
            
            # Validate and clean domain to prevent invalid field errors
            domain = self._validate_domain(domain, model)

            # Handle related queries (e.g., products in sales orders)
            if related_query and related_query.get("include_related"):
                combined_data = self._execute_related_query(model, fields, domain, related_query, natural_language)
                return {
                    "success": True,
                    "data": combined_data,
                    "model": f"{model}_with_{related_query.get('related_model', '')}",
                    "query": natural_language
                }
            else:
                # Standard single-model query
                records = self.models.execute_kw(
                    self.db, self.uid, self.password,
                    model, 'search_read',
                    [domain],
                    {'fields': fields, 'limit': 100}
                )

                cleaned_records = [clean_record(rec) for rec in records]

                return {
                    "success": True,
                    "data": cleaned_records,
                    "model": model,
                    "query": natural_language
                }
        except Exception as e:
            return {"success": False, "error": str(e), "query": natural_language}
    
    def _validate_domain(self, domain: list, model: str) -> list:
        """Validate domain filters and remove invalid fields"""
        if not domain:
            return []
            
        # Define known invalid fields for common models
        invalid_fields = {
            'res.partner': ['region'],  # 'region' field doesn't exist on res.partner
            'sale.order': [],
            'hr.employee': []
        }
        
        # Get invalid fields for this model
        model_invalid_fields = invalid_fields.get(model, [])
        
        # Filter out invalid domain conditions
        valid_domain = []
        for condition in domain:
            if isinstance(condition, list) and len(condition) >= 3:
                field_name = condition[0]
                # Check if field contains invalid field names
                if not any(invalid_field in field_name for invalid_field in model_invalid_fields):
                    valid_domain.append(condition)
                else:
                    logging.warning(f"Removed invalid field '{field_name}' from domain for model '{model}'")
            else:
                valid_domain.append(condition)  # Keep logical operators like '&', '|'
                
        return valid_domain if valid_domain else [["id", ">", 0]]  # Default safe domain
    
    def _apply_smart_fallback(self, analysis: dict, natural_language: str) -> dict:
        """Apply smart fallback to detect if we need related data"""
        query_lower = natural_language.lower()
        if (analysis.get("model") == "sale.order" and 
            any(keyword in query_lower for keyword in ['products', 'product', 'lines', 'order lines', 'items']) and
            not analysis.get("related_query")):
            
            analysis["related_query"] = {
                "main_model": "sale.order",
                "related_model": "sale.order.line",
                "relationship_field": "order_id",
                "include_related": True
            }
        return analysis
    
    def _execute_related_query(self, main_model: str, main_fields: list, main_domain: list, related_config: dict, query: str) -> list:
        """Execute a query that involves related models (e.g., orders with their products)"""
        try:
            related_model = related_config.get("related_model", "sale.order.line")
            relationship_field = related_config.get("relationship_field", "order_id")
            
            # Step 1: Get main records (e.g., sale orders)
            main_records = self.models.execute_kw(
                self.db, self.uid, self.password,
                main_model, 'search_read',
                [main_domain],
                {'fields': main_fields, 'limit': 100}
            )
            
            if not main_records:
                return []
            
            # Step 2: Get related records (e.g., order lines/products)
            main_ids = [record['id'] for record in main_records]
            
            # Determine related fields based on model
            if related_model == "sale.order.line":
                related_fields = ["product_id", "name", "product_uom_qty", "price_unit", "price_subtotal", "order_id"]
            else:
                related_fields = ["id", "name"]
            
            # Check if query is asking for specific order
            query_lower = query.lower()
            specific_order = None
            if "order:" in query_lower or "s00" in query_lower:
                # Extract order reference (e.g., S00014)
                import re
                order_match = re.search(r's\d{5}', query_lower)
                if order_match:
                    specific_order = order_match.group().upper()
            
            # Build domain for related records
            if specific_order:
                # Find the specific order ID
                specific_domain = [["name", "=", specific_order]]
                specific_records = self.models.execute_kw(
                    self.db, self.uid, self.password,
                    main_model, 'search_read',
                    [specific_domain],
                    {'fields': ['id', 'name'], 'limit': 1}
                )
                if specific_records:
                    related_domain = [[relationship_field, "=", specific_records[0]['id']]]
                else:
                    return []  # Order not found
            else:
                related_domain = [[relationship_field, "in", main_ids]]
            
            related_records = self.models.execute_kw(
                self.db, self.uid, self.password,
                related_model, 'search_read',
                [related_domain],
                {'fields': related_fields, 'limit': 500}
            )
            
            # Step 3: Combine data
            combined_data = []
            
            if specific_order and related_records:
                # For specific order queries, focus on the products
                for line in related_records:
                    clean_line = clean_record(line)
                    # Add order info to each line
                    if specific_records:
                        clean_line['order_name'] = specific_records[0]['name']
                    combined_data.append(clean_line)
            else:
                # For general queries, combine orders with their products
                order_dict = {record['id']: clean_record(record) for record in main_records}
                
                for order_id, order_data in order_dict.items():
                    # Find related records for this order
                    order_related = [r for r in related_records if r.get(relationship_field) and 
                                   (isinstance(r[relationship_field], list) and r[relationship_field][0] == order_id or
                                    isinstance(r[relationship_field], int) and r[relationship_field] == order_id)]
                    
                    if order_related:
                        # Add products info to order
                        order_data['products'] = []
                        for line in order_related:
                            clean_line = clean_record(line)
                            order_data['products'].append(clean_line)
                        order_data['product_count'] = len(order_related)
                    else:
                        order_data['products'] = []
                        order_data['product_count'] = 0
                    
                    combined_data.append(order_data)
            
            return combined_data
            
        except Exception as e:
            logger.error(f"Error in related query: {str(e)}")
            # Fallback to main records only
            try:
                records = self.models.execute_kw(
                    self.db, self.uid, self.password,
                    main_model, 'search_read',
                    [main_domain],
                    {'fields': main_fields, 'limit': 100}
                )
                return [clean_record(rec) for rec in records]
            except:
                return []
    
    # LangChain compatibility methods
    def get(self, key, default=None):
        """LangChain compatibility method"""
        return getattr(self, key, default)
    
    def __getitem__(self, key):
        """LangChain compatibility method"""
        return getattr(self, key)
    
    def __contains__(self, key):
        """LangChain compatibility method"""
        return hasattr(self, key)


# =========================
# TOOL 2: Generate PDF
# =========================
class PDFReportInput(BaseModel):
    data_json: str = Field(..., description="JSON string of data")
    title: str = Field(..., description="Report title")
    filename: str = Field(..., description="e.g., sales_report.pdf")

class PDFReportTool:
    """Custom PDF report tool that implements LangChain tool interface"""
    
    def __init__(self, session_id: str):
        self.name = "generate_pdf_report"
        self.description = "Generates a PDF report and saves it to disk."
        self.args_schema = PDFReportInput
        self.args = {
            "data_json": "string",
            "title": "string", 
            "filename": "string"
        }
        self.session_id = session_id
        self.file_storage_path = "reports/"
    
    def _run(self, data_json: str, title: str, filename: str) -> str:
        try:
            data = json.loads(data_json)

            # Create session-specific directory using absolute path
            base_path = Path(__file__).parent.parent  # Go up from services/ to project root
            session_dir = base_path / self.file_storage_path / self.session_id
            session_dir.mkdir(parents=True, exist_ok=True)
            
            filepath = session_dir / filename

            # Generate professional PDF with enhanced formatting
            return self._generate_professional_pdf(data, title, filepath)
            
        except Exception as e:
            logger.error(f"Error generating PDF: {str(e)}")
            return f"Error generating PDF: {str(e)}"
    
    def _generate_professional_pdf(self, data: list, title: str, filepath: Path) -> str:
        """Generate a professionally formatted PDF with proper text handling"""
        try:
            from reportlab.lib.pagesizes import A4, letter
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            from reportlab.lib.units import inch
            from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT
            from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
            from reportlab.platypus.tableofcontents import TableOfContents
            from reportlab.lib import colors
            from datetime import datetime

            buffer = io.BytesIO()
            
            # Enhanced page setup with better margins
            doc = SimpleDocTemplate(
                buffer, 
                pagesize=letter,
                rightMargin=0.5*inch, 
                leftMargin=0.5*inch,
                topMargin=0.75*inch, 
                bottomMargin=0.75*inch
            )
            
            # Create enhanced styles
            styles = getSampleStyleSheet()
            
            # Custom styles for better formatting
            title_style = ParagraphStyle(
                'CustomTitle',
                parent=styles['Title'],
                fontSize=18,
                textColor=colors.darkblue,
                alignment=TA_CENTER,
                spaceAfter=30,
                spaceBefore=20
            )
            
            heading_style = ParagraphStyle(
                'CustomHeading',
                parent=styles['Heading1'],
                fontSize=14,
                textColor=colors.darkblue,
                alignment=TA_LEFT,
                spaceAfter=12,
                spaceBefore=20
            )
            
            normal_style = ParagraphStyle(
                'CustomNormal',
                parent=styles['Normal'],
                fontSize=10,
                alignment=TA_LEFT,
                spaceAfter=6
            )
            
            small_style = ParagraphStyle(
                'CustomSmall',
                parent=styles['Normal'],
                fontSize=8,
                alignment=TA_LEFT,
                spaceAfter=3
            )
            
            flowables = []
            
            # Title and header
            flowables.append(Paragraph(title, title_style))
            flowables.append(Paragraph(f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", small_style))
            flowables.append(Spacer(1, 20))
            
            if not data:
                flowables.append(Paragraph("No data to display.", normal_style))
                doc.build(flowables)
                buffer.seek(0)
                with open(filepath, "wb") as f:
                    f.write(buffer.read())
                buffer.close()
                return f"PDF successfully generated and saved as '{filepath.name}'"
            
            # Detect data structure and format accordingly
            if self._is_related_data(data):
                # Handle complex relationship data (orders with products)
                flowables.extend(self._format_related_data(data, heading_style, normal_style, small_style))
            else:
                # Handle simple tabular data
                flowables.extend(self._format_tabular_data(data, heading_style, normal_style))
            
            # Add summary
            flowables.append(Spacer(1, 20))
            flowables.append(Paragraph(f"Total Records: {len(data)}", normal_style))
            
            doc.build(flowables)
            buffer.seek(0)
            
            # Save to file
            with open(filepath, "wb") as f:
                f.write(buffer.read())
            
            buffer.close()
            logger.info(f"✅ Professional PDF saved: {filepath}")
            return f"PDF successfully generated and saved as '{filepath.name}'"
            
        except Exception as e:
            logger.error(f"Error in professional PDF generation: {str(e)}")
            # Fallback to simple PDF
            return self._generate_simple_pdf_fallback(data, title, filepath)
    
    def _is_related_data(self, data: list) -> bool:
        """Check if data contains relationship structures (like orders with products)"""
        if not data or not isinstance(data, list):
            return False
        
        first_item = data[0] if data else {}
        # Check for relationship indicators
        return any(key in first_item for key in ['products', 'product_count', 'order_name', 'order_id'])
    
    def _format_related_data(self, data: list, heading_style, normal_style, small_style) -> list:
        """Format complex relationship data (orders with products) professionally"""
        flowables = []
        
        for i, record in enumerate(data):
            if i > 0:
                flowables.append(Spacer(1, 15))
            
            # Check if this is order-with-products or specific-order-products
            if 'products' in record:
                # Orders with embedded products
                order_name = record.get('name', f"Record {i+1}")
                flowables.append(Paragraph(f"Order: {order_name}", heading_style))
                
                # Order details
                order_info = []
                if 'partner_id' in record:
                    partner = record['partner_id']
                    partner_name = partner[1] if isinstance(partner, list) and len(partner) > 1 else str(partner)
                    order_info.append(f"Customer: {partner_name}")
                
                if 'amount_total' in record:
                    order_info.append(f"Total Amount: ${record.get('amount_total', 0):.2f}")
                
                if 'state' in record:
                    order_info.append(f"Status: {record.get('state', 'N/A').title()}")
                
                if order_info:
                    flowables.append(Paragraph(" | ".join(order_info), normal_style))
                
                # Products table
                products = record.get('products', [])
                if products:
                    flowables.append(Spacer(1, 10))
                    flowables.append(Paragraph("Products:", normal_style))
                    
                    # Create products table with proper column widths
                    table_data = [['Product', 'Qty', 'Unit Price', 'Subtotal']]
                    
                    for product in products:
                        product_name = self._get_product_name(product)
                        qty = product.get('product_uom_qty', 0)
                        price = product.get('price_unit', 0)
                        subtotal = product.get('price_subtotal', qty * price)
                        
                        table_data.append([
                            Paragraph(product_name, small_style),
                            f"{qty:.1f}",
                            f"${price:.2f}",
                            f"${subtotal:.2f}"
                        ])
                    
                    # Calculate column widths based on content
                    col_widths = [4*inch, 0.8*inch, 1*inch, 1*inch]
                    
                    table = Table(table_data, colWidths=col_widths)
                    table.setStyle(TableStyle([
                        ('BACKGROUND', (0, 0), (-1, 0), colors.lightblue),
                        ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
                        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                        ('ALIGN', (1, 0), (-1, -1), 'RIGHT'),  # Numbers right-aligned
                        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                        ('FONTSIZE', (0, 0), (-1, -1), 9),
                        ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
                        ('BACKGROUND', (0, 1), (-1, -1), colors.lightyellow),
                        ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
                        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                    ]))
                    flowables.append(table)
                    
            elif 'order_name' in record:
                # Specific order products (from queries like "products in S00014")
                if i == 0:
                    order_name = record.get('order_name', 'Unknown Order')
                    flowables.append(Paragraph(f"Products in Order: {order_name}", heading_style))
                    flowables.append(Spacer(1, 10))
                    
                    # Create header for products table
                    table_data = [['Product', 'Description', 'Qty', 'Unit Price', 'Subtotal']]
                
                product_name = self._get_product_name(record)
                description = record.get('name', '')
                qty = record.get('product_uom_qty', 0)
                price = record.get('price_unit', 0)
                subtotal = record.get('price_subtotal', qty * price)
                
                if i == 0:
                    # Start the table data
                    self._current_table_data = table_data
                
                self._current_table_data.append([
                    Paragraph(product_name, small_style),
                    Paragraph(description[:50] + "..." if len(description) > 50 else description, small_style),
                    f"{qty:.1f}",
                    f"${price:.2f}",
                    f"${subtotal:.2f}"
                ])
        
        # If we were building a products table, add it now
        if hasattr(self, '_current_table_data') and len(self._current_table_data) > 1:
            col_widths = [2*inch, 2.5*inch, 0.8*inch, 1*inch, 1*inch]
            
            table = Table(self._current_table_data, colWidths=col_widths)
            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.lightblue),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('ALIGN', (2, 0), (-1, -1), 'RIGHT'),  # Numbers right-aligned
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 9),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
                ('BACKGROUND', (0, 1), (-1, -1), colors.lightyellow),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ]))
            flowables.append(table)
            delattr(self, '_current_table_data')
        
        return flowables
    
    def _get_product_name(self, product_record: dict) -> str:
        """Extract product name from various product record formats"""
        if 'product_id' in product_record:
            product_id = product_record['product_id']
            if isinstance(product_id, list) and len(product_id) > 1:
                return product_id[1]  # [id, name] format
            elif isinstance(product_id, str):
                return product_id
        
        return product_record.get('name', 'Unknown Product')
    
    def _format_tabular_data(self, data: list, heading_style, normal_style) -> list:
        """Format simple tabular data with proper text wrapping"""
        flowables = []
        
        if not data:
            return flowables
        
        # Convert to DataFrame for easier handling
        df = pd.DataFrame(data)
        
        # Clean up column names
        df.columns = [self._clean_column_name(col) for col in df.columns]
        
        flowables.append(Paragraph("Data Report", heading_style))
        flowables.append(Spacer(1, 10))
        
        # Calculate optimal column widths
        available_width = 7*inch  # Total available width
        num_cols = len(df.columns)
        
        # Analyze content to determine column widths
        col_widths = self._calculate_column_widths(df, available_width)
        
        # Prepare table data with text wrapping
        table_data = []
        
        # Headers - use simple strings to avoid Paragraph issues
        headers = [str(col) for col in df.columns]
        table_data.append(headers)
        
        # Data rows with text wrapping
        for _, row in df.iterrows():
            wrapped_row = []
            for col_name in df.columns:
                # Safe handling of cell values, including lists and arrays
                cell_raw = row[col_name]
                
                # Handle different data types safely
                if cell_raw is None or cell_raw is pd.NA:
                    cell_value = ""
                elif isinstance(cell_raw, (list, tuple)):
                    # Handle Odoo-style [id, name] pairs
                    if len(cell_raw) > 1:
                        cell_value = str(cell_raw[1])  # Use the name part
                    elif len(cell_raw) == 1:
                        cell_value = str(cell_raw[0])
                    else:
                        cell_value = ""
                else:
                    # Convert to string for other types
                    cell_value = str(cell_raw)
                
                # Handle long text with simple truncation for tables
                if len(cell_value) > 80:
                    cell_value = cell_value[:80] + "..."
                
                # Replace newlines with spaces for table cells
                cell_value = cell_value.replace('\n', ' ').replace('\r', ' ')
                
                wrapped_row.append(cell_value)
            
            table_data.append(wrapped_row)
        
        # Create table with calculated widths
        table = Table(table_data, colWidths=col_widths, repeatRows=1)
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.lightblue),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
            ('BACKGROUND', (0, 1), (-1, -1), colors.lightyellow),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ]))
        
        flowables.append(table)
        return flowables
    
    def _clean_column_name(self, col_name: str) -> str:
        """Clean up column names for better display"""
        # Replace underscores with spaces and title case
        cleaned = str(col_name).replace('_', ' ').title()
        
        # Handle special cases
        replacements = {
            'Id': 'ID',
            'Uom': 'UOM',
            'Qty': 'Quantity',
            'Product Id': 'Product',
            'Partner Id': 'Customer',
            'Order Id': 'Order'
        }
        
        for old, new in replacements.items():
            cleaned = cleaned.replace(old, new)
        
        return cleaned
    
    def _calculate_column_widths(self, df: pd.DataFrame, available_width: float) -> list:
        """Calculate optimal column widths based on content with safety limits"""
        num_cols = len(df.columns)
        min_width = 1.0  # Minimum column width in inches
        max_width = 3.0  # Maximum column width in inches
        
        if num_cols == 0:
            return []
        
        # For many columns, use equal width distribution
        if num_cols > 6:
            equal_width = max(min_width, available_width / num_cols)
            return [min(equal_width, max_width)] * num_cols
        
        # Analyze content length for each column
        col_scores = []
        for col in df.columns:
            # Consider header length and average content length (not max to avoid outliers)
            header_len = len(str(col))
            if not df.empty:
                # Safe content length calculation that handles lists
                content_lengths = []
                for value in df[col]:
                    if value is None or value is pd.NA:
                        content_lengths.append(0)
                    elif isinstance(value, (list, tuple)):
                        # For lists, use the name part length
                        if len(value) > 1:
                            content_lengths.append(len(str(value[1])))
                        elif len(value) == 1:
                            content_lengths.append(len(str(value[0])))
                        else:
                            content_lengths.append(0)
                    else:
                        content_lengths.append(len(str(value)))
                
                avg_content_len = sum(content_lengths) / len(content_lengths) if content_lengths else 10
                # Use average but cap it to prevent extreme values
                content_score = min(avg_content_len, 40)
            else:
                content_score = 10
            
            # Score based on content characteristics
            score = max(header_len, content_score)
            col_scores.append(score)
        
        # Normalize scores to available width
        total_score = sum(col_scores)
        if total_score == 0:
            return [available_width / num_cols] * num_cols
        
        col_widths = []
        allocated_width = 0
        
        for i, score in enumerate(col_scores):
            if i == len(col_scores) - 1:  # Last column gets remaining width
                width = max(min_width, available_width - allocated_width)
            else:
                width = max(min_width, (score / total_score) * available_width)
                width = min(width, max_width)  # Cap at max width
                allocated_width += width
            
            col_widths.append(width)
        
        return col_widths
    
    def _wrap_text(self, text: str, max_length: int) -> str:
        """Wrap long text for better display with safety limits"""
        if not text or len(text) <= max_length:
            return str(text)
        
        # Truncate extremely long text to prevent issues
        if len(text) > 500:
            text = text[:500] + "..."
        
        # Try to break at word boundaries
        words = text.split()
        lines = []
        current_line = []
        current_length = 0
        max_lines = 5  # Limit number of lines to prevent huge cells
        
        for word in words:
            # If we've reached max lines, stop
            if len(lines) >= max_lines:
                if current_line:
                    current_line.append("...")
                    lines.append(' '.join(current_line))
                break
                
            if current_length + len(word) + 1 <= max_length:
                current_line.append(word)
                current_length += len(word) + 1
            else:
                if current_line:
                    lines.append(' '.join(current_line))
                # Handle very long single words
                if len(word) > max_length:
                    word = word[:max_length-3] + "..."
                current_line = [word]
                current_length = len(word)
        
        if current_line and len(lines) < max_lines:
            lines.append(' '.join(current_line))
        
        return '<br/>'.join(lines)
    
    def _generate_simple_pdf_fallback(self, data: list, title: str, filepath: Path) -> str:
        """Fallback to simple PDF generation with proper table formatting"""
        try:
            buffer = io.BytesIO()
            doc = SimpleDocTemplate(buffer, pagesize=A4, 
                                  rightMargin=0.5*inch, leftMargin=0.5*inch,
                                  topMargin=0.75*inch, bottomMargin=0.75*inch)
            styles = getSampleStyleSheet()
            flowables = []

            flowables.append(Paragraph(title, styles['Title']))
            flowables.append(Spacer(1, 12))
            flowables.append(Paragraph(f"Data contains {len(data)} records", styles['Normal']))
            flowables.append(Spacer(1, 12))
            
            if not data:
                flowables.append(Paragraph("No data to display.", styles['Normal']))
            else:
                # Create a simple table from the data
                df = pd.DataFrame(data)
                
                # Prepare table data with safe string conversion
                table_data = []
                
                # Headers
                headers = [self._clean_column_name(str(col)) for col in df.columns]
                table_data.append(headers)
                
                # Data rows with safe conversion
                for _, row in df.iterrows():
                    row_data = []
                    for col_name in df.columns:
                        cell_raw = row[col_name]
                        
                        # Safe conversion of various data types
                        if cell_raw is None or cell_raw is pd.NA:
                            cell_value = ""
                        elif isinstance(cell_raw, (list, tuple)):
                            # Handle Odoo-style [id, name] pairs
                            if len(cell_raw) > 1:
                                cell_value = str(cell_raw[1])  # Use the name part
                            elif len(cell_raw) == 1:
                                cell_value = str(cell_raw[0])
                            else:
                                cell_value = ""
                        else:
                            cell_value = str(cell_raw)
                        
                        # Truncate long content
                        if len(cell_value) > 30:
                            cell_value = cell_value[:30] + "..."
                        
                        # Clean up formatting
                        cell_value = cell_value.replace('\n', ' ').replace('\r', ' ')
                        row_data.append(cell_value)
                    
                    table_data.append(row_data)
                
                # Calculate simple column widths
                num_cols = len(headers)
                available_width = 7*inch
                if num_cols > 0:
                    col_width = available_width / num_cols
                    col_widths = [col_width] * num_cols
                else:
                    col_widths = None
                
                # Create table
                table = Table(table_data, colWidths=col_widths, repeatRows=1)
                table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                    ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, -1), 9),
                    ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
                    ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                    ('GRID', (0, 0), (-1, -1), 1, colors.black),
                    ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ]))
                
                flowables.append(table)
                
                if len(data) > 50:
                    flowables.append(Spacer(1, 12))
                    flowables.append(Paragraph(f"Showing first 50 of {len(data)} records", styles['Normal']))

            doc.build(flowables)
            buffer.seek(0)

            with open(filepath, "wb") as f:
                f.write(buffer.read())

            buffer.close()
            return f"Simple PDF generated and saved as '{filepath.name}'"
            
        except Exception as e:
            return f"Error in fallback PDF generation: {str(e)}"
    
    # LangChain compatibility methods
    def get(self, key, default=None):
        """LangChain compatibility method"""
        return getattr(self, key, default)
    
    def __getitem__(self, key):
        """LangChain compatibility method"""
        return getattr(self, key)
    
    def __contains__(self, key):
        """LangChain compatibility method"""
        return hasattr(self, key)


# =========================
# TOOL 3: Generate Chart
# =========================
class ChartInput(BaseModel):
    data_json: str = Field(..., description="JSON string of data")
    chart_type: str = Field(..., description="bar, line, pie, scatter")
    x_field: Optional[str] = Field(None, description="X-axis field")
    y_field: Optional[str] = Field(None, description="Y-axis numeric field")
    category_field: Optional[str] = Field(None, description="Grouping field")
    title: str = Field(..., description="Chart title")
    filename: str = Field(..., description="Output filename, e.g., chart.png")

class ChartTool:
    """Custom chart tool that implements LangChain tool interface"""
    
    def __init__(self, session_id: str):
        self.name = "generate_chart"
        self.description = "Generates a chart and saves it to disk as PNG."
        self.args_schema = ChartInput
        self.args = {
            "data_json": "string",
            "chart_type": "string",
            "x_field": "string",
            "y_field": "string", 
            "category_field": "string",
            "title": "string",
            "filename": "string"
        }
        self.session_id = session_id
        self.file_storage_path = "reports/"
    
    def _run(self, data_json: str, chart_type: str, title: str,
             x_field: str = None, y_field: str = None, category_field: str = None,
             filename: str = "chart.html") -> str:
        try:
            data = json.loads(data_json)
            df = pd.DataFrame(data)
            
            logger.info(f"Chart generation - Data shape: {df.shape}, Columns: {list(df.columns)}")
            logger.info(f"Chart generation - Requested fields: X={x_field}, Y={y_field}, Category={category_field}")

            # Create session-specific directory using absolute path
            base_path = Path(__file__).parent.parent  # Go up from services/ to project root
            session_dir = base_path / self.file_storage_path / self.session_id
            session_dir.mkdir(parents=True, exist_ok=True)
            
            filepath = session_dir / filename

            # Validate that requested fields exist in the data
            available_columns = list(df.columns)
            missing_fields = []
            
            if x_field and x_field not in available_columns:
                missing_fields.append(x_field)
            if y_field and y_field not in available_columns:
                missing_fields.append(y_field)
            if category_field and category_field not in available_columns:
                missing_fields.append(category_field)
            
            if missing_fields:
                return f"Error generating chart: Column(s) not found: {', '.join(missing_fields)}. Available columns: {available_columns}"

            # If grouped chart, ensure sum
            if chart_type in ["bar", "pie"] and x_field and y_field:
                if df[x_field].dtype == 'object' and y_field:
                    df = df.groupby(x_field)[y_field].sum().reset_index()

            fig = None
            if chart_type == "bar" and x_field and y_field:
                fig = px.bar(df, x=x_field, y=y_field, color=category_field, title=title,
                            hover_data=[x_field, y_field], text=y_field)
            elif chart_type == "pie" and y_field and x_field:
                fig = px.pie(df, names=x_field, values=y_field, title=title,
                           hover_data=[x_field, y_field])
            elif chart_type == "line" and x_field and y_field:
                fig = px.line(df, x=x_field, y=y_field, title=title,
                            hover_data=[x_field, y_field])
            elif chart_type == "scatter" and x_field and y_field:
                fig = px.scatter(df, x=x_field, y=y_field, color=category_field, title=title,
                               hover_data=[x_field, y_field])
            else:
                return f"Invalid chart configuration. Required fields for {chart_type} chart: X={x_field}, Y={y_field}"

            # Update layout for better interactivity
            fig.update_layout(
                title=title,
                xaxis_title=x_field,
                yaxis_title=y_field,
                hovermode='closest',
                showlegend=True,
                height=500,
                width=800
            )

            # Save as interactive HTML
            fig.write_html(str(filepath), include_plotlyjs=True, full_html=False)
            logger.info(f"✅ Interactive HTML chart saved: {filepath}")
            
            # Read the HTML content to return it for direct display
            with open(filepath, 'r', encoding='utf-8') as f:
                html_content = f.read()
            
            return f"Interactive chart successfully generated and saved as '{filename}'. HTML content ready for display."
            
        except Exception as e:
            logger.error(f"Chart generation error: {str(e)}")
            return f"Error generating chart: {str(e)}"
    
    # LangChain compatibility methods
    def get(self, key, default=None):
        """LangChain compatibility method"""
        return getattr(self, key, default)
    
    def __getitem__(self, key):
        """LangChain compatibility method"""
        return getattr(self, key)
    
    def __contains__(self, key):
        """LangChain compatibility method"""
        return hasattr(self, key)


# =========================
# TOOL 3: Generate CSV
# =========================
class CSVExportInput(BaseModel):
    data_json: str = Field(..., description="JSON string of data")
    filename: str = Field(..., description="e.g., sales_data.csv")

class CSVExportTool:
    """CSV export tool that implements LangChain tool interface"""
    
    def __init__(self, session_id: str):
        self.name = "generate_csv_export"
        self.description = "Generates a CSV file and saves it to disk."
        self.args_schema = CSVExportInput
        self.args = {
            "data_json": "string",
            "filename": "string"
        }
        self.session_id = session_id
        self.file_storage_path = "reports/"
    
    def _run(self, data_json: str, filename: str) -> str:
        try:
            data = json.loads(data_json)
            
            # Create session-specific directory using absolute path
            base_path = Path(__file__).parent.parent  # Go up from services/ to project root
            session_dir = base_path / self.file_storage_path / self.session_id
            session_dir.mkdir(parents=True, exist_ok=True)
            
            filepath = session_dir / filename
            
            if not data:
                # Create empty CSV with header
                with open(filepath, 'w', newline='', encoding='utf-8') as csvfile:
                    writer = csv.writer(csvfile)
                    writer.writerow(["No data available"])
                logger.info(f"✅ Empty CSV saved: {filepath}")
                return f"CSV file successfully generated (no data) and saved as '{filename}'"
            
            # Convert to DataFrame for easier CSV handling
            df = pd.DataFrame(data)
            
            # Clean up data for CSV export
            df_cleaned = df.copy()
            
            # Handle Odoo-style [id, name] pairs
            for col in df_cleaned.columns:
                df_cleaned[col] = df_cleaned[col].apply(self._clean_cell_value)
            
            # Clean column names
            df_cleaned.columns = [self._clean_column_name(col) for col in df_cleaned.columns]
            
            # Export to CSV
            df_cleaned.to_csv(filepath, index=False, encoding='utf-8')
            
            logger.info(f"✅ CSV saved: {filepath}")
            return f"CSV file successfully generated and saved as '{filename}'"
            
        except Exception as e:
            logger.error(f"Error generating CSV: {str(e)}")
            return f"Error generating CSV: {str(e)}"
    
    def _clean_cell_value(self, value):
        """Clean cell values for CSV export"""
        if value is None or value is pd.NA:
            return ""
        elif isinstance(value, (list, tuple)):
            # Handle Odoo-style [id, name] pairs
            if len(value) > 1:
                return str(value[1])  # Use the name part
            elif len(value) == 1:
                return str(value[0])
            else:
                return ""
        else:
            # Convert to string and clean
            str_value = str(value)
            # Remove newlines and carriage returns
            str_value = str_value.replace('\n', ' ').replace('\r', ' ')
            return str_value
    
    def _clean_column_name(self, col_name: str) -> str:
        """Clean up column names for CSV headers"""
        # Replace underscores with spaces and title case
        cleaned = str(col_name).replace('_', ' ').title()
        
        # Handle special cases
        replacements = {
            'Id': 'ID',
            'Uom': 'UOM',
            'Qty': 'Quantity',
            'Product Id': 'Product',
            'Partner Id': 'Customer',
            'Order Id': 'Order'
        }
        
        for old, new in replacements.items():
            cleaned = cleaned.replace(old, new)
        
        return cleaned
    
    def _format_data_as_text(self, data: List[Dict], query: str) -> str:
        """Format data as a well-structured text response"""
        try:
            if not data:
                return "No data found for your query."
            
            # Create a summary header
            total_records = len(data)
            response_lines = []
            response_lines.append(f"📊 **Sales Report Results**")
            response_lines.append(f"Found {total_records} record(s)\n")
            
            # Convert to DataFrame for easier processing
            df = pd.DataFrame(data)
            
            # Generate summary statistics if numeric columns exist
            numeric_cols = df.select_dtypes(include=['number']).columns
            if len(numeric_cols) > 0:
                response_lines.append("📈 **Summary Statistics:**")
                for col in numeric_cols:
                    if 'total' in col.lower() or 'amount' in col.lower() or 'price' in col.lower():
                        total_val = df[col].sum()
                        avg_val = df[col].mean()
                        response_lines.append(f"• {self._clean_column_name(col)}: Total = {total_val:,.2f}, Average = {avg_val:,.2f}")
                response_lines.append("")
            
            # Show detailed records (limit to first 10 for readability)
            response_lines.append("📋 **Detailed Records:**")
            display_limit = min(10, total_records)
            
            for i, record in enumerate(data[:display_limit]):
                response_lines.append(f"\n**Record {i+1}:**")
                for key, value in record.items():
                    clean_key = self._clean_column_name(key)
                    clean_value = self._clean_cell_value(value)
                    if clean_value:  # Only show non-empty values
                        response_lines.append(f"• {clean_key}: {clean_value}")
            
            if total_records > display_limit:
                response_lines.append(f"\n... and {total_records - display_limit} more records")
                response_lines.append("\n💡 *Tip: Use 'generate PDF' or 'export to Excel' to get the complete dataset*")
            
            return "\n".join(response_lines)
            
        except Exception as e:
            logger.error(f"Error formatting data as text: {str(e)}")
            return f"Data retrieved successfully, but formatting failed. Found {len(data) if data else 0} records. Use 'generate PDF' for a formatted report."
    
    # LangChain compatibility methods
    def get(self, key, default=None):
        """LangChain compatibility method"""
        return getattr(self, key, default)
    
    def __getitem__(self, key):
        """LangChain compatibility method"""
        return getattr(self, key)
    
    def __contains__(self, key):
        """LangChain compatibility method"""
        return hasattr(self, key)


# =========================
# TOOL 4: Generate Excel
# =========================
class ExcelExportInput(BaseModel):
    data_json: str = Field(..., description="JSON string of data")
    filename: str = Field(..., description="e.g., sales_data.xlsx")

class ExcelExportTool:
    """Excel export tool that implements LangChain tool interface"""
    
    def __init__(self, session_id: str):
        self.name = "generate_excel_export"
        self.description = "Generates an Excel (.xlsx) file and saves it to disk."
        self.args_schema = ExcelExportInput
        self.args = {
            "data_json": "string",
            "filename": "string"
        }
        self.session_id = session_id
        self.file_storage_path = "reports/"
    
    def _run(self, data_json: str, filename: str) -> str:
        try:
            data = json.loads(data_json)
            
            # Create session-specific directory using absolute path
            base_path = Path(__file__).parent.parent  # Go up from services/ to project root
            session_dir = base_path / self.file_storage_path / self.session_id
            session_dir.mkdir(parents=True, exist_ok=True)
            
            filepath = session_dir / filename
            
            if not data:
                # Create empty Excel with header
                df_empty = pd.DataFrame({"No data available": [""]})
                df_empty.to_excel(filepath, index=False, engine='openpyxl' if EXCEL_AVAILABLE else None)
                logger.info(f"✅ Empty Excel saved: {filepath}")
                return f"Excel file successfully generated (no data) and saved as '{filename}'"
            
            # Convert to DataFrame for easier Excel handling
            df = pd.DataFrame(data)
            
            # Clean up data for Excel export
            df_cleaned = df.copy()
            
            # Handle Odoo-style [id, name] pairs and other data types
            for col in df_cleaned.columns:
                df_cleaned[col] = df_cleaned[col].apply(self._clean_cell_value)
            
            # Clean column names
            df_cleaned.columns = [self._clean_column_name(col) for col in df_cleaned.columns]
            
            if EXCEL_AVAILABLE:
                # Use openpyxl for enhanced Excel export with formatting
                with pd.ExcelWriter(filepath, engine='openpyxl') as writer:
                    df_cleaned.to_excel(writer, sheet_name='Data', index=False)
                    
                    # Get the worksheet for formatting
                    worksheet = writer.sheets['Data']
                    
                    # Format headers
                    for cell in worksheet[1]:  # First row (headers)
                        cell.font = openpyxl.styles.Font(bold=True)
                        cell.fill = openpyxl.styles.PatternFill(start_color="CCCCCC", end_color="CCCCCC", fill_type="solid")
                    
                    # Auto-adjust column widths
                    for column in worksheet.columns:
                        max_length = 0
                        column_letter = column[0].column_letter
                        for cell in column:
                            try:
                                if len(str(cell.value)) > max_length:
                                    max_length = len(str(cell.value))
                            except:
                                pass
                        adjusted_width = min(max_length + 2, 50)  # Cap at 50 characters
                        worksheet.column_dimensions[column_letter].width = adjusted_width
            else:
                # Fallback to basic Excel export
                df_cleaned.to_excel(filepath, index=False)
            
            logger.info(f"✅ Excel saved: {filepath}")
            return f"Excel file successfully generated and saved as '{filename}'"
            
        except Exception as e:
            logger.error(f"Error generating Excel: {str(e)}")
            return f"Error generating Excel: {str(e)}"
    
    def _clean_cell_value(self, value):
        """Clean cell values for Excel export"""
        if value is None or value is pd.NA:
            return ""
        elif isinstance(value, (list, tuple)):
            # Handle Odoo-style [id, name] pairs
            if len(value) > 1:
                return str(value[1])  # Use the name part
            elif len(value) == 1:
                return str(value[0])
            else:
                return ""
        else:
            # Convert to string and clean
            str_value = str(value)
            # Remove problematic characters for Excel
            str_value = str_value.replace('\n', ' ').replace('\r', ' ')
            return str_value
    
    def _clean_column_name(self, col_name: str) -> str:
        """Clean up column names for Excel headers"""
        # Replace underscores with spaces and title case
        cleaned = str(col_name).replace('_', ' ').title()
        
        # Handle special cases
        replacements = {
            'Id': 'ID',
            'Uom': 'UOM', 
            'Qty': 'Quantity',
            'Product Id': 'Product',
            'Partner Id': 'Customer',
            'Order Id': 'Order'
        }
        
        for old, new in replacements.items():
            cleaned = cleaned.replace(old, new)
        
        return cleaned
    
    # LangChain compatibility methods
    def get(self, key, default=None):
        """LangChain compatibility method"""
        return getattr(self, key, default)
    
    def __getitem__(self, key):
        """LangChain compatibility method"""
        return getattr(self, key)
    
    def __contains__(self, key):
        """LangChain compatibility method"""
        return hasattr(self, key)


# Global instance
dynamic_reporting_agent_service = DynamicReportingAgentService()