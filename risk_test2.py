from app import calculate_trade

tests = [

    # TEST 1 - EURUSD BUY
    {
        "name": "EURUSD BUY",
        "params": (1000, 0.10, 1.1000, 1.1050, 1.0950, "buy", "EURUSD")
    },

    # TEST 2 - EURUSD SELL
    {
        "name": "EURUSD SELL",
        "params": (1000, 0.10, 1.1000, 1.0950, 1.1050, "sell", "EURUSD")
    },

    # TEST 3 - USDJPY
    {
        "name": "USDJPY BUY",
        "params": (1000, 0.10, 110.00, 111.00, 109.00, "buy", "USDJPY")
    },

    # TEST 4 - LOT SIZE
    {
        "name": "LOT SIZE x10",
        "params": (1000, 1.00, 1.1000, 1.1050, 1.0950, "buy", "EURUSD")
    },

    # TEST 5 - GOLD
    {
        "name": "XAUUSD",
        "params": (1000, 0.10, 2000, 2010, 1990, "buy", "XAUUSD")
    },

    # TEST 6 - ERRORE SL
    {
        "name": "SL ERROR",
        "params": (1000, 0.10, 1.1000, 1.1050, 1.1010, "buy", "EURUSD")
    }

]

for t in tests:
    print("\n---", t["name"], "---")
    result = calculate_trade(*t["params"])
    print(result)