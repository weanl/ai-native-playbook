"""UI module - Streamlit web interface.

This module provides the Streamlit web UI for NextAIOpsAlgoApp:
- app.py: Main application (data upload + algorithm selection + experiment run + visualization)

Streamlit UI calls pipeline.run_experiment and storage queries;
no direct business logic or storage access in UI layer.
"""