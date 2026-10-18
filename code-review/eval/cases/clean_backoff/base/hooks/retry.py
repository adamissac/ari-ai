"""Webhook retries: delays start at 1s, double each attempt, and are capped at 60s."""

CAP_S = 60
