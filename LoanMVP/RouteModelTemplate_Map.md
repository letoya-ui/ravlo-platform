# 🔗 Route–Model–Template Map

---

### Borrower Module
| Route | Model(s) | Template | Notes |
|:--|:--|:--|:--|
| /borrower/dashboard | BorrowerProfile, LoanApplication | borrower/dashboard.html | Main dashboard |
| /borrower/upload_docs | LoanDocument | borrower/upload_docs.html | Upload center |
| /borrower/quotes | LoanQuote, LenderAPI | borrower/quotes.html | New lender quote tool |
| /borrower/messages | Message | borrower/messages.html | CRM chat view |
| /borrower/profile | BorrowerProfile | borrower/profile.html | Edit borrower info |

---

### Loan Officer Module
| Route | Model(s) | Template | Notes |
| /loan_officer/dashboard | LoanApplication, BehavioralInsight | loan_officer/dashboard.html | Central dashboard |
| /loan_officer/analytics | BehavioralInsight | loan_officer/analytics.html | Trends & performance |
| /loan_officer/new_application | BorrowerProfile, LoanApplication | loan_officer/new_application.html | Create borrower loan |

---

### Admin Module
| Route | Model(s) | Template | Notes |
| /admin/verify | LoanApplication, CreditProfile | admin/verify_loans.html | Loan health check |
| /admin/analytics | LoanApplication, BehavioralInsight | admin/analytics.html | Global stats |

---

### CRM Module
| Route | Model(s) | Template | Notes |
| /crm/leads | Lead, LeadSource | crm/leads.html | Manage leads |
| /crm/messages | Message | crm/messages.html | Communication |
| /crm/notes | Note | crm/notes.html | Internal notes |

