import React, { useState, useEffect } from 'react';
import { useCredentials } from '../hooks/useCredentials';
import SetupModal from './SetupModal';
import LoadingSpinner from './LoadingSpinner';

const CredentialGuard = ({ children }) => {
  const { isConfigured, isLoading, refreshCredentials } = useCredentials();
  const [showSetupModal, setShowSetupModal] = useState(false);
  const [setupCompleted, setSetupCompleted] = useState(false);
  const [forceConfigured, setForceConfigured] = useState(false); // Force configured state after setup

  console.log('[CredentialGuard] State:', { isConfigured, isLoading, showSetupModal, setupCompleted, forceConfigured });
  
  // Listen for credential updates and force a configured state
  useEffect(() => {
    const handleCredentialsUpdate = () => {
      console.log('[CredentialGuard] 🔔 Credentials updated event received - forcing configured state');
      setForceConfigured(true);
      setSetupCompleted(true);
    };
    
    window.addEventListener('credentialsUpdated', handleCredentialsUpdate);
    
    return () => {
      window.removeEventListener('credentialsUpdated', handleCredentialsUpdate);
    };
  }, []);

  // Show loading while checking credentials
  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-100">
        <LoadingSpinner message="Checking configuration..." />
      </div>
    );
  }

  // Show setup modal if credentials not configured
  if (!isConfigured && !setupCompleted && !forceConfigured) {
    return (
      <>
        <CredentialRequiredView onSetup={() => setShowSetupModal(true)} />
        <SetupModal 
          isOpen={showSetupModal || (!isConfigured && !setupCompleted && !forceConfigured)}
          onComplete={async () => {
            console.log('[CredentialGuard] 🚀 Setup completed - hiding modal and refreshing credentials');
            console.log('[CredentialGuard] Current state before completion:', { isConfigured, setupCompleted, forceConfigured });
            
            setShowSetupModal(false);
            setSetupCompleted(true);
            setForceConfigured(true); // Force the app to render even if hook hasn't updated yet
            
            console.log('[CredentialGuard] ✅ State updated - should trigger immediate re-render');
            console.log('[CredentialGuard] New state:', { 
              showSetupModal: false, 
              setupCompleted: true, 
              forceConfigured: true 
            });
            
            // Refresh credentials to get updated state
            console.log('[CredentialGuard] 🔄 First credential refresh...');
            await refreshCredentials();
            
            // Give more time for credentials to be verified and state to update
            console.log('[CredentialGuard] ⏱️ Waiting for credential state to update...');
            setTimeout(async () => {
              console.log('[CredentialGuard] 🔄 Final credential refresh...');
              await refreshCredentials();
              console.log('[CredentialGuard] Final credential refresh completed');
              
              // Check the final state
              setTimeout(() => {
                console.log('[CredentialGuard] 🔍 Final state check - this should trigger re-render');
              }, 500);
            }, 2000); // Increased delay to ensure state updates
          }}
        />
      </>
    );
  }

  // If setup was completed but credentials are still being verified, show loading
  if (setupCompleted && !isConfigured && !forceConfigured) {
    console.log('[CredentialGuard] Setup completed but credentials still loading - showing spinner');
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-100">
        <LoadingSpinner message="Finalizing setup..." />
      </div>
    );
  }

  // Credentials are configured, render the app
  console.log('[CredentialGuard] ✅ Credentials configured OR forced - rendering app');
  console.log('[CredentialGuard] Final render decision:', { 
    isConfigured, 
    setupCompleted, 
    forceConfigured,
    shouldRenderApp: isConfigured || forceConfigured 
  });
  return children;
};

// Component shown when credentials are required
const CredentialRequiredView = ({ onSetup }) => {
  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-100">
      <div className="max-w-md w-full bg-white rounded-lg shadow-lg p-8 text-center">
        <div className="mb-6">
          <div className="w-16 h-16 bg-blue-100 rounded-full flex items-center justify-center mx-auto mb-4">
            <svg className="w-8 h-8 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
            </svg>
          </div>
          <h2 className="text-2xl font-bold text-gray-900 mb-2">Setup Required</h2>
          <p className="text-gray-600">
            Before you can use the Odoo AI Agent, you need to configure your Odoo connection settings.
          </p>
        </div>

        <div className="space-y-4 mb-6">
          <div className="flex items-center gap-3 text-sm text-gray-600">
            <div className="w-2 h-2 bg-blue-500 rounded-full"></div>
            <span>Connect to your Odoo instance</span>
          </div>
          <div className="flex items-center gap-3 text-sm text-gray-600">
            <div className="w-2 h-2 bg-blue-500 rounded-full"></div>
            <span>Secure credential storage</span>
          </div>
          <div className="flex items-center gap-3 text-sm text-gray-600">
            <div className="w-2 h-2 bg-blue-500 rounded-full"></div>
            <span>AI-powered assistance</span>
          </div>
        </div>

        <button
          onClick={onSetup}
          className="w-full bg-blue-600 text-white py-3 px-4 rounded-md hover:bg-blue-700 transition-colors font-medium"
        >
          Configure Odoo Connection
        </button>

        <p className="text-xs text-gray-500 mt-4">
          Your credentials are encrypted and stored securely
        </p>
      </div>
    </div>
  );
};

export default CredentialGuard; 