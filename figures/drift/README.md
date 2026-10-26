# Drift figures

Built by `scripts/figures/plot_drift_concentration.py` from `data/drift_axes_v1.csv`. Figures are PNG at 300 dpi.

## drift_concentration: main figure

Drift hours by (a) mechanism and (b) trigger across 403 goal-period episodes (36 agents, 5,723 h). Triggers are grouped into families. Each bar is split into the single largest contributing agent, the next two, and all others. Labels give total hours, the number of agents, and the top agent's share. Waiting loops are widespread (28 agents). Self-imposed rules and proxy objectives are each concentrated in about ten agents. Several triggers come mostly from one agent: lull (GPT-5.5, 69%), agent message without a request (Gemini 2.5 Pro, 73%), human request (Claude Fable 5, 75%), and operator decision (DeepSeek-V3.2 only).

## drift_agent_profile: supplementary figure

Each agent's drift broken down by (a) mechanism and (b) trigger, as the share of that agent's own drift hours. Rows sum to 100% within each panel. Cells of 5% or more are numbered, and the agent's total drift hours are on the right. Agents are sorted by total drift hours. Vertical lines in (b) separate the trigger families shown in the main figure. Rows for agents with very little drift (the control agents at the bottom, under 2 h) rest on one or two short episodes.
