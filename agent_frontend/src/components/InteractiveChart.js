import React, { useEffect, useRef, useState } from 'react';
import { ArrowTopRightOnSquareIcon } from '@heroicons/react/24/outline';

const InteractiveChart = ({ htmlContent, onEnlarge }) => {
  const chartRef = useRef(null);
  const [iframeSrc, setIframeSrc] = useState('');

  useEffect(() => {
    if (htmlContent) {
      // Create a blob URL for the HTML content
      const blob = new Blob([htmlContent], { type: 'text/html' });
      const url = URL.createObjectURL(blob);
      setIframeSrc(url);
      
      // Cleanup function
      return () => {
        URL.revokeObjectURL(url);
      };
    }
  }, [htmlContent]);

  const handleEnlarge = () => {
    if (onEnlarge) {
      onEnlarge(htmlContent);
    } else {
      // Fallback: open in new window
      const newWindow = window.open('', '_blank');
      newWindow.document.write(htmlContent);
      newWindow.document.close();
    }
  };

  return (
    <div className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 shadow-sm">
      <div className="p-4 border-b border-gray-200 dark:border-gray-700">
        <h3 className="text-sm font-medium text-gray-900 dark:text-gray-100">
          📊 Interactive Chart
        </h3>
        <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
          Hover over data points to see details
        </p>
      </div>
      <div className="p-4">
        <div className="w-full overflow-x-auto min-h-[400px] flex items-center justify-center">
          {iframeSrc ? (
            <iframe
              src={iframeSrc}
              className="w-full h-[400px] border-0"
              title="Interactive Chart"
              sandbox="allow-scripts allow-same-origin"
            />
          ) : (
            <div className="text-gray-500 dark:text-gray-400 text-sm">
              Loading chart...
            </div>
          )}
        </div>
      </div>
      <div className="p-4 border-t border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-700">
        <div className="flex items-center justify-between">
          <span className="text-xs text-gray-500 dark:text-gray-400">
            Interactive Plotly Chart
          </span>
          <button
            onClick={handleEnlarge}
            className="inline-flex items-center px-2 py-1 text-xs font-medium text-blue-600 hover:text-blue-800 dark:text-blue-400 dark:hover:text-blue-300 bg-blue-50 hover:bg-blue-100 dark:bg-blue-900/30 dark:hover:bg-blue-900/50 rounded border border-blue-200 dark:border-blue-700 transition-colors duration-200"
          >
            <ArrowTopRightOnSquareIcon className="w-3 h-3 mr-1" />
            Enlarge
          </button>
        </div>
      </div>
    </div>
  );
};

export default InteractiveChart; 