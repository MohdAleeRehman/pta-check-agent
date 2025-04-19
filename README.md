# IMEI Verification System



An automated system for verifying IMEI compliance status with the Pakistan Telecommunication Authority (PTA) DIRBS system.

## Overview

This project provides a robust agent-based solution for automating IMEI verification against the PTA DIRBS system. The system uses a crew of specialized agents, each responsible for a specific task in the workflow, from IMEI input validation to captcha solving and result parsing.

## Key Features

- **Agent-Based Architecture**: Uses CrewAI for orchestrating specialized agents
- **Automated Captcha Solving**: Handles both traditional image captchas and reCAPTCHA
- **Browser Automation**: Uses Playwright for headless browser interactions
- **API Interface**: FastAPI-based REST API for easy integration
- **Persistent Storage**: Supabase integration for storing verification results
- **Error Handling**: Built-in retry mechanism and detailed error logging

## Architecture

The system is designed with a modular architecture consisting of:

- **Agents**: Specialized components each responsible for one aspect of the workflow
- **Workflow**: Orchestrates the execution of tasks across agents
- **Models**: Pydantic models for data validation and serialization
- **Utilities**: Shared functionality for captcha solving and database interaction
- **API**: RESTful interface for external access

### Agent Components

- **IMEI Input Agent**: Validates IMEI number format
- **Captcha Solver Agent**: Solves both traditional and reCAPTCHA challenges
- **PTA Check Agent**: Navigates the PTA website and submits verification requests
- **Result Parser Agent**: Extracts and standardizes verification results
- **Supabase Save Agent**: Persists results to the database
- **Error Handler Agent**: Manages retries and error reporting

## Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/yourusername/Agent-PTA-Detection.git
   cd Agent-PTA-Detection
   ```

2. Create and activate a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows, use: venv\Scripts\activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Install Playwright browsers:
   ```bash
   playwright install chromium
   ```

5. Set up environment variables:
   - Create a `.env` file in the `src` directory
   - Add the following variables (replace with your actual values):
     ```
     SUPABASE_URL=your_supabase_url
     SUPABASE_ANON_KEY=your_supabase_anon_key
     CAPTCHA_SERVICE=2captcha
     CAPTCHA_API_KEY_2CAPTCHA=your_2captcha_api_key
     CAPTCHA_API_KEY_CAPMONSTER=your_capmonster_api_key
     OPENAI_API_KEY=your_openai_api_key
     PTA_URL=https://dirbs.pta.gov.pk/
     ```

## Usage

### Running the API Server

Start the FastAPI server:

```bash
cd Agent-PTA-Detection
uvicorn src.api:app --host 0.0.0.0 --port 8000 --reload
```

### API Endpoints

- **Verify IMEI**: `POST /verify`
  ```json
  {
    "imei": "359871977331199"
  }
  ```

- **Health Check**: `GET /health`

### Diagnostic Utilities

The repository includes diagnostic tools to help troubleshoot issues:

```bash
python diagnose.py  # Test the agents and workflow
```

## Development

### Project Structure

```
├── src/
│   ├── agents/       # Specialized agents for different tasks
│   ├── config/       # Configuration handling
│   ├── models/       # Pydantic data models
│   ├── utils/        # Utility functions (captcha solving, database)
│   ├── workflows/    # Task orchestration workflows
│   └── api.py        # FastAPI application
├── requirements.txt  # Project dependencies
└── .gitignore        # Git ignore rules
```

### Adding New Features

1. To add a new agent:
   - Create a new file in `src/agents/`
   - Inherit from `BaseAgent` class
   - Implement required methods

2. To modify the workflow:
   - Update `imei_verification_workflow.py` to include new steps

## Deployment

### EC2 Deployment

1. SSH into your EC2 instance
2. Clone the repository:
   ```bash
   git clone https://github.com/yourusername/Agent-PTA-Detection.git
   cd Agent-PTA-Detection
   ```

3. Follow the installation steps above
4. Set up a systemd service or use PM2 to keep the API running

### Docker Deployment

A Dockerfile is available for containerized deployment:

```bash
docker build -t imei-verification-system .
docker run -p 8000:8000 -d imei-verification-system
```

## Testing

Run the test suite:

```bash
pytest
```

## License

[MIT](LICENSE)

## Acknowledgments

- PTA DIRBS system for providing the verification service
- CrewAI for the agent orchestration framework
- Playwright for browser automation capabilities
