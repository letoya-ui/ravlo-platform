# Ravlo Grid System (Expanded)
The structural backbone of the Ravlo OS — columns, gutters, grids, and responsive rules.

---

# 1. Grid Philosophy

Ravlo grids are:
- Architectural, not arbitrary  
- Calm and predictable  
- Built for investor-grade clarity  
- Consistent across marketing and dashboard surfaces  

The grid is the invisible skeleton of the OS.

---

# 2. Core Grid Types

### Fixed Grids
- ravlo-grid-2  
- ravlo-grid-3  
- ravlo-grid-4  

### Auto Grids
- ravlo-grid-auto-fit  
- ravlo-grid-auto-fill  

### Stack Layouts
- ravlo-stack-vertical  
- ravlo-stack-horizontal  

---

# 3. Column System

### Desktop (= 1200px)
- 12-column underlying system  
- Gutter: 24px  
- Max content width: 1200–1320px  

### Tablet (768–1199px)
- 8-column system  
- Gutter: 20px  

### Mobile (= 767px)
- 4-column system  
- Gutter: 16px  

---

# 4. Grid Tokens

### Column Widths (Conceptual)
- col-1: 1/12  
- col-2: 2/12  
- col-3: 3/12  
- col-4: 4/12  
- col-6: 6/12  
- col-8: 8/12  
- col-12: full width  

### Gutter Tokens
- gutter-sm: 16px  
- gutter-md: 24px  
- gutter-lg: 32px  

---

# 5. Layout Patterns

### 5.1 Two-Column Layout
- Left: content  
- Right: panel / visual  
- Ratio: 7/12 + 5/12 or 8/12 + 4/12  

### 5.2 Three-Column Layout
- Equal columns  
- Used for features, metrics, modules  

### 5.3 Sidebar Layout
- Sidebar: 3/12 or 4/12  
- Main: 9/12 or 8/12  

---

# 6. Component Grid Usage

### Panels
- Typically span 4–12 columns  
- Use consistent gutters  

### Cards
- Use ravlo-grid-3 or ravlo-grid-4  
- Auto-fit on smaller screens  

### Metrics
- Use tight grids (3–4 per row)  
- Maintain consistent spacing  

---

# 7. Responsive Rules

### Desktop ? Tablet
- 3-column ? 2-column  
- 4-column ? 2-column  

### Tablet ? Mobile
- All grids collapse to single column  
- Maintain vertical rhythm with spacing tokens  

---

# 8. Vertical Rhythm

### Spacing Between Sections
- space-64 to space-96  

### Spacing Between Components
- space-24 to space-48  

### Spacing Inside Components
- Panels: space-32  
- Cards: space-24  

---

# 9. Grid Do & Don't

### Do
- Align components to the grid  
- Use consistent gutters  
- Maintain clear hierarchy  

### Don't
- Break grid arbitrarily  
- Mix random widths  
- Overcrowd rows  

---

# 10. Grid Principles

1. Structure over improvisation  
2. Predictability over chaos  
3. Calm spacing over compression  
4. One grid system across OS and marketing  
5. The grid is the architecture of the experience  

---
