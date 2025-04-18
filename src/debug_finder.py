import logging
import sys
import traceback
from src.workflows.imei_verification_workflow import IMEIVerificationWorkflow
from src.agents.imei_input_agent import IMEIInputAgent
import asyncio

async def debug_validate():
    try:
        imei = "359871977331199"
        print(f"Testing with IMEI: {imei}")
        
        # Test IMEIInputAgent directly
        imei_agent = IMEIInputAgent()
        validation_result = await imei_agent.validate_imei(imei)
        print(f"Direct validation result: {validation_result}")
        print(f"Result type: {type(validation_result)}")
        
        # Test workflow run method
        workflow = IMEIVerificationWorkflow()
        result = await workflow.run(imei)
        print(f"Workflow run result: {result}")
        print(f"Result type: {type(result)}")
    except Exception as e:
        print(f"Error: {e}")
        print(traceback.format_exc())

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(debug_validate())
