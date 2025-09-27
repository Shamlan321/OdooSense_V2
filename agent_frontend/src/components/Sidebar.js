import React, { useState, useEffect, useCallback } from 'react';
import { useChat } from '../context/ChatContext';
import { agentAPI } from '../services/api';
import {
  ChatBubbleLeftRightIcon,
  DocumentTextIcon,
  ChartBarIcon,
  EnvelopeIcon,
  ClockIcon,
  PlusIcon,
  ChevronLeftIcon,
  ChevronRightIcon
} from '@heroicons/react/24/outline';

const Sidebar = () => {
  const { sessionId, conversationHistory, setConversationHistory, newSession } = useChat();
  const [isCollapsed, setIsCollapsed] = useState(false);
  const [activeTab, setActiveTab] = useState('chat');
  const [isLoadingHistory, setIsLoadingHistory] = useState(false);

  const loadConversationHistory = useCallback(async () => {
    setIsLoadingHistory(true);
    try {
      const history = await agentAPI.getConversationHistory(sessionId);
      setConversationHistory(history.conversations || []);
    } catch (error) {
      console.error('Failed to load conversation history:', error);
    } finally {
      setIsLoadingHistory(false);
    }
  }, [sessionId, setConversationHistory]);

  useEffect(() => {
    if (activeTab === 'history') {
      loadConversationHistory();
    }
  }, [activeTab, loadConversationHistory]);

  const navigationItems = [
    {
      id: 'chat',
      name: 'Chat',
      icon: ChatBubbleLeftRightIcon,
      description: 'General conversation'
    },
    {
      id: 'reporting',
      name: 'Reporting Agent',
      icon: ChartBarIcon,
      description: 'Generate reports & CRUD operations'
    },
    {
      id: 'documents',
      name: 'Documents',
      icon: DocumentTextIcon,
      description: 'Process documents'
    },
    {
      id: 'email',
      name: 'Email',
      icon: EnvelopeIcon,
      description: 'Process emails'
    },
    {
      id: 'history',
      name: 'History',
      icon: ClockIcon,
      description: 'Conversation history'
    }
  ];

  const formatTimestamp = (timestamp) => {
    const date = new Date(timestamp);
    const now = new Date();
    const diffInHours = (now - date) / (1000 * 60 * 60);
    
    if (diffInHours < 1) {
      return 'Just now';
    } else if (diffInHours < 24) {
      return `${Math.floor(diffInHours)}h ago`;
    } else {
      return date.toLocaleDateString();
    }
  };

  const truncateText = (text, maxLength = 50) => {
    if (text.length <= maxLength) return text;
    return text.substring(0, maxLength) + '...';
  };

  return (
    <div className={`bg-gray-900 text-white transition-all duration-300 flex flex-col ${
      isCollapsed ? 'w-16' : 'w-64'
    }`}>
      {/* Header */}
      <div className="p-4 border-b border-gray-700">
        <div className="flex items-center justify-between">
          {!isCollapsed && (
            <h2 className="text-lg font-semibold">Navigation</h2>
          )}
          <button
            onClick={() => setIsCollapsed(!isCollapsed)}
            className="p-1 hover:bg-gray-700 rounded transition-colors"
          >
            {isCollapsed ? (
              <ChevronRightIcon className="w-5 h-5" />
            ) : (
              <ChevronLeftIcon className="w-5 h-5" />
            )}
          </button>
        </div>
      </div>

      {/* New Session Button */}
      <div className="p-4">
        <button
          onClick={newSession}
          className={`w-full flex items-center justify-center space-x-2 bg-blue-600 hover:bg-blue-700 text-white py-2 px-3 rounded-lg transition-colors ${
            isCollapsed ? 'px-2' : ''
          }`}
          title="Start new session"
        >
          <PlusIcon className="w-5 h-5" />
          {!isCollapsed && <span>New Session</span>}
        </button>
      </div>

      {/* Navigation Items */}
      <nav className="flex-1 px-4">
        <ul className="space-y-2">
          {navigationItems.map((item) => {
            const Icon = item.icon;
            const isActive = activeTab === item.id;
            
            return (
              <li key={item.id}>
                <button
                  onClick={() => setActiveTab(item.id)}
                  className={`w-full flex items-center space-x-3 px-3 py-2 rounded-lg transition-colors ${
                    isActive
                      ? 'bg-blue-600 text-white'
                      : 'text-gray-300 hover:bg-gray-700 hover:text-white'
                  }`}
                  title={isCollapsed ? item.name : item.description}
                >
                  <Icon className="w-5 h-5 flex-shrink-0" />
                  {!isCollapsed && (
                    <div className="text-left">
                      <div className="font-medium">{item.name}</div>
                      <div className="text-xs text-gray-400">{item.description}</div>
                    </div>
                  )}
                </button>
              </li>
            );
          })}
        </ul>
      </nav>

      {/* Content Area */}
      {!isCollapsed && activeTab === 'history' && (
        <div className="border-t border-gray-700 p-4 max-h-64 overflow-y-auto">
          <h3 className="text-sm font-semibold text-gray-300 mb-3">
            Recent Conversations
          </h3>
          
          {isLoadingHistory ? (
            <div className="text-center py-4">
              <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-white mx-auto"></div>
              <p className="text-xs text-gray-400 mt-2">Loading...</p>
            </div>
          ) : conversationHistory.length > 0 ? (
            <div className="space-y-2">
              {conversationHistory.slice(0, 10).map((conversation, index) => (
                <div
                  key={index}
                  className="p-2 bg-gray-800 rounded text-xs hover:bg-gray-700 cursor-pointer transition-colors"
                >
                  <p className="text-white font-medium mb-1">
                    {truncateText(conversation.user_message)}
                  </p>
                  <p className="text-gray-400">
                    {truncateText(conversation.assistant_response)}
                  </p>
                  <p className="text-gray-500 text-xs mt-1">
                    {formatTimestamp(conversation.timestamp)}
                  </p>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-gray-400 text-xs text-center py-4">
              No conversation history
            </p>
          )}
        </div>
      )}

      {/* Quick Actions */}
      {!isCollapsed && activeTab !== 'history' && (
        <div className="border-t border-gray-700 p-4">
          <h3 className="text-sm font-semibold text-gray-300 mb-3">
            Quick Actions
          </h3>
          <div className="space-y-2">
            {activeTab === 'documents' && (
              <>
                <button className="w-full text-left text-xs text-gray-400 hover:text-white p-2 hover:bg-gray-700 rounded transition-colors">
                  📄 Upload Invoice
                </button>
                <button className="w-full text-left text-xs text-gray-400 hover:text-white p-2 hover:bg-gray-700 rounded transition-colors">
                  🧾 Upload Receipt
                </button>
                <button className="w-full text-left text-xs text-gray-400 hover:text-white p-2 hover:bg-gray-700 rounded transition-colors">
                  👤 Upload Contact
                </button>
              </>
            )}
            {activeTab === 'reports' && (
              <>
                <button className="w-full text-left text-xs text-gray-400 hover:text-white p-2 hover:bg-gray-700 rounded transition-colors">
                  📊 Sales Report
                </button>
                <button className="w-full text-left text-xs text-gray-400 hover:text-white p-2 hover:bg-gray-700 rounded transition-colors">
                  💰 Financial Summary
                </button>
              </>
            )}
            {activeTab === 'chat' && (
              <>
                <button className="w-full text-left text-xs text-gray-400 hover:text-white p-2 hover:bg-gray-700 rounded transition-colors">
                  ❓ Ask a Question
                </button>
                <button className="w-full text-left text-xs text-gray-400 hover:text-white p-2 hover:bg-gray-700 rounded transition-colors">
                  🔍 Search Data
                </button>
              </>
            )}
          </div>
        </div>
      )}
    </div>
  );
};

export default Sidebar;