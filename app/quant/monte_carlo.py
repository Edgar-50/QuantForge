import numpy as np

def monte_carlo_terminal_values(initial_value, annual_return, annual_volatility, years=1.0, simulations=5000, seed=42):
    rng = np.random.default_rng(seed)
    z = rng.normal(size=simulations)
    terminal = initial_value * np.exp(
        (annual_return - 0.5 * annual_volatility ** 2) * years
        + annual_volatility * np.sqrt(years) * z
    )
    q = np.quantile(terminal, [0.01, 0.05, 0.25, 0.5, 0.75, 0.95, 0.99])
    return {
        "mean_terminal_value": float(terminal.mean()),
        "median_terminal_value": float(np.median(terminal)),
        "probability_of_loss": float(np.mean(terminal < initial_value)),
        "p01": float(q[0]), "p05": float(q[1]), "p25": float(q[2]),
        "p50": float(q[3]), "p75": float(q[4]), "p95": float(q[5]), "p99": float(q[6])
    }
