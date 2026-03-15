# Ravlo Interaction States Spec
The micro-interaction layer of the Ravlo OS — hover, active, focus, and disabled states across all components.

---

# 1. Interaction Philosophy

Ravlo interactions are:
- Calm, not flashy  
- Cinematic, not playful  
- Intentional, not decorative  
- Investor-grade, not consumer-grade  

Every interaction should reinforce clarity and confidence.

---

# 2. Core Interaction States

## 2.1 Hover State

### Behavior
- Soft scale: 1.00 ? 1.02  
- Glow: subtle blueprint cyan (2–4px)  
- Shadow: deepen by 10–20%  

### Applies To
- Buttons  
- Cards  
- Panels  
- Icons  
- Navigation items  

### Notes
Hover should feel like a gentle lift — never bouncy.

---

## 2.2 Active (Pressed) State

### Behavior
- Scale: 1.00 ? 0.98  
- Shadow: reduced  
- Glow: removed  
- Quick, precise feedback  

### Applies To
- Buttons  
- Icons  
- Interactive cards  

### Notes
Active state should feel mechanical and intentional.

---

## 2.3 Focus State

### Behavior
- Blueprint cyan outline (1–2px)  
- Soft glow (2–4px)  
- Increased clarity  

### Applies To
- Inputs  
- Buttons  
- Form elements  
- Interactive components  

### Notes
Focus must be accessible and visible without being loud.

---

## 2.4 Disabled State

### Behavior
- Opacity: 30–40%  
- No glow  
- No shadow  
- No hover or active states  

### Applies To
- Buttons  
- Inputs  
- Cards  
- Icons  

### Notes
Disabled elements should feel unavailable but still readable.

---

# 3. Component-Specific Interaction Rules

## 3.1 Buttons

### Hover
- Soft scale  
- Slight glow  
- Shadow deepen  

### Active
- Quick depress  
- Remove glow  

### Focus
- Blueprint outline  

### Disabled
- Lower opacity  
- No interactions  

---

## 3.2 Cards

### Hover
- Soft scale  
- Shadow deepen  
- Optional glow  

### Active
- Slight depress  

### Disabled
- Reduced opacity  

---

## 3.3 Panels

### Hover
- Very subtle lift (1–2px)  
- Slight shadow deepen  

### Active
- Minimal movement  

### Focus
- Blueprint outline (rare)  

---

## 3.4 Inputs & Form Elements

### Hover
- Slight border highlight  

### Focus
- Blueprint glow  
- Clear outline  

### Active
- Crisp feedback  

### Disabled
- Muted border  
- Lower opacity  

---

# 4. Timing & Easing

### Standard
- 150–250ms ease-out  

### Active
- 80–120ms ease-in  

### Focus
- 150–200ms ease-out  

### Disabled
- No transitions  

---

# 5. Accessibility Rules

- Focus states must always be visible  
- Hover cannot be the only indicator  
- Disabled elements must remain readable  
- Motion must be subtle and non-distracting  

---

# 6. Interaction Principles

1. Feedback must be immediate  
2. Motion must be calm  
3. Glow must be subtle  
4. States must be consistent  
5. Interactions must support clarity  

---
