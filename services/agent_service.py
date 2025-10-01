import logging
from typing import Dict, Any, List, Optional, Union
from datetime import datetime
import uuid
from langgraph_agent import OdooLangGraphAgent

# Import the dynamic CRUD agent service
from services.dynamic_crud_agent_service import dynamic_crud_agent_service
# Import persistent session storage
from services.persistent_session_storage import persistent_session_storage

logger = logging.getLogger(__name__)

class AgentService:
    """
    Service class that wraps the OdooLangGraphAgent to provide a clean interface
    for chat, document ingestion, email parsing, LinkedIn processing, and reporting.
    
    This wrapper maintains the agent's core functionality while providing
    additional service-level features like session management, error handling,
    and logging. It also intercepts CRUD operations and routes them to the 
    dynamic CRUD agent.
    """
    
    def __init__(self):
        """Initialize the agent service with the core agent."""
        try:
            self.agent = OdooLangGraphAgent()
            # Initialize in-memory cache for performance
            self._session_credentials_cache = {}
            # Initialize cached clients for reuse
            self._session_odoo_clients = {}
            logger.info("AgentService initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize AgentService: {str(e)}")
            raise
    
    def chat(self, message: str, session_id: str = None, user_id: int = None) -> Dict[str, Any]:
        """
        Process a chat message through the agent.
        
        Args:
            message: The user's message
            session_id: Session identifier (generated if not provided)
            user_id: User identifier
            
        Returns:
            Dict containing the agent's response and metadata
        """
        if not session_id:
            session_id = self._generate_session_id()
            
        try:
            logger.info(f"[AgentService] Processing chat message for session {session_id}")
            logger.debug(f"[AgentService] Message: '{message}', User ID: {user_id}")
            
            # Check if this is a CRUD operation that should be handled by dynamic CRUD agent
            if self._should_use_dynamic_crud_agent(message, session_id):
                logger.info(f"[AgentService] Routing to dynamic CRUD agent for session {session_id}")
                return self._handle_with_dynamic_crud_agent(message, session_id, user_id)
            
            # Check if agent is properly initialized
            if self.agent is None:
                logger.error("[AgentService] Agent is None - not properly initialized")
                return {
                    "success": False,
                    "response": "Agent service is not properly initialized.",
                    "error": "Agent is None",
                    "session_id": session_id
                }
            
            logger.debug(f"[AgentService] Calling agent.process_message()")
            result = self.agent.process_message(message, session_id, user_id)
            logger.debug(f"[AgentService] Agent returned result: {result}")
            
            if result is None:
                logger.error(f"[AgentService] Agent returned None result for session {session_id}")
                return {
                    "success": False,
                    "response": "Agent returned no response.",
                    "error": "Agent returned None",
                    "session_id": session_id
                }
            
            if not isinstance(result, dict):
                logger.error(f"[AgentService] Agent returned non-dict result: {type(result)} for session {session_id}")
                return {
                    "success": False,
                    "response": "Agent returned invalid response format.",
                    "error": f"Expected dict, got {type(result)}",
                    "session_id": session_id
                }
            
            logger.info(f"[AgentService] Chat message processed successfully for session {session_id}")
            return result
        except Exception as e:
            import traceback
            logger.error(f"[AgentService] Chat processing failed for session {session_id}: {str(e)}")
            logger.error(f"[AgentService] Full traceback: {traceback.format_exc()}")
            return {
                "success": False,
                "response": "I apologize, but I encountered an error processing your message.",
                "error": str(e),
                "session_id": session_id
            }
    
    def _should_use_dynamic_crud_agent(self, message: str, session_id: str) -> bool:
        """
        Determine if a message should be handled by the dynamic CRUD agent
        instead of the main LangGraph agent.
        
        Args:
            message: User message
            session_id: Session identifier
            
        Returns:
            bool: True if should use dynamic CRUD agent
        """
        try:
            
            credentials = self._get_credentials_for_dynamic_crud_agent(session_id)
            if credentials:
                # Initialize the agent if not already done
                if session_id not in dynamic_crud_agent_service.agents:
                    dynamic_crud_agent_service.initialize_agent(credentials, session_id)
                return True
            else:
                logger.warning(f"No credentials available for session {session_id}. Cannot use dynamic CRUD agent.")
                return False
            
        except Exception as e:
            logger.error(f"Error determining dynamic CRUD agent usage: {str(e)}")
            return False
    
    def _handle_with_dynamic_crud_agent(self, message: str, session_id: str, user_id: int = None) -> Dict[str, Any]:
        """
        Handle message using the dynamic CRUD agent
        
        Args:
            message: User message
            session_id: Session identifier
            user_id: User identifier
            
        Returns:
            Dict containing response and metadata
        """
        try:
            # Process query with dynamic CRUD agent
            result = dynamic_crud_agent_service.process_query(message, session_id)
            
            # Format the result to match the expected structure
            if result.get("success"):
                return {
                    "success": True,
                    "response": result.get("response", "Operation completed successfully."),
                    "data": result.get("data"),
                    "agent_type": "dynamic_crud_agent",
                    "session_id": session_id
                }
            else:
                return {
                    "success": False,
                    "response": f"I encountered an error: {result.get('error', 'Unknown error')}",
                    "error": result.get('error'),
                    "agent_type": "dynamic_crud_agent",
                    "session_id": session_id
                }
                
        except Exception as e:
            logger.error(f"Error handling message with dynamic CRUD agent: {str(e)}")
            return {
                "success": False,
                "response": "I apologize, but I encountered an error processing your request.",
                "error": str(e),
                "agent_type": "dynamic_crud_agent",
                "session_id": session_id
            }
    
    def _get_credentials_for_dynamic_crud_agent(self, session_id: str) -> Optional[Dict[str, str]]:
        """
        Get credentials for the dynamic CRUD agent from the current session
        
        Args:
            session_id: Session identifier
            
        Returns:
            Optional[Dict]: Credentials if available
        """
        try:
            # Get Odoo client for this session
            client = self.get_odoo_client_for_session(session_id)
            if client and hasattr(client, 'url') and hasattr(client, 'database'):
                return {
                    'url': client.url,
                    'database': client.database,
                    'username': client.username,
                    'password': client.password,
                    'gemini_api_key': getattr(client, 'gemini_api_key', None)
                }
            
            return None
            
        except Exception as e:
            logger.error(f"Error getting credentials for dynamic CRUD agent: {str(e)}")
            return None
    
    def chat_stream(self, message: str, session_id: str = None, user_id: int = None):
        """
        Process a chat message through the agent with streaming response.
        
        Args:
            message: The user's message
            session_id: Session identifier (generated if not provided)
            user_id: User identifier
            
        Yields:
            Streaming response chunks
        """
        if not session_id:
            session_id = self._generate_session_id()
            
        try:
            logger.info(f"Processing streaming chat message for session {session_id}")
            
            # First yield session info
            yield f"""data: {{"session_id": "{session_id}", "type": "session_start"}}\n\n"""
            
            # Process message with streaming
            for chunk in self.agent.process_message_stream(message, session_id, user_id):
                # Fixed escaping for inner quotes
                yield f"""data: {{"content": "{chunk.replace('"', '\\"')}", "type": "content"}}\n\n"""
            
            # Signal completion
            yield f"""data: {{"type": "done"}}\n\n"""
            
            logger.info(f"Streaming chat message processed successfully for session {session_id}")
            
        except Exception as e:
            logger.error(f"Streaming chat processing failed for session {session_id}: {str(e)}")
            # Fixed escaping for error message
            yield f"""data: {{"error": "{str(e).replace('"', '\\"')}", "type": "error"}}\n\n"""

    
    def document_ingestion(self, file_data: bytes, filename: str, mime_type: str, 
                          session_id: str = None, user_id: int = None, 
                          doc_type: str = None) -> Dict[str, Any]:
        """
        Process an uploaded document through the agent.
        
        Args:
            file_data: Binary data of the file
            filename: Name of the file
            mime_type: MIME type of the file
            session_id: Session identifier (generated if not provided)
            user_id: User identifier
            doc_type: Type of document (invoice, bill, lead, etc.)
            
        Returns:
            Dict containing processing results and extracted data
        """
        if not session_id:
            session_id = self._generate_session_id()
            
        try:
            logger.info(f"Processing document '{filename}' for session {session_id}")
            result = self.agent.process_document(
                file_data, filename, mime_type, session_id, user_id, doc_type
            )
            logger.info(f"Document '{filename}' processed successfully for session {session_id}")
            return result
        except Exception as e:
            logger.error(f"Document processing failed for '{filename}' in session {session_id}: {str(e)}")
            return {
                "success": False,
                "response": f"I apologize, but I encountered an error processing the document '{filename}'.",
                "error": str(e),
                "session_id": session_id
            }
    
    def document_preview(self, file_data: bytes, filename: str, mime_type: str, 
                        session_id: str = None, user_id: int = None, 
                        doc_type: str = None) -> Dict[str, Any]:
        """
        Extract data from document without processing to Odoo (preview mode).
        
        Args:
            file_data: Binary data of the file
            filename: Name of the file
            mime_type: MIME type of the file
            session_id: Session identifier (generated if not provided)
            user_id: User identifier
            doc_type: Type of document (invoice, bill, lead, etc.)
            
        Returns:
            Dict containing extracted data for preview
        """
        if not session_id:
            session_id = self._generate_session_id()
            
        try:
            logger.info(f"Previewing document '{filename}' for session {session_id}")
            result = self.agent.preview_document(
                file_data, filename, mime_type, session_id, user_id, doc_type
            )
            logger.info(f"Document '{filename}' preview completed successfully for session {session_id}")
            return result
        except Exception as e:
            logger.error(f"Document preview failed for '{filename}' in session {session_id}: {str(e)}")
            return {
                "success": False,
                "response": f"I apologize, but I encountered an error previewing the document '{filename}'.",
                "error": str(e),
                "session_id": session_id
            }
    
    def process_confirmed_data(self, extracted_data: Dict[str, Any], session_id: str, 
                              user_id: int = None, document_type: str = None) -> Dict[str, Any]:
        """
        Process confirmed extracted data to Odoo.
        
        Args:
            extracted_data: The confirmed extracted data
            session_id: Session identifier
            user_id: User identifier
            document_type: Type of document being processed
            
        Returns:
            Dict containing processing results
        """
        try:
            logger.info(f"Processing confirmed data for session {session_id}")
            result = self.agent.process_confirmed_data(
                extracted_data, session_id, user_id, document_type
            )
            logger.info(f"Confirmed data processed successfully for session {session_id}")
            return result
        except Exception as e:
            logger.error(f"Confirmed data processing failed for session {session_id}: {str(e)}")
            return {
                "success": False,
                "response": "I apologize, but I encountered an error processing the confirmed data.",
                "error": str(e),
                "session_id": session_id
            }
    
    def process_email(self, email_content: str, session_id: str = None, 
                     user_id: int = None, email_type: str = None) -> Dict[str, Any]:
        """
        Process email content through the agent.
        
        Args:
            email_content: The email content to process
            session_id: Session identifier (generated if not provided)
            user_id: User identifier
            email_type: Type of email (bill, lead, etc.)
            
        Returns:
            Dict containing processing results
        """
        if not session_id:
            session_id = self._generate_session_id()
            
        try:
            logger.info(f"Processing email for session {session_id}")
            result = self.agent.process_email(
                email_content, session_id, user_id, email_type
            )
            logger.info(f"Email processed successfully for session {session_id}")
            return result
        except Exception as e:
            logger.error(f"Email processing failed for session {session_id}: {str(e)}")
            return {
                "success": False,
                "response": "I apologize, but I encountered an error processing the email.",
                "error": str(e),
                "session_id": session_id
            }
    
    def process_linkedin_profile(self, profile_url: str, session_id: str = None, 
                                user_id: int = None) -> Dict[str, Any]:
        """
        Process LinkedIn profile URL through the agent.
        
        Args:
            profile_url: LinkedIn profile URL
            session_id: Session identifier (generated if not provided)
            user_id: User identifier
            
        Returns:
            Dict containing processing results
        """
        if not session_id:
            session_id = self._generate_session_id()
            
        try:
            logger.info(f"Processing LinkedIn profile for session {session_id}")
            result = self.agent.process_linkedin_profile(
                profile_url, session_id, user_id
            )
            logger.info(f"LinkedIn profile processed successfully for session {session_id}")
            return result
        except Exception as e:
            logger.error(f"LinkedIn profile processing failed for session {session_id}: {str(e)}")
            return {
                "success": False,
                "response": "I apologize, but I encountered an error processing the LinkedIn profile.",
                "error": str(e),
                "session_id": session_id
            }
    
    def generate_report(self, report_type: str, parameters: Dict[str, Any] = None, 
                       session_id: str = None, user_id: int = None) -> Dict[str, Any]:
        """
        Generate a report through the agent.
        
        Args:
            report_type: Type of report to generate
            parameters: Report parameters
            session_id: Session identifier (generated if not provided)
            user_id: User identifier
            
        Returns:
            Dict containing report results
        """
        if not session_id:
            session_id = self._generate_session_id()
            
        try:
            logger.info(f"Generating {report_type} report for session {session_id}")
            result = self.agent.generate_report(
                report_type, parameters or {}, session_id, user_id
            )
            logger.info(f"Report generated successfully for session {session_id}")
            return result
        except Exception as e:
            logger.error(f"Report generation failed for session {session_id}: {str(e)}")
            return {
                "success": False,
                "response": f"I apologize, but I encountered an error generating the {report_type} report.",
                "error": str(e),
                "session_id": session_id
            }
    
    def health_check(self) -> Dict[str, Any]:
        """
        Perform a health check of the agent service.
        
        Returns:
            Dict containing health status
        """
        try:
            if self.agent is None:
                return {
                    "status": "unhealthy",
                    "error": "Agent not initialized",
                    "timestamp": datetime.now().isoformat()
                }
            
            # Delegate to agent's health check
            agent_health = self.agent.health_check()
            
            return {
                "status": "healthy" if agent_health.get("overall") == "healthy" else "partial",
                "agent_health": agent_health,
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            logger.error(f"Health check failed: {str(e)}")
            return {
                "status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
    
    def _generate_session_id(self) -> str:
        """Generate a unique session ID."""
        return str(uuid.uuid4())
    
    def get_conversation_history(self, session_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Get conversation history for a session.
        
        Args:
            session_id: Session identifier
            limit: Maximum number of messages to return
            
        Returns:
            List of conversation messages
        """
        try:
            if hasattr(self.agent, 'get_conversation_history'):
                return self.agent.get_conversation_history(session_id, limit)
            else:
                logger.warning("Agent does not support conversation history")
                return []
        except Exception as e:
            logger.error(f"Failed to get conversation history for session {session_id}: {str(e)}")
            return []
    
    def clear_session(self, session_id: str) -> bool:
        """
        Clear session data.
        
        Args:
            session_id: Session identifier
            
        Returns:
            True if successful, False otherwise
        """
        try:
            if hasattr(self.agent, 'clear_session'):
                return self.agent.clear_session(session_id)
            else:
                logger.warning("Agent does not support session clearing")
                return True
        except Exception as e:
            logger.error(f"Failed to clear session {session_id}: {str(e)}")
            return False
    
    def save_odoo_credentials(self, session_id: str, credentials: Dict[str, str]) -> bool:
        """
        Save Odoo credentials for a session with persistent storage and immediate caching.
        
        Args:
            session_id: Session identifier
            credentials: Dictionary containing url, database, username, password
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Save to persistent storage
            success = persistent_session_storage.save_session_credentials(session_id, credentials)
            
            if success:
                # Update in-memory cache for performance
                self._session_credentials_cache[session_id] = credentials.copy()
                
                # Clear any existing cached client to force refresh with new credentials
                if session_id in self._session_odoo_clients:
                    del self._session_odoo_clients[session_id]
                
                # Pre-create and cache the client for immediate availability
                try:
                    from odoo_client import OdooClient
                    import time
                    
                    client = OdooClient(
                        url=credentials['url'],
                        database=credentials['database'],
                        username=credentials['username'],
                        password=credentials['password']
                    )
                    
                    # Add validation timestamp
                    client.last_validated = time.time()
                    
                    # Cache the client for immediate use
                    self._session_odoo_clients[session_id] = client
                    
                    logger.info(f"Odoo credentials saved and client pre-cached for session {session_id}")
                except Exception as client_error:
                    logger.warning(f"Failed to pre-cache client for session {session_id}: {str(client_error)}")
                    # Still return success since credentials were saved
                
                return True
            else:
                logger.error(f"Failed to save credentials to persistent storage for session {session_id}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to save Odoo credentials for session {session_id}: {str(e)}")
            return False
    
    def get_odoo_credentials(self, session_id: str) -> Optional[Dict[str, str]]:
        """
        Get Odoo credentials for a session from cache or persistent storage.
        
        Args:
            session_id: Session identifier
            
        Returns:
            Dictionary containing credentials or None if not found
        """
        try:
            # First check in-memory cache
            if session_id in self._session_credentials_cache:
                logger.debug(f"Retrieved credentials from cache for session {session_id}")
                return self._session_credentials_cache[session_id].copy()
            
            # If not in cache, check persistent storage
            credentials = persistent_session_storage.get_session_credentials(session_id)
            
            if credentials:
                # Cache for future requests
                self._session_credentials_cache[session_id] = credentials.copy()
                logger.info(f"Retrieved Odoo credentials from persistent storage for session {session_id}")
                return credentials.copy()
            else:
                logger.warning(f"No Odoo credentials found for session {session_id}")
                return None
                
        except Exception as e:
            logger.error(f"Failed to get Odoo credentials for session {session_id}: {str(e)}")
            return None
    
    def clear_odoo_credentials(self, session_id: str) -> bool:
        """
        Clear Odoo credentials for a session.
        
        Args:
            session_id: Session identifier
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Remove from persistent storage
            persistent_session_storage.delete_session(session_id)
            
            # Remove from cache
            if session_id in self._session_credentials_cache:
                del self._session_credentials_cache[session_id]
            
            # Remove cached client
            if session_id in self._session_odoo_clients:
                del self._session_odoo_clients[session_id]
            
            logger.info(f"Cleared Odoo credentials for session {session_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to clear Odoo credentials for session {session_id}: {str(e)}")
            return False
    
    def get_odoo_client_for_session(self, session_id: str):
        """
        Get an Odoo client instance for a specific session using saved credentials.
        Now with enhanced caching and connection validation for better performance.
        
        Args:
            session_id: Session identifier
            
        Returns:
            OdooClient instance or None if no credentials found
        """
        try:
            # Check if we have a cached client
            if session_id in self._session_odoo_clients:
                client = self._session_odoo_clients[session_id]
                # Test if client is still valid with a quick check
                try:
                    if hasattr(client, 'uid') and client.uid and hasattr(client, 'last_validated'):
                        # Only revalidate if it's been more than 5 minutes
                        import time
                        if time.time() - getattr(client, 'last_validated', 0) < 300:  # 5 minutes
                            logger.debug(f"Using recently validated cached Odoo client for session {session_id}")
                            return client
                        
                    # Quick validation - try to get user info
                    user_info = client.get_user_info()
                    if user_info:
                        # Update validation timestamp
                        client.last_validated = time.time()
                        logger.debug(f"Revalidated cached Odoo client for session {session_id}")
                        return client
                except Exception as validation_error:
                    logger.warning(f"Cached client validation failed for session {session_id}: {str(validation_error)}")
                    # Client is invalid, remove from cache
                    del self._session_odoo_clients[session_id]

            credentials = self.get_odoo_credentials(session_id)
            if not credentials:
                logger.warning(f"No Odoo credentials found for session {session_id}")
                return None

            # Import OdooClient here to avoid circular imports
            from odoo_client import OdooClient
            import time

            # Create and cache Odoo client with session credentials
            client = OdooClient(
                url=credentials['url'],
                database=credentials['database'],
                username=credentials['username'],
                password=credentials['password']
            )
            
            # Add validation timestamp
            client.last_validated = time.time()
            
            # Cache the client for future use
            self._session_odoo_clients[session_id] = client
            
            logger.info(f"Created and cached new Odoo client for session {session_id}")
            return client
            
        except Exception as e:
            logger.error(f"Failed to create Odoo client for session {session_id}: {str(e)}")
            return None
    
    def get_session_info(self) -> Dict[str, Any]:
        """
        Get information about active sessions.
        
        Returns:
            Dict containing session statistics
        """
        try:
            return {
                'active_sessions_count': persistent_session_storage.get_active_sessions_count(),
                'cached_sessions_count': len(self._session_credentials_cache),
                'cached_clients_count': len(self._session_odoo_clients)
            }
        except Exception as e:
            logger.error(f"Failed to get session info: {str(e)}")
            return {}
    
    def get_supported_features(self) -> List[str]:
        """
        Get list of supported features.
        
        Returns:
            List of supported feature names
        """
        return [
            "chat",
            "document_processing",
            "document_preview",
            "email_processing",
            "linkedin_processing",
            "report_generation",
            "health_monitoring",
            "session_management",
            "odoo_integration"
        ]

# Global agent service instance for use by Flask routes
agent_service = None

def get_agent_service():
    """Get or create the global agent service instance."""
    global agent_service
    if agent_service is None:
        agent_service = AgentService()
    return agent_service

# Initialize the global instance
agent_service = AgentService()
