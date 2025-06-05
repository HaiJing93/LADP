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
#  Master list passed to OpenAI                                       #
# ------------------------------------------------------------------- #
TOOLS = [
    {"type": "function", "function": PIE_TOOL_SCHEMA},
    {"type": "function", "function": PORTFOLIO_TOOL_SCHEMA},
    {"type": "function", "function": YEARLY_TOOL_SCHEMA},
    {"type": "function", "function": QUOTE_TOOL_SCHEMA},  # ← NEW
    {"type": "function", "function": HISTORY_TOOL_SCHEMA},
    {"type": "function", "function": DRAWDOWN_TOOL_SCHEMA},  # ← NEW
]
