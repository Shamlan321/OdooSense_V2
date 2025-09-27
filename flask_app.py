#!/usr/bin/env python3
"""
Flask Application Entry Point for OdooSense

This module serves as the main entry point for the Flask backend application
that powers the OdooSense AI agent interface.
"""

import os
from dotenv import load_dotenv
from flask import request, jsonify
from app import create_app, socketio
from odoo_client import OdooClient
from cache_service import cache_service
from performance_monitor import performance_monitor
import logging
import atexit

# Load environment variables from .env file
load_dotenv('rag_config_enhanced.env')

logger = logging.getLogger(__name__)

# Create Flask application
app = create_app()

@app.route('/api/config/test-connection', methods=['POST'])
def test_odoo_connection():
    """Test Odoo connection endpoint"""
    try:
        data = request.get_json()
        
        # Extract credentials from request
        url = data.get('url')
        database = data.get('database')
        username = data.get('username')
        password = data.get('password')
        
        if not all([url, database, username, password]):
            return jsonify({
                'success': False,
                'message': 'Missing required credentials (url, database, username, password)'
            }), 400
        
        # Create OdooClient instance with provided credentials
        odoo_client = OdooClient(
            url=url,
            database=database,
            username=username,
            password=password
        )
        
        # Test connection
        result = odoo_client.test_connection()
        
        if result['success']:
            return jsonify({
                'success': True,
                'message': 'Odoo connection successful',
                'user_info': result.get('user_info')
            })
        else:
            return jsonify({
                'success': False,
                'message': result.get('message', 'Connection failed')
            }), 400
            
    except Exception as e:
        logger.error(f"Error testing Odoo connection: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'Connection test failed: {str(e)}'
        }), 500

@app.route('/api/config/test-session-connection', methods=['POST'])
def test_session_connection():
    """Test Odoo connection using stored session credentials"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No JSON data provided'}), 400
            
        session_id = data.get('session_id')
        if not session_id:
            return jsonify({
                'success': False,
                'message': 'Session ID is required',
                'status': 'disconnected'
            }), 400
        
        # Import agent service to get stored credentials
        try:
            from services.agent_service import agent_service
            
            # Get stored credentials from agent service
            client = agent_service.get_odoo_client_for_session(session_id)
            if not client:
                return jsonify({
                    'success': False,
                    'message': 'No credentials found for this session',
                    'status': 'disconnected'
                }), 404
            
            # Test the connection
            result = client.test_connection()
            success = result.get('success', False)
            
            return jsonify({
                'success': success,
                'status': 'connected' if success else 'disconnected',
                'message': result.get('message', 'Session connection successful') if success else result.get('message', 'Session connection failed'),
                'user_info': result.get('user_info', {}) if success else {}
            })
            
        except Exception as session_error:
            logger.error(f"Session error: {str(session_error)}")
            return jsonify({
                'success': False,
                'status': 'disconnected',
                'message': f'Session error: {str(session_error)}'
            }), 500
    
    except Exception as e:
        logger.error(f"Session connection test failed: {str(e)}")
        return jsonify({
            'success': False,
            'status': 'disconnected',
            'message': f'Session connection test failed: {str(e)}'
        }), 500

@app.route('/api/cache/stats', methods=['GET'])
def get_cache_stats():
    """Get cache statistics"""
    try:
        stats = cache_service.get_cache_stats()
        return jsonify({
            'success': True,
            'stats': stats
        })
    except Exception as e:
        logger.error(f"Error getting cache stats: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'Failed to get cache stats: {str(e)}'
        }), 500

@app.route('/api/cache/clear', methods=['POST'])
def clear_cache():
    """Clear all cache entries"""
    try:
        cache_service.clear_cache()
        return jsonify({
            'success': True,
            'message': 'Cache cleared successfully'
        })
    except Exception as e:
        logger.error(f"Error clearing cache: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'Failed to clear cache: {str(e)}'
        }), 500

@app.route('/api/performance/stats', methods=['GET'])
def get_performance_stats():
    """Get performance statistics"""
    try:
        last_n = request.args.get('last_n', type=int)
        stats = performance_monitor.get_stats(last_n)
        return jsonify({
            'success': True,
            'stats': stats
        })
    except Exception as e:
        logger.error(f"Error getting performance stats: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'Failed to get performance stats: {str(e)}'
        }), 500

@app.route('/api/performance/clear', methods=['POST'])
def clear_performance_metrics():
    """Clear performance metrics"""
    try:
        performance_monitor.clear_metrics()
        return jsonify({
            'success': True,
            'message': 'Performance metrics cleared successfully'
        })
    except Exception as e:
        logger.error(f"Error clearing performance metrics: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'Failed to clear performance metrics: {str(e)}'
        }), 500

if __name__ == '__main__':
    # Start cache service
    cache_service.start()
    
    # Register cleanup on exit
    atexit.register(cache_service.stop)
    
    # Get configuration from environment
    host = os.getenv('FLASK_HOST', '127.0.0.1')
    port = int(os.getenv('FLASK_PORT', 5000))
    debug = os.getenv('FLASK_DEBUG', 'False').lower() == 'true'
    
    print(f"Starting OdooSense Flask Backend...")
    print(f"Server running on: http://{host}:{port}")
    print(f"Debug mode: {debug}")
    print(f"API endpoints available at: http://{host}:{port}/api")
    print(f"Cache service: {'Enabled' if cache_service.running else 'Disabled'}")
    
    # Run the application with SocketIO support
    socketio.run(
        app,
        host=host,
        port=port,
        debug=debug,
        allow_unsafe_werkzeug=True  # For development only
    )