# Ravlo Accessibility Guidelines
Ensuring the Ravlo OS is inclusive, readable, and usable for all investors, borrowers, and partners.

---

# 1. Accessibility Philosophy

Ravlo accessibility is:
- Invisible but intentional  
- Calm and supportive  
- Designed to reduce cognitive load  
- Built for clarity and confidence  
- Integrated into every component and interaction  

Accessibility is not an add-on — it is part of the OS.

---

# 2. Color & Contrast

### Minimum Contrast Ratios
- Body text: **4.5:1**  
- Large text (18px+): **3:1**  
- Icons: **3:1**  
- UI elements (borders, inputs): **3:1**  

### Ravlo Color Rules
- Soft White (#F2F5F8) must maintain contrast against midnight surfaces  
- Blueprint Cyan should be used sparingly and never as body text  
- Accent colors must not be used for long-form reading  

---

# 3. Typography Accessibility

### Minimum Font Sizes
- Body text: **16px**  
- Labels: **12px**  
- Buttons: **14px**  

### Line Height
- Body text: **150%**  
- Headings: **110–130%**  

### Readability Rules
- Avoid long line lengths (max 70–80 characters)  
- Maintain consistent hierarchy  
- Never rely on color alone to convey meaning  

---

# 4. Interaction Accessibility

### Focus States
- Must always be visible  
- Use blueprint cyan outline + soft glow  
- Must not be removed or hidden  

### Hover States
- Cannot be the only indicator  
- Must be paired with focus or active states  

### Active States
- Provide clear mechanical feedback  

### Disabled States
- Must remain readable  
- Must not trigger hover or active states  

---

# 5. Motion Accessibility

### Motion Rules
- All motion must be subtle  
- Avoid parallax or aggressive movement  
- No bouncing or elastic easing  
- Provide reduced-motion alternatives when possible  

### Reduced Motion Mode
- Disable blueprint drift  
- Disable glow pulse  
- Reduce slide-up distance  
- Keep fade-ins minimal  

---

# 6. Component Accessibility

## Buttons
- Must have visible focus  
- Must include text (no icon-only primary actions)  
- Must have accessible labels  

## Inputs
- Must include labels  
- Must include helper text when needed  
- Must show clear error states  

## Cards
- Must not rely solely on hover for interaction  
- Must maintain readable contrast  

## Panels
- Must maintain clear hierarchy  
- Must support keyboard navigation  

---

# 7. Keyboard Navigation

### Requirements
- All interactive elements must be reachable via Tab  
- Focus order must follow visual order  
- Escape must close modals and overlays  
- Enter/Space must activate buttons  

### Skip Links
- Provide a skip-to-content link for long pages  

---

# 8. Screen Reader Support

### Required ARIA Attributes
- aria-label  
- aria-expanded  
- aria-controls  
- aria-current  
- aria-live (for dynamic content)  

### Announce
- Navigation changes  
- Modal openings  
- Form errors  
- Success confirmations  

---

# 9. Content Accessibility

### Writing Rules
- Use clear, concise language  
- Avoid jargon unless defined  
- Use descriptive link text  
- Provide alt text for all images  

### Alt Text Guidelines
- Describe purpose, not appearance  
- Keep it short and meaningful  

---

# 10. Accessibility Principles

1. Clarity over complexity  
2. Inclusion over aesthetics  
3. Predictability builds trust  
4. Motion must support, not distract  
5. Accessibility is part of the OS  

---
