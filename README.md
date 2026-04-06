# OHS Document Intelligence Pipeline 📄🔍

[![Streamlit App](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://comfortable-achievement-production.up.railway.app/)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-green.svg)](https://fastapi.tiangolo.com/)

An end-to-end Machine Learning pipeline that automates the extraction and structuring of data from complex health and safety compliance records (e.g., LOLER, pressure vessel certificates). 

**[View the Live Demo]((https://comfortable-achievement-production.up.railway.app/))**

![UI Screenshot](https://github.com/user-attachments/assets/97eb2914-778b-4610-84df-fad502e85c06)

## Business Value
Manual auditing of OHS certificates is error-prone and time-intensive. This API leverages multimodal LLMs to extract key regulatory data points from unstructured PDFs and images and outputs validated JSON for integration into risk management systems.

## Core Features
* **Multimodal Extraction:** Parses both text-heavy PDFs and scanned images using PyMuPDF and OCR.
* **Complex Reasoning:** Utilises **Gemini 2.5 Flash API** to accurately identify compliance dates, equipment IDs, and failure conditions.
* **Strict Validation:** Implements **Pydantic v2** to ensure all extracted data strictly adheres to expected regulatory schemas.
* **RESTful Architecture:** Served via **FastAPI** for seamless downstream integration.
* **Interactive UI:** Built with **Streamlit** for non-technical stakeholder demonstration.

## Tech Stack
* **Backend:** FastAPI, Python
* **AI/ML:** Gemini 2.5 Flash API, ModernBERT
* **Data Validation:** Pydantic v2
* **Document Processing:** PyMuPDF
* **Frontend:** Streamlit

## Quickstart (Local Development)

1. **Clone the repository**
   ```bash
   git clone [https://github.com/stuartclark-ml/ohs-document-parser.git](https://github.com/stuartclark-ml/ohs-document-parser.git)
   cd ohs-document-parser
