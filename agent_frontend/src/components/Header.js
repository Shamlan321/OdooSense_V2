import React, { useState, useEffect } from 'react';
import { useChat } from '../context/ChatContext';
import { useAuth } from '../context/AuthContext';
import { useTheme } from '../context/ThemeContext';
import { agentAPI } from '../services/api';

import { 
  InformationCircleIcon,
  ArrowPathIcon,
  CheckCircleIcon,
  XCircleIcon,
  ShieldCheckIcon,
  ExclamationTriangleIcon,
  SunIcon,
  MoonIcon,
  ArrowRightOnRectangleIcon,
  UserIcon
} from '@heroicons/react/24/outline';

const Header = () => {
  const { newSession, clearMessages } = useChat();
  const { credentials, logout } = useAuth();
  const { isDarkMode, toggleTheme } = useTheme();
  const [agentInfo, setAgentInfo] = useState(null);
  const [healthStatus, setHealthStatus] = useState(null);
  const [showInfo, setShowInfo] = useState(false);
  const [isCheckingHealth, setIsCheckingHealth] = useState(false);
  const [isLoggingOut, setIsLoggingOut] = useState(false);

  useEffect(() => {
    checkAgentHealth();
    fetchAgentInfo();
  }, []);

  const checkAgentHealth = async () => {
    setIsCheckingHealth(true);
    try {
      const health = await agentAPI.checkHealth();
      setHealthStatus(health);
    } catch (error) {
      setHealthStatus({ status: 'error', message: error.message });
    } finally {
      setIsCheckingHealth(false);
    }
  };

  const fetchAgentInfo = async () => {
    try {
      const info = await agentAPI.getAgentInfo();
      setAgentInfo(info);
    } catch (error) {
      console.error('Failed to fetch agent info:', error);
    }
  };

  const handleNewSession = () => {
    newSession();
    clearMessages();
  };

  const handleLogout = async () => {
    setIsLoggingOut(true);
    try {
      await logout();
      // Clear messages on logout
      clearMessages();
    } catch (error) {
      console.error('Logout failed:', error);
    } finally {
      setIsLoggingOut(false);
    }
  };

  const getConnectionDisplay = () => {
    if (credentials) {
      return (
        <div className="flex items-center gap-2 text-sm">
          <div className="flex items-center gap-1">
            <CheckCircleIcon className="h-4 w-4 text-green-500" />
            <span className="text-green-600 dark:text-green-400 font-medium">Connected</span>
          </div>
          <span className="text-gray-400">•</span>
          <span className="text-gray-600 dark:text-gray-300">{credentials.database}</span>
          <span className="text-gray-400">•</span>
          <span className="text-gray-600 dark:text-gray-300">{credentials.username}</span>
        </div>
      );
    }
    return (
      <div className="flex items-center gap-1 text-sm">
        <XCircleIcon className="h-4 w-4 text-red-500" />
        <span className="text-red-600 dark:text-red-400">Not Connected</span>
      </div>
    );
  };

  const getHealthStatusIcon = () => {
    if (isCheckingHealth) {
      return <ArrowPathIcon className="w-5 h-5 animate-spin" />;
    }
    
    if (healthStatus?.status === 'healthy') {
      return <CheckCircleIcon className="w-5 h-5 text-green-500" />;
    }
    
    return <XCircleIcon className="w-5 h-5 text-red-500" />;
  };

  return (
    <>
      <header className="bg-white dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700 px-6 py-4 transition-colors">
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-4">
            <h1 className="text-xl font-bold text-gray-900 dark:text-white">
              Odoo AI Agent
            </h1>
            {agentInfo?.version && (
              <span className="text-sm text-gray-500 dark:text-gray-400 bg-gray-100 dark:bg-gray-700 px-2 py-1 rounded">
                v{agentInfo.version}
              </span>
            )}
          </div>

          <div className="flex items-center space-x-3">
            {/* Connection status */}
            <div className="flex items-center space-x-2 px-3 py-1 rounded-lg bg-gray-50 dark:bg-gray-700">
              <UserIcon className="h-4 w-4 text-gray-500 dark:text-gray-400" />
              {getConnectionDisplay()}
            </div>

            {/* Health status */}
            <button
              onClick={checkAgentHealth}
              className="flex items-center space-x-2 px-3 py-1 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors"
              title="Check agent health"
            >
              {getHealthStatusIcon()}
              <span className="text-sm text-gray-600 dark:text-gray-300">
                {isCheckingHealth ? 'Checking...' : healthStatus?.status || 'Unknown'}
              </span>
            </button>

            {/* Theme toggle */}
            <button
              onClick={toggleTheme}
              className="p-2 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors"
              title={isDarkMode ? 'Switch to light mode' : 'Switch to dark mode'}
            >
              {isDarkMode ? (
                <SunIcon className="w-5 h-5 text-gray-600 dark:text-gray-300" />
              ) : (
                <MoonIcon className="w-5 h-5 text-gray-600 dark:text-gray-300" />
              )}
            </button>

            {/* New session */}
            <button
              onClick={handleNewSession}
              className="px-3 py-2 text-sm bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
              title="Start new session"
            >
              New Session
            </button>

            {/* Logout */}
            <button
              onClick={handleLogout}
              disabled={isLoggingOut}
              className="flex items-center gap-2 px-3 py-2 text-sm bg-gray-600 text-white rounded-lg hover:bg-gray-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
              title="Logout"
            >
              {isLoggingOut ? (
                <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin"></div>
              ) : (
                <ArrowRightOnRectangleIcon className="w-4 h-4" />
              )}
              {isLoggingOut ? 'Logging out...' : 'Logout'}
            </button>

            {/* Info button */}
            <button
              onClick={() => setShowInfo(!showInfo)}
              className="p-2 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors"
              title="Agent information"
            >
              <InformationCircleIcon className="w-5 h-5 text-gray-600 dark:text-gray-300" />
            </button>
          </div>
        </div>

        {/* Info panel */}
        {showInfo && (
          <div className="mt-4 p-4 bg-gray-50 dark:bg-gray-700 rounded-lg border border-gray-200 dark:border-gray-600">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-sm">
              <div>
                <h3 className="font-semibold text-gray-900 dark:text-white mb-2">Agent Information</h3>
                {agentInfo ? (
                  <div className="space-y-1 text-gray-600 dark:text-gray-300">
                    <p><span className="font-medium">API Title:</span> {agentInfo.api_title}</p>
                    <p><span className="font-medium">Version:</span> {agentInfo.version}</p>
                    <p><span className="font-medium">Description:</span> {agentInfo.description}</p>
                  </div>
                ) : (
                  <p className="text-gray-500 dark:text-gray-400">Loading agent information...</p>
                )}
              </div>
              
              <div>
                <h3 className="font-semibold text-gray-900 dark:text-white mb-2">Connection Details</h3>
                {credentials ? (
                  <div className="space-y-1 text-gray-600 dark:text-gray-300">
                    <p><span className="font-medium">URL:</span> {credentials.url}</p>
                    <p><span className="font-medium">Database:</span> {credentials.database}</p>
                    <p><span className="font-medium">Username:</span> {credentials.username}</p>
                    <p><span className="font-medium">Status:</span> <span className="text-green-600 dark:text-green-400">Connected</span></p>
                  </div>
                ) : (
                  <div className="space-y-1 text-gray-600 dark:text-gray-300">
                    <p className="text-red-600 dark:text-red-400">No active connection</p>
                  </div>
                )}
              </div>
              
              <div>
                <h3 className="font-semibold text-gray-900 dark:text-white mb-2">Health Status</h3>
                {healthStatus ? (
                  <div className="space-y-1 text-gray-600 dark:text-gray-300">
                    <p><span className="font-medium">Status:</span> 
                      <span className={healthStatus.status === 'healthy' ? 'text-green-600 dark:text-green-400' : 'text-red-600 dark:text-red-400'}>
                        {' '}{healthStatus.status}
                      </span>
                    </p>
                    {healthStatus.message && <p><span className="font-medium">Message:</span> {healthStatus.message}</p>}
                  </div>
                ) : (
                  <p className="text-gray-500 dark:text-gray-400">No health information available</p>
                )}
              </div>
            </div>
          </div>
        )}
      </header>
    </>
  );
};

export default Header;