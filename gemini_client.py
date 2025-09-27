import json
import logging
from typing import Dict, List, Any, Optional, Union
from google import genai
from google.genai import types
from config import config

logger = logging.getLogger(__name__)

class GeminiClient:
    def __init__(self):
        self.api_key = config.gemini.api_key
        self.model_name = config.gemini.model_name
        self.vision_model = config.gemini.vision_model
        self.client = None
        
    def initialize(self) -> bool:
        """Initialize the Gemini client"""
        try:
            if not self.api_key:
                logger.error("Gemini API key not provided")
                return False
            
            # Initialize the client
            self.client = genai.Client(api_key=self.api_key)
            
            logger.info("Gemini client initialized successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize Gemini client: {str(e)}")
            return False
    
    def generate_text(self, prompt: str, temperature: float = None, max_tokens: int = None) -> str:
        """Generate text response using Gemini"""
        if not self.client:
            raise Exception("Gemini client not initialized")
        
        # Use optimized defaults from config
        temperature = temperature or config.gemini.temperature
        max_tokens = max_tokens or config.gemini.max_tokens
        
        try:
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=temperature,
                    max_output_tokens=max_tokens
                )
            )
            
            # Handle cases where response.text might be None
            if response.text is None:
                logger.warning("Gemini API returned None text response")
                return None
            
            return response.text
            
        except Exception as e:
            logger.error(f"Text generation failed: {str(e)}")
            raise
    
    def generate_text_stream(self, prompt: str, temperature: float = 0.7, max_tokens: int = 1000):
        """Generate streaming text response using Gemini"""
        if not self.client:
            raise Exception("Gemini client not initialized")
        
        try:
            response = self.client.models.generate_content_stream(
                model=self.model_name,
                contents=prompt
            )
            
            for chunk in response:
                if hasattr(chunk, 'text') and chunk.text:
                    yield chunk.text
                    
        except Exception as e:
            logger.error(f"Streaming text generation failed: {str(e)}")
            raise
    
    def process_image_with_text(self, image_bytes: bytes, prompt: str, mime_type: str = 'image/jpeg') -> str:
        """Process image with text prompt using Gemini Vision"""
        if not self.client:
            raise Exception("Gemini client not initialized")
        
        try:
            image_part = types.Part.from_bytes(
                data=image_bytes,
                mime_type=mime_type
            )
            response = self.client.models.generate_content(
                model=self.vision_model,
                contents=[image_part, prompt]
            )
            
            # Handle cases where response.text might be None
            if response.text is None:
                logger.warning("Gemini Vision API returned None text response")
                return ""
            
            return response.text
            
        except Exception as e:
            logger.error(f"Image processing failed: {str(e)}")
            raise
    
    def process_pdf_with_text(self, pdf_bytes: bytes, prompt: str) -> str:
        """Process PDF document with text prompt using Gemini"""
        if not self.client:
            raise Exception("Gemini client not initialized")
        
        try:
            pdf_part = types.Part.from_bytes(
                data=pdf_bytes,
                mime_type='application/pdf'
            )
            response = self.client.models.generate_content(
                model=self.vision_model,  # Use vision model for document processing
                contents=[pdf_part, prompt]
            )
            
            # Handle cases where response.text might be None
            if response.text is None:
                logger.warning("Gemini PDF processing returned None text response")
                return ""
            
            return response.text
            
        except Exception as e:
            logger.error(f"PDF processing failed: {str(e)}")
            raise
    
    def classify_intent(self, user_message: str, conversation_history: List[Dict] = None) -> Dict[str, Any]:
        """Classify user intent using Gemini with optimized prompt"""
        # Limit conversation history for faster processing
        conversation_context = ""
        if conversation_history:
            # Only use last 2 exchanges and truncate long messages
            recent_history = conversation_history[-2:]
            conversation_context = "\n".join([
                f"User: {msg.get('user', '')[:100]}...\nBot: {msg.get('assistant', '')[:100]}..."
                for msg in recent_history
            ])
        
        # Enhanced prompt with better examples for qa_navigation
        prompt = f"""
Classify intent for: "{user_message}"

Context: {conversation_context}

Intents:
- qa_navigation: Odoo documentation, how-to guides, tutorials, explanations (e.g., "How to create a sales order", "How do I register an invoice", "What is the process for", "Steps to configure", "How to setup", "Explain how to")
- document_processing: Upload and process documents (invoices, receipts, business cards)
- data_entry: Create or update records in Odoo
- data_lookup: Query existing data from Odoo
- reporting: Generate reports and analytics
- linkedin_processing: Process LinkedIn profile URLs
- general_help: General assistance, unclear requests, greetings

Examples:
- "How to create a sales order and register an invoice" → qa_navigation
- "Show me recent sales orders" → data_lookup
- "Create a new customer" → data_entry
- "Generate sales report" → reporting
- "Process this invoice" → document_processing

JSON only:
{{
    "intent": "intent_name",
    "confidence": 0.95,
    "entities": {{}}
}}
"""
        
        try:
            response = self.generate_text(prompt)
            
            # Handle None response from generate_text
            if response is None:
                logger.warning("Received None response from generate_text")
                return {
                    "intent": "general_help",
                    "confidence": 0.5,
                    "entities": {},
                    "reasoning": "No response from AI"
                }
            
            cleaned_response = self._clean_json_response(response)
            parsed_data = json.loads(cleaned_response)
            
            # Validate and set defaults
            default_data = {
                "intent": "general_help",
                "confidence": 0.5,
                "entities": {},
                "reasoning": "Default response"
            }
            
            for key, default_value in default_data.items():
                if key not in parsed_data:
                    parsed_data[key] = default_value
            
            return parsed_data
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse intent classification response: {str(e)}")
            return {
                "intent": "general_help",
                "confidence": 0.5,
                "entities": {},
                "reasoning": "Failed to parse response"
            }
        except Exception as e:
            logger.error(f"Intent classification failed: {str(e)}")
            raise
    
    def _clean_json_response(self, response: str) -> str:
        """Clean and validate JSON response from AI"""
        import re
        
        # Handle None response
        if response is None:
            logger.warning("Received None response from AI, returning empty JSON")
            return '{}'
        
        # Remove common markdown formatting
        response = response.strip()
        if response.startswith('```json'):
            response = response[7:]
        elif response.startswith('```'):
            response = response[3:]
        if response.endswith('```'):
            response = response[:-3]
        
        # Remove any leading/trailing whitespace
        response = response.strip()
        
        # Find the first { and last } to extract just the JSON object
        start_idx = response.find('{')
        end_idx = response.rfind('}')
        
        if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
            response = response[start_idx:end_idx + 1]
        
        # Fix common JSON issues
        # Fix unquoted property names (but be careful not to break already quoted ones)
        response = re.sub(r'(?<!")\b(\w+)\s*:', r'"\1":', response)
        
        # Fix missing commas between properties
        # Look for pattern: "property": value followed by newline and another "property"
        response = re.sub(r'("[^"]+"\s*:\s*(?:"[^"]*"|\d+(?:\.\d+)?|true|false|null))\s*\n\s*("[^"]+"\s*:)', r'\1,\n    \2', response)
        
        # Fix missing commas in objects
        response = re.sub(r'}\s*\n\s*"', '},\n    "', response)
        
        # Fix trailing commas
        response = re.sub(r',\s*}', '}', response)
        response = re.sub(r',\s*]', ']', response)
        
        # Fix incomplete JSON structures - specifically handle incomplete line_items arrays
        # Look for incomplete objects in arrays (missing closing braces)
        response = self._fix_incomplete_json_objects(response)
        
        return response
    
    def _fix_incomplete_json_objects(self, json_str: str) -> str:
        """Fix incomplete JSON objects, particularly in arrays"""
        import re
        
        # Handle the specific malformed pattern from the error:
        # "total": 65.0\n        ,\n        {
        # This should become:
        # "total": 65.0\n        },\n        {
        
        # First, fix the specific pattern where there's a missing closing brace before a comma
        # Look for: property: value followed by whitespace, comma, whitespace, opening brace
        lines = json_str.split('\n')
        fixed_lines = []
        
        i = 0
        while i < len(lines):
            line = lines[i]
            
            # Check if this line contains a property: value pattern
            if re.match(r'\s*"[^"]+"\s*:\s*(?:\d+(?:\.\d+)?|"[^"]*"|null|true|false)\s*$', line):
                # Check if the next line is just a comma
                if i + 1 < len(lines) and re.match(r'\s*,\s*$', lines[i + 1]):
                    # Check if the line after that starts a new object
                    if i + 2 < len(lines) and re.match(r'\s*\{\s*$', lines[i + 2]):
                        # This is the malformed pattern - fix it
                        fixed_lines.append(line)
                        fixed_lines.append(lines[i + 1].replace(',', '},'))  # Add closing brace before comma
                        fixed_lines.append(lines[i + 2])  # Keep the opening brace
                        i += 3
                        continue
            
            fixed_lines.append(line)
            i += 1
        
        json_str = '\n'.join(fixed_lines)
        
        # Handle truncated content (like "CHEESE TOAST S/W",...)
        # Remove incomplete trailing content after the last complete object
        json_str = re.sub(r',\s*\{\s*"[^"]*"\s*:\s*"[^"]*"\s*\.\.\..*$', '', json_str, flags=re.DOTALL)
        
        # Count braces and brackets to ensure they're balanced
        open_braces = json_str.count('{')
        close_braces = json_str.count('}')
        open_brackets = json_str.count('[')
        close_brackets = json_str.count(']')
        
        # Add missing closing braces
        if open_braces > close_braces:
            json_str += '}' * (open_braces - close_braces)
        
        # Add missing closing brackets
        if open_brackets > close_brackets:
            json_str += ']' * (open_brackets - close_brackets)
        
        # Clean up formatting issues
        json_str = re.sub(r',\s*,', ',', json_str)  # Remove duplicate commas
        json_str = re.sub(r',\s*}', '}', json_str)   # Remove trailing commas before closing braces
        json_str = re.sub(r',\s*]', ']', json_str)   # Remove trailing commas before closing brackets
        
        return json_str
    
    def extract_invoice_data(self, document_bytes: bytes, mime_type: str = 'image/jpeg') -> Dict[str, Any]:
        """Extract structured data from invoice image or PDF"""
        prompt = """
Extract structured data from this invoice document. Be precise and only extract information that is clearly visible.

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

IMPORTANT: 
- Use null for missing string fields
- Use 0.0 for missing numeric fields
- Use proper JSON syntax with double quotes
- Do not include any text before or after the JSON object
- For amounts, use numeric values without currency symbols
"""
        
        max_retries = 2
        pdf_fallback_attempted = False
        
        for attempt in range(max_retries + 1):
            try:
                # Use appropriate processing method based on mime type
                if mime_type == 'application/pdf' and not pdf_fallback_attempted:
                    try:
                        response = self.process_pdf_with_text(document_bytes, prompt)
                    except Exception as pdf_error:
                        # Check if it's a Gemini processing error that might benefit from fallback
                        error_str = str(pdf_error).lower()
                        if any(keyword in error_str for keyword in ["unable to process", "invalid_argument", "400", "image"]):
                            logger.warning(f"PDF processing failed with Gemini error: {str(pdf_error)}")
                            logger.info("Attempting PDF-to-image fallback...")
                            pdf_fallback_attempted = True
                            
                            # Try to convert PDF to image as fallback
                            try:
                                image_bytes = self._convert_pdf_to_image(document_bytes)
                                response = self.process_image_with_text(image_bytes, prompt, 'image/png')
                                logger.info("PDF-to-image fallback successful")
                            except Exception as fallback_error:
                                logger.error(f"PDF-to-image fallback failed: {str(fallback_error)}")
                                raise pdf_error  # Re-raise original PDF error
                        else:
                            raise pdf_error
                elif mime_type == 'application/pdf' and pdf_fallback_attempted:
                    # If we've already attempted fallback, use image processing
                    try:
                        image_bytes = self._convert_pdf_to_image(document_bytes)
                        response = self.process_image_with_text(image_bytes, prompt, 'image/png')
                    except Exception as fallback_error:
                        logger.error(f"PDF-to-image conversion failed: {str(fallback_error)}")
                        raise
                else:
                    response = self.process_image_with_text(document_bytes, prompt, mime_type)
                    
                cleaned_response = self._clean_json_response(response)
                
                # Log the cleaned response for debugging
                logger.debug(f"Cleaned JSON response (attempt {attempt + 1}): {cleaned_response[:500]}...")
                
                # Try to parse the JSON
                parsed_data = json.loads(cleaned_response)
                
                # Validate required fields and set defaults
                default_data = {
                    "vendor_name": None,
                    "vendor_address": None,
                    "vendor_email": None,
                    "vendor_phone": None,
                    "invoice_number": None,
                    "invoice_date": None,
                    "due_date": None,
                    "total_amount": 0.0,
                    "currency": None,
                    "tax_amount": 0.0,
                    "subtotal": 0.0,
                    "line_items": [],
                    "confidence_score": 0.0
                }
                
                # Merge with defaults
                for key, default_value in default_data.items():
                    if key not in parsed_data:
                        parsed_data[key] = default_value
                
                # Validate line_items structure
                if "line_items" in parsed_data and isinstance(parsed_data["line_items"], list):
                    validated_items = []
                    for item in parsed_data["line_items"]:
                        if isinstance(item, dict):
                            # Ensure each line item has required fields
                            validated_item = {
                                "description": item.get("description", ""),
                                "quantity": float(item.get("quantity", 0.0)),
                                "unit_price": float(item.get("unit_price", 0.0)),
                                "total": float(item.get("total", 0.0))
                            }
                            validated_items.append(validated_item)
                    parsed_data["line_items"] = validated_items
                
                logger.info(f"Successfully parsed invoice data on attempt {attempt + 1}")
                return parsed_data
                
            except json.JSONDecodeError as e:
                logger.warning(f"JSON parsing failed on attempt {attempt + 1}: {str(e)}")
                if attempt < max_retries:
                    logger.info(f"Retrying invoice extraction (attempt {attempt + 2}/{max_retries + 1})...")
                    # Modify prompt for retry to be more explicit about JSON format
                    prompt += "\n\nIMPORTANT: Ensure the JSON is complete and properly formatted with all opening braces { matched by closing braces }."
                    continue
                else:
                    logger.error(f"Failed to parse invoice data after {max_retries + 1} attempts")
                    logger.error(f"Final raw response: {response[:1000] if 'response' in locals() else 'No response'}...")
                    return {
                        "error": "Failed to parse response after multiple attempts", 
                        "confidence_score": 0.0,
                        "vendor_name": None,
                        "total_amount": 0.0,
                        "line_items": []
                    }
            except Exception as e:
                logger.error(f"Invoice extraction failed on attempt {attempt + 1}: {str(e)}")
                if attempt < max_retries:
                    # For PDF processing errors, try the fallback on next attempt
                    if mime_type == 'application/pdf' and not pdf_fallback_attempted and ("Unable to process input image" in str(e) or "INVALID_ARGUMENT" in str(e)):
                        pdf_fallback_attempted = True
                        logger.info("Will attempt PDF-to-image fallback on next retry...")
                    continue
                else:
                    raise
    
    def extract_contact_data(self, image_bytes: bytes, mime_type: str = 'image/jpeg') -> Dict[str, Any]:
        """Extract contact information from business card image"""
        prompt = """
Extract contact information from this business card image. Be precise and only extract information that is clearly visible.

Return ONLY a valid JSON object with this exact structure:
{
    "name": "string",
    "company": "string",
    "title": "string",
    "email": "string",
    "phone": "string",
    "mobile": "string",
    "address": "string",
    "website": "string",
    "linkedin": "string",
    "confidence_score": "float between 0 and 1"
}

If any field is not clearly visible, use null.
"""
        
        max_retries = 2
        pdf_fallback_attempted = False
        
        for attempt in range(max_retries + 1):
            try:
                response = self.process_image_with_text(image_bytes, prompt, mime_type)
                cleaned_response = self._clean_json_response(response)
                logger.debug(f"Cleaned business card response: {cleaned_response}")
                parsed_data = json.loads(cleaned_response)
                
                # Validate and set defaults
                default_data = {
                    "name": None,
                    "company": None,
                    "title": None,
                    "email": None,
                    "phone": None,
                    "mobile": None,
                    "address": None,
                    "website": None,
                    "linkedin": None,
                    "confidence_score": 0.0
                }
                
                for key, default_value in default_data.items():
                    if key not in parsed_data:
                        parsed_data[key] = default_value
                
                logger.info(f"Successfully parsed contact data on attempt {attempt + 1}")
                return parsed_data
                
            except json.JSONDecodeError as e:
                logger.warning(f"JSON parsing failed on attempt {attempt + 1}: {str(e)}")
                if attempt < max_retries:
                    logger.info(f"Retrying contact extraction (attempt {attempt + 2}/{max_retries + 1})...")
                    # Modify prompt for retry to be more explicit about JSON format
                    prompt += "\n\nIMPORTANT: Ensure the JSON is complete and properly formatted with all opening braces { matched by closing braces }."
                    continue
                else:
                    logger.error(f"Failed to parse contact data after {max_retries + 1} attempts")
                    logger.error(f"Final raw response: {response[:1000] if 'response' in locals() else 'No response'}...")
                    return {
                        "error": "Failed to parse response after multiple attempts", 
                        "confidence_score": 0.0,
                        "name": None,
                        "company": None
                    }
            except Exception as e:
                logger.error(f"Contact extraction failed on attempt {attempt + 1}: {str(e)}")
                if attempt < max_retries:
                    # For PDF processing errors, try the fallback on next attempt
                    if mime_type == 'application/pdf' and not pdf_fallback_attempted and ("Unable to process input image" in str(e) or "INVALID_ARGUMENT" in str(e)):
                        pdf_fallback_attempted = True
                        logger.info("Will attempt PDF-to-image fallback on next retry...")
                    continue
                else:
                    raise
    
    def extract_receipt_data(self, image_bytes: bytes, mime_type: str = 'image/jpeg') -> Dict[str, Any]:
        """Extract expense data from receipt image"""
        prompt = """
Extract expense information from this receipt image. Be precise and only extract information that is clearly visible.

Return ONLY a valid JSON object with this exact structure:
{
    "merchant_name": "string",
    "merchant_address": "string",
    "date": "YYYY-MM-DD",
    "time": "HH:MM",
    "total_amount": "float",
    "currency": "string",
    "tax_amount": "float",
    "payment_method": "string",
    "category": "string (meals, travel, office_supplies, etc.)",
    "items": [
        {
            "description": "string",
            "amount": "float"
        }
    ],
    "confidence_score": "float between 0 and 1"
}

If any field is not clearly visible, use null. For amounts, use numeric values without currency symbols.
"""
        
        try:
            response = self.process_image_with_text(image_bytes, prompt, mime_type)
            response = response.strip()
            if response.startswith('```json'):
                response = response[7:]
            if response.endswith('```'):
                response = response[:-3]
            
            return json.loads(response)
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse receipt data response: {str(e)}")
            return {"error": "Failed to parse response", "confidence_score": 0.0}
        except Exception as e:
            logger.error(f"Receipt extraction failed: {str(e)}")
            raise
    
    def generate_qa_response(self, question: str, context: str, odoo_context: Dict = None) -> str:
        """Generate Q&A response with Odoo context"""
        odoo_info = ""
        if odoo_context:
            odoo_info = f"""
Odoo System Context:
- User: {odoo_context.get('user', {}).get('name', 'Unknown')}
- Company: {odoo_context.get('user', {}).get('company_id', ['Unknown'])[1] if odoo_context.get('user', {}).get('company_id') else 'Unknown'}
- Database: {odoo_context.get('database', 'Unknown')}
"""
        
        prompt = f"""
You are an expert Odoo assistant. Answer the user's question using the provided context and your knowledge of Odoo.

{odoo_info}

User Question: {question}

Relevant Context:
{context}

Provide a helpful, accurate response. If the question is about navigation, provide step-by-step instructions.
If the question is about data lookup, format the response clearly.
If you're not certain about something, say so rather than guessing.

Response:
"""
        
        return self.generate_text(prompt)
    
    def _convert_pdf_to_image(self, pdf_bytes: bytes) -> bytes:
        """Convert PDF to image as fallback when direct PDF processing fails"""
        try:
            import fitz  # PyMuPDF
            from io import BytesIO
            
            # Open PDF from bytes
            pdf_document = fitz.open(stream=pdf_bytes, filetype="pdf")
            
            # Get first page
            page = pdf_document[0]
            
            # Convert to image (PNG)
            mat = fitz.Matrix(2.0, 2.0)  # 2x zoom for better quality
            pix = page.get_pixmap(matrix=mat)
            
            # Convert to bytes
            img_bytes = pix.tobytes("png")
            
            pdf_document.close()
            return img_bytes
            
        except ImportError:
            logger.error("PyMuPDF (fitz) not installed. Cannot convert PDF to image.")
            raise Exception("PDF to image conversion requires PyMuPDF. Install with: pip install PyMuPDF")
        except Exception as e:
            logger.error(f"PDF to image conversion failed: {str(e)}")
            raise
    
    def test_connection(self) -> Dict[str, Any]:
        """Test the Gemini API connection"""
        try:
            if not self.initialize():
                return {'status': 'failed', 'error': 'Initialization failed'}
            
            test_response = self.generate_text("Hello, this is a test. Please respond with 'Test successful'.")
            
            return {
                'status': 'success',
                'model': self.model_name,
                'vision_model': self.vision_model,
                'test_response': test_response
            }
        except Exception as e:
            return {'status': 'error', 'error': str(e)}

    def clean_linkedin_profile(self, raw_profile: dict) -> dict:
        """Use Gemini to clean and map raw LinkedIn profile data to Odoo lead fields."""
        
        try:
            # Log the raw profile for debugging
            logger.debug(f"Raw LinkedIn profile keys: {list(raw_profile.keys()) if isinstance(raw_profile, dict) else 'Not a dict'}")
            
            # Truncate very large profile data to avoid overwhelming Gemini
            profile_str = str(raw_profile)
            if len(profile_str) > 3000:
                logger.info(f"Truncating large LinkedIn profile data ({len(profile_str)} chars -> 3000 chars)")
                profile_str = profile_str[:3000] + "... [truncated]"
                raw_profile = {"truncated_data": profile_str}
            
            prompt = f"""
You are an expert CRM assistant. Given the following raw LinkedIn profile data (as a Python dictionary), extract and clean the information to fit the following Odoo CRM lead fields:
- name (full name)
- company (current company)
- title (current job title)
- email (if available)
- phone (if available)
- mobile (if available)
- website (if available)
- address (city, country)
- linkedin (profile URL)
- confidence_score (float between 0 and 1, based on completeness and certainty)

Return ONLY a valid JSON object with this exact structure:
{{
    "name": "string",
    "company": "string",
    "title": "string",
    "email": "string",
    "phone": "string",
    "mobile": "string",
    "website": "string",
    "address": "string",
    "linkedin": "string",
    "confidence_score": 0.95
}}

If any field is missing or not available, use null. Do not include any text before or after the JSON object.

Raw LinkedIn profile data:
{raw_profile}
"""

            logger.debug(f"Sending LinkedIn profile cleaning request to Gemini (prompt length: {len(prompt)})")
            response = self.generate_text(prompt)
            
            if not response or not response.strip():
                logger.error("Gemini returned empty response for LinkedIn profile cleaning")
                return {"error": "Empty response from Gemini", "confidence_score": 0.0}
            
            logger.debug(f"Raw Gemini response for LinkedIn profile: {response[:200]}...")
            
            cleaned_response = self._clean_json_response(response)
            logger.debug(f"Cleaned LinkedIn profile response: {cleaned_response[:200]}...")
            
            if not cleaned_response.strip():
                logger.error("Cleaned response is empty")
                return {"error": "Cleaned response is empty", "confidence_score": 0.0}
            
            parsed_data = json.loads(cleaned_response)
            
            # Validate and set defaults
            default_data = {
                "name": None,
                "company": None,
                "title": None,
                "email": None,
                "phone": None,
                "mobile": None,
                "website": None,
                "address": None,
                "linkedin": None,
                "confidence_score": 0.0
            }
            for key, default_value in default_data.items():
                if key not in parsed_data:
                    parsed_data[key] = default_value
                    
            logger.info(f"Successfully parsed LinkedIn profile data with confidence: {parsed_data.get('confidence_score', 0.0)}")
            return parsed_data
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse cleaned LinkedIn profile: {str(e)}")
            logger.error(f"Raw response was: {response if 'response' in locals() else 'No response'}")
            logger.error(f"Cleaned response was: {cleaned_response if 'cleaned_response' in locals() else 'No cleaned response'}")
            return {"error": "Failed to parse JSON response", "confidence_score": 0.0}
        except Exception as e:
            logger.error(f"LinkedIn profile cleaning failed: {str(e)}")
            return {"error": f"Profile cleaning failed: {str(e)}", "confidence_score": 0.0}

# Global client instance
gemini_client = GeminiClient()

# Auto-initialize the client
if not gemini_client.initialize():
    logger.warning("Failed to initialize Gemini client. Check your API key configuration.")