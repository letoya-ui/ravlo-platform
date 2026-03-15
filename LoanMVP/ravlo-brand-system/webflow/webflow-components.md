# Ravlo Webflow Component Library
Cinematic, modular components for ravlohq.com using the Ravlo Webflow class system.

---

# 1. Hero Component

**Purpose:** Primary page intro with headline, subheadline, and CTAs.

**Structure:**
- div.hero  
  - div.container  
    - div.hero-content  
      - h1.hero-heading  
      - p.hero-subheading  
      - div.hero-buttons  
        - a.button.button--primary  
        - a.button.button--secondary  

**Classes:**
- hero  
- hero-content  
- hero-heading  
- hero-subheading  
- hero-buttons  
- button, button--primary, button--secondary  

---

# 2. Section Component

**Purpose:** Reusable layout wrapper for all page sections.

**Structure:**
- section.section.section--dark (or --light / --blueprint / --hero)  
  - div.container  
    - div.section-header  
      - h2.heading-lg  
      - p.body-md  
    - div.section-body  

**Classes:**
- section, section--dark, section--light, section--blueprint, section--hero  
- container, container--wide, container--narrow  
- heading-lg, body-md  

---

# 3. Card Component

**Purpose:** Generic content card for features, metrics, or modules.

**Structure:**
- div.card.card--feature (or --metric / --module)  
  - div.card-icon (optional)  
  - h3.heading-md  
  - p.body-md  

**Classes:**
- card, card--feature, card--metric, card--module  
- heading-md  
- body-md  

---

# 4. Panel Component (Visual OS)

**Purpose:** Cinematic OS-style floating panels.

**Structure:**
- div.panel.panel--floating (or --glass / --blueprint)  
  - div.panel-header  
    - p.label  
  - div.panel-body  
    - content  

**Classes:**
- panel, panel--floating, panel--glass, panel--blueprint  
- label  
- body-md  

---
# 5. Pricing Card Component

**Purpose:** Display pricing tiers with features.

**Structure:**
- div.pricing-card.card  
  - p.label (tier name)  
  - h3.heading-md  
  - ul.pricing-feature-list  
    - li.pricing-feature.body-md  

**Classes:**
- pricing-card  
- pricing-tier  
- pricing-feature-list  
- pricing-feature  
- label  
- heading-md  
- body-md  

---

# 6. Module Feature Component

**Purpose:** Highlight individual module features.

**Structure:**
- div.module-feature.card--feature  
  - div.module-feature-icon  
  - div.module-feature-text  
    - h4.heading-sm  
    - p.body-sm  

**Classes:**
- module-feature  
- module-feature-icon  
- module-feature-text  
- heading-sm  
- body-sm  

---

# 7. Ecosystem Diagram Component

**Purpose:** Visualize the Ravlo Universe rings.

**Structure:**
- div.ecosystem-diagram  
  - div.ecosystem-ring.ecosystem-ring--core  
  - div.ecosystem-ring.ecosystem-ring--modules  
  - div.ecosystem-ring.ecosystem-ring--extensions  

**Classes:**
- ecosystem-diagram  
- ecosystem-ring, ecosystem-ring--core, ecosystem-ring--modules, ecosystem-ring--extensions  
- blueprint-ring  
- blueprint-grid  

---

# 8. Partner Card Component

**Purpose:** Display partner roles or individual partners.

**Structure:**
- div.partner-card.card  
  - p.label  
  - h3.heading-md  
  - p.body-sm  

**Classes:**
- partner-card  
- card  
- label  
- heading-md  
- body-sm  

---

# 9. Contact Block Component

**Purpose:** Show contact methods (Support, Sales, Partnerships, Press).

**Structure:**
- div.contact-card.card  
  - h3.heading-sm  
  - p.body-sm  

**Classes:**
- contact-card  
- contact-method  
- heading-sm  
- body-sm  

---

# 10. Usage Guidelines

1. Use **section + container** as the base layout.  
2. Keep **hero** unique per page.  
3. Combine base + modifier classes (card card--feature).  
4. Use typography classes (heading-*, ody-*).  
5. Treat this library as the **source of truth** for new components.

---
