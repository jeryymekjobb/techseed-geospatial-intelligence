"""Continuous monitoring of an area with live sources, as the MVP one-pager describes it
(docs/mvp/onepager-mvp.md): events in, live sources, detection, alarms the operator confirms or
dismisses, a sourced briefing and contact lists by role. Run with

    .venv/bin/python -m app.monitoring --area flenkommun

It is a service of its own beside the demo and does not touch the scenario playback. Nothing is
sent onward: an alarm only changes state when the operator confirms or dismisses it.
"""
