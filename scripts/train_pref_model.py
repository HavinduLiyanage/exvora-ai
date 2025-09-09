#!/usr/bin/env python3
"""
Offline training script for preference scoring model.
Generates synthetic data if data/pref_training.csv is missing.
"""

import os
import json
import pandas as pd
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline
from sklearn.metrics import accuracy_score, roc_auc_score
from sklearn.feature_extraction.text import CountVectorizer
import joblib
from datetime import datetime

# Create directories
os.makedirs("data", exist_ok=True)
os.makedirs("app/models", exist_ok=True)

def generate_synthetic_data(n_samples=400):
    """Generate synthetic training data for preference scoring."""
    np.random.seed(42)  # For reproducibility
    
    # Define tag vocabulary
    tag_vocab = [
        "culture", "nature", "food", "history", "art", "music", "sports", "shopping",
        "adventure", "relaxation", "family", "romantic", "budget", "luxury", "local",
        "tourist", "quiet", "crowded", "indoor", "outdoor", "religious", "secular",
        "modern", "traditional", "urban", "rural", "beach", "mountain", "city", "village"
    ]
    
    # Price bands
    price_bands = ["free", "low", "medium", "high"]
    
    data = []
    
    for i in range(n_samples):
        # Generate random number of tags (1-4)
        n_tags = np.random.randint(1, 5)
        tags = np.random.choice(tag_vocab, n_tags, replace=False)
        
        # Generate price band with bias toward lower prices
        price_band = np.random.choice(price_bands, p=[0.2, 0.4, 0.3, 0.1])
        
        # Generate cost based on price band
        if price_band == "free":
            cost = 0
        elif price_band == "low":
            cost = np.random.uniform(1, 15)
        elif price_band == "medium":
            cost = np.random.uniform(15, 50)
        else:  # high
            cost = np.random.uniform(50, 200)
        
        # Generate duration (30-300 minutes)
        duration = np.random.uniform(30, 300)
        
        # Generate opening alignment (0-1)
        opening_align = np.random.beta(2, 2)  # Biased toward middle values
        
        # Generate distance (0-50 km)
        distance = np.random.exponential(5)
        
        # Generate label based on heuristics
        # Prefer: lower cost, shorter duration, better opening alignment, closer distance
        # Also prefer certain tag combinations
        cost_score = max(0, 1 - cost / 100)  # Lower cost is better
        duration_score = max(0, 1 - duration / 200)  # Shorter duration is better
        distance_score = max(0, 1 - distance / 20)  # Closer is better
        
        # Tag preference (some tags are more "preferred")
        preferred_tags = {"culture", "nature", "food", "history", "art", "local", "quiet"}
        tag_score = len(set(tags) & preferred_tags) / len(tags) if len(tags) > 0 else 0
        
        # Combined score
        combined_score = (cost_score * 0.3 + duration_score * 0.2 + 
                         float(opening_align) * 0.2 + distance_score * 0.1 + tag_score * 0.2)
        
        # Add some noise and convert to binary
        noise = np.random.normal(0, 0.1)
        label = 1 if combined_score + noise > 0.5 else 0
        
        data.append({
            "label": label,
            "tags": ";".join(tags),
            "price_band": price_band,
            "estimated_cost": round(cost, 2),
            "duration_minutes": round(duration),
            "opening_align": round(opening_align, 3),
            "distance_km": round(distance, 2)
        })
    
    return pd.DataFrame(data)

def build_features(df, tag_vocab, feature_names):
    """Build feature matrix from dataframe."""
    # One-hot encode tags
    tag_vectorizer = CountVectorizer(vocabulary=tag_vocab, binary=True)
    tag_features = tag_vectorizer.fit_transform(df["tags"]).toarray()
    
    # One-hot encode price bands
    price_bands = ["free", "low", "medium", "high"]
    price_features = np.zeros((len(df), len(price_bands)))
    for i, price_band in enumerate(price_bands):
        price_features[:, i] = (df["price_band"] == price_band).astype(int)
    
    # Numeric features
    numeric_features = df[["estimated_cost", "duration_minutes", "opening_align", "distance_km"]].values
    
    # Combine all features
    features = np.hstack([tag_features, price_features, numeric_features])
    
    return features

def train_model():
    """Train the preference scoring model."""
    print("Training preference scoring model...")
    
    # Load or generate data
    data_path = "data/pref_training.csv"
    if os.path.exists(data_path):
        print(f"Loading training data from {data_path}")
        df = pd.read_csv(data_path)
    else:
        print("No training data found, generating synthetic data...")
        df = generate_synthetic_data()
        df.to_csv(data_path, index=False)
        print(f"Generated synthetic data saved to {data_path}")
    
    print(f"Training data shape: {df.shape}")
    print(f"Label distribution: {df['label'].value_counts().to_dict()}")
    
    # Define tag vocabulary
    tag_vocab = [
        "culture", "nature", "food", "history", "art", "music", "sports", "shopping",
        "adventure", "relaxation", "family", "romantic", "budget", "luxury", "local",
        "tourist", "quiet", "crowded", "indoor", "outdoor", "religious", "secular",
        "modern", "traditional", "urban", "rural", "beach", "mountain", "city", "village"
    ]
    
    # Build features
    X = build_features(df, tag_vocab, None)
    y = df["label"].values
    
    # Define feature names
    price_bands = ["free", "low", "medium", "high"]
    numeric_features = ["estimated_cost", "duration_minutes", "opening_align", "distance_km"]
    feature_names = tag_vocab + [f"price_{band}" for band in price_bands] + numeric_features
    
    # Train model
    model = Pipeline([
        ("scaler", StandardScaler()),
        ("classifier", LogisticRegression(random_state=42, max_iter=1000))
    ])
    
    model.fit(X, y)
    
    # Evaluate
    y_pred = model.predict(X)
    y_pred_proba = model.predict_proba(X)[:, 1]
    
    accuracy = accuracy_score(y, y_pred)
    auc = roc_auc_score(y, y_pred_proba)
    
    print(f"Training accuracy: {accuracy:.3f}")
    print(f"Training AUC: {auc:.3f}")
    
    # Save model
    model_path = "app/models/pref_lr_v1.joblib"
    joblib.dump(model, model_path)
    print(f"Model saved to {model_path}")
    
    # Save metadata
    metadata = {
        "version": "pref_lr_v1",
        "created_at": datetime.now().isoformat(),
        "feature_names": feature_names,
        "tag_vocab": tag_vocab,
        "metrics": {
            "accuracy": accuracy,
            "auc": auc,
            "n_samples": len(df),
            "n_features": len(feature_names)
        },
        "model_type": "LogisticRegression",
        "preprocessing": ["StandardScaler"]
    }
    
    metadata_path = "app/models/pref_lr_v1.metadata.json"
    with open(metadata_path, "w") as f:
        json.dump(metadata, f, indent=2)
    print(f"Metadata saved to {metadata_path}")
    
    return model, metadata

if __name__ == "__main__":
    train_model()
