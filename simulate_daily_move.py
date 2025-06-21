import matplotlib.ticker as ticker
import numpy as np
import matplotlib.pyplot as plt


def simulate_tqqq_price(start_price, nasdaq_vol, num_days, num_simulations):
    """
    Simulate future TQQQ prices using a Monte Carlo approach.

    Parameters:
        start_price (float): Current TQQQ price
        nasdaq_vol (float): Annualized volatility of Nasdaq index (e.g. 0.25 for 25%)
        num_days (int): Number of days to simulate forward
        num_simulations (int): Number of simulation paths

    Returns:
        np.ndarray: Final simulated TQQQ prices
    """

    # Convert annual volatility to daily
    daily_vol = nasdaq_vol / np.sqrt(252)

    # Preallocate simulation matrix
    tqqq_prices = np.full((num_simulations,), start_price, dtype=np.float64)

    for day in range(num_days):
        # Simulate daily Nasdaq return
        nasdaq_daily_return = np.random.normal(
            0, daily_vol, size=num_simulations)
        # TQQQ return is 3x Nasdaq daily return
        tqqq_daily_return = 3 * nasdaq_daily_return
        # Update TQQQ price
        tqqq_prices *= np.exp(tqqq_daily_return)

    return tqqq_prices


# Parameters
current_price = 75.6
volatility = 0.18  # annualized volatility
days_forward = 15
num_simulations = 10000

# Run simulation
simulated_prices = simulate_tqqq_price(
    start_price=current_price,
    nasdaq_vol=volatility,
    num_days=days_forward,
    num_simulations=num_simulations
)


# Plot cumulative distribution
plt.figure(figsize=(10, 6))
counts, bins, patches = plt.hist(
    simulated_prices,
    bins=100,
    cumulative=True,
    density=True,
    color='skyblue',
    edgecolor='black',
    label='CDF'
)
plt.axvline(current_price, color='red', linestyle='--', label='Start Price')
plt.title(
    f"Cumulative Distribution of TQQQ Prices in {days_forward} Days\n({num_simulations} Simulations)")
plt.xlabel("TQQQ Price")
plt.ylabel("Cumulative Probability")
# Add minor ticks
plt.gca().xaxis.set_major_locator(ticker.MultipleLocator(5))
plt.gca().xaxis.set_minor_locator(ticker.MultipleLocator(1))
plt.gca().yaxis.set_major_locator(ticker.MultipleLocator(0.1))
plt.grid(True, which='both', linestyle='--', linewidth=0.5)
plt.legend()
plt.tight_layout()
plt.show()
plt.savefig("simulated_tqqq_prices.png")

# Compute TQQQ volatility
log_returns = np.log(simulated_prices / current_price)
realized_std = np.std(log_returns)
annualized_vol = realized_std * np.sqrt(252 / days_forward)
print(f"Estimated Annualized Volatility of TQQQ: {annualized_vol:.2%}")
