# PDF-Aware Finance Chatbot

This project provides a Streamlit web application that lets you chat about uploaded PDF financial statements and perform portfolio analysis. It relies on Azure OpenAI for language model responses and embeddings. The app supports PDF indexing, portfolio metrics calculation, and market data retrieval via Yahoo Finance.

## Installation

1. Clone this repository and change into the project folder.
2. Install the Python dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Create a `.env` file in the project root containing your Azure OpenAI credentials (e.g. `AZURE_OPENAI_API_KEY`, `AZURE_OPENAI_CHAT_DEPLOYMENT_NAME`, `AZURE_OPENAI_ENDPOINT`, etc.).

## Running the app

Start the Streamlit interface with:
```bash
streamlit run appp.py
```
Once running, upload one or more PDF statements in the sidebar, build the index and then chat with the bot in the main window.

### UI theme

The app ships with a basic Streamlit theme that reflects the corporate colours `#242459` and white. You can adjust these values in `.streamlit/config.toml`.
