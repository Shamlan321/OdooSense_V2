#!/usr/bin/env python3

import requests
import json
import logging
import re
from typing import Dict, List, Any, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class RAGSource:
    """Represents a source document from RAG response"""
    url: str
    title: str

@dataclass
class NavigationLink:
    """Represents a navigation link for Odoo operations"""
    label: str
    url: str
    description: str
    icon: str = "🔗"

@dataclass
class RAGResponse:
    """Represents a response from the RAG API"""
    answer: str
    sources: List[RAGSource]
    navigation_links: List[NavigationLink] = None

class OdooNavigationGenerator:
    """Generates dynamic navigation links based on user queries"""
    
    def __init__(self):
        # Navigation mapping for different Odoo modules and operations
        self.navigation_patterns = {
            # Sales Operations
            r'create.*sales? order|new sales? order|make.*quotation': {
                'path': 'web#action=sale.action_orders&model=sale.order&view_type=form',
                'label': 'Create Sales Order',
                'description': 'Create a new sales order',
                'icon': '🛒'
            },
            r'sales? quotation|quotation|quote': {
                'path': 'web#action=sale.action_quotations&model=sale.order&view_type=list',
                'label': 'Sales Quotations',
                'description': 'View and manage quotations',
                'icon': '📄'
            },
            r'sales? order.*list|view.*sales? order': {
                'path': 'web#action=sale.action_orders&model=sale.order&view_type=list',
                'label': 'Sales Orders',
                'description': 'View all sales orders',
                'icon': '📋'
            },
            
            # Customer/Partner Operations
            r'create.*customer|new customer|add customer': {
                'path': 'web#action=base.action_partner_form&model=res.partner&view_type=form',
                'label': 'Create Customer',
                'description': 'Add a new customer',
                'icon': '👤'
            },
            r'customer.*list|view.*customer|customer.*management': {
                'path': 'web#action=base.action_partner_customer_form&model=res.partner&view_type=list',
                'label': 'Customers',
                'description': 'View and manage customers',
                'icon': '👥'
            },
            
            # Product Operations
            r'create.*product|new product|add product': {
                'path': 'web#action=product.product_template_action&model=product.template&view_type=form',
                'label': 'Create Product',
                'description': 'Add a new product',
                'icon': '📦'
            },
            r'product.*list|view.*product|product.*catalog': {
                'path': 'web#action=product.product_template_action&model=product.template&view_type=list',
                'label': 'Products',
                'description': 'View product catalog',
                'icon': '📦'
            },
            
            # Invoice Operations
            r'create.*invoice|new invoice|customer invoice': {
                'path': 'web#action=account.action_move_out_invoice_type&model=account.move&view_type=form',
                'label': 'Create Invoice',
                'description': 'Create a customer invoice',
                'icon': '🧾'
            },
            r'invoice.*list|view.*invoice|customer.*invoice': {
                'path': 'web#action=account.action_move_out_invoice_type&model=account.move&view_type=list',
                'label': 'Customer Invoices',
                'description': 'View customer invoices',
                'icon': '📑'
            },
            r'vendor.*bill|supplier.*bill|bill': {
                'path': 'web#action=account.action_move_in_invoice_type&model=account.move&view_type=list',
                'label': 'Vendor Bills',
                'description': 'View vendor bills',
                'icon': '📄'
            },
            
            # Inventory Operations
            r'inventory|stock|warehouse': {
                'path': 'web#action=stock.dashboard_open&model=stock.picking.type&view_type=kanban',
                'label': 'Inventory Dashboard',
                'description': 'Access inventory overview',
                'icon': '📊'
            },
            r'stock.*transfer|transfer|delivery': {
                'path': 'web#action=stock.action_picking_tree_all&model=stock.picking&view_type=list',
                'label': 'Stock Transfers',
                'description': 'View stock transfers',
                'icon': '🚚'
            },
            
            # CRM Operations
            r'create.*lead|new lead|lead': {
                'path': 'web#action=crm.crm_lead_all_leads&model=crm.lead&view_type=form',
                'label': 'Create Lead',
                'description': 'Create a new lead',
                'icon': '🎯'
            },
            r'crm|lead.*list|opportunity': {
                'path': 'web#action=crm.crm_lead_all_leads&model=crm.lead&view_type=list',
                'label': 'CRM Pipeline',
                'description': 'View CRM pipeline',
                'icon': '💼'
            },
            
            # Purchase Operations
            r'purchase.*order|purchase|vendor': {
                'path': 'web#action=purchase.purchase_rfq&model=purchase.order&view_type=list',
                'label': 'Purchase Orders',
                'description': 'View purchase orders',
                'icon': '🛍️'
            },
            
            # Employee/HR Operations
            r'employee|hr|human.*resource': {
                'path': 'web#action=hr.open_view_employee_list_my&model=hr.employee&view_type=list',
                'label': 'Employees',
                'description': 'View employees',
                'icon': '👨‍💼'
            },
            
            # Expense Operations
            r'expense|expense.*report': {
                'path': 'web#action=hr_expense.hr_expense_actions_my_unsubmitted&model=hr.expense&view_type=list',
                'label': 'Expenses',
                'description': 'View expenses',
                'icon': '💳'
            },
            
            # Settings and Configuration
            r'setting|configuration|config': {
                'path': 'web#action=base.action_res_config_settings&model=res.config.settings&view_type=form',
                'label': 'Settings',
                'description': 'Access system settings',
                'icon': '⚙️'
            }
        }
    
    def generate_navigation_links(self, query: str, odoo_base_url: str = None) -> List[NavigationLink]:
        """Generate navigation links based on user query"""
        if not odoo_base_url:
            return []
        
        # Clean the base URL
        base_url = odoo_base_url.rstrip('/')
        
        navigation_links = []
        query_lower = query.lower()
        
        for pattern, config in self.navigation_patterns.items():
            if re.search(pattern, query_lower):
                full_url = f"{base_url}/{config['path']}"
                nav_link = NavigationLink(
                    label=config['label'],
                    url=full_url,
                    description=config['description'],
                    icon=config['icon']
                )
                navigation_links.append(nav_link)
        
        # Remove duplicates while preserving order
        seen = set()
        unique_links = []
        for link in navigation_links:
            if link.url not in seen:
                seen.add(link.url)
                unique_links.append(link)
        
        return unique_links[:3]  # Limit to 3 most relevant links

class OdooRAGClient:
    """Client for interacting with the Odoo RAG Documentation API"""
    
    def __init__(self, base_url: str = "http://localhost:8000", api_token: str = None):
        self.base_url = base_url.rstrip('/')
        self.api_token = api_token or "4S6BZAlC3DnUhR8rMk3Q6wg1dICzW1yKfwz1Belq6ZY"
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {self.api_token}",
            "Content-Type": "application/json"
        })
        self.nav_generator = OdooNavigationGenerator()
        
    def query_documentation(self, 
                          query: str, 
                          version: int = 180, 
                          conversation_history: List[Dict[str, str]] = None,
                          odoo_base_url: str = None) -> Optional[RAGResponse]:
        """Query the Odoo documentation using RAG
        
        Args:
            query: The question about Odoo
            version: Odoo version (160, 170, or 180)
            conversation_history: Optional conversation context
            odoo_base_url: Base URL for generating navigation links
            
        Returns:
            RAGResponse object with answer, sources, and navigation links
        """
        try:
            payload = {
                "query": query,
                "version": version,
                "conversation_history": conversation_history or []
            }
            
            response = self.session.post(
                f"{self.base_url}/api/chat",
                json=payload,
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                logger.info(f"RAG API response keys: {list(data.keys())}")
                logger.info(f"RAG API sources count: {len(data.get('sources', []))}")
                
                sources = [RAGSource(url=s["url"], title=s["title"]) for s in data.get("sources", [])]
                logger.info(f"Parsed sources count: {len(sources)}")
                
                # Generate navigation links
                navigation_links = self.nav_generator.generate_navigation_links(query, odoo_base_url)
                logger.info(f"Generated {len(navigation_links)} navigation links")
                
                return RAGResponse(
                    answer=data.get("answer", ""),
                    sources=sources,
                    navigation_links=navigation_links
                )
            else:
                logger.error(f"RAG API error: {response.status_code} - {response.text}")
                return None
                
        except requests.exceptions.RequestException as e:
            logger.error(f"RAG API request failed: {str(e)}")
            return None
        except json.JSONDecodeError as e:
            logger.error(f"RAG API response parsing failed: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"Unexpected RAG API error: {str(e)}")
            return None
    
    def stream_documentation_query(self, 
                                 query: str, 
                                 version: int = 180, 
                                 conversation_history: List[Dict[str, str]] = None):
        """Stream query response from the Odoo documentation
        
        Args:
            query: The question about Odoo
            version: Odoo version (160, 170, or 180)
            conversation_history: Optional conversation context
            
        Yields:
            Text chunks from the streaming response
        """
        try:
            payload = {
                "query": query,
                "version": version,
                "conversation_history": conversation_history or []
            }
            
            response = self.session.post(
                f"{self.base_url}/api/stream",
                json=payload,
                stream=True,
                timeout=30
            )
            
            if response.status_code == 200:
                for chunk in response.iter_content(chunk_size=1024, decode_unicode=True):
                    if chunk:
                        yield chunk
            else:
                logger.error(f"RAG streaming API error: {response.status_code} - {response.text}")
                yield f"Error: Unable to get documentation response ({response.status_code})"
                
        except requests.exceptions.RequestException as e:
            logger.error(f"RAG streaming API request failed: {str(e)}")
            yield f"Error: Documentation service unavailable - {str(e)}"
        except Exception as e:
            logger.error(f"Unexpected RAG streaming error: {str(e)}")
            yield f"Error: Unexpected documentation service error - {str(e)}"
    
    def health_check(self) -> bool:
        """Check if the RAG API is available
        
        Returns:
            True if API is healthy, False otherwise
        """
        try:
            response = self.session.get(f"{self.base_url}/health", timeout=5)
            return response.status_code == 200
        except:
            return False
    
    def format_response_with_sources(self, rag_response: RAGResponse, include_navigation: bool = True) -> str:
        """Format RAG response with minimal sources and navigation links
        
        Args:
            rag_response: The RAG response object
            include_navigation: Whether to include navigation links
            
        Returns:
            Formatted string with answer, minimal sources, and navigation
        """
        if not rag_response:
            return "No documentation found for your query."
        
        formatted = rag_response.answer
        logger.info(f"Formatting response with {len(rag_response.sources)} sources")
        
        # Clean up any remaining verbose source sections that might come from the RAG agent
        # Remove "Sources Used:" sections and similar verbose formatting
        lines = formatted.split('\n')
        cleaned_lines = []
        skip_section = False
        
        for line in lines:
            line_lower = line.lower().strip()
            
            # Skip verbose source sections
            if any(pattern in line_lower for pattern in [
                'sources used:', 'source 1:', 'source 2:', 'source 3:', 'source 4:',
                'source 5:', 'source 6:', '📚 sources:', 'references:'
            ]):
                skip_section = True
                continue
            
            # Skip lines that look like source listings
            if skip_section and (line.strip().startswith('Source ') or 
                               line.strip().startswith('-') or
                               line.strip().startswith('[#]') or
                               not line.strip()):
                continue
            
            # Reset skip when we encounter normal content
            if line.strip() and not any(pattern in line_lower for pattern in [
                'source ', '[#]', 'documentation', 'chunk[', 'url'
            ]):
                skip_section = False
            
            if not skip_section:
                cleaned_lines.append(line)
        
        formatted = '\n'.join(cleaned_lines).strip()
        
        # Add minimal sources with embedded links
        if rag_response.sources:
            # Embed source numbers in the answer text with clickable links
            for i, source in enumerate(rag_response.sources, 1):
                # Replace source references in text with clickable links
                source_pattern = f"(Source {i})"
                link_replacement = f"[{i}]({source.url})"
                formatted = re.sub(rf"\(Source {i}\)", link_replacement, formatted)
                
            # Add compact sources list at the end
            formatted += "\n\n**📚 References:** "
            source_links = [f"[{i}]({source.url})" for i, source in enumerate(rag_response.sources, 1)]
            formatted += " | ".join(source_links)
            logger.info(f"Added compact sources section to response")
        else:
            logger.warning("No sources found in RAG response")
        
        # Add navigation links if available and requested
        if include_navigation and rag_response.navigation_links:
            formatted += "\n\n**🧭 Quick Actions:**\n"
            for link in rag_response.navigation_links:
                formatted += f"\n{link.icon} **[{link.label}]({link.url})** - {link.description}"
            logger.info(f"Added {len(rag_response.navigation_links)} navigation links")
        
        return formatted

# Global instance
rag_client = OdooRAGClient()