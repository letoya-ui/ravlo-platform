# Ravlo CMS Schema
The structured content architecture powering the Ravlo OS — modules, partners, pricing, presets, blog, and investor resources.

---

# 1. CMS Philosophy

The Ravlo CMS is:
- Modular  
- Scalable  
- Cinematic  
- Investor-grade  
- Structured like an operating system  

Every content type is designed to support the Ravlo Visual OS and Ravlo Layout System.

---

# 2. Core Collections

These are the foundational content types.

---

## 2.1 Modules Collection

### Purpose
Represents each major Ravlo module.

### Fields
- Name (text)  
- Slug (text)  
- Description (rich text)  
- Icon (image)  
- Accent Color (color)  
- Category (reference: Module Categories)  
- Features (multi-reference: Module Features)  
- Hero Image (image)  
- Status (enum: Active, Coming Soon, Deprecated)  

---

## 2.2 Module Features Collection

### Purpose
Stores reusable features for modules.

### Fields
- Title (text)  
- Description (text)  
- Icon (image)  
- Module (reference: Modules)  

---

## 2.3 Module Categories Collection

### Purpose
Groups modules into logical families.

### Fields
- Name (text)  
- Description (text)  
- Accent Color (color)  

---

# 3. Partner Ecosystem Collections

---

## 3.1 Partners Collection

### Purpose
Represents companies or individuals in the Ravlo ecosystem.

### Fields
- Name (text)  
- Logo (image)  
- Category (reference: Partner Categories)  
- Description (rich text)  
- Website URL (text)  
- Contact Email (text)  
- Status (enum: Active, Pending, Inactive)  

---

## 3.2 Partner Categories Collection

### Purpose
Defines partner types.

### Fields
- Name (text)  
- Description (text)  

---

# 4. Pricing & Plans Collections

---

## 4.1 Pricing Tiers Collection

### Purpose
Defines pricing tiers for Ravlo.

### Fields
- Tier Name (text)  
- Price (text)  
- Description (text)  
- Features (multi-reference: Pricing Features)  
- Accent Color (color)  
- Recommended (boolean)  

---

## 4.2 Pricing Features Collection

### Purpose
Reusable features for pricing tiers.

### Fields
- Feature Name (text)  
- Description (text)  

---

# 5. Content Collections

---

## 5.1 Blog Posts Collection

### Purpose
Long-form content for education and SEO.

### Fields
- Title (text)  
- Slug (text)  
- Author (reference: Authors)  
- Cover Image (image)  
- Body (rich text)  
- Tags (multi-reference: Tags)  
- Publish Date (date)  
- Status (enum: Draft, Published)  

---

## 5.2 Authors Collection

### Purpose
Stores blog authors.

### Fields
- Name (text)  
- Bio (text)  
- Avatar (image)  

---

## 5.3 Tags Collection

### Purpose
Reusable tags for blog posts.

### Fields
- Name (text)  

---

# 6. Presets & Style Collections

---

## 6.1 Architectural Presets Collection

### Purpose
Stores preset styles for property transformations.

### Fields
- Name (text)  
- Description (text)  
- Category (reference: Preset Categories)  
- Preview Image (image)  
- Color Palette (multi-image or multi-color)  
- Moodboard (multi-image)  

---

## 6.2 Preset Categories Collection

### Purpose
Groups presets into families.

### Fields
- Name (text)  
- Description (text)  

---

# 7. Investor Resources Collection

### Purpose
Educational and operational content for investors.

### Fields
- Title (text)  
- Category (reference: Resource Categories)  
- Body (rich text)  
- Download File (file)  
- Thumbnail (image)  

---

## 7.1 Resource Categories Collection

### Purpose
Groups investor resources.

### Fields
- Name (text)  
- Description (text)  

---

# 8. CMS Principles

1. Modular, not monolithic  
2. Reusable, not duplicated  
3. Structured, not chaotic  
4. Cinematic, not generic  
5. Scalable for future modules  

---
