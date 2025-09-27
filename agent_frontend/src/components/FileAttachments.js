import React, { useState } from 'react';
import {
  DocumentArrowDownIcon,
  PhotoIcon,
  DocumentTextIcon,
  ChartBarIcon,
  EyeIcon,
  XMarkIcon
} from '@heroicons/react/24/outline';
import { agentAPI } from '../services/api';

const FileAttachments = ({ files, sessionId }) => {
  const [previewImage, setPreviewImage] = useState(null);

  const getFileIcon = (filename) => {
    const extension = filename.split('.').pop()?.toLowerCase();
    
    switch (extension) {
      case 'pdf':
        return <DocumentTextIcon className="h-5 w-5 text-red-500" />;
      case 'png':
      case 'jpg':
      case 'jpeg':
        return <PhotoIcon className="h-5 w-5 text-blue-500" />;
      case 'html':
        return <ChartBarIcon className="h-5 w-5 text-green-500" />;
      default:
        return <DocumentArrowDownIcon className="h-5 w-5 text-gray-500" />;
    }
  };

  const formatFileSize = (bytes) => {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  };

  const isImageFile = (filename) => {
    const extension = filename.split('.').pop()?.toLowerCase();
    return ['png', 'jpg', 'jpeg', 'gif', 'bmp', 'webp'].includes(extension);
  };

  const handleDownload = async (filename) => {
    try {
      console.log('🔄 Starting download for:', filename);
      const response = await agentAPI.downloadReport(sessionId, filename);
      console.log('📥 Download response received:', response);
      console.log('📋 Response headers:', response.headers);
      console.log('📊 Response data type:', typeof response.data);
      console.log('📊 Response data size:', response.data?.length || 'unknown');
      
      // Handle blob creation - response.data might already be a blob
      let blob;
      if (response.data instanceof Blob) {
        blob = response.data;
        console.log('📦 Using existing blob');
      } else {
        blob = new Blob([response.data], { 
          type: response.headers['content-type'] || 'application/octet-stream' 
        });
        console.log('📦 Created new blob from data');
      }
      console.log('📦 Final blob:', blob);
      
      const url = window.URL.createObjectURL(blob);
      console.log('🔗 Object URL created:', url);
      
      const a = document.createElement('a');
      a.href = url;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
      console.log('✅ Download triggered successfully');
    } catch (error) {
      console.error('❌ Download error:', error);
    }
  };

  const handlePreview = async (filename) => {
    try {
      const response = await agentAPI.downloadReport(sessionId, filename);
      // Handle blob creation - response.data might already be a blob
      let blob;
      if (response.data instanceof Blob) {
        blob = response.data;
      } else {
        blob = new Blob([response.data], { 
          type: response.headers['content-type'] || 'application/octet-stream' 
        });
      }
      const url = window.URL.createObjectURL(blob);
      setPreviewImage({ url, filename });
    } catch (error) {
      console.error('Preview error:', error);
    }
  };

  const closePreview = () => {
    if (previewImage) {
      window.URL.revokeObjectURL(previewImage.url);
      setPreviewImage(null);
    }
  };

  if (!files || files.length === 0) {
    return null;
  }

  return (
    <>
      <div className="mt-3 space-y-2">
        <div className="text-sm font-medium text-gray-700 dark:text-gray-300">
          Generated Files:
        </div>
        <div className="space-y-2">
          {files.map((file, index) => (
            <div
              key={index}
              className="flex items-center justify-between p-3 bg-gray-50 dark:bg-gray-700 rounded-lg border border-gray-200 dark:border-gray-600 hover:bg-gray-100 dark:hover:bg-gray-600 transition-colors"
            >
              <div className="flex items-center space-x-3">
                {getFileIcon(file.filename)}
                <div>
                  <div className="font-medium text-gray-900 dark:text-white">
                    {file.filename}
                  </div>
                  <div className="text-xs text-gray-500 dark:text-gray-400">
                    {formatFileSize(file.size || 0)}
                  </div>
                </div>
              </div>
              
              <div className="flex items-center space-x-2">
                {isImageFile(file.filename) && (
                  <button
                    onClick={() => handlePreview(file.filename)}
                    className="px-3 py-1 text-sm bg-green-600 hover:bg-green-700 text-white rounded-md transition-colors flex items-center space-x-1"
                    title="Preview"
                  >
                    <EyeIcon className="h-4 w-4" />
                    <span>Preview</span>
                  </button>
                )}
                <button
                  onClick={() => handleDownload(file.filename)}
                  className="px-3 py-1 text-sm bg-blue-600 hover:bg-blue-700 text-white rounded-md transition-colors flex items-center space-x-1"
                  title="Download"
                >
                  <DocumentArrowDownIcon className="h-4 w-4" />
                  <span>Download</span>
                </button>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Image Preview Modal */}
      {previewImage && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white dark:bg-gray-800 rounded-lg p-4 max-w-4xl max-h-4xl overflow-auto">
            <div className="flex justify-between items-center mb-4">
              <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
                {previewImage.filename}
              </h3>
              <button
                onClick={closePreview}
                className="text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200"
              >
                <XMarkIcon className="h-6 w-6" />
              </button>
            </div>
            <div className="flex justify-center">
              <img
                src={previewImage.url}
                alt={previewImage.filename}
                className="max-w-full max-h-full object-contain"
              />
            </div>
            <div className="mt-4 flex justify-center space-x-4">
              <button
                onClick={() => handleDownload(previewImage.filename)}
                className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-md transition-colors flex items-center space-x-2"
              >
                <DocumentArrowDownIcon className="h-4 w-4" />
                <span>Download</span>
              </button>
              <button
                onClick={closePreview}
                className="px-4 py-2 bg-gray-600 hover:bg-gray-700 text-white rounded-md transition-colors"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
};

export default FileAttachments; 