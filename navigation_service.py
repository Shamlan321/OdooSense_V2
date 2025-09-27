#!/usr/bin/env python3

import logging
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
import re

logger = logging.getLogger(__name__)

@dataclass
class NavigationTarget:
    """Represents a navigation target in Odoo"""
    name: str
    menu_id: Optional[int]
    action_id: Optional[int]
    model: Optional[str]
    view_type: str = "tree"
    domain: List = None
    context: Dict = None
    url_path: str = ""
    description: str = ""

class OdooNavigationService:
    """Service for handling Odoo navigation and shortcuts"""
    
    def __init__(self, odoo_client):
        self.odoo_client = odoo_client
        self.navigation_map = self._build_navigation_map()
        
    def _build_navigation_map(self) -> Dict[str, NavigationTarget]:
        """Build a comprehensive navigation map for common Odoo modules"""
        return {
            # Sales Module
            "sales dashboard": NavigationTarget(
                name="Sales Dashboard",
                menu_id=None,
                action_id=None,
                model="sale.order",
                view_type="kanban",
                url_path="/web#action=sale.action_orders&model=sale.order&view_type=kanban",
                description="Main sales dashboard with quotations and orders"
            ),
            "sales orders": NavigationTarget(
                name="Sales Orders",
                menu_id=None,
                action_id=None,
                model="sale.order",
                view_type="tree",
                domain=[("state", "in", ["sale", "done"])],
                url_path="/web#action=sale.action_orders&model=sale.order&view_type=list",
                description="All confirmed sales orders"
            ),
            "quotations": NavigationTarget(
                name="Quotations",
                menu_id=None,
                action_id=None,
                model="sale.order",
                view_type="tree",
                domain=[("state", "in", ["draft", "sent"])],
                url_path="/web#action=sale.action_quotations&model=sale.order&view_type=list",
                description="Sales quotations and draft orders"
            ),
            "customers": NavigationTarget(
                name="Customers",
                menu_id=None,
                action_id=None,
                model="res.partner",
                view_type="tree",
                domain=[("is_company", "=", True), ("customer_rank", ">", 0)],
                url_path="/web#action=base.action_partner_form&model=res.partner&view_type=list",
                description="Customer database"
            ),
            
            # CRM Module
            "crm dashboard": NavigationTarget(
                name="CRM Dashboard",
                menu_id=None,
                action_id=None,
                model="crm.lead",
                view_type="kanban",
                url_path="/web#action=crm.crm_lead_action_pipeline&model=crm.lead&view_type=kanban",
                description="CRM pipeline and opportunities"
            ),
            "leads": NavigationTarget(
                name="Leads",
                menu_id=None,
                action_id=None,
                model="crm.lead",
                view_type="tree",
                domain=[("type", "=", "lead")],
                url_path="/web#action=crm.crm_lead_all_leads&model=crm.lead&view_type=list",
                description="All CRM leads"
            ),
            "opportunities": NavigationTarget(
                name="Opportunities",
                menu_id=None,
                action_id=None,
                model="crm.lead",
                view_type="tree",
                domain=[("type", "=", "opportunity")],
                url_path="/web#action=crm.crm_lead_opportunities&model=crm.lead&view_type=list",
                description="Sales opportunities"
            ),
            
            # Inventory Module
            "inventory dashboard": NavigationTarget(
                name="Inventory Dashboard",
                menu_id=None,
                action_id=None,
                model="stock.quant",
                view_type="tree",
                url_path="/web#action=stock.dashboard&model=stock.quant&view_type=list",
                description="Inventory overview and stock levels"
            ),
            "products": NavigationTarget(
                name="Products",
                menu_id=None,
                action_id=None,
                model="product.product",
                view_type="tree",
                url_path="/web#action=product.product_normal_action&model=product.product&view_type=list",
                description="Product catalog"
            ),
            "stock moves": NavigationTarget(
                name="Stock Moves",
                menu_id=None,
                action_id=None,
                model="stock.move",
                view_type="tree",
                url_path="/web#action=stock.action_stock_move_line&model=stock.move&view_type=list",
                description="Inventory movements and transfers"
            ),
            
            # Accounting Module
            "accounting dashboard": NavigationTarget(
                name="Accounting Dashboard",
                menu_id=None,
                action_id=None,
                model="account.move",
                view_type="kanban",
                url_path="/web#action=account.action_move_journal_line&model=account.move&view_type=kanban",
                description="Accounting overview and journal entries"
            ),
            "invoices": NavigationTarget(
                name="Customer Invoices",
                menu_id=None,
                action_id=None,
                model="account.move",
                view_type="tree",
                domain=[("move_type", "=", "out_invoice")],
                url_path="/web#action=account.action_move_out_invoice_type&model=account.move&view_type=list",
                description="Customer invoices"
            ),
            "bills": NavigationTarget(
                name="Vendor Bills",
                menu_id=None,
                action_id=None,
                model="account.move",
                view_type="tree",
                domain=[("move_type", "=", "in_invoice")],
                url_path="/web#action=account.action_move_in_invoice_type&model=account.move&view_type=list",
                description="Vendor bills and supplier invoices"
            ),
            
            # HR Module
            "employees": NavigationTarget(
                name="Employees",
                menu_id=None,
                action_id=None,
                model="hr.employee",
                view_type="tree",
                url_path="/web#action=hr.open_view_employee_list_my&model=hr.employee&view_type=list",
                description="Employee directory"
            ),
            "hr dashboard": NavigationTarget(
                name="HR Dashboard",
                menu_id=None,
                action_id=None,
                model="hr.employee",
                view_type="kanban",
                url_path="/web#action=hr.hr_employee_action&model=hr.employee&view_type=kanban",
                description="Human resources overview"
            ),
            
            # Project Module
            "projects": NavigationTarget(
                name="Projects",
                menu_id=None,
                action_id=None,
                model="project.project",
                view_type="tree",
                url_path="/web#action=project.action_project_project&model=project.project&view_type=list",
                description="Project management"
            ),
            "tasks": NavigationTarget(
                name="Tasks",
                menu_id=None,
                action_id=None,
                model="project.task",
                view_type="tree",
                url_path="/web#action=project.action_view_task&model=project.task&view_type=list",
                description="Project tasks and activities"
            ),
            "my tasks": NavigationTarget(
                name="My Tasks",
                menu_id=None,
                action_id=None,
                model="project.task",
                view_type="tree",
                domain=[("user_ids", "in", [1])],  # Will be replaced with actual user ID
                url_path="/web#action=project.action_view_my_task&model=project.task&view_type=list",
                description="Tasks assigned to current user"
            ),
        }
    
    def find_navigation_target(self, query: str) -> Optional[NavigationTarget]:
        """Find navigation target based on user query
        
        Args:
            query: User's navigation request
            
        Returns:
            NavigationTarget if found, None otherwise
        """
        query_lower = query.lower().strip()
        
        # Remove common navigation words
        navigation_words = ["go to", "open", "show me", "navigate to", "take me to", "display"]
        for word in navigation_words:
            query_lower = query_lower.replace(word, "").strip()
        
        # Direct match
        if query_lower in self.navigation_map:
            return self.navigation_map[query_lower]
        
        # Fuzzy matching
        for key, target in self.navigation_map.items():
            if any(word in query_lower for word in key.split()):
                return target
            if any(word in target.description.lower() for word in query_lower.split()):
                return target
        
        return None
    
    def get_navigation_url(self, target: NavigationTarget, user_id: int = 1) -> str:
        """Generate navigation URL for the target
        
        Args:
            target: Navigation target
            user_id: Current user ID for personalized navigation
            
        Returns:
            URL string for navigation
        """
        if target.url_path:
            # Replace user ID placeholder for personalized views
            if "user_ids" in str(target.domain) and user_id:
                url = target.url_path.replace("user_ids", f"user_ids&user_id={user_id}")
                return url
            return target.url_path
        
        # Build URL from components
        base_url = "/web#"
        params = []
        
        if target.action_id:
            params.append(f"action={target.action_id}")
        if target.model:
            params.append(f"model={target.model}")
        if target.view_type:
            params.append(f"view_type={target.view_type}")
        
        return base_url + "&".join(params)
    
    def get_available_shortcuts(self) -> List[str]:
        """Get list of available navigation shortcuts
        
        Returns:
            List of available navigation commands
        """
        return list(self.navigation_map.keys())
    
    def search_records(self, model: str, search_term: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Search for specific records in a model
        
        Args:
            model: Odoo model name
            search_term: Search term
            limit: Maximum number of results
            
        Returns:
            List of matching records
        """
        try:
            # Define search fields for different models
            search_fields = {
                "res.partner": ["name", "email", "phone"],
                "product.product": ["name", "default_code", "barcode"],
                "sale.order": ["name", "partner_id.name"],
                "account.move": ["name", "partner_id.name", "ref"],
                "crm.lead": ["name", "partner_name", "email_from"],
                "project.task": ["name", "description"],
                "hr.employee": ["name", "work_email", "job_title"]
            }
            
            fields = search_fields.get(model, ["name"])
            
            # Build search domain
            domain = []
            for field in fields:
                domain.append((field, "ilike", search_term))
            
            # Use OR condition for multiple fields
            if len(domain) > 1:
                domain = ["|"] * (len(domain) - 1) + domain
            
            # Execute search
            records = self.odoo_client.search_read(
                model=model,
                domain=domain,
                fields=["id", "name", "display_name"] + fields[:2],  # Include key fields
                limit=limit
            )
            
            return records
            
        except Exception as e:
            logger.error(f"Record search failed: {str(e)}")
            return []
    
    def get_record_url(self, model: str, record_id: int, view_type: str = "form") -> str:
        """Generate URL for a specific record
        
        Args:
            model: Odoo model name
            record_id: Record ID
            view_type: View type (form, tree, etc.)
            
        Returns:
            URL string for the record
        """
        return f"/web#id={record_id}&model={model}&view_type={view_type}"
    
    def format_navigation_response(self, target: NavigationTarget, user_id: int = 1) -> str:
        """Format navigation response for user
        
        Args:
            target: Navigation target
            user_id: Current user ID
            
        Returns:
            Formatted response string
        """
        url = self.get_navigation_url(target, user_id)
        
        response = f"🧭 **Navigating to {target.name}**\n\n"
        response += f"📝 {target.description}\n\n"
        response += f"🔗 **Direct Link:** `{url}`\n\n"
        response += "💡 *Tip: You can bookmark this link for quick access!*"
        
        return response
    
    def format_search_results(self, model: str, records: List[Dict[str, Any]], search_term: str) -> str:
        """Format search results for display
        
        Args:
            model: Odoo model name
            records: List of found records
            search_term: Original search term
            
        Returns:
            Formatted search results string
        """
        if not records:
            return f"🔍 No records found for '{search_term}' in {model.replace('_', ' ').title()}"
        
        response = f"🔍 **Found {len(records)} result(s) for '{search_term}':**\n\n"
        
        for i, record in enumerate(records[:5], 1):  # Show top 5 results
            name = record.get("display_name") or record.get("name", "Unknown")
            record_id = record.get("id")
            url = self.get_record_url(model, record_id)
            
            response += f"{i}. **{name}** (ID: {record_id})\n"
            response += f"   🔗 [Open Record]({url})\n\n"
        
        if len(records) > 5:
            response += f"... and {len(records) - 5} more results\n"
        
        return response

# This will be initialized with the odoo_client when needed
navigation_service = None