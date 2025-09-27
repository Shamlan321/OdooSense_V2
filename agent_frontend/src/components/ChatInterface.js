import React, { useState, useRef, useEffect } from 'react';
import { useChat } from '../context/ChatContext';
import { agentAPI } from '../services/api';
import MessageList from './MessageList';
import MessageInput from './MessageInput';
import FileUpload from './FileUpload';
import StatusIndicator from './StatusIndicator';
import { PaperClipIcon, XMarkIcon, ExclamationTriangleIcon } from '@heroicons/react/24/outline';

const ChatInterface = () => {
  const {
    messages,
    isLoading,
    error,
    uploadedFile,
    agentStatus,
    addMessage,
    setLoading,
    setError,
    setUploadedFile,
    clearUploadedFile,
    setAgentStatus
  } = useChat();

  const [showFileUpload, setShowFileUpload] = useState(false);
  const [documentType, setDocumentType] = useState('');
  const messagesEndRef = useRef(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const handleSendMessage = async (message) => {
    if (!message.trim() && !uploadedFile) return;

    // Add user message
    const userMessage = {
      id: Date.now(),
      role: 'user',
      content: message,
      timestamp: new Date(),
      file: uploadedFile ? {
        name: uploadedFile.name,
        type: uploadedFile.type,
        size: uploadedFile.size
      } : null
    };

    addMessage(userMessage);
    setLoading(true);
    setAgentStatus('processing');
    setError(null);

    try {
      // Handle file upload first if there's a file
      if (uploadedFile) {
        try {
          // First upload in preview mode
          const uploadResult = await agentAPI.uploadDocument(
            uploadedFile, 
            null, // No session ID needed - auth handled by backend
            documentType || null,
            null,
            true // preview mode
          );
          
          if (uploadResult.extracted_data) {
            // Add preview message to chat
            const previewMessage = {
              id: Date.now(),
              role: 'assistant',
              content: 'Document processed successfully. Please review the extracted data below:',
              timestamp: new Date(),
              isPreview: true,
              previewData: {
                extractedData: uploadResult.extracted_data,
                filename: uploadedFile.name,
                documentType: documentType
              }
            };
            addMessage(previewMessage);
            clearUploadedFile();
            setDocumentType('');
            setLoading(false);
            setAgentStatus('idle');
            return; // Don't send the message yet
          } else {
            // Fallback to normal processing if no extracted data
            clearUploadedFile();
            setDocumentType('');
          }
        } catch (uploadError) {
          console.error('File upload failed:', uploadError);
          // Continue with text message if file upload fails
          clearUploadedFile();
          setDocumentType('');
        }
      }

      // Send message to agent
      setAgentStatus('responding');
      const response = await agentAPI.sendMessage(message);
      
      // Add agent response
      const agentMessage = {
        id: Date.now() + 1,
        role: 'assistant',
        content: response.response || 'I encountered an issue processing your request.',
        timestamp: new Date(),
        files: response.files || [],
        htmlContent: response.html_content || null,
        agentType: response.agent_type || 'main_agent',
        sessionId: response.session_id // Capture session ID for file downloads
      };

      addMessage(agentMessage);
      setAgentStatus('idle');
    } catch (error) {
      console.error('Send message failed:', error);
      
      // Handle authentication errors
      if (error.message.includes('Authentication required') || error.message.includes('unauthenticated')) {
        setError('Your session has expired. Please refresh the page to log in again.');
        // Note: The AuthGuard will handle showing the auth dialog when the user refreshes
      } else {
        setError(error.message || 'Failed to send message');
      }
      
      setAgentStatus('error');
    } finally {
      setLoading(false);
    }
  };

  const handleFileSelect = (file) => {
    setUploadedFile(file);
    setShowFileUpload(false);
  };

  const handlePreviewConfirm = async (result) => {
    try {
      // Add success message
      const successMessage = {
        id: Date.now(),
        role: 'assistant',
        content: result.message || 'Document data has been successfully added to Odoo.',
        timestamp: new Date()
      };
      
      addMessage(successMessage);
      
    } catch (error) {
      console.error('Failed to process confirmed data:', error);
      setError(`Failed to process data: ${error.message}`);
    }
  };

  const handlePreviewCancel = () => {
    // Add cancellation message
    const cancelMessage = {
      id: Date.now(),
      role: 'assistant',
      content: 'Document processing cancelled.',
      timestamp: new Date()
    };
    
    addMessage(cancelMessage);
  };

  const handleRemoveFile = () => {
    clearUploadedFile();
    setDocumentType('');
  };

  const documentTypes = [
    { value: '', label: 'Auto-detect' },
    { value: 'bill', label: 'Bill/Invoice' },
    { value: 'expense', label: 'Expense Receipt' },
    { value: 'lead', label: 'Lead/Contact' },
    { value: 'contact', label: 'Contact Information' }
  ];

  return (
    <div className="flex flex-col h-full bg-white dark:bg-gray-900 transition-colors">
      {/* Header with status */}
      <div className="border-b border-gray-200 dark:border-gray-700 p-4">
        <div className="flex items-center justify-between">
          <h1 className="text-xl font-semibold text-gray-900 dark:text-white">
            Odoo AI Agent
          </h1>
          <StatusIndicator status={agentStatus} />
        </div>
        
        {error && (
          <div className="mt-2 p-3 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-md">
            <p className="text-sm text-red-600 dark:text-red-400">{error}</p>
          </div>
        )}
      </div>

      {/* Messages area */}
      <div className="flex-1 overflow-y-auto p-4">
        <MessageList
          messages={messages}
          isLoading={isLoading}
          agentStatus={agentStatus}
          onPreviewConfirm={handlePreviewConfirm}
          onPreviewCancel={handlePreviewCancel}
        />
        <div ref={messagesEndRef} />
      </div>

      {/* File upload area */}
      {uploadedFile && (
        <div className="border-t border-gray-200 dark:border-gray-700 p-4 bg-gray-50 dark:bg-gray-800">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-3">
              <PaperClipIcon className="h-5 w-5 text-gray-400 dark:text-gray-500" />
              <div>
                <p className="text-sm font-medium text-gray-900 dark:text-white">
                  {uploadedFile.name}
                </p>
                <p className="text-xs text-gray-500 dark:text-gray-400">
                  {(uploadedFile.size / 1024 / 1024).toFixed(2)} MB
                </p>
              </div>
            </div>
            <div className="flex items-center space-x-3">
              <select
                value={documentType}
                onChange={(e) => setDocumentType(e.target.value)}
                className="text-sm border border-gray-300 rounded-md px-2 py-1"
              >
                {documentTypes.map((type) => (
                  <option key={type.value} value={type.value}>
                    {type.label}
                  </option>
                ))}
              </select>
              <button
                onClick={handleRemoveFile}
                className="p-1 text-gray-400 hover:text-gray-600"
              >
                <XMarkIcon className="h-4 w-4" />
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Input area */}
      <div className="border-t border-gray-200 p-4">
        <MessageInput
          onSendMessage={handleSendMessage}
          disabled={isLoading}
          onAttachFile={() => setShowFileUpload(true)}
          hasFile={!!uploadedFile}
        />
      </div>

      {/* File upload modal */}
      {showFileUpload && (
        <FileUpload
          onFileSelect={handleFileSelect}
          onClose={() => setShowFileUpload(false)}
        />
      )}
    </div>
  );
};

export default ChatInterface;