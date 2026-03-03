# LoanMVP/models/document_models.py
from LoanMVP.extensions import db
from datetime import datetime


class LoanDocument(db.Model):
    __tablename__ = "loan_document"

    id = db.Column(db.Integer, primary_key=True)
    borrower_profile_id = db.Column(db.Integer, db.ForeignKey("borrower_profile.id"), nullable=True)
    investor_profile_id = db.Column(db.Integer, db.ForeignKey("investor_profile.id"), nullable=True)
    loan_id = db.Column(db.Integer, db.ForeignKey("loan_application.id"), nullable=True)
    processor_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
    file_name = db.Column(db.String(255))
    file_path = db.Column(db.String(255))
    document_type = db.Column(db.String(100))
    notes = db.Column(db.Text)
    document_name = db.Column(db.String(255))
    review_status = db.Column(db.String(50), default="Pending")  # ✅ New
    sent_to_underwriter = db.Column(db.Boolean, default=False)
    reviewed_at = db.Column(db.DateTime, nullable=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    status = db.Column(db.String(50), default="Pending")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    uploaded_by = db.Column(db.String(120))
    submitted_file = db.Column(db.String(255))          # 🆕 uploaded file name
    submitted_at = db.Column(db.DateTime)  
    document_type = db.Column(db.String(100), default="Other")
    review_notes = db.Column(db.Text, nullable=True)
    reviewed_by = db.Column(db.String(120), nullable=True)

    # Relationships
    borrower_profile = db.relationship("BorrowerProfile", back_populates="documents")
    loan_application = db.relationship("LoanApplication", back_populates="loan_documents")
    investor_profile = db.relationship("InvestorProfile", back_populates="documents")

    def __repr__(self):
        return f"<LoanDocument {self.file_name} Loan:{self.loan_id}>"


class DocumentRequest(db.Model):
    __tablename__ = "document_requests"

    id = db.Column(db.Integer, primary_key=True)
    borrower_id = db.Column(db.Integer, db.ForeignKey("borrower_profile.id"))
    investor_profile_id = db.Column(db.Integer, db.ForeignKey("investor_profile.id"))
    loan_id = db.Column(db.Integer, db.ForeignKey("loan_application.id"), nullable=True)
    requested_by = db.Column(db.String(120))
    document_name = db.Column(db.String(255))
    notes = db.Column(db.Text)
    status = db.Column(db.String(50), default="Pending")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    file_path = db.Column(db.String(255))
    verified_at = db.Column(db.DateTime)
    is_resolved = db.Column(db.Boolean, default=False)

    # Relationships
    borrower = db.relationship("BorrowerProfile", back_populates="document_requests")
    loan = db.relationship("LoanApplication", back_populates="document_requests")
    investor_profile = db.relationship("InvestorProfile", back_populates="documents_requests")

    def __repr__(self):
        return f"<DocRequest {self.document_name} for borrower {self.investor_id}>"

class ESignedDocument(db.Model):
    __tablename__ = "esigned_document"

    id = db.Column(db.Integer, primary_key=True)

    # ----------------------------------------------------------------------
    #  Relationships
    # ----------------------------------------------------------------------
    borrower_profile_id = db.Column(
        db.Integer,
        db.ForeignKey("borrower_profile.id"),
        nullable=False
    )

    investor_profile_id = db.Column(
        db.Integer,
        db.ForeignKey("investor_profile.id"),
        nullable=False
    )

    loan_id = db.Column(
        db.Integer,
        db.ForeignKey("loan_application.id"),
        nullable=False
    )

    # Attached document record (optional)
    loan_document_id = db.Column(
        db.Integer,
        db.ForeignKey("loan_document.id"),
        nullable=True
    )

    # ----------------------------------------------------------------------
    # 📄 E-Signature Metadata
    # ----------------------------------------------------------------------
    document_name = db.Column(db.String(255), nullable=False)
    document_type = db.Column(db.String(100), nullable=True)  # e.g., 1003, 4506C, LOE, etc.

    provider = db.Column(db.String(50), nullable=False)   
    # DocuSign / HelloSign / SignNow / AdobeSign / PandaDoc

    envelope_id = db.Column(db.String(255), nullable=True)   # Envelope / request ID
    signer_email = db.Column(db.String(255), nullable=True)
    signer_name = db.Column(db.String(255), nullable=True)

    # ----------------------------------------------------------------------
    #  Signing Status
    # ----------------------------------------------------------------------
    status = db.Column(db.String(50), default="pending")
    # pending / sent / viewed / signed / declined / voided / error

    status_message = db.Column(db.String(500), nullable=True)

    viewed_at = db.Column(db.DateTime, nullable=True)
    signed_at = db.Column(db.DateTime, nullable=True)

    # ----------------------------------------------------------------------
    #  File Paths (Local or S3)
    # ----------------------------------------------------------------------
    pdf_original_path = db.Column(db.String(500), nullable=True)
    pdf_signed_path = db.Column(db.String(500), nullable=True)

    # ----------------------------------------------------------------------
    #  Audit Trail
    # ----------------------------------------------------------------------
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # JSON logs from provider (optional)
    webhook_log = db.Column(db.JSON, nullable=True)

    # ----------------------------------------------------------------------
    #  Relationships Backrefs
    # ----------------------------------------------------------------------
    borrower = db.relationship("BorrowerProfile", backref="esigned_documents")
    loan = db.relationship("LoanApplication", backref="esigned_documents")
    loan_document = db.relationship("LoanDocument", backref="esign_record")
    investor_profile = db.relationship("InvestorProfile", back_populates="esigned_documents")

    def __repr__(self):
        return f"<ESignedDocument {self.document_name} status={self.status}>"

class DocumentNeed(db.Model):
    __tablename__ = "document_need"

    id = db.Column(db.Integer, primary_key=True)

    borrower_id = db.Column(
        db.Integer,
        db.ForeignKey("borrower_profile.id", name="fk_need_borrower")
    )
    
    investor_id = db.Column(
        db.Integer,
        db.ForeignKey("investor_profile.id", name="fk_need_investor")
    )   

    loan_id = db.Column(
        db.Integer,
        db.ForeignKey("loan_application.id", name="fk_need_loan")
    )

    name = db.Column(db.String(200))
    reason = db.Column(db.String(500))   # Why AI thinks it's needed
    status = db.Column(db.String(50), default="required")  # required / uploaded / waived
    created_at = db.Column(db.DateTime, default=db.func.now())

    borrower = db.relationship("BorrowerProfile", backref="doc_needs")
    loan = db.relationship("LoanApplication", backref="doc_needs")
    investor_profile = db.relationship("InvestorProfile", backref="doc_needs")

    def __repr__(self):
        return f"<DocNeed {self.name} investor={self.investor_id}>"

class ResourceDocument(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False)
    category = db.Column(db.String(100), nullable=False)
    filename = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text)
    active = db.Column(db.Boolean, default=True)

