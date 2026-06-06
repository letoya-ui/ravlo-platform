export interface QuizQuestion {
  question: string;
  options: string[];
  correctIndex: number;
  explanation: string;
}

export interface Lesson {
  title: string;
  duration: string;
  content: string;
  keyPoints: string[];
  quiz: QuizQuestion[];
}

export interface Module {
  id: string;
  title: string;
  description: string;
  icon: string;
  color: string;
  lessons: Lesson[];
  tiers: string[];
  creditHours: number;
}

export const MODULES: Module[] = [
  {
    id: 'residential',
    title: 'Residential Mastery',
    description: 'Master the fundamentals of residential real estate sales, buyer representation, and client conversion.',
    icon: 'home-outline',
    color: '#3BAF7A',
    tiers: ['starter', 'pro', 'elite', 'lending'],
    creditHours: 6,
    lessons: [
      {
        title: 'Listing Strategy & Pricing',
        duration: '12 min',
        content: `A well-priced listing sells faster and for more money. Pricing is both art and science — you need to understand the market, the property, and seller psychology.\n\nStart with a Comparative Market Analysis (CMA). Pull 3-6 active comps, 3-6 pending comps, and 3-6 sold comps within the last 90 days. Adjust for square footage, lot size, condition, upgrades, and location factors.\n\nPricing strategies:\n\n**Aggressive Pricing** — List 2-3% below market to trigger multiple offers and drive the price above ask. Works in low-inventory markets.\n\n**At-Market Pricing** — List at or within 1% of estimated value. Best for balanced markets.\n\n**Value Range Pricing** — Show a price range (e.g. $485K–$510K) to attract more showings and let the market determine value.\n\nAvoid the trap of "buying the listing" — pricing too high to get the contract, then chasing the market down with price reductions. Every price reduction signals weakness and costs more time and money than pricing right from day one.\n\nPresent your pricing recommendation with data, not opinion. Sellers trust numbers. Show the absorption rate (how many months of inventory exist), list-to-sale ratios, and days on market for your price band.`,
        keyPoints: [
          'Pull comps within 90 days and adjust for differences',
          'Aggressive pricing creates multiple offer scenarios',
          'Price reductions signal weakness — price right from day one',
          'Use absorption rate data to back your recommendation',
        ],
        quiz: [
          {
            question: 'What is the recommended timeframe for comps in a Comparative Market Analysis?',
            options: ['6 months', '90 days', '12 months', '30 days'],
            correctIndex: 1,
            explanation: 'Comps within 90 days reflect current market conditions most accurately. In slow markets you may extend to 120 days.',
          },
          {
            question: 'Which pricing strategy is best for triggering multiple offers in a low-inventory market?',
            options: ['At-market pricing', 'Value range pricing', 'Aggressive pricing (2–3% below market)', 'Above-market pricing'],
            correctIndex: 2,
            explanation: 'Aggressive pricing creates urgency and competition, often driving the final sale price above asking.',
          },
          {
            question: '"Buying the listing" refers to:',
            options: ['Purchasing your own listing', 'Pricing too high to get the contract, then reducing price', 'Buying MLS data', 'Underpricing for a quick sale'],
            correctIndex: 1,
            explanation: 'Overpricing to win the listing then chasing the market down with reductions signals weakness and costs the seller time and money.',
          },
        ],
      },
      {
        title: 'Buyer Representation',
        duration: '15 min',
        content: `Representing buyers well starts before you ever show a property. The consultation sets the tone for the entire relationship.\n\n**Buyer Consultation Essentials**\n\nSpend 45–60 minutes understanding your buyer before showing a single home. Cover:\n- Their must-haves vs. nice-to-haves\n- Timeline and flexibility\n- Pre-approval status (or connect them with your lender)\n- Previous home-buying experience\n- Decision-making process (who else is involved?)\n\n**Setting Expectations**\n\nBuyers who understand the process make better decisions under pressure. Walk them through: search → showing → offer → contract → inspection → appraisal → closing. Explain that in competitive markets, they may lose multiple homes before winning one — and that's normal.\n\n**Showing Strategy**\n\nShow homes in clusters, not one at a time. Start with a home that sets the baseline, include one slightly above budget (the "dream"), and end with the best value match. This anchoring technique helps buyers calibrate quickly.\n\n**Writing Winning Offers**\n\nBeyond price: escalation clauses, waived inspections (with appropriate caveats), strong earnest money, flexible closing dates, and personal letters can differentiate your offer. Know what the seller wants — sometimes certainty beats price.`,
        keyPoints: [
          'Invest 45–60 min in buyer consultation before showing homes',
          'Set expectations about competition and losing offers upfront',
          'Show homes in clusters using anchoring technique',
          'Ask listing agents what terms the seller values most',
        ],
        quiz: [
          {
            question: 'How long should an initial buyer consultation take?',
            options: ['10–15 minutes', '30 minutes', '45–60 minutes', '90+ minutes'],
            correctIndex: 2,
            explanation: 'Investing 45–60 minutes upfront ensures you understand the buyer\'s needs, budget, and decision-making process before showing a single property.',
          },
          {
            question: 'What is the "anchoring technique" when showing homes?',
            options: ['Show the best home first', 'Show one home at a time', 'Start with a baseline, include a dream home, end with the best value match', 'Show all homes in ascending price order'],
            correctIndex: 2,
            explanation: 'Anchoring helps buyers calibrate quickly by experiencing the range — baseline, dream, then the best fit.',
          },
          {
            question: 'Beyond price, what can differentiate an offer in a competitive market?',
            options: ['Requesting more repairs', 'Lower earnest money', 'Escalation clauses, flexible closing dates, and strong earnest money', 'Longer inspection period'],
            correctIndex: 2,
            explanation: 'Sellers often value certainty and flexibility over raw price — knowing what the seller needs lets you craft a more competitive offer.',
          },
        ],
      },
      {
        title: 'Negotiation Frameworks',
        duration: '18 min',
        content: `Negotiation is not arguing — it's problem-solving with incomplete information. The best negotiators in real estate think in terms of interests, not positions.\n\n**The BATNA Principle**\nBest Alternative To a Negotiated Agreement. Know yours and know theirs. A buyer with one home they love has weak BATNA. A seller with no place to go has weak BATNA. Whoever needs the deal more has less leverage.\n\n**The FBI Tactical Empathy Framework**\nAdapted for real estate:\n- **Mirroring** — Repeat the last 2-3 words of what they said. "Three other offers?" This invites them to elaborate.\n- **Labeling** — "It sounds like you're concerned about the timeline." Naming emotions defuses them.\n- **Calibrated Questions** — "How am I supposed to make that work?" or "What would need to happen for this to work?" These force the other side to solve your problem.\n\n**Counter-Offer Architecture**\nNever counter at your maximum. Always leave room. When presenting a counter, anchor high (or low for buyers) and give a specific reason — "Based on the roof inspection, we're requesting $8,500 in credit." Specificity signals credibility.\n\n**Handling Multiple Offers**\nAs a listing agent: set a call for offers deadline, create urgency, and ask for "highest and best." As a buyer's agent: find out what the seller cares about most — sometimes price isn't it.`,
        keyPoints: [
          'Think in interests, not positions — find the underlying need',
          'Know your BATNA and assess the other side\'s',
          'Use mirroring and labeled empathy to open conversations',
          'Anchor with specific reasons, not arbitrary numbers',
        ],
        quiz: [
          {
            question: 'What does BATNA stand for?',
            options: ['Best Available Transaction and Negotiation Agreement', 'Best Alternative To a Negotiated Agreement', 'Bargaining Advantage Through Networked Actions', 'Basic Approach To Negotiation Advantage'],
            correctIndex: 1,
            explanation: 'Knowing your BATNA (and the other side\'s) reveals who has more leverage and how far you can push.',
          },
          {
            question: 'In the FBI Tactical Empathy Framework, "mirroring" means:',
            options: ['Copying the other party\'s body language', 'Repeating the last 2–3 words of what they said', 'Using their words against them', 'Making the same offer twice'],
            correctIndex: 1,
            explanation: 'Mirroring invites the other party to elaborate, giving you more information without revealing your position.',
          },
          {
            question: 'When presenting a counter-offer, you should:',
            options: ['Always counter at your maximum', 'Never counter at your maximum — leave room', 'Always accept the first offer', 'Counter only if you have multiple buyers'],
            correctIndex: 1,
            explanation: 'Leaving room in a counter allows for continued negotiation and signals flexibility while protecting your true limit.',
          },
        ],
      },
      {
        title: 'CMA Deep Dive',
        duration: '20 min',
        content: `A Comparative Market Analysis is the foundation of every pricing conversation. Agents who can explain their CMA methodology build instant credibility.\n\n**Comp Selection Criteria**\n- Same subdivision or within ½ mile in urban areas, 1 mile in suburban\n- Within 20% of subject square footage\n- Sold within 90 days (120 days in slow markets)\n- Similar style (ranch vs. two-story, attached vs. detached)\n\n**Adjustments Grid**\nCreate a spreadsheet showing your comp data and adjustments:\n- GLA (Gross Living Area): $50–$150/sq ft depending on market\n- Garage: $5,000–$20,000 per stall\n- Lot size: varies widely by market\n- Age/Condition: subjective, use $/sq ft of renovation cost\n- Pools: often negative in cold climates, positive in warm\n\n**List Price vs. Sale Price**\nAlways compare against sale prices, not list prices. List price is opinion; sale price is fact. Track list-to-sale ratios — if homes are selling at 103% of list, the market is hot and you can price aggressively.\n\n**Automated Valuation Models (AVMs)**\nZillow, Redfin, and CoreLogic estimates are starting points, not endpoints. They miss condition, updates, and micro-location factors. Use them to sanity-check your work, not replace it.\n\n**Presenting the CMA**\nUse a one-page summary showing the range, your recommendation, and the key drivers. Avoid overwhelming sellers with 20 pages of data — lead with the conclusion, support with evidence.`,
        keyPoints: [
          'Use sold comps within 90 days, same style, within 20% sq footage',
          'Adjust systematically for GLA, garage, lot, condition',
          'Compare sale prices, not list prices',
          'Lead CMA presentation with conclusion, support with evidence',
        ],
        quiz: [
          {
            question: 'Which type of prices should you primarily compare in a CMA?',
            options: ['List prices of active listings', 'Pending sales prices', 'Sold prices within 90 days', 'Zillow Zestimate values'],
            correctIndex: 2,
            explanation: 'Sale prices are facts; list prices are opinions. Always underwrite to what the market actually paid.',
          },
          {
            question: 'What is the acceptable square footage difference for CMA comps?',
            options: ['5%', '10%', '20%', '50%'],
            correctIndex: 2,
            explanation: 'Comps within 20% of subject square footage are close enough to adjust accurately without distorting the analysis.',
          },
          {
            question: 'When presenting a CMA, what should you lead with?',
            options: ['All 20 pages of raw data', 'The conclusion, supported by evidence', 'The Zillow estimate', 'Comparable list prices'],
            correctIndex: 1,
            explanation: 'Sellers trust a clear recommendation backed by data — leading with the conclusion builds credibility faster than burying it in data.',
          },
        ],
      },
      {
        title: 'Open House Optimization',
        duration: '10 min',
        content: `Open houses have two goals: sell the house (primary) and capture buyer leads (secondary). Most agents only do the second.\n\n**Pre-Open House**\n- Market via Zillow, Realtor.com, Facebook Events, neighborhood apps (Nextdoor), and direct mail to surrounding homes\n- Send personal invites to your top 20 buyer leads\n- Arrive 45 minutes early: staging touch-ups, lighting, scent, temperature\n- Remove personalized photos and valuables\n- Create a sign-in process (paper or digital — capture email + phone)\n\n**During the Open House**\n- Greet visitors at the door, not from across the room\n- Ask: "Have you been working with a Realtor?" — qualifying without pressure\n- Let visitors explore independently, then check in with "Any questions so far?"\n- Point out 2-3 features you know photograph poorly (things that are better in person)\n- Have a one-page feature sheet with key upgrades and recent comps\n\n**Follow-Up**\n- Contact every sign-in within 2 hours\n- For unrepresented buyers: offer a buyer consultation\n- For represented buyers: notify their agent of serious interest\n- For neighbors: they may have referrals — "Did you know anyone who'd love this neighborhood?"`,
        keyPoints: [
          'Market open houses through 5+ channels including Nextdoor',
          'Arrive 45 min early for staging and setup',
          'Always ask if visitors are working with an agent',
          'Follow up with every sign-in within 2 hours',
        ],
        quiz: [
          {
            question: 'What is the primary goal of an open house?',
            options: ['Capture buyer leads', 'Sell the house', 'Network with neighbors', 'Generate social media content'],
            correctIndex: 1,
            explanation: 'Most agents focus on lead generation, but the primary goal is always to sell the listed property first.',
          },
          {
            question: 'How early should you arrive before an open house?',
            options: ['5–10 minutes', '15–20 minutes', '45 minutes', 'The day before'],
            correctIndex: 2,
            explanation: '45 minutes allows time for staging touch-ups, lighting, temperature, and proper visitor sign-in setup.',
          },
          {
            question: 'When should you follow up with open house sign-ins?',
            options: ['Within 2 hours', 'Within 24 hours', 'Within 48 hours', 'At the end of the week'],
            correctIndex: 0,
            explanation: 'Immediate follow-up within 2 hours shows professionalism and catches buyers while the property is fresh in their mind.',
          },
        ],
      },
      {
        title: 'Lead Conversion Systems',
        duration: '22 min',
        content: `Lead conversion is where income is made or lost. Most agents respond too slowly, follow up inconsistently, and don't have a system.\n\n**Speed to Lead**\nNAR research shows leads contacted within 5 minutes are 100x more likely to convert than those contacted after 30 minutes. Build instant response into your workflow: use auto-responders, text-first outreach, and calendar blocks for lead follow-up.\n\n**The 5x5x5 Framework**\n- 5 texts in the first 5 days\n- 5 emails in the first 5 weeks\n- 5 calls in the first 5 months\nAdjust based on engagement. If they respond, accelerate.\n\n**Database Segmentation**\n- **A List**: Ready to transact in 0–90 days — personal outreach weekly\n- **B List**: Ready in 90–180 days — bi-weekly check-ins\n- **C List**: 6+ months out — monthly market updates\n- **D List**: Long-term/nurture — quarterly touchpoints\n\n**Value-First Follow-Up**\nEvery touchpoint should provide value: a new listing, a market update, a neighborhood stat, a home tip. Never "just checking in." Agents who provide value get callbacks. Agents who just check in get ignored.\n\n**CRM Discipline**\nA CRM only works if you use it consistently. Block 30 minutes every morning for CRM tasks. Log every call, note every personal detail (kids' names, hobbies, move reasons), and set follow-up tasks before closing every contact record.`,
        keyPoints: [
          'Contact new leads within 5 minutes — 100x conversion rate difference',
          'Use 5x5x5 framework for systematic follow-up',
          'Segment database by timeline: A/B/C/D lists',
          'Every follow-up touchpoint must provide specific value',
        ],
        quiz: [
          {
            question: 'How much more likely are leads contacted within 5 minutes to convert vs. after 30 minutes?',
            options: ['10x', '50x', '100x', '5x'],
            correctIndex: 2,
            explanation: 'NAR research confirms that speed-to-lead dramatically increases conversion — every minute of delay costs you.',
          },
          {
            question: 'In the 5x5x5 follow-up framework, what happens in the first 5 days?',
            options: ['5 calls', '5 emails', '5 texts', '5 appointments'],
            correctIndex: 2,
            explanation: 'Text-first outreach in the first 5 days has higher open and response rates than calls or emails in the initial contact phase.',
          },
          {
            question: 'An "A List" lead in database segmentation is ready to transact within:',
            options: ['6–12 months', '90–180 days', '0–90 days', 'Over a year'],
            correctIndex: 2,
            explanation: 'A List contacts get weekly personal outreach — they are in the buying/selling window now and need your attention most.',
          },
        ],
      },
    ],
  },
  {
    id: 'commercial',
    title: 'Commercial Real Estate',
    description: 'Navigate commercial leasing, investment sales, and complex deal structures in office, retail, and industrial.',
    icon: 'business-outline',
    color: '#4C8ED9',
    tiers: ['pro', 'elite'],
    creditHours: 8,
    lessons: [
      {
        title: 'Office & Retail Leasing',
        duration: '20 min',
        content: `Commercial leasing differs fundamentally from residential. Leases are negotiated documents, not standard forms, and the economics are far more complex.\n\n**Lease Types**\n- **Gross Lease**: Tenant pays flat rent; landlord pays operating expenses (NNN)\n- **Net Lease (NNN)**: Tenant pays base rent + property taxes + insurance + maintenance\n- **Modified Gross**: Hybrid — base expenses included, increases are tenant's responsibility\n- **Percentage Lease**: Common in retail — base rent + % of tenant's gross sales\n\n**Key Lease Terms to Negotiate**\n- Free rent period (tenant improvement buildout)\n- Tenant Improvement Allowance (TIA): $20–$80/sq ft depending on market\n- Option to renew and at what rate (fixed, CPI-adjusted, or market)\n- Personal guarantee vs. entity-only guarantee\n- Sublease and assignment rights\n- Termination rights (kick-out clauses)\n\n**Retail Site Selection Criteria**\nFor retailers: traffic counts, co-tenancy (who's nearby), parking ratios, visibility, and demographics within 1/3/5 mile rings. A great lease in a bad location will fail.\n\n**Office Leasing Trends**\nPost-COVID hybrid work has created surplus office space in many markets. Flight to quality — tenants upgrading to Class A space at similar rates as their old Class B. Understand sublease supply and direct vacancy separately.`,
        keyPoints: [
          'NNN leases shift all operating expenses to the tenant',
          'TIA and free rent are key items to negotiate aggressively',
          'Retail: traffic, co-tenancy, and demographics drive success',
          'Track direct vacancy and sublease availability separately',
        ],
        quiz: [
          {
            question: 'In a Triple Net (NNN) lease, who pays property taxes, insurance, and maintenance?',
            options: ['The landlord', 'The tenant', 'Split 50/50', 'Depends on state law'],
            correctIndex: 1,
            explanation: 'NNN tenants pay base rent plus all operating expenses — the landlord receives a net income stream with minimal obligations.',
          },
          {
            question: 'What is Tenant Improvement Allowance (TIA) primarily used for?',
            options: ['Moving expenses', 'Building out the leased space to the tenant\'s requirements', 'Paying the first month\'s rent', 'Security deposit'],
            correctIndex: 1,
            explanation: 'TIA is the landlord\'s contribution toward customizing the raw space — negotiating it aggressively can save tenants significant capital.',
          },
          {
            question: 'Which post-COVID trend most impacted office leasing?',
            options: ['Elimination of office space entirely', 'Suburban office boom', 'Flight to quality — tenants upgrading to Class A at similar rents as old Class B', 'Increased demand for small offices'],
            correctIndex: 2,
            explanation: 'Hybrid work created surplus lower-quality space while demand for premium amenities and flexible layouts drove Class A occupancy.',
          },
        ],
      },
      {
        title: 'Cap Rate & NOI Analysis',
        duration: '25 min',
        content: `Cap rate and NOI are the language of commercial real estate investment. Mastering these concepts is non-negotiable.\n\n**Net Operating Income (NOI)**\nNOI = Gross Potential Rent − Vacancy & Credit Loss − Operating Expenses\n\nOperating expenses include: property taxes, insurance, utilities, management fees, maintenance, reserves. They do NOT include debt service or capital expenditures.\n\nExample:\n- Gross rents: $500,000/year\n- Vacancy (5%): −$25,000\n- Operating expenses: −$175,000\n- **NOI = $300,000**\n\n**Capitalization Rate**\nCap Rate = NOI ÷ Purchase Price\n\nA property with $300,000 NOI at a 6% cap rate is worth $5,000,000.\n\nCap rates compress (go lower) when the market is hot or the asset is high-quality. A Class A office building in Manhattan might trade at a 4% cap. A strip mall in rural Ohio might be 9%.\n\n**What Drives Cap Rates**\n- Risk of the asset class (apartments < office < retail)\n- Location and market strength\n- Lease term and tenant quality (credit vs. local)\n- Market interest rates (cap rates generally follow 10-year Treasury)\n\n**The Danger of Pro Forma NOI**\nSellers often present "stabilized" or "pro forma" NOI based on assumptions. Always underwrite to actual trailing 12-month financials, not projections. Verify rent rolls, review leases, and confirm tenant estoppels.`,
        keyPoints: [
          'NOI excludes debt service and capex — it\'s the property\'s earning power',
          'Cap Rate = NOI ÷ Price — lower cap = more expensive per dollar of income',
          'Always underwrite actual T12 NOI, never seller pro formas',
          'Cap rates correlate with risk, location quality, and interest rates',
        ],
        quiz: [
          {
            question: 'What is the formula for Net Operating Income (NOI)?',
            options: ['Gross Rent − Mortgage Payments', 'Gross Potential Rent − Vacancy − Operating Expenses', 'Purchase Price × Cap Rate', 'NOI ÷ Cap Rate'],
            correctIndex: 1,
            explanation: 'NOI excludes debt service and capital expenditures — it measures the property\'s earning power independent of financing.',
          },
          {
            question: 'A property has $300,000 NOI and a 6% cap rate. What is its value?',
            options: ['$1,800,000', '$3,000,000', '$5,000,000', '$18,000,000'],
            correctIndex: 2,
            explanation: 'Value = NOI ÷ Cap Rate = $300,000 ÷ 0.06 = $5,000,000.',
          },
          {
            question: 'Why is "pro forma" NOI risky to underwrite to?',
            options: ['It\'s certified by an accountant', 'It\'s projected/stabilized income based on assumptions — always verify actual trailing 12-month financials', 'It includes debt service', 'It\'s government-standardized'],
            correctIndex: 1,
            explanation: 'Pro forma NOI assumes ideal conditions. Savvy buyers underwrite T12 actuals and stress-test from there.',
          },
        ],
      },
      {
        title: 'Investment Sales',
        duration: '18 min',
        content: `Commercial investment sales (also called capital markets) involves selling income-producing assets to investors. The skill set is different from leasing — it's financial analysis combined with relationship management.\n\n**The Investment Sales Process**\n1. Engagement — sign exclusive listing agreement with seller\n2. Underwriting — build financial model with T12 actuals and forward projections\n3. Offering Memorandum (OM) — marketing package with financials, photos, location analysis\n4. Marketing — targeted outreach to qualified buyer pool (not MLS blasts)\n5. Offers — collect LOIs, qualify buyers, negotiate price and terms\n6. Due Diligence — 30–60 days of buyer inspection, lease review, financial audit\n7. Closing — coordinate with title, lenders, and attorneys\n\n**Building a Buyer Pool**\nIn commercial, the buyer universe is smaller and more defined. Track: REITs, private equity firms, family offices, 1031 exchange buyers, owner-users, and high-net-worth individuals. Match asset type to buyer profile.\n\n**Pricing Strategy**\nIn commercial, you're pricing cash flow, not comps. Build your pricing around NOI and appropriate cap rate range based on market evidence. Stress-test the model with rising vacancy and expense scenarios.\n\n**Confidentiality**\nAlways use NDAs before releasing financials. Tenant information and financial details are sensitive — sellers can be exposed if competitors or tenants learn their property is for sale.`,
        keyPoints: [
          'Investment sales is financial analysis + relationship management',
          'OM is your marketing document — quality reflects on the deal',
          'Price by NOI and cap rate, not comparable sales alone',
          'Always use NDAs before releasing financial information',
        ],
        quiz: [
          {
            question: 'What is an Offering Memorandum (OM) in commercial investment sales?',
            options: ['A court filing for foreclosure', 'A marketing package with financials, photos, and location analysis', 'The purchase agreement', 'A bank loan application'],
            correctIndex: 1,
            explanation: 'The OM is your primary marketing tool — its quality signals the professionalism of the deal and attracts the right buyer pool.',
          },
          {
            question: 'How should commercial properties be priced?',
            options: ['By comparable sales alone', 'By square footage', 'By NOI and appropriate cap rate range based on market evidence', 'By the age of the building'],
            correctIndex: 2,
            explanation: 'In commercial, you\'re pricing cash flow, not bricks — cap rate and NOI together tell the story of value.',
          },
          {
            question: 'Why must NDAs be used before releasing financials?',
            options: ['Legally required in all states', 'Tenant and financial data are sensitive — disclosure can harm the seller competitively', 'To prevent competing buyers', 'NDAs guarantee a higher sale price'],
            correctIndex: 1,
            explanation: 'Competitors, tenants, or lenders learning a property is for sale can create operational problems and weaken negotiating position.',
          },
        ],
      },
      {
        title: '1031 Exchanges',
        duration: '22 min',
        content: `A 1031 exchange allows investors to defer capital gains taxes by reinvesting proceeds from a sold property into a like-kind replacement property. It's one of the most powerful wealth-building tools in real estate.\n\n**Basic Requirements**\n- Properties must be held for investment or business use (not personal use or flipping)\n- Must be "like-kind" — any real property for any real property (land for apartments, office for industrial, etc.)\n- Must use a Qualified Intermediary (QI) — you cannot touch the money\n- 45-day identification period after close of relinquished property\n- 180-day close period for replacement property\n\n**Identification Rules**\nChoose one of:\n- **3-Property Rule**: Identify up to 3 properties of any value\n- **200% Rule**: Identify any number of properties as long as total FMV ≤ 200% of relinquished property\n- **95% Rule**: Identify unlimited properties if you close on 95% of the value\n\n**Boot**\nBoot = any cash or non-like-kind property received. Boot is taxable. If the investor doesn't reinvest 100% of the proceeds, the unspent portion is taxed.\n\n**Common Mistakes**\n- Missing the 45-day deadline (no extensions except disaster)\n- Receiving proceeds before QI is set up\n- Buying a vacation home without proper use documentation\n- Under-buying (not reinvesting enough equity)\n\n**Reverse 1031**\nBuy the replacement property first, then sell. More complex and expensive, but useful when the perfect property is available now.`,
        keyPoints: [
          '45-day ID window and 180-day close — no exceptions',
          'Qualified Intermediary must hold all funds — never touch the money',
          'Boot (uninvested proceeds) is taxable in the year of exchange',
          'Any real property for any real property = like-kind',
        ],
        quiz: [
          {
            question: 'How many days does an investor have to identify a replacement property in a 1031 exchange?',
            options: ['30 days', '45 days', '90 days', '180 days'],
            correctIndex: 1,
            explanation: '45 days to identify, 180 days to close — these deadlines are fixed with very limited exceptions.',
          },
          {
            question: 'What is "boot" in a 1031 exchange?',
            options: ['The required down payment', 'Cash or non-like-kind property received — it is taxable', 'Earnest money deposit', 'A property eligible for exchange'],
            correctIndex: 1,
            explanation: 'Boot triggers immediate taxation. To fully defer taxes, all proceeds must be reinvested in like-kind property.',
          },
          {
            question: 'Who must hold the exchange proceeds?',
            options: ['The buyer\'s attorney', 'The seller', 'A Qualified Intermediary', 'The title company'],
            correctIndex: 2,
            explanation: 'The IRS requires a QI to hold funds — if the seller touches the money at any point, the exchange is disqualified.',
          },
        ],
      },
      {
        title: 'Tenant & Landlord Rep',
        duration: '16 min',
        content: `In commercial leasing, you typically represent either the landlord (as their listing agent) or the tenant (as their representative). Each role has distinct responsibilities and conflicts of interest.\n\n**Landlord Representation**\n- List the space, market to tenant prospects and brokers\n- Negotiate from the landlord's perspective: highest rent, least TIA, shortest free rent, personal guarantees\n- Manage the broker community — cooperating brokers bring deals, so be responsive and pay fair commissions\n- Track leasing pipeline, update landlord on market conditions\n\n**Tenant Representation**\nTenant rep is arguably more complex because you're managing a more involved process:\n- Needs analysis: how much space, what configuration, budget, parking, growth options\n- Market survey: identify all options in target submarkets\n- RFP (Request for Proposals): send standardized requirements to multiple landlords to create competitive tension\n- Comparison matrix: apples-to-apples cost comparison over lease term (TotalCost of Occupancy)\n- Negotiate best economics: free rent, TIA, rate, term, options\n\n**Total Cost of Occupancy (TCO)**\nTCO = (Base Rent × Years) + NNN Costs − TIA − Free Rent Value\n\nAlways present options in TCO format — base rent alone is misleading.\n\n**Conflict of Interest**\nDual agency (representing both sides) in commercial is legal in most states but creates inherent conflicts. Disclose always, document everything.`,
        keyPoints: [
          'Tenant rep: create competitive tension through RFP to multiple landlords',
          'Compare options on Total Cost of Occupancy, not just base rent',
          'Landlord rep: manage broker community as a key source of deals',
          'Dual agency in commercial is legal but requires full disclosure',
        ],
        quiz: [
          {
            question: 'What is Total Cost of Occupancy (TCO)?',
            options: ['Just the monthly base rent', '(Base Rent × Years) + NNN Costs − TIA − Free Rent Value', 'The landlord\'s profit margin', 'The tenant\'s moving costs'],
            correctIndex: 1,
            explanation: 'TCO provides an apples-to-apples comparison of competing spaces over the full lease term — base rent alone is misleading.',
          },
          {
            question: 'What is the purpose of an RFP in tenant representation?',
            options: ['Requesting a price reduction after signing', 'Sending standardized requirements to multiple landlords to create competitive tension', 'Applying for a zoning permit', 'Filing a lease renewal'],
            correctIndex: 1,
            explanation: 'Competitive tension through an RFP process typically produces better economics than negotiating with a single landlord.',
          },
          {
            question: 'Commercial dual agency requires:',
            options: ['Automatic government disclosure', 'Full disclosure to both parties and documentation — it is legal but creates conflicts', 'Extra commission from both sides', 'Prior state board approval'],
            correctIndex: 1,
            explanation: 'While dual agency is legal in most states, the inherent conflict of representing both sides demands full transparency.',
          },
        ],
      },
      {
        title: 'Market Analysis',
        duration: '24 min',
        content: `Commercial real estate decisions are driven by market fundamentals. Understanding supply, demand, vacancy, and rent trends is essential for advising clients and underwriting investments.\n\n**Market Structure**\nMarkets are divided into submarkets — geographic clusters with similar characteristics. A "Chicago office market" means nothing; "Chicago CBD Class A office" is useful.\n\n**Key Metrics by Asset Class**\n\nOffice: Vacancy rate, absorption, average asking rent, sublease availability rate\nRetail: Vacancy rate, retail sales per square foot, co-tenancy, foot traffic\nIndustrial: Vacancy, rent growth, port proximity, clear height, available power\nMultifamily: Vacancy/occupancy, asking vs. effective rent, concessions, new supply pipeline\n\n**Demand Drivers**\nAlways trace demand to economic fundamentals:\n- Office: employment growth, especially FIRE (Finance, Insurance, Real Estate) and tech sectors\n- Retail: population growth, household income, consumer spending trends\n- Industrial: e-commerce penetration, port activity, manufacturing activity\n- Multifamily: household formation, in-migration, home affordability\n\n**Supply Analysis**\nTrack under-construction pipeline, deliveries, and conversions. Supply takes 2-4 years from approval to delivery, so today's construction activity predicts future competition.\n\n**Data Sources**\nCOSTAR (institutional standard), Cushman & Wakefield research, JLL reports, Marcus & Millichap research, and CBRE Econometric Advisors. For small markets, county assessor and permit data may be your best source.`,
        keyPoints: [
          'Analyze submarkets, not entire metros — granularity matters',
          'Trace demand back to economic fundamentals for each asset class',
          'Supply pipeline takes 2-4 years — today\'s starts predict future vacancy',
          'Use CoStar for institutional-quality market data',
        ],
        quiz: [
          {
            question: 'For industrial real estate, what is a critical demand driver?',
            options: ['School district ratings', 'Retail sales per square foot', 'E-commerce penetration and port activity', 'Office employment growth'],
            correctIndex: 2,
            explanation: 'Industrial demand is driven by logistics, distribution, and manufacturing — e-commerce growth and port proximity are key indicators.',
          },
          {
            question: 'What metric best describes how fast properties are absorbing in a market?',
            options: ['Asking rent per square foot', 'Absorption rate', 'Building age', 'Permit count'],
            correctIndex: 1,
            explanation: 'Net absorption measures how much space tenants are actually occupying vs. vacating — the clearest demand signal.',
          },
          {
            question: 'How long does it typically take from approval to delivery of a new commercial building?',
            options: ['6–12 months', '1–2 years', '2–4 years', '5–7 years'],
            correctIndex: 2,
            explanation: 'Long construction timelines mean today\'s pipeline data predicts future competitive supply 2–4 years out.',
          },
        ],
      },
    ],
  },
  {
    id: 'mortgage',
    title: 'Mortgage & Lending',
    description: 'Master loan products, underwriting, and deal structuring for residential and commercial financing.',
    icon: 'card-outline',
    color: '#E6A23C',
    tiers: ['starter', 'pro', 'elite', 'lending'],
    creditHours: 12,
    lessons: [
      {
        title: 'SBA 7(a) & 504 Programs',
        duration: '20 min',
        content: `SBA loans are government-backed financing programs designed to help small businesses access capital. Two primary programs for real estate: 7(a) and 504.\n\n**SBA 7(a) — Flexible Working Capital & Real Estate**\n- Maximum loan: $5 million\n- Rates: WSJ Prime + 2.75% (variable) or fixed options\n- Terms: up to 25 years for real estate, 10 years for equipment\n- Use cases: purchase, renovation, refinance, business acquisition\n- Down payment: typically 10% (vs. 25-30% conventional)\n- Key requirement: owner-occupancy (51% for existing, 60% for new construction)\n\n**SBA 504 — Fixed-Rate Long-Term Real Estate**\n- Structure: 50% conventional bank + 40% SBA debenture + 10% borrower\n- Maximum SBA portion: $5.5 million ($5.5M for energy projects)\n- Rate: fixed, tied to 5- and 10-year Treasury\n- Terms: 20 or 25 years\n- Use: owner-occupied commercial real estate and equipment\n- Advantage: fixed long-term rate, low down payment, preservation of working capital\n\n**Eligibility Requirements**\n- For-profit business in the US\n- Tangible net worth < $15 million AND average net income < $5 million over 2 years\n- Cannot be publicly traded\n- No other financing sources available on reasonable terms\n\n**The SBA Packaging Process**\nSBA loans require more documentation than conventional: 3 years tax returns (personal and business), financial statements, business plan for startups, debt schedule, and environmental questionnaire for real estate.`,
        keyPoints: [
          '7(a): flexible up to $5M, 10% down for owner-occupied RE',
          '504: 50/40/10 structure with fixed long-term rate',
          'Owner-occupancy required: 51% existing, 60% new construction',
          'SBA requires significantly more documentation than conventional',
        ],
        quiz: [
          {
            question: 'What is the maximum SBA 7(a) loan amount?',
            options: ['$1 million', '$2.5 million', '$5 million', '$10 million'],
            correctIndex: 2,
            explanation: 'SBA 7(a) goes up to $5M with competitive terms — the low down payment (10%) is its main advantage over conventional commercial loans.',
          },
          {
            question: 'What is the typical SBA 504 loan structure?',
            options: ['100% SBA financing', '50% bank + 40% SBA + 10% borrower', '80% bank + 20% SBA', '70% bank + 30% borrower'],
            correctIndex: 1,
            explanation: 'The 50/40/10 structure preserves borrower working capital while giving lenders security through the layered structure.',
          },
          {
            question: 'What owner-occupancy percentage is required for an existing building with SBA financing?',
            options: ['25%', '51%', '75%', '100%'],
            correctIndex: 1,
            explanation: 'SBA requires at least 51% owner-occupancy for existing buildings (60% for new construction) to qualify as an owner-occupied business loan.',
          },
        ],
      },
      {
        title: 'CMBS & Bridge Lending',
        duration: '22 min',
        content: `Commercial Mortgage-Backed Securities (CMBS) and bridge loans serve different parts of the commercial real estate capital stack.\n\n**CMBS Overview**\nCMBS are bonds backed by commercial mortgages. Lenders originate loans, pool them, and sell them as securities. This allows lenders to recycle capital and often offer competitive rates.\n\nCMBS characteristics:\n- Non-recourse (property is collateral, not borrower personally)\n- Typically 10-year fixed rate with 25-30 year amortization or interest-only\n- Prepayment penalties are severe: defeasance or yield maintenance\n- Serviced by a special servicer when in default\n- Reporting requirements: quarterly financials, annual inspections\n\n**When to Use CMBS**\nBest for stabilized assets with predictable cash flow: anchored retail, multifamily, office with strong lease terms. Not ideal for value-add or transitional properties.\n\n**Bridge Loans**\nBridge loans are short-term (6–36 months), higher-rate loans for transitional situations:\n- Acquiring a property with occupancy below permanent financing thresholds (85%+)\n- Completing a renovation or lease-up\n- Buying quickly without time for full underwriting\n- Taking advantage of an opportunity before longer-term financing can close\n\nBridge loan rates: typically SOFR + 300–600 bps (significantly above CMBS). The higher rate compensates for transitional risk.\n\n**Exit Strategy**\nEvery bridge loan needs a clear exit: refinance into CMBS or agency, sell the asset, or pay off with equity raise. Lenders will ask about exit strategy before approving.`,
        keyPoints: [
          'CMBS is non-recourse with severe prepayment penalties',
          'Use CMBS for stabilized assets, bridge for transitional/value-add',
          'Bridge rates are SOFR + 300-600bps — expensive but fast and flexible',
          'Always underwrite a clear bridge loan exit strategy',
        ],
        quiz: [
          {
            question: 'CMBS loans are characterized as:',
            options: ['Recourse, short-term, variable rate', 'Non-recourse, typically 10-year fixed with severe prepayment penalties', 'Government-backed with flexible terms', 'Only available for residential properties'],
            correctIndex: 1,
            explanation: 'CMBS non-recourse structure protects the borrower personally, but the severe prepayment penalties make them inflexible for short-hold strategies.',
          },
          {
            question: 'Bridge loans are best suited for:',
            options: ['Stabilized, long-term holds', 'Transitional properties needing renovation or lease-up', 'Owner-occupied primary residences', 'Government agencies'],
            correctIndex: 1,
            explanation: 'Bridge loans fill the gap when a property doesn\'t yet qualify for permanent financing — they\'re short-term and expensive by design.',
          },
          {
            question: 'A bridge loan exit strategy should be:',
            options: ['Identified after closing', 'Not required by lenders', 'Clearly defined before approval — refinance, sell, or equity raise', 'Optional for experienced borrowers'],
            correctIndex: 2,
            explanation: 'Lenders will not approve a bridge loan without understanding how and when it will be paid off — the exit is part of the underwriting.',
          },
        ],
      },
      {
        title: 'DSCR & Underwriting',
        duration: '25 min',
        content: `Debt Service Coverage Ratio (DSCR) is the single most important metric in commercial real estate underwriting. It measures a property's ability to service its debt from operating income.\n\n**DSCR Formula**\nDSCR = NOI ÷ Annual Debt Service\n\nExample:\n- NOI: $300,000\n- Annual debt service (P+I): $240,000\n- DSCR = 1.25x\n\n**Lender Requirements**\n- Most commercial lenders: minimum 1.20x–1.25x DSCR\n- SBA: typically 1.25x global DSCR (property + borrower income vs. all debt)\n- Agency (Fannie/Freddie): 1.25x–1.35x for multifamily\n- Conservative lenders: 1.30x or higher\n\n**Global DSCR**\nFor SBA and some other lenders, they underwrite the borrower's global cash flow: business income + real estate NOI − all personal and business debt payments. This is why personal tax returns matter even for commercial loans.\n\n**Stress Testing**\nSophisticated underwriters stress DSCR by modeling:\n- 10-15% vacancy increase\n- 5-10% expense increase\n- Rate increase scenarios for variable rate debt\n\nIf the property still meets DSCR at stressed assumptions, it's a conservative investment.\n\n**Common Underwriting Adjustments**\n- Management fee: 3-8% of gross rents (even if self-managed)\n- Reserves: $0.10-$0.25/sq ft annual reserve for capex\n- Vacancy: never underwrite at 0% — always include market-rate vacancy`,
        keyPoints: [
          'DSCR = NOI ÷ Annual Debt Service — minimum 1.20-1.25x for most lenders',
          'Global DSCR includes borrower personal income and all debts',
          'Always include management fee and reserves even if not current costs',
          'Stress test DSCR with higher vacancy and expenses before committing',
        ],
        quiz: [
          {
            question: 'What is the DSCR formula?',
            options: ['NOI ÷ Purchase Price', 'Gross Rent ÷ Mortgage Payment', 'NOI ÷ Annual Debt Service', 'Appraised Value ÷ Loan Amount'],
            correctIndex: 2,
            explanation: 'DSCR measures how many times the property\'s income can cover its debt payments — a 1.25x DSCR means the property earns 25% more than the debt cost.',
          },
          {
            question: 'What is the minimum DSCR most commercial lenders require?',
            options: ['0.90x', '1.00x', '1.20–1.25x', '1.50x'],
            correctIndex: 2,
            explanation: 'The 1.20–1.25x minimum provides a buffer against vacancy increases and expense surprises without over-constraining the deal.',
          },
          {
            question: 'Why include a management fee even if the property is self-managed?',
            options: ['It\'s legally required', 'To accurately reflect true operating costs and stress-test deal sustainability', 'Only required for properties over $1M', 'Self-managed properties don\'t need it'],
            correctIndex: 1,
            explanation: 'If you sell or can\'t manage anymore, the new owner pays management fees — underwriting without it creates an inflated NOI.',
          },
        ],
      },
      {
        title: 'LTV, LTC & Loan Sizing',
        duration: '18 min',
        content: `Loan-to-Value (LTV) and Loan-to-Cost (LTC) are the primary constraints on commercial loan sizing, along with DSCR.\n\n**Loan-to-Value (LTV)**\nLTV = Loan Amount ÷ Appraised Value\n\nLenders cap LTV to protect against value declines:\n- Multifamily (Fannie/Freddie): up to 80% LTV\n- Commercial (bank): typically 65-75% LTV\n- SBA 7(a): up to 90% LTV\n- Hard money: 65-70% of ARV\n\n**Loan-to-Cost (LTC)**\nLTC = Loan Amount ÷ Total Project Cost (purchase + renovation)\n\nUsed for construction and value-add deals where appraisal is based on projected value, not current value. Lenders use LTC to ensure borrower has meaningful equity in the deal from day one.\n\n**Which Constrains the Loan?**\nBoth LTV and DSCR are applied simultaneously — the lower resulting loan amount wins. Example:\n- Based on LTV (75%): $3,750,000 loan\n- Based on DSCR (1.25x): $2,900,000 loan\n- Lender will offer: $2,900,000\n\n**As-Is vs. As-Stabilized Value**\nFor value-add deals, appraisers provide both: current "as-is" value and projected "as-stabilized" value after renovation/lease-up. Lenders may lend against stabilized value but typically hold back proceeds in a reserve to be released as work is completed.`,
        keyPoints: [
          'LTV is capped by asset type: 65-80% conventional, up to 90% SBA',
          'LTC applies to construction/value-add based on total project cost',
          'The binding constraint is whichever gives the smaller loan — LTV or DSCR',
          'As-stabilized value allows more proceeds but with holdback reserves',
        ],
        quiz: [
          {
            question: 'LTC (Loan-to-Cost) is primarily used for:',
            options: ['Stabilized income properties', 'Single-family homes', 'Construction and value-add deals', 'Government-backed loans only'],
            correctIndex: 2,
            explanation: 'LTC ensures the borrower has real equity in a project from day one — it\'s used when appraised value doesn\'t yet exist.',
          },
          {
            question: 'If LTV supports a $3.75M loan but DSCR only supports $2.9M, what does the lender offer?',
            options: ['$3,750,000', '$3,325,000 (the average)', '$2,900,000', 'They decline the loan'],
            correctIndex: 2,
            explanation: 'The binding constraint wins — whichever test produces the smaller loan amount is what the lender will offer.',
          },
          {
            question: '"As-stabilized value" in appraisal means:',
            options: ['The current market value', 'The projected value after renovation and lease-up', 'The bank\'s internal assessed value', 'Replacement cost of the building'],
            correctIndex: 1,
            explanation: 'As-stabilized value allows lenders to size a larger loan, but they typically hold back portions until improvements are verified.',
          },
        ],
      },
      {
        title: 'Rate Locks & Interest Rate Risk',
        duration: '14 min',
        content: `Interest rate risk management is a critical skill for mortgage professionals. Rates can move significantly during the loan process, affecting both affordability and deal viability.\n\n**Rate Lock Basics**\nA rate lock guarantees a specific interest rate for a defined period. Standard residential locks: 15, 30, 45, or 60 days. Commercial: 30-60 days standard, up to 120-180 days for complex deals.\n\nRate lock pricing: shorter locks are cheaper (or free); longer locks cost more in the form of higher rate or upfront fees.\n\n**Float-Down Options**\nSome lenders offer float-down provisions: the borrower can capture a lower rate if rates decrease during the lock period. Usually costs 0.125-0.25% of the loan amount.\n\n**Lock-In Strategy**\n- If rates are rising: lock early, lock longer\n- If rates are falling: float (don't lock), capture the lower rate at closing\n- When volatile: lock on the first good day, don't try to time the bottom\n\n**Index + Margin**\nARMs and commercial floating-rate loans use: Rate = Index + Margin\n- Common indexes: SOFR (replaced LIBOR), Prime Rate, 5-year Treasury\n- Margin is fixed; index floats\n\n**Hedging Tools (Commercial)**\nFor large commercial deals: interest rate caps (limits maximum rate exposure), swaps (converts floating to fixed), and collars (both cap and floor). These are structured finance tools that add cost but reduce risk for long-term holds.`,
        keyPoints: [
          'Longer rate locks cost more — factor into pricing comparison',
          'In rising rate environments: lock early and lock longer',
          'Float-down options provide downside protection at a cost',
          'Rate = Index + Margin for adjustable-rate products',
        ],
        quiz: [
          {
            question: 'In a rising rate environment, what lock strategy is recommended?',
            options: ['Float as long as possible', 'Lock early and lock longer', 'Never lock — always float', 'Wait for the Federal Reserve announcement'],
            correctIndex: 1,
            explanation: 'When rates are trending up, locking in secures the current rate — the cost of a longer lock is far less than the cost of a rate spike.',
          },
          {
            question: 'What is a float-down option?',
            options: ['Converting a fixed rate to variable', 'A provision allowing the borrower to capture a lower rate if rates drop during the lock', 'A penalty for floating too long', 'An option to delay closing'],
            correctIndex: 1,
            explanation: 'Float-down options cost 0.125–0.25% but provide downside protection — you lock in protection while retaining some upside.',
          },
          {
            question: 'The formula for an ARM loan rate is:',
            options: ['Prime Rate × Margin', 'Loan Amount ÷ Term', 'Index + Margin', 'DSCR + Spread'],
            correctIndex: 2,
            explanation: 'The index (SOFR, Prime, Treasury) floats with the market; the margin is fixed by the lender at origination.',
          },
        ],
      },
      {
        title: 'Hard Money & Private Lending',
        duration: '16 min',
        content: `Hard money and private lending are asset-based financing — the property is the primary collateral, and underwriting focuses on the deal, not the borrower's creditworthiness.\n\n**Hard Money Characteristics**\n- Rates: 10-15% (sometimes higher)\n- Terms: 6-24 months\n- LTV: 60-70% of ARV (After Repair Value)\n- Points: 2-4 points origination\n- Approval speed: 5-15 days (sometimes faster)\n- Use case: fix-and-flip, distressed acquisitions, bridge situations\n\n**The Math of Hard Money**\nExample: $200,000 ARV, 65% LTV = $130,000 loan\n- Purchase: $90,000\n- Renovation: $30,000 = $120,000 total cost\n- Loan: $130,000 (covers purchase + rehab + reserve)\n- Rate: 12%, 1-year term = $15,600 interest\n- 3 points: $3,900\n- Total financing cost: ~$19,500\n\n**Private Lending**\nPrivate lenders are individuals (not institutions) lending their own capital. Often more flexible than hard money companies, with negotiated terms. Found through real estate networks, attorney introductions, and real estate investor associations.\n\n**DSCR Loans (Long-Term Rental)**\nDSCR loans are a newer product — qualifying based solely on property cash flow, not borrower income. No tax returns, no employment verification. DSCR ≥ 1.0 typically required; rates 1-2% above conventional. Ideal for investors with multiple properties or non-W2 income.`,
        keyPoints: [
          'Hard money: 65-70% LTV of ARV, 10-15% rate, 2-4 points',
          'Asset-based: deal quality matters more than borrower credit',
          'Private lenders are individuals — more flexible, found through networks',
          'DSCR loans: qualify on property income only, no tax returns',
        ],
        quiz: [
          {
            question: 'Hard money loans are primarily underwritten based on:',
            options: ['Borrower credit score', 'Borrower income and employment', 'The property\'s After Repair Value (ARV)', 'The borrower\'s net worth'],
            correctIndex: 2,
            explanation: 'Hard money is asset-based lending — the deal must make sense on paper even if the borrower has no credit history.',
          },
          {
            question: 'What does ARV stand for?',
            options: ['Annual Rental Value', 'After Repair Value', 'Adjusted Real Value', 'Asset Replacement Value'],
            correctIndex: 1,
            explanation: 'ARV is the projected market value after all renovations are complete — it\'s the ceiling for hard money loan sizing.',
          },
          {
            question: 'DSCR non-QM loans qualify borrowers based on:',
            options: ['W-2 income only', 'Property cash flow — no tax returns required', '3 years of bank statements', '2 years of self-employment income'],
            correctIndex: 1,
            explanation: 'DSCR loans are ideal for investors with complex income structures — the property pays for itself in the underwriting model.',
          },
        ],
      },
      {
        title: 'Conventional, FHA & VA',
        duration: '18 min',
        content: `These three loan programs cover the majority of residential purchase and refinance transactions. Understanding the key differences helps you match borrowers to the right product.\n\n**Conventional Loans**\n- Conforming: meets Fannie Mae/Freddie Mac guidelines, maximum loan limits vary by county\n- Jumbo: above conforming limits, stricter requirements (720+ credit, 20%+ down, larger reserves)\n- PMI required below 20% down (0.5-1.5% annually, cancellable at 80% LTV)\n- Rates: typically lowest for well-qualified borrowers\n\n**FHA Loans**\n- 3.5% down with 580+ credit score; 10% down with 500-579\n- MIP: 1.75% upfront (added to loan) + 0.55% annual (for 30-year term with <10% down, now permanent)\n- FHA appraisals are more stringent — property must meet HUD Minimum Property Standards\n- Loan limits vary by county and area\n- Ideal for first-time buyers with limited savings or lower credit\n\n**VA Loans**\n- 0% down, no PMI, competitive rates\n- Available to eligible veterans, active duty, and surviving spouses\n- VA Funding Fee: 2.15-3.3% (waived for service-connected disability)\n- Certificate of Eligibility (COE) required\n- VA appraisal (MPR inspection) required\n- No maximum loan amount (though lenders have limits above conforming)\n\n**Program Comparison Quick Guide**\n- Low down payment, lower credit: FHA\n- Military/veteran: always check VA first\n- Strong credit, 10-20% down: Conventional\n- High price point: Jumbo conventional`,
        keyPoints: [
          'FHA: 3.5% down, but permanent MIP — refinance out when you can',
          'VA: 0% down, no PMI, best rate for eligible veterans',
          'Conventional: best rate for 680+ credit with 20%+ down',
          'Jumbo requires stronger reserves and lower DTI than conforming',
        ],
        quiz: [
          {
            question: 'When should a veteran always explore VA loans?',
            options: ['Only if they have poor credit', 'Before considering any other loan type — 0% down, no PMI', 'Only for second homes', 'After being declined by conventional lenders'],
            correctIndex: 1,
            explanation: 'VA loans offer the best combination of rate, terms, and down payment for eligible veterans — always check VA eligibility first.',
          },
          {
            question: 'FHA\'s annual MIP for 30-year loans with less than 10% down:',
            options: ['Can be cancelled at 80% LTV', 'Is permanent for the life of the loan', 'Expires after 5 years', 'Is not required for first-time buyers'],
            correctIndex: 1,
            explanation: 'Unlike PMI, FHA MIP on loans with <10% down is permanent — refinancing into conventional once you have 20% equity is the common strategy.',
          },
          {
            question: 'Jumbo loans (above conforming limits) typically require:',
            options: ['Lower credit scores than conforming', 'Government backing', 'Higher credit scores, larger down payments, and more reserves', 'FHA insurance'],
            correctIndex: 2,
            explanation: 'Without government backing, jumbo lenders manage their own risk — stricter guidelines reflect the larger loan amounts at stake.',
          },
        ],
      },
      {
        title: 'ARMs & Buydowns',
        duration: '14 min',
        content: `Adjustable-Rate Mortgages and buydowns are tools to lower initial payments or manage rate risk.\n\n**Adjustable-Rate Mortgages (ARMs)**\nARM structure: initial fixed period + adjustment period\n- 5/1 ARM: Fixed for 5 years, adjusts annually thereafter\n- 7/1 ARM: Fixed 7 years, annual adjustments\n- 10/1 ARM: Fixed 10 years, annual adjustments\n\nRate caps protect borrowers:\n- Initial cap: maximum change at first adjustment (typically 2%)\n- Periodic cap: maximum change per adjustment period (2%)\n- Lifetime cap: maximum total increase (5-6%)\n\n**When ARMs Make Sense**\n- Borrower plans to sell or refinance before the fixed period ends\n- Investor properties — lower rate means better cash flow\n- Rates are elevated and likely to decrease\n\n**Temporary Buydowns**\nA temporary buydown reduces the rate for the initial years of the loan:\n- 2-1 Buydown: Rate is 2% below note rate in year 1, 1% below in year 2, at note rate thereafter\n- 1-0 Buydown: Rate is 1% below note rate in year 1, at note rate thereafter\n- Seller or builder often pays for the buydown as a concession\n- Cost: roughly 1% of loan per year of subsidy\n\n**Permanent Buydown (Points)**\nPaying discount points at closing to reduce the permanent interest rate:\n- 1 point = 1% of loan amount\n- Each point typically buys down 0.25% in rate\n- Break-even: divide point cost by monthly savings to find payback period`,
        keyPoints: [
          'ARM caps: 2% initial / 2% periodic / 5-6% lifetime — protect borrowers',
          'ARMs make sense when selling or refinancing before adjustment period',
          '2-1 buydown: 2% lower year 1, 1% lower year 2 — seller often pays',
          'Point break-even: point cost ÷ monthly savings = payback months',
        ],
        quiz: [
          {
            question: 'A 5/1 ARM means the rate is fixed for:',
            options: ['1 year, then adjusts every 5 years', '5 years, then adjusts annually', '5 months, then adjusts monthly', '5% rate plus one origination point'],
            correctIndex: 1,
            explanation: 'The first number is always the fixed period in years; the second is the adjustment frequency in years after that.',
          },
          {
            question: 'In a 2-1 buydown, what is the rate in Year 2?',
            options: ['2% below note rate', 'At the full note rate', '1% below note rate', 'It adjusts to market rate'],
            correctIndex: 2,
            explanation: '2-1 buydown: Year 1 is 2% below, Year 2 is 1% below, Year 3+ is at the full note rate.',
          },
          {
            question: 'How do you calculate the break-even period for paying discount points?',
            options: ['Multiply points by monthly payment', 'Divide point cost by monthly payment savings', 'Add points to the rate', 'Divide monthly savings by the loan amount'],
            correctIndex: 1,
            explanation: 'Break-even = total point cost ÷ monthly savings. If you plan to keep the loan longer than the break-even period, points make sense.',
          },
        ],
      },
      {
        title: 'Borrower Qualification',
        duration: '20 min',
        content: `Qualifying a borrower requires analyzing the four Cs of credit: Capacity, Capital, Collateral, and Credit.\n\n**Capacity — Income Analysis**\nW-2 Employees: Use 2-year average of gross income. Overtime and bonus included if 2-year history documented.\n\nSelf-Employed: Use 2-year average of Schedule C net income (after depreciation add-back for real estate investors). This is where many self-employed borrowers struggle — deductions that reduce taxes also reduce qualifying income.\n\nRental Income: 75% of gross rents (or lease amounts) less documented expenses. For new rental properties, use appraiser's market rent schedule.\n\n**Capital — Assets & Down Payment**\nSource and season all funds: bank statements for 60 days minimum. Large unexplained deposits must be documented (gift letter if from family, business document if from sale).\n\nReserves: lenders want 2-6 months PITI in reserves after down payment and closing costs.\n\n**Collateral — Property Analysis**\nAppraisal must support contract price. For conventional loans, PMI and LTV are calculated on the lesser of purchase price or appraised value.\n\n**Credit**\n- FICO scores from all 3 bureaus; middle score used for qualification\n- 620+ minimum for most conventional; 580+ for FHA; 620+ typical for VA\n- DTI limits: 43-50% back-end DTI for most programs\n- Recent collections, judgments, and late payments require explanation letters`,
        keyPoints: [
          '4 Cs: Capacity (income), Capital (assets), Collateral, Credit',
          'Self-employed income: 2-year average of Schedule C net — deductions reduce qualifying',
          'Source and season all down payment/closing cost funds — 60 days bank statements',
          'Middle FICO score used; 43-50% max back-end DTI',
        ],
        quiz: [
          {
            question: 'What are the 4 Cs of mortgage underwriting?',
            options: ['Cash, Credit, Collateral, Construction', 'Capacity, Capital, Collateral, Credit', 'Cost, Credit, Cash, Compliance', 'Coverage, Capacity, Cash, Closing'],
            correctIndex: 1,
            explanation: 'Every mortgage is underwritten through these four lenses — weakness in any C can disqualify or limit the loan.',
          },
          {
            question: 'How is self-employed income typically calculated for mortgage qualification?',
            options: ['Current year\'s gross revenue', '2-year average of Schedule C net income', 'The higher of the last 2 years\' income', 'Gross income before deductions'],
            correctIndex: 1,
            explanation: 'Lenders use net Schedule C income — the same deductions that reduce your taxes also reduce your qualifying income.',
          },
          {
            question: 'What is the minimum bank statement seasoning period for down payment funds?',
            options: ['30 days', '60 days', '90 days', '6 months'],
            correctIndex: 1,
            explanation: '60 days of bank statements is the standard — large unexplained recent deposits will require a paper trail.',
          },
        ],
      },
      {
        title: 'Loan Processing & Closing',
        duration: '22 min',
        content: `Understanding the loan process from application to closing allows mortgage professionals to set accurate expectations and prevent last-minute surprises.\n\n**The Loan Process Timeline**\n1. **Application** — collect all borrower documents, run credit, issue Loan Estimate (3 business days)\n2. **Processing** — processor organizes file, orders appraisal, verification of employment/income/assets\n3. **Appraisal** — independent appraiser values the property (5-10 days typical)\n4. **Underwriting** — underwriter reviews complete file, issues approval, conditional approval, or denial\n5. **Conditions** — borrower clears all conditions (additional documents, letters, explanations)\n6. **Clear to Close (CTC)** — underwriter approves all conditions\n7. **Closing Disclosure** — issued 3 business days before closing (TRID rule)\n8. **Closing** — signing, funding, recording\n\n**Common Delays**\n- Appraisal issues: value comes in low (renegotiate or switch lenders)\n- Underwriter conditions: missing documents, unexplained deposits, employment gaps\n- Title issues: liens, judgments, missing easements\n- Last-minute credit changes: never let borrowers make large purchases or open new accounts during the loan process\n\n**The TRID Rule**\nKnow Your Customer regulations under TRID (TILA-RESPA Integrated Disclosure):\n- Loan Estimate due within 3 business days of application\n- Closing Disclosure due 3 business days before closing\n- Changes to APR >0.125% require new CD and new 3-day wait\n\n**Clear to Close Checklist**\nBefore issuing CTC, underwriter verifies: income, assets, credit, title, appraisal, flood cert, hazard insurance, all conditions cleared, final VOE (verbal verification of employment within 10 days of closing).`,
        keyPoints: [
          'Never let borrowers open credit or make large purchases during processing',
          'TRID: Loan Estimate within 3 days of application; CD 3 days before closing',
          'Appraisal low value: renegotiate price, challenge appraisal, or switch lenders',
          'Final VOE required within 10 days of closing — verify employment is still active',
        ],
        quiz: [
          {
            question: 'Under TRID, when must the Closing Disclosure be delivered to the borrower?',
            options: ['At least 1 business day before closing', 'At closing', 'At least 3 business days before closing', '7 days before closing'],
            correctIndex: 2,
            explanation: 'The 3-business-day waiting period after the CD is mandatory — changes to APR >0.125% restart the clock.',
          },
          {
            question: 'What should borrowers NEVER do during the loan process?',
            options: ['Submit additional income documentation', 'Open new credit accounts or make large purchases', 'Provide updated bank statements', 'Verify employment information'],
            correctIndex: 1,
            explanation: 'New debt or large deposits can disqualify a loan that was already approved — coach borrowers to freeze all financial activity until after closing.',
          },
          {
            question: 'When must the final Verbal Verification of Employment (VOE) be completed?',
            options: ['At the time of application', '30 days before closing', 'Within 10 days of closing', 'On the day of closing'],
            correctIndex: 2,
            explanation: 'A final VOE within 10 days confirms the borrower is still employed — losing a job before closing would require new underwriting.',
          },
        ],
      },
    ],
  },
  {
    id: 'realtor_growth',
    title: 'Realtor Business Growth',
    description: 'Build a referral-based real estate business through SOI systems, branding, and scalable lead generation.',
    icon: 'trending-up-outline',
    color: '#9B59B6',
    tiers: ['pro', 'elite'],
    creditHours: 7,
    lessons: [
      {
        title: 'SOI System',
        duration: '20 min',
        content: `Your Sphere of Influence (SOI) is the single most reliable source of real estate business. Studies consistently show that 70%+ of business comes from people who know you or were referred by someone who does.\n\n**Building Your Database**\nStart by listing every person you know: family, friends, past coworkers, classmates, neighbors, service providers, coaches, religious community. Import contacts from your phone, LinkedIn, email, and social media. A well-built SOI has 200-500 people.\n\n**Categorizing Your SOI**\nNot all contacts are equal. Score them:\n- **A+**: People who actively refer you — nurture intensely\n- **A**: People who know you well and would refer if reminded\n- **B**: People who know you casually — build the relationship\n- **C**: New contacts with potential\n\n**The 33-Touch Program**\nTouch your database 33 times per year through a mix of:\n- 12 monthly market updates (email or mail)\n- 4 seasonal cards (physical mail — stands out)\n- 12 pop-by visits or personal calls to A/A+ contacts\n- 5 value-add touches (newsletter, event invite, referral to their business)\n\n**Converting SOI to Referrals**\nAsk directly, but create a context: "I'm trying to grow my business and I rely on referrals from people I trust. If you know anyone thinking about buying or selling, I'd love an introduction." Then make it easy with a text introduction template they can forward.\n\n**Client Events**\nHosting annual client events (summer cookout, holiday party, educational seminar) deepens relationships and gives you a natural reason to reconnect with your entire database.`,
        keyPoints: [
          'SOI = 200-500 contacts who know you or know someone who does',
          '33-touch program: 12 market updates + 4 seasonal cards + personal calls',
          'A+ contacts refer actively — nurture them weekly',
          'Client events create natural annual reconnection with entire database',
        ],
        quiz: [
          {
            question: 'How many contacts should a well-built Sphere of Influence (SOI) include?',
            options: ['20–50', '50–100', '200–500', '1,000+'],
            correctIndex: 2,
            explanation: '200–500 contacts gives you enough depth to generate consistent referrals while staying manageable for personal outreach.',
          },
          {
            question: 'The 33-touch program includes how many monthly market updates per year?',
            options: ['4', '6', '12', '24'],
            correctIndex: 2,
            explanation: '12 monthly market updates (one per month) keep you top of mind as a market expert throughout the year.',
          },
          {
            question: 'An A+ contact in your SOI is someone who:',
            options: ['You\'ve met recently', 'Actively refers you — nurture intensely', 'Is ready to transact in 90 days', 'Is a past client from 5+ years ago'],
            correctIndex: 1,
            explanation: 'A+ contacts are your highest-value relationship asset — they generate business without being asked. Protect and nurture these relationships weekly.',
          },
        ],
      },
      {
        title: 'CRM Setup & Management',
        duration: '16 min',
        content: `A Customer Relationship Management system is your business operating system. Without one, you're running your business from memory — and memory is unreliable.\n\n**CRM Selection Criteria**\n- Real estate specific vs. general purpose (Salesforce, HubSpot)\n- Contact management, pipeline tracking, task automation\n- Email/text integration\n- Mobile app for on-the-go updates\n- Popular real estate CRMs: Follow Up Boss, LionDesk, KVCore, Chime, Top Producer\n\n**Minimum Viable CRM Setup**\nEven a simple system used consistently beats a sophisticated system used sporadically:\n1. Import all contacts with complete information (phone, email, birthday)\n2. Tag every contact: SOI, past client, active buyer, active seller, investor, referral partner\n3. Set recurring touchpoints for A and A+ contacts\n4. Create pipelines: Leads → Active → Under Contract → Closed\n5. Log every interaction — calls, emails, showings, meetings\n\n**Automation Workflows**\nAutomate repetitive tasks:\n- New lead: immediate text + email + call task created\n- Closing anniversary: automated "happy anniversary" note\n- Birthday: automated card order or email\n- Monthly: market report email to entire database\n\n**CRM Discipline**\nThe 3-30-3 rule: spend 3 minutes updating CRM after each interaction, 30 minutes reviewing your pipeline daily, 3 hours monthly auditing your database for stale contacts.`,
        keyPoints: [
          'Choose any CRM and use it daily — consistency beats sophistication',
          'Tag every contact to enable targeted communication',
          'Automate birthdays, anniversaries, and monthly market reports',
          '3-30-3: 3 min after each call, 30 min daily pipeline review, 3 hr monthly audit',
        ],
        quiz: [
          {
            question: 'What is the most important factor in CRM effectiveness?',
            options: ['The software brand you choose', 'How many contacts are loaded', 'Using it consistently every day', 'Having automation set up'],
            correctIndex: 2,
            explanation: 'A simple CRM used every day beats a sophisticated one used sporadically — discipline is the differentiator.',
          },
          {
            question: 'The "3-30-3" CRM rule means:',
            options: ['3 calls per day, 30 contacts per week, 3 meetings per month', '3 min after each interaction, 30 min daily pipeline review, 3 hr monthly audit', '3% response rate, 30-day follow-up, 3 closings per month', '3 texts, 30 emails, 3 calls per lead'],
            correctIndex: 1,
            explanation: 'The 3-30-3 rhythm keeps your database current and your pipeline visible — small consistent habits prevent lost opportunities.',
          },
          {
            question: 'Which tag categories should every CRM contact have?',
            options: ['Transaction type and deal size', 'SOI, past client, active buyer/seller, investor, referral partner', 'Income level and credit score', 'State and zip code only'],
            correctIndex: 1,
            explanation: 'Status-based tags allow you to target communication precisely — sending the wrong message to the wrong person wastes both parties\' time.',
          },
        ],
      },
      {
        title: 'Social Media & Video Strategy',
        duration: '24 min',
        content: `Social media and video are the modern equivalent of door knocking — but scalable. One video can reach thousands; one good Instagram post can generate multiple leads.\n\n**Platform Strategy**\n- **Instagram**: Visual-first. Best for listings, neighborhood content, and behind-the-scenes. Reels get the most reach.\n- **Facebook**: Still dominant for 35+ demographic. Facebook Groups (neighborhood, community) are underutilized gold mines.\n- **YouTube**: Long-form is best for search — neighborhood tours, home-buying guides, market updates. Videos rank on Google.\n- **TikTok**: Fastest reach for younger buyers. Real estate content performs extremely well.\n- **LinkedIn**: Best for luxury, commercial, relocation, and corporate clients.\n\n**Content Pillars**\nCreate content across 4 pillars:\n1. **Market Education** — stats, trends, explainers (establishes expertise)\n2. **Local Life** — restaurants, events, neighborhoods (builds local identity)\n3. **Client Stories** — wins, transformations, testimonials (social proof)\n4. **Behind the Scenes** — your day, your process (humanizes you)\n\n**Video Production Basics**\nYou don't need expensive equipment:\n- Phone on a tripod + ring light = professional look\n- Record in landscape for YouTube, portrait for Reels/TikTok\n- Consistent thumbnail style and posting time builds audience\n- Hook in first 3 seconds — state the topic immediately\n\n**The 1-3-1 Weekly System**\n1 long-form YouTube video → 3 short clips from it → 1 blog post from the transcript. Maximum content from minimum effort.`,
        keyPoints: [
          'YouTube ranks on Google — neighborhood tours get long-term search traffic',
          '4 content pillars: Market Education, Local Life, Client Stories, Behind-the-Scenes',
          'First 3 seconds must hook the viewer — lead with the topic',
          '1-3-1 system: 1 YouTube video → 3 clips → 1 blog post',
        ],
        quiz: [
          {
            question: 'Which platform generates the most long-term search traffic for real estate content?',
            options: ['TikTok', 'Instagram', 'YouTube', 'Snapchat'],
            correctIndex: 2,
            explanation: 'YouTube videos rank on Google — a neighborhood tour from 3 years ago can still drive leads today.',
          },
          {
            question: 'What is the "1-3-1" content system?',
            options: ['1 listing, 3 tours, 1 closing per week', '1 YouTube video → 3 short clips → 1 blog post', '1 photo, 3 captions, 1 hashtag per day', '1 post per day on 3 different platforms'],
            correctIndex: 1,
            explanation: 'The 1-3-1 system maximizes content output from minimum effort — one production session creates a week of content across platforms.',
          },
          {
            question: 'What are the four content pillars for real estate social media?',
            options: ['Listings, Prices, Events, Team', 'Market Education, Local Life, Client Stories, Behind the Scenes', 'Buyers, Sellers, Investors, Renters', 'Home Tours, Tips, Stats, Giveaways'],
            correctIndex: 1,
            explanation: 'Rotating through these four pillars builds authority, relatability, trust, and human connection — the ingredients of a referral-generating brand.',
          },
        ],
      },
      {
        title: 'Geographic Farming',
        duration: '18 min',
        content: `Geographic farming means owning a neighborhood — becoming the go-to agent through consistent presence, value delivery, and market expertise.\n\n**Selecting Your Farm**\nIdeal farm characteristics:\n- 200-500 homes (manageable for one agent)\n- Turnover rate of 5-8%+ per year (100+ transactions if farm is 200 homes at 5%)\n- Low existing agent market share (you can penetrate)\n- Area you can authentically claim expertise in\n\nCheck MLS for last 12 months of activity in the target area before committing.\n\n**The 6-Month Domination Plan**\n- Month 1-2: Introduction mailing (market report + who you are)\n- Month 3: Value delivery (neighborhood guide, area stats)\n- Month 4: Community engagement (sponsor a local event, join neighborhood Facebook group)\n- Month 5: Market update + just sold/listed announcements\n- Month 6: Door knock with branded gift (notepad, magnet, pumpkin in fall)\n\n**Digital Farming**\nComplement physical farming:\n- Run geo-targeted Facebook/Instagram ads to your farm addresses\n- Create a neighborhood-specific Instagram account or hashtag\n- Join/start a neighborhood Facebook Group\n- Build a neighborhood page on your website with local content\n\n**Time to ROI**\nFarming takes 12-24 months before consistent returns. Most agents quit too early. Track: mailings sent, doors knocked, leads generated, deals closed. The key metric is market share growth — aim for 5% in year 1, 10% in year 2, 20% in year 3+.`,
        keyPoints: [
          'Farm 200-500 homes with 5%+ annual turnover for viable economics',
          'Check MLS agent market share before entering — low concentration is your opening',
          'Farming ROI takes 12-24 months — commit fully or skip it',
          'Combine physical (mail, door knocks) and digital (geo-targeted ads) farming',
        ],
        quiz: [
          {
            question: 'What is the ideal size of a geographic farm?',
            options: ['50–100 homes', '100–200 homes', '200–500 homes', '1,000+ homes'],
            correctIndex: 2,
            explanation: '200–500 homes is manageable for one agent while generating enough transaction volume to justify the marketing investment.',
          },
          {
            question: 'What annual turnover rate makes a farm economically viable?',
            options: ['1–2%', '3–4%', '5–8%+', '10–15%'],
            correctIndex: 2,
            explanation: 'At 5–8% turnover, a 300-home farm generates 15–24 potential transactions annually — enough to build a meaningful business.',
          },
          {
            question: 'How long does geographic farming typically take to generate consistent returns?',
            options: ['1–3 months', '6–9 months', '12–24 months', '3–5 years'],
            correctIndex: 2,
            explanation: 'Consistency over 12–24 months is what separates successful farmers from those who quit too early — the market needs to know and trust you first.',
          },
        ],
      },
      {
        title: 'Team Building',
        duration: '20 min',
        content: `Building a real estate team allows you to scale beyond what a single agent can accomplish. But teams require management, culture, and systems — not just bodies.\n\n**When to Build a Team**\nHire when you're consistently turning away business or when administrative tasks are preventing you from generating revenue. Most agents should be at $200K+ GCI before adding overhead.\n\n**First Hire: The Buyer's Agent**\nYour first hire is almost always a buyer's agent. You keep listings (highest leverage activity), they handle buyer showings and contracts. Set a minimum production expectation (e.g., 2 closings/month) with a 90-day ramp period.\n\n**Team Models**\n- **Traditional Team**: Leader on listings, buyer agents on buyers. Lead generation centralized.\n- **Rainmaker Model**: Leader generates all leads, team members convert. High control, limited autonomy.\n- **Partnership Model**: Two or more senior agents share resources, marketing, and admin.\n- **Expansion Model**: Multiple team leaders in different markets under one brand.\n\n**Compensation Structures**\n- Buyer agents: 40-60% of their commissions\n- Showing assistants: flat fee per showing or small salary\n- Transaction coordinator: flat fee per file ($400-$600) or part-time salary\n- ISA (Inside Sales Agent): base salary + lead conversion bonus\n\n**Culture and Retention**\nTop agents leave for culture and growth, not commission splits. Create weekly team meetings, set clear goals, celebrate wins, and provide mentorship. The cost of replacing a producing agent is 3-6 months of their production.`,
        keyPoints: [
          'First hire: buyer agent when you\'re turning down buyer business at $200K+ GCI',
          'You keep listings — it\'s your highest leverage activity',
          'Buyer agents: 40-60% of their commissions, 90-day ramp with minimum targets',
          'Agents leave for culture, not splits — invest in weekly meetings and mentorship',
        ],
        quiz: [
          {
            question: 'At what GCI level should most agents consider building a team?',
            options: ['$50,000+', '$100,000+', '$200,000+', '$500,000+'],
            correctIndex: 2,
            explanation: 'At $200K+ GCI you have the revenue to cover team overhead while still profiting — building earlier risks underfunding the team\'s growth.',
          },
          {
            question: 'What is typically the first hire for a growing real estate team?',
            options: ['Administrative assistant', 'Transaction coordinator', 'Buyer\'s agent', 'Marketing manager'],
            correctIndex: 2,
            explanation: 'A buyer\'s agent allows you to focus on your highest-leverage activity (listings) while team production scales.',
          },
          {
            question: 'What percentage of commissions do buyer agents on a team typically receive?',
            options: ['20–30%', '40–60%', '70–80%', '90–100%'],
            correctIndex: 1,
            explanation: '40–60% is the market standard — the team leader provides lead generation, systems, and mentorship in exchange for the commission split.',
          },
        ],
      },
      {
        title: 'Brokerage Selection',
        duration: '14 min',
        content: `Choosing a brokerage is a business decision, not an emotional one. The right brokerage provides leverage: tools, training, brand, and support that accelerate your production.\n\n**What to Evaluate**\n\n**Compensation Structure**\n- Traditional: 50-70% split to agent, decreasing as production increases (cap model)\n- Cap Model: split until you pay a set annual fee ($20-30K), then 100% for the rest of the year\n- 100% Commission: flat fee per transaction, agent keeps everything after the fee\n\n**Training & Support**\n- New agents need coaching and mentorship more than commission percentage\n- Look for structured onboarding, weekly training, and accessible managing broker\n- Mentorship programs (percentage of first deals goes to mentor) can accelerate learning\n\n**Brand Recognition**\nNational brands (KW, RE/MAX, Coldwell Banker, EXP) offer instant credibility in new markets. Boutique independent brokerages offer culture and flexibility but require more personal brand building.\n\n**Technology & Lead Generation**\nWhat technology does the brokerage provide? CRM, website, marketing tools, transaction management? Does the brokerage provide leads, or do you generate your own?\n\n**The True Cost of "Higher Splits"**\nAn agent at 70% with 20 closings = 14 deal-equivalents.\nAn agent at 60% with 28 closings (more support/training) = 16.8 deal-equivalents.\nBetter tools and training often outperform higher splits in the first 3-5 years.`,
        keyPoints: [
          'New agents: training and support matter more than commission percentage',
          'Cap model: pay a fixed annual fee, then keep 100% — best for high producers',
          'Evaluate real cost of splits — better tools often beat higher percentages',
          'Ask about lead gen: provided vs. self-generated changes the calculus entirely',
        ],
        quiz: [
          {
            question: 'In a "cap model" brokerage, what happens after the agent reaches their annual cap?',
            options: ['They earn 50% of commissions', 'They stop earning commissions until next year', 'They keep 100% of commissions for the rest of the year', 'Their split decreases to 30%'],
            correctIndex: 2,
            explanation: 'The cap model rewards high producers — once you\'ve paid your annual fee, every subsequent commission is yours entirely.',
          },
          {
            question: 'For new agents, what matters most when selecting a brokerage?',
            options: ['Highest commission split', 'Training, mentorship, and accessible support', 'The most recognizable brand', 'Technology and lead generation'],
            correctIndex: 1,
            explanation: 'A new agent who learns the business properly is worth far more in year 3 than one who had a high split in year 1 with no coaching.',
          },
          {
            question: 'An agent at 70% with 20 closings vs. 60% with 28 closings — which earns more?',
            options: ['The 70% agent (14 deal-equivalents)', 'The 60% agent (16.8 deal-equivalents)', 'They earn the same', 'Cannot be determined without knowing commission amounts'],
            correctIndex: 1,
            explanation: 'Better tools and training that generate more volume often outperform higher splits — count deal-equivalents, not split percentages.',
          },
        ],
      },
    ],
  },
  {
    id: 'investing',
    title: 'Real Estate Investing',
    description: 'Build wealth through BRRRR strategy, multifamily underwriting, and smart market selection.',
    icon: 'trending-up-outline',
    color: '#E35D5D',
    tiers: ['pro', 'elite'],
    creditHours: 8,
    lessons: [
      {
        title: 'BRRRR Strategy',
        duration: '22 min',
        content: `BRRRR — Buy, Rehab, Rent, Refinance, Repeat — is a wealth-building strategy for investors who want to maximize returns and recycle capital.\n\n**The BRRRR Cycle**\n1. **Buy**: Acquire a distressed property below market value\n2. **Rehab**: Renovate to increase value and attract quality tenants\n3. **Rent**: Stabilize with a long-term tenant at market rent\n4. **Refinance**: Cash-out refinance based on new appraised value\n5. **Repeat**: Use extracted equity to fund the next purchase\n\n**The Math of BRRRR**\nExample:\n- Purchase: $80,000\n- Rehab: $30,000\n- Total invested: $110,000\n- After-repair value (ARV): $160,000\n- Refinance at 75% LTV: $120,000\n- Cash out: $120,000 − $110,000 = $10,000 profit + property retained\n\n**Ideal BRRRR Numbers**\n- Purchase 60-70% of ARV\n- All-in cost (purchase + rehab) = 75-80% of ARV\n- Refinance at 75% LTV recovers most/all invested capital\n- Post-refi cash flow should still be positive at DSCR ≥ 1.1x\n\n**Common Mistakes**\n- Underestimating rehab costs (always add 20% contingency)\n- Over-improving for the neighborhood ($$$ upgrades in a $100K market)\n- Not stabilizing the property before refinancing (lenders want 6-12 months tenancy)\n- Refinancing too early before seasoning period\n\n**Scaling BRRRR**\nAs you perfect the system, you can run parallel projects. The key bottleneck is usually rehab management — build relationships with reliable contractors before scaling.`,
        keyPoints: [
          'All-in cost (purchase + rehab) should be 75-80% of ARV',
          'Refinance at 75% LTV should recover most or all invested capital',
          'Add 20% contingency to all rehab budgets — always',
          'Property must be stabilized (6-12 months tenancy) before cash-out refi',
        ],
        quiz: [
          {
            question: 'What does BRRRR stand for?',
            options: ['Build, Renovate, Rent, Refinance, Repeat', 'Buy, Rehab, Rent, Refinance, Repeat', 'Buy, Renovate, Resell, Refinance, Return', 'Build, Rent, Rehab, Refinance, Return'],
            correctIndex: 1,
            explanation: 'BRRRR is a wealth-building cycle that recycles the same capital across multiple properties — the goal is to pull out most or all of your invested cash.',
          },
          {
            question: 'What should the all-in cost (purchase + rehab) be relative to ARV?',
            options: ['50–60% of ARV', '75–80% of ARV', '90–95% of ARV', 'Equal to ARV'],
            correctIndex: 1,
            explanation: 'At 75–80% of ARV, a 75% LTV refinance recovers most of your invested capital — the margin is your profit and safety buffer.',
          },
          {
            question: 'How long should a property typically be stabilized before a BRRRR cash-out refinance?',
            options: ['Immediately after renovation', '30 days', '3 months', '6–12 months'],
            correctIndex: 3,
            explanation: 'Most lenders require 6–12 months of seasoned tenancy before allowing a cash-out refinance — rushing this step can disqualify the loan.',
          },
        ],
      },
      {
        title: 'Multifamily Underwriting',
        duration: '28 min',
        content: `Multifamily underwriting is the process of analyzing an apartment building's financials to determine what it's worth and what you can pay for it.\n\n**The Income Approach**\n\nStep 1: Gross Potential Income (GPI)\n= All units × Market Rent × 12 months\n(Use market rent, not current rent — you're buying potential)\n\nStep 2: Effective Gross Income (EGI)\n= GPI − Vacancy & Credit Loss (5-10% of GPI)\n+ Other Income (laundry, parking, storage)\n\nStep 3: Net Operating Income (NOI)\n= EGI − Operating Expenses\n\n**Operating Expense Categories**\n- Property management: 8-12% of EGI\n- Property taxes: varies widely by location\n- Insurance: 0.5-1% of property value annually\n- Utilities (if landlord pays): varies by unit count and leases\n- Repairs & maintenance: $800-$1,500 per unit annually\n- Capital reserves: $300-$800 per unit annually\n- Administrative (accounting, legal, misc): $500-$1,000/year flat\n\n**Typical Operating Expenses**\nAs a sanity check: operating expenses are typically 35-50% of EGI for stabilized properties. If a seller shows 20% expense ratio, they're probably not including management and reserves.\n\n**Value-Add Underwriting**\nFor value-add deals:\n1. Underwrite current (T12 actuals) — what it is today\n2. Underwrite stabilized projections — what it will be after improvements\n3. Apply appropriate cap rates to both (current and stabilized)\n4. Bridge the gap with a capital improvement budget and timeline`,
        keyPoints: [
          'Underwrite to market rents, not current rents — you\'re buying potential',
          'Operating expenses should be 35-50% of EGI for stabilized multifamily',
          'Management fee (8-12%) and reserves ($300-800/unit) must be included',
          'Model both as-is and as-stabilized NOI for value-add deals',
        ],
        quiz: [
          {
            question: 'In multifamily underwriting, should you use current rents or market rents for GPI?',
            options: ['Current rents — what the property actually earns today', 'Market rents — you\'re buying the property\'s potential', 'An average of current and market rents', 'Rents from 2 years ago for trending purposes'],
            correctIndex: 1,
            explanation: 'You\'re buying the asset\'s income potential, not its current under-market performance — underwriting to market rents shows the true opportunity.',
          },
          {
            question: 'What percentage of EGI should operating expenses represent for a stabilized multifamily?',
            options: ['10–20%', '20–30%', '35–50%', '60–70%'],
            correctIndex: 2,
            explanation: 'If a seller shows operating expenses below 35% of EGI, they\'re almost certainly excluding management fees or reserves — red flag.',
          },
          {
            question: 'If a seller shows a 15% expense ratio on a multifamily, what should you suspect?',
            options: ['Exceptional management', 'Management fees and reserves are not being included', 'No maintenance needed', 'The seller is being overly conservative'],
            correctIndex: 1,
            explanation: 'A 15% expense ratio is nearly impossible for a real property — management (8–12%) alone would exceed that. Always underwrite your own expenses.',
          },
        ],
      },
      {
        title: 'Market Selection',
        duration: '18 min',
        content: `The biggest predictor of real estate investment success is market selection. A great deal in a declining market is worse than a mediocre deal in a growing market.\n\n**Market Evaluation Framework**\n\n**Population & Job Growth**\nLook for markets with:\n- Population growth > 1% annually (US average is ~0.5%)\n- Job growth in diversified sectors (not single-employer markets)\n- Net in-migration (people moving in > moving out)\n- Young median age (millennials are peak household formation age)\n\n**Economic Diversity**\nSingle-industry markets (Detroit auto, Houston oil) are vulnerable to industry cycles. Diversified markets (tech + healthcare + government + education) weather recessions better.\n\n**Housing Supply & Affordability**\n- Zoning constraints = supply-constrained markets = stronger appreciation\n- Home price-to-income ratio: areas where renting is much cheaper than owning support rental demand\n- New permits relative to population growth\n\n**Landlord-Friendly Laws**\nEviction timelines, rent control regulations, and security deposit limits vary dramatically by state/city. Texas and Florida are landlord-friendly; California and NYC are tenant-friendly. This affects risk and operations.\n\n**Cash Flow vs. Appreciation Markets**\nRule of thumb:\n- **Cash flow markets** (Midwest, South): Lower prices, higher cap rates, less appreciation\n- **Appreciation markets** (Coastal): Higher prices, lower cap rates, stronger long-term appreciation\n\nMost successful investors hold cash flow properties for stability and appreciation properties for wealth building.`,
        keyPoints: [
          'Population growth >1% annually and job diversification are primary screens',
          'Single-industry markets have boom/bust cycles — avoid or hedge carefully',
          'Landlord-friendly laws (TX, FL) reduce operational risk vs. regulated markets',
          'Cash flow vs. appreciation: hold both for stability + wealth building',
        ],
        quiz: [
          {
            question: 'What annual population growth rate is considered strong for real estate investment?',
            options: ['Less than 0.1%', '0.1–0.5%', 'Greater than 1%', 'Greater than 5%'],
            correctIndex: 2,
            explanation: 'The US average is ~0.5% — markets growing at >1% annually have above-average demand that supports rent growth and appreciation.',
          },
          {
            question: 'Why are single-industry markets (Detroit, Houston) considered higher risk?',
            options: ['Too many properties available', 'Unfavorable landlord laws', 'Vulnerable to industry cycles — boom and bust', 'Higher insurance costs'],
            correctIndex: 2,
            explanation: 'When one industry dominates, job losses in that sector create vacancy waves across the entire market — diversified economies are far more resilient.',
          },
          {
            question: 'Midwest and South markets are generally characterized as:',
            options: ['Appreciation markets with low cap rates', 'Cash flow markets with higher cap rates and less appreciation', 'Markets with no rental demand', 'Suitable only for commercial investing'],
            correctIndex: 1,
            explanation: 'Savvy investors hold cash flow markets for stability and income while holding coastal appreciation markets for long-term wealth building.',
          },
        ],
      },
      {
        title: 'Deal Sourcing',
        duration: '20 min',
        content: `Finding deals before they hit the market is the competitive edge of successful real estate investors.\n\n**Off-Market Deal Sources**\n\n**Direct Mail**\nMail to motivated seller segments: absentee owners, high-equity homeowners, pre-foreclosures, probate estates, tax delinquents. Response rates of 0.5-2% — plan for 1,000+ mailers per deal.\n\n**Driving for Dollars**\nDrive neighborhoods looking for distressed properties: overgrown yards, boarded windows, peeling paint, accumulated mail, tarps on roofs. Skip trace the owner and make contact.\n\n**Wholesaler Networks**\nBuild relationships with wholesalers — they find deals, assign contracts, and take a fee. Join local real estate investment associations (REIAs) to meet active wholesalers.\n\n**MLS Monitoring**\nStale listings (60+ days on market), price-reduced properties, and relisted homes often indicate motivated sellers. Make low-ball offers with quick-close and cash terms.\n\n**Agent Relationships**\nAgents who know you buy ugly houses will call you first when the listing comes in. Build a reputation as a reliable, fast buyer who doesn't nickel-and-dime.\n\n**Deal Analysis Speed**\nThe faster you can analyze a deal, the more deals you can review. Build your underwriting model into a spreadsheet and be able to evaluate any deal in 10 minutes. Serious offers should be submitted within 24 hours of finding a deal — motivated sellers won't wait.`,
        keyPoints: [
          'Direct mail: target absentee owners, high-equity, pre-foreclosures, probate',
          'Wholesaler relationships: build your buyers list at REIAs',
          'MLS: 60+ day stale listings often signal motivated sellers',
          'Speed wins deals — analyze in 10 minutes, offer within 24 hours',
        ],
        quiz: [
          {
            question: 'What is "driving for dollars"?',
            options: ['Driving for Uber to fund investments', 'Driving neighborhoods to identify distressed properties by their outward appearance', 'A direct mail marketing method', 'Using a vehicle to transport cash to closings'],
            correctIndex: 1,
            explanation: 'Visible distress (overgrown yards, tarps, boarded windows) signals a potentially motivated seller — skip trace the owner and make contact.',
          },
          {
            question: 'What is the typical response rate for direct mail targeting motivated sellers?',
            options: ['10–20%', '5–10%', '0.5–2%', 'Less than 0.1%'],
            correctIndex: 2,
            explanation: 'Plan for 1,000+ mailers per deal at 0.5–2% response — the economics work because you\'re buying at a steep discount.',
          },
          {
            question: 'For MLS deal sourcing, which listings often indicate a motivated seller?',
            options: ['New listings at full asking price', 'Open house listings', '60+ day stale listings or price-reduced properties', 'Luxury properties above $1M'],
            correctIndex: 2,
            explanation: 'Days on market and price reductions signal motivation — the longer a property sits, the more willing the seller becomes.',
          },
        ],
      },
      {
        title: 'Property Management',
        duration: '16 min',
        content: `Property management is the operational side of real estate investing. Done well, it preserves asset value and maintains cash flow. Done poorly, it destroys both.\n\n**Self-Manage vs. Hire a PM**\n\nSelf-manage if:\n- 1-5 properties within 30 minutes of you\n- You have time and enjoy operations\n- Properties are in good condition\n\nHire a PM if:\n- 5+ properties or out-of-state\n- You value your time at >$75/hour\n- Properties require intensive management\n\nTypical PM fees: 8-12% of collected rent + 50-100% of first month's rent for leasing fee.\n\n**Tenant Screening — The Most Important Step**\nScreening standards:\n- Credit score: 620+ minimum\n- Income: 3× monthly rent in gross income\n- Employment: 1+ year at current job\n- Rental history: no evictions in last 5 years\n- Background: felony-free (with judgment)\n\nApply criteria consistently to all applicants — Fair Housing Act prohibits discrimination based on protected classes.\n\n**Lease Enforcement**\nBe firm and consistent. Late fees should be charged every time or never. Once you make exceptions, tenants learn they can negotiate. Issue pay or quit notices on day 2 of late rent — it sets the tone.\n\n**Preventive Maintenance**\nAnnual inspections catch problems early. HVAC filter replacements, gutter cleaning, and weatherstripping are cheap. A $50 repair ignored becomes a $500 problem, then a $5,000 emergency.`,
        keyPoints: [
          'Hire PM for 5+ properties or out-of-state — your time has value',
          'Tenant screening: 620+ credit, 3× income, no evictions',
          'Apply screening criteria consistently — Fair Housing compliance',
          'Preventive maintenance saves 10x the cost of deferred repairs',
        ],
        quiz: [
          {
            question: 'When should you strongly consider hiring a professional property manager?',
            options: ['1–2 properties within 10 miles', '3–4 properties within 20 miles', '5+ properties or out-of-state', '10+ properties or outside the country'],
            correctIndex: 2,
            explanation: 'At 5+ properties, self-management becomes a full-time job — a PM at 8–12% of rents frees you to find and close more deals.',
          },
          {
            question: 'What is the standard income-to-rent ratio for tenant screening?',
            options: ['2× monthly rent', '3× monthly rent', '5× monthly rent', '10× monthly rent'],
            correctIndex: 1,
            explanation: '3× gross monthly income provides enough cushion to ensure the tenant can pay rent and still meet other living expenses.',
          },
          {
            question: 'Fair Housing Act compliance requires:',
            options: ['Accepting all applicants regardless of income', 'Applying screening criteria consistently to all applicants', 'Prioritizing veterans and elderly applicants', 'Removing all screening criteria'],
            correctIndex: 1,
            explanation: 'You can have strict screening standards — you just must apply them uniformly regardless of protected class characteristics.',
          },
        ],
      },
      {
        title: 'Exit Strategies',
        duration: '18 min',
        content: `Every investment needs an exit strategy before you buy. Your exit determines your hold period, financing structure, and tax planning.\n\n**Common Exit Strategies**\n\n**Sell Retail**\nList with an agent on the MLS at full market value. Best for stabilized properties in strong markets. Plan for 90-120 days from decision to close.\n\n**Sell to Another Investor**\nOff-market sale to another investor — faster, fewer contingencies, usually slightly below retail. Good for tired landlords or properties that need work.\n\n**1031 Exchange**\nDefer capital gains by rolling proceeds into a like-kind property. Best for investors with significant appreciation. Requires 45-day ID and 180-day close.\n\n**Cash-Out Refinance**\nExtract equity tax-free (not a taxable event) while retaining the asset. Best when rates are favorable and the property has substantial appreciation.\n\n**Owner Finance**\nSell on installment basis — collect monthly payments instead of a lump sum. Spreads capital gains over time and generates ongoing cash flow. Requires working with a real estate attorney.\n\n**Hold and Build Equity**\nLong-term hold — let rent pay down the mortgage and appreciation do the work. The Millionaire Real Estate Investor's foundational strategy.\n\n**Tax Planning by Exit**\n- Assets held <1 year: short-term capital gains (ordinary income rates)\n- Assets held >1 year: long-term capital gains (0%, 15%, 20% depending on income)\n- Depreciation recapture: 25% rate on accumulated depreciation\n- 1031 defers all of the above until final sale`,
        keyPoints: [
          'Plan your exit before you buy — hold period determines financing and tax strategy',
          'Cash-out refi extracts equity tax-free while retaining the asset',
          '1031: defer all gains by reinvesting in like-kind property within 180 days',
          'Long-term hold >1 year gets preferred capital gains rates',
        ],
        quiz: [
          {
            question: 'Which exit strategy defers capital gains taxes by rolling proceeds into a like-kind property?',
            options: ['Owner financing', 'Cash-out refinance', '1031 exchange', 'Retail sale on MLS'],
            correctIndex: 2,
            explanation: '1031 exchanges defer ALL taxes — gains, depreciation recapture, and state taxes — by reinvesting into qualifying replacement properties.',
          },
          {
            question: 'Assets held less than 1 year are taxed at:',
            options: ['0–20% long-term capital gains rate', 'Short-term capital gains rate (ordinary income rates)', '25% depreciation recapture rate', 'No tax if reinvested within 6 months'],
            correctIndex: 1,
            explanation: 'Short-term gains are taxed as ordinary income — which can be 37% for high earners. Holding past 12 months to qualify for LTCG rates is almost always worth it.',
          },
          {
            question: 'A cash-out refinance is advantageous because:',
            options: ['It sells the property for maximum value', 'It extracts equity tax-free while retaining ownership', 'It eliminates capital gains taxes permanently', 'It is faster than a 1031 exchange'],
            correctIndex: 1,
            explanation: 'Borrowed money is not taxable income — a cash-out refi lets you access equity for reinvestment without triggering a taxable event.',
          },
        ],
      },
    ],
  },
  {
    id: 'deal_structuring',
    title: 'Advanced Deal Structuring',
    description: 'Master creative financing, joint ventures, syndication, and off-market deal strategies.',
    icon: 'git-network-outline',
    color: '#E6A23C',
    tiers: ['elite'],
    creditHours: 10,
    lessons: [
      {
        title: 'Creative Financing Overview',
        duration: '20 min',
        content: `Creative financing refers to any transaction structure that differs from a standard purchase with bank financing. It's used when conventional financing is unavailable, insufficient, or when the deal structure creates a better outcome for all parties.\n\n**Why Creative Financing?**\n- Access deals that wouldn't qualify for conventional financing\n- Reduce down payment requirements\n- Create transactions where seller gets better tax treatment\n- Access distressed assets where banks won't lend\n- Move faster than the conventional lending timeline\n\n**Common Creative Financing Structures**\n\n**Subject-To**\nBuy a property "subject to" the existing mortgage — the seller's loan stays in place, title transfers to you, you make the payments. The seller's name stays on the mortgage but not the deed.\n\nRisk: Due-on-sale clause. If lender discovers transfer, they can accelerate the loan (demand full payoff). In practice, lenders rarely exercise this if payments are current.\n\n**Lease Option**\nLease the property with an option to purchase at a set price within a set timeframe. Option fee is non-refundable but typically credited toward purchase price.\n\nUsed by buyers who aren't ready to qualify for conventional financing or who want to test the market.\n\n**Contract for Deed / Land Contract**\nSeller finances the purchase — buyer makes payments directly to seller and receives title at payoff or after meeting conditions. Common in rural markets and for buyers who can't qualify for conventional loans.\n\n**Blended Structures**\nMany deals use combinations: conventional bank first + seller second, or hard money + seller carryback. The key is understanding how each layer of capital works together.`,
        keyPoints: [
          'Subject-to: existing mortgage stays in place, you make payments, title transfers',
          'Due-on-sale clause risk: mitigated by keeping loans current',
          'Lease option: control the asset, lock in price, test the deal',
          'Most sophisticated deals layer multiple financing sources',
        ],
        quiz: [
          {
            question: 'In a "Subject-To" purchase, what happens to the existing mortgage?',
            options: ['It is paid off at closing', 'It is assumed by the buyer with bank approval', 'The loan stays in place; title transfers but the seller\'s name remains on the mortgage', 'It is converted to lease payments'],
            correctIndex: 2,
            explanation: 'Subject-to is a creative way to acquire property with existing financing — no bank approval needed, but the seller remains liable on the mortgage.',
          },
          {
            question: 'The primary risk of a Subject-To purchase is:',
            options: ['The seller could change the locks', 'The lender could invoke the due-on-sale clause and demand full payoff', 'Title cannot be transferred', 'The interest rate increases automatically'],
            correctIndex: 1,
            explanation: 'The due-on-sale clause technically gives lenders the right to demand full payoff on sale — in practice, lenders rarely exercise this if payments remain current.',
          },
          {
            question: 'A lease option gives the buyer:',
            options: ['Ownership immediately upon signing', 'A long-term land lease with an option to build', 'Control of the asset with a right to purchase at a set price within a set timeframe', 'A government-backed purchase option'],
            correctIndex: 2,
            explanation: 'Lease options let investors control and test an asset before committing to full purchase — the option fee is the price of that flexibility.',
          },
        ],
      },
      {
        title: 'Seller Financing & Wraps',
        duration: '22 min',
        content: `Seller financing is one of the most powerful tools in real estate. When a seller doesn't need all their proceeds immediately, they become the bank.\n\n**Seller Financing Basics**\nInstead of cashing out at closing, the seller accepts a promissory note and deed of trust (or mortgage) from the buyer. The buyer makes monthly payments directly to the seller.\n\nBenefits for sellers:\n- Spread capital gains over time (installment sale reporting)\n- Generate ongoing income stream\n- Often achieve higher price than cash sale\n- Avoid tax in the year of sale on proceeds received in future years\n\nBenefits for buyers:\n- Potentially lower down payment\n- Faster closing (no bank underwriting)\n- More flexible terms\n- Access to properties conventional lenders won't finance\n\n**Wrap-Around Mortgages**\nA wrap is a seller finance structure where the existing mortgage is embedded within the new larger note:\n\nExample:\n- Existing mortgage: $150,000 at 4%\n- Wrap note: $250,000 at 7%\n- Seller's spread: receives 7% on $250K, pays 4% on $150K\n- Buyer's effective leverage: borrowed at 7% with only $100K new capital at risk for seller\n\n**Documentation Requirements**\nSeller financing must be properly documented:\n- Promissory note with full terms\n- Deed of trust or mortgage as security\n- Loan servicing company (not DIY) for payment collection and records\n- Title insurance\n- Dodd-Frank compliance (SAFE Act if seller does >3 seller-financed deals/year)`,
        keyPoints: [
          'Seller finance: installment sale spreads capital gains over time',
          'Wrap-around mortgage: seller keeps existing mortgage, creates new larger note',
          'Always use a professional loan servicer — don\'t collect payments directly',
          'Dodd-Frank limits seller financing to 3 deals/year without MLO licensing',
        ],
        quiz: [
          {
            question: 'What is the primary tax benefit of seller financing for the seller?',
            options: ['Eliminates all capital gains taxes', 'Spreads capital gains over time via installment sale reporting', 'Creates a tax deduction for the seller', 'Avoids depreciation recapture entirely'],
            correctIndex: 1,
            explanation: 'Installment sales report gain only as principal is received — a powerful tax deferral strategy for sellers with significant appreciation.',
          },
          {
            question: 'In a wrap-around mortgage, the seller:',
            options: ['Pays off the existing mortgage first', 'Receives interest at a higher rate and continues paying the original mortgage at its lower rate', 'Transfers the mortgage to the buyer directly', 'Requires the buyer to refinance immediately'],
            correctIndex: 1,
            explanation: 'The spread between the wrap rate and the underlying mortgage rate is the seller\'s profit — they arbitrage their own cheap financing.',
          },
          {
            question: 'Dodd-Frank limits seller financing without MLO licensing to:',
            options: ['1 transaction per year', '3 transactions per year', '5 transactions per year', '10 transactions per year'],
            correctIndex: 1,
            explanation: 'Sellers who do more than 3 seller-financed deals per year are considered mortgage originators under Dodd-Frank and must be licensed.',
          },
        ],
      },
      {
        title: 'Joint Ventures',
        duration: '18 min',
        content: `A joint venture (JV) allows investors to pool resources — money, expertise, relationships, or time — to complete deals that neither could accomplish alone.\n\n**Common JV Structures**\n\n**Money Partner + Operator**\nMost common structure:\n- Money partner: provides capital, passive role\n- Operator: finds deals, manages rehab/operations, active role\n- Typical split: 50/50 or 60/40 (operator gets more) after capital return\n\n**Preferred Return + Split**\nMoney partner receives a preferred return first (8-10% on invested capital annually), then remaining profits split with operator.\n\nExample:\n- Investment: $200,000\n- Preferred return (8%): $16,000/year\n- Year 1 profits: $30,000\n- Preferred return paid: $16,000\n- Remaining profit ($14,000) split 50/50: $7,000 each\n\n**Documentation — Never Skip This**\nEvery JV needs a proper Operating Agreement:\n- Ownership percentages\n- Decision-making authority\n- Capital contribution requirements\n- Waterfall (order of distributions)\n- Exit provisions (what if one partner wants out?)\n- Deadlock resolution\n\n**JV Partner Vetting**\nMoney is easy to lose with the wrong partner. Before entering a JV:\n- Check references (talk to people they've done deals with)\n- Review their financial statements\n- Start small before scaling\n- Make sure exit provisions are favorable in case of disagreement`,
        keyPoints: [
          'JV: money partner + operator split profits after capital return',
          'Preferred return (8-10%) is paid first, then remaining profits split',
          'Operating Agreement is mandatory — never proceed without one',
          'Vet partners through references and start small before scaling',
        ],
        quiz: [
          {
            question: 'What does a "preferred return" mean in a joint venture?',
            options: ['The money partner gets to choose the property', 'The money partner receives a set return first before profits are split with the operator', 'The operator earns a higher percentage than normal', 'Profits are paid monthly regardless of performance'],
            correctIndex: 1,
            explanation: 'A preferred return (8–10%) protects the passive capital partner by ensuring they\'re made whole before profits are shared.',
          },
          {
            question: 'Why is an Operating Agreement critical in a JV?',
            options: ['Required by banks for financing', 'It defines ownership, decision-making, capital requirements, waterfall, and exit provisions', 'It replaces the need for title insurance', 'It enforces verbal agreements'],
            correctIndex: 1,
            explanation: 'Partnerships fail when expectations aren\'t written down — the Operating Agreement prevents disputes before they start.',
          },
          {
            question: 'How should you vet a JV partner before investing?',
            options: ['Ask about their experience only', 'Check references, review financial capacity, start small before scaling', 'Require their credit score only', 'JV partners cannot be effectively vetted in advance'],
            correctIndex: 1,
            explanation: 'The cost of a bad partner is not just financial — disputes can tie up assets in litigation for years. References and a small test deal are essential.',
          },
        ],
      },
      {
        title: 'Real Estate Syndication',
        duration: '26 min',
        content: `Syndication is the process of pooling capital from multiple investors to acquire a larger asset than any one investor could fund alone. It's how institutional-scale deals are done in the private market.\n\n**Syndication Structure**\n- **Sponsor (GP)**: Finds deal, raises capital, manages the asset\n- **Limited Partners (LPs)**: Passive investors who provide capital\n- **Entity**: Typically an LLC or LP through which the deal is held\n\n**The Capital Stack**\n- Senior debt (bank): First position, lowest risk, lowest return (5-8%)\n- Mezzanine debt: Second position, higher risk, higher return (10-14%)\n- Preferred equity: Gets paid before common equity (8-12% preferred)\n- Common equity (GP + LP): Highest risk, highest upside\n\n**SEC Regulation**\nSyndications involve offering securities and are regulated by the SEC:\n- **Reg D 506(b)**: Up to 35 non-accredited investors, no advertising, 506 relationships\n- **Reg D 506(c)**: Accredited investors only, public advertising allowed\n- **Reg A+**: Lower capital raise with more disclosure, can include non-accredited\n\n**Typical Syndication Economics**\n- Sponsor fee: 1-2% of purchase price\n- Asset management fee: 1-2% of gross revenues annually\n- Acquisition fee at close\n- Promote: 20-30% of profits above preferred return\n\n**The Waterfall**\nOrder of distributions:\n1. Return of LP capital\n2. Preferred return to LPs (6-8%)\n3. Catch-up to GP (if applicable)\n4. Remaining profits split 70/30 or 80/20 (LP/GP)`,
        keyPoints: [
          'GP manages, LP invests passively — GP earns fees + promote',
          'SEC Reg D 506(c) allows advertising but only to accredited investors',
          'Waterfall: LP capital return → preferred return → remaining split',
          'Sponsor earns 1-2% acquisition fee + ongoing asset management fee',
        ],
        quiz: [
          {
            question: 'In a syndication, who is the General Partner (GP)?',
            options: ['The passive investor who provides capital', 'A government licensing body', 'The sponsor who finds deals, raises capital, and manages the asset', 'The senior lender'],
            correctIndex: 2,
            explanation: 'The GP drives the deal — they earn acquisition fees, asset management fees, and a promote (share of profits) for their active role.',
          },
          {
            question: 'SEC Regulation D 506(c) allows:',
            options: ['Non-accredited investors to participate with full disclosure', 'Public advertising of the offering but only accredited investors may invest', 'Unlimited investors without SEC registration', 'Syndications under $5M without any SEC filings'],
            correctIndex: 1,
            explanation: '506(c) is the modern fundraising tool — social media and advertising are permitted, but investor verification is required for all participants.',
          },
          {
            question: 'What is the "waterfall" in a real estate syndication?',
            options: ['The construction schedule', 'The order in which profits are distributed: LP capital return → preferred return → remaining split', 'The minimum investment threshold', 'The process of reporting to the SEC'],
            correctIndex: 1,
            explanation: 'The waterfall determines who gets paid in what order — LPs are protected first, then the GP earns their promote on remaining upside.',
          },
        ],
      },
      {
        title: 'Distressed Asset Acquisition',
        duration: '20 min',
        content: `Distressed assets — foreclosures, REOs, short sales, and bankruptcy estates — offer significant discount opportunities, but with higher complexity and risk.\n\n**Types of Distressed Assets**\n\n**Pre-Foreclosure**\nThe owner is behind on payments but hasn't lost the property yet. Approach directly with a solution: cash purchase, subject-to acquisition, or short sale facilitation.\n\n**Short Sales**\nSeller owes more than the property is worth. Requires lender approval to accept less than full payoff. Process:\n1. Buyer makes offer subject to lender approval\n2. Seller's agent submits short sale package (hardship letter, financials, HUD-1 estimate)\n3. Lender BPO (Broker Price Opinion) determines acceptable price\n4. Lender approval typically takes 30-120 days\n\n**REO (Real Estate Owned)**\nProperties the bank has already foreclosed on. Listed through asset management companies. Banks want to sell quickly — be a clean, fast offer. Sold "as-is"; no seller disclosures.\n\n**Tax Deed Sales**\nCounties sell properties to recoup unpaid taxes. Buyers purchase the tax deed, which may not convey clear title — title insurance is often unavailable. Research liens, litigation, and property access before bidding.\n\n**Due Diligence for Distressed**\nDistressed properties require deeper diligence:\n- Title search for all liens (mortgage, mechanic's lien, judgment, tax)\n- Environmental assessment\n- Physical inspection (often limited or denied pre-purchase)\n- Estimated rehab budget with 30% contingency\n- Holding cost calculation during renovation and sale period`,
        keyPoints: [
          'Pre-foreclosure: approach owner directly with cash or subject-to solution',
          'Short sales: 30-120 day lender approval timeline — patience required',
          'REO: sold as-is, no disclosures — factor unknown defects into price',
          'Tax deed: research all liens first — title insurance may be unavailable',
        ],
        quiz: [
          {
            question: 'In a short sale, what determines the acceptable sale price?',
            options: ['The buyer\'s offer alone', 'The seller\'s remaining mortgage balance', 'A Broker Price Opinion (BPO) commissioned by the lender', 'The county tax assessment'],
            correctIndex: 2,
            explanation: 'The lender orders a BPO to establish minimum acceptable proceeds — the BPO value is the floor, and negotiating below it requires a hardship justification.',
          },
          {
            question: 'REO (bank-owned) properties are sold:',
            options: ['With full seller disclosures and warranties', 'As-is, with no seller disclosures, by the foreclosing bank', 'Through normal MLS with buyer contingencies', 'Only to investors with cash'],
            correctIndex: 1,
            explanation: 'Banks have never occupied the property and disclaim all knowledge — as-is pricing must reflect unknown defects.',
          },
          {
            question: 'Tax deed sales present what key risk?',
            options: ['Properties cannot be renovated', 'Zoning restrictions apply', 'Title may not be clear and title insurance is often unavailable', 'Properties must be owner-occupied'],
            correctIndex: 2,
            explanation: 'A tax deed conveys the right to the property but not necessarily clear title — other liens may remain and title insurance companies often won\'t insure them.',
          },
        ],
      },
      {
        title: 'Off-Market Strategies',
        duration: '22 min',
        content: `Off-market deals are the holy grail for serious investors — no competition, motivated sellers, and the ability to move at your own pace.\n\n**Why Sellers Go Off-Market**\n- Privacy (divorce, financial distress, estate situations)\n- Speed (need to close in days, not months)\n- Condition (property won't pass conventional appraisal)\n- Simplicity (don't want showings, open houses, and negotiations)\n\n**Building Your Off-Market Pipeline**\n\n**Attorney Network**\nEstate attorneys, probate attorneys, and divorce attorneys regularly handle real estate as part of their practice. A referral fee arrangement (buyer pays at closing) creates a steady stream of opportunities.\n\n**Wholesaler Relationships**\nWholesalers are professional deal finders. They tie up properties at a discount and assign the contract to end buyers for a fee ($5,000-$30,000+). Having deep wholesaler relationships means getting first call on deals.\n\n**Cold Outreach — Targeted**\nDirect mail, text, and cold calls to:\n- Absentee owners (owner doesn't live at the property)\n- High-equity owners (low or no mortgage balance)\n- Probate filings (public record)\n- Expired listings (motivated sellers who couldn't sell retail)\n\n**Social Proof and Reputation**\nSuccessful investors become known as reliable, fast buyers. Word travels in real estate circles. Every clean, professional close generates future deal flow. Reputation is your most valuable off-market lead source.\n\n**Direct-to-Seller Offers**\nKnocking on doors or calling property owners directly:\n- "I'm a local investor. I buy properties as-is for cash. Is this something you'd ever consider?"\n- Low batting average (1 in 50+) but no competition\n- Best for driving-for-dollars targets and distressed properties`,
        keyPoints: [
          'Build attorney (estate/probate/divorce) referral network for consistent flow',
          'Wholesalers: be the first call by being reliable and fast',
          'Target absentee owners, high-equity, and probate filings for direct mail',
          'Reputation = deal flow: every clean close generates future opportunities',
        ],
        quiz: [
          {
            question: 'Which attorney network is most valuable for consistent off-market deal flow?',
            options: ['Real estate transaction attorneys', 'Estate/probate and divorce attorneys who regularly handle real estate', 'Eviction attorneys', 'Patent attorneys'],
            correctIndex: 1,
            explanation: 'Estate and divorce attorneys handle distressed real estate situations regularly and can refer deals to reliable investors — build these relationships proactively.',
          },
          {
            question: 'For direct mail targeting, which list typically yields the most motivated sellers?',
            options: ['All homeowners in a zip code', 'Recent home buyers', 'Absentee owners, high-equity holders, probate filings, and expired listings', 'Homeowners who\'ve lived in the home less than 2 years'],
            correctIndex: 2,
            explanation: 'These groups have a motivated reason to sell — absentees want passive income, high-equity owners can sell at a discount and still profit, probates need to liquidate.',
          },
          {
            question: 'What is the primary long-term source of off-market deal flow?',
            options: ['Direct mail campaigns', 'Door knocking', 'Reputation — every clean, professional close generates future deal flow', 'Social media advertising'],
            correctIndex: 2,
            explanation: 'In real estate networks, word travels fast — being known as reliable, fast, and fair is the most durable and cost-effective deal source.',
          },
        ],
      },
    ],
  },
];

// Avenue IDs map directly to module IDs
export const ALL_AVENUE_IDS = MODULES.map(m => m.id);

// Legacy tier fallback (used for platform roles like loan_officer, investor, etc.)
export const LEGACY_TIER_ACCESS: Record<string, string[]> = {
  starter: ['residential', 'mortgage'],
  pro: ['residential', 'commercial', 'mortgage', 'realtor_growth', 'investing'],
  elite: ['residential', 'commercial', 'mortgage', 'realtor_growth', 'investing', 'deal_structuring'],
  lending: ['residential', 'mortgage'],
};

export const AVENUE_PRICES: Record<string, number> = {
  residential: 49,
  commercial: 49,
  mortgage: 49,
  realtor_growth: 49,
  investing: 49,
  deal_structuring: 79,
};

export const ALL_ACCESS_PRICE = 149;

/**
 * Determine if a user can access a module based on the new avenue model.
 * - chosen_avenue: the one free avenue selected at onboarding
 * - unlocked_avenues: additional avenues unlocked via payment
 * - legacy_tier: fallback for platform users who predate the avenue model
 */
export function canAccessModule(
  chosenAvenue: string | null,
  unlockedAvenues: string[],
  moduleId: string,
  legacyTier?: string | null,
): boolean {
  if (chosenAvenue === moduleId) return true;
  if (unlockedAvenues.includes(moduleId)) return true;
  // Legacy tier support for platform-role users
  if (legacyTier) {
    const legacyAllowed = LEGACY_TIER_ACCESS[legacyTier] || [];
    if (legacyAllowed.includes(moduleId)) return true;
  }
  return false;
}
