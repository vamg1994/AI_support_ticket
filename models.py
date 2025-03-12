from datetime import datetime
from app import db
from sqlalchemy import Index

class Ticket(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), nullable=False)
    description = db.Column(db.Text, nullable=False)
    category = db.Column(db.String(50), nullable=False)
    status = db.Column(db.String(20), nullable=False)
    ai_response = db.Column(db.Text)
    confidence_score = db.Column(db.Float)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    requires_human_attention = db.Column(db.Boolean, default=False)
    resolution_notes = db.Column(db.Text)
    resolved_at = db.Column(db.DateTime)

    # Indexes for commonly queried fields
    __table_args__ = (
        Index('idx_ticket_email', email),
        Index('idx_ticket_status', status),
        Index('idx_ticket_category', category),
        Index('idx_ticket_created_at', created_at),
        Index('idx_ticket_resolved_at', resolved_at),
    )

    def __repr__(self):
        return f'<Ticket {self.id}>'

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'email': self.email,
            'description': self.description,
            'category': self.category,
            'status': self.status,
            'ai_response': self.ai_response,
            'confidence_score': self.confidence_score,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'requires_human_attention': self.requires_human_attention,
            'resolution_notes': self.resolution_notes,
            'resolved_at': self.resolved_at.isoformat() if self.resolved_at else None
        }