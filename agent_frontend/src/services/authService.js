import axios from 'axios';

const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:5000';

const authAPI = axios.create({
  baseURL: API_BASE_URL,
  timeout: 30000, // 30 second timeout
  headers: {
    'Content-Type': 'application/json',
  },
});

// Add request interceptor for logging
authAPI.interceptors.request.use(
  (config) => {
    console.log('[AuthService] API Request:', config.method?.toUpperCase(), config.url);
    return config;
  },
  (error) => {
    console.error('[AuthService] API Request Error:', error);
    return Promise.reject(error);
  }
);

// Add response interceptor for logging
authAPI.interceptors.response.use(
  (response) => {
    console.log('[AuthService] API Response:', response.status, response.config.url);
    return response;
  },
  (error) => {
    console.error('[AuthService] API Response Error:', error.response?.status, error.response?.data);
    return Promise.reject(error);
  }
);

class AuthService {
  constructor() {
    this.isAuthenticated = false;
    this.sessionId = null;
    this.credentials = null;
    this.authPromise = null; // To prevent multiple simultaneous auth checks
  }

  /**
   * Check if user has existing authentication session
   * @returns {Promise<{authenticated: boolean, sessionId?: string, credentials?: object}>}
   */
  async checkSession() {
    console.log('[AuthService] Checking session...');
    
    // Prevent multiple simultaneous checks
    if (this.authPromise) {
      console.log('[AuthService] Auth check already in progress, waiting...');
      return this.authPromise;
    }

    this.authPromise = this._performSessionCheck();
    const result = await this.authPromise;
    this.authPromise = null;
    
    return result;
  }

  async _performSessionCheck() {
    try {
      const response = await authAPI.post('/api/auth/check-session');
      const data = response.data;

      if (data.authenticated) {
        console.log('[AuthService] ✅ Valid session found');
        this.isAuthenticated = true;
        this.sessionId = data.session_id;
        this.credentials = data.credentials;
        
        return {
          authenticated: true,
          sessionId: data.session_id,
          credentials: data.credentials
        };
      } else {
        console.log('[AuthService] ❌ No valid session found');
        this.isAuthenticated = false;
        this.sessionId = null;
        this.credentials = null;
        
        return {
          authenticated: false
        };
      }
    } catch (error) {
      console.error('[AuthService] Session check failed:', error);
      this.isAuthenticated = false;
      this.sessionId = null;
      this.credentials = null;
      
      return {
        authenticated: false,
        error: error.response?.data?.message || error.message
      };
    }
  }

  /**
   * Authenticate user with Odoo credentials
   * @param {object} credentials - {url, database, username, password}
   * @returns {Promise<{success: boolean, message: string, sessionId?: string}>}
   */
  async authenticate(credentials) {
    console.log('[AuthService] Authenticating user...');
    
    try {
      // Validate credentials
      const requiredFields = ['url', 'database', 'username', 'password'];
      for (const field of requiredFields) {
        if (!credentials[field] || !credentials[field].trim()) {
          throw new Error(`${field} is required`);
        }
      }

      const response = await authAPI.post('/api/auth/authenticate', credentials);
      const data = response.data;

      if (data.success) {
        console.log('[AuthService] ✅ Authentication successful');
        this.isAuthenticated = true;
        this.sessionId = data.session_id;
        this.credentials = data.credentials;
        
        return {
          success: true,
          message: data.message,
          sessionId: data.session_id,
          credentials: data.credentials
        };
      } else {
        console.log('[AuthService] ❌ Authentication failed');
        return {
          success: false,
          message: data.message
        };
      }
    } catch (error) {
      console.error('[AuthService] Authentication error:', error);
      
      if (error.response?.status === 401) {
        return {
          success: false,
          message: error.response.data.message || 'Invalid credentials'
        };
      } else {
        return {
          success: false,
          message: error.response?.data?.message || error.message || 'Authentication failed'
        };
      }
    }
  }

  /**
   * Logout user and clear session
   * @returns {Promise<{success: boolean, message: string}>}
   */
  async logout() {
    console.log('[AuthService] Logging out user...');
    
    try {
      const response = await authAPI.post('/api/auth/logout');
      const data = response.data;

      // Clear local state regardless of API response
      this.isAuthenticated = false;
      this.sessionId = null;
      this.credentials = null;

      console.log('[AuthService] ✅ Logout successful');
      return {
        success: true,
        message: data.message || 'Logged out successfully'
      };
    } catch (error) {
      console.error('[AuthService] Logout error:', error);
      
      // Still clear local state even if API call fails
      this.isAuthenticated = false;
      this.sessionId = null;
      this.credentials = null;

      return {
        success: false,
        message: error.response?.data?.message || error.message || 'Logout failed'
      };
    }
  }

  /**
   * Get full credentials for agent use
   * @returns {Promise<{success: boolean, credentials?: object, sessionId?: string}>}
   */
  async getCredentials() {
    console.log('[AuthService] Getting full credentials...');
    
    try {
      const response = await authAPI.post('/api/auth/get-credentials');
      const data = response.data;

      if (data.success) {
        console.log('[AuthService] ✅ Credentials retrieved');
        return {
          success: true,
          credentials: data.credentials,
          sessionId: data.session_id
        };
      } else {
        console.log('[AuthService] ❌ No credentials found');
        return {
          success: false,
          message: data.message
        };
      }
    } catch (error) {
      console.error('[AuthService] Get credentials error:', error);
      return {
        success: false,
        message: error.response?.data?.message || error.message || 'Failed to get credentials'
      };
    }
  }

  /**
   * Get current authentication state
   * @returns {object} Current auth state
   */
  getAuthState() {
    return {
      isAuthenticated: this.isAuthenticated,
      sessionId: this.sessionId,
      credentials: this.credentials
    };
  }

  /**
   * Clear local authentication state
   */
  clearAuthState() {
    this.isAuthenticated = false;
    this.sessionId = null;
    this.credentials = null;
  }
}

// Export singleton instance
export const authService = new AuthService();
export default authService; 