import logging
from typing import Dict, Optional
from services.auth_service import auth_service

logger = logging.getLogger(__name__)

class AgentAuthIntegration:
    """
    Integration service that provides authenticated credentials to agent services.
    This service acts as a bridge between the new auth system and existing agents.
    """
    
    def __init__(self):
        self._agent_sessions = {}  # Track which agent sessions map to auth sessions
    
    def get_credentials_for_request(self, user_agent: str, ip_address: str) -> Optional[Dict[str, str]]:
        """
        Get authenticated credentials for an agent request
        
        Args:
            user_agent: Browser user agent
            ip_address: Client IP address
            
        Returns:
            Dict containing credentials or None if not authenticated
        """
        try:
            # Get auth session
            auth_session = auth_service.get_session(user_agent, ip_address)
            
            if auth_session:
                logger.debug(f"Retrieved credentials for browser session {auth_session.browser_id}")
                return auth_session.credentials.copy()
            else:
                logger.warning("No authenticated session found for request")
                return None
                
        except Exception as e:
            logger.error(f"Failed to get credentials for request: {str(e)}")
            return None
    
    def get_session_id_for_request(self, user_agent: str, ip_address: str) -> Optional[str]:
        """
        Get session ID for an agent request
        
        Args:
            user_agent: Browser user agent
            ip_address: Client IP address
            
        Returns:
            Session ID or None if not authenticated
        """
        try:
            # Get auth session
            auth_session = auth_service.get_session(user_agent, ip_address)
            
            if auth_session:
                return auth_session.session_id
            else:
                return None
                
        except Exception as e:
            logger.error(f"Failed to get session ID for request: {str(e)}")
            return None
    
    def create_odoo_client_for_request(self, user_agent: str, ip_address: str):
        """
        Create an OdooClient instance for authenticated requests
        
        Args:
            user_agent: Browser user agent
            ip_address: Client IP address
            
        Returns:
            OdooClient instance or None if not authenticated
        """
        try:
            credentials = self.get_credentials_for_request(user_agent, ip_address)
            
            if credentials:
                from odoo_client import OdooClient
                
                client = OdooClient(
                    url=credentials['url'],
                    database=credentials['database'],
                    username=credentials['username'],
                    password=credentials['password']
                )
                
                logger.debug(f"Created OdooClient for authenticated request")
                return client
            else:
                logger.warning("Cannot create OdooClient - no authenticated session")
                return None
                
        except Exception as e:
            logger.error(f"Failed to create OdooClient for request: {str(e)}")
            return None
    
    def is_request_authenticated(self, user_agent: str, ip_address: str) -> bool:
        """
        Check if a request is from an authenticated session
        
        Args:
            user_agent: Browser user agent
            ip_address: Client IP address
            
        Returns:
            True if authenticated, False otherwise
        """
        try:
            auth_session = auth_service.get_session(user_agent, ip_address)
            return auth_session is not None
        except Exception as e:
            logger.error(f"Failed to check request authentication: {str(e)}")
            return False

# Global integration service instance
agent_auth_integration = AgentAuthIntegration() 