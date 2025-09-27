#!/usr/bin/env python3
"""
Enhanced CRM lead creation functionality for integration into main agent
"""

import logging
from typing import Dict, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

class EnhancedLeadCreator:
    """Enhanced lead creation with better validation and logging"""
    
    def __init__(self, odoo_client):
        self.odoo_client = odoo_client
    
    def create_lead_from_business_card(self, extracted_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a CRM lead from business card data with enhanced validation"""
        try:
            logger.info(f"Creating lead from extracted data: {extracted_data}")
            
            # Extract and validate data
            name = self._get_valid_string(extracted_data.get('name'), 'Unknown Contact')
            company = self._get_valid_string(extracted_data.get('company'), '')
            email = self._get_valid_string(extracted_data.get('email'), '')
            phone = self._get_valid_string(extracted_data.get('phone'), '')
            mobile = self._get_valid_string(extracted_data.get('mobile'), '')
            website = self._get_valid_string(extracted_data.get('website'), '')
            job_title = self._get_valid_string(extracted_data.get('title'), '')
            
            # Generate meaningful lead name
            lead_name = self._generate_lead_name(name, company)
            
            # Prepare lead data with proper field mapping
            lead_data = {
                'name': lead_name,  # Opportunity name (mandatory)
                'contact_name': name if name != 'Unknown Contact' else '',
                'partner_name': company,  # Company name
                'email_from': email,
                'phone': phone or mobile,  # Primary phone
                'mobile': mobile if mobile != phone else '',  # Mobile if different
                'website': website,
                'function': job_title,  # Job title
                'description': self._generate_description(name, company, job_title, email, phone),
                'type': 'lead',  # Explicitly set as lead
                'stage_id': 1,  # Default to first stage (New)
                'priority': '1',  # Normal priority
                'source_id': self._get_or_create_source(),  # Lead source
            }
            
            # Clean up empty fields but keep mandatory ones
            lead_data = self._clean_lead_data(lead_data)
            
            logger.info(f"Prepared lead data: {lead_data}")
            
            # Create the lead
            lead_id = self.odoo_client.create('crm.lead', lead_data)
            
            if lead_id:
                logger.info(f"Successfully created lead with ID: {lead_id}")
                
                # Verify the lead was created
                verification_result = self._verify_lead_creation(lead_id)
                
                return {
                    'success': True,
                    'lead_id': lead_id,
                    'lead_data': lead_data,
                    'verification': verification_result,
                    'message': f'Lead created successfully with ID: {lead_id}',
                    'contact_name': name,
                    'company': company,
                    'email': email,
                    'phone': phone or mobile
                }
            else:
                logger.error("Failed to create lead - no ID returned")
                return {
                    'success': False,
                    'error': 'Failed to create lead - no ID returned',
                    'lead_data': lead_data
                }
                
        except Exception as e:
            logger.error(f"Error creating lead: {str(e)}")
            return {
                'success': False,
                'error': f'Failed to create lead: {str(e)}',
                'extracted_data': extracted_data
            }
    
    def _get_valid_string(self, value: Any, default: str = '') -> str:
        """Get a valid string value or default"""
        if value is None:
            return default
        return str(value).strip() if str(value).strip() else default
    
    def _generate_lead_name(self, name: str, company: str) -> str:
        """Generate a meaningful lead name"""
        timestamp = datetime.now().strftime("%Y-%m-%d")
        
        if company and name != 'Unknown Contact':
            return f"{company} - {name} ({timestamp})"
        elif company:
            return f"{company} - New Lead ({timestamp})"
        elif name != 'Unknown Contact':
            return f"{name} - Business Card Lead ({timestamp})"
        else:
            return f"Business Card Lead ({timestamp})"
    
    def _generate_description(self, name: str, company: str, job_title: str, email: str, phone: str) -> str:
        """Generate a comprehensive description"""
        description_parts = ["Lead generated from business card processing"]
        
        if name != 'Unknown Contact':
            description_parts.append(f"Contact: {name}")
        if company:
            description_parts.append(f"Company: {company}")
        if job_title:
            description_parts.append(f"Title: {job_title}")
        if email:
            description_parts.append(f"Email: {email}")
        if phone:
            description_parts.append(f"Phone: {phone}")
        
        description_parts.append(f"Created: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        return "\n".join(description_parts)
    
    def _get_or_create_source(self) -> Optional[int]:
        """Get or create a lead source for business cards"""
        try:
            # Try to find existing source
            sources = self.odoo_client.search_read(
                'utm.source',
                [('name', '=', 'Business Card')],
                ['id'],
                limit=1
            )
            
            if sources:
                return sources[0]['id']
            
            # Create new source if not found
            source_id = self.odoo_client.create('utm.source', {
                'name': 'Business Card',
                'description': 'Leads generated from business card processing'
            })
            
            logger.info(f"Created new lead source with ID: {source_id}")
            return source_id
            
        except Exception as e:
            logger.warning(f"Could not create/find lead source: {str(e)}")
            return None
    
    def _clean_lead_data(self, lead_data: Dict[str, Any]) -> Dict[str, Any]:
        """Clean lead data by removing empty fields except mandatory ones"""
        mandatory_fields = {'name', 'stage_id', 'type', 'priority'}
        
        cleaned_data = {}
        for key, value in lead_data.items():
            # Keep mandatory fields regardless of value
            if key in mandatory_fields:
                cleaned_data[key] = value
            # Keep non-empty values
            elif value and str(value).strip():
                cleaned_data[key] = value
        
        return cleaned_data
    
    def _verify_lead_creation(self, lead_id: int) -> Dict[str, Any]:
        """Verify that the lead was created successfully"""
        try:
            # Read the created lead
            lead = self.odoo_client.search_read(
                'crm.lead',
                [('id', '=', lead_id)],
                ['name', 'contact_name', 'partner_name', 'email_from', 'phone', 'stage_id', 'create_date']
            )
            
            if lead:
                lead_info = lead[0]
                logger.info(f"Lead verification successful: {lead_info}")
                return {
                    'verified': True,
                    'lead_info': lead_info,
                    'stage': lead_info.get('stage_id', ['Unknown', 'Unknown'])[1] if lead_info.get('stage_id') else 'Unknown'
                }
            else:
                logger.error(f"Lead verification failed - lead {lead_id} not found")
                return {
                    'verified': False,
                    'error': f'Lead {lead_id} not found after creation'
                }
                
        except Exception as e:
            logger.error(f"Lead verification error: {str(e)}")
            return {
                'verified': False,
                'error': f'Verification failed: {str(e)}'
            }
    
    def list_recent_leads(self, limit: int = 5) -> Dict[str, Any]:
        """List recent leads for verification"""
        try:
            leads = self.odoo_client.search_read(
                'crm.lead',
                [],
                ['name', 'contact_name', 'partner_name', 'email_from', 'stage_id', 'create_date'],
                limit=limit
            )
            
            return {
                'success': True,
                'leads': leads,
                'count': len(leads)
            }
            
        except Exception as e:
            logger.error(f"Error listing recent leads: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }

# Test function
def test_enhanced_lead_creation():
    """Test the enhanced lead creation"""
    import sys
    import os
    sys.path.append(os.path.dirname(os.path.abspath(__file__)))
    
    from odoo_client import OdooClient
    
    # Test data (same as from your logs)
    test_data = {
        "name": "Sandra Sully",
        "company": "bostongreen",
        "title": "Landscape Designer",
        "email": "sandra@bostongreen.com",
        "phone": "+1 (555) 7182 1921",
        "mobile": None,
        "address": None,
        "website": "www.bostongreen.com",
        "linkedin": None,
        "confidence_score": 0.98
    }
    
    # Initialize Odoo client
    odoo_client = OdooClient()
    if not odoo_client.connect():
        print("❌ Failed to connect to Odoo")
        return
    
    # Create enhanced lead creator
    lead_creator = EnhancedLeadCreator(odoo_client)
    
    # Create lead
    print("🔄 Creating lead with enhanced functionality...")
    result = lead_creator.create_lead_from_business_card(test_data)
    
    print("\n📊 Result:")
    for key, value in result.items():
        print(f"  {key}: {value}")
    
    if result.get('success'):
        print("\n✅ Enhanced lead creation successful!")
        
        # List recent leads
        print("\n📋 Recent leads:")
        recent_leads = lead_creator.list_recent_leads(3)
        if recent_leads.get('success'):
            for i, lead in enumerate(recent_leads['leads'], 1):
                print(f"  {i}. {lead['name']} (ID: {lead['id']})")
    else:
        print("\n❌ Enhanced lead creation failed!")

if __name__ == "__main__":
    test_enhanced_lead_creation()