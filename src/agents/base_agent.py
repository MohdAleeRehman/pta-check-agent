import logging
import os
from crewai import Agent
from langchain_community.llms import OpenAI
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.language_models.llms import BaseLLM
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


class MockLLM(BaseLLM):
    """Mock LLM for testing without OpenAI API key."""

    def _call(self, prompt, stop=None, run_manager=None, **kwargs):
        """Mock the LLM call."""
        logger.warning("Using MockLLM. Set OPENAI_API_KEY to use real LLM.")
        return "This is a mock response. Please set OPENAI_API_KEY to use real LLM."

    @property
    def _llm_type(self):
        return "mock"


class BaseAgent:
    """Base agent class that all specific agents will inherit from."""

    def __init__(
        self,
        name: str,
        description: str,
        goal: str,
        backstory: str = None,
        verbose: bool = False,
        allow_delegation: bool = True,
        llm: Optional[Any] = None,
    ):
        """
        Initialize the base agent with common attributes.

        Args:
            name: Name of the agent
            description: Description of the agent's role
            goal: The goal this agent is trying to achieve
            backstory: Optional backstory for the agent
            verbose: Whether to log verbose output
            allow_delegation: Whether this agent can delegate to other agents
            llm: Optional language model to use (defaults to OpenAI)
        """
        self.name = name
        self.description = description
        self.goal = goal
        self.backstory = (
            backstory
            or f"{name} is a specialized agent focused on {description.lower()}."
        )
        self.verbose = verbose
        self.allow_delegation = allow_delegation

        try:
            # Check if OPENAI_API_KEY is set
            openai_api_key = os.environ.get("OPENAI_API_KEY")
            if not openai_api_key and not llm:
                logger.warning("OPENAI_API_KEY not found. Using MockLLM instead.")
                self.llm = MockLLM()
            else:
                self.llm = llm or OpenAI(temperature=0.7)

            # Create the CrewAI agent
            self.agent = Agent(
                name=self.name,
                role=self.description,
                goal=self.goal,
                backstory=self.backstory,
                verbose=self.verbose,
                allow_delegation=self.allow_delegation,
                llm=self.llm,
            )

            logger.info(f"Initialized {self.name} agent")

        except Exception as e:
            logger.error(f"Failed to initialize {self.name} agent: {str(e)}")
            raise

    def get_agent(self) -> Agent:
        """Get the CrewAI agent instance."""
        return self.agent

    def log_info(self, message: str):
        """Log info message with agent name as prefix."""
        logger.info(f"[{self.name}] {message}")

    def log_error(self, message: str):
        """Log error message with agent name as prefix."""
        logger.error(f"[{self.name}] {message}")
