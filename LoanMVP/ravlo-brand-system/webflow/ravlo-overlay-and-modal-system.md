# Ravlo Overlay & Modal System
The architecture for dialogs, drawers, overlays, confirmations, and full-screen takeovers across the Ravlo OS.

---

# 1. Overlay Philosophy

Ravlo overlays are:
- Calm and cinematic  
- Focused and intentional  
- Designed to reduce cognitive load  
- Structured to guide decision-making  
- Consistent across all modules and workflows  

Overlays must feel like a controlled shift in attention, not a disruption.

---

# 2. Overlay Types

### 2.1 Standard Modal
- Centered  
- Medium width  
- Used for confirmations, forms, and details  

### 2.2 Fullscreen Modal
- Edge-to-edge  
- Used for complex workflows  
- Includes header + close action  

### 2.3 Drawer (Left or Right)
- Slides in from side  
- Used for quick actions, filters, or summaries  

### 2.4 Bottom Sheet (Mobile)
- Slides up  
- Used for mobile-first workflows  

### 2.5 Lightbox Overlay
- Used for images, previews, or media  

---

# 3. Modal Anatomy

### Required Elements
- Header  
- Title  
- Close button  
- Body content  
- Footer (optional)  

### Optional Elements
- Subheader  
- Icon  
- Progress indicator  

---

# 4. Overlay States

### Default
- Dimmed backdrop  
- Soft fade-in  
- Slight scale-up  

### Hover (Close Button)
- Glow  
- Soft scale  

### Active
- Crisp feedback  

### Focus
- Blueprint outline  

### Disabled
- Muted  
- No interactions  

---

# 5. Motion & Timing

### Open Animation
- Fade-in: 150–200ms  
- Slide or scale: 150–200ms  
- Easing: ease-out  

### Close Animation
- Fade-out: 120–150ms  
- Easing: ease-in  

### Drawer Motion
- Slide-in from edge  
- Smooth, not bouncy  

---

# 6. Backdrop Rules

### Backdrop Color
- rgba(0, 0, 0, 0.6)  

### Backdrop Behavior
- Click outside closes modal (optional)  
- Backdrop must not distract  
- Backdrop must not blur content excessively  

---

# 7. Accessibility Requirements

### Focus Management
- Focus moves into modal on open  
- Focus returns to trigger on close  
- Focus trap required  

### Keyboard Support
- Escape closes modal  
- Tab cycles through elements  
- Shift+Tab reverses cycle  

### Screen Reader Support
- aria-modal="true"  
- aria-labelledby  
- aria-describedby  

---

# 8. Drawer System

### Drawer Widths
- Small: 320px  
- Medium: 480px  
- Large: 640px  

### Drawer Behavior
- Slide-in  
- Dimmed backdrop  
- Close on escape  
- Optional close on backdrop click  

---

# 9. Fullscreen Modal System

### Use Cases
- Multi-step workflows  
- Document review  
- Complex forms  
- Data-heavy tasks  

### Structure
- Header  
- Body  
- Footer  
- Optional sidebar  

---

# 10. Confirmation Dialogs

### Types
- Standard confirmation  
- Destructive confirmation  
- Multi-step confirmation  

### Rules
- Clear title  
- Clear description  
- Primary + secondary CTA  
- Destructive actions use semantic red  

---

# 11. Overlay Principles

1. Overlays must focus attention, not overwhelm  
2. Motion must be calm and intentional  
3. Accessibility is mandatory  
4. Overlays must feel like OS-level surfaces  
5. Every overlay must support clarity and decision-making  

---
