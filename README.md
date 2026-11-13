# StaleAnswer-Detector

### AI-Powered Stale Answer Detection and Verification System

## Overview

StaleAnswer-Detector is an AI-powered application that identifies potentially outdated, incorrect, or conflicting information in AI-generated answers.

It extracts factual claims from an answer, searches the web for current information, and verifies each claim using AI. The application provides verification results, a freshness score, and a downloadable PDF report.

## Problem Statement

AI-generated answers may contain outdated information because their knowledge may not reflect recent developments. This can lead to incorrect or misleading information being presented as factual.

StaleAnswer-Detector helps address this problem by checking factual claims against current web research.

## Key Features

- **Claim Extraction:** Extracts important factual statements from the given answer.
- **Live Web Research:** Uses Tavily to gather relevant and recent information.
- **AI Claim Verification:** Compares extracted claims with web research.
- **Verification Status:** Classifies claims as:
  - Verified
  - Potentially outdated
  - Conflicting
  - Unable to verify
- **Freshness Score:** Provides an overall heuristic freshness score.
- **PDF Report:** Generates a downloadable report containing verification results and sources.
- **Error Handling:** Handles temporary API failures with retry logic.
- **Streamlit Interface:** Provides a simple and user-friendly interface.

## Technology Stack

| Technology | Purpose |
|---|---|
| Python | Core application development |
| Streamlit | User interface |
| Bifrost | LLM gateway |
| Google Gemini | Claim extraction and verification |
| Tavily API | Web research |
| ReportLab | PDF report generation |
| Pytest | Automated testing |

## Project Workflow

1. User enters an AI-generated answer.
2. Gemini extracts factual claims through Bifrost.
3. Tavily searches the web for supporting information.
4. Gemini compares the claims with the retrieved evidence.
5. Each claim receives a verification status.
6. The application calculates an overall freshness score.
7. A PDF report is generated for download.

## Project Structure

```text
StaleAnswer-Detector/
│
├── app.py
├── claim_extractor.py
├── web_research.py
├── answer_verifier.py
├── pdf_generator.py
├── tests/
│   └── test_pipeline_helpers.py
├── requirements.txt
├── .gitignore
└── README.md
```

## Installation and Setup

### 1. Clone the Repository

```bash
git clone https://github.com/himarashmi940/StaleAnswer-Detector.git
cd StaleAnswer-Detector
```

### 2. Create a Virtual Environment

```bash
py -3.12 -m venv .venv
```

Activate it on Windows:

```powershell
.\.venv\Scripts\Activate.ps1
```

### 3. Install Dependencies

```bash
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### 4. Configure Environment Variables

Create a `.env` file in the project root:

```env
TAVILY_API_KEY=your_tavily_api_key
BIFROST_API_KEY=your_bifrost_virtual_key
BIFROST_BASE_URL=http://localhost:8080
BIFROST_MODEL_NAME=gemini/gemini-3.6-flash
```

Replace the placeholder values with your own credentials.

**Important:** Never upload your `.env` file or expose API keys publicly.

### 5. Start Bifrost

Start your locally configured Bifrost gateway:

```bash
npx -y @maximhq/bifrost
```

Ensure the configured Gemini provider and virtual key are active.

### 6. Run the Application

Open another terminal and execute:

```bash
streamlit run app.py
```

The application will open in your browser.

## Running Tests

Run the automated tests using:

```bash
python -m pytest -q
```

The project test suite passed all 15 tests during development.

## Future Enhancements

- Support for additional LLM providers.
- Improved source reliability scoring.
- Historical tracking of answer freshness.
- More detailed verification analytics.
- Public cloud deployment.

## Author

**Himarashmi N Kadabageri**

GitHub: https://github.com/himarashmi940

## License

This project is developed for educational and hackathon purposes.
