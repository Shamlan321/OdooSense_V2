import React, { useState, useEffect } from 'react';
import { agentAPI } from '../services/api';
import { useCredentials } from '../hooks/useCredentials';
import { useChat } from '../context/ChatContext';
import {
  CheckCircleIcon,
  ExclamationTriangleIcon,
  EyeIcon,
  EyeSlashIcon,
  Cog6ToothIcon,
  ServerIcon,
  UserIcon,
  KeyIcon,
  BuildingOfficeIcon,
  XMarkIcon
} from '@heroicons/react/24/outline';

const SetupModal = ({ isOpen, onComplete, onClose = null, allowClose = false }) => {
  const { saveCredentials, refreshCredentials } = useCredentials();
  const { sessionId, updateSessionId } = useChat();
  const [credentials, setCredentials] = useState({
    url: '',
    database: '',
    username: '',
    password: ''
  });
  const [showPassword, setShowPassword] = useState(false);
  const [isTestingConnection, setIsTestingConnection] = useState(false);
  const [connectionStatus, setConnectionStatus] = useState(null);
  const [isSaving, setIsSaving] = useState(false);
  const [currentStep, setCurrentStep] = useState(1);

  // Load any existing credentials on mount
  useEffect(() => {
    if (isOpen) {
      loadExistingCredentials();
    }
  }, [isOpen]);

  const loadExistingCredentials = () => {
    const saved = localStorage.getItem('odoo_credentials');
    if (saved) {
      try {
        const parsedCredentials = JSON.parse(saved);
        setCredentials({
          url: parsedCredentials.url || '',
          database: parsedCredentials.database || '',
          username: parsedCredentials.username || '',
          password: '' // Don't load password for security
        });
      } catch (error) {
        console.error('Failed to load saved credentials:', error);
      }
    }
  };

  const handleInputChange = (field, value) => {
    setCredentials(prev => ({
      ...prev,
      [field]: value
    }));
    // Clear connection status when credentials change
    setConnectionStatus(null);
  };

  const validateCredentials = () => {
    const errors = [];
    if (!credentials.url.trim()) errors.push('Odoo URL is required');
    if (!credentials.database.trim()) errors.push('Database name is required');
    if (!credentials.username.trim()) errors.push('Username is required');
    if (!credentials.password.trim()) errors.push('Password is required');
    
    // URL validation
    if (credentials.url.trim()) {
      try {
        new URL(credentials.url);
      } catch (e) {
        errors.push('Invalid URL format');
      }
    }

    return errors;
  };

  const testConnection = async () => {
    const errors = validateCredentials();
    if (errors.length > 0) {
      setConnectionStatus({
        success: false,
        message: errors.join(', ')
      });
      return;
    }

    setIsTestingConnection(true);
    setConnectionStatus(null);

    try {
      console.log('[SetupModal] Testing connection with sessionId:', sessionId);
      
      // Validate session ID before making API call
      if (!sessionId) {
        throw new Error('Session ID not available. Please refresh the page and try again.');
      }
      
      // Use the combined test and save endpoint for streamlined flow
      const result = await agentAPI.testAndSaveOdooConnection(credentials, sessionId);
      console.log('[SetupModal] Test and save result:', result);
      
      if (result.success) {
        // Check if the backend returned a different session ID
        if (result.session_id && result.session_id !== sessionId) {
          console.warn('[SetupModal] ⚠️  Backend returned different session ID!');
          console.warn('[SetupModal] Expected:', sessionId);
          console.warn('[SetupModal] Backend returned:', result.session_id);
          
          // IMMEDIATELY update the session ID to match backend
          console.log('[SetupModal] 🔄 FORCE updating session ID to match backend...');
          updateSessionId(result.session_id);
          
          console.log('[SetupModal] ✅ Session ID synchronized with backend');
          console.log('[SetupModal] New session ID:', result.session_id);
        } else {
          console.log('[SetupModal] ✅ Session IDs match - credentials should be accessible');
        }
        setConnectionStatus({
          success: true,
          message: 'Connection successful and credentials saved! Redirecting to chat...'
        });
        
        // Save to local storage for UI consistency
        const credentialsToStore = {
          url: credentials.url,
          database: credentials.database,
          username: credentials.username
        };
        localStorage.setItem('odoo_credentials', JSON.stringify(credentialsToStore));
        
        console.log('[SetupModal] Forcing credential refresh...');
        
        // If session ID was updated, we need to force a fresh check with the new session
        if (result.session_id && result.session_id !== sessionId) {
          console.log('[SetupModal] 🔄 Session ID changed, forcing fresh credential check with new session');
          // Wait a moment for the context to update
          await new Promise(resolve => setTimeout(resolve, 200));
        }
        
        // Force refresh of credential status with updated session if needed
        await refreshCredentials();
        
        // Additional verification - check if credentials are now accessible
        console.log('[SetupModal] 🔍 Verifying credentials are accessible...');
        try {
          const verifyResponse = await agentAPI.getOdooCredentials(result.session_id || sessionId);
          if (verifyResponse.success && verifyResponse.credentials) {
            console.log('[SetupModal] ✅ Credentials verified successfully');
          } else {
            console.warn('[SetupModal] ⚠️ Credentials verification failed:', verifyResponse);
          }
        } catch (verifyError) {
          console.warn('[SetupModal] ⚠️ Credentials verification error:', verifyError);
        }
        
        // Notify other components that credentials were updated
        console.log('[SetupModal] Dispatching credentialsUpdated event');
        window.dispatchEvent(new CustomEvent('credentialsUpdated'));
        localStorage.setItem('odoo_credentials_updated', Date.now().toString());
        localStorage.removeItem('odoo_credentials_updated'); // Trigger storage event
        
        console.log('[SetupModal] Completing setup in 1 second...');
        // Complete setup immediately after event dispatch to ensure redirect happens
        setTimeout(() => {
          console.log('[SetupModal] 🚀 Calling onComplete - credentials should be ready!');
          if (onComplete) {
            onComplete();
          } else {
            console.warn('[SetupModal] onComplete callback is not defined');
          }
        }, 1000); // Reduced to 1 second for faster redirect
      } else {
        setConnectionStatus({
          success: false,
          message: result.message || 'Connection test failed'
        });
      }
    } catch (error) {
      console.error('[SetupModal] Connection test error:', error);
      setConnectionStatus({
        success: false,
        message: `Connection test failed: ${error.message}`
      });
    } finally {
      setIsTestingConnection(false);
    }
  };



  const nextStep = () => {
    if (currentStep === 1) {
      const errors = validateCredentials();
      if (errors.length > 0) {
        setConnectionStatus({
          success: false,
          message: errors.join(', ')
        });
        return;
      }
      setCurrentStep(2);
      setConnectionStatus(null);
    } else if (currentStep === 2) {
      testConnection();
    }
  };

  const prevStep = () => {
    if (currentStep > 1) {
      setCurrentStep(currentStep - 1);
      setConnectionStatus(null);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
      <div className="bg-white dark:bg-gray-800 rounded-lg shadow-xl max-w-md w-full max-h-[90vh] overflow-y-auto transition-colors">
        {/* Header */}
        <div className="bg-blue-600 text-white p-6 rounded-t-lg">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <Cog6ToothIcon className="h-8 w-8" />
              <div>
                <h2 className="text-xl font-bold">Setup Required</h2>
                <p className="text-blue-100 text-sm">Configure Odoo connection to continue</p>
              </div>
            </div>
            {allowClose && onClose && (
              <button
                onClick={onClose}
                className="p-1 hover:bg-blue-700 rounded transition-colors"
                title="Close"
              >
                <XMarkIcon className="h-6 w-6" />
              </button>
            )}
          </div>
        </div>

        {/* Progress indicator - Simplified to 2 steps */}
        <div className="px-6 py-4 border-b border-gray-200 dark:border-gray-600">
          <div className="flex items-center justify-between text-sm">
            <div className={`flex items-center gap-2 ${currentStep >= 1 ? 'text-blue-600 dark:text-blue-400' : 'text-gray-400 dark:text-gray-500'}`}>
              <div className={`w-6 h-6 rounded-full flex items-center justify-center ${currentStep >= 1 ? 'bg-blue-600 text-white' : 'bg-gray-300 dark:bg-gray-600 text-gray-600 dark:text-gray-300'}`}>
                {currentStep > 1 ? <CheckCircleIcon className="h-4 w-4" /> : '1'}
              </div>
              <span>Credentials</span>
            </div>
            <div className={`w-16 h-0.5 ${currentStep >= 2 ? 'bg-blue-600' : 'bg-gray-300 dark:bg-gray-600'}`}></div>
            <div className={`flex items-center gap-2 ${currentStep >= 2 ? 'text-blue-600 dark:text-blue-400' : 'text-gray-400 dark:text-gray-500'}`}>
              <div className={`w-6 h-6 rounded-full flex items-center justify-center ${currentStep >= 2 ? 'bg-blue-600 text-white' : 'bg-gray-300 dark:bg-gray-600 text-gray-600 dark:text-gray-300'}`}>
                {connectionStatus?.success && !isTestingConnection && !isSaving ? <CheckCircleIcon className="h-4 w-4" /> : '2'}
              </div>
              <span>Test & Save</span>
            </div>
          </div>
        </div>

        {/* Content */}
        <div className="p-6">
          {currentStep === 1 && (
            <div className="space-y-4">
              <div className="text-center mb-6">
                <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-2">Enter Odoo Credentials</h3>
                <p className="text-gray-600 dark:text-gray-300 text-sm">
                  To use the AI agent, you need to configure your Odoo connection details.
                </p>
              </div>

              <div className="space-y-4">
                <div>
                  <label className="flex items-center gap-2 text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                    <ServerIcon className="h-4 w-4" />
                    Odoo URL
                  </label>
                  <input
                    type="url"
                    placeholder="https://your-odoo-instance.com"
                    value={credentials.url}
                    onChange={(e) => handleInputChange('url', e.target.value)}
                    className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md bg-white dark:bg-gray-700 text-gray-900 dark:text-white placeholder-gray-500 dark:placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                  />
                </div>

                <div>
                  <label className="flex items-center gap-2 text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                    <BuildingOfficeIcon className="h-4 w-4" />
                    Database Name
                  </label>
                  <input
                    type="text"
                    placeholder="your-database-name"
                    value={credentials.database}
                    onChange={(e) => handleInputChange('database', e.target.value)}
                    className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md bg-white dark:bg-gray-700 text-gray-900 dark:text-white placeholder-gray-500 dark:placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                  />
                </div>

                <div>
                  <label className="flex items-center gap-2 text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                    <UserIcon className="h-4 w-4" />
                    Username
                  </label>
                  <input
                    type="text"
                    placeholder="your-username"
                    value={credentials.username}
                    onChange={(e) => handleInputChange('username', e.target.value)}
                    className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md bg-white dark:bg-gray-700 text-gray-900 dark:text-white placeholder-gray-500 dark:placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                  />
                </div>

                <div>
                  <label className="flex items-center gap-2 text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                    <KeyIcon className="h-4 w-4" />
                    Password
                  </label>
                  <div className="relative">
                    <input
                      type={showPassword ? 'text' : 'password'}
                      placeholder="your-password"
                      value={credentials.password}
                      onChange={(e) => handleInputChange('password', e.target.value)}
                      className="w-full px-3 py-2 pr-10 border border-gray-300 dark:border-gray-600 rounded-md bg-white dark:bg-gray-700 text-gray-900 dark:text-white placeholder-gray-500 dark:placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                    />
                    <button
                      type="button"
                      onClick={() => setShowPassword(!showPassword)}
                      className="absolute inset-y-0 right-0 pr-3 flex items-center"
                    >
                      {showPassword ? (
                        <EyeSlashIcon className="h-4 w-4 text-gray-400 dark:text-gray-500" />
                      ) : (
                        <EyeIcon className="h-4 w-4 text-gray-400 dark:text-gray-500" />
                      )}
                    </button>
                  </div>
                </div>
              </div>
            </div>
          )}

          {currentStep === 2 && (
            <div className="space-y-4">
              <div className="text-center mb-6">
                <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-2">Test & Save Connection</h3>
                <p className="text-gray-600 dark:text-gray-300 text-sm">
                  We'll test your credentials and automatically save them if successful.
                </p>
              </div>

              <div className="bg-gray-50 dark:bg-gray-700 p-4 rounded-lg space-y-2">
                <div className="flex items-center gap-2 text-sm">
                  <ServerIcon className="h-4 w-4 text-gray-500 dark:text-gray-400" />
                  <span className="text-gray-600 dark:text-gray-300">URL:</span>
                  <span className="font-medium text-gray-900 dark:text-white">{credentials.url}</span>
                </div>
                <div className="flex items-center gap-2 text-sm">
                  <BuildingOfficeIcon className="h-4 w-4 text-gray-500 dark:text-gray-400" />
                  <span className="text-gray-600 dark:text-gray-300">Database:</span>
                  <span className="font-medium text-gray-900 dark:text-white">{credentials.database}</span>
                </div>
                <div className="flex items-center gap-2 text-sm">
                  <UserIcon className="h-4 w-4 text-gray-500 dark:text-gray-400" />
                  <span className="text-gray-600 dark:text-gray-300">Username:</span>
                  <span className="font-medium text-gray-900 dark:text-white">{credentials.username}</span>
                </div>
              </div>

              <button
                onClick={testConnection}
                disabled={isTestingConnection}
                className="w-full flex items-center justify-center gap-2 px-4 py-3 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
              >
                {isTestingConnection ? (
                  <>
                    <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin"></div>
                    Testing & Saving...
                  </>
                ) : (
                  'Test & Save Connection'
                )}
              </button>
            </div>
          )}



          {/* Status Messages */}
          {connectionStatus && (
            <div className={`mt-4 p-3 rounded-md ${
              connectionStatus.success 
                ? 'bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-800' 
                : 'bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800'
            }`}>
              <div className="flex items-center gap-2">
                {connectionStatus.success ? (
                  <CheckCircleIcon className="h-5 w-5 text-green-500 dark:text-green-400" />
                ) : (
                  <ExclamationTriangleIcon className="h-5 w-5 text-red-500 dark:text-red-400" />
                )}
                <span className={`text-sm ${
                  connectionStatus.success ? 'text-green-700 dark:text-green-300' : 'text-red-700 dark:text-red-300'
                }`}>
                  {connectionStatus.message}
                </span>
              </div>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="bg-gray-50 dark:bg-gray-700 px-6 py-4 rounded-b-lg flex justify-between">
          <button
            onClick={prevStep}
            disabled={currentStep === 1 || isTestingConnection}
            className="px-4 py-2 text-gray-600 dark:text-gray-300 hover:text-gray-800 dark:hover:text-white disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            Previous
          </button>
          
          {currentStep < 2 && (
            <button
              onClick={nextStep}
              disabled={isTestingConnection}
              className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              Next
            </button>
          )}
        </div>

        {/* Security Notice */}
        <div className="px-6 py-3 bg-amber-50 dark:bg-amber-900/20 border-t border-amber-200 dark:border-amber-800 rounded-b-lg">
          <p className="text-xs text-amber-700 dark:text-amber-300">
            🔒 Your credentials are securely stored and encrypted. They are only used to connect to your Odoo instance.
          </p>
        </div>
      </div>
    </div>
  );
};

export default SetupModal; 