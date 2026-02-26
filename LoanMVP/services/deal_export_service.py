"""
Deal Export Service
-------------------
Charts and visualizations for deal reports.
"""

import base64
import matplotlib.pyplot as plt
import io


def _encode_plot_to_base64():
    """Convert current Matplotlib figure to base64 string."""
    buffer = io.BytesIO()
    plt.savefig(buffer, format="png", bbox_inches="tight")
    buffer.seek(0)
    encoded = base64.b64encode(buffer.read()).decode("utf-8")
    plt.close()
    return encoded


def generate_cashflow_chart(net_cash_flow, annual_cash_flow):
    """
    Generate a simple 12‑month cash flow chart.
    """
    months = list(range(1, 13))
    monthly_values = [net_cash_flow] * 12

    plt.figure(figsize=(8, 4))
    plt.plot(months, monthly_values, marker="o", color="#007bff")
    plt.title("Monthly Cash Flow")
    plt.xlabel("Month")
    plt.ylabel("Cash Flow ($)")
    plt.grid(True, linestyle="--", alpha=0.5)

    return _encode_plot_to_base64()


def generate_roi_vs_rehab_chart(roi_values, rehab_costs):
    """
    ROI sensitivity chart.
    """
    plt.figure(figsize=(8, 4))
    plt.plot(rehab_costs, roi_values, marker="o", color="#28a745")
    plt.title("ROI vs Rehab Cost")
    plt.xlabel("Rehab Cost ($)")
    plt.ylabel("ROI (%)")
    plt.grid(True, linestyle="--", alpha=0.5)

    return _encode_plot_to_base64()


def generate_amortization_chart(principal_values, interest_values):
    """
    Loan amortization breakdown chart.
    """
    months = list(range(1, len(principal_values) + 1))

    plt.figure(figsize=(8, 4))
    plt.plot(months, principal_values, label="Principal", color="#17a2b8")
    plt.plot(months, interest_values, label="Interest", color="#dc3545")
    plt.title("Loan Amortization Breakdown")
    plt.xlabel("Month")
    plt.ylabel("Amount ($)")
    plt.legend()
    plt.grid(True, linestyle="--", alpha=0.5)

    return _encode_plot_to_base64()
