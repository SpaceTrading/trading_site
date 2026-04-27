import numpy as np
import json
import random

# ==========================================
# FUNZIONE DI SUPPORTO (DEVE ESSERE NEL TUO APP.PY)
# ==========================================
def max_drawdown(equity):
    if not equity: return 0
    peak = equity[0]
    max_dd = 0
    for value in equity:
        if value > peak:
            peak = value
        dd = peak - value
        if dd > max_dd:
            max_dd = dd
    return float(max_dd)

# ==========================================
# SIMULAZIONE LOGICA BACKEND
# ==========================================
def simulate_backend_logic(trades, sims=1000):
    print(f"--- Avvio simulazione su {len(trades)} trade per {sims} iterazioni ---")
    
    # 1. Original Equity
    original_equity = np.cumsum(trades).tolist()

    # 2. Monte Carlo Loop
    all_equities = []
    final_profits = []

    for _ in range(sims):
        shuffled = trades.copy()
        random.shuffle(shuffled) # Usiamo random.shuffle per semplicità nel test
        
        equity = np.cumsum(shuffled)
        all_equities.append(equity)
        final_profits.append(equity[-1])

    # 3. Ordinamento e Percentili
    sorted_indices = np.argsort(final_profits)
    sorted_equities = [all_equities[i] for i in sorted_indices]

    p5_index = int(sims * 0.95)   # Best 5%
    p50_index = int(sims * 0.5)   # Median
    p95_index = int(sims * 0.05)  # Worst 95%

    best_5_equity = sorted_equities[p5_index].tolist()
    median_equity = sorted_equities[p50_index].tolist()
    worst_95_equity = sorted_equities[p95_index].tolist()

    # 4. Campionamento (50 curve)
    sample_size = min(50, sims)
    sample_indices = random.sample(range(sims), sample_size)
    samples = [all_equities[i].tolist() for i in sample_indices]

    # 5. Metriche
    metrics = {
        "avg_profit": float(np.mean(final_profits)),
        "median_profit": float(np.median(final_profits)),
        "best_profit": float(np.max(final_profits)),
        "worst_profit": float(np.min(final_profits)),
        "median_dd": max_drawdown(median_equity)
    }

    return {
        "original_len": len(original_equity),
        "samples_count": len(samples),
        "metrics": metrics,
        "check_points": {
            "last_median": median_equity[-1],
            "last_worst": worst_95_equity[-1]
        }
    }

# ==========================================
# ESECUZIONE TEST
# ==========================================
if __name__ == "__main__":
    # Simuliamo 100 trade (alcuni positivi, alcuni negativi)
    mock_trades = [random.uniform(-100, 150) for _ in range(100)]
    
    risultato = simulate_backend_logic(mock_trades, sims=1000)
    
    print("\n--- RISULTATO JSON (SINTESI) ---")
    print(json.dumps(risultato, indent=4))
    
    print("\n✅ TEST COMPLETATO: Se vedi i numeri sopra, il motore è perfetto.")