const { useState, useRef, useEffect } = React;

const ROLES = ["Realtor / Agent", "Real Estate Investor", "Mortgage Loan Officer", "Mortgage Processor / Underwriter", "Lender / Broker", "New to Real Estate"];
const GOALS = ["Close more deals this year", "Get my first deal", "Grow and scale my team", "Master mortgage & lending", "Build a rental portfolio", "Increase my income by 50%+"];
const CHALLENGES = ["Finding consistent leads", "Converting leads to clients", "Understanding financing & loans", "Managing my time and pipeline", "Building systems that scale", "Standing out in my market"];
const TIMELINES = ["30 days", "60 days", "90 days", "6 months"];
const INCOMES = ["Under $50K", "$50K–$100K", "$100K–$200K", "$200K+", "Prefer not to say"];

const SYSTEM = `You are the Ravlo Academy Business Plan Coach — an elite real estate business strategist who has helped thousands of realtors, investors, and mortgage professionals build scalable, profitable businesses.

Your expertise spans:
- Realtor business development (SOI, geographic farming, team building, CRM, branding)
- Real estate investing (BRRRR, multifamily, deal analysis, portfolio scaling)
- Mortgage & lending (loan officer production, pipeline management, referral networks, underwriting)
- Sales systems, lead generation, and conversion frameworks
- 90-day sprint planning with measurable KPIs

When creating a business plan, you ALWAYS produce a structured, specific, personalized document with these exact sections:

---
## 🎯 YOUR RAVLO BUSINESS PLAN
### Built for [Name] · [Role] · [Date]

---
## EXECUTIVE SUMMARY
2-3 sentences capturing who they are, their goal, and the core strategy to get there.

---
## ASSESSMENT
What you know about their current situation, strengths to build on, and gaps to close.

---
## 30-DAY SPRINT
**Theme:** [One-word focus]
Specific daily and weekly actions. Use actual numbers (call 10 people per day, post 3x per week, etc.)
- Week 1: ...
- Week 2: ...
- Week 3: ...
- Week 4: ...

---
## 60-DAY MILESTONES
Concrete, measurable targets they must hit by day 60. No vague language.

---
## 90-DAY VISION
A vivid, specific picture of where they will be if they execute the plan.

---
## KEY METRICS (Track Weekly)
A table of 5-7 specific metrics with target numbers.

---
## REVENUE PROJECTION
Conservative and optimistic projections based on their role and goal.

---
## ACCOUNTABILITY SYSTEM
How to stay on track — daily habits, weekly reviews, accountability partners.

---
## YOUR TOP 3 PRIORITIES THIS WEEK
The very first things they should do after reading this plan.

---

Rules:
- Always use real numbers, not ranges where possible
- Always personalize — never give generic advice
- Be direct and confident — this is a serious business document
- Use their name throughout
- End with an encouraging, direct closing statement`;

const API_ENDPOINT = "/academy/business-plan/generate";

function RavloBusinessPlan() {
  const [step, setStep] = useState("landing");
  const [form, setForm] = useState({ name: "", role: "", goal: "", challenge: "", timeline: "90 days", income: "", notes: "" });
  const [plan, setPlan] = useState("");
  const [loading, setLoading] = useState(false);
  const [messages, setMessages] = useState([]);
  const [chatInput, setChatInput] = useState("");
  const [chatLoading, setChatLoading] = useState(false);
  const [isMobile, setIsMobile] = useState(false);
  const messagesEndRef = useRef(null);
  const inputRef = useRef(null);

  useEffect(() => {
    const check = () => setIsMobile(window.innerWidth < 768);
    check();
    window.addEventListener("resize", check);
    return () => window.removeEventListener("resize", check);
  }, []);

  useEffect(() => { messagesEndRef.current?.scrollIntoView({ behavior: "smooth" }); }, [messages]);

  const generatePlan = async () => {
    setStep("generating");
    setLoading(true);
    const prompt = `Create a complete, personalized Ravlo Business Plan for:

Name: ${form.name}
Role: ${form.role}
Primary Goal: ${form.goal}
Biggest Challenge: ${form.challenge}
Timeline Focus: ${form.timeline}
Current Income Range: ${form.income || "Not specified"}
Additional Context: ${form.notes || "None provided"}

Build a full, specific, actionable business plan using the exact format in your instructions. Use ${form.name}'s name throughout. Make every number, action, and recommendation specific to a ${form.role} focused on "${form.goal}".`;

    try {
      const res = await fetch(API_ENDPOINT, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ model: "claude-opus-4-8", max_tokens: 1000, system: SYSTEM, messages: [{ role: "user", content: prompt }] }),
      });
      const data = await res.json();
      const text = data.content?.map(c => c.text || "").join("\n") || "Unable to generate plan. Please try again.";
      setPlan(text);
      setMessages([{ role: "assistant", content: `Your business plan is ready, ${form.name}! I've built it specifically around your goal to ${form.goal.toLowerCase()} as a ${form.role}. Ask me anything about it — I can drill deeper into any section, adjust the timeline, or help you take the first step right now.` }]);
      setStep("plan");
    } catch {
      setPlan("Connection error. Please try again.");
      setStep("plan");
    } finally { setLoading(false); }
  };

  const sendChat = async () => {
    const msg = chatInput.trim();
    if (!msg || chatLoading) return;
    setChatInput("");
    const newMsgs = [...messages, { role: "user", content: msg }];
    setMessages(newMsgs);
    setChatLoading(true);
    const ctx = `User: ${form.name} | Role: ${form.role} | Goal: ${form.goal} | Business Plan has been generated and shown to the user.`;
    try {
      const res = await fetch(API_ENDPOINT, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          model: "claude-opus-4-8", max_tokens: 1000,
          system: SYSTEM + `\n\nContext: ${ctx}\n\nThe user's full business plan:\n${plan}\n\nAnswer their follow-up questions with the same specificity and directness as the plan itself.`,
          messages: newMsgs,
        }),
      });
      const data = await res.json();
      const reply = data.content?.map(c => c.text || "").join("\n") || "Please try again.";
      setMessages([...newMsgs, { role: "assistant", content: reply }]);
    } catch { setMessages([...newMsgs, { role: "assistant", content: "Connection error. Please try again." }]); }
    finally { setChatLoading(false); setTimeout(() => inputRef.current?.focus(), 100); }
  };

  const fmt = (txt) => txt
    .replace(/^## (.*)/gm, '<div style="font-family:\'Cormorant Garamond\',serif;font-size:22px;font-weight:700;color:#D4AF6A;margin:28px 0 12px;padding-bottom:8px;border-bottom:1px solid rgba(212,175,106,0.15)">$1</div>')
    .replace(/^### (.*)/gm, '<div style="font-family:\'Cormorant Garamond\',serif;font-size:16px;font-weight:600;color:#EDE8DF;margin:20px 0 8px;letter-spacing:0.5px">$1</div>')
    .replace(/\*\*(.*?)\*\*/g, '<strong style="color:#D4AF6A;font-weight:600">$1</strong>')
    .replace(/^- (.*)/gm, '<div style="display:flex;gap:10px;margin:5px 0;align-items:flex-start"><span style="color:#D4AF6A;flex-shrink:0;margin-top:2px">▸</span><span style="color:#C8C0B4">$1</span></div>')
    .replace(/^---$/gm, '<hr style="border:none;border-top:1px solid rgba(212,175,106,0.1);margin:24px 0"/>')
    .replace(/\n\n/g, '<div style="height:8px"></div>')
    .replace(/\n/g, '<br/>');

  const fmtChat = (txt) => txt
    .replace(/\*\*(.*?)\*\*/g, '<strong style="color:#D4AF6A">$1</strong>')
    .replace(/^- (.*)/gm, '<div style="display:flex;gap:8px;margin:3px 0"><span style="color:#D4AF6A;flex-shrink:0">▸</span><span>$1</span></div>')
    .replace(/\n\n/g, '<div style="height:8px"></div>')
    .replace(/\n/g, '<br/>');

  const printPlan = () => {
    const w = window.open("", "_blank");
    w.document.write(`<html><head><title>Ravlo Business Plan — ${form.name}</title><style>body{font-family:'Georgia',serif;max-width:800px;margin:40px auto;color:#1a1a1a;line-height:1.6;font-size:15px}h1{font-size:32px;margin-bottom:4px}h2{font-size:22px;border-bottom:2px solid #D4AF6A;padding-bottom:6px;margin-top:32px;color:#1a1a1a}h3{font-size:16px;margin-top:20px;color:#333}strong{color:#9A7A3A}hr{border:none;border-top:1px solid #eee;margin:20px 0}.header{background:#080808;color:#D4AF6A;padding:24px;border-radius:8px;margin-bottom:32px;text-align:center}.header p{color:#7A7268;font-size:13px;margin-top:4px}</style></head><body><div class="header"><h1 style="color:#D4AF6A;font-size:28px">RAVLO ACADEMY</h1><p>Personalized Business Plan</p></div><div>${plan.replace(/\n/g,'<br/>')}</div></body></html>`);
    w.document.close();
    w.print();
  };

  const S = {
    wrap: { minHeight:"100vh", background:"#080808", fontFamily:"'DM Sans',sans-serif", color:"#EDE8DF" },
    gold: "#D4AF6A", serif: "'Cormorant Garamond',serif",
  };

  if (step === "landing") return (
    <div style={{ ...S.wrap, display:"flex", flexDirection:"column", alignItems:"center", justifyContent:"center", padding:"40px 24px", textAlign:"center", position:"relative", overflow:"hidden" }}>
      <div style={{ position:"absolute", inset:0, background:"radial-gradient(ellipse 70% 50% at 50% 0%, rgba(212,175,106,0.12) 0%, transparent 70%)", pointerEvents:"none" }}/>
      <div style={{ position:"absolute", inset:0, backgroundImage:"repeating-linear-gradient(0deg,transparent,transparent 60px,rgba(212,175,106,0.015) 60px,rgba(212,175,106,0.015) 61px)", pointerEvents:"none" }}/>

      <div style={{ position:"relative", zIndex:1, maxWidth:640 }}>
        <div style={{ display:"inline-flex", alignItems:"center", gap:8, padding:"6px 16px", borderRadius:20, border:"1px solid rgba(212,175,106,0.3)", background:"rgba(212,175,106,0.08)", marginBottom:32 }}>
          <span style={{ width:6, height:6, borderRadius:"50%", background:"#D4AF6A", display:"inline-block" }}/>
          <span style={{ fontSize:11, letterSpacing:3, color:"#D4AF6A", textTransform:"uppercase", fontWeight:600 }}>Ravlo Academy</span>
        </div>

        <h1 style={{ fontFamily:S.serif, fontSize: isMobile?"48px":"clamp(56px,8vw,88px)", fontWeight:300, lineHeight:0.92, letterSpacing:-2, margin:"0 0 24px" }}>
          <span style={{ display:"block" }}>Your</span>
          <span style={{ display:"block", color:"#D4AF6A", fontWeight:700, fontStyle:"italic" }}>Business Plan.</span>
        </h1>

        <p style={{ fontSize:16, color:"#7A7268", lineHeight:1.75, marginBottom:48, fontWeight:300 }}>
          Answer 6 questions. Get a personalized 90-day business plan built by AI — with specific actions, real metrics, and a revenue projection tailored to your role and goals.
        </p>

        <div style={{ display:"grid", gridTemplateColumns: isMobile?"1fr":"repeat(3,1fr)", gap:12, marginBottom:48, textAlign:"left" }}>
          {[["🎯","Goal-Based","Built around your specific role and #1 goal"],["📋","Fully Structured","30, 60, and 90-day milestones with weekly metrics"],["💬","Ask Anything","Chat with your coach after to go deeper on any section"]].map(([icon,title,desc]) => (
            <div key={title} style={{ padding:"18px", borderRadius:10, border:"1px solid rgba(212,175,106,0.15)", background:"rgba(212,175,106,0.04)" }}>
              <div style={{ fontSize:22, marginBottom:8 }}>{icon}</div>
              <div style={{ fontFamily:S.serif, fontSize:16, fontWeight:700, marginBottom:4 }}>{title}</div>
              <div style={{ fontSize:12, color:"#5A5248", lineHeight:1.5 }}>{desc}</div>
            </div>
          ))}
        </div>

        <button onClick={() => setStep("form")} style={{ padding:"18px 52px", borderRadius:10, border:"none", background:"linear-gradient(135deg,#D4AF6A,#9A7A3A)", color:"#080808", fontSize:15, fontWeight:700, cursor:"pointer", letterSpacing:1, fontFamily:"'DM Sans',sans-serif", boxShadow:"0 12px 40px rgba(212,175,106,0.25)", transition:"all 0.2s" }}
          onMouseEnter={e => { e.target.style.transform="translateY(-2px)"; e.target.style.boxShadow="0 16px 48px rgba(212,175,106,0.35)"; }}
          onMouseLeave={e => { e.target.style.transform="translateY(0)"; e.target.style.boxShadow="0 12px 40px rgba(212,175,106,0.25)"; }}>
          Build My Business Plan →
        </button>

        <p style={{ fontSize:12, color:"#3A3530", marginTop:16 }}>Free for all Academy members &amp; Ravlo VIP Partners</p>
      </div>
    </div>
  );

  if (step === "form") {
    const fields = [
      { key:"name", label:"Your Name", type:"text", placeholder:"First & Last Name", options:null },
      { key:"role", label:"What best describes you?", type:"select", options:ROLES },
      { key:"goal", label:"What's your #1 goal right now?", type:"select", options:GOALS },
      { key:"challenge", label:"What's your biggest challenge?", type:"select", options:CHALLENGES },
      { key:"timeline", label:"What's your planning horizon?", type:"select", options:TIMELINES },
      { key:"income", label:"Current annual income range?", type:"select", options:INCOMES },
      { key:"notes", label:"Anything else we should know? (optional)", type:"textarea", placeholder:"Current deals, team size, market, specific situation..." },
    ];
    const complete = form.name && form.role && form.goal && form.challenge;

    return (
      <div style={{ ...S.wrap, display:"flex", flexDirection:"column", alignItems:"center", padding:"40px 24px", minHeight:"100vh" }}>
        <div style={{ maxWidth:600, width:"100%" }}>
          <button onClick={() => setStep("landing")} style={{ background:"none", border:"none", color:"#5A5248", cursor:"pointer", fontSize:13, fontFamily:"'DM Sans',sans-serif", marginBottom:32 }}>← Back</button>

          <div style={{ marginBottom:40 }}>
            <div style={{ fontSize:10, letterSpacing:4, color:"#D4AF6A", textTransform:"uppercase", marginBottom:12 }}>Step 1 of 1</div>
            <h2 style={{ fontFamily:S.serif, fontSize: isMobile?32:44, fontWeight:300, margin:"0 0 8px" }}>Tell us about <strong style={{ fontWeight:700 }}>yourself.</strong></h2>
            <p style={{ color:"#7A7268", fontSize:14 }}>The more specific you are, the more powerful your plan.</p>
          </div>

          <div style={{ display:"flex", flexDirection:"column", gap:20 }}>
            {fields.map(f => (
              <div key={f.key}>
                <label style={{ display:"block", fontSize:10, letterSpacing:3, color:"#D4AF6A", marginBottom:10, textTransform:"uppercase" }}>{f.label}</label>
                {f.type === "text" && (
                  <input value={form[f.key]} onChange={e => setForm(p => ({...p,[f.key]:e.target.value}))} placeholder={f.placeholder}
                    style={{ width:"100%", padding:"13px 16px", background:"rgba(255,255,255,0.04)", border:"1px solid rgba(212,175,106,0.2)", borderRadius:8, color:"#EDE8DF", fontSize:14, outline:"none", boxSizing:"border-box", fontFamily:"'DM Sans',sans-serif" }}/>
                )}
                {f.type === "select" && (
                  <div style={{ display:"flex", flexWrap:"wrap", gap:8 }}>
                    {f.options.map(opt => (
                      <button key={opt} onClick={() => setForm(p => ({...p,[f.key]:opt}))}
                        style={{ padding:"9px 16px", borderRadius:20, border:`1px solid ${form[f.key]===opt?"#D4AF6A":"rgba(212,175,106,0.2)"}`, background:form[f.key]===opt?"rgba(212,175,106,0.15)":"rgba(212,175,106,0.04)", color:form[f.key]===opt?"#D4AF6A":"#7A7268", fontSize:13, cursor:"pointer", transition:"all 0.2s", fontFamily:"'DM Sans',sans-serif" }}>
                        {opt}
                      </button>
                    ))}
                  </div>
                )}
                {f.type === "textarea" && (
                  <textarea value={form[f.key]} onChange={e => setForm(p => ({...p,[f.key]:e.target.value}))} placeholder={f.placeholder} rows={3}
                    style={{ width:"100%", padding:"13px 16px", background:"rgba(255,255,255,0.04)", border:"1px solid rgba(212,175,106,0.2)", borderRadius:8, color:"#EDE8DF", fontSize:14, outline:"none", resize:"vertical", boxSizing:"border-box", fontFamily:"'DM Sans',sans-serif" }}/>
                )}
              </div>
            ))}
          </div>

          <button onClick={generatePlan} disabled={!complete}
            style={{ width:"100%", marginTop:40, padding:"18px", borderRadius:10, border:"none", background:complete?"linear-gradient(135deg,#D4AF6A,#9A7A3A)":"rgba(255,255,255,0.05)", color:complete?"#080808":"#3A3530", fontSize:15, fontWeight:700, cursor:complete?"pointer":"not-allowed", fontFamily:"'DM Sans',sans-serif", letterSpacing:1, transition:"all 0.2s" }}>
            {complete ? "Generate My Business Plan →" : "Fill in required fields to continue"}
          </button>
        </div>
      </div>
    );
  }

  if (step === "generating") return (
    <div style={{ ...S.wrap, display:"flex", flexDirection:"column", alignItems:"center", justifyContent:"center", minHeight:"100vh", textAlign:"center", padding:24 }}>
      <div style={{ position:"relative" }}>
        <div style={{ width:80, height:80, borderRadius:"50%", background:"linear-gradient(135deg,#D4AF6A,#8A6A2A)", display:"flex", alignItems:"center", justifyContent:"center", fontSize:28, marginBottom:32, boxShadow:"0 0 60px rgba(212,175,106,0.3)", animation:"pulse 2s ease-in-out infinite" }}>📋</div>
      </div>
      <h2 style={{ fontFamily:S.serif, fontSize: isMobile?28:40, fontWeight:300, marginBottom:12 }}>Building your plan, <strong style={{ fontWeight:700, color:"#D4AF6A" }}>{form.name}.</strong></h2>
      <p style={{ color:"#5A5248", fontSize:14, maxWidth:400 }}>Analyzing your role, goals, and challenges to build a personalized 90-day roadmap...</p>
      <div style={{ display:"flex", gap:6, marginTop:32, alignItems:"center" }}>
        {[0,1,2,3,4].map(i => <div key={i} style={{ width:8, height:8, borderRadius:"50%", background:"#D4AF6A", opacity:0.4, animation:`dot 1.5s ease-in-out ${i*0.15}s infinite both` }}/>)}
      </div>
      <style>{`@keyframes pulse{0%,100%{box-shadow:0 0 40px rgba(212,175,106,0.2)}50%{box-shadow:0 0 80px rgba(212,175,106,0.4)}} @keyframes dot{0%,100%{transform:scale(0.6);opacity:0.2}50%{transform:scale(1.3);opacity:1}}`}</style>
    </div>
  );

  if (step === "plan") return (
    <div style={{ ...S.wrap, display:"flex", flexDirection: isMobile?"column":"row", height: isMobile?"auto":"100vh" }}>

      <div style={{ flex: isMobile?"none":"1 1 55%", overflowY:"auto", borderRight: isMobile?"none":"1px solid rgba(212,175,106,0.1)", display:"flex", flexDirection:"column" }}>
        <div style={{ padding: isMobile?"16px 20px":"20px 32px", borderBottom:"1px solid rgba(212,175,106,0.1)", background:"rgba(8,8,8,0.97)", position:"sticky", top:0, zIndex:10, display:"flex", alignItems:"center", justifyContent:"space-between", flexShrink:0 }}>
          <div style={{ display:"flex", alignItems:"center", gap:12 }}>
            <div style={{ width:32, height:32, border:"1.5px solid #D4AF6A", borderRadius:6, display:"flex", alignItems:"center", justifyContent:"center", fontFamily:S.serif, fontSize:14, fontWeight:700, color:"#D4AF6A" }}>R</div>
            <div>
              <div style={{ fontFamily:S.serif, fontSize:14, fontWeight:700, letterSpacing:2 }}>RAVLO <span style={{ color:"#D4AF6A" }}>Academy</span></div>
              <div style={{ fontSize:9, letterSpacing:3, color:"#5A5248", textTransform:"uppercase" }}>Business Plan</div>
            </div>
          </div>
          <div style={{ display:"flex", gap:8 }}>
            <button onClick={printPlan} style={{ padding:"6px 14px", borderRadius:6, border:"1px solid rgba(212,175,106,0.2)", background:"rgba(212,175,106,0.06)", color:"#D4AF6A", fontSize:11, fontWeight:600, cursor:"pointer", fontFamily:"'DM Sans',sans-serif" }}>🖨 Print / Save PDF</button>
            <button onClick={() => setStep("form")} style={{ padding:"6px 14px", borderRadius:6, border:"1px solid rgba(255,255,255,0.06)", background:"rgba(255,255,255,0.02)", color:"#5A5248", fontSize:11, cursor:"pointer", fontFamily:"'DM Sans',sans-serif" }}>Rebuild</button>
          </div>
        </div>

        <div style={{ padding: isMobile?"24px 20px":"40px 40px", flex:1 }}>
          <div style={{ marginBottom:32 }}>
            <div style={{ fontSize:10, letterSpacing:4, color:"#D4AF6A", textTransform:"uppercase", marginBottom:8 }}>Your Personalized Plan</div>
            <h2 style={{ fontFamily:S.serif, fontSize: isMobile?28:38, fontWeight:300, margin:"0 0 4px" }}>{form.name}<span style={{ color:"#D4AF6A" }}>.</span></h2>
            <p style={{ color:"#5A5248", fontSize:13 }}>{form.role} · Goal: {form.goal}</p>
          </div>
          <div style={{ fontSize:14, lineHeight:1.8, color:"#C8C0B4" }} dangerouslySetInnerHTML={{ __html: fmt(plan) }}/>
        </div>
      </div>

      <div style={{ flex: isMobile?"none":"0 0 45%", display:"flex", flexDirection:"column", height: isMobile?"500px":"100vh", borderTop: isMobile?"1px solid rgba(212,175,106,0.1)":"none" }}>
        <div style={{ padding: isMobile?"14px 20px":"18px 24px", borderBottom:"1px solid rgba(212,175,106,0.1)", background:"rgba(8,8,8,0.97)", flexShrink:0 }}>
          <div style={{ display:"flex", alignItems:"center", gap:10 }}>
            <div style={{ width:28, height:28, borderRadius:"50%", background:"linear-gradient(135deg,#D4AF6A,#8A6A2A)", display:"flex", alignItems:"center", justifyContent:"center", fontSize:11, fontWeight:700, color:"#080808" }}>AI</div>
            <div>
              <div style={{ fontFamily:S.serif, fontSize:15, fontWeight:700 }}>Ask Your Coach</div>
              <div style={{ fontSize:10, color:"#5A5248", letterSpacing:1 }}>FOLLOW-UP SESSION</div>
            </div>
          </div>
        </div>

        <div style={{ flex:1, overflowY:"auto", padding: isMobile?"16px":"20px", display:"flex", flexDirection:"column", gap:14 }}>
          {messages.map((msg, i) => (
            <div key={i} style={{ display:"flex", justifyContent:msg.role==="user"?"flex-end":"flex-start", gap:8, alignItems:"flex-start" }}>
              {msg.role==="assistant" && <div style={{ width:26, height:26, borderRadius:"50%", background:"linear-gradient(135deg,#D4AF6A,#8A6A2A)", display:"flex", alignItems:"center", justifyContent:"center", fontSize:10, fontWeight:700, color:"#080808", flexShrink:0, marginTop:2 }}>AI</div>}
              <div style={{ maxWidth:"85%", padding:msg.role==="user"?"10px 14px":"16px 18px", borderRadius:msg.role==="user"?"16px 16px 4px 16px":"16px 16px 16px 4px", background:msg.role==="user"?"linear-gradient(135deg,#D4AF6A,#9A7A3A)":"rgba(255,255,255,0.04)", border:msg.role==="assistant"?"1px solid rgba(212,175,106,0.1)":"none", color:msg.role==="user"?"#080808":"#C8C0B4", fontSize:13, lineHeight:1.7 }}>
                {msg.role==="user" ? msg.content : <span dangerouslySetInnerHTML={{ __html:fmtChat(msg.content) }}/>}
              </div>
            </div>
          ))}
          {chatLoading && (
            <div style={{ display:"flex", gap:8, alignItems:"flex-start" }}>
              <div style={{ width:26, height:26, borderRadius:"50%", background:"linear-gradient(135deg,#D4AF6A,#8A6A2A)", display:"flex", alignItems:"center", justifyContent:"center", fontSize:10, fontWeight:700, color:"#080808" }}>AI</div>
              <div style={{ padding:"14px 18px", borderRadius:"16px 16px 16px 4px", background:"rgba(255,255,255,0.04)", border:"1px solid rgba(212,175,106,0.1)", display:"flex", gap:4 }}>
                {[0,1,2].map(i => <div key={i} style={{ width:6, height:6, borderRadius:"50%", background:"#D4AF6A", opacity:0.6, animation:`dot 1.2s ${i*0.2}s ease-in-out infinite both` }}/>)}
              </div>
            </div>
          )}
          <div ref={messagesEndRef}/>
        </div>

        <div style={{ padding:"10px 20px 0", display:"flex", gap:6, overflowX:"auto", flexShrink:0 }}>
          {["Explain my 30-day sprint","How do I hit 60-day targets?","Help me start this week","Adjust my revenue projection"].map(s => (
            <button key={s} onClick={() => { setChatInput(s); setTimeout(() => sendChat(), 50); }} style={{ padding:"5px 12px", borderRadius:16, border:"1px solid rgba(212,175,106,0.12)", background:"transparent", color:"#5A5248", fontSize:11, cursor:"pointer", whiteSpace:"nowrap", fontFamily:"'DM Sans',sans-serif", transition:"all 0.2s" }}
              onMouseEnter={e => { e.target.style.color="#D4AF6A"; e.target.style.borderColor="rgba(212,175,106,0.3)"; }}
              onMouseLeave={e => { e.target.style.color="#5A5248"; e.target.style.borderColor="rgba(212,175,106,0.12)"; }}>
              {s}
            </button>
          ))}
        </div>

        <div style={{ padding: isMobile?"12px 16px":"14px 20px", borderTop:"1px solid rgba(212,175,106,0.08)", background:"rgba(8,8,8,0.97)", flexShrink:0 }}>
          <div style={{ display:"flex", gap:8, alignItems:"flex-end" }}>
            <textarea ref={inputRef} value={chatInput} onChange={e => setChatInput(e.target.value)}
              onKeyDown={e => { if(e.key==="Enter"&&!e.shiftKey){ e.preventDefault(); sendChat(); }}}
              placeholder="Ask about any part of your plan..." rows={1}
              style={{ flex:1, padding:"11px 14px", background:"rgba(255,255,255,0.04)", border:"1px solid rgba(212,175,106,0.15)", borderRadius:10, color:"#EDE8DF", fontSize:13, outline:"none", resize:"none", lineHeight:1.5, fontFamily:"'DM Sans',sans-serif", maxHeight:100 }}/>
            <button onClick={sendChat} disabled={!chatInput.trim()||chatLoading}
              style={{ width:40, height:40, borderRadius:8, border:"none", background:chatInput.trim()&&!chatLoading?"linear-gradient(135deg,#D4AF6A,#9A7A3A)":"rgba(255,255,255,0.04)", color:chatInput.trim()&&!chatLoading?"#080808":"#3A3530", fontSize:16, cursor:chatInput.trim()&&!chatLoading?"pointer":"not-allowed", flexShrink:0, display:"flex", alignItems:"center", justifyContent:"center" }}>↑</button>
          </div>
        </div>
      </div>
      <style>{`@keyframes dot{0%,100%{transform:scale(0.7);opacity:0.3}50%{transform:scale(1.2);opacity:1}} ::-webkit-scrollbar{width:3px} ::-webkit-scrollbar-thumb{background:rgba(212,175,106,0.15);border-radius:3px} textarea{overflow:hidden}`}</style>
    </div>
  );

  return null;
}

const container = document.getElementById("ravlo-business-plan-root");
const root = ReactDOM.createRoot(container);
root.render(React.createElement(RavloBusinessPlan));
