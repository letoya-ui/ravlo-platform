# LoanMVP/forms/__init__.py
from .borrower_forms import BorrowerProfileForm, PreapprovalForm
from .credit_forms import CreditCheckForm
from .auth_forms import LoginForm, ResetPasswordRequestForm, ResetPasswordForm, RegisterForm
from .loan_officer_forms import (
    BorrowerIntakeForm,
    BorrowerSearchForm,
    LoanEditForm,
    QuoteForm,
    QuotePlanForm,
    UploadForm,
    FollowUpForm,
    CRMNoteForm,
    CampaignForm,
    TaskForm,
    GenerateQuoteForm,
)

from .ai_forms import (
    AIIntakePromptForm,
    AIChatForm,
    AICampaignForm,
     AIIntakeForm,
    AIIntakeReviewForm,
)
