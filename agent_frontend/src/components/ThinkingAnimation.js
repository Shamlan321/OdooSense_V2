import React, { useState, useEffect } from 'react';
import { CpuChipIcon, SparklesIcon } from '@heroicons/react/24/outline';
import './ThinkingAnimation.css';

const ThinkingAnimation = ({ status = 'processing', message = null }) => {
  const [dots, setDots] = useState('');
  const [thinkingText, setThinkingText] = useState('AI is thinking');

  useEffect(() => {
    const interval = setInterval(() => {
      setDots(prev => {
        if (prev.length >= 3) return '';
        return prev + '.';
      });
    }, 500);

    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    const thinkingTexts = [
      'AI is thinking',
      'Processing your request',
      'Analyzing data',
      'Connecting to Odoo',
      'Generating response',
      'Almost ready'
    ];

    let currentIndex = 0;
    const interval = setInterval(() => {
      currentIndex = (currentIndex + 1) % thinkingTexts.length;
      setThinkingText(thinkingTexts[currentIndex]);
    }, 2000);

    return () => clearInterval(interval);
  }, []);

  const getStatusIcon = () => {
    switch (status) {
      case 'processing':
        return <CpuChipIcon className="h-5 w-5" />;
      case 'responding':
        return <SparklesIcon className="h-5 w-5" />;
      default:
        return <CpuChipIcon className="h-5 w-5" />;
    }
  };

  const getStatusColor = () => {
    switch (status) {
      case 'processing':
        return 'text-blue-500';
      case 'responding':
        return 'text-purple-500';
      default:
        return 'text-gray-500';
    }
  };

  return (
    <div className="flex items-start space-x-3 p-4 bg-gray-50 dark:bg-gray-800 rounded-lg mb-4 animate-pulse">
      {/* AI Avatar */}
      <div className={`flex-shrink-0 w-8 h-8 rounded-full bg-gradient-to-r from-blue-400 to-purple-500 flex items-center justify-center animate-spin-slow`}>
        {getStatusIcon()}
      </div>

      {/* Content */}
      <div className="flex-1 min-w-0">
        <div className="flex items-center space-x-2 mb-2">
          <span className={`text-sm font-medium ${getStatusColor()}`}>
            {thinkingText}{dots}
          </span>
        </div>

        {/* Animated bars representing thinking process */}
        <div className="space-y-2">
          <div className="flex space-x-1">
            <div className="h-2 bg-blue-200 dark:bg-blue-700 rounded animate-pulse"></div>
            <div className="h-2 bg-blue-300 dark:bg-blue-600 rounded animate-pulse" style={{ animationDelay: '0.1s' }}></div>
            <div className="h-2 bg-blue-400 dark:bg-blue-500 rounded animate-pulse" style={{ animationDelay: '0.2s' }}></div>
            <div className="h-2 bg-blue-200 dark:bg-blue-700 rounded animate-pulse" style={{ animationDelay: '0.3s' }}></div>
            <div className="h-2 bg-blue-300 dark:bg-blue-600 rounded animate-pulse" style={{ animationDelay: '0.4s' }}></div>
          </div>
          
          <div className="flex space-x-1">
            <div className="h-2 bg-purple-200 dark:bg-purple-700 rounded animate-pulse" style={{ animationDelay: '0.2s' }}></div>
            <div className="h-2 bg-purple-300 dark:bg-purple-600 rounded animate-pulse" style={{ animationDelay: '0.3s' }}></div>
            <div className="h-2 bg-purple-400 dark:bg-purple-500 rounded animate-pulse" style={{ animationDelay: '0.4s' }}></div>
            <div className="h-2 bg-purple-200 dark:bg-purple-700 rounded animate-pulse" style={{ animationDelay: '0.5s' }}></div>
          </div>
        </div>

        {/* Custom message if provided */}
        {message && (
          <div className="mt-2 text-xs text-gray-500 dark:text-gray-400">
            {message}
          </div>
        )}

        {/* Bouncing dots */}
        <div className="flex items-center space-x-1 mt-3">
          <div className="flex space-x-1">
            <div className="w-2 h-2 bg-blue-400 rounded-full animate-bounce"></div>
            <div className="w-2 h-2 bg-purple-400 rounded-full animate-bounce" style={{ animationDelay: '0.1s' }}></div>
            <div className="w-2 h-2 bg-blue-400 rounded-full animate-bounce" style={{ animationDelay: '0.2s' }}></div>
          </div>
          <span className="text-xs text-gray-500 dark:text-gray-400 ml-2">
            Please wait...
          </span>
        </div>
      </div>
    </div>
  );
};

export default ThinkingAnimation; 