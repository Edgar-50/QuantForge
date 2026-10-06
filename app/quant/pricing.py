import math

def _norm_cdf(x):
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))

def black_scholes(spot, strike, time_to_maturity, risk_free_rate, volatility, option_type="call"):
    if min(spot, strike, time_to_maturity, volatility) <= 0:
        raise ValueError("spot, strike, time and volatility must be positive")

    sqrt_t = math.sqrt(time_to_maturity)
    d1 = (
        math.log(spot / strike) + (risk_free_rate + 0.5 * volatility ** 2) * time_to_maturity
    ) / (volatility * sqrt_t)
    d2 = d1 - volatility * sqrt_t
    disc = math.exp(-risk_free_rate * time_to_maturity)

    call = spot * _norm_cdf(d1) - strike * disc * _norm_cdf(d2)
    put = strike * disc * _norm_cdf(-d2) - spot * _norm_cdf(-d1)
    price = call if option_type.lower() == "call" else put

    pdf = math.exp(-0.5 * d1 * d1) / math.sqrt(2 * math.pi)
    delta = _norm_cdf(d1) if option_type.lower() == "call" else _norm_cdf(d1) - 1
    gamma = pdf / (spot * volatility * sqrt_t)
    vega = spot * pdf * sqrt_t / 100.0
    theta_call = (-(spot * pdf * volatility) / (2 * sqrt_t) - risk_free_rate * strike * disc * _norm_cdf(d2)) / 365.0
    theta_put = (-(spot * pdf * volatility) / (2 * sqrt_t) + risk_free_rate * strike * disc * _norm_cdf(-d2)) / 365.0
    rho_call = strike * time_to_maturity * disc * _norm_cdf(d2) / 100.0
    rho_put = -strike * time_to_maturity * disc * _norm_cdf(-d2) / 100.0

    return {
        "option_type": option_type.lower(),
        "price": float(price),
        "delta": float(delta),
        "gamma": float(gamma),
        "vega_per_1pct": float(vega),
        "theta_per_day": float(theta_call if option_type.lower() == "call" else theta_put),
        "rho_per_1pct": float(rho_call if option_type.lower() == "call" else rho_put),
        "d1": float(d1),
        "d2": float(d2),
    }
