from flask import jsonify, request, Response, send_file
from app.api import bp
from services.agent_service import AgentService
import os
import uuid
import logging
import traceback
from werkzeug.utils import secure_filename
from services.agent_service import agent_service
from services.enhanced_agent_service import enhanced_agent_service

# Configure verbose logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

@bp.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint."""
    return jsonify({
        'status': 'healthy',
        'message': 'API is running'
    })

@bp.route('/info', methods=['GET'])
def api_info():
    """API information endpoint."""
    return jsonify({
        'api_title': 'OdooSense API',
        'version': 'v1',
        'description': 'AI-powered Odoo management API with natural language processing'
    })

@bp.route('/chat', methods=['POST'])
def chat():
    """Chat endpoint for natural language queries."""
    try:
        logger.info("=== CHAT ENDPOINT START ===")
        data = request.get_json()
        logger.debug(f"Request data: {data}")
        
        message = data.get('message', '')
        
        # Get browser fingerprint for authentication
        user_agent = request.headers.get('User-Agent', '')
        ip_address = request.environ.get('REMOTE_ADDR', request.environ.get('HTTP_X_FORWARDED_FOR', ''))
        
        # Use new auth integration to get session ID and credentials
        from services.agent_auth_integration import agent_auth_integration
        
        # Check if request is authenticated
        if not agent_auth_integration.is_request_authenticated(user_agent, ip_address):
            logger.warning("Unauthenticated request to chat endpoint")
            return jsonify({
                'error': 'Authentication required',
                'status': 'unauthenticated'
            }), 401
        
        # Get session ID from auth session
        session_id = agent_auth_integration.get_session_id_for_request(user_agent, ip_address)
        if not session_id:
            logger.error("No session ID found for authenticated request")
            return jsonify({
                'error': 'Session not found',
                'status': 'error'
            }), 400
        
        logger.info(f"Processing message: '{message}' for authenticated session: {session_id}")
        
        if not message:
            logger.warning("No message provided in request")
            return jsonify({'error': 'Message is required'}), 400
        
        # Get credentials for the agent services
        credentials = agent_auth_integration.get_credentials_for_request(user_agent, ip_address)
        if not credentials:
            logger.error("No credentials found for authenticated session")
            return jsonify({
                'error': 'Credentials not found',
                'status': 'error'
            }), 400
        
        # Initialize agent services with credentials if needed
        from services.enhanced_agent_service import enhanced_agent_service
        
        # Ensure agent has access to credentials
        try:
            # Set credentials in the main agent service
            from services.agent_service import agent_service
            agent_service.save_odoo_credentials(session_id, credentials)
        except Exception as cred_error:
            logger.warning(f"Failed to set credentials in agent service: {str(cred_error)}")
        
        # Process message through enhanced agent service with extended timeout
        logger.debug("Calling enhanced_agent_service.chat()")
        try:
            response = enhanced_agent_service.chat(message, session_id)
            logger.debug(f"Enhanced agent service response: {response}")
        except Exception as e:
            logger.error(f"Enhanced agent service timeout or error: {str(e)}")
            return jsonify({
                'error': f'Agent request timed out or failed: {str(e)}',
                'status': 'error'
            }), 408
        
        if response is None:
            logger.error("Agent service returned None response")
            return jsonify({
                'error': 'Agent service returned None response',
                'status': 'error'
            }), 500
        
        # Check if response has the expected structure
        if not isinstance(response, dict):
            logger.error(f"Agent service returned non-dict response: {type(response)}")
            return jsonify({
                'error': f'Agent service returned invalid response type: {type(response)}',
                'status': 'error'
            }), 500
        
        logger.info(f"Successfully processed message for session: {session_id}")
        return jsonify({
            'response': response.get('response', ''),
            'files': response.get('files', []),
            'html_content': response.get('html_content', ''),  # Add HTML content for charts
            'session_id': session_id,
            'agent_type': response.get('agent_type', 'main_agent'),
            'status': 'success'
        })
    
    except Exception as e:
        logger.error(f"Chat endpoint error: {str(e)}")
        logger.error(f"Full traceback: {traceback.format_exc()}")
        return jsonify({
            'error': str(e),
            'status': 'error'
        }), 500

@bp.route('/reporting/chat', methods=['POST'])
def reporting_chat():
    """Dedicated endpoint for reporting agent chat."""
    try:
        logger.info("=== REPORTING CHAT ENDPOINT START ===")
        data = request.get_json()
        logger.debug(f"Request data: {data}")
        
        message = data.get('message', '')
        session_id = data.get('session_id', str(uuid.uuid4()))
        report_type = data.get('report_type', 'auto')
        
        logger.info(f"Processing reporting message: '{message}' for session: {session_id}")
        
        if not message:
            logger.warning("No message provided in request")
            return jsonify({'error': 'Message is required'}), 400
        
        # Process message through reporting agent with extended timeout
        logger.debug("Calling enhanced_agent_service.chat() for reporting")
        try:
            response = enhanced_agent_service.chat(message, session_id)
            logger.debug(f"Reporting agent response: {response}")
        except Exception as e:
            logger.error(f"Reporting agent timeout or error: {str(e)}")
            return jsonify({
                'error': f'Reporting agent request timed out or failed: {str(e)}',
                'status': 'error'
            }), 408
        
        if response is None:
            logger.error("Reporting agent returned None response")
            return jsonify({
                'error': 'Reporting agent returned None response',
                'status': 'error'
            }), 500
        
        # Check if response has the expected structure
        if not isinstance(response, dict):
            logger.error(f"Reporting agent returned non-dict response: {type(response)}")
            return jsonify({
                'error': f'Reporting agent returned invalid response type: {type(response)}',
                'status': 'error'
            }), 500
        
        logger.info(f"Successfully processed reporting message for session: {session_id}")
        return jsonify({
            'response': response.get('response', ''),
            'files': response.get('files', []),
            'session_id': session_id,
            'agent_type': response.get('agent_type', 'reporting_agent'),
            'status': 'success'
        })
    
    except Exception as e:
        logger.error(f"Reporting chat endpoint error: {str(e)}")
        logger.error(f"Full traceback: {traceback.format_exc()}")
        return jsonify({
            'error': str(e),
            'status': 'error'
        }), 500

@bp.route('/reporting/files/<session_id>', methods=['GET'])
def get_reporting_files(session_id):
    """Get list of generated files for a session."""
    try:
        files = enhanced_agent_service.get_generated_files(session_id)
        return jsonify({
            'files': files,
            'session_id': session_id,
            'status': 'success'
        })
    except Exception as e:
        logger.error(f"Error getting reporting files: {str(e)}")
        return jsonify({
            'error': str(e),
            'status': 'error'
        }), 500

@bp.route('/reporting/download/<session_id>/<filename>', methods=['GET'])
def download_report(session_id, filename):
    """Download a generated report file."""
    try:
        # Get browser fingerprint for authentication
        user_agent = request.headers.get('User-Agent', '')
        ip_address = request.environ.get('REMOTE_ADDR', request.environ.get('HTTP_X_FORWARDED_FOR', ''))
        
        # Use new auth integration to verify authentication
        from services.agent_auth_integration import agent_auth_integration
        
        # Check if request is authenticated
        if not agent_auth_integration.is_request_authenticated(user_agent, ip_address):
            logger.warning("Unauthenticated request to download endpoint")
            return jsonify({
                'error': 'Authentication required',
                'status': 'unauthenticated'
            }), 401
        
        # Get the authenticated session ID (this should match the provided session_id)
        auth_session_id = agent_auth_integration.get_session_id_for_request(user_agent, ip_address)
        if not auth_session_id:
            logger.error("No session ID found for authenticated request")
            return jsonify({
                'error': 'Session not found',
                'status': 'error'
            }), 400
        
        # Verify the session_id matches the authenticated session (security check)
        if session_id != auth_session_id:
            logger.warning(f"Session ID mismatch: URL={session_id}, Auth={auth_session_id}")
            return jsonify({
                'error': 'Session mismatch',
                'status': 'error'
            }), 403
        
        # Get file path from dynamic reporting agent service
        file_path = enhanced_agent_service.get_file_download_url(filename, session_id)
        
        if not file_path or not os.path.exists(file_path):
            return jsonify({
                'error': 'File not found',
                'status': 'error'
            }), 404
        
        # Determine content type based on file extension
        file_extension = filename.lower().split('.')[-1]
        content_type_map = {
            'pdf': 'application/pdf',
            'png': 'image/png',
            'jpg': 'image/jpeg',
            'jpeg': 'image/jpeg',
            'html': 'text/html',
            'csv': 'text/csv',
            'xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        }
        
        content_type = content_type_map.get(file_extension, 'application/octet-stream')
        
        # Return file for download
        return send_file(
            file_path,
            as_attachment=True,
            download_name=filename,
            mimetype=content_type
        )
        
    except Exception as e:
        logger.error(f"Error downloading file: {str(e)}")
        return jsonify({
            'error': str(e),
            'status': 'error'
        }), 500

@bp.route('/files/<path:file_path>', methods=['GET'])
def serve_file(file_path):
    """Serve files by their full path for Odoo module integration."""
    try:
        # Decode the file path and ensure it's safe
        import urllib.parse
        decoded_path = urllib.parse.unquote(file_path)
        
        # Security check: ensure the path exists and is within allowed directories
        if not os.path.exists(decoded_path):
            logger.error(f"File not found: {decoded_path}")
            return jsonify({
                'error': 'File not found',
                'status': 'error'
            }), 404
        
        # Additional security: ensure the file is in the reports directory
        reports_dir = os.path.abspath('reports')
        file_abs_path = os.path.abspath(decoded_path)
        
        if not file_abs_path.startswith(reports_dir):
            logger.error(f"Access denied to file outside reports directory: {decoded_path}")
            return jsonify({
                'error': 'Access denied',
                'status': 'error'
            }), 403
        
        # Determine content type based on file extension
        filename = os.path.basename(decoded_path)
        file_extension = filename.lower().split('.')[-1]
        content_type_map = {
            'pdf': 'application/pdf',
            'png': 'image/png',
            'jpg': 'image/jpeg',
            'jpeg': 'image/jpeg',
            'html': 'text/html',
            'csv': 'text/csv',
            'xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        }
        
        content_type = content_type_map.get(file_extension, 'application/octet-stream')
        
        logger.info(f"Serving file: {decoded_path} with content-type: {content_type}")
        return send_file(file_abs_path, mimetype=content_type)
        
    except Exception as e:
        logger.error(f"Error serving file: {str(e)}")
        return jsonify({
            'error': str(e),
            'status': 'error'
        }), 500

@bp.route('/reporting/initialize', methods=['POST'])
def initialize_reporting_agent():
    """Initialize dynamic reporting agent with credentials."""
    try:
        data = request.get_json()
        credentials = data.get('credentials', {})
        session_id = data.get('session_id', str(uuid.uuid4()))
        
        if not credentials:
            return jsonify({
                'error': 'Credentials are required',
                'status': 'error'
            }), 400
        
        success = enhanced_agent_service.initialize_dynamic_reporting_agent(credentials, session_id)
        
        return jsonify({
            'success': success,
            'session_id': session_id,
            'status': 'success' if success else 'error'
        })
        
    except Exception as e:
        logger.error(f"Error initializing dynamic reporting agent: {str(e)}")
        return jsonify({
            'error': str(e),
            'status': 'error'
        }), 500

@bp.route('/reporting/routing-info', methods=['POST'])
def get_routing_info():
    """Get detailed routing information for a message."""
    try:
        data = request.get_json()
        message = data.get('message', '')
        
        if not message:
            return jsonify({
                'error': 'Message is required',
                'status': 'error'
            }), 400
        
        # Determine agent type based on message content
        agent_type = enhanced_agent_service._determine_agent_type(message)
        
        return jsonify({
            'routing_info': {
                'agent_type': agent_type,
                'message': message,
                'keywords_found': [keyword for keyword in [
                    'report', 'chart', 'graph', 'pdf', 'generate', 'create',
                    'bar chart', 'line chart', 'pie chart', 'scatter plot',
                    'visualization', 'plot', 'diagram', 'statistics',
                    'sales report', 'customer report', 'invoice report',
                    'monthly report', 'quarterly report', 'annual report',
                    'export', 'download', 'save as', 'print'
                ] if keyword in message.lower()]
            },
            'status': 'success'
        })
        
    except Exception as e:
        logger.error(f"Error getting routing info: {str(e)}")
        return jsonify({
            'error': str(e),
            'status': 'error'
        }), 500

@bp.route('/chat/stream', methods=['POST'])
def chat_stream():
    """Streaming chat endpoint for natural language queries."""
    try:
        data = request.get_json()
        message = data.get('message', '')
        session_id = data.get('session_id', str(uuid.uuid4()))
        
        if not message:
            return jsonify({'error': 'Message is required'}), 400
        
        # Return streaming response
        def generate():
            for chunk in agent_service.chat_stream(message, session_id):
                yield chunk
        
        return Response(generate(), mimetype='text/event-stream')
        
    except Exception as e:
        return jsonify({
            'error': str(e),
            'status': 'error'
        }), 500

@bp.route('/upload', methods=['POST'])
def upload_document():
    """Document upload endpoint for processing files."""
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'No file provided'}), 400
        
        file = request.files['file']
        session_id = request.form.get('session_id', str(uuid.uuid4()))
        preview_mode = request.form.get('preview_mode', 'false').lower() == 'true'
        document_type = request.form.get('document_type')  # Get document type from form
        
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
        
        # Read file data
        filename = secure_filename(file.filename)
        file_data = file.read()
        mime_type = file.content_type or 'application/octet-stream'
        
        if preview_mode:
            # Extract data without processing to Odoo
            response = agent_service.document_preview(file_data, filename, mime_type, session_id, doc_type=document_type)
        else:
            # Process document through agent service
            response = agent_service.document_ingestion(file_data, filename, mime_type, session_id, doc_type=document_type)
        
        return jsonify({
            'response': response.get('response', ''),
            'session_id': session_id,
            'status': 'success',
            'filename': filename,
            'extracted_data': response.get('extracted_data'),
            'preview_mode': preview_mode,
            'document_type': document_type
        })
    
    except Exception as e:
        return jsonify({
            'error': str(e),
            'status': 'error'
        }), 500

@bp.route('/upload/confirm', methods=['POST'])
def confirm_document_processing():
    """Confirm and process extracted document data to Odoo."""
    try:
        print(f"[CONSOLE DEBUG] /upload/confirm endpoint called")
        data = request.get_json()
        print(f"[CONSOLE DEBUG] Request data: {data}")
        
        session_id = data.get('session_id')
        extracted_data = data.get('extracted_data')
        document_type = data.get('document_type')  # Get document type from request
        
        print(f"[CONSOLE DEBUG] Session ID: {session_id}")
        print(f"[CONSOLE DEBUG] Document type: {document_type}")
        print(f"[CONSOLE DEBUG] Extracted data keys: {list(extracted_data.keys()) if extracted_data else 'None'}")
        
        if not session_id:
            return jsonify({'error': 'Session ID is required'}), 400
        
        if not extracted_data:
            return jsonify({'error': 'Extracted data is required'}), 400
        
        print(f"[CONSOLE DEBUG] About to call agent_service.process_confirmed_data")
        # Process the confirmed data to Odoo
        response = agent_service.process_confirmed_data(extracted_data, session_id, document_type=document_type)
        print(f"[CONSOLE DEBUG] Agent service response: {response}")
        
        return jsonify({
            'response': response.get('response', ''),
            'session_id': session_id,
            'status': 'success'
        })
    
    except Exception as e:
        return jsonify({
            'error': str(e),
            'status': 'error'
        }), 500

@bp.route('/config/test-and-save-connection', methods=['POST'])
def test_and_save_odoo_connection():
    """Test and save Odoo connection in one request for streamlined flow."""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No JSON data provided'}), 400
            
        url = data.get('url')
        database = data.get('database')
        username = data.get('username')
        password = data.get('password', '')
        session_id = data.get('session_id', str(uuid.uuid4()))
        
        # DEBUG: Log session information
        logger.info(f"[TEST-AND-SAVE] Received session_id: {session_id}")
        logger.info(f"[TEST-AND-SAVE] Request data keys: {list(data.keys())}")
        
        # Check required fields
        missing_fields = []
        if not url:
            missing_fields.append('url')
        if not database:
            missing_fields.append('database')
        if not username:
            missing_fields.append('username')
        if not password:
            missing_fields.append('password')
            
        if missing_fields:
            return jsonify({
                'success': False,
                'message': f'Missing required fields: {", ".join(missing_fields)}',
                'status': 'error',
                'session_id': session_id
            }), 400
        
        # Test connection first
        from odoo_client import OdooClient
        
        client = OdooClient(url=url, database=database, username=username, password=password)
        test_result = client.test_connection()
        
        # Handle the response from test_connection
        test_success = test_result.get('status') == 'success'
        
        if not test_success:
            return jsonify({
                'success': False,
                'status': 'test_failed',
                'message': test_result.get('error', 'Connection test failed'),
                'session_id': session_id
            }), 400
        
        # Connection test passed, now save credentials
        try:
            credentials = {
                'url': url,
                'database': database,
                'username': username,
                'password': password
            }
            
            save_success = agent_service.save_odoo_credentials(session_id, credentials)
            
            if save_success:
                logger.info(f"[TEST-AND-SAVE] Credentials saved successfully for session: {session_id}")
                return jsonify({
                    'success': True,
                    'status': 'saved',
                    'message': 'Connection tested and credentials saved successfully',
                    'session_id': session_id,
                    'user_info': test_result.get('user', {}),
                    'odoo_version': test_result.get('version', {}).get('server_version', '')
                })
            else:
                return jsonify({
                    'success': False,
                    'status': 'save_failed',
                    'message': 'Connection test passed but failed to save credentials',
                    'session_id': session_id
                }), 500
                
        except Exception as save_error:
            return jsonify({
                'success': False,
                'status': 'save_failed',
                'message': f'Failed to save credentials: {str(save_error)}',
                'session_id': session_id
            }), 500
    
    except Exception as e:
        return jsonify({
            'success': False,
            'status': 'error',
            'message': f'Request failed: {str(e)}',
            'session_id': session_id if 'session_id' in locals() else None
        }), 500

@bp.route('/config/test-connection', methods=['POST'])
def test_odoo_connection():
    """Test Odoo connection endpoint."""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No JSON data provided'}), 400
            
        url = data.get('url')
        database = data.get('database')
        username = data.get('username')
        password = data.get('password', '')
        
        # Check required fields
        missing_fields = []
        if not url:
            missing_fields.append('url')
        if not database:
            missing_fields.append('database')
        if not username:
            missing_fields.append('username')
        if not password:
            missing_fields.append('password')
            
        if missing_fields:
            return jsonify({
                'success': False,
                'message': f'Missing required fields: {", ".join(missing_fields)}',
                'status': 'disconnected'
            }), 400
        
        # Test connection using odoo_client
        from odoo_client import OdooClient
        
        client = OdooClient(url=url, database=database, username=username, password=password)
        result = client.test_connection()
        
        # Handle the response from test_connection
        success = result.get('status') == 'success'
        
        return jsonify({
            'success': success,
            'status': 'connected' if success else 'disconnected',
            'message': result.get('error', 'Connection successful') if not success else 'Connection successful',
            'odoo_version': result.get('version', {}).get('server_version', '') if success else '',
            'user_info': result.get('user', {}) if success else {}
        })
    
    except Exception as e:
        return jsonify({
            'success': False,
            'status': 'disconnected',
            'message': f'Connection test failed: {str(e)}'
        }), 500

@bp.route('/config/test-session-connection', methods=['POST'])
def test_session_connection():
    """Test Odoo connection using stored session credentials."""
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
        
        # Get stored credentials from agent service
        try:
            client = agent_service.get_odoo_client_for_session(session_id)
            if not client:
                return jsonify({
                    'success': False,
                    'message': 'No credentials found for this session',
                    'status': 'disconnected'
                }), 404
            
            # Test the connection
            result = client.test_connection()
            success = result.get('status') == 'success'
            
            return jsonify({
                'success': success,
                'status': 'connected' if success else 'disconnected',
                'message': result.get('error', 'Session connection successful') if not success else 'Session connection successful',
                'odoo_version': result.get('version', {}).get('server_version', '') if success else '',
                'user_info': result.get('user', {}) if success else {}
            })
            
        except Exception as session_error:
            return jsonify({
                'success': False,
                'status': 'disconnected',
                'message': f'Session error: {str(session_error)}'
            }), 500
    
    except Exception as e:
        return jsonify({
            'success': False,
            'status': 'disconnected',
            'message': f'Session connection test failed: {str(e)}'
        }), 500

@bp.route('/config/credentials', methods=['POST'])
def save_odoo_credentials():
    """Save Odoo credentials for the session."""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No JSON data provided'}), 400
        
        # Extract credentials
        url = data.get('url')
        database = data.get('database')
        username = data.get('username')
        password = data.get('password')
        session_id = data.get('session_id', str(uuid.uuid4()))
        
        # Validate required fields
        if not all([url, database, username, password]):
            return jsonify({
                'success': False,
                'message': 'Missing required credentials (url, database, username, password)'
            }), 400
        
        # Store credentials in agent service (you may want to implement session-based storage)
        agent_service.save_odoo_credentials(session_id, {
            'url': url,
            'database': database,
            'username': username,
            'password': password
        })
        
        return jsonify({
            'success': True,
            'message': 'Credentials saved successfully',
            'session_id': session_id
        })
    
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Failed to save credentials: {str(e)}'
        }), 500

@bp.route('/config/credentials', methods=['GET'])
def get_odoo_credentials():
    """Get current Odoo credentials for the session."""
    try:
        session_id = request.args.get('session_id')
        if not session_id:
            return jsonify({'error': 'Session ID is required'}), 400
        
        # Get credentials from agent service
        credentials = agent_service.get_odoo_credentials(session_id)
        
        if credentials:
            # Don't return the password for security
            safe_credentials = {
                'url': credentials.get('url', ''),
                'database': credentials.get('database', ''),
                'username': credentials.get('username', ''),
                'has_password': bool(credentials.get('password'))
            }
            return jsonify({
                'success': True,
                'credentials': safe_credentials
            })
        else:
            return jsonify({
                'success': False,
                'message': 'No credentials found for this session'
            })
    
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Failed to get credentials: {str(e)}'
        }), 500

@bp.route('/config/credentials', methods=['DELETE'])
def clear_odoo_credentials():
    """Clear Odoo credentials for the session."""
    try:
        session_id = request.args.get('session_id')
        if not session_id:
            return jsonify({'error': 'Session ID is required'}), 400
        
        # Clear credentials from agent service
        success = agent_service.clear_odoo_credentials(session_id)
        
        if success:
            return jsonify({
                'success': True,
                'message': 'Credentials cleared successfully'
            })
        else:
            return jsonify({
                'success': False,
                'message': 'Failed to clear credentials'
            }), 500
    
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Failed to clear credentials: {str(e)}'
        }), 500

@bp.route('/config/session-info', methods=['GET'])
def get_session_info():
    """Get session information."""
    try:
        session_info = agent_service.get_session_info()
        return jsonify({
            'success': True,
            'session_info': session_info
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Failed to get session info: {str(e)}'
        }), 500

@bp.route('/conversation/<session_id>', methods=['GET'])
def get_conversation_history(session_id):
    """Get conversation history for a session."""
    try:
        history = agent_service.get_conversation_history(session_id)
        return jsonify({
            'history': history,
            'session_id': session_id,
            'status': 'success'
        })
    
    except Exception as e:
        return jsonify({
            'error': str(e),
            'status': 'error'
        }), 500

@bp.route('/features', methods=['GET'])
def get_supported_features():
    """Get list of supported features."""
    try:
        features = agent_service.get_supported_features()
        return jsonify({
            'features': features,
            'status': 'success'
        })
    
    except Exception as e:
        return jsonify({
            'error': str(e),
            'status': 'error'
        }), 500

@bp.route('/test', methods=['GET', 'POST'])
def test_endpoint():
    """Test endpoint for debugging."""
    # Write to log file to verify endpoint is being called
    import logging
    logging.basicConfig(filename='flask_debug.log', level=logging.DEBUG, 
                       format='%(asctime)s - %(levelname)s - %(message)s')
    logger = logging.getLogger(__name__)
    
    logger.info(f"[DEBUG] Test endpoint called with method: {request.method}")
    logger.info(f"[DEBUG] Request data: {request.get_json() if request.is_json else 'No JSON data'}")
    logger.info(f"[DEBUG] This is a test print statement")
    
    print(f"[DEBUG] Test endpoint called with method: {request.method}")
    print(f"[DEBUG] Request data: {request.get_json() if request.is_json else 'No JSON data'}")
    print(f"[DEBUG] This is a test print statement")
    import sys
    sys.stdout.flush()
    
    from datetime import datetime
    return jsonify({
        'message': 'Test endpoint working',
        'method': request.method,
        'timestamp': datetime.now().isoformat()
    })

@bp.route('/test-dynamic-crud', methods=['POST'])
def test_dynamic_crud():
    """Test endpoint for dynamic CRUD agent integration."""
    try:
        logger.info("=== TEST DYNAMIC CRUD ENDPOINT START ===")
        data = request.get_json()
        logger.debug(f"Request data: {data}")
        
        message = data.get('message', 'How many sales orders do we have?')
        session_id = data.get('session_id', str(uuid.uuid4()))
        
        logger.info(f"Testing dynamic CRUD with message: '{message}' for session: {session_id}")
        
        # Import the dynamic CRUD agent service directly
        from services.dynamic_crud_agent_service import dynamic_crud_agent_service
        
        # Test if message is detected as CRUD operation
        is_crud = dynamic_crud_agent_service.is_crud_query(message)
        
        logger.info(f"Message detected as CRUD operation: {is_crud}")
        
        # Process message through enhanced agent service 
        logger.debug("Calling enhanced_agent_service.chat() for CRUD test")
        try:
            response = enhanced_agent_service.chat(message, session_id)
            logger.debug(f"Enhanced agent service response: {response}")
        except Exception as e:
            logger.error(f"Enhanced agent service error: {str(e)}")
            return jsonify({
                'error': f'Agent request failed: {str(e)}',
                'status': 'error',
                'is_crud_detected': is_crud
            }), 500
        
        if response is None:
            logger.error("Agent service returned None response")
            return jsonify({
                'error': 'Agent service returned None response',
                'status': 'error',
                'is_crud_detected': is_crud
            }), 500
        
        logger.info(f"Successfully processed test message for session: {session_id}")
        return jsonify({
            'response': response.get('response', ''),
            'agent_type': response.get('agent_type', 'unknown'),
            'success': response.get('success', False),
            'session_id': session_id,
            'is_crud_detected': is_crud,
            'status': 'success'
        })
        
    except Exception as e:
        logger.error(f"Test dynamic CRUD endpoint failed: {str(e)}")
        return jsonify({
            'error': str(e),
            'status': 'error'
        }), 500
