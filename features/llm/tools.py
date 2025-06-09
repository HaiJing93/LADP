# features/llm/tools.py
# ------------------------------------------------------------------- #
#  Existing schemas (UNCHANGED)                                       #
# ------------------------------------------------------------------- #

PIE_TOOL_SCHEMA = {
    "name": "create_pie_chart",
    "description": "Create a pie chart from categorical labels and numeric values.",
    "parameters": {
        "type": "object",
        "properties": {
            "labels": {"type": "array", "items": {"type": "string"}},
            "values": {"type": "array", "items": {"type": "number"}},
        },
        "required": ["labels", "values"],
    },
}

PORTFOLIO_TOOL_SCHEMA = {
    "name": "calculate_portfolio_metrics",
    "description": (
        "Calculate cumulative & annualised return, volatility and Sharpe from a "
        "price or return series. Set 'returns_are_percent' if the return values "
        "are in percent form."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "series": {"type": "array", "items": {"type": "number"}},
            "is_prices": {"type": "boolean", "default": True},
            "periods_per_year": {"type": "integer", "default": 252},
            "risk_free_rate": {"type": "number", "default": 0.0},
            "returns_are_percent": {"type": "boolean", "default": False},
        },
        "required": ["series"],
    },
}

YEARLY_TOOL_SCHEMA = {
    "name": "calculate_yearly_performance",
    "description": "Aggregate monthly decimal returns into yearly returns.",
    "parameters": {
        "type": "object",
        "properties": {
            "dates": {"type": "array", "items": {"type": "string"}},
            "returns": {"type": "array", "items": {"type": "number"}},
        },
        "required": ["dates", "returns"],
    },
}

# ------------------------------------------------------------------- #
#  NEW Yahoo-Finance schemas                                          #
# ------------------------------------------------------------------- #

QUOTE_TOOL_SCHEMA = {
    "name": "get_stock_quote",
    "description": "Return latest price and key ratios for a single equity ticker.",
    "parameters": {
        "type": "object",
        "properties": {
            "ticker": {
                "type": "string",
                "description": "Ticker symbol, e.g. 'AAPL' or 'TSLA'.",
            }
        },
        "required": ["ticker"],
    },
}

HISTORY_TOOL_SCHEMA = {
    "name": "get_stock_history",
    "description": (
        "Fetch historical prices for a ticker and return a list of "
        "[(date, price), …] so the assistant can quote specific dates."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "ticker": {"type": "string"},
            "period": {
                "type": "string",
                "enum": [
                    "1d",
                    "5d",
                    "1mo",
                    "3mo",
                    "6mo",
                    "1y",
                    "2y",
                    "5y",
                    "10y",
                    "ytd",
                    "max",
                ],
                "default": "1y",
                "default": "1y"
            },
            "interval": {
                "type": "string",
                "enum": ["1m", "5m", "15m", "30m", "60m", "1d", "1wk", "1mo"],
                "default": "1d",
            },
            "col": {
                "type": "string",
                "enum": [
                    "Open",
                    "High",
                    "Low",
                    "Close",
                    "Adj Close",
                    "Volume",
                ],
                "default": "Adj Close",
            },
        },
        "required": ["ticker"],
    },
}

FX_RATE_TOOL_SCHEMA = {
    "name": "get_fx_rate",
    "description": "Return the latest FX spot rate for a currency pair like 'USD/SGD'.",
    "parameters": {
        "type": "object",
        "properties": {
            "pair": {
                "type": "string",
                "description": "Currency pair, e.g. 'USD/SGD'.",
            }
        },
        "required": ["pair"],
    },
}
DRAWDOWN_TOOL_SCHEMA = {
    "name": "calculate_max_drawdown",
    "description": (
        "Return the maximum peak-to-trough drawdown (as decimal, e.g., -0.25) "
        "from a series of price or return values. Accepts the same arguments "
        "as calculate_portfolio_metrics but only outputs the single drawdown."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "series": {"type": "array", "items": {"type": "number"}},
            "is_prices": {"type": "boolean", "default": True},
        },
        "required": ["series"],
    },
}

# ------------------------------------------------------------------- #
#  Excel schema                                                       #
# ------------------------------------------------------------------- #

EXCEL_TOOL_SCHEMA = {
    "name": "get_excel_data",
    "description": (
        "Return a JSON array of rows from an uploaded Excel sheet. "
        "Use this to inspect tabular data provided by the user."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "sheet": {"type": "string"},
            "rows": {"type": "integer", "default": 5},
        },
        "required": ["sheet"],
    },
}

# ------------------------------------------------------------------- #
#  Python execution schema                                          #
# ------------------------------------------------------------------- #

PYTHON_TOOL_SCHEMA = {
    "name": "execute_python_code",
    "description": (
        "Execute arbitrary Python code and return any printed output or the"
        " result. Use this for calculations that require Python. The runtime"
        " has pandas available as 'pd' along with 'json' and 'math'."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "code": {"type": "string", "description": "Python code to execute."},
        },
        "required": ["code"],
    },
}


# ------------------------------------------------------------------- #
#  Master list passed to OpenAI                                       #
# ------------------------------------------------------------------- #
TOOLS = [
    {"type": "function", "function": PIE_TOOL_SCHEMA},
    {"type": "function", "function": PORTFOLIO_TOOL_SCHEMA},
    {"type": "function", "function": YEARLY_TOOL_SCHEMA},
    {"type": "function", "function": QUOTE_TOOL_SCHEMA},  # ← NEW
    {"type": "function", "function": HISTORY_TOOL_SCHEMA},
    {"type": "function", "function": FX_RATE_TOOL_SCHEMA},
    {"type": "function", "function": DRAWDOWN_TOOL_SCHEMA},  # ← NEW
    {"type": "function", "function": EXCEL_TOOL_SCHEMA},      # ← NEW
    {"type": "function", "function": PYTHON_TOOL_SCHEMA},
    ]

