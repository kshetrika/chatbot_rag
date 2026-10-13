"""
LAYER 1 - Document Ingestion
Stores company documents in ChromaDB
"""

import chromadb
from sentence_transformers import SentenceTransformer
from config import EMBED_MODEL

print("Loading embedding model...")
embedder = SentenceTransformer(EMBED_MODEL)
print(f"Embedding model ready: {EMBED_MODEL}")

client = chromadb.PersistentClient(path="./chroma_db")
collection = client.get_or_create_collection(name="enterprise_docs")
print(f"ChromaDB ready - {collection.count()} documents stored")


def chunk_text(text, max_words=150):
    paragraphs = [p.strip() for p in text.split("\n") if p.strip()]
    chunks, current = [], ""
    for para in paragraphs:
        combined = (current + " " + para).strip()
        if len(combined.split()) > max_words and current:
            chunks.append(current)
            current = para
        else:
            current = combined
    if current:
        chunks.append(current)
    return chunks if chunks else [text]


def ingest(doc_id, content, metadata):
    chunks = chunk_text(content)
    for i, chunk in enumerate(chunks):
        chunk_id = f"{doc_id}_chunk{i}"
        vector = embedder.encode(chunk).tolist()
        meta = dict(metadata)
        if isinstance(meta.get("topic_tags"), list):
            meta["topic_tags"] = ",".join(meta["topic_tags"])
        collection.upsert(
            ids=[chunk_id],
            embeddings=[vector],
            documents=[chunk],
            metadatas=[meta]
        )
    print(f"Stored: {doc_id} ({len(chunks)} chunks)")


def search(query, filters=None, top_k=5):
    query_vector = embedder.encode(query).tolist()
    where = None
    if filters:
        conditions = {}
        if filters.get("department"):
            conditions["department"] = {"$eq": filters["department"]}
        if filters.get("document_type"):
            conditions["document_type"] = {"$eq": filters["document_type"]}
        if len(conditions) == 1:
            where = conditions
        elif len(conditions) > 1:
            where = {"$and": [{k: v} for k, v in conditions.items()]}
    
    total = collection.count()
    if total == 0:
        return []
    
    results = collection.query(
        query_embeddings=[query_vector],
        n_results=min(top_k, total),
        where=where,
        include=["documents", "metadatas", "distances"]
    )
    
    output = []
    for j in range(len(results["ids"][0])):
        score = round(1 - results["distances"][0][j], 4)
        output.append({
            "id": results["ids"][0][j],
            "content": results["documents"][0][j],
            "metadata": results["metadatas"][0][j],
            "score": score
        })
    return output


SAMPLE_DOCUMENTS = [
    {
        "id": "HR-001",
        "content": """EMPLOYEE HANDBOOK 2024

Leave Policy:
- Annual leave: 20 days per year
- Sick leave: 10 days per year
- Maternity leave: 6 months
- Paternity leave: 2 weeks

How to request leave:
1. Login to HR portal
2. Click Request Leave
3. Select dates
4. Add reason
5. Submit for manager approval

Approval timeline:
- Annual leave: Approved within 2 days
- Sick leave: Approved same day
- Special leave: Approved within 5 days

Important: Leave must be requested minimum 5 days in advance except sick leave.""",
        "metadata": {
            "department": "HR",
            "document_type": "policy",
            "author": "HR Team",
            "creation_date": "2024-01-01",
            "last_updated": "2024-04-29",
            "topic_tags": ["leave", "employee", "policy"],
            "security_classification": "internal"
        }
    },
    {
        "id": "IT-001",
        "content": """DATA SECURITY POLICY 2024

Password Requirements:
- Minimum 14 characters
- Must include uppercase, lowercase, numbers, symbols
- Change every 90 days
- Cannot reuse last 5 passwords

Account Access:
- Multi-factor authentication MFA required
- VPN required for remote access
- Screen lock after 5 minutes inactivity

Data Classification:
- Public: Can be shared externally
- Internal: Employees only
- Confidential: Department heads only
- Restricted: Director approval required

Violation consequences:
- First violation: Warning
- Second violation: Account suspension
- Third violation: Termination

Report security issues immediately to IT Security team.""",
        "metadata": {
            "department": "IT",
            "document_type": "policy",
            "author": "IT Security",
            "creation_date": "2024-01-15",
            "last_updated": "2024-04-29",
            "topic_tags": ["security", "data", "policy"],
            "security_classification": "confidential"
        }
    },
    {
        "id": "HR-002",
        "content": """REMOTE WORKING POLICY 2024

Remote Work Allowance:
- Maximum 3 days per week remote
- Requires line manager approval
- Home office assessment mandatory before approval

Equipment Provided:
- Laptop
- Monitor
- Keyboard and mouse
- Headphones

Requirements:
- Reliable internet minimum 10 Mbps
- Quiet workspace
- Proper desk setup
- VPN connection required

Working Hours:
- Must align with team schedule
- Office days: Monday, Wednesday, Thursday
- Flexible timing: 8 AM to 6 PM
- Must attend all meetings on-site when required""",
        "metadata": {
            "department": "HR",
            "document_type": "policy",
            "author": "HR Team",
            "creation_date": "2024-02-01",
            "last_updated": "2024-04-29",
            "topic_tags": ["remote", "work", "policy"],
            "security_classification": "internal"
        }
    },
    {
        "id": "FIN-001",
        "content": """EXPENSE POLICY 2024

Reimbursement Guidelines:
- All expenses must be submitted within 30 days
- Original receipts required for expenses over Rs 25
- Personal expenses NOT reimbursable
- Alcoholic beverages NOT reimbursable

Travel Expenses:
- Pre-approval required for travel
- Accommodation: Maximum Rs 150 per night
- Meals: Maximum Rs 500 per day
- Transportation: Economy class only

Approval Authority:
- Under Rs 1000: Line manager
- Rs 1000 to Rs 5000: Department head
- Over Rs 5000: Finance director

Submission Process:
1. Fill expense form
2. Attach receipts
3. Get manager approval
4. Submit to Finance
5. Reimbursement within 5 working days""",
        "metadata": {
            "department": "Finance",
            "document_type": "policy",
            "author": "Finance Team",
            "creation_date": "2024-01-10",
            "last_updated": "2024-04-29",
            "topic_tags": ["expenses", "travel", "policy"],
            "security_classification": "internal"
        }
    },
    {
        "id": "IT-002",
        "content": """INCIDENT RESPONSE PROCEDURE 2024

Incident Severity Levels:

P1 Critical:
- Complete system down
- Data breach
- Security attack
- Escalate to: CISO, CEO, CTO
- Response time: 15 minutes

P2 High:
- System partially down
- Performance degradation
- Single service affected
- Escalate to: IT Manager
- Response time: 1 hour

P3 Medium:
- Minor functionality issues
- Performance concern
- Single user affected
- Response time: 4 hours

P4 Low:
- Documentation updates
- Feature requests
- General inquiries
- Response time: 24 hours

Reporting:
- Call: +91-XXXX-XXXX-XXX
- Email: incidents@company.com
- Include: What happened, when, impact, affected systems""",
        "metadata": {
            "department": "IT",
            "document_type": "procedure",
            "author": "IT Team",
            "creation_date": "2024-01-20",
            "last_updated": "2024-04-29",
            "topic_tags": ["incident", "security", "emergency"],
            "security_classification": "confidential"
        }
    }
]


if __name__ == "__main__":
    print("\n" + "="*60)
    print("LAYER 1 - DOCUMENT INGESTION")
    print("="*60)
    print(f"\nIngesting {len(SAMPLE_DOCUMENTS)} documents...")
    for doc in SAMPLE_DOCUMENTS:
        ingest(doc["id"], doc["content"], doc["metadata"])
    print(f"\nTotal documents in DB: {collection.count()}")
    print("="*60)
