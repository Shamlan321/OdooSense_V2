#!/usr/bin/env python3
"""
Robust JSON Recovery Utilities for LLM Responses

This module provides advanced JSON parsing and recovery capabilities
for handling inconsistent LLM responses in data lookup operations.
"""

import json
import re
import logging
from typing import Dict, Any, Optional, Union
from gemini_client import GeminiClient

logger = logging.getLogger(__name__)

class JSONRecoveryEngine:
    """
    Advanced JSON recovery engine that can handle various LLM response formats
    and attempt multiple recovery strategies when JSON parsing fails.
    """
    
    def __init__(self, gemini_client: GeminiClient):
        self.gemini_client = gemini_client
        
    def extract_and_parse_json(self, raw_response: str, context: str = "data_lookup") -> Dict[str, Any]:
        """
        Main entry point for robust JSON extraction and parsing.
        Tries multiple strategies in order of reliability.
        
        Args:
            raw_response: Raw LLM response text
            context: Context for error handling (e.g., "data_lookup", "analysis")
            
        Returns:
            Parsed JSON dict or error dict with fallback data
        """
        if not raw_response or not raw_response.strip():
            logger.warning(f"Empty response received for {context}")
            return self._create_fallback_response("Empty response from AI service")
        
        logger.debug(f"Attempting JSON extraction from response: {raw_response[:200]}...")
        
        # Strategy 1: Direct JSON parsing (best case)
        result = self._try_direct_json_parse(raw_response)
        if result:
            logger.debug("Strategy 1 (direct parsing) succeeded")
            return result
            
        # Strategy 2: Clean and parse JSON
        result = self._try_cleaned_json_parse(raw_response)
        if result:
            logger.debug("Strategy 2 (cleaned parsing) succeeded")
            return result
            
        # Strategy 3: Extract JSON from markdown/mixed content
        result = self._try_extract_json_from_text(raw_response)
        if result:
            logger.debug("Strategy 3 (extraction from text) succeeded")
            return result
            
        # Strategy 4: Progressive JSON reconstruction
        result = self._try_progressive_json_reconstruction(raw_response)
        if result:
            logger.debug("Strategy 4 (progressive reconstruction) succeeded")
            return result
            
        # Strategy 5: LLM-assisted JSON correction
        result = self._try_llm_assisted_correction(raw_response, context)
        if result:
            logger.debug("Strategy 5 (LLM-assisted correction) succeeded")
            return result
            
        # Strategy 6: Pattern-based extraction for common formats
        result = self._try_pattern_based_extraction(raw_response, context)
        if result:
            logger.debug("Strategy 6 (pattern-based extraction) succeeded")
            return result
            
        # Final fallback: Create smart default based on context
        logger.warning(f"All JSON recovery strategies failed for {context}. Creating intelligent fallback.")
        return self._create_intelligent_fallback(raw_response, context)
    
    def _try_direct_json_parse(self, response: str) -> Optional[Dict[str, Any]]:
        """Try to parse response directly as JSON"""
        try:
            return json.loads(response.strip())
        except (json.JSONDecodeError, ValueError):
            return None
    
    def _try_cleaned_json_parse(self, response: str) -> Optional[Dict[str, Any]]:
        """Try to clean common JSON issues and parse"""
        try:
            cleaned = self._clean_json_response(response)
            return json.loads(cleaned)
        except (json.JSONDecodeError, ValueError):
            return None
    
    def _clean_json_response(self, response: str) -> str:
        """Enhanced version of JSON cleaning with more edge cases"""
        cleaned = response.strip()
        
        # Remove markdown code blocks
        if cleaned.startswith('```json'):
            cleaned = cleaned[7:]
        elif cleaned.startswith('```'):
            cleaned = cleaned[3:]
        if cleaned.endswith('```'):
            cleaned = cleaned[:-3]
        cleaned = cleaned.strip()
        
        # Remove common prefixes/suffixes
        prefixes_to_remove = [
            'Here is the JSON:',
            'Here\'s the JSON:',
            'JSON:',
            'Response:',
            'Result:',
            'Output:'
        ]
        for prefix in prefixes_to_remove:
            if cleaned.lower().startswith(prefix.lower()):
                cleaned = cleaned[len(prefix):].strip()
        
        # Fix common JSON issues
        import re
        
        # Remove trailing commas
        cleaned = re.sub(r',\s*}', '}', cleaned)
        cleaned = re.sub(r',\s*]', ']', cleaned)
        
        # Remove duplicate commas
        cleaned = re.sub(r',\s*,+', ',', cleaned)
        
        # Fix missing quotes around keys
        cleaned = re.sub(r'(\w+):', r'"\1":', cleaned)
        
        # Handle incomplete JSON structures
        open_braces = cleaned.count('{')
        close_braces = cleaned.count('}')
        if open_braces > close_braces:
            cleaned += '}' * (open_braces - close_braces)
        
        open_brackets = cleaned.count('[')
        close_brackets = cleaned.count(']')
        if open_brackets > close_brackets:
            cleaned += ']' * (open_brackets - close_brackets)
            
        return cleaned.strip()
    
    def _try_extract_json_from_text(self, response: str) -> Optional[Dict[str, Any]]:
        """Extract JSON from mixed text content"""
        import re
        
        # Look for JSON-like structures in the text
        json_patterns = [
            r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}',  # Nested objects
            r'\{[^{}]+\}',  # Simple objects
        ]
        
        for pattern in json_patterns:
            matches = re.findall(pattern, response, re.DOTALL)
            for match in matches:
                try:
                    cleaned = self._clean_json_response(match)
                    parsed = json.loads(cleaned)
                    if isinstance(parsed, dict) and len(parsed) > 0:
                        return parsed
                except (json.JSONDecodeError, ValueError):
                    continue
        
        return None
    
    def _try_progressive_json_reconstruction(self, response: str) -> Optional[Dict[str, Any]]:
        """Try to progressively build valid JSON from partial response"""
        lines = response.strip().split('\n')
        json_lines = []
        in_json = False
        brace_count = 0
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            # Detect JSON start
            if '{' in line and not in_json:
                in_json = True
                json_lines.append(line)
                brace_count += line.count('{') - line.count('}')
            elif in_json:
                json_lines.append(line)
                brace_count += line.count('{') - line.count('}')
                
                # Check if JSON is complete
                if brace_count <= 0:
                    break
        
        if json_lines:
            reconstructed = '\n'.join(json_lines)
            try:
                cleaned = self._clean_json_response(reconstructed)
                return json.loads(cleaned)
            except (json.JSONDecodeError, ValueError):
                pass
                
        return None
    
    def _try_llm_assisted_correction(self, response: str, context: str) -> Optional[Dict[str, Any]]:
        """Use LLM to fix malformed JSON"""
        try:
            correction_prompt = f"""
The following text should be valid JSON for {context}, but it has formatting issues. 
Please fix it and return ONLY valid JSON, no explanations:

{response[:1000]}

Expected JSON format for {context}:
{{
    "model": "model_name",
    "domain": [["field", "operator", "value"]],
    "fields": ["field1", "field2"],
    "limit": 50,
    "query_type": "search"
}}

Return only the corrected JSON:"""

            corrected_response = self.gemini_client.generate_text(correction_prompt)
            if corrected_response:
                return self._try_cleaned_json_parse(corrected_response)
                
        except Exception as e:
            logger.debug(f"LLM-assisted correction failed: {e}")
            
        return None
    
    def _try_pattern_based_extraction(self, response: str, context: str) -> Optional[Dict[str, Any]]:
        """Extract data using patterns specific to the context"""
        if context == "data_lookup":
            return self._extract_data_lookup_pattern(response)
        elif context == "analysis":
            return self._extract_analysis_pattern(response)
        return None
    
    def _extract_data_lookup_pattern(self, response: str) -> Optional[Dict[str, Any]]:
        """Extract data lookup parameters using pattern matching"""
        result = {
            "model": None,
            "domain": [],
            "fields": [],
            "limit": 50,
            "query_type": "search"
        }
        
        # Extract model name
        model_patterns = [
            r'model["\s]*:?\s*["\s]*([a-z._]+)',
            r'"([a-z._]+)"\s*model',
            r'search\s+([a-z._]+)',
            r'from\s+([a-z._]+)'
        ]
        
        response_lower = response.lower()
        for pattern in model_patterns:
            match = re.search(pattern, response_lower)
            if match:
                result["model"] = match.group(1)
                break
        
        # Try to extract common models from text
        if not result["model"]:
            model_keywords = {
                'invoice': 'account.move',
                'customer': 'res.partner',
                'product': 'product.template',
                'sale': 'sale.order',
                'purchase': 'purchase.order',
                'employee': 'hr.employee',
                'lead': 'crm.lead'
            }
            
            for keyword, model in model_keywords.items():
                if keyword in response_lower:
                    result["model"] = model
                    break
        
        # Extract filters/domain from natural language
        if 'open' in response_lower and 'invoice' in response_lower:
            result["domain"] = [["state", "=", "posted"], ["payment_state", "!=", "paid"]]
            result["model"] = "account.move"
            result["fields"] = ["name", "partner_id", "amount_total", "date", "state", "payment_state"]
        
        # Only return if we found a model
        if result["model"]:
            return result
            
        return None
    
    def _extract_analysis_pattern(self, response: str) -> Optional[Dict[str, Any]]:
        """Extract analysis results using pattern matching"""
        # This would be used for other types of analysis
        return None
    
    def _create_fallback_response(self, error_message: str) -> Dict[str, Any]:
        """Create a basic fallback response"""
        return {
            "error": error_message,
            "fallback": True,
            "model": None,
            "domain": [],
            "fields": [],
            "limit": 50,
            "query_type": "search"
        }
    
    def _create_intelligent_fallback(self, response: str, context: str) -> Dict[str, Any]:
        """Create an intelligent fallback based on response content and context"""
        if context == "data_lookup":
            # Try to infer what the user wanted based on keywords
            response_lower = response.lower()
            
            # Common queries and their mappings
            if any(word in response_lower for word in ['invoice', 'bill', 'payment']):
                return {
                    "model": "account.move",
                    "domain": [["move_type", "=", "out_invoice"]],
                    "fields": ["name", "partner_id", "amount_total", "date", "state"],
                    "limit": 20,
                    "query_type": "search",
                    "fallback": True,
                    "fallback_reason": "Inferred from invoice-related keywords"
                }
            elif any(word in response_lower for word in ['customer', 'partner', 'contact']):
                return {
                    "model": "res.partner",
                    "domain": [["is_company", "=", False], ["customer_rank", ">", 0]],
                    "fields": ["name", "email", "phone", "city", "country_id"],
                    "limit": 20,
                    "query_type": "search",
                    "fallback": True,
                    "fallback_reason": "Inferred from customer-related keywords"
                }
            elif any(word in response_lower for word in ['product', 'item', 'stock']):
                return {
                    "model": "product.template",
                    "domain": [["sale_ok", "=", True]],
                    "fields": ["name", "list_price", "categ_id", "qty_available"],
                    "limit": 20,
                    "query_type": "search",
                    "fallback": True,
                    "fallback_reason": "Inferred from product-related keywords"
                }
        
        # Generic fallback
        return {
            "error": "Could not parse response or infer intent",
            "raw_response": response[:200] + "..." if len(response) > 200 else response,
            "fallback": True,
            "suggested_action": "Please rephrase your query more specifically"
        } 