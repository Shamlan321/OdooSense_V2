import axios from 'axios';

const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:5000';

const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 90000, // 90 second timeout for reporting operations
  headers: {
    'Content-Type': 'application/json',
  },
});

// Request interceptor
api.interceptors.request.use(
  (config) => {
    console.log('API Request:', config.method?.toUpperCase(), config.url);
    return config;
  },
  (error) => {
    console.error('API Request Error:', error);
    return Promise.reject(error);
  }
);

// Response interceptor
api.interceptors.response.use(
  (response) => {
    console.log('API Response:', response.status, response.config.url);
    return response;
  },
  (error) => {
    console.error('API Response Error:', error.response?.status, error.response?.data);
    return Promise.reject(error);
  }
);

export const agentAPI = {
  // Health check
  async checkHealth() {
    try {
      const response = await api.get('/api/health');
      return response.data;
    } catch (error) {
      throw new Error(`Health check failed: ${error.message}`);
    }
  },

  // Get agent info
  async getAgentInfo() {
    try {
      const response = await api.get('/api/info');
      return response.data;
    } catch (error) {
      throw new Error(`Failed to get agent info: ${error.message}`);
    }
  },

  // Send chat message
  async sendMessage(message, userId = null) {
    try {
      const response = await api.post('/api/chat', {
        message,
        user_id: userId
        // No session_id needed - auth handled by browser fingerprint
      });
      return response.data;
    } catch (error) {
      throw new Error(`Failed to send message: ${error.message}`);
    }
  },

  // Send chat message with streaming
  async sendMessageStream(message, sessionId, userId = null, onChunk = null) {
    try {
      const response = await fetch(`${API_BASE_URL}/api/chat/stream`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          message,
          session_id: sessionId,
          user_id: userId
        })
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let fullResponse = '';
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        
        // Keep the last incomplete line in buffer
        buffer = lines.pop() || '';

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            const data = line.slice(6).trim();
            if (data === '[DONE]') {
              return fullResponse;
            }
            try {
              const parsed = JSON.parse(data);
              if (parsed.type === 'content' && parsed.content) {
                fullResponse += parsed.content;
                if (onChunk) {
                  onChunk(parsed.content);
                }
              } else if (parsed.type === 'done') {
                return fullResponse;
              } else if (parsed.type === 'error') {
                throw new Error(parsed.error || 'Streaming error occurred');
              }
            } catch (e) {
              // Skip invalid JSON, but log for debugging
              console.warn('Failed to parse streaming data:', data, e);
            }
          }
        }
      }

      return fullResponse;
    } catch (error) {
      throw new Error(`Failed to send streaming message: ${error.message}`);
    }
  },

  // Upload document
  async uploadDocument(file, sessionId, documentType = null, userId = null, previewMode = false) {
    try {
      const formData = new FormData();
      formData.append('file', file);
      formData.append('session_id', sessionId);
      formData.append('preview_mode', previewMode.toString());
      if (documentType) {
        formData.append('document_type', documentType);
      }
      if (userId) {
        formData.append('user_id', userId);
      }

      const response = await api.post('/api/upload', formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      });
      return response.data;
    } catch (error) {
      throw new Error(`Failed to upload document: ${error.message}`);
    }
  },

  // Confirm document data
  async confirmDocumentData(extractedData, sessionId, documentType = null, userId = null) {
    try {
      const requestData = {
        extracted_data: extractedData,
        session_id: sessionId,
        user_id: userId
      };
      
      if (documentType) {
        requestData.document_type = documentType;
      }
      
      const response = await api.post('/api/upload/confirm', requestData);
      return response.data;
    } catch (error) {
      throw new Error(`Failed to confirm document data: ${error.message}`);
    }
  },

  // Test and save Odoo connection in one request
  async testAndSaveOdooConnection(credentials, sessionId) {
    try {
      console.log('[API] testAndSaveOdooConnection called with sessionId:', sessionId);
      console.log('[API] Credentials object keys:', Object.keys(credentials));
      
      // Ensure we have a valid session ID
      if (!sessionId) {
        throw new Error('Session ID is required for testAndSaveOdooConnection');
      }
      
      const requestData = {
        ...credentials,
        session_id: sessionId
      };
      
      console.log('[API] Request data:', { ...requestData, password: '[REDACTED]' });
      
      const response = await api.post('/api/config/test-and-save-connection', requestData);
      
      console.log('[API] Response data:', response.data);
      return response.data;
    } catch (error) {
      throw new Error(`Failed to test and save Odoo connection: ${error.message}`);
    }
  },

  // Test Odoo connection
  async testOdooConnection(credentials) {
    try {
      const response = await api.post('/api/config/test-connection', credentials);
      return response.data;
    } catch (error) {
      throw new Error(`Failed to test Odoo connection: ${error.message}`);
    }
  },

  // Test Odoo connection using stored session credentials
  async testSessionConnection(sessionId) {
    try {
      const response = await api.post('/api/config/test-session-connection', {
        session_id: sessionId
      });
      return response.data;
    } catch (error) {
      throw new Error(`Failed to test session connection: ${error.message}`);
    }
  },

  // Save Odoo credentials
  async saveOdooCredentials(sessionId, credentials) {
    try {
      const response = await api.post('/api/config/credentials', {
        session_id: sessionId,
        ...credentials
      });
      return response.data;
    } catch (error) {
      throw new Error(`Failed to save Odoo credentials: ${error.message}`);
    }
  },

  // Get current Odoo credentials
  async getOdooCredentials(sessionId) {
    try {
      const params = sessionId ? { session_id: sessionId } : {};
      const response = await api.get('/api/config/credentials', { params });
      return response.data;
    } catch (error) {
      throw new Error(`Failed to get Odoo credentials: ${error.message}`);
    }
  },

  // Clear Odoo credentials
  async clearOdooCredentials(sessionId) {
    try {
      const response = await api.delete('/api/config/credentials', {
        params: { session_id: sessionId }
      });
      return response.data;
    } catch (error) {
      throw new Error(`Failed to clear Odoo credentials: ${error.message}`);
    }
  },

  // Get session info
  async getSessionInfo() {
    try {
      const response = await api.get('/api/config/session-info');
      return response.data;
    } catch (error) {
      throw new Error(`Failed to get session info: ${error.message}`);
    }
  },

  // Get conversation history
  async getConversationHistory(sessionId, limit = 50) {
    try {
      const response = await api.get(`/api/conversation/${sessionId}`, {
        params: {
          limit
        }
      });
      return response.data;
    } catch (error) {
      throw new Error(`Failed to get conversation history: ${error.message}`);
    }
  },

  // Get supported features
  async getSupportedFeatures() {
    try {
      const response = await api.get('/api/features');
      return response.data;
    } catch (error) {
      throw new Error(`Failed to get supported features: ${error.message}`);
    }
  },

  // Reporting Agent Methods
  async reportingChat(data) {
    try {
      const response = await api.post('/api/reporting/chat', data);
      return response.data;
    } catch (error) {
      throw new Error(`Failed to send reporting message: ${error.message}`);
    }
  },

  async getReportingFiles(sessionId) {
    try {
      const response = await api.get(`/api/reporting/files/${sessionId}`);
      return response.data;
    } catch (error) {
      throw new Error(`Failed to get reporting files: ${error.message}`);
    }
  },

  async downloadReport(sessionId, filename) {
    try {
      const response = await api.get(`/api/reporting/download/${sessionId}/${filename}`, {
        responseType: 'blob'
      });
      return response;
    } catch (error) {
      throw new Error(`Failed to download report: ${error.message}`);
    }
  },

  async initializeReportingAgent(credentials, sessionId) {
    try {
      const response = await api.post('/api/reporting/initialize', {
        credentials,
        session_id: sessionId
      });
      return response.data;
    } catch (error) {
      throw new Error(`Failed to initialize reporting agent: ${error.message}`);
    }
  },

  async getRoutingInfo(message) {
    try {
      const response = await api.post('/api/reporting/routing-info', {
        message
      });
      return response.data;
    } catch (error) {
      throw new Error(`Failed to get routing info: ${error.message}`);
    }
  },

  async getAgentStatus() {
    try {
      const response = await api.get('/api/health');
      return response.data;
    } catch (error) {
      throw new Error(`Failed to get agent status: ${error.message}`);
    }
  }
};

export default api;