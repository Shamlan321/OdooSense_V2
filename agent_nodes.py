import logging
import json
from datetime import datetime
from typing import Dict, Any, List, Optional
from agent_state import AgentState, StateManager, NodeResult, ProcessingResult
from gemini_client import gemini_client
from odoo_client import odoo_client, OdooClient
from rag_client import rag_client
from navigation_handler import navigation_handler
from config import config
from optimization_utils import fast_path_router, query_cache
from performance_monitor import performance_monitor, performance_tracker
import re

logger = logging.getLogger(__name__)

def get_odoo_client_for_session(session_id: str = None) -> OdooClient:
    """
    Get the appropriate Odoo client for a session.
    Uses cached session-specific client if available, otherwise falls back to default client.
    """
    if session_id:
        try:
            # Import here to avoid circular imports
            from services.agent_service import agent_service
            
            # Use the AgentService's cached client method
            return agent_service.get_odoo_client_for_session(session_id)
        except Exception as e:
            logger.warning(f"Failed to get session client for {session_id}: {str(e)}")
    
    # Fallback to default client
    logger.info("Using default Odoo client")
    return odoo_client

class IntentClassificationNode:
    """Node for classifying user intent and extracting entities"""
    
    def __init__(self):
        self.confidence_threshold = config.agent.confidence_threshold
    
    @performance_tracker("intent_classification", performance_monitor)
    def process(self, state: AgentState) -> AgentState:
        """Classify the intent of the user message"""
        try:
            if state is None:
                logger.error("Intent classification failed: state is None")
                return state
            
            try:
                user_message = StateManager.get_last_user_message(state)
            except Exception as e:
                logger.warning(f"Could not extract user message for intent classification: {e}")
                user_message = ""
            
            # Check for LinkedIn lead creation requests (highest priority)
            linkedin_url_pattern = r'https?://[^/]*linkedin\.com/in/[\w\-\.]+'
            linkedin_match = re.search(linkedin_url_pattern, user_message, re.IGNORECASE)
            
            if linkedin_match:
                logger.info(f"[LINKEDIN] LinkedIn URL detected in message: {user_message[:50]}...")
                
                # More inclusive detection - any LinkedIn URL with lead-related context
                message_lower = user_message.lower()
                create_keywords = ['create', 'add', 'new', 'generate', 'make', 'from']
                lead_keywords = ['lead', 'prospect', 'contact', 'crm']
                
                has_create = any(keyword in message_lower for keyword in create_keywords)
                has_lead = any(keyword in message_lower for keyword in lead_keywords)
                has_linkedin = 'linkedin' in message_lower
                
                logger.info(f"[LINKEDIN] Create keywords found: {has_create}")
                logger.info(f"[LINKEDIN] Lead keywords found: {has_lead}")
                logger.info(f"[LINKEDIN] LinkedIn keyword found: {has_linkedin}")
                
                # If it has LinkedIn URL and either create/lead keywords, OR just mentions LinkedIn, treat as lead creation
                if has_create or has_lead or has_linkedin:
                    linkedin_url = linkedin_match.group(0)
                    logger.info(f"[LINKEDIN] LinkedIn lead creation request confirmed: {linkedin_url}")
                    
                    state["intent"] = "data_entry"
                    state["confidence"] = 0.98  # Very high confidence for LinkedIn lead creation
                    state["entities"] = {
                        "linkedin_url": linkedin_url,
                        "linkedin_lead": True,
                        "create_lead": True
                    }
                    state["current_step"] = "intent_classified"
                    state["next_action"] = "handle_crud"
                    logger.info(f"[LINKEDIN] Routing to CRUD with entities: {state['entities']}")
                    return state
                else:
                    logger.info(f"[LINKEDIN] LinkedIn URL found but no lead creation context, continuing to normal classification")
            
            # Check for direct navigation requests first (highest priority)
            if navigation_handler.is_navigation_request(user_message):
                logger.info(f"Navigation request detected: {user_message[:50]}...")
                state["intent"] = "navigation"
                state["confidence"] = 0.98  # Very high confidence for navigation
                state["entities"] = {"navigation_request": user_message}
                state["current_step"] = "intent_classified"
                state["next_action"] = "handle_navigation"
                return state
            
            # Fast-path routing for common queries (skip AI classification)
            if config.agent.enable_fast_path:
                fast_intent = fast_path_router.detect_intent(user_message)
                if fast_intent:
                    logger.info(f"Fast-path detected intent: {fast_intent}")
                    state["intent"] = "data_lookup"
                    state["confidence"] = 0.95  # High confidence for regex matches
                    state["entities"] = {"fast_path_intent": fast_intent}
                    state["current_step"] = "intent_classified"
                    state["next_action"] = "handle_data_lookup"
                    return state
            
            # Check for stock update queries - route to data_lookup (Phase 1 proven methods)
            user_message_lower = user_message.lower()
            if any(phrase in user_message_lower for phrase in ['add', 'remove', 'set', 'update']) and \
               any(word in user_message_lower for word in ['stock', 'inventory', 'units']) and \
               any(word in user_message_lower for word in ['product', 'in', 'for']):
                logger.info("Routing stock update to data_lookup (Phase 1 proven methods)")
                
                state["intent"] = "data_lookup"
                state["confidence"] = 0.95
                state["entities"] = {"stock_update": True}
                state["current_step"] = "intent_classified"
                state["next_action"] = "handle_data_lookup"
                return state
            
            conversation_history = state.get("conversation_memory", [])
            
            # Limit conversation history for faster processing
            if len(conversation_history) > config.agent.max_conversation_history:
                conversation_history = conversation_history[-config.agent.max_conversation_history:]
            
            logger.info(f"Classifying intent for message: {user_message[:100]}...")
            
            # Use Gemini to classify intent
            intent_result = gemini_client.classify_intent(user_message, conversation_history)
            
            # Update state with classification results
            state["intent"] = intent_result.get("intent", "general_help")
            state["confidence"] = intent_result.get("confidence", 0.0)
            state["entities"] = intent_result.get("entities", {})
            state["current_step"] = "intent_classified"
            
            # Determine next action based on intent and uploaded file presence
            # Don't override next_action if it's already set to handle_crud (from process_confirmed_data)
            current_next_action = state.get("next_action")
            
            if state["confidence"] < self.confidence_threshold:
                # For low-confidence general_help, route to qa_navigation as it might be a documentation query
                if state["intent"] == "general_help":
                    logger.info(f"Low-confidence general_help detected, routing to qa_navigation for potential documentation query")
                    state["intent"] = "qa_navigation"
                    state["next_action"] = "handle_qa"
                else:
                    state["next_action"] = "clarify_intent"
            elif StateManager.has_uploaded_file(state):
                # If there's an uploaded file, prioritize document processing regardless of intent
                state["next_action"] = "process_document"
                # Override intent to document_processing if it was misclassified
                if state["intent"] == "data_entry":
                    state["intent"] = "document_processing"
                    logger.info(f"Intent overridden to document_processing due to uploaded file")
            elif current_next_action == "handle_crud":
                # Preserve existing next_action if it's already set to handle_crud
                # This happens when process_confirmed_data is called with extracted data
                logger.info(f"Preserving existing next_action: handle_crud")
                pass  # Don't change next_action
            elif state["intent"] == "document_processing":
                state["next_action"] = "request_document"
            elif state["intent"] == "data_entry":
                state["next_action"] = "handle_crud"
            elif state["intent"] == "reporting":
                state["next_action"] = "handle_reporting"
            elif state["intent"] == "qa_navigation":
                state["next_action"] = "handle_qa"
            elif state["intent"] == "data_lookup":
                state["next_action"] = "handle_data_lookup"
            elif state["intent"] == "navigation":
                state["next_action"] = "handle_navigation"
            else:
                state["next_action"] = "general_response"
            
            logger.info(f"Intent classified: {state['intent']} (confidence: {state['confidence']})")
            
        except Exception as e:
            logger.error(f"Intent classification failed: {str(e)}")
            StateManager.set_error(state, f"Intent classification failed: {str(e)}", "intent_classification_error")
        
        return state

class DocumentProcessingNode:
    """Node for processing uploaded documents using Gemini Vision"""
    
    def __init__(self):
        self.confidence_threshold = config.agent.confidence_threshold
    
    @performance_tracker("document_processing", performance_monitor)
    def process(self, state: AgentState) -> AgentState:
        """Process uploaded document and extract structured data"""
        try:
            uploaded_file = state.get("uploaded_file")
            if not uploaded_file:
                StateManager.set_error(state, "No file uploaded for processing", "document_processing_error")
                return state
            
            file_data = uploaded_file["data"]
            mime_type = uploaded_file["mime_type"]
            filename = uploaded_file.get("filename", "unknown")
            preview_mode = state.get("preview_mode", False)
            
            logger.info(f"Processing document: {filename} ({mime_type}) - Preview mode: {preview_mode}")
            
            # Determine document type and extract data accordingly
            logger.info(f"State keys: {list(state.keys())}")
            logger.info(f"Document type from state before detection: {state.get('document_type')}")
            document_type = self._detect_document_type(filename, state.get("intent"), state)
            logger.info(f"Detected document type: {document_type} for file: {filename}")
            logger.info(f"Document type from state after detection: {state.get('document_type')}")
            
            if document_type == "invoice":
                extracted_data = gemini_client.extract_invoice_data(file_data, mime_type)
            elif document_type == "business_card":
                extracted_data = gemini_client.extract_contact_data(file_data, mime_type)
            elif document_type == "receipt":
                extracted_data = gemini_client.extract_invoice_data(file_data, mime_type)  # Use invoice extraction for receipts
            else:
                # Generic text extraction
                prompt = "Extract all text and structured information from this document. Return as JSON."
                response = gemini_client.process_image_with_text(file_data, prompt, mime_type)
                extracted_data = {"text_content": response, "confidence_score": 0.7}
            
            # Validate extraction results
            if extracted_data and "error" in extracted_data:
                StateManager.set_error(state, f"Document extraction failed: {extracted_data['error']}", "extraction_error")
                return state
            
            confidence = extracted_data.get("confidence_score", 0.0)
            if confidence < self.confidence_threshold:
                logger.warning(f"Low confidence extraction: {confidence}")
            
            state["extracted_data"] = extracted_data
            state["document_type"] = document_type
            
            if preview_mode:
                # In preview mode, don't proceed to CRUD operations
                state["current_step"] = "document_preview_ready"
                state["next_action"] = "generate_response"
                logger.info(f"Document preview ready with confidence: {confidence}")
            else:
                # Normal processing mode
                state["current_step"] = "document_processed"
                state["next_action"] = "handle_crud"  # Process the extracted data
                logger.info(f"Document processed successfully with confidence: {confidence}")
            
        except Exception as e:
            logger.error(f"Document processing failed: {str(e)}")
            StateManager.set_error(state, f"Document processing failed: {str(e)}", "document_processing_error")
        
        return state
    
    def _detect_document_type(self, filename: str, intent: str, state: AgentState = None) -> str:
        """Detect document type based on filename, intent, and explicit document type"""
        # Check if document type is explicitly specified
        if state and state.get("document_type"):
            doc_type = state["document_type"]
            # Map CLI types to internal types
            type_mapping = {
                "bill": "invoice",
                "expense": "receipt", 
                "lead": "business_card",
                "contact": "business_card"
            }
            return type_mapping.get(doc_type, doc_type)
        
        # Fallback to filename-based detection
        filename_lower = filename.lower()
        
        if "invoice" in filename_lower or "bill" in filename_lower:
            return "invoice"
        elif "card" in filename_lower or "contact" in filename_lower:
            return "business_card"
        elif "receipt" in filename_lower or "expense" in filename_lower:
            return "receipt"
        
        # Fallback to intent-based detection
        if intent == "document_processing":
            return "invoice"  # Default assumption
        
        return "generic"

class CRUDOperationsNode:
    """Node for handling CRUD operations in Odoo"""
    
    @performance_tracker("crud_operations", performance_monitor)
    def process(self, state: AgentState) -> AgentState:
        """Handle CRUD operations based on intent and extracted data"""
        try:
            intent = state.get("intent")
            extracted_data = state.get("extracted_data", {})
            entities = state.get("entities", {})
            document_type = state.get("document_type")
            session_id = state.get("session_id")
            
            print(f"[CONSOLE DEBUG] CRUDOperationsNode.process called")
            print(f"[CONSOLE DEBUG] Intent: {intent}")
            print(f"[CONSOLE DEBUG] Document type: {document_type}")
            print(f"[CONSOLE DEBUG] Session ID: {session_id}")
            print(f"[CONSOLE DEBUG] Extracted data keys: {list(extracted_data.keys()) if extracted_data else 'None'}")
            print(f"[CONSOLE DEBUG] Full extracted data: {extracted_data}")
            
            logger.info(f"[CRUD] Processing CRUD operation for intent: {intent}")
            logger.info(f"[CRUD] Document type: {document_type}")
            logger.info(f"[CRUD] Session ID: {session_id}")
            logger.info(f"[CRUD] Extracted data keys: {list(extracted_data.keys()) if extracted_data else 'None'}")
            logger.info(f"[CRUD] Full extracted data: {extracted_data}")
            
            # Get session-specific Odoo client
            current_odoo_client = get_odoo_client_for_session(session_id)
            
            # Ensure Odoo connection
            if not current_odoo_client.uid:
                logger.info(f"[CRUD] Connecting to Odoo...")
                if not current_odoo_client.connect():
                    logger.error(f"[CRUD] Failed to connect to Odoo")
                    StateManager.set_error(state, "Failed to connect to Odoo", "odoo_connection_error")
                    return state
                logger.info(f"[CRUD] Successfully connected to Odoo")
            
            result = None
            
            if intent == "document_processing":
                logger.info(f"[CRUD] Processing document data...")
                result = self._process_document_data(extracted_data, state, current_odoo_client)
                logger.info(f"[CRUD] Document processing result: {result.to_dict() if result else 'None'}")
            elif intent == "data_entry":
                logger.info(f"[CRUD] Handling manual entry...")
                result = self._handle_manual_entry(state, current_odoo_client)
            elif intent == "reporting":
                logger.info(f"[CRUD] Generating report...")
                result = self._generate_report(state, current_odoo_client)
            else:
                logger.error(f"[CRUD] Unsupported CRUD operation for intent: {intent}")
                StateManager.set_error(state, f"Unsupported CRUD operation for intent: {intent}", "unsupported_operation")
                return state
            
            state["odoo_result"] = result.to_dict() if result else None
            state["current_step"] = "crud_completed"
            state["next_action"] = "generate_response"
            
            if result and result.success:
                logger.info(f"[CRUD] CRUD operation completed successfully: {result.data}")
            else:
                logger.warning(f"[CRUD] CRUD operation failed: {result.error if result else 'Unknown error'}")
            
        except Exception as e:
            logger.error(f"[CRUD] CRUD operation failed with exception: {str(e)}")
            import traceback
            logger.error(f"[CRUD] Traceback: {traceback.format_exc()}")
            StateManager.set_error(state, f"CRUD operation failed: {str(e)}", "crud_error")
        
        return state
    
    def _process_document_data(self, extracted_data: Dict[str, Any], state: AgentState = None, odoo_client_instance: OdooClient = None) -> ProcessingResult:
        """Process extracted document data and create Odoo records, including LinkedIn lead creation"""
        try:
            # Use the passed client or fall back to global client
            client = odoo_client_instance or odoo_client
            
            logger.info(f"[PROCESS_DOC] Starting document data processing")
            logger.info(f"[PROCESS_DOC] Extracted data: {extracted_data}")
            logger.info(f"[PROCESS_DOC] State available: {state is not None}")
            logger.debug(f"[PROCESS_DOC] extracted_data type: {type(extracted_data)}")
            logger.debug(f"[PROCESS_DOC] state type: {type(state)}")
            
            # Handle None extracted_data
            if extracted_data is None:
                logger.warning(f"[PROCESS_DOC] extracted_data is None, cannot process document")
                return ProcessingResult(False, error="No extracted data available to process")
            
            # LinkedIn lead creation support
            linkedin_url = None
            # Check for LinkedIn URL in extracted_data or state entities
            if extracted_data and 'linkedin_url' in extracted_data:
                linkedin_url = extracted_data['linkedin_url']
            elif extracted_data and 'linkedin_profile_url' in extracted_data:
                linkedin_url = extracted_data['linkedin_profile_url']
            elif state:
                entities = state.get('entities', {}) or {}
                if entities and 'linkedin_url' in entities:
                    linkedin_url = entities['linkedin_url']
                elif entities and 'linkedin_profile_url' in entities:
                    linkedin_url = entities['linkedin_profile_url']
                else:
                    # Try to detect LinkedIn URL in user message
                    try:
                        user_message = StateManager.get_last_user_message(state)
                        linkedin_url = self._extract_linkedin_url(user_message)
                    except Exception as e:
                        logger.warning(f"Could not extract user message for LinkedIn URL detection: {e}")
                        linkedin_url = None
            
            if linkedin_url:
                logger.info(f"[PROCESS_DOC] LinkedIn URL detected: {linkedin_url}")
                try:
                    from linkedin_api import fetch_linkedin_profile
                    from gemini_client import gemini_client
                    raw_profile = fetch_linkedin_profile(linkedin_url)
                    cleaned_profile = gemini_client.clean_linkedin_profile(raw_profile)
                    return self._create_lead(cleaned_profile, client)
                except Exception as e:
                    logger.error(f"[PROCESS_DOC] LinkedIn lead creation failed: {str(e)}")
                    return ProcessingResult(False, error=f"LinkedIn lead creation failed: {str(e)}")
            
            # Existing document type logic
            doc_type = state.get("document_type") if state else None
            logger.info(f"[PROCESS_DOC] Document type from state: {doc_type}")
            
            if doc_type == "bill" or doc_type == "invoice":
                logger.info(f"[PROCESS_DOC] Creating vendor bill")
                return self._create_vendor_bill(extracted_data, client)
            elif doc_type == "expense" or doc_type == "receipt":
                logger.info(f"[PROCESS_DOC] Creating expense (doc_type={doc_type})")
                return self._create_expense(extracted_data, client)
            elif doc_type == "lead":
                logger.info(f"[PROCESS_DOC] Creating lead")
                return self._create_lead(extracted_data, client)
            elif doc_type == "contact":
                logger.info(f"[PROCESS_DOC] Creating contact (doc_type=contact)")
                return self._create_contact(extracted_data, client)
            elif doc_type == "business_card":
                logger.info(f"[PROCESS_DOC] Creating contact (doc_type=business_card)")
                return self._create_contact(extracted_data, client)
            elif doc_type is None:
                logger.info(f"[PROCESS_DOC] No document type specified, using fallback detection")
                # Fallback to data-based detection only when no explicit type
                if extracted_data is not None and isinstance(extracted_data, dict) and "vendor_name" in extracted_data:
                    logger.info(f"[PROCESS_DOC] Fallback: Creating vendor bill (vendor_name detected)")
                    return self._create_vendor_bill(extracted_data, client)
                elif extracted_data is not None and isinstance(extracted_data, dict) and "merchant_name" in extracted_data:
                    logger.info(f"[PROCESS_DOC] Fallback: Creating expense (merchant_name detected)")
                    return self._create_expense(extracted_data, client)
                elif extracted_data is not None and isinstance(extracted_data, dict) and "name" in extracted_data:
                    logger.info(f"[PROCESS_DOC] Fallback: Creating contact (name detected)")
                    return self._create_contact(extracted_data, client)
                else:
                    logger.error(f"[PROCESS_DOC] Could not determine document type from extracted data")
                    return ProcessingResult(False, error="Could not determine document type from extracted data")
            else:
                logger.error(f"[PROCESS_DOC] Unknown document type: {doc_type}")
                return ProcessingResult(False, error=f"Unknown document type '{doc_type}'")
        except Exception as e:
            logger.error(f"[PROCESS_DOC] Exception in document processing: {str(e)}")
            import traceback
            logger.error(f"[PROCESS_DOC] Traceback: {traceback.format_exc()}")
            return ProcessingResult(False, error=str(e))

    def _extract_linkedin_url(self, text: str) -> str:
        """Detect and return a LinkedIn profile URL from text, or None if not found."""
        if text is None:
            return None
        import re
        match = re.search(r"https?://[^/]*linkedin\.com/in/[\w\-\.]+", text)
        if match:
            return match.group(0)
        return None
    
    def _get_or_create_purchase_journal(self, client):
        """Get or create a purchase journal for vendor bills"""
        try:
            # Try to find existing purchase journal
            journals = client.search_read('account.journal', 
                                             [('type', '=', 'purchase')], 
                                             ['id', 'name'], limit=1)
            
            if journals:
                return journals[0]['id']
            
            # Create a purchase journal if none exists
            journal_data = {
                'name': 'Vendor Bills',
                'code': 'BILL',
                'type': 'purchase',
                'sequence': 10
            }
            
            journal_id = client.create('account.journal', journal_data)
            return journal_id
            
        except Exception as e:
            # If we can't create a journal, try to find any journal as fallback
            try:
                journals = client.search_read('account.journal', [], ['id'], limit=1)
                if journals:
                    return journals[0]['id']
            except:
                pass
            raise Exception(f"Could not find or create purchase journal: {str(e)}")
    
    def _create_purchase_order(self, vendor_id: int, invoice_data: Dict[str, Any], client) -> int:
        """Create a purchase order for the vendor bill"""
        try:
            # Create purchase order data
            po_data = {
                'partner_id': vendor_id,
                'state': 'draft',
                'order_line': []
            }
            
            # Add dates if available
            invoice_date = invoice_data.get("invoice_date")
            if invoice_date:
                po_data['date_order'] = invoice_date
            
            # Add line items
            line_items = invoice_data.get("line_items", [])
            if line_items:
                for item in line_items:
                    # Try to find existing product or create a generic one
                    product_name = self._get_valid_string(item.get("description"), "Product/Service")
                    
                    # For simplicity, we'll use a generic product or create one
                    # In a real implementation, you might want to match products more intelligently
                    line = (0, 0, {
                        'name': product_name,
                        'product_qty': float(item.get("quantity", 1)),
                        'price_unit': float(item.get("unit_price", 0)),
                        'date_planned': invoice_date or client.call_method('ir.fields', 'datetime', ['now'])
                    })
                    po_data['order_line'].append(line)
            else:
                # Create single line with total amount
                total_amount = invoice_data.get("total_amount", 0)
                if total_amount:
                    line = (0, 0, {
                        'name': 'Invoice Amount',
                        'product_qty': 1,
                        'price_unit': float(total_amount),
                        'date_planned': invoice_date or client.call_method('ir.fields', 'datetime', ['now'])
                    })
                    po_data['order_line'].append(line)
            
            # Create the purchase order
            po_id = client.create('purchase.order', po_data)
            
            # Confirm the purchase order to make it ready for billing
            try:
                client.call_method('purchase.order', 'button_confirm', [po_id])
            except:
                # If confirmation fails, that's okay - we can still link the bill
                pass
            
            return po_id
            
        except Exception as e:
            raise Exception(f"Failed to create purchase order: {str(e)}")
    
    def _create_vendor_bill(self, invoice_data: Dict[str, Any], client=None) -> ProcessingResult:
        """Create vendor bill from invoice data"""
        try:
            # Use the passed client or fall back to global client
            odoo_client_to_use = client or odoo_client
            
            # Find or create vendor
            vendor_name = invoice_data.get("vendor_name")
            if not vendor_name:
                return ProcessingResult(False, error="Vendor name is required")
            
            vendor = odoo_client_to_use.find_partner_by_name(vendor_name)
            if not vendor:
                # Create new vendor
                vendor_data = {
                    'name': vendor_name,
                    'is_company': True,
                    'supplier_rank': 1
                }
                
                # Add optional fields using _get_valid_string to handle None values
                vendor_data['street'] = self._get_valid_string(invoice_data.get("vendor_address"), "")
                vendor_data['email'] = self._get_valid_string(invoice_data.get("vendor_email"), "")
                vendor_data['phone'] = self._get_valid_string(invoice_data.get("vendor_phone"), "")
                
                vendor_id = odoo_client_to_use.create('res.partner', vendor_data)
            else:
                vendor_id = vendor['id']
            
            # Create purchase order first
            po_id = self._create_purchase_order(vendor_id, invoice_data, odoo_client_to_use)
            
            # Get or create purchase journal
            journal_id = self._get_or_create_purchase_journal(odoo_client_to_use)
            
            # Create vendor bill with proper purchase order linking
            # Get the purchase order name for reference
            po_records = odoo_client_to_use.read('purchase.order', po_id, ['name'])
            po_record = po_records[0] if isinstance(po_records, list) else po_records
            po_name = po_record.get('name', f"P{po_id:05d}")
            
            bill_data = {
                'partner_id': vendor_id,
                'move_type': 'in_invoice',
                'journal_id': journal_id,
                'ref': self._get_valid_string(invoice_data.get("invoice_number"), ""),
                'invoice_origin': po_name,  # Link to purchase order by name
                'invoice_line_ids': []
            }
            
            # Try to add purchase order ID in different ways
            try:
                # Method 1: Try purchase_vendor_bill_id field
                bill_data['purchase_vendor_bill_id'] = po_id
            except:
                try:
                    # Method 2: Try purchase_id field
                    bill_data['purchase_id'] = po_id
                except:
                    pass
            
            # Add dates only if they are valid (not None)
            invoice_date = invoice_data.get("invoice_date")
            if invoice_date:
                bill_data['invoice_date'] = invoice_date
            
            due_date = invoice_data.get("due_date")
            if due_date:
                bill_data['invoice_date_due'] = due_date
            
            # Add line items
            line_items = invoice_data.get("line_items", [])
            if line_items:
                for item in line_items:
                    line = (0, 0, {
                        'name': self._get_valid_string(item.get("description"), "Product/Service"),
                        'quantity': float(item.get("quantity", 1)),
                        'price_unit': float(item.get("unit_price", 0))
                    })
                    bill_data['invoice_line_ids'].append(line)
            else:
                # Create single line with total amount
                total_amount = invoice_data.get("total_amount", 0)
                if total_amount:
                    line = (0, 0, {
                        'name': 'Invoice Amount',
                        'quantity': 1,
                        'price_unit': float(total_amount)
                    })
                    bill_data['invoice_line_ids'].append(line)
            
            bill_id = odoo_client_to_use.create('account.move', bill_data)
            
            # After creating the bill, try to establish the link using different methods
            try:
                # Method 1: Update the purchase order to reference this bill
                odoo_client_to_use.write('purchase.order', po_id, {'invoice_ids': [(4, bill_id)]})
            except Exception as e:
                logger.debug(f"Could not link via purchase order invoice_ids: {e}")
                try:
                    # Method 2: Update the bill with purchase order line references
                    po_lines = odoo_client_to_use.search('purchase.order.line', [('order_id', '=', po_id)])
                    if po_lines:
                        # Update bill lines to reference purchase order lines
                        bill_lines = odoo_client_to_use.search('account.move.line', [('move_id', '=', bill_id), ('exclude_from_invoice_tab', '=', False)])
                        if bill_lines and len(bill_lines) >= len(po_lines):
                            for i, po_line_id in enumerate(po_lines[:len(bill_lines)]):
                                try:
                                    odoo_client_to_use.write('account.move.line', bill_lines[i], {'purchase_line_id': po_line_id})
                                except:
                                    pass
                except Exception as e:
                    logger.debug(f"Could not link via purchase order lines: {e}")
            
            return ProcessingResult(
                True,
                data={
                    'type': 'vendor_bill',
                    'id': bill_id,
                    'purchase_order_id': po_id,
                    'vendor_id': vendor_id,
                    'vendor_name': vendor_name,
                    'reference': invoice_data.get("invoice_number", ""),
                    'amount': invoice_data.get("total_amount", 0)
                },
                confidence=invoice_data.get("confidence_score", 0.8)
            )
            
        except Exception as e:
            return ProcessingResult(False, error=f"Failed to create vendor bill: {str(e)}")
    
    def _create_contact(self, contact_data: Dict[str, Any], client=None) -> ProcessingResult:
        """Create contact from business card data"""
        try:
            # Use the passed client or fall back to global client
            odoo_client_to_use = client or odoo_client
            
            logger.info(f"[CREATE_CONTACT] Starting contact creation")
            logger.info(f"[CREATE_CONTACT] Contact data: {contact_data}")
            
            name = contact_data.get("name")
            if not name:
                logger.error(f"[CREATE_CONTACT] Contact name is required but not provided")
                return ProcessingResult(False, error="Contact name is required")
            
            logger.info(f"[CREATE_CONTACT] Creating contact for: {name}")
            
            # Check for existing contact
            logger.info(f"[CREATE_CONTACT] Checking for existing contact...")
            existing_contact = odoo_client_to_use.find_partner_by_name(name)
            if existing_contact:
                logger.info(f"[CREATE_CONTACT] Contact already exists: {existing_contact}")
                return ProcessingResult(
                    True,
                    data={
                        'type': 'contact_exists',
                        'id': existing_contact['id'],
                        'name': existing_contact['name'],
                        'message': 'Contact already exists'
                    }
                )
            
            # Create new contact using _get_valid_string to handle None values
            partner_data = {
                'name': name,
                'is_company': False,
                'email': self._get_valid_string(contact_data.get("email"), ""),
                'phone': self._get_valid_string(contact_data.get("phone"), ""),
                'mobile': self._get_valid_string(contact_data.get("mobile"), ""),
                'street': self._get_valid_string(contact_data.get("address"), ""),
                'website': self._get_valid_string(contact_data.get("website"), ""),
                'function': self._get_valid_string(contact_data.get("title"), ""),
                'comment': f"Created from business card. Company: {self._get_valid_string(contact_data.get('company'), 'N/A')}"
            }
            
            logger.info(f"[CREATE_CONTACT] Prepared partner data: {partner_data}")
            logger.info(f"[CREATE_CONTACT] Calling odoo_client.create('res.partner', ...)")
            
            contact_id = odoo_client_to_use.create('res.partner', partner_data)
            
            logger.info(f"[CREATE_CONTACT] Contact created with ID: {contact_id}")
            
            result = ProcessingResult(
                True,
                data={
                    'type': 'contact_created',
                    'id': contact_id,
                    'name': name,
                    'company': contact_data.get("company", ""),
                    'email': contact_data.get("email", "")
                },
                confidence=contact_data.get("confidence_score", 0.8)
            )
            
            logger.info(f"[CREATE_CONTACT] Returning result: {result.to_dict()}")
            return result
            
        except Exception as e:
            logger.error(f"[CREATE_CONTACT] Exception in contact creation: {str(e)}")
            import traceback
            logger.error(f"[CREATE_CONTACT] Traceback: {traceback.format_exc()}")
            return ProcessingResult(False, error=f"Failed to create contact: {str(e)}")
    
    def _create_expense(self, receipt_data: Dict[str, Any], client=None) -> ProcessingResult:
        """Create expense from receipt data"""
        try:
            # Use the passed client or fall back to global client
            odoo_client_to_use = client or odoo_client
            
            logger.info(f"[CREATE_EXPENSE] Starting expense creation with data: {receipt_data}")
            
            # Extract required data - handle both merchant_name and vendor_name
            merchant_name = receipt_data.get("merchant_name") or receipt_data.get("vendor_name")
            total_amount = receipt_data.get("total_amount")
            
            if not merchant_name or not total_amount:
                return ProcessingResult(False, error="Merchant/vendor name and amount are required")
            
            # Get default employee
            logger.info(f"[CREATE_EXPENSE] Getting default employee")
            try:
                employees = odoo_client_to_use.search_read(
                    'hr.employee',
                    [('user_id', '=', odoo_client_to_use.uid)],
                    ['id'],
                    limit=1
                )
                
                if not employees:
                    # Fallback to first available employee
                    employees = odoo_client_to_use.search_read(
                        'hr.employee',
                        [],
                        ['id'],
                        limit=1
                    )
                
                if not employees:
                    return ProcessingResult(False, error="No employee found in the system")
                
                employee_id = employees[0]['id']
                logger.info(f"[CREATE_EXPENSE] Using employee ID: {employee_id}")
                
            except Exception as e:
                logger.error(f"[CREATE_EXPENSE] Error getting employee: {str(e)}")
                return ProcessingResult(False, error=f"Failed to get employee: {str(e)}")
            
            # Get or create expense product
            try:
                products = odoo_client_to_use.search_read(
                    'product.product',
                    [('can_be_expensed', '=', True)],
                    ['id'],
                    limit=1
                )
                
                if not products:
                    # Create a generic expense product
                    product_data = {
                        'name': 'General Expense',
                        'type': 'service',
                        'can_be_expensed': True,
                        'list_price': 0.0
                    }
                    product_id = odoo_client_to_use.create('product.product', product_data)
                    logger.info(f"[CREATE_EXPENSE] Created expense product with ID: {product_id}")
                else:
                    product_id = products[0]['id']
                    logger.info(f"[CREATE_EXPENSE] Using existing product ID: {product_id}")
                    
            except Exception as e:
                logger.error(f"[CREATE_EXPENSE] Error getting/creating product: {str(e)}")
                return ProcessingResult(False, error=f"Failed to get expense product: {str(e)}")
            
            # Prepare expense data with correct field names for Odoo 18
            expense_data = {
                'name': f'Expense - {merchant_name}',
                'employee_id': employee_id,
                'product_id': product_id,
                'total_amount': float(total_amount),  # Use total_amount instead of unit_amount
                'quantity': 1,
                'date': receipt_data.get("date", datetime.now().strftime('%Y-%m-%d')),
                'description': self._build_expense_description(receipt_data),
                'payment_mode': 'own_account'
            }
            
            logger.info(f"[CREATE_EXPENSE] Prepared expense data: {expense_data}")
            
            # Create the expense
            expense_id = odoo_client_to_use.create('hr.expense', expense_data)
            
            if expense_id:
                logger.info(f"[CREATE_EXPENSE] Successfully created expense with ID: {expense_id}")
                return ProcessingResult(
                    True,
                    data={
                        'type': 'expense_created',
                        'id': expense_id,
                        'merchant': merchant_name,
                        'amount': total_amount,
                        'date': expense_data['date'],
                        'employee_id': employee_id
                    },
                    confidence=receipt_data.get("confidence_score", 0.8)
                )
            else:
                logger.error(f"[CREATE_EXPENSE] Failed to create expense - no ID returned")
                return ProcessingResult(False, error="Failed to create expense - no ID returned")
            
        except Exception as e:
            logger.error(f"[CREATE_EXPENSE] Exception in expense creation: {str(e)}")
            import traceback
            logger.error(f"[CREATE_EXPENSE] Traceback: {traceback.format_exc()}")
            return ProcessingResult(False, error=f"Failed to create expense: {str(e)}")
    
    def _build_expense_description(self, receipt_data: Dict[str, Any]) -> str:
        """Build a comprehensive description for the expense"""
        description_parts = []
        
        merchant = receipt_data.get("merchant_name") or receipt_data.get("vendor_name")
        if merchant:
            description_parts.append(f"Expense at {merchant}")
        
        # Add line items if available
        line_items = receipt_data.get("line_items", [])
        if line_items:
            description_parts.append("\nItems:")
            for item in line_items:
                item_name = item.get("description", "Unknown Item")
                item_price = item.get("total", 0)
                description_parts.append(f"- {item_name}: ${item_price}")
        
        return "\n".join(description_parts) if description_parts else "Expense from receipt"
    
    def _create_lead(self, extracted_data: Dict[str, Any], client=None) -> ProcessingResult:
        """Create a CRM lead from business card data with enhanced validation"""
        try:
            from datetime import datetime
            
            # Use provided client or fall back to global odoo_client
            odoo_client_to_use = client or odoo_client
            
            logger.info(f"Creating lead from extracted data: {extracted_data}")
            
            # Extract and validate data
            name = self._get_valid_string(extracted_data.get('name'), 'Unknown Contact')
            company = self._get_valid_string(extracted_data.get('company'), '')
            email = self._get_valid_string(extracted_data.get('email'), '')
            phone = self._get_valid_string(extracted_data.get('phone'), '')
            mobile = self._get_valid_string(extracted_data.get('mobile'), '')
            website = self._get_valid_string(extracted_data.get('website'), '')
            job_title = self._get_valid_string(extracted_data.get('title'), '')
            
            # Generate meaningful lead name with timestamp
            timestamp = datetime.now().strftime("%Y-%m-%d")
            if company and name != 'Unknown Contact':
                lead_name = f"{company} - {name} ({timestamp})"
            elif company:
                lead_name = f"{company} - New Lead ({timestamp})"
            elif name != 'Unknown Contact':
                lead_name = f"{name} - Business Card Lead ({timestamp})"
            else:
                lead_name = f"Business Card Lead ({timestamp})"
            
            # Generate comprehensive description
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
                'description': "\n".join(description_parts),
                'type': 'lead',  # Explicitly set as lead
                'stage_id': 1,  # Default to first stage (New)
                'priority': '1',  # Normal priority
            }
            
            # Try to get or create lead source
            try:
                source_id = self._get_or_create_lead_source(odoo_client_to_use)
                if source_id:
                    lead_data['source_id'] = source_id
            except Exception as e:
                logger.warning(f"Could not set lead source: {str(e)}")
            
            # Clean up empty fields but keep mandatory ones
            mandatory_fields = {'name', 'stage_id', 'type', 'priority'}
            cleaned_lead_data = {}
            for key, value in lead_data.items():
                if key in mandatory_fields or (value and str(value).strip()):
                    cleaned_lead_data[key] = value
            
            logger.info(f"Prepared lead data: {cleaned_lead_data}")
            
            # Create the lead
            lead_id = odoo_client_to_use.create('crm.lead', cleaned_lead_data)
            
            if lead_id:
                logger.info(f"Successfully created lead with ID: {lead_id}")
                
                # Verify the lead was created
                try:
                    verification = self._verify_lead_creation(lead_id, odoo_client_to_use)
                    logger.info(f"Lead verification: {verification}")
                except Exception as e:
                    logger.warning(f"Lead verification failed: {str(e)}")
                
                return ProcessingResult(
                    True, 
                    data={
                        'type': 'lead_created',
                        'id': lead_id,
                        'contact_name': name,
                        'company': company,
                        'email': email,
                        'phone': phone or mobile,
                        'lead_name': lead_name,
                        'stage': 'New'
                    },
                    confidence=extracted_data.get("confidence_score", 0.8)
                )
            else:
                logger.error("Failed to create lead - no ID returned")
                return ProcessingResult(False, error="Failed to create lead - no ID returned")
                
        except Exception as e:
            logger.error(f"Error creating lead: {str(e)}")
            return ProcessingResult(False, error=f"Failed to create lead: {str(e)}")
    
    def _get_valid_string(self, value: Any, default: str = '') -> str:
        """Get a valid string value or default"""
        if value is None:
            return default
        return str(value).strip() if str(value).strip() else default
    
    def _get_or_create_lead_source(self, client=None) -> Optional[int]:
        """Get or create a lead source for business cards"""
        try:
            # Use provided client or fall back to global odoo_client
            odoo_client_to_use = client or odoo_client
            
            # Try to find existing source
            sources = odoo_client_to_use.search_read(
                'utm.source',
                [('name', '=', 'Business Card')],
                ['id'],
                limit=1
            )
            
            if sources:
                return sources[0]['id']
            
            # Create new source if not found
            source_id = odoo_client_to_use.create('utm.source', {
                'name': 'Business Card',
                'description': 'Leads generated from business card processing'
            })
            
            logger.info(f"Created new lead source with ID: {source_id}")
            return source_id
            
        except Exception as e:
            logger.warning(f"Could not create/find lead source: {str(e)}")
            return None
    
    def _verify_lead_creation(self, lead_id: int, client=None) -> Dict[str, Any]:
        """Verify that the lead was created successfully"""
        try:
            # Use provided client or fall back to global odoo_client
            odoo_client_to_use = client or odoo_client
            
            # Read the created lead
            lead = odoo_client_to_use.search_read(
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
    
    def _handle_manual_entry(self, state: AgentState, client=None) -> ProcessingResult:
        """Handle manual data entry requests"""
        try:
            user_message = StateManager.get_last_user_message(state)
            entities = state.get("entities", {})
            
            logger.info(f"Processing manual data entry for: {user_message}")
            
            # Check for LinkedIn lead creation first
            if entities.get("linkedin_url") or entities.get("linkedin_lead"):
                linkedin_url = entities.get("linkedin_url")
                if linkedin_url:
                    logger.info(f"Processing LinkedIn lead creation for URL: {linkedin_url}")
                    return self._create_linkedin_lead(linkedin_url, client)
            
            # Parse the user message to determine what type of record to create
            message_lower = user_message.lower()
            
            if any(word in message_lower for word in ['lead', 'prospect', 'opportunity']):
                return self._create_lead_from_text(user_message, entities, client)
            elif any(word in message_lower for word in ['contact', 'customer', 'partner']):
                return self._create_contact_from_text(user_message, entities, client)
            elif any(word in message_lower for word in ['invoice', 'bill']):
                return self._create_invoice_from_text(user_message, entities, client)
            else:
                # Try to extract structured data using Gemini
                return self._extract_and_create_from_text(user_message, entities, client)
                
        except Exception as e:
            logger.error(f"Manual data entry failed: {str(e)}")
            return ProcessingResult(False, error=f"Manual data entry failed: {str(e)}")
    
    def _create_linkedin_lead(self, linkedin_url: str, client=None) -> ProcessingResult:
        """Create a lead from LinkedIn profile URL using APIFY API"""
        try:
            from linkedin_api import fetch_linkedin_profile
            from gemini_client import gemini_client
            
            logger.info(f"Fetching LinkedIn profile data for: {linkedin_url}")
            
            # Fetch LinkedIn profile data using APIFY
            raw_profile = fetch_linkedin_profile(linkedin_url)
            logger.info(f"Raw LinkedIn profile fetched: {type(raw_profile)}")
            
            # Try Gemini cleaning first
            cleaned_profile = gemini_client.clean_linkedin_profile(raw_profile)
            logger.info(f"LinkedIn profile cleaned by Gemini")
            
            # Check if profile cleaning failed or if Gemini is not working
            if cleaned_profile.get('error') or not cleaned_profile.get('name'):
                logger.warning(f"Gemini cleaning failed or returned incomplete data: {cleaned_profile.get('error', 'No name field')}")
                logger.info("Attempting direct data extraction from APIFY response")
                
                # Direct extraction from APIFY data structure
                cleaned_profile = self._extract_linkedin_data_directly(raw_profile, linkedin_url)
                logger.info(f"Direct extraction completed with confidence: {cleaned_profile.get('confidence_score', 0.0)}")
            
            # Create lead using cleaned profile data
            result = self._create_lead(cleaned_profile, client)
            
            if result.success:
                logger.info(f"LinkedIn lead created successfully from: {linkedin_url}")
                # Add LinkedIn URL to the description
                if result.data and 'id' in result.data:
                    try:
                        odoo_client_to_use = client or odoo_client
                        lead_id = result.data['id']
                        current_desc = odoo_client_to_use.read('crm.lead', [lead_id], ['description'])[0].get('description', '')
                        new_desc = f"{current_desc}\n\nLinkedIn Profile: {linkedin_url}".strip()
                        odoo_client_to_use.write('crm.lead', [lead_id], {'description': new_desc})
                        logger.info(f"Added LinkedIn URL to lead description")
                    except Exception as e:
                        logger.warning(f"Could not update lead description with LinkedIn URL: {e}")
            
            return result
            
        except Exception as e:
            logger.error(f"LinkedIn lead creation failed: {str(e)}")
            return ProcessingResult(False, error=f"LinkedIn lead creation failed: {str(e)}")
    
    def _extract_linkedin_data_directly(self, raw_profile: dict, linkedin_url: str) -> dict:
        """Extract LinkedIn data directly from APIFY response structure"""
        try:
            logger.info("Extracting LinkedIn data directly from APIFY response")
            
            extracted_data = {
                'name': None,
                'company': None,
                'title': None,
                'email': None,
                'phone': None,
                'mobile': None,
                'website': None,
                'address': None,
                'linkedin': linkedin_url,
                'confidence_score': 0.7  # Good confidence for direct extraction
            }
            
            # Extract basic info
            basic_info = raw_profile.get('basic_info', {})
            if basic_info:
                extracted_data['name'] = basic_info.get('fullname') or f"{basic_info.get('first_name', '')} {basic_info.get('last_name', '')}".strip()
                headline = basic_info.get('headline', '')
                if headline:
                    extracted_data['title'] = headline
                
                # Try to extract location
                location = basic_info.get('location')
                if location:
                    extracted_data['address'] = location
            
            # Extract current experience (first entry is usually current)
            experience = raw_profile.get('experience', [])
            if experience and len(experience) > 0:
                current_job = experience[0]
                if not extracted_data['title'] and current_job.get('title'):
                    extracted_data['title'] = current_job.get('title')
                if not extracted_data['company'] and current_job.get('company'):
                    extracted_data['company'] = current_job.get('company')
                if not extracted_data['address'] and current_job.get('location'):
                    extracted_data['address'] = current_job.get('location')
            
            # Clean up empty values
            for key, value in extracted_data.items():
                if value == '' or value == 'None':
                    extracted_data[key] = None
            
            # Calculate confidence based on available data
            available_fields = sum(1 for v in extracted_data.values() if v is not None)
            extracted_data['confidence_score'] = min(0.9, 0.3 + (available_fields * 0.1))
            
            logger.info(f"Direct extraction results: name='{extracted_data['name']}', company='{extracted_data['company']}', title='{extracted_data['title']}'")
            
            return extracted_data
            
        except Exception as e:
            logger.error(f"Direct extraction failed: {str(e)}")
            # Ultimate fallback
            return {
                'name': f"LinkedIn Contact - {linkedin_url.split('/')[-1]}",
                'description': f"LinkedIn Profile: {linkedin_url}\n\nRaw data: {str(raw_profile)[:500]}...",
                'linkedin': linkedin_url,
                'confidence_score': 0.2
            }
    
    def _create_lead_from_text(self, user_message: str, entities: Dict, client=None) -> ProcessingResult:
        """Create a lead from text description"""
        try:
            # Use Gemini to extract lead information from text
            prompt = f"""
            Extract lead information from this text and return as JSON:
            
            Text: "{user_message}"
            
            Return JSON with these fields (use empty string if not found):
            {{
                "name": "lead/opportunity name",
                "contact_name": "contact person name",
                "company": "company name",
                "email": "email address",
                "phone": "phone number",
                "title": "job title",
                "description": "additional notes",
                "confidence_score": 0.8
            }}
            """
            
            response = gemini_client.generate_text(prompt)
            logger.debug(f"Raw Gemini response for lead: {response[:200]}...")
            
            try:
                import json
                # Clean the response before parsing
                cleaned_response = gemini_client._clean_json_response(response)
                
                if not cleaned_response.strip():
                    logger.warning("Empty response from Gemini for lead creation")
                    raise ValueError("Empty response from Gemini")
                
                extracted_data = json.loads(cleaned_response)
            except Exception as parse_error:
                logger.warning(f"Failed to parse Gemini response for lead: {parse_error}")
                # Fallback to basic extraction
                extracted_data = {
                    "name": f"Lead from text - {datetime.now().strftime('%Y-%m-%d')}",
                    "description": user_message,
                    "confidence_score": 0.6
                }
            
            return self._create_lead(extracted_data, client)
            
        except Exception as e:
            return ProcessingResult(False, error=f"Failed to create lead from text: {str(e)}")
    
    def _create_contact_from_text(self, user_message: str, entities: Dict, client=None) -> ProcessingResult:
        """Create a contact from text description"""
        try:
            # Use Gemini to extract contact information from text
            prompt = f"""
            Extract contact information from this text and return as JSON:
            
            Text: "{user_message}"
            
            Return JSON with these fields (use empty string if not found):
            {{
                "name": "person name",
                "company": "company name",
                "email": "email address",
                "phone": "phone number",
                "mobile": "mobile number",
                "title": "job title",
                "address": "address",
                "website": "website",
                "confidence_score": 0.8
            }}
            """
            
            response = gemini_client.generate_text(prompt)
            logger.debug(f"Raw Gemini response for contact: {response[:200]}...")
            
            try:
                import json
                # Clean the response before parsing
                cleaned_response = gemini_client._clean_json_response(response)
                
                if not cleaned_response.strip():
                    logger.warning("Empty response from Gemini for contact creation")
                    raise ValueError("Empty response from Gemini")
                
                extracted_data = json.loads(cleaned_response)
            except Exception as parse_error:
                logger.warning(f"Failed to parse Gemini response for contact: {parse_error}")
                # Fallback to basic extraction
                extracted_data = {
                    "name": "Contact from text",
                    "confidence_score": 0.6
                }
            
            return self._create_contact(extracted_data, client)
            
        except Exception as e:
            return ProcessingResult(False, error=f"Failed to create contact from text: {str(e)}")
    
    def _create_invoice_from_text(self, user_message: str, entities: Dict, client=None) -> ProcessingResult:
        """Create an invoice from text description"""
        try:
            # Use Gemini to extract invoice information from text
            prompt = f"""
            Extract invoice information from this text and return as JSON:
            
            Text: "{user_message}"
            
            Return JSON with these fields (use empty string if not found):
            {{
                "vendor_name": "vendor/supplier name",
                "invoice_number": "invoice number",
                "total_amount": "total amount as number",
                "invoice_date": "invoice date",
                "due_date": "due date",
                "description": "invoice description",
                "confidence_score": 0.8
            }}
            """
            
            response = gemini_client.generate_text(prompt)
            logger.debug(f"Raw Gemini response for invoice: {response[:200]}...")
            
            try:
                import json
                # Clean the response before parsing
                cleaned_response = gemini_client._clean_json_response(response)
                
                if not cleaned_response.strip():
                    logger.warning("Empty response from Gemini for invoice creation")
                    raise ValueError("Empty response from Gemini")
                
                extracted_data = json.loads(cleaned_response)
            except Exception as parse_error:
                logger.warning(f"Failed to parse Gemini response for invoice: {parse_error}")
                # Fallback to basic extraction
                extracted_data = {
                    "vendor_name": "Vendor from text",
                    "description": user_message,
                    "confidence_score": 0.6
                }
            
            return self._create_vendor_bill(extracted_data, client)
            
        except Exception as e:
            return ProcessingResult(False, error=f"Failed to create invoice from text: {str(e)}")
    
    def _extract_and_create_from_text(self, user_message: str, entities: Dict, client=None) -> ProcessingResult:
        """Extract structured data from text and determine what to create"""
        try:
            # Use Gemini to analyze the text and determine the best action
            prompt = f"""
            Analyze this text and determine what type of Odoo record should be created:
            
            Text: "{user_message}"
            
            Return JSON with:
            {{
                "record_type": "lead|contact|invoice|other",
                "extracted_data": {{relevant fields based on record_type}},
                "confidence_score": 0.8,
                "reasoning": "why this record type was chosen"
            }}
            """
            
            response = gemini_client.generate_text(prompt)
            
            # Log the raw response for debugging
            logger.debug(f"Raw Gemini response: {response[:200]}...")
            
            try:
                import json
                # Clean the response before parsing
                cleaned_response = gemini_client._clean_json_response(response)
                logger.debug(f"Cleaned response: {cleaned_response[:200]}...")
                
                if not cleaned_response.strip():
                    logger.warning("Empty response from Gemini after cleaning")
                    raise ValueError("Empty response from Gemini")
                
                analysis = json.loads(cleaned_response)
                record_type = analysis.get("record_type", "other")
                extracted_data = analysis.get("extracted_data", {})
                
                if record_type == "lead":
                    return self._create_lead(extracted_data, client)
                elif record_type == "contact":
                    return self._create_contact(extracted_data, client)
                else:
                    return ProcessingResult(
                        True,
                        data={
                            'type': 'analysis_result',
                            'record_type': record_type,
                            'extracted_data': extracted_data,
                            'reasoning': analysis.get('reasoning', ''),
                            'message': f'Analyzed request: {analysis.get("reasoning", "")}'
                        },
                        confidence=analysis.get('confidence_score', 0.6)
                    )
                    
            except Exception as parse_error:
                logger.warning(f"Failed to parse Gemini response: {parse_error}")
                return ProcessingResult(
                    True,
                    data={
                        'type': 'text_processed',
                        'message': f'Processed text request: {user_message[:100]}...',
                        'raw_response': response
                    },
                    confidence=0.5
                )
                
        except Exception as e:
            return ProcessingResult(False, error=f"Failed to process text request: {str(e)}")
    
    def _generate_report(self, state: AgentState, client=None) -> ProcessingResult:
        """Generate reports based on user request"""
        try:
            if state is None:
                return ProcessingResult(False, error="State is None")
            
            try:
                user_message = StateManager.get_last_user_message(state)
            except Exception as e:
                logger.warning(f"Could not extract user message for report generation: {e}")
                user_message = ""
            
            # Extract entities for report parameters
            entities = state.get("entities", {})
            
            # Handle common reporting requests
            if "sales order" in user_message.lower():
                return self._get_sales_orders_report(entities, client)
            elif "invoice" in user_message.lower():
                return self._get_invoices_report(entities, client)
            elif "customer" in user_message.lower():
                return self._get_customers_report(entities, client)
            elif "product" in user_message.lower():
                return self._get_products_report(entities, client)
            else:
                return ProcessingResult(
                    True,
                    data={
                        'type': 'report_info',
                        'message': 'I can help you with reports on sales orders, invoices, customers, and products. What specific information would you like to see?'
                    }
                )
                
        except Exception as e:
            return ProcessingResult(False, error=f"Report generation failed: {str(e)}")
    
    def _get_sales_orders_report(self, entities: Dict, client=None) -> ProcessingResult:
        """Get sales orders report"""
        try:
            # Use provided client or fall back to global odoo_client
            odoo_client_to_use = client or odoo_client
            
            # Search for sales orders
            domain = [('state', 'in', ['sale', 'done'])]  # Confirmed orders
            
            orders = odoo_client_to_use.search_read('sale.order', domain, 
                                            ['name', 'partner_id', 'amount_total', 'state', 'date_order'],
                                            limit=100)
            
            total_count = len(orders)
            total_amount = sum(order['amount_total'] for order in orders)
            
            return ProcessingResult(
                True,
                data={
                    'type': 'sales_orders_report',
                    'total_count': total_count,
                    'total_amount': total_amount,
                    'orders': orders[:10],  # Show first 10
                    'message': f'Found {total_count} sales orders with total value of ${total_amount:,.2f}'
                }
            )
            
        except Exception as e:
            return ProcessingResult(False, error=f"Failed to get sales orders: {str(e)}")
    
    def _get_invoices_report(self, entities: Dict, client=None) -> ProcessingResult:
        """Get invoices report"""
        try:
            # Use provided client or fall back to global odoo_client
            odoo_client_to_use = client or odoo_client
            
            domain = [('move_type', '=', 'out_invoice'), ('state', '=', 'posted')]
            
            invoices = odoo_client_to_use.search_read('account.move', domain,
                                             ['name', 'partner_id', 'amount_total', 'invoice_date'],
                                             limit=100)
            
            total_count = len(invoices)
            total_amount = sum(inv['amount_total'] for inv in invoices)
            
            return ProcessingResult(
                True,
                data={
                    'type': 'invoices_report',
                    'total_count': total_count,
                    'total_amount': total_amount,
                    'invoices': invoices[:10],
                    'message': f'Found {total_count} posted invoices with total value of ${total_amount:,.2f}'
                }
            )
            
        except Exception as e:
            return ProcessingResult(False, error=f"Failed to get invoices: {str(e)}")
    
    def _get_customers_report(self, entities: Dict, client=None) -> ProcessingResult:
        """Get customers report"""
        try:
            # Use provided client or fall back to global odoo_client
            odoo_client_to_use = client or odoo_client
            
            domain = [('is_company', '=', True), ('customer_rank', '>', 0)]
            
            customers = odoo_client_to_use.search_read('res.partner', domain,
                                              ['name', 'email', 'phone', 'country_id'],
                                              limit=100)
            
            total_count = len(customers)
            
            return ProcessingResult(
                True,
                data={
                    'type': 'customers_report',
                    'total_count': total_count,
                    'customers': customers[:10],
                    'message': f'Found {total_count} customers in the system'
                }
            )
            
        except Exception as e:
            return ProcessingResult(False, error=f"Failed to get customers: {str(e)}")
    
    def _get_products_report(self, entities: Dict, client=None) -> ProcessingResult:
        """Get products report"""
        try:
            # Use provided client or fall back to global odoo_client
            odoo_client_to_use = client or odoo_client
            
            domain = [('sale_ok', '=', True)]  # Saleable products
            
            products = odoo_client_to_use.search_read('product.product', domain,
                                             ['name', 'list_price', 'qty_available', 'categ_id'],
                                             limit=100)
            
            total_count = len(products)
            
            return ProcessingResult(
                True,
                data={
                    'type': 'products_report',
                    'total_count': total_count,
                    'products': products[:10],
                    'message': f'Found {total_count} saleable products in the system'
                }
            )
            
        except Exception as e:
            return ProcessingResult(False, error=f"Failed to get products: {str(e)}")

class QANavigationNode:
    """Node for handling Q&A and navigation requests with RAG integration"""
    
    def process(self, state: AgentState) -> AgentState:
        """Handle Q&A and navigation requests"""
        try:
            if state is None:
                logger.error("Q&A processing failed: state is None")
                return state
            
            try:
                user_message = StateManager.get_last_user_message(state)
            except Exception as e:
                logger.warning(f"Could not extract user message for Q&A processing: {e}")
                user_message = ""
            
            logger.info(f"Processing Q&A request: {user_message[:100]}...")
            
            # Get session-specific Odoo client
            session_id = state.get("session_id")
            current_odoo_client = get_odoo_client_for_session(session_id)
            
            # Get Odoo context
            odoo_context = self._get_odoo_context(current_odoo_client)
            
            # Check if it's a navigation request
            if self._is_navigation_request(user_message):
                response = self._handle_navigation(user_message, odoo_context)
                state["response_type"] = "navigation"
            elif self._is_documentation_request(user_message):
                # Route to RAG documentation handler
                logger.info(f"Routing to RAG documentation handler for: {user_message[:100]}...")
                response = self._handle_documentation_query(user_message, state)
                state["response_type"] = "documentation"
            else:
                # Generate Q&A response using Gemini
                context = self._get_relevant_context(user_message)
                response = gemini_client.generate_qa_response(user_message, context, odoo_context)
                state["response_type"] = "text"
            
            state["response"] = response
            state["current_step"] = "qa_completed"
            state["next_action"] = "finalize_response"
            
            logger.info("Q&A processing completed")
            
        except Exception as e:
            logger.error(f"Q&A processing failed: {str(e)}")
            StateManager.set_error(state, f"Q&A processing failed: {str(e)}", "qa_error")
        
        return state
    
    def _is_navigation_request(self, message: str) -> bool:
        """Check if the message is a navigation request"""
        navigation_keywords = [
            "go to", "open", "show me", "navigate to", "take me to",
            "where is", "how to get to", "find", "access"
        ]
        message_lower = message.lower()
        return any(keyword in message_lower for keyword in navigation_keywords)
    
    def _handle_navigation(self, message: str, odoo_context: Dict) -> str:
        """Handle navigation requests"""
        prompt = f"""
Provide navigation instructions for this Odoo request: {message}

Odoo System Information:
{json.dumps(odoo_context, indent=2)}

Provide step-by-step navigation instructions. If you can identify a specific menu path, include it.
Format your response as clear, actionable steps.
"""
        
        return gemini_client.generate_text(prompt)
    
    def _get_relevant_context(self, question: str) -> str:
        """Get relevant context for the question"""
        # This would typically use a vector database to find relevant documentation
        # For now, return basic Odoo information
        return """
Odoo is an integrated business management software with modules for:
- Sales (CRM, Sales Orders, Quotations)
- Accounting (Invoicing, Payments, Financial Reports)
- Inventory (Stock Management, Warehouses, Products)
- HR (Employees, Payroll, Time Tracking)
- Manufacturing (Bill of Materials, Work Orders)
- Website (E-commerce, Content Management)

Common navigation paths:
- Sales: Sales > Orders > Sales Orders
- Invoicing: Accounting > Customers > Invoices
- Inventory: Inventory > Operations > Transfers
- Contacts: Contacts > Contacts
"""
    
    def _get_odoo_context(self, client=None) -> Dict[str, Any]:
        """Get current Odoo system context"""
        try:
            # Use provided client or fall back to global odoo_client
            odoo_client_to_use = client or odoo_client
            
            if not odoo_client_to_use.uid:
                odoo_client_to_use.connect()
            
            user_info = odoo_client_to_use.get_user_info()
            return {
                'user': user_info,
                'database': odoo_client_to_use.db,
                'url': odoo_client_to_use.url,
                'connected': bool(odoo_client_to_use.uid)
            }
        except Exception as e:
            logger.error(f"Failed to get Odoo context: {str(e)}")
            return {'connected': False, 'error': str(e)}
    
    def _get_odoo_base_url_from_session(self, state: AgentState) -> Optional[str]:
        """Get Odoo base URL from session or config for navigation links"""
        try:
            # First try to get from session-specific client
            session_id = state.get("session_id")
            if session_id:
                try:
                    from services.agent_service import agent_service
                    session_client = agent_service.get_odoo_client_for_session(session_id)
                    if session_client and session_client.url:
                        logger.info(f"Using session-specific Odoo URL: {session_client.url}")
                        return session_client.url
                except Exception as e:
                    logger.debug(f"Could not get session-specific Odoo URL: {e}")
            
            # Fallback to global config
            from config import config
            if config.odoo.url:
                logger.info(f"Using global Odoo URL: {config.odoo.url}")
                return config.odoo.url
            
            # Last resort - try from saved frontend settings
            # This would require additional API to fetch user's saved Odoo URL
            logger.warning("No Odoo URL found in session or config")
            return None
            
        except Exception as e:
            logger.error(f"Failed to get Odoo base URL: {str(e)}")
            return None
    
    def _is_documentation_request(self, message: str) -> bool:
        """Check if the message is requesting Odoo documentation or how-to information"""
        documentation_keywords = [
            "how to", "how do i", "how can i", "how to create", "how to setup", "how to configure",
            "what is", "what are", "explain", "documentation", "guide", "tutorial", "instructions",
            "steps to", "procedure", "process", "workflow", "best practice", "recommended way",
            "how does", "how should", "what's the", "tell me about", "describe", "definition"
        ]
        message_lower = message.lower()
        return any(keyword in message_lower for keyword in documentation_keywords)
    
    def _handle_documentation_query(self, message: str, state: AgentState) -> str:
        """Handle documentation queries using RAG"""
        try:
            # Get conversation history for context
            conversation_history = state.get("conversation_memory", [])
            
            # Convert conversation history to the format expected by RAG client
            rag_conversation_history = []
            for msg in conversation_history:
                if isinstance(msg, dict) and "role" in msg and "content" in msg:
                    rag_conversation_history.append({
                        "role": msg["role"],
                        "content": msg["content"]
                    })
            
            logger.info(f"Calling rag_client.query_documentation for: {message[:100]}...")
            
            # Get Odoo base URL for navigation links
            odoo_base_url = self._get_odoo_base_url_from_session(state)
            
            # Query the RAG documentation API with navigation support
            rag_response = rag_client.query_documentation(
                query=message,
                version=180,  # Default to Odoo 18.0
                conversation_history=rag_conversation_history,
                odoo_base_url=odoo_base_url
            )
            
            if rag_response:
                logger.info(f"RAG API response keys: {list(rag_response.__dict__.keys()) if hasattr(rag_response, '__dict__') else 'N/A'}")
                logger.info(f"RAG API sources count: {len(rag_response.sources) if rag_response.sources else 0}")
                logger.info(f"RAG API navigation links count: {len(rag_response.navigation_links) if rag_response.navigation_links else 0}")
                
                # Format the response with minimal sources and navigation
                formatted_response = rag_client.format_response_with_sources(rag_response, include_navigation=True)
                logger.info(f"RAG documentation query completed successfully")
                return formatted_response
            else:
                logger.warning(f"RAG API returned no response for query: {message[:100]}...")
                # Fallback to Gemini if RAG fails
                context = self._get_relevant_context(message)
                odoo_context = self._get_odoo_context()
                return gemini_client.generate_qa_response(message, context, odoo_context)
                
        except Exception as e:
            logger.error(f"RAG documentation query failed: {str(e)}")
            # Fallback to Gemini if RAG fails
            try:
                context = self._get_relevant_context(message)
                odoo_context = self._get_odoo_context()
                return gemini_client.generate_qa_response(message, context, odoo_context)
            except Exception as fallback_error:
                logger.error(f"Fallback to Gemini also failed: {str(fallback_error)}")
                return f"I apologize, but I'm having trouble accessing the documentation right now. Please try again later or contact support. Error: {str(e)}"

class DataLookupNode:
    """Node for dynamic data lookup using LLM-generated Odoo API queries"""
    
    def __init__(self):
        self.sales_models = {
            'sale.order': 'Sales Orders',
            'sale.order.line': 'Sales Order Lines', 
            'res.partner': 'Customers/Partners',
            'product.product': 'Products',
            'product.template': 'Product Templates',
            'account.move': 'Invoices/Bills',
            'account.move.line': 'Invoice Lines',
            'stock.quant': 'Stock/Inventory',
            'stock.move': 'Stock Movements',
            'stock.picking': 'Stock Transfers/Deliveries',
            'stock.location': 'Stock Locations',
            'purchase.order': 'Purchase Orders',
            'purchase.order.line': 'Purchase Order Lines',
            'hr.expense': 'Employee Expenses',
            'hr.expense.sheet': 'Expense Reports',
            'crm.lead': 'Leads/Opportunities',
            'hr.employee': 'Employees',
            'hr.department': 'Departments',
            'hr.job': 'Job Positions'
        }
    
    @performance_tracker("data_lookup", performance_monitor)
    def process(self, state: AgentState) -> AgentState:
        """Process data lookup requests dynamically"""
        try:
            if state is None:
                logger.error("Data lookup failed: state is None")
                return state
            
            try:
                user_message = StateManager.get_last_user_message(state)
            except Exception as e:
                logger.warning(f"Could not extract user message for data lookup: {e}")
                user_message = ""
            logger.info(f"Processing data lookup for: {user_message}")
            
            # Get session-specific Odoo client
            session_id = state.get("session_id")
            current_odoo_client = get_odoo_client_for_session(session_id)
            
            # Ensure Odoo connection
            if not current_odoo_client.uid:
                if not current_odoo_client.connect():
                    StateManager.set_error(state, "Failed to connect to Odoo", "odoo_connection_error")
                    return state
            
            # NEW: Try Truly Dynamic Odoo Agent (handles ANY query)
            try:
                from dynamic_odoo_agent import DynamicOdooAgent
                
                dynamic_agent = DynamicOdooAgent(current_odoo_client, gemini_client)
                dynamic_result = dynamic_agent.process_query(user_message)
                
                if dynamic_result.get('success'):
                    # Format response for user
                    formatted_response = dynamic_result.get('response', 'Query completed successfully')
                    
                    # Set successful state
                    state["data_lookup_result"] = {
                        "success": True,
                        "data": dynamic_result.get('data'),
                        "method": "dynamic_odoo_agent",
                        "api_call": dynamic_result.get('api_call'),
                        "attempts": dynamic_result.get('attempts', 1),
                        "response": formatted_response
                    }
                    state["response"] = formatted_response
                    state["current_step"] = "data_lookup_completed"
                    state["next_action"] = "generate_response"
                    
                    logger.info(f"Dynamic Odoo agent completed successfully in {dynamic_result.get('attempts', 1)} attempt(s)")
                    return state
                
                else:
                    # Dynamic agent failed, continue to legacy methods
                    logger.info(f"Dynamic Odoo agent failed: {dynamic_result.get('error')}")
                    logger.info("Falling back to Phase 1 proven methods")
                    
            except Exception as e:
                logger.warning(f"Dynamic Odoo agent error: {str(e)}")
                logger.info("Falling back to Phase 1 proven methods")
            
            # NEW: Try Dynamic Query Processing First (Multi-layer approach)
            try:
                from dynamic_query_processor import DynamicQueryProcessor
                
                dynamic_processor = DynamicQueryProcessor(current_odoo_client)
                dynamic_result = dynamic_processor.process_query(user_message)
                
                if dynamic_result.success:
                    # Format response for user
                    formatted_response = dynamic_processor.format_result_for_user(dynamic_result, user_message)
                    
                    # Set successful state
                    state["data_lookup_result"] = {
                        "success": True,
                        "data": dynamic_result.data,
                        "method": dynamic_result.method,
                        "execution_time": dynamic_result.execution_time,
                        "cached": dynamic_result.cached,
                        "response": formatted_response
                    }
                    state["response"] = formatted_response
                    state["current_step"] = "data_lookup_completed"
                    state["next_action"] = "generate_response"
                    
                    logger.info(f"Dynamic query completed successfully via {dynamic_result.method}")
                    return state
                
                else:
                    # Dynamic processing failed, continue to legacy methods
                    logger.info(f"Dynamic query processing failed: {dynamic_result.error}")
                    logger.info("Falling back to LLM-based query generation")
                    
            except Exception as e:
                logger.warning(f"Dynamic query processor error: {str(e)}")
                logger.info("Falling back to legacy LLM-based processing")
            
            # NEW: Try Phase 1 Proven Methods (83.3% success rate)
            try:
                from phase1_data_methods import Phase1DataMethods
                
                phase1_methods = Phase1DataMethods(current_odoo_client)
                phase1_result = phase1_methods.process_data_lookup(user_message)
                
                if phase1_result.get('success'):
                    # Format response for user
                    formatted_response = phase1_methods.format_result_for_agent(phase1_result, user_message)
                    
                    # Set successful state
                    state["data_lookup_result"] = {
                        "success": True,
                        "data": phase1_result,
                        "method": "phase1_proven",
                        "response": formatted_response
                    }
                    state["response"] = formatted_response
                    state["current_step"] = "data_lookup_completed"
                    state["next_action"] = "generate_response"
                    
                    logger.info(f"Phase 1 proven method completed successfully")
                    return state
                
                else:
                    # Phase 1 methods failed, continue to legacy
                    logger.info(f"Phase 1 proven methods failed: {phase1_result.get('error')}")
                    logger.info("Falling back to LLM-based query generation")
                    
            except Exception as e:
                logger.warning(f"Phase 1 proven methods error: {str(e)}")
                logger.info("Falling back to legacy LLM-based processing")
            
            # EXISTING: Check for fast-path intent and execute optimized query
            fast_path_intent = state.get("entities", {}).get("fast_path_intent")
            if fast_path_intent and config.agent.enable_fast_path:
                logger.info(f"Executing fast-path query for: {fast_path_intent}")
                result = self._execute_fast_path_query(fast_path_intent, current_odoo_client)
                if result and "error" not in result:
                    formatted_response = self._format_fast_path_response(fast_path_intent, result)
                    state["data_lookup_result"] = {
                        "success": True,
                        "data": result,
                        "fast_path": True,
                        "response": formatted_response
                    }
                    state["response"] = formatted_response
                    state["current_step"] = "data_lookup_completed"
                    state["next_action"] = "generate_response"
                    logger.info(f"Fast-path query completed successfully")
                    return state
            
            # Use LLM to analyze the query and generate API parameters
            api_params = self._generate_api_query(user_message)
            
            if not api_params or "error" in api_params:
                error_msg = api_params.get("error", "Could not understand the data request")
                StateManager.set_error(state, error_msg, "query_analysis_error")
                return state
            
            # Execute the Odoo API query with caching
            result = self._execute_odoo_query_with_cache(api_params, current_odoo_client)
            
            # Format the response conversationally
            formatted_response = self._format_conversational_response(user_message, api_params, result)
            
            state["data_lookup_result"] = {
                "success": True,
                "data": result,
                "api_params": api_params,
                "response": formatted_response
            }
            state["response"] = formatted_response
            state["current_step"] = "data_lookup_completed"
            state["next_action"] = "generate_response"
            
            logger.info(f"Data lookup completed successfully")
            
        except Exception as e:
            logger.error(f"Data lookup failed: {str(e)}")
            StateManager.set_error(state, f"Data lookup failed: {str(e)}", "data_lookup_error")
        
        return state
    
    def _generate_api_query(self, user_message: str) -> Dict[str, Any]:
        """Use LLM to analyze user query and generate Odoo API parameters"""
        try:
            # Create a prompt for the LLM to analyze the query
            prompt = f"""
Analyze this user query and generate Odoo API parameters to retrieve the requested data.

User Query: "{user_message}"

Available Odoo Models for Sales Module:
{json.dumps(self.sales_models, indent=2)}

Generate a JSON response with these fields:
{{
    "model": "odoo_model_name",
    "domain": [["field", "operator", "value"], ...],
    "fields": ["field1", "field2", ...],
    "limit": 50,
    "order": "field_name desc",
    "explanation": "Brief explanation of what data will be retrieved",
    "query_type": "search|count|aggregate",
    "user_intent": "Brief description of what user wants"
}}

Rules:
1. For stock/inventory queries, use 'stock.quant' model with fields like 'product_id', 'quantity', 'location_id'
2. For product queries, use 'product.product' or 'product.template'
3. For customer data, use 'res.partner' with domain [('customer_rank', '>', 0)]
4. For sales data, use 'sale.order' or 'sale.order.line'
5. For invoice data, use 'account.move' with appropriate move_type
6. For purchase orders, use 'purchase.order' model with fields like 'name', 'partner_id', 'date_order', 'amount_total', 'state', 'currency_id'
7. For purchase order lines, use 'purchase.order.line' model with fields like 'order_id', 'product_id', 'product_qty', 'price_unit', 'price_subtotal'
8. For employee expenses, use 'hr.expense' model with fields like 'name', 'employee_id', 'product_id', 'quantity', 'total_amount', 'date', 'state'
9. For expense reports/sheets, use 'hr.expense.sheet' model with fields like 'name', 'employee_id', 'total_amount', 'state', 'date'
10. For stock transfers/deliveries, use 'stock.picking' model with fields like 'name', 'partner_id', 'picking_type_id', 'state', 'date_done'
11. For employee data, use 'hr.employee' model with fields like 'name', 'work_email', 'work_phone', 'mobile_phone', 'job_title', 'department_id', 'parent_id', 'company_id'
12. For department data, use 'hr.department' model
13. Use appropriate operators: '=', '!=', '>', '<', '>=', '<=', 'like', 'ilike', 'in', 'not in'
14. Limit results to reasonable numbers (10-100)
15. Include relevant fields for the query
16. IMPORTANT: For hr.employee address queries, note that address fields are not available in this Odoo installation. Use only 'name' field and mark as address query for proper user messaging.
17. If query is unclear, return {{"error": "explanation"}}

Examples:
- "current stock for Acoustic Bloc Screens" → model: "stock.quant", domain: [["product_id.name", "ilike", "Acoustic Bloc Screens"]], fields: ["product_id", "quantity", "location_id"]
- "recent sales orders" → model: "sale.order", domain: [["state", "in", ["sale", "done"]]], order: "date_order desc"
- "customers from USA" → model: "res.partner", domain: [["customer_rank", ">", 0], ["country_id.code", "=", "US"]]
- "how many purchase orders do we have" → model: "purchase.order", domain: [], fields: ["name", "partner_id", "date_order", "amount_total", "state"], query_type: "count"
- "purchase orders from this month" → model: "purchase.order", domain: [["date_order", ">=", "2024-01-01"]], fields: ["name", "partner_id", "date_order", "amount_total", "state"]
- "pending purchase orders" → model: "purchase.order", domain: [["state", "in", ["draft", "sent", "to approve"]]], fields: ["name", "partner_id", "date_order", "amount_total", "state"]
- "employee expenses this month" → model: "hr.expense", domain: [["date", ">=", "2024-01-01"]], fields: ["name", "employee_id", "product_id", "total_amount", "date", "state"]
- "expense reports waiting approval" → model: "hr.expense.sheet", domain: [["state", "=", "submit"]], fields: ["name", "employee_id", "total_amount", "state", "date"]
- "employee details for John Smith" → model: "hr.employee", domain: [["name", "ilike", "John Smith"]], fields: ["name", "work_email", "work_phone", "mobile_phone", "job_title", "department_id", "parent_id", "company_id"]
- "address of employee John Smith" → model: "hr.employee", domain: [["name", "ilike", "John Smith"]], fields: ["name"]

Special handling for address queries:
- If user asks for employee address details (street, city, zip, etc.), use hr.employee model with address_home_id field only
- The system will explain that detailed address information requires separate access to the partner record

Return ONLY valid JSON:
"""
            
            response = gemini_client.generate_text(prompt)
            
            # Parse the JSON response using robust recovery engine
            try:
                # Handle None or empty response from Gemini API
                if response is None or (isinstance(response, str) and not response.strip()):
                    logger.warning("Gemini API returned None/empty response for data lookup query")
                    logger.info("Attempting keyword-based fallback for empty Gemini response")
                    
                    # Try keyword-based fallback immediately
                    fallback_params = self._create_keyword_based_fallback(user_message)
                    if fallback_params.get("model") and "error" not in fallback_params:
                        logger.info(f"Using keyword fallback due to empty Gemini response: {fallback_params.get('fallback_reason')}")
                        return fallback_params
                    else:
                        return {"error": "AI service returned empty response and could not infer query intent. Please try rephrasing your query more specifically."}
                
                # Use robust JSON recovery engine
                from json_recovery_utils import JSONRecoveryEngine
                recovery_engine = JSONRecoveryEngine(gemini_client)
                api_params = recovery_engine.extract_and_parse_json(response, "data_lookup")
                
                # Check if this is a fallback response with error
                if "error" in api_params and api_params.get("fallback"):
                    # If it's an intelligent fallback, try to proceed
                    if api_params.get("model") and "suggested_action" not in api_params:
                        logger.info(f"Using intelligent fallback: {api_params.get('fallback_reason', 'Unknown reason')}")
                        # Continue processing with the fallback params
                    else:
                        # If it's a basic error fallback, try keyword-based approach as last resort
                        logger.info("JSON recovery failed, trying keyword-based fallback")
                        fallback_params = self._create_keyword_based_fallback(user_message)
                        if fallback_params.get("model") and "error" not in fallback_params:
                            logger.info(f"Using keyword fallback after JSON recovery failed: {fallback_params.get('fallback_reason')}")
                            return fallback_params
                        else:
                            # If everything fails, return the error
                            return api_params
                
                # Validate required fields
                if "model" not in api_params or not api_params["model"]:
                    # Try one more fallback based on user message keywords
                    fallback_params = self._create_keyword_based_fallback(user_message)
                    if fallback_params.get("model"):
                        logger.info("Using keyword-based fallback for missing model")
                        api_params = fallback_params
                    else:
                        return {"error": "No model specified in API parameters and could not infer from query"}
                
                # Set defaults
                api_params.setdefault("domain", [])
                api_params.setdefault("fields", [])
                api_params.setdefault("limit", 50)
                api_params.setdefault("query_type", "search")
                
                # Validate and fix hr.employee address fields
                if api_params.get("model") == "hr.employee":
                    fields = api_params.get("fields", [])
                    # Remove any address-related fields as they don't exist in this Odoo installation
                    has_address_fields = any(field.startswith("address_home_id") for field in fields)
                    if has_address_fields:
                        # Filter out all address-related fields
                        api_params["fields"] = [field for field in fields if not field.startswith("address_home_id")]
                        # Ensure name is included for address queries
                        if "name" not in api_params["fields"]:
                            api_params["fields"].append("name")
                        # Mark this as an address query that needs special handling
                        api_params["is_address_query"] = True
                
                return api_params
                
            except Exception as parse_error:
                logger.error(f"JSON parsing failed: {parse_error}")
                logger.debug(f"Raw response that failed parsing: {response}")
                
                # If parsing fails completely, return an error
                return {
                    "error": f"Failed to parse LLM response: {str(parse_error)}",
                    "raw_response": response[:200] + "..." if len(response) > 200 else response,
                    "suggested_action": "Please try rephrasing your query more specifically"
                }
                
        except Exception as e:
            logger.error(f"Failed to generate API query: {str(e)}")
            return {"error": f"Failed to analyze query: {str(e)}"}
    
    def _create_keyword_based_fallback(self, user_message: str) -> Dict[str, Any]:
        """
        Create a fallback API params based on keywords in the user message.
        This is used when JSON parsing completely fails but we can infer intent.
        """
        message_lower = user_message.lower()
        
        # Invoice/Account related queries
        if any(word in message_lower for word in ['invoice', 'bill', 'payment', 'outstanding', 'due', 'overdue']):
            domain = []
            fields = ["name", "partner_id", "amount_total", "date", "state", "payment_state"]
            
            # Refine domain based on specific keywords
            if 'open' in message_lower or 'outstanding' in message_lower or 'unpaid' in message_lower:
                domain = [["state", "=", "posted"], ["payment_state", "!=", "paid"]]
            elif 'paid' in message_lower:
                domain = [["state", "=", "posted"], ["payment_state", "=", "paid"]]
            elif 'draft' in message_lower:
                domain = [["state", "=", "draft"]]
            
            # Customer-specific filters
            if 'customer' in message_lower or 'client' in message_lower:
                domain.append(["move_type", "=", "out_invoice"])
            elif 'vendor' in message_lower or 'supplier' in message_lower:
                domain.append(["move_type", "=", "in_invoice"])
                
            return {
                "model": "account.move",
                "domain": domain,
                "fields": fields,
                "limit": 50,
                "query_type": "search",
                "fallback": True,
                "fallback_reason": "Keyword-based fallback for invoice/payment queries"
            }
        
        # Customer/Partner related queries
        elif any(word in message_lower for word in ['customer', 'client', 'partner', 'contact']):
            domain = [["customer_rank", ">", 0]]
            fields = ["name", "email", "phone", "city", "country_id", "category_id"]
            
            return {
                "model": "res.partner",
                "domain": domain,
                "fields": fields,
                "limit": 50,
                "query_type": "search",
                "fallback": True,
                "fallback_reason": "Keyword-based fallback for customer queries"
            }
        
        # Product related queries
        elif any(word in message_lower for word in ['product', 'item', 'stock', 'inventory']):
            domain = [["sale_ok", "=", True]]
            fields = ["name", "list_price", "categ_id", "qty_available", "default_code"]
            
            return {
                "model": "product.template",
                "domain": domain,
                "fields": fields,
                "limit": 50,
                "query_type": "search",
                "fallback": True,
                "fallback_reason": "Keyword-based fallback for product queries"
            }
        
        # Sales Order related queries
        elif any(word in message_lower for word in ['sale', 'order', 'quotation', 'quote']):
            domain = []
            fields = ["name", "partner_id", "amount_total", "date_order", "state"]
            
            if 'draft' in message_lower or 'quotation' in message_lower:
                domain = [["state", "in", ["draft", "sent"]]]
            elif 'confirmed' in message_lower or 'confirmed' in message_lower:
                domain = [["state", "=", "sale"]]
                
            return {
                "model": "sale.order",
                "domain": domain,
                "fields": fields,
                "limit": 50,
                "query_type": "search",
                "fallback": True,
                "fallback_reason": "Keyword-based fallback for sales order queries"
            }
        
        # Lead/CRM related queries
        elif any(word in message_lower for word in ['lead', 'opportunity', 'prospect', 'crm']):
            domain = []
            fields = ["name", "partner_id", "email_from", "phone", "stage_id", "expected_revenue"]
            
            return {
                "model": "crm.lead",
                "domain": domain,
                "fields": fields,
                "limit": 50,
                "query_type": "search",
                "fallback": True,
                "fallback_reason": "Keyword-based fallback for CRM queries"
            }
        
        # Employee related queries
        elif any(word in message_lower for word in ['employee', 'staff', 'worker', 'team member']):
            domain = []
            fields = ["name", "work_email", "work_phone", "department_id", "job_id"]
            
            return {
                "model": "hr.employee",
                "domain": domain,
                "fields": fields,
                "limit": 50,
                "query_type": "search",
                "fallback": True,
                "fallback_reason": "Keyword-based fallback for employee queries"
            }
        
        # No keywords matched
        return {
            "error": "Could not infer query type from message",
            "fallback": True,
            "suggested_action": "Please be more specific about what you're looking for (e.g., 'invoices', 'customers', 'products')"
        }
    
    def _execute_fast_path_query(self, fast_path_intent: str, client=None) -> Dict[str, Any]:
        """Execute optimized fast-path queries without LLM analysis"""
        try:
            odoo_client_to_use = client or odoo_client
            query_config = fast_path_router.get_fast_query_config(fast_path_intent)
            
            if not query_config:
                return {"error": f"No fast-path configuration for: {fast_path_intent}"}
            
            model = query_config["model"]
            domain = query_config["domain"]
            fields = query_config["fields"]
            method = query_config["method"]
            
            logger.info(f"Fast-path query: {method} on {model} with domain {domain}")
            
            # Check cache first
            if config.agent.cache_query_results:
                cached_result = query_cache.get(
                    model=model,
                    method=method,
                    domain=domain,
                    fields=fields,
                    limit=query_config.get("limit"),
                    order=query_config.get("order")
                )
                if cached_result:
                    logger.info(f"Cache hit for fast-path query: {fast_path_intent}")
                    return cached_result
            
            # Execute query
            if method == "search_count":
                count = odoo_client_to_use.search_count(model, domain)
                result = {"type": "count", "count": count, "model": model}
            elif method == "search_read":
                limit = query_config.get("limit", 50)
                records = odoo_client_to_use.search_read(model, domain, fields, limit=limit)
                result = {
                    "type": "records",
                    "records": records,
                    "count": len(records),
                    "model": model,
                    "fields": fields
                }
            else:
                return {"error": f"Unsupported fast-path method: {method}"}
            
            # Cache the result
            if config.agent.cache_query_results:
                query_cache.set(
                    model=model,
                    method=method,
                    domain=domain,
                    fields=fields,
                    result=result,
                    ttl=300,  # 5 minutes cache
                    limit=query_config.get("limit"),
                    order=query_config.get("order")
                )
            
            return result
            
        except Exception as e:
            logger.error(f"Fast-path query execution failed: {str(e)}")
            return {"error": f"Fast-path query failed: {str(e)}"}
    
    def _format_fast_path_response(self, fast_path_intent: str, result: Dict[str, Any]) -> str:
        """Format fast-path query results using templates"""
        try:
            query_config = fast_path_router.get_fast_query_config(fast_path_intent)
            if not query_config:
                return "✅ Query completed successfully."
            
            template = query_config.get("response_template", "Found {count} results.")
            
            if result["type"] == "count":
                return template.format(count=result["count"])
            elif result["type"] == "records":
                records = result["records"]
                count = result["count"]
                
                if "formatted_results" in template:
                    # Format records for display
                    formatted_results = self._format_records_for_template(records, result["model"])
                    return template.format(count=count, formatted_results=formatted_results)
                else:
                    return template.format(count=count)
            
            return "✅ Query completed successfully."
            
        except Exception as e:
            logger.error(f"Fast-path response formatting failed: {str(e)}")
            return f"Found results but couldn't format them properly: {str(e)}"
    
    def _format_records_for_template(self, records: List[Dict], model: str) -> str:
        """Format records for template display"""
        if not records:
            return "No records found."
        
        formatted = []
        for i, record in enumerate(records[:5]):  # Limit to 5 records
            if model == "sale.order":
                name = record.get("name", "Unknown")
                partner = record.get("partner_id", [None, "Unknown Customer"])
                partner_name = partner[1] if isinstance(partner, list) else str(partner)
                amount = record.get("amount_total", 0)
                formatted.append(f"{i+1}. {name} - {partner_name} (${amount:,.2f})")
            elif model == "account.move":
                name = record.get("name", "Unknown")
                partner = record.get("partner_id", [None, "Unknown Customer"])
                partner_name = partner[1] if isinstance(partner, list) else str(partner)
                amount = record.get("amount_total", 0)
                formatted.append(f"{i+1}. {name} - {partner_name} (${amount:,.2f})")
            else:
                # Generic formatting
                name = record.get("name", f"Record {record.get('id', i+1)}")
                formatted.append(f"{i+1}. {name}")
        
        return "\n".join(formatted)
    
    def _execute_odoo_query_with_cache(self, api_params: Dict[str, Any], client=None) -> Dict[str, Any]:
        """Execute Odoo query with caching support"""
        try:
            model = api_params["model"]
            domain = api_params.get("domain", [])
            fields = api_params.get("fields", [])
            limit = api_params.get("limit", 50)
            order = api_params.get("order", "")
            query_type = api_params.get("query_type", "search")
            
            # Check cache first
            if config.agent.cache_query_results:
                cached_result = query_cache.get(
                    model=model,
                    method=query_type,
                    domain=domain,
                    fields=fields,
                    limit=limit,
                    order=order
                )
                if cached_result:
                    logger.info(f"Cache hit for query: {model} with domain {domain}")
                    return cached_result
            
            # Execute query using original method
            result = self._execute_odoo_query(api_params, client)
            
            # Cache successful results
            if config.agent.cache_query_results and "error" not in result:
                query_cache.set(
                    model=model,
                    method=query_type,
                    domain=domain,
                    fields=fields,
                    result=result,
                    ttl=300,  # 5 minutes cache
                    limit=limit,
                    order=order
                )
                logger.info(f"Cached query result for: {model}")
            
            return result
            
        except Exception as e:
            logger.error(f"Cached query execution failed: {str(e)}")
            return {"error": f"Query execution failed: {str(e)}"}
    
    def _execute_odoo_query(self, api_params: Dict[str, Any], client=None) -> Dict[str, Any]:
        """Execute the Odoo API query"""
        try:
            # Use provided client or fall back to global odoo_client
            odoo_client_to_use = client or odoo_client
            
            model = api_params["model"]
            domain = api_params.get("domain", [])
            fields = api_params.get("fields", [])
            limit = api_params.get("limit", 50)
            order = api_params.get("order", "")
            query_type = api_params.get("query_type", "search")
            
            logger.info(f"Executing Odoo query: model={model}, domain={domain}, fields={fields}")
            
            if query_type == "count":
                # Just count records
                count = odoo_client_to_use.search_count(model, domain)
                return {
                    "type": "count",
                    "count": count,
                    "model": model
                }
            
            elif query_type == "search":
                # Search and read records
                # Note: OdooClient.search_read doesn't support 'order' parameter
                records = odoo_client_to_use.search_read(model, domain, fields, limit=limit)
                
                return {
                    "type": "records",
                    "records": records,
                    "count": len(records),
                    "model": model,
                    "fields": fields
                }
            
            else:
                return {"error": f"Unsupported query type: {query_type}"}
                
        except Exception as e:
            logger.error(f"Odoo query execution failed: {str(e)}")
            # Provide user-friendly error message instead of technical details
            if "Invalid field" in str(e):
                return {"error": "The requested information is not available in the current system configuration."}
            elif "Access Denied" in str(e) or "AccessError" in str(e):
                return {"error": "You don't have permission to access this information."}
            elif "Connection" in str(e) or "timeout" in str(e).lower():
                return {"error": "Unable to connect to the system. Please try again later."}
            else:
                return {"error": "Unable to retrieve the requested information. Please try a different query."}
    
    def _format_conversational_response(self, user_message: str, api_params: Dict[str, Any], result: Dict[str, Any]) -> str:
        """Format the query results in a conversational manner"""
        try:
            if "error" in result:
                return f"❌ I couldn't retrieve the data: {result['error']}"
            
            model = api_params.get("model", "")
            explanation = api_params.get("explanation", "")
            user_intent = api_params.get("user_intent", "")
            
            if result["type"] == "count":
                count = result["count"]
                model_name = self.sales_models.get(model, model)
                return f"📊 I found **{count}** {model_name.lower()} matching your query.\n\n{explanation}"
            
            elif result["type"] == "records":
                records = result["records"]
                count = result["count"]
                model_name = self.sales_models.get(model, model)
                
                if count == 0:
                    return f"🔍 I didn't find any {model_name.lower()} matching your criteria.\n\n{explanation}"
                
                # Format the response based on the model type
                if model == "stock.quant":
                    return self._format_stock_response(records, count, user_message)
                elif model in ["product.product", "product.template"]:
                    return self._format_product_response(records, count, user_message)
                elif model == "sale.order":
                    return self._format_sales_order_response(records, count, user_message)
                elif model == "purchase.order":
                    return self._format_purchase_order_response(records, count, user_message)
                elif model == "hr.expense":
                    return self._format_expense_response(records, count, user_message)
                elif model == "hr.expense.sheet":
                    return self._format_expense_sheet_response(records, count, user_message)
                elif model == "stock.picking":
                    return self._format_stock_picking_response(records, count, user_message)
                elif model == "res.partner":
                    return self._format_partner_response(records, count, user_message)
                elif model == "account.move":
                    return self._format_invoice_response(records, count, user_message)
                elif model == "hr.employee":
                    return self._format_employee_response(records, count, user_message, api_params)
                else:
                    return self._format_generic_response(records, count, model_name, user_message)
            
            return "✅ Query completed successfully."
            
        except Exception as e:
            logger.error(f"Response formatting failed: {str(e)}")
            return f"✅ I found the data, but had trouble formatting it: {str(e)}"
    
    def _format_stock_response(self, records: List[Dict], count: int, user_message: str) -> str:
        """Format stock/inventory data response"""
        if not records:
            return "📦 No stock information found for the requested items."
        
        response = f"📦 **Stock Information** ({count} items found)\n\n"
        
        for record in records[:10]:  # Show max 10 items
            product_name = "Unknown Product"
            if record.get("product_id"):
                if isinstance(record["product_id"], list) and len(record["product_id"]) > 1:
                    product_name = record["product_id"][1]
                else:
                    product_name = str(record["product_id"])
            
            quantity = record.get("quantity", 0)
            location = "Unknown Location"
            if record.get("location_id"):
                if isinstance(record["location_id"], list) and len(record["location_id"]) > 1:
                    location = record["location_id"][1]
                else:
                    location = str(record["location_id"])
            
            response += f"• **{product_name}**: {quantity} units in {location}\n"
        
        if count > 10:
            response += f"\n... and {count - 10} more items."
        
        return response
    
    def _format_product_response(self, records: List[Dict], count: int, user_message: str) -> str:
        """Format product data response"""
        response = f"🛍️ **Products** ({count} found)\n\n"
        
        for record in records[:10]:
            name = record.get("name", "Unknown Product")
            price = record.get("list_price", 0)
            qty_available = record.get("qty_available", "N/A")
            
            response += f"• **{name}**\n"
            response += f"  Price: ${price:.2f}\n"
            if qty_available != "N/A":
                response += f"  Stock: {qty_available} units\n"
            response += "\n"
        
        if count > 10:
            response += f"... and {count - 10} more products."
        
        return response
    
    def _format_sales_order_response(self, records: List[Dict], count: int, user_message: str) -> str:
        """Format sales order data response"""
        response = f"📋 **Sales Orders** ({count} found)\n\n"
        
        total_amount = 0
        for record in records[:10]:
            name = record.get("name", "Unknown Order")
            partner_name = "Unknown Customer"
            if record.get("partner_id") and isinstance(record["partner_id"], list):
                partner_name = record["partner_id"][1]
            
            amount = record.get("amount_total", 0)
            total_amount += amount
            state = record.get("state", "unknown")
            date_order = record.get("date_order", "")
            
            response += f"• **{name}** - {partner_name}\n"
            response += f"  Amount: ${amount:,.2f} | Status: {state}\n"
            if date_order:
                response += f"  Date: {date_order}\n"
            response += "\n"
        
        if count > 0:
            avg_amount = total_amount / min(count, 10)
            response += f"\n💰 **Summary**: Total shown: ${total_amount:,.2f} | Average: ${avg_amount:,.2f}"
        
        if count > 10:
            response += f"\n... and {count - 10} more orders."
        
        return response
    
    def _format_partner_response(self, records: List[Dict], count: int, user_message: str) -> str:
        """Format partner/customer data response"""
        response = f"👥 **Customers/Partners** ({count} found)\n\n"
        
        for record in records[:10]:
            name = record.get("name", "Unknown")
            email = record.get("email", "No email")
            phone = record.get("phone", "No phone")
            country = "Unknown Country"
            if record.get("country_id") and isinstance(record["country_id"], list):
                country = record["country_id"][1]
            
            response += f"• **{name}**\n"
            response += f"  Email: {email} | Phone: {phone}\n"
            response += f"  Country: {country}\n\n"
        
        if count > 10:
            response += f"... and {count - 10} more customers."
        
        return response
    
    def _format_invoice_response(self, records: List[Dict], count: int, user_message: str) -> str:
        """Format invoice data response"""
        response = f"🧾 **Invoices** ({count} found)\n\n"
        
        total_amount = 0
        for record in records[:10]:
            name = record.get("name", "Unknown Invoice")
            partner_name = "Unknown Partner"
            if record.get("partner_id") and isinstance(record["partner_id"], list):
                partner_name = record["partner_id"][1]
            
            amount = record.get("amount_total", 0)
            total_amount += amount
            state = record.get("state", "unknown")
            invoice_date = record.get("invoice_date", "")
            
            response += f"• **{name}** - {partner_name}\n"
            response += f"  Amount: ${amount:,.2f} | Status: {state}\n"
            if invoice_date:
                response += f"  Date: {invoice_date}\n"
            response += "\n"
        
        if count > 0:
            response += f"\n💰 **Total Amount**: ${total_amount:,.2f}"
        
        if count > 10:
            response += f"\n... and {count - 10} more invoices."
        
        return response
    
    def _format_employee_response(self, records: List[Dict], count: int, user_message: str, api_params: Dict = None) -> str:
        """Format employee data response"""
        if not records:
            return "👤 No employee information found for the requested person."
        
        # Check if this is an address-specific query
        is_address_query = any(word in user_message.lower() for word in ['address', 'street', 'city', 'zip', 'location', 'home'])
        # Also check if this was flagged as an address query that had fields removed
        is_filtered_address_query = api_params and api_params.get('is_address_query', False)
        
        response = f"👤 **Employee Information** ({count} found)\n\n"
        
        for record in records[:10]:
            name = record.get("name", "Unknown Employee")
            
            if is_address_query or is_filtered_address_query:
                # For address queries, focus on address information
                response += f"• **{name}**\n"
                
                if is_filtered_address_query:
                    # Address fields were filtered out because they don't exist in this system
                    response += f"  🏠 **Address Information**: Not available\n"
                    response += f"  ℹ️ **Note**: Employee address fields are not configured in this Odoo installation.\n\n"
                else:
                    # Handle address_home_id (Many2one field) - legacy handling
                    if record.get("address_home_id"):
                        if isinstance(record["address_home_id"], list) and len(record["address_home_id"]) > 1:
                            response += f"  🏠 Home Address Contact: {record['address_home_id'][1]}\n"
                            response += f"  📋 Address Record ID: {record['address_home_id'][0]}\n"
                        else:
                            response += f"  🏠 Address Record ID: {record['address_home_id']}\n"
                        
                        response += f"\n  ℹ️ **Note**: Detailed address information (street, city, zip code) is stored in a separate partner record and requires additional access permissions to view the complete address details.\n\n"
                    else:
                        response += f"  🏠 No home address information on file\n\n"
            else:
                # For general employee queries, show all available information
                work_email = record.get("work_email", "No work email")
                work_phone = record.get("work_phone", "No work phone")
                mobile_phone = record.get("mobile_phone", "No mobile phone")
                
                # Handle job_title (string field)
                job_title = record.get("job_title", "No job title")
                
                # Handle department_id (Many2one field)
                department = "No department"
                if record.get("department_id"):
                    if isinstance(record["department_id"], list) and len(record["department_id"]) > 1:
                        department = record["department_id"][1]
                    else:
                        department = str(record["department_id"])
                
                # Handle parent_id (Many2one field for manager)
                manager = "No manager"
                if record.get("parent_id"):
                    if isinstance(record["parent_id"], list) and len(record["parent_id"]) > 1:
                        manager = record["parent_id"][1]
                    else:
                        manager = str(record["parent_id"])
                
                # Handle company_id (Many2one field)
                company = "No company"
                if record.get("company_id"):
                    if isinstance(record["company_id"], list) and len(record["company_id"]) > 1:
                        company = record["company_id"][1]
                    else:
                        company = str(record["company_id"])
                
                # Handle address_home_id (Many2one field)
                address_info = "No home address on file"
                if record.get("address_home_id"):
                    if isinstance(record["address_home_id"], list) and len(record["address_home_id"]) > 1:
                        address_info = f"Home address contact: {record['address_home_id'][1]} (ID: {record['address_home_id'][0]})"
                    else:
                        address_info = f"Home address ID: {record['address_home_id']}"
                
                response += f"• **{name}**\n"
                response += f"  📧 Work Email: {work_email}\n"
                response += f"  📞 Work Phone: {work_phone}\n"
                response += f"  📱 Mobile Phone: {mobile_phone}\n"
                response += f"  💼 Job Title: {job_title}\n"
                response += f"  🏢 Department: {department}\n"
                response += f"  👤 Manager: {manager}\n"
                response += f"  🏛️ Company: {company}\n"
                response += f"  🏠 Address: {address_info}\n\n"
        
        if count > 10:
            response += f"... and {count - 10} more employees."
        
        return response
    
    def _format_generic_response(self, records: List[Dict], count: int, model_name: str, user_message: str) -> str:
        """Format generic data response"""
        response = f"📊 **{model_name}** ({count} found)\n\n"
        
        for record in records[:5]:  # Show fewer for generic
            # Try to find a name field
            name = record.get("name") or record.get("display_name") or f"Record {record.get('id', 'Unknown')}"
            response += f"• {name}\n"
            
            # Show a few key fields
            for key, value in list(record.items())[:3]:
                if key not in ['id', 'name', 'display_name'] and value:
                    response += f"  {key}: {value}\n"
            response += "\n"
        
        if count > 5:
            response += f"... and {count - 5} more records."
        
        return response

    def _format_purchase_order_response(self, records: List[Dict], count: int, user_message: str) -> str:
        """Format purchase order data response"""
        response = f"🛒 **Purchase Orders** ({count} found)\n\n"
        
        total_amount = 0
        for record in records[:10]:
            name = record.get("name", "Unknown Order")
            partner_name = "Unknown Vendor"
            if record.get("partner_id") and isinstance(record["partner_id"], list):
                partner_name = record["partner_id"][1]
            
            amount = record.get("amount_total", 0)
            total_amount += amount
            state = record.get("state", "unknown")
            date_order = record.get("date_order", "")
            
            response += f"• **{name}** - {partner_name}\n"
            response += f"  Amount: ${amount:,.2f} | Status: {state}\n"
            if date_order:
                response += f"  Date: {date_order}\n"
            response += "\n"
        
        if count > 0:
            avg_amount = total_amount / min(count, 10)
            response += f"\n💰 **Summary**: Total shown: ${total_amount:,.2f} | Average: ${avg_amount:,.2f}"
        
        if count > 10:
            response += f"\n... and {count - 10} more orders."
        
        return response

    def _format_expense_response(self, records: List[Dict], count: int, user_message: str) -> str:
        """Format employee expense data response"""
        response = f"💳 **Employee Expenses** ({count} found)\n\n"
        
        total_amount = 0
        for record in records[:10]:
            name = record.get("name", "Unknown Expense")
            employee_name = "Unknown Employee"
            if record.get("employee_id") and isinstance(record["employee_id"], list):
                employee_name = record["employee_id"][1]
            
            amount = record.get("total_amount", 0)
            total_amount += amount
            state = record.get("state", "unknown")
            date = record.get("date", "")
            
            response += f"• **{name}** - {employee_name}\n"
            response += f"  Amount: ${amount:,.2f} | Status: {state}\n"
            if date:
                response += f"  Date: {date}\n"
            response += "\n"
        
        if count > 0:
            response += f"\n💰 **Total Amount**: ${total_amount:,.2f}"
        
        if count > 10:
            response += f"\n... and {count - 10} more expenses."
        
        return response

    def _format_expense_sheet_response(self, records: List[Dict], count: int, user_message: str) -> str:
        """Format expense sheet/report data response"""
        response = f"📋 **Expense Reports** ({count} found)\n\n"
        
        total_amount = 0
        for record in records[:10]:
            name = record.get("name", "Unknown Report")
            employee_name = "Unknown Employee"
            if record.get("employee_id") and isinstance(record["employee_id"], list):
                employee_name = record["employee_id"][1]
            
            amount = record.get("total_amount", 0)
            total_amount += amount
            state = record.get("state", "unknown")
            date = record.get("date", "")
            
            response += f"• **{name}** - {employee_name}\n"
            response += f"  Amount: ${amount:,.2f} | Status: {state}\n"
            if date:
                response += f"  Date: {date}\n"
            response += "\n"
        
        if count > 0:
            response += f"\n💰 **Total Amount**: ${total_amount:,.2f}"
        
        if count > 10:
            response += f"\n... and {count - 10} more reports."
        
        return response

    def _format_stock_picking_response(self, records: List[Dict], count: int, user_message: str) -> str:
        """Format stock picking/transfer data response"""
        response = f"📦 **Stock Transfers** ({count} found)\n\n"
        
        for record in records[:10]:
            name = record.get("name", "Unknown Transfer")
            partner_name = "Internal Transfer"
            if record.get("partner_id") and isinstance(record["partner_id"], list):
                partner_name = record["partner_id"][1]
            
            state = record.get("state", "unknown")
            date_done = record.get("date_done", "")
            picking_type = "Unknown Type"
            if record.get("picking_type_id") and isinstance(record["picking_type_id"], list):
                picking_type = record["picking_type_id"][1]
            
            response += f"• **{name}** - {partner_name}\n"
            response += f"  Type: {picking_type} | Status: {state}\n"
            if date_done:
                response += f"  Completed: {date_done}\n"
            response += "\n"
        
        if count > 10:
            response += f"... and {count - 10} more transfers."
        
        return response

class ResponseGenerationNode:
    """Node for generating final responses"""
    
    def process(self, state: AgentState) -> AgentState:
        """Generate final response based on processing results"""
        try:
            # Safety check for state
            if state is None:
                logger.error("ResponseGenerationNode: state is None")
                return StateManager.create_initial_state("Error: Invalid state", "unknown", None)
            
            if state.get("error_state"):
                state["response"] = self._generate_error_response(state)
                state["response_type"] = "error"
            elif state.get("response"):  # Already has response from Q&A
                pass  # Keep existing response
            else:
                state["response"] = self._generate_success_response(state)
                state["response_type"] = "data"
            
            state["current_step"] = "completed"
            
            # Add to conversation memory
            self._update_conversation_memory(state)
            
        except Exception as e:
            logger.error(f"Response generation failed: {str(e)}")
            import traceback
            logger.error(f"Full traceback: {traceback.format_exc()}")
            state["response"] = f"I apologize, but I encountered an error while generating the response: {str(e)}"
            state["response_type"] = "error"
        
        return state
    
    def _generate_error_response(self, state: AgentState) -> str:
        """Generate user-friendly error response"""
        error = state.get("error_state", "Unknown error")
        intent = state.get("intent", "unknown")
        
        if "connection" in error.lower():
            return "I'm having trouble connecting to the system. Please check your connection and try again."
        elif "authentication" in error.lower():
            return "There seems to be an authentication issue. Please verify your credentials."
        elif "extraction" in error.lower():
            return "I had trouble reading the document. Please ensure the image is clear and try again."
        else:
            return f"I encountered an issue while processing your request: {error}. Please try again or rephrase your request."
    
    def _generate_success_response(self, state: AgentState) -> str:
        """Generate success response based on results"""
        if state is None:
            return "I encountered an error while generating the response. Please try again."
        
        intent = state.get("intent")
        odoo_result = state.get("odoo_result", {})
        try:
            user_message = StateManager.get_last_user_message(state)
        except Exception as e:
            logger.warning(f"Could not extract user message for response generation: {e}")
            user_message = ""
        
        # Handle document processing results
        if intent == "document_processing":
            # Check if odoo_result is None or empty
            if odoo_result is None:
                return "📄 I understand you want to process a document. Please upload a file (invoice, receipt, business card, etc.) and I'll help you extract the data and create the appropriate records in Odoo."
            elif odoo_result.get("success"):
                data = odoo_result.get("data", {})
                if data.get("type") == "vendor_bill":
                    return f"✅ Successfully created vendor bill for {data.get('vendor_name')} with reference {data.get('reference')}. Amount: ${data.get('amount', 0)}"
                elif data.get("type") == "contact_created":
                    return f"✅ Successfully created contact: {data.get('name')} from {data.get('company', 'Unknown Company')}"
                elif data.get("type") == "contact_exists":
                    return f"ℹ️ Contact {data.get('name')} already exists in the system."
                elif data.get("type") == "expense_data":
                    return f"✅ Extracted expense data: {data.get('merchant')} - ${data.get('amount')} on {data.get('date')}. Please create the expense record manually."
            else:
                # Document processing failed
                error = odoo_result.get("error", "Unknown error") if odoo_result else "No file uploaded"
                return f"📄 I couldn't process the document: {error}. Please upload a clear image or PDF file and try again."
        
        # Handle reporting results
        elif intent == "reporting":
            if odoo_result and odoo_result.get("success"):
                data = odoo_result.get("data", {})
                if data.get("type") == "sales_orders_report":
                    return f"📊 **Sales Orders Report**\n\n{data.get('message')}\n\nRecent orders: {self._format_orders_list(data.get('orders', []))}"
                elif data.get("type") == "invoices_report":
                    return f"📊 **Invoices Report**\n\n{data.get('message')}\n\nRecent invoices: {self._format_invoices_list(data.get('invoices', []))}"
                elif data.get("type") == "customers_report":
                    return f"📊 **Customers Report**\n\n{data.get('message')}\n\nSample customers: {self._format_customers_list(data.get('customers', []))}"
                elif data.get("type") == "products_report":
                    return f"📊 **Products Report**\n\n{data.get('message')}\n\nSample products: {self._format_products_list(data.get('products', []))}"
                elif data.get("type") == "report_info":
                    return data.get("message", "I can help you with various reports.")
            else:
                error = odoo_result.get("error", "Unknown error") if odoo_result else "No result available"
                return f"❌ I couldn't generate the report: {error}. Please check your Odoo connection and try again."
        
        # Handle general help
        elif intent == "general_help":
            return self._generate_general_help_response(user_message)
        
        # Handle data entry results
        elif intent == "data_entry":
            if odoo_result and odoo_result.get("success"):
                return "✅ Data entry completed successfully!"
            else:
                error = odoo_result.get("error", "Unknown error") if odoo_result else "No result available"
                return f"❌ Data entry failed: {error}. Please try again or provide more details."
        
        # Default fallback
        return "I've processed your request. Is there anything else I can help you with?"
    
    def _format_orders_list(self, orders: list) -> str:
        """Format sales orders for display"""
        if not orders:
            return "None found"
        
        formatted = []
        for order in orders[:5]:  # Show max 5
            customer = order.get('partner_id', ['', 'Unknown'])[1] if order.get('partner_id') else 'Unknown'
            amount = order.get('amount_total', 0)
            formatted.append(f"• {order.get('name', 'N/A')} - {customer} (${amount:,.2f})")
        
        return "\n".join(formatted)
    
    def _format_invoices_list(self, invoices: list) -> str:
        """Format invoices for display"""
        if not invoices:
            return "None found"
        
        formatted = []
        for invoice in invoices[:5]:  # Show max 5
            customer = invoice.get('partner_id', ['', 'Unknown'])[1] if invoice.get('partner_id') else 'Unknown'
            amount = invoice.get('amount_total', 0)
            formatted.append(f"• {invoice.get('name', 'N/A')} - {customer} (${amount:,.2f})")
        
        return "\n".join(formatted)
    
    def _format_customers_list(self, customers: list) -> str:
        """Format customers for display"""
        if not customers:
            return "None found"
        
        formatted = []
        for customer in customers[:5]:  # Show max 5
            email = customer.get('email', 'No email')
            formatted.append(f"• {customer.get('name', 'N/A')} - {email}")
        
        return "\n".join(formatted)
    
    def _format_products_list(self, products: list) -> str:
        """Format products for display"""
        if not products:
            return "None found"
        
        formatted = []
        for product in products[:5]:  # Show max 5
            price = product.get('list_price', 0)
            qty = product.get('qty_available', 0)
            formatted.append(f"• {product.get('name', 'N/A')} - ${price:.2f} (Stock: {qty})")
        
        return "\n".join(formatted)
    
    def _generate_general_help_response(self, user_message: str) -> str:
        """Generate contextual help response"""
        message_lower = user_message.lower()
        
        # Greeting responses
        if any(greeting in message_lower for greeting in ['hello', 'hi', 'hey', 'good morning', 'good afternoon']):
            return "👋 Hello! I'm your Odoo AI Assistant. I can help you with:\n\n• 📊 **Reports** - Sales orders, invoices, customers, products\n• 📄 **Document Processing** - Upload invoices, business cards, receipts\n• 💬 **Q&A** - Ask questions about Odoo functionality\n• ✏️ **Data Entry** - Create and update records\n\nWhat would you like to do today?"
        
        # How are you responses
        elif any(phrase in message_lower for phrase in ['how are you', 'how do you do', 'what\'s up']):
            return "I'm doing great, thank you for asking! 😊 I'm here and ready to help you with your Odoo tasks. Whether you need reports, want to process documents, or have questions about Odoo functionality, I'm at your service. What can I help you with?"
        
        # General help
        else:
            return "I'm here to help! I can assist you with:\n\n🔍 **Ask me questions** like:\n  • \"How many sales orders do we have?\"\n  • \"Show me recent invoices\"\n  • \"How do I create a customer?\"\n\n📄 **Upload documents** for processing:\n  • Invoices → Vendor bills\n  • Business cards → Contacts\n  • Receipts → Expense data\n\n💡 **Try commands** like:\n  • \"Show me customers\"\n  • \"Generate sales report\"\n  • \"Help with inventory\"\n\nWhat would you like to do?"
    
    def _update_conversation_memory(self, state: AgentState) -> None:
        """Update conversation memory with current exchange"""
        if state is None:
            logger.warning("Cannot update conversation memory: state is None")
            return
        
        try:
            user_message = StateManager.get_last_user_message(state)
        except Exception as e:
            logger.warning(f"Could not extract user message for conversation memory: {e}")
            user_message = ""
        
        response = state.get("response", "")
        intent = state.get("intent", "unknown")
        
        memory_entry = {
            "user_message": user_message,
            "assistant_response": response,
            "intent": intent,
            "timestamp": datetime.now().isoformat(),
            "confidence": state.get("confidence", 0.0)
        }
        
        if "conversation_memory" not in state:
            state["conversation_memory"] = []
        
        state["conversation_memory"].append(memory_entry)
        
        # Keep only recent entries
        max_memory = config.agent.max_conversation_history
        if len(state["conversation_memory"]) > max_memory:
            state["conversation_memory"] = state["conversation_memory"][-max_memory:]


class NavigationNode:
    """Node for handling direct navigation requests"""
    
    @performance_tracker("navigation", performance_monitor)
    def process(self, state: AgentState) -> AgentState:
        """Process navigation requests and provide direct shortcuts"""
        try:
            if state is None:
                logger.error("Navigation processing failed: state is None")
                return state
            
            try:
                user_message = StateManager.get_last_user_message(state)
            except Exception as e:
                logger.warning(f"Could not extract user message for navigation: {e}")
                user_message = ""
            
            logger.info(f"Processing navigation request: {user_message[:100]}...")
            
            # Get Odoo base URL for navigation links
            session_id = state.get("session_id")
            odoo_base_url = self._get_odoo_base_url_from_session(state, session_id)
            
            # Handle the navigation request
            is_navigation, response = navigation_handler.handle_navigation_request(
                user_message, odoo_base_url
            )
            
            if is_navigation and response:
                state["response"] = response
                state["response_type"] = "navigation"
                state["current_step"] = "navigation_completed"
                state["next_action"] = "generate_response"
                logger.info(f"Navigation request processed successfully")
            else:
                # Fallback if navigation handler fails
                state["response"] = "I understand you want to navigate somewhere in Odoo. Please provide more specific details about where you'd like to go."
                state["response_type"] = "text"
                state["current_step"] = "navigation_completed"
                state["next_action"] = "generate_response"
                logger.warning(f"Navigation request could not be processed")
            
        except Exception as e:
            logger.error(f"Navigation processing failed: {str(e)}")
            StateManager.set_error(state, f"Navigation processing failed: {str(e)}", "navigation_error")
        
        return state
    
    def _get_odoo_base_url_from_session(self, state: AgentState, session_id: str) -> Optional[str]:
        """Get Odoo base URL from session or config for navigation links"""
        try:
            # First try to get from session-specific client
            if session_id:
                try:
                    from services.agent_service import agent_service
                    session_client = agent_service.get_odoo_client_for_session(session_id)
                    if session_client and session_client.url:
                        logger.info(f"Using session-specific Odoo URL: {session_client.url}")
                        return session_client.url
                except Exception as e:
                    logger.debug(f"Could not get session-specific Odoo URL: {e}")
            
            # Fallback to global config
            from config import config
            if config.odoo.url:
                logger.info(f"Using global Odoo URL: {config.odoo.url}")
                return config.odoo.url
            
            logger.warning("No Odoo URL found in session or config")
            return None
            
        except Exception as e:
            logger.error(f"Failed to get Odoo base URL: {str(e)}")
            return None

class LinkedInProcessingNode:
    """Node for processing LinkedIn profile data and creating leads"""
    
    def __init__(self):
        from linkedin_scraper import LinkedInScraper
        self.linkedin_scraper = LinkedInScraper()
    
    def process(self, state: AgentState) -> AgentState:
        """Process LinkedIn profile data and create leads"""
        try:
            if state is None:
                logger.error("LinkedIn processing failed: state is None")
                return state
            
            try:
                user_message = StateManager.get_last_user_message(state)
            except Exception as e:
                logger.warning(f"Could not extract user message for LinkedIn processing: {e}")
                user_message = ""
            
            entities = state.get("entities", {})
            
            logger.info(f"Processing LinkedIn request: {user_message[:100]}...")
            
            # Extract LinkedIn URL from message or entities
            linkedin_url = self._extract_linkedin_url(user_message)
            if not linkedin_url and entities.get("linkedin_url"):
                linkedin_url = entities["linkedin_url"]
            
            if not linkedin_url:
                StateManager.set_error(state, "No LinkedIn profile URL found in the message", "linkedin_processing_error")
                return state
            
            # Process LinkedIn profile
            result = self.linkedin_scraper.process_profile_for_lead(linkedin_url)
            
            if not result.get("success"):
                error_msg = result.get("error", "Failed to process LinkedIn profile")
                StateManager.set_error(state, error_msg, "linkedin_processing_error")
                return state
            
            # Get session-specific Odoo client
            session_id = state.get("session_id")
            client = get_odoo_client_for_session(session_id) if session_id else None
            
            # Create lead from processed data
            processed_data = result.get("processed_data", {})
            lead_result = self._create_lead_from_linkedin(processed_data, linkedin_url, client)
            
            if lead_result.success:
                state["odoo_result"] = {
                    "success": True,
                    "data": {
                        "type": "linkedin_lead_created",
                        "lead_id": lead_result.data.get("lead_id"),
                        "name": processed_data.get("name", "Unknown"),
                        "company": processed_data.get("company", "Unknown"),
                        "linkedin_url": linkedin_url
                    }
                }
                state["current_step"] = "linkedin_processed"
            else:
                StateManager.set_error(state, lead_result.error, "linkedin_lead_creation_error")
            
        except Exception as e:
            logger.error(f"LinkedIn processing failed: {str(e)}")
            StateManager.set_error(state, f"LinkedIn processing failed: {str(e)}", "linkedin_processing_error")
        
        return state
    
    def _extract_linkedin_url(self, text: str) -> str:
        """Extract LinkedIn profile URL from text"""
        import re
        match = re.search(r"https?://[^/]*linkedin\.com/in/[\w\-\.]+", text)
        if match:
            return match.group(0)
        return None
    
    def _create_lead_from_linkedin(self, processed_data: Dict[str, Any], linkedin_url: str, client=None) -> ProcessingResult:
        """Create a CRM lead from LinkedIn profile data"""
        try:
            from datetime import datetime
            
            # Use provided client or fall back to global odoo_client
            odoo_client_to_use = client or odoo_client
            
            # Ensure Odoo connection
            if not odoo_client_to_use.uid:
                if not odoo_client_to_use.connect():
                    return ProcessingResult(False, error="Failed to connect to Odoo")
            
            # Prepare lead data
            lead_data = {
                'name': processed_data.get('name', 'LinkedIn Lead'),
                'contact_name': processed_data.get('name', ''),
                'function': processed_data.get('title', ''),
                'partner_name': processed_data.get('company', ''),
                'email_from': processed_data.get('email', ''),
                'phone': processed_data.get('phone', ''),
                'street': processed_data.get('location', ''),
                'description': f"LinkedIn Profile: {linkedin_url}\n\nSummary: {processed_data.get('summary', '')}",
                'source_id': self._get_or_create_source('LinkedIn', odoo_client_to_use),
                'stage_id': 1,  # Default to first stage
                'user_id': 1,   # Assign to admin user
                'date_open': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
            
            # Remove empty fields
            lead_data = {k: v for k, v in lead_data.items() if v}
            
            logger.info(f"Creating LinkedIn lead with data: {lead_data}")
            
            # Create the lead
            lead_id = odoo_client_to_use.create('crm.lead', lead_data)
            
            if lead_id:
                logger.info(f"Successfully created LinkedIn lead with ID: {lead_id}")
                return ProcessingResult(
                    True,
                    data={
                        'lead_id': lead_id,
                        'name': lead_data['name'],
                        'company': lead_data.get('partner_name', ''),
                        'linkedin_url': linkedin_url
                    }
                )
            else:
                return ProcessingResult(False, error="Failed to create lead in Odoo")
                
        except Exception as e:
            logger.error(f"LinkedIn lead creation failed: {str(e)}")
            return ProcessingResult(False, error=f"Lead creation failed: {str(e)}")
    
    def _get_or_create_source(self, source_name: str, client=None) -> int:
        """Get or create a lead source"""
        try:
            # Use provided client or fall back to global odoo_client
            odoo_client_to_use = client or odoo_client
            
            # Search for existing source
            sources = odoo_client_to_use.search_read('utm.source', [('name', '=', source_name)], ['id'])
            if sources:
                return sources[0]['id']
            
            # Create new source if not found
            source_id = odoo_client_to_use.create('utm.source', {'name': source_name})
            return source_id if source_id else 1  # Fallback to ID 1
            
        except Exception as e:
            logger.warning(f"Could not get/create source '{source_name}': {str(e)}")
            return 1  # Fallback to default source


class EnhancedReportingNode:
    """Node for handling enhanced reporting requests"""
    
    def process(self, state: AgentState) -> AgentState:
        """Process enhanced reporting requests"""
        try:
            if state is None:
                logger.error("Enhanced reporting failed: state is None")
                return state
            
            try:
                user_message = StateManager.get_last_user_message(state)
            except Exception as e:
                logger.warning(f"Could not extract user message for enhanced reporting: {e}")
                user_message = ""
            entities = state.get("entities", {})
            
            logger.info(f"Processing enhanced reporting request: {user_message[:100]}...")
            
            # Get session-specific Odoo client
            session_id = state.get("session_id")
            client = get_odoo_client_for_session(session_id) if session_id else None
            odoo_client_to_use = client or odoo_client
            
            # Ensure Odoo connection
            if not odoo_client_to_use.uid:
                if not odoo_client_to_use.connect():
                    StateManager.set_error(state, "Failed to connect to Odoo", "odoo_connection_error")
                    return state
            
            # Generate enhanced report
            result = self._generate_enhanced_report(user_message, entities, odoo_client_to_use)
            
            if result.success:
                state["odoo_result"] = {
                    "success": True,
                    "data": result.data
                }
                state["current_step"] = "reporting_completed"
            else:
                StateManager.set_error(state, result.error, "enhanced_reporting_error")
            
        except Exception as e:
            logger.error(f"Enhanced reporting failed: {str(e)}")
            StateManager.set_error(state, f"Enhanced reporting failed: {str(e)}", "enhanced_reporting_error")
        
        return state
    
    def _generate_enhanced_report(self, user_message: str, entities: Dict, client=None) -> ProcessingResult:
        """Generate enhanced reports with detailed analytics"""
        try:
            message_lower = user_message.lower()
            
            # Enhanced headcount/HR analysis
            if any(keyword in message_lower for keyword in ['headcount', 'employee', 'department', 'staff', 'hr']):
                return self._get_enhanced_headcount_report(entities, client)
            
            # Enhanced sales analysis
            elif any(keyword in message_lower for keyword in ['sales', 'revenue', 'performance']):
                return self._get_enhanced_sales_report(entities, client)
            
            # Enhanced customer analysis
            elif any(keyword in message_lower for keyword in ['customer', 'client', 'partner']):
                return self._get_enhanced_customer_report(entities, client)
            
            # Enhanced inventory analysis
            elif any(keyword in message_lower for keyword in ['inventory', 'stock', 'product']):
                return self._get_enhanced_inventory_report(entities, client)
            
            # Enhanced financial analysis
            elif any(keyword in message_lower for keyword in ['financial', 'invoice', 'payment']):
                return self._get_enhanced_financial_report(entities, client)
            
            # Default enhanced overview
            else:
                return self._get_enhanced_overview_report(entities, client)
                
        except Exception as e:
            logger.error(f"Enhanced report generation failed: {str(e)}")
            return ProcessingResult(False, error=f"Report generation failed: {str(e)}")
    
    def _get_enhanced_headcount_report(self, entities: Dict, client=None) -> ProcessingResult:
        """Generate enhanced headcount breakdown by department"""
        try:
            # Use provided client or fall back to global odoo_client
            odoo_client_to_use = client or odoo_client
            
            # Get employees from hr.employee model
            employees = odoo_client_to_use.search_read('hr.employee',
                                              [('active', '=', True)],
                                              ['name', 'department_id', 'job_title', 'work_email', 'work_phone'],
                                              limit=500)
            
            # Group employees by department
            department_breakdown = {}
            total_employees = len(employees)
            
            for employee in employees:
                dept_name = employee['department_id'][1] if employee['department_id'] else 'No Department'
                
                if dept_name not in department_breakdown:
                    department_breakdown[dept_name] = {
                        'count': 0,
                        'employees': []
                    }
                
                department_breakdown[dept_name]['count'] += 1
                department_breakdown[dept_name]['employees'].append({
                    'name': employee['name'],
                    'job_title': employee['job_title'] or 'N/A',
                    'email': employee['work_email'] or 'N/A'
                })
            
            # Sort departments by employee count
            sorted_departments = sorted(department_breakdown.items(), 
                                      key=lambda x: x[1]['count'], 
                                      reverse=True)
            
            # Create summary message
            dept_summary = []
            for dept_name, dept_data in sorted_departments:
                dept_summary.append(f"{dept_name}: {dept_data['count']} employees")
            
            summary_message = f"Headcount Breakdown - Total: {total_employees} employees across {len(department_breakdown)} departments\n" + "\n".join(dept_summary)
            
            return ProcessingResult(
                True,
                data={
                    'type': 'enhanced_headcount_report',
                    'total_employees': total_employees,
                    'department_count': len(department_breakdown),
                    'department_breakdown': dict(sorted_departments),
                    'employees': employees[:20],  # First 20 for preview
                    'message': summary_message
                }
            )
            
        except Exception as e:
            # Fallback if hr.employee model is not available
            try:
                # Try to get users as a fallback
                users = odoo_client_to_use.search_read('res.users',
                                               [('active', '=', True), ('share', '=', False)],
                                               ['name', 'login', 'email'],
                                               limit=100)
                
                return ProcessingResult(
                    True,
                    data={
                        'type': 'enhanced_headcount_report',
                        'total_employees': len(users),
                        'department_count': 1,
                        'department_breakdown': {'All Users': {'count': len(users), 'employees': users}},
                        'employees': users,
                        'message': f"Headcount Report (Fallback): {len(users)} active users found. HR module may not be installed for detailed department breakdown."
                    }
                )
            except Exception as fallback_error:
                return ProcessingResult(False, error=f"Headcount report failed: {str(e)}. Fallback also failed: {str(fallback_error)}")
    
    def _get_enhanced_sales_report(self, entities: Dict, client=None) -> ProcessingResult:
        """Generate enhanced sales performance report"""
        try:
            # Use provided client or fall back to global odoo_client
            odoo_client_to_use = client or odoo_client
            
            # Get sales orders with detailed analysis
            domain = [('state', 'in', ['sale', 'done'])]
            orders = odoo_client_to_use.search_read('sale.order', domain,
                                           ['name', 'partner_id', 'amount_total', 'date_order', 'state'],
                                           limit=100)
            
            total_revenue = sum(order['amount_total'] for order in orders)
            avg_order_value = total_revenue / len(orders) if orders else 0
            
            # Group by month for trend analysis
            monthly_data = {}
            for order in orders:
                month = order['date_order'][:7] if order['date_order'] else 'Unknown'
                if month not in monthly_data:
                    monthly_data[month] = {'count': 0, 'revenue': 0}
                monthly_data[month]['count'] += 1
                monthly_data[month]['revenue'] += order['amount_total']
            
            return ProcessingResult(
                True,
                data={
                    'type': 'enhanced_sales_report',
                    'total_orders': len(orders),
                    'total_revenue': total_revenue,
                    'avg_order_value': avg_order_value,
                    'monthly_trends': monthly_data,
                    'recent_orders': orders[:10],
                    'message': f"Enhanced Sales Report: {len(orders)} orders totaling ${total_revenue:,.2f} (Avg: ${avg_order_value:,.2f})"
                }
            )
            
        except Exception as e:
            return ProcessingResult(False, error=f"Enhanced sales report failed: {str(e)}")
    
    def _get_enhanced_customer_report(self, entities: Dict, client=None) -> ProcessingResult:
        """Generate enhanced customer analysis report"""
        try:
            # Use provided client or fall back to global odoo_client
            odoo_client_to_use = client or odoo_client
            
            # Get customers with purchase history
            customers = odoo_client_to_use.search_read('res.partner', 
                                              [('is_company', '=', True), ('customer_rank', '>', 0)],
                                              ['name', 'email', 'phone', 'country_id'],
                                              limit=100)
            
            # Get sales data for customer analysis
            sales_data = odoo_client_to_use.search_read('sale.order',
                                               [('state', 'in', ['sale', 'done'])],
                                               ['partner_id', 'amount_total'],
                                               limit=500)
            
            # Analyze customer value
            customer_values = {}
            for sale in sales_data:
                partner_id = sale['partner_id'][0] if sale['partner_id'] else None
                if partner_id:
                    if partner_id not in customer_values:
                        customer_values[partner_id] = 0
                    customer_values[partner_id] += sale['amount_total']
            
            # Sort customers by value
            top_customers = sorted(customer_values.items(), key=lambda x: x[1], reverse=True)[:10]
            
            return ProcessingResult(
                True,
                data={
                    'type': 'enhanced_customer_report',
                    'total_customers': len(customers),
                    'customers_with_purchases': len(customer_values),
                    'top_customers': top_customers,
                    'customer_list': customers[:20],
                    'message': f"Enhanced Customer Report: {len(customers)} customers, {len(customer_values)} with purchases"
                }
            )
            
        except Exception as e:
            return ProcessingResult(False, error=f"Enhanced customer report failed: {str(e)}")
    
    def _get_enhanced_inventory_report(self, entities: Dict, client=None) -> ProcessingResult:
        """Generate enhanced inventory analysis report"""
        try:
            # Use provided client or fall back to global odoo_client
            odoo_client_to_use = client or odoo_client
            
            # Get products with stock information
            products = odoo_client_to_use.search_read('product.product',
                                             [('sale_ok', '=', True)],
                                             ['name', 'list_price', 'qty_available', 'categ_id'],
                                             limit=100)
            
            # Analyze inventory levels
            low_stock = [p for p in products if p['qty_available'] < 10]
            out_of_stock = [p for p in products if p['qty_available'] <= 0]
            total_value = sum(p['list_price'] * p['qty_available'] for p in products)
            
            return ProcessingResult(
                True,
                data={
                    'type': 'enhanced_inventory_report',
                    'total_products': len(products),
                    'low_stock_count': len(low_stock),
                    'out_of_stock_count': len(out_of_stock),
                    'total_inventory_value': total_value,
                    'low_stock_items': low_stock[:10],
                    'products': products[:20],
                    'message': f"Enhanced Inventory Report: {len(products)} products, {len(low_stock)} low stock, ${total_value:,.2f} total value"
                }
            )
            
        except Exception as e:
            return ProcessingResult(False, error=f"Enhanced inventory report failed: {str(e)}")
    
    def _get_enhanced_financial_report(self, entities: Dict, client=None) -> ProcessingResult:
        """Generate enhanced financial analysis report"""
        try:
            # Use provided client or fall back to global odoo_client
            odoo_client_to_use = client or odoo_client
            
            # Get invoices and payments
            invoices = odoo_client_to_use.search_read('account.move',
                                             [('move_type', '=', 'out_invoice'), ('state', '=', 'posted')],
                                             ['name', 'partner_id', 'amount_total', 'invoice_date', 'payment_state'],
                                             limit=100)
            
            # Analyze financial metrics
            total_invoiced = sum(inv['amount_total'] for inv in invoices)
            paid_invoices = [inv for inv in invoices if inv['payment_state'] == 'paid']
            unpaid_invoices = [inv for inv in invoices if inv['payment_state'] in ['not_paid', 'partial']]
            
            total_paid = sum(inv['amount_total'] for inv in paid_invoices)
            total_outstanding = sum(inv['amount_total'] for inv in unpaid_invoices)
            
            return ProcessingResult(
                True,
                data={
                    'type': 'enhanced_financial_report',
                    'total_invoices': len(invoices),
                    'total_invoiced': total_invoiced,
                    'total_paid': total_paid,
                    'total_outstanding': total_outstanding,
                    'paid_count': len(paid_invoices),
                    'unpaid_count': len(unpaid_invoices),
                    'recent_invoices': invoices[:10],
                    'message': f"Enhanced Financial Report: ${total_invoiced:,.2f} invoiced, ${total_paid:,.2f} paid, ${total_outstanding:,.2f} outstanding"
                }
            )
            
        except Exception as e:
            return ProcessingResult(False, error=f"Enhanced financial report failed: {str(e)}")
    
    def _get_enhanced_overview_report(self, entities: Dict, client=None) -> ProcessingResult:
        """Generate enhanced business overview report"""
        try:
            # Use provided client or fall back to global odoo_client
            odoo_client_to_use = client or odoo_client
            
            # Get key metrics from multiple models
            sales_count = len(odoo_client_to_use.search('sale.order', [('state', 'in', ['sale', 'done'])], limit=1000))
            customer_count = len(odoo_client_to_use.search('res.partner', [('customer_rank', '>', 0)], limit=1000))
            product_count = len(odoo_client_to_use.search('product.product', [('sale_ok', '=', True)], limit=1000))
            invoice_count = len(odoo_client_to_use.search('account.move', [('move_type', '=', 'out_invoice')], limit=1000))
            
            return ProcessingResult(
                True,
                data={
                    'type': 'enhanced_overview_report',
                    'sales_orders': sales_count,
                    'customers': customer_count,
                    'products': product_count,
                    'invoices': invoice_count,
                    'message': f"Enhanced Business Overview: {sales_count} sales orders, {customer_count} customers, {product_count} products, {invoice_count} invoices"
                }
            )
            
        except Exception as e:
            return ProcessingResult(False, error=f"Enhanced overview report failed: {str(e)}")