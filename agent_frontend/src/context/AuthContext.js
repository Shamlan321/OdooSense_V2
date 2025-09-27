import React, { createContext, useContext, useReducer, useCallback, useEffect } from 'react';
import { authService } from '../services/authService';

const AuthContext = createContext();

// Auth state management
const initialState = {
  isAuthenticated: false,
  isLoading: true,
  sessionId: null,
  credentials: null,
  error: null
};

const authReducer = (state, action) => {
  switch (action.type) {
    case 'SET_LOADING':
      return {
        ...state,
        isLoading: action.payload,
        error: null
      };
    
    case 'SET_AUTHENTICATED':
      return {
        ...state,
        isAuthenticated: true,
        isLoading: false,
        sessionId: action.payload.sessionId,
        credentials: action.payload.credentials,
        error: null
      };
    
    case 'SET_UNAUTHENTICATED':
      return {
        ...state,
        isAuthenticated: false,
        isLoading: false,
        sessionId: null,
        credentials: null,
        error: action.payload?.error || null
      };
    
    case 'SET_ERROR':
      return {
        ...state,
        isLoading: false,
        error: action.payload
      };
    
    case 'CLEAR_ERROR':
      return {
        ...state,
        error: null
      };
    
    default:
      return state;
  }
};

export const AuthProvider = ({ children }) => {
  const [state, dispatch] = useReducer(authReducer, initialState);

  // Check for existing authentication session on mount
  useEffect(() => {
    checkAuthStatus();
  }, []);

  const checkAuthStatus = useCallback(async () => {
    console.log('[AuthContext] Checking authentication status...');
    
    dispatch({ type: 'SET_LOADING', payload: true });
    
    try {
      const result = await authService.checkSession();
      
      if (result.authenticated) {
        dispatch({
          type: 'SET_AUTHENTICATED',
          payload: {
            sessionId: result.sessionId,
            credentials: result.credentials
          }
        });
        console.log('[AuthContext] ✅ User is authenticated');
      } else {
        dispatch({
          type: 'SET_UNAUTHENTICATED',
          payload: { error: result.error }
        });
        console.log('[AuthContext] ❌ User is not authenticated');
      }
    } catch (error) {
      console.error('[AuthContext] Auth check failed:', error);
      dispatch({
        type: 'SET_ERROR',
        payload: error.message || 'Authentication check failed'
      });
    }
  }, []);

  const authenticate = useCallback(async (credentials) => {
    console.log('[AuthContext] Authenticating user...');
    
    dispatch({ type: 'SET_LOADING', payload: true });
    
    try {
      const result = await authService.authenticate(credentials);
      
      if (result.success) {
        dispatch({
          type: 'SET_AUTHENTICATED',
          payload: {
            sessionId: result.sessionId,
            credentials: result.credentials
          }
        });
        console.log('[AuthContext] ✅ Authentication successful');
        return { success: true, message: result.message };
      } else {
        dispatch({ type: 'SET_UNAUTHENTICATED' });
        console.log('[AuthContext] ❌ Authentication failed');
        return { success: false, message: result.message };
      }
    } catch (error) {
      console.error('[AuthContext] Authentication error:', error);
      dispatch({
        type: 'SET_ERROR',
        payload: error.message || 'Authentication failed'
      });
      return { success: false, message: error.message || 'Authentication failed' };
    }
  }, []);

  const logout = useCallback(async () => {
    console.log('[AuthContext] Logging out user...');
    
    try {
      await authService.logout();
      dispatch({ type: 'SET_UNAUTHENTICATED' });
      console.log('[AuthContext] ✅ Logout successful');
      return { success: true };
    } catch (error) {
      console.error('[AuthContext] Logout error:', error);
      // Still clear local state even if API call fails
      dispatch({ type: 'SET_UNAUTHENTICATED' });
      return { success: false, message: error.message || 'Logout failed' };
    }
  }, []);

  const getCredentials = useCallback(async () => {
    console.log('[AuthContext] Getting full credentials...');
    
    try {
      const result = await authService.getCredentials();
      
      if (result.success) {
        console.log('[AuthContext] ✅ Credentials retrieved');
        return result;
      } else {
        console.log('[AuthContext] ❌ No credentials found');
        // If credentials not found, user might be logged out
        dispatch({ type: 'SET_UNAUTHENTICATED' });
        return result;
      }
    } catch (error) {
      console.error('[AuthContext] Get credentials error:', error);
      return { success: false, message: error.message || 'Failed to get credentials' };
    }
  }, []);

  const clearError = useCallback(() => {
    dispatch({ type: 'CLEAR_ERROR' });
  }, []);

  const value = {
    // State
    isAuthenticated: state.isAuthenticated,
    isLoading: state.isLoading,
    sessionId: state.sessionId,
    credentials: state.credentials,
    error: state.error,
    
    // Actions
    authenticate,
    logout,
    getCredentials,
    checkAuthStatus,
    clearError
  };

  return (
    <AuthContext.Provider value={value}>
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};

export default AuthContext; 