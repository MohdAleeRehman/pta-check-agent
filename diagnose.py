import logging
import os
import sys
import traceback
import asyncio
from src.agents.imei_input_agent import IMEIInputAgent
from src.agents.base_agent import BaseAgent
from src.workflows.imei_verification_workflow import IMEIVerificationWorkflow

# Configure detailed logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s [%(levelname)s] %(name)s:%(lineno)d - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("diagnose.log")
    ]
)

logger = logging.getLogger("diagnose")

async def test_agent():
    """Test the IMEIInputAgent directly."""
    try:
        logger.info("Testing IMEIInputAgent...")
        agent = IMEIInputAgent()
        logger.info(f"Agent created: {agent}")
        result = await agent.validate_imei("359871977331199")
        logger.info(f"Result type: {type(result)}")
        logger.info(f"Result content: {result}")
        return result
    except Exception as e:
        logger.error(f"Agent test failed: {str(e)}")
        logger.error(traceback.format_exc())
        return None

async def test_workflow():
    """Test the workflow."""
    try:
        logger.info("Testing workflow...")
        workflow = IMEIVerificationWorkflow(headless=True, max_retries=3)
        logger.info(f"Workflow created: {workflow}")
        result = await workflow.run("359871977331199")
        logger.info(f"Result type: {type(result)}")
        logger.info(f"Result content: {result}")
        return result
    except Exception as e:
        logger.error(f"Workflow test failed: {str(e)}")
        logger.error(traceback.format_exc())
        return None

if __name__ == "__main__":
    logger.info("Starting diagnostic tests...")
    asyncio.run(test_agent())
    asyncio.run(test_workflow())
    logger.info("Diagnostic tests completed")
