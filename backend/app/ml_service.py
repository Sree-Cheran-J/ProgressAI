from pathlib import Path
from datetime import datetime, timezone, timedelta
import joblib
import numpy as np
from sklearn.linear_model import LinearRegression
from sklearn.ensemble import RandomForestRegressor, RandomForestClassifier
from sklearn.tree import DecisionTreeClassifier
from sklearn.cluster import KMeans
from sklearn.neighbors import KNeighborsClassifier
from app.config import settings

FEATURES=["complexity","priority_score","estimated_duration_hours","active_tasks","historical_avg_hours","on_time_rate"]
PRIORITY={"Low":1,"Medium":2,"High":3,"Urgent":4}
def features(complexity,priority,estimated_duration_hours,active_tasks,historical_avg_hours=None,on_time_rate=None):
    return np.array([[complexity,PRIORITY.get(priority,2),estimated_duration_hours,active_tasks,historical_avg_hours or estimated_duration_hours,on_time_rate if on_time_rate is not None else 0.7]],dtype=float)
class MLService:
    def __init__(self): self.models={}; self.metadata={}; self.load()
    def load(self):
        p=Path(settings.model_dir)/"models.joblib"
        if p.exists():
            try:
                bundle=joblib.load(p); self.models=bundle.get("models",{}); self.metadata=bundle.get("metadata",{})
            except Exception: self.models={}; self.metadata={"load_error":"Model artifact could not be loaded"}
    def predict(self, x, deadline=None):
        source="Trained ML (synthetic demonstration data)" if "duration_rf" in self.models else "Transparent baseline (insufficient trained model)"
        model=self.models.get("duration_rf")
        duration=float(model.predict(x)[0]) if model else float(max(0.5,x[0,2]*(0.65+0.12*x[0,0]+0.035*x[0,3])))
        duration=max(0.25,min(duration,10000))
        linear_model=self.models.get("duration_linear")
        linear_duration=max(0.25,min(float(linear_model.predict(x)[0]),10000)) if linear_model else None
        hours_left=None
        if deadline:
            dt=deadline if deadline.tzinfo else deadline.replace(tzinfo=timezone.utc)
            hours_left=(dt-datetime.now(timezone.utc)).total_seconds()/3600
        classifier=self.models.get("risk_rf")
        if classifier and len(getattr(classifier,"classes_",[]))>1:
            probs=classifier.predict_proba(x)[0]; classes=list(classifier.classes_); risk_prob=float(probs[classes.index(1)]) if 1 in classes else 0.0
            risk_source="trained classifier"
        else:
            risk_prob=0.25
            if hours_left is not None: risk_prob=float(np.clip(0.15+(duration-hours_left)/max(duration,1)*0.7,0.05,0.95))
            risk_source="baseline heuristic; not a trained risk model"
        risk="High" if risk_prob>=0.67 else "Moderate" if risk_prob>=0.34 else "Low"
        tree=self.models.get("risk_tree")
        tree_risk=int(tree.predict(x)[0]) if tree is not None else None
        cluster=self.models.get("behaviour_kmeans")
        cluster_id=int(cluster.predict(x[:,[0,2,3,4,5]])[0]) if cluster is not None else None
        finish=datetime.now(timezone.utc)+timedelta(hours=duration)
        if deadline and hours_left is not None and duration>hours_left: risk="High"
        return {"predicted_duration_hours":round(duration,2),"predicted_finish_at":finish.isoformat(),"deadline_risk_probability":round(risk_prob,3),"risk_level":risk,"source":source,"risk_source":risk_source,"linear_regression_comparison_hours":round(linear_duration,2) if linear_duration is not None else None,"decision_tree_risk_class":("High" if tree_risk==1 else "Low") if tree_risk is not None else None,"behaviour_cluster":f"Cluster {cluster_id} (unsupervised; interpretation needs validation)" if cluster_id is not None else None,"uncertainty_hours":None,"uncertainty_note":"Not calculated; no calibrated uncertainty interval is available.","suggested_action":"Review scope and split the task if risk is High." if risk=="High" else "Check progress at the next planned milestone."}
    def recommend(self, x):
        model=self.models.get("knn_recommendation")
        if not model: return {"recommendation":"Break the task into smaller milestones and record actual effort.","source":"rule-based fallback"}
        label=int(model.predict(x)[0]); choices={0:"Schedule a focused work block.",1:"Reduce active workload or split this task.",2:"Review scope and request help early."}
        return {"recommendation":choices.get(label,choices[0]),"source":"KNN model trained on synthetic demonstration data"}
ml_service=MLService()
