from typing import TypedDict, List, Optional, Dict, Any
from dataclasses import dataclass, field
from datetime import datetime

class AgentState(TypedDict):
    """State definition for the LangGraph agent"""
    # Core message flow
    messages: List[Dict[str, Any]]
    user_id: Optional[int]
    session_id: str
    
    # Intent and processing
    intent: Optional[str]
    confidence: Optional[float]
    entities: Optional[Dict[str, Any]]
    
    # Document processing
    uploaded_file: Optional[Dict[str, Any]]  # {"data": bytes, "mime_type": str, "filename": str}
    extracted_data: Optional[Dict[str, Any]]
    document_type: Optional[str]  # Type specified by user (bill, expense, lead, contact)
    
    # Odoo operations
    odoo_context: Optional[Dict[str, Any]]
    odoo_result: Optional[Dict[str, Any]]
    
    # Conversation management
    conversation_memory: List[Dict[str, Any]]
    
    # Agent flow control
    current_step: str
    next_action: Optional[str]
    error_state: Optional[str]
    retry_count: int
    
    # Response generation
    response: Optional[str]
    response_type: Optional[str]  # "text", "data", "navigation", "error"
    
    # Metadata
    timestamp: Optional[datetime]
    processing_time: Optional[float]

@dataclass
class ConversationEntry:
    """Single conversation entry for memory management"""
    user_message: str
    assistant_response: str
    intent: str
    timestamp: datetime
    entities: Dict[str, Any] = field(default_factory=dict)
    confidence: float = 0.0

@dataclass
class ProcessingResult:
    """Result of any processing operation"""
    success: bool
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    confidence: float = 0.0
    processing_time: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "data": self.data,
            "error": self.error,
            "confidence": self.confidence,
            "processing_time": self.processing_time
        }

class StateManager:
    """Utility class for managing agent state"""
    
    @staticmethod
    def create_initial_state(user_message: str, session_id: str, user_id: int = None) -> AgentState:
        """Create initial state for a new conversation turn"""
        return AgentState(
            messages=[{"role": "user", "content": user_message, "timestamp": datetime.now()}],
            user_id=user_id,
            session_id=session_id,
            intent=None,
            confidence=None,
            entities=None,
            uploaded_file=None,
            extracted_data=None,
            document_type=None,
            odoo_context=None,
            odoo_result=None,
            conversation_memory=[],
            current_step="start",
            next_action=None,
            error_state=None,
            retry_count=0,
            response=None,
            response_type=None,
            timestamp=datetime.now(),
            processing_time=None
        )
    
    @staticmethod
    def add_message(state: AgentState, role: str, content: str, **kwargs) -> AgentState:
        """Add a message to the conversation"""
        message = {
            "role": role,
            "content": content,
            "timestamp": datetime.now(),
            **kwargs
        }
        state["messages"].append(message)
        return state
    
    @staticmethod
    def set_error(state: AgentState, error_message: str, step: str = None) -> AgentState:
        """Set error state"""
        state["error_state"] = error_message
        state["response_type"] = "error"
        if step:
            state["current_step"] = step
        return state
    
    @staticmethod
    def increment_retry(state: AgentState) -> AgentState:
        """Increment retry counter"""
        state["retry_count"] += 1
        return state
    
    @staticmethod
    def should_retry(state: AgentState, max_retries: int = 3) -> bool:
        """Check if operation should be retried"""
        return state["retry_count"] < max_retries and state.get("error_state") is not None
    
    @staticmethod
    def clear_error(state: AgentState) -> AgentState:
        """Clear error state for retry"""
        state["error_state"] = None
        return state
    
    @staticmethod
    def get_last_user_message(state: AgentState) -> str:
        """Get the last user message"""
        for message in reversed(state["messages"]):
            if message["role"] == "user":
                return message["content"]
        return ""
    
    @staticmethod
    def has_uploaded_file(state: AgentState) -> bool:
        """Check if there's an uploaded file to process"""
        return state.get("uploaded_file") is not None
    
    @staticmethod
    def get_conversation_summary(state: AgentState) -> str:
        """Get a summary of the conversation for context"""
        if not state["conversation_memory"]:
            return "No previous conversation."
        
        recent_entries = state["conversation_memory"][-3:]  # Last 3 exchanges
        summary_parts = []
        
        for entry in recent_entries:
            summary_parts.append(f"User: {entry['user_message']}")
            summary_parts.append(f"Assistant: {entry['assistant_response']}")
        
        return "\n".join(summary_parts)

class NodeResult:
    """Standard result format for agent nodes"""
    
    def __init__(self, state: AgentState, success: bool = True, next_node: str = None, error: str = None):
        self.state = state
        self.success = success
        self.next_node = next_node
        self.error = error
    
    def __bool__(self):
        return self.success