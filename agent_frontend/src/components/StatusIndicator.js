import React from 'react';
import { CheckCircleIcon, ExclamationTriangleIcon, CpuChipIcon } from '@heroicons/react/24/outline';

const StatusIndicator = ({ status }) => {
  const getStatusConfig = () => {
    switch (status) {
      case 'idle':
        return {
          icon: CheckCircleIcon,
          text: 'Ready',
          color: 'text-green-600',
          bgColor: 'bg-green-100',
          dotColor: 'bg-green-500'
        };
      case 'processing':
        return {
          icon: CpuChipIcon,
          text: 'Processing',
          color: 'text-blue-600',
          bgColor: 'bg-blue-100',
          dotColor: 'bg-blue-500',
          animate: true
        };
      case 'responding':
        return {
          icon: CpuChipIcon,
          text: 'Generating response',
          color: 'text-purple-600',
          bgColor: 'bg-purple-100',
          dotColor: 'bg-purple-500',
          animate: true
        };
      case 'error':
        return {
          icon: ExclamationTriangleIcon,
          text: 'Error',
          color: 'text-red-600',
          bgColor: 'bg-red-100',
          dotColor: 'bg-red-500'
        };
      default:
        return {
          icon: CheckCircleIcon,
          text: 'Ready',
          color: 'text-gray-600',
          bgColor: 'bg-gray-100',
          dotColor: 'bg-gray-500'
        };
    }
  };

  const config = getStatusConfig();
  const Icon = config.icon;

  return (
    <div className="flex items-center space-x-2">
      {/* Status dot */}
      <div className="relative">
        <div className={`w-3 h-3 rounded-full ${config.dotColor}`}></div>
        {config.animate && (
          <div className={`absolute inset-0 w-3 h-3 rounded-full ${config.dotColor} animate-ping opacity-75`}></div>
        )}
      </div>

      {/* Status text */}
      <div className={`flex items-center space-x-1 px-2 py-1 rounded-full ${config.bgColor}`}>
        <Icon className={`w-4 h-4 ${config.color}`} />
        <span className={`text-sm font-medium ${config.color}`}>
          {config.text}
        </span>
      </div>


    </div>
  );
};

export default StatusIndicator;