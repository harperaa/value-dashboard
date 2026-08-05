# Dashboard (value-dashboard) — Hermes Plugin

> Aligned with the mentoring of **Dr. Allen Harper, AI Cyber Value Creator™** — join the community at [AI Cyber Value Creators on Skool](https://www.skool.com/ai-cyber-value-creators).

The mentee's metrics home for [Hermes Agent](https://github.com/NousResearch/hermes-agent) — first in the sidebar, launching with the **AI ROI widget** and built to grow more metrics.

## The AI ROI widget

- **Real usage, not estimates** — collectors pull actual LLM spend from every connected provider with a usage API: OpenRouter (per-key spend), Anthropic (org cost report, admin key), OpenAI (org costs, admin key). Providers without usage APIs (xAI, Gemini, DeepSeek) are labeled honestly and covered by a manual monthly-spend override, so the ROI never rests on invented numbers.
- **The transparent 8-step methodology** from [ai-saves.com](https://www.ai-saves.com/en): team cost ×1.3 payroll burden → hours on the task → effective hourly rate → automation share (their published medians: support 65%, content 55%, analytics 50%, search 70%) → gross savings → net of every AI dollar → payback → first-year ROI. Every intermediate value renders in the step-by-step panel — nothing hidden.
- **The x-factor headline** — ROI% ÷ 100 + 1, so 1,900% reads as **20x**: every AI dollar came back as twenty.
- **Parameters from what we know about you** — the host LLM derives employees / time value / hours / automation share from the AICVC Roadmap's Company Context (with its reasoning shown), falling back to standard blended rates: analysis $75/h, engineering $95/h, marketing $60/h → $76.67/h. Everything is editable inline; when AI cost is zero the widget says a ratio isn't meaningful yet rather than printing infinity.

## Layout

```
plugin.yaml        manifest
store.py           kv sqlite (params, usage snapshots) + env-key presence
usage.py           provider usage collectors (ok / unsupported / error states)
roi.py             the 8-step computation, x-factor, Company-Context derivation
dashboard/         the /metrics page (React via the hermes plugin SDK)
tests/             pytest suite — includes a test pinning our math to the
                   ai-saves.com base scenario (ROI 1,921%)
```

MIT licensed.
