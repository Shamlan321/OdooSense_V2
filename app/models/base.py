from datetime import datetime
from typing import Dict, Any

class BaseModel:
    """Base model class for common functionality."""
    
    def __init__(self):
        self.created_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert model to dictionary."""
        result = {}
        for key, value in self.__dict__.items():
            if isinstance(value, datetime):
                result[key] = value.isoformat()
            else:
                result[key] = value
        return result
    
    def update(self, **kwargs):
        """Update model attributes."""
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)
        self.updated_at = datetime.utcnow()

class User(BaseModel):
    """User model."""
    
    def __init__(self, username: str, email: str, **kwargs):
        super().__init__()
        self.username = username
        self.email = email
        self.is_active = kwargs.get('is_active', True)
        self.roles = kwargs.get('roles', [])

class Message(BaseModel):
    """Message model."""
    
    def __init__(self, content: str, sender: str, room: str = 'default', **kwargs):
        super().__init__()
        self.content = content
        self.sender = sender
        self.room = room
        self.message_type = kwargs.get('message_type', 'text')
