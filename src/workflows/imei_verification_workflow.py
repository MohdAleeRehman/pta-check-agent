import logging
import asyncio
from typing import Dict, Any, Optional
from crewai import Crew, Process, Task
from src.agents.imei_input_agent import IMEIInputAgent
from src.agents.captcha_solver_agent import CaptchaSolverAgent
from src.agents.pta_check_agent import PTACheckAgent
from src.agents.result_parser_agent import ResultParserAgent
from src.agents.supabase_save_agent import SupabaseSaveAgent
from src.agents.error_handler_agent import ErrorHandlerAgent

logger = logging.getLogger(__name__)


# Define a safe way to get values from any object
def safe_get(obj: Any, key: str, default: Any = None) -> Any:
    """Safely access a key from an object, whether it's a dict or not."""
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(key, default)
    return default


class IMEIVerificationWorkflow:
    """
    CrewAI-based workflow for orchestrating the IMEI verification process.
    """

    def __init__(self, headless: bool = True, max_retries: int = 3):
        """
        Initialize the workflow.

        Args:
            headless: Whether to run browser in headless mode
            max_retries: Maximum number of retries for failed operations
        """
        self.headless = headless
        self.max_retries = max_retries

        # Initialize agents
        self.imei_input_agent = IMEIInputAgent()
        self.captcha_solver_agent = CaptchaSolverAgent()
        self.pta_check_agent = PTACheckAgent(headless=self.headless)
        self.result_parser_agent = ResultParserAgent()
        self.supabase_save_agent = SupabaseSaveAgent()
        self.error_handler_agent = ErrorHandlerAgent(max_retries=self.max_retries)

        # Initialize CrewAI crew
        self._init_crew()

    def _init_crew(self) -> None:
        """Initialize the CrewAI crew with sequential tasks."""
        # Create tasks for each verification step
        self.validate_imei_task = self.imei_input_agent.create_validation_task()
        self.get_captcha_task = self._create_get_captcha_task()
        self.solve_captcha_task = self.captcha_solver_agent.create_solving_task()
        self.check_imei_task = self.pta_check_agent.create_check_task()
        self.parse_result_task = self.result_parser_agent.create_parsing_task()
        self.save_result_task = self.supabase_save_agent.create_save_task()
        self.handle_error_task = self.error_handler_agent.create_error_handling_task()

        # Create the crew with all agents
        self.crew = Crew(
            agents=[
                self.imei_input_agent.get_agent(),
                self.captcha_solver_agent.get_agent(),
                self.pta_check_agent.get_agent(),
                self.result_parser_agent.get_agent(),
                self.supabase_save_agent.get_agent(),
                self.error_handler_agent.get_agent(),
            ],
            tasks=[],  # We'll set tasks dynamically during execution
            verbose=True,
            process=Process.sequential,
        )

    def _create_get_captcha_task(self) -> Task:
        """Create a task for getting captcha from PTA website."""
        return Task(
            description="Get captcha from the PTA website",
            expected_output="A base64-encoded captcha image",
            agent=self.pta_check_agent.get_agent(),
        )

    async def run(self, imei: str) -> Dict[str, Any]:
        """
        Run the workflow for a given IMEI.

        Args:
            imei: The IMEI to verify

        Returns:
            Dictionary with verification result
        """
        try:
            # Initialize state to track workflow progress
            state = {"imei": imei}
            retry_count = 0

            # Debug logging
            logger.info(f"Starting workflow run for IMEI: {imei}")

            # Step 1: Validate IMEI
            try:
                logger.info("Calling validate_imei method")
                validation_result = await self.imei_input_agent.validate_imei(imei)
                logger.info(
                    f"Validation result: {validation_result}, type: {type(validation_result)}"
                )

                if not isinstance(validation_result, dict):
                    logger.error(
                        f"Validation result is not a dictionary: {validation_result}"
                    )
                    return {
                        "success": False,
                        "imei": imei,
                        "message": f"Invalid validation result format: {type(validation_result)}",
                    }

                if not safe_get(validation_result, "success", False):
                    logger.info(
                        f"IMEI validation failed: {safe_get(validation_result, 'message', '')}"
                    )
                    return validation_result

                logger.info("IMEI validation successful, updating state")
                state.update(validation_result)
            except Exception as e:
                logger.error(
                    f"Exception in validate_imei step: {str(e)}", exc_info=True
                )
                error_result = await self._handle_error(
                    "validate_imei", e, {"imei": imei}, retry_count
                )
                if not safe_get(error_result, "should_retry", False):
                    return error_result
                retry_count += 1
                return await self.run(imei)  # Retry the entire workflow

            # Step 2: Get Captcha
            try:
                captcha_result = await self.pta_check_agent.get_captcha()
                logger.info(f"Captcha detection result: {captcha_result}")

                if not isinstance(captcha_result, dict):
                    logger.error(
                        f"Captcha result is not a dictionary: {captcha_result}"
                    )
                    return {
                        "success": False,
                        "imei": imei,
                        "message": f"Invalid captcha result format: {type(captcha_result)}",
                    }

                if not safe_get(captcha_result, "success", False):
                    return captcha_result

                # Store captcha type for later steps
                captcha_type = safe_get(captcha_result, "captcha_type", "unknown")
                logger.info(f"Detected captcha type: {captcha_type}")
                state.update(captcha_result)
                state["captcha_type"] = captcha_type

            except Exception as e:
                error_result = await self._handle_error(
                    "get_captcha", e, {"imei": imei}, retry_count
                )
                if not safe_get(error_result, "should_retry", False):
                    return error_result
                retry_count += 1
                return await self.run(imei)  # Retry the entire workflow

            # Step 3: Solve Captcha (if needed)
            captcha_solution = {
                "success": True,
                "solution": "",
            }  # Default for no_captcha case

            if state["captcha_type"] == "image_captcha":
                try:
                    logger.info("Solving traditional image captcha")
                    captcha_solution = await self.captcha_solver_agent.solve_captcha(
                        base64_image=safe_get(state, "captcha_image")
                    )
                    if not isinstance(captcha_solution, dict):
                        logger.error(
                            f"Captcha solution is not a dictionary: {captcha_solution}"
                        )
                        return {
                            "success": False,
                            "imei": imei,
                            "message": f"Invalid captcha solution format: {type(captcha_solution)}",
                        }

                    if not safe_get(captcha_solution, "success", False):
                        return captcha_solution
                    state.update(captcha_solution)
                except Exception as e:
                    error_result = await self._handle_error(
                        "solve_captcha", e, {"imei": imei}, retry_count
                    )
                    if not safe_get(error_result, "should_retry", False):
                        return error_result
                    retry_count += 1
                    return await self.run(imei)  # Retry the entire workflow

            elif state["captcha_type"] == "recaptcha":
                try:
                    logger.info("Solving reCAPTCHA")
                    captcha_solution = await self.captcha_solver_agent.solve_captcha(
                        site_key=safe_get(state, "site_key"),
                        page_url=safe_get(state, "page_url"),
                    )
                    if not isinstance(captcha_solution, dict):
                        logger.error(
                            f"reCAPTCHA solution is not a dictionary: {captcha_solution}"
                        )
                        return {
                            "success": False,
                            "imei": imei,
                            "message": f"Invalid reCAPTCHA solution format: {type(captcha_solution)}",
                        }

                    if not safe_get(captcha_solution, "success", False):
                        return captcha_solution
                    state.update(captcha_solution)
                except Exception as e:
                    error_result = await self._handle_error(
                        "solve_recaptcha", e, {"imei": imei}, retry_count
                    )
                    if not safe_get(error_result, "should_retry", False):
                        return error_result
                    retry_count += 1
                    return await self.run(imei)  # Retry the entire workflow
            elif state["captcha_type"] == "no_captcha":
                logger.info("No captcha needed, proceeding directly to IMEI check")
            else:
                logger.error(f"Unknown captcha type: {state['captcha_type']}")
                return {
                    "success": False,
                    "imei": imei,
                    "message": f"Unknown captcha type: {state['captcha_type']}",
                }

            # Step 4: Check IMEI
            try:
                check_result = await self.pta_check_agent.check_imei(
                    safe_get(state, "imei", imei), safe_get(state, "solution", "")
                )
                if not isinstance(check_result, dict):
                    logger.error(f"Check result is not a dictionary: {check_result}")
                    return {
                        "success": False,
                        "imei": imei,
                        "message": f"Invalid check result format: {type(check_result)}",
                    }

                if not safe_get(check_result, "success", False):
                    return check_result
                state.update(check_result)
            except Exception as e:
                error_context = {
                    "imei": imei,
                    "solution": safe_get(state, "solution", ""),
                }
                error_result = await self._handle_error(
                    "check_imei", e, error_context, retry_count
                )
                if not safe_get(error_result, "should_retry", False):
                    return error_result
                retry_count += 1
                return await self.run(imei)  # Retry the entire workflow

            # Step 5: Parse Result
            try:
                parsed_result = await self.result_parser_agent.parse_result(
                    safe_get(state, "result", {})
                )
                if not isinstance(parsed_result, dict):
                    logger.error(f"Parsed result is not a dictionary: {parsed_result}")
                    return {
                        "success": False,
                        "imei": imei,
                        "message": f"Invalid parsed result format: {type(parsed_result)}",
                    }

                if not safe_get(parsed_result, "success", False):
                    return parsed_result
                state.update(parsed_result)
            except Exception as e:
                error_context = {"imei": imei, "result": safe_get(state, "result", {})}
                error_result = await self._handle_error(
                    "parse_result", e, error_context, retry_count
                )
                if not safe_get(error_result, "should_retry", False):
                    return error_result
                retry_count += 1
                return await self.run(imei)  # Retry the entire workflow

            # Step 6: Save Result
            try:
                save_result = await self.supabase_save_agent.save_verification_result(
                    safe_get(state, "result", {})
                )
                if not isinstance(save_result, dict):
                    logger.error(f"Save result is not a dictionary: {save_result}")
                    return {
                        "success": False,
                        "imei": imei,
                        "message": f"Invalid save result format: {type(save_result)}",
                    }

                if not safe_get(save_result, "success", False):
                    return save_result
                state.update(save_result)
            except Exception as e:
                error_context = {"imei": imei, "result": safe_get(state, "result", {})}
                error_result = await self._handle_error(
                    "save_result", e, error_context, retry_count
                )
                if not safe_get(error_result, "should_retry", False):
                    return error_result
                retry_count += 1
                return await self.run(imei)  # Retry the entire workflow

            # Return final state
            return state

        except Exception as e:
            logger.error(f"Error running workflow: {str(e)}")
            return {
                "success": False,
                "imei": imei,
                "message": f"Error running workflow: {str(e)}",
            }

    async def _handle_error(
        self,
        error_step: str,
        error: Exception,
        error_context: Dict[str, Any],
        retry_count: int,
    ) -> Dict[str, Any]:
        """Handle errors that occur during workflow execution."""
        try:
            logger.info(f"Handling error in {error_step}: {str(error)}")
            error_result = await self.error_handler_agent.handle_error(
                error, error_context, error_step, retry_count
            )

            # Ensure we have a dictionary result
            if not isinstance(error_result, dict):
                logger.error(
                    f"Error handler returned non-dictionary response: {error_result}"
                )
                return {
                    "success": False,
                    "should_retry": False,
                    "message": f"Error handling failed: invalid response format from error handler",
                }

            return error_result
        except Exception as e:
            logger.error(f"Error handling itself failed: {str(e)}")
            return {
                "success": False,
                "should_retry": False,
                "message": f"Error handling failed: {str(e)}",
            }
