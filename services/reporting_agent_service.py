#!/usr/bin/env python3
"""
Reporting Agent Service
======================
AutoGen-based agent for Odoo CRUD operations, report generation, and chart creation.
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

from autogen import AssistantAgent, UserProxyAgent
from google import genai
from google.genai import types

# Load environment variables from .env file
load_dotenv('rag_config_enhanced.env')

logger = logging.getLogger(__name__)

class ReportingAgentService:
    """
    Dedicated service for AutoGen-based reporting and CRUD operations.
    Handles dynamic credentials, file generation, and chat integration.
    """
    
    def __init__(self):
        self.autogen_agent = None
        self.credentials_cache = {}
        self.file_storage_path = "reports/"
        self.gemini_client = None
        self._ensure_storage_path()
        
    def _ensure_storage_path(self):
        """Ensure the file storage directory exists"""
        Path(self.file_storage_path).mkdir(parents=True, exist_ok=True)
        
    def initialize_agent(self, credentials: Dict[str, str], session_id: str) -> bool:
        """
        Initialize AutoGen agent with user credentials
        
        Args:
            credentials: Odoo connection credentials
            session_id: Session identifier for caching
            
        Returns:
            bool: True if initialization successful
        """
        try:
            # Cache credentials for this session
            self.credentials_cache[session_id] = credentials
            
            # Initialize Gemini client
            google_api_key = os.getenv("GOOGLE_API_KEY")
            if not google_api_key:
                logger.error("GOOGLE_API_KEY not found in environment. Please check your .env file.")
                logger.error("Available environment variables: " + str([k for k in os.environ.keys() if 'GOOGLE' in k or 'API' in k]))
                return False
            
            logger.info(f"Using Google API key: {google_api_key[:10]}...")
                
            self.gemini_client = genai.Client(api_key=google_api_key)
            
            # Create Odoo XML-RPC preamble
            odoo_preamble = self._create_odoo_preamble(credentials)
            
            # Configure LLM
            llm_config = {
                "config_list": [{
                    "model": "gemini-2.5-flash",
                    "api_key": google_api_key,
                    "api_type": "google"
                }],
                "temperature": 0,
            }
            
            # Create AutoGen agents
            self.autogen_agent = AssistantAgent(
                name="OdooReportingAgent",
                llm_config=llm_config,
                system_message=(
                    "You are an Odoo CRUD & reporting assistant.\n"
                    "You can:\n"
                    "  - Query / create / update / delete any Odoo record via XML-RPC.\n"
                    "  - Create **PDF reports** with ReportLab when the user asks for a PDF.\n"
                    "  - Generate **interactive graphs** with Plotly when the user asks for charts.\n"
                    + odoo_preamble +
                    "\n\nIMPORTANT INSTRUCTIONS:\n"
                    "1. ALWAYS wrap executable code in ```python ... ``` blocks.\n"
                    "2. If you need shell commands (e.g. pip install), use ```bash ... ``` blocks.\n"
                    "3. If the user wants a PDF report:\n"
                    "   - pip install reportlab if needed.\n"
                    "   - Use reportlab.pdfgen.canvas or reportlab.platypus to build the PDF.\n"
                    "   - Save the file as 'report_<timestamp>.pdf' in the working directory.\n"
                    "   - Print the path of the generated file so the user can download it.\n"
                    "4. If the user wants a graph:\n"
                    "   - pip install plotly pandas kaleido if needed.\n"
                    "   - Use plotly.graph_objects or plotly.express.\n"
                    "   - Save as PNG image to 'chart_<timestamp>.png' using fig.write_image().\n"
                    "   - For JPG format, save to 'chart_<timestamp>.jpg'.\n"
                    "   - Print the path of the generated image file.\n"
                    "5. Do NOT print the password.\n"
                    "6. Always return a JSON response with 'content' and 'files' fields.\n"
                    "7. IMPORTANT: The Odoo connection variables (url, db, user, pwd, models, uid) are already defined in the preamble.\n"
                    "8. IMPORTANT: Always check if required libraries are installed before using them.\n"
                    "9. IMPORTANT: Handle errors gracefully and provide meaningful error messages.\n"
                ),
            )
            
            self.reporting_proxy = UserProxyAgent(
                name="Reporting_Proxy",
                human_input_mode="NEVER",
                max_consecutive_auto_reply=5,
                code_execution_config={
                    "work_dir": self.file_storage_path,
                    "use_docker": False,
                    "timeout": 90,  # 90 second timeout
                    "last_n_messages": 10,
                },
            )
            
            logger.info(f"Reporting agent initialized successfully for session {session_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize reporting agent: {str(e)}")
            return False
    
    def _create_odoo_preamble(self, credentials: Dict[str, str]) -> str:
        """Create Odoo XML-RPC connection preamble"""
        return f"""
import xmlrpc.client, datetime, json
url   = "{credentials.get('url', '')}"
db    = "{credentials.get('db', '')}"
user  = "{credentials.get('user', '')}"
pwd   = "{credentials.get('password', '')}"

common = xmlrpc.client.ServerProxy(f'{{url}}/xmlrpc/2/common')
models = xmlrpc.client.ServerProxy(f'{{url}}/xmlrpc/2/object')
uid    = common.authenticate(db, user, pwd, {{}})
"""
    
    def generate_report(self, query: str, session_id: str, 
                       report_type: str = "auto") -> Dict[str, Any]:
        """
        Generate reports using AutoGen agent
        
        Args:
            query: User's report request
            session_id: Session identifier
            report_type: Type of report to generate
            
        Returns:
            Dict containing response and generated files
        """
        try:
            # Check if agent is initialized for this session
            if session_id not in self.credentials_cache:
                return {
                    "success": False,
                    "error": "Agent not initialized for this session. Please provide credentials first.",
                    "response": "Please provide your Odoo credentials to use the reporting agent."
                }
            
            if not self.autogen_agent:
                return {
                    "success": False,
                    "error": "Reporting agent not properly initialized",
                    "response": "Reporting agent is not available."
                }
            
            # Use enhanced AutoGen agent
            from services.enhanced_autogen_agent import EnhancedAutoGenAgent
            
            credentials = self.credentials_cache[session_id]
            enhanced_agent = EnhancedAutoGenAgent(credentials, session_id)
            
            # Execute the query through enhanced agent
            result = enhanced_agent.execute_query(query)
            result["agent_type"] = "reporting_agent"
            
            return result
            
        except Exception as e:
            logger.error(f"Error in report generation: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "response": f"Error generating report: {str(e)}",
                "session_id": session_id
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
    
    def _get_generated_files(self, session_id: str) -> List[Dict[str, str]]:
        """Get list of generated files for the session"""
        try:
            session_path = Path(self.file_storage_path) / session_id
            if not session_path.exists():
                return []
            
            files = []
            for file_path in session_path.glob("*"):
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
    
    def get_file_download_url(self, filename: str, session_id: str) -> str:
        """Generate download URL for a file"""
        return f"/api/reporting/download/{session_id}/{filename}"
    
    def cleanup_session_files(self, session_id: str) -> bool:
        """Clean up files for a specific session"""
        try:
            session_path = Path(self.file_storage_path) / session_id
            if session_path.exists():
                shutil.rmtree(session_path)
            return True
        except Exception as e:
            logger.error(f"Error cleaning up session files: {str(e)}")
            return False
    
    def health_check(self) -> Dict[str, Any]:
        """Check the health of the reporting agent service"""
        return {
            "status": "healthy" if self.autogen_agent else "unhealthy",
            "agent_initialized": self.autogen_agent is not None,
            "gemini_available": self.gemini_client is not None,
            "storage_path": self.file_storage_path,
            "active_sessions": len(self.credentials_cache)
        }

# Global instance
reporting_agent_service = ReportingAgentService() 