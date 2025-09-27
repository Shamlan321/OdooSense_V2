import logging
from typing import Dict, Any, Literal, List
from langgraph.graph import StateGraph, END
from agent_state import AgentState, StateManager
from agent_nodes import (
    IntentClassificationNode,
    DocumentProcessingNode,
    CRUDOperationsNode,
    QANavigationNode,
    ResponseGenerationNode,
    DataLookupNode,
    NavigationNode,
    LinkedInProcessingNode,
    EnhancedReportingNode
)
from odoo_autogen_reporting import AutoGenReportingNode
from config import config

logger = logging.getLogger(__name__)

class OdooLangGraphAgent:
    """Main LangGraph agent for Odoo AI Assistant"""
    
    def __init__(self):
        self.intent_classifier = IntentClassificationNode()
        self.document_processor = DocumentProcessingNode()
        self.crud_processor = CRUDOperationsNode()
        self.qa_processor = QANavigationNode()
        self.data_lookup_processor = DataLookupNode()
        self.navigation_processor = NavigationNode()
        self.linkedin_processor = LinkedInProcessingNode()
        self.enhanced_reporting_processor = EnhancedReportingNode()
        self.autogen_reporting_processor = AutoGenReportingNode()
        self.response_generator = ResponseGenerationNode()
        
        self.workflow = self._build_workflow()
        self.app = self.workflow.compile()
    
    def _build_workflow(self) -> StateGraph:
        """Build the LangGraph workflow"""
        workflow = StateGraph(AgentState)
        
        # Add nodes
        workflow.add_node("classify_intent", self._classify_intent_wrapper)
        workflow.add_node("process_document", self._process_document_wrapper)
        workflow.add_node("handle_crud", self._handle_crud_wrapper)
        workflow.add_node("handle_qa", self._handle_qa_wrapper)
        workflow.add_node("handle_data_lookup", self._handle_data_lookup_wrapper)
        workflow.add_node("handle_navigation", self._handle_navigation_wrapper)
        workflow.add_node("process_linkedin", self._process_linkedin_wrapper)
        workflow.add_node("handle_reporting", self._handle_reporting_wrapper)
        workflow.add_node("handle_autogen_reporting", self._handle_autogen_reporting_wrapper)
        workflow.add_node("generate_response", self._generate_response_wrapper)
        workflow.add_node("handle_error", self._handle_error_wrapper)
        
        # Set entry point
        workflow.set_entry_point("classify_intent")
        
        # Define conditional routing
        workflow.add_conditional_edges(
            "classify_intent",
            self._route_after_intent,
            {
                "process_document": "process_document",
                "handle_crud": "handle_crud",
                "handle_qa": "handle_qa",
                "handle_data_lookup": "handle_data_lookup",
                "handle_navigation": "handle_navigation",
                "process_linkedin": "process_linkedin",
                "handle_reporting": "handle_reporting",
                "handle_autogen_reporting": "handle_autogen_reporting",
                "generate_response": "generate_response",
                "handle_error": "handle_error"
            }
        )
        
        workflow.add_conditional_edges(
            "process_document",
            self._route_after_document,
            {
                "handle_crud": "handle_crud",
                "generate_response": "generate_response",
                "handle_error": "handle_error"
            }
        )
        
        workflow.add_conditional_edges(
            "handle_crud",
            self._route_after_crud,
            {
                "generate_response": "generate_response",
                "handle_error": "handle_error"
            }
        )
        
        workflow.add_conditional_edges(
            "handle_qa",
            self._route_after_qa,
            {
                "generate_response": "generate_response",
                "handle_error": "handle_error"
            }
        )
        
        workflow.add_conditional_edges(
            "handle_data_lookup",
            self._route_after_data_lookup,
            {
                "generate_response": "generate_response",
                "handle_error": "handle_error"
            }
        )
        
        workflow.add_conditional_edges(
            "handle_navigation",
            self._route_after_navigation,
            {
                "generate_response": "generate_response",
                "handle_error": "handle_error"
            }
        )
        
        workflow.add_conditional_edges(
            "process_linkedin",
            self._route_after_linkedin,
            {
                "generate_response": "generate_response",
                "handle_error": "handle_error"
            }
        )
        
        workflow.add_conditional_edges(
            "handle_reporting",
            self._route_after_reporting,
            {
                "generate_response": "generate_response",
                "handle_error": "handle_error"
            }
        )
        
        workflow.add_conditional_edges(
            "handle_autogen_reporting",
            self._route_after_autogen_reporting,
            {
                "generate_response": "generate_response",
                "handle_error": "handle_error"
            }
        )
        
        # All paths lead to END after response generation or error handling
        workflow.add_edge("generate_response", END)
        workflow.add_edge("handle_error", END)
        
        return workflow
    
    # Node wrappers
    def _classify_intent_wrapper(self, state: AgentState) -> AgentState:
        """Wrapper for intent classification node"""
        print(f"[CONSOLE DEBUG] _classify_intent_wrapper called")
        print(f"[CONSOLE DEBUG] State keys: {list(state.keys()) if state else 'None'}")
        print(f"[CONSOLE DEBUG] Intent before classification: {state.get('intent') if state else 'None'}")
        print(f"[CONSOLE DEBUG] Next action before classification: {state.get('next_action') if state else 'None'}")
        
        logger.info("Starting intent classification")
        try:
            if state is None:
                logger.error("Intent classification: state is None")
                return StateManager.create_initial_state("Error: state is None", "unknown", None)
            
            # Skip intent classification if next_action is already set to handle_crud
            # This preserves the routing for confirmed data processing
            if state.get('next_action') == 'handle_crud':
                print(f"[CONSOLE DEBUG] Skipping intent classification - next_action already set to handle_crud")
                return state
            
            result = self.intent_classifier.process(state)
            if result is None:
                logger.error("Intent classification returned None")
                StateManager.set_error(state, "Intent classification failed", "intent_classification_error")
                return state
            
            print(f"[CONSOLE DEBUG] Intent after classification: {result.get('intent') if result else 'None'}")
            print(f"[CONSOLE DEBUG] Next action after classification: {result.get('next_action') if result else 'None'}")
            return result
        except Exception as e:
            logger.error(f"Intent classification wrapper failed: {str(e)}")
            if state is not None:
                StateManager.set_error(state, f"Intent classification error: {str(e)}", "intent_classification_error")
                return state
            return StateManager.create_initial_state("Error in intent classification", "unknown", None)
    
    def _process_document_wrapper(self, state: AgentState) -> AgentState:
        """Wrapper for document processing node"""
        logger.info("Starting document processing")
        try:
            if state is None:
                logger.error("Document processing: state is None")
                return StateManager.create_initial_state("Error: state is None", "unknown", None)
            
            result = self.document_processor.process(state)
            if result is None:
                logger.error("Document processing returned None")
                StateManager.set_error(state, "Document processing failed", "document_processing_error")
                return state
            return result
        except Exception as e:
            logger.error(f"Document processing wrapper failed: {str(e)}")
            if state is not None:
                StateManager.set_error(state, f"Document processing error: {str(e)}", "document_processing_error")
                return state
            return StateManager.create_initial_state("Error in document processing", "unknown", None)
    
    def _handle_crud_wrapper(self, state: AgentState) -> AgentState:
        """Wrapper for CRUD operations node"""
        logger.info("Starting CRUD operations")
        try:
            if state is None:
                logger.error("CRUD operations: state is None")
                return StateManager.create_initial_state("Error: state is None", "unknown", None)
            
            result = self.crud_processor.process(state)
            if result is None:
                logger.error("CRUD operations returned None")
                StateManager.set_error(state, "CRUD operations failed", "crud_processing_error")
                return state
            return result
        except Exception as e:
            logger.error(f"CRUD operations wrapper failed: {str(e)}")
            if state is not None:
                StateManager.set_error(state, f"CRUD operations error: {str(e)}", "crud_processing_error")
                return state
            return StateManager.create_initial_state("Error in CRUD operations", "unknown", None)
    
    def _handle_qa_wrapper(self, state: AgentState) -> AgentState:
        """Wrapper for Q&A processing node"""
        logger.info("Starting Q&A processing")
        try:
            if state is None:
                logger.error("Q&A processing: state is None")
                return StateManager.create_initial_state("Error: state is None", "unknown", None)
            
            result = self.qa_processor.process(state)
            if result is None:
                logger.error("Q&A processing returned None")
                StateManager.set_error(state, "Q&A processing failed", "qa_processing_error")
                return state
            return result
        except Exception as e:
            logger.error(f"Q&A processing wrapper failed: {str(e)}")
            if state is not None:
                StateManager.set_error(state, f"Q&A processing error: {str(e)}", "qa_processing_error")
                return state
            return StateManager.create_initial_state("Error in Q&A processing", "unknown", None)
    
    def _handle_data_lookup_wrapper(self, state: AgentState) -> AgentState:
        """Wrapper for data lookup processing node"""
        logger.info("Starting data lookup processing")
        try:
            if state is None:
                logger.error("Data lookup processing: state is None")
                return StateManager.create_initial_state("Error: state is None", "unknown", None)
            
            result = self.data_lookup_processor.process(state)
            if result is None:
                logger.error("Data lookup processing returned None")
                StateManager.set_error(state, "Data lookup processing failed", "data_lookup_processing_error")
                return state
            return result
        except Exception as e:
            logger.error(f"Data lookup processing wrapper failed: {str(e)}")
            if state is not None:
                StateManager.set_error(state, f"Data lookup processing error: {str(e)}", "data_lookup_processing_error")
                return state
            return StateManager.create_initial_state("Error in data lookup processing", "unknown", None)
    
    def _handle_navigation_wrapper(self, state: AgentState) -> AgentState:
        """Wrapper for navigation processing node"""
        logger.info("Starting navigation processing")
        try:
            if state is None:
                logger.error("Navigation processing: state is None")
                return StateManager.create_initial_state("Error: state is None", "unknown", None)
            
            result = self.navigation_processor.process(state)
            if result is None:
                logger.error("Navigation processing returned None")
                StateManager.set_error(state, "Navigation processing failed", "navigation_processing_error")
                return state
            return result
        except Exception as e:
            logger.error(f"Navigation processing wrapper failed: {str(e)}")
            if state is not None:
                StateManager.set_error(state, f"Navigation processing error: {str(e)}", "navigation_processing_error")
                return state
            return StateManager.create_initial_state("Error in navigation processing", "unknown", None)
    
    def _process_linkedin_wrapper(self, state: AgentState) -> AgentState:
        """Wrapper for LinkedIn processing node"""
        logger.info("Starting LinkedIn processing")
        try:
            if state is None:
                logger.error("LinkedIn processing: state is None")
                return StateManager.create_initial_state("Error: state is None", "unknown", None)
            
            result = self.linkedin_processor.process(state)
            if result is None:
                logger.error("LinkedIn processing returned None")
                StateManager.set_error(state, "LinkedIn processing failed", "linkedin_processing_error")
                return state
            return result
        except Exception as e:
            logger.error(f"LinkedIn processing wrapper failed: {str(e)}")
            if state is not None:
                StateManager.set_error(state, f"LinkedIn processing error: {str(e)}", "linkedin_processing_error")
                return state
            return StateManager.create_initial_state("Error in LinkedIn processing", "unknown", None)
    
    def _handle_reporting_wrapper(self, state: AgentState) -> AgentState:
        """Wrapper for enhanced reporting node"""
        logger.info("Starting enhanced reporting")
        try:
            if state is None:
                logger.error("Enhanced reporting: state is None")
                return StateManager.create_initial_state("Error: state is None", "unknown", None)
            
            result = self.enhanced_reporting_processor.process(state)
            if result is None:
                logger.error("Enhanced reporting returned None")
                StateManager.set_error(state, "Enhanced reporting failed", "reporting_processing_error")
                return state
            return result
        except Exception as e:
            logger.error(f"Enhanced reporting wrapper failed: {str(e)}")
            if state is not None:
                StateManager.set_error(state, f"Enhanced reporting error: {str(e)}", "reporting_processing_error")
                return state
            return StateManager.create_initial_state("Error in enhanced reporting", "unknown", None)
    
    def _handle_autogen_reporting_wrapper(self, state: AgentState) -> AgentState:
        """Wrapper for AutoGen reporting node"""
        logger.info("Starting AutoGen advanced reporting")
        try:
            if state is None:
                logger.error("AutoGen reporting: state is None")
                return StateManager.create_initial_state("Error: state is None", "unknown", None)
            
            result = self.autogen_reporting_processor.process(state)
            if result is None:
                logger.error("AutoGen reporting returned None")
                StateManager.set_error(state, "AutoGen reporting failed", "autogen_reporting_processing_error")
                return state
            return result
        except Exception as e:
            logger.error(f"AutoGen reporting wrapper failed: {str(e)}")
            if state is not None:
                StateManager.set_error(state, f"AutoGen reporting error: {str(e)}", "autogen_reporting_processing_error")
                return state
            return StateManager.create_initial_state("Error in AutoGen reporting", "unknown", None)
    
    def _generate_response_wrapper(self, state: AgentState) -> AgentState:
        """Wrapper for response generation node"""
        logger.info("Starting response generation")
        try:
            if state is None:
                logger.error("Response generation: state is None")
                return StateManager.create_initial_state("Error: state is None", "unknown", None)
            
            result = self.response_generator.process(state)
            if result is None:
                logger.error("Response generation returned None")
                StateManager.set_error(state, "Response generation failed", "response_generation_error")
                return state
            return result
        except Exception as e:
            logger.error(f"Response generation wrapper failed: {str(e)}")
            if state is not None:
                StateManager.set_error(state, f"Response generation error: {str(e)}", "response_generation_error")
                return state
            return StateManager.create_initial_state("Error in response generation", "unknown", None)
    
    def _handle_error_wrapper(self, state: AgentState) -> AgentState:
        """Wrapper for error handling"""
        logger.info("Handling error state")
        
        try:
            if state is None:
                logger.error("Error handling: state is None")
                return StateManager.create_initial_state("Error: state is None in error handler", "unknown", None)
            
            # Check if we should retry
            if StateManager.should_retry(state, config.agent.max_retries):
                StateManager.increment_retry(state)
                StateManager.clear_error(state)
                
                # Determine where to retry from
                current_step = state.get("current_step", "start")
                if "intent" in current_step:
                    state["next_action"] = "classify_intent"
                elif "document" in current_step:
                    state["next_action"] = "process_document"
                elif "crud" in current_step:
                    state["next_action"] = "handle_crud"
                elif "qa" in current_step:
                    state["next_action"] = "handle_qa"
                elif "data_lookup" in current_step:
                    state["next_action"] = "handle_data_lookup"
                elif "linkedin" in current_step:
                    state["next_action"] = "process_linkedin"
                elif "reporting" in current_step:
                    state["next_action"] = "handle_reporting"
                else:
                    state["next_action"] = "generate_response"
                
                logger.info(f"Retrying from: {state['next_action']} (attempt {state['retry_count']})")
            else:
                # Generate error response
                result = self.response_generator.process(state)
                if result is None:
                    logger.error("Response generator returned None in error handler")
                    StateManager.set_error(state, "Response generation failed in error handler", "error_handler_failure")
                    return state
                state = result
                logger.error(f"Max retries exceeded. Final error: {state.get('error_state')}")
            
            return state
            
        except Exception as e:
            logger.error(f"Error handler wrapper failed: {str(e)}")
            if state is not None:
                StateManager.set_error(state, f"Error handler failed: {str(e)}", "error_handler_failure")
                return state
            return StateManager.create_initial_state("Error in error handler", "unknown", None)
    
    # Routing functions
    def _route_after_intent(self, state: AgentState) -> Literal[
        "process_document", "handle_crud", "handle_qa", "handle_data_lookup", "process_linkedin", "handle_reporting", "handle_autogen_reporting", "generate_response", "handle_error"
    ]:
        """Route after intent classification"""
        print(f"[CONSOLE DEBUG] _route_after_intent called")
        print(f"[CONSOLE DEBUG] Error state: {state.get('error_state')}")
        print(f"[CONSOLE DEBUG] Next action: {state.get('next_action')}")
        print(f"[CONSOLE DEBUG] Intent: {state.get('intent')}")
        
        if state.get("error_state"):
            print(f"[CONSOLE DEBUG] Routing to handle_error due to error_state")
            return "handle_error"
        
        next_action = state.get("next_action")
        intent = state.get("intent")
        
        try:
            user_message = StateManager.get_last_user_message(state)
        except Exception as e:
            logger.warning(f"Could not extract user message for routing: {e}")
            user_message = ""
        
        # Priority routing: next_action takes precedence over intent
        if next_action == "process_document":
            print(f"[CONSOLE DEBUG] Routing to process_document")
            return "process_document"
        elif next_action == "handle_crud":
            print(f"[CONSOLE DEBUG] Routing to handle_crud")
            return "handle_crud"
        elif next_action == "handle_qa_navigation":
            return "handle_qa"
        elif next_action == "handle_data_lookup":
            return "handle_data_lookup"
        elif next_action == "handle_navigation":
            return "handle_navigation"
        elif next_action == "process_linkedin":
            return "process_linkedin"
        elif next_action == "handle_reporting":
            # Check if this should use AutoGen for advanced reporting
            if self.autogen_reporting_processor.supports_request(user_message):
                return "handle_autogen_reporting"
            return "handle_reporting"
        elif intent == "qa_navigation":
            return "handle_qa"
        elif intent == "data_lookup":
            return "handle_data_lookup"
        elif intent == "navigation":
            return "handle_navigation"
        elif intent == "linkedin_processing":
            return "process_linkedin"
        elif intent == "reporting":
            # Check if this should use AutoGen for advanced reporting
            if self.autogen_reporting_processor.supports_request(user_message):
                return "handle_autogen_reporting"
            return "handle_reporting"
        else:
            return "generate_response"
    
    def _route_after_document(self, state: AgentState) -> Literal[
        "handle_crud", "generate_response", "handle_error"
    ]:
        """Route after document processing"""
        logger.debug(f"[LangGraphAgent] _route_after_document: state type = {type(state)}")
        
        if state is None:
            logger.error("[LangGraphAgent] _route_after_document: state is None, routing to handle_error")
            return "handle_error"
        
        if not hasattr(state, 'get'):
            logger.error(f"[LangGraphAgent] _route_after_document: state has no 'get' method, type: {type(state)}, routing to handle_error")
            return "handle_error"
        
        error_state = state.get("error_state")
        logger.debug(f"[LangGraphAgent] _route_after_document: error_state = {error_state}")
        
        if error_state:
            logger.debug(f"[LangGraphAgent] _route_after_document: routing to handle_error due to error_state")
            return "handle_error"
        
        # If document processing succeeded, proceed to CRUD operations
        extracted_data = state.get("extracted_data")
        logger.debug(f"[LangGraphAgent] _route_after_document: extracted_data = {bool(extracted_data)}")
        
        if extracted_data:
            logger.debug(f"[LangGraphAgent] _route_after_document: routing to handle_crud")
            return "handle_crud"
        else:
            logger.debug(f"[LangGraphAgent] _route_after_document: routing to generate_response")
            return "generate_response"
    
    def _route_after_crud(self, state: AgentState) -> Literal[
        "generate_response", "handle_error"
    ]:
        """Route after CRUD operations"""
        if state.get("error_state"):
            return "handle_error"
        else:
            return "generate_response"
    
    def _route_after_qa(self, state: AgentState) -> Literal[
        "generate_response", "handle_error"
    ]:
        """Route after Q&A processing"""
        if state.get("error_state"):
            return "handle_error"
        else:
            return "generate_response"
    
    def _route_after_data_lookup(self, state: AgentState) -> Literal[
        "generate_response", "handle_error"
    ]:
        """Route after data lookup processing"""
        if state.get("error_state"):
            return "handle_error"
        else:
            return "generate_response"
    
    def _route_after_navigation(self, state: AgentState) -> Literal[
        "generate_response", "handle_error"
    ]:
        """Route after navigation processing"""
        if state.get("error_state"):
            return "handle_error"
        else:
            return "generate_response"
    
    def _route_after_linkedin(self, state: AgentState) -> Literal[
        "generate_response", "handle_error"
    ]:
        """Route after LinkedIn processing"""
        if state.get("error_state"):
            return "handle_error"
        else:
            return "generate_response"
    
    def _route_after_reporting(self, state: AgentState) -> Literal[
        "generate_response", "handle_error"
    ]:
        """Route after enhanced reporting"""
        if state.get("error_state"):
            return "handle_error"
        else:
            return "generate_response"
    
    def _route_after_autogen_reporting(self, state: AgentState) -> Literal[
        "generate_response", "handle_error"
    ]:
        """Route after AutoGen reporting"""
        if state.get("error_state"):
            return "handle_error"
        else:
            return "generate_response"
    
    # Public interface methods
    def process_message(self, message: str, session_id: str, user_id: int = None) -> Dict[str, Any]:
        """Process a text message"""
        try:
            logger.info(f"[LangGraphAgent] Processing message for session {session_id}")
            logger.debug(f"[LangGraphAgent] Message: '{message}', User ID: {user_id}")
            
            # Create initial state
            logger.debug(f"[LangGraphAgent] Creating initial state")
            initial_state = StateManager.create_initial_state(message, session_id, user_id)
            logger.debug(f"[LangGraphAgent] Initial state created: {initial_state}")
            
            if initial_state is None:
                logger.error(f"[LangGraphAgent] StateManager returned None initial state")
                return {
                    "success": False,
                    "response": "Failed to create initial state",
                    "error": "Initial state is None"
                }
            
            # Run the workflow
            logger.debug(f"[LangGraphAgent] Running workflow with app.invoke()")
            result = self.app.invoke(initial_state)
            logger.debug(f"[LangGraphAgent] Workflow result: {result}")
            
            if result is None:
                logger.error(f"[LangGraphAgent] Workflow returned None result")
                return {
                    "success": False,
                    "response": "Workflow execution failed",
                    "error": "Workflow result is None"
                }
            
            logger.debug(f"[LangGraphAgent] Formatting response")
            formatted_response = self._format_response(result)
            logger.debug(f"[LangGraphAgent] Formatted response: {formatted_response}")
            
            return formatted_response
            
        except Exception as e:
            import traceback
            logger.error(f"[LangGraphAgent] Message processing failed: {str(e)}")
            logger.error(f"[LangGraphAgent] Full traceback: {traceback.format_exc()}")
            return {
                "success": False,
                "response": f"I apologize, but I encountered an error: {str(e)}",
                "error": str(e)
            }
    
    def process_message_stream(self, message: str, session_id: str, user_id: int = None):
        """Process a text message with streaming response"""
        try:
            from gemini_client import gemini_client
            
            # Create initial state
            initial_state = StateManager.create_initial_state(message, session_id, user_id)
            
            # First classify intent to determine if we can stream
            intent_result = self.intent_classifier.process(initial_state)
            intent = intent_result.get("intent")
            
            # For intents that require Gemini text generation, use streaming
            if intent in ["general_help", "qa_navigation", "data_lookup"]:
                # Generate streaming response directly
                prompt = f"""You are an AI assistant for Odoo ERP system. 
                User message: {message}
                
                Provide a helpful response about Odoo functionality, navigation, or general assistance.
                Be concise and practical in your response."""
                
                for chunk in gemini_client.generate_text_stream(prompt):
                    yield chunk
            else:
                # For non-streamable intents, process normally and yield the result
                result = self.app.invoke(initial_state)
                formatted_result = self._format_response(result)
                yield formatted_result.get("response", "No response generated")
                
        except Exception as e:
            logger.error(f"Streaming message processing failed: {str(e)}")
            yield f"I apologize, but I encountered an error processing your message: {str(e)}"
    
    def process_document(self, file_data: bytes, filename: str, mime_type: str, 
                       session_id: str, user_id: int = None, doc_type: str = None) -> Dict[str, Any]:
        """Process an uploaded document"""
        try:
            # Create initial state with document
            type_msg = f" as {doc_type}" if doc_type else ""
            message = f"Process this {filename}{type_msg}"
            initial_state = StateManager.create_initial_state(message, session_id, user_id)
            
            # Add uploaded file to state
            initial_state["uploaded_file"] = {
                "data": file_data,
                "filename": filename,
                "mime_type": mime_type
            }
            
            # Add document type to state if specified
            if doc_type:
                initial_state["document_type"] = doc_type
                logger.info(f"Document type set in initial state: {doc_type}")
            
            # Set intent to document processing
            initial_state["intent"] = "document_processing"
            initial_state["next_action"] = "process_document"
            
            # Run the workflow
            result = self.app.invoke(initial_state)
            
            return self._format_response(result)
            
        except Exception as e:
            logger.error(f"Document processing failed: {str(e)}")
            return {
                "success": False,
                "response": f"I apologize, but I encountered an error processing the document: {str(e)}",
                "error": str(e)
            }
    
    def preview_document(self, file_data: bytes, filename: str, mime_type: str, 
                        session_id: str, user_id: int = None, doc_type: str = None) -> Dict[str, Any]:
        """Extract data from document without processing to Odoo (preview mode)"""
        try:
            # Create initial state with document
            type_msg = f" as {doc_type}" if doc_type else ""
            message = f"Preview data from {filename}{type_msg}"
            initial_state = StateManager.create_initial_state(message, session_id, user_id)
            
            # Add uploaded file to state
            initial_state["uploaded_file"] = {
                "data": file_data,
                "filename": filename,
                "mime_type": mime_type
            }
            
            # Add document type to state if specified
            if doc_type:
                initial_state["document_type"] = doc_type
                logger.info(f"Document type set in initial state: {doc_type}")
            
            # Set intent to document processing but skip CRUD operations
            initial_state["intent"] = "document_processing"
            initial_state["next_action"] = "process_document"
            initial_state["preview_mode"] = True  # Flag to indicate preview mode
            
            # Run only document processing (extract data but don't save to Odoo)
            result = self.document_processor.process(initial_state)
            
            return self._format_response(result)
            
        except Exception as e:
            logger.error(f"Document preview failed: {str(e)}")
            return {
                "success": False,
                "response": f"I apologize, but I encountered an error previewing the document: {str(e)}",
                "error": str(e)
            }
    
    def process_confirmed_data(self, extracted_data: Dict[str, Any], session_id: str, 
                              user_id: int = None, document_type: str = None) -> Dict[str, Any]:
        """Process confirmed extracted data to Odoo"""
        try:
            print(f"[CONSOLE DEBUG] process_confirmed_data called with session_id: {session_id}")
            print(f"[CONSOLE DEBUG] document_type: {document_type}")
            print(f"[CONSOLE DEBUG] extracted_data: {extracted_data}")
            
            # Create initial state with extracted data
            message = "Process confirmed data to Odoo"
            initial_state = StateManager.create_initial_state(message, session_id, user_id)
            
            # Add extracted data to state
            initial_state["extracted_data"] = extracted_data
            initial_state["intent"] = "document_processing"
            initial_state["next_action"] = "handle_crud"
            
            # Use provided document_type or determine from extracted data
            if document_type:
                initial_state["document_type"] = document_type
                print(f"[CONSOLE DEBUG] Using provided document_type: {document_type}")
            elif extracted_data and isinstance(extracted_data, dict) and ("invoice_number" in extracted_data or "vendor_name" in extracted_data):
                initial_state["document_type"] = "bill"
                print(f"[CONSOLE DEBUG] Auto-determined document_type: bill")
            elif extracted_data and isinstance(extracted_data, dict) and "company" in extracted_data and "name" in extracted_data:
                initial_state["document_type"] = "business_card"
                print(f"[CONSOLE DEBUG] Auto-determined document_type: business_card")
            else:
                initial_state["document_type"] = "unknown"
                print(f"[CONSOLE DEBUG] Auto-determined document_type: unknown")
            
            print(f"[CONSOLE DEBUG] initial_state prepared: {initial_state}")
            print(f"[CONSOLE DEBUG] About to call self.app.invoke()")
            
            # Run the workflow starting from CRUD operations
            result = self.app.invoke(initial_state)
            
            print(f"[CONSOLE DEBUG] self.app.invoke() completed, result: {result}")
            
            return self._format_response(result)
            
        except Exception as e:
            logger.error(f"Confirmed data processing failed: {str(e)}")
            return {
                "success": False,
                "response": f"I apologize, but I encountered an error processing the confirmed data: {str(e)}",
                "error": str(e)
            }
    
    def process_email_for_vendor_bill(self, email_content: str, session_id: str, user_id: int = None) -> Dict[str, Any]:
        """Process email content to extract invoice data and create vendor bill"""
        try:
            from gemini_client import gemini_client
            
            # Create initial state
            message = "Process email content for vendor bill creation"
            initial_state = StateManager.create_initial_state(message, session_id, user_id)
            
            # Extract invoice data from email using Gemini
            prompt = """
Extract invoice/bill information from this email content. Be thorough and look carefully for ALL financial details.

Look for:
1. VENDOR INFORMATION: Company name, address, email, phone
2. INVOICE DETAILS: Invoice number, dates (invoice date, due date)
3. FINANCIAL AMOUNTS: Total amount, subtotal, tax amount, currency
4. LINE ITEMS: Product/service descriptions, quantities, unit prices, totals
5. EMAIL HEADERS: Sender information for vendor details

Return ONLY a valid JSON object with this exact structure:
{
    "vendor_name": "string",
    "vendor_address": "string",
    "vendor_email": "string",
    "vendor_phone": "string",
    "invoice_number": "string",
    "invoice_date": "YYYY-MM-DD",
    "due_date": "YYYY-MM-DD",
    "total_amount": 0.0,
    "currency": "string",
    "tax_amount": 0.0,
    "subtotal": 0.0,
    "line_items": [
        {
            "description": "string",
            "quantity": 1.0,
            "unit_price": 0.0,
            "total": 0.0
        }
    ],
    "confidence_score": 0.95
}

CRITICAL INSTRUCTIONS:
- ALWAYS extract total_amount if mentioned anywhere in the email (look for words like "Total:", "Amount:", "$", currency symbols)
- Extract vendor_name from email sender, signature, or company letterhead
- Use null for missing string fields, 0.0 for missing numeric fields
- Look for patterns like "Invoice #", "Bill #", "Reference:"
- Check email signature for vendor contact information
- Parse any tables or structured data in the email
- Use proper JSON syntax with double quotes

Email content:
""" + email_content
            
            # Use Gemini to extract invoice data from email text
            response = gemini_client.generate_text(prompt)
            cleaned_response = gemini_client._clean_json_response(response)
            
            try:
                import json
                extracted_data = json.loads(cleaned_response)
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse email extraction response: {str(e)}")
                return {
                    "success": False,
                    "response": "Failed to extract invoice data from email content. Please check the email format.",
                    "error": f"JSON parsing failed: {str(e)}"
                }
            
            # Add extracted data to state
            initial_state["extracted_data"] = extracted_data
            initial_state["document_type"] = "bill"  # Force bill creation
            initial_state["intent"] = "document_processing"
            initial_state["next_action"] = "handle_crud"
            
            # Run the workflow starting from CRUD operations
            result = self.app.invoke(initial_state)
            
            return self._format_response(result)
            
        except Exception as e:
            logger.error(f"Email processing failed: {str(e)}")
            return {
                "success": False,
                "response": f"I apologize, but I encountered an error processing the email: {str(e)}",
                "error": str(e)
            }
    
    def process_email_signature_for_lead(self, email_content: str, session_id: str, user_id: int = None) -> Dict[str, Any]:
        """Process email content to extract signature data and create CRM lead"""
        try:
            from gemini_client import gemini_client
            
            # Create initial state
            message = "Process email signature for CRM lead creation"
            initial_state = StateManager.create_initial_state(message, session_id, user_id)
            
            # Extract contact data from email signature using Gemini
            prompt = """
Extract contact information from this email signature/content. Look for names, companies, job titles, contact details, and addresses.

Return ONLY a valid JSON object with this exact structure:
{
    "name": "string",
    "company": "string",
    "title": "string",
    "email": "string",
    "phone": "string",
    "mobile": "string",
    "website": "string",
    "address": "string",
    "city": "string",
    "state": "string",
    "country": "string",
    "zip": "string",
    "linkedin": "string",
    "department": "string",
    "confidence_score": 0.95
}

IMPORTANT:
- Use null for missing string fields
- Extract information from email signature, footer, or contact details
- Look for patterns like "Best regards,", "Sincerely,", "--" that indicate signature start
- Extract sender information from email headers (From, Reply-To)
- Use proper JSON syntax with double quotes
- Focus on business contact information, not personal details

Email content:
""" + email_content
            
            # Use Gemini to extract contact data from email signature
            response = gemini_client.generate_text(prompt)
            cleaned_response = gemini_client._clean_json_response(response)
            
            try:
                import json
                extracted_data = json.loads(cleaned_response)
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse email signature extraction response: {str(e)}")
                return {
                    "success": False,
                    "response": "Failed to extract contact data from email signature. Please check the email format.",
                    "error": f"JSON parsing failed: {str(e)}"
                }
            
            # Add extracted data to state
            initial_state["extracted_data"] = extracted_data
            initial_state["document_type"] = "lead"  # Force lead creation
            initial_state["intent"] = "document_processing"
            initial_state["next_action"] = "handle_crud"
            
            # Run the workflow starting from CRUD operations
            result = self.app.invoke(initial_state)
            
            return self._format_response(result)
            
        except Exception as e:
            logger.error(f"Email signature processing failed: {str(e)}")
            return {
                "success": False,
                "response": f"I apologize, but I encountered an error processing the email signature: {str(e)}",
                "error": str(e)
            }
    
    def _format_response(self, state: AgentState) -> Dict[str, Any]:
        """Format the final response"""
        try:
            logger.debug(f"[LangGraphAgent] _format_response called with state type: {type(state)}")
            
            # Handle case where state might be None
            if state is None:
                logger.error(f"[LangGraphAgent] _format_response: state is None")
                return {
                    "success": False,
                    "response": "I apologize, but I encountered an error while generating the response: 'NoneType' object has no attribute 'get'",
                    "error": "State is None - response generation failed",
                    "intent": None,
                    "confidence": None,
                    "response_type": "error",
                    "session_id": None,
                    "metadata": {
                        "current_step": None,
                        "retry_count": 0,
                        "timestamp": None
                    }
                }
            
            logger.debug(f"[LangGraphAgent] _format_response: state keys: {list(state.keys()) if hasattr(state, 'keys') else 'No keys method'}")
            
            # Check if state has get method (should be dict-like)
            if not hasattr(state, 'get'):
                logger.error(f"[LangGraphAgent] _format_response: state has no 'get' method, type: {type(state)}")
                return {
                    "success": False,
                    "response": f"Invalid state type: {type(state)}",
                    "error": f"State is not dict-like: {type(state)}",
                    "intent": None,
                    "confidence": None,
                    "response_type": "error",
                    "session_id": None,
                    "metadata": {
                        "current_step": None,
                        "retry_count": 0,
                        "timestamp": None
                    }
                }
            
            logger.debug(f"[LangGraphAgent] _format_response: Getting error_state")
            error_state = state.get("error_state")
            logger.debug(f"[LangGraphAgent] _format_response: error_state = {error_state}")
            
            success = not bool(error_state)
            logger.debug(f"[LangGraphAgent] _format_response: success = {success}")
            
            logger.debug(f"[LangGraphAgent] _format_response: Building response_data")
            response_data = {
                "success": success,
                "response": state.get("response", "No response generated"),
                "intent": state.get("intent"),
                "confidence": state.get("confidence"),
                "response_type": state.get("response_type", "text"),
                "session_id": state.get("session_id")
            }
            logger.debug(f"[LangGraphAgent] _format_response: Basic response_data built")
            
            # Add additional data based on response type
            if state.get("odoo_result"):
                logger.debug(f"[LangGraphAgent] _format_response: Adding odoo_result")
                response_data["odoo_result"] = state["odoo_result"]
            
            if state.get("extracted_data"):
                logger.debug(f"[LangGraphAgent] _format_response: Adding extracted_data")
                response_data["extracted_data"] = state["extracted_data"]
            
            if state.get("error_state"):
                logger.debug(f"[LangGraphAgent] _format_response: Adding error_state")
                response_data["error"] = state["error_state"]
            
            # Add processing metadata
            logger.debug(f"[LangGraphAgent] _format_response: Getting timestamp")
            timestamp_value = state.get("timestamp")
            logger.debug(f"[LangGraphAgent] _format_response: timestamp_value = {timestamp_value}")
            
            response_data["metadata"] = {
                "current_step": state.get("current_step"),
                "retry_count": state.get("retry_count", 0),
                "timestamp": timestamp_value.isoformat() if timestamp_value else None
            }
            logger.debug(f"[LangGraphAgent] _format_response: Final response_data built successfully")
            
            return response_data
            
        except Exception as e:
            import traceback
            logger.error(f"[LangGraphAgent] _format_response failed: {str(e)}")
            logger.error(f"[LangGraphAgent] _format_response traceback: {traceback.format_exc()}")
            return {
                "success": False,
                "response": f"Error formatting response: {str(e)}",
                "error": f"_format_response failed: {str(e)}",
                "intent": None,
                "confidence": None,
                "response_type": "error",
                "session_id": None,
                "metadata": {
                    "current_step": None,
                    "retry_count": 0,
                    "timestamp": None
                }
            }
    
    def get_conversation_history(self, session_id: str) -> List[Dict[str, Any]]:
        """Get conversation history for a session"""
        # This would typically be stored in a database
        # For now, return empty list as we're not persisting conversations
        return []
    
    def health_check(self) -> Dict[str, Any]:
        """Check the health of all components"""
        from gemini_client import gemini_client
        from odoo_client import odoo_client
        
        health_status = {
            "agent": "healthy",
            "gemini": "unknown",
            "odoo": "unknown",
            "overall": "unknown"
        }
        
        try:
            # Test Gemini connection
            gemini_status = gemini_client.test_connection()
            health_status["gemini"] = gemini_status["status"]
            
            # Test Odoo connection
            odoo_status = odoo_client.test_connection()
            health_status["odoo"] = odoo_status["status"]
            
            # Determine overall health
            if health_status["gemini"] == "success" and health_status["odoo"] == "success":
                health_status["overall"] = "healthy"
            elif health_status["gemini"] == "success" or health_status["odoo"] == "success":
                health_status["overall"] = "partial"
            else:
                health_status["overall"] = "unhealthy"
            
        except Exception as e:
            health_status["overall"] = "error"
            health_status["error"] = str(e)
        
        return health_status

# Global agent instance
agent = OdooLangGraphAgent()