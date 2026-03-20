import os
import json
import logging
import argparse
from typing import Dict, List

import mlflow
import numpy as np
import kserve
from kserve import Model, ModelServer
from dotenv import load_dotenv

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────── #
# Helper Functions (Logic từ Transformer cũ)
# ─────────────────────────────────────────────────────────── #

def _serialize(obj):
    """Đệ quy convert numpy types → Python native để JSON serialize được."""
    if isinstance(obj, (np.floating, np.float32, np.float64)):
        return float(obj)
    if isinstance(obj, (np.integer, np.int32, np.int64)):
        return int(obj)
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    if isinstance(obj, list):
        return [_serialize(i) for i in obj]
    if isinstance(obj, dict):
        return {k: _serialize(v) for k, v in obj.items()}
    return obj

def _join_words(words: List[str]) -> str:
    if not words: return ""
    text = ""
    for i, word in enumerate(words):
        if word.endswith("@@"): text += word[:-2]
        else:
            text += word
            if i < len(words) - 1: text += " "
    return text.strip().rstrip(".,;")

def _merge_bio_tags(entities: List[Dict]) -> List[Dict]:
    if not entities: return []
    merged: List[Dict] = []
    current_label = None
    current_words: List[str] = []

    def _flush():
        nonlocal current_label, current_words
        if current_label:
            merged.append({"label": current_label, "value": _join_words(current_words)})
        current_label = None
        current_words = []

    for ent in entities:
        tag = ent.get("entity", "O")
        word = ent.get("word", "")
        prefix, label = tag.split("-", 1) if "-" in tag else (tag, "")

        if prefix == "B":
            _flush()
            current_label = label
            current_words = [word]
        elif prefix == "I" and current_label == label:
            current_words.append(word)
        elif prefix == "I":
            _flush()
            current_label = label
            current_words = [word]
        else: _flush()
    _flush()
    return merged

def _build_profile(merged_entities: List[Dict]) -> Dict:
    profile = {
        "Patient_ID": "N/A", "Name": "Chưa rõ", "Age": "N/A", "Gender": "N/A",
        "Job": "N/A", "Location": [], "Organization": [], "Date": [],
        "Symptoms_Diseases": [], "Transportation": [],
    }
    _label_map = {
        "NAME": ("Name", False), "AGE": ("Age", False), "GENDER": ("Gender", False),
        "PATIENT_ID": ("Patient_ID", False), "JOB": ("Job", False),
        "LOCATION": ("Location", True), "ORGANIZATION": ("Organization", True),
        "DATE": ("Date", True), "SYMPTOM_AND_DISEASE": ("Symptoms_Diseases", True),
        "TRANSPORTATION": ("Transportation", True),
    }
    for ent in merged_entities:
        lbl = ent["label"].upper()
        if lbl in _label_map:
            field, is_list = _label_map[lbl]
            if is_list: profile[field].append(ent["value"])
            else: profile[field] = ent["value"]

    for field in ("Location", "Organization", "Date", "Symptoms_Diseases", "Transportation"):
        profile[field] = ", ".join(profile[field]) if profile[field] else ("N/A" if field in ["Location", "Symptoms_Diseases"] else "")
    return profile

# ─────────────────────────────────────────────────────────── #
# PhoBERT Model (Gộp Predictor + Transformer)
# ─────────────────────────────────────────────────────────── #

class PhoBERTModel(Model):
    def __init__(self, name: str):
        super().__init__(name)
        self.name = name
        self.ready = False
        self.pipeline = None

    def load(self):
        logger.info("Loading PhoBERT model and internalizing transformer logic...")
        # Setup MLflow Env
        for key in ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "MLFLOW_S3_ENDPOINT_URL"):
            if os.getenv(key): os.environ[key] = os.getenv(key)
        os.environ["MLFLOW_S3_IGNORE_TLS"] = "true"
        
        mlflow.set_tracking_uri(os.getenv("MLFLOW_TRACKING_URI", "http://localhost:5000"))
        
        model_name = os.getenv("MODEL_NAME", "phobert-medical")
        model_version = os.getenv("MODEL_VERSION", "latest")
        
        # Resolve URI
        if model_version == "latest":
            client = mlflow.MlflowClient()
            versions = client.get_registered_model(model_name).latest_versions
            model_uri = f"models:/{model_name}/{max(versions, key=lambda v: int(v.version)).version}"
        else:
            model_uri = f"models:/{model_name}/{model_version}"

        self.pipeline = mlflow.transformers.load_model(model_uri, return_type="pipeline")
        self.ready = True
        logger.info(f"✅ Model loaded from {model_uri}")

    def predict(self, request: Dict, headers: Dict[str, str] = None) -> Dict:
        # 1. Preprocess nội bộ
        instances = request.get("instances", [])
        if not instances and "text" in request:
            text = request.get("text")
            instances = [text] if isinstance(text, str) else text
            
        if not instances: return {"profiles": []}

        # 2. Inference
        logger.info(f"Running inference on {len(instances)} text(s)...")
        raw_results = self.pipeline(instances)
        
        # Chuẩn hóa raw: list[dict] -> list[list[dict]]
        if isinstance(raw_results, list) and raw_results and isinstance(raw_results[0], dict):
            raw_results = [raw_results]

        # 3. Postprocess nội bộ (Merge BIO & Build Profile)
        final_profiles = []
        for sentence_entities in raw_results:
            # Làm sạch dữ liệu số trước khi xử lý logic
            cleaned_entities = _serialize(sentence_entities)
            
            merged = _merge_bio_tags(cleaned_entities)
            profile = _build_profile(merged)
            final_profiles.append(profile)

        logger.info(f"✅ Successfully generated {len(final_profiles)} medical profiles")
        return {"profiles": final_profiles}

if __name__ == "__main__":
    parser = argparse.ArgumentParser(parents=[kserve.model_server.parser])
    args, _ = parser.parse_known_args()

    model = PhoBERTModel("phobert-medical")
    model.load()
    ModelServer().start([model])