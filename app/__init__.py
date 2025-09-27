from flask import Flask
from flask_socketio import SocketIO
from flask_restful import Api
from flask_cors import CORS
from flask_config import get_config
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv('rag_config_enhanced.env')

# Initialize extensions
socketio = SocketIO()
api = Api()
cors = CORS()

def create_app(config_name=None):
    """Application factory pattern."""
    app = Flask(__name__)
    
    # Load configuration
    if config_name:
        from flask_config import config
        app.config.from_object(config[config_name])
    else:
        app.config.from_object(get_config())
    
    # Initialize extensions with app
    cors.init_app(app, origins=app.config.get('CORS_ORIGINS', ['http://localhost:3000', 'http://127.0.0.1:3000']))
    
    socketio.init_app(app, 
                     cors_allowed_origins=app.config.get('CORS_ORIGINS', '*'),
                     async_mode=app.config.get('SOCKETIO_ASYNC_MODE', 'threading'))
    
    api.init_app(app)
    
    # Register blueprints
    from app.api import bp as api_bp
    app.register_blueprint(api_bp, url_prefix='/api')
    
    # Register new auth blueprint
    from app.api.auth_routes import auth_bp
    app.register_blueprint(auth_bp)
    
    # Register SocketIO events
    from app.services.socketio_service import register_socketio_events
    register_socketio_events(socketio)
    
    return app
