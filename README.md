# Introduction

LLMKGraph leverages NLP to extract relationships from textual data on
Age-related Macular Degeneration (AMD) and integrating this information 
into a knowledge graph, enhancing insights into this complex condition. 
It features an interactive chat system for querying the graph, 
supported by a VueJS frontend and Flask backend.

# Installation

This project consists of four main components: GraphDB for the knowledge graph, 
Flask for the backend, VueJS for the frontend, and a Streamlit app for interactive 
chat. Follow these steps to get the system up and running on your local machine.

## Prerequisites
- Python (version 3.9 or newer) and Node.js must be installed on your computer.
- A running instance of GraphDB. Download and install 
from [GraphDB](https://www.ontotext.com/products/graphdb/download/) official site.
- An OpenAI API key for accessing OpenAI's services. Once you have your API key, 
set it as an environment variable named `OPENAI_API_KEY`:
- A Huggingface API token for accessing Huggingface models.

      export OPENAI_API_KEY="sk-...."
      export HUGGINGFACEHUB_API_TOKEN="hf_...."


## GraphDB Configuration

1. Launch GraphDB and create a new repository named `amd_repo`.
2. Populate the knowledge graph with AMD-related data using the Flask backend.

## Backend Setup

1. Navigate to the backend directory.
2. Create a virtual environment using Python 3.10.
3. Install the required Python packages

    `pip install -r requirements.txt`

4. Start the Flask server

    `flask run`

## Streamlit App Setup

1. Navigate to the backend directory.
2. Start the Streamlit app:

   `streamlit run streamlit_app.py`

3. Note the URL where the Streamlit app is running 
(typically http://localhost:8501). This URL will be used to embed 
the Streamlit app in frontend.

## Frontend Setup

1. Navigate to the frontend directory.
2. Install the required Node.js packages:

   `npm install`

3. Start the VueJS development server

   `npm run dev`

4. The VueJS application will now be running and accessible via the browser at `http://localhost:5173/'
