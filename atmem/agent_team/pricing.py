"""Reconcile a selected reader's declared tariff with its metered tokens."""

from decimal import Decimal, ROUND_HALF_UP
import re


def reader_terms(model, prices):
    if model is None:
        if prices is not None:
            raise ValueError("A reader tariff requires a selected reader model.")
        return {}
    if not isinstance(model, str) or not model.isprintable() or not 0 < len(model.strip()) <= 160:
        raise ValueError("Invalid reader model.")
    terms = {"reader_model": model}
    if prices is not None:
        keys = {"input_usd_per_million", "output_usd_per_million"}
        if (
            not isinstance(prices, dict)
            or prices.keys() != keys
            or not all(
                isinstance(value, str) and re.fullmatch(r"(?:0|[1-9][0-9]{0,4})(?:\.[0-9]{1,6})?", value)
                for value in prices.values()
            )
        ):
            raise ValueError("Supply both USD-per-million token rates as non-negative decimal strings.")
        terms["reader_pricing"] = dict(prices)
    return terms


def reader_cost(run, usage):
    actual = usage.get("cost_microusd")
    rates = run.get("reader_pricing")
    estimate = None
    if (
        rates
        and usage.get("model") == run["reader_model"]
        and {"input_tokens", "output_tokens"} <= usage.keys()
    ):
        # One million microdollars per dollar cancels the million-token denominator.
        amount = usage["input_tokens"] * Decimal(rates["input_usd_per_million"]) + usage[
            "output_tokens"
        ] * Decimal(rates["output_usd_per_million"])
        estimate = int(amount.to_integral_value(rounding=ROUND_HALF_UP))
    return {
        "estimated_reader_cost_microusd": estimate,
        "reported_reader_cost_microusd": actual,
        "reader_cost_delta_microusd": None if actual is None or estimate is None else actual - estimate,
    }
