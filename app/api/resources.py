from flask_restful import Resource
from flask import jsonify

class HealthResource(Resource):
    """Health check resource."""
    
    def get(self):
        return {
            'status': 'healthy',
            'message': 'API is running'
        }

class InfoResource(Resource):
    """API information resource."""
    
    def get(self):
        return {
            'api_title': 'Flask API',
            'version': 'v1',
            'description': 'A modular Flask API with SocketIO support'
        }

def register_resources(api):
    """Register API resources."""
    api.add_resource(HealthResource, '/health')
    api.add_resource(InfoResource, '/info')
