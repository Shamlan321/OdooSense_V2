import os
import json
import logging
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
import hashlib
import base64
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

logger = logging.getLogger(__name__)

class PersistentSessionStorage:
    """
    Persistent session storage that saves encrypted credentials to disk.
    Sessions persist across server restarts but are cleaned up after expiry.
    Enhanced with in-memory caching for better performance.
    """
    
    def __init__(self, storage_dir: str = "sessions", session_expiry_hours: int = 24):
        """
        Initialize persistent session storage.
        
        Args:
            storage_dir: Directory to store session files
            session_expiry_hours: Hours after which sessions expire
        """
        self.storage_dir = storage_dir
        self.session_expiry = timedelta(hours=session_expiry_hours)
        self._memory_cache = {}  # In-memory cache for faster access
        self._cache_timestamps = {}  # Track when items were cached
        self._cache_expiry = timedelta(minutes=10)  # Cache items for 10 minutes
        self._ensure_storage_dir()
        self._encryption_key = self._get_or_create_encryption_key()
        self._cleanup_expired_sessions()
        
    def _ensure_storage_dir(self):
        """Ensure storage directory exists."""
        if not os.path.exists(self.storage_dir):
            os.makedirs(self.storage_dir, mode=0o700)  # Secure permissions
            logger.info(f"Created session storage directory: {self.storage_dir}")
    
    def _get_or_create_encryption_key(self) -> Fernet:
        """Get or create encryption key for session data."""
        key_file = os.path.join(self.storage_dir, '.session_key')
        
        if os.path.exists(key_file):
            with open(key_file, 'rb') as f:
                key = f.read()
        else:
            # Generate a new key
            key = Fernet.generate_key()
            with open(key_file, 'wb') as f:
                f.write(key)
            os.chmod(key_file, 0o600)  # Secure permissions
            logger.info("Generated new session encryption key")
        
        return Fernet(key)
    
    def _get_session_file_path(self, session_id: str) -> str:
        """Get file path for session data."""
        # Hash session ID for security
        session_hash = hashlib.sha256(session_id.encode()).hexdigest()[:16]
        return os.path.join(self.storage_dir, f"session_{session_hash}.enc")
    
    def save_session_credentials(self, session_id: str, credentials: Dict[str, str]) -> bool:
        """
        Save encrypted credentials for a session with in-memory caching.
        
        Args:
            session_id: Session identifier
            credentials: Credentials dictionary
            
        Returns:
            bool: True if successful
        """
        try:
            session_data = {
                'session_id': session_id,
                'credentials': credentials,
                'created_at': datetime.now().isoformat(),
                'last_accessed': datetime.now().isoformat()
            }
            
            # Encrypt and save to disk
            encrypted_data = self._encryption_key.encrypt(
                json.dumps(session_data).encode()
            )
            
            session_file = self._get_session_file_path(session_id)
            with open(session_file, 'wb') as f:
                f.write(encrypted_data)
            
            os.chmod(session_file, 0o600)  # Secure permissions
            
            # Cache in memory for faster access
            self._memory_cache[session_id] = credentials.copy()
            self._cache_timestamps[session_id] = datetime.now()
            
            logger.info(f"Session credentials saved and cached for session {session_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to save session credentials for {session_id}: {str(e)}")
            return False
    
    def get_session_credentials(self, session_id: str) -> Optional[Dict[str, str]]:
        """
        Get credentials for a session with in-memory caching.
        
        Args:
            session_id: Session identifier
            
        Returns:
            Optional[Dict]: Credentials if found and valid, None otherwise
        """
        try:
            # Check memory cache first
            if session_id in self._memory_cache:
                cached_time = self._cache_timestamps.get(session_id)
                if cached_time and datetime.now() - cached_time < self._cache_expiry:
                    logger.debug(f"Retrieved credentials from memory cache for session {session_id}")
                    return self._memory_cache[session_id].copy()
                else:
                    # Cache expired, remove from memory
                    self._memory_cache.pop(session_id, None)
                    self._cache_timestamps.pop(session_id, None)
            
            # Not in cache or cache expired, read from disk
            session_file = self._get_session_file_path(session_id)
            
            if not os.path.exists(session_file):
                logger.debug(f"No session file found for {session_id}")
                return None
            
            # Read and decrypt
            with open(session_file, 'rb') as f:
                encrypted_data = f.read()
            
            decrypted_data = self._encryption_key.decrypt(encrypted_data)
            session_data = json.loads(decrypted_data.decode())
            
            # Check if session has expired
            created_at = datetime.fromisoformat(session_data['created_at'])
            if datetime.now() - created_at > self.session_expiry:
                logger.info(f"Session {session_id} has expired")
                self.delete_session(session_id)
                return None
            
            # Update last accessed time and save back to disk
            session_data['last_accessed'] = datetime.now().isoformat()
            self.save_session_credentials(session_id, session_data['credentials'])
            
            # Cache the credentials in memory
            credentials = session_data['credentials']
            self._memory_cache[session_id] = credentials.copy()
            self._cache_timestamps[session_id] = datetime.now()
            
            logger.info(f"Retrieved and cached session credentials for {session_id}")
            return credentials
            
        except Exception as e:
            logger.error(f"Failed to get session credentials for {session_id}: {str(e)}")
            return None
    
    def delete_session(self, session_id: str) -> bool:
        """
        Delete a session from both disk and memory cache.
        
        Args:
            session_id: Session identifier
            
        Returns:
            bool: True if successful
        """
        try:
            # Remove from disk
            session_file = self._get_session_file_path(session_id)
            if os.path.exists(session_file):
                os.remove(session_file)
            
            # Remove from memory cache
            self._memory_cache.pop(session_id, None)
            self._cache_timestamps.pop(session_id, None)
            
            logger.info(f"Deleted session {session_id} from disk and cache")
            return True
        except Exception as e:
            logger.error(f"Failed to delete session {session_id}: {str(e)}")
            return False
    
    def _cleanup_expired_sessions(self):
        """Clean up expired session files."""
        try:
            if not os.path.exists(self.storage_dir):
                return
            
            expired_count = 0
            for filename in os.listdir(self.storage_dir):
                if filename.startswith('session_') and filename.endswith('.enc'):
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
                logger.info(f"Cleaned up {expired_count} expired session files")
                
        except Exception as e:
            logger.error(f"Failed to cleanup expired sessions: {str(e)}")
    
    def get_active_sessions_count(self) -> int:
        """Get count of active sessions."""
        try:
            if not os.path.exists(self.storage_dir):
                return 0
            
            count = 0
            for filename in os.listdir(self.storage_dir):
                if filename.startswith('session_') and filename.endswith('.enc'):
                    count += 1
            return count
        except Exception as e:
            logger.error(f"Failed to get active sessions count: {str(e)}")
            return 0

# Global instance
persistent_session_storage = PersistentSessionStorage() 