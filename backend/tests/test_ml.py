from datetime import datetime, timezone, timedelta
from app.ml_service import MLService, features

def test_baseline_prediction_is_labelled():
    service=MLService(); service.models={}
    result=service.predict(features(3,"Medium",2,1),datetime.now(timezone.utc)+timedelta(hours=8))
    assert result["predicted_duration_hours"]>0
    assert result["source"].startswith("Transparent baseline")
    assert result["uncertainty_hours"] is None

def test_risk_has_expected_values():
    service=MLService(); service.models={}
    result=service.predict(features(5,"Urgent",10,8),datetime.now(timezone.utc)+timedelta(hours=1))
    assert result["risk_level"] in {"Low","Moderate","High"}
