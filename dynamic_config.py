#!/usr/bin/env python3
"""
Configuration management for the dynamic Odoo AI Agent.
This file contains all settings and parameters for the dynamic processing system.
"""

import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
import json

@dataclass
class DynamicAgentConfig:
    """Configuration class for dynamic agent processing"""
    
    # === Core Settings ===
    enabled: bool = True
    """Enable/disable dynamic processing globally"""
    
    fallback_enabled: bool = True
    """Enable fallback to original system on errors"""
    
    debug_mode: bool = False
    """Enable detailed debug logging"""
    
    # === Query Analysis Settings ===
    confidence_threshold: float = 0.3
    """Minimum confidence score to execute a query plan"""
    
    max_query_complexity: int = 10
    """Maximum complexity score for queries (1-10 scale)"""
    
    enable_query_optimization: bool = True
    """Enable automatic query optimization"""
    
    # === Schema Discovery Settings ===
    schema_cache_enabled: bool = True
    """Enable caching of schema information"""
    
    schema_cache_ttl: int = 3600
    """Schema cache TTL in seconds (default: 1 hour)"""
    
    auto_refresh_schema: bool = True
    """Automatically refresh schema on cache miss"""
    
    excluded_models: List[str] = field(default_factory=lambda: [
        'ir.model',
        'ir.model.fields',
        'ir.ui.view',
        'ir.ui.menu',
        'ir.actions.act_window',
        'ir.cron',
        'ir.sequence',
        'base.language.install',
        'base.module.upgrade'
    ])
    """Models to exclude from schema discovery"""
    
    # === Query Execution Settings ===
    max_execution_time: int = 30
    """Maximum query execution time in seconds"""
    
    max_result_size: int = 1000
    """Maximum number of records to return"""
    
    enable_result_caching: bool = True
    """Enable caching of query results"""
    
    result_cache_ttl: int = 300
    """Result cache TTL in seconds (default: 5 minutes)"""
    
    # === LLM Settings ===
    llm_model: str = "gemini-1.5-flash"
    """LLM model to use for query analysis"""
    
    llm_temperature: float = 0.1
    """LLM temperature for query analysis"""
    
    llm_max_tokens: int = 2048
    """Maximum tokens for LLM responses"""
    
    llm_timeout: int = 30
    """LLM request timeout in seconds"""
    
    # === Rollout Settings ===
    rollout_percentage: int = 100
    """Percentage of queries to route to dynamic system (0-100)"""
    
    rollout_user_whitelist: List[str] = field(default_factory=list)
    """User IDs to always use dynamic processing"""
    
    rollout_query_patterns: List[str] = field(default_factory=lambda: [
        r'.*complex.*',
        r'.*custom.*field.*',
        r'.*where.*',
        r'.*filter.*',
        r'.*aggregate.*'
    ])
    """Query patterns that should always use dynamic processing"""
    
    # === Performance Settings ===
    enable_async_processing: bool = True
    """Enable asynchronous query processing"""
    
    max_concurrent_queries: int = 5
    """Maximum number of concurrent queries"""
    
    enable_query_batching: bool = False
    """Enable batching of similar queries"""
    
    # === Error Handling Settings ===
    max_retry_attempts: int = 3
    """Maximum number of retry attempts for failed queries"""
    
    retry_delay: float = 1.0
    """Delay between retry attempts in seconds"""
    
    enable_graceful_degradation: bool = True
    """Enable graceful degradation on errors"""
    
    # === Monitoring Settings ===
    enable_metrics: bool = True
    """Enable performance metrics collection"""
    
    metrics_retention_days: int = 7
    """Number of days to retain metrics data"""
    
    enable_query_logging: bool = True
    """Enable detailed query logging"""
    
    # === Security Settings ===
    allowed_operations: List[str] = field(default_factory=lambda: [
        'search', 'read', 'search_count', 'fields_get'
    ])
    """Allowed Odoo operations for dynamic queries"""
    
    forbidden_fields: List[str] = field(default_factory=lambda: [
        'password', 'api_key', 'token', 'secret'
    ])
    """Fields that should never be accessed"""
    
    enable_field_filtering: bool = True
    """Enable automatic filtering of sensitive fields"""
    
    # === Custom Field Handling ===
    custom_field_prefixes: List[str] = field(default_factory=lambda: [
        'x_', 'custom_', 'ext_'
    ])
    """Prefixes that indicate custom fields"""
    
    enable_custom_field_discovery: bool = True
    """Enable automatic discovery of custom fields"""
    
    # === Business Logic Settings ===
    business_term_mappings: Dict[str, str] = field(default_factory=lambda: {
        'customers': 'res.partner',
        'clients': 'res.partner',
        'vendors': 'res.partner',
        'suppliers': 'res.partner',
        'orders': 'sale.order',
        'sales': 'sale.order',
        'invoices': 'account.move',
        'bills': 'account.move',
        'products': 'product.product',
        'items': 'product.product',
        'employees': 'hr.employee',
        'staff': 'hr.employee',
        'projects': 'project.project',
        'tasks': 'project.task',
        'leads': 'crm.lead',
        'opportunities': 'crm.lead'
    })
    """Mapping of business terms to Odoo models"""
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary"""
        return {
            field.name: getattr(self, field.name)
            for field in self.__dataclass_fields__.values()
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'DynamicAgentConfig':
        """Create configuration from dictionary"""
        # Filter out unknown fields
        valid_fields = {field.name for field in cls.__dataclass_fields__.values()}
        filtered_data = {k: v for k, v in data.items() if k in valid_fields}
        return cls(**filtered_data)
    
    def save_to_file(self, filepath: str) -> None:
        """Save configuration to JSON file"""
        with open(filepath, 'w') as f:
            json.dump(self.to_dict(), f, indent=2, default=str)
    
    @classmethod
    def load_from_file(cls, filepath: str) -> 'DynamicAgentConfig':
        """Load configuration from JSON file"""
        if not os.path.exists(filepath):
            return cls()  # Return default config
        
        with open(filepath, 'r') as f:
            data = json.load(f)
        
        return cls.from_dict(data)

class ConfigManager:
    """Manager for dynamic agent configuration"""
    
    def __init__(self, config_file: Optional[str] = None):
        self.config_file = config_file or os.path.join(
            os.path.dirname(__file__), 'dynamic_agent_config.json'
        )
        self._config = None
        self._load_config()
    
    def _load_config(self) -> None:
        """Load configuration from file or environment"""
        try:
            # Try to load from file first
            if os.path.exists(self.config_file):
                self._config = DynamicAgentConfig.load_from_file(self.config_file)
            else:
                self._config = DynamicAgentConfig()
            
            # Override with environment variables
            self._apply_env_overrides()
            
        except Exception as e:
            print(f"Warning: Failed to load config, using defaults: {e}")
            self._config = DynamicAgentConfig()
    
    def _apply_env_overrides(self) -> None:
        """Apply environment variable overrides"""
        env_mappings = {
            'DYNAMIC_AGENT_ENABLED': ('enabled', bool),
            'DYNAMIC_AGENT_DEBUG': ('debug_mode', bool),
            'DYNAMIC_AGENT_CONFIDENCE_THRESHOLD': ('confidence_threshold', float),
            'DYNAMIC_AGENT_MAX_EXECUTION_TIME': ('max_execution_time', int),
            'DYNAMIC_AGENT_ROLLOUT_PERCENTAGE': ('rollout_percentage', int),
            'DYNAMIC_AGENT_LLM_MODEL': ('llm_model', str),
            'DYNAMIC_AGENT_CACHE_TTL': ('schema_cache_ttl', int),
        }
        
        for env_var, (config_attr, type_func) in env_mappings.items():
            env_value = os.getenv(env_var)
            if env_value is not None:
                try:
                    if type_func == bool:
                        value = env_value.lower() in ('true', '1', 'yes', 'on')
                    else:
                        value = type_func(env_value)
                    setattr(self._config, config_attr, value)
                except (ValueError, TypeError) as e:
                    print(f"Warning: Invalid value for {env_var}: {env_value} ({e})")
    
    @property
    def config(self) -> DynamicAgentConfig:
        """Get current configuration"""
        return self._config
    
    def update_config(self, **kwargs) -> None:
        """Update configuration parameters"""
        for key, value in kwargs.items():
            if hasattr(self._config, key):
                setattr(self._config, key, value)
            else:
                print(f"Warning: Unknown config parameter: {key}")
    
    def save_config(self) -> None:
        """Save current configuration to file"""
        try:
            self._config.save_to_file(self.config_file)
        except Exception as e:
            print(f"Warning: Failed to save config: {e}")
    
    def reload_config(self) -> None:
        """Reload configuration from file"""
        self._load_config()
    
    def get_effective_config(self) -> Dict[str, Any]:
        """Get effective configuration as dictionary"""
        return self._config.to_dict()

# Global configuration instance
_config_manager = None

def get_config() -> DynamicAgentConfig:
    """Get global configuration instance"""
    global _config_manager
    if _config_manager is None:
        _config_manager = ConfigManager()
    return _config_manager.config

def get_config_manager() -> ConfigManager:
    """Get global configuration manager instance"""
    global _config_manager
    if _config_manager is None:
        _config_manager = ConfigManager()
    return _config_manager

def update_config(**kwargs) -> None:
    """Update global configuration"""
    get_config_manager().update_config(**kwargs)

def save_config() -> None:
    """Save global configuration"""
    get_config_manager().save_config()

# Configuration validation
def validate_config(config: DynamicAgentConfig) -> List[str]:
    """Validate configuration and return list of issues"""
    issues = []
    
    # Validate ranges
    if not 0 <= config.confidence_threshold <= 1:
        issues.append("confidence_threshold must be between 0 and 1")
    
    if not 0 <= config.rollout_percentage <= 100:
        issues.append("rollout_percentage must be between 0 and 100")
    
    if config.max_execution_time <= 0:
        issues.append("max_execution_time must be positive")
    
    if config.schema_cache_ttl <= 0:
        issues.append("schema_cache_ttl must be positive")
    
    if config.max_result_size <= 0:
        issues.append("max_result_size must be positive")
    
    # Validate LLM settings
    if not 0 <= config.llm_temperature <= 2:
        issues.append("llm_temperature should be between 0 and 2")
    
    if config.llm_max_tokens <= 0:
        issues.append("llm_max_tokens must be positive")
    
    # Validate security settings
    if not config.allowed_operations:
        issues.append("allowed_operations cannot be empty")
    
    return issues

if __name__ == "__main__":
    # Example usage and testing
    print("Dynamic Agent Configuration")
    print("=" * 40)
    
    # Create default config
    config = DynamicAgentConfig()
    
    # Validate config
    issues = validate_config(config)
    if issues:
        print("Configuration issues:")
        for issue in issues:
            print(f"  - {issue}")
    else:
        print("✓ Configuration is valid")
    
    # Show current settings
    print("\nCurrent settings:")
    for key, value in config.to_dict().items():
        print(f"  {key}: {value}")
    
    # Test config manager
    print("\nTesting config manager...")
    manager = ConfigManager()
    print(f"✓ Config loaded: enabled={manager.config.enabled}")
    
    # Test environment override
    os.environ['DYNAMIC_AGENT_DEBUG'] = 'true'
    manager.reload_config()
    print(f"✓ Environment override: debug_mode={manager.config.debug_mode}")