<p align="center">
  <img src="tatic/img/preview.jpg" alt="Preview" width="100%">
</p>

# consulta antecedentes
<p>
  Intelligent automation for disciplinary background checks
</p>



---

## Table of Contents

- [Overview](#overview)
- [Technologies](#technologies)
- [Architecture](#architecture)
- [Application Flow](#application-flow)
- [Installation](#installation)
- [Configuration](#configuration)
- [Usage](#usage)
- [API](#api)
- [Project Structure](#project-structure)
- [Technical Decisions](#technical-decisions)
- [Roadmap](#roadmap)
- [License](#license)

---

## Overview

This project automates disciplinary background checks on the Colombian **Procuraduría General de la Nación** website. It is not a simple scraper. It is a system that navigates, interprets dynamic security verification questions, and extracts results with the precision of a human operator — at machine speed.

The system is built as a **REST API** with an integrated web interface. The minimal frontend lets you enter a document type and number and receive results in seconds. Every step — launching the browser, filling the form, solving the security challenge, and extracting the outcome — happens automatically behind the scenes.

> The real value of this project lies not in the automation itself, but in how it elegantly solves the human verification problem: using a large language model (Groq) to interpret natural language questions when heuristic methods fall short.

---

## Technologies

| Layer           | Technology                  | Purpose                                        |
|-----------------|-----------------------------|------------------------------------------------|
| Backend         | **FastAPI** (Python)         | REST API, routing, business logic              |
| Automation      | **Pyppeteer**                | Headless browser control (Chrome/Edge)         |
| AI              | **Groq** (LLaMA 3.3-70B)     | Complex verification question resolution       |
| Frontend        | **HTML + Tailwind CSS**      | Clean, responsive user interface               |
| Server          | **Uvicorn**                  | ASGI server for FastAPI                        |

---

## Architecture

The system operates as a **three-layer orchestrator** working in sequence:

```
┌─────────────┐     ┌──────────────┐     ┌─────────────┐
│   Client    │────▶│   FastAPI    │────▶│  Pyppeteer  │
│  (Browser)  │     │  (Backend)   │     │  (Scraper)  │
└─────────────┘     └──────┬───────┘     └──────┬──────┘
                           │                    │
                           │              ┌─────▼──────┐
                           │              │  Groq AI   │
                           │              │(Verification)
                           │              └────────────┘
                           │
                     ┌─────▼──────┐
                     │  Frontend  │
                     │ (Response) │
                     └────────────┘
```

1. **Client** sends document type and number via HTTP POST.
2. **FastAPI** receives the request and delegates the scraping process.
3. **Pyppeteer** opens a headless browser, navigates to the Procuraduría portal, fills the form, and solves the security challenge.
4. **Groq** steps in when local methods cannot resolve the verification question.
5. The result is returned to the frontend and displayed to the user.

---

## Application Flow

```
                    ┌─────────────────────────┐
                    │    User enters data      │
                    │  (doc type + number)     │
                    └────────────┬────────────┘
                                 │
                    ┌────────────▼────────────┐
                    │  FastAPI receives POST   │
                    └────────────┬────────────┘
                                 │
                    ┌────────────▼────────────┐
                    │  Pyppeteer launches      │
                    │  Chrome (headless)       │
                    └────────────┬────────────┘
                                 │
                    ┌────────────▼────────────┐
                    │  Navigates to the        │
                    │  Procuraduría portal     │
                    └────────────┬────────────┘
                                 │
                    ┌────────────▼────────────┐
                    │  Locates the form iframe │
                    └────────────┬────────────┘
                                 │
                    ┌────────────▼────────────┐
                    │  Selects document type   │
                    │  Enters document number  │
                    └────────────┬────────────┘
                                 │
                    ┌────────────▼────────────┐
                    │   Verification question  │
                    │   present?               │
                    └────────────┬────────────┘
                          ┌──────┴──────┐
                          ▼              ▼
                    ┌───────────┐  ┌───────────┐
                    │  Math     │  │ Dictionary│
                    │  problem? │  │  lookup?  │
                    └─────┬─────┘  └─────┬─────┘
                    Yes   No        Yes   No
                    ▼      ▼         ▼      ▼
               ┌────────┐ ┌────────┐ ┌────────┐ ┌──────────┐
               │Solve   │ │ Groq   │ │Known   │ │ Groq     │
               │locally │ │ AI     │ │capital │ │ (complex │
               │        │ │        │ │        │ │ question)│
               └───┬────┘ └───┬────┘ └───┬────┘ └────┬─────┘
                   ▼          ▼          ▼           ▼
               ┌─────────────────────────────────────────┐
               │   Answer entered into verification field │
               └──────────────────┬──────────────────────┘
                                  │
                    ┌─────────────▼──────────────────┐
                    │  "Consultar" button pressed     │
                    │  Waiting for ASP.NET postback   │
                    └─────────────┬──────────────────┘
                                  │
                    ┌─────────────▼──────────────────┐
                    │  Result extracted:               │
                    │  • Citizen name                  │
                    │  • Has background records?       │
                    │  • Descriptive message           │
                    └─────────────┬──────────────────┘
                                  │
                    ┌─────────────▼──────────────────┐
                    │  FastAPI returns JSON            │
                    │  Frontend displays result        │
                    └─────────────────────────────────┘
```

---

## Installation

### Prerequisites

- **Python 3.10+**
- **Google Chrome** or **Microsoft Edge** installed
- **Groq API key** (optional, for complex questions)

### Steps

Clone the repository:

```bash
git clone https://github.com/sebastianvasquezechavarria1234/automatizaciones.git
cd automatizaciones
```

Create and activate a virtual environment:

```bash
python -m venv venv

# Windows
venv\Scripts\activate

# macOS / Linux
source venv/bin/activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

---

## Configuration

### Environment variable

Groq is only used for verification questions that cannot be resolved locally. The system will work without it, but some security challenges may fail.

```bash
# Optional — only needed for full question coverage
set GROQ_API_KEY=gsk_your_key_here
```

> If `GROQ_API_KEY` is not set, a built-in fallback key is used. For production environments, setting the environment variable is strongly recommended.

---

## Usage

Start the server:

```bash
python main.py
```

The server runs at `http://localhost:8003`.

Open that URL in your browser. You will see a clean interface where you can:

1. Select the **document type** (CC, CE, PAS, PEP, PPT, NIT).
2. Enter the **document number**.
3. Click **Consultar**.

The system processes the request and displays the result on screen. The response includes the citizen's name, whether they have background records, and the official message from the portal.

### Sample response

```json
{
  "tipo_documento": "CC",
  "numero_documento": "123456789",
  "nombre": "JUAN PEREZ",
  "tiene_antecedentes": false,
  "mensaje": "The citizen has no background records"
}
```

---

## API

### `POST /consultar-antecedentes`

Main endpoint for performing background checks.

**Request:**

```json
{
  "tipo_documento": "CC",
  "numero_documento": "123456789"
}
```

| Field              | Type   | Description                                  |
|--------------------|--------|----------------------------------------------|
| `tipo_documento`   | string | Document type: CC, CE, PAS, PEP, PPT or NIT |
| `numero_documento` | string | Identification number                        |

**Response (success — no records):**

```json
{
  "tipo_documento": "CC",
  "numero_documento": "123456789",
  "nombre": "JUAN PEREZ",
  "tiene_antecedentes": false,
  "mensaje": "The citizen has no background records"
}
```

**Response (success — records found):**

```json
{
  "tipo_documento": "CC",
  "numero_documento": "123456789",
  "nombre": "JUAN PEREZ",
  "tiene_antecedentes": true,
  "mensaje": "The citizen has registered background records."
}
```

**Response (error):**

```json
{
  "error": true,
  "tipo_documento": "CC",
  "numero_documento": "123456789",
  "mensaje": "The query could not be completed. The security verification could not be resolved."
}
```

| Field                | Type    | Description                                    |
|----------------------|---------|------------------------------------------------|
| `tipo_documento`     | string  | Document type sent                             |
| `numero_documento`   | string  | Document number sent                           |
| `nombre`             | string  | Citizen name extracted from the portal         |
| `tiene_antecedentes` | boolean | `true` if records found, `false` otherwise     |
| `mensaje`            | string  | Descriptive result message                     |
| `error`              | boolean | `true` if an error occurred during the query   |

### `GET /`

Serves the web interface (frontend) at the root path.

---

## Project Structure

```
automatizaciones/
├── static/                  # Frontend
│   ├── index.html           # User interface (Tailwind CSS)
│   └── app.js               # Frontend logic
├── main.py                  # FastAPI server (entry point)
├── scraper.py               # Pyppeteer automation
├── groq_service.py          # Groq AI integration
├── requirements.txt         # Python dependencies
├── .gitignore
├── LICENSE                  # MIT License
└── README.md                # This file
```

---

## Technical Decisions

### Why Pyppeteer instead of Selenium?

Pyppeteer is the async Python port of Puppeteer. Since FastAPI is asynchronous by nature, Pyppeteer integrates seamlessly without thread pools or extra event loops. The entire pipeline runs on pure `async/await`.

### Intelligent verification resolution

The system uses a cascading resolution strategy:

1. **Local math** — arithmetic questions are solved instantly.
2. **Document-based rules** — questions about the document number digits use the provided input.
3. **Capital city dictionary** — department capital questions are answered from a predefined map.
4. **Groq AI** — any other question is sent to LLaMA 3.3-70B via Groq, which interprets natural language and returns the answer.

This design minimizes external API usage (and associated costs) by resolving most cases locally.

### ASP.NET iframe handling

The Procuraduría portal uses a form embedded in an iframe with ASP.NET postbacks. The system locates the correct iframe, operates within it, and waits for reload cycles after each interaction. Wait times are calibrated to ensure the DOM has updated before proceeding.

---

## Roadmap

- [x] Basic form automation
- [x] Verification question resolution (math + dictionary + Groq)
- [x] Web interface with Tailwind CSS
- [ ] Visual captcha support with computer vision
- [ ] Rate limiting and automatic retries
- [ ] Dockerization
- [ ] Automated tests (unit + integration)
- [ ] Multi-language frontend support
- [ ] Query history with a lightweight database

---


<div align="center">

Made with ❤️ by <a href="https://sebas-dev.vercel.app/" target="_blank" rel="noopener noreferrer">Sebastián V</a>

</div>