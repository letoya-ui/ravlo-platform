# LoanMVP/models/__init__.py
from LoanMVP.extensions import db

# ======================================================
# 🧱 Base Model Imports — Core Entities First
# ======================================================

# 🧍 User & Authentication
from LoanMVP.models.user_model import User

# 🏠 Property (used by LoanApplication)
from LoanMVP.models.property import Property, SavedProperty 

# 🧾 Borrower / Loan Models (core financial logic)
from LoanMVP.models.loan_models import (
    BorrowerProfile,
    LoanIntakeSession,
    LoanApplication,
    LoanQuote,
    CreditProfile,
    LoanNotification,
    Upload,
    LoanScenario,
    DocumentEvent,
    LoanStatusEvent,
)

# 📄 Loan Documents
from LoanMVP.models.document_models import LoanDocument, DocumentRequest, ESignedDocument, DocumentNeed

# 🤖 Loan Officer & Analytics
from LoanMVP.models.loan_officer_model import (
    LoanOfficerProfile,
    LoanOfficerAnalytics,
    LoanOfficerPortfolio,
    LenderQuote,
    
)

# 💬 CRM Models (communication, notes, insights)
from LoanMVP.models.crm_models import (
    Lead,
    CRMNote,
    Message,
    LeadSource,
    Task,
    BehavioralInsight,
    Partner, 
    FollowUpItem, 
    MessageThread,
    FollowUpTask,
    BorrowerLastContact,
)

# 📈 Borrower-side tools (analysis, budgeting, plans)
from LoanMVP.models.borrowers import (
    PropertyAnalysis,
    ProjectBudget,
    SubscriptionPlan,
    ProjectExpense,
    BorrowerInteraction,
    BorrowerMessage,
    Deal,
    DealShare,
    
)

# 💬 Chat / AI conversation history
from LoanMVP.models.chat_models import ChatHistory

from LoanMVP.models.underwriter_model import UnderwriterProfile, UnderwritingCondition, ConditionRequest, UnderwriterAuditLog, UnderwriterTask

from LoanMVP.models.processor_model import ProcessorProfile

from LoanMVP.models.ai_models import LoanAIConversation, AIAuditLog, LoanOfficerAISummary, AIIntakeSummary, AIAssistantInteraction

from LoanMVP.models.system_models import System, SystemLog, AuditLog, SystemSettings

from LoanMVP.models.chat_models import ChatHistory

from LoanMVP.models.campaign_model import Campaign, CampaignRecipient, CampaignMessage

from LoanMVP.models.call_model import CallLog, CommunicationLog

from LoanMVP.models.contractor_models import Contractor, ContractorPayment

from LoanMVP.models.activity_models import BorrowerActivity

from LoanMVP.models.payment_models import PaymentRecord

from LoanMVP.models.credit_models import SoftCreditReport
from LoanMVP.models.partner_models import PartnerRequest, PartnerJob
# ======================================================
# 🧩 SQLAlchemy Export (for Migrate / Shell)
# ======================================================

__all__ = [
    # Core
    "db",
    "User",
    "Property",

    # Borrower / Loan
    "BorrowerProfile",
    "LoanApplication",
    "LoanQuote",
    "CreditProfile",
    "LoanDocument",

    # Loan Officer
    "LoanOfficerProfile",
    "LoanOfficerAISummary",
    "LoanOfficerAnalytics",
    "LoanOfficerPortfolio",
    "LenderQuote",

    # CRM
    "Lead",
    "CRMNote",
    "Message",
    "LeadSource",
    "Task",
    "BehavioralInsight",

    # Borrower-side features
    "PropertyAnalysis",
    "ProjectBudget",
    "SubscriptionPlan",

    # Chat History
    "ChatHistory",
]
