import pytest
import numpy as np
from unittest.mock import MagicMock, patch
from app.model import (
    _serialize, _join_words, _merge_bio_tags, _build_profile, PhoBERTModel
)

# ─────────────────────────────────────────────────────────── #
# UNIT TESTS CHO HELPER FUNCTIONS
# ─────────────────────────────────────────────────────────── #

def test_serialize():
    """Kiểm tra việc convert numpy types sang python native."""
    data = {
        "float": np.float32(0.99),
        "int": np.int64(10),
        "array": np.array([1, 2, 3]),
        "list": [np.float64(1.2), {"nested": np.int32(5)}]
    }
    result = _serialize(data)
    assert isinstance(result["float"], float)
    assert isinstance(result["int"], int)
    assert isinstance(result["array"], list)
    assert isinstance(result["list"][0], float)
    assert isinstance(result["list"][1]["nested"], int)

def test_join_words():
    """Kiểm tra xử lý token @@ của PhoBERT."""
    assert _join_words(["Nguyễn", "Văn", "A@@"]) == "Nguyễn Văn A"
    assert _join_words(["sốt", "cao@@", "."]) == "sốt cao"
    assert _join_words([]) == ""

def test_merge_bio_tags():
    """Kiểm tra logic gộp thực thể BIO."""
    entities = [
        {"entity": "B-NAME", "word": "Nguyễn"},
        {"entity": "I-NAME", "word": "Văn"},
        {"entity": "I-NAME", "word": "A@@"},
        {"entity": "O", "word": "bị"},
        {"entity": "B-SYMPTOM_AND_DISEASE", "word": "sốt"},
    ]
    merged = _merge_bio_tags(entities)
    assert len(merged) == 2
    assert merged[0] == {"label": "NAME", "value": "Nguyễn Văn A"}
    assert merged[1] == {"label": "SYMPTOM_AND_DISEASE", "value": "sốt"}

def test_build_profile():
    """Kiểm tra việc mapping thực thể vào Medical Profile."""
    merged = [
        {"label": "NAME", "value": "An Cao"},
        {"label": "AGE", "value": "20"},
        {"label": "LOCATION", "value": "Hà Nội"},
        {"label": "LOCATION", "value": "Việt Nam"},
        {"label": "SYMPTOM_AND_DISEASE", "value": "Sốt"},
    ]
    profile = _build_profile(merged)
    assert profile["Name"] == "An Cao"
    assert profile["Age"] == "20"
    assert profile["Location"] == "Hà Nội, Việt Nam"
    assert profile["Symptoms_Diseases"] == "Sốt"
    assert profile["Gender"] == "N/A" # Trường không có dữ liệu

# ─────────────────────────────────────────────────────────── #
# INTEGRATION TESTS CHO PHOBERTMODEL
# ─────────────────────────────────────────────────────────── #

@pytest.fixture
def mock_model():
    """Fixture tạo PhoBERTModel với pipeline được mock."""
    with patch('mlflow.transformers.load_model') as mock_load, \
         patch('mlflow.MlflowClient') as mock_client:
        
        # Giả lập model name và version
        mock_client.return_value.get_registered_model.return_value.latest_versions = [
            MagicMock(version="1")
        ]
        
        model = PhoBERTModel("phobert-medical")
        model.pipeline = MagicMock()
        model.ready = True
        return model

def test_predict_success(mock_model):
    """Test trường hợp dự đoán thành công với format 'instances'."""
    request = {"instances": ["Bệnh nhân An bị sốt."]}
    
    # Mock kết quả trả về từ pipeline NER
    mock_model.pipeline.return_value = [[
        {"entity": "B-NAME", "word": "An", "score": np.float32(0.9)},
        {"entity": "O", "word": "bị"},
        {"entity": "B-SYMPTOM_AND_DISEASE", "word": "sốt", "score": np.float32(0.8)},
    ]]

    response = mock_model.predict(request)
    
    assert "profiles" in response
    assert len(response["profiles"]) == 1
    assert response["profiles"][0]["Name"] == "An"
    assert response["profiles"][0]["Symptoms_Diseases"] == "sốt"

def test_predict_text_format(mock_model):
    """Test trường hợp sử dụng key 'text' thay vì 'instances'."""
    request = {"text": "Sốt cao tại Hà Nội"}
    mock_model.pipeline.return_value = [[
        {"entity": "B-LOCATION", "word": "Hà Nội", "score": np.float32(0.9)}
    ]]
    
    response = mock_model.predict(request)
    assert len(response["profiles"]) == 1
    assert "Hà Nội" in response["profiles"][0]["Location"]

def test_predict_empty_input(mock_model):
    """Test trường hợp input rỗng."""
    assert mock_model.predict({}) == {"profiles": []}
    assert mock_model.predict({"instances": []}) == {"profiles": []}

@patch('mlflow.transformers.load_model')
@patch('mlflow.MlflowClient')
@patch('os.getenv')
def test_load_logic(mock_getenv, mock_client, mock_load):
    """Test logic load model và cấu hình environment."""
    mock_getenv.side_effect = lambda k, default=None: {
        "MLFLOW_TRACKING_URI": "http://test:5000",
        "MODEL_NAME": "test-model",
        "MODEL_VERSION": "latest"
    }.get(k, default)
    
    # Giả lập tìm version mới nhất
    mock_version = MagicMock()
    mock_version.version = "5"
    mock_client.return_value.get_registered_model.return_value.latest_versions = [mock_version]
    
    model = PhoBERTModel("test")
    model.load()
    
    assert model.ready is True
    mock_load.assert_called_with("models:/test-model/5", return_type="pipeline")