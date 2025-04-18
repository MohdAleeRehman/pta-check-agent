import logging
import traceback
from typing import Dict, Any, Optional
from crewai import Task
from src.agents.base_agent import BaseAgent  # Updated import path
from src.models.imei_models import PTAVerificationResult  # Updated import path
from src.utils.supabase_client import SupabaseClient  # Updated import path

logger = logging.getLogger(__name__)


class ErrorHandlerAgent(BaseAgent):
    """
    Agent responsible for handling errors and retrying failed operations.
    """

    def __init__(self, supabase_client=None, max_retries=3, **kwargs):
        """
        Initialize the Error Handler Agent.

        Args:
            supabase_client: Optional SupabaseClient instance for logging errors
            max_retries: Maximum number of retries for failed operations
        """
        super().__init__(
            name="ErrorHandlerAgent",
            description="Agent responsible for handling errors and retrying failed operations",
            goal="Ensure system reliability by handling errors gracefully",
            backstory="I am a troubleshooting expert specializing in error recovery. "
            "When things go wrong, I identify the issues, log them properly, and "
            "coordinate recovery or graceful degradation.",
            **kwargs,
        )
        self.supabase_client = supabase_client or SupabaseClient()
        self.max_retries = max_retries
        self.error_table_name = "error_logs"

    def create_error_handling_task(self) -> Task:
        """
        Create a task for handling errors.

        Returns:
            Task object for error handling
        """
        return Task(
            description="Handle errors and coordinate recovery",
            expected_output="Error handling result and recovery status",
            agent=self.get_agent(),
            # Removed context and async_execution parameters
        )

    async def handle_error(
        self,
        error: Exception,
        context: Dict[str, Any],
        step_name: str,
        retry_count: int = 0,
    ) -> Dict[str, Any]:
        """
        Handle an error that occurred during the workflow.

        Args:
            error: The exception that occurred
            context: Context information about the error
            step_name: Name of the step where the error occurred
            retry_count: Current retry count

        Returns:
            Dictionary with error handling result
        """
        try:
            error_message = str(error)
            stack_trace = traceback.format_exc()

            self.log_error(f"Error in {step_name}: {error_message}")

            # Log the error
            error_log = {
                "step": step_name,
                "error_message": error_message,
                "stack_trace": stack_trace,
                "context": context,
                "retry_count": retry_count,
            }

            # Save error to Supabase if possible
            try:
                await self._log_error_to_supabase(error_log)
            except Exception as e:
                self.log_error(f"Failed to log error to Supabase: {str(e)}")

            # Check if we should retry
            can_retry = retry_count < self.max_retries

            if can_retry:
                self.log_info(
                    f"Retrying {step_name} (Attempt {retry_count + 1}/{self.max_retries})"
                )
                return {
                    "success": False,
                    "should_retry": True,
                    "retry_count": retry_count + 1,
                    "message": f"Error in {step_name}: {error_message}. Retrying (Attempt {retry_count + 1}/{self.max_retries}).",
                }
            else:
                self.log_error(f"Max retries reached for {step_name}. Giving up.")

                # If we have an IMEI in context, create a failed verification result
                imei = context.get("imei")
                if imei:
                    result = PTAVerificationResult(
                        imei=imei,
                        status="Error",
                        error_message=f"Failed after {self.max_retries} retries: {error_message}",
                    )

                    # Try to save the failed result
                    try:
                        from src.utils.supabase_client import SupabaseClient
                        from src.models.imei_models import SupabaseRecord

                        supabase_record = SupabaseRecord(
                            imei=imei,
                            status="Error",
                            error_message=f"Failed after {self.max_retries} retries: {error_message}",
                        )

                        await self.supabase_client.save_verification_result(
                            supabase_record
                        )
                        self.log_info(
                            f"Saved failed verification result for IMEI {imei} to Supabase"
                        )
                    except Exception as e:
                        self.log_error(
                            f"Failed to save failed verification result: {str(e)}"
                        )

                return {
                    "success": False,
                    "should_retry": False,
                    "retry_count": retry_count,
                    "result": result.dict() if "result" in locals() else None,
                    "message": f"Error in {step_name}: {error_message}. Max retries reached.",
                }
        except Exception as e:
            # If error handling itself fails
            self.log_error(f"Error in error handler: {str(e)}")
            return {
                "success": False,
                "should_retry": False,
                "retry_count": retry_count,
                "message": f"Error handling failed: {str(e)}",
            }

    async def _log_error_to_supabase(self, error_log: Dict[str, Any]) -> None:
        """
        Log an error to Supabase.

        Args:
            error_log: Error information to log
        """
        try:
            # Create error logs table if it doesn't exist
            await self._ensure_error_table_exists()

            # Insert the error log
            self.supabase_client.client.table(self.error_table_name).insert(
                error_log
            ).execute()
            self.log_info("Error logged to Supabase")
        except Exception as e:
            self.log_error(f"Failed to log error to Supabase: {str(e)}")
            # Don't raise - this is already error handling code

    async def _ensure_error_table_exists(self) -> None:
        """Create error logs table if it doesn't exist."""
        try:
            # Use raw SQL to create the table if it doesn't exist
            sql = f"""
            CREATE TABLE IF NOT EXISTS {self.error_table_name} (
                id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
                step TEXT NOT NULL,
                error_message TEXT NOT NULL,
                stack_trace TEXT,
                context JSONB,
                retry_count INTEGER DEFAULT 0,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
            );
            
            -- Create index on step for faster lookups
            CREATE INDEX IF NOT EXISTS idx_{self.error_table_name}_step ON {self.error_table_name}(step);
            """

            self.supabase_client.client.table(self.error_table_name).execute(sql)
            self.log_info(f"Ensured {self.error_table_name} table exists")
        except Exception as e:
            self.log_error(f"Error ensuring error table exists: {str(e)}")
            # Don't raise - this is already error handling code
