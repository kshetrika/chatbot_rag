"""
LAYER 3 - Adaptive Retrieval Optimization
"""

from layer1_ingestion import search
from layer2_dmfe import extract_filters
from config import ARO_THRESHOLD, ARO_MAX_RETRY, DEFAULT_TOP_K


def retrieve(question, filters, top_k=DEFAULT_TOP_K):
    print(f"[ARO] Retrieving documents...")
    best_results = []
    current_filters = dict(filters) if filters else {}
    
    for attempt in range(1, ARO_MAX_RETRY + 1):
        results = search(question, filters=current_filters, top_k=top_k)
        if not results:
            print(f"  Attempt {attempt}: No results")
        else:
            top_score = results[0]["score"]
            print(f"  Attempt {attempt}: Score {top_score:.3f}", end="")
            if top_score >= ARO_THRESHOLD:
                print(" OK")
                return results
            else:
                print(" (Below threshold)")
                if not best_results or top_score > best_results[0]["score"]:
                    best_results = results
        
        if "document_type" in current_filters:
            current_filters.pop("document_type")
        elif "depatment" in current_filters:
            current_filters.pop("department")
        elif current_filters:
            current_filters = {}
        else:
            break
    
    if best_results:
        return best_results
    return search(question, filters=None, top_k=top_k)


def retrieve_with_analysis(question):
    filters = extract_filters(question)
    results = retrieve(question, filters, top_k=DEFAULT_TOP_K)
    return {
        "filters": filters,
        "results": results,
        "result_count": len(results),
        "query_type": "document",
        "is_comprehensive": False
    }
