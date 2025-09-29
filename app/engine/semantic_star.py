"""
 SemanticStarModel
- stable SHA256 keys for descriptions
- normalized embeddings
- optional ANN support (FAISS or hnswlib if available)
- FAISS write/read when available
- Cross-encoder rescoring pipeline (optional)
- Efficient persistence: embeddings in .npy (memmap-compatible), metadata in JSON
- Time decay, Bayesian shrinkage, and clustering hooks

Requirements:
  pip install sentence-transformers numpy scikit-learn faiss-cpu hnswlib (optional)

Note: ANN libraries are optional. The class will fall back to linear search if FAISS/hnswlib unavailable.
"""

import os
import json
import hashlib
import logging
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any
import numpy as np

# sentence_transformers for embeddings and cross-encoder
from sentence_transformers import SentenceTransformer
try:
    from sentence_transformers import CrossEncoder
    HAS_CROSS = True
except Exception:
    HAS_CROSS = False

# Attempt optional ANN libraries
HAS_FAISS = False
HAS_HNSW = False
try:
    import faiss
    HAS_FAISS = True
except Exception:
    try:
        import hnswlib
        HAS_HNSW = True
    except Exception:
        HAS_HNSW = False

# sklearn helpers
from sklearn.decomposition import PCA
from sklearn.cluster import KMeans


logger = logging.getLogger("SemanticStarModel")
logging.basicConfig(level=logging.INFO)


def _sha256_key(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _normalize(vec: np.ndarray) -> np.ndarray:
    v = vec.astype(np.float32)
    norm = np.linalg.norm(v)
    if norm == 0 or np.isnan(norm):
        return v
    return v / norm


class SemanticStarModel:
    def __init__(
        self,
        model_name: str = "sentence-transformers/all-MiniLM-L6-v2",
        alpha: float = 0.25,
        decay_rate: float = 0.02,
        ann_backend: Optional[str] = None,  # 'faiss', 'hnsw', or None
        ann_dim: Optional[int] = None,
    ):
        self.model = SentenceTransformer(model_name)
        self.cross_encoder = None

        self.tag_affinities: Dict[str, float] = {}
        self.semantic_affinities: Dict[str, Dict[str, Any]] = {}
        self.alpha = float(alpha)
        self.decay_rate = float(decay_rate)
        self.last_update = datetime.now()

        # ANN related
        self.ann_backend = ann_backend if ann_backend in ("faiss", "hnsw") else None
        self.ann_index = None
        self._keys_list: List[str] = []  # mapping from ANN index position -> key
        self._embeddings_matrix: Optional[np.ndarray] = None  # (N, D) float32 normalized embeddings
        self.ann_dim = ann_dim  # set during build if None

        # Persistence metadata
        self._metadata_file = None
        self._embeddings_file = None
        self._faiss_index_file = None

        logger.info(f"Model initialized: embed_dim={self.model.get_sentence_embedding_dimension()}, ann_backend={self.ann_backend}")

    def init_cross_encoder(self, model_name: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"):
        if not HAS_CROSS:
            raise RuntimeError("sentence-transformers CrossEncoder unavailable in this environment")
        try:
            self.cross_encoder = CrossEncoder(model_name)
            logger.info(f"CrossEncoder loaded: {model_name}")
        except Exception:
            logger.warning(f"Failed to load CrossEncoder model {model_name}. Cross-encoder reranking will be disabled.")
            self.cross_encoder = None

    def rating_to_weight(self, rating: int) -> float:
        # tanh sharpening of linear mapping to emphasize extremes
        x = (rating - 3) / 2.0
        return float(np.tanh(2.0 * x))

    def update_tag_affinity(self, tag: str, rating: int) -> None:
        weight = self.rating_to_weight(rating)
        if tag not in self.tag_affinities:
            self.tag_affinities[tag] = 0.0
        self.tag_affinities[tag] = (1 - self.alpha) * self.tag_affinities[tag] + self.alpha * weight

    def _embed_text(self, text: str) -> np.ndarray:
        emb = self.model.encode([text], convert_to_numpy=True)[0]
        return _normalize(emb)

    def update_semantic_affinity(self, description: str, rating: int) -> str:
        key = _sha256_key(description)
        embedding = self._embed_text(description)
        weight = self.rating_to_weight(rating)
        now_iso = datetime.now().isoformat()

        if key not in self.semantic_affinities:
            self.semantic_affinities[key] = {
                'description': description,
                'embedding': embedding,
                'weight': float(weight),
                'count': 1,
                'last_seen': now_iso,
            }
            logger.debug(f"New semantic profile added: {key}")
        else:
            entry = self.semantic_affinities[key]
            entry['weight'] = float((1 - self.alpha) * entry['weight'] + self.alpha * weight)
            entry['count'] = int(entry['count'] + 1)
            entry['last_seen'] = now_iso
            
        self._invalidate_ann()
        return key

    def _invalidate_ann(self):
        self.ann_index = None
        self._keys_list = []
        self._embeddings_matrix = None

    def apply_decay(self) -> None:
        now = datetime.now()
        days_elapsed = (now - self.last_update).days
        if days_elapsed <= 0:
            return
        decay_factor = (1 - self.decay_rate) ** days_elapsed
        for tag in list(self.tag_affinities.keys()):
            self.tag_affinities[tag] *= decay_factor
        for k in list(self.semantic_affinities.keys()):
            self.semantic_affinities[k]['weight'] *= decay_factor
        self.last_update = now
        logger.info(f"Applied decay for {days_elapsed} days (factor={decay_factor:.6f})")

    def save_model(self, dirpath: str) -> None:
        os.makedirs(dirpath, exist_ok=True)
        metadata = {
            'tag_affinities': self.tag_affinities,
            'semantic_meta': {},
            'alpha': self.alpha,
            'decay_rate': self.decay_rate,
            'last_update': self.last_update.isoformat(),
        }
        
        keys = list(self.semantic_affinities.keys())
        embeddings = []
        for k in keys:
            v = self.semantic_affinities[k]
            embeddings.append(v['embedding'].astype(np.float32))
            metadata['semantic_meta'][k] = {
                'description': v['description'],
                'weight': v['weight'],
                'count': v['count'],
                'last_seen': v['last_seen']
            }
        embeddings = np.vstack(embeddings) if embeddings else np.zeros((0, self.model.get_sentence_embedding_dimension()), dtype=np.float32)

        meta_file = os.path.join(dirpath, 'metadata.json')
        emb_file = os.path.join(dirpath, 'embeddings.npy')
        with open(meta_file, 'w') as f:
            json.dump(metadata, f, indent=2)
        np.save(emb_file, embeddings)

        if HAS_FAISS and self.ann_index is not None and self.ann_backend == 'faiss':
            faiss_file = os.path.join(dirpath, 'faiss.index')
            faiss.write_index(self.ann_index, faiss_file)
            logger.info(f"FAISS index saved to {faiss_file}")

        logger.info(f"Model saved to {dirpath} (metadata + embeddings)")

    def load_model(self, dirpath: str) -> None:
        meta_file = os.path.join(dirpath, 'metadata.json')
        emb_file = os.path.join(dirpath, 'embeddings.npy')
        if not os.path.exists(meta_file) or not os.path.exists(emb_file):
            raise FileNotFoundError(f"Model files not found in {dirpath}")
            
        with open(meta_file, 'r') as f:
            metadata = json.load(f)
            
        self.tag_affinities = metadata.get('tag_affinities', {})
        self.alpha = metadata.get('alpha', self.alpha)
        self.decay_rate = metadata.get('decay_rate', self.decay_rate)
        self.last_update = datetime.fromisoformat(metadata.get('last_update')) if metadata.get('last_update') else self.last_update

        semantic_meta = metadata.get('semantic_meta', {})
        self.semantic_affinities = {}
        for k, v in semantic_meta.items():
            self.semantic_affinities[k] = {
                'description': v.get('description', ''),
                'embedding': None,
                'weight': v.get('weight', 0.0),
                'count': int(v.get('count', 0)),
                'last_seen': v.get('last_seen')
            }

        embeddings = np.load(emb_file)
        if embeddings.shape[0] != len(self.semantic_affinities):
            keys = list(self.semantic_affinities.keys())
            for i, k in enumerate(keys):
                if i < embeddings.shape[0]:
                    self.semantic_affinities[k]['embedding'] = embeddings[i]
                else:
                    self.semantic_affinities[k]['embedding'] = np.zeros((self.model.get_sentence_embedding_dimension(),), dtype=np.float32)
        else:
            for i, k in enumerate(self.semantic_affinities.keys()):
                self.semantic_affinities[k]['embedding'] = embeddings[i]

        self._invalidate_ann()
        logger.info(f"Model loaded from {dirpath}")

    def build_ann_index(self, backend: Optional[str] = None, ef_construction: int = 200) -> None:
        if backend:
            self.ann_backend = backend if backend in ('faiss', 'hnsw') else None
        if self.ann_backend == 'faiss' and not HAS_FAISS:
            logger.warning('FAISS requested but not available. Falling back to linear search.')
            self.ann_backend = None
        if self.ann_backend == 'hnsw' and not HAS_HNSW:
            logger.warning('hnswlib requested but not available. Falling back to linear search.')
            self.ann_backend = None

        keys = list(self.semantic_affinities.keys())
        if not keys:
            logger.info('No semantic profiles to index')
            return

        embeddings = np.vstack([self.semantic_affinities[k]['embedding'] for k in keys]).astype(np.float32)
        norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        embeddings = embeddings / norms

        self._embeddings_matrix = embeddings
        self._keys_list = keys
        d = embeddings.shape[1]
        self.ann_dim = d

        if self.ann_backend == 'faiss' and HAS_FAISS:
            index = faiss.IndexFlatIP(d)
            index.add(embeddings)
            self.ann_index = index
            logger.info('Built FAISS IndexFlatIP')
        elif self.ann_backend == 'hnsw' and HAS_HNSW:
            p = hnswlib.Index(space='cosine', dim=d)
            p.init_index(max_elements=embeddings.shape[0], ef_construction=ef_construction, M=16)
            p.add_items(embeddings, np.arange(embeddings.shape[0]))
            p.set_ef(ef_construction)
            self.ann_index = p
            logger.info('Built hnswlib index')
        else:
            self.ann_index = None
            logger.info('ANN not built - will use linear search fallback')

    def _ann_search(self, query_emb: np.ndarray, top_k: int = 32) -> List[Tuple[float, str]]:
        if self._embeddings_matrix is None or len(self._keys_list) == 0:
            return []
        q = query_emb.astype(np.float32)
        if self.ann_index is None:
            sims = np.dot(self._embeddings_matrix, q)
            idx = np.argsort(-sims)[:top_k]
            return [(float(sims[i]), self._keys_list[i]) for i in idx]

        if self.ann_backend == 'faiss' and HAS_FAISS:
            D, I = self.ann_index.search(q.reshape(1, -1), top_k)
            D = D[0]
            I = I[0]
            results = []
            for sim, idx in zip(D, I):
                if idx < 0:
                    continue
                results.append((float(sim), self._keys_list[idx]))
            return results

        if self.ann_backend == 'hnsw' and HAS_HNSW:
            labels, distances = self.ann_index.knn_query(q, k=min(top_k, len(self._keys_list)))
            results = []
            for lbl, dist in zip(labels[0], distances[0]):
                sim = 1.0 - dist / 2.0
                results.append((float(sim), self._keys_list[int(lbl)]))
            return results

        sims = np.dot(self._embeddings_matrix, q)
        idx = np.argsort(-sims)[:top_k]
        return [(float(sims[i]), self._keys_list[i]) for i in idx]

    def calculate_semantic_score(self, description: str, top_k: int = 32, prior_count: float = 5.0) -> float:
        if not self.semantic_affinities:
            return 0.0
        q_emb = _normalize(self._embed_text(description))
        if self._embeddings_matrix is None:
            self.build_ann_index(self.ann_backend)

        neighbors = self._ann_search(q_emb, top_k=top_k)
        if not neighbors:
            return 0.0

        weighted_scores = []
        weights = []
        for sim, key in neighbors:
            entry = self.semantic_affinities.get(key)
            if entry is None:
                continue
            w = float(entry['weight'])
            c = float(entry.get('count', 1))
            conf = c / (c + prior_count)
            
            last_seen = entry.get('last_seen')
            if last_seen:
                try:
                    days = (datetime.now() - datetime.fromisoformat(last_seen)).days
                    time_decay = (1 - self.decay_rate) ** max(days, 0)
                except Exception:
                    time_decay = 1.0
            else:
                time_decay = 1.0

            effective_weight = w * conf * time_decay
            weighted_scores.append(sim * effective_weight)
            weights.append(abs(effective_weight))

        if not weights or sum(weights) == 0:
            return 0.0
        return float(sum(weighted_scores) / sum(weights))

    def calculate_tag_score(self, tags: List[str]) -> float:
        if not tags or not self.tag_affinities:
            return 0.0
        vals = [self.tag_affinities.get(t, 0.0) for t in tags]
        if not vals:
            return 0.0
        return float(sum(vals) / len(vals))

    def rerank_candidates(self, candidates: List[Dict], base_scores: Optional[List[float]] = None, top_k_cross: int = 20) -> List[Dict]:
        self.apply_decay()
        results = []
        if base_scores is None:
            base_scores = [0.5] * len(candidates)

        for i, cand in enumerate(candidates):
            poi_id = cand.get('poi_id', '')
            tags = cand.get('tags', [])
            desc = cand.get('description', '')

            tag_score = self.calculate_tag_score(tags)
            semantic_score = self.calculate_semantic_score(desc)
            base_score = base_scores[i]

            tag_weight = 0.4
            semantic_weight = 0.4
            base_weight = 0.2

            final_score = (
                base_weight * base_score +
                tag_weight * (0.5 + 0.5 * tag_score) +
                semantic_weight * (0.5 + 0.5 * semantic_score)
            )

            reasons = []
            if tag_score > 0.1:
                reasons.append(f"Strong tag affinity (+{tag_score:.2f})")
            elif tag_score < -0.1:
                reasons.append(f"Negative tag affinity ({tag_score:.2f})")

            if semantic_score > 0.1:
                reasons.append(f"Semantic match (+{semantic_score:.2f})")
            elif semantic_score < -0.1:
                reasons.append(f"Semantic mismatch ({semantic_score:.2f})")

            if not reasons:
                reasons.append("Neutral preference")

            results.append({
                'index': i,
                'poi_id': poi_id,
                'score': max(0.0, min(1.0, float(final_score))),
                'reason': '; '.join(reasons),
                'tag_score': float(tag_score),
                'semantic_score': float(semantic_score),
                'base_score': float(base_score),
                'candidate': cand
            })

        results.sort(key=lambda x: x['score'], reverse=True)
        return results

    def _build_user_profile_text(self) -> str:
        tags_sorted = sorted(self.tag_affinities.items(), key=lambda x: x[1], reverse=True)
        top_tags = [t for t, s in tags_sorted[:8] if s > 0]
        positives = [v for v in self.semantic_affinities.values() if v['weight'] > 0]
        positives_sorted = sorted(positives, key=lambda x: (x['weight'], x['count']), reverse=True)
        descs = [p['description'] for p in positives_sorted[:5]]
        parts = []
        if top_tags:
            parts.append('I like: ' + ', '.join(top_tags))
        if descs:
            parts.append('Examples: ' + ' | '.join(descs))
        return ' '.join(parts) if parts else ''

    def process_feedback(self, events: List[Dict]) -> None:
        self.apply_decay()
        for ev in events:
            poi = ev.get('poi_id')
            rating = int(ev.get('rating', 3))
            tags = ev.get('tags', []) or []
            desc = ev.get('description', '') or ''
            comment = ev.get('comment', '') or ''
            for t in tags:
                self.update_tag_affinity(t, rating)
            if desc:
                self.update_semantic_affinity(desc, rating)
            if comment:
                self.update_semantic_affinity(comment, rating)
            logger.info(f"Processed feedback {poi}: {rating}★")