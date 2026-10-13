"""
LAYER 4 - Hallucination Detection Pipeline
"""

import numpy as np
from sentence_transformers import SentenceTransformer
from config import EMBED_MODEL, HDP_WARNING, HDP_REFUSAL

embedder = SentenceTransformer(EMBED_MODEL)


def cosine_similarity(vec_a, vec_b):
    a = np.array(vec_a)
    b = np.array(vec_b)
    dot = np.dot(a, b)
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return float(dot / (norm_a * norm_b))


def check(answer, source_chunks):
    if not answer or not source_chunks:
        return {
            "confidence": 0.0,
            "status": "refused",
            "message": "No answer or sources",
            "answer": None
        }
    
    answer_vec = embedder.encode(answer).tolist()
    scores = []
    
    for chunk in source_chunks:
        if isinstance(chunk, dict):
            content = chunk.get("content", "")
        else:
            content = str(chunk)
        if not content:
            continue
        chunk_vec = embedder.encode(content).tolist()
        sim = cosine_similarity(answer_vec, chunk_vec)
        scores.append(sim)
    
    if not scores:
        return {
            "confidence": 0.0,
            "status": "refused",
            "message": "Could not analyze",
            "answer": None
        }
    
    confidence = round(max(scores), 4)
    
    if confidence < HDP_REFUSAL:
        return {
            "confidence": confidence,
            "status": "refused",
            "message": "Low confidence",
            "answer": None
        }
    elif confidence < HDP_WARNING:
        return {
            "confidence": confidence,
            "status": "warning",
            "message": "Medium confidence",
            "answer": answer
        }
    else:
        return {
            "confidence": confidence,
            "status": "verified",
            "message": "Verified",
            "answer": answer
        }
