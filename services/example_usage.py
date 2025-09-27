#!/usr/bin/env python3
"""
Example usage of the AgentService class.

This file demonstrates how to use the AgentService for various tasks:
- Chat interactions
- Document processing
- Email processing
- LinkedIn profile processing
- Report generation
"""

import sys
import os
from pathlib import Path

# Add parent directory to path to import modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from services.agent_service import AgentService
import logging

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def example_chat():
    """Example of chat functionality"""
    print("\n=== Chat Example ===")
    
    try:
        # Initialize the agent service
        agent_service = AgentService()
        
        # Example chat messages
        messages = [
            "Hello, how are you?",
            "Show me recent sales orders",
            "How many customers do we have?",
            "Create a new customer named John Doe"
        ]
        
        session_id = "example_session_001"
        user_id = 1
        
        for message in messages:
            print(f"\nUser: {message}")
            
            response = agent_service.chat(
                message=message,
                session_id=session_id,
                user_id=user_id
            )
            
            if response.get('success'):
                print(f"Agent: {response.get('response', 'No response')}")
            else:
                print(f"Error: {response.get('error', 'Unknown error')}")
                
    except Exception as e:
        print(f"Chat example failed: {str(e)}")

def example_document_processing():
    """Example of document processing"""
    print("\n=== Document Processing Example ===")
    
    try:
        agent_service = AgentService()
        
        # Example: Process a sample PDF invoice
        # Note: In real usage, you would read actual file data
        sample_pdf_data = b"Sample PDF content"  # This would be actual PDF bytes
        filename = "sample_invoice.pdf"
        mime_type = "application/pdf"
        doc_type = "bill"  # vendor bill
        
        print(f"Processing document: {filename}")
        
        # First, preview the document
        preview_result = agent_service.document_preview(
            file_data=sample_pdf_data,
            filename=filename,
            mime_type=mime_type,
            doc_type=doc_type
        )
        
        if preview_result.get('success'):
            print("Document preview successful")
            print(f"Extracted data: {preview_result.get('extracted_data', {})}")
            
            # If preview looks good, process the document
            process_result = agent_service.document_ingestion(
                file_data=sample_pdf_data,
                filename=filename,
                mime_type=mime_type,
                doc_type=doc_type
            )
            
            if process_result.get('success'):
                print("Document processing successful")
                print(f"Result: {process_result.get('response', 'No response')}")
            else:
                print(f"Processing error: {process_result.get('error')}")
        else:
            print(f"Preview error: {preview_result.get('error')}")
            
    except Exception as e:
        print(f"Document processing example failed: {str(e)}")

def example_email_processing():
    """Example of email processing"""
    print("\n=== Email Processing Example ===")
    
    try:
        agent_service = AgentService()
        
        # Example email content for vendor bill
        email_content = """
        Subject: Invoice #INV-2024-001
        From: vendor@example.com
        
        Dear Customer,
        
        Please find attached our invoice for the recent services:
        
        Invoice Number: INV-2024-001
        Date: 2024-01-15
        Amount: $1,250.00
        
        Services:
        - Consulting Services: $1,000.00
        - Travel Expenses: $250.00
        
        Payment terms: Net 30 days
        
        Best regards,
        Vendor Company
        """
        
        print("Processing email for vendor bill...")
        
        result = agent_service.process_email(
            email_content=email_content,
            email_type="bill"
        )
        
        if result.get('success'):
            print("Email processing successful")
            print(f"Response: {result.get('response', 'No response')}")
        else:
            print(f"Email processing error: {result.get('error')}")
            
    except Exception as e:
        print(f"Email processing example failed: {str(e)}")

def example_linkedin_processing():
    """Example of LinkedIn profile processing"""
    print("\n=== LinkedIn Processing Example ===")
    
    try:
        agent_service = AgentService()
        
        # Example LinkedIn profile URL
        profile_url = "https://www.linkedin.com/in/johndoe"
        
        print(f"Processing LinkedIn profile: {profile_url}")
        
        result = agent_service.process_linkedin_profile(
            profile_url=profile_url
        )
        
        if result.get('success'):
            print("LinkedIn processing successful")
            print(f"Response: {result.get('response', 'No response')}")
        else:
            print(f"LinkedIn processing error: {result.get('error')}")
            
    except Exception as e:
        print(f"LinkedIn processing example failed: {str(e)}")

def example_report_generation():
    """Example of report generation"""
    print("\n=== Report Generation Example ===")
    
    try:
        agent_service = AgentService()
        
        # Example: Generate sales report
        report_types = [
            ("sales_summary", {"period": "last_month"}),
            ("customer_analysis", {"top_n": 10}),
            ("inventory_status", {})
        ]
        
        for report_type, parameters in report_types:
            print(f"\nGenerating {report_type} report...")
            
            result = agent_service.generate_report(
                report_type=report_type,
                parameters=parameters
            )
            
            if result.get('success'):
                print(f"Report generation successful")
                print(f"Response: {result.get('response', 'No response')}")
            else:
                print(f"Report generation error: {result.get('error')}")
                
    except Exception as e:
        print(f"Report generation example failed: {str(e)}")

def example_health_check():
    """Example of health check"""
    print("\n=== Health Check Example ===")
    
    try:
        agent_service = AgentService()
        
        health_status = agent_service.health_check()
        
        print(f"Service Status: {health_status.get('status')}")
        print(f"Timestamp: {health_status.get('timestamp')}")
        
        if health_status.get('agent_health'):
            print("Agent Health Details:")
            for component, status in health_status['agent_health'].items():
                print(f"  {component}: {status}")
                
        if health_status.get('error'):
            print(f"Error: {health_status.get('error')}")
            
    except Exception as e:
        print(f"Health check example failed: {str(e)}")

def example_session_management():
    """Example of session management"""
    print("\n=== Session Management Example ===")
    
    try:
        agent_service = AgentService()
        session_id = "example_session_002"
        
        # Send a few messages to build conversation history
        messages = [
            "Hello",
            "What's the weather like?",
            "Show me sales data"
        ]
        
        for message in messages:
            agent_service.chat(message=message, session_id=session_id)
        
        # Get conversation history
        history = agent_service.get_conversation_history(session_id, limit=10)
        print(f"Conversation history length: {len(history)}")
        
        # Clear session
        cleared = agent_service.clear_session(session_id)
        print(f"Session cleared: {cleared}")
        
    except Exception as e:
        print(f"Session management example failed: {str(e)}")

def main():
    """Run all examples"""
    print("AgentService Usage Examples")
    print("============================")
    
    # Run examples
    example_health_check()
    example_chat()
    example_document_processing()
    example_email_processing()
    example_linkedin_processing()
    example_report_generation()
    example_session_management()
    
    print("\n=== All Examples Completed ===")

if __name__ == "__main__":
    main()