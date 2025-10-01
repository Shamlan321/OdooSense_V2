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
RAG_AGENT_DIR="$INSTALL_DIR/odoo-exper-gemini"

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
    ╔═══════════════════════════════════════════════════════════════╗
    ║                                                               ║
    ║    ██████╗ ██████╗  ██████╗  ██████╗ ███████╗███████╗███╗   ██╗ ║
    ║   ██╔═══██╗██╔══██╗██╔═══██╗██╔═══██╗██╔════╝██╔════╝████╗  ██║ ║
    ║   ██║   ██║██║  ██║██║   ██║██║   ██║███████╗█████╗  ██╔██╗ ██║ ║
    ║   ██║   ██║██║  ██║██║   ██║██║   ██║╚════██║██╔══╝  ██║╚██╗██║ ║
    ║   ╚██████╔╝██████╔╝╚██████╔╝╚██████╔╝███████║███████╗██║ ╚████║ ║
    ║    ╚═════╝ ╚═════╝  ╚═════╝  ╚═════╝ ╚══════╝╚══════╝╚═╝  ╚═══╝ ║
    ║                                                               ║
    ║                    ██╗   ██╗██████╗                          ║
    ║                    ██║   ██║╚════██╗                         ║
    ║                    ██║   ██║ █████╔╝                         ║
    ║                    ╚██╗ ██╔╝██╔═══╝                          ║
    ║                     ╚████╔╝ ███████╗                         ║
    ║                      ╚═══╝  ╚══════╝                         ║
    ║                                                               ║
    ║                    by Shamlan Arshad                         ║
    ║                                                               ║
    ╚═══════════════════════════════════════════════════════════════╝
    "
    print_color $WHITE "    🚀 AI-Powered Odoo Agent Installation Script 🚀"
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

# Function to install Docker and Docker Compose
install_docker() {
    print_info "Installing Docker and Docker Compose..."
    
    # Remove any existing problematic docker-compose installations
    print_info "Removing any existing problematic docker-compose installations..."
    sudo apt-get remove -y docker-compose 2>/dev/null || true
    sudo pip uninstall -y docker-compose 2>/dev/null || true
    sudo pip3 uninstall -y docker-compose 2>/dev/null || true
    sudo rm -f /usr/local/bin/docker-compose /usr/bin/docker-compose 2>/dev/null || true
    
    # Use Docker's convenience script which handles all distributions
    print_info "Downloading Docker installation script..."
    curl -fsSL https://get.docker.com -o get-docker.sh
    
    # Run the Docker installation script
    print_info "Running Docker installation script..."
    sudo sh get-docker.sh
    
    # Clean up the script
    rm get-docker.sh
    
    # Add user to docker group
    sudo usermod -aG docker "$USER"
    
    # Enable and start Docker service
    sudo systemctl enable docker
    sudo systemctl start docker
    
    print_status "Docker installed successfully"
    
    # Install Docker Compose V2 plugin (modern approach)
    print_info "Installing Docker Compose V2 plugin..."
    
    # Create docker CLI plugins directory
    mkdir -p ~/.docker/cli-plugins/
    
    # Get latest version
    DOCKER_COMPOSE_VERSION=$(curl -s https://api.github.com/repos/docker/compose/releases/latest | grep 'tag_name' | cut -d\" -f4)
    
    # Download Docker Compose V2 plugin
    curl -SL "https://github.com/docker/compose/releases/download/${DOCKER_COMPOSE_VERSION}/docker-compose-$(uname -s)-$(uname -m)" -o ~/.docker/cli-plugins/docker-compose
    chmod +x ~/.docker/cli-plugins/docker-compose
    
    # Also install system-wide for all users
    sudo curl -SL "https://github.com/docker/compose/releases/download/${DOCKER_COMPOSE_VERSION}/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/lib/docker/cli-plugins/docker-compose 2>/dev/null || true
    sudo chmod +x /usr/local/lib/docker/cli-plugins/docker-compose 2>/dev/null || true
    
    # Create system-wide CLI plugins directory if it doesn't exist
    sudo mkdir -p /usr/local/lib/docker/cli-plugins/ 2>/dev/null || true
    sudo curl -SL "https://github.com/docker/compose/releases/download/${DOCKER_COMPOSE_VERSION}/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/lib/docker/cli-plugins/docker-compose 2>/dev/null || true
    sudo chmod +x /usr/local/lib/docker/cli-plugins/docker-compose 2>/dev/null || true
    
    print_status "Docker Compose V2 plugin installed successfully"
    print_warning "Please log out and log back in for Docker group changes to take effect, or run: newgrp docker"
}

# Function to execute Docker commands with proper permissions
execute_docker_cmd() {
    local cmd="$1"
    shift
    local args="$@"
    
    # Test if we can run docker commands directly
    if docker version >/dev/null 2>&1; then
        # Direct execution works
        $cmd $args
        return $?
    fi
    
    # Check if user is in docker group but group membership isn't active
    if groups "$USER" | grep -q docker && command_exists sg; then
        print_info "Activating docker group membership for command execution..."
        sg docker -c "$cmd $args"
        return $?
    fi
    
    # Fallback: provide clear error message
    print_error "Cannot execute Docker command: $cmd $args"
    print_error "Docker permissions are not properly configured."
    print_error "Please ensure:"
    print_error "1. Docker daemon is running"
    print_error "2. User is in docker group: sudo usermod -aG docker \$USER"
    print_error "3. Log out and back in to activate group membership"
    return 1
}

# Function to detect Docker Compose command
get_docker_compose_cmd() {
    # First, prioritize modern docker compose (V2 plugin)
    if docker compose version >/dev/null 2>&1; then
        echo "docker compose"
        return
    fi
    
    # Test legacy docker-compose but check for compatibility issues
    if command_exists docker-compose; then
        # Test if legacy docker-compose works properly with a simple command
        if docker-compose --version >/dev/null 2>&1; then
            # Additional test to check for ssl_version compatibility issue
            if docker-compose config --help >/dev/null 2>&1; then
                print_warning "Using legacy docker-compose. Consider upgrading to Docker Compose V2."
                echo "docker-compose"
                return
            else
                print_warning "Legacy docker-compose has compatibility issues. Attempting to use modern docker compose."
                # Try to force use modern docker compose even if version check failed
                if command_exists docker; then
                    echo "docker compose"
                    return
                fi
            fi
        fi
    fi
    
    # If neither works, show error with helpful instructions
    print_error "Neither docker-compose nor docker compose is working properly."
    print_error "This may be due to:"
    print_error "1. Docker not being installed properly"
    print_error "2. User not being in the docker group"
    print_error "3. Legacy docker-compose compatibility issues"
    print_error ""
    print_error "Please try the following:"
    print_error "1. Ensure Docker is running: sudo systemctl start docker"
    print_error "2. Add user to docker group: sudo usermod -aG docker \$USER"
    print_error "3. Log out and back in, or run: newgrp docker"
    print_error "4. Re-run this installation script"
    exit 1
}

# Function to generate random bearer token
generate_bearer_token() {
    openssl rand -base64 32 | tr -d "=+/" | cut -c1-32
}

# Function to update rag_client.py to use environment variable
update_rag_client() {
    local rag_client_file="$MAIN_AGENT_DIR/rag_client.py"
    print_info "Updating rag_client.py to use environment variable for API token..."
    
    # Backup original file
    cp "$rag_client_file" "$rag_client_file.backup"
    
    # Replace hardcoded token with environment variable
    sed -i 's/self\.api_token = api_token or "4S6BZAlC3DnUhR8rMk3Q6wg1dICzW1yKfwz1Belq6ZY"/self.api_token = api_token or os.getenv("RAG_BEARER_TOKEN", "4S6BZAlC3DnUhR8rMk3Q6wg1dICzW1yKfwz1Belq6ZY")/' "$rag_client_file"
    
    # Add import os if not present
    if ! grep -q "import os" "$rag_client_file"; then
        sed -i '3i import os' "$rag_client_file"
    fi
    
    print_status "rag_client.py updated successfully"
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
    
    # Configure Flask for network access
    inject_env_vars "$env_file" "FLASK_HOST" "0.0.0.0"
    inject_env_vars "$env_file" "FLASK_PORT" "5000"
    inject_env_vars "$env_file" "FLASK_DEBUG" "False"
    
    print_status "Main agent environment configured"
}

# Function to setup RAG agent environment
setup_rag_agent_env() {
    local gemini_api_key="$1"
    local bearer_token="$2"
    
    print_info "Setting up RAG agent environment variables..."
    
    # Copy .env.example to .env
    cp "$RAG_AGENT_DIR/.env.example" "$RAG_AGENT_DIR/.env"
    
    local env_file="$RAG_AGENT_DIR/.env"
    
    # Update environment variables
    inject_env_vars "$env_file" "GOOGLE_API_KEY" "$gemini_api_key"
    inject_env_vars "$env_file" "BEARER_TOKEN" "$bearer_token"
    inject_env_vars "$env_file" "POSTGRES_USER" "odoo_expert"
    inject_env_vars "$env_file" "POSTGRES_PASSWORD" "$(openssl rand -base64 16)"
    inject_env_vars "$env_file" "POSTGRES_DB" "odoo_expert_db"
    inject_env_vars "$env_file" "POSTGRES_HOST" "db"
    inject_env_vars "$env_file" "POSTGRES_PORT" "5432"
    
    print_status "RAG agent environment configured"
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

# Function to ensure Docker permissions
ensure_docker_permissions() {
    local docker_socket="/var/run/docker.sock"
    local user_in_docker_group=false
    
    # Check if user is in docker group
    if groups "$USER" | grep -q docker; then
        user_in_docker_group=true
    fi
    
    # Ensure Docker daemon is running
    if ! sudo systemctl is-active --quiet docker; then
        print_info "Starting Docker daemon..."
        sudo systemctl start docker
        sleep 2
    fi
    
    # Check if Docker socket exists and get its permissions
    if [ -S "$docker_socket" ]; then
        local socket_group=$(stat -c '%G' "$docker_socket" 2>/dev/null || echo "")
        local socket_perms=$(stat -c '%a' "$docker_socket" 2>/dev/null || echo "")
        
        print_info "Docker socket found at $docker_socket (group: $socket_group, permissions: $socket_perms)"
        
        # Test if user can access Docker without sudo
        if docker version >/dev/null 2>&1; then
            print_status "Docker permissions are correctly configured"
            return 0
        fi
    fi
    
    # If user is not in docker group, add them
    if [ "$user_in_docker_group" = false ]; then
        print_warning "User not in docker group. Adding user to docker group..."
        sudo usermod -aG docker "$USER"
        print_info "User added to docker group"
    fi
    
    # Fix Docker socket permissions if needed
    if [ -S "$docker_socket" ]; then
        print_info "Ensuring Docker socket has correct permissions..."
        sudo chown root:docker "$docker_socket"
        sudo chmod 660 "$docker_socket"
    fi
    
    # Test Docker access again
    if docker version >/dev/null 2>&1; then
        print_success "Docker permissions fixed successfully"
        return 0
    fi
    
    # If still not working, try using sg command for group activation
    print_warning "Docker permissions still not working. Attempting group activation..."
    if command_exists sg; then
        print_info "Using 'sg docker' to activate docker group membership for this session"
        print_warning "Note: Docker commands in this script will now run with proper group permissions"
        return 0
    fi
    
    # Last resort: provide clear instructions
    print_error "Docker permissions could not be automatically fixed."
    print_info "Please run the following commands manually:"
    print_info "  sudo usermod -aG docker \$USER"
    print_info "  sudo systemctl restart docker"
    print_info "  newgrp docker"
    print_info "Or log out and log back in to activate the docker group membership."
    return 1
}

# Function to fix Docker Compose compatibility issues
fix_docker_compose_issues() {
    print_info "Detecting and fixing Docker Compose compatibility issues..."
    
    # Check if we have the ssl_version error with legacy docker-compose
    if command_exists docker-compose; then
        # Test for the specific ssl_version error
        if docker-compose --version >/dev/null 2>&1; then
            # Try a simple config command to detect ssl_version issue
            if ! docker-compose config --help >/dev/null 2>&1; then
                print_warning "Detected legacy docker-compose compatibility issue (ssl_version error)"
                print_info "Removing problematic legacy docker-compose installation..."
                
                # Remove the problematic installation
                sudo apt-get remove -y docker-compose 2>/dev/null || true
                sudo pip uninstall -y docker-compose 2>/dev/null || true
                sudo pip3 uninstall -y docker-compose 2>/dev/null || true
                sudo rm -f /usr/local/bin/docker-compose /usr/bin/docker-compose 2>/dev/null || true
                
                # Install Docker Compose V2 plugin if not already installed
                if ! docker compose version >/dev/null 2>&1; then
                    print_info "Installing Docker Compose V2 plugin..."
                    
                    # Create docker CLI plugins directory
                    mkdir -p ~/.docker/cli-plugins/
                    
                    # Get latest version
                    DOCKER_COMPOSE_VERSION=$(curl -s https://api.github.com/repos/docker/compose/releases/latest | grep 'tag_name' | cut -d\" -f4)
                    
                    # Download Docker Compose V2 plugin
                    curl -SL "https://github.com/docker/compose/releases/download/${DOCKER_COMPOSE_VERSION}/docker-compose-$(uname -s)-$(uname -m)" -o ~/.docker/cli-plugins/docker-compose
                    chmod +x ~/.docker/cli-plugins/docker-compose
                    
                    # Also install system-wide
                    sudo mkdir -p /usr/local/lib/docker/cli-plugins/ 2>/dev/null || true
                    sudo curl -SL "https://github.com/docker/compose/releases/download/${DOCKER_COMPOSE_VERSION}/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/lib/docker/cli-plugins/docker-compose 2>/dev/null || true
                    sudo chmod +x /usr/local/lib/docker/cli-plugins/docker-compose 2>/dev/null || true
                    
                    print_status "Docker Compose V2 plugin installed successfully"
                else
                    print_status "Docker Compose V2 plugin is already available"
                fi
            fi
        fi
    fi
}

# Function to setup RAG agent with Docker
setup_rag_agent_docker() {
    print_info "Setting up RAG agent with Docker..."
    cd "$RAG_AGENT_DIR"
    
    # Ensure Docker permissions are set up
    ensure_docker_permissions
    
    # Fix any Docker Compose compatibility issues
    fix_docker_compose_issues
    
    # Get the correct Docker Compose command
    local docker_compose_cmd=$(get_docker_compose_cmd)
    
    # Start Docker services with error handling
    print_info "Starting Docker services using: $docker_compose_cmd"
    if ! execute_docker_cmd $docker_compose_cmd up -d; then
        print_warning "Failed to start Docker services with $docker_compose_cmd. Attempting to fix compatibility issues..."
        
        # Try to fix issues and retry
        fix_docker_compose_issues
        docker_compose_cmd=$(get_docker_compose_cmd)
        
        print_info "Retrying with: $docker_compose_cmd"
        if ! execute_docker_cmd $docker_compose_cmd up -d; then
            print_error "Failed to start Docker services after attempting fixes."
            print_error "Please check Docker installation and permissions."
            print_info "You can try running manually: cd $RAG_AGENT_DIR && $docker_compose_cmd up -d"
            exit 1
        fi
    fi
    
    # Wait for services to be ready
    print_info "Waiting for services to start..."
    sleep 30
    
    # Pull raw data with error handling
    print_info "Pulling Odoo documentation..."
    if ! execute_docker_cmd $docker_compose_cmd run --rm odoo-expert ./pull_rawdata.sh; then
        print_warning "Failed to pull raw data automatically. You may need to run this manually later."
    fi
    
    # Convert RST to Markdown with error handling
    print_info "Converting RST files to Markdown..."
    if ! execute_docker_cmd $docker_compose_cmd run --rm odoo-expert python main.py process-raw; then
        print_warning "Failed to process raw files. You may need to run this manually later."
    fi
    
    # Process documents and create embeddings with error handling
    print_info "Processing documents and creating embeddings (this may take a while)..."
    if ! execute_docker_cmd $docker_compose_cmd run --rm odoo-expert python main.py process-docs; then
        print_warning "Failed to process documents. You may need to run this manually later."
        print_info "You can manually run: cd $RAG_AGENT_DIR && $docker_compose_cmd run --rm odoo-expert python main.py process-docs"
    fi
    
    print_status "RAG agent setup completed"
}

# Function to start services
start_services() {
    local install_rag="$1"
    
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
    
    # Start RAG agent if installed
    if [ "$install_rag" = "yes" ]; then
        cd "$RAG_AGENT_DIR"
        print_info "Starting RAG agent..."
        local docker_compose_cmd=$(get_docker_compose_cmd)
        execute_docker_cmd $docker_compose_cmd up -d
    fi
    
    print_status "All services started"
}

# Function to display URLs
display_urls() {
    local install_rag="$1"
    
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
    
    if [ "$install_rag" = "yes" ]; then
        print_color $WHITE "📚 DOCUMENTATION RAG AGENT:"
        print_color $BLUE "   API: http://localhost:8000"
        print_color $BLUE "   UI:  http://localhost:8501"
        echo ""
    fi
    
    print_color $CYAN "═══════════════════════════════════════════════════════════════"
    echo ""
    print_color $WHITE "📝 Service logs are available in:"
    print_color $BLUE "   Main Agent: $MAIN_AGENT_DIR/flask_app.log"
    print_color $BLUE "   Frontend:   $MAIN_AGENT_DIR/agent_frontend/frontend.log"
    if [ "$install_rag" = "yes" ]; then
        print_color $BLUE "   RAG Agent:  $RAG_AGENT_DIR (docker-compose logs)"
    fi
    echo ""
    print_color $WHITE "🛑 To stop services:"
    print_color $BLUE "   kill \$(cat $MAIN_AGENT_DIR/flask_app.pid)"
    print_color $BLUE "   kill \$(cat $MAIN_AGENT_DIR/agent_frontend/frontend.pid)"
    if [ "$install_rag" = "yes" ]; then
        local docker_compose_cmd=$(get_docker_compose_cmd)
        if [[ "$docker_compose_cmd" == *"docker compose"* ]]; then
            print_color $BLUE "   cd $RAG_AGENT_DIR && docker compose down"
        else
            print_color $BLUE "   cd $RAG_AGENT_DIR && docker-compose down"
        fi
    fi
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
    
    # Show installation options
    print_color $YELLOW "Please choose an installation option:"
    echo ""
    print_color $WHITE "1) 🚀 OdooSense Agent (Standalone)"
    print_color $WHITE "2) 🚀 OdooSense Agent + Documentation Assistant (Full Setup)"
    echo ""
    
    while true; do
        read -p "Enter your choice (1 or 2): " choice
        case $choice in
            1)
                install_rag="no"
                print_status "Selected: Standalone installation"
                break
                ;;
            2)
                install_rag="yes"
                print_warning "Installing Documentation Assistant can take quite a bit of time (an Hour maybe)"
                echo ""
                read -p "Do you want to proceed? (y/N): " proceed
                if [[ $proceed =~ ^[Yy]$ ]]; then
                    print_status "Selected: Full installation with Documentation Assistant"
                    break
                else
                    print_info "Installation cancelled"
                    exit 0
                fi
                ;;
            *)
                print_error "Invalid choice. Please enter 1 or 2."
                ;;
        esac
    done
    
    # Clone repositories
    print_info "Cloning OdooSense_V2 repository..."
    git clone https://github.com/Shamlan321/OdooSense_V2.git
    print_status "OdooSense_V2 cloned successfully"
    
    if [ "$install_rag" = "yes" ]; then
        print_info "Cloning RAG agent repository..."
        git clone https://github.com/Shamlan321/odoo-exper-gemini.git
        print_status "RAG agent cloned successfully"
    fi
    
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
    
    # Generate bearer token for RAG communication
    bearer_token=""
    if [ "$install_rag" = "yes" ]; then
        bearer_token=$(generate_bearer_token)
        print_status "Generated bearer token for RAG communication"
    fi
    
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
    
    if [ "$install_rag" = "yes" ]; then
        # Check if Docker is installed and working
        if ! command_exists docker || ! sudo docker --version >/dev/null 2>&1; then
            install_docker
        else
            print_status "Docker is already installed"
            # Still need to add user to docker group if not already
            if ! groups "$USER" | grep -q docker; then
                print_info "Adding user to docker group..."
                sudo usermod -aG docker "$USER"
                print_warning "Please log out and log back in for Docker group changes to take effect, or run: newgrp docker"
            fi
        fi
        
        # Check if Docker Compose is installed
        if ! command_exists docker-compose && ! docker compose version >/dev/null 2>&1; then
            print_info "Installing Docker Compose..."
            DOCKER_COMPOSE_VERSION=$(curl -s https://api.github.com/repos/docker/compose/releases/latest | grep 'tag_name' | cut -d\" -f4)
            sudo curl -L "https://github.com/docker/compose/releases/download/${DOCKER_COMPOSE_VERSION}/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
            sudo chmod +x /usr/local/bin/docker-compose
            sudo ln -sf /usr/local/bin/docker-compose /usr/bin/docker-compose 2>/dev/null || true
            print_status "Docker Compose installed successfully"
        else
            # Determine which Docker Compose command is available
            if command_exists docker-compose; then
                print_status "Docker Compose (legacy) is already installed"
            elif docker compose version >/dev/null 2>&1; then
                print_status "Docker Compose (modern) is already installed"
            fi
        fi
    fi
    
    # Update rag_client.py if RAG is being installed
    if [ "$install_rag" = "yes" ]; then
        update_rag_client
    fi
    
    # Setup environment variables
    setup_main_agent_env "$gemini_api_key" "$apify_api_key" "$bearer_token"
    
    if [ "$install_rag" = "yes" ]; then
        setup_rag_agent_env "$gemini_api_key" "$bearer_token"
    fi
    
    # Install Python requirements for main agent
    install_python_requirements "$MAIN_AGENT_DIR"
    
    # Install Node.js dependencies for frontend
    install_node_dependencies "$MAIN_AGENT_DIR/agent_frontend"
    
    # Setup RAG agent if selected
    if [ "$install_rag" = "yes" ]; then
        setup_rag_agent_docker
    fi
    
    # Start all services
    start_services "$install_rag"
    
    # Wait a moment for services to start
    sleep 5
    
    # Display access URLs
    display_urls "$install_rag"
    
    print_color $GREEN "🎊 Enjoy using OdooSense_V2! 🎊"
}

# Run main function
main "$@"
