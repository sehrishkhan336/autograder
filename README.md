# Environment Setup – Deployment Guide
## Overview
This document provides step-by-step instructions to set up the local and deployment environment for Phase 1 deployment of the AI Grading System.
It is intended for deployment engineers, DevOps, and reviewers to ensure consistent and error-free setup.
## System Requirements
# Operating System

* Windows 10/11 (Primary)

* macOS / Linux (Optional – requires driver adjustments)

## Software Prerequisites

* Python: 3.9 or higher

* pip: Latest version

* SQL Server: SQL Server 2019 or higher

* ODBC Driver: ODBC Driver 17 or 18 for SQL Server

# Python Environment Setup
## Install Required Python Packages
Run the following command to install all required Python packages:

RUN IN bash

pip install python-dotenv pyodbc pandas numpy openai requests

# Key Libraries Used

* pyodbc – Database connectivity

* pandas – Data processing

* numpy – Numerical operations

* python-docx – Document handling

* beautifulsoup4 – HTML parsing (if applicable)

* openai / ai-sdk – AI grading logic (Phase 1)

# Database Configuration
## Install ODBC Driver
* Install ODBC Driver 17 or 18 for SQL Server

* Restart machine after installation
## Verify Database Connection
Ensure SQL Server access is available with:

* Server Name

* Database Name

* Username & Password (or Windows Auth)

# Environment Variables (.env)
# --- OpenAI ---
OPENAI_API_KEY=

ENABLE_AI_GRADING=
OPENAI_MODEL=

AI_TIMEOUT_SECS=
AI_MAX_GRADE_DELTA=
AI_PROMPT_FILE=
AI_SYSTEM_INSTRUCTIONS_FILE=
AI_TEMPERATURE=
AI_MAX_TOKENS=

# --- Mandrill Email ---
MANDRILL_API_KEY=
MANDRILL_API_URL=

#EMAIL_SENDER=cai@colaberry.com
#BCC_EMAILS=s
#EMAIL_DRY_RUN=
#FORCE_SEND_EMAIL=
EMAIL_SENDER=
STUDENT_EMAIL=
BCC_EMAILS=
ESCALATION_EMAIL=
FORCE_SEND_EMAIL=
EMAIL_DRY_RUN=

# --- Database (SQL Server) ---
DB_SERVER=
DB_DATABASE=
DB_USERNAME=
DB_PASSWORD=
DB_TABLE=
DB_TRUSTED=

# Read from vw_Homework
DB_SOURCE_VIEW=

# Write into test table
DB_TEST_TABLE=

IGNORE_SOURCE_FILTERS=

# Running the Application
## Run Batch / Main Script
python run_batch.py

# Expected behavior:

* Connects to SQL Server

* Fetches ungraded records from vw_homework

* Applies AI grading logic (Phase 1)

* Updates grades back into Test database

# Deployment Notes

##  Phase 1: Rule-based + AI-assisted grading (Current)

## Phase 2 (Upcoming):

* Enhanced AI training

* Improved grading accuracy

* Stronger rubric anchoring & edge-case handling

* Deployment team only needs Phase 1 setup at this stage.