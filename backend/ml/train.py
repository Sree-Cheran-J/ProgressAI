"""Generate clearly labelled synthetic data and train a demo pipeline. Not production training data."""
from pathlib import Path
import argparse, joblib, numpy as np
from sklearn.ensemble import RandomForestRegressor, RandomForestClassifier
from sklearn.linear_model import LinearRegression
from sklearn.tree import DecisionTreeClassifier
from sklearn.cluster import KMeans
from sklearn.neighbors import KNeighborsClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_absolute_error, accuracy_score, f1_score
from app.ml_service import FEATURES

def main():
    parser=argparse.ArgumentParser(); parser.add_argument("--rows",type=int,default=1200); parser.add_argument("--output",default="ml/artifacts/models.joblib"); args=parser.parse_args()
    rng=np.random.default_rng(42); n=max(args.rows,100)
    complexity=rng.integers(1,6,n); priority=rng.integers(1,5,n); estimated=rng.uniform(.5,24,n); active=rng.integers(0,9,n); avg=rng.uniform(.5,20,n); ontime=rng.uniform(.2,1,n)
    X=np.column_stack([complexity,priority,estimated,active,avg,ontime])
    y=np.maximum(.25,estimated*(.55+.13*complexity+.045*active+.08*(priority-1))*.55+avg*.22+rng.normal(0,.6,n))
    # Label deadline risk from simulated deadline slack; labels are synthetic and not validated for real work.
    slack=rng.uniform(0,30,n); risk=((y>slack)|(ontime<.4)).astype(int)
    Xtr,Xte,ytr,yte=train_test_split(X,y,test_size=.2,random_state=42)
    duration=RandomForestRegressor(n_estimators=160,min_samples_leaf=3,random_state=42,n_jobs=-1).fit(Xtr,ytr)
    rf=RandomForestClassifier(n_estimators=120,min_samples_leaf=3,random_state=42).fit(X,risk)
    tree=DecisionTreeClassifier(max_depth=5,random_state=42).fit(X,risk)
    cluster=KMeans(n_clusters=3,n_init=10,random_state=42).fit(X[:,[0,2,3,4,5]])
    rec_labels=np.where((active>=5)|(ontime<.45),2,np.where((complexity>=4)|(priority>=3),1,0))
    knn=KNeighborsClassifier(n_neighbors=7).fit(X,rec_labels)
    linear=LinearRegression().fit(Xtr,ytr)
    out=Path(args.output); out.parent.mkdir(parents=True,exist_ok=True)
    bundle={"models":{"duration_rf":duration,"duration_linear":linear,"risk_rf":rf,"risk_tree":tree,"behaviour_kmeans":cluster,"knn_recommendation":knn},"metadata":{"trained_at_utc":__import__('datetime').datetime.now(__import__('datetime').timezone.utc).isoformat(),"rows":n,"dataset":"SYNTHETIC_DEMONSTRATION_ONLY","duration_test_mae_synthetic":round(float(mean_absolute_error(yte,duration.predict(Xte))),3),"duration_linear_test_mae_synthetic":round(float(mean_absolute_error(yte,linear.predict(Xte))),3),"risk_training_f1_synthetic":round(float(f1_score(risk,rf.predict(X))),3),"warning":"Metrics are computed on synthetic data and do not represent real employee performance."}}
    joblib.dump(bundle,out); print(f"Saved demo models: {out}\nMetadata: {bundle['metadata']}")
if __name__=="__main__": main()
