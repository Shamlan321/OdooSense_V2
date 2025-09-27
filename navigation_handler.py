#!/usr/bin/env python3
"""
Standalone Navigation Handler for Odoo AI Agent

Handles direct navigation requests like "Go to sales dashboard", "Open product master data", etc.
Provides immediate navigation shortcuts without requiring documentation lookup.
"""

import re
import logging
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class NavigationShortcut:
    """Represents a navigation shortcut for direct Odoo access"""
    label: str
    url: str
    description: str
    icon: str
    category: str = "general"

class OdooNavigationHandler:
    """Handles standalone navigation requests and generates direct shortcuts"""
    
    def __init__(self):
        # Comprehensive navigation mapping for direct access requests
        self.navigation_shortcuts = {
            # Sales & CRM Navigation
            r'(?:go to|open|show|access|navigate to).*(?:sales? dashboard|sales? overview|sales? summary)': {
                'shortcuts': [
                    {
                        'label': 'Sales Dashboard',
                        'path': 'web#menu_id=sale.menu_sale_reporting',
                        'description': 'View sales dashboard and analytics',
                        'icon': '📊',
                        'category': 'sales'
                    },
                    {
                        'label': 'Sales Orders',
                        'path': 'web#action=sale.action_orders&model=sale.order&view_type=list',
                        'description': 'View all sales orders',
                        'icon': '📋',
                        'category': 'sales'
                    }
                ]
            },
            r'(?:go to|open|show|access).*(?:sales? order|sales? list|quotation)': {
                'shortcuts': [
                    {
                        'label': 'Sales Orders',
                        'path': 'web#action=sale.action_orders&model=sale.order&view_type=list',
                        'description': 'View all sales orders',
                        'icon': '📋',
                        'category': 'sales'
                    },
                    {
                        'label': 'Create Sales Order',
                        'path': 'web#action=sale.action_orders&model=sale.order&view_type=form',
                        'description': 'Create a new sales order',
                        'icon': '🛒',
                        'category': 'sales'
                    }
                ]
            },
            r'(?:go to|open|show|access).*(?:crm|leads?|opportunities|pipeline)': {
                'shortcuts': [
                    {
                        'label': 'CRM Pipeline',
                        'path': 'web#action=crm.crm_lead_opportunities&model=crm.lead&view_type=kanban',
                        'description': 'View CRM pipeline and opportunities',
                        'icon': '💼',
                        'category': 'crm'
                    },
                    {
                        'label': 'Create Lead',
                        'path': 'web#action=crm.crm_lead_all_leads&model=crm.lead&view_type=form',
                        'description': 'Create a new lead',
                        'icon': '🎯',
                        'category': 'crm'
                    }
                ]
            },
            
            # Customer & Partner Management
            r'(?:go to|open|show|access).*(?:customer|contact|partner)(?:s|list|master|data)?': {
                'shortcuts': [
                    {
                        'label': 'Customers',
                        'path': 'web#action=base.action_partner_customer_form&model=res.partner&view_type=list',
                        'description': 'View and manage customers',
                        'icon': '👥',
                        'category': 'contacts'
                    },
                    {
                        'label': 'Create Customer',
                        'path': 'web#action=base.action_partner_form&model=res.partner&view_type=form',
                        'description': 'Add a new customer',
                        'icon': '👤',
                        'category': 'contacts'
                    }
                ]
            },
            
            # Product Management
            r'(?:go to|open|show|access).*(?:product|item)(?:s|list|master|data|catalog)?': {
                'shortcuts': [
                    {
                        'label': 'Product Catalog',
                        'path': 'web#action=product.product_template_action&model=product.template&view_type=list',
                        'description': 'View product catalog',
                        'icon': '📦',
                        'category': 'inventory'
                    },
                    {
                        'label': 'Create Product',
                        'path': 'web#action=product.product_template_action&model=product.template&view_type=form',
                        'description': 'Add a new product',
                        'icon': '📦',
                        'category': 'inventory'
                    }
                ]
            },
            
            # Inventory & Warehouse
            r'(?:go to|open|show|access).*(?:inventory|stock|warehouse|storage)(?:dashboard|overview|summary)?': {
                'shortcuts': [
                    {
                        'label': 'Inventory Dashboard',
                        'path': 'web#menu_id=stock.menu_stock_root',
                        'description': 'Access inventory overview',
                        'icon': '📊',
                        'category': 'inventory'
                    },
                    {
                        'label': 'Stock Levels',
                        'path': 'web#action=stock.action_stock_quant_tree&model=stock.quant&view_type=list',
                        'description': 'View current stock levels',
                        'icon': '📋',
                        'category': 'inventory'
                    }
                ]
            },
            r'(?:go to|open|show|access).*(?:transfer|delivery|receipt|picking)': {
                'shortcuts': [{
                    'label': 'Stock Transfers',
                    'path': 'web#action=stock.action_picking_tree_all&model=stock.picking&view_type=list',
                    'description': 'View stock transfers and deliveries',
                    'icon': '🚚',
                    'category': 'inventory'
                }]
            },
            
            # Accounting & Finance
            r'(?:go to|open|show|access).*(?:accounting|finance)(?:dashboard|overview)?': {
                'shortcuts': [{
                    'label': 'Accounting Dashboard',
                    'path': 'web#menu_id=account.menu_finance',
                    'description': 'Access accounting overview',
                    'icon': '💰',
                    'category': 'accounting'
                }]
            },
            r'(?:go to|open|show|access).*(?:invoice|bill)(?:s|list)?': {
                'shortcuts': [
                    {
                        'label': 'Customer Invoices',
                        'path': 'web#action=account.action_move_out_invoice_type&model=account.move&view_type=list',
                        'description': 'View customer invoices',
                        'icon': '🧾',
                        'category': 'accounting'
                    },
                    {
                        'label': 'Vendor Bills',
                        'path': 'web#action=account.action_move_in_invoice_type&model=account.move&view_type=list',
                        'description': 'View vendor bills',
                        'icon': '📄',
                        'category': 'accounting'
                    }
                ]
            },
            
            # HR & Employee Management
            r'(?:go to|open|show|access).*(?:hr|human|employee)(?:s|dashboard|overview)?': {
                'shortcuts': [
                    {
                        'label': 'Employees',
                        'path': 'web#action=hr.open_view_employee_list_my&model=hr.employee&view_type=list',
                        'description': 'View employee directory',
                        'icon': '👨‍💼',
                        'category': 'hr'
                    },
                    {
                        'label': 'HR Dashboard',
                        'path': 'web#action=hr.hr_employee_action&model=hr.employee&view_type=kanban',
                        'description': 'HR management overview',
                        'icon': '📊',
                        'category': 'hr'
                    }
                ]
            },
            r'(?:go to|open|show|access).*(?:task|to.?do|pending|work)(?:s|list)?': {
                'shortcuts': [
                    {
                        'label': 'My Tasks',
                        'path': 'web#action=project.action_view_task&model=project.task&view_type=list',
                        'description': 'View your pending tasks',
                        'icon': '✅',
                        'category': 'project'
                    },
                    {
                        'label': 'Project Dashboard',
                        'path': 'web#action=project.open_view_project_all&model=project.project&view_type=kanban',
                        'description': 'Project management overview',
                        'icon': '📊',
                        'category': 'project'
                    }
                ]
            },
            
            # Expense Management
            r'(?:go to|open|show|access).*(?:expense|cost)(?:s|list|report)?': {
                'shortcuts': [
                    {
                        'label': 'My Expenses',
                        'path': 'web#action=hr_expense.hr_expense_actions_my_unsubmitted&model=hr.expense&view_type=list',
                        'description': 'View and manage expenses',
                        'icon': '💳',
                        'category': 'hr'
                    },
                    {
                        'label': 'Create Expense',
                        'path': 'web#action=hr_expense.hr_expense_actions_my_unsubmitted&model=hr.expense&view_type=form',
                        'description': 'Submit a new expense',
                        'icon': '💳',
                        'category': 'hr'
                    }
                ]
            },
            
            # Purchase Management
            r'(?:go to|open|show|access).*(?:purchase|buying|procurement)(?:s|order|list)?': {
                'shortcuts': [
                    {
                        'label': 'Purchase Orders',
                        'path': 'web#action=purchase.purchase_rfq&model=purchase.order&view_type=list',
                        'description': 'View purchase orders',
                        'icon': '🛍️',
                        'category': 'purchase'
                    },
                    {
                        'label': 'Create Purchase Order',
                        'path': 'web#action=purchase.purchase_rfq&model=purchase.order&view_type=form',
                        'description': 'Create a new purchase order',
                        'icon': '🛍️',
                        'category': 'purchase'
                    }
                ]
            },
            
            # Settings & Configuration
            r'(?:go to|open|show|access).*(?:setting|config|administration|admin)(?:s|panel)?': {
                'shortcuts': [
                    {
                        'label': 'Settings',
                        'path': 'web#action=base.action_res_config_settings&model=res.config.settings&view_type=form',
                        'description': 'Access system settings',
                        'icon': '⚙️',
                        'category': 'admin'
                    },
                    {
                        'label': 'Users & Access Rights',
                        'path': 'web#action=base.action_res_users&model=res.users&view_type=list',
                        'description': 'Manage users and permissions',
                        'icon': '👥',
                        'category': 'admin'
                    }
                ]
            },
            
            # Calendar & Events
            r'(?:go to|open|show|access).*(?:calendar|event|meeting|appointment)(?:s|list)?': {
                'shortcuts': [{
                    'label': 'Calendar',
                    'path': 'web#action=calendar.action_calendar_event&model=calendar.event&view_type=calendar',
                    'description': 'View calendar and events',
                    'icon': '📅',
                    'category': 'general'
                }]
            },
            
            # Reports & Analytics
            r'(?:go to|open|show|access).*(?:report|analytic|dashboard)(?:s|ing)?': {
                'shortcuts': [
                    {
                        'label': 'Reports Dashboard',
                        'path': 'web#menu_id=base.menu_reporting',
                        'description': 'Access business reports',
                        'icon': '📊',
                        'category': 'reporting'
                    }
                ]
            }
        }
    
    def is_navigation_request(self, message: str) -> bool:
        """
        Check if the message is a direct navigation request.
        Only matches explicit navigation intent, not data lookup queries.
        """
        message_lower = message.lower().strip()
        
        # Explicit navigation patterns - must include clear navigation intent
        navigation_patterns = [
            # Explicit navigation commands
            r'\b(?:navigate to|go to|take me to|direct me to|redirect to)\s+',
            r'\b(?:open|access)\s+(?:the\s+)?(?:page|section|module|dashboard|menu|interface)',
            r'\b(?:show me the|display the)\s+(?:main\s+)?(?:dashboard|menu|page|interface|navigation)',
            
            # Specific dashboard/overview requests
            r'\b(?:open|show|display)\s+(?:the\s+)?(?:main|primary|central)\s+(?:dashboard|overview)',
            r'\b(?:go to|navigate to|open)\s+(?:the\s+)?(?:home|main)\s+(?:page|dashboard)',
            
            # Admin/Settings navigation
            r'\b(?:open|go to|navigate to|access)\s+(?:the\s+)?(?:settings|configuration|admin|setup)',
            
            # Module-specific navigation (when explicitly asking to "navigate to" or "open the X page")
            r'\b(?:navigate to|go to|open)\s+(?:the\s+)?(?:sales|crm|inventory|accounting|hr|project|purchase)\s+(?:module|app|section|dashboard|page)',
            
            # Only match when user explicitly says "navigate to X" or "open X page"
            r'\b(?:navigate to|go to|open)\s+(?:the\s+)?(?:product|customer|contact|partner|lead|opportunity|invoice|bill)\s+(?:list|page|module|section|master)',
            
            # Help finding locations
            r'\b(?:where (?:is|can i find))\s+(?:the\s+)?(?:page|section|module|dashboard|menu)',
        ]
        
        # Data lookup exclusions - these indicate data requests, not navigation
        data_lookup_exclusions = [
            r'\b(?:what|how many|list all|show me all|find all|get all|fetch all)\s+',
            r'\b(?:what are|what is|who are|who is)\s+',
            r'\bfor\s+(?:customer|client|partner)\s+[A-Z]',  # "for Customer Azure Interior"
            r'\b(?:open|show)\s+(?:invoices?|bills?|orders?|products?)\s+(?:for|of|from)',  # "open invoices for..."
            r'\b(?:show me|give me|find me)\s+.*(?:data|information|details|records|entries|list)',
            r'\bhow\s+(?:many|much)',
            r'\b(?:count|total|sum|amount)',
        ]
        
        # First check if it matches exclusion patterns (data lookup)
        for exclusion_pattern in data_lookup_exclusions:
            if re.search(exclusion_pattern, message_lower, re.IGNORECASE):
                return False
        
        # Then check if it matches navigation patterns
        for pattern in navigation_patterns:
            if re.search(pattern, message_lower, re.IGNORECASE):
                return True
        
        return False
    
    def generate_navigation_shortcuts(self, message: str, odoo_base_url: str = None) -> List[NavigationShortcut]:
        """Generate navigation shortcuts based on user request"""
        if not odoo_base_url:
            logger.warning("No Odoo base URL provided for navigation shortcuts")
            return []
        
        # Clean the base URL
        base_url = odoo_base_url.rstrip('/')
        
        shortcuts = []
        message_lower = message.lower().strip()
        
        # Match against navigation patterns
        for pattern, config in self.navigation_shortcuts.items():
            if re.search(pattern, message_lower):
                for shortcut_config in config['shortcuts']:
                    full_url = f"{base_url}/{shortcut_config['path']}"
                    shortcut = NavigationShortcut(
                        label=shortcut_config['label'],
                        url=full_url,
                        description=shortcut_config['description'],
                        icon=shortcut_config['icon'],
                        category=shortcut_config['category']
                    )
                    shortcuts.append(shortcut)
        
        # Remove duplicates while preserving order
        seen = set()
        unique_shortcuts = []
        for shortcut in shortcuts:
            if shortcut.url not in seen:
                seen.add(shortcut.url)
                unique_shortcuts.append(shortcut)
        
        # Limit to 4 most relevant shortcuts
        return unique_shortcuts[:4]
    
    def handle_navigation_request(self, message: str, odoo_base_url: str = None) -> Tuple[bool, str]:
        """
        Handle a navigation request and return response
        
        Args:
            message: User's navigation request
            odoo_base_url: Base URL for Odoo instance
            
        Returns:
            Tuple of (is_navigation_request, formatted_response)
        """
        if not self.is_navigation_request(message):
            return False, ""
        
        shortcuts = self.generate_navigation_shortcuts(message, odoo_base_url)
        
        if not shortcuts:
            # Generic response when no specific shortcuts found
            response = """I understand you want to navigate somewhere in Odoo. Here are some common destinations:

**🧭 Quick Navigation:**

📊 **[Dashboard](# "Main dashboard")** - Main overview
⚙️ **[Settings](# "System settings")** - System configuration
👥 **[Contacts](# "Customer management")** - Customer management
📦 **[Products](# "Product catalog")** - Product catalog

Please provide your Odoo URL in the settings to enable direct navigation links."""
            return True, response
        
        # Generate response with shortcuts
        response = "Here are the navigation shortcuts for your request:\n\n**🧭 Direct Access:**\n"
        
        for shortcut in shortcuts:
            response += f"\n{shortcut.icon} **[{shortcut.label}]({shortcut.url})** - {shortcut.description}"
        
        # Add helpful context
        category_count = len(set(s.category for s in shortcuts))
        if category_count > 1:
            response += f"\n\n💡 Found {len(shortcuts)} relevant shortcuts across {category_count} modules."
        else:
            response += f"\n\n💡 Found {len(shortcuts)} relevant shortcuts in the {shortcuts[0].category} module."
        
        response += "\n\n*Click any button above to open the page directly in Odoo.*"
        
        logger.info(f"Generated {len(shortcuts)} navigation shortcuts for request: {message[:50]}...")
        return True, response
    
    def get_popular_shortcuts(self, odoo_base_url: str = None) -> List[NavigationShortcut]:
        """Get a list of popular/common navigation shortcuts"""
        if not odoo_base_url:
            return []
        
        base_url = odoo_base_url.rstrip('/')
        
        popular_shortcuts = [
            NavigationShortcut(
                label="Sales Dashboard",
                url=f"{base_url}/web#menu_id=sale.menu_sale_reporting",
                description="View sales analytics and performance",
                icon="📊",
                category="sales"
            ),
            NavigationShortcut(
                label="CRM Pipeline",
                url=f"{base_url}/web#action=crm.crm_lead_opportunities&model=crm.lead&view_type=kanban",
                description="Manage leads and opportunities",
                icon="💼",
                category="crm"
            ),
            NavigationShortcut(
                label="Inventory Overview",
                url=f"{base_url}/web#menu_id=stock.menu_stock_root",
                description="Monitor inventory and stock levels",
                icon="📦",
                category="inventory"
            ),
            NavigationShortcut(
                label="My Tasks",
                url=f"{base_url}/web#action=project.action_view_task&model=project.task&view_type=list",
                description="View your pending tasks and projects",
                icon="✅",
                category="project"
            )
        ]
        
        return popular_shortcuts

# Global navigation handler instance
navigation_handler = OdooNavigationHandler() 