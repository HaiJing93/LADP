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

### Fund rankings

When you upload the portfolio Excel sheets and a rankings workbook, the chatbot can fetch ranking data for a specific ticker using the `get_fund_rankings` tool.
To see how a fund stacks up against the other marked funds in a sheet, ask for the rankings from that sheet and the bot will use `get_starred_ticker_rankings` to gather them. The bot returns these rankings in a table so the different tickers are easy to compare. Any starred row that contains the word "Average" is ignored so only real tickers are listed. If you do not mention a sheet name, the bot will ask you to provide one. Starred rows may be located in either workbook, so make sure both files are uploaded.
Use `list_excel_sheets` to list the available sheet names. Pass `workbook="ranking"` or `workbook="portfolio"` to view sheets from a single workbook, or `workbook="both"` to show the sheet names from every uploaded workbook.
Make sure both the portfolio workbook and the rankings workbook are uploaded in the sidebar before requesting any ranking lookups or comparisons.
