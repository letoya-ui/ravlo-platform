// ─── Ravlo Academy — Flask Integration Build ──────────────────────────────
// AI calls are proxied through /academy/chat (keeps ANTHROPIC_API_KEY
// server-side).  Fonts are loaded in portal.html <head> to prevent FOUC.
// React hooks pulled from the global React UMD bundle (no import needed).

const { useState, useRef, useEffect, useCallback } = React;

// ─── CONSTANTS ────────────────────────────────────────────────────────────────

const ACCESS_TIERS = {
  elite: {
    label: "Elite Access", badge: "ELITE", color: "#D4AF6A",
    bg: "rgba(212,175,106,0.12)", border: "rgba(212,175,106,0.4)", icon: "◆",
    description: "Ravlo Investors & Partners",
    perks: ["Unlimited AI Coaching", "All Modules", "1-on-1 Success Plans", "Priority Support", "Investor Briefings"],
    accessCode: "RAVLO-ELITE", monthly: 0, badge_text: "Complimentary",
  },
  lending: {
    label: "Lending Team", badge: "TEAM", color: "#6AB4D4",
    bg: "rgba(106,180,212,0.12)", border: "rgba(106,180,212,0.4)", icon: "◈",
    description: "Ravlo Lending Staff",
    perks: ["Unlimited AI Coaching", "Loan Modules", "Commercial Training", "Team Dashboard", "Deal Review"],
    accessCode: "RAVLO-LENDING", monthly: 0, badge_text: "Employment Benefit",
  },
  pro: {
    label: "Pro", badge: "PRO", color: "#B06AD4",
    bg: "rgba(176,106,212,0.12)", border: "rgba(176,106,212,0.4)", icon: "●",
    description: "Independent Realtors & Investors",
    perks: ["Unlimited AI Coaching", "All Modules", "Success Plans", "Community Access"],
    monthly: 97, badge_text: "$97 / month",
  },
  starter: {
    label: "Starter", badge: "START", color: "#6AD4A0",
    bg: "rgba(106,212,160,0.12)", border: "rgba(106,212,160,0.4)", icon: "○",
    description: "New to Real Estate",
    perks: ["Core AI Coaching", "3 Modules", "Basic Success Plan"],
    monthly: 47, badge_text: "$47 / month",
  },
};

// Auto-detect tier from access code
const CODE_MAP = {
  "RAVLO-ELITE": "elite",
  "RAVLO-LENDING": "lending",
};

const MODULES = [
  {
    id: "residential", title: "Residential Mastery", icon: "🏠", color: "#D4AF6A",
    lessons: ["Listing Strategy & Pricing", "Buyer Representation", "Negotiation Frameworks", "CMA Deep Dive", "Open House Optimization", "Lead Conversion Systems"],
    tier: ["starter", "pro", "elite", "lending"],
    desc: "Master the full residential transaction from lead to close.",
  },
  {
    id: "commercial", title: "Commercial Real Estate", icon: "🏢", color: "#6AB4D4",
    lessons: ["Office & Retail Leasing", "Cap Rate & NOI Analysis", "Investment Sales", "1031 Exchanges", "Tenant & Landlord Rep", "Market Analysis"],
    tier: ["pro", "elite", "lending"],
    desc: "Advanced commercial strategies for office, retail, and industrial.",
  },
  {
    id: "loans", title: "Mortgage & Lending", icon: "💰", color: "#6AD4A0",
    lessons: [
      "SBA 7(a) & 504 Programs",
      "CMBS & Bridge Loans",
      "DSCR & Underwriting",
      "LTV / LTC Ratios",
      "Rate Locks & Assumptions",
      "Hard Money & Private Lending",
      "Conventional, FHA & VA Loans",
      "Adjustable Rate Mortgages & Buydowns",
      "Borrower Qualification Framework",
      "Loan Processing Workflows",
    ],
    tier: ["pro", "elite", "lending"],
    desc: "Complete loan structuring from application to close — residential, commercial, and beyond.",
  },
  {
    id: "business", title: "Realtor Business Growth", icon: "📈", color: "#B06AD4",
    lessons: ["Building Your SOI System", "CRM Setup & Automation", "Social Media & Video", "Geographic Farming", "Team Building", "Brokerage Selection"],
    tier: ["starter", "pro", "elite", "lending"],
    desc: "Build a scalable real estate business that generates without you.",
  },
  {
    id: "investing", title: "Real Estate Investing", icon: "🏗️", color: "#D46A6A",
    lessons: ["BRRRR Strategy", "Multifamily Underwriting", "Market Selection", "Deal Sourcing", "Property Management", "Exit Strategies"],
    tier: ["pro", "elite"],
    desc: "From first rental to multifamily portfolio — a complete investor path.",
  },
  {
    id: "advanced", title: "Advanced Deal Structuring", icon: "⚡", color: "#D4A06A",
    lessons: ["Creative Financing", "Seller Financing & Wraps", "Joint Ventures", "Syndication Basics", "Distressed Assets", "Off-Market Strategies"],
    tier: ["elite"],
    desc: "Elite strategies for complex, high-value transactions.",
  },
];

const ONBOARDING_ROLES = ["Realtor / Agent", "Real Estate Investor", "Mortgage Loan Officer", "Lender / Broker", "New to Real Estate"];
const ONBOARDING_GOALS = ["Close more deals this year", "Get my first deal", "Master mortgage & lending", "Build a rental portfolio", "Grow and scale my team", "Increase my income by 50%+"];
const ONBOARDING_CHALLENGES = ["Finding consistent leads", "Converting leads to clients", "Understanding financing & loans", "Managing my time and pipeline", "Building systems that scale", "Standing out in my market"];

const AI_SYSTEM = `You are the RealEdge AI Coach inside Ravlo Academy — an elite real estate education platform.

You are a world-class coach with deep expertise in:
- Residential Real Estate (listings, buyers, negotiation, CMAs, lead gen, farming)
- Commercial Real Estate (office, retail, industrial, cap rates, NOI, 1031s, investment sales)
- Mortgage & Lending (conventional, FHA, VA, DSCR, SBA, CMBS, bridge, ARMs, buydowns, rate locks, borrower qualification, loan processing, pipeline management)
- Realtor Business Development (SOI, CRM, branding, team building, social media, farming)
- Real Estate Investing (BRRRR, multifamily, deal analysis, exit strategies)

Your style: Direct, no-fluff, data-driven. You speak like a top producer who has closed $100M+ and mentored 500+ agents. Use real numbers, real scenarios, real frameworks.

When asked for a success plan or first-week action plan, create a structured plan with:
1. ASSESSMENT (what you know about them)
2. 30-DAY SPRINT (specific daily/weekly actions with real numbers)
3. 60-DAY MILESTONES (measurable targets)
4. 90-DAY VISION (where they should be)
5. KEY METRICS (what to track weekly)
6. ACCOUNTABILITY SYSTEM (how to stay on track)

Always personalize. Always be specific. Never be generic.`;

const STORAGE_KEY = "ravlo_academy_v2";

function loadStorage() {
  try { return JSON.parse(localStorage.getItem(STORAGE_KEY) || "{}"); } catch { return {}; }
}
function saveStorage(data) {
  try { localStorage.setItem(STORAGE_KEY, JSON.stringify(data)); } catch {}
}

// ─── MAIN COMPONENT ───────────────────────────────────────────────────────────
function RavloAcademy() {
  const [screen, setScreen] = useState("landing");
  const [tier, setTier] = useState(null);
  const [userName, setUserName] = useState("");
  const [nameInput, setNameInput] = useState("");
  const [codeInput, setCodeInput] = useState("");
  const [codeError, setCodeError] = useState("");
  const [activeModule, setActiveModule] = useState(null);
  const [messages, setMessages] = useState([]);
  const [chatInput, setChatInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [notification, setNotification] = useState(null);
  const [isMobile, setIsMobile] = useState(false);

  // Progress: { [moduleId]: boolean[] }
  const [progress, setProgress] = useState({});
  // Chat history: [{ id, label, date, messages }]
  const [chatHistory, setChatHistory] = useState([]);
  // Onboarding
  const [onboardingStep, setOnboardingStep] = useState(0);
  const [onboardingAnswers, setOnboardingAnswers] = useState({ role: "", goal: "", challenge: "" });
  const [hasOnboarded, setHasOnboarded] = useState(false);
  // History panel
  const [showHistory, setShowHistory] = useState(false);
  const [historyFilter, setHistoryFilter] = useState("");

  const messagesEndRef = useRef(null);
  const inputRef = useRef(null);

  // ── Server-injected tier (authoritative — set by Flask, never user-controlled) ──
  useEffect(() => {
    const srv = window.RAVLO_ACADEMY || {};
    if (srv.tier && ACCESS_TIERS[srv.tier]) {
      const name = (srv.userName || "").trim() || "Member";
      setTier(srv.tier);
      setUserName(name);
      const store = loadStorage();
      const userData = store[name] || {};
      if (!userData.onboarded) {
        setOnboardingStep(0);
        setOnboardingAnswers({ role: "", goal: "", challenge: "" });
        setScreen("onboarding");
      } else {
        setHasOnboarded(true);
        setScreen("dashboard");
      }
    }
  }, []);

  // Mobile detection
  useEffect(() => {
    const check = () => setIsMobile(window.innerWidth < 768);
    check();
    window.addEventListener("resize", check);
    return () => window.removeEventListener("resize", check);
  }, []);

  useEffect(() => { messagesEndRef.current?.scrollIntoView({ behavior: "smooth" }); }, [messages]);

  // Load user data from localStorage when userName changes
  useEffect(() => {
    if (!userName) return;
    const store = loadStorage();
    const userData = store[userName] || {};
    setProgress(userData.progress || {});
    setChatHistory(userData.history || []);
    setHasOnboarded(userData.onboarded || false);
  }, [userName]);

  // Persist progress
  const saveProgress = useCallback((newProgress) => {
    const store = loadStorage();
    store[userName] = { ...store[userName], progress: newProgress };
    saveStorage(store);
    setProgress(newProgress);
  }, [userName]);

  // Persist history
  const saveHistory = useCallback((newHistory) => {
    const store = loadStorage();
    store[userName] = { ...store[userName], history: newHistory };
    saveStorage(store);
    setChatHistory(newHistory);
  }, [userName]);

  const notify = (msg) => { setNotification(msg); setTimeout(() => setNotification(null), 3000); };

  // ── Smart code detection ──────────────────────────────────────────────────
  const handleSmartCodeAccess = () => {
    const code = codeInput.trim().toUpperCase();
    const detectedTier = CODE_MAP[code];
    if (detectedTier) {
      const name = nameInput.trim() || "Member";
      setTier(detectedTier);
      setUserName(name);
      setCodeError("");
      // Check if first time (onboarding needed)
      const store = loadStorage();
      const userData = store[name] || {};
      if (!userData.onboarded) {
        setOnboardingStep(0);
        setOnboardingAnswers({ role: "", goal: "", challenge: "" });
        setScreen("onboarding");
      } else {
        setHasOnboarded(true);
        setScreen("dashboard");
      }
    } else if (code.length > 0) {
      setCodeError("Access code not recognized. Contact your Ravlo representative.");
    } else {
      setCodeError("Please enter your access code.");
    }
  };

  const handlePaidAccess = (tierKey) => {
    const name = nameInput.trim() || "Member";
    setTier(tierKey);
    setUserName(name);
    const store = loadStorage();
    const userData = store[name] || {};
    if (!userData.onboarded) {
      setOnboardingStep(0);
      setOnboardingAnswers({ role: "", goal: "", challenge: "" });
      setScreen("onboarding");
    } else {
      setScreen("dashboard");
    }
  };

  const finishOnboarding = () => {
    const store = loadStorage();
    const userData = store[userName] || {};
    store[userName] = { ...userData, onboarded: true, onboardingAnswers };
    saveStorage(store);
    setHasOnboarded(true);
    // Transition to coach with welcome plan
    setMessages([]);
    setScreen("coach");
    const welcomePrompt = `I'm ${userName}, a ${onboardingAnswers.role || "real estate professional"}. My #1 goal is to ${(onboardingAnswers.goal || "grow my business").toLowerCase()} and my biggest challenge is ${(onboardingAnswers.challenge || "consistency").toLowerCase()}. I have ${ACCESS_TIERS[tier]?.description} access. Please greet me, then immediately build my personalized first-week action plan — specific actions I can start today with real numbers and clear milestones.`;
    setTimeout(() => sendMessage(welcomePrompt), 100);
  };

  // ── AI chat — proxied through Flask /academy/chat ─────────────────────────
  const sendMessage = async (text) => {
    const msg = text || chatInput.trim();
    if (!msg || loading) return;
    setChatInput("");
    const newMsgs = [...messages, { role: "user", content: msg }];
    setMessages(newMsgs);
    setLoading(true);
    const context = `User: ${userName} | Access: ${ACCESS_TIERS[tier]?.label} | Module: ${activeModule?.title || "General"} | Role: ${onboardingAnswers?.role || "Not specified"} | Goal: ${onboardingAnswers?.goal || "Not specified"}`;
    try {
      const res = await fetch("/academy/chat", {
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
      const finalMsgs = [...newMsgs, { role: "assistant", content: reply }];
      setMessages(finalMsgs);
    } catch { setMessages([...newMsgs, { role: "assistant", content: "Connection error. Please try again." }]); }
    finally { setLoading(false); setTimeout(() => inputRef.current?.focus(), 100); }
  };

  // ── Session history ───────────────────────────────────────────────────────
  const saveCurrentSession = () => {
    if (messages.length === 0) return;
    const firstUser = messages.find(m => m.role === "user");
    const label = firstUser ? firstUser.content.slice(0, 60) + (firstUser.content.length > 60 ? "…" : "") : "Coaching Session";
    const session = { id: Date.now(), label, date: new Date().toLocaleDateString(), messages };
    const updated = [session, ...chatHistory].slice(0, 20);
    saveHistory(updated);
    notify("Session saved ✓");
  };

  const loadSession = (session) => {
    setMessages(session.messages);
    setShowHistory(false);
    setScreen("coach");
  };

  const deleteSession = (id) => {
    const updated = chatHistory.filter(s => s.id !== id);
    saveHistory(updated);
  };

  // ── Progress ─────────────────────────────────────────────────────────────
  const toggleLesson = (moduleId, lessonIndex) => {
    const modProgress = [...(progress[moduleId] || [])];
    modProgress[lessonIndex] = !modProgress[lessonIndex];
    const newProgress = { ...progress, [moduleId]: modProgress };
    saveProgress(newProgress);
  };

  const getModuleProgress = (moduleId) => {
    const mod = MODULES.find(m => m.id === moduleId);
    if (!mod) return { completed: 0, total: 0, pct: 0 };
    const modProgress = progress[moduleId] || [];
    const completed = modProgress.filter(Boolean).length;
    return { completed, total: mod.lessons.length, pct: Math.round((completed / mod.lessons.length) * 100) };
  };

  // ── Referral ─────────────────────────────────────────────────────────────
  const copyReferralLink = () => {
    const link = window.location.origin + "/academy";
    navigator.clipboard.writeText(link).then(() => notify("Academy link copied to clipboard! ✓")).catch(() => notify("Copy: " + link));
  };

  // ── Coach helpers ─────────────────────────────────────────────────────────
  const startCoach = (prompt = "") => {
    setScreen("coach");
    if (messages.length === 0 || prompt) {
      if (!prompt) {
        const welcome = `Hi ${userName}! I'm your RealEdge AI Coach. What's your biggest challenge right now, or what would you like to master today?`;
        setMessages([{ role: "assistant", content: welcome }]);
      } else { setMessages([]); setTimeout(() => sendMessage(prompt), 100); }
    }
  };

  const startPlan = () => {
    setMessages([]);
    setScreen("coach");
    const prompt = `Create my personalized 90-day success plan. My name is ${userName}, I'm a ${onboardingAnswers?.role || ACCESS_TIERS[tier]?.description} with ${ACCESS_TIERS[tier]?.label} access. My #1 goal: ${onboardingAnswers?.goal || "grow my business"}. My biggest challenge: ${onboardingAnswers?.challenge || "consistency"}. Build a complete, specific plan.`;
    setTimeout(() => sendMessage(prompt), 100);
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

  const S = {
    page: { minHeight: "100svh", background: "#080808", fontFamily: "'DM Sans',sans-serif", color: "#EDE8DF" },
    gold: "#D4AF6A",
  };

  // ── LANDING ───────────────────────────────────────────────────────────────
  if (screen === "landing") return (
    <div style={{ ...S.page, display: "flex", flexDirection: "column", overflow: "hidden", position: "relative" }}>
      <div style={{ position: "absolute", inset: 0, backgroundImage: "radial-gradient(ellipse 80% 50% at 50% -10%, rgba(212,175,106,0.15) 0%, transparent 70%)", pointerEvents: "none" }} />
      <div style={{ position: "absolute", inset: 0, backgroundImage: "repeating-linear-gradient(0deg,transparent,transparent 80px,rgba(212,175,106,0.02) 80px,rgba(212,175,106,0.02) 81px),repeating-linear-gradient(90deg,transparent,transparent 80px,rgba(212,175,106,0.02) 80px,rgba(212,175,106,0.02) 81px)", pointerEvents: "none" }} />

      <nav style={{ padding: isMobile ? "16px 20px" : "20px 48px", display: "flex", alignItems: "center", justifyContent: "space-between", borderBottom: "1px solid rgba(212,175,106,0.1)", position: "relative", zIndex: 10 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <div style={{ width: isMobile ? 30 : 36, height: isMobile ? 30 : 36, border: "1.5px solid #D4AF6A", borderRadius: 6, display: "flex", alignItems: "center", justifyContent: "center", fontSize: isMobile ? 14 : 16, color: "#D4AF6A", fontFamily: "'Cormorant Garamond',serif", fontWeight: 700 }}>R</div>
          <div>
            <div style={{ fontFamily: "'Cormorant Garamond',serif", fontSize: isMobile ? 16 : 20, fontWeight: 700, letterSpacing: 2, color: "#EDE8DF" }}>RAVLO</div>
            <div style={{ fontSize: 9, letterSpacing: 4, color: "#D4AF6A", textTransform: "uppercase", marginTop: -2 }}>Academy</div>
          </div>
        </div>
        <button onClick={() => setScreen("access")} style={{ padding: isMobile ? "8px 18px" : "10px 28px", borderRadius: 6, border: "1px solid rgba(212,175,106,0.4)", background: "rgba(212,175,106,0.08)", color: "#D4AF6A", fontSize: isMobile ? 12 : 13, fontWeight: 600, cursor: "pointer", letterSpacing: 1, fontFamily: "'DM Sans',sans-serif" }}>
          Access Portal →
        </button>
      </nav>

      <div style={{ flex: 1, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", padding: isMobile ? "48px 20px" : "80px 24px", textAlign: "center", position: "relative", zIndex: 1 }}>
        <div style={{ fontSize: 11, letterSpacing: 6, color: "#D4AF6A", textTransform: "uppercase", marginBottom: 24, fontWeight: 500 }}>Real Estate Education · Reimagined</div>
        <h1 style={{ fontFamily: "'Cormorant Garamond',serif", fontSize: isMobile ? "clamp(44px,12vw,64px)" : "clamp(52px,8vw,100px)", fontWeight: 300, lineHeight: 0.95, margin: "0 0 8px", letterSpacing: -2 }}>
          <span style={{ display: "block", color: "#EDE8DF" }}>Ravlo</span>
          <span style={{ display: "block", color: "#D4AF6A", fontWeight: 700, fontStyle: "italic" }}>Academy</span>
        </h1>
        <p style={{ fontSize: isMobile ? 15 : "clamp(15px,2vw,18px)", color: "#7A7268", maxWidth: 540, lineHeight: 1.7, margin: "32px auto 48px", fontWeight: 300 }}>
          AI-powered coaching for realtors, investors, and lenders. One-on-one guidance, personalized success plans, and the knowledge to close more deals.
        </p>
        <div style={{ display: "flex", gap: 12, flexWrap: "wrap", justifyContent: "center" }}>
          <button onClick={() => setScreen("access")} style={{ padding: isMobile ? "14px 28px" : "16px 40px", borderRadius: 8, border: "none", background: "linear-gradient(135deg,#D4AF6A,#9A7A3A)", color: "#080808", fontSize: isMobile ? 14 : 15, fontWeight: 700, cursor: "pointer", letterSpacing: 1, fontFamily: "'DM Sans',sans-serif" }}>
            Start Learning
          </button>
          <button onClick={() => setScreen("access")} style={{ padding: isMobile ? "14px 28px" : "16px 40px", borderRadius: 8, border: "1px solid rgba(212,175,106,0.3)", background: "transparent", color: "#D4AF6A", fontSize: isMobile ? 14 : 15, fontWeight: 500, cursor: "pointer", letterSpacing: 0.5, fontFamily: "'DM Sans',sans-serif" }}>
            Partner Access
          </button>
        </div>

        <div style={{ display: "flex", gap: isMobile ? 28 : 48, marginTop: isMobile ? 48 : 80, flexWrap: "wrap", justifyContent: "center" }}>
          {[["6", "Learning Modules"], ["AI", "Powered Coaching"], ["1:1", "Success Plans"], ["∞", "Deal Knowledge"]].map(([n, l]) => (
            <div key={l} style={{ textAlign: "center" }}>
              <div style={{ fontFamily: "'Cormorant Garamond',serif", fontSize: isMobile ? 32 : 40, fontWeight: 700, color: "#D4AF6A", lineHeight: 1 }}>{n}</div>
              <div style={{ fontSize: 10, color: "#5A5248", letterSpacing: 2, textTransform: "uppercase", marginTop: 6 }}>{l}</div>
            </div>
          ))}
        </div>
      </div>

      <div style={{ padding: isMobile ? "0 16px 48px" : "0 24px 80px", maxWidth: 900, margin: "0 auto", width: "100%", position: "relative", zIndex: 1 }}>
        <div style={{ textAlign: "center", marginBottom: 24 }}>
          <div style={{ fontSize: 11, letterSpacing: 4, color: "#5A5248", textTransform: "uppercase" }}>Access Tiers</div>
        </div>
        <div style={{ display: "grid", gridTemplateColumns: isMobile ? "1fr 1fr" : "repeat(4,1fr)", gap: 10 }}>
          {Object.entries(ACCESS_TIERS).map(([key, t]) => (
            <div key={key} onClick={() => setScreen("access")} style={{ padding: isMobile ? "14px" : "20px", borderRadius: 10, border: `1px solid ${t.border}`, background: t.bg, cursor: "pointer", transition: "all 0.2s" }}
              onMouseEnter={e => e.currentTarget.style.transform = "translateY(-2px)"}
              onMouseLeave={e => e.currentTarget.style.transform = "translateY(0)"}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 8 }}>
                <span style={{ fontSize: 18, color: t.color }}>{t.icon}</span>
                <span style={{ fontSize: 9, padding: "2px 6px", borderRadius: 20, border: `1px solid ${t.border}`, color: t.color, letterSpacing: 0.5, fontWeight: 600 }}>{t.badge_text}</span>
              </div>
              <div style={{ fontFamily: "'Cormorant Garamond',serif", fontSize: isMobile ? 14 : 16, fontWeight: 700, color: "#EDE8DF", marginBottom: 2 }}>{t.label}</div>
              <div style={{ fontSize: 10, color: "#5A5248" }}>{t.description}</div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );

  // ── ACCESS ────────────────────────────────────────────────────────────────
  if (screen === "access") return (
    <div style={{ ...S.page, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", padding: "40px 20px", position: "relative" }}>
      <div style={{ position: "absolute", inset: 0, backgroundImage: "radial-gradient(ellipse 60% 40% at 50% 0%, rgba(212,175,106,0.08) 0%, transparent 70%)", pointerEvents: "none" }} />
      <button onClick={() => setScreen("landing")} style={{ position: "absolute", top: 20, left: 20, background: "none", border: "none", color: "#5A5248", cursor: "pointer", fontSize: 13, fontFamily: "'DM Sans',sans-serif" }}>← Back</button>

      <div style={{ maxWidth: 680, width: "100%", position: "relative", zIndex: 1 }}>
        <div style={{ textAlign: "center", marginBottom: 40 }}>
          <div style={{ fontFamily: "'Cormorant Garamond',serif", fontSize: 12, letterSpacing: 6, color: "#D4AF6A", textTransform: "uppercase", marginBottom: 10 }}>Choose Your Access</div>
          <h2 style={{ fontFamily: "'Cormorant Garamond',serif", fontSize: isMobile ? 32 : 42, fontWeight: 300, margin: "0 0 8px" }}>Ravlo <strong style={{ fontWeight: 700 }}>Academy</strong></h2>
          <p style={{ color: "#5A5248", fontSize: 13 }}>Partners &amp; investors enter your code. New members choose a plan below.</p>
        </div>

        {/* Name */}
        <div style={{ marginBottom: 20 }}>
          <label style={{ display: "block", fontSize: 10, letterSpacing: 3, color: "#D4AF6A", marginBottom: 10, textTransform: "uppercase" }}>Your Name</label>
          <input value={nameInput} onChange={e => setNameInput(e.target.value)} placeholder="First & Last Name"
            style={{ width: "100%", padding: "14px 18px", background: "rgba(255,255,255,0.04)", border: "1px solid rgba(212,175,106,0.2)", borderRadius: 8, color: "#EDE8DF", fontSize: 14, outline: "none", boxSizing: "border-box", fontFamily: "'DM Sans',sans-serif" }} />
        </div>

        {/* Smart code input */}
        <div style={{ marginBottom: 28 }}>
          <label style={{ display: "block", fontSize: 10, letterSpacing: 3, color: "#D4AF6A", marginBottom: 10, textTransform: "uppercase" }}>Partner / Team Access Code</label>
          <div style={{ position: "relative" }}>
            <input value={codeInput} onChange={e => { setCodeInput(e.target.value); setCodeError(""); }}
              placeholder="Enter your access code (e.g. RAVLO-ELITE)"
              onKeyDown={e => e.key === "Enter" && handleSmartCodeAccess()}
              style={{ width: "100%", padding: "14px 18px", background: "rgba(255,255,255,0.04)", border: `1px solid ${codeError ? "#D46A6A" : "rgba(212,175,106,0.2)"}`, borderRadius: 8, color: "#EDE8DF", fontSize: 14, outline: "none", boxSizing: "border-box", fontFamily: "'DM Sans',sans-serif" }} />
            {CODE_MAP[codeInput.trim().toUpperCase()] && (
              <div style={{ position: "absolute", right: 14, top: "50%", transform: "translateY(-50%)", fontSize: 11, color: "#6AD4A0", fontWeight: 600, letterSpacing: 1 }}>
                {ACCESS_TIERS[CODE_MAP[codeInput.trim().toUpperCase()]]?.label} ✓
              </div>
            )}
          </div>
          {codeError && <div style={{ color: "#D46A6A", fontSize: 12, marginTop: 8 }}>{codeError}</div>}
          <button onClick={handleSmartCodeAccess} style={{ width: "100%", marginTop: 12, padding: "13px", borderRadius: 8, border: "none", background: "linear-gradient(135deg,#D4AF6A,#9A7A3A)", color: "#080808", fontSize: 14, fontWeight: 700, cursor: "pointer", fontFamily: "'DM Sans',sans-serif", letterSpacing: 0.5 }}>
            Enter Academy →
          </button>
        </div>

        <div style={{ height: 1, background: "rgba(255,255,255,0.05)", margin: "0 0 28px" }} />

        {/* Paid plans */}
        <div>
          <div style={{ fontSize: 10, letterSpacing: 3, color: "#5A5248", marginBottom: 16, textTransform: "uppercase" }}>Subscription Plans</div>
          <div style={{ display: "grid", gridTemplateColumns: isMobile ? "1fr" : "1fr 1fr", gap: 12 }}>
            {["pro", "starter"].map(key => {
              const pt = ACCESS_TIERS[key];
              return (
                <div key={key} style={{ padding: "20px", borderRadius: 10, border: `1px solid ${pt.border}`, background: pt.bg }}>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 10 }}>
                    <div style={{ fontFamily: "'Cormorant Garamond',serif", fontSize: 20, fontWeight: 700, color: "#EDE8DF" }}>{pt.label}</div>
                    <div style={{ textAlign: "right" }}>
                      <div style={{ fontFamily: "'Cormorant Garamond',serif", fontSize: 26, fontWeight: 700, color: pt.color, lineHeight: 1 }}>${pt.monthly}</div>
                      <div style={{ fontSize: 10, color: "#5A5248" }}>/month</div>
                    </div>
                  </div>
                  <div style={{ fontSize: 11, color: "#5A5248", marginBottom: 10 }}>{pt.description}</div>
                  <ul style={{ margin: "0 0 14px", padding: 0, listStyle: "none" }}>
                    {pt.perks.map(p => <li key={p} style={{ fontSize: 11, color: "#7A7268", display: "flex", gap: 6, marginBottom: 3 }}><span style={{ color: pt.color }}>✓</span>{p}</li>)}
                  </ul>
                  <button onClick={() => handlePaidAccess(key)} style={{ width: "100%", padding: "11px", borderRadius: 6, border: "none", background: `linear-gradient(135deg,${pt.color},${pt.color}88)`, color: "#080808", fontSize: 13, fontWeight: 700, cursor: "pointer", fontFamily: "'DM Sans',sans-serif" }}>
                    Subscribe — ${pt.monthly}/mo
                  </button>
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );

  // ── ONBOARDING ────────────────────────────────────────────────────────────
  if (screen === "onboarding") {
    const steps = [
      { key: "role", label: "What's your primary role?", options: ONBOARDING_ROLES },
      { key: "goal", label: "What's your #1 goal right now?", options: ONBOARDING_GOALS },
      { key: "challenge", label: "What's your biggest challenge?", options: ONBOARDING_CHALLENGES },
    ];
    const currentStep = steps[onboardingStep];
    const allAnswered = steps.slice(0, onboardingStep + 1).every(s => onboardingAnswers[s.key]);

    return (
      <div style={{ ...S.page, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", padding: "40px 20px", position: "relative" }}>
        <div style={{ position: "absolute", inset: 0, backgroundImage: "radial-gradient(ellipse 60% 40% at 50% 0%, rgba(212,175,106,0.08) 0%, transparent 70%)", pointerEvents: "none" }} />

        <div style={{ maxWidth: 600, width: "100%", position: "relative", zIndex: 1 }}>
          {/* Progress indicators */}
          <div style={{ display: "flex", gap: 8, marginBottom: 40, justifyContent: "center" }}>
            {steps.map((s, i) => (
              <div key={s.key} style={{ height: 3, flex: 1, maxWidth: 80, borderRadius: 2, background: i <= onboardingStep ? "#D4AF6A" : "rgba(212,175,106,0.15)", transition: "all 0.3s" }} />
            ))}
          </div>

          <div style={{ marginBottom: 32 }}>
            <div style={{ fontSize: 10, letterSpacing: 4, color: "#D4AF6A", textTransform: "uppercase", marginBottom: 16 }}>Step {onboardingStep + 1} of {steps.length}</div>
            <h2 style={{ fontFamily: "'Cormorant Garamond',serif", fontSize: isMobile ? 28 : 38, fontWeight: 300, margin: "0 0 8px" }}>
              Welcome, <strong style={{ fontWeight: 700, color: "#D4AF6A" }}>{userName}.</strong>
            </h2>
            <p style={{ color: "#7A7268", fontSize: 15, marginBottom: 32 }}>{currentStep.label}</p>

            <div style={{ display: "flex", flexWrap: "wrap", gap: 10 }}>
              {currentStep.options.map(opt => (
                <button key={opt} onClick={() => setOnboardingAnswers(prev => ({ ...prev, [currentStep.key]: opt }))}
                  style={{ padding: "10px 18px", borderRadius: 24, border: `1px solid ${onboardingAnswers[currentStep.key] === opt ? "#D4AF6A" : "rgba(212,175,106,0.2)"}`, background: onboardingAnswers[currentStep.key] === opt ? "rgba(212,175,106,0.15)" : "rgba(212,175,106,0.04)", color: onboardingAnswers[currentStep.key] === opt ? "#D4AF6A" : "#7A7268", fontSize: 13, cursor: "pointer", transition: "all 0.2s", fontFamily: "'DM Sans',sans-serif" }}>
                  {opt}
                </button>
              ))}
            </div>
          </div>

          <div style={{ display: "flex", gap: 12, justifyContent: "flex-end" }}>
            {onboardingStep > 0 && (
              <button onClick={() => setOnboardingStep(s => s - 1)} style={{ padding: "13px 24px", borderRadius: 8, border: "1px solid rgba(255,255,255,0.08)", background: "transparent", color: "#5A5248", fontSize: 14, cursor: "pointer", fontFamily: "'DM Sans',sans-serif" }}>Back</button>
            )}
            {onboardingStep < steps.length - 1 ? (
              <button onClick={() => { if (onboardingAnswers[currentStep.key]) setOnboardingStep(s => s + 1); }}
                disabled={!onboardingAnswers[currentStep.key]}
                style={{ padding: "13px 32px", borderRadius: 8, border: "none", background: onboardingAnswers[currentStep.key] ? "linear-gradient(135deg,#D4AF6A,#9A7A3A)" : "rgba(255,255,255,0.05)", color: onboardingAnswers[currentStep.key] ? "#080808" : "#3A3530", fontSize: 14, fontWeight: 700, cursor: onboardingAnswers[currentStep.key] ? "pointer" : "not-allowed", fontFamily: "'DM Sans',sans-serif" }}>
                Continue →
              </button>
            ) : (
              <button onClick={() => { if (onboardingAnswers[currentStep.key]) finishOnboarding(); }}
                disabled={!onboardingAnswers[currentStep.key]}
                style={{ padding: "13px 32px", borderRadius: 8, border: "none", background: onboardingAnswers[currentStep.key] ? "linear-gradient(135deg,#D4AF6A,#9A7A3A)" : "rgba(255,255,255,0.05)", color: onboardingAnswers[currentStep.key] ? "#080808" : "#3A3530", fontSize: 14, fontWeight: 700, cursor: onboardingAnswers[currentStep.key] ? "pointer" : "not-allowed", fontFamily: "'DM Sans',sans-serif" }}>
                Get My Plan →
              </button>
            )}
          </div>
        </div>
      </div>
    );
  }

  // ── DASHBOARD ─────────────────────────────────────────────────────────────
  if (screen === "dashboard") return (
    <div style={{ ...S.page, position: "relative" }}>

      {/* Notification */}
      {notification && <div style={{ position: "fixed", top: 20, right: 20, padding: "12px 20px", borderRadius: 8, background: "rgba(212,175,106,0.15)", border: "1px solid rgba(212,175,106,0.3)", color: "#D4AF6A", fontSize: 13, zIndex: 200, fontFamily: "'DM Sans',sans-serif" }}>{notification}</div>}

      {/* History panel */}
      {showHistory && (
        <div style={{ position: "fixed", inset: 0, zIndex: 100 }}>
          <div onClick={() => setShowHistory(false)} style={{ position: "absolute", inset: 0, background: "rgba(0,0,0,0.6)" }} />
          <div style={{ position: "absolute", right: 0, top: 0, bottom: 0, width: isMobile ? "100%" : 420, background: "#0D0D0D", borderLeft: "1px solid rgba(212,175,106,0.15)", display: "flex", flexDirection: "column" }}>
            <div style={{ padding: "20px 24px", borderBottom: "1px solid rgba(212,175,106,0.1)", display: "flex", alignItems: "center", justifyContent: "space-between" }}>
              <div>
                <div style={{ fontFamily: "'Cormorant Garamond',serif", fontSize: 18, fontWeight: 700 }}>Session History</div>
                <div style={{ fontSize: 11, color: "#5A5248", marginTop: 2 }}>{chatHistory.length} saved sessions</div>
              </div>
              <button onClick={() => setShowHistory(false)} style={{ background: "none", border: "none", color: "#5A5248", cursor: "pointer", fontSize: 18, lineHeight: 1 }}>×</button>
            </div>
            <div style={{ padding: "12px 16px", borderBottom: "1px solid rgba(255,255,255,0.04)" }}>
              <input value={historyFilter} onChange={e => setHistoryFilter(e.target.value)} placeholder="Search sessions..."
                style={{ width: "100%", padding: "9px 14px", background: "rgba(255,255,255,0.04)", border: "1px solid rgba(212,175,106,0.15)", borderRadius: 6, color: "#EDE8DF", fontSize: 13, outline: "none", boxSizing: "border-box", fontFamily: "'DM Sans',sans-serif" }} />
            </div>
            <div style={{ flex: 1, overflowY: "auto", padding: "12px" }}>
              {chatHistory.length === 0 ? (
                <div style={{ textAlign: "center", color: "#3A3530", fontSize: 13, marginTop: 40 }}>No saved sessions yet.</div>
              ) : (
                chatHistory.filter(s => !historyFilter || s.label.toLowerCase().includes(historyFilter.toLowerCase())).map(session => (
                  <div key={session.id} style={{ padding: "14px", borderRadius: 8, border: "1px solid rgba(212,175,106,0.1)", background: "rgba(255,255,255,0.02)", marginBottom: 8, cursor: "pointer" }}
                    onClick={() => loadSession(session)}>
                    <div style={{ fontSize: 13, color: "#C8C0B4", marginBottom: 4, lineHeight: 1.4 }}>{session.label}</div>
                    <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                      <div style={{ fontSize: 11, color: "#3A3530" }}>{session.date} · {session.messages.length} messages</div>
                      <button onClick={e => { e.stopPropagation(); deleteSession(session.id); }} style={{ background: "none", border: "none", color: "#3A3530", cursor: "pointer", fontSize: 11, padding: "2px 6px" }}>Delete</button>
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>
        </div>
      )}

      {/* Header */}
      <div style={{ padding: isMobile ? "14px 16px" : "18px 32px", borderBottom: "1px solid rgba(212,175,106,0.1)", display: "flex", alignItems: "center", justifyContent: "space-between", background: "rgba(8,8,8,0.95)", position: "sticky", top: 0, zIndex: 50 }}>
        <div style={{ display: "flex", alignItems: "center", gap: isMobile ? 8 : 14 }}>
          <div style={{ width: isMobile ? 28 : 34, height: isMobile ? 28 : 34, border: "1.5px solid #D4AF6A", borderRadius: 6, display: "flex", alignItems: "center", justifyContent: "center", fontSize: isMobile ? 12 : 14, color: "#D4AF6A", fontFamily: "'Cormorant Garamond',serif", fontWeight: 700 }}>R</div>
          <div>
            <div style={{ fontFamily: "'Cormorant Garamond',serif", fontSize: isMobile ? 13 : 16, fontWeight: 700, letterSpacing: 2 }}>RAVLO <span style={{ color: "#D4AF6A" }}>Academy</span></div>
            {!isMobile && <div style={{ fontSize: 9, letterSpacing: 3, color: "#5A5248", textTransform: "uppercase" }}>AI Coaching Platform</div>}
          </div>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: isMobile ? 8 : 16 }}>
          <span style={{ fontSize: isMobile ? 9 : 11, color: t.color, padding: "3px 8px", borderRadius: 20, border: `1px solid ${t.border}`, background: t.bg, letterSpacing: 1, fontWeight: 600 }}>{t.badge}</span>
          {!isMobile && <span style={{ fontSize: 13, color: "#7A7268" }}>{userName}</span>}
          <button onClick={() => setShowHistory(true)} style={{ background: "none", border: "1px solid rgba(212,175,106,0.15)", borderRadius: 6, color: "#7A7268", cursor: "pointer", fontSize: isMobile ? 11 : 12, padding: "5px 10px", fontFamily: "'DM Sans',sans-serif" }}>History</button>
          <button onClick={() => setScreen("landing")} style={{ background: "none", border: "none", color: "#3A3530", cursor: "pointer", fontSize: 12, fontFamily: "'DM Sans',sans-serif" }}>Out</button>
        </div>
      </div>

      <div style={{ maxWidth: 1100, margin: "0 auto", padding: isMobile ? "24px 16px" : "40px 32px" }}>
        {/* Welcome */}
        <div style={{ marginBottom: isMobile ? 32 : 48 }}>
          <div style={{ fontSize: 10, letterSpacing: 4, color: "#5A5248", textTransform: "uppercase", marginBottom: 8 }}>Welcome back</div>
          <h2 style={{ fontFamily: "'Cormorant Garamond',serif", fontSize: isMobile ? 32 : 44, fontWeight: 300, margin: "0 0 4px" }}>
            Hello, <strong style={{ fontWeight: 700, color: "#D4AF6A" }}>{userName}</strong>
          </h2>
          <p style={{ color: "#5A5248", fontSize: 13, margin: 0 }}>What are we mastering today?</p>
        </div>

        {/* Action cards */}
        <div style={{ display: "grid", gridTemplateColumns: isMobile ? "1fr 1fr" : "repeat(4,1fr)", gap: isMobile ? 10 : 16, marginBottom: isMobile ? 32 : 48 }}>
          {[
            { icon: "🤖", label: "AI Coach", desc: "One-on-one session", color: "#D4AF6A", action: () => startCoach() },
            { icon: "📋", label: "My Plan", desc: "90-day success plan", color: "#6AD4A0", action: startPlan },
            { icon: "📚", label: "Modules", desc: `${availableModules.length} available`, color: "#6AB4D4", action: () => document.getElementById("modules")?.scrollIntoView({ behavior: "smooth" }) },
            { icon: "🔗", label: "Refer a Colleague", desc: "Copy your Academy link", color: "#B06AD4", action: copyReferralLink },
          ].map(card => (
            <button key={card.label} onClick={card.action} style={{ padding: isMobile ? "16px 12px" : "24px", borderRadius: 12, border: `1px solid ${card.color}30`, background: `${card.color}08`, cursor: "pointer", textAlign: "left", transition: "all 0.2s", fontFamily: "'DM Sans',sans-serif" }}
              onMouseEnter={e => { e.currentTarget.style.border = `1px solid ${card.color}60`; e.currentTarget.style.background = `${card.color}12`; e.currentTarget.style.transform = "translateY(-2px)"; }}
              onMouseLeave={e => { e.currentTarget.style.border = `1px solid ${card.color}30`; e.currentTarget.style.background = `${card.color}08`; e.currentTarget.style.transform = "translateY(0)"; }}>
              <div style={{ fontSize: isMobile ? 22 : 28, marginBottom: 10 }}>{card.icon}</div>
              <div style={{ fontFamily: "'Cormorant Garamond',serif", fontSize: isMobile ? 15 : 18, fontWeight: 700, color: "#EDE8DF", marginBottom: 3 }}>{card.label}</div>
              <div style={{ fontSize: isMobile ? 10 : 12, color: "#5A5248" }}>{card.desc}</div>
            </button>
          ))}
        </div>

        {/* Quick prompts */}
        <div style={{ marginBottom: isMobile ? 32 : 48 }}>
          <div style={{ fontSize: 10, letterSpacing: 3, color: "#5A5248", textTransform: "uppercase", marginBottom: 14 }}>Quick Coaching Topics</div>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
            {[
              "Explain cap rates with real examples",
              "How do I build a sphere of influence system?",
              "Walk me through SBA 504 vs 7(a)",
              "Best lead gen strategies for 2026",
              "How to analyze a multifamily deal",
              "Explain DSCR underwriting",
              ...(tier === "lending" ? [
                "Walk me through conventional vs FHA vs VA guidelines",
                "Explain rate lock strategies for this market",
                "How do ARMs and buydowns work?",
                "Walk me through the loan processing workflow",
              ] : [
                "How do I get my first commercial listing?",
                "Build me a 30-day prospecting plan",
              ]),
            ].map(q => (
              <button key={q} onClick={() => startCoach(q)} style={{ padding: "8px 14px", borderRadius: 20, border: "1px solid rgba(212,175,106,0.15)", background: "rgba(212,175,106,0.05)", color: "#7A7268", fontSize: isMobile ? 11 : 12, cursor: "pointer", transition: "all 0.2s", fontFamily: "'DM Sans',sans-serif" }}
                onMouseEnter={e => { e.target.style.borderColor = "#D4AF6A"; e.target.style.color = "#D4AF6A"; }}
                onMouseLeave={e => { e.target.style.borderColor = "rgba(212,175,106,0.15)"; e.target.style.color = "#7A7268"; }}>
                {q}
              </button>
            ))}
          </div>
        </div>

        {/* Modules */}
        <div id="modules">
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 18 }}>
            <div style={{ fontSize: 10, letterSpacing: 3, color: "#5A5248", textTransform: "uppercase" }}>Your Modules</div>
            <div style={{ fontSize: 11, color: "#3A3530" }}>{availableModules.length} of {MODULES.length} unlocked</div>
          </div>
          <div style={{ display: "grid", gridTemplateColumns: isMobile ? "1fr" : "repeat(auto-fill,minmax(280px,1fr))", gap: 12 }}>
            {MODULES.map(mod => {
              const locked = !mod.tier.includes(tier);
              const prog = getModuleProgress(mod.id);
              return (
                <div key={mod.id} onClick={() => { if (!locked) { setActiveModule(mod); setScreen("module"); } else notify("Upgrade your plan to unlock this module."); }}
                  style={{ padding: "22px", borderRadius: 12, border: locked ? "1px solid rgba(255,255,255,0.04)" : `1px solid ${mod.color}25`, background: locked ? "rgba(255,255,255,0.02)" : `${mod.color}08`, cursor: locked ? "not-allowed" : "pointer", transition: "all 0.2s", opacity: locked ? 0.4 : 1, position: "relative" }}
                  onMouseEnter={e => { if (!locked) { e.currentTarget.style.border = `1px solid ${mod.color}50`; e.currentTarget.style.transform = "translateY(-2px)"; } }}
                  onMouseLeave={e => { if (!locked) { e.currentTarget.style.border = `1px solid ${mod.color}25`; e.currentTarget.style.transform = "translateY(0)"; } }}>
                  {locked && <div style={{ position: "absolute", top: 14, right: 14, fontSize: 12, color: "#3A3530" }}>🔒</div>}
                  <div style={{ fontSize: 26, marginBottom: 10 }}>{mod.icon}</div>
                  <div style={{ fontFamily: "'Cormorant Garamond',serif", fontSize: 17, fontWeight: 700, color: "#EDE8DF", marginBottom: 5 }}>{mod.title}</div>
                  <div style={{ fontSize: 11, color: "#5A5248", marginBottom: 14, lineHeight: 1.5 }}>{mod.desc}</div>

                  {/* Progress bar */}
                  {!locked && (
                    <div>
                      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 6 }}>
                        <div style={{ fontSize: 10, color: "#5A5248" }}>{prog.completed}/{prog.total} lessons</div>
                        {prog.pct === 100 && <div style={{ fontSize: 10, color: mod.color, fontWeight: 600 }}>Complete ✓</div>}
                      </div>
                      <div style={{ height: 3, borderRadius: 2, background: "rgba(255,255,255,0.06)", overflow: "hidden" }}>
                        <div style={{ height: "100%", width: `${prog.pct}%`, background: mod.color, borderRadius: 2, transition: "width 0.4s ease" }} />
                      </div>
                    </div>
                  )}
                  {locked && <div style={{ fontSize: 11, color: mod.color }}>{mod.lessons.length} lessons</div>}
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );

  // ── MODULE VIEW ───────────────────────────────────────────────────────────
  if (screen === "module" && activeModule) {
    const prog = getModuleProgress(activeModule.id);
    const modProgress = progress[activeModule.id] || [];
    return (
      <div style={{ ...S.page }}>
        <div style={{ padding: isMobile ? "14px 16px" : "18px 32px", borderBottom: "1px solid rgba(212,175,106,0.1)", display: "flex", alignItems: "center", gap: 14, background: "rgba(8,8,8,0.95)", position: "sticky", top: 0, zIndex: 50 }}>
          <button onClick={() => setScreen("dashboard")} style={{ background: "none", border: "none", color: "#5A5248", cursor: "pointer", fontSize: 13, fontFamily: "'DM Sans',sans-serif", flexShrink: 0 }}>← Dashboard</button>
          <div style={{ width: 1, height: 18, background: "rgba(255,255,255,0.06)", flexShrink: 0 }} />
          <span style={{ fontSize: 18 }}>{activeModule.icon}</span>
          <span style={{ fontFamily: "'Cormorant Garamond',serif", fontSize: isMobile ? 15 : 18, fontWeight: 700, flex: 1, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{activeModule.title}</span>
          <div style={{ fontSize: 11, color: activeModule.color, flexShrink: 0 }}>{prog.completed}/{prog.total}</div>
        </div>

        {/* Module progress bar */}
        <div style={{ height: 3, background: "rgba(255,255,255,0.04)" }}>
          <div style={{ height: "100%", width: `${prog.pct}%`, background: activeModule.color, transition: "width 0.4s ease" }} />
        </div>

        <div style={{ maxWidth: 900, margin: "0 auto", padding: isMobile ? "28px 16px" : "48px 32px" }}>
          <div style={{ marginBottom: 36 }}>
            <div style={{ fontSize: 12, color: activeModule.color, letterSpacing: 2, textTransform: "uppercase", marginBottom: 10, fontWeight: 600 }}>Module Overview</div>
            <h2 style={{ fontFamily: "'Cormorant Garamond',serif", fontSize: isMobile ? 28 : 40, fontWeight: 300, margin: "0 0 12px" }}>{activeModule.title}</h2>
            <p style={{ color: "#7A7268", fontSize: 14, lineHeight: 1.7, maxWidth: 600 }}>{activeModule.desc}</p>
          </div>

          <div style={{ display: "grid", gridTemplateColumns: isMobile ? "1fr" : "1fr 1fr", gap: 10, marginBottom: 36 }}>
            {activeModule.lessons.map((lesson, i) => {
              const done = !!modProgress[i];
              return (
                <div key={lesson} style={{ display: "flex", alignItems: "center", gap: 10, padding: "14px 16px", borderRadius: 10, border: `1px solid ${done ? activeModule.color + "50" : activeModule.color + "20"}`, background: done ? `${activeModule.color}10` : `${activeModule.color}06`, transition: "all 0.2s" }}>
                  {/* Checkmark button */}
                  <button onClick={e => { e.stopPropagation(); toggleLesson(activeModule.id, i); }}
                    style={{ width: 26, height: 26, borderRadius: 6, border: `1.5px solid ${done ? activeModule.color : activeModule.color + "50"}`, background: done ? activeModule.color : "transparent", display: "flex", alignItems: "center", justifyContent: "center", cursor: "pointer", flexShrink: 0, transition: "all 0.2s" }}>
                    {done && <span style={{ color: "#080808", fontSize: 12, fontWeight: 700 }}>✓</span>}
                  </button>
                  {/* Lesson number */}
                  <span style={{ width: 22, height: 22, borderRadius: 5, background: `${activeModule.color}20`, display: "flex", alignItems: "center", justifyContent: "center", fontSize: 11, color: activeModule.color, fontWeight: 700, flexShrink: 0 }}>{i + 1}</span>
                  {/* Lesson name — click to open in coach */}
                  <button onClick={() => startCoach(`Teach me about: "${lesson}" from the ${activeModule.title} module. Start with the key concepts, then give me real-world examples and actionable steps I can use immediately.`)}
                    style={{ flex: 1, background: "none", border: "none", textAlign: "left", color: done ? activeModule.color : "#C8C0B4", fontSize: 13, fontWeight: done ? 600 : 500, cursor: "pointer", fontFamily: "'DM Sans',sans-serif", textDecoration: done ? "line-through" : "none", opacity: done ? 0.7 : 1 }}>
                    {lesson}
                  </button>
                  <span style={{ color: activeModule.color, fontSize: 11, flexShrink: 0 }}>→</span>
                </div>
              );
            })}
          </div>

          <button onClick={() => startCoach(`Give me a comprehensive overview of the entire ${activeModule.title} module. Cover all key concepts, how they connect, and what I should focus on mastering first based on my profile as a ${ACCESS_TIERS[tier]?.description}.`)}
            style={{ padding: "15px 28px", borderRadius: 8, border: `1px solid ${activeModule.color}40`, background: `${activeModule.color}12`, color: activeModule.color, fontSize: 14, fontWeight: 600, cursor: "pointer", fontFamily: "'DM Sans',sans-serif" }}>
            🤖 AI Overview of Entire Module →
          </button>
        </div>
      </div>
    );
  }

  // ── COACH / CHAT ──────────────────────────────────────────────────────────
  if (screen === "coach") return (
    <div style={{ height: "100svh", display: "flex", flexDirection: "column", background: "#080808", fontFamily: "'DM Sans',sans-serif", color: "#EDE8DF" }}>

      {notification && <div style={{ position: "fixed", top: 20, right: 20, padding: "12px 20px", borderRadius: 8, background: "rgba(212,175,106,0.15)", border: "1px solid rgba(212,175,106,0.3)", color: "#D4AF6A", fontSize: 13, zIndex: 200, fontFamily: "'DM Sans',sans-serif" }}>{notification}</div>}

      <div style={{ padding: isMobile ? "12px 16px" : "16px 28px", borderBottom: "1px solid rgba(212,175,106,0.1)", display: "flex", alignItems: "center", justifyContent: "space-between", background: "rgba(8,8,8,0.95)", flexShrink: 0 }}>
        <div style={{ display: "flex", alignItems: "center", gap: isMobile ? 8 : 14 }}>
          <button onClick={() => { if (activeModule) setScreen("module"); else setScreen("dashboard"); }} style={{ background: "none", border: "none", color: "#5A5248", cursor: "pointer", fontSize: 13, fontFamily: "'DM Sans',sans-serif", flexShrink: 0 }}>← {isMobile ? "" : "Back"}</button>
          <div style={{ width: 1, height: 18, background: "rgba(255,255,255,0.06)", flexShrink: 0 }} />
          <div style={{ width: isMobile ? 28 : 32, height: isMobile ? 28 : 32, borderRadius: "50%", background: "linear-gradient(135deg,#D4AF6A,#8A6A2A)", display: "flex", alignItems: "center", justifyContent: "center", fontSize: isMobile ? 11 : 13, fontWeight: 700, color: "#080808", flexShrink: 0 }}>AI</div>
          {!isMobile && (
            <div>
              <div style={{ fontFamily: "'Cormorant Garamond',serif", fontSize: 16, fontWeight: 700 }}>RealEdge AI Coach</div>
              <div style={{ fontSize: 10, color: "#5A5248", letterSpacing: 1 }}>COACHING SESSION</div>
            </div>
          )}
        </div>
        <div style={{ display: "flex", gap: 8 }}>
          <button onClick={saveCurrentSession} style={{ padding: isMobile ? "6px 10px" : "7px 14px", borderRadius: 6, border: "1px solid rgba(212,175,106,0.2)", background: "rgba(212,175,106,0.06)", color: "#D4AF6A", fontSize: isMobile ? 10 : 11, fontWeight: 600, cursor: "pointer", fontFamily: "'DM Sans',sans-serif" }}>
            Save
          </button>
          <button onClick={() => { setMessages([]); startCoach(); }} style={{ padding: isMobile ? "6px 10px" : "7px 14px", borderRadius: 6, border: "1px solid rgba(255,255,255,0.06)", background: "rgba(255,255,255,0.02)", color: "#5A5248", fontSize: isMobile ? 10 : 11, cursor: "pointer", fontFamily: "'DM Sans',sans-serif" }}>
            + New
          </button>
          <button onClick={() => { setShowHistory(true); setScreen("dashboard"); }} style={{ padding: isMobile ? "6px 10px" : "7px 14px", borderRadius: 6, border: "1px solid rgba(255,255,255,0.06)", background: "rgba(255,255,255,0.02)", color: "#5A5248", fontSize: isMobile ? 10 : 11, cursor: "pointer", fontFamily: "'DM Sans',sans-serif" }}>
            History
          </button>
        </div>
      </div>

      <div style={{ flex: 1, overflowY: "auto", padding: isMobile ? "16px" : "28px", display: "flex", flexDirection: "column", gap: 18 }}>
        {messages.length === 0 && (
          <div style={{ textAlign: "center", margin: "auto", color: "#3A3530", fontSize: 13 }}>
            <div style={{ fontSize: 32, marginBottom: 12 }}>🤖</div>
            <div>Ready when you are, {userName}.</div>
          </div>
        )}
        {messages.map((msg, i) => (
          <div key={i} style={{ display: "flex", justifyContent: msg.role === "user" ? "flex-end" : "flex-start", gap: 10, alignItems: "flex-start" }}>
            {msg.role === "assistant" && (
              <div style={{ width: isMobile ? 26 : 30, height: isMobile ? 26 : 30, borderRadius: "50%", background: "linear-gradient(135deg,#D4AF6A,#8A6A2A)", display: "flex", alignItems: "center", justifyContent: "center", fontSize: isMobile ? 10 : 11, fontWeight: 700, color: "#080808", flexShrink: 0, marginTop: 2 }}>AI</div>
            )}
            <div style={{ maxWidth: isMobile ? "90%" : "76%", padding: msg.role === "user" ? "12px 16px" : "18px 22px", borderRadius: msg.role === "user" ? "18px 18px 4px 18px" : "18px 18px 18px 4px", background: msg.role === "user" ? "linear-gradient(135deg,#D4AF6A,#9A7A3A)" : "rgba(255,255,255,0.04)", border: msg.role === "assistant" ? "1px solid rgba(212,175,106,0.1)" : "none", color: msg.role === "user" ? "#080808" : "#C8C0B4", fontSize: isMobile ? 13 : 14, lineHeight: 1.75 }}>
              {msg.role === "user" ? <span style={{ fontWeight: 500 }}>{msg.content}</span> : <span dangerouslySetInnerHTML={{ __html: fmt(msg.content) }} />}
            </div>
          </div>
        ))}
        {loading && (
          <div style={{ display: "flex", gap: 10, alignItems: "flex-start" }}>
            <div style={{ width: 30, height: 30, borderRadius: "50%", background: "linear-gradient(135deg,#D4AF6A,#8A6A2A)", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 11, fontWeight: 700, color: "#080808" }}>AI</div>
            <div style={{ padding: "16px 20px", borderRadius: "18px 18px 18px 4px", background: "rgba(255,255,255,0.04)", border: "1px solid rgba(212,175,106,0.1)", display: "flex", gap: 5, alignItems: "center" }}>
              {[0, 1, 2].map(i => <div key={i} style={{ width: 6, height: 6, borderRadius: "50%", background: "#D4AF6A", opacity: 0.6, animation: "dot 1.2s ease-in-out infinite", animationDelay: `${i * 0.2}s` }} />)}
            </div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Quick prompts — lending-aware */}
      {messages.length <= 1 && (
        <div style={{ padding: "8px 16px 0", display: "flex", gap: 6, overflowX: "auto", flexShrink: 0 }}>
          {(tier === "lending"
            ? ["Explain DSCR underwriting", "Walk me through conventional vs FHA vs VA", "How do rate locks work?", "Build me a production plan"]
            : ["Help me close more deals", "Build my 30-day prospecting plan", "Analyze this deal with me", "Create my success plan"]
          ).map(q => (
            <button key={q} onClick={() => sendMessage(q)} style={{ padding: "5px 12px", borderRadius: 16, border: "1px solid rgba(212,175,106,0.12)", background: "transparent", color: "#5A5248", fontSize: 11, cursor: "pointer", whiteSpace: "nowrap", fontFamily: "'DM Sans',sans-serif", transition: "all 0.2s" }}
              onMouseEnter={e => { e.target.style.color = "#D4AF6A"; e.target.style.borderColor = "rgba(212,175,106,0.3)"; }}
              onMouseLeave={e => { e.target.style.color = "#5A5248"; e.target.style.borderColor = "rgba(212,175,106,0.12)"; }}>
              {q}
            </button>
          ))}
        </div>
      )}

      <div style={{ padding: isMobile ? "12px 14px" : "16px 28px", borderTop: "1px solid rgba(212,175,106,0.08)", background: "rgba(8,8,8,0.95)", flexShrink: 0 }}>
        <div style={{ display: "flex", gap: 10, alignItems: "flex-end" }}>
          <textarea ref={inputRef} value={chatInput} onChange={e => setChatInput(e.target.value)}
            onKeyDown={e => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); sendMessage(); } }}
            placeholder="Ask your coach anything..." rows={1}
            style={{ flex: 1, padding: "13px 16px", background: "rgba(255,255,255,0.04)", border: "1px solid rgba(212,175,106,0.15)", borderRadius: 12, color: "#EDE8DF", fontSize: 14, outline: "none", resize: "none", lineHeight: 1.5, fontFamily: "'DM Sans',sans-serif", maxHeight: 120 }} />
          <button onClick={() => sendMessage()} disabled={!chatInput.trim() || loading}
            style={{ width: isMobile ? 40 : 46, height: isMobile ? 40 : 46, borderRadius: 10, border: "none", background: chatInput.trim() && !loading ? "linear-gradient(135deg,#D4AF6A,#9A7A3A)" : "rgba(255,255,255,0.05)", color: chatInput.trim() && !loading ? "#080808" : "#3A3530", fontSize: 18, cursor: chatInput.trim() && !loading ? "pointer" : "not-allowed", flexShrink: 0, display: "flex", alignItems: "center", justifyContent: "center", transition: "all 0.2s" }}>↑</button>
        </div>
        {!isMobile && <div style={{ fontSize: 10, color: "#2A2520", textAlign: "center", marginTop: 8, letterSpacing: 1 }}>ENTER TO SEND · SHIFT+ENTER FOR NEW LINE</div>}
      </div>
      <style>{`@keyframes dot{0%,100%{transform:scale(0.7);opacity:0.3}50%{transform:scale(1.2);opacity:1}} textarea{overflow:hidden} ::-webkit-scrollbar{width:3px} ::-webkit-scrollbar-thumb{background:rgba(212,175,106,0.15);border-radius:3px}`}</style>
    </div>
  );

  return null;
}

// ── Mount ─────────────────────────────────────────────────────────────────────
(function () {
  var container = document.getElementById("ravlo-university-root");
  if (container) ReactDOM.createRoot(container).render(React.createElement(RavloAcademy));
})();
