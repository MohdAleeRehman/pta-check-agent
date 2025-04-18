import logging
import base64
import os
import time
from typing import Dict, Any
from crewai import Task
from src.agents.base_agent import BaseAgent
from src.utils.captcha_solver import CaptchaSolver
from src.models.imei_models import CaptchaSolution

logger = logging.getLogger(__name__)


class CaptchaSolverAgent(BaseAgent):
    """
    Agent responsible for solving captchas on the PTA website.
    Uses either 2Captcha or CapMonster Cloud API.
    """

    def __init__(self, captcha_solver=None, **kwargs):
        """
        Initialize the Captcha Solver Agent.

        Args:
            captcha_solver: Optional CaptchaSolver instance
        """
        super().__init__(
            name="CaptchaSolverAgent",
            description="Agent responsible for solving captchas on the PTA website",
            goal="Efficiently solve captchas to enable automated verification",
            backstory="I am a specialist in solving visual puzzles and captchas. "
            "I use advanced APIs to decode captchas quickly and accurately.",
            **kwargs,
        )
        self.captcha_solver = captcha_solver or CaptchaSolver()

    def create_solving_task(self) -> Task:
        """
        Create a task for solving captchas.

        Returns:
            Task object for captcha solving
        """
        return Task(
            description="Solve the captcha from the PTA website",
            expected_output="A solved captcha text or an error message",
            agent=self.get_agent(),
            # Removed context and async_execution parameters
        )

    async def solve_captcha(
        self,
        image_path: str = None,
        base64_image: str = None,
        site_key: str = None,
        page_url: str = None,
    ) -> Dict[str, Any]:
        """
        Solve a captcha using the configured solver.

        Args:
            image_path: Path to the captcha image file
            base64_image: Base64-encoded captcha image
            site_key: Site key for reCAPTCHA
            page_url: URL of the page with reCAPTCHA

        Returns:
            Dictionary with captcha solution or error
        """
        try:
            if not image_path and not base64_image and not (site_key and page_url):
                raise ValueError(
                    "Must provide either image_path, base64_image, or both site_key and page_url"
                )

            self.log_info("Attempting to solve captcha...")

            solution = await self.captcha_solver.solve_image_captcha(
                base64_image=base64_image,
                image_path=image_path,
                site_key=site_key,
                page_url=page_url,
            )

            if solution.success:
                self.log_info("Captcha solved successfully")
                return {
                    "success": True,
                    "solution": solution.solution,
                    "captcha_id": solution.captcha_id,
                    "message": "Captcha solved successfully",
                }
            else:
                self.log_error(f"Captcha solution failed: {solution.error}")
                return {
                    "success": False,
                    "solution": "",
                    "error": solution.error,
                    "message": f"Captcha solution failed: {solution.error}",
                }
        except Exception as e:
            error_message = str(e)
            self.log_error(f"Error solving captcha: {error_message}")
            return {
                "success": False,
                "solution": "",
                "error": error_message,
                "message": f"Error solving captcha: {error_message}",
            }

    async def save_captcha_image(
        self, image_data: bytes, output_dir: str = "captchas"
    ) -> str:
        """
        Save a captcha image to a file.

        Args:
            image_data: Binary image data
            output_dir: Directory to save the image in

        Returns:
            Path to the saved image file
        """
        try:
            # Create output directory if it doesn't exist
            os.makedirs(output_dir, exist_ok=True)

            # Generate a unique filename
            filename = f"captcha_{int(time.time())}.png"
            filepath = os.path.join(output_dir, filename)

            # Save the image
            with open(filepath, "wb") as f:
                f.write(image_data)

            self.log_info(f"Saved captcha image to {filepath}")
            return filepath
        except Exception as e:
            self.log_error(f"Error saving captcha image: {str(e)}")
            return None
