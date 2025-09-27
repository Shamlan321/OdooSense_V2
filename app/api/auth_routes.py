from flask import Blueprint, request, jsonify
import logging
import uuid

logger = logging.getLogger(__name__)

# Create auth blueprint
auth_bp = Blueprint('auth', __name__, url_prefix='/api/auth')

@auth_bp.route('/check-session', methods=['POST'])
def check_auth_session():
    """Check if user has existing auth session"""
    try:
        # Get browser fingerprint data
        user_agent = request.headers.get('User-Agent', '')
        ip_address = request.environ.get('REMOTE_ADDR', request.environ.get('HTTP_X_FORWARDED_FOR', ''))
        
        from services.auth_service import auth_service
        
        # Check for existing session
        session = auth_service.get_session(user_agent, ip_address)
        
        if session:
            logger.info(f"Found valid auth session for browser {session.browser_id}")
            return jsonify({
                'authenticated': True,
                'session_id': session.session_id,
                'credentials': {
                    'url': session.credentials['url'],
                    'database': session.credentials['database'],
                    'username': session.credentials['username']
                    # Never return password
                },
                'message': 'Valid session found'
            })
        else:
            logger.info("No valid auth session found")
            return jsonify({
                'authenticated': False,
                'message': 'No valid session found'
            })
            
    except Exception as e:
        logger.error(f"Session check failed: {str(e)}")
        return jsonify({
            'authenticated': False,
            'error': f'Session check failed: {str(e)}'
        }), 500

@auth_bp.route('/authenticate', methods=['POST'])
def authenticate():
    """Authenticate user with Odoo credentials and create session"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({
                'success': False,
                'message': 'No data provided'
            }), 400
        
        # Extract credentials
        credentials = {
            'url': data.get('url', '').strip(),
            'database': data.get('database', '').strip(),
            'username': data.get('username', '').strip(),
            'password': data.get('password', '').strip()
        }
        
        # Validate required fields
        required_fields = ['url', 'database', 'username', 'password']
        missing_fields = [field for field in required_fields if not credentials[field]]
        
        if missing_fields:
            return jsonify({
                'success': False,
                'message': f'Missing required fields: {", ".join(missing_fields)}'
            }), 400
        
        # Get browser fingerprint data
        user_agent = request.headers.get('User-Agent', '')
        ip_address = request.environ.get('REMOTE_ADDR', request.environ.get('HTTP_X_FORWARDED_FOR', ''))
        
        from services.auth_service import auth_service
        
        # Authenticate and save
        success, message, session_id = auth_service.authenticate_and_save(
            credentials, user_agent, ip_address
        )
        
        if success:
            logger.info(f"Authentication successful for {credentials['username']} on {credentials['database']}")
            return jsonify({
                'success': True,
                'session_id': session_id,
                'message': message,
                'credentials': {
                    'url': credentials['url'],
                    'database': credentials['database'],
                    'username': credentials['username']
                    # Never return password
                }
            })
        else:
            logger.warning(f"Authentication failed for {credentials['username']}: {message}")
            return jsonify({
                'success': False,
                'message': message
            }), 401
            
    except Exception as e:
        logger.error(f"Authentication error: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'Authentication failed: {str(e)}'
        }), 500

@auth_bp.route('/logout', methods=['POST'])
def logout():
    """Clear auth session"""
    try:
        # Get browser fingerprint data
        user_agent = request.headers.get('User-Agent', '')
        ip_address = request.environ.get('REMOTE_ADDR', request.environ.get('HTTP_X_FORWARDED_FOR', ''))
        
        from services.auth_service import auth_service
        
        # Clear session
        success = auth_service.clear_session(user_agent, ip_address)
        
        if success:
            logger.info("Session cleared successfully")
            return jsonify({
                'success': True,
                'message': 'Session cleared successfully'
            })
        else:
            return jsonify({
                'success': False,
                'message': 'Failed to clear session'
            }), 500
            
    except Exception as e:
        logger.error(f"Logout error: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'Logout failed: {str(e)}'
        }), 500

@auth_bp.route('/get-credentials', methods=['POST'])
def get_credentials():
    """Get credentials for authenticated session"""
    try:
        # Get browser fingerprint data
        user_agent = request.headers.get('User-Agent', '')
        ip_address = request.environ.get('REMOTE_ADDR', request.environ.get('HTTP_X_FORWARDED_FOR', ''))
        
        from services.auth_service import auth_service
        
        # Get session
        session = auth_service.get_session(user_agent, ip_address)
        
        if session:
            return jsonify({
                'success': True,
                'session_id': session.session_id,
                'credentials': session.credentials  # Include password for agent use
            })
        else:
            return jsonify({
                'success': False,
                'message': 'No valid session found'
            }), 404
            
    except Exception as e:
        logger.error(f"Get credentials error: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'Failed to get credentials: {str(e)}'
        }), 500 