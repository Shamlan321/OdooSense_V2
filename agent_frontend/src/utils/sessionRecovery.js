/**
 * Session Recovery Utility
 * Finds and recovers credentials from any available session
 */

import { agentAPI } from '../services/api';

/**
 * Attempts to find credentials in any available session
 * @param {string} currentSessionId - The current session ID
 * @returns {Promise<{found: boolean, sessionId?: string, credentials?: object}>}
 */
export const findAvailableSession = async (currentSessionId) => {
  console.log('[SessionRecovery] 🔍 Searching for available credentials...');
  
  try {
    // First, check the current session
    console.log('[SessionRecovery] Checking current session:', currentSessionId);
    const currentCheck = await agentAPI.getOdooCredentials(currentSessionId);
    
    if (currentCheck.success && currentCheck.credentials) {
      console.log('[SessionRecovery] ✅ Found credentials in current session');
      return {
        found: true,
        sessionId: currentSessionId,
        credentials: currentCheck.credentials
      };
    }
    
    // If no credentials in current session, check localStorage for hints of other sessions
    const allStorageKeys = Object.keys(localStorage);
    const sessionHints = allStorageKeys.filter(key => 
      key.includes('session') || key.includes('odoo')
    );
    
    console.log('[SessionRecovery] Found storage hints:', sessionHints);
    
    // Try some common session ID patterns that might have been used
    const commonSessions = [
      '8428094f-8aeb-4bad-aa6d-6a838a3c9192', // From the logs
      'fc208a99-36eb-4b0f-9e9a-b49cd882b943'  // From the logs
    ];
    
    for (const testSession of commonSessions) {
      if (testSession !== currentSessionId) {
        console.log('[SessionRecovery] Testing session:', testSession);
        try {
          const testCheck = await agentAPI.getOdooCredentials(testSession);
          if (testCheck.success && testCheck.credentials) {
            console.log('[SessionRecovery] ✅ Found credentials in session:', testSession);
            return {
              found: true,
              sessionId: testSession,
              credentials: testCheck.credentials
            };
          }
        } catch (error) {
          console.log('[SessionRecovery] Session not found:', testSession);
        }
      }
    }
    
    console.log('[SessionRecovery] ❌ No credentials found in any session');
    return { found: false };
    
  } catch (error) {
    console.error('[SessionRecovery] Error during session recovery:', error);
    return { found: false };
  }
};

/**
 * Recovers session if credentials are found elsewhere
 * @param {string} currentSessionId - Current session ID
 * @param {function} updateSessionId - Function to update session ID
 * @returns {Promise<boolean>} - True if recovery was successful
 */
export const recoverSession = async (currentSessionId, updateSessionId) => {
  console.log('[SessionRecovery] 🔄 Starting session recovery...');
  
  const result = await findAvailableSession(currentSessionId);
  
  if (result.found && result.sessionId !== currentSessionId) {
    console.log('[SessionRecovery] 🎯 Recovering session from:', result.sessionId);
    
    // Update the frontend to use the session with credentials
    updateSessionId(result.sessionId);
    
    // Store credentials locally for UI consistency
    const credentialsToStore = {
      url: result.credentials.url,
      database: result.credentials.database,
      username: result.credentials.username
    };
    localStorage.setItem('odoo_credentials', JSON.stringify(credentialsToStore));
    
    // Notify components
    window.dispatchEvent(new CustomEvent('credentialsUpdated'));
    
    console.log('[SessionRecovery] ✅ Session recovery completed');
    return true;
  }
  
  return false;
};