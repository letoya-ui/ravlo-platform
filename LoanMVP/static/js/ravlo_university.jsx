const { useState, useEffect, useRef } = React;

// ── Design tokens — aligned to ravlo_tokens.css brand foundation ───────────
const T = {
  bg: '#070c12', bgSoft: '#0c1116',
  panel: '#101821', panel2: '#131c26',
  border: 'rgba(255,255,255,0.07)', borderSoft: 'rgba(107,127,147,0.18)',
  text: '#ffffff', muted: 'rgba(255,255,255,0.58)', mutedDark: '#6B7F93',
  accent: '#3A5C7A', accentLight: '#5FA8FF', accentGlow: 'rgba(95,168,255,0.15)',
  success: '#2cb67d', warning: '#d1a246', danger: '#c46363',
  shadow: '0 18px 48px rgba(0,0,0,0.34)',
  radius: { sm: 12, md: 16, lg: 22, xl: 28 },
};

// ── Career tracks ──────────────────────────────────────────────────────────
const TRACKS = {
  investor: {
    label: 'Real Estate Investor', color: '#52d3a6', icon: '⬡',
    levels: [
      { title: 'Foundations of Investing', modules: [
        { id: 'inv-l1-m1', title: 'The Investor Mindset', lessons: [
          { title: 'How Wealth is Built Through Real Estate', desc: 'Core mechanics: appreciation, cash flow, equity, and tax advantages.' },
          { title: 'Types of Real Estate Investments', desc: 'SFR, multifamily, commercial, land, notes — risk/return profiles.' },
          { title: 'Setting Your Investment Criteria', desc: 'Define your buy box: market, price range, property type, return thresholds.' },
        ]},
        { id: 'inv-l1-m2', title: 'Market Fundamentals', lessons: [
          { title: 'Reading a Real Estate Market', desc: 'Supply, demand, absorption rates — buyer vs seller market signals.' },
          { title: 'Choosing Your Target Market', desc: 'Population growth, job diversity, affordability ratios, landlord-friendliness.' },
          { title: 'Neighborhood Analysis', desc: 'A/B/C/D neighborhoods, crime data, school ratings, rent-to-value ratios.' },
        ]},
      ]},
      { title: 'Finding & Analyzing Deals', modules: [
        { id: 'inv-l2-m1', title: 'Deal Sourcing', lessons: [
          { title: 'On-Market vs Off-Market Strategies', desc: 'MLS, wholesalers, direct mail, driving for dollars, agent relationships.' },
          { title: 'Working with Wholesalers', desc: 'Evaluating wholesale deals, building buyer lists, and protecting your MAO.' },
          { title: 'Building a Lead Pipeline', desc: 'CRM setup, follow-up sequences, and lead tracking systems.' },
        ]},
        { id: 'inv-l2-m2', title: 'Deal Analysis', lessons: [
          { title: 'Running the Numbers on Rentals', desc: 'NOI, cap rate, cash-on-cash return, GRM — step-by-step underwriting.' },
          { title: 'Estimating Repairs Accurately', desc: 'Scope of work, contractor bids, contingency buffers, and avoiding surprises.' },
          { title: 'The Maximum Allowable Offer Formula', desc: 'ARV-based pricing, assignment fees, rehab costs, and your profit margin.' },
        ]},
      ]},
      { title: 'Financing Your Deals', modules: [
        { id: 'inv-l3-m1', title: 'Conventional & Agency Loans', lessons: [
          { title: 'DSCR Loans for Investors', desc: 'Qualification, LTV, rates, and use cases for debt-service coverage ratio loans.' },
          { title: 'Fannie Mae Investment Guidelines', desc: '10-property rule, reserve requirements, and portfolio strategy.' },
          { title: 'Working with Lenders Effectively', desc: 'Pre-approval process, what lenders look for, and building banking relationships.' },
        ]},
        { id: 'inv-l3-m2', title: 'Creative Financing', lessons: [
          { title: 'Hard Money & Bridge Loans', desc: 'Short-term lending, points, ARV requirements, and exit strategies.' },
          { title: 'Seller Financing & Subject-To', desc: 'Structuring owner-carry deals, due-on-sale risks, and documentation.' },
          { title: 'Private Money & Partnerships', desc: 'Raising capital, investor agreements, preferred returns, JV structures.' },
        ]},
      ]},
      { title: 'BRRRR & Flipping', modules: [
        { id: 'inv-l4-m1', title: 'The BRRRR Method', lessons: [
          { title: 'BRRRR Step by Step', desc: 'Buy, Rehab, Rent, Refinance, Repeat — the complete cycle explained.' },
          { title: 'Managing Rehab Projects', desc: 'Contractor management, draw schedules, scope creep, and timelines.' },
          { title: 'The Cash-Out Refinance', desc: 'Seasoning requirements, LTV targets, and recycling your capital.' },
        ]},
        { id: 'inv-l4-m2', title: 'Fix & Flip', lessons: [
          { title: 'Flipping vs Holding — Decision Framework', desc: 'Tax implications, market timing, and personal cash flow needs.' },
          { title: 'Flip Budgeting & Project Management', desc: 'Timeline-to-profit, holding costs, and managing contractors.' },
          { title: 'Selling for Top Dollar', desc: 'Staging, pricing strategy, agent selection, and negotiation.' },
        ]},
      ]},
      { title: 'Portfolio & Scale', modules: [
        { id: 'inv-l5-m1', title: 'Building Systems', lessons: [
          { title: 'Property Management: Self vs Professional', desc: 'Cost analysis, tenant screening, maintenance systems, and your time.' },
          { title: 'Building Your Team', desc: 'Agents, lenders, CPAs, attorneys, property managers — who you need and when.' },
          { title: 'Depreciation & Cost Segregation', desc: 'Paper losses, bonus depreciation, and how investors pay little to no tax.' },
        ]},
      ]},
    ],
  },
  lending: {
    label: 'Lending Professional', color: '#59B7FF', icon: '◈',
    levels: [
      { title: 'Mortgage Fundamentals', modules: [
        { id: 'len-l1-m1', title: 'Loan Products & Programs', lessons: [
          { title: 'Conventional vs Government Loans', desc: 'FHA, VA, USDA, Conventional — eligibility, MI, limits, and use cases.' },
          { title: 'Understanding Loan Limits & Overlays', desc: 'Conforming limits, jumbo thresholds, lender-specific requirements.' },
          { title: 'Rate vs APR vs Points', desc: 'How pricing works, buy-down math, and presenting costs to borrowers.' },
        ]},
        { id: 'len-l1-m2', title: 'The Loan Process', lessons: [
          { title: 'Application to Clear-to-Close', desc: 'Every milestone from 1003 to funding: who does what and when.' },
          { title: 'Key Disclosures & Timelines', desc: 'LE, CD, 3-day rule, RESPA requirements, and compliance touchpoints.' },
          { title: 'Reading a Credit Report', desc: 'Tradelines, inquiries, derogatory marks, and rapid rescoring strategy.' },
        ]},
      ]},
      { title: 'Loan Officer Skills', modules: [
        { id: 'len-l2-m1', title: 'Client Qualification', lessons: [
          { title: 'Income Calculation: W2 & Salaried', desc: 'Base, overtime, bonus, and part-time income — what counts and what does not.' },
          { title: 'Self-Employed Income Analysis', desc: '1084 worksheet, 24-month average, and business income adjustments.' },
          { title: 'DTI & Residual Income', desc: 'Front-end, back-end ratios, VA residual income, and manual underwrite thresholds.' },
        ]},
        { id: 'len-l2-m2', title: 'Sales & Relationships', lessons: [
          { title: 'Building a Realtor Referral Network', desc: 'Value proposition, co-marketing, open houses, and maintaining relationships.' },
          { title: 'The Borrower Consultation Call', desc: 'Needs assessment, expectation setting, and creating pre-approval urgency.' },
          { title: 'Objection Handling for LOs', desc: 'Rate objections, "I will wait" objections, and competitor comparisons.' },
        ]},
      ]},
      { title: 'Loan Processing', modules: [
        { id: 'len-l3-m1', title: 'File Documentation', lessons: [
          { title: 'The Complete Loan Package', desc: 'Every document checklist: income, assets, identity, property, and title.' },
          { title: 'Ordering & Reviewing the Appraisal', desc: 'Ordering timeline, reviewing comps, contesting low appraisals.' },
          { title: 'Working Underwriting Conditions', desc: 'PTD vs PTC conditions, writing cover letters, and expediting approvals.' },
        ]},
      ]},
      { title: 'Underwriting Fundamentals', modules: [
        { id: 'len-l4-m1', title: 'The Four Cs of Credit', lessons: [
          { title: 'Capacity — Income Analysis Deep Dive', desc: 'Complex scenarios: rental income, commission, seasonal employment.' },
          { title: 'Collateral — Property Eligibility', desc: 'Non-warrantable condos, rural properties, manufactured homes, mixed-use.' },
          { title: 'DU & LP Deep Dive', desc: 'Reading AUS findings, message codes, and resubmission strategy.' },
        ]},
      ]},
      { title: 'Lending Leadership', modules: [
        { id: 'len-l5-m1', title: 'Branch & Team Management', lessons: [
          { title: 'Recruiting & Developing Loan Officers', desc: 'Compensation structures, onboarding plans, and production accountability.' },
          { title: 'Pipeline Management at Scale', desc: 'Team production tracking, pull-through rates, and bottleneck identification.' },
          { title: 'Compliance & Quality Control', desc: 'HMDA reporting, audit prep, and building a compliance-first culture.' },
        ]},
      ]},
    ],
  },
  realtor: {
    label: 'Real Estate Agent', color: '#ffd36f', icon: '◇',
    levels: [
      { title: 'Agent Foundations', modules: [
        { id: 'rea-l1-m1', title: 'Building Your Business', lessons: [
          { title: 'Your First 90 Days as an Agent', desc: 'Sphere of influence, database setup, and generating your first transaction.' },
          { title: 'Lead Generation Fundamentals', desc: 'Prospecting, open houses, online leads, and referral cultivation.' },
          { title: 'Time Blocking & Productivity', desc: 'Dollar-productive activities, non-negotiable blocks, and accountability systems.' },
        ]},
        { id: 'rea-l1-m2', title: 'Contract & Transaction Basics', lessons: [
          { title: 'Reading the Purchase Agreement', desc: 'Key contract terms: contingencies, timelines, earnest money, and default.' },
          { title: 'The Inspection Process', desc: 'Coordinating inspections, negotiating repairs, and managing client expectations.' },
          { title: 'Closing Day Coordination', desc: 'Title, lender, and settlement timelines — keeping everyone on track.' },
        ]},
      ]},
      { title: 'Buyer Representation', modules: [
        { id: 'rea-l2-m1', title: 'Working with Buyers', lessons: [
          { title: 'The Buyer Consultation', desc: 'Needs assessment, timeline, financing status, and buyer agency agreement.' },
          { title: 'Writing Competitive Offers', desc: 'Escalation clauses, appraisal gaps, waiving contingencies — and when not to.' },
          { title: 'Navigating Multiple Offers', desc: 'How to present, when to advise clients to walk, and closing on value.' },
        ]},
      ]},
      { title: 'Listings & Sellers', modules: [
        { id: 'rea-l3-m1', title: 'Winning Listings', lessons: [
          { title: 'The Listing Presentation', desc: 'CMA delivery, marketing plan, commission defense, and closing the listing.' },
          { title: 'Pricing Strategy', desc: 'Absorption rate analysis, days-on-market risk, and price reduction conversations.' },
          { title: 'Marketing & Photography', desc: 'Professional photography, MLS strategy, social media, and open house execution.' },
        ]},
      ]},
      { title: 'Building a Real Estate Business', modules: [
        { id: 'rea-l4-m1', title: 'Team & Brand Building', lessons: [
          { title: 'Solo Agent vs Team Model', desc: 'Economic comparison, leverage points, and when to hire your first assistant.' },
          { title: 'Your Personal Brand', desc: 'Niche selection, content strategy, becoming the local market expert.' },
          { title: 'Investor-Friendly Agent Skills', desc: 'Understanding investor math, DSCR properties, building an investor client base.' },
        ]},
      ]},
    ],
  },
  property_mgmt: {
    label: 'Property Manager', color: '#c4b5fd', icon: '▣',
    levels: [
      { title: 'PM Foundations', modules: [
        { id: 'pm-l1-m1', title: 'Landlord-Tenant Law', lessons: [
          { title: 'Fair Housing Compliance', desc: 'Protected classes, advertising rules, and screening criteria that survive audit.' },
          { title: 'Lease Agreements', desc: 'Key clauses, addenda, late fees, and what courts actually enforce.' },
          { title: 'Security Deposits & Move-In/Out', desc: 'Collection, holding, deduction documentation, and return timelines.' },
        ]},
        { id: 'pm-l1-m2', title: 'Tenant Screening', lessons: [
          { title: 'Building a Screening Criteria Document', desc: 'Income requirements, credit thresholds, rental history, criminal guidelines.' },
          { title: 'Running Background & Credit Checks', desc: 'Report interpretation, adverse action notices, and FCRA compliance.' },
          { title: 'The Showing & Application Process', desc: 'Self-showing technology, application collection, and first-come first-served.' },
        ]},
      ]},
      { title: 'Operations', modules: [
        { id: 'pm-l2-m1', title: 'Maintenance & Vendors', lessons: [
          { title: 'Preventive Maintenance Programs', desc: 'Annual inspection schedules, HVAC service, and roof/exterior cycles.' },
          { title: 'Building a Vendor Network', desc: 'Contractor vetting, pricing benchmarks, and preferred vendor agreements.' },
          { title: 'Maintenance Request Systems', desc: 'Work order software, tenant portal setup, and emergency response protocols.' },
        ]},
      ]},
      { title: 'Legal & Compliance', modules: [
        { id: 'pm-l3-m1', title: 'Evictions & Collections', lessons: [
          { title: 'The Eviction Process Step by Step', desc: 'Notice requirements, unlawful detainer, writ of possession, and timeline.' },
          { title: 'Collections After Eviction', desc: 'Judgment liens, collection agencies, credit reporting, and debt forgiveness.' },
          { title: 'Navigating Rent Control', desc: 'Jurisdictions, allowable increases, just-cause eviction requirements.' },
        ]},
      ]},
    ],
  },
  contractor: {
    label: 'Contractor / Builder', color: '#fb923c', icon: '◆',
    levels: [
      { title: 'Business Foundation', modules: [
        { id: 'con-l1-m1', title: 'Licensing & Operations', lessons: [
          { title: 'Licensing, Bonding & Insurance', desc: 'State requirements, general liability, workers comp, and surety bonds.' },
          { title: 'Business Entity & Accounting', desc: 'LLC structure, job costing, QuickBooks setup, separating business finances.' },
          { title: 'Contracts & Scope of Work', desc: 'Key clauses: payment schedule, change orders, lien waivers, and warranties.' },
        ]},
      ]},
      { title: 'Estimating & Bidding', modules: [
        { id: 'con-l2-m1', title: 'Accurate Estimating', lessons: [
          { title: 'Material Takeoffs', desc: 'Measuring and quantifying materials from plans or site visits.' },
          { title: 'Labor Pricing & Subcontractor Bids', desc: 'Unit pricing, sub markup, and protecting your margin.' },
          { title: 'Overhead & Profit in Your Bid', desc: 'True overhead calculation, target GP%, and presenting your price.' },
        ]},
      ]},
      { title: 'Project Management', modules: [
        { id: 'con-l3-m1', title: 'Managing Jobs', lessons: [
          { title: 'Scheduling & Critical Path', desc: 'Gantt charts, trade sequencing, lead times, and milestone tracking.' },
          { title: 'Managing Subcontractors', desc: 'Written agreements, lien waivers, quality inspections, and payment holdbacks.' },
          { title: 'Change Order Management', desc: 'Documenting scope changes, pricing changes, and client communication.' },
        ]},
      ]},
      { title: 'Growing the Business', modules: [
        { id: 'con-l4-m1', title: 'Working with Investors & Agents', lessons: [
          { title: 'Becoming an Investor-Preferred Contractor', desc: 'Scope of work literacy, rehab budgets, and reliable timelines as your brand.' },
          { title: 'Referral Networks & Repeat Business', desc: 'Building relationships with investors, agents, and property managers.' },
          { title: 'Scaling Your Crew', desc: 'Hiring, training, retention, and systems for running multiple jobs simultaneously.' },
        ]},
      ]},
    ],
  },
};

// ── Helpers ────────────────────────────────────────────────────────────────
const pKey = (moduleId, idx) => `${moduleId}:${idx}`;

async function apiFetch(url, opts) {
  const r = await fetch(url, opts);
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}

function trackProgress(track, progress) {
  let total = 0, done = 0;
  TRACKS[track].levels.forEach(lv => lv.modules.forEach(mod => {
    mod.lessons.forEach((_, i) => {
      total++;
      if (progress.completed[pKey(mod.id, i)]) done++;
    });
  }));
  return total ? Math.round((done / total) * 100) : 0;
}

function levelProgress(level, progress) {
  let total = 0, done = 0;
  level.modules.forEach(mod => mod.lessons.forEach((_, i) => {
    total++;
    if (progress.completed[pKey(mod.id, i)]) done++;
  }));
  return total ? Math.round((done / total) * 100) : 0;
}

// Render simple markdown: **Header** → h3, - item → bullet, else paragraph
function RichText({ text }) {
  if (!text) return null;
  const lines = text.split('\n');
  const nodes = [];
  let bullets = [];

  function flushBullets() {
    if (bullets.length) {
      nodes.push(
        <ul key={`ul-${nodes.length}`} style={{ margin: '8px 0 12px 0', paddingLeft: 20 }}>
          {bullets.map((b, i) => (
            <li key={i} style={{ color: T.muted, lineHeight: 1.7, marginBottom: 4, fontSize: 14 }}>{b}</li>
          ))}
        </ul>
      );
      bullets = [];
    }
  }

  lines.forEach((line, i) => {
    const trimmed = line.trim();
    if (!trimmed) { flushBullets(); return; }
    const hMatch = trimmed.match(/^\*\*(.+?)\*\*$/);
    if (hMatch) {
      flushBullets();
      nodes.push(
        <h3 key={i} style={{ color: T.text, fontSize: 15, fontWeight: 700, margin: '18px 0 8px', letterSpacing: '-0.3px' }}>
          {hMatch[1]}
        </h3>
      );
    } else if (trimmed.startsWith('- ')) {
      bullets.push(trimmed.slice(2));
    } else {
      flushBullets();
      nodes.push(
        <p key={i} style={{ color: T.muted, lineHeight: 1.75, marginBottom: 10, fontSize: 14 }}>{trimmed}</p>
      );
    }
  });
  flushBullets();
  return <div>{nodes}</div>;
}

// ── LandingGate ────────────────────────────────────────────────────────────
function LandingGate({ onAccess }) {
  const [code, setCode] = useState('');
  const [name, setName] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  async function handleSubmit(e) {
    e.preventDefault();
    if (!code.trim()) return;
    setLoading(true); setError('');
    try {
      const data = await apiFetch('/academy/activate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ code: code.trim(), name: name.trim() || 'Member' }),
      });
      onAccess(data.tier, data.name);
    } catch {
      setError('Access code not recognized. Contact your Ravlo representative.');
    } finally {
      setLoading(false);
    }
  }

  const inp = {
    width: '100%', padding: '12px 16px',
    background: T.panel2, border: `1px solid ${T.border}`,
    borderRadius: T.radius.md, color: T.text,
    fontSize: 14, outline: 'none', fontFamily: 'Inter, sans-serif',
  };

  return (
    <div style={{ minHeight: '100vh', background: `radial-gradient(circle at top left, rgba(54,115,255,.18), transparent 40%), linear-gradient(180deg,#06101d,#081322)`, display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 20 }}>
      <div style={{ width: '100%', maxWidth: 420 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 40 }}>
          <div style={{ width: 44, height: 44, borderRadius: 14, background: `linear-gradient(135deg,${T.accent},${T.accentLight})`, display: 'grid', placeItems: 'center', fontSize: 20, fontWeight: 900, color: '#fff' }}>R</div>
          <div>
            <div style={{ fontSize: 13, fontWeight: 800, letterSpacing: 3, color: T.text }}>RAVLO</div>
            <div style={{ fontSize: 9, letterSpacing: 3, color: T.muted, marginTop: 2 }}>ACADEMY OS</div>
          </div>
        </div>

        <div style={{ background: T.panel, border: `1px solid ${T.border}`, borderRadius: T.radius.xl, padding: 32, backdropFilter: 'blur(20px)' }}>
          <h1 style={{ fontSize: 24, fontWeight: 800, color: T.text, marginBottom: 8, letterSpacing: '-0.5px' }}>Enter Your Access Code</h1>
          <p style={{ color: T.muted, fontSize: 14, lineHeight: 1.6, marginBottom: 28 }}>Enter the code provided by your company or Ravlo representative to access the Academy.</p>

          <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
            <input style={inp} placeholder="Your name (optional)" value={name} onChange={e => setName(e.target.value)} />
            <input style={{ ...inp, textTransform: 'uppercase', letterSpacing: 2, fontWeight: 700 }} placeholder="ACCESS CODE" value={code} onChange={e => setCode(e.target.value.toUpperCase())} required />
            {error && <div style={{ color: T.danger, fontSize: 13, padding: '8px 12px', background: 'rgba(255,143,143,.08)', borderRadius: T.radius.sm }}>{error}</div>}
            <button type="submit" disabled={loading} style={{ padding: '13px 0', borderRadius: T.radius.md, background: `linear-gradient(135deg,${T.accent},#1F3A56)`, color: '#fff', fontWeight: 700, fontSize: 15, border: 'none', cursor: loading ? 'default' : 'pointer', opacity: loading ? 0.7 : 1, fontFamily: 'Inter, sans-serif', letterSpacing: 0.3 }}>
              {loading ? 'Verifying…' : 'Access Academy →'}
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}

// ── Sidebar ────────────────────────────────────────────────────────────────
function Sidebar({ track, setTrack, levelIdx, setLevelIdx, view, setView, progress, xp, userName, open, setOpen, isDesktop }) {
  const trackKeys = Object.keys(TRACKS);

  function selectTrack(key) {
    setTrack(key); setLevelIdx(0); setView('home'); if (!isDesktop) setOpen(false);
  }

  function selectLevel(i) {
    setLevelIdx(i); setView('level'); if (!isDesktop) setOpen(false);
  }

  const sideStyle = {
    position: 'fixed', top: 0, left: 0, bottom: 0, width: 280,
    background: 'linear-gradient(180deg,rgba(6,14,27,.97),rgba(8,17,31,.94))',
    borderRight: `1px solid ${T.border}`,
    display: 'flex', flexDirection: 'column',
    zIndex: 100,
    transform: (isDesktop || open) ? 'translateX(0)' : 'translateX(-100%)',
    transition: 'transform .25s cubic-bezier(.4,0,.2,1)',
  };

  const currentLevels = track ? TRACKS[track].levels : [];
  const trackColor = track ? TRACKS[track].color : T.accentLight;

  return (
    <>
      {!isDesktop && open && <div onClick={() => setOpen(false)} style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,.5)', zIndex: 99, backdropFilter: 'blur(2px)' }} />}
      <div style={sideStyle}>
        {/* Brand */}
        <div style={{ padding: '20px 20px 16px', borderBottom: `1px solid ${T.borderSoft}` }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <div style={{ width: 38, height: 38, borderRadius: 12, background: `linear-gradient(135deg,${T.accent},${T.accentLight})`, display: 'grid', placeItems: 'center', fontSize: 18, fontWeight: 900, color: '#fff', flexShrink: 0 }}>R</div>
            <div>
              <div style={{ fontSize: 12, fontWeight: 800, letterSpacing: 3, color: T.text }}>RAVLO</div>
              <div style={{ fontSize: 8, letterSpacing: 3, color: T.mutedDark }}>ACADEMY OS</div>
            </div>
          </div>
          {userName && <div style={{ marginTop: 12, fontSize: 12, color: T.muted }}>Welcome, <strong style={{ color: T.text }}>{userName}</strong></div>}
          <div style={{ marginTop: 8, display: 'flex', alignItems: 'center', gap: 6 }}>
            <div style={{ flex: 1, height: 4, background: T.borderSoft, borderRadius: 2 }}>
              <div style={{ height: '100%', width: `${Math.min((xp / 500) * 100, 100)}%`, background: `linear-gradient(90deg,${T.accent},${T.accentLight})`, borderRadius: 2, transition: 'width .5s' }} />
            </div>
            <span style={{ fontSize: 11, color: T.accentLight, fontWeight: 700 }}>{xp} XP</span>
          </div>
        </div>

        {/* Track nav */}
        <div style={{ padding: '14px 12px 8px', flex: 1, overflowY: 'auto' }}>
          <div style={{ fontSize: 10, letterSpacing: 2, color: T.mutedDark, fontWeight: 700, padding: '0 8px', marginBottom: 8 }}>CAREER TRACKS</div>
          {trackKeys.map(key => {
            const tr = TRACKS[key];
            const isActive = track === key;
            const pct = trackProgress(key, progress);
            return (
              <div key={key}>
                <button onClick={() => selectTrack(key)} style={{ width: '100%', display: 'flex', alignItems: 'center', gap: 10, padding: '9px 10px', borderRadius: T.radius.md, background: isActive ? `rgba(${tr.color === '#52d3a6' ? '82,211,166' : tr.color === '#59B7FF' ? '89,183,255' : tr.color === '#ffd36f' ? '255,211,111' : tr.color === '#c4b5fd' ? '196,181,253' : '251,146,60'},.1)` : 'transparent', border: isActive ? `1px solid rgba(255,255,255,.1)` : '1px solid transparent', cursor: 'pointer', textAlign: 'left', transition: 'all .15s' }}>
                  <span style={{ fontSize: 16, color: tr.color, flexShrink: 0 }}>{tr.icon}</span>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ fontSize: 12, fontWeight: isActive ? 700 : 500, color: isActive ? T.text : T.muted, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{tr.label}</div>
                    {pct > 0 && <div style={{ fontSize: 10, color: tr.color, marginTop: 2 }}>{pct}% complete</div>}
                  </div>
                </button>

                {isActive && currentLevels.map((lv, i) => {
                  const lvPct = levelProgress(lv, progress);
                  const isLvActive = levelIdx === i && (view === 'level' || view === 'lesson');
                  return (
                    <button key={i} onClick={() => selectLevel(i)} style={{ width: '100%', display: 'flex', alignItems: 'center', gap: 8, padding: '7px 10px 7px 32px', borderRadius: T.radius.sm, background: isLvActive ? T.panel2 : 'transparent', border: 'none', cursor: 'pointer', textAlign: 'left', transition: 'all .15s', marginTop: 2 }}>
                      <div style={{ width: 18, height: 18, borderRadius: 6, background: lvPct === 100 ? T.success : isLvActive ? trackColor : T.borderSoft, flexShrink: 0, display: 'grid', placeItems: 'center', fontSize: 9, fontWeight: 800, color: '#07111f' }}>
                        {lvPct === 100 ? '✓' : i + 1}
                      </div>
                      <span style={{ fontSize: 11, color: isLvActive ? T.text : T.muted, fontWeight: isLvActive ? 600 : 400, lineHeight: 1.3 }}>{lv.title}</span>
                    </button>
                  );
                })}
              </div>
            );
          })}

          {/* AI Coach */}
          <div style={{ marginTop: 16, paddingTop: 12, borderTop: `1px solid ${T.borderSoft}` }}>
            <button onClick={() => { setView('coach'); setOpen(false); }} style={{ width: '100%', display: 'flex', alignItems: 'center', gap: 10, padding: '10px', borderRadius: T.radius.md, background: view === 'coach' ? T.accentGlow : 'transparent', border: view === 'coach' ? `1px solid ${T.accentLight}30` : '1px solid transparent', cursor: 'pointer', transition: 'all .15s' }}>
              <span style={{ fontSize: 18 }}>◎</span>
              <div style={{ textAlign: 'left' }}>
                <div style={{ fontSize: 12, fontWeight: 700, color: view === 'coach' ? T.accentLight : T.muted }}>AI Coach</div>
                <div style={{ fontSize: 10, color: T.mutedDark }}>Ask anything</div>
              </div>
            </button>
          </div>
        </div>
      </div>
    </>
  );
}

// ── TrackHome ──────────────────────────────────────────────────────────────
function TrackHome({ track, setLevelIdx, setView, progress }) {
  const tr = TRACKS[track];
  const pct = trackProgress(track, progress);
  let doneLessons = 0, totalLessons = 0;
  tr.levels.forEach(lv => lv.modules.forEach(mod => {
    mod.lessons.forEach((_, i) => {
      totalLessons++;
      if (progress.completed[pKey(mod.id, i)]) doneLessons++;
    });
  }));

  return (
    <div>
      {/* Hero */}
      <div style={{ background: `linear-gradient(135deg,rgba(10,20,36,.9),rgba(6,14,27,.95))`, border: `1px solid ${T.border}`, borderRadius: T.radius.xl, padding: '32px 36px', marginBottom: 24, position: 'relative', overflow: 'hidden' }}>
        <div style={{ position: 'absolute', top: -30, right: -30, width: 160, height: 160, borderRadius: '50%', background: `radial-gradient(circle,${tr.color}22,transparent 70%)`, pointerEvents: 'none' }} />
        <div style={{ fontSize: 11, letterSpacing: 2.5, color: tr.color, fontWeight: 800, marginBottom: 10 }}>CAREER TRACK</div>
        <h1 style={{ fontSize: 30, fontWeight: 800, color: T.text, marginBottom: 10, letterSpacing: '-0.5px' }}>{tr.label}</h1>
        <div style={{ display: 'flex', alignItems: 'center', gap: 16, flexWrap: 'wrap' }}>
          <div style={{ fontSize: 13, color: T.muted }}>{doneLessons} of {totalLessons} lessons complete</div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, flex: 1, minWidth: 120 }}>
            <div style={{ flex: 1, height: 6, background: T.borderSoft, borderRadius: 3 }}>
              <div style={{ height: '100%', width: `${pct}%`, background: `linear-gradient(90deg,${tr.color},${tr.color}99)`, borderRadius: 3, transition: 'width .5s' }} />
            </div>
            <span style={{ fontSize: 13, color: tr.color, fontWeight: 700 }}>{pct}%</span>
          </div>
        </div>
      </div>

      {/* Level cards */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill,minmax(280px,1fr))', gap: 16 }}>
        {tr.levels.map((lv, i) => {
          const lvPct = levelProgress(lv, progress);
          const totalM = lv.modules.reduce((a, m) => a + m.lessons.length, 0);
          const doneM = lv.modules.reduce((a, m) => a + m.lessons.filter((_, li) => progress.completed[pKey(m.id, li)]).length, 0);
          return (
            <button key={i} onClick={() => { setLevelIdx(i); setView('level'); }} style={{ textAlign: 'left', background: T.panel, border: `1px solid ${T.border}`, borderRadius: T.radius.lg, padding: '22px 24px', cursor: 'pointer', transition: 'border-color .15s, box-shadow .15s', position: 'relative', overflow: 'hidden' }}
              onMouseEnter={e => { e.currentTarget.style.borderColor = `${tr.color}60`; e.currentTarget.style.boxShadow = T.shadow; }}
              onMouseLeave={e => { e.currentTarget.style.borderColor = T.border; e.currentTarget.style.boxShadow = 'none'; }}>
              <div style={{ position: 'absolute', top: 0, left: 0, height: 3, width: `${lvPct}%`, background: tr.color, transition: 'width .5s' }} />
              <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 12 }}>
                <div style={{ width: 32, height: 32, borderRadius: 10, background: lvPct === 100 ? T.success : T.borderSoft, display: 'grid', placeItems: 'center', fontSize: 13, fontWeight: 800, color: lvPct === 100 ? '#07111f' : T.muted, flexShrink: 0 }}>
                  {lvPct === 100 ? '✓' : `L${i + 1}`}
                </div>
                <div style={{ fontSize: 11, letterSpacing: 1.5, color: tr.color, fontWeight: 700 }}>LEVEL {i + 1}</div>
              </div>
              <div style={{ fontSize: 16, fontWeight: 700, color: T.text, marginBottom: 6, lineHeight: 1.3 }}>{lv.title}</div>
              <div style={{ fontSize: 12, color: T.muted }}>{lv.modules.length} modules · {totalM} lessons</div>
              {lvPct > 0 && lvPct < 100 && (
                <div style={{ marginTop: 10, fontSize: 11, color: tr.color }}>{doneM}/{totalM} lessons done</div>
              )}
            </button>
          );
        })}
      </div>
    </div>
  );
}

// ── LevelView ──────────────────────────────────────────────────────────────
function LevelView({ track, levelIdx, setView, setLesson, progress }) {
  const tr = TRACKS[track];
  const level = tr.levels[levelIdx];
  const [openMod, setOpenMod] = useState(0);

  return (
    <div>
      <button onClick={() => setView('home')} style={{ display: 'flex', alignItems: 'center', gap: 6, color: T.muted, background: 'none', border: 'none', cursor: 'pointer', fontSize: 13, marginBottom: 20, padding: 0 }}>
        ← Back to {tr.label}
      </button>

      <div style={{ marginBottom: 24 }}>
        <div style={{ fontSize: 11, letterSpacing: 2, color: tr.color, fontWeight: 700, marginBottom: 6 }}>LEVEL {levelIdx + 1}</div>
        <h2 style={{ fontSize: 26, fontWeight: 800, color: T.text, letterSpacing: '-0.5px' }}>{level.title}</h2>
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
        {level.modules.map((mod, mi) => {
          const isOpen = openMod === mi;
          const modDone = mod.lessons.filter((_, i) => progress.completed[pKey(mod.id, i)]).length;
          return (
            <div key={mod.id} style={{ background: T.panel, border: `1px solid ${T.border}`, borderRadius: T.radius.lg, overflow: 'hidden' }}>
              <button onClick={() => setOpenMod(isOpen ? -1 : mi)} style={{ width: '100%', display: 'flex', alignItems: 'center', gap: 14, padding: '18px 22px', background: 'none', border: 'none', cursor: 'pointer', textAlign: 'left' }}>
                <div style={{ flex: 1 }}>
                  <div style={{ fontSize: 15, fontWeight: 700, color: T.text }}>{mod.title}</div>
                  <div style={{ fontSize: 12, color: T.muted, marginTop: 3 }}>{modDone}/{mod.lessons.length} lessons complete</div>
                </div>
                <span style={{ color: T.muted, fontSize: 18, transform: isOpen ? 'rotate(180deg)' : 'none', transition: 'transform .2s' }}>⌄</span>
              </button>

              {isOpen && (
                <div style={{ borderTop: `1px solid ${T.borderSoft}`, padding: '8px 0' }}>
                  {mod.lessons.map((lesson, li) => {
                    const done = !!progress.completed[pKey(mod.id, li)];
                    return (
                      <button key={li} onClick={() => { setLesson({ moduleId: mod.id, lessonIndex: li, title: lesson.title, desc: lesson.desc, moduleTitle: mod.title, trackLabel: tr.label }); setView('lesson'); }}
                        style={{ width: '100%', display: 'flex', alignItems: 'center', gap: 14, padding: '13px 22px', background: 'none', border: 'none', cursor: 'pointer', textAlign: 'left', transition: 'background .15s' }}
                        onMouseEnter={e => e.currentTarget.style.background = T.panel2}
                        onMouseLeave={e => e.currentTarget.style.background = 'none'}>
                        <div style={{ width: 24, height: 24, borderRadius: 8, background: done ? T.success : T.borderSoft, display: 'grid', placeItems: 'center', fontSize: 11, fontWeight: 800, color: done ? '#07111f' : T.muted, flexShrink: 0 }}>
                          {done ? '✓' : li + 1}
                        </div>
                        <div style={{ flex: 1 }}>
                          <div style={{ fontSize: 14, fontWeight: done ? 500 : 600, color: done ? T.muted : T.text }}>{lesson.title}</div>
                          <div style={{ fontSize: 12, color: T.mutedDark, marginTop: 2 }}>{lesson.desc}</div>
                        </div>
                        <span style={{ color: T.muted, fontSize: 13 }}>→</span>
                      </button>
                    );
                  })}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ── LessonViewer ───────────────────────────────────────────────────────────
function LessonViewer({ lesson, track, levelIdx, progress, onComplete, onBack }) {
  const tr = TRACKS[track];
  const level = tr.levels[levelIdx];
  const [content, setContent] = useState(null);
  const [loadErr, setLoadErr] = useState('');
  const [answers, setAnswers] = useState({});
  const [submitted, setSubmitted] = useState(false);
  const [completing, setCompleting] = useState(false);
  const alreadyDone = !!progress.completed[pKey(lesson.moduleId, lesson.lessonIndex)];

  useEffect(() => {
    setContent(null); setLoadErr(''); setAnswers({}); setSubmitted(false);
    const lessonId = `${lesson.moduleId}-${lesson.lessonIndex}`;
    apiFetch('/academy/lesson-content', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ lesson_id: lessonId, title: lesson.title, description: lesson.desc, course_title: tr.label, unit_title: lesson.moduleTitle }),
    }).then(d => setContent(d)).catch(() => setLoadErr('Could not load lesson content. Please try again.'));
  }, [lesson.moduleId, lesson.lessonIndex]);

  async function handleComplete() {
    if (alreadyDone || completing) return;
    setCompleting(true);
    await onComplete(lesson.moduleId, lesson.lessonIndex);
    setCompleting(false);
  }

  const quiz = content && content.quiz;
  const allAnswered = quiz && Object.keys(answers).length === quiz.length;
  const quizScore = submitted && quiz ? quiz.filter((q, i) => answers[i] === q.correctIndex).length : 0;

  return (
    <div>
      <button onClick={onBack} style={{ display: 'flex', alignItems: 'center', gap: 6, color: T.muted, background: 'none', border: 'none', cursor: 'pointer', fontSize: 13, marginBottom: 20, padding: 0 }}>
        ← {level.title}
      </button>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 280px', gap: 24, alignItems: 'start' }}>
        {/* Main column */}
        <div>
          <div style={{ background: T.panel, border: `1px solid ${T.border}`, borderRadius: T.radius.xl, padding: '28px 32px', marginBottom: 20 }}>
            <div style={{ fontSize: 11, letterSpacing: 2, color: tr.color, fontWeight: 700, marginBottom: 8 }}>{lesson.moduleTitle}</div>
            <h1 style={{ fontSize: 22, fontWeight: 800, color: T.text, marginBottom: 8, letterSpacing: '-0.4px', lineHeight: 1.3 }}>{lesson.title}</h1>
            <p style={{ color: T.muted, fontSize: 13, lineHeight: 1.6 }}>{lesson.desc}</p>
          </div>

          <div style={{ background: T.panel, border: `1px solid ${T.border}`, borderRadius: T.radius.xl, padding: '28px 32px', marginBottom: 20 }}>
            {!content && !loadErr && (
              <div style={{ display: 'flex', alignItems: 'center', gap: 10, color: T.muted, fontSize: 13 }}>
                <div style={{ width: 16, height: 16, border: `2px solid ${T.accentLight}30`, borderTopColor: T.accentLight, borderRadius: '50%', animation: 'spin .8s linear infinite' }} />
                Generating lesson content…
              </div>
            )}
            {loadErr && <div style={{ color: T.danger, fontSize: 14 }}>{loadErr}</div>}
            {content && <RichText text={content.content} />}
          </div>

          {/* Quiz */}
          {content && quiz && (
            <div style={{ background: T.panel, border: `1px solid ${T.border}`, borderRadius: T.radius.xl, padding: '28px 32px' }}>
              <h3 style={{ fontSize: 16, fontWeight: 800, color: T.text, marginBottom: 20 }}>Knowledge Check</h3>
              {quiz.map((q, qi) => (
                <div key={qi} style={{ marginBottom: 24 }}>
                  <div style={{ fontSize: 14, fontWeight: 600, color: T.text, marginBottom: 12 }}>{qi + 1}. {q.question}</div>
                  {q.options.map((opt, oi) => {
                    const sel = answers[qi] === oi;
                    const isCorrect = q.correctIndex === oi;
                    let bg = T.panel2, border = T.border, color = T.muted;
                    if (sel && !submitted) { bg = T.accentGlow; border = `${T.accentLight}60`; color = T.text; }
                    if (submitted && isCorrect) { bg = 'rgba(82,211,166,.1)'; border = `${T.success}60`; color = T.success; }
                    if (submitted && sel && !isCorrect) { bg = 'rgba(255,143,143,.08)'; border = `${T.danger}60`; color = T.danger; }
                    return (
                      <button key={oi} disabled={submitted} onClick={() => setAnswers(a => ({ ...a, [qi]: oi }))}
                        style={{ width: '100%', display: 'flex', alignItems: 'center', gap: 10, padding: '10px 14px', marginBottom: 8, borderRadius: T.radius.md, background: bg, border: `1px solid ${border}`, cursor: submitted ? 'default' : 'pointer', textAlign: 'left', color, fontSize: 13, fontFamily: 'Inter, sans-serif', transition: 'all .15s' }}>
                        <div style={{ width: 22, height: 22, borderRadius: 6, border: `1px solid ${border}`, display: 'grid', placeItems: 'center', fontSize: 11, fontWeight: 700, color, flexShrink: 0 }}>
                          {String.fromCharCode(65 + oi)}
                        </div>
                        {opt}
                      </button>
                    );
                  })}
                  {submitted && q.explanation && (
                    <div style={{ marginTop: 8, padding: '10px 14px', background: 'rgba(255,255,255,.03)', borderRadius: T.radius.sm, fontSize: 12, color: T.muted, lineHeight: 1.6 }}>
                      {q.explanation}
                    </div>
                  )}
                </div>
              ))}

              {!submitted ? (
                <button disabled={!allAnswered} onClick={() => setSubmitted(true)} style={{ padding: '12px 28px', borderRadius: T.radius.md, background: allAnswered ? `linear-gradient(135deg,${T.accent},#1F3A56)` : T.borderSoft, color: allAnswered ? '#fff' : T.muted, fontWeight: 700, fontSize: 14, border: 'none', cursor: allAnswered ? 'pointer' : 'default', fontFamily: 'Inter, sans-serif' }}>
                  Submit Answers
                </button>
              ) : (
                <div style={{ display: 'flex', alignItems: 'center', gap: 16, flexWrap: 'wrap' }}>
                  <div style={{ fontSize: 15, fontWeight: 700, color: quizScore === quiz.length ? T.success : T.warning }}>
                    {quizScore}/{quiz.length} correct
                  </div>
                  {!alreadyDone && (
                    <button onClick={handleComplete} disabled={completing} style={{ padding: '11px 24px', borderRadius: T.radius.md, background: `linear-gradient(135deg,${T.success},#36b88a)`, color: '#07111f', fontWeight: 800, fontSize: 14, border: 'none', cursor: completing ? 'default' : 'pointer', fontFamily: 'Inter, sans-serif', opacity: completing ? 0.7 : 1 }}>
                      {completing ? 'Saving…' : '✓ Mark Complete +10 XP'}
                    </button>
                  )}
                  {alreadyDone && <span style={{ fontSize: 13, color: T.success }}>✓ Completed</span>}
                </div>
              )}
            </div>
          )}
        </div>

        {/* Key points sidebar */}
        <div style={{ position: 'sticky', top: 20 }}>
          {content && content.keyPoints && (
            <div style={{ background: T.panel, border: `1px solid ${T.border}`, borderRadius: T.radius.lg, padding: '22px 24px' }}>
              <div style={{ fontSize: 11, letterSpacing: 2, color: tr.color, fontWeight: 700, marginBottom: 14 }}>KEY POINTS</div>
              {content.keyPoints.map((pt, i) => (
                <div key={i} style={{ display: 'flex', gap: 10, marginBottom: 12 }}>
                  <div style={{ width: 20, height: 20, borderRadius: 6, background: `${tr.color}20`, display: 'grid', placeItems: 'center', fontSize: 10, fontWeight: 800, color: tr.color, flexShrink: 0, marginTop: 1 }}>{i + 1}</div>
                  <span style={{ fontSize: 13, color: T.muted, lineHeight: 1.5 }}>{pt}</span>
                </div>
              ))}
            </div>
          )}

          {alreadyDone && (
            <div style={{ marginTop: 14, background: 'rgba(82,211,166,.08)', border: `1px solid ${T.success}40`, borderRadius: T.radius.lg, padding: '16px 20px', textAlign: 'center' }}>
              <div style={{ fontSize: 20, marginBottom: 4 }}>✓</div>
              <div style={{ fontSize: 13, color: T.success, fontWeight: 700 }}>Lesson Complete</div>
            </div>
          )}
        </div>
      </div>
      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
    </div>
  );
}

// ── AICoach ────────────────────────────────────────────────────────────────
function AICoach({ track, tier, userName }) {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const bottomRef = useRef(null);
  const tr = track ? TRACKS[track] : null;

  const systemPrompt = `You are the Ravlo Academy AI Coach — a real estate expert and mentor for ${tr ? tr.label + 's' : 'real estate professionals'}.
The user's name is ${userName || 'a member'} and they have ${tier} access.
Be direct, specific, and practitioner-focused. Give actionable advice grounded in real-world real estate.
Never give generic advice. Always tie recommendations to actual numbers, strategies, or processes.`;

  useEffect(() => {
    if (bottomRef.current) bottomRef.current.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  async function sendMessage() {
    if (!input.trim() || loading) return;
    const userMsg = { role: 'user', content: input.trim() };
    const newMessages = [...messages, userMsg];
    setMessages(newMessages); setInput(''); setLoading(true);
    try {
      const data = await apiFetch('/academy/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ model: 'claude-haiku-4-5-20251001', max_tokens: 800, system: systemPrompt, messages: newMessages }),
      });
      const text = (data.content || [{}])[0].text || '';
      setMessages(m => [...m, { role: 'assistant', content: text }]);
    } catch {
      setMessages(m => [...m, { role: 'assistant', content: 'I encountered an issue. Please try again.' }]);
    } finally {
      setLoading(false);
    }
  }

  const starters = ['How do I analyze my first rental property?', 'Explain DSCR loans in simple terms', 'What should I look for in a target market?', 'How do I calculate ARV?'];

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: 'calc(100vh - 48px)' }}>
      <div style={{ marginBottom: 20 }}>
        <div style={{ fontSize: 11, letterSpacing: 2, color: T.accentLight, fontWeight: 700, marginBottom: 6 }}>AI COACH</div>
        <h2 style={{ fontSize: 22, fontWeight: 800, color: T.text }}>Ask Your Coach</h2>
        {tr && <p style={{ color: T.muted, fontSize: 13, marginTop: 4 }}>Focused on {tr.label} strategies</p>}
      </div>

      <div style={{ flex: 1, overflowY: 'auto', background: T.panel, border: `1px solid ${T.border}`, borderRadius: T.radius.xl, padding: 20, display: 'flex', flexDirection: 'column', gap: 14, marginBottom: 14 }}>
        {messages.length === 0 && (
          <div style={{ flex: 1, display: 'flex', flexDirection: 'column', justifyContent: 'center', alignItems: 'center', gap: 20, padding: 20 }}>
            <div style={{ width: 60, height: 60, borderRadius: 20, background: T.accentGlow, border: `1px solid ${T.accentLight}30`, display: 'grid', placeItems: 'center', fontSize: 28 }}>◎</div>
            <p style={{ color: T.muted, fontSize: 14, textAlign: 'center', maxWidth: 320, lineHeight: 1.6 }}>
              Your AI coach is ready. Ask about strategies, deal analysis, market research, financing, and more.
            </p>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, justifyContent: 'center' }}>
              {starters.map((s, i) => (
                <button key={i} onClick={() => { setInput(s); }} style={{ padding: '8px 14px', borderRadius: T.radius.md, background: T.panel2, border: `1px solid ${T.border}`, color: T.muted, fontSize: 12, cursor: 'pointer', fontFamily: 'Inter, sans-serif' }}>{s}</button>
              ))}
            </div>
          </div>
        )}
        {messages.map((msg, i) => (
          <div key={i} style={{ display: 'flex', justifyContent: msg.role === 'user' ? 'flex-end' : 'flex-start', gap: 10 }}>
            {msg.role === 'assistant' && (
              <div style={{ width: 30, height: 30, borderRadius: 10, background: T.accentGlow, border: `1px solid ${T.accentLight}30`, display: 'grid', placeItems: 'center', fontSize: 14, flexShrink: 0, alignSelf: 'flex-end' }}>◎</div>
            )}
            <div style={{ maxWidth: '78%', padding: '12px 16px', borderRadius: msg.role === 'user' ? `${T.radius.lg}px ${T.radius.lg}px 6px ${T.radius.lg}px` : `${T.radius.lg}px ${T.radius.lg}px ${T.radius.lg}px 6px`, background: msg.role === 'user' ? `linear-gradient(135deg,${T.accent},#1F3A56)` : T.panel2, border: msg.role === 'user' ? 'none' : `1px solid ${T.border}`, fontSize: 14, color: T.text, lineHeight: 1.65, whiteSpace: 'pre-wrap' }}>
              {msg.content}
            </div>
          </div>
        ))}
        {loading && (
          <div style={{ display: 'flex', gap: 10 }}>
            <div style={{ width: 30, height: 30, borderRadius: 10, background: T.accentGlow, border: `1px solid ${T.accentLight}30`, display: 'grid', placeItems: 'center', fontSize: 14 }}>◎</div>
            <div style={{ padding: '12px 16px', background: T.panel2, border: `1px solid ${T.border}`, borderRadius: T.radius.lg, display: 'flex', gap: 6, alignItems: 'center' }}>
              {[0, 1, 2].map(d => <div key={d} style={{ width: 6, height: 6, borderRadius: '50%', background: T.muted, animation: `dot .8s ${d * 0.2}s ease-in-out infinite` }} />)}
            </div>
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      <div style={{ display: 'flex', gap: 10 }}>
        <input value={input} onChange={e => setInput(e.target.value)} onKeyDown={e => e.key === 'Enter' && !e.shiftKey && sendMessage()}
          placeholder="Ask your coach anything…"
          style={{ flex: 1, padding: '13px 18px', background: T.panel, border: `1px solid ${T.border}`, borderRadius: T.radius.lg, color: T.text, fontSize: 14, outline: 'none', fontFamily: 'Inter, sans-serif' }} />
        <button onClick={sendMessage} disabled={loading || !input.trim()} style={{ padding: '0 22px', borderRadius: T.radius.lg, background: input.trim() ? `linear-gradient(135deg,${T.accent},#1F3A56)` : T.borderSoft, color: input.trim() ? '#fff' : T.muted, border: 'none', cursor: input.trim() ? 'pointer' : 'default', fontWeight: 700, fontSize: 20, fontFamily: 'Inter, sans-serif' }}>→</button>
      </div>
      <style>{`@keyframes dot { 0%,80%,100%{opacity:.3;transform:scale(.8)} 40%{opacity:1;transform:scale(1)} }`}</style>
    </div>
  );
}

// ── App ────────────────────────────────────────────────────────────────────
function App() {
  const init = window.RAVLO_ACADEMY || {};
  const [tier, setTier] = useState(init.tier || null);
  const [userName, setUserName] = useState(init.userName || '');
  const [track, setTrack] = useState('investor');
  const [levelIdx, setLevelIdx] = useState(0);
  const [view, setView] = useState('home');
  const [lesson, setLesson] = useState(null);
  const [progress, setProgress] = useState({ completed: {}, xp: 0 });
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [isDesktop, setIsDesktop] = useState(window.innerWidth >= 768);

  useEffect(() => {
    function onResize() { setIsDesktop(window.innerWidth >= 768); }
    window.addEventListener('resize', onResize);
    return () => window.removeEventListener('resize', onResize);
  }, []);

  useEffect(() => {
    if (!tier) return;
    apiFetch('/academy/api/progress').then(d => setProgress(d)).catch(() => {});
  }, [tier]);

  function handleAccess(newTier, newName) {
    setTier(newTier); setUserName(newName);
  }

  async function handleComplete(moduleId, lessonIndex) {
    try {
      await apiFetch('/academy/api/progress/complete', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ module_id: moduleId, lesson_index: lessonIndex }),
      });
      setProgress(p => ({
        completed: { ...p.completed, [pKey(moduleId, lessonIndex)]: true },
        xp: p.xp + 10,
      }));
    } catch {}
  }

  if (!tier) return <LandingGate onAccess={handleAccess} />;

  const bgStyle = {
    minHeight: '100vh',
    background: 'radial-gradient(circle at top left,rgba(54,115,255,.18),transparent 40%), linear-gradient(180deg,#06101d,#081322)',
    fontFamily: 'Inter, sans-serif',
    color: T.text,
  };

  function renderMain() {
    if (view === 'coach') return <AICoach track={track} tier={tier} userName={userName} />;
    if (view === 'lesson' && lesson) return (
      <LessonViewer lesson={lesson} track={track} levelIdx={levelIdx} progress={progress} onComplete={handleComplete} onBack={() => setView('level')} />
    );
    if (view === 'level') return (
      <LevelView track={track} levelIdx={levelIdx} setView={setView} setLesson={setLesson} progress={progress} />
    );
    return <TrackHome track={track} setLevelIdx={setLevelIdx} setView={setView} progress={progress} />;
  }

  return (
    <div style={bgStyle}>
      <Sidebar track={track} setTrack={setTrack} levelIdx={levelIdx} setLevelIdx={setLevelIdx} view={view} setView={setView} progress={progress} xp={progress.xp} userName={userName} open={sidebarOpen} setOpen={setSidebarOpen} isDesktop={isDesktop} />

      {/* Topbar */}
      <div style={{ position: 'fixed', top: 0, left: isDesktop ? 280 : 0, right: 0, height: 52, background: 'rgba(7,17,31,.92)', borderBottom: `1px solid ${T.border}`, backdropFilter: 'blur(12px)', display: 'flex', alignItems: 'center', padding: '0 24px', gap: 12, zIndex: 50 }}>
        <button onClick={() => setSidebarOpen(true)} style={{ display: isDesktop ? 'none' : 'block', background: 'none', border: 'none', color: T.muted, cursor: 'pointer', fontSize: 22, padding: 0, lineHeight: 1 }}>≡</button>
        <span style={{ fontSize: 12, color: T.muted }}>{TRACKS[track]?.label}</span>
        {view !== 'home' && view !== 'coach' && <><span style={{ color: T.mutedDark }}>›</span><span style={{ fontSize: 12, color: T.muted }}>{TRACKS[track]?.levels[levelIdx]?.title}</span></>}
        {view === 'lesson' && lesson && <><span style={{ color: T.mutedDark }}>›</span><span style={{ fontSize: 12, color: T.text, fontWeight: 600 }}>{lesson.title}</span></>}
        <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 8 }}>
          <span style={{ fontSize: 12, color: T.accentLight, fontWeight: 700 }}>{progress.xp} XP</span>
          {tier && <div style={{ padding: '3px 10px', borderRadius: 20, background: T.accentGlow, border: `1px solid ${T.accentLight}30`, fontSize: 10, color: T.accentLight, fontWeight: 700, letterSpacing: 1 }}>{tier.toUpperCase()}</div>}
        </div>
      </div>

      {/* Content */}
      <div style={{ marginLeft: isDesktop ? 280 : 0, paddingTop: 52 }}>
        <div style={{ padding: isDesktop ? '28px 32px' : '20px 16px', maxWidth: 1000 }}>
          {renderMain()}
        </div>
      </div>
    </div>
  );
}

ReactDOM.createRoot(document.getElementById('ravlo-university-root')).render(<App />);
