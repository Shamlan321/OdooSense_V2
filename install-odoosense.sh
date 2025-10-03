#!/bin/bash

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
WHITE='\033[1;37m'
NC='\033[0m' # No Color

# Installation directory
INSTALL_DIR="$HOME/odoosense"
MAIN_AGENT_DIR="$INSTALL_DIR/OdooSense_V2"

# Function to print colored output
print_color() {
    printf "${1}${2}${NC}\n"
}

# Function to print status
print_status() {
    print_color $GREEN "✓ $1"
}

# Function to print warning
print_warning() {
    print_color $YELLOW "⚠ $1"
}

# Function to print error
print_error() {
    print_color $RED "✗ $1"
}

# Function to print info
print_info() {
    print_color $BLUE "ℹ $1"
}

# Cool ASCII Logo
show_logo() {
    clear
    print_color $CYAN "
      ══════════════════════════════════════════════════════════════════════════════
    ║                                                                                ║
    ║   ██████╗ ██████╗  ██████╗  ██████╗ ███████╗███████╗███╗   ██╗███████╗███████╗ ║
    ║  ██╔═══██╗██╔══██╗██╔═══██╗██╔═══██╗██╔════╝██╔════╝████╗  ██║██╔════╝██╔════╝ ║
    ║  ██║   ██║██║  ██║██║   ██║██║   ██║███████╗█████╗  ██╔██╗ ██║███████╗█████╗   ║
    ║  ██║   ██║██║  ██║██║   ██║██║   ██║╚════██║██╔══╝  ██║╚██╗██║╚════██║██╔══╝   ║
    ║  ╚██████╔╝██████╔╝╚██████╔╝╚██████╔╝███████║███████╗██║ ╚████║███████║███████╗ ║
    ║   ╚═════╝ ╚═════╝  ╚═════╝  ╚═════╝ ╚══════╝╚══════╝╚═╝  ╚═══╝╚══════╝╚══════╝ ║
    ║                                                                                ║
    ║                            by Shamlan Arshad                                   ║
    ║                                                                                ║
        ════════════════════════════════════════════════════════════════════════
    "
    print_color $WHITE "    🚀  Odoo Agent Installation Script 🚀"
    echo ""
}

# Function to check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}


# Function to install Python
install_python() {
    print_info "Installing Python 3..."
    if command_exists apt-get; then
        sudo apt-get update
        sudo apt-get install -y python3 python3-pip python3-venv 
    elif command_exists yum; then
        sudo yum install -y python3 python3-pip
    elif command_exists dnf; then
        sudo dnf install -y python3 python3-pip
    else
        print_error "Unsupported package manager. Please install Python 3 manually."
        exit 1
    fi
    print_status "Python 3 installed successfully"
}

# Function to install Node.js
install_nodejs() {
    print_info "Installing Node.js..."
    if command_exists apt-get; then
        curl -fsSL https://deb.nodesource.com/setup_18.x | sudo -E bash -
        sudo apt-get install -y nodejs
    elif command_exists yum; then
        curl -fsSL https://rpm.nodesource.com/setup_18.x | sudo bash -
        sudo yum install -y nodejs npm
    elif command_exists dnf; then
        curl -fsSL https://rpm.nodesource.com/setup_18.x | sudo bash -
        sudo dnf install -y nodejs npm
    else
        print_error "Unsupported package manager. Please install Node.js manually."
        exit 1
    fi
    print_status "Node.js installed successfully"
}









# Function to inject environment variables
inject_env_vars() {
    local env_file="$1"
    local key="$2"
    local value="$3"
    
    if grep -q "^${key}=" "$env_file"; then
        sed -i "s|^${key}=.*|${key}=${value}|" "$env_file"
    else
        echo "${key}=${value}" >> "$env_file"
    fi
}

# Function to setup main agent environment
setup_main_agent_env() {
    local env_file="$MAIN_AGENT_DIR/.env"
    local gemini_api_key="$1"
    local apify_api_key="$2"
    local bearer_token="$3"
    
    print_info "Setting up main agent environment variables..."
    
    # Update Gemini API key
    inject_env_vars "$env_file" "GEMINI_API_KEY" "$gemini_api_key"
    
    # Update Apify API key if provided
    if [ -n "$apify_api_key" ]; then
        inject_env_vars "$env_file" "APIFY_API_KEY" "$apify_api_key"
    fi
    
    # Add RAG bearer token
    inject_env_vars "$env_file" "RAG_BEARER_TOKEN" "$bearer_token"
    
    print_status "Main agent environment configured"
}



# Function to install Python requirements
install_python_requirements() {
    local dir="$1"
    print_info "Installing Python requirements in $dir..."
    cd "$dir"
    
    if [ -f "requirements.txt" ]; then
        python3 -m pip install --break-system-packages -r requirements.txt
        print_status "Python requirements installed"
    else
        print_warning "No requirements.txt found in $dir"
    fi
}

# Function to install Node.js dependencies
install_node_dependencies() {
    local dir="$1"
    print_info "Installing Node.js dependencies in $dir..."
    cd "$dir"
    
    if [ -f "package.json" ]; then
        npm install
        print_status "Node.js dependencies installed"
    else
        print_warning "No package.json found in $dir"
    fi
}







# Function to start services
start_services() {
    print_info "Starting services..."
    
    # Start main agent backend
    cd "$MAIN_AGENT_DIR"
    print_info "Starting main agent backend..."
    nohup python3 flask_app.py > flask_app.log 2>&1 &
    FLASK_PID=$!
    echo $FLASK_PID > flask_app.pid
    
    # Start frontend
    cd "$MAIN_AGENT_DIR/agent_frontend"
    print_info "Starting frontend..."
    nohup npm start > frontend.log 2>&1 &
    FRONTEND_PID=$!
    echo $FRONTEND_PID > frontend.pid
    
    print_status "All services started"
}

# Function to display URLs
display_urls() {
    echo ""
    print_color $GREEN "🎉 Installation completed successfully! 🎉"
    echo ""
    print_color $CYAN "═══════════════════════════════════════════════════════════════"
    print_color $WHITE "                        ACCESS URLS"
    print_color $CYAN "═══════════════════════════════════════════════════════════════"
    echo ""
    
    # Highlighted main frontend URL
    print_color $YELLOW "🌟 MAIN AGENT FRONTEND (Primary Access Point):"
    print_color $GREEN "   👉 http://localhost:3000"
    echo ""
    
    print_color $WHITE "📡 MAIN AGENT API:"
    print_color $BLUE "   http://localhost:5000"
    echo ""
    
    print_color $CYAN "═══════════════════════════════════════════════════════════════"
    echo ""
    print_color $WHITE "📝 Service logs are available in:"
    print_color $BLUE "   Main Agent: $MAIN_AGENT_DIR/flask_app.log"
    print_color $BLUE "   Frontend:   $MAIN_AGENT_DIR/agent_frontend/frontend.log"
    echo ""
    print_color $WHITE "🛑 To stop services:"
    print_color $BLUE "   kill \$(cat $MAIN_AGENT_DIR/flask_app.pid)"
    print_color $BLUE "   kill \$(cat $MAIN_AGENT_DIR/agent_frontend/frontend.pid)"
    echo ""
}

# Main installation function
main() {
    show_logo
    
    print_info "Welcome to OdooSense_V2 Installation Script!"
    echo ""
    
    # Check if running as root
    if [ "$EUID" -eq 0 ]; then
        print_error "Please do not run this script as root. Run as a regular user with sudo privileges."
        exit 1
    fi
    
    # Create installation directory
    print_info "Creating installation directory: $INSTALL_DIR"
    mkdir -p "$INSTALL_DIR"
    cd "$INSTALL_DIR"
    
    # Only offer standalone installation
    print_color $YELLOW "Installing OdooSense Agent (Standalone)"
    echo ""
    install_rag="no"
    print_status "Selected: Standalone installation"
    
    # Clone repository
    print_info "Cloning OdooSense_V2 repository..."
    git clone https://github.com/Shamlan321/OdooSense_V2.git
    print_status "OdooSense_V2 cloned successfully"
    
    # Get API keys
    echo ""
    print_color $YELLOW "🔑 API Configuration"
    echo ""
    
    while true; do
        read -p "Enter your Gemini API key: " gemini_api_key
        if [ -n "$gemini_api_key" ]; then
            break
        else
            print_error "Gemini API key is required!"
        fi
    done
    
    # LinkedIn integration
    apify_api_key=""
    echo ""
    read -p "Do you want to enable LinkedIn URL lead creation? (y/N): " enable_linkedin
    if [[ $enable_linkedin =~ ^[Yy]$ ]]; then
        read -p "Enter your Apify API key: " apify_api_key
        if [ -n "$apify_api_key" ]; then
            print_status "LinkedIn integration will be enabled"
        else
            print_warning "No Apify API key provided, LinkedIn integration will be disabled"
        fi
    fi
    
    # No bearer token needed for standalone installation
    bearer_token=""
    
    # Check and install dependencies
    echo ""
    print_info "Checking and installing dependencies..."
    
    if ! command_exists python3; then
        install_python
    else
        print_status "Python 3 is already installed"
    fi
    
    if ! command_exists node; then
        install_nodejs
    else
        print_status "Node.js is already installed"
    fi
    
    # No Docker dependencies needed for standalone installation
    
    # Setup environment variables
    setup_main_agent_env "$gemini_api_key" "$apify_api_key" "$bearer_token"
    
    # Install Python requirements for main agent
    install_python_requirements "$MAIN_AGENT_DIR"
    
    # Install Node.js dependencies for frontend
    install_node_dependencies "$MAIN_AGENT_DIR/agent_frontend"
    
    # No RAG agent setup needed for standalone installation
    
    # Start all services
    start_services
    
    # Wait a moment for services to start
    sleep 5
    
    # Display access URLs
    display_urls
    
    print_color $GREEN "🎊 Enjoy using OdooSense_V2! 🎊"
}

# Run main function
main "$@"
