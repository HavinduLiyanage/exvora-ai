"""
Rerank API endpoint for contextual candidate reranking.
"""

from fastapi import APIRouter, HTTPException, Request, Depends
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from app.engine.reranker import rerank_candidates_with_metadata
from app.api.errors import raise_http_error
from app.logs import log_json
from app.common.logging import timed
import time

router = APIRouter()


class FeedbackEvent(BaseModel):
    """Individual feedback event model."""
    poi_id: Optional[str] = None
    rating: int = Field(..., ge=1, le=5, description="Rating from 1 to 5 stars")
    tags: List[str] = Field(default_factory=list, description="Tags associated with the rating")
    comment: Optional[str] = None
    ts: Optional[str] = Field(None, description="Timestamp in ISO format")


class AuditLog(BaseModel):
    """Audit log containing feedback events."""
    feedback_events: List[FeedbackEvent] = Field(default_factory=list)


class Candidate(BaseModel):
    """Candidate POI for reranking."""
    poi_id: str
    tags: List[str] = Field(default_factory=list)
    score: float = Field(..., description="Base score for the candidate")
    title: Optional[str] = None


class RerankRequest(BaseModel):
    """Request model for reranking."""
    candidates: List[Candidate] = Field(..., description="List of candidates to rerank")
    preferences: Dict[str, Any] = Field(default_factory=dict, description="User preferences")
    audit_log: AuditLog = Field(..., description="Audit log with feedback events")
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "candidates": [
                    {"poi_id": "ella_hike", "tags": ["hiking", "quiet"], "score": 0.62},
                    {"poi_id": "nightlife_district", "tags": ["nightlife"], "score": 0.58},
                    {"poi_id": "pettah_market", "tags": ["street_food"], "score": 0.55}
                ],
                "preferences": {"themes": ["nature"], "avoid_tags": ["crowded"]},
                "audit_log": {
                    "feedback_events": [
                        {
                            "poi_id": "ella_hike",
                            "rating": 5,
                            "tags": ["hiking", "quiet"],
                            "ts": "2025-08-25T08:30:00Z"
                        },
                        {
                            "poi_id": "nightlife_district",
                            "rating": 1,
                            "tags": ["nightlife", "crowded"],
                            "ts": "2025-08-24T19:10:00Z"
                        }
                    ]
                }
            }
        }
    }


class RerankedCandidate(BaseModel):
    """Reranked candidate with updated score and reason."""
    poi_id: str
    score: float
    reason: Optional[str] = None


class RerankResponse(BaseModel):
    """Response model for reranking."""
    reranked: List[RerankedCandidate] = Field(..., description="Reranked candidates")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Reranking metadata")
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "reranked": [
                    {
                        "poi_id": "ella_hike",
                        "score": 0.745,
                        "reason": "Boosted by 1.0★ hiking affinity"
                    },
                    {
                        "poi_id": "pettah_market",
                        "score": 0.55
                    },
                    {
                        "poi_id": "nightlife_district",
                        "score": 0.455,
                        "reason": "Penalized by 1.0★ nightlife rating"
                    }
                ],
                "metadata": {
                    "rerank_applied": True,
                    "n_feedback_events": 2,
                    "n_affinity_tags": 4,
                    "n_candidates_with_reasons": 2
                }
            }
        }
    }


@router.post("/rerank", response_model=RerankResponse)
def rerank_candidates_endpoint(req: RerankRequest, request: Request):
    """
    Rerank candidates based on user feedback and tag affinities.
    
    This endpoint takes a list of candidates and an audit log of user feedback,
    then reranks the candidates based on learned tag affinities from the feedback.
    """
    request_id = getattr(request.state, 'req_id', 'unknown')
    start_time = time.time()
    
    log_json(request_id, "rerank_start", 
             n_candidates=len(req.candidates),
             n_feedback_events=len(req.audit_log.feedback_events))
    
    try:
        with timed("rerank"):
            # Convert Pydantic models to dictionaries
            candidates_dict = [candidate.model_dump() for candidate in req.candidates]
            audit_log_dict = req.audit_log.model_dump()
            
            # Perform reranking
            reranked_candidates, metadata = rerank_candidates_with_metadata(
                candidates_dict, audit_log_dict
            )
            
            # Convert back to response format
            reranked_response = []
            for candidate in reranked_candidates:
                reranked_response.append(RerankedCandidate(
                    poi_id=candidate["poi_id"],
                    score=round(candidate["score"], 3),
                    reason=candidate.get("reason")
                ))
            
            # Prepare response
            response = RerankResponse(
                reranked=reranked_response,
                metadata=metadata
            )
            
            duration = time.time() - start_time
            log_json(request_id, "rerank_complete",
                     duration_ms=round(duration * 1000, 1),
                     rerank_applied=metadata.get("rerank_applied", False),
                     n_candidates_with_reasons=metadata.get("n_candidates_with_reasons", 0))
            
            return response
            
    except Exception as e:
        log_json(request_id, "rerank_error", error=str(e))
        raise_http_error(500, "rerank_error", f"Reranking failed: {e}", ["Try again later"])


@router.get("/rerank/health")
def rerank_health():
    """Health check for rerank endpoint."""
    return {"status": "ok", "endpoint": "rerank"}
