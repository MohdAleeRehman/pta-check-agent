import logging
import re
from typing import Dict, Any
from crewai import Task
from src.agents.base_agent import BaseAgent
from src.models.imei_models import PTAVerificationResult

logger = logging.getLogger(__name__)


class ResultParserAgent(BaseAgent):
    """
    Agent responsible for parsing and standardizing the results from the PTA website.
    """

    def __init__(self, **kwargs):
        """Initialize the Result Parser Agent."""
        super().__init__(
            name="ResultParserAgent",
            description="Agent responsible for parsing and standardizing verification results",
            goal="Extract and normalize verification results from raw data",
            backstory="I am a data parsing specialist with expertise in extracting meaningful information from web content. "
            "I transform raw text into structured data with high accuracy.",
            **kwargs,
        )

    def create_parsing_task(self) -> Task:
        """
        Create a task for parsing verification results.

        Returns:
            Task object for result parsing
        """
        return Task(
            description="Parse and standardize the IMEI verification result",
            expected_output="A standardized verification result object",
            agent=self.get_agent(),
            # Removed context and async_execution parameters
        )

    async def parse_result(self, raw_result: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parse the raw verification result.

        Args:
            raw_result: Raw result from the PTA website

        Returns:
            Dictionary with parsed and standardized result
        """
        try:
            self.log_info("Parsing verification result")

            # Extract the IMEI and details from the raw result
            imei = raw_result.get("imei")
            if not imei:
                self.log_error("No IMEI found in raw result")
                return {
                    "success": False,
                    "result": None,
                    "message": "No IMEI found in raw result",
                }

            raw_status = raw_result.get("status")
            raw_text = raw_result.get("details", {}).get("raw_text", "")
            error_message = raw_result.get("error_message")

            # Initialize verification result
            verification_result = PTAVerificationResult(
                imei=imei,
                status=raw_status or "Error",
                details=raw_result.get("details", {}),
                error_message=error_message,
            )

            # If we already have a valid status, no need for further parsing
            if raw_status in ["Compliant", "Non-Compliant"]:
                self.log_info(f"Result already parsed with status: {raw_status}")
                return {
                    "success": True,
                    "result": verification_result.dict(),
                    "message": "Result already parsed",
                }

            # If there's raw text to parse
            if raw_text:
                # Look for compliance status patterns
                if re.search(r"\bcompliant\b", raw_text, re.IGNORECASE):
                    if re.search(r"\bnon[\s-]compliant\b", raw_text, re.IGNORECASE):
                        verification_result.status = "Non-Compliant"
                    else:
                        verification_result.status = "Compliant"
                elif re.search(r"\bnon[\s-]compliant\b", raw_text, re.IGNORECASE):
                    verification_result.status = "Non-Compliant"
                elif re.search(r"\binvalid\b", raw_text, re.IGNORECASE) or re.search(
                    r"\berror\b", raw_text, re.IGNORECASE
                ):
                    verification_result.status = "Error"
                    verification_result.error_message = (
                        "Invalid IMEI or error in verification"
                    )
                else:
                    # If we can't determine the status from the text
                    verification_result.status = "Error"
                    verification_result.error_message = (
                        "Could not determine compliance status from result text"
                    )

                self.log_info(f"Parsed result status: {verification_result.status}")

            # If still no status, mark as error
            if not verification_result.status:
                verification_result.status = "Error"
                verification_result.error_message = (
                    "No compliance status found in result"
                )

            return {
                "success": True,
                "result": verification_result.dict(),
                "message": f"Successfully parsed result: {verification_result.status}",
            }
        except Exception as e:
            error_message = str(e)
            self.log_error(f"Error parsing verification result: {error_message}")
            return {
                "success": False,
                "result": PTAVerificationResult(
                    imei=imei if "imei" in locals() else "unknown",
                    status="Error",
                    error_message=f"Error parsing verification result: {error_message}",
                ).dict(),
                "message": f"Error parsing verification result: {error_message}",
            }
