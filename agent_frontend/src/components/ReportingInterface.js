import React, { useState, useEffect } from 'react';
import { useChat } from '../context/ChatContext';
import { agentAPI } from '../services/api';
import {
  ChartBarIcon,
  DocumentArrowDownIcon,
  CogIcon,
  ExclamationTriangleIcon,
  CheckCircleIcon
} from '@heroicons/react/24/outline';

const ReportingInterface = () => {
  const { sessionId, addMessage } = useChat();
  const [isLoading, setIsLoading] = useState(false);
  const [generatedFiles, setGeneratedFiles] = useState([]);
  const [agentStatus, setAgentStatus] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    loadGeneratedFiles();
    checkAgentStatus();
  }, [sessionId]);

  const loadGeneratedFiles = async () => {
    try {
      const response = await agentAPI.getReportingFiles(sessionId);
      if (response.files) {
        setGeneratedFiles(response.files);
      }
    } catch (error) {
      console.error('Failed to load generated files:', error);
    }
  };

  const checkAgentStatus = async () => {
    try {
      const response = await agentAPI.getAgentStatus();
      setAgentStatus(response);
    } catch (error) {
      console.error('Failed to check agent status:', error);
    }
  };

  const handleReportingQuery = async (query) => {
    setIsLoading(true);
    setError(null);

    try {
      const response = await agentAPI.reportingChat({
        message: query,
        session_id: sessionId
      });

      if (response.status === 'success') {
        // Add the response to chat
        addMessage({
          id: Date.now(),
          content: response.response,
          sender: 'agent',
          timestamp: new Date().toISOString(),
          files: response.files || [],
          agentType: response.agent_type
        });

        // Update generated files
        if (response.files && response.files.length > 0) {
          setGeneratedFiles(prev => [...prev, ...response.files]);
        }
      } else {
        setError(response.error || 'Failed to process reporting query');
      }
    } catch (error) {
      console.error('Reporting query error:', error);
      setError('Failed to process reporting query');
    } finally {
      setIsLoading(false);
    }
  };

  const downloadFile = async (filename) => {
    try {
      const response = await agentAPI.downloadReport(sessionId, filename);
      if (response.ok) {
        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(url);
        document.body.removeChild(a);
      }
    } catch (error) {
      console.error('Download error:', error);
      setError('Failed to download file');
    }
  };

  const formatFileSize = (bytes) => {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  };

  const formatDate = (dateString) => {
    return new Date(dateString).toLocaleString();
  };

  return (
    <div className="flex flex-col h-full bg-white dark:bg-gray-800 rounded-lg shadow-sm">
      {/* Header */}
      <div className="flex items-center justify-between p-4 border-b border-gray-200 dark:border-gray-700">
        <div className="flex items-center space-x-2">
          <ChartBarIcon className="h-6 w-6 text-blue-600" />
          <h2 className="text-lg font-semibold text-gray-900 dark:text-white">
            Reporting Agent
          </h2>
        </div>
        
        {agentStatus && (
          <div className="flex items-center space-x-2">
            {agentStatus.reporting_agent?.status === 'healthy' ? (
              <CheckCircleIcon className="h-5 w-5 text-green-500" />
            ) : (
              <ExclamationTriangleIcon className="h-5 w-5 text-yellow-500" />
            )}
            <span className="text-sm text-gray-600 dark:text-gray-400">
              {agentStatus.reporting_agent?.status || 'Unknown'}
            </span>
          </div>
        )}
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-4">
        {error && (
          <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-md">
            <div className="flex items-center">
              <ExclamationTriangleIcon className="h-5 w-5 text-red-400 mr-2" />
              <span className="text-red-800">{error}</span>
            </div>
          </div>
        )}

        {/* Quick Actions */}
        <div className="mb-6">
          <h3 className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-3">
            Quick Actions
          </h3>
          <div className="grid grid-cols-2 gap-3">
            <button
              onClick={() => handleReportingQuery("Generate a sales report for this month")}
              disabled={isLoading}
              className="p-3 text-left bg-blue-50 hover:bg-blue-100 dark:bg-blue-900/20 dark:hover:bg-blue-900/30 rounded-lg border border-blue-200 dark:border-blue-700 transition-colors"
            >
              <div className="font-medium text-blue-900 dark:text-blue-100">Sales Report</div>
              <div className="text-xs text-blue-600 dark:text-blue-400">Monthly sales data</div>
            </button>
            
            <button
              onClick={() => handleReportingQuery("Create an inventory chart")}
              disabled={isLoading}
              className="p-3 text-left bg-green-50 hover:bg-green-100 dark:bg-green-900/20 dark:hover:bg-green-900/30 rounded-lg border border-green-200 dark:border-green-700 transition-colors"
            >
              <div className="font-medium text-green-900 dark:text-green-100">Inventory Chart</div>
              <div className="text-xs text-green-600 dark:text-green-400">Stock levels visualization</div>
            </button>
            
            <button
              onClick={() => handleReportingQuery("Generate a customer analysis report")}
              disabled={isLoading}
              className="p-3 text-left bg-purple-50 hover:bg-purple-100 dark:bg-purple-900/20 dark:hover:bg-purple-900/30 rounded-lg border border-purple-200 dark:border-purple-700 transition-colors"
            >
              <div className="font-medium text-purple-900 dark:text-purple-100">Customer Analysis</div>
              <div className="text-xs text-purple-600 dark:text-purple-400">Customer insights</div>
            </button>
            
            <button
              onClick={() => handleReportingQuery("Create a financial dashboard")}
              disabled={isLoading}
              className="p-3 text-left bg-orange-50 hover:bg-orange-100 dark:bg-orange-900/20 dark:hover:bg-orange-900/30 rounded-lg border border-orange-200 dark:border-orange-700 transition-colors"
            >
              <div className="font-medium text-orange-900 dark:text-orange-100">Financial Dashboard</div>
              <div className="text-xs text-orange-600 dark:text-orange-400">Financial overview</div>
            </button>
          </div>
        </div>

        {/* Generated Files */}
        {generatedFiles.length > 0 && (
          <div>
            <h3 className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-3">
              Generated Files
            </h3>
            <div className="space-y-2">
              {generatedFiles.map((file, index) => (
                <div
                  key={index}
                  className="flex items-center justify-between p-3 bg-gray-50 dark:bg-gray-700 rounded-lg border border-gray-200 dark:border-gray-600"
                >
                  <div className="flex items-center space-x-3">
                    <DocumentArrowDownIcon className="h-5 w-5 text-gray-400" />
                    <div>
                      <div className="font-medium text-gray-900 dark:text-white">
                        {file.filename}
                      </div>
                      <div className="text-xs text-gray-500 dark:text-gray-400">
                        {formatFileSize(file.size)} • {formatDate(file.created)}
                      </div>
                    </div>
                  </div>
                  
                  <button
                    onClick={() => downloadFile(file.filename)}
                    className="px-3 py-1 text-sm bg-blue-600 hover:bg-blue-700 text-white rounded-md transition-colors"
                  >
                    Download
                  </button>
                </div>
              ))}
            </div>
          </div>
        )}

        {isLoading && (
          <div className="flex items-center justify-center py-8">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
            <span className="ml-3 text-gray-600 dark:text-gray-400">
              Processing your request...
            </span>
          </div>
        )}
      </div>

      {/* Footer */}
      <div className="p-4 border-t border-gray-200 dark:border-gray-700">
        <div className="text-xs text-gray-500 dark:text-gray-400">
          The Reporting Agent can generate PDF reports, create charts, and perform CRUD operations.
          Make sure your Odoo credentials are configured in the settings.
        </div>
      </div>
    </div>
  );
};

export default ReportingInterface; 