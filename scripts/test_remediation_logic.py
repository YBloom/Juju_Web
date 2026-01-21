
from sqlmodel import SQLModel, Field, Session, create_engine, text
import logging

# Define simplified model
class SubscriptionTarget(SQLModel, table=True):
    id: int = Field(default=None, primary_key=True)
    kind: str

def test_remediation_logic():
    # In-memory DB
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    
    with Session(engine) as session:
        # Insert mixed data
        session.add(SubscriptionTarget(kind="play"))  # Lowercase (Bad)
        session.add(SubscriptionTarget(kind="ACTOR")) # Uppercase (Good)
        session.commit()
        
        # Run remediation logic (copied from script)
        raw_results = session.execute(text("SELECT kind, COUNT(*) FROM subscriptiontarget GROUP BY kind")).all()
        
        to_fix = []
        for kind_result, count in raw_results:
            kind_str = str(kind_result) if kind_result else ""
            if kind_str and kind_str != kind_str.upper():
                to_fix.append((kind_str, count))
        
        print(f"Found to fix: {to_fix}")
        
        if len(to_fix) == 1 and to_fix[0][0] == 'play':
            print("✅ Logic Verified: Detection works.")
        else:
            print("❌ Logic Failed: Detection is broken.")

if __name__ == "__main__":
    test_remediation_logic()
