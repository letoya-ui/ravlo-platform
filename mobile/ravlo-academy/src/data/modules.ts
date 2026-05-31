export interface Lesson {
  title: string;
  duration: string;
  content: string;
  keyPoints: string[];
}

export interface Module {
  id: string;
  title: string;
  description: string;
  icon: string;
  color: string;
  lessons: Lesson[];
  tiers: string[];
}

export const MODULES: Module[] = [
  {
    id: 'residential',
    title: 'Residential Mastery',
    description: 'Master the fundamentals of residential real estate sales, buyer representation, and client conversion.',
    icon: 'home-outline',
    color: '#3BAF7A',
    tiers: ['starter', 'pro', 'elite', 'lending'],
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
      },
    ],
  },
];

export const MODULE_TIER_ACCESS: Record<string, string[]> = {
  starter: ['residential', 'mortgage'],
  pro: ['residential', 'commercial', 'mortgage', 'realtor_growth', 'investing'],
  elite: ['residential', 'commercial', 'mortgage', 'realtor_growth', 'investing', 'deal_structuring'],
  lending: ['residential', 'mortgage'],
};

export function canAccessModule(tier: string | null, moduleId: string): boolean {
  if (!tier) return false;
  const allowed = MODULE_TIER_ACCESS[tier] || [];
  return allowed.includes(moduleId);
}
