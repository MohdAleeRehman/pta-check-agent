import logging
import asyncio
import warnings
from typing import Dict, Any, Optional
from fastapi import FastAPI, HTTPException, BackgroundTasks, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from src.models.imei_models import IMEIRequest
from src.workflows.imei_verification_workflow import IMEIVerificationWorkflow
from src.config.config import validate_config

# Filter out specific warnings
warnings.filterwarnings("ignore", message=".*validate_urls_array.*")
warnings.filterwarnings(
    "ignore", message="Importing LLMs from langchain is deprecated.*"
)
warnings.filterwarnings("ignore", message="The class `OpenAI` was deprecated.*")

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("imei_verification.log"),
    ],
)
logger = logging.getLogger(__name__)

# Validate configuration
try:
    validate_config()
except ValueError as e:
    logger.error(f"Configuration error: {str(e)}")
    raise

# Create FastAPI application
app = FastAPI(
    title="IMEI Verification API",
    description="API for verifying IMEI compliance status with the PTA DIRBS system",
    version="1.0.0",
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Update this in production to only allow specific origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Response models
class IMEIVerificationResponse(BaseModel):
    """Response model for IMEI verification."""

    success: bool
    imei: str
    status: Optional[str] = None
    details: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    message: str


# Store running verification workflows
verification_workflows = {}


def get_workflow(
    headless: bool = True, max_retries: int = 3
) -> IMEIVerificationWorkflow:
    """Get or create a verification workflow."""
    key = f"headless_{headless}_retries_{max_retries}"
    if key not in verification_workflows:
        logger.info(
            f"Creating new workflow with headless={headless}, max_retries={max_retries}"
        )
        verification_workflows[key] = IMEIVerificationWorkflow(
            headless=headless, max_retries=max_retries
        )
    return verification_workflows[key]


@app.get("/")
async def root():
    """Root endpoint."""
    return {"message": "IMEI Verification API is running"}


@app.post("/verify", response_model=IMEIVerificationResponse)
async def verify_imei(
    request: IMEIRequest,
    background_tasks: BackgroundTasks,
    headless: bool = True,
    max_retries: int = 3,
):
    """
    Verify an IMEI number with the PTA DIRBS system.

    Args:
        request: The IMEI request
        background_tasks: FastAPI background tasks
        headless: Whether to run the browser in headless mode
        max_retries: Maximum number of retries for failed operations

    Returns:
        Verification result
    """
    try:
        # Get workflow
        workflow = get_workflow(headless=headless, max_retries=max_retries)

        # Run verification
        logger.info(f"Starting verification for IMEI: {request.imei}")
        result = await workflow.run(request.imei)

        # Set default values
        status = "Error"
        details = None
        error_message = None
        success = False
        message = "Unknown error"

        # Added safe access function to prevent errors
        def safe_get(obj, key, default=None):
            if obj is None:
                return default
            if isinstance(obj, dict):
                return obj.get(key, default)
            return default

        # Check if result exists and is a dictionary
        if result is not None:
            if isinstance(result, dict):
                success = safe_get(result, "success", False)
                message = safe_get(result, "message", "Unknown error")

                # Extract more detailed information if available
                if "result" in result and isinstance(result["result"], dict):
                    status = safe_get(result["result"], "status", "Error")
                    details = safe_get(result["result"], "details")
                    error_message = safe_get(result["result"], "error_message")
            else:
                # Handle case where result is not a dictionary
                message = f"Unexpected result format: {str(result)}"
                logger.error(message)
        else:
            message = "No result returned from workflow"
            logger.error(message)

        return IMEIVerificationResponse(
            success=success,
            imei=request.imei,
            status=status,
            details=details,
            error_message=error_message,
            message=message,
        )
    except Exception as e:
        logger.error(f"Error verifying IMEI {request.imei}: {str(e)}", exc_info=True)
        return IMEIVerificationResponse(
            success=False,
            imei=request.imei,
            status="Error",
            details=None,
            error_message=str(e),
            message=f"Error verifying IMEI: {str(e)}",
        )


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
