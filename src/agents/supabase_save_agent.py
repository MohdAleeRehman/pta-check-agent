import logging
from typing import Dict, Any
from crewai import Task
from src.agents.base_agent import BaseAgent
from src.utils.supabase_client import SupabaseClient
from src.models.imei_models import SupabaseRecord, PTAVerificationResult

logger = logging.getLogger(__name__)


class SupabaseSaveAgent(BaseAgent):
    """
    Agent responsible for saving verification results to Supabase database.
    """

    def __init__(self, supabase_client=None, **kwargs):
        """
        Initialize the Supabase Save Agent.

        Args:
            supabase_client: Optional SupabaseClient instance
        """
        super().__init__(
            name="SupabaseSaveAgent",
            description="Agent responsible for saving verification results to the database",
            goal="Reliably store IMEI verification results in the database",
            backstory="I am a database expert specializing in data persistence. "
            "I ensure that all verification results are properly stored and can be retrieved later.",
            **kwargs,
        )
        self.supabase_client = supabase_client or SupabaseClient()

    def create_save_task(self) -> Task:
        """
        Create a task for saving verification results to Supabase.

        Returns:
            Task object for saving to Supabase
        """
        return Task(
            description="Save IMEI verification result to Supabase database",
            expected_output="Confirmation of successful database save or error",
            agent=self.get_agent(),
            # Removed context and async_execution parameters
        )

    async def save_verification_result(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """
        Save verification result to Supabase.

        Args:
            result: PTAVerificationResult as a dict

        Returns:
            Dictionary with save operation result
        """
        try:
            # Convert to PTAVerificationResult object
            verification_result = PTAVerificationResult(**result)

            # Create SupabaseRecord from verification result
            supabase_record = SupabaseRecord(
                imei=verification_result.imei,
                status=verification_result.status or "Error",
                details=verification_result.details,
                error_message=verification_result.error_message,
                verification_date=verification_result.verification_date,
            )

            self.log_info(
                f"Saving IMEI {supabase_record.imei} with status {supabase_record.status} to Supabase"
            )

            # Save to Supabase
            response = await self.supabase_client.save_verification_result(
                supabase_record
            )

            # Check if save was successful
            if response and response.data:
                self.log_info(
                    f"Successfully saved IMEI {supabase_record.imei} to Supabase"
                )
                return {
                    "success": True,
                    "record_id": (
                        response.data[0].get("id", None) if response.data else None
                    ),
                    "message": f"Successfully saved IMEI {supabase_record.imei} with status {supabase_record.status}",
                }
            else:
                self.log_error("Save operation returned no data")
                return {
                    "success": False,
                    "record_id": None,
                    "message": "Save operation returned no data",
                }
        except Exception as e:
            error_message = str(e)
            self.log_error(f"Error saving to Supabase: {error_message}")
            return {
                "success": False,
                "record_id": None,
                "message": f"Error saving to Supabase: {error_message}",
            }

    async def get_verification_history(
        self, imei: str = None, limit: int = 10
    ) -> Dict[str, Any]:
        """
        Get verification history for a specific IMEI or all IMEIs.

        Args:
            imei: Optional IMEI to filter by
            limit: Maximum number of records to return

        Returns:
            Dictionary with verification history
        """
        try:
            self.log_info(
                f"Getting verification history for {'IMEI ' + imei if imei else 'all IMEIs'}"
            )

            # Get history from Supabase
            history = await self.supabase_client.get_verification_history(imei, limit)

            self.log_info(f"Retrieved {len(history)} records from Supabase")
            return {
                "success": True,
                "history": history,
                "message": f"Retrieved {len(history)} verification records",
            }
        except Exception as e:
            error_message = str(e)
            self.log_error(f"Error getting verification history: {error_message}")
            return {
                "success": False,
                "history": [],
                "message": f"Error getting verification history: {error_message}",
            }

    async def ensure_table_exists(self) -> Dict[str, Any]:
        """
        Ensure that the necessary table exists in Supabase.

        Returns:
            Dictionary with operation result
        """
        try:
            self.log_info("Ensuring Supabase table exists")

            # Create table if it doesn't exist
            result = await self.supabase_client.create_tables_if_not_exist()

            if result:
                self.log_info("Supabase table is ready")
                return {"success": True, "message": "Supabase table is ready"}
            else:
                self.log_error("Failed to ensure Supabase table exists")
                return {
                    "success": False,
                    "message": "Failed to ensure Supabase table exists",
                }
        except Exception as e:
            error_message = str(e)
            self.log_error(f"Error ensuring Supabase table exists: {error_message}")
            return {
                "success": False,
                "message": f"Error ensuring Supabase table exists: {error_message}",
            }
