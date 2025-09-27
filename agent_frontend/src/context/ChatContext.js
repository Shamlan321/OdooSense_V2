import React, { createContext, useContext, useReducer, useCallback, useEffect } from 'react';
import { v4 as uuidv4 } from 'uuid';

const ChatContext = createContext();

// Get or create persistent session ID
const getOrCreateSessionId = () => {
  let sessionId = localStorage.getItem('odoo_session_id');
  if (!sessionId) {
    sessionId = uuidv4();
    localStorage.setItem('odoo_session_id', sessionId);
    console.log('[ChatContext] Created new session ID:', sessionId);
  } else {
    console.log('[ChatContext] Using existing session ID:', sessionId);
  }
  return sessionId;
};

const initialState = {
  messages: [],
  isLoading: false,
  error: null,
  sessionId: getOrCreateSessionId(), // Use persistent session ID
  isStreaming: false,
  uploadedFile: null,
  conversationHistory: [],
  agentStatus: 'idle' // idle, processing, responding
};

const chatReducer = (state, action) => {
  switch (action.type) {
    case 'ADD_MESSAGE':
      return {
        ...state,
        messages: [...state.messages, action.payload],
        error: null
      };
    
    case 'UPDATE_LAST_MESSAGE':
      return {
        ...state,
        messages: state.messages.map((msg, index) => 
          index === state.messages.length - 1 
            ? { 
                ...msg, 
                content: action.payload.isCompletion ? msg.content : msg.content + action.payload.content,
                isStreaming: !action.payload.isCompletion
              }
            : msg
        )
      };
    
    case 'SET_LOADING':
      return {
        ...state,
        isLoading: action.payload
      };
    
    case 'SET_STREAMING':
      return {
        ...state,
        isStreaming: action.payload
      };
    
    case 'SET_ERROR':
      return {
        ...state,
        error: action.payload,
        isLoading: false,
        isStreaming: false
      };
    
    case 'SET_UPLOADED_FILE':
      return {
        ...state,
        uploadedFile: action.payload
      };
    
    case 'CLEAR_UPLOADED_FILE':
      return {
        ...state,
        uploadedFile: null
      };
    
    case 'SET_AGENT_STATUS':
      return {
        ...state,
        agentStatus: action.payload
      };
    
    case 'CLEAR_MESSAGES':
      return {
        ...state,
        messages: [],
        error: null
      };
    
    case 'SET_CONVERSATION_HISTORY':
      return {
        ...state,
        conversationHistory: action.payload
      };
    
    case 'NEW_SESSION':
      // Create new session but keep the same persistent session ID for credentials
      const newSessionId = getOrCreateSessionId();
      return {
        ...initialState,
        sessionId: newSessionId
      };
    
    case 'RESTORE_SESSION':
      // Restore session with existing session ID
      return {
        ...state,
        sessionId: action.payload.sessionId || state.sessionId,
        messages: action.payload.messages || [],
        conversationHistory: action.payload.conversationHistory || []
      };
    
    case 'UPDATE_SESSION_ID':
      // Update session ID without affecting other state
      return {
        ...state,
        sessionId: action.payload
      };
    
    default:
      return state;
  }
};

export const ChatProvider = ({ children }) => {
  const [state, dispatch] = useReducer(chatReducer, initialState);

  // Restore session on mount
  useEffect(() => {
    const restoreSession = () => {
      try {
        console.log('[ChatContext] 🔄 Restoring session on page load...');
        const savedMessages = localStorage.getItem('odoo_chat_messages');
        const savedHistory = localStorage.getItem('odoo_conversation_history');
        const currentSessionId = getOrCreateSessionId();
        
        console.log('[ChatContext] Current session ID:', currentSessionId);
        
        if (savedMessages || savedHistory) {
          dispatch({
            type: 'RESTORE_SESSION',
            payload: {
              sessionId: currentSessionId,
              messages: savedMessages ? JSON.parse(savedMessages) : [],
              conversationHistory: savedHistory ? JSON.parse(savedHistory) : []
            }
          });
        }
        
        // Check if we have credentials for a different session and need to sync
        setTimeout(() => {
          console.log('[ChatContext] 🔍 Checking for session synchronization needs...');
          window.dispatchEvent(new CustomEvent('sessionRestored', { 
            detail: { sessionId: currentSessionId } 
          }));
        }, 500);
      } catch (error) {
        console.error('Failed to restore session:', error);
      }
    };

    restoreSession();
  }, []);

  // Save messages to localStorage when they change
  useEffect(() => {
    try {
      localStorage.setItem('odoo_chat_messages', JSON.stringify(state.messages));
    } catch (error) {
      console.error('Failed to save messages:', error);
    }
  }, [state.messages]);

  // Save conversation history to localStorage when it changes
  useEffect(() => {
    try {
      localStorage.setItem('odoo_conversation_history', JSON.stringify(state.conversationHistory));
    } catch (error) {
      console.error('Failed to save conversation history:', error);
    }
  }, [state.conversationHistory]);

  const addMessage = useCallback((message) => {
    dispatch({ type: 'ADD_MESSAGE', payload: message });
  }, []);

  const updateLastMessage = useCallback((content, isCompletion = false) => {
    dispatch({ type: 'UPDATE_LAST_MESSAGE', payload: { content, isCompletion } });
  }, []);

  const setLoading = useCallback((loading) => {
    dispatch({ type: 'SET_LOADING', payload: loading });
  }, []);

  const setStreaming = useCallback((streaming) => {
    dispatch({ type: 'SET_STREAMING', payload: streaming });
  }, []);

  const setError = useCallback((error) => {
    dispatch({ type: 'SET_ERROR', payload: error });
  }, []);

  const setUploadedFile = useCallback((file) => {
    dispatch({ type: 'SET_UPLOADED_FILE', payload: file });
  }, []);

  const clearUploadedFile = useCallback(() => {
    dispatch({ type: 'CLEAR_UPLOADED_FILE' });
  }, []);

  const setAgentStatus = useCallback((status) => {
    dispatch({ type: 'SET_AGENT_STATUS', payload: status });
  }, []);

  const clearMessages = useCallback(() => {
    dispatch({ type: 'CLEAR_MESSAGES' });
    localStorage.removeItem('odoo_chat_messages');
  }, []);

  const setConversationHistory = useCallback((history) => {
    dispatch({ type: 'SET_CONVERSATION_HISTORY', payload: history });
  }, []);

  const newSession = useCallback(() => {
    // Clear chat but keep credentials and session ID
    dispatch({ type: 'CLEAR_MESSAGES' });
    localStorage.removeItem('odoo_chat_messages');
    localStorage.removeItem('odoo_conversation_history');
    // Keep session ID and credentials for persistence
  }, []);

  const clearSession = useCallback(() => {
    // Clear everything including credentials
    dispatch({ type: 'NEW_SESSION' });
    localStorage.removeItem('odoo_chat_messages');
    localStorage.removeItem('odoo_conversation_history');
    localStorage.removeItem('odoo_session_id');
    localStorage.removeItem('odoo_credentials');
  }, []);

  const updateSessionId = useCallback((newSessionId) => {
    console.log('[ChatContext] 🔄 Updating session ID from', state.sessionId, 'to', newSessionId);
    // Update session ID and persist to localStorage
    localStorage.setItem('odoo_session_id', newSessionId);
    dispatch({ type: 'UPDATE_SESSION_ID', payload: newSessionId });
    
    // Force all components to refresh with new session ID
    setTimeout(() => {
      console.log('[ChatContext] 📢 Broadcasting session change event');
      window.dispatchEvent(new CustomEvent('sessionIdChanged', { 
        detail: { newSessionId, oldSessionId: state.sessionId } 
      }));
    }, 100);
  }, [state.sessionId]);

  const value = {
    ...state,
    addMessage,
    updateLastMessage,
    setLoading,
    setStreaming,
    setError,
    setUploadedFile,
    clearUploadedFile,
    setAgentStatus,
    clearMessages,
    setConversationHistory,
    newSession,
    clearSession,
    updateSessionId
  };

  return (
    <ChatContext.Provider value={value}>
      {children}
    </ChatContext.Provider>
  );
};

export const useChat = () => {
  const context = useContext(ChatContext);
  if (!context) {
    throw new Error('useChat must be used within a ChatProvider');
  }
  return context;
};