import { useState, useEffect, useCallback, useRef } from 'react';
import { agentAPI } from '../services/api';
import { useChat } from '../context/ChatContext';
import { recoverSession } from '../utils/sessionRecovery';

// Global state to prevent multiple simultaneous credential checks
let globalCredentialCheck = null;
let globalCredentialStatus = null;
let globalLastCheck = 0;
let globalSessionId = null; // Track which session the global cache belongs to

export const useCredentials = () => {
  const { sessionId, updateSessionId } = useChat();
  const [credentialsStatus, setCredentialsStatus] = useState({
    isConfigured: false,
    isLoading: true,
    isChecking: false,
    lastChecked: null,
    error: null
  });
  
  // Use ref to track if component is mounted
  const isMountedRef = useRef(true);
  
  // Use ref to store the checkCredentials function to avoid circular dependencies
  const checkCredentialsRef = useRef(null);
  
  // Use ref to prevent rapid useEffect re-execution
  const lastEffectRunRef = useRef(0);
  
  useEffect(() => {
    return () => {
      isMountedRef.current = false;
    };
  }, []);

  // Check if credentials are configured and valid
  const checkCredentials = useCallback(async (skipCache = false) => {
    console.log('[useCredentials] checkCredentials called, sessionId:', sessionId, 'skipCache:', skipCache);
    
    // If session ID changed, clear global cache
    if (globalSessionId && globalSessionId !== sessionId) {
      console.log('[useCredentials] 🔄 Session ID changed from', globalSessionId, 'to', sessionId, '- clearing global cache');
      globalCredentialCheck = null;
      globalCredentialStatus = null;
      globalLastCheck = 0;
    }
    globalSessionId = sessionId;
    
    // Skip if already checking globally
    if (globalCredentialCheck) {
      console.log('[useCredentials] Already checking globally, returning existing promise');
      return globalCredentialCheck;
    }

    // Use global cache if recent (within 5 minutes) and not forcing refresh
    const now = Date.now();
    const cacheExpiry = 5 * 60 * 1000; // 5 minutes cache
    if (!skipCache && globalLastCheck && 
        (now - globalLastCheck) < cacheExpiry && 
        globalCredentialStatus !== null) {
      console.log('[useCredentials] Using cached global status:', globalCredentialStatus);
      // Update local state with cached global state
      if (isMountedRef.current) {
        setCredentialsStatus(prev => ({
          ...prev,
          isConfigured: globalCredentialStatus.isConfigured,
          isLoading: false,
          isChecking: false,
          lastChecked: globalLastCheck,
          error: globalCredentialStatus.error
        }));
      }
      return globalCredentialStatus.isConfigured;
    }

    // Set checking state
    if (isMountedRef.current) {
      setCredentialsStatus(prev => ({ 
        ...prev, 
        isChecking: true,
        isLoading: false, // Clear loading state when we start checking
        error: null 
      }));
    }

    // Create global promise to prevent multiple simultaneous requests
    globalCredentialCheck = (async () => {
      try {
        // First check if we have local storage credentials
        const localCredentials = localStorage.getItem('odoo_credentials');
        
        if (localCredentials) {
          try {
            const parsedCredentials = JSON.parse(localCredentials);
            const requiredFields = ['url', 'database', 'username'];
            const hasAllFields = requiredFields.every(field => parsedCredentials[field]);
            
            if (hasAllFields) {
              // We have valid local credentials, check backend
              console.log('[useCredentials] 🔍 Checking backend credentials for session:', sessionId);
              const credentialCheck = await agentAPI.getOdooCredentials(sessionId);
              
              if (credentialCheck.success && credentialCheck.credentials) {
                // Backend has credentials, we're good
                const newStatus = {
                  isConfigured: true,
                  error: null
                };
                
                globalCredentialStatus = newStatus;
                globalLastCheck = now;
                
                if (isMountedRef.current) {
                  setCredentialsStatus({
                    isConfigured: true,
                    isLoading: false,
                    isChecking: false,
                    lastChecked: now,
                    error: null
                  });
                }
                return true;
              } else {
                // Local credentials exist but backend doesn't have them
                localStorage.removeItem('odoo_credentials');
                const newStatus = {
                  isConfigured: false,
                  error: 'Session expired - please re-enter credentials'
                };
                
                globalCredentialStatus = newStatus;
                globalLastCheck = now;
                
                if (isMountedRef.current) {
                  setCredentialsStatus({
                    isConfigured: false,
                    isLoading: false,
                    isChecking: false,
                    lastChecked: now,
                    error: newStatus.error
                  });
                }
                return false;
              }
            } else {
              localStorage.removeItem('odoo_credentials');
            }
          } catch (parseError) {
            localStorage.removeItem('odoo_credentials');
          }
        }
        
        // No valid local credentials, check backend anyway
        console.log('[useCredentials] 🔍 No local credentials, checking backend for session:', sessionId);
        const credentialCheck = await agentAPI.getOdooCredentials(sessionId);
        
        if (credentialCheck.success && credentialCheck.credentials) {
          // Backend has credentials but local storage doesn't
          const localCredentials = {
            url: credentialCheck.credentials.url,
            database: credentialCheck.credentials.database,
            username: credentialCheck.credentials.username
          };
          localStorage.setItem('odoo_credentials', JSON.stringify(localCredentials));
          
          const newStatus = {
            isConfigured: true,
            error: null
          };
          
          globalCredentialStatus = newStatus;
          globalLastCheck = now;
          
          if (isMountedRef.current) {
            setCredentialsStatus({
              isConfigured: true,
              isLoading: false,
              isChecking: false,
              lastChecked: now,
              error: null
            });
          }
          return true;
        } else {
          // No credentials anywhere, try session recovery before giving up
          console.log('[useCredentials] 🔄 No credentials found, attempting session recovery...');
          
          const recoverySuccessful = await recoverSession(sessionId, updateSessionId);
          
          if (recoverySuccessful) {
            console.log('[useCredentials] ✅ Session recovery successful, rechecking credentials...');
            // Session recovery succeeded, recheck credentials with new session
            // Don't use global cache since we just changed sessions
            globalCredentialCheck = null;
            globalCredentialStatus = null;
            globalLastCheck = 0;
            
            // Wait a moment for the session update to propagate
            await new Promise(resolve => setTimeout(resolve, 500));
            
            // Recursive call to check with recovered session (but skip cache)
            return await checkCredentialsRef.current(true);
          }
          
          // No credentials anywhere and no recovery possible
          console.log('[useCredentials] ❌ No credentials found anywhere, setting isConfigured: false');
          const newStatus = {
            isConfigured: false,
            error: null
          };
          
          globalCredentialStatus = newStatus;
          globalLastCheck = now;
          
          if (isMountedRef.current) {
            setCredentialsStatus({
              isConfigured: false,
              isLoading: false,
              isChecking: false,
              lastChecked: now,
              error: null
            });
          }
          return false;
        }
      } catch (error) {
        console.error('Credential check failed:', error);
        const newStatus = {
          isConfigured: false,
          error: 'Failed to check credentials'
        };
        
        globalCredentialStatus = newStatus;
        globalLastCheck = now;
        
        if (isMountedRef.current) {
          setCredentialsStatus({
            isConfigured: false,
            isLoading: false,
            isChecking: false,
            lastChecked: now,
            error: newStatus.error
          });
        }
        return false;
      } finally {
        globalCredentialCheck = null;
      }
    })();

    return globalCredentialCheck;
  }, [sessionId]); // Removed credentialsStatus dependencies to prevent circular updates

  // Store the function in ref to avoid circular dependencies
  checkCredentialsRef.current = checkCredentials;

  // Initial check on mount and when session changes - fixed dependency
  useEffect(() => {
    console.log('[useCredentials] useEffect triggered, sessionId:', sessionId, 'isMounted:', isMountedRef.current);
    
    // Prevent rapid re-execution of this effect
    const now = Date.now();
    if (now - lastEffectRunRef.current < 1000) {
      console.log('[useCredentials] useEffect called too frequently, skipping');
      return;
    }
    lastEffectRunRef.current = now;
    
    if (sessionId && isMountedRef.current) {
      // Check if we already have cached global status
      const cacheExpiry = 5 * 60 * 1000; // 5 minutes cache
      if (globalLastCheck && (now - globalLastCheck) < cacheExpiry && globalCredentialStatus !== null) {
        console.log('[useCredentials] Using cached status on mount:', globalCredentialStatus);
        // Use cached status instead of making new request
        setCredentialsStatus({
          isConfigured: globalCredentialStatus.isConfigured,
          isLoading: false,
          isChecking: false,
          lastChecked: globalLastCheck,
          error: globalCredentialStatus.error
        });
      } else {
        console.log('[useCredentials] No cache or cache expired, making fresh check');
        // No cache or cache expired, make fresh check
        checkCredentials();
      }
    } else if (!sessionId && isMountedRef.current) {
      console.log('[useCredentials] No sessionId, clearing loading state');
      // No sessionId available, clear loading state immediately
      setCredentialsStatus({
        isConfigured: false,
        isLoading: false,
        isChecking: false,
        lastChecked: null,
        error: 'Session not initialized'
      });
    }
  }, [sessionId]); // Only depend on sessionId, not checkCredentials

  // Listen for credential changes from other components AND session ID changes
  useEffect(() => {
    const handleStorageChange = (e) => {
      if (e.key === 'odoo_credentials_updated') {
        // Another component saved credentials, refresh our status
        setTimeout(() => {
          if (isMountedRef.current && checkCredentialsRef.current) {
            checkCredentialsRef.current(true);
          }
        }, 100);
      }
    };

    const handleCredentialsUpdate = () => {
      setTimeout(() => {
        if (isMountedRef.current && checkCredentialsRef.current) {
          checkCredentialsRef.current(true);
        }
      }, 100);
    };
    
    const handleSessionIdChange = (event) => {
      console.log('[useCredentials] 🔄 Session ID changed event received:', event.detail);
      // Clear all caches and force fresh check with new session ID
      globalCredentialCheck = null;
      globalCredentialStatus = null;
      globalLastCheck = 0;
      globalSessionId = event.detail.newSessionId;
      
      setTimeout(() => {
        if (isMountedRef.current && checkCredentialsRef.current) {
          console.log('[useCredentials] 🔍 Refreshing credentials with new session ID');
          checkCredentialsRef.current(true);
        }
      }, 200);
    };
    
    window.addEventListener('storage', handleStorageChange);
    window.addEventListener('credentialsUpdated', handleCredentialsUpdate);
    window.addEventListener('sessionIdChanged', handleSessionIdChange);
    
    return () => {
      window.removeEventListener('storage', handleStorageChange);
      window.removeEventListener('credentialsUpdated', handleCredentialsUpdate);
      window.removeEventListener('sessionIdChanged', handleSessionIdChange);
    };
  }, []); // No dependencies - set up event listeners only once

  // Refresh credentials status (useful after saving new credentials)
  const refreshCredentials = useCallback(() => {
    console.log('[useCredentials] 🔄 refreshCredentials called with sessionId:', sessionId);
    console.trace('[useCredentials] refreshCredentials call stack'); // This will show us where it's being called from
    if (isMountedRef.current) {
      // Clear global cache to force fresh check
      globalCredentialCheck = null;
      globalCredentialStatus = null;
      globalLastCheck = 0;
      globalSessionId = sessionId; // Update global session tracking
      // Use ref to avoid circular dependency
      return checkCredentialsRef.current ? checkCredentialsRef.current(true) : Promise.resolve(false);
    }
    return Promise.resolve(false);
  }, [sessionId]); // Only depend on sessionId to prevent circular dependencies

  // Get stored credentials (without password for security)
  const getStoredCredentials = useCallback(() => {
    try {
      const stored = localStorage.getItem('odoo_credentials');
      if (stored) {
        const credentials = JSON.parse(stored);
        return {
          url: credentials.url || '',
          database: credentials.database || '',
          username: credentials.username || ''
          // Deliberately exclude password for security
        };
      }
    } catch (error) {
      console.error('Failed to get stored credentials:', error);
    }
    return {
      url: '',
      database: '',
      username: ''
    };
  }, []);

  // Save credentials and refresh status
  const saveCredentials = useCallback(async (credentials) => {
    try {
      // Save to localStorage (excluding password)
      const credentialsToStore = {
        url: credentials.url,
        database: credentials.database,
        username: credentials.username
      };
      localStorage.setItem('odoo_credentials', JSON.stringify(credentialsToStore));

      // Save to backend with password (persistent storage)
      const saveResult = await agentAPI.saveOdooCredentials(sessionId, credentials);
      
      if (saveResult.success) {
        // Clear global cache
        globalCredentialCheck = null;
        globalCredentialStatus = { isConfigured: true, error: null };
        globalLastCheck = Date.now();
        
        // Immediate status update for better UX
        if (isMountedRef.current) {
          setCredentialsStatus({
            isConfigured: true,
            isLoading: false,
            isChecking: false,
            lastChecked: Date.now(),
            error: null
          });
        }
        
        // Notify other components that credentials were updated
        window.dispatchEvent(new CustomEvent('credentialsUpdated'));
        
        return { success: true };
      } else {
        throw new Error(saveResult.message || 'Failed to save credentials on server');
      }
    } catch (error) {
      console.error('Failed to save credentials:', error);
      return { 
        success: false, 
        error: error.message || 'Failed to save credentials' 
      };
    }
  }, [sessionId]);

  // Clear credentials
  const clearCredentials = useCallback(async () => {
    try {
      // Clear from backend persistent storage
      await agentAPI.clearOdooCredentials(sessionId);
    } catch (error) {
      console.error('Failed to clear backend credentials:', error);
    }
    
    // Clear from localStorage
    localStorage.removeItem('odoo_credentials');
    
    // Clear global cache
    globalCredentialCheck = null;
    globalCredentialStatus = { isConfigured: false, error: null };
    globalLastCheck = Date.now();
    
    if (isMountedRef.current) {
      setCredentialsStatus({
        isConfigured: false,
        isLoading: false,
        isChecking: false,
        lastChecked: Date.now(),
        error: null
      });
    }
  }, [sessionId]);

  // Check if user has attempted to configure credentials
  const hasAttemptedConfiguration = useCallback(() => {
    const stored = localStorage.getItem('odoo_credentials');
    return !!stored;
  }, []);

  return {
    credentialsStatus,
    checkCredentials,
    refreshCredentials,
    getStoredCredentials,
    saveCredentials,
    clearCredentials,
    hasAttemptedConfiguration,
    
    // Convenience getters
    isConfigured: credentialsStatus.isConfigured,
    isLoading: credentialsStatus.isLoading,
    isChecking: credentialsStatus.isChecking,
    error: credentialsStatus.error
  };
}; 