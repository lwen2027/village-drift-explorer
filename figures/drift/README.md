# Drift figures

Built by `scripts/figures/plot_drift_concentration.py` and `scripts/figures/plot_drift_timeline.py` from `data/drift_axes_v1.csv`. Figures are PNG at 300 dpi. Titles and section headers use Lora, the AI Village site's serif, bundled in `scripts/figures/fonts/` under the SIL Open Font License. Other text uses Helvetica Neue; on a machine without it, matplotlib falls back to its default font.

## drift_concentration: main figure

Drift hours by (a) mechanism and (b) trigger across 403 goal-period episodes (36 agents, 5,723 h). Each bar is split into the single largest contributing agent, the next two, and all others. Labels give total hours, the number of agents, and the top agent's share. After the agents' own plans, the most common triggers are ordinary events: a finished task with no next step, a pending dependency, a lull. Waiting loops are widespread (28 agents). Self-imposed rules and proxy objectives are each concentrated in about ten agents. Several triggers come mostly from one agent: lull (GPT-5.5, 69%), agent message without a request (Gemini 2.5 Pro, 73%), human request (Claude Fable 5, 75%), and operator decision (DeepSeek-V3.2 only).

## drift_agent_profile: supplementary figure

Each agent's drift broken down by (a) mechanism and (b) trigger, as the share of that agent's own drift hours. Rows sum to 100% within each panel. Cells of 5% or more are numbered, and the agent's total drift hours are on the right. Agents are sorted by total drift hours. Rows for agents with very little drift (the control agents at the bottom, under 2 h) rest on one or two short episodes.

## drift_timeline

Drift episodes across the goal period (6 Jul – 3 Oct 2026) for the 31 agents with drift interview points, in the style of the findings page's goal atlas. Each row gives the agent and its short goal, its goal window (pale pill) and each goal-period drift episode as a rust pill from its first to its last drift bout. Triangles mark interview points; the right column gives total drift hours and episode count. Rows are sorted by drift hours. The heaviest drifters show one or two episodes running for weeks to the end of the period, while others drift in many short, separate episodes.
