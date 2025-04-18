from crewai import Task, Agent

# Create a simple agent
agent = Agent(
    role="Test Agent",
    goal="Testing Task Creation",
    backstory="I am a test agent"
)

# Create a simple task
print("Creating task...")
task = Task(
    description="Test Task",
    expected_output="Test Output",
    agent=agent
)
print("Task created successfully!")
print(f"Task object: {task}")

