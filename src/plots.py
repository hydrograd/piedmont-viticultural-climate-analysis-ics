"""Static plots for quick inspection of the processed outputs."""
from __future__ import annotations

import matplotlib.pyplot as plt
import pandas as pd

import config


def plot_production(csv_path=config.PRODUCTION_CSV,
                    save_to=config.OUTPUTS / "production_timeline.png"):
    """Save a two-panel production and yield timeline for the regional series."""
    df = pd.read_csv(csv_path)
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 7), sharex=True)

    ax1.plot(df["year"], df["production"] / 1e6, marker="o", color="#6a1b9a")
    ax1.set_ylabel("Production (million quintals)")
    ax1.set_title(f"{config.REGION_NAME} wine-grape production, "
                  f"{int(df['year'].min())} to {int(df['year'].max())}")
    ax1.grid(alpha=0.3)

    ax2.plot(df["year"], df["yield_per_ha"], marker="s", color="#2e7d32")
    ax2.set_ylabel("Yield (quintals / ha)")
    ax2.set_xlabel("Year")
    ax2.grid(alpha=0.3)

    fig.tight_layout()
    fig.savefig(save_to, dpi=130)
    print(f"Saved {save_to}")


if __name__ == "__main__":
    plot_production()
