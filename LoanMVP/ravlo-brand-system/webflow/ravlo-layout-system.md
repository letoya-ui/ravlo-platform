# Ravlo Layout System
The spatial rules that define the Ravlo OS — cinematic, architectural, investor-grade.

---

# 1. Ravlo Spacing Scale

Ravlo uses a modular 8-point system with cinematic breathing room.

| Token | Value | Usage |
|------|-------|-------|
| space-2 | 2px | hairline spacing |
| space-4 | 4px | micro adjustments |
| space-8 | 8px | small gaps |
| space-12 | 12px | card internals |
| space-16 | 16px | default UI spacing |
| space-24 | 24px | section internals |
| space-32 | 32px | panel padding |
| space-48 | 48px | hero spacing |
| space-64 | 64px | cinematic breathing room |
| space-96 | 96px | major section spacing |

---

# 2. Ravlo Section Structure

Every section follows a predictable structure:

<section class="ravlo-section ravlo-section--dark">
    <div class="ravlo-container">
        <div class="ravlo-section-header">
            <h2 class="heading-lg">Title</h2>
            <p class="body-md">Subtitle</p>
        </div>
        <div class="ravlo-section-body"></div>
    </div>
</section>

### Section modifiers:
- ravlo-section--dark  
- ravlo-section--light  
- ravlo-section--blueprint  
- ravlo-section--hero  

### Container widths:
- ravlo-container (1200px)  
- ravlo-container--wide (1400px)  
- ravlo-container--narrow (900px)  

---

# 3. Ravlo Grid System

Ravlo uses a 12-column responsive grid with simplified utilities.

### Prebuilt grids:
- ravlo-grid-2  
- ravlo-grid-3  
- ravlo-grid-4  
- ravlo-grid-auto  

### Rules:
- Grid gaps use space-24 or space-32  
- Tablet collapses to 2 columns  
- Mobile collapses to 1 column  

---

# 4. Ravlo Flex System

Utilities for alignment:

- ravlo-flex  
- ravlo-flex-center  
- ravlo-flex-between  
- ravlo-flex-column  
- ravlo-flex-end  

---

# 5. Ravlo Panel Layout Rules

Panels are core to the Ravlo Visual OS.

### Panel padding:
- space-24 (compact)  
- space-32 (standard)  
- space-48 (cinematic)  

### Structure:
<div class="ravlo-panel ravlo-panel--floating">
    <div class="ravlo-panel-header"></div>
    <div class="ravlo-panel-body"></div>
</div>

### Modifiers:
- ravlo-panel--floating  
- ravlo-panel--glass  
- ravlo-panel--blueprint  

---

# 6. Ravlo Vertical Rhythm

Vertical spacing between elements:

- Standard sections: space-96  
- Hero ? next section: space-64  
- Panel stacks: space-32  
- Card stacks: space-24  

---

# 7. Ravlo Breakpoints

| Device | Width |
|--------|--------|
| Desktop XL | 1440px+ |
| Desktop | 1200px |
| Tablet | 992px |
| Mobile Large | 768px |
| Mobile | 480px |

### Rules:
- Typography scales at 992px  
- Grids collapse at 768px  
- Panels stack vertically at 768px  
- Hero spacing reduces at 480px  

---

# 8. Ravlo Hero Layout

### Structure:
- full width  
- large breathing room (space-96)  
- blueprint rings or spotlighting behind content  

### Spacing:
- Desktop: space-96  
- Tablet: space-64  
- Mobile: space-48  

---

# 9. Ravlo Layout Principles

1. Cinematic spacing  
2. Architectural alignment  
3. Predictable structure  
4. Calm hierarchy  
5. Modular composition  

---
