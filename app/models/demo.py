from datetime import datetime
from ..extensions import db


class DemoRecord(db.Model):
    """A single row created by the demo seeder.

    Demo data lives in the same tables as real data and looks identical, so
    every row the seeder inserts is recorded here. `clear-demo` deletes
    exactly these rows and nothing else, so real data is never touched.
    """

    __tablename__ = "demo_records"

    id         = db.Column(db.Integer, primary_key=True)
    # Groups one `seed-demo` invocation, so runs can be removed individually.
    run_id     = db.Column(db.String(32), nullable=False, index=True)
    # Logical table name: 'user', 'gym', 'fighter', 'fight', 'venue',
    # 'event', 'bout', 'registration'.
    entity     = db.Column(db.String(30), nullable=False)
    entity_id  = db.Column(db.Integer, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    def to_dict(self) -> dict:
        return {
            "id":         self.id,
            "run_id":     self.run_id,
            "entity":     self.entity,
            "entity_id":  self.entity_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
