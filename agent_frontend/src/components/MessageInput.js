import React, { useState, useRef, useEffect } from 'react';
import { PaperAirplaneIcon, PaperClipIcon } from '@heroicons/react/24/outline';

const MessageInput = ({ onSendMessage, disabled, onAttachFile, hasFile }) => {
  const [message, setMessage] = useState('');
  const textareaRef = useRef(null);

  const handleSubmit = (e) => {
    e.preventDefault();
    if ((message.trim() || hasFile) && !disabled) {
      onSendMessage(message);
      setMessage('');
      // Reset textarea height
      if (textareaRef.current) {
        textareaRef.current.style.height = 'auto';
      }
    }
  };

  const handleKeyPress = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e);
    }
  };

  const handleTextareaChange = (e) => {
    setMessage(e.target.value);
    
    // Auto-resize textarea
    const textarea = e.target;
    textarea.style.height = 'auto';
    const scrollHeight = textarea.scrollHeight;
    const maxHeight = 120; // Max height in pixels
    textarea.style.height = Math.min(scrollHeight, maxHeight) + 'px';
  };

  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.focus();
    }
  }, []);

  const placeholderText = hasFile 
    ? 'Add a message about your file or press Enter to process...'
    : 'Type your message here... (Shift+Enter for new line)';

  return (
    <form onSubmit={handleSubmit} className="flex items-end space-x-3">
      {/* Attach file button */}
      <button
        type="button"
        onClick={onAttachFile}
        disabled={disabled}
        className={`flex-shrink-0 p-2 rounded-lg transition-colors ${
          disabled
            ? 'bg-gray-100 dark:bg-gray-700 text-gray-400 dark:text-gray-500 cursor-not-allowed'
            : hasFile
              ? 'bg-blue-100 dark:bg-blue-900/30 text-blue-600 dark:text-blue-400 hover:bg-blue-200 dark:hover:bg-blue-900/50'
              : 'bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-600'
        }`}
        title="Attach file"
      >
        <PaperClipIcon className="w-5 h-5" />
      </button>

      {/* Message input */}
      <div className="flex-1 relative">
        <textarea
          ref={textareaRef}
          value={message}
          onChange={handleTextareaChange}
          onKeyPress={handleKeyPress}
          placeholder={placeholderText}
          disabled={disabled}
          rows={1}
          className={`w-full px-4 py-3 border border-gray-300 dark:border-gray-600 rounded-lg resize-none focus:ring-2 focus:ring-blue-500 dark:focus:ring-blue-400 focus:border-transparent transition-all text-gray-900 dark:text-gray-100 placeholder-gray-500 dark:placeholder-gray-400 ${
            disabled ? 'bg-gray-50 dark:bg-gray-800 cursor-not-allowed' : 'bg-white dark:bg-gray-700'
          }`}
          style={{
            minHeight: '48px',
            maxHeight: '120px',
            overflowY: 'auto'
          }}
        />
        
        {/* Character count (optional) */}
        {message.length > 500 && (
          <div className="absolute bottom-1 right-2 text-xs text-gray-400 dark:text-gray-500">
            {message.length}/2000
          </div>
        )}
      </div>

      {/* Send button */}
      <button
        type="submit"
        disabled={disabled || (!message.trim() && !hasFile)}
        className={`flex-shrink-0 p-3 rounded-lg transition-all ${
          disabled || (!message.trim() && !hasFile)
            ? 'bg-gray-100 dark:bg-gray-700 text-gray-400 dark:text-gray-500 cursor-not-allowed'
            : 'bg-blue-500 text-white hover:bg-blue-600 dark:bg-blue-600 dark:hover:bg-blue-700 focus:ring-2 focus:ring-blue-500 dark:focus:ring-blue-400 focus:ring-offset-2 dark:focus:ring-offset-gray-800'
        }`}
        title="Send message"
      >
        <PaperAirplaneIcon className="w-5 h-5" />
      </button>
    </form>
  );
};

export default MessageInput;