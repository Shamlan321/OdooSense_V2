import React from 'react';
import ReactMarkdown from 'react-markdown';
import { UserIcon, CpuChipIcon, PaperClipIcon, ArrowTopRightOnSquareIcon } from '@heroicons/react/24/outline';
import DocumentPreview from './DocumentPreview';
import FileAttachments from './FileAttachments';
import InteractiveChart from './InteractiveChart';
import ThinkingAnimation from './ThinkingAnimation';
import './ThinkingAnimation.css';

const MessageList = ({ messages, isLoading, agentStatus, onPreviewConfirm, onPreviewCancel }) => {
  const formatTimestamp = (timestamp) => {
    return new Date(timestamp).toLocaleTimeString([], {
      hour: '2-digit',
      minute: '2-digit'
    });
  };

  // Custom component for navigation buttons
  const NavigationButton = ({ href, children, title }) => {
    const isOdooLink = href && (href.includes('/web#') || href.includes('action='));
    
    if (isOdooLink) {
      return (
        <a
          href={href}
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex items-center px-4 py-2 mr-2 mb-2 text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 rounded-lg border border-transparent shadow-sm transition-colors duration-200 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2"
          title={title}
        >
          <span className="mr-2">{children}</span>
          <ArrowTopRightOnSquareIcon className="w-4 h-4" />
        </a>
      );
    }
    
    // Regular link
    return (
      <a
        href={href}
        target="_blank"
        rel="noopener noreferrer"
        className="text-blue-600 hover:text-blue-800 underline"
        title={title}
      >
        {children}
      </a>
    );
  };

  // Custom renderer for markdown links
  const LinkRenderer = ({ href, children, title }) => {
    const linkText = children?.[0] || '';
    
    // Check if this is part of a Quick Actions section
    const parentText = title || '';
    const isQuickAction = parentText.includes('Quick Actions') || 
                          linkText.toString().match(/^[🛒📄📋👤👥📦🧾📑📄📊🚚🎯💼🛍️👨‍💼💳⚙️]/);
    
    if (isQuickAction || (href && href.includes('/web#'))) {
      return <NavigationButton href={href} title={title}>{children}</NavigationButton>;
    }
    
    // For reference links (numbered), render as compact inline links
    if (linkText.match(/^\d+$/)) {
      return (
        <a
          href={href}
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex items-center px-1 py-0.5 text-xs font-medium text-blue-600 hover:text-blue-800 dark:text-blue-400 dark:hover:text-blue-300 bg-blue-50 hover:bg-blue-100 dark:bg-blue-900/30 dark:hover:bg-blue-900/50 rounded border border-blue-200 dark:border-blue-700 transition-colors duration-200 ml-1"
          title={title || href}
        >
          {children}
        </a>
      );
    }
    
    return <NavigationButton href={href} title={title}>{children}</NavigationButton>;
  };

  const MessageBubble = ({ message }) => {
    const isUser = message.role === 'user';
    const isError = message.isError;
    
    return (
      <div className={`flex ${isUser ? 'justify-end' : 'justify-start'} mb-4`}>
        <div className={`flex max-w-3xl ${isUser ? 'flex-row-reverse' : 'flex-row'}`}>
          {/* Avatar */}
          <div className={`flex-shrink-0 ${isUser ? 'ml-3' : 'mr-3'}`}>
            <div className={`w-8 h-8 rounded-full flex items-center justify-center ${
              isUser 
                ? 'bg-blue-500 text-white' 
                : isError 
                  ? 'bg-red-500 text-white'
                  : 'bg-gray-500 text-white'
            }`}>
              {isUser ? (
                <UserIcon className="w-5 h-5" />
              ) : (
                <CpuChipIcon className="w-5 h-5" />
              )}
            </div>
          </div>

          {/* Message content */}
          <div className={`flex flex-col ${isUser ? 'items-end' : 'items-start'}`}>
            <div className={`rounded-lg px-4 py-2 max-w-full ${
              isUser
                ? 'bg-blue-500 text-white dark:bg-blue-600'
                : isError
                  ? 'bg-red-50 border border-red-200 text-red-800 dark:bg-red-900/20 dark:border-red-800 dark:text-red-400'
                  : 'bg-gray-100 text-gray-900 dark:bg-gray-800 dark:text-gray-100'
            }`}>
              {/* File attachment indicator */}
              {message.file && (
                <div className={`flex items-center space-x-2 mb-2 pb-2 border-b ${
                  isUser ? 'border-blue-400 dark:border-blue-300' : 'border-gray-300 dark:border-gray-600'
                }`}>
                  <PaperClipIcon className="w-4 h-4" />
                  <span className="text-sm">
                    {message.file.name} ({(message.file.size / 1024 / 1024).toFixed(2)} MB)
                  </span>
                </div>
              )}

              {/* Message text */}
              <div className="prose prose-sm max-w-none">
                {isUser ? (
                  <p className="whitespace-pre-wrap">{message.content}</p>
                ) : (
                  <ReactMarkdown
                    components={{
                      p: ({ children }) => <p className="mb-2 last:mb-0">{children}</p>,
                      ul: ({ children }) => <ul className="list-disc list-inside mb-2">{children}</ul>,
                      ol: ({ children }) => <ol className="list-decimal list-inside mb-2">{children}</ol>,
                      li: ({ children }) => <li className="mb-1">{children}</li>,
                      a: LinkRenderer,
                      code: ({ children, inline }) => 
                        inline ? (
                          <code className="bg-gray-200 dark:bg-gray-700 px-1 py-0.5 rounded text-sm">{children}</code>
                        ) : (
                          <pre className="bg-gray-200 dark:bg-gray-700 p-2 rounded text-sm overflow-x-auto">
                            <code>{children}</code>
                          </pre>
                        ),
                      strong: ({ children }) => <strong className="font-semibold">{children}</strong>,
                      em: ({ children }) => <em className="italic">{children}</em>,
                      h1: ({ children }) => <h1 className="text-lg font-bold mb-2">{children}</h1>,
                      h2: ({ children }) => <h2 className="text-md font-bold mb-2">{children}</h2>,
                      h3: ({ children }) => <h3 className="text-sm font-bold mb-1">{children}</h3>,
                    }}
                  >
                    {message.content || ''}
                  </ReactMarkdown>
                )}
              </div>

              {/* Streaming indicator */}
              {message.isStreaming && (
                <div className="flex items-center space-x-1 mt-2">
                  <div className="flex space-x-1">
                    <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce"></div>
                    <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '0.1s' }}></div>
                    <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '0.2s' }}></div>
                  </div>
                  <span className="text-xs text-gray-500">AI is typing...</span>
                </div>
              )}
            </div>

            {/* Document Preview */}
            {message.isPreview && message.previewData && (
              <div className="mt-3 w-full max-w-4xl">
                <DocumentPreview
                  extractedData={message.previewData.extractedData}
                  sessionId={message.previewData.sessionId}
                  documentType={message.previewData.documentType}
                  onConfirm={onPreviewConfirm}
                  onCancel={onPreviewCancel}
                />
              </div>
            )}

            {/* File Attachments */}
            {message.files && message.files.length > 0 && (
              <div className="mt-3 w-full max-w-4xl">
                <FileAttachments 
                  files={message.files} 
                  sessionId={message.sessionId || message.previewData?.sessionId}
                />
              </div>
            )}

            {/* Interactive HTML Chart */}
            {message.htmlContent && (
              <div className="mt-3 w-full max-w-4xl">
                <InteractiveChart 
                  htmlContent={message.htmlContent}
                  onEnlarge={(htmlContent) => {
                    const newWindow = window.open('', '_blank');
                    newWindow.document.write(htmlContent);
                    newWindow.document.close();
                  }}
                />
              </div>
            )}

            {/* Timestamp */}
            <div className={`text-xs text-gray-500 mt-1 ${isUser ? 'text-right' : 'text-left'}`}>
              {formatTimestamp(message.timestamp)}
            </div>
          </div>
        </div>
      </div>
    );
  };

  const LoadingIndicator = () => (
    <ThinkingAnimation status="processing" message="Processing your request..." />
  );

  const ThinkingIndicator = () => (
    <ThinkingAnimation status="responding" message="Generating response..." />
  );

  const WelcomeMessage = () => (
    <div className="flex justify-center mb-8">
      <div className="text-center max-w-2xl">
        <div className="w-16 h-16 bg-blue-500 rounded-full flex items-center justify-center mx-auto mb-4">
          <CpuChipIcon className="w-8 h-8 text-white" />
        </div>
        <h2 className="text-2xl font-bold text-gray-900 mb-2">
          Welcome to Odoo AI Agent
        </h2>
        <p className="text-gray-600 mb-4">
          I can help you with various tasks including:
        </p>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-left">
          <div className="bg-blue-50 p-4 rounded-lg">
            <h3 className="font-semibold text-blue-900 mb-2">📄 Document Processing</h3>
            <p className="text-sm text-blue-700">
              Upload bills, invoices, receipts, or contact information for automatic processing
            </p>
          </div>
          <div className="bg-green-50 p-4 rounded-lg">
            <h3 className="font-semibold text-green-900 mb-2">💬 General Chat</h3>
            <p className="text-sm text-green-700">
              Ask questions about your Odoo data or get help with various tasks
            </p>
          </div>
          <div className="bg-purple-50 p-4 rounded-lg">
            <h3 className="font-semibold text-purple-900 mb-2">📊 Reporting</h3>
            <p className="text-sm text-purple-700">
              Generate reports and analyze your business data
            </p>
          </div>
          <div className="bg-orange-50 p-4 rounded-lg">
            <h3 className="font-semibold text-orange-900 mb-2">📧 Email Processing</h3>
            <p className="text-sm text-orange-700">
              Process emails and extract relevant information
            </p>
          </div>
        </div>
        <p className="text-gray-500 text-sm mt-4">
          Start by typing a message or uploading a document!
        </p>
      </div>
    </div>
  );

  return (
    <div className="space-y-4">
      {messages.length === 0 && !isLoading && <WelcomeMessage />}
      
      {messages.map((message) => (
        <MessageBubble key={message.id} message={message} />
      ))}
      
      {/* Show thinking animation when agent is processing */}
      {(isLoading || agentStatus === 'processing' || agentStatus === 'responding') && (
        <ThinkingAnimation 
          status={agentStatus || 'processing'} 
          message={
            agentStatus === 'processing' ? 'Processing your request...' :
            agentStatus === 'responding' ? 'Generating response...' :
            'Working on it...'
          }
        />
      )}
    </div>
  );
};

export default MessageList;