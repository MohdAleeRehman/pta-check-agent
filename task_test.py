from crewai import Task, Agent
import inspect

# Check Task's signature
print("Task's __init__ signature:")
print(inspect.signature(Task.__init__))

# Create a test agent
test_agent = Agent(
    role="Test Agent",
    goal="Testing",
    backstory="I am a test agent"
)

# Try different ways to create a Task
try:
    # Method 1 - Using standard parameters
    task1 = Task(
        description="Test task",
        expected_output="Test output",
        agent=test_agent
    )
    print("\nMethod 1 created successfully")
except Exception as e:
    print(f"\nMethod 1 failed: {e}")

try:
    # Method 2 - Using kwargs
    task2 = Task(
        description="Test task",
        expected_output="Test output", 
        agent=test_agent,
        context=["This is context"]
    )
    print("\nMethod 2 created successfully")
except Exception as e:
    print(f"\nMethod 2 failed: {e}")

try:
    # Method 3 - Using dictionary context
    task3 = Task(
        description="Test task",
        expected_output="Test output",
        agent=test_agent,
        context={"task_context": ["This is context"]}
    )
    print("\nMethod 3 created successfully")
except Exception as e:
    print(f"\nMethod 3 failed: {e}")

