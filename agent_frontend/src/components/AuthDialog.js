import React, { useState } from 'react';
import { useAuth } from '../context/AuthContext';
import {
  EyeIcon,
  EyeSlashIcon,
  ServerIcon,
  BuildingOfficeIcon,
  UserIcon,
  KeyIcon,
  CheckCircleIcon,
  ExclamationTriangleIcon
} from '@heroicons/react/24/outline';

const AuthDialog = () => {
  const { authenticate, isLoading, error, clearError } = useAuth();
  
  const [credentials, setCredentials] = useState({
    url: '',
    database: '',
    username: '',
    password: ''
  });
  
  const [showPassword, setShowPassword] = useState(false);
  const [validationErrors, setValidationErrors] = useState([]);
  const [status, setStatus] = useState(null); // { type: 'success'|'error', message: string }

  const handleInputChange = (field, value) => {
    setCredentials(prev => ({
      ...prev,
      [field]: value
    }));
    
    // Clear validation errors when user starts typing
    if (validationErrors.length > 0) {
      setValidationErrors([]);
    }
    
    // Clear status when user modifies inputs
    if (status) {
      setStatus(null);
    }
    
    // Clear context error
    if (error) {
      clearError();
    }
  };

  const validateCredentials = () => {
    const errors = [];
    
    if (!credentials.url.trim()) {
      errors.push('Odoo URL is required');
    } else {
      // Basic URL validation
      try {
        new URL(credentials.url.trim());
      } catch (e) {
        errors.push('Please enter a valid URL (e.g., https://your-odoo-instance.com)');
      }
    }
    
    if (!credentials.database.trim()) {
      errors.push('Database name is required');
    }
    
    if (!credentials.username.trim()) {
      errors.push('Username is required');
    }
    
    if (!credentials.password.trim()) {
      errors.push('Password is required');
    }
    
    return errors;
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    
    // Clear previous status
    setStatus(null);
    clearError();
    
    // Validate inputs
    const errors = validateCredentials();
    if (errors.length > 0) {
      setValidationErrors(errors);
      return;
    }
    
    setValidationErrors([]);
    
    // Prepare credentials (trim whitespace)
    const trimmedCredentials = {
      url: credentials.url.trim(),
      database: credentials.database.trim(),
      username: credentials.username.trim(),
      password: credentials.password.trim()
    };
    
    try {
      const result = await authenticate(trimmedCredentials);
      
      if (result.success) {
        setStatus({
          type: 'success',
          message: result.message || 'Authentication successful! Welcome to OdooSense.'
        });
        // Note: The AuthContext will handle the state change and the dialog will disappear
      } else {
        setStatus({
          type: 'error',
          message: result.message || 'Authentication failed. Please check your credentials.'
        });
      }
    } catch (error) {
      setStatus({
        type: 'error',
        message: error.message || 'An unexpected error occurred. Please try again.'
      });
    }
  };

  const getUrlPlaceholder = () => {
    return 'https://your-odoo-instance.com';
  };

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
      <div className="bg-white dark:bg-gray-800 rounded-xl shadow-2xl max-w-md w-full transition-colors">
        {/* Header */}
        <div className="bg-gradient-to-r from-blue-600 to-blue-700 text-white p-6 rounded-t-xl">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 bg-white bg-opacity-20 rounded-full flex items-center justify-center">
              <ServerIcon className="h-6 w-6" />
            </div>
            <div>
              <h2 className="text-xl font-bold">Welcome to OdooSense</h2>
              <p className="text-blue-100 text-sm">Connect to your Odoo instance to get started</p>
            </div>
          </div>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit} className="p-6 space-y-4">
          {/* Odoo URL */}
          <div>
            <label className="flex items-center gap-2 text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
              <ServerIcon className="h-4 w-4" />
              Odoo URL
            </label>
            <input
              type="url"
              placeholder={getUrlPlaceholder()}
              value={credentials.url}
              onChange={(e) => handleInputChange('url', e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent dark:bg-gray-700 dark:text-white transition-colors"
              disabled={isLoading}
            />
          </div>

          {/* Database */}
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
              className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent dark:bg-gray-700 dark:text-white transition-colors"
              disabled={isLoading}
            />
          </div>

          {/* Username */}
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
              className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent dark:bg-gray-700 dark:text-white transition-colors"
              disabled={isLoading}
            />
          </div>

          {/* Password */}
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
                className="w-full px-3 py-2 pr-10 border border-gray-300 dark:border-gray-600 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent dark:bg-gray-700 dark:text-white transition-colors"
                disabled={isLoading}
              />
              <button
                type="button"
                onClick={() => setShowPassword(!showPassword)}
                className="absolute inset-y-0 right-0 pr-3 flex items-center text-gray-400 hover:text-gray-600 dark:hover:text-gray-300"
                disabled={isLoading}
              >
                {showPassword ? (
                  <EyeSlashIcon className="h-4 w-4" />
                ) : (
                  <EyeIcon className="h-4 w-4" />
                )}
              </button>
            </div>
          </div>

          {/* Submit Button */}
          <button
            type="submit"
            disabled={isLoading}
            className="w-full flex items-center justify-center gap-2 px-4 py-3 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors font-medium"
          >
            {isLoading ? (
              <>
                <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin"></div>
                Testing Connection...
              </>
            ) : (
              'Connect to Odoo'
            )}
          </button>

          {/* Validation Errors */}
          {validationErrors.length > 0 && (
            <div className="bg-red-50 border border-red-200 rounded-md p-3">
              <div className="flex items-start gap-2">
                <ExclamationTriangleIcon className="h-5 w-5 text-red-500 mt-0.5 flex-shrink-0" />
                <div className="text-sm text-red-700">
                  <p className="font-medium mb-1">Please fix the following issues:</p>
                  <ul className="space-y-1">
                    {validationErrors.map((error, index) => (
                      <li key={index} className="flex items-center gap-1">
                        <span className="w-1 h-1 bg-red-500 rounded-full"></span>
                        {error}
                      </li>
                    ))}
                  </ul>
                </div>
              </div>
            </div>
          )}

          {/* Status Messages */}
          {status && (
            <div className={`rounded-md p-3 ${
              status.type === 'success' 
                ? 'bg-green-50 border border-green-200' 
                : 'bg-red-50 border border-red-200'
            }`}>
              <div className="flex items-center gap-2">
                {status.type === 'success' ? (
                  <CheckCircleIcon className="h-5 w-5 text-green-500" />
                ) : (
                  <ExclamationTriangleIcon className="h-5 w-5 text-red-500" />
                )}
                <span className={`text-sm ${
                  status.type === 'success' ? 'text-green-700' : 'text-red-700'
                }`}>
                  {status.message}
                </span>
              </div>
            </div>
          )}

          {/* Context Error */}
          {error && (
            <div className="bg-red-50 border border-red-200 rounded-md p-3">
              <div className="flex items-center gap-2">
                <ExclamationTriangleIcon className="h-5 w-5 text-red-500" />
                <span className="text-sm text-red-700">{error}</span>
              </div>
            </div>
          )}
        </form>

        {/* Footer */}
        <div className="bg-gray-50 dark:bg-gray-700 px-6 py-4 rounded-b-xl">
          <div className="flex items-center gap-2 text-xs text-gray-600 dark:text-gray-400">
            <div className="w-3 h-3 bg-green-500 rounded-full flex items-center justify-center">
              <div className="w-1.5 h-1.5 bg-white rounded-full"></div>
            </div>
            <span>Your credentials are securely encrypted and stored on the server</span>
          </div>
        </div>
      </div>
    </div>
  );
};

export default AuthDialog; 