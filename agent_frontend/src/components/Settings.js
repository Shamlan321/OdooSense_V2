import React, { useState, useEffect } from 'react';
import { agentAPI } from '../services/api';
import { useChat } from '../context/ChatContext';
import {
  XMarkIcon,
  CheckCircleIcon,
  ExclamationTriangleIcon,
  EyeIcon,
  EyeSlashIcon
} from '@heroicons/react/24/outline';

const Settings = ({ isOpen, onClose }) => {
  const { sessionId } = useChat();
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

  useEffect(() => {
    if (isOpen) {
      loadSavedCredentials();
    }
  }, [isOpen]);

  const loadSavedCredentials = () => {
    // Load credentials from localStorage
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

  const testConnection = async () => {
    if (!credentials.url || !credentials.database || !credentials.username || !credentials.password) {
      setConnectionStatus({
        success: false,
        message: 'Please fill in all required fields'
      });
      return;
    }

    setIsTestingConnection(true);
    setConnectionStatus(null);

    try {
      const result = await agentAPI.testOdooConnection(credentials);
      setConnectionStatus(result);
    } catch (error) {
      setConnectionStatus({
        success: false,
        message: `Connection test failed: ${error.message}`
      });
    } finally {
      setIsTestingConnection(false);
    }
  };

  const saveCredentials = async () => {
    if (!credentials.url || !credentials.database || !credentials.username || !credentials.password) {
      setConnectionStatus({
        success: false,
        message: 'Please fill in all required fields'
      });
      return;
    }

    setIsSaving(true);

    try {
      // Test connection first
      const testResult = await agentAPI.testOdooConnection(credentials);
      
      if (testResult.success) {
        // Save credentials to backend AgentService for the current session
        await agentAPI.saveOdooCredentials(sessionId, credentials);
        
        // Save credentials to localStorage (without password for security)
        const credentialsToSave = {
          url: credentials.url,
          database: credentials.database,
          username: credentials.username
        };
        localStorage.setItem('odoo_credentials', JSON.stringify(credentialsToSave));
        
        // Save credentials to session storage for current session
        sessionStorage.setItem('odoo_session_credentials', JSON.stringify(credentials));
        
        setConnectionStatus({
          success: true,
          message: 'Credentials saved successfully!'
        });
        
        // Close modal after successful save
        setTimeout(() => {
          onClose();
        }, 1500);
      } else {
        setConnectionStatus(testResult);
      }
    } catch (error) {
      setConnectionStatus({
        success: false,
        message: `Failed to save credentials: ${error.message}`
      });
    } finally {
      setIsSaving(false);
    }
  };

  const clearCredentials = () => {
    setCredentials({
      url: '',
      database: '',
      username: '',
      password: ''
    });
    setConnectionStatus(null);
    localStorage.removeItem('odoo_credentials');
    sessionStorage.removeItem('odoo_session_credentials');
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg shadow-xl max-w-md w-full mx-4 max-h-[90vh] overflow-y-auto">
        <div className="flex items-center justify-between p-6 border-b border-gray-200">
          <h3 className="text-lg font-semibold text-gray-900">
            Odoo Connection Settings
          </h3>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-gray-600"
          >
            <XMarkIcon className="w-6 h-6" />
          </button>
        </div>
        
        <div className="p-6 space-y-4">
          {/* URL Field */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Odoo URL *
            </label>
            <input
              type="url"
              value={credentials.url}
              onChange={(e) => handleInputChange('url', e.target.value)}
              placeholder="https://your-odoo-instance.com"
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            />
          </div>

          {/* Database Field */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Database Name *
            </label>
            <input
              type="text"
              value={credentials.database}
              onChange={(e) => handleInputChange('database', e.target.value)}
              placeholder="your-database-name"
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            />
          </div>

          {/* Username Field */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Username *
            </label>
            <input
              type="text"
              value={credentials.username}
              onChange={(e) => handleInputChange('username', e.target.value)}
              placeholder="your-username"
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            />
          </div>

          {/* Password Field */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Password *
            </label>
            <div className="relative">
              <input
                type={showPassword ? 'text' : 'password'}
                value={credentials.password}
                onChange={(e) => handleInputChange('password', e.target.value)}
                placeholder="your-password"
                className="w-full px-3 py-2 pr-10 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              />
              <button
                type="button"
                onClick={() => setShowPassword(!showPassword)}
                className="absolute inset-y-0 right-0 pr-3 flex items-center text-gray-400 hover:text-gray-600"
              >
                {showPassword ? (
                  <EyeSlashIcon className="w-5 h-5" />
                ) : (
                  <EyeIcon className="w-5 h-5" />
                )}
              </button>
            </div>
          </div>

          {/* Connection Status */}
          {connectionStatus && (
            <div className={`p-3 rounded-md flex items-start space-x-2 ${
              connectionStatus.success 
                ? 'bg-green-50 border border-green-200' 
                : 'bg-red-50 border border-red-200'
            }`}>
              {connectionStatus.success ? (
                <CheckCircleIcon className="w-5 h-5 text-green-500 mt-0.5 flex-shrink-0" />
              ) : (
                <ExclamationTriangleIcon className="w-5 h-5 text-red-500 mt-0.5 flex-shrink-0" />
              )}
              <div className="flex-1">
                <p className={`text-sm font-medium ${
                  connectionStatus.success ? 'text-green-800' : 'text-red-800'
                }`}>
                  {connectionStatus.success ? 'Connection Successful!' : 'Connection Failed'}
                </p>
                <p className={`text-sm mt-1 ${
                  connectionStatus.success ? 'text-green-700' : 'text-red-700'
                }`}>
                  {connectionStatus.message}
                </p>
                {connectionStatus.success && connectionStatus.user_info && (
                  <p className="text-sm text-green-600 mt-1">
                    Connected as: {connectionStatus.user_info.name}
                  </p>
                )}
              </div>
            </div>
          )}

          {/* Action Buttons */}
          <div className="flex space-x-3 pt-4">
            <button
              onClick={testConnection}
              disabled={isTestingConnection}
              className="flex-1 px-4 py-2 text-sm font-medium text-blue-600 bg-blue-50 border border-blue-200 rounded-md hover:bg-blue-100 focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {isTestingConnection ? 'Testing...' : 'Test Connection'}
            </button>
            
            <button
              onClick={clearCredentials}
              className="px-4 py-2 text-sm font-medium text-gray-600 bg-gray-50 border border-gray-200 rounded-md hover:bg-gray-100 focus:outline-none focus:ring-2 focus:ring-gray-500"
            >
              Clear
            </button>
          </div>

          <button
            onClick={saveCredentials}
            disabled={isSaving || !connectionStatus?.success}
            className="w-full px-4 py-2 text-sm font-medium text-white bg-blue-600 border border-transparent rounded-md hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {isSaving ? 'Saving...' : 'Save Credentials'}
          </button>

          <p className="text-xs text-gray-500 text-center">
            * Required fields. Passwords are not stored permanently for security.
          </p>
        </div>
      </div>
    </div>
  );
};

export default Settings;