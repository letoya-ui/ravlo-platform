# Ravlo Notification System
The unified architecture for toasts, alerts, banners, and inline messages across the Ravlo OS.

---

# 1. Notification Philosophy

Ravlo notifications are:
- Calm and unobtrusive  
- Clear and purposeful  
- Designed to reduce anxiety  
- Consistent across all modules  
- Focused on clarity, not noise  

Notifications should guide, not overwhelm.

---

# 2. Notification Types

### 2.1 Toasts
- Temporary  
- Appears bottom-right (desktop)  
- Appears top-center (mobile)  
- Used for confirmations, updates, and quick feedback  

### 2.2 Alerts
- Inline  
- Used for form errors, warnings, and info messages  

### 2.3 Banners
- Full-width  
- Used for system-wide messages, outages, or major updates  

### 2.4 Status Badges
- Small, inline indicators  
- Used for statuses like “Active”, “Pending”, “Failed”  

---

# 3. Toast System

### Toast Types
- Success  
- Warning  
- Error  
- Info  

### Anatomy
- Icon  
- Title  
- Description (optional)  
- Close button  

### Behavior
- Slide-in + fade  
- Auto-dismiss (4–6 seconds)  
- Pause on hover  
- Manual close allowed  

### Motion
- 150–200ms ease-out  
- No bounce  

---

# 4. Alert System

### Alert Types
- Error  
- Warning  
- Info  
- Success  

### Anatomy
- Icon  
- Title  
- Description  
- Optional actions  

### Placement
- Inline within forms or panels  

### Behavior
- Persistent until resolved  
- No auto-dismiss  

---

# 5. Banner System

### Banner Types
- System banner  
- Announcement banner  
- Warning banner  

### Anatomy
- Icon  
- Message  
- CTA (optional)  
- Close button  

### Behavior
- Full-width  
- Stays until dismissed  
- High visibility  

---

# 6. Status Badges

### Badge Types
- Active  
- Pending  
- Completed  
- Failed  
- Draft  

### Rules
- Use semantic colors  
- Keep text short  
- Rounded pill shape  

---

# 7. Color Tokens for Notifications

### Success
- Green background  
- Soft white text  

### Warning
- Yellow background  
- Midnight text  

### Error
- Red background  
- Soft white text  

### Info
- Blueprint background  
- Soft white text  

---

# 8. Accessibility Requirements

- Must meet contrast ratios  
- Must be screen-reader friendly  
- Toasts must announce via aria-live  
- Banners must be keyboard navigable  
- Close buttons must have accessible labels  

---

# 9. Motion Guidelines

### Allowed
- Fade  
- Slide  
- Soft glow  

### Avoid
- Bounce  
- Overshoot  
- Aggressive movement  

---

# 10. Notification Principles

1. Clarity over noise  
2. Calm over urgency  
3. Predictability builds trust  
4. Notifications must guide, not distract  
5. Every message must support decision-making  

---
