#!/usr/bin/env python3
"""
Enhanced Agent Service
=====================
Coordinates between main agent, dynamic reporting agent, and dynamic CRUD agent.
Handles routing, credential management, and response formatting.
"""

import logging
import os
import re
from typing import Dict, Any, Optional, List
from datetime import datetime
import uuid
import importlib

import services.dynamic_reporting_agent_service
from services.agent_service import agent_service
from services.dynamic_reporting_agent_service import DynamicReportingAgentService
from services.dynamic_crud_agent_service import dynamic_crud_agent_service

logger = logging.getLogger(__name__)

class EnhancedAgentService:
    """
    Enhanced service that coordinates between main agent, dynamic reporting agent, 
    and dynamic CRUD agent. Handles intelligent routing and credential management.
    """
    
    def __init__(self):
        self.main_agent = agent_service
        importlib.reload(services.dynamic_reporting_agent_service)
        self.dynamic_reporting_agent = services.dynamic_reporting_agent_service.DynamicReportingAgentService()

    def chat(self, message: str, session_id: str, user_id: int = None) -> Dict[str, Any]:
        """
        Process chat message through appropriate agent
        
        Args:
            message: User message
            session_id: Session identifier
            user_id: User identifier (optional)
            
        Returns:
            Dict containing response and metadata
        """
        try:
            # Determine which agent to use
            agent_type = self._determine_agent_type(message)
            logger.info(f"Routing message to {agent_type} agent: '{message[:50]}...'")
            
            if agent_type == "dynamic_crud_agent":
                return self._handle_dynamic_crud_agent(message, session_id, user_id)
            elif agent_type == "dynamic_reporting_agent":
                return self._handle_dynamic_reporting_agent(message, session_id, user_id)
            else:
                return self._handle_main_agent(message, session_id, user_id)
                
        except Exception as e:
            logger.error(f"Error in enhanced agent service: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "agent_type": "enhanced_agent"
            }
    
    def _determine_agent_type(self, message: str) -> str:
        """
        Determine which agent should handle the message
        
        Priority:
        1. Dynamic Reporting Agent - for reports, charts, PDFs, visualizations
        2. Main Agent - for navigation, shortcuts, document processing, QA/documentation
        3. Dynamic CRUD Agent - for data lookup, create, update, delete operations
        
        Args:
            message: User message
            
        Returns:
            str: Agent type ("dynamic_crud_agent", "dynamic_reporting_agent", or "main_agent")
        """
        message_lower = message.lower()
        
        # Check for reporting/charting needs FIRST (highest priority)
        # Only route to reporting agent if specific format is requested (PDF, Excel, Charts, etc.)
        reporting_keywords = [
            'pdf report', 'export report', 'generate pdf', 'create pdf', 'pdf reoort', 'generate reoort', # Added typo variants
            'generate graph', 'create graph', 'generate chart', 'create chart',
            'generate a graph', 'create a graph', 'generate a chart', 'create a chart',
            'bar chart', 'line chart', 'pie chart', 'scatter plot', 'bar graph',
            'visualization', 'visualize', 'plot', 'diagram', 'graph', 'chart',
            'export to pdf', 'export data to pdf', 'export sales data to pdf',
            'download report', 'save as pdf', 'print report',
            'dashboard', 'analytics report', 'export to excel', 'generate excel', 'create excel',
            'generate csv', 'create csv', 'export to csv', 'export csv', 'csv file',
            'excel file', 'xlsx file', 'spreadsheet', 'generate spreadsheet', 'excel sheet',
            'export data', 'download data', 'export as csv', 'export as excel',
            # Excel and chart generation patterns - HIGHEST PRIORITY
            'excel sheet of', 'excel sheet', 'generate a excel', 'create a excel',
            'bar graph showing', 'line graph showing', 'pie chart showing',
            'chart showing', 'graph showing', 'trends by month', 'monthly trends'
        ]
        
        for keyword in reporting_keywords:
            if keyword in message_lower:
                logger.info(f"Routing to dynamic reporting agent - keyword '{keyword}' found in message")
                return "dynamic_reporting_agent"
        
        # Check for high-priority reporting patterns (Excel/Chart generation)
        reporting_patterns = [
            r'excel.*sheet', r'generate.*excel', r'create.*excel', r'export.*excel',
            r'bar.*graph', r'line.*graph', r'pie.*chart', r'scatter.*plot',
            r'chart.*showing', r'graph.*showing', r'trends.*by.*month',
            r'monthly.*trends', r'visualization.*of', r'plot.*data'
        ]
        
        for pattern in reporting_patterns:
            if re.search(pattern, message_lower):
                logger.info(f"Routing to dynamic reporting agent - pattern '{pattern}' matched in message")
                return "dynamic_reporting_agent"
        
        # Check for navigation/documentation needs SECOND
        navigation_keywords = [
            'go to', 'navigate to', 'take me to', 'where is', 'how to access',
            'show me the way to', 'open', 'access', 'menu', 'page', 'module'
        ]
        
        documentation_keywords = [
            'how to', 'how do i', 'tutorial', 'guide', 'help', 'explain',
            'what is', 'what does', 'documentation', 'manual', 'instructions',
            'step by step'
        ]
        
        main_agent_keywords = navigation_keywords + documentation_keywords
        
        for keyword in main_agent_keywords:
            if keyword in message_lower:
                logger.info(f"Routing to main agent - keyword '{keyword}' found in message")
                return "main_agent"
        
        # Check for CRUD operations (data operations) - simplified routing
        # Route to CRUD agent for data-related queries AND textual reports
        crud_keywords = [
            'how many', 'count', 'list', 'show', 'find', 'search', 'get', 'retrieve',
            'sales order', 'purchase order', 'customer', 'product', 'invoice',
            'expense', 'lead', 'contact', 'partner', 'employee', 'record',
            # Textual report patterns (without specific format requirements)
            'generate report', 'create report', 'monthly report', 'quarterly report', 
            'annual report', 'sales report', 'monthly sales', 'quarterly sales', 
            'annual sales', 'sales data', 'revenue report', 'sales analysis', 
            'sales summary', 'generate a monthly', 'generate monthly', 'create monthly',
            'sales for', 'report for', 'data for', 'analysis for',
            'headcount breakdown', 'breakdown by department', 'employee report'
        ]
        
        if any(keyword in message_lower for keyword in crud_keywords):
            logger.info(f"Routing to dynamic CRUD agent - data query detected")
            return "dynamic_crud_agent"
        
        # Check for general CRUD patterns that might be missed
        crud_general_patterns = [
            'create', 'add', 'new', 'register', 'insert', 'make',
            'update', 'edit', 'modify', 'change', 'set',
            'delete', 'remove', 'cancel', 'archive',
            'sales order', 'purchase order', 'customer', 'product', 'invoice',
            'expense', 'lead', 'contact', 'partner', 'employee'
        ]
        
        # If message contains both CRUD intent and business entities, likely CRUD
        has_crud_intent = any(word in message_lower for word in ['create', 'add', 'new', 'register', 'update', 'edit', 'modify', 'change', 'set', 'delete', 'remove', 'cancel', 'archive'])
        has_business_entity = any(entity in message_lower for entity in ['sales order', 'purchase order', 'customer', 'product', 'invoice', 'expense', 'lead', 'contact', 'partner', 'employee'])
        
        if has_crud_intent and has_business_entity:
            logger.info(f"Routing to dynamic CRUD agent - CRUD intent with business entity detected")
            return "dynamic_crud_agent"
        
        # Default to main agent for everything else
        logger.info(f"Routing to main agent - no specialized keywords found")
        return "main_agent"
    
    def _handle_dynamic_crud_agent(self, message: str, session_id: str, user_id: int = None) -> Dict[str, Any]:
        """
        Handle message through dynamic CRUD agent
        
        Args:
            message: User message
            session_id: Session identifier
            user_id: User identifier (optional)
            
        Returns:
            Dict containing response and metadata
        """
        try:
            # Get credentials for this session
            credentials = self._get_credentials_from_main_agent(session_id)
            
            if not credentials:
                return {
                    "success": False,
                    "error": "No Odoo credentials found. Please set up your Odoo connection first.",
                    "agent_type": "dynamic_crud_agent"
                }
            
            # Initialize dynamic CRUD agent if not already done
            if not self._is_dynamic_crud_agent_initialized(session_id):
                if not dynamic_crud_agent_service.initialize_agent(credentials, session_id):
                    return {
                        "success": False,
                        "error": "Failed to initialize dynamic CRUD agent",
                        "agent_type": "dynamic_crud_agent"
                    }
            
            # Process query
            result = dynamic_crud_agent_service.process_query(message, session_id)
            result["agent_type"] = "dynamic_crud_agent"
            
            return result
            
        except Exception as e:
            logger.error(f"Error in dynamic CRUD agent: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "agent_type": "dynamic_crud_agent"
            }
    
    def _handle_dynamic_reporting_agent(self, message: str, session_id: str, user_id: int = None) -> Dict[str, Any]:
        """
        Handle message through dynamic reporting agent
        
        Args:
            message: User message
            session_id: Session identifier
            user_id: User identifier (optional)
            
        Returns:
            Dict containing response and metadata
        """
        try:
            # Get credentials for this session
            credentials = self._get_credentials_from_main_agent(session_id)
            
            if not credentials:
                return {
                    "success": False,
                    "error": "No Odoo credentials found. Please set up your Odoo connection first.",
                    "agent_type": "dynamic_reporting_agent"
                }
            
            # Initialize dynamic reporting agent if not already done
            if not self._is_dynamic_reporting_agent_initialized(session_id):
                if not self.dynamic_reporting_agent.initialize_agent(credentials, session_id):
                    return {
                        "success": False,
                        "error": "Failed to initialize dynamic reporting agent",
                        "agent_type": "dynamic_reporting_agent"
                    }
            
            # Generate report
            result = self.dynamic_reporting_agent.generate_report(message, session_id)
            result["agent_type"] = "dynamic_reporting_agent"
            
            return result
            
        except Exception as e:
            logger.error(f"Error in dynamic reporting agent: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "agent_type": "dynamic_reporting_agent"
            }
    
    def _handle_main_agent(self, message: str, session_id: str, user_id: int = None) -> Dict[str, Any]:
        """
        Handle message through main agent
        
        Args:
            message: User message
            session_id: Session identifier
            user_id: User identifier (optional)
            
        Returns:
            Dict containing response and metadata
        """
        try:
            # Use the main agent service
            result = self.main_agent.chat(message, session_id, user_id)
            result["agent_type"] = "main_agent"
            return result
            
        except Exception as e:
            logger.error(f"Error in main agent: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "agent_type": "main_agent"
            }
    
    def _get_credentials_from_main_agent(self, session_id: str) -> Optional[Dict[str, str]]:
        """
        Get Odoo credentials from the main agent's session
        
        Args:
            session_id: Session identifier
            
        Returns:
            Optional[Dict]: Credentials if found, None otherwise
        """
        try:
            # First try to get credentials from the main agent service directly
            if hasattr(self.main_agent, 'get_odoo_credentials'):
                credentials = self.main_agent.get_odoo_credentials(session_id)
                if credentials:
                    logger.info(f"Retrieved credentials from main agent for session {session_id}")
                    # Add gemini API key from environment if not present
                    if 'gemini_api_key' not in credentials:
                        import os
                        credentials['gemini_api_key'] = os.getenv('GEMINI_API_KEY')
                    return credentials
            
            # Fallback: try to get credentials from Odoo client
            if hasattr(self.main_agent, 'get_odoo_client_for_session'):
                client = self.main_agent.get_odoo_client_for_session(session_id)
                if client and hasattr(client, 'url') and hasattr(client, 'database'):
                    return {
                        'url': client.url,
                        'database': client.database,
                        'username': client.username,
                        'password': client.password,
                        'gemini_api_key': getattr(client, 'gemini_api_key', os.getenv('GEMINI_API_KEY'))
                    }
            
            logger.warning(f"No credentials found for session {session_id}")
            return None
            
        except Exception as e:
            logger.error(f"Error getting credentials for session {session_id}: {str(e)}")
            return None
    
    def get_file_download_url(self, filename: str, session_id: str) -> str:
        """
        Get download URL for a generated file
        
        Args:
            filename: Name of the file to download
            session_id: Session identifier
            
        Returns:
            str: File path if file exists, None otherwise
        """
        try:
            # Delegate to dynamic reporting agent service
            return self.dynamic_reporting_agent.get_file_download_url(filename, session_id)
        except Exception as e:
            logger.error(f"Error getting file download URL: {str(e)}")
            return None
    
    def _is_dynamic_crud_agent_initialized(self, session_id: str) -> bool:
        """Check if dynamic CRUD agent is initialized for session"""
        return session_id in dynamic_crud_agent_service.agents
    
    def _is_dynamic_reporting_agent_initialized(self, session_id: str) -> bool:
        """Check if dynamic reporting agent is initialized for session"""
        return session_id in self.dynamic_reporting_agent.tools
    
    def get_agent_info(self, session_id: str) -> Dict[str, Any]:
        """
        Get information about available agents for a session
        
        Args:
            session_id: Session identifier
            
        Returns:
            Dict containing agent availability information
        """
        return {
            "main_agent": {
                "available": True,
                "description": "Handles navigation, shortcuts, document processing"
            },
            "dynamic_crud_agent": {
                "available": self._is_dynamic_crud_agent_initialized(session_id),
                "description": "Handles data lookup, create, update, delete operations"
            },
            "dynamic_reporting_agent": {
                "available": self._is_dynamic_reporting_agent_initialized(session_id),
                "description": "Handles reports, charts, and PDF generation"
            }
        }
    
    def cleanup_session(self, session_id: str):
        """Clean up resources for all agents in a session"""
        try:
            dynamic_crud_agent_service.cleanup_session(session_id)
            # Note: dynamic_reporting_agent_service cleanup would be called here too
            logger.info(f"Cleaned up session {session_id} for all agents")
        except Exception as e:
            logger.error(f"Error cleaning up session {session_id}: {str(e)}")

# Global instance
enhanced_agent_service = EnhancedAgentService()