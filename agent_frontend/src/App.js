import React from 'react';
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import ChatInterface from './components/ChatInterface';
import ReportingInterface from './components/ReportingInterface';
import Header from './components/Header';
import Sidebar from './components/Sidebar';
import AuthGuard from './components/AuthGuard';
import { ChatProvider } from './context/ChatContext';
import { AuthProvider } from './context/AuthContext';
import { ThemeProvider } from './context/ThemeContext';
import './App.css';

function App() {
  return (
    <ThemeProvider>
      <AuthProvider>
        <AuthGuard>
          <ChatProvider>
            <Router>
              <div className="flex h-screen bg-gray-100 dark:bg-gray-900 transition-colors">
                <Sidebar />
                <div className="flex-1 flex flex-col">
                  <Header />
                  <main className="flex-1 overflow-hidden">
                    <Routes>
                      <Route path="/" element={<ChatInterface />} />
                      <Route path="/chat" element={<ChatInterface />} />
                      <Route path="/reporting" element={<ReportingInterface />} />
                    </Routes>
                  </main>
                </div>
              </div>
            </Router>
          </ChatProvider>
        </AuthGuard>
      </AuthProvider>
    </ThemeProvider>
  );
}

export default App;