// ─── Ravlo University — Flask Integration Build ───────────────────────────
// AI calls are proxied through /university/chat (keeps ANTHROPIC_API_KEY
// server-side).  Fonts are loaded in portal.html <head> to prevent FOUC.
// React hooks pulled from the global React UMD bundle (no import needed).

const { useState, useRef, useEffect } = React;

// ─── CONSTANTS ───────────────────────────────────────────────────────────────

const ACCESS_TIERS = {
  elite: {
    label: "Elite Access",
    badge: "ELITE",
    color: "#D4AF6A",
    bg: "rgba(212,175,106,0.12)",
    border: "rgba(212,175,106,0.4)",
    icon: "◆",
    description: "Ravlo Investors & Partners",
    perks: ["Unlimited AI Coaching", "All Modules", "1-on-1 Success Plans", "Priority Support", "Investor Briefings"],
    accessCode: "RAVLO-ELITE",
    monthly: 0,
    badge_text: "Complimentary",
  },
  lending: {
    label: "Lending Team",
    badge: "TEAM",
    color: "#6AB4D4",
    bg: "rgba(106,180,212,0.12)",
    border: "rgba(106,180,212,0.4)",
    icon: "◈",
    description: "Ravlo Lending Staff",
    perks: ["Unlimited AI Coaching", "Loan Modules", "Commercial Training", "Team Dashboard", "Deal Review"],
    accessCode: "RAVLO-LENDING",
    monthly: 0,
    badge_text: "Employment Benefit",
  },
  pro: {
    label: "Pro",
    badge: "PRO",
    color: "#B06AD4",
    bg: "rgba(176,106,212,0.12)",
    border: "rgba(176,106,212,0.4)",
    icon: "●",
    description: "Independent Realtors & Investors",
    perks: ["Unlimited AI Coaching", "All Modules", "Success Plans", "Community Access"],
    monthly: 97,
    badge_text: "$97 / month",
  },
  starter: {
    label: "Starter",
    badge: "START",
    color: "#6AD4A0",
    bg: "rgba(106,212,160,0.12)",
    border: "rgba(106,212,160,0.4)",
    icon: "○",
    description: "New to Real Estate",
    perks: ["Core AI Coaching", "3 Modules", "Basic Success Plan"],
    monthly: 47,
    badge_text: "$47 / month",
  },
};

const MODULES = [
  {
    id: "residential",
    title: "Residential Mastery",
    icon: "🏠",
    color: "#D4AF6A",
    lessons: ["Listing Strategy & Pricing", "Buyer Representation", "Negotiation Frameworks", "CMA Deep Dive", "Open House Optimization", "Lead Conversion Systems"],
    tier: ["starter", "pro", "elite", "lending"],
    desc: "Master the full residential transaction from lead to close.",
  },
  {
    id: "commercial",
    title: "Commercial Real Estate",
    icon: "🏢",
    color: "#6AB4D4",
    lessons: ["Office & Retail Leasing", "Cap Rate & NOI Analysis", "Investment Sales", "1031 Exchanges", "Tenant & Landlord Rep", "Market Analysis"],
    tier: ["pro", "elite", "lending"],
    desc: "Advanced commercial strategies for office, retail, and industrial.",
  },
  {
    id: "loans",
    title: "Commercial Lending",
    icon: "💰",
    color: "#6AD4A0",
    lessons: ["SBA 7(a) & 504 Programs", "CMBS & Bridge Loans", "DSCR & Underwriting", "LTV / LTC Ratios", "Rate Locks & Assumptions", "Hard Money & Private Lending"],
    tier: ["pro", "elite", "lending"],
    desc: "Complete commercial loan structuring from application to close.",
  },
  {
    id: "business",
    title: "Realtor Business Growth",
    icon: "📈",
    color: "#B06AD4",
    lessons: ["Building Your SOI System", "CRM Setup & Automation", "Social Media & Video", "Geographic Farming", "Team Building", "Brokerage Selection"],
    tier: ["starter", "pro", "elite", "lending"],
    desc: "Build a scalable real estate business that generates without you.",
  },
  {
    id: "investing",
    title: "Real Estate Investing",
    icon: "🏗️",
    color: "#D46A6A",
    lessons: ["BRRRR Strategy", "Multifamily Underwriting", "Market Selection", "Deal Sourcing", "Property Management", "Exit Strategies"],
    tier: ["pro", "elite"],
    desc: "From first rental to multifamily portfolio — a complete investor path.",
  },
  {
    id: "advanced",
    title: "Advanced Deal Structuring",
    icon: "⚡",
    color: "#D4A06A",
    lessons: ["Creative Financing", "Seller Financing & Wraps", "Joint Ventures", "Syndication Basics", "Distressed Assets", "Off-Market Strategies"],
    tier: ["elite"],
    desc: "Elite strategies for complex, high-value transactions.",
  },
];

const AI_SYSTEM = `You are the RealEdge AI Coach inside Ravlo University — an elite real estate education platform.

You are a world-class coach with deep expertise in:
- Residential Real Estate (listings, buyers, negotiation, CMAs, lead gen, farming)
- Commercial Real Estate (office, retail, industrial, cap rates, NOI, 1031s, investment sales)
- Commercial Lending (SBA 7a/504, CMBS, bridge loans, DSCR, LTV, underwriting, hard money)
- Realtor Business Development (SOI, CRM, branding, team building, social media, farming)
- Real Estate Investing (BRRRR, multifamily, deal analysis, exit strategies)

Your style: Direct, no-fluff, data-driven. You speak like a top producer who has closed $100M+ and mentored 500+ agents. Use real numbers, real scenarios, real frameworks.

When asked for a success plan, create a structured plan with:
1. ASSESSMENT (what you know about them)
2. 30-DAY SPRINT (specific daily/weekly actions)
3. 60-DAY MILESTONES (measurable targets)
4. 90-DAY VISION (where they should be)
5. KEY METRICS (what to track weekly)
6. ACCOUNTABILITY SYSTEM (how to stay on track)

Always personalize. Always be specific. Never be generic.`;

// ─── MAIN COMPONENT ──────────────────────────────────────────────────────────
function RavloUniversity() {
  const [screen, setScreen] = useState("landing"); // landing | access | dashboard | module | coach | plan
  const [tier, setTier] = useState(null);
  const [userName, setUserName] = useState("");
  const [codeInput, setCodeInput] = useState("");
  const [codeError, setCodeError] = useState("");
  const [activeModule, setActiveModule] = useState(null);
  const [activeLesson, setActiveLesson] = useState(null);
  const [messages, setMessages] = useState([]);
  const [chatInput, setChatInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [nameInput, setNameInput] = useState("");
  const [planStarted, setPlanStarted] = useState(false);
  const [notification, setNotification] = useState(null);
  const messagesEndRef = useRef(null);
  const inputRef = useRef(null);

  useEffect(() => { messagesEndRef.current?.scrollIntoView({ behavior: "smooth" }); }, [messages]);

  const notify = (msg) => { setNotification(msg); setTimeout(() => setNotification(null), 3000); };

  const handleCodeAccess = (tierKey) => {
    const t = ACCESS_TIERS[tierKey];
    if (t.accessCode) {
      if (codeInput.toUpperCase() === t.accessCode) {
        setTier(tierKey);
        setUserName(nameInput || "Member");
        setScreen("dashboard");
        setCodeError("");
      } else {
        setCodeError("Invalid access code. Contact your Ravlo representative.");
      }
    }
  };

  const handlePaidAccess = (tierKey) => {
    setTier(tierKey);
    setUserName(nameInput || "Member");
    setScreen("dashboard");
  };

  // ── AI chat — proxied through Flask /university/chat ─────────────────────
  const sendMessage = async (text) => {
    const msg = text || chatInput.trim();
    if (!msg) return;
    setChatInput("");
    const newMsgs = [...messages, { role: "user", content: msg }];
    setMessages(newMsgs);
    setLoading(true);
    const context = `User: ${userName || "Member"} | Access: ${ACCESS_TIERS[tier]?.label} | Module: ${activeModule?.title || "General"}`;
    try {
      const res = await fetch("/university/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          model: "claude-opus-4-5",
          max_tokens: 1000,
          system: AI_SYSTEM + `\n\nContext: ${context}`,
          messages: newMsgs,
        }),
      });
      const data = await res.json();
      const reply = data.content?.map(c => c.text || "").join("\n") || "Please try again.";
      setMessages([...newMsgs, { role: "assistant", content: reply }]);
    } catch { setMessages([...newMsgs, { role: "assistant", content: "Connection error. Please try again." }]); }
    finally { setLoading(false); setTimeout(() => inputRef.current?.focus(), 100); }
  };

  const startPlan = () => {
    setPlanStarted(true);
    setScreen("coach");
    setMessages([]);
    sendMessage(`Create my personalized success plan. I am ${userName}, a ${ACCESS_TIERS[tier]?.description} member. Ask me the key questions first to build a plan tailored to my specific situation, goals, and current level.`);
  };

  const startCoach = (prompt = "") => {
    setScreen("coach");
    if (messages.length === 0 || prompt) {
      const welcome = prompt || `Hi ${userName}! I'm your RealEdge AI Coach. What's your biggest challenge right now, or what do you want to master today?`;
      if (!prompt) setMessages([{ role: "assistant", content: welcome }]);
      else { setMessages([]); setTimeout(() => sendMessage(prompt), 100); }
    }
  };

  const t = tier ? ACCESS_TIERS[tier] : null;
  const availableModules = tier ? MODULES.filter(m => m.tier.includes(tier)) : [];

  const fmt = (txt) => txt
    .replace(/\*\*(.*?)\*\*/g, '<strong style="color:#D4AF6A">$1</strong>')
    .replace(/^### (.*)$/gm, '<div style="font-size:13px;font-weight:700;color:#D4AF6A;margin:14px 0 6px;letter-spacing:1px;text-transform:uppercase;font-family:\'Cormorant Garamond\',serif">$1</div>')
    .replace(/^## (.*)$/gm, '<div style="font-size:16px;font-weight:700;color:#D4AF6A;margin:16px 0 8px;font-family:\'Cormorant Garamond\',serif">$1</div>')
    .replace(/^- (.*)$/gm, '<div style="display:flex;gap:8px;margin:3px 0;align-items:flex-start"><span style="color:#D4AF6A;margin-top:2px;flex-shrink:0">▸</span><span>$1</span></div>')
    .replace(/^\d+\. (.*)$/gm, (m, p1) => `<div style="display:flex;gap:8px;margin:4px 0;align-items:flex-start"><span style="color:#D4AF6A;flex-shrink:0;font-weight:700">•</span><span>${p1}</span></div>`)
    .replace(/\n\n/g, '<div style="height:10px"></div>')
    .replace(/\n/g, '<br/>');

  // ── LANDING ────────────────────────────────────────────────────────────────
  if (screen === "landing") return (
    <div style={{ minHeight:"100vh", background:"#080808", fontFamily:"'DM Sans',sans-serif", color:"#EDE8DF", display:"flex", flexDirection:"column", overflow:"hidden", position:"relative" }}>
      <div style={{ position:"absolute", inset:0, backgroundImage:"radial-gradient(ellipse 80% 50% at 50% -10%, rgba(212,175,106,0.15) 0%, transparent 70%)", pointerEvents:"none" }}/>
      <div style={{ position:"absolute", inset:0, backgroundImage:"repeating-linear-gradient(0deg,transparent,transparent 80px,rgba(212,175,106,0.02) 80px,rgba(212,175,106,0.02) 81px),repeating-linear-gradient(90deg,transparent,transparent 80px,rgba(212,175,106,0.02) 80px,rgba(212,175,106,0.02) 81px)", pointerEvents:"none" }}/>

      {/* Nav */}
      <nav style={{ padding:"20px 48px", display:"flex", alignItems:"center", justifyContent:"space-between", borderBottom:"1px solid rgba(212,175,106,0.1)", position:"relative", zIndex:10 }}>
        <div style={{ display:"flex", alignItems:"center", gap:12 }}>
          <div style={{ width:36, height:36, border:"1.5px solid #D4AF6A", borderRadius:6, display:"flex", alignItems:"center", justifyContent:"center", fontSize:16, color:"#D4AF6A", fontFamily:"'Cormorant Garamond',serif", fontWeight:700 }}>R</div>
          <div>
            <div style={{ fontFamily:"'Cormorant Garamond',serif", fontSize:20, fontWeight:700, letterSpacing:2, color:"#EDE8DF" }}>RAVLO</div>
            <div style={{ fontSize:9, letterSpacing:4, color:"#D4AF6A", textTransform:"uppercase", marginTop:-2 }}>University</div>
          </div>
        </div>
        <button onClick={() => setScreen("access")} style={{ padding:"10px 28px", borderRadius:6, border:"1px solid rgba(212,175,106,0.4)", background:"rgba(212,175,106,0.08)", color:"#D4AF6A", fontSize:13, fontWeight:600, cursor:"pointer", letterSpacing:1, fontFamily:"'DM Sans',sans-serif" }}>
          Access Portal →
        </button>
      </nav>

      {/* Hero */}
      <div style={{ flex:1, display:"flex", flexDirection:"column", alignItems:"center", justifyContent:"center", padding:"80px 24px", textAlign:"center", position:"relative", zIndex:1 }}>
        <div style={{ fontSize:11, letterSpacing:6, color:"#D4AF6A", textTransform:"uppercase", marginBottom:24, fontWeight:500 }}>Real Estate Education · Reimagined</div>
        <h1 style={{ fontFamily:"'Cormorant Garamond',serif", fontSize:"clamp(52px,8vw,100px)", fontWeight:300, lineHeight:0.95, margin:"0 0 8px", letterSpacing:-2 }}>
          <span style={{ display:"block", color:"#EDE8DF" }}>Ravlo</span>
          <span style={{ display:"block", color:"#D4AF6A", fontWeight:700, fontStyle:"italic" }}>University</span>
        </h1>
        <p style={{ fontSize:"clamp(15px,2vw,18px)", color:"#7A7268", maxWidth:540, lineHeight:1.7, margin:"32px auto 48px", fontWeight:300 }}>
          AI-powered coaching for realtors, investors, and lenders. One-on-one guidance, personalized success plans, and the knowledge to close more deals.
        </p>
        <div style={{ display:"flex", gap:16, flexWrap:"wrap", justifyContent:"center" }}>
          <button onClick={() => setScreen("access")} style={{ padding:"16px 40px", borderRadius:8, border:"none", background:"linear-gradient(135deg, #D4AF6A, #9A7A3A)", color:"#080808", fontSize:15, fontWeight:700, cursor:"pointer", letterSpacing:1, fontFamily:"'DM Sans',sans-serif" }}>
            Start Learning
          </button>
          <button onClick={() => setScreen("access")} style={{ padding:"16px 40px", borderRadius:8, border:"1px solid rgba(212,175,106,0.3)", background:"transparent", color:"#D4AF6A", fontSize:15, fontWeight:500, cursor:"pointer", letterSpacing:0.5, fontFamily:"'DM Sans',sans-serif" }}>
            Partner Access
          </button>
        </div>

        {/* Stats */}
        <div style={{ display:"flex", gap:48, marginTop:80, flexWrap:"wrap", justifyContent:"center" }}>
          {[["6", "Learning Modules"],["AI", "Powered Coaching"],["1:1", "Success Plans"],["∞", "Deal Knowledge"]].map(([n,l]) => (
            <div key={l} style={{ textAlign:"center" }}>
              <div style={{ fontFamily:"'Cormorant Garamond',serif", fontSize:40, fontWeight:700, color:"#D4AF6A", lineHeight:1 }}>{n}</div>
              <div style={{ fontSize:11, color:"#5A5248", letterSpacing:2, textTransform:"uppercase", marginTop:6 }}>{l}</div>
            </div>
          ))}
        </div>
      </div>

      {/* Access tiers preview */}
      <div style={{ padding:"0 24px 80px", maxWidth:900, margin:"0 auto", width:"100%", position:"relative", zIndex:1 }}>
        <div style={{ textAlign:"center", marginBottom:32 }}>
          <div style={{ fontSize:11, letterSpacing:4, color:"#5A5248", textTransform:"uppercase" }}>Access Tiers</div>
        </div>
        <div style={{ display:"grid", gridTemplateColumns:"repeat(auto-fit,minmax(200px,1fr))", gap:12 }}>
          {Object.entries(ACCESS_TIERS).map(([key, t]) => (
            <div key={key} onClick={() => setScreen("access")} style={{ padding:"20px", borderRadius:10, border:`1px solid ${t.border}`, background:t.bg, cursor:"pointer", transition:"all 0.2s" }}
              onMouseEnter={e => e.currentTarget.style.transform="translateY(-2px)"}
              onMouseLeave={e => e.currentTarget.style.transform="translateY(0)"}>
              <div style={{ display:"flex", justifyContent:"space-between", alignItems:"flex-start", marginBottom:10 }}>
                <span style={{ fontSize:20, color:t.color }}>{t.icon}</span>
                <span style={{ fontSize:10, padding:"3px 8px", borderRadius:20, border:`1px solid ${t.border}`, color:t.color, letterSpacing:1, fontWeight:600 }}>{t.badge_text}</span>
              </div>
              <div style={{ fontFamily:"'Cormorant Garamond',serif", fontSize:18, fontWeight:700, color:"#EDE8DF", marginBottom:4 }}>{t.label}</div>
              <div style={{ fontSize:11, color:"#5A5248", letterSpacing:0.5 }}>{t.description}</div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );

  // ── ACCESS ─────────────────────────────────────────────────────────────────
  if (screen === "access") return (
    <div style={{ minHeight:"100vh", background:"#080808", fontFamily:"'DM Sans',sans-serif", color:"#EDE8DF", display:"flex", flexDirection:"column", alignItems:"center", justifyContent:"center", padding:"40px 24px", position:"relative" }}>
      <div style={{ position:"absolute", inset:0, backgroundImage:"radial-gradient(ellipse 60% 40% at 50% 0%, rgba(212,175,106,0.08) 0%, transparent 70%)", pointerEvents:"none" }}/>

      <button onClick={() => setScreen("landing")} style={{ position:"absolute", top:24, left:24, background:"none", border:"none", color:"#5A5248", cursor:"pointer", fontSize:13, fontFamily:"'DM Sans',sans-serif" }}>← Back</button>

      <div style={{ maxWidth:720, width:"100%", position:"relative", zIndex:1 }}>
        <div style={{ textAlign:"center", marginBottom:48 }}>
          <div style={{ fontFamily:"'Cormorant Garamond',serif", fontSize:14, letterSpacing:6, color:"#D4AF6A", textTransform:"uppercase", marginBottom:12 }}>Choose Your Access</div>
          <h2 style={{ fontFamily:"'Cormorant Garamond',serif", fontSize:42, fontWeight:300, margin:"0 0 8px" }}>Ravlo <strong style={{ fontWeight:700 }}>University</strong></h2>
          <p style={{ color:"#5A5248", fontSize:14 }}>Investors & partners enter your access code. Subscribers select a plan below.</p>
        </div>

        {/* Name */}
        <div style={{ marginBottom:32 }}>
          <label style={{ display:"block", fontSize:10, letterSpacing:3, color:"#D4AF6A", marginBottom:10, textTransform:"uppercase" }}>Your Name</label>
          <input value={nameInput} onChange={e => setNameInput(e.target.value)} placeholder="First & Last Name"
            style={{ width:"100%", padding:"14px 18px", background:"rgba(255,255,255,0.04)", border:"1px solid rgba(212,175,106,0.2)", borderRadius:8, color:"#EDE8DF", fontSize:15, outline:"none", boxSizing:"border-box", fontFamily:"'DM Sans',sans-serif" }}/>
        </div>

        {/* Free / Code access */}
        <div style={{ marginBottom:32 }}>
          <div style={{ fontSize:10, letterSpacing:3, color:"#D4AF6A", marginBottom:16, textTransform:"uppercase" }}>Elite & Team Access — Enter Code</div>
          <div style={{ display:"grid", gridTemplateColumns:"1fr 1fr", gap:12, marginBottom:16 }}>
            {["elite","lending"].map(key => {
              const t = ACCESS_TIERS[key];
              return (
                <div key={key} style={{ padding:"16px", borderRadius:10, border:`1px solid ${t.border}`, background:t.bg }}>
                  <div style={{ display:"flex", gap:8, alignItems:"center", marginBottom:8 }}>
                    <span style={{ color:t.color, fontSize:16 }}>{t.icon}</span>
                    <span style={{ fontFamily:"'Cormorant Garamond',serif", fontSize:16, fontWeight:700, color:"#EDE8DF" }}>{t.label}</span>
                    <span style={{ marginLeft:"auto", fontSize:10, padding:"2px 8px", borderRadius:20, border:`1px solid ${t.border}`, color:t.color, letterSpacing:0.5 }}>{t.badge_text}</span>
                  </div>
                  <div style={{ fontSize:11, color:"#5A5248", marginBottom:12 }}>{t.description}</div>
                  <ul style={{ margin:0, padding:0, listStyle:"none" }}>
                    {t.perks.slice(0,3).map(p => <li key={p} style={{ fontSize:11, color:"#7A7268", display:"flex", gap:6, marginBottom:3 }}><span style={{ color:t.color }}>✓</span>{p}</li>)}
                  </ul>
                  <button onClick={() => handleCodeAccess(key)} style={{ width:"100%", marginTop:14, padding:"10px", borderRadius:6, border:`1px solid ${t.border}`, background:"rgba(0,0,0,0.3)", color:t.color, fontSize:12, fontWeight:600, cursor:"pointer", fontFamily:"'DM Sans',sans-serif", letterSpacing:0.5 }}>
                    Activate with Code
                  </button>
                </div>
              );
            })}
          </div>
          <div style={{ display:"flex", gap:10 }}>
            <input value={codeInput} onChange={e => { setCodeInput(e.target.value); setCodeError(""); }} placeholder="Enter access code (e.g. RAVLO-ELITE)"
              style={{ flex:1, padding:"13px 16px", background:"rgba(255,255,255,0.04)", border:"1px solid rgba(212,175,106,0.2)", borderRadius:8, color:"#EDE8DF", fontSize:14, outline:"none", fontFamily:"'DM Sans',sans-serif" }}
              onKeyDown={e => { if (e.key==="Enter") { handleCodeAccess("elite"); if(codeError) handleCodeAccess("lending"); }}}/>
          </div>
          {codeError && <div style={{ color:"#D46A6A", fontSize:12, marginTop:8 }}>{codeError}</div>}
        </div>

        {/* Paid plans */}
        <div>
          <div style={{ fontSize:10, letterSpacing:3, color:"#7A7268", marginBottom:16, textTransform:"uppercase" }}>Subscription Plans</div>
          <div style={{ display:"grid", gridTemplateColumns:"1fr 1fr", gap:12 }}>
            {["pro","starter"].map(key => {
              const t = ACCESS_TIERS[key];
              return (
                <div key={key} style={{ padding:"20px", borderRadius:10, border:`1px solid ${t.border}`, background:t.bg }}>
                  <div style={{ display:"flex", justifyContent:"space-between", alignItems:"flex-start", marginBottom:10 }}>
                    <div style={{ fontFamily:"'Cormorant Garamond',serif", fontSize:20, fontWeight:700, color:"#EDE8DF" }}>{t.label}</div>
                    <div style={{ textAlign:"right" }}>
                      <div style={{ fontFamily:"'Cormorant Garamond',serif", fontSize:26, fontWeight:700, color:t.color, lineHeight:1 }}>${t.monthly}</div>
                      <div style={{ fontSize:10, color:"#5A5248" }}>/month</div>
                    </div>
                  </div>
                  <div style={{ fontSize:11, color:"#5A5248", marginBottom:12 }}>{t.description}</div>
                  <ul style={{ margin:"0 0 14px", padding:0, listStyle:"none" }}>
                    {t.perks.map(p => <li key={p} style={{ fontSize:11, color:"#7A7268", display:"flex", gap:6, marginBottom:3 }}><span style={{ color:t.color }}>✓</span>{p}</li>)}
                  </ul>
                  <button onClick={() => handlePaidAccess(key)} style={{ width:"100%", padding:"11px", borderRadius:6, border:"none", background:`linear-gradient(135deg, ${t.color}, ${t.color}88)`, color:"#080808", fontSize:13, fontWeight:700, cursor:"pointer", fontFamily:"'DM Sans',sans-serif", letterSpacing:0.5 }}>
                    Subscribe — ${t.monthly}/mo
                  </button>
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );

  // ── DASHBOARD ──────────────────────────────────────────────────────────────
  if (screen === "dashboard") return (
    <div style={{ minHeight:"100vh", background:"#080808", fontFamily:"'DM Sans',sans-serif", color:"#EDE8DF" }}>

      {/* Notification */}
      {notification && <div style={{ position:"fixed", top:20, right:20, padding:"12px 20px", borderRadius:8, background:"rgba(212,175,106,0.15)", border:"1px solid rgba(212,175,106,0.3)", color:"#D4AF6A", fontSize:13, zIndex:100, fontFamily:"'DM Sans',sans-serif" }}>{notification}</div>}

      {/* Header */}
      <div style={{ padding:"18px 32px", borderBottom:"1px solid rgba(212,175,106,0.1)", display:"flex", alignItems:"center", justifyContent:"space-between", background:"rgba(8,8,8,0.95)", position:"sticky", top:0, zIndex:50 }}>
        <div style={{ display:"flex", alignItems:"center", gap:14 }}>
          <div style={{ width:34, height:34, border:"1.5px solid #D4AF6A", borderRadius:6, display:"flex", alignItems:"center", justifyContent:"center", fontSize:14, color:"#D4AF6A", fontFamily:"'Cormorant Garamond',serif", fontWeight:700 }}>R</div>
          <div>
            <div style={{ fontFamily:"'Cormorant Garamond',serif", fontSize:16, fontWeight:700, letterSpacing:2 }}>RAVLO <span style={{ color:"#D4AF6A" }}>University</span></div>
            <div style={{ fontSize:9, letterSpacing:3, color:"#5A5248", textTransform:"uppercase" }}>AI Coaching Platform</div>
          </div>
        </div>
        <div style={{ display:"flex", alignItems:"center", gap:16 }}>
          <div style={{ display:"flex", alignItems:"center", gap:8 }}>
            <span style={{ fontSize:11, color:t.color, padding:"3px 10px", borderRadius:20, border:`1px solid ${t.border}`, background:t.bg, letterSpacing:1, fontWeight:600 }}>{t.badge} ACCESS</span>
            <span style={{ fontSize:13, color:"#7A7268" }}>{userName}</span>
          </div>
          <button onClick={() => setScreen("landing")} style={{ background:"none", border:"none", color:"#3A3530", cursor:"pointer", fontSize:12, fontFamily:"'DM Sans',sans-serif" }}>Sign Out</button>
        </div>
      </div>

      <div style={{ maxWidth:1100, margin:"0 auto", padding:"40px 32px" }}>
        {/* Welcome */}
        <div style={{ marginBottom:48 }}>
          <div style={{ fontSize:11, letterSpacing:4, color:"#5A5248", textTransform:"uppercase", marginBottom:8 }}>Welcome back</div>
          <h2 style={{ fontFamily:"'Cormorant Garamond',serif", fontSize:44, fontWeight:300, margin:"0 0 4px" }}>
            Hello, <strong style={{ fontWeight:700, color:"#D4AF6A" }}>{userName}</strong>
          </h2>
          <p style={{ color:"#5A5248", fontSize:14, margin:0 }}>What are we mastering today?</p>
        </div>

        {/* Action cards */}
        <div style={{ display:"grid", gridTemplateColumns:"repeat(3,1fr)", gap:16, marginBottom:48 }}>
          {[
            { icon:"🤖", label:"AI Coach", desc:"One-on-one coaching session", color:"#D4AF6A", action:() => startCoach() },
            { icon:"📋", label:"My Success Plan", desc:"Get your personalized 90-day plan", color:"#6AD4A0", action:startPlan },
            { icon:"📚", label:"Browse Modules", desc:`${availableModules.length} modules available`, color:"#6AB4D4", action:() => document.getElementById("modules")?.scrollIntoView({behavior:"smooth"}) },
          ].map(card => (
            <button key={card.label} onClick={card.action} style={{ padding:"24px", borderRadius:12, border:`1px solid ${card.color}30`, background:`${card.color}08`, cursor:"pointer", textAlign:"left", transition:"all 0.2s", fontFamily:"'DM Sans',sans-serif" }}
              onMouseEnter={e => { e.currentTarget.style.border=`1px solid ${card.color}60`; e.currentTarget.style.background=`${card.color}12`; e.currentTarget.style.transform="translateY(-2px)"; }}
              onMouseLeave={e => { e.currentTarget.style.border=`1px solid ${card.color}30`; e.currentTarget.style.background=`${card.color}08`; e.currentTarget.style.transform="translateY(0)"; }}>
              <div style={{ fontSize:28, marginBottom:12 }}>{card.icon}</div>
              <div style={{ fontFamily:"'Cormorant Garamond',serif", fontSize:20, fontWeight:700, color:"#EDE8DF", marginBottom:4 }}>{card.label}</div>
              <div style={{ fontSize:12, color:"#5A5248" }}>{card.desc}</div>
              <div style={{ marginTop:14, fontSize:12, color:card.color, fontWeight:600 }}>Open →</div>
            </button>
          ))}
        </div>

        {/* Quick prompts */}
        <div style={{ marginBottom:48 }}>
          <div style={{ fontSize:10, letterSpacing:3, color:"#5A5248", textTransform:"uppercase", marginBottom:16 }}>Quick Coaching Topics</div>
          <div style={{ display:"flex", flexWrap:"wrap", gap:8 }}>
            {["Explain cap rates with real examples","How do I build a sphere of influence system?","Walk me through SBA 504 vs 7(a)","Best lead gen strategies for 2026","How to analyze a multifamily deal","Explain DSCR underwriting","How do I get my first commercial listing?","Build me a 30-day prospecting plan"].map(q => (
              <button key={q} onClick={() => startCoach(q)} style={{ padding:"9px 16px", borderRadius:20, border:"1px solid rgba(212,175,106,0.15)", background:"rgba(212,175,106,0.05)", color:"#7A7268", fontSize:12, cursor:"pointer", transition:"all 0.2s", fontFamily:"'DM Sans',sans-serif" }}
                onMouseEnter={e => { e.target.style.borderColor="#D4AF6A"; e.target.style.color="#D4AF6A"; }}
                onMouseLeave={e => { e.target.style.borderColor="rgba(212,175,106,0.15)"; e.target.style.color="#7A7268"; }}>
                {q}
              </button>
            ))}
          </div>
        </div>

        {/* Modules */}
        <div id="modules">
          <div style={{ display:"flex", alignItems:"center", justifyContent:"space-between", marginBottom:20 }}>
            <div style={{ fontSize:10, letterSpacing:3, color:"#5A5248", textTransform:"uppercase" }}>Your Modules</div>
            <div style={{ fontSize:11, color:"#3A3530" }}>{availableModules.length} of {MODULES.length} unlocked</div>
          </div>
          <div style={{ display:"grid", gridTemplateColumns:"repeat(auto-fill,minmax(280px,1fr))", gap:14 }}>
            {MODULES.map(mod => {
              const locked = !mod.tier.includes(tier);
              return (
                <div key={mod.id} onClick={() => { if (!locked) { setActiveModule(mod); setScreen("module"); } else notify("Upgrade your plan to unlock this module."); }}
                  style={{ padding:"22px", borderRadius:12, border:locked ? "1px solid rgba(255,255,255,0.04)" : `1px solid ${mod.color}25`, background:locked ? "rgba(255,255,255,0.02)" : `${mod.color}08`, cursor:locked?"not-allowed":"pointer", transition:"all 0.2s", opacity:locked?0.4:1, position:"relative" }}
                  onMouseEnter={e => { if (!locked) { e.currentTarget.style.border=`1px solid ${mod.color}50`; e.currentTarget.style.transform="translateY(-2px)"; }}}
                  onMouseLeave={e => { if (!locked) { e.currentTarget.style.border=`1px solid ${mod.color}25`; e.currentTarget.style.transform="translateY(0)"; }}}>
                  {locked && <div style={{ position:"absolute", top:14, right:14, fontSize:12, color:"#3A3530" }}>🔒</div>}
                  <div style={{ fontSize:28, marginBottom:12 }}>{mod.icon}</div>
                  <div style={{ fontFamily:"'Cormorant Garamond',serif", fontSize:18, fontWeight:700, color:"#EDE8DF", marginBottom:6 }}>{mod.title}</div>
                  <div style={{ fontSize:11, color:"#5A5248", marginBottom:14, lineHeight:1.5 }}>{mod.desc}</div>
                  <div style={{ fontSize:11, color:mod.color }}>{mod.lessons.length} lessons</div>
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );

  // ── MODULE VIEW ────────────────────────────────────────────────────────────
  if (screen === "module" && activeModule) return (
    <div style={{ minHeight:"100vh", background:"#080808", fontFamily:"'DM Sans',sans-serif", color:"#EDE8DF" }}>
      <div style={{ padding:"18px 32px", borderBottom:"1px solid rgba(212,175,106,0.1)", display:"flex", alignItems:"center", gap:16, background:"rgba(8,8,8,0.95)", position:"sticky", top:0, zIndex:50 }}>
        <button onClick={() => setScreen("dashboard")} style={{ background:"none", border:"none", color:"#5A5248", cursor:"pointer", fontSize:13, fontFamily:"'DM Sans',sans-serif" }}>← Dashboard</button>
        <div style={{ width:1, height:20, background:"rgba(255,255,255,0.06)" }}/>
        <span style={{ fontSize:16 }}>{activeModule.icon}</span>
        <span style={{ fontFamily:"'Cormorant Garamond',serif", fontSize:18, fontWeight:700 }}>{activeModule.title}</span>
      </div>

      <div style={{ maxWidth:900, margin:"0 auto", padding:"48px 32px" }}>
        <div style={{ marginBottom:40 }}>
          <div style={{ fontSize:12, color:activeModule.color, letterSpacing:2, textTransform:"uppercase", marginBottom:12, fontWeight:600 }}>Module Overview</div>
          <h2 style={{ fontFamily:"'Cormorant Garamond',serif", fontSize:40, fontWeight:300, margin:"0 0 16px" }}>{activeModule.title}</h2>
          <p style={{ color:"#7A7268", fontSize:15, lineHeight:1.7, maxWidth:600 }}>{activeModule.desc}</p>
        </div>

        <div style={{ display:"grid", gridTemplateColumns:"1fr 1fr", gap:12, marginBottom:40 }}>
          {activeModule.lessons.map((lesson, i) => (
            <button key={lesson} onClick={() => { setActiveLesson(lesson); startCoach(`Teach me about: "${lesson}" from the ${activeModule.title} module. Start with the key concepts, then give me real-world examples and actionable steps I can use immediately.`); }}
              style={{ padding:"18px 20px", borderRadius:10, border:`1px solid ${activeModule.color}20`, background:`${activeModule.color}06`, cursor:"pointer", textAlign:"left", display:"flex", alignItems:"center", gap:14, transition:"all 0.2s", fontFamily:"'DM Sans',sans-serif" }}
              onMouseEnter={e => { e.currentTarget.style.border=`1px solid ${activeModule.color}50`; e.currentTarget.style.background=`${activeModule.color}12`; }}
              onMouseLeave={e => { e.currentTarget.style.border=`1px solid ${activeModule.color}20`; e.currentTarget.style.background=`${activeModule.color}06`; }}>
              <span style={{ width:28, height:28, borderRadius:6, background:`${activeModule.color}20`, display:"flex", alignItems:"center", justifyContent:"center", fontSize:12, color:activeModule.color, fontWeight:700, flexShrink:0 }}>{i+1}</span>
              <span style={{ fontSize:14, color:"#C8C0B4", fontWeight:500 }}>{lesson}</span>
              <span style={{ marginLeft:"auto", color:activeModule.color, fontSize:12, flexShrink:0 }}>→</span>
            </button>
          ))}
        </div>

        <button onClick={() => startCoach(`Give me a comprehensive overview of the entire ${activeModule.title} module. Cover all key concepts, how they connect, and what I should focus on mastering first based on my profile as a ${ACCESS_TIERS[tier]?.description}.`)}
          style={{ padding:"16px 32px", borderRadius:8, border:`1px solid ${activeModule.color}40`, background:`${activeModule.color}12`, color:activeModule.color, fontSize:14, fontWeight:600, cursor:"pointer", fontFamily:"'DM Sans',sans-serif", letterSpacing:0.5 }}>
          🤖 AI Overview of Entire Module →
        </button>
      </div>
    </div>
  );

  // ── COACH / CHAT ───────────────────────────────────────────────────────────
  if (screen === "coach") return (
    <div style={{ height:"100vh", display:"flex", flexDirection:"column", background:"#080808", fontFamily:"'DM Sans',sans-serif", color:"#EDE8DF" }}>
      <div style={{ padding:"16px 28px", borderBottom:"1px solid rgba(212,175,106,0.1)", display:"flex", alignItems:"center", justifyContent:"space-between", background:"rgba(8,8,8,0.95)", flexShrink:0 }}>
        <div style={{ display:"flex", alignItems:"center", gap:14 }}>
          <button onClick={() => { if(activeModule) setScreen("module"); else setScreen("dashboard"); }} style={{ background:"none", border:"none", color:"#5A5248", cursor:"pointer", fontSize:13, fontFamily:"'DM Sans',sans-serif" }}>← Back</button>
          <div style={{ width:1, height:20, background:"rgba(255,255,255,0.06)" }}/>
          <div style={{ width:32, height:32, borderRadius:"50%", background:"linear-gradient(135deg,#D4AF6A,#8A6A2A)", display:"flex", alignItems:"center", justifyContent:"center", fontSize:13, fontWeight:700, color:"#080808" }}>AI</div>
          <div>
            <div style={{ fontFamily:"'Cormorant Garamond',serif", fontSize:16, fontWeight:700 }}>RealEdge AI Coach</div>
            <div style={{ fontSize:10, color:"#5A5248", letterSpacing:1 }}>{planStarted ? "SUCCESS PLAN MODE" : "COACHING SESSION"}</div>
          </div>
        </div>
        <div style={{ display:"flex", gap:8 }}>
          <button onClick={() => { setPlanStarted(false); setMessages([]); startCoach(); }} style={{ padding:"7px 14px", borderRadius:6, border:"1px solid rgba(212,175,106,0.2)", background:"rgba(212,175,106,0.06)", color:"#D4AF6A", fontSize:11, fontWeight:600, cursor:"pointer", fontFamily:"'DM Sans',sans-serif" }}>
            + New Session
          </button>
        </div>
      </div>

      <div style={{ flex:1, overflowY:"auto", padding:"28px 28px", display:"flex", flexDirection:"column", gap:20 }}>
        {messages.map((msg, i) => (
          <div key={i} style={{ display:"flex", justifyContent:msg.role==="user"?"flex-end":"flex-start", gap:10, alignItems:"flex-start" }}>
            {msg.role==="assistant" && (
              <div style={{ width:30, height:30, borderRadius:"50%", background:"linear-gradient(135deg,#D4AF6A,#8A6A2A)", display:"flex", alignItems:"center", justifyContent:"center", fontSize:11, fontWeight:700, color:"#080808", flexShrink:0, marginTop:2 }}>AI</div>
            )}
            <div style={{ maxWidth:"76%", padding:msg.role==="user"?"12px 16px":"18px 22px", borderRadius:msg.role==="user"?"18px 18px 4px 18px":"18px 18px 18px 4px", background:msg.role==="user"?"linear-gradient(135deg,#D4AF6A,#9A7A3A)":"rgba(255,255,255,0.04)", border:msg.role==="assistant"?"1px solid rgba(212,175,106,0.1)":"none", color:msg.role==="user"?"#080808":"#C8C0B4", fontSize:14, lineHeight:1.75 }}>
              {msg.role==="user" ? <span style={{ fontWeight:500 }}>{msg.content}</span> : <span dangerouslySetInnerHTML={{ __html:fmt(msg.content) }}/>}
            </div>
          </div>
        ))}
        {loading && (
          <div style={{ display:"flex", gap:10, alignItems:"flex-start" }}>
            <div style={{ width:30, height:30, borderRadius:"50%", background:"linear-gradient(135deg,#D4AF6A,#8A6A2A)", display:"flex", alignItems:"center", justifyContent:"center", fontSize:11, fontWeight:700, color:"#080808" }}>AI</div>
            <div style={{ padding:"16px 20px", borderRadius:"18px 18px 18px 4px", background:"rgba(255,255,255,0.04)", border:"1px solid rgba(212,175,106,0.1)", display:"flex", gap:5, alignItems:"center" }}>
              {[0,1,2].map(i => <div key={i} style={{ width:6, height:6, borderRadius:"50%", background:"#D4AF6A", opacity:0.6, animation:"dot 1.2s ease-in-out infinite", animationDelay:`${i*0.2}s` }}/>)}
            </div>
          </div>
        )}
        <div ref={messagesEndRef}/>
      </div>

      <div style={{ padding:"16px 28px", borderTop:"1px solid rgba(212,175,106,0.08)", background:"rgba(8,8,8,0.95)", flexShrink:0 }}>
        <div style={{ display:"flex", gap:10, alignItems:"flex-end" }}>
          <textarea ref={inputRef} value={chatInput} onChange={e => setChatInput(e.target.value)}
            onKeyDown={e => { if(e.key==="Enter"&&!e.shiftKey){ e.preventDefault(); sendMessage(); }}}
            placeholder="Ask your coach anything..." rows={1}
            style={{ flex:1, padding:"14px 18px", background:"rgba(255,255,255,0.04)", border:"1px solid rgba(212,175,106,0.15)", borderRadius:12, color:"#EDE8DF", fontSize:14, outline:"none", resize:"none", lineHeight:1.5, fontFamily:"'DM Sans',sans-serif", maxHeight:120 }}/>
          <button onClick={() => sendMessage()} disabled={!chatInput.trim()||loading}
            style={{ width:46, height:46, borderRadius:10, border:"none", background:chatInput.trim()&&!loading?"linear-gradient(135deg,#D4AF6A,#9A7A3A)":"rgba(255,255,255,0.05)", color:chatInput.trim()&&!loading?"#080808":"#3A3530", fontSize:18, cursor:chatInput.trim()&&!loading?"pointer":"not-allowed", flexShrink:0, display:"flex", alignItems:"center", justifyContent:"center", transition:"all 0.2s" }}>↑</button>
        </div>
        <div style={{ fontSize:10, color:"#2A2520", textAlign:"center", marginTop:8, letterSpacing:1 }}>ENTER TO SEND · SHIFT+ENTER FOR NEW LINE</div>
      </div>
      <style>{`@keyframes dot{0%,100%{transform:scale(0.7);opacity:0.3}50%{transform:scale(1.2);opacity:1}} textarea{overflow:hidden} ::-webkit-scrollbar{width:3px} ::-webkit-scrollbar-thumb{background:rgba(212,175,106,0.15);border-radius:3px}`}</style>
    </div>
  );

  return null;
}

// ── Mount to the DOM ──────────────────────────────────────────────────────────
(function () {
  var container = document.getElementById("ravlo-university-root");
  if (container) {
    ReactDOM.createRoot(container).render(React.createElement(RavloUniversity));
  }
})();
