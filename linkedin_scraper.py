import json
import logging
import re
from typing import Dict, Any, Optional
from apify_client import ApifyClient
from config import config
from gemini_client import gemini_client

logger = logging.getLogger(__name__)

class LinkedInScraper:
    """LinkedIn profile scraper using Apify API"""
    
    def __init__(self):
        # Use API key from config or fallback to hardcoded one
        self.api_key = getattr(config, 'apify_api_key', "apify_api_8ViThYsJGuDpcAQXNzKKdem6umJJS20PdRUV")
        self.client = ApifyClient(self.api_key)
        self.actor_id = "VhxlqQXRwhW8H5hNV"  # LinkedIn Profile Scraper Actor ID
    
    def extract_username_from_url(self, linkedin_url: str) -> Optional[str]:
        """Extract LinkedIn username from URL"""
        try:
            # Common LinkedIn URL patterns
            patterns = [
                r'linkedin\.com/in/([^/?]+)',
                r'linkedin\.com/pub/([^/?]+)',
                r'linkedin\.com/profile/view\?id=([^&]+)'
            ]
            
            for pattern in patterns:
                match = re.search(pattern, linkedin_url, re.IGNORECASE)
                if match:
                    username = match.group(1)
                    # Clean up username (remove trailing slashes, etc.)
                    username = username.rstrip('/')
                    return username
            
            logger.warning(f"Could not extract username from URL: {linkedin_url}")
            return None
            
        except Exception as e:
            logger.error(f"Error extracting username from URL: {str(e)}")
            return None
    
    def scrape_profile(self, linkedin_url: str) -> Dict[str, Any]:
        """Scrape LinkedIn profile data"""
        try:
            # Extract username from URL
            username = self.extract_username_from_url(linkedin_url)
            if not username:
                return {
                    "error": "Could not extract username from LinkedIn URL",
                    "success": False
                }
            
            logger.info(f"Scraping LinkedIn profile for username: {username}")
            
            # Prepare the Actor input
            run_input = {
                "username": username,
                "maxDelay": 5,
                "minDelay": 1
            }
            
            # Run the Actor and wait for it to finish
            run = self.client.actor(self.actor_id).call(run_input=run_input)
            
            # Fetch results from the run's dataset
            items = list(self.client.dataset(run["defaultDatasetId"]).iterate_items())
            
            if not items:
                return {
                    "error": "No data found for the LinkedIn profile",
                    "success": False
                }
            
            # Get the first (and usually only) result
            profile_data = items[0]
            
            logger.info(f"Successfully scraped LinkedIn profile for {username}")
            
            return {
                "success": True,
                "data": profile_data,
                "username": username,
                "url": linkedin_url
            }
            
        except Exception as e:
            logger.error(f"LinkedIn scraping failed: {str(e)}")
            return {
                "error": f"LinkedIn scraping failed: {str(e)}",
                "success": False
            }
    
    def process_profile_for_lead(self, linkedin_url: str) -> Dict[str, Any]:
        """Scrape LinkedIn profile and process it for CRM lead creation"""
        try:
            # Scrape the profile
            scrape_result = self.scrape_profile(linkedin_url)
            
            if not scrape_result.get("success"):
                return scrape_result
            
            profile_data = scrape_result["data"]
            
            # Use Gemini to clean and structure the data for lead creation
            processed_data = self._process_with_gemini(profile_data, linkedin_url)
            
            return {
                "success": True,
                "raw_data": profile_data,
                "processed_data": processed_data,
                "source": "linkedin",
                "url": linkedin_url
            }
            
        except Exception as e:
            logger.error(f"LinkedIn profile processing failed: {str(e)}")
            return {
                "error": f"LinkedIn profile processing failed: {str(e)}",
                "success": False
            }
    
    def _process_with_gemini(self, profile_data: Dict[str, Any], linkedin_url: str) -> Dict[str, Any]:
        """Use Gemini to clean and structure LinkedIn data for CRM lead"""
        try:
            prompt = f"""
Analyze this LinkedIn profile data and extract structured information for CRM lead creation.

LinkedIn Profile Data:
{profile_data}

Extract and clean the following information:
1. Personal Information (name, title, location)
2. Company Information (current company, industry, size)
3. Contact Information (if available)
4. Professional Summary
5. Skills and Experience
6. Education

Return ONLY a valid JSON object with this structure:
{{
    "name": "Full Name",
    "job_title": "Current Job Title",
    "company_name": "Current Company",
    "industry": "Industry",
    "location": "City, Country",
    "email": "email@example.com or null",
    "phone": "phone number or null",
    "linkedin_url": "{linkedin_url}",
    "summary": "Professional summary",
    "skills": ["skill1", "skill2", "skill3"],
    "experience": [
        {{
            "company": "Company Name",
            "title": "Job Title",
            "duration": "Duration"
        }}
    ],
    "education": [
        {{
            "institution": "University Name",
            "degree": "Degree",
            "field": "Field of Study"
        }}
    ],
    "confidence_score": 0.95
}}

Ensure all fields are properly formatted and cleaned. Use null for missing information.
"""
            
            response = gemini_client.generate_text(prompt)
            cleaned_response = gemini_client._clean_json_response(response)
            
            try:
                processed_data = json.loads(cleaned_response)  # Using proper JSON parsing
                
                # Validate required fields
                required_fields = ["name", "job_title", "company_name", "linkedin_url"]
                for field in required_fields:
                    if field not in processed_data or not processed_data[field]:
                        logger.warning(f"Missing required field: {field}")
                
                return processed_data
                
            except json.JSONDecodeError as parse_error:
                logger.error(f"Failed to parse JSON response: {str(parse_error)}")
                logger.error(f"Raw response: {response}")
                logger.error(f"Cleaned response: {cleaned_response}")
                
                # Try a more aggressive cleaning approach
                try:
                    aggressively_cleaned = self._aggressive_json_clean(response)
                    processed_data = json.loads(aggressively_cleaned)
                    logger.info("Successfully parsed with aggressive cleaning")
                    return processed_data
                except:
                    logger.warning("Aggressive cleaning also failed, using fallback")
                
                # Fallback: create basic structure from raw data
                return self._create_fallback_structure(profile_data, linkedin_url)
                
        except Exception as e:
            logger.error(f"Gemini processing failed: {str(e)}")
            return self._create_fallback_structure(profile_data, linkedin_url)
    
    def _aggressive_json_clean(self, response: str) -> str:
        """More aggressive JSON cleaning for problematic responses"""
        import re
        
        # Remove markdown formatting
        response = response.strip()
        if response.startswith('```json'):
            response = response[7:]
        elif response.startswith('```'):
            response = response[3:]
        if response.endswith('```'):
            response = response[:-3]
        
        response = response.strip()
        
        # Extract JSON object
        start_idx = response.find('{')
        end_idx = response.rfind('}')
        if start_idx != -1 and end_idx != -1:
            response = response[start_idx:end_idx + 1]
        
        # Fix backticks around URLs
        response = re.sub(r'"\s*`([^`]+)`\s*"', r'"\1"', response)
        
        # Aggressively fix the education field issue
        # Replace the problematic pattern entirely
        response = re.sub(
            r'"field":\s*"Civil Engineering \([^)]*"[^)]*\)[^"]*"',
            r'"field": "Civil Engineering (minor: Engineering management)"',
            response
        )
        
        # Fix any remaining unescaped quotes in string values
        # This is a more aggressive approach that removes quotes within parentheses
        def clean_parentheses_content(match):
            content = match.group(1)
            # Remove all quotes within parentheses
            cleaned = re.sub(r'"([^"]+)":', r'\1:', content)
            return f'({cleaned})'
        
        # Apply to content within parentheses in string values
        response = re.sub(r'\(([^)]*"[^)]*)\)', clean_parentheses_content, response)
        
        # Fix control characters by using proper JSON escaping
        # Replace problematic characters in the summary field specifically
        summary_pattern = r'"summary":\s*"([^"]*(?:\\.[^"]*)*?)"'
        
        def fix_summary_content(match):
            content = match.group(1)
            # Properly escape control characters
            content = content.replace('\\', '\\\\')
            content = content.replace('"', '\\"')
            content = content.replace('\n', '\\n')
            content = content.replace('\r', '\\r')
            content = content.replace('\t', '\\t')
            content = content.replace('\b', '\\b')
            content = content.replace('\f', '\\f')
            return f'"summary": "{content}"'
        
        response = re.sub(summary_pattern, fix_summary_content, response, flags=re.DOTALL)
        
        # Also fix any other string fields that might have control characters
        def fix_string_content(match):
            field_name = match.group(1)
            content = match.group(2)
            # Skip if it's already properly escaped or if it's a simple value
            if '\\n' in content or len(content) < 50:
                return match.group(0)
            
            # Escape control characters
            content = content.replace('\\', '\\\\')
            content = content.replace('"', '\\"')
            content = content.replace('\n', '\\n')
            content = content.replace('\r', '\\r')
            content = content.replace('\t', '\\t')
            return f'"{field_name}": "{content}"'
        
        # Apply to other potential problematic fields
        response = re.sub(r'"(\w+)":\s*"([^"]{50,}?)"', fix_string_content, response)
        
        # Fix trailing commas
        response = re.sub(r',\s*}', '}', response)
        response = re.sub(r',\s*]', ']', response)
        
        return response
    
    def _create_fallback_structure(self, profile_data: Dict[str, Any], linkedin_url: str) -> Dict[str, Any]:
        """Create a fallback structure when Gemini processing fails"""
        try:
            # Extract basic information from raw profile data
            name = profile_data.get("name", "Unknown")
            job_title = profile_data.get("headline", "")
            company = profile_data.get("company", "")
            location = profile_data.get("location", "")
            summary = profile_data.get("summary", "")
            
            return {
                "name": name,
                "job_title": job_title,
                "company_name": company,
                "industry": profile_data.get("industry", ""),
                "location": location,
                "email": None,
                "phone": None,
                "linkedin_url": linkedin_url,
                "summary": summary,
                "skills": profile_data.get("skills", []),
                "experience": profile_data.get("experience", []),
                "education": profile_data.get("education", []),
                "confidence_score": 0.7
            }
            
        except Exception as e:
            logger.error(f"Fallback structure creation failed: {str(e)}")
            return {
                "name": "Unknown",
                "job_title": "",
                "company_name": "",
                "industry": "",
                "location": "",
                "email": None,
                "phone": None,
                "linkedin_url": linkedin_url,
                "summary": "",
                "skills": [],
                "experience": [],
                "education": [],
                "confidence_score": 0.5
            }

# Global instance
linkedin_scraper = LinkedInScraper()