import xmlrpc.client
import logging
from typing import Dict, List, Any, Optional, Union
from config import config

logger = logging.getLogger(__name__)

class OdooClient:
    def __init__(self, url=None, database=None, username=None, password=None):
        # Use provided parameters or fall back to config
        self.url = url or config.odoo.url
        self.db = database or config.odoo.database
        self.username = username or config.odoo.username
        self.password = password or config.odoo.password
        self.uid = None
        self.models = None
        self.common = None
        
    def connect(self) -> bool:
        """Establish connection to Odoo instance"""
        try:
            # Connect to common endpoint
            self.common = xmlrpc.client.ServerProxy(f'{self.url}/xmlrpc/2/common')
            
            # Authenticate
            self.uid = self.common.authenticate(self.db, self.username, self.password, {})
            
            if not self.uid:
                logger.error("Authentication failed")
                return False
            
            # Connect to object endpoint
            self.models = xmlrpc.client.ServerProxy(f'{self.url}/xmlrpc/2/object')
            
            logger.info(f"Successfully connected to Odoo as user ID: {self.uid}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to connect to Odoo: {str(e)}")
            return False
    
    def search(self, model: str, domain: List = None, limit: int = None, offset: int = 0) -> List[int]:
        """Search for records in a model"""
        if not self.models:
            raise Exception("Not connected to Odoo")
        
        domain = domain or []
        kwargs = {'offset': offset}
        if limit:
            kwargs['limit'] = limit
            
        return self.models.execute_kw(
            self.db, self.uid, self.password,
            model, 'search', [domain], kwargs
        )
    
    def search_count(self, model: str, domain: List = None) -> int:
        """Count records matching the domain"""
        if not self.models:
            raise Exception("Not connected to Odoo")
        
        domain = domain or []
        
        return self.models.execute_kw(
            self.db, self.uid, self.password,
            model, 'search_count', [domain]
        )
    
    def read(self, model: str, ids: Union[int, List[int]], fields: List[str] = None) -> List[Dict]:
        """Read records from a model"""
        if not self.models:
            raise Exception("Not connected to Odoo")
        
        if isinstance(ids, int):
            ids = [ids]
        
        kwargs = {}
        if fields:
            kwargs['fields'] = fields
            
        return self.models.execute_kw(
            self.db, self.uid, self.password,
            model, 'read', [ids], kwargs
        )
    
    def search_read(self, model: str, domain: List = None, fields: List[str] = None, 
                   limit: int = None, offset: int = 0) -> List[Dict]:
        """Search and read records in one call"""
        if not self.models:
            raise Exception("Not connected to Odoo")
        
        domain = domain or []
        kwargs = {'offset': offset}
        if limit:
            kwargs['limit'] = limit
        if fields:
            kwargs['fields'] = fields
            
        return self.models.execute_kw(
            self.db, self.uid, self.password,
            model, 'search_read', [domain], kwargs
        )
    
    def create(self, model: str, values: Dict) -> int:
        """Create a new record"""
        if not self.models:
            raise Exception("Not connected to Odoo")
        
        return self.models.execute_kw(
            self.db, self.uid, self.password,
            model, 'create', [values]
        )
    
    def write(self, model: str, ids: Union[int, List[int]], values: Dict) -> bool:
        """Update existing records"""
        if not self.models:
            raise Exception("Not connected to Odoo")
        
        if isinstance(ids, int):
            ids = [ids]
            
        return self.models.execute_kw(
            self.db, self.uid, self.password,
            model, 'write', [ids, values]
        )
    
    def unlink(self, model: str, ids: Union[int, List[int]]) -> bool:
        """Delete records"""
        if not self.models:
            raise Exception("Not connected to Odoo")
        
        if isinstance(ids, int):
            ids = [ids]
            
        return self.models.execute_kw(
            self.db, self.uid, self.password,
            model, 'unlink', [ids]
        )
    
    def get_model_fields(self, model: str) -> Dict:
        """Get field definitions for a model"""
        if not self.models:
            raise Exception("Not connected to Odoo")
        
        return self.models.execute_kw(
            self.db, self.uid, self.password,
            model, 'fields_get', []
        )
    
    def call_method(self, model: str, method: str, args: List = None, kwargs: Dict = None) -> Any:
        """Call a custom method on a model"""
        if not self.models:
            raise Exception("Not connected to Odoo")
        
        args = args or []
        kwargs = kwargs or {}
        
        return self.models.execute_kw(
            self.db, self.uid, self.password,
            model, method, args, kwargs
        )
    
    # Convenience methods for common operations
    def find_partner_by_name(self, name: str) -> Optional[Dict]:
        """Find a partner (customer/vendor) by name"""
        if not name:
            return None
            
        partners = self.search_read(
            'res.partner',
            [('name', 'ilike', name)],
            ['id', 'name', 'email', 'phone', 'is_company'],
            limit=1
        )
        return partners[0] if partners else None
    
    def find_product_by_name(self, name: str) -> Optional[Dict]:
        """Find a product by name"""
        if not name:
            return None
            
        products = self.search_read(
            'product.product',
            [('name', 'ilike', name)],
            ['id', 'name', 'default_code', 'list_price', 'standard_price'],
            limit=1
        )
        return products[0] if products else None
    
    def get_user_info(self) -> Dict:
        """Get current user information"""
        if not self.uid:
            raise Exception("Not authenticated")
        
        user_info = self.read('res.users', self.uid, ['name', 'email', 'company_id'])
        return user_info[0] if user_info else {}
    
    def test_connection(self) -> Dict[str, Any]:
        """Test the connection and return system info"""
        try:
            if not self.connect():
                return {'status': 'failed', 'error': 'Authentication failed'}
            
            user_info = self.get_user_info()
            version_info = self.common.version()
            
            return {
                'status': 'success',
                'user': user_info,
                'version': version_info,
                'database': self.db,
                'url': self.url
            }
        except Exception as e:
            return {'status': 'error', 'error': str(e)}

# Global client instance
odoo_client = OdooClient()