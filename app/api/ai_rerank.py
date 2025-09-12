from fastapi import APIRouter, HTTPException, status, Depends
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
import threading
import asyncio
import os
import logging

# Import your model class (adjust import path if needed)
from app.engine.semantic_star import SemanticStarModel

logger = logging.getLogger("ai_rerank_router")

router = APIRouter()

# ----------------- Module-level model + lock -----------------
_model: Optional[SemanticStarModel] = None
_model_lock = threading.Lock()

# Operation counter for optional autosave
_operation_counter = 0
_AUTOSAVE_INTERVAL = int(os.getenv("RERANK_AUTOSAVE_INTERVAL", "0"))  # 0 => disabled

# ----------------- Pydantic request models --------------------
class Candidate(BaseModel):
    poi_id: str
    tags: List[str] = Field(default_factory=list)
    description: str = ""

class FeedbackEvent(BaseModel):
    poi_id: Optional[str] = None
    rating: int = Field(..., ge=1, le=5)
    tags: List[str] = Field(default_factory=list)
    description: str = ""
    comment: str = ""

class RerankRequest(BaseModel):
    feedback_events: List[FeedbackEvent] = Field(default_factory=list, max_items=500)
    candidates: List[Candidate] = Field(..., max_items=500)
    use_semantic: bool = True

# ----------------- Init / Shutdown helpers --------------------
def init_model(model_path: str = "saved_model", ann_backend: Optional[str] = None,
               model_name: str = "sentence-transformers/all-MiniLM-L6-v2",
               alpha: float = 0.25, decay_rate: float = 0.02) -> None:
    """
    Initialize and load the SemanticStarModel into this module.
    Call this from your application's startup event.
    """
    global _model
    logger.info("Initializing reranker model...")
    _model = SemanticStarModel(model_name=model_name, alpha=alpha, decay_rate=decay_rate, ann_backend=ann_backend)
    meta_file = os.path.join(model_path, 'metadata.json')
    emb_file = os.path.join(model_path, 'embeddings.npy')
    if os.path.exists(meta_file) and os.path.exists(emb_file):
        try:
            _model.load_model(model_path)
            logger.info(f"Loaded saved model from {model_path} (profiles={len(_model.semantic_affinities)})")
            try:
                _model.build_ann_index(backend=ann_backend)
                logger.info("Built ANN index for reranker")
            except Exception as e:
                logger.warning(f"Failed to build ANN index: {e}")
        except Exception as e:
            logger.warning(f"Failed to load saved model from {model_path}: {e}. Starting fresh reranker.")
    else:
        logger.warning(f"No valid saved model found at {model_path}; starting fresh reranker (no embeddings loaded)")

def shutdown_model(save_path: str = "saved_model") -> None:
    """Save model state on shutdown (if loaded)."""
    global _model
    if _model:
        try:
            _model.save_model(save_path)
            logger.info("Reranker model saved on shutdown")
        except Exception as e:
            logger.exception("Failed to save reranker model on shutdown: %s", e)

# ----------------- Internal worker wrapper --------------------
async def _run_feedback_and_rerank_in_thread(feedback_list: List[Dict[str, Any]],
                                             candidates_list: List[Dict[str, Any]],
                                             use_semantic: bool):
    """
    Run the blocking model operations inside a threadpool.
    This function acquires the module-level lock to avoid concurrent mutation.
    """
    global _model, _model_lock, _operation_counter, _AUTOSAVE_INTERVAL

    if _model is None:
        raise RuntimeError("Reranker model not initialized")

    loop = asyncio.get_running_loop()

    def worker():
        # critical section
        with _model_lock:
            # apply feedback (mutates model state)
            if feedback_list:
                _model.process_feedback(feedback_list)

            # rerank and return results
            if use_semantic:
                return _model.rerank_candidates(candidates_list)
            else:
                # tag-only fallback shaped like reranker output
                results = []
                for i, cand in enumerate(candidates_list):
                    tag_score = _model.calculate_tag_score(cand.get("tags", []))
                    results.append({
                        "index": i,
                        "poi_id": cand.get("poi_id", ""),
                        "score": max(0.0, min(1.0, 0.5 + 0.5 * tag_score)),
                        "reason": f"Tag-only scoring: {tag_score:.2f}",
                        "tag_score": float(tag_score),
                        "semantic_score": 0.0,
                        "candidate": cand
                    })
                results.sort(key=lambda x: x["score"], reverse=True)
                return results

    reranked = await loop.run_in_executor(None, worker)

    # optional autosave after N operations
    if _AUTOSAVE_INTERVAL and _model:
        _operation_counter += 1
        if _operation_counter % _AUTOSAVE_INTERVAL == 0:
            try:
                _model.save_model()  # default saves to provided model path earlier or you can pass explicit path
                logger.info("Reranker autosaved model state")
            except Exception as e:
                logger.warning("Reranker autosave failed: %s", e)

    return reranked

# ----------------- Router endpoint -----------------------------
@router.post("/feedback_rerank")
async def feedback_rerank(request: RerankRequest):
    """
    Process feedback_events and rerank provided candidates in one call.
    """
    logger.info(f"[feedback_rerank] Entry: {len(request.candidates)} candidates, {len(request.feedback_events)} feedback events")

    try:
        feedback_dicts = [f.dict() for f in request.feedback_events] if request.feedback_events else []
        candidates_dicts = [c.dict() for c in request.candidates]

        results = await _run_feedback_and_rerank_in_thread(feedback_dicts, candidates_dicts, request.use_semantic)
        return {"results": results}

    except RuntimeError as e:
        logger.exception("Reranker runtime error")
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        logger.exception("Unhandled error in reranker endpoint")
        raise HTTPException(status_code=500, detail=str(e))


# ----------------- Health check endpoint ---------------------
@router.get("/ping")
async def ping():
    """Simple ping endpoint to verify router reachability."""
    return {"status": "ok", "router": "ai_rerank"}
