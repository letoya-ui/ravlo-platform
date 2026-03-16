# \# AI Assistant

# 

# The AI Assistant panel surfaces insights, recommendations, risk alerts, and opportunities. It acts as a contextual advisor embedded directly into the Command Center.

# 

# \## Purpose

# 

# The AI Assistant answers:  

# “What should I pay attention to, and what should I do next?”

# 

# It should:

# \- highlight risks and opportunities  

# \- provide prioritized recommendations  

# \- connect insights to concrete actions  

# 

# \## Types of Insights

# 

# \- Portfolio performance insights  

# \- Deal‑level risks or opportunities  

# \- Market or rate changes affecting the portfolio  

# \- Upcoming deadlines or tasks with impact  

# \- Suggested next steps (e.g., “Refinance this property,” “Review this deal”)  

# 

# \## Anatomy

# 

# \- Panel title (e.g., “AI Assistant” or “Ravlo Insights”)  

# \- Insight list (cards or rows)  

# \- Each insight includes:

# &#x20; - Title  

# &#x20; - Short explanation  

# &#x20; - Impact level (e.g., low, medium, high)  

# &#x20; - Suggested action (button or link)  

# 

# \## Layout

# 

# \- Positioned in the mid‑tier of the Command Center layout.  

# \- Uses a vertical list or stack of insight cards.  

# \- Limited number of visible insights (e.g., 3–5) to avoid overload.  

# 

# \## Component References

# 

# \- Insight card  

# \- Badge / impact indicator  

# \- Buttons or links for actions  

# \- Optional: filters (e.g., “All,” “Risks,” “Opportunities”)  

# 

# \## Behavior

# 

# \- Insights should update based on new data and events.  

# \- Clicking an action should deep‑link into the relevant module or view.  

# \- Insights should be dismissible or snoozable where appropriate.  

# 

# \## States

# 

# \- \*\*Normal:\*\* A small set of prioritized insights.  

# \- \*\*High activity:\*\* More insights available, but still ordered by priority.  

# \- \*\*Empty:\*\* If no insights are available, show a reassuring message (e.g., “No critical insights right now. Your portfolio is stable.”).  

# \- \*\*Error:\*\* If AI insights cannot load, show a clear fallback state.  

# 

# \## Do

# 

# \- Keep insights concise and actionable.  

# \- Clearly indicate why an insight matters.  

# \- Tie every insight to a concrete next step.  

# 

# \## Don’t

# 

# \- Flood the investor with low‑value or noisy insights.  

# \- Use overly technical language without explanation.  

# \- Present conflicting or redundant recommendations.



