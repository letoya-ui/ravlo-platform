from LoanMVP.extensions import db
from datetime import datetime
import platform, socket


# -----------------------------
# 🧠 SYSTEM MODEL
# -----------------------------
class System(db.Model):
    """
    Represents the LoanMVP system instance.
    Tracks environment, version, uptime, and performance metrics.
    """
    __tablename__ = "system"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), default="LoanMVP Core")
    version = db.Column(db.String(50), default="v1.0")
    environment = db.Column(db.String(50), default="production")  # dev, staging, production
    hostname = db.Column(db.String(120), default=socket.gethostname)
    os = db.Column(db.String(120), default=platform.system)
    uptime_start = db.Column(db.DateTime, default=datetime.utcnow)
    last_heartbeat = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String(50), default="Online")

    total_users = db.Column(db.Integer, default=0)
    total_loans = db.Column(db.Integer, default=0)
    total_errors = db.Column(db.Integer, default=0)

    logs = db.relationship("SystemLog", backref="system", lazy=True)
    audits = db.relationship("AuditLog", backref="system", lazy=True)

    def heartbeat(self):
        self.last_heartbeat = datetime.utcnow()
        db.session.commit()

    def __repr__(self):
        return f"<System {self.name} {self.version} {self.status}>"


# -----------------------------
# 🧾 SYSTEM LOG MODEL
# -----------------------------
class SystemLog(db.Model):
    """
    Logs system-level events and errors.
    """
    __tablename__ = "system_log"

    id = db.Column(db.Integer, primary_key=True)
    system_id = db.Column(db.Integer, db.ForeignKey("system.id"))
    level = db.Column(db.String(20))  # INFO, WARNING, ERROR, DEBUG
    message = db.Column(db.Text)
    origin = db.Column(db.String(120))  # module, route, or service
    user = db.Column(db.String(120))  # user or "system"
    ip_address = db.Column(db.String(64))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<SystemLog {self.level}: {self.message[:40]}>"


# -----------------------------
# 🕵️‍♀️ AUDIT LOG MODEL
# -----------------------------
class AuditLog(db.Model):
    """
    Records every key user or admin action across the platform for traceability.
    """
    __tablename__ = "audit_log"

    id = db.Column(db.Integer, primary_key=True)
    system_id = db.Column(db.Integer, db.ForeignKey("system.id"))
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
    module = db.Column(db.String(120))  # e.g. "CRM", "AI", "Executive", "Borrower"
    action = db.Column(db.String(120))  # e.g. "Created Lead", "Edited Quote", "Deleted Loan"
    object_type = db.Column(db.String(120))  # e.g. "Lead", "Loan", "Borrower"
    object_id = db.Column(db.Integer)
    message = db.Column(db.Text)
    ip_address = db.Column(db.String(64))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<AuditLog {self.module}: {self.action}>"

class SystemSettings(db.Model):
    __tablename__ = "system_settings"

    id = db.Column(db.Integer, primary_key=True)
    system_name = db.Column(db.String(120), default="Caughman Mason Loan Services")
    theme_color = db.Column(db.String(20), default="#7ab8ff")
    ai_mode = db.Column(db.String(50), default="Enabled")
    version = db.Column(db.String(20), default="1.0.0")
    maintenance_mode = db.Column(db.Boolean, default=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<SystemSettings {self.system_name}>"


