// Ravlo Academy OS — Professional Development Platform
// Web-first Academy experience for individuals, teams, and companies.

const { useMemo, useState } = React;

const BRAND = {
  midnight: '#0C1116',
  deepSlate: '#11161C',
  steel: '#1A232C',
  blueprint: '#3A5C7A',
  blueprintLight: '#4C7AA3',
  grayBlue: '#6B7F93',
  softSteel: '#A7A9AC',
  white: '#FFFFFF',
  line: 'rgba(107,127,147,.22)',
  glow: 'rgba(58,92,122,.25)',
};

const CAREER_PATHS = [
  {
    category: 'Investment',
    paths: [
      { icon: '🏠', title: 'New Investor', outcome: 'Become confident enough to analyze and prepare for your first investment.', modules: ['Investor foundations', 'Deal analysis', 'Financing basics', 'Budget Studio'], progress: 38 },
      { icon: '📈', title: 'Growing Investor', outcome: 'Turn scattered deals into repeatable systems and portfolio discipline.', modules: ['BRRRR', 'Capital strategy', 'Portfolio tracking', 'Team building'], progress: 64 },
      { icon: '🏢', title: 'Professional Investor', outcome: 'Build the operating habits, reporting, team workflows, and capital systems behind an investment business.', modules: ['SOPs', 'Operations', 'Risk management', 'Investor reporting'], progress: 72 },
    ],
  },
  {
    category: 'Lending',
    paths: [
      { icon: '🏦', title: 'Loan Officer', outcome: 'Improve product knowledge, borrower communication, and Lending OS execution.', modules: ['Loan products', 'Borrower intake', 'Capital readiness', 'Pipeline habits'], progress: 46 },
      { icon: '📋', title: 'Loan Processor', outcome: 'Learn file anatomy, conditions management, documentation review, and operational consistency.', modules: ['1003 review', 'Income docs', 'Conditions', 'Title and insurance'], progress: 28 },
      { icon: '📑', title: 'Underwriter', outcome: 'Build stronger risk review, guideline awareness, DSCR thinking, and file decision discipline.', modules: ['Risk review', 'DSCR', 'Self-employed income', 'Exception scenarios'], progress: 18 },
    ],
  },
  {
    category: 'Partners',
    paths: [
      { icon: '🏡', title: 'Realtor', outcome: 'Serve investors better with deal analysis, investor language, and Ravlo collaboration workflows.', modules: ['Investor clients', 'Market analysis', 'Offer strategy', 'Partner workflow'], progress: 41 },
      { icon: '🏢', title: 'Property Manager', outcome: 'Train leasing, tenant operations, maintenance coordination, owner reporting, and portfolio support.', modules: ['Leasing', 'Maintenance', 'Owner reporting', 'Vendor workflows'], progress: 21 },
      { icon: '🔨', title: 'Contractor / Builder', outcome: 'Standardize estimating, scope, budgets, schedules, change orders, and investor communication.', modules: ['Estimating', 'Project Studio', 'Change orders', 'Budget approvals'], progress: 12 },
    ],
  },
];

const COMPANY_METRICS = [
  { label: 'Employees', value: '127', detail: 'Across 9 roles' },
  { label: 'Assigned Paths', value: '24', detail: 'Company + Ravlo' },
  { label: 'Completion', value: '82%', detail: 'This quarter' },
  { label: 'Knowledge Docs', value: '68', detail: 'SOPs, forms, guides' },
];

const ASSIGNMENTS = [
  { title: 'New Processor Onboarding', team: 'Lending Operations', due: 'Due this week', complete: 74 },
  { title: 'Investor Client Training', team: 'Realtor Partners', due: '12 active learners', complete: 61 },
  { title: 'Property Manager Foundations', team: 'Property Ops', due: 'New path', complete: 24 },
  { title: 'Company SOP Review', team: 'All employees', due: 'Required', complete: 89 },
];

const BLUEPRINTS = [
  { title: 'Buy Your First Rental', tag: 'Investor', tools: ['Lessons', 'Checklist', 'Calculator', 'AI practice'] },
  { title: 'Process a DSCR File', tag: 'Processor', tools: ['Workflow', 'Docs', 'Conditions', 'AI coach'] },
  { title: 'Underwrite a Rental Loan', tag: 'Underwriter', tools: ['Guidelines', 'Risk review', 'Scenario quiz', 'Checklist'] },
  { title: 'Investor-Friendly Realtor', tag: 'Realtor', tools: ['Scripts', 'Deal analysis', 'Client workflow', 'Partner badge'] },
  { title: 'Maintenance Intake System', tag: 'Property Manager', tools: ['SOP', 'Vendor log', 'Owner update', 'AI response'] },
  { title: 'Rehab Budget Approval', tag: 'Contractor', tools: ['Scope', 'Budget Studio', 'Change order', 'Timeline'] },
];

const ACHIEVEMENTS = [
  'Investor Foundations',
  'Budget Studio Mastery',
  'Loan File Basics',
  'DSCR Workflow',
  'Property Management Foundations',
  'Ravlo Platform Expert',
];

function App() {
  const academy = window.RAVLO_ACADEMY || {};
  const userName = academy.userName || 'Letoya';
  const tier = academy.tier || 'enterprise';
  const [activeView, setActiveView] = useState('dashboard');
  const [activeCategory, setActiveCategory] = useState('Investment');

  const visiblePaths = useMemo(() => {
    return CAREER_PATHS.find(group => group.category === activeCategory)?.paths || [];
  }, [activeCategory]);

  return (
    <div className="academy-shell">
      <style>{styles}</style>

      <aside className="sidebar">
        <a className="brand" href="/">
          <div className="brand-mark">R</div>
          <div>
            <div className="brand-name">RAVLO</div>
            <div className="brand-sub">ACADEMY OS</div>
          </div>
        </a>

        <nav className="side-nav">
          {[
            ['dashboard', 'Dashboard'],
            ['paths', 'Career Paths'],
            ['company', 'Company Academy'],
            ['knowledge', 'Knowledge Base'],
            ['blueprints', 'Blueprints'],
            ['achievements', 'Achievements'],
          ].map(([id, label]) => (
            <button key={id} className={`nav-item ${activeView === id ? 'active' : ''}`} onClick={() => setActiveView(id)}>
              <span>{label}</span>
            </button>
          ))}
        </nav>

        <div className="sidebar-card">
          <div className="mini-label">Access</div>
          <strong>{String(tier).toUpperCase()}</strong>
          <p>Professional development, team training, AI coaching, and company knowledge in one platform.</p>
        </div>
      </aside>

      <main className="main">
        <header className="topbar">
          <div>
            <div className="eyebrow">Professional Development Platform</div>
            <h1>Build the people behind every real estate business.</h1>
          </div>
          <div className="top-actions">
            <button className="ghost-btn">Upload SOP</button>
            <button className="primary-btn">Assign Training</button>
          </div>
        </header>

        {activeView === 'dashboard' && <Dashboard userName={userName} setActiveView={setActiveView} />}
        {activeView === 'paths' && <CareerPaths activeCategory={activeCategory} setActiveCategory={setActiveCategory} visiblePaths={visiblePaths} />}
        {activeView === 'company' && <CompanyAcademy />}
        {activeView === 'knowledge' && <KnowledgeBase />}
        {activeView === 'blueprints' && <Blueprints />}
        {activeView === 'achievements' && <Achievements />}
      </main>
    </div>
  );
}

function Dashboard({ userName, setActiveView }) {
  return (
    <div className="view-stack">
      <section className="hero-panel">
        <div>
          <div className="eyebrow">Welcome back, {userName}</div>
          <h2>Learn. Work. Connect.</h2>
          <p>
            Ravlo Academy OS helps individuals grow into stronger professionals and helps companies train employees, preserve SOPs, and scale consistent real estate workflows.
          </p>
          <div className="hero-actions">
            <button className="primary-btn" onClick={() => setActiveView('paths')}>Choose Career Path</button>
            <button className="ghost-btn" onClick={() => setActiveView('company')}>Open Company Academy</button>
          </div>
        </div>
        <div className="journey-card">
          <div className="mini-label">Current Journey</div>
          <h3>Professional Investor</h3>
          <div className="progress-wrap"><div style={{ width: '72%' }} /></div>
          <div className="progress-meta"><span>72% complete</span><span>Next: Capital Strategy</span></div>
        </div>
      </section>

      <section className="metric-grid">
        {COMPANY_METRICS.map(metric => (
          <div className="metric-card" key={metric.label}>
            <span>{metric.label}</span>
            <strong>{metric.value}</strong>
            <p>{metric.detail}</p>
          </div>
        ))}
      </section>

      <section className="two-col">
        <div className="panel">
          <div className="panel-head"><div><div className="mini-label">Continue</div><h3>Assigned learning</h3></div><button onClick={() => setActiveView('company')}>Manage</button></div>
          <div className="assignment-list">
            {ASSIGNMENTS.map(item => <Assignment item={item} key={item.title} />)}
          </div>
        </div>
        <div className="panel ai-panel">
          <div className="mini-label">Ravlo AI Mentor</div>
          <h3>Training that meets users inside the workflow.</h3>
          <p>Employees can ask questions from Ravlo content and company SOPs. Investors can practice deal analysis. Processors can learn file steps. Property managers can standardize operations.</p>
          <div className="prompt-list">
            <button>How do we process a DSCR file?</button>
            <button>What should a new investor learn first?</button>
            <button>Show my company's maintenance SOP.</button>
          </div>
        </div>
      </section>
    </div>
  );
}

function CareerPaths({ activeCategory, setActiveCategory, visiblePaths }) {
  return (
    <div className="view-stack">
      <section className="section-head">
        <div className="eyebrow">Role-based development</div>
        <h2>Career Paths for the whole Ravlo ecosystem.</h2>
        <p>Each role gets practical training, workflow practice, AI coaching, and platform guidance designed around what they actually do.</p>
      </section>

      <div className="tabs">
        {CAREER_PATHS.map(group => (
          <button className={activeCategory === group.category ? 'active' : ''} onClick={() => setActiveCategory(group.category)} key={group.category}>{group.category}</button>
        ))}
      </div>

      <div className="path-grid">
        {visiblePaths.map(path => <PathCard path={path} key={path.title} />)}
      </div>
    </div>
  );
}

function CompanyAcademy() {
  return (
    <div className="view-stack">
      <section className="section-head">
        <div className="eyebrow">Company Academy</div>
        <h2>Train employees and users inside your real estate operating system.</h2>
        <p>Admins can assign Ravlo paths, upload company SOPs, track progress, and create internal onboarding journeys for employees, partners, and clients.</p>
      </section>
      <section className="company-grid">
        <div className="panel large">
          <div className="panel-head"><div><div className="mini-label">Team Dashboard</div><h3>Ravlo HQ Training</h3></div><button>Invite Employee</button></div>
          <div className="metric-grid compact">
            {COMPANY_METRICS.map(metric => <div className="metric-card" key={metric.label}><span>{metric.label}</span><strong>{metric.value}</strong><p>{metric.detail}</p></div>)}
          </div>
          <div className="assignment-list spaced">
            {ASSIGNMENTS.map(item => <Assignment item={item} key={item.title} />)}
          </div>
        </div>
        <div className="panel">
          <div className="mini-label">What companies can build</div>
          <ul className="check-list">
            <li>New employee onboarding</li>
            <li>Processor and underwriter training</li>
            <li>Realtor and partner training</li>
            <li>Property management SOPs</li>
            <li>Company-specific knowledge base</li>
            <li>Internal Ravlo achievements</li>
          </ul>
        </div>
      </section>
    </div>
  );
}

function KnowledgeBase() {
  return (
    <div className="view-stack">
      <section className="section-head">
        <div className="eyebrow">Company Knowledge</div>
        <h2>Turn SOPs, forms, policies, and playbooks into searchable training.</h2>
        <p>Ravlo Academy OS is designed to preserve company knowledge and make it easier for employees to ask the right questions at the right time.</p>
      </section>
      <div className="knowledge-grid">
        {['Employee Handbook', 'Processing SOP', 'Underwriting Guide', 'Maintenance Checklist', 'Owner Reporting Template', 'Investor Client Scripts'].map(name => (
          <div className="doc-card" key={name}><span>DOC</span><strong>{name}</strong><p>Ready for AI-assisted training and assignment.</p></div>
        ))}
      </div>
    </div>
  );
}

function Blueprints() {
  return (
    <div className="view-stack">
      <section className="section-head">
        <div className="eyebrow">Blueprint Library</div>
        <h2>Actionable playbooks connected to Ravlo workflows.</h2>
        <p>Blueprints combine lessons, checklists, calculators, AI coaching, and direct links back into Investor OS, Lending OS, Partner tools, and future Property Management workflows.</p>
      </section>
      <div className="blueprint-grid">
        {BLUEPRINTS.map(bp => <BlueprintCard bp={bp} key={bp.title} />)}
      </div>
    </div>
  );
}

function Achievements() {
  return (
    <div className="view-stack">
      <section className="section-head">
        <div className="eyebrow">Achievements</div>
        <h2>Platform achievements, not regulated credentials.</h2>
        <p>Academy achievements show practical completion inside Ravlo. They are internal learning milestones and do not represent licensing, continuing education credit, or state certification.</p>
      </section>
      <div className="achievement-grid">
        {ACHIEVEMENTS.map((name, index) => <div className="achievement" key={name}><div>{index < 3 ? '🏆' : '◇'}</div><strong>{name}</strong><span>{index < 3 ? 'Complete' : 'Available'}</span></div>)}
      </div>
    </div>
  );
}

function Assignment({ item }) {
  return (
    <div className="assignment">
      <div>
        <strong>{item.title}</strong>
        <span>{item.team} · {item.due}</span>
      </div>
      <div className="assignment-progress"><div style={{ width: `${item.complete}%` }} /></div>
      <b>{item.complete}%</b>
    </div>
  );
}

function PathCard({ path }) {
  return (
    <article className="path-card">
      <div className="path-top"><span>{path.icon}</span><b>{path.progress}%</b></div>
      <h3>{path.title}</h3>
      <p>{path.outcome}</p>
      <div className="module-pills">{path.modules.map(m => <span key={m}>{m}</span>)}</div>
      <div className="progress-wrap"><div style={{ width: `${path.progress}%` }} /></div>
      <button className="path-btn">Open Path</button>
    </article>
  );
}

function BlueprintCard({ bp }) {
  return (
    <article className="blueprint-card">
      <div className="blueprint-tag">{bp.tag}</div>
      <h3>{bp.title}</h3>
      <div className="module-pills">{bp.tools.map(tool => <span key={tool}>{tool}</span>)}</div>
      <button className="ghost-btn small">Open Blueprint</button>
    </article>
  );
}

const styles = `
:root{--midnight:${BRAND.midnight};--slate:${BRAND.deepSlate};--steel:${BRAND.steel};--blue:${BRAND.blueprint};--blue2:${BRAND.blueprintLight};--gray:${BRAND.grayBlue};--soft:${BRAND.softSteel};--white:${BRAND.white};--line:${BRAND.line};--glow:${BRAND.glow}}
*{box-sizing:border-box}body{margin:0;background:var(--midnight);font-family:Inter,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;color:var(--white)}button{font-family:inherit}.academy-shell{min-height:100vh;display:grid;grid-template-columns:280px 1fr;background:radial-gradient(circle at 70% -10%,rgba(58,92,122,.22),transparent 34%),linear-gradient(180deg,#0C1116 0%,#11161C 100%)}.sidebar{position:sticky;top:0;height:100vh;padding:28px 22px;border-right:1px solid var(--line);background:rgba(12,17,22,.76);backdrop-filter:blur(18px);display:flex;flex-direction:column;gap:28px}.brand{display:flex;align-items:center;gap:12px;text-decoration:none}.brand-mark{width:42px;height:42px;border-radius:14px;border:1px solid rgba(76,122,163,.45);background:linear-gradient(135deg,rgba(58,92,122,.34),rgba(26,35,44,.9));display:grid;place-items:center;color:#d9e7f4;font-family:"Cormorant Garamond",serif;font-size:25px;font-weight:700;box-shadow:0 18px 40px rgba(58,92,122,.18)}.brand-name{letter-spacing:3px;font-size:13px;font-weight:800;color:#fff}.brand-sub{letter-spacing:3px;font-size:9px;color:var(--gray);margin-top:2px}.side-nav{display:flex;flex-direction:column;gap:8px}.nav-item{width:100%;text-align:left;border:1px solid transparent;background:transparent;color:var(--soft);padding:12px 14px;border-radius:14px;cursor:pointer;font-size:14px;font-weight:700}.nav-item:hover,.nav-item.active{border-color:rgba(76,122,163,.32);background:rgba(58,92,122,.14);color:#fff}.sidebar-card{margin-top:auto;border:1px solid var(--line);background:rgba(26,35,44,.68);border-radius:20px;padding:18px}.sidebar-card strong{display:block;color:#dceafa;margin:6px 0}.sidebar-card p{font-size:12px;line-height:1.55;color:var(--gray)}.main{min-width:0;padding:32px;max-width:1440px;width:100%;margin:0 auto}.topbar{display:flex;align-items:flex-start;justify-content:space-between;gap:24px;margin-bottom:28px}.eyebrow,.mini-label{font-size:11px;letter-spacing:2.5px;text-transform:uppercase;color:#88a6bf;font-weight:800}.topbar h1{font-size:clamp(32px,4vw,56px);line-height:.98;letter-spacing:-2.2px;max-width:880px;margin:10px 0 0}.top-actions,.hero-actions{display:flex;gap:12px;flex-wrap:wrap}.primary-btn,.ghost-btn,.path-btn{border:0;border-radius:14px;padding:12px 18px;font-weight:800;cursor:pointer}.primary-btn{background:linear-gradient(135deg,var(--blue2),var(--blue));color:#fff;box-shadow:0 18px 44px rgba(58,92,122,.24)}.ghost-btn{background:rgba(58,92,122,.12);border:1px solid rgba(76,122,163,.28);color:#dceafa}.ghost-btn.small{padding:10px 12px;font-size:12px}.view-stack{display:flex;flex-direction:column;gap:22px}.hero-panel,.panel,.metric-card,.path-card,.blueprint-card,.doc-card,.achievement{border:1px solid var(--line);background:linear-gradient(180deg,rgba(26,35,44,.86),rgba(17,22,28,.78));border-radius:26px;box-shadow:0 24px 90px rgba(0,0,0,.22)}.hero-panel{display:grid;grid-template-columns:minmax(0,1.4fr) minmax(300px,.6fr);gap:22px;padding:34px;position:relative;overflow:hidden}.hero-panel:before{content:"";position:absolute;inset:-1px;background:radial-gradient(circle at 25% 0%,rgba(76,122,163,.18),transparent 34%);pointer-events:none}.hero-panel>*{position:relative}.hero-panel h2,.section-head h2{font-size:clamp(32px,4vw,54px);line-height:1;letter-spacing:-2px;margin:10px 0 12px}.hero-panel p,.section-head p,.panel p,.path-card p,.blueprint-card p,.doc-card p{color:#9fb0bf;line-height:1.65}.journey-card{border:1px solid rgba(76,122,163,.26);background:rgba(12,17,22,.55);border-radius:22px;padding:22px;align-self:stretch;display:flex;flex-direction:column;justify-content:center}.journey-card h3{font-size:26px;margin:8px 0 18px}.progress-wrap,.assignment-progress{height:8px;background:rgba(107,127,147,.18);border-radius:999px;overflow:hidden}.progress-wrap div,.assignment-progress div{height:100%;background:linear-gradient(90deg,var(--blue),var(--blue2));border-radius:999px}.progress-meta{display:flex;justify-content:space-between;gap:12px;margin-top:10px;color:#8fa6b8;font-size:12px}.metric-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:14px}.metric-grid.compact{grid-template-columns:repeat(2,minmax(0,1fr));margin:20px 0}.metric-card{padding:20px}.metric-card span{color:#8fa6b8;font-size:12px;font-weight:700}.metric-card strong{display:block;font-size:34px;margin:8px 0 0}.metric-card p{font-size:12px;margin:4px 0 0}.two-col,.company-grid{display:grid;grid-template-columns:1.1fr .9fr;gap:18px}.panel{padding:24px}.panel.large{grid-column:span 1}.panel-head{display:flex;align-items:center;justify-content:space-between;gap:16px;margin-bottom:18px}.panel-head h3,.panel h3{font-size:24px;margin:6px 0 0}.panel-head button{border:1px solid rgba(76,122,163,.28);background:rgba(58,92,122,.12);color:#dceafa;border-radius:12px;padding:10px 12px;font-weight:800}.assignment-list{display:flex;flex-direction:column;gap:12px}.assignment-list.spaced{margin-top:8px}.assignment{display:grid;grid-template-columns:1.2fr 1fr 48px;gap:14px;align-items:center;border:1px solid rgba(107,127,147,.18);background:rgba(12,17,22,.34);border-radius:16px;padding:14px}.assignment strong{display:block}.assignment span{display:block;color:#8298aa;font-size:12px;margin-top:4px}.assignment b{text-align:right;color:#dceafa}.ai-panel{background:linear-gradient(160deg,rgba(58,92,122,.24),rgba(26,35,44,.72))}.prompt-list{display:flex;flex-direction:column;gap:10px;margin-top:20px}.prompt-list button{border:1px solid rgba(76,122,163,.28);background:rgba(12,17,22,.44);color:#dceafa;text-align:left;border-radius:14px;padding:12px;font-weight:700}.section-head{max-width:920px}.tabs{display:flex;gap:10px;flex-wrap:wrap}.tabs button{border:1px solid rgba(76,122,163,.24);background:rgba(58,92,122,.1);color:#9fb0bf;border-radius:999px;padding:10px 16px;font-weight:800;cursor:pointer}.tabs button.active{background:rgba(76,122,163,.26);border-color:rgba(76,122,163,.52);color:#fff}.path-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:18px}.path-card{padding:24px}.path-top{display:flex;justify-content:space-between;align-items:center;margin-bottom:18px}.path-top span{font-size:34px}.path-top b{color:#dceafa;background:rgba(58,92,122,.18);border:1px solid rgba(76,122,163,.24);border-radius:999px;padding:6px 10px}.path-card h3,.blueprint-card h3{font-size:24px;margin:0 0 10px}.module-pills{display:flex;flex-wrap:wrap;gap:8px;margin:18px 0}.module-pills span{font-size:11px;font-weight:800;color:#b9ccdc;background:rgba(58,92,122,.12);border:1px solid rgba(76,122,163,.2);border-radius:999px;padding:7px 10px}.path-btn{width:100%;margin-top:18px;background:rgba(76,122,163,.2);border:1px solid rgba(76,122,163,.34);color:#fff}.check-list{list-style:none;display:flex;flex-direction:column;gap:14px;margin-top:18px}.check-list li{color:#d3e2ee}.check-list li:before{content:"✓";color:#8EA7C0;font-weight:900;margin-right:10px}.knowledge-grid,.blueprint-grid,.achievement-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:16px}.doc-card,.blueprint-card,.achievement{padding:22px}.doc-card span,.blueprint-tag{font-size:10px;letter-spacing:2px;text-transform:uppercase;color:#88a6bf;font-weight:900}.doc-card strong{display:block;font-size:20px;margin:12px 0 6px}.achievement{display:flex;flex-direction:column;gap:10px;align-items:flex-start}.achievement div{font-size:28px}.achievement strong{font-size:18px}.achievement span{font-size:12px;color:#8fa6b8;font-weight:800;text-transform:uppercase;letter-spacing:1px}@media(max-width:1100px){.academy-shell{grid-template-columns:1fr}.sidebar{position:relative;height:auto}.side-nav{display:grid;grid-template-columns:repeat(3,1fr)}.hero-panel,.two-col,.company-grid{grid-template-columns:1fr}.metric-grid,.path-grid,.knowledge-grid,.blueprint-grid,.achievement-grid{grid-template-columns:repeat(2,1fr)}}@media(max-width:720px){.main{padding:22px}.topbar{flex-direction:column}.metric-grid,.path-grid,.knowledge-grid,.blueprint-grid,.achievement-grid,.metric-grid.compact{grid-template-columns:1fr}.side-nav{grid-template-columns:1fr}.assignment{grid-template-columns:1fr}.assignment b{text-align:left}}
`;

ReactDOM.createRoot(document.getElementById('ravlo-university-root')).render(<App />);
