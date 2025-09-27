import React, { useState } from 'react';
import { agentAPI } from '../services/api';

const DocumentPreview = ({ extractedData, sessionId, documentType, onConfirm, onCancel }) => {
  const [isProcessing, setIsProcessing] = useState(false);
  const [error, setError] = useState(null);

  const handleAddToOdoo = async () => {
    setIsProcessing(true);
    setError(null);
    
    try {
      const result = await agentAPI.confirmDocumentData(extractedData, sessionId, documentType);
      onConfirm(result);
    } catch (err) {
      setError(err.message);
    } finally {
      setIsProcessing(false);
    }
  };

  const renderDataTable = () => {
    if (!extractedData || typeof extractedData !== 'object') {
      return <p className="text-gray-500">No data to display</p>;
    }

    const entries = Object.entries(extractedData).filter(([key, value]) => 
      key !== 'confidence_score' && value !== null && value !== undefined && value !== ''
    );

    if (entries.length === 0) {
      return <p className="text-gray-500">No data extracted</p>;
    }

    return (
      <div className="overflow-x-auto">
        <table className="min-w-full bg-white border border-gray-200 rounded-lg">
          <thead className="bg-gray-50">
            <tr>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider border-b">
                Field
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider border-b">
                Value
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-200">
            {entries.map(([key, value], index) => (
              <tr key={index} className={index % 2 === 0 ? 'bg-white' : 'bg-gray-50'}>
                <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900 capitalize">
                  {key.replace(/_/g, ' ')}
                </td>
                <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-700">
                  {typeof value === 'object' ? JSON.stringify(value) : String(value)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    );
  };

  const confidenceScore = extractedData?.confidence_score;
  const confidenceColor = confidenceScore >= 0.8 ? 'text-green-600' : 
                         confidenceScore >= 0.6 ? 'text-yellow-600' : 'text-red-600';

  return (
    <div className="bg-white border border-gray-200 rounded-lg p-6 mb-4">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-semibold text-gray-900">Extracted Document Data</h3>
        {confidenceScore && (
          <span className={`text-sm font-medium ${confidenceColor}`}>
            Confidence: {(confidenceScore * 100).toFixed(1)}%
          </span>
        )}
      </div>
      
      {renderDataTable()}
      
      {error && (
        <div className="mt-4 p-3 bg-red-50 border border-red-200 rounded-md">
          <p className="text-sm text-red-600">{error}</p>
        </div>
      )}
      
      <div className="flex justify-end space-x-3 mt-6">
        <button
          onClick={onCancel}
          className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500"
          disabled={isProcessing}
        >
          Cancel
        </button>
        <button
          onClick={handleAddToOdoo}
          disabled={isProcessing}
          className="px-4 py-2 text-sm font-medium text-white bg-blue-600 border border-transparent rounded-md hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {isProcessing ? (
            <>
              <svg className="animate-spin -ml-1 mr-2 h-4 w-4 text-white inline" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
              </svg>
              Processing...
            </>
          ) : (
            'Add to Odoo'
          )}
        </button>
      </div>
    </div>
  );
};

export default DocumentPreview;