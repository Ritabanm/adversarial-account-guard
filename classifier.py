import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestClassifier, HistGradientBoostingClassifier, IsolationForest
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, roc_auc_score, precision_recall_curve
import pickle
import os

class FeatureEngineer:
    def __init__(self):
        self.text_counts = {}
        self.is_fitted = False

    def fit(self, df_accounts, df_reviews):
        """Fits any global state from the training data (e.g. review text frequencies)."""
        if len(df_reviews) > 0:
            self.text_counts = df_reviews['review_text'].value_counts().to_dict()
        else:
            self.text_counts = {}
        self.is_fitted = True
        return self

    def transform(self, df_accounts, df_reviews):
        """Transforms accounts and reviews dataframes into a feature matrix per account."""
        df_acc = df_accounts.copy()
        df_rev = df_reviews.copy()

        # --- 1. Account Metadata Features ---
        # Share count for exact IP
        df_acc['ip_shared_count'] = df_acc.groupby('signup_ip')['account_id'].transform('count') - 1
        
        # Share count for Subnet (/24 subnet, i.e., first 3 octets)
        df_acc['subnet'] = df_acc['signup_ip'].apply(lambda x: '.'.join(str(x).split('.')[:3]) if pd.notnull(x) else '')
        df_acc['subnet_shared_count'] = df_acc.groupby('subnet')['account_id'].transform('count') - 1
        df_acc.drop(columns=['subnet'], inplace=True)

        # Share count for Device ID
        df_acc['device_shared_count'] = df_acc.groupby('device_id')['account_id'].transform('count') - 1

        # --- 2. Review Behavior Features ---
        if len(df_rev) > 0:
            # Map global text frequency (using text frequency in fit or current dataset)
            # Default to 1 if text is new/unseen
            df_rev['text_frequency'] = df_rev['review_text'].apply(
                lambda x: self.text_counts.get(x, df_rev['review_text'].value_counts().get(x, 1))
            )
            
            # Join account signup time to calculate review velocity (delay in hours)
            df_rev_joined = df_rev.merge(df_acc[['account_id', 'signup_time']], on='account_id', how='left')
            
            # Make sure times are datetime
            df_rev_joined['review_time'] = pd.to_datetime(df_rev_joined['review_time'])
            df_rev_joined['signup_time'] = pd.to_datetime(df_rev_joined['signup_time'])
            
            df_rev_joined['delay_hours'] = (df_rev_joined['review_time'] - df_rev_joined['signup_time']).dt.total_seconds() / 3600.0

            # Group reviews by account
            review_aggs = []
            for acct_id, group in df_rev_joined.groupby('account_id'):
                rev_count = len(group)
                avg_rating = group['rating'].mean()
                rating_std = group['rating'].std() if rev_count > 1 else 0.0
                
                # Extreme rating ratio (1-star or 5-star reviews)
                extreme_count = group['rating'].isin([1, 5]).sum()
                extreme_ratio = extreme_count / rev_count
                
                # Review delay statistics
                min_delay = group['delay_hours'].min()
                avg_delay = group['delay_hours'].mean()
                
                # Seller Concentration Entropy
                # How spread out are reviews across sellers?
                seller_counts = group['seller_id'].value_counts()
                seller_probs = seller_counts / len(group)
                seller_entropy = -np.sum(seller_probs * np.log2(seller_probs + 1e-9))
                
                # Average global text frequency of reviews written by this user
                avg_text_freq = group['text_frequency'].mean()
                
                review_aggs.append({
                    'account_id': acct_id,
                    'review_count': rev_count,
                    'avg_rating': avg_rating,
                    'rating_std': rating_std,
                    'extreme_rating_ratio': extreme_ratio,
                    'min_delay_hours': min_delay,
                    'avg_delay_hours': avg_delay,
                    'seller_entropy': seller_entropy,
                    'avg_text_freq': avg_text_freq
                })
                
            df_rev_features = pd.DataFrame(review_aggs)
        else:
            df_rev_features = pd.DataFrame(columns=[
                'account_id', 'review_count', 'avg_rating', 'rating_std', 
                'extreme_rating_ratio', 'min_delay_hours', 'avg_delay_hours', 
                'seller_entropy', 'avg_text_freq'
            ])

        # --- 3. Merge Account Features with Review Features ---
        df_features = df_acc.merge(df_rev_features, on='account_id', how='left')
        
        # Fill missing values for users with no reviews
        df_features['review_count'] = df_features['review_count'].fillna(0)
        df_features['avg_rating'] = df_features['avg_rating'].fillna(3.0)  # Neutral rating
        df_features['rating_std'] = df_features['rating_std'].fillna(0.0)
        df_features['extreme_rating_ratio'] = df_features['extreme_rating_ratio'].fillna(0.0)
        
        # If no reviews, set delay to a large number of hours (e.g. 9999) to indicate no quick reviews
        df_features['min_delay_hours'] = df_features['min_delay_hours'].fillna(9999.0)
        df_features['avg_delay_hours'] = df_features['avg_delay_hours'].fillna(9999.0)
        
        # If no reviews, entropy is 0 (neutral/no diversity)
        df_features['seller_entropy'] = df_features['seller_entropy'].fillna(0.0)
        
        # If no reviews, average text frequency is 1.0 (defaults to unique)
        df_features['avg_text_freq'] = df_features['avg_text_freq'].fillna(1.0)
        
        return df_features


class FakeAccountClassifier:
    def __init__(self):
        self.rf_model = RandomForestClassifier(n_estimators=100, random_state=42, class_weight='balanced')
        self.gbdt_model = HistGradientBoostingClassifier(random_state=42, class_weight='balanced')
        self.unsup_model = IsolationForest(random_state=42, contamination=0.1)
        self.feature_cols = [
            'ip_shared_count', 'subnet_shared_count', 'device_shared_count',
            'review_count', 'avg_rating', 'rating_std', 'extreme_rating_ratio',
            'min_delay_hours', 'avg_delay_hours', 'seller_entropy', 'avg_text_freq'
        ]
        self.engineer = FeatureEngineer()

    def train(self, df_accounts, df_reviews):
        """Fits the feature engineer and trains all models (RF, GBDT, Unsupervised Isolation Forest)."""
        # Fit & Transform features
        self.engineer.fit(df_accounts, df_reviews)
        df_features = self.engineer.transform(df_accounts, df_reviews)
        
        X = df_features[self.feature_cols]
        y = df_features['is_fake']
        
        # Train supervised models
        self.rf_model.fit(X, y)
        self.gbdt_model.fit(X, y)
        
        # Train unsupervised model
        self.unsup_model.fit(X)
        
        # Calculate training metrics for RF as a reference
        y_pred_prob = self.rf_model.predict_proba(X)[:, 1]
        roc_auc = roc_auc_score(y, y_pred_prob)
        
        return df_features, roc_auc

    def evaluate(self, df_accounts, df_reviews):
        """Evaluates RF, GBDT, and Unsupervised Isolation Forest, returning compared metrics."""
        df_features = self.engineer.transform(df_accounts, df_reviews)
        
        X = df_features[self.feature_cols]
        y = df_features['is_fake']
        
        # 1. Random Forest Evaluation
        rf_pred = self.rf_model.predict(X)
        rf_prob = self.rf_model.predict_proba(X)[:, 1]
        rf_report = classification_report(y, rf_pred, output_dict=True)
        rf_auc = roc_auc_score(y, rf_prob)
        
        # 2. GBDT Evaluation
        gbdt_pred = self.gbdt_model.predict(X)
        gbdt_prob = self.gbdt_model.predict_proba(X)[:, 1]
        gbdt_report = classification_report(y, gbdt_pred, output_dict=True)
        gbdt_auc = roc_auc_score(y, gbdt_prob)
        
        # 3. Isolation Forest Evaluation (Unsupervised)
        unsup_pred_raw = self.unsup_model.predict(X)  # -1 for anomaly, 1 for normal
        unsup_pred = np.where(unsup_pred_raw == -1, 1, 0)
        unsup_score = -self.unsup_model.decision_function(X)
        unsup_report = classification_report(y, unsup_pred, output_dict=True)
        try:
            unsup_auc = roc_auc_score(y, unsup_score)
        except:
            unsup_auc = 0.5
            
        return {
            'rf': {
                'accuracy': rf_report['accuracy'],
                'precision_fake': rf_report['1.0']['precision'] if '1.0' in rf_report else rf_report['1']['precision'] if '1' in rf_report else 0.0,
                'recall_fake': rf_report['1.0']['recall'] if '1.0' in rf_report else rf_report['1']['recall'] if '1' in rf_report else 0.0,
                'f1_fake': rf_report['1.0']['f1-score'] if '1.0' in rf_report else rf_report['1']['f1-score'] if '1' in rf_report else 0.0,
                'roc_auc': rf_auc,
                'report': rf_report
            },
            'gbdt': {
                'accuracy': gbdt_report['accuracy'],
                'precision_fake': gbdt_report['1.0']['precision'] if '1.0' in gbdt_report else gbdt_report['1']['precision'] if '1' in gbdt_report else 0.0,
                'recall_fake': gbdt_report['1.0']['recall'] if '1.0' in gbdt_report else gbdt_report['1']['recall'] if '1' in gbdt_report else 0.0,
                'f1_fake': gbdt_report['1.0']['f1-score'] if '1.0' in gbdt_report else gbdt_report['1']['f1-score'] if '1' in gbdt_report else 0.0,
                'roc_auc': gbdt_auc,
                'report': gbdt_report
            },
            'unsup': {
                'accuracy': unsup_report['accuracy'],
                'precision_fake': unsup_report['1.0']['precision'] if '1.0' in unsup_report else unsup_report['1']['precision'] if '1' in unsup_report else 0.0,
                'recall_fake': unsup_report['1.0']['recall'] if '1.0' in unsup_report else unsup_report['1']['recall'] if '1' in unsup_report else 0.0,
                'f1_fake': unsup_report['1.0']['f1-score'] if '1.0' in unsup_report else unsup_report['1']['f1-score'] if '1' in unsup_report else 0.0,
                'roc_auc': unsup_auc,
                'report': unsup_report
            }
        }

    def predict_risk(self, df_accounts, df_reviews, model_type='rf'):
        """Predicts the risk probability of each account being fake using specified model."""
        df_features = self.engineer.transform(df_accounts, df_reviews)
        X = df_features[self.feature_cols]
        
        if model_type == 'rf':
            probs = self.rf_model.predict_proba(X)[:, 1]
        elif model_type == 'gbdt':
            probs = self.gbdt_model.predict_proba(X)[:, 1]
        elif model_type == 'unsup':
            # Map Isolation Forest score to [0, 1] range using sigmoid
            raw_anomaly = -self.unsup_model.decision_function(X)
            probs = 1 / (1 + np.exp(-12 * raw_anomaly))
        else:
            raise ValueError(f"Unknown model_type: {model_type}")
            
        df_features['risk_score'] = probs
        return df_features

    def get_feature_importances(self):
        """Returns feature importance mapping for the RF model."""
        importances = self.rf_model.feature_importances_
        return pd.DataFrame({
            'feature': self.feature_cols,
            'importance': importances
        }).sort_values(by='importance', ascending=False)

    def save(self, filepath):
        """Saves the classifier models and their feature engineer."""
        with open(filepath, 'wb') as f:
            pickle.dump({
                'rf_model': self.rf_model,
                'gbdt_model': self.gbdt_model,
                'unsup_model': self.unsup_model,
                'feature_cols': self.feature_cols,
                'engineer': self.engineer
            }, f)

    @classmethod
    def load(cls, filepath):
        """Loads saved classifier models."""
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"No classifier model found at {filepath}")
        with open(filepath, 'rb') as f:
            data = pickle.load(f)
        
        classifier = cls()
        classifier.rf_model = data.get('rf_model', data.get('model'))
        classifier.gbdt_model = data.get('gbdt_model')
        classifier.unsup_model = data.get('unsup_model')
        classifier.feature_cols = data['feature_cols']
        classifier.engineer = data['engineer']
        return classifier


if __name__ == "__main__":
    from data_generator import EcommerceDataGenerator
    print("Testing classifier pipeline...")
    
    # Generate data
    gen = EcommerceDataGenerator()
    df_acc, df_rev = gen.generate_data(num_genuine=300, num_fake=30)
    
    # Split accounts for train/test
    train_acc, test_acc = train_test_split(df_acc, test_size=0.3, random_state=42, stratify=df_acc['is_fake'])
    
    # Filter reviews accordingly
    train_rev = df_rev[df_rev['account_id'].isin(train_acc['account_id'])]
    test_rev = df_rev[df_rev['account_id'].isin(test_acc['account_id'])]
    
    # Initialize and train classifier
    clf = FakeAccountClassifier()
    df_feat, train_auc = clf.train(train_acc, train_rev)
    print(f"Models trained. Train RF ROC AUC: {train_auc:.4f}")
    
    # Evaluate
    metrics = clf.evaluate(test_acc, test_rev)
    for model_name, m_dict in metrics.items():
        print(f"\nEvaluation Metrics ({model_name.upper()}):")
        for k, v in m_dict.items():
            if k != 'report':
                print(f"  {k}: {v:.4f}")
            
    print("\nFeature Importances:")
    print(clf.get_feature_importances())
