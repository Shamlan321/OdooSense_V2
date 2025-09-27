import os
from typing import Dict, Any
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()

@dataclass
class OdooConfig:
    url: str
    database: str
    username: str
    password: str

@dataclass
class GeminiConfig:
    api_key: str
    model_name: str = "gemini-2.5-flash"
    vision_model: str = "gemini-2.5-flash"
    temperature: float = 0.7
    max_tokens: int = 500  # Reduced from 1000 for faster responses

@dataclass
class AgentConfig:
    max_conversation_history: int = 5  # Reduced from 10 for faster processing
    confidence_threshold: float = 0.6  # Reduced from 0.7 for faster classification
    max_retries: int = 2  # Reduced from 3 for faster failure handling
    response_timeout: int = 20  # Reduced from 30 for faster timeouts
    enable_fast_path: bool = True  # Enable fast-path routing
    cache_query_results: bool = True  # Enable query result caching
    max_cache_size: int = 100  # Maximum cached query results

class Config:
    def __init__(self):
        self.odoo = OdooConfig(
            url=os.getenv('ODOO_URL', 'http://localhost:8069'),
            database=os.getenv('ODOO_DATABASE', 'op'),
            username=os.getenv('ODOO_USERNAME', 'admin'),
            password=os.getenv('ODOO_PASSWORD', 'admin')
        )
        
        self.gemini = GeminiConfig(
            api_key=os.getenv('GEMINI_API_KEY', ''),
            model_name=os.getenv('GEMINI_MODEL', 'gemini-2.5-flash'),
            vision_model=os.getenv('GEMINI_VISION_MODEL', 'gemini-2.5-flash')
        )
        
        self.agent = AgentConfig(
            max_conversation_history=int(os.getenv('MAX_CONVERSATION_HISTORY', '10')),
            confidence_threshold=float(os.getenv('CONFIDENCE_THRESHOLD', '0.7')),
            max_retries=int(os.getenv('MAX_RETRIES', '3')),
            response_timeout=int(os.getenv('RESPONSE_TIMEOUT', '60'))
        )
    
    def validate(self) -> bool:
        """Validate configuration settings"""
        if not self.gemini.api_key:
            print("Warning: GEMINI_API_KEY not set. Please set it in .env file or environment variable.")
            return False
        
        if not all([self.odoo.url, self.odoo.database, self.odoo.username, self.odoo.password]):
            print("Warning: Odoo configuration incomplete.")
            return False
        
        return True

# Global config instance
config = Config()