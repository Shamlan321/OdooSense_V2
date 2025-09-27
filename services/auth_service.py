import os
import json
import logging
import hashlib
from typing import Dict, Optional, Tuple
from datetime import datetime, timedelta
from cryptography.fernet import Fernet
from dataclasses import dataclass
import uuid

logger = logging.getLogger(__name__)

@dataclass
class AuthSession:
    """Authentication session data structure"""
    session_id: str
    browser_id: str
    credentials: Dict[str, str]
    created_at: datetime
    last_accessed: datetime
    is_valid: bool = True

class AuthService:
    """
    Clean authentication service for managing Odoo credentials.
    Handles browser-based session persistence and credential validation.
    """
    
    def __init__(self, storage_dir: str = "auth_sessions"):
        self.storage_dir = storage_dir
        self.session_expiry = timedelta(days=30)  # 30-day session expiry
        self._sessions = {}  # In-memory session cache
        self._ensure_storage_dir()
        self._encryption_key = self._get_or_create_encryption_key()
        self._cleanup_expired_sessions()
        
    def _ensure_storage_dir(self):
        """Ensure auth storage directory exists"""
        if not os.path.exists(self.storage_dir):
            os.makedirs(self.storage_dir, mode=0o700)
            logger.info(f"Created auth storage directory: {self.storage_dir}")
    
    def _get_or_create_encryption_key(self) -> Fernet:
        """Get or create encryption key for credential data"""
        key_file = os.path.join(self.storage_dir, '.auth_key')
        
        if os.path.exists(key_file):
            with open(key_file, 'rb') as f:
                key = f.read()
        else:
            key = Fernet.generate_key()
            with open(key_file, 'wb') as f:
                f.write(key)
            os.chmod(key_file, 0o600)
            logger.info("Generated new auth encryption key")
        
        return Fernet(key)
    
    def _generate_browser_id(self, user_agent: str, ip_address: str) -> str:
        """Generate a unique browser ID based on user agent and IP"""
        browser_data = f"{user_agent}:{ip_address}"
        return hashlib.sha256(browser_data.encode()).hexdigest()[:16]
    
    def _get_session_file_path(self, browser_id: str) -> str:
        """Get file path for browser session data"""
        return os.path.join(self.storage_dir, f"auth_{browser_id}.enc")
    
    def authenticate_and_save(self, credentials: Dict[str, str], user_agent: str, ip_address: str) -> Tuple[bool, str, Optional[str]]:
        """
        Test Odoo connection and save credentials if successful
        
        Args:
            credentials: Dict with url, database, username, password
            user_agent: Browser user agent string
            ip_address: Client IP address
            
        Returns:
            Tuple of (success, message, session_id)
        """
        try:
            # Test Odoo connection first
            test_success, test_message, user_info = self._test_odoo_connection(credentials)
            
            if not test_success:
                return False, test_message, None
            
            # Generate browser ID and session ID
            browser_id = self._generate_browser_id(user_agent, ip_address)
            session_id = str(uuid.uuid4())
            
            # Create auth session
            auth_session = AuthSession(
                session_id=session_id,
                browser_id=browser_id,
                credentials=credentials.copy(),
                created_at=datetime.now(),
                last_accessed=datetime.now()
            )
            
            # Save to encrypted storage
            if self._save_session(auth_session):
                # Cache in memory
                self._sessions[browser_id] = auth_session
                
                logger.info(f"Credentials authenticated and saved for browser {browser_id}")
                return True, f"Connection successful! Welcome {user_info.get('name', 'User')}", session_id
            else:
                return False, "Failed to save credentials", None
                
        except Exception as e:
            logger.error(f"Authentication failed: {str(e)}")
            return False, f"Authentication error: {str(e)}", None
    
    def get_session(self, user_agent: str, ip_address: str) -> Optional[AuthSession]:
        """
        Get existing auth session for browser
        
        Args:
            user_agent: Browser user agent string
            ip_address: Client IP address
            
        Returns:
            AuthSession if found and valid, None otherwise
        """
        try:
            browser_id = self._generate_browser_id(user_agent, ip_address)
            
            # Check memory cache first
            if browser_id in self._sessions:
                session = self._sessions[browser_id]
                if self._is_session_valid(session):
                    session.last_accessed = datetime.now()
                    self._save_session(session)  # Update last accessed time
                    return session
                else:
                    # Session expired, remove from cache
                    del self._sessions[browser_id]
            
            # Load from disk
            session = self._load_session(browser_id)
            if session and self._is_session_valid(session):
                # Update last accessed and cache
                session.last_accessed = datetime.now()
                self._save_session(session)
                self._sessions[browser_id] = session
                return session
            elif session:
                # Session expired, clean up
                self._delete_session(browser_id)
                
            return None
            
        except Exception as e:
            logger.error(f"Failed to get session: {str(e)}")
            return None
    
    def clear_session(self, user_agent: str, ip_address: str) -> bool:
        """Clear auth session for browser"""
        try:
            browser_id = self._generate_browser_id(user_agent, ip_address)
            
            # Remove from memory cache
            if browser_id in self._sessions:
                del self._sessions[browser_id]
            
            # Remove from disk
            return self._delete_session(browser_id)
            
        except Exception as e:
            logger.error(f"Failed to clear session: {str(e)}")
            return False
    
    def _test_odoo_connection(self, credentials: Dict[str, str]) -> Tuple[bool, str, Dict]:
        """Test Odoo connection with provided credentials"""
        try:
            from odoo_client import OdooClient
            
            # Validate required fields
            required_fields = ['url', 'database', 'username', 'password']
            for field in required_fields:
                if not credentials.get(field):
                    return False, f"Missing required field: {field}", {}
            
            # Create client and test connection
            client = OdooClient(
                url=credentials['url'],
                database=credentials['database'],
                username=credentials['username'],
                password=credentials['password']
            )
            
            result = client.test_connection()
            
            if result.get('status') == 'success':
                user_info = result.get('user', {})
                return True, "Connection successful", user_info
            else:
                error_msg = result.get('error', 'Connection failed')
                return False, error_msg, {}
                
        except Exception as e:
            logger.error(f"Odoo connection test failed: {str(e)}")
            return False, f"Connection test failed: {str(e)}", {}
    
    def _save_session(self, session: AuthSession) -> bool:
        """Save auth session to encrypted file"""
        try:
            session_data = {
                'session_id': session.session_id,
                'browser_id': session.browser_id,
                'credentials': session.credentials,
                'created_at': session.created_at.isoformat(),
                'last_accessed': session.last_accessed.isoformat(),
                'is_valid': session.is_valid
            }
            
            # Encrypt and save
            encrypted_data = self._encryption_key.encrypt(
                json.dumps(session_data).encode()
            )
            
            session_file = self._get_session_file_path(session.browser_id)
            with open(session_file, 'wb') as f:
                f.write(encrypted_data)
            
            os.chmod(session_file, 0o600)
            return True
            
        except Exception as e:
            logger.error(f"Failed to save session: {str(e)}")
            return False
    
    def _load_session(self, browser_id: str) -> Optional[AuthSession]:
        """Load auth session from encrypted file"""
        try:
            session_file = self._get_session_file_path(browser_id)
            
            if not os.path.exists(session_file):
                return None
            
            # Read and decrypt
            with open(session_file, 'rb') as f:
                encrypted_data = f.read()
            
            decrypted_data = self._encryption_key.decrypt(encrypted_data)
            session_data = json.loads(decrypted_data.decode())
            
            # Reconstruct session object
            session = AuthSession(
                session_id=session_data['session_id'],
                browser_id=session_data['browser_id'],
                credentials=session_data['credentials'],
                created_at=datetime.fromisoformat(session_data['created_at']),
                last_accessed=datetime.fromisoformat(session_data['last_accessed']),
                is_valid=session_data.get('is_valid', True)
            )
            
            return session
            
        except Exception as e:
            logger.error(f"Failed to load session {browser_id}: {str(e)}")
            return None
    
    def _delete_session(self, browser_id: str) -> bool:
        """Delete auth session file"""
        try:
            session_file = self._get_session_file_path(browser_id)
            if os.path.exists(session_file):
                os.remove(session_file)
                logger.info(f"Deleted auth session for browser {browser_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete session {browser_id}: {str(e)}")
            return False
    
    def _is_session_valid(self, session: AuthSession) -> bool:
        """Check if auth session is still valid"""
        if not session.is_valid:
            return False
        
        # Check if session has expired
        if datetime.now() - session.created_at > self.session_expiry:
            return False
        
        return True
    
    def _cleanup_expired_sessions(self):
        """Clean up expired session files"""
        try:
            if not os.path.exists(self.storage_dir):
                return
            
            expired_count = 0
            for filename in os.listdir(self.storage_dir):
                if filename.startswith('auth_') and filename.endswith('.enc'):
                    file_path = os.path.join(self.storage_dir, filename)
                    try:
                        # Check file modification time
                        mod_time = datetime.fromtimestamp(os.path.getmtime(file_path))
                        if datetime.now() - mod_time > self.session_expiry:
                            os.remove(file_path)
                            expired_count += 1
                    except Exception as e:
                        logger.warning(f"Failed to check/cleanup session file {filename}: {str(e)}")
            
            if expired_count > 0:
                logger.info(f"Cleaned up {expired_count} expired auth sessions")
                
        except Exception as e:
            logger.error(f"Failed to cleanup expired sessions: {str(e)}")

# Global auth service instance
auth_service = AuthService() 