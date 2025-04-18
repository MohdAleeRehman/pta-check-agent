import logging
from typing import Dict, Any
from crewai import Task
from src.agents.base_agent import BaseAgent
from src.models.imei_models import IMEIRequest

logger = logging.getLogger(__name__)


class IMEIInputAgent(BaseAgent):
    """
    Agent responsible for accepting and validating IMEI inputs.
    This agent acts as the entry point for the workflow.
    """

    def __init__(self, **kwargs):
        """Initialize the IMEI Input Agent."""
        super().__init__(
            name="IMEIInputAgent",
            description="Agent responsible for accepting and validating IMEI numbers",
            goal="Validate IMEI numbers and prepare them for verification",
            backstory="I am an expert at validating IMEI numbers and ensuring they meet the required format. "
            "I carefully check each digit and make sure the input is valid before passing it along.",
            **kwargs,
        )

    def create_validation_task(self) -> Task:
        """
        Create a task for validating IMEI input.

        Returns:
            Task object for IMEI validation
        """
        return Task(
            description="Validate the given IMEI number",
            expected_output="A validated IMEI number or an error message",
            agent=self.get_agent(),
            # Removed context and async_execution parameters that may be causing issues
        )

    async def validate_imei(self, imei: str) -> Dict[str, Any]:
        try:
            imei = str(imei).strip()  # Ensure type and remove whitespace
            validated_imei = IMEIRequest(imei=imei)
            self.log_info(f"IMEI {imei} is valid")
            return {
                "success": True,
                "imei": validated_imei.imei,
                "message": "IMEI validation successful",
            }
        except Exception as e:
            error_message = str(e)
            self.log_error(f"IMEI validation failed: {error_message}")
            return {
                "success": False,
                "imei": imei,
                "message": f"IMEI validation failed: {error_message}",
            }
