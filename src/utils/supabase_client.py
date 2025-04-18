import logging
from supabase import create_client
from src.config.config import SUPABASE_URL, SUPABASE_ANON_KEY
from src.models.imei_models import SupabaseRecord

logger = logging.getLogger(__name__)


class SupabaseClient:
    """Utility class for Supabase integration."""

    def __init__(self):
        """Initialize the Supabase client."""
        self.client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)
        self.table_name = "imei_verification_results"

    async def save_verification_result(self, result: SupabaseRecord) -> dict:
        """
        Save verification result to Supabase.

        Args:
            result: SupabaseRecord object containing verification result

        Returns:
            Response from Supabase
        """
        try:
            response = (
                self.client.table(self.table_name).insert(result.dict()).execute()
            )
            return response
        except Exception as e:
            logger.error(f"Error saving verification result to Supabase: {str(e)}")
            raise

    async def get_verification_history(self, imei: str = None, limit: int = 10):
        """
        Get verification history for an IMEI or all IMEIs.

        Args:
            imei: Optional IMEI to filter by
            limit: Maximum number of records to return

        Returns:
            List of verification results
        """
        try:
            query = self.client.table(self.table_name)

            if imei:
                query = query.eq("imei", imei)

            response = (
                query.order("verification_date", desc=True).limit(limit).execute()
            )
            return response.data
        except Exception as e:
            logger.error(f"Error getting verification history from Supabase: {str(e)}")
            raise

    async def create_tables_if_not_exist(self):
        """Create the necessary tables in Supabase if they don't exist."""
        try:
            # Use raw SQL to create the table if it doesn't exist
            sql = f"""
            CREATE TABLE IF NOT EXISTS {self.table_name} (
                id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
                imei TEXT NOT NULL,
                status TEXT NOT NULL,
                details JSONB,
                error_message TEXT,
                verification_date TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
            );
            
            -- Create index on IMEI for faster lookups
            CREATE INDEX IF NOT EXISTS idx_{self.table_name}_imei ON {self.table_name}(imei);
            """

            self.client.table(self.table_name).execute(sql)
            logger.info(f"Created table {self.table_name} in Supabase")
            return True
        except Exception as e:
            logger.error(f"Error creating table in Supabase: {str(e)}")
            raise
