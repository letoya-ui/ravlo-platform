// ─── Ravlo Academy — School Structure Build ──────────────────────────────
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
    perks: ["Unlimited AI Coaching", "All Courses", "1-on-1 Success Plans", "Priority Support", "Investor Briefings"],
    accessCode: "RAVLO-ELITE", monthly: 0, badge_text: "Complimentary",
  },
  lending: {
    label: "Lending Team", badge: "TEAM", color: "#6AB4D4",
    bg: "rgba(106,180,212,0.12)", border: "rgba(106,180,212,0.4)", icon: "◈",
    description: "Ravlo Lending Staff",
    perks: ["Unlimited AI Coaching", "Loan Courses", "Commercial Training", "Team Dashboard", "Deal Review"],
    accessCode: "RAVLO-LENDING", monthly: 0, badge_text: "Employment Benefit",
  },
  pro: {
    label: "Pro", badge: "PRO", color: "#B06AD4",
    bg: "rgba(176,106,212,0.12)", border: "rgba(176,106,212,0.4)", icon: "●",
    description: "Independent Realtors & Investors",
    perks: ["Unlimited AI Coaching", "All Courses", "Success Plans", "Community Access"],
    monthly: 97, badge_text: "$97 / month",
  },
  starter: {
    label: "Starter", badge: "START", color: "#6AD4A0",
    bg: "rgba(106,212,160,0.12)", border: "rgba(106,212,160,0.4)", icon: "○",
    description: "New to Real Estate",
    perks: ["Core AI Coaching", "Foundational Courses", "Basic Success Plan"],
    monthly: 47, badge_text: "$47 / month",
  },
};

const CODE_MAP = {
  "RAVLO-ELITE": "elite",
  "RAVLO-LENDING": "lending",
};

// ─── XP & LEVELS ─────────────────────────────────────────────────────────────

const XP_PER_LESSON = 10;
const XP_PER_QUIZ_PASS = 25;
const XP_PER_COURSE = 100;

const LEVELS = [
  { name: "Scholar", minXP: 0, icon: "📖" },
  { name: "Associate", minXP: 100, icon: "📘" },
  { name: "Professional", minXP: 300, icon: "🎓" },
  { name: "Expert", minXP: 600, icon: "🏆" },
  { name: "Master", minXP: 1000, icon: "👑" },
];

function getLevel(xp) {
  for (let i = LEVELS.length - 1; i >= 0; i--) {
    if (xp >= LEVELS[i].minXP) return { ...LEVELS[i], index: i };
  }
  return { ...LEVELS[0], index: 0 };
}

function getNextLevel(xp) {
  const current = getLevel(xp);
  if (current.index >= LEVELS.length - 1) return null;
  return LEVELS[current.index + 1];
}

// ─── CURRICULUM: Departments → Courses → Units → Lessons ──────────────────

const CURRICULUM = [
  {
    id: "fundamentals",
    name: "Real Estate Fundamentals",
    icon: "🏛️",
    color: "#D4AF6A",
    description: "Core knowledge every real estate professional needs.",
    courses: [
      {
        id: "residential",
        title: "Residential Mastery",
        icon: "🏠",
        color: "#D4AF6A",
        credits: 3,
        prerequisites: [],
        tier: ["starter", "pro", "elite", "lending"],
        desc: "Master the full residential transaction from lead to close.",
        units: [
          {
            id: "res-u1",
            title: "Listings & Pricing Strategy",
            lessons: [
              { id: "res-l1", title: "Listing Strategy & Pricing", duration: "15 min", description: "How to price homes competitively using CMAs and market data." },
              { id: "res-l2", title: "CMA Deep Dive", duration: "20 min", description: "Building bulletproof comparative market analyses that win listings." },
              { id: "res-l3", title: "Open House Optimization", duration: "12 min", description: "Convert open house visitors into buyers and listing leads." },
            ],
            quiz: [
              { q: "What is the primary purpose of a CMA?", options: ["Determine tax value", "Estimate market value for pricing", "Calculate mortgage payments", "Assess insurance costs"], correct: 1 },
              { q: "Which factor is MOST important when selecting comparables?", options: ["Paint color", "Proximity and recency of sale", "Number of bathrooms only", "Seller motivation"], correct: 1 },
              { q: "What is the ideal pricing strategy in a competitive market?", options: ["Price 20% above market", "Price at or slightly below market value", "Always price at the Zestimate", "Price based on what the seller owes"], correct: 1 },
            ],
          },
          {
            id: "res-u2",
            title: "Buyer Representation & Negotiation",
            lessons: [
              { id: "res-l4", title: "Buyer Representation", duration: "18 min", description: "Fiduciary duties, buyer agency agreements, and client advocacy." },
              { id: "res-l5", title: "Negotiation Frameworks", duration: "22 min", description: "Win-win negotiation strategies for offers, counteroffers, and repairs." },
            ],
            quiz: [
              { q: "What is a fiduciary duty?", options: ["A marketing obligation", "A legal duty to act in the client's best interest", "A requirement to sell at listing price", "A tax obligation"], correct: 1 },
              { q: "Which negotiation approach typically yields the best results?", options: ["Hardball tactics always", "Win-win collaborative strategy", "Always accept the first offer", "Ignore the other party's needs"], correct: 1 },
              { q: "When should you recommend a buyer walk away?", options: ["Never — always close", "When inspection reveals major undisclosed issues", "When the home is more than 1% over budget", "Only if the seller is rude"], correct: 1 },
            ],
          },
          {
            id: "res-u3",
            title: "Lead Systems & Conversion",
            lessons: [
              { id: "res-l6", title: "Lead Conversion Systems", duration: "16 min", description: "Turn inquiries into appointments with proven follow-up scripts." },
            ],
            quiz: [
              { q: "What is the ideal follow-up time for a new lead?", options: ["Within 24 hours", "Within 5 minutes", "Within a week", "Whenever convenient"], correct: 1 },
              { q: "What is the average number of touchpoints needed to convert a lead?", options: ["1-2", "3-4", "5-12", "20+"], correct: 2 },
            ],
          },
        ],
      },
      {
        id: "commercial",
        title: "Commercial Real Estate",
        icon: "🏢",
        color: "#6AB4D4",
        credits: 4,
        prerequisites: [],
        tier: ["pro", "elite", "lending"],
        desc: "Advanced commercial strategies for office, retail, and industrial.",
        units: [
          {
            id: "com-u1",
            title: "Commercial Fundamentals",
            lessons: [
              { id: "com-l1", title: "Office & Retail Leasing", duration: "20 min", description: "Lease structures, NNN vs gross, tenant improvements, and LOIs." },
              { id: "com-l2", title: "Cap Rate & NOI Analysis", duration: "25 min", description: "How to calculate and interpret capitalization rates and net operating income." },
            ],
            quiz: [
              { q: "What does NNN stand for in a lease?", options: ["Net Net Net (triple net)", "No Negotiation Necessary", "New Notional Net", "Nine-month Neutral Net"], correct: 0 },
              { q: "How is Cap Rate calculated?", options: ["Sale Price / Rent", "NOI / Purchase Price", "Gross Income / Expenses", "Mortgage / Down Payment"], correct: 1 },
              { q: "A lower cap rate generally indicates:", options: ["Higher risk, lower price", "Lower risk, higher price", "No investment value", "A distressed property"], correct: 1 },
            ],
          },
          {
            id: "com-u2",
            title: "Investment Sales & Exchanges",
            lessons: [
              { id: "com-l3", title: "Investment Sales", duration: "18 min", description: "Positioning and marketing commercial properties for maximum value." },
              { id: "com-l4", title: "1031 Exchanges", duration: "22 min", description: "Tax-deferred exchanges: timelines, rules, and strategies." },
            ],
            quiz: [
              { q: "What is the identification period for a 1031 exchange?", options: ["30 days", "45 days", "90 days", "180 days"], correct: 1 },
              { q: "Can you do a 1031 exchange on a primary residence?", options: ["Yes, always", "No — only investment/business property qualifies", "Yes, but only if owned 5+ years", "Only if the home is over $1M"], correct: 1 },
            ],
          },
          {
            id: "com-u3",
            title: "Representation & Market Analysis",
            lessons: [
              { id: "com-l5", title: "Tenant & Landlord Representation", duration: "16 min", description: "Dual-sided commercial representation and conflict management." },
              { id: "com-l6", title: "Market Analysis", duration: "20 min", description: "Vacancy rates, absorption, rent comps, and market cycle positioning." },
            ],
            quiz: [
              { q: "What is absorption rate in commercial real estate?", options: ["Rate of property depreciation", "Rate at which available space is leased over time", "Percentage of tenants leaving", "Cost of tenant improvements"], correct: 1 },
              { q: "Which metric best indicates market health?", options: ["Building age", "Vacancy rate trends", "Number of brokers", "Property color"], correct: 1 },
            ],
          },
        ],
      },
    ],
  },
  {
    id: "finance",
    name: "Finance & Lending",
    icon: "💰",
    color: "#6AD4A0",
    description: "Complete loan structuring and underwriting knowledge.",
    courses: [
      {
        id: "loans",
        title: "Mortgage & Lending",
        icon: "💰",
        color: "#6AD4A0",
        credits: 5,
        prerequisites: [],
        tier: ["pro", "elite", "lending"],
        desc: "Complete loan structuring from application to close — residential, commercial, and beyond.",
        units: [
          {
            id: "loan-u1",
            title: "Government & Conventional Programs",
            lessons: [
              { id: "loan-l1", title: "Conventional, FHA & VA Loans", duration: "25 min", description: "Guidelines, limits, and use cases for the three main residential loan programs." },
              { id: "loan-l2", title: "SBA 7(a) & 504 Programs", duration: "20 min", description: "Small business lending for commercial real estate acquisition." },
            ],
            quiz: [
              { q: "What is the minimum down payment for a conventional loan?", options: ["0%", "3%", "10%", "20%"], correct: 1 },
              { q: "Which loan type requires no down payment for eligible veterans?", options: ["FHA", "Conventional", "VA", "SBA 504"], correct: 2 },
              { q: "SBA 504 loans are primarily used for:", options: ["Residential mortgages", "Fixed-asset acquisition (real estate/equipment)", "Credit card debt", "Auto loans"], correct: 1 },
            ],
          },
          {
            id: "loan-u2",
            title: "Commercial & Alternative Lending",
            lessons: [
              { id: "loan-l3", title: "CMBS & Bridge Loans", duration: "22 min", description: "Securitized lending and short-term bridge financing for commercial deals." },
              { id: "loan-l4", title: "Hard Money & Private Lending", duration: "18 min", description: "Asset-based lending, terms, and when to use private capital." },
            ],
            quiz: [
              { q: "What does CMBS stand for?", options: ["Commercial Mortgage-Backed Securities", "Central Mortgage Banking System", "Certified Mortgage Broker Standards", "Commercial Money Borrowing Service"], correct: 0 },
              { q: "Bridge loans are typically:", options: ["30-year fixed rate", "Short-term (6-36 months)", "Government-backed", "Only for residential"], correct: 1 },
              { q: "Hard money lenders primarily evaluate:", options: ["Borrower credit score only", "The property/asset value", "Employment history", "Social media presence"], correct: 1 },
            ],
          },
          {
            id: "loan-u3",
            title: "Underwriting & Ratios",
            lessons: [
              { id: "loan-l5", title: "DSCR & Underwriting", duration: "25 min", description: "Debt service coverage ratios and how lenders evaluate deal viability." },
              { id: "loan-l6", title: "LTV / LTC Ratios", duration: "15 min", description: "Loan-to-value and loan-to-cost calculations for investment properties." },
              { id: "loan-l7", title: "Borrower Qualification Framework", duration: "20 min", description: "Income, assets, credit — the full borrower qualification picture." },
            ],
            quiz: [
              { q: "A DSCR of 1.25 means:", options: ["The property loses money", "Income is 25% more than debt payments", "The loan is 25% paid off", "The cap rate is 1.25%"], correct: 1 },
              { q: "LTV stands for:", options: ["Loan-to-Value", "Long-term Verification", "Lender Tax Valuation", "Leverage Through Volume"], correct: 0 },
              { q: "What DSCR do most lenders require as a minimum?", options: ["0.50", "0.75", "1.00", "1.20-1.25"], correct: 3 },
            ],
          },
          {
            id: "loan-u4",
            title: "Rates, Processing & Pipeline",
            lessons: [
              { id: "loan-l8", title: "Rate Locks & Assumptions", duration: "15 min", description: "When and how to lock rates, and assumable mortgage strategies." },
              { id: "loan-l9", title: "Adjustable Rate Mortgages & Buydowns", duration: "18 min", description: "ARM structures, rate caps, and temporary/permanent buydowns." },
              { id: "loan-l10", title: "Loan Processing Workflows", duration: "20 min", description: "From application to closing — the processor's complete checklist." },
            ],
            quiz: [
              { q: "A rate lock protects the borrower from:", options: ["Property value changes", "Interest rate increases during processing", "Appraisal fees", "Closing delays"], correct: 1 },
              { q: "What does a 2-1 buydown mean?", options: ["2% down payment, 1% closing costs", "Rate is 2% lower year 1, 1% lower year 2, then full rate", "2 loans combined into 1", "1 buyer, 2 properties"], correct: 1 },
            ],
          },
        ],
      },
    ],
  },
  {
    id: "growth",
    name: "Business & Growth",
    icon: "📈",
    color: "#B06AD4",
    description: "Build and scale your real estate business.",
    courses: [
      {
        id: "business",
        title: "Realtor Business Growth",
        icon: "📈",
        color: "#B06AD4",
        credits: 3,
        prerequisites: [],
        tier: ["starter", "pro", "elite", "lending"],
        desc: "Build a scalable real estate business that generates without you.",
        units: [
          {
            id: "biz-u1",
            title: "Lead Generation & SOI",
            lessons: [
              { id: "biz-l1", title: "Building Your SOI System", duration: "18 min", description: "Sphere of influence strategies that generate consistent referrals." },
              { id: "biz-l2", title: "Geographic Farming", duration: "15 min", description: "Dominate a neighborhood with targeted marketing and community presence." },
            ],
            quiz: [
              { q: "SOI stands for:", options: ["System of Investment", "Sphere of Influence", "Standard Operating Instructions", "Source of Income"], correct: 1 },
              { q: "Geographic farming is most effective when:", options: ["You cover the entire city", "You focus on 200-500 homes consistently", "You only send one mailer", "You avoid personal contact"], correct: 1 },
              { q: "How often should you contact your SOI?", options: ["Once a year", "Monthly with varied touchpoints", "Only when you need a deal", "Daily cold calls"], correct: 1 },
            ],
          },
          {
            id: "biz-u2",
            title: "Systems & Branding",
            lessons: [
              { id: "biz-l3", title: "CRM Setup & Automation", duration: "20 min", description: "Set up a CRM that nurtures leads and automates follow-up." },
              { id: "biz-l4", title: "Social Media & Video", duration: "16 min", description: "Content strategies that build authority and generate inbound leads." },
            ],
            quiz: [
              { q: "What is the primary purpose of a real estate CRM?", options: ["Accounting", "Lead tracking, follow-up automation, and relationship management", "Website design", "Property valuation"], correct: 1 },
              { q: "Which content type generates the most engagement for real estate?", options: ["Stock photos", "Video walkthroughs and market updates", "Plain text posts", "Memes only"], correct: 1 },
            ],
          },
          {
            id: "biz-u3",
            title: "Scaling & Team Building",
            lessons: [
              { id: "biz-l5", title: "Team Building", duration: "22 min", description: "When to hire, who to hire, and how to build a production team." },
              { id: "biz-l6", title: "Brokerage Selection", duration: "14 min", description: "Choosing the right brokerage for your career stage and goals." },
            ],
            quiz: [
              { q: "When should an agent consider building a team?", options: ["On their first day", "When they consistently close 30+ deals/year", "After 1 month in the business", "Only if they dislike working alone"], correct: 1 },
              { q: "What is the most important factor in brokerage selection?", options: ["Office decor", "Training, support, and culture fit for your goals", "Proximity to home", "Free coffee"], correct: 1 },
            ],
          },
        ],
      },
    ],
  },
  {
    id: "advanced",
    name: "Advanced Strategies",
    icon: "⚡",
    color: "#D46A6A",
    description: "Elite-level investment and deal structuring.",
    courses: [
      {
        id: "investing",
        title: "Real Estate Investing",
        icon: "🏗️",
        color: "#D46A6A",
        credits: 4,
        prerequisites: [],
        tier: ["pro", "elite"],
        desc: "From first rental to multifamily portfolio — a complete investor path.",
        units: [
          {
            id: "inv-u1",
            title: "Investment Strategies",
            lessons: [
              { id: "inv-l1", title: "BRRRR Strategy", duration: "22 min", description: "Buy, Rehab, Rent, Refinance, Repeat — the full wealth-building cycle." },
              { id: "inv-l2", title: "Market Selection", duration: "18 min", description: "Identify high-growth markets using data-driven analysis." },
              { id: "inv-l3", title: "Deal Sourcing", duration: "16 min", description: "Find off-market deals, wholesalers, auctions, and direct mail campaigns." },
            ],
            quiz: [
              { q: "What does BRRRR stand for?", options: ["Buy, Rent, Refinance, Repeat, Return", "Buy, Rehab, Rent, Refinance, Repeat", "Borrow, Renovate, Rent, Refi, Resell", "Build, Rent, Repair, Refinance, Retire"], correct: 1 },
              { q: "Which metric is most important for market selection?", options: ["Population growth and job diversification", "Number of palm trees", "Distance from your home", "Average home color"], correct: 0 },
              { q: "The best off-market deal sources include:", options: ["Zillow featured listings", "Driving for dollars, direct mail, and wholesalers", "Only MLS listings", "Social media ads"], correct: 1 },
            ],
          },
          {
            id: "inv-u2",
            title: "Analysis & Management",
            lessons: [
              { id: "inv-l4", title: "Multifamily Underwriting", duration: "28 min", description: "Analyze apartment complexes: rent rolls, expenses, cap rates, and value-add plays." },
              { id: "inv-l5", title: "Property Management", duration: "18 min", description: "Self-manage vs hire a PM — systems, screening, and maintenance." },
              { id: "inv-l6", title: "Exit Strategies", duration: "15 min", description: "When to sell, refinance, 1031, or hold — optimizing your exit." },
            ],
            quiz: [
              { q: "What is a rent roll?", options: ["A type of sushi", "A document listing all units, tenants, and current rents", "A mortgage document", "A construction technique"], correct: 1 },
              { q: "Value-add investing means:", options: ["Buying the most expensive property", "Acquiring underperforming properties and improving them to increase NOI", "Adding a swimming pool", "Only buying new construction"], correct: 1 },
              { q: "Which exit strategy defers capital gains tax?", options: ["Cash sale", "1031 Exchange", "Lease option", "Short sale"], correct: 1 },
            ],
          },
        ],
      },
      {
        id: "deal_structuring",
        title: "Advanced Deal Structuring",
        icon: "⚡",
        color: "#D4A06A",
        credits: 4,
        prerequisites: ["investing"],
        tier: ["elite"],
        desc: "Elite strategies for complex, high-value transactions.",
        units: [
          {
            id: "adv-u1",
            title: "Creative Financing",
            lessons: [
              { id: "adv-l1", title: "Creative Financing", duration: "25 min", description: "Subject-to, lease options, and unconventional deal structures." },
              { id: "adv-l2", title: "Seller Financing & Wraps", duration: "22 min", description: "Structure seller-financed deals and wraparound mortgages." },
            ],
            quiz: [
              { q: "What is a 'subject-to' deal?", options: ["Buying subject to government approval", "Buying property subject to the existing mortgage staying in place", "A conditional inspection", "A type of short sale"], correct: 1 },
              { q: "A wraparound mortgage means:", options: ["Adding insulation to a property", "A new mortgage that wraps around the existing one", "A construction loan", "Refinancing at a lower rate"], correct: 1 },
              { q: "Seller financing benefits the buyer because:", options: ["It never requires a down payment", "It can offer more flexible terms than traditional lending", "Sellers always offer 0% interest", "It eliminates closing costs"], correct: 1 },
            ],
          },
          {
            id: "adv-u2",
            title: "Partnerships & Syndication",
            lessons: [
              { id: "adv-l3", title: "Joint Ventures", duration: "20 min", description: "Structure JV deals with clear equity splits, roles, and exit triggers." },
              { id: "adv-l4", title: "Syndication Basics", duration: "24 min", description: "Pool investor capital for larger deals — SEC rules, PPMs, and investor relations." },
            ],
            quiz: [
              { q: "In a JV, the GP (General Partner) typically:", options: ["Just provides capital", "Manages the deal and operations", "Has no liability", "Is always a bank"], correct: 1 },
              { q: "SEC Rule 506(b) allows:", options: ["Unlimited public advertising", "Up to 35 non-accredited investors with no general solicitation", "Only accredited investors", "No investor limits"], correct: 1 },
            ],
          },
          {
            id: "adv-u3",
            title: "Distressed & Off-Market",
            lessons: [
              { id: "adv-l5", title: "Distressed Assets", duration: "20 min", description: "Foreclosures, REOs, and note buying strategies." },
              { id: "adv-l6", title: "Off-Market Strategies", duration: "18 min", description: "Advanced sourcing: probate, tax liens, direct-to-seller campaigns." },
            ],
            quiz: [
              { q: "An REO property is:", options: ["A rental property", "Real Estate Owned — a bank-owned foreclosure", "A type of mortgage", "A new construction"], correct: 1 },
              { q: "Tax lien investing involves:", options: ["Avoiding property taxes", "Purchasing the tax debt on a property for potential returns", "Filing tax returns for owners", "Government grants"], correct: 1 },
              { q: "Probate leads come from:", options: ["Properties with expired listings", "Estates of deceased property owners going through court", "Rental properties", "New construction"], correct: 1 },
            ],
          },
        ],
      },
    ],
  },
];

// Flatten helpers
function getAllCourses() {
  const courses = [];
  CURRICULUM.forEach(dept => dept.courses.forEach(c => courses.push({ ...c, departmentId: dept.id })));
  return courses;
}
function getCourse(id) { return getAllCourses().find(c => c.id === id) || null; }
function getDepartment(id) { return CURRICULUM.find(d => d.id === id) || null; }

// ─── AI SYSTEM PROMPT ─────────────────────────────────────────────────────────

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

const ONBOARDING_ROLES = ["Realtor / Agent", "Real Estate Investor", "Mortgage Loan Officer", "Lender / Broker", "New to Real Estate"];
const ONBOARDING_GOALS = ["Close more deals this year", "Get my first deal", "Master mortgage & lending", "Build a rental portfolio", "Grow and scale my team", "Increase my income by 50%+"];
const ONBOARDING_CHALLENGES = ["Finding consistent leads", "Converting leads to clients", "Understanding financing & loans", "Managing my time and pipeline", "Building systems that scale", "Standing out in my market"];

const STORAGE_KEY = "ravlo_academy_v3";

function loadStorage() {
  try { return JSON.parse(localStorage.getItem(STORAGE_KEY) || "{}"); } catch { return {}; }
}
function saveStorage(data) {
  try { localStorage.setItem(STORAGE_KEY, JSON.stringify(data)); } catch {}
}

// ─── GPA helpers ──────────────────────────────────────────────────────────────

function scoreToGrade(pct) {
  if (pct >= 97) return { letter: "A+", gpa: 4.0 };
  if (pct >= 93) return { letter: "A", gpa: 4.0 };
  if (pct >= 90) return { letter: "A-", gpa: 3.7 };
  if (pct >= 87) return { letter: "B+", gpa: 3.3 };
  if (pct >= 83) return { letter: "B", gpa: 3.0 };
  if (pct >= 80) return { letter: "B-", gpa: 2.7 };
  if (pct >= 77) return { letter: "C+", gpa: 2.3 };
  if (pct >= 73) return { letter: "C", gpa: 2.0 };
  if (pct >= 70) return { letter: "C-", gpa: 1.7 };
  if (pct >= 67) return { letter: "D+", gpa: 1.3 };
  if (pct >= 60) return { letter: "D", gpa: 1.0 };
  return { letter: "F", gpa: 0.0 };
}

// ─── MAIN COMPONENT ───────────────────────────────────────────────────────────
function RavloAcademy() {
  const [screen, setScreen] = useState("landing");
  const [tier, setTier] = useState(null);
  const [userName, setUserName] = useState("");
  const [nameInput, setNameInput] = useState("");
  const [codeInput, setCodeInput] = useState("");
  const [codeError, setCodeError] = useState("");
  const [activeCourse, setActiveCourse] = useState(null);
  const [activeUnit, setActiveUnit] = useState(null);
  const [messages, setMessages] = useState([]);
  const [chatInput, setChatInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [notification, setNotification] = useState(null);
  const [isMobile, setIsMobile] = useState(false);

  // Progress: { lessons: {lessonId: true}, quizzes: {unitId: {score, total, passed}}, xp: number, certificates: [courseId] }
  const [progress, setProgress] = useState({ lessons: {}, quizzes: {}, xp: 0, certificates: [] });
  const [chatHistory, setChatHistory] = useState([]);
  const [onboardingStep, setOnboardingStep] = useState(0);
  const [onboardingAnswers, setOnboardingAnswers] = useState({ role: "", goal: "", challenge: "" });
  const [hasOnboarded, setHasOnboarded] = useState(false);
  const [showHistory, setShowHistory] = useState(false);
  const [historyFilter, setHistoryFilter] = useState("");

  // Quiz state
  const [quizAnswers, setQuizAnswers] = useState({});
  const [quizSubmitted, setQuizSubmitted] = useState(false);
  const [viewCertCourse, setViewCertCourse] = useState(null);

  const messagesEndRef = useRef(null);
  const inputRef = useRef(null);

  // Server-injected tier
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

  useEffect(() => {
    const check = () => setIsMobile(window.innerWidth < 768);
    check();
    window.addEventListener("resize", check);
    return () => window.removeEventListener("resize", check);
  }, []);

  useEffect(() => { messagesEndRef.current?.scrollIntoView({ behavior: "smooth" }); }, [messages]);

  useEffect(() => {
    if (!userName) return;
    const store = loadStorage();
    const userData = store[userName] || {};
    setProgress(userData.progress || { lessons: {}, quizzes: {}, xp: 0, certificates: [] });
    setChatHistory(userData.history || []);
    setHasOnboarded(userData.onboarded || false);
  }, [userName]);

  const saveProgress = useCallback((newProgress) => {
    const store = loadStorage();
    store[userName] = { ...store[userName], progress: newProgress };
    saveStorage(store);
    setProgress(newProgress);
  }, [userName]);

  const saveHistory = useCallback((newHistory) => {
    const store = loadStorage();
    store[userName] = { ...store[userName], history: newHistory };
    saveStorage(store);
    setChatHistory(newHistory);
  }, [userName]);

  const notify = (msg) => { setNotification(msg); setTimeout(() => setNotification(null), 3000); };

  // ── Access logic ──────────────────────────────────────────────────────────
  const handleSmartCodeAccess = async () => {
    const code = codeInput.trim().toUpperCase();
    const name = nameInput.trim() || "Member";
    if (!code) { setCodeError("Please enter your access code."); return; }
    setLoading(true);
    setCodeError("");
    try {
      const res = await fetch("/academy/activate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ code, name }),
      });
      const data = await res.json();
      if (res.ok) {
        const resolvedName = data.name || name;
        setTier(data.tier);
        setUserName(resolvedName);
        const store = loadStorage();
        const userData = store[resolvedName] || {};
        if (!userData.onboarded) {
          setOnboardingStep(0);
          setOnboardingAnswers({ role: "", goal: "", challenge: "" });
          setScreen("onboarding");
        } else {
          setHasOnboarded(true);
          setScreen("dashboard");
        }
      } else {
        setCodeError(data.error || "Access code not recognized.");
      }
    } catch {
      setCodeError("Connection error. Please try again.");
    } finally {
      setLoading(false);
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
    setMessages([]);
    setScreen("coach");
    const welcomePrompt = `I'm ${userName}, a ${onboardingAnswers.role || "real estate professional"}. My #1 goal is to ${(onboardingAnswers.goal || "grow my business").toLowerCase()} and my biggest challenge is ${(onboardingAnswers.challenge || "consistency").toLowerCase()}. I have ${ACCESS_TIERS[tier]?.description} access. Please greet me, then immediately build my personalized first-week action plan — specific actions I can start today with real numbers and clear milestones.`;
    setTimeout(() => sendMessage(welcomePrompt), 100);
  };

  // ── AI chat ───────────────────────────────────────────────────────────────
  const sendMessage = async (text) => {
    const msg = text || chatInput.trim();
    if (!msg || loading) return;
    setChatInput("");
    const newMsgs = [...messages, { role: "user", content: msg }];
    setMessages(newMsgs);
    setLoading(true);
    const context = `User: ${userName} | Access: ${ACCESS_TIERS[tier]?.label} | Course: ${activeCourse?.title || "General"} | Role: ${onboardingAnswers?.role || "Not specified"} | Goal: ${onboardingAnswers?.goal || "Not specified"}`;
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
    const label = firstUser ? firstUser.content.slice(0, 60) + (firstUser.content.length > 60 ? "..." : "") : "Coaching Session";
    const sess = { id: Date.now(), label, date: new Date().toLocaleDateString(), messages };
    const updated = [sess, ...chatHistory].slice(0, 20);
    saveHistory(updated);
    notify("Session saved");
  };

  const loadSession = (sess) => { setMessages(sess.messages); setShowHistory(false); setScreen("coach"); };
  const deleteSession = (id) => { saveHistory(chatHistory.filter(s => s.id !== id)); };

  // ── Lesson completion ─────────────────────────────────────────────────────
  const toggleLesson = (lessonId) => {
    const newP = { ...progress, lessons: { ...progress.lessons } };
    if (newP.lessons[lessonId]) {
      delete newP.lessons[lessonId];
      newP.xp = Math.max(0, (newP.xp || 0) - XP_PER_LESSON);
    } else {
      newP.lessons[lessonId] = true;
      newP.xp = (newP.xp || 0) + XP_PER_LESSON;
    }
    saveProgress(newP);
  };

  // ── Quiz ──────────────────────────────────────────────────────────────────
  const submitQuiz = (unit) => {
    const quiz = unit.quiz || [];
    let correct = 0;
    quiz.forEach((q, i) => { if (quizAnswers[i] === q.correct) correct++; });
    const pct = Math.round((correct / quiz.length) * 100);
    const passed = pct >= 70;
    const newP = { ...progress, quizzes: { ...progress.quizzes } };
    const prev = newP.quizzes[unit.id];
    const isNewPass = passed && (!prev || !prev.passed);
    newP.quizzes[unit.id] = { score: correct, total: quiz.length, pct, passed };
    if (isNewPass) newP.xp = (newP.xp || 0) + XP_PER_QUIZ_PASS;
    // Check course completion
    if (activeCourse) {
      const allPassed = activeCourse.units.every(u => {
        if (u.id === unit.id) return passed;
        return newP.quizzes[u.id]?.passed;
      });
      if (allPassed && !(newP.certificates || []).includes(activeCourse.id)) {
        newP.certificates = [...(newP.certificates || []), activeCourse.id];
        newP.xp = (newP.xp || 0) + XP_PER_COURSE;
        setTimeout(() => notify(`Course Complete! Certificate earned for ${activeCourse.title}`), 500);
      }
    }
    saveProgress(newP);
    setQuizSubmitted(true);
  };

  const startQuiz = (unit) => {
    setActiveUnit(unit);
    setQuizAnswers({});
    setQuizSubmitted(false);
    setScreen("quiz");
  };

  // ── Progress helpers ──────────────────────────────────────────────────────
  const getCourseProgress = (course) => {
    const allLessons = course.units.flatMap(u => u.lessons);
    const completed = allLessons.filter(l => progress.lessons[l.id]).length;
    const unitsPassed = course.units.filter(u => progress.quizzes[u.id]?.passed).length;
    return {
      lessons: completed,
      totalLessons: allLessons.length,
      lessonPct: allLessons.length ? Math.round((completed / allLessons.length) * 100) : 0,
      unitsPassed,
      totalUnits: course.units.length,
      allPassed: unitsPassed === course.units.length,
    };
  };

  const getCourseGrade = (course) => {
    const quizScores = course.units.map(u => progress.quizzes[u.id]).filter(Boolean);
    if (quizScores.length === 0) return null;
    const avgPct = Math.round(quizScores.reduce((s, q) => s + q.pct, 0) / quizScores.length);
    return scoreToGrade(avgPct);
  };

  const getOverallGPA = () => {
    const allCourses = getAllCourses().filter(c => c.tier.includes(tier));
    let totalPoints = 0, totalCredits = 0;
    allCourses.forEach(c => {
      const grade = getCourseGrade(c);
      if (grade) {
        totalPoints += grade.gpa * c.credits;
        totalCredits += c.credits;
      }
    });
    return totalCredits ? (totalPoints / totalCredits).toFixed(2) : "N/A";
  };

  const getEarnedCredits = () => {
    return getAllCourses().filter(c => c.tier.includes(tier) && (progress.certificates || []).includes(c.id)).reduce((s, c) => s + c.credits, 0);
  };

  const getTotalCredits = () => {
    return getAllCourses().filter(c => c.tier.includes(tier)).reduce((s, c) => s + c.credits, 0);
  };

  const meetsPrereqs = (course) => {
    if (!course.prerequisites || course.prerequisites.length === 0) return true;
    return course.prerequisites.every(p => (progress.certificates || []).includes(p));
  };

  // ── Coach helpers ─────────────────────────────────────────────────────────
  const copyReferralLink = () => {
    const link = window.location.origin + "/academy";
    navigator.clipboard.writeText(link).then(() => notify("Academy link copied!")).catch(() => notify("Copy: " + link));
  };

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
  const availableCourses = tier ? getAllCourses().filter(c => c.tier.includes(tier)) : [];

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

  // XP bar component
  const XPBar = () => {
    const xp = progress.xp || 0;
    const lvl = getLevel(xp);
    const next = getNextLevel(xp);
    const pct = next ? Math.min(100, Math.round(((xp - lvl.minXP) / (next.minXP - lvl.minXP)) * 100)) : 100;
    return (
      <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
        <span style={{ fontSize: 16 }}>{lvl.icon}</span>
        <div style={{ flex: 1, minWidth: isMobile ? 60 : 100 }}>
          <div style={{ display: "flex", justifyContent: "space-between", fontSize: 10, color: "#7A7268", marginBottom: 3 }}>
            <span>{lvl.name}</span>
            <span>{xp} XP</span>
          </div>
          <div style={{ height: 4, borderRadius: 2, background: "rgba(255,255,255,0.06)", overflow: "hidden" }}>
            <div style={{ height: "100%", width: `${pct}%`, background: "linear-gradient(90deg,#D4AF6A,#9A7A3A)", borderRadius: 2, transition: "width 0.4s" }} />
          </div>
        </div>
        {next && <span style={{ fontSize: 9, color: "#3A3530" }}>{next.minXP - xp} to {next.name}</span>}
      </div>
    );
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
          Access Portal
        </button>
      </nav>

      <div style={{ flex: 1, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", padding: isMobile ? "48px 20px" : "80px 24px", textAlign: "center", position: "relative", zIndex: 1 }}>
        <div style={{ fontSize: 11, letterSpacing: 6, color: "#D4AF6A", textTransform: "uppercase", marginBottom: 24, fontWeight: 500 }}>Real Estate Education - Reimagined</div>
        <h1 style={{ fontFamily: "'Cormorant Garamond',serif", fontSize: isMobile ? "clamp(44px,12vw,64px)" : "clamp(52px,8vw,100px)", fontWeight: 300, lineHeight: 0.95, margin: "0 0 8px", letterSpacing: -2 }}>
          <span style={{ display: "block", color: "#EDE8DF" }}>Ravlo</span>
          <span style={{ display: "block", color: "#D4AF6A", fontWeight: 700, fontStyle: "italic" }}>Academy</span>
        </h1>
        <p style={{ fontSize: isMobile ? 15 : "clamp(15px,2vw,18px)", color: "#7A7268", maxWidth: 580, lineHeight: 1.7, margin: "32px auto 48px", fontWeight: 300 }}>
          A structured school for realtors, investors, and lenders. Earn credits, pass quizzes, and build your transcript — powered by AI coaching.
        </p>
        <div style={{ display: "flex", gap: 12, flexWrap: "wrap", justifyContent: "center" }}>
          <button onClick={() => setScreen("access")} style={{ padding: isMobile ? "14px 28px" : "16px 40px", borderRadius: 8, border: "none", background: "linear-gradient(135deg,#D4AF6A,#9A7A3A)", color: "#080808", fontSize: isMobile ? 14 : 15, fontWeight: 700, cursor: "pointer", letterSpacing: 1, fontFamily: "'DM Sans',sans-serif" }}>
            Enroll Now
          </button>
          <button onClick={() => setScreen("access")} style={{ padding: isMobile ? "14px 28px" : "16px 40px", borderRadius: 8, border: "1px solid rgba(212,175,106,0.3)", background: "transparent", color: "#D4AF6A", fontSize: isMobile ? 14 : 15, fontWeight: 500, cursor: "pointer", letterSpacing: 0.5, fontFamily: "'DM Sans',sans-serif" }}>
            Partner Access
          </button>
        </div>

        <div style={{ display: "flex", gap: isMobile ? 24 : 48, marginTop: isMobile ? 48 : 80, flexWrap: "wrap", justifyContent: "center" }}>
          {[["4", "Departments"], ["6", "Courses"], ["20+", "Units"], ["AI", "Coaching"]].map(([n, l]) => (
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
      <button onClick={() => setScreen("landing")} style={{ position: "absolute", top: 20, left: 20, background: "none", border: "none", color: "#5A5248", cursor: "pointer", fontSize: 13, fontFamily: "'DM Sans',sans-serif" }}>&#8592; Back</button>

      <div style={{ maxWidth: 680, width: "100%", position: "relative", zIndex: 1 }}>
        <div style={{ textAlign: "center", marginBottom: 40 }}>
          <div style={{ fontFamily: "'Cormorant Garamond',serif", fontSize: 12, letterSpacing: 6, color: "#D4AF6A", textTransform: "uppercase", marginBottom: 10 }}>Enrollment</div>
          <h2 style={{ fontFamily: "'Cormorant Garamond',serif", fontSize: isMobile ? 32 : 42, fontWeight: 300, margin: "0 0 8px" }}>Ravlo <strong style={{ fontWeight: 700 }}>Academy</strong></h2>
          <p style={{ color: "#5A5248", fontSize: 13 }}>Partners &amp; investors enter your code. New students choose a plan below.</p>
        </div>

        <div style={{ marginBottom: 20 }}>
          <label style={{ display: "block", fontSize: 10, letterSpacing: 3, color: "#D4AF6A", marginBottom: 10, textTransform: "uppercase" }}>Your Name</label>
          <input value={nameInput} onChange={e => setNameInput(e.target.value)} placeholder="First & Last Name"
            style={{ width: "100%", padding: "14px 18px", background: "rgba(255,255,255,0.04)", border: "1px solid rgba(212,175,106,0.2)", borderRadius: 8, color: "#EDE8DF", fontSize: 14, outline: "none", boxSizing: "border-box", fontFamily: "'DM Sans',sans-serif" }} />
        </div>

        <div style={{ marginBottom: 28 }}>
          <label style={{ display: "block", fontSize: 10, letterSpacing: 3, color: "#D4AF6A", marginBottom: 10, textTransform: "uppercase" }}>Partner / Team Access Code</label>
          <div style={{ position: "relative" }}>
            <input value={codeInput} onChange={e => { setCodeInput(e.target.value); setCodeError(""); }}
              placeholder="Enter your access code (e.g. RAVLO-ELITE)"
              onKeyDown={e => e.key === "Enter" && handleSmartCodeAccess()}
              style={{ width: "100%", padding: "14px 18px", background: "rgba(255,255,255,0.04)", border: `1px solid ${codeError ? "#D46A6A" : "rgba(212,175,106,0.2)"}`, borderRadius: 8, color: "#EDE8DF", fontSize: 14, outline: "none", boxSizing: "border-box", fontFamily: "'DM Sans',sans-serif" }} />
            {CODE_MAP[codeInput.trim().toUpperCase()] && (
              <div style={{ position: "absolute", right: 14, top: "50%", transform: "translateY(-50%)", fontSize: 11, color: "#6AD4A0", fontWeight: 600, letterSpacing: 1 }}>
                {ACCESS_TIERS[CODE_MAP[codeInput.trim().toUpperCase()]]?.label}
              </div>
            )}
          </div>
          {codeError && <div style={{ color: "#D46A6A", fontSize: 12, marginTop: 8 }}>{codeError}</div>}
          <button onClick={handleSmartCodeAccess} style={{ width: "100%", marginTop: 12, padding: "13px", borderRadius: 8, border: "none", background: "linear-gradient(135deg,#D4AF6A,#9A7A3A)", color: "#080808", fontSize: 14, fontWeight: 700, cursor: "pointer", fontFamily: "'DM Sans',sans-serif", letterSpacing: 0.5 }}>
            Enter Academy
          </button>
        </div>

        <div style={{ height: 1, background: "rgba(255,255,255,0.05)", margin: "0 0 28px" }} />

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
                    {pt.perks.map(p => <li key={p} style={{ fontSize: 11, color: "#7A7268", display: "flex", gap: 6, marginBottom: 3 }}><span style={{ color: pt.color }}>+</span>{p}</li>)}
                  </ul>
                  <button onClick={() => handlePaidAccess(key)} style={{ width: "100%", padding: "11px", borderRadius: 6, border: "none", background: `linear-gradient(135deg,${pt.color},${pt.color}88)`, color: "#080808", fontSize: 13, fontWeight: 700, cursor: "pointer", fontFamily: "'DM Sans',sans-serif" }}>
                    Subscribe - ${pt.monthly}/mo
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

    return (
      <div style={{ ...S.page, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", padding: "40px 20px", position: "relative" }}>
        <div style={{ position: "absolute", inset: 0, backgroundImage: "radial-gradient(ellipse 60% 40% at 50% 0%, rgba(212,175,106,0.08) 0%, transparent 70%)", pointerEvents: "none" }} />

        <div style={{ maxWidth: 600, width: "100%", position: "relative", zIndex: 1 }}>
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
                Continue
              </button>
            ) : (
              <button onClick={() => { if (onboardingAnswers[currentStep.key]) finishOnboarding(); }}
                disabled={!onboardingAnswers[currentStep.key]}
                style={{ padding: "13px 32px", borderRadius: 8, border: "none", background: onboardingAnswers[currentStep.key] ? "linear-gradient(135deg,#D4AF6A,#9A7A3A)" : "rgba(255,255,255,0.05)", color: onboardingAnswers[currentStep.key] ? "#080808" : "#3A3530", fontSize: 14, fontWeight: 700, cursor: onboardingAnswers[currentStep.key] ? "pointer" : "not-allowed", fontFamily: "'DM Sans',sans-serif" }}>
                Get My Plan
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
              <button onClick={() => setShowHistory(false)} style={{ background: "none", border: "none", color: "#5A5248", cursor: "pointer", fontSize: 18, lineHeight: 1 }}>x</button>
            </div>
            <div style={{ padding: "12px 16px", borderBottom: "1px solid rgba(255,255,255,0.04)" }}>
              <input value={historyFilter} onChange={e => setHistoryFilter(e.target.value)} placeholder="Search sessions..."
                style={{ width: "100%", padding: "9px 14px", background: "rgba(255,255,255,0.04)", border: "1px solid rgba(212,175,106,0.15)", borderRadius: 6, color: "#EDE8DF", fontSize: 13, outline: "none", boxSizing: "border-box", fontFamily: "'DM Sans',sans-serif" }} />
            </div>
            <div style={{ flex: 1, overflowY: "auto", padding: "12px" }}>
              {chatHistory.length === 0 ? (
                <div style={{ textAlign: "center", color: "#3A3530", fontSize: 13, marginTop: 40 }}>No saved sessions yet.</div>
              ) : (
                chatHistory.filter(s => !historyFilter || s.label.toLowerCase().includes(historyFilter.toLowerCase())).map(sess => (
                  <div key={sess.id} style={{ padding: "14px", borderRadius: 8, border: "1px solid rgba(212,175,106,0.1)", background: "rgba(255,255,255,0.02)", marginBottom: 8, cursor: "pointer" }}
                    onClick={() => loadSession(sess)}>
                    <div style={{ fontSize: 13, color: "#C8C0B4", marginBottom: 4, lineHeight: 1.4 }}>{sess.label}</div>
                    <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                      <div style={{ fontSize: 11, color: "#3A3530" }}>{sess.date} - {sess.messages.length} messages</div>
                      <button onClick={e => { e.stopPropagation(); deleteSession(sess.id); }} style={{ background: "none", border: "none", color: "#3A3530", cursor: "pointer", fontSize: 11, padding: "2px 6px" }}>Delete</button>
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
            {!isMobile && <div style={{ fontSize: 9, letterSpacing: 3, color: "#5A5248", textTransform: "uppercase" }}>School of Real Estate</div>}
          </div>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: isMobile ? 6 : 12 }}>
          <span style={{ fontSize: isMobile ? 9 : 11, color: t.color, padding: "3px 8px", borderRadius: 20, border: `1px solid ${t.border}`, background: t.bg, letterSpacing: 1, fontWeight: 600 }}>{t.badge}</span>
          {!isMobile && <span style={{ fontSize: 13, color: "#7A7268" }}>{userName}</span>}
          <button onClick={() => setScreen("transcript")} style={{ background: "none", border: "1px solid rgba(212,175,106,0.15)", borderRadius: 6, color: "#7A7268", cursor: "pointer", fontSize: isMobile ? 10 : 12, padding: "5px 10px", fontFamily: "'DM Sans',sans-serif" }}>Transcript</button>
          <button onClick={() => setShowHistory(true)} style={{ background: "none", border: "1px solid rgba(212,175,106,0.15)", borderRadius: 6, color: "#7A7268", cursor: "pointer", fontSize: isMobile ? 10 : 12, padding: "5px 10px", fontFamily: "'DM Sans',sans-serif" }}>History</button>
          <button onClick={() => setScreen("landing")} style={{ background: "none", border: "none", color: "#3A3530", cursor: "pointer", fontSize: 12, fontFamily: "'DM Sans',sans-serif" }}>Out</button>
        </div>
      </div>

      <div style={{ maxWidth: 1100, margin: "0 auto", padding: isMobile ? "24px 16px" : "40px 32px" }}>
        {/* Welcome + XP bar */}
        <div style={{ marginBottom: isMobile ? 28 : 40 }}>
          <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", flexWrap: "wrap", gap: 16 }}>
            <div>
              <div style={{ fontSize: 10, letterSpacing: 4, color: "#5A5248", textTransform: "uppercase", marginBottom: 8 }}>Welcome back</div>
              <h2 style={{ fontFamily: "'Cormorant Garamond',serif", fontSize: isMobile ? 28 : 44, fontWeight: 300, margin: "0 0 4px" }}>
                Hello, <strong style={{ fontWeight: 700, color: "#D4AF6A" }}>{userName}</strong>
              </h2>
            </div>
            <div style={{ minWidth: isMobile ? "100%" : 280 }}><XPBar /></div>
          </div>
        </div>

        {/* Stats row */}
        <div style={{ display: "grid", gridTemplateColumns: isMobile ? "repeat(2,1fr)" : "repeat(4,1fr)", gap: 10, marginBottom: isMobile ? 28 : 40 }}>
          {[
            { label: "GPA", value: getOverallGPA(), color: "#D4AF6A" },
            { label: "Credits", value: `${getEarnedCredits()} / ${getTotalCredits()}`, color: "#6AD4A0" },
            { label: "Courses", value: `${(progress.certificates || []).length} / ${availableCourses.length}`, color: "#6AB4D4" },
            { label: "Level", value: getLevel(progress.xp || 0).name, color: "#B06AD4" },
          ].map(stat => (
            <div key={stat.label} style={{ padding: isMobile ? "14px 12px" : "20px", borderRadius: 10, border: `1px solid ${stat.color}25`, background: `${stat.color}08`, textAlign: "center" }}>
              <div style={{ fontFamily: "'Cormorant Garamond',serif", fontSize: isMobile ? 22 : 28, fontWeight: 700, color: stat.color, lineHeight: 1 }}>{stat.value}</div>
              <div style={{ fontSize: 10, color: "#5A5248", letterSpacing: 2, textTransform: "uppercase", marginTop: 6 }}>{stat.label}</div>
            </div>
          ))}
        </div>

        {/* Action cards */}
        <div style={{ display: "grid", gridTemplateColumns: isMobile ? "1fr 1fr" : "repeat(4,1fr)", gap: isMobile ? 10 : 14, marginBottom: isMobile ? 32 : 48 }}>
          {[
            { icon: "AI", label: "AI Coach", desc: "One-on-one session", color: "#D4AF6A", action: () => startCoach() },
            { icon: "90", label: "My Plan", desc: "90-day success plan", color: "#6AD4A0", action: startPlan },
            { icon: "#", label: "Transcript", desc: "Grades & credits", color: "#6AB4D4", action: () => setScreen("transcript") },
            { icon: "+", label: "Refer", desc: "Copy your link", color: "#B06AD4", action: copyReferralLink },
          ].map(card => (
            <button key={card.label} onClick={card.action} style={{ padding: isMobile ? "16px 12px" : "22px", borderRadius: 12, border: `1px solid ${card.color}30`, background: `${card.color}08`, cursor: "pointer", textAlign: "left", transition: "all 0.2s", fontFamily: "'DM Sans',sans-serif" }}
              onMouseEnter={e => { e.currentTarget.style.border = `1px solid ${card.color}60`; e.currentTarget.style.transform = "translateY(-2px)"; }}
              onMouseLeave={e => { e.currentTarget.style.border = `1px solid ${card.color}30`; e.currentTarget.style.transform = "translateY(0)"; }}>
              <div style={{ fontSize: isMobile ? 18 : 24, marginBottom: 8, fontFamily: "'Cormorant Garamond',serif", fontWeight: 700, color: card.color }}>{card.icon}</div>
              <div style={{ fontFamily: "'Cormorant Garamond',serif", fontSize: isMobile ? 14 : 17, fontWeight: 700, color: "#EDE8DF", marginBottom: 3 }}>{card.label}</div>
              <div style={{ fontSize: isMobile ? 10 : 12, color: "#5A5248" }}>{card.desc}</div>
            </button>
          ))}
        </div>

        {/* Departments → Courses */}
        {CURRICULUM.map(dept => {
          const deptCourses = dept.courses.filter(c => c.tier.includes(tier));
          if (deptCourses.length === 0) return null;
          return (
            <div key={dept.id} style={{ marginBottom: isMobile ? 36 : 48 }}>
              <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 16 }}>
                <span style={{ fontSize: 22 }}>{dept.icon}</span>
                <div>
                  <div style={{ fontFamily: "'Cormorant Garamond',serif", fontSize: isMobile ? 18 : 22, fontWeight: 700, color: "#EDE8DF" }}>{dept.name}</div>
                  <div style={{ fontSize: 11, color: "#5A5248" }}>{dept.description}</div>
                </div>
              </div>
              <div style={{ display: "grid", gridTemplateColumns: isMobile ? "1fr" : "repeat(auto-fill,minmax(300px,1fr))", gap: 12 }}>
                {deptCourses.map(course => {
                  const locked = !meetsPrereqs(course);
                  const prog = getCourseProgress(course);
                  const grade = getCourseGrade(course);
                  const hasCert = (progress.certificates || []).includes(course.id);
                  return (
                    <div key={course.id}
                      onClick={() => {
                        if (locked) { notify(`Complete "${getCourse(course.prerequisites[0])?.title}" first`); return; }
                        setActiveCourse(course);
                        setScreen("course");
                      }}
                      style={{ padding: "22px", borderRadius: 12, border: locked ? "1px solid rgba(255,255,255,0.04)" : `1px solid ${course.color}25`, background: locked ? "rgba(255,255,255,0.02)" : `${course.color}08`, cursor: locked ? "not-allowed" : "pointer", transition: "all 0.2s", opacity: locked ? 0.4 : 1, position: "relative" }}
                      onMouseEnter={e => { if (!locked) { e.currentTarget.style.border = `1px solid ${course.color}50`; e.currentTarget.style.transform = "translateY(-2px)"; } }}
                      onMouseLeave={e => { if (!locked) { e.currentTarget.style.border = `1px solid ${course.color}25`; e.currentTarget.style.transform = "translateY(0)"; } }}>
                      {locked && <div style={{ position: "absolute", top: 14, right: 14, fontSize: 11, color: "#3A3530" }}>Locked</div>}
                      {hasCert && <div style={{ position: "absolute", top: 14, right: 14, fontSize: 11, color: course.color, fontWeight: 600 }}>Certified</div>}
                      <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 10 }}>
                        <span style={{ fontSize: 24 }}>{course.icon}</span>
                        <div style={{ flex: 1 }}>
                          <div style={{ fontFamily: "'Cormorant Garamond',serif", fontSize: 17, fontWeight: 700, color: "#EDE8DF" }}>{course.title}</div>
                          <div style={{ fontSize: 10, color: "#5A5248" }}>{course.credits} credits - {course.units.length} units</div>
                        </div>
                      </div>
                      <div style={{ fontSize: 11, color: "#5A5248", marginBottom: 14, lineHeight: 1.5 }}>{course.desc}</div>

                      {!locked && (
                        <div>
                          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 6 }}>
                            <div style={{ fontSize: 10, color: "#5A5248" }}>{prog.unitsPassed}/{prog.totalUnits} units passed</div>
                            {grade && <div style={{ fontSize: 10, color: course.color, fontWeight: 600 }}>{grade.letter}</div>}
                          </div>
                          <div style={{ height: 3, borderRadius: 2, background: "rgba(255,255,255,0.06)", overflow: "hidden" }}>
                            <div style={{ height: "100%", width: `${prog.lessonPct}%`, background: course.color, borderRadius: 2, transition: "width 0.4s ease" }} />
                          </div>
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );

  // ── COURSE VIEW (formerly MODULE) ─────────────────────────────────────────
  if (screen === "course" && activeCourse) {
    const prog = getCourseProgress(activeCourse);
    const grade = getCourseGrade(activeCourse);
    const hasCert = (progress.certificates || []).includes(activeCourse.id);
    return (
      <div style={{ ...S.page }}>
        <div style={{ padding: isMobile ? "14px 16px" : "18px 32px", borderBottom: "1px solid rgba(212,175,106,0.1)", display: "flex", alignItems: "center", gap: 14, background: "rgba(8,8,8,0.95)", position: "sticky", top: 0, zIndex: 50 }}>
          <button onClick={() => setScreen("dashboard")} style={{ background: "none", border: "none", color: "#5A5248", cursor: "pointer", fontSize: 13, fontFamily: "'DM Sans',sans-serif", flexShrink: 0 }}>&#8592; Dashboard</button>
          <div style={{ width: 1, height: 18, background: "rgba(255,255,255,0.06)", flexShrink: 0 }} />
          <span style={{ fontSize: 18 }}>{activeCourse.icon}</span>
          <span style={{ fontFamily: "'Cormorant Garamond',serif", fontSize: isMobile ? 15 : 18, fontWeight: 700, flex: 1, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{activeCourse.title}</span>
          <div style={{ display: "flex", gap: 8, alignItems: "center", flexShrink: 0 }}>
            {grade && <span style={{ fontSize: 14, color: activeCourse.color, fontWeight: 700, fontFamily: "'Cormorant Garamond',serif" }}>{grade.letter}</span>}
            <span style={{ fontSize: 11, color: activeCourse.color }}>{prog.unitsPassed}/{prog.totalUnits} units</span>
          </div>
        </div>

        <div style={{ height: 3, background: "rgba(255,255,255,0.04)" }}>
          <div style={{ height: "100%", width: `${prog.lessonPct}%`, background: activeCourse.color, transition: "width 0.4s ease" }} />
        </div>

        <div style={{ maxWidth: 900, margin: "0 auto", padding: isMobile ? "28px 16px" : "48px 32px" }}>
          <div style={{ marginBottom: 36 }}>
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: 12 }}>
              <div>
                <div style={{ fontSize: 12, color: activeCourse.color, letterSpacing: 2, textTransform: "uppercase", marginBottom: 8, fontWeight: 600 }}>Course - {activeCourse.credits} Credits</div>
                <h2 style={{ fontFamily: "'Cormorant Garamond',serif", fontSize: isMobile ? 28 : 40, fontWeight: 300, margin: "0 0 8px" }}>{activeCourse.title}</h2>
                <p style={{ color: "#7A7268", fontSize: 14, lineHeight: 1.7, maxWidth: 600 }}>{activeCourse.desc}</p>
              </div>
              {hasCert && (
                <button onClick={() => { setViewCertCourse(activeCourse); setScreen("certificate"); }}
                  style={{ padding: "10px 20px", borderRadius: 8, border: `1px solid ${activeCourse.color}40`, background: `${activeCourse.color}12`, color: activeCourse.color, fontSize: 13, fontWeight: 600, cursor: "pointer", fontFamily: "'DM Sans',sans-serif" }}>
                  View Certificate
                </button>
              )}
            </div>
          </div>

          {/* Units */}
          {activeCourse.units.map((unit, ui) => {
            const unitLessons = unit.lessons || [];
            const lessonsComplete = unitLessons.filter(l => progress.lessons[l.id]).length;
            const quizResult = progress.quizzes[unit.id];
            const allLessonsDone = lessonsComplete === unitLessons.length;

            return (
              <div key={unit.id} style={{ marginBottom: 24, borderRadius: 12, border: `1px solid ${activeCourse.color}20`, background: `${activeCourse.color}05`, overflow: "hidden" }}>
                {/* Unit header */}
                <div style={{ padding: "18px 20px", borderBottom: `1px solid ${activeCourse.color}15`, display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                  <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
                    <div style={{ width: 32, height: 32, borderRadius: 8, background: `${activeCourse.color}20`, display: "flex", alignItems: "center", justifyContent: "center", fontSize: 14, color: activeCourse.color, fontWeight: 700 }}>{ui + 1}</div>
                    <div>
                      <div style={{ fontFamily: "'Cormorant Garamond',serif", fontSize: 16, fontWeight: 700, color: "#EDE8DF" }}>{unit.title}</div>
                      <div style={{ fontSize: 11, color: "#5A5248" }}>{unitLessons.length} lessons - {lessonsComplete}/{unitLessons.length} complete</div>
                    </div>
                  </div>
                  {quizResult && (
                    <div style={{ fontSize: 12, color: quizResult.passed ? "#6AD4A0" : "#D46A6A", fontWeight: 600 }}>
                      {quizResult.passed ? `Passed ${quizResult.pct}%` : `${quizResult.pct}% — Retry`}
                    </div>
                  )}
                </div>

                {/* Lessons */}
                <div style={{ padding: "12px 16px" }}>
                  {unitLessons.map((lesson, li) => {
                    const done = !!progress.lessons[lesson.id];
                    return (
                      <div key={lesson.id} style={{ display: "flex", alignItems: "center", gap: 10, padding: "10px 8px", borderRadius: 8, marginBottom: 4, transition: "all 0.2s" }}>
                        <button onClick={e => { e.stopPropagation(); toggleLesson(lesson.id); }}
                          style={{ width: 24, height: 24, borderRadius: 6, border: `1.5px solid ${done ? activeCourse.color : activeCourse.color + "50"}`, background: done ? activeCourse.color : "transparent", display: "flex", alignItems: "center", justifyContent: "center", cursor: "pointer", flexShrink: 0, transition: "all 0.2s" }}>
                          {done && <span style={{ color: "#080808", fontSize: 11, fontWeight: 700 }}>+</span>}
                        </button>
                        <button onClick={() => startCoach(`Teach me about: "${lesson.title}" from the ${activeCourse.title} course, Unit "${unit.title}". ${lesson.description} Start with the key concepts, then give me real-world examples and actionable steps I can use immediately.`)}
                          style={{ flex: 1, background: "none", border: "none", textAlign: "left", cursor: "pointer", fontFamily: "'DM Sans',sans-serif", padding: 0 }}>
                          <div style={{ fontSize: 13, color: done ? activeCourse.color : "#C8C0B4", fontWeight: done ? 600 : 500, textDecoration: done ? "line-through" : "none", opacity: done ? 0.7 : 1 }}>{lesson.title}</div>
                          <div style={{ fontSize: 11, color: "#3A3530", marginTop: 2 }}>{lesson.duration} - {lesson.description}</div>
                        </button>
                      </div>
                    );
                  })}
                </div>

                {/* Quiz button */}
                {unit.quiz && unit.quiz.length > 0 && (
                  <div style={{ padding: "12px 16px", borderTop: `1px solid ${activeCourse.color}10` }}>
                    <button onClick={() => startQuiz(unit)}
                      style={{ width: "100%", padding: "12px", borderRadius: 8, border: `1px solid ${activeCourse.color}30`, background: allLessonsDone ? `${activeCourse.color}15` : "rgba(255,255,255,0.02)", color: allLessonsDone ? activeCourse.color : "#5A5248", fontSize: 13, fontWeight: 600, cursor: "pointer", fontFamily: "'DM Sans',sans-serif", transition: "all 0.2s" }}>
                      {quizResult?.passed ? `Retake Quiz (Best: ${quizResult.pct}%)` : `Take Unit Quiz — ${unit.quiz.length} questions`}
                    </button>
                  </div>
                )}
              </div>
            );
          })}

          {/* AI overview */}
          <button onClick={() => startCoach(`Give me a comprehensive overview of the entire ${activeCourse.title} course. Cover all key concepts across all ${activeCourse.units.length} units, how they connect, and what I should focus on mastering first based on my profile as a ${ACCESS_TIERS[tier]?.description}.`)}
            style={{ marginTop: 12, padding: "15px 28px", borderRadius: 8, border: `1px solid ${activeCourse.color}40`, background: `${activeCourse.color}12`, color: activeCourse.color, fontSize: 14, fontWeight: 600, cursor: "pointer", fontFamily: "'DM Sans',sans-serif" }}>
            AI Overview of Entire Course
          </button>
        </div>
      </div>
    );
  }

  // ── QUIZ ──────────────────────────────────────────────────────────────────
  if (screen === "quiz" && activeUnit) {
    const quiz = activeUnit.quiz || [];
    const allAnswered = quiz.every((_, i) => quizAnswers[i] !== undefined);
    const result = quizSubmitted ? progress.quizzes[activeUnit.id] : null;

    return (
      <div style={{ ...S.page }}>
        <div style={{ padding: isMobile ? "14px 16px" : "18px 32px", borderBottom: "1px solid rgba(212,175,106,0.1)", display: "flex", alignItems: "center", gap: 14, background: "rgba(8,8,8,0.95)", position: "sticky", top: 0, zIndex: 50 }}>
          <button onClick={() => setScreen("course")} style={{ background: "none", border: "none", color: "#5A5248", cursor: "pointer", fontSize: 13, fontFamily: "'DM Sans',sans-serif" }}>&#8592; Back to Course</button>
          <div style={{ width: 1, height: 18, background: "rgba(255,255,255,0.06)" }} />
          <span style={{ fontFamily: "'Cormorant Garamond',serif", fontSize: isMobile ? 14 : 16, fontWeight: 700 }}>Unit Quiz: {activeUnit.title}</span>
        </div>

        <div style={{ maxWidth: 700, margin: "0 auto", padding: isMobile ? "28px 16px" : "48px 32px" }}>
          {!quizSubmitted && (
            <div style={{ marginBottom: 24 }}>
              <div style={{ fontSize: 10, letterSpacing: 4, color: "#D4AF6A", textTransform: "uppercase", marginBottom: 8 }}>Assessment</div>
              <h2 style={{ fontFamily: "'Cormorant Garamond',serif", fontSize: isMobile ? 24 : 32, fontWeight: 300, margin: "0 0 8px" }}>{activeUnit.title}</h2>
              <p style={{ color: "#5A5248", fontSize: 13 }}>{quiz.length} questions - Must score 70% to pass</p>
            </div>
          )}

          {quizSubmitted && result && (
            <div style={{ marginBottom: 32, padding: "24px", borderRadius: 12, border: `1px solid ${result.passed ? "#6AD4A050" : "#D46A6A50"}`, background: result.passed ? "rgba(106,212,160,0.08)" : "rgba(212,106,106,0.08)", textAlign: "center" }}>
              <div style={{ fontFamily: "'Cormorant Garamond',serif", fontSize: 48, fontWeight: 700, color: result.passed ? "#6AD4A0" : "#D46A6A" }}>{result.pct}%</div>
              <div style={{ fontSize: 16, color: result.passed ? "#6AD4A0" : "#D46A6A", fontWeight: 600, marginBottom: 4 }}>{result.passed ? "Passed!" : "Not Passed"}</div>
              <div style={{ fontSize: 13, color: "#5A5248" }}>{result.score} of {result.total} correct</div>
              {result.passed && <div style={{ fontSize: 12, color: "#D4AF6A", marginTop: 8 }}>+{XP_PER_QUIZ_PASS} XP earned</div>}
            </div>
          )}

          {quiz.map((q, qi) => {
            const answered = quizAnswers[qi] !== undefined;
            const isCorrect = quizSubmitted && quizAnswers[qi] === q.correct;
            const isWrong = quizSubmitted && answered && quizAnswers[qi] !== q.correct;

            return (
              <div key={qi} style={{ marginBottom: 20, padding: "20px", borderRadius: 10, border: "1px solid rgba(212,175,106,0.1)", background: "rgba(255,255,255,0.02)" }}>
                <div style={{ display: "flex", gap: 10, marginBottom: 14 }}>
                  <div style={{ width: 26, height: 26, borderRadius: 6, background: "rgba(212,175,106,0.15)", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 12, color: "#D4AF6A", fontWeight: 700, flexShrink: 0 }}>{qi + 1}</div>
                  <div style={{ fontSize: 14, color: "#C8C0B4", lineHeight: 1.6, flex: 1 }}>{q.q}</div>
                </div>
                <div style={{ display: "flex", flexDirection: "column", gap: 8, paddingLeft: 36 }}>
                  {q.options.map((opt, oi) => {
                    const selected = quizAnswers[qi] === oi;
                    const correctOpt = quizSubmitted && oi === q.correct;
                    let borderColor = "rgba(212,175,106,0.15)";
                    let bgColor = "rgba(255,255,255,0.02)";
                    let textColor = "#7A7268";
                    if (selected && !quizSubmitted) { borderColor = "#D4AF6A"; bgColor = "rgba(212,175,106,0.1)"; textColor = "#D4AF6A"; }
                    if (quizSubmitted && correctOpt) { borderColor = "#6AD4A0"; bgColor = "rgba(106,212,160,0.1)"; textColor = "#6AD4A0"; }
                    if (quizSubmitted && selected && !correctOpt) { borderColor = "#D46A6A"; bgColor = "rgba(212,106,106,0.1)"; textColor = "#D46A6A"; }

                    return (
                      <button key={oi} onClick={() => { if (!quizSubmitted) setQuizAnswers(prev => ({ ...prev, [qi]: oi })); }}
                        disabled={quizSubmitted}
                        style={{ padding: "11px 16px", borderRadius: 8, border: `1px solid ${borderColor}`, background: bgColor, color: textColor, fontSize: 13, cursor: quizSubmitted ? "default" : "pointer", textAlign: "left", fontFamily: "'DM Sans',sans-serif", transition: "all 0.2s" }}>
                        {opt}
                      </button>
                    );
                  })}
                </div>
              </div>
            );
          })}

          <div style={{ display: "flex", gap: 12, justifyContent: "flex-end", marginTop: 16 }}>
            {!quizSubmitted ? (
              <button onClick={() => submitQuiz(activeUnit)} disabled={!allAnswered}
                style={{ padding: "14px 32px", borderRadius: 8, border: "none", background: allAnswered ? "linear-gradient(135deg,#D4AF6A,#9A7A3A)" : "rgba(255,255,255,0.05)", color: allAnswered ? "#080808" : "#3A3530", fontSize: 14, fontWeight: 700, cursor: allAnswered ? "pointer" : "not-allowed", fontFamily: "'DM Sans',sans-serif" }}>
                Submit Quiz
              </button>
            ) : (
              <div style={{ display: "flex", gap: 12 }}>
                {!result?.passed && (
                  <button onClick={() => { setQuizAnswers({}); setQuizSubmitted(false); }}
                    style={{ padding: "14px 28px", borderRadius: 8, border: "1px solid rgba(212,175,106,0.3)", background: "transparent", color: "#D4AF6A", fontSize: 14, fontWeight: 600, cursor: "pointer", fontFamily: "'DM Sans',sans-serif" }}>
                    Retake Quiz
                  </button>
                )}
                <button onClick={() => setScreen("course")}
                  style={{ padding: "14px 28px", borderRadius: 8, border: "none", background: "linear-gradient(135deg,#D4AF6A,#9A7A3A)", color: "#080808", fontSize: 14, fontWeight: 700, cursor: "pointer", fontFamily: "'DM Sans',sans-serif" }}>
                  Back to Course
                </button>
              </div>
            )}
          </div>
        </div>
      </div>
    );
  }

  // ── TRANSCRIPT ────────────────────────────────────────────────────────────
  if (screen === "transcript") return (
    <div style={{ ...S.page }}>
      <div style={{ padding: isMobile ? "14px 16px" : "18px 32px", borderBottom: "1px solid rgba(212,175,106,0.1)", display: "flex", alignItems: "center", gap: 14, background: "rgba(8,8,8,0.95)", position: "sticky", top: 0, zIndex: 50 }}>
        <button onClick={() => setScreen("dashboard")} style={{ background: "none", border: "none", color: "#5A5248", cursor: "pointer", fontSize: 13, fontFamily: "'DM Sans',sans-serif" }}>&#8592; Dashboard</button>
        <div style={{ width: 1, height: 18, background: "rgba(255,255,255,0.06)" }} />
        <span style={{ fontFamily: "'Cormorant Garamond',serif", fontSize: isMobile ? 15 : 18, fontWeight: 700 }}>Academic Transcript</span>
      </div>

      <div style={{ maxWidth: 900, margin: "0 auto", padding: isMobile ? "28px 16px" : "48px 32px" }}>
        {/* Transcript header */}
        <div style={{ textAlign: "center", marginBottom: 40, padding: "32px", borderRadius: 12, border: "1px solid rgba(212,175,106,0.15)", background: "rgba(212,175,106,0.04)" }}>
          <div style={{ fontSize: 10, letterSpacing: 6, color: "#D4AF6A", textTransform: "uppercase", marginBottom: 12 }}>Ravlo Academy</div>
          <div style={{ fontFamily: "'Cormorant Garamond',serif", fontSize: isMobile ? 20 : 26, fontWeight: 700, color: "#EDE8DF", marginBottom: 4 }}>{userName}</div>
          <div style={{ fontSize: 12, color: "#5A5248", marginBottom: 20 }}>{ACCESS_TIERS[tier]?.label} - {ACCESS_TIERS[tier]?.description}</div>

          <div style={{ display: "flex", justifyContent: "center", gap: isMobile ? 24 : 48, flexWrap: "wrap" }}>
            <div>
              <div style={{ fontFamily: "'Cormorant Garamond',serif", fontSize: 36, fontWeight: 700, color: "#D4AF6A" }}>{getOverallGPA()}</div>
              <div style={{ fontSize: 10, color: "#5A5248", letterSpacing: 2, textTransform: "uppercase" }}>Cumulative GPA</div>
            </div>
            <div>
              <div style={{ fontFamily: "'Cormorant Garamond',serif", fontSize: 36, fontWeight: 700, color: "#6AD4A0" }}>{getEarnedCredits()}</div>
              <div style={{ fontSize: 10, color: "#5A5248", letterSpacing: 2, textTransform: "uppercase" }}>Credits Earned</div>
            </div>
            <div>
              <div style={{ fontFamily: "'Cormorant Garamond',serif", fontSize: 36, fontWeight: 700, color: "#6AB4D4" }}>{(progress.certificates || []).length}</div>
              <div style={{ fontSize: 10, color: "#5A5248", letterSpacing: 2, textTransform: "uppercase" }}>Certificates</div>
            </div>
            <div>
              <div style={{ fontFamily: "'Cormorant Garamond',serif", fontSize: 36, fontWeight: 700, color: "#B06AD4" }}>{progress.xp || 0}</div>
              <div style={{ fontSize: 10, color: "#5A5248", letterSpacing: 2, textTransform: "uppercase" }}>Total XP</div>
            </div>
          </div>
        </div>

        {/* Course records */}
        <div style={{ fontSize: 10, letterSpacing: 3, color: "#5A5248", textTransform: "uppercase", marginBottom: 16 }}>Course Records</div>

        {/* Table header */}
        <div style={{ display: "grid", gridTemplateColumns: "1fr 60px 80px 80px 80px", gap: 8, padding: "10px 16px", borderRadius: "8px 8px 0 0", background: "rgba(212,175,106,0.06)", fontSize: 10, color: "#5A5248", letterSpacing: 1, textTransform: "uppercase", fontWeight: 600 }}>
          <div>Course</div>
          <div style={{ textAlign: "center" }}>Credits</div>
          <div style={{ textAlign: "center" }}>Units</div>
          <div style={{ textAlign: "center" }}>Grade</div>
          <div style={{ textAlign: "center" }}>Status</div>
        </div>

        {availableCourses.map(course => {
          const prog = getCourseProgress(course);
          const grade = getCourseGrade(course);
          const hasCert = (progress.certificates || []).includes(course.id);
          const started = prog.lessons > 0 || prog.unitsPassed > 0;
          const status = hasCert ? "Completed" : started ? "In Progress" : "Not Started";
          const statusColor = hasCert ? "#6AD4A0" : started ? "#D4AF6A" : "#3A3530";

          return (
            <div key={course.id} style={{ display: "grid", gridTemplateColumns: "1fr 60px 80px 80px 80px", gap: 8, padding: "14px 16px", borderBottom: "1px solid rgba(255,255,255,0.04)", alignItems: "center" }}>
              <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                <span style={{ fontSize: 16 }}>{course.icon}</span>
                <div>
                  <div style={{ fontSize: 13, color: "#C8C0B4", fontWeight: 500 }}>{course.title}</div>
                  {hasCert && (
                    <button onClick={() => { setViewCertCourse(course); setScreen("certificate"); }}
                      style={{ fontSize: 10, color: "#D4AF6A", background: "none", border: "none", cursor: "pointer", padding: 0, fontFamily: "'DM Sans',sans-serif", marginTop: 2 }}>
                      View Certificate
                    </button>
                  )}
                </div>
              </div>
              <div style={{ textAlign: "center", fontSize: 13, color: "#7A7268" }}>{course.credits}</div>
              <div style={{ textAlign: "center", fontSize: 13, color: "#7A7268" }}>{prog.unitsPassed}/{prog.totalUnits}</div>
              <div style={{ textAlign: "center", fontSize: 14, color: grade ? "#D4AF6A" : "#3A3530", fontWeight: 700, fontFamily: "'Cormorant Garamond',serif" }}>{grade ? grade.letter : "—"}</div>
              <div style={{ textAlign: "center", fontSize: 11, color: statusColor, fontWeight: 500 }}>{status}</div>
            </div>
          );
        })}
      </div>
    </div>
  );

  // ── CERTIFICATE ───────────────────────────────────────────────────────────
  if (screen === "certificate" && viewCertCourse) return (
    <div style={{ ...S.page, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", padding: "40px 20px", position: "relative" }}>
      <div style={{ position: "absolute", inset: 0, backgroundImage: "radial-gradient(ellipse 60% 40% at 50% 30%, rgba(212,175,106,0.1) 0%, transparent 70%)", pointerEvents: "none" }} />
      <button onClick={() => { if (activeCourse) setScreen("course"); else setScreen("transcript"); }}
        style={{ position: "absolute", top: 20, left: 20, background: "none", border: "none", color: "#5A5248", cursor: "pointer", fontSize: 13, fontFamily: "'DM Sans',sans-serif" }}>&#8592; Back</button>

      <div style={{ maxWidth: 600, width: "100%", position: "relative", zIndex: 1, padding: "48px 40px", borderRadius: 16, border: "2px solid rgba(212,175,106,0.3)", background: "linear-gradient(180deg, rgba(212,175,106,0.06) 0%, rgba(8,8,8,0.95) 100%)", textAlign: "center" }}>
        <div style={{ width: 60, height: 60, margin: "0 auto 20px", border: "2px solid #D4AF6A", borderRadius: 12, display: "flex", alignItems: "center", justifyContent: "center", fontSize: 28, color: "#D4AF6A", fontFamily: "'Cormorant Garamond',serif", fontWeight: 700 }}>R</div>
        <div style={{ fontSize: 10, letterSpacing: 6, color: "#D4AF6A", textTransform: "uppercase", marginBottom: 24 }}>Certificate of Completion</div>
        <div style={{ fontFamily: "'Cormorant Garamond',serif", fontSize: 14, color: "#5A5248", marginBottom: 8, fontStyle: "italic" }}>This certifies that</div>
        <div style={{ fontFamily: "'Cormorant Garamond',serif", fontSize: isMobile ? 28 : 36, fontWeight: 700, color: "#D4AF6A", marginBottom: 8 }}>{userName}</div>
        <div style={{ fontFamily: "'Cormorant Garamond',serif", fontSize: 14, color: "#5A5248", marginBottom: 24, fontStyle: "italic" }}>has successfully completed</div>
        <div style={{ fontFamily: "'Cormorant Garamond',serif", fontSize: isMobile ? 22 : 28, fontWeight: 700, color: "#EDE8DF", marginBottom: 8 }}>{viewCertCourse.title}</div>
        <div style={{ fontSize: 13, color: "#5A5248", marginBottom: 8 }}>{viewCertCourse.credits} Credit Hours - {viewCertCourse.units.length} Units</div>
        {getCourseGrade(viewCertCourse) && (
          <div style={{ fontSize: 16, color: "#D4AF6A", fontWeight: 700, marginBottom: 20 }}>Grade: {getCourseGrade(viewCertCourse).letter}</div>
        )}
        <div style={{ height: 1, background: "rgba(212,175,106,0.2)", margin: "20px 0" }} />
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <div style={{ fontSize: 11, color: "#3A3530" }}>Ravlo Academy</div>
          <div style={{ fontSize: 11, color: "#3A3530" }}>{new Date().toLocaleDateString()}</div>
        </div>
      </div>
    </div>
  );

  // ── COACH / CHAT ──────────────────────────────────────────────────────────
  if (screen === "coach") return (
    <div style={{ height: "100svh", display: "flex", flexDirection: "column", background: "#080808", fontFamily: "'DM Sans',sans-serif", color: "#EDE8DF" }}>

      {notification && <div style={{ position: "fixed", top: 20, right: 20, padding: "12px 20px", borderRadius: 8, background: "rgba(212,175,106,0.15)", border: "1px solid rgba(212,175,106,0.3)", color: "#D4AF6A", fontSize: 13, zIndex: 200, fontFamily: "'DM Sans',sans-serif" }}>{notification}</div>}

      <div style={{ padding: isMobile ? "12px 16px" : "16px 28px", borderBottom: "1px solid rgba(212,175,106,0.1)", display: "flex", alignItems: "center", justifyContent: "space-between", background: "rgba(8,8,8,0.95)", flexShrink: 0 }}>
        <div style={{ display: "flex", alignItems: "center", gap: isMobile ? 8 : 14 }}>
          <button onClick={() => { if (activeCourse) setScreen("course"); else setScreen("dashboard"); }} style={{ background: "none", border: "none", color: "#5A5248", cursor: "pointer", fontSize: 13, fontFamily: "'DM Sans',sans-serif", flexShrink: 0 }}>&#8592; {isMobile ? "" : "Back"}</button>
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
            <div style={{ width: 40, height: 40, borderRadius: "50%", background: "linear-gradient(135deg,#D4AF6A,#8A6A2A)", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 16, fontWeight: 700, color: "#080808", margin: "0 auto 12px" }}>AI</div>
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

      {/* Quick prompts */}
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
            style={{ width: isMobile ? 40 : 46, height: isMobile ? 40 : 46, borderRadius: 10, border: "none", background: chatInput.trim() && !loading ? "linear-gradient(135deg,#D4AF6A,#9A7A3A)" : "rgba(255,255,255,0.05)", color: chatInput.trim() && !loading ? "#080808" : "#3A3530", fontSize: 18, cursor: chatInput.trim() && !loading ? "pointer" : "not-allowed", flexShrink: 0, display: "flex", alignItems: "center", justifyContent: "center", transition: "all 0.2s" }}>&#8593;</button>
        </div>
        {!isMobile && <div style={{ fontSize: 10, color: "#2A2520", textAlign: "center", marginTop: 8, letterSpacing: 1 }}>ENTER TO SEND - SHIFT+ENTER FOR NEW LINE</div>}
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
