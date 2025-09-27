from flask_socketio import emit, join_room, leave_room
from flask import request

def register_socketio_events(socketio):
    """Register SocketIO event handlers."""
    
    @socketio.on('connect')
    def handle_connect():
        """Handle client connection."""
        print(f'Client connected: {request.sid}')
        emit('status', {'message': 'Connected to server'})
    
    @socketio.on('disconnect')
    def handle_disconnect():
        """Handle client disconnection."""
        print(f'Client disconnected: {request.sid}')
    
    @socketio.on('join')
    def handle_join(data):
        """Handle client joining a room."""
        room = data.get('room', 'default')
        join_room(room)
        emit('status', {'message': f'Joined room: {room}'})
    
    @socketio.on('leave')
    def handle_leave(data):
        """Handle client leaving a room."""
        room = data.get('room', 'default')
        leave_room(room)
        emit('status', {'message': f'Left room: {room}'})
    
    @socketio.on('message')
    def handle_message(data):
        """Handle incoming messages."""
        room = data.get('room', 'default')
        message = data.get('message', '')
        
        # Echo the message back to the room
        emit('message', {
            'message': message,
            'sender': request.sid,
            'room': room
        }, room=room)
