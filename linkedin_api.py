import os
from apify_client import ApifyClient
from urllib.parse import urlparse
import re

APIFY_API_TOKEN = os.getenv("APIFY_API_TOKEN", "apify_api_8ViThYsJGuDpcAQXNzKKdem6umJJS20PdRUV")
APIFY_ACTOR_ID = os.getenv("APIFY_ACTOR_ID", "VhxlqQXRwhW8H5hNV")

client = ApifyClient(APIFY_API_TOKEN)

def extract_linkedin_username(linkedin_url: str) -> str:
    """Extract the LinkedIn username from a profile URL."""
    # Handles URLs like https://www.linkedin.com/in/username/
    parsed = urlparse(linkedin_url)
    match = re.search(r"/in/([\w\-\.]+)", parsed.path)
    if match:
        return match.group(1)
    raise ValueError(f"Could not extract username from LinkedIn URL: {linkedin_url}")

def fetch_linkedin_profile(linkedin_url: str) -> dict:
    """Fetch LinkedIn profile data from Apify for the given profile URL."""
    username = extract_linkedin_username(linkedin_url)
    run_input = {"username": username}
    run = client.actor(APIFY_ACTOR_ID).call(run_input=run_input)
    dataset_id = run["defaultDatasetId"]
    # Get the first (and usually only) item
    for item in client.dataset(dataset_id).iterate_items():
        return item
    raise RuntimeError(f"No data returned from Apify for LinkedIn username: {username}")