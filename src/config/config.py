import os
from dotenv import load_dotenv
from pathlib import Path

# Load environment variables from .env file
env_path = Path(__file__).parent.parent / '.env'
load_dotenv(dotenv_path=env_path)

# Supabase configuration
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY")

# Captcha solver configuration
CAPTCHA_SERVICE = os.getenv("CAPTCHA_SERVICE", "2captcha")  # Default to 2captcha
CAPTCHA_API_KEY_2CAPTCHA = os.getenv("CAPTCHA_API_KEY_2CAPTCHA")
CAPTCHA_API_KEY_CAPMONSTER = os.getenv("CAPTCHA_API_KEY_CAPMONSTER")

# PTA website configuration
PTA_URL = os.getenv("PTA_URL", "https://dirbs.pta.gov.pk/")

# Validate required environment variables
def validate_config():
    """Validate that all required environment variables are set."""
    required_vars = [
        ("SUPABASE_URL", SUPABASE_URL),
        ("SUPABASE_ANON_KEY", SUPABASE_ANON_KEY),
    ]
    
    if CAPTCHA_SERVICE == "2captcha":
        required_vars.append(("CAPTCHA_API_KEY_2CAPTCHA", CAPTCHA_API_KEY_2CAPTCHA))
    elif CAPTCHA_SERVICE == "capmonster":
        required_vars.append(("CAPTCHA_API_KEY_CAPMONSTER", CAPTCHA_API_KEY_CAPMONSTER))
    
    missing = [var_name for var_name, var_value in required_vars if not var_value]
    
    if missing:
        raise ValueError(f"Missing required environment variables: {', '.join(missing)}")
    
    return True
