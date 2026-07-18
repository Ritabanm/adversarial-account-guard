# 🛡️ Adversarial Account Guard (Risk ML Console)

An enterprise-grade, white-labeled Marketplace Trust & Safety Console built to detect, analyze, and enforce on adversarial bad actors (fake accounts, rating manipulation rings, and seller boosting rings).

This project showcases a complete **Risk Machine Learning pipeline**, including **Supervised learning (Random Forests & GBDTs)**, **Unsupervised anomaly detection (Isolation Forests)**, a **Human-in-the-loop audit overrides database**, and a **dynamic operational threshold simulator**.

---

## 🚀 Key Features

*   **⚡ Multi-Model Scoring Engine**:
    *   **Random Forest**: A robust supervised class-balanced ensemble model.
    *   **HistGBDT (Gradient Boosting)**: High-speed GBDT (scikit-learn's optimized GBDT, comparable to LightGBM/XGBoost) for state-of-the-art tabular classification.
    *   **Isolation Forest (Unsupervised Anomaly Detector)**: Captures emerging and novel fraud patterns without requiring labels, achieving a **98.2% test AUC** out-of-the-box.
*   **📈 Competing Objectives & Decision Threshold Simulator**:
    *   Interactive UI slider to set the risk cutoff.
    *   Live operational metrics tracking **Scammer Catch Rate (Recall)** vs. **Customer Friction Rate (False Positive Rate)**.
    *   Real-time **Operational ROC Curve** plot with a highlighted red operational point showing the exact operational trade-off.
*   **🔍 Interactive Manual Audit Console**:
    *   Search and audit individual accounts.
    *   Examine hardware device footprints, shared IP networks, and signup timestamps.
    *   View risk contribution comparison explainers matching user metrics to Genuine vs. Bot cohort medians.
*   **💾 Persistent Actions Database**:
    *   Supports manual override decisions (`🚫 Suspend`, `🛡️ Approve / Safe`, `⏳ Escalate`).
    *   Actions are saved to a local persistent JSON file (`audit_actions.json`) so overrides survive page refreshes and server reboots.
*   **📁 Batch Processing Pipeline**:
    *   Drag-and-drop CSV uploader to score batch accounts and review logs in real-time, displaying anomalies and providing clean CSV reports.

---

## 🛠️ Tech Stack

*   **Core Logic**: Python 3.10+
*   **Machine Learning**: `scikit-learn` (Random Forest, HistGradientBoostingClassifier, IsolationForest)
*   **Data Wrangling**: `pandas`, `numpy`
*   **Visualizations**: `plotly` (interactive scatter plots, histograms, and gauge charts)
*   **Frontend Interface**: `streamlit`

---

## 📁 Project Structure

```
├── app.py                # Main Streamlit dashboard (tabs, metrics, visuals, actions)
├── classifier.py         # Feature engineering & ML training/evaluation pipelines
├── data_generator.py     # Collusion simulation engine (generates user/review logs)
├── requirements.txt      # Python dependencies
├── .gitignore            # Git exclusion guidelines
└── audit_actions.json    # Local persistent manual audit database
```

---

## 🧪 Simulation & Feature Engineering

The simulator (`data_generator.py`) generates two distinct populations of accounts to train the models:
1.  **Genuine Users**: Organic signup patterns, low review density, varied ratings, unique hardware devices, and typical review delay times.
2.  **Adversarial Bot Rings**: Collusive buyer accounts created in campaign bursts to review a single target seller. They feature:
    *   **Shared Devices**: Multiple fake accounts mapped to the same device ID.
    *   **Network Clusters**: Shared subnets (`/24` network blocks).
    *   **Time Velocity**: Near-zero delay between registration time and review creation (under a few hours).
    *   **Text Duplicity**: Using identical/repetitive templates for review text.
    *   **Rating Skew**: Heavy density of 5-star (positive boosting) or 1-star (negative attack) reviews.

`classifier.py` aggregates these behaviors into engineered features for the models:
*   `ip_shared_count` & `subnet_shared_count`
*   `device_shared_count`
*   `extreme_rating_ratio` & `seller_entropy`
*   `min_delay_hours` & `avg_delay_hours`
*   `avg_text_freq` (global text duplicity across the database)

---

## 🏁 Quick Start

### 1. Clone the repository and navigate inside
```bash
git clone https://github.com/Ritabanm/adversarial-account-guard.git
cd adversarial-account-guard
```

### 2. Install dependencies
```bash
pip install -r requirements.txt
```

### 3. Run the ML pipeline test
Verify the classifier executes, trains, and displays validation results:
```bash
python classifier.py
```

### 4. Launch the dashboard console
```bash
streamlit run app.py
```
Open **`http://localhost:8501`** in your browser to access the dashboard!