import React from 'react';
import { useAuth } from '../context/AuthContext';
import AuthDialog from './AuthDialog';
import LoadingSpinner from './LoadingSpinner';

const AuthGuard = ({ children }) => {
  const { isAuthenticated, isLoading, error } = useAuth();

  // Show loading spinner while checking authentication
  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-100 dark:bg-gray-900">
        <LoadingSpinner message="Checking authentication..." />
      </div>
    );
  }

  // Show auth dialog if not authenticated
  if (!isAuthenticated) {
    return <AuthDialog />;
  }

  // User is authenticated, render the app
  return children;
};

export default AuthGuard; 