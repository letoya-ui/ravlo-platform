\# 🧠 Caughman Mason Intelligence – AI Module



This directory contains all templates for the \*\*Caughman Mason Intelligence Suite\*\* — the core AI-driven command center of the LoanMVP platform.  

Each template is designed with a unified \*\*dark-glow aesthetic\*\*, consistent with the Caughman Mason brand.



---



\## 🎯 Overview



| Template | Route | Description |

|-----------|--------|-------------|

| `\_sidebar\_ai.html` | (included) | Shared sidebar component used across all AI templates. Contains Lucide icons, navigation links, and brand header “Caughman Mason Intelligence.” |

| `dashboard.html` | `/ai/dashboard` | The \*\*AI Command Center\*\* — a centralized console displaying key system KPIs, ApexCharts visualizations, and a floating mini chat dock. |

| `chat.html` | `/ai/chat` | Full-page AI chat assistant for text-based interaction with the intelligence system. Supports POST requests returning `{"reply": "..."}` JSON. |

| `borrower\_intake.html` | `/ai/borrower\_intake` | Form for collecting borrower details. On submit, POSTs to the same route and redirects to the result page. |

| `borrower\_intake\_result.html` | `/ai/borrower\_intake\_result` | Displays borrower input summary and AI-generated evaluation insight returned from the intake form. |

| `predictive.html` | `/ai/predictive` | Interactive dashboard with \*\*ApexCharts\*\* showing approval rate, default risk, and credit health metrics. Also displays an AI summary card. |

| `workflow.html` | `/ai/workflow` | Interface for creating automated workflows via AI. Submits form data to the `/ai/workflow` route, then renders the AI’s JSON-formatted workflow plan. |

| `memory.html` | `/ai/memory` | Displays recent AI memory entries from `assistant.list\_memories()`. Includes timestamps, context, and data content formatted as readable logs. |

| `omni.html` | `/ai/omni` | The \*\*Omni Panel\*\* — cross-departmental interface connecting CRM, Borrower, Processor, Loan Officer, and Underwriter AI tools. Allows per-context queries. |

| `voice.html` | `/ai/voice` | Voice-based interface mockup supporting simulated mic input and playback. Designed for future integration with real STT/TTS APIs. |



---



\## 🧩 Integration Notes



\### \*\*Brand Consistency\*\*

\- Follows `:root` color system used in Loan Officer Dashboard:  

&nbsp; - `--bg: #0f0f11`  

&nbsp; - `--panel: #15161a`  

&nbsp; - `--accent: #7ab8ff` (primary blue glow)  

&nbsp; - `--line: #282b31`  

\- Uses \[Lucide Icons](https://lucide.dev/icons/) CDN for modern, clean vector icons.  

\- Each template imports `\_sidebar\_ai.html` for unified navigation and layout alignment.



\### \*\*Frontend Libraries\*\*

\- \[ApexCharts.js](https://apexcharts.com/) — used for all chart visualizations.  

\- Lucide Icons (CSS font-based version) — used for consistent iconography.  

\- Vanilla JS for lightweight async fetch calls and DOM updates.



\### \*\*Flask Dependencies\*\*

Ensure the following AI routes exist in your Flask app:



```python

@ai\_bp.route('/dashboard')

@ai\_bp.route('/chat', methods=\['GET', 'POST'])

@ai\_bp.route('/borrower\_intake', methods=\['GET', 'POST'])

@ai\_bp.route('/predictive')

@ai\_bp.route('/workflow', methods=\['GET', 'POST'])

@ai\_bp.route('/memory')

@ai\_bp.route('/omni')

@ai\_bp.route('/voice')



