import numpy as np
import pandas as pd
from datetime import datetime, timedelta
import random

class EcommerceDataGenerator:
    def __init__(self, seed=42):
        self.seed = seed
        random.seed(seed)
        np.random.seed(seed)
        
        # Product and seller catalogs
        self.num_sellers = 50
        self.num_products = 500
        self.sellers = [f"SEL-{i:03d}" for i in range(1, self.num_sellers + 1)]
        self.products = [f"PRD-{i:04d}" for i in range(1, self.num_products + 1)]
        
        # Map products to sellers
        self.product_to_seller = {}
        for p in self.products:
            # Group products by seller to make it realistic
            seller_idx = int(p.split("-")[1]) % self.num_sellers
            self.product_to_seller[p] = self.sellers[seller_idx]
            
        # Review templates
        self.genuine_good_templates = [
            "Really liked this product, works well.",
            "Decent quality for the price.",
            "Works as advertised, would buy again.",
            "Great value and functions perfectly. Very pleased.",
            "Very satisfied with the build quality. Recommended."
        ]
        self.genuine_neutral_templates = [
            "Okay product, arrived a bit late though.",
            "Average quality. Nothing special but does the job.",
            "It works, but the instructions were hard to follow.",
            "Decent but has some minor issues.",
            "Average experience. Packaging was a bit damaged."
        ]
        self.genuine_bad_templates = [
            "Not what I expected, returned it.",
            "Broke after two weeks of light use.",
            "Poor quality materials. Do not recommend.",
            "Did not fit my expectations. Disappointed.",
            "Customer service was slow, product is sub-par."
        ]
        
        self.fake_positive_templates = [
            "Amazing product!!! Best seller ever! Highly recommended!",
            "Absolutely perfect! Outstanding quality and fast shipping.",
            "Best purchase I have ever made! 100% recommended.",
            "Very good! Buying more next week.",
            "Outstanding quality, very satisfied! A+++ seller!",
            "Super fast shipping, amazing price. Will buy again!"
        ]
        
        self.fake_negative_templates = [
            "TERRIBLE! DO NOT BUY! Scammer seller!",
            "Horrible quality, broke on first day. Garbage.",
            "Total waste of money. Avoid this seller.",
            "DO NOT TRUST THIS! False advertising.",
            "Extremely disappointed. Awful experience. Save your cash."
        ]
        
        # Distribution of countries
        self.countries = ["US", "US", "US", "CA", "GB", "GB", "DE", "FR", "IN", "AU"]

    def _generate_ip(self, subnet=None):
        """Generates a random IP address, optionally within a subnet."""
        if subnet:
            parts = subnet.split('.')
            return f"{parts[0]}.{parts[1]}.{parts[2]}.{random.randint(2, 254)}"
        return f"{random.randint(24, 220)}.{random.randint(10, 250)}.{random.randint(0, 254)}.{random.randint(2, 254)}"

    def _generate_device_id(self):
        """Generates a unique device ID hash."""
        chars = "0123456789abcdef"
        return "".join(random.choices(chars, k=16))

    def generate_data(self, num_genuine=1000, num_fake=100, attack_severity=0.8):
        """
        Generates synthetic users and their reviews.
        
        Parameters:
        - num_genuine: Number of normal users to generate.
        - num_fake: Number of fake accounts to generate.
        - attack_severity: Probability of fake accounts targeting a single seller (0.0 to 1.0).
        """
        base_time = datetime(2026, 4, 1, 0, 0, 0) # Simulation starts April 1, 2026
        
        accounts = []
        reviews = []
        
        # --- 1. GENERATE GENUINE ACCOUNTS & REVIEWS ---
        for i in range(1, num_genuine + 1):
            account_id = f"USR-{i:05d}"
            
            # Signup is distributed over a 90-day period
            signup_delay_days = random.uniform(0, 90)
            signup_time = base_time + timedelta(days=signup_delay_days, 
                                                hours=random.uniform(0, 24), 
                                                minutes=random.uniform(0, 60))
            
            accounts.append({
                "account_id": account_id,
                "username": f"user_{random.randint(1000, 99999)}_{i}",
                "signup_time": signup_time,
                "signup_ip": self._generate_ip(),
                "device_id": self._generate_device_id(),
                "country": random.choice(self.countries),
                "is_fake": 0
            })
            
            # Normal users have a 70% chance to write reviews
            if random.random() < 0.7:
                # Number of reviews is usually small: 1 to 4
                num_user_reviews = random.choices([1, 2, 3, 4], weights=[0.6, 0.25, 0.1, 0.05])[0]
                for r in range(num_user_reviews):
                    review_id = f"REV-G{i:05d}-{r}"
                    product = random.choice(self.products)
                    seller = self.product_to_seller[product]
                    
                    # Normal rating distribution: positive skew
                    rating = random.choices([1, 2, 3, 4, 5], weights=[0.08, 0.07, 0.15, 0.30, 0.40])[0]
                    
                    # Review text based on rating
                    if rating >= 4:
                        text = random.choice(self.genuine_good_templates)
                    elif rating == 3:
                        text = random.choice(self.genuine_neutral_templates)
                    else:
                        text = random.choice(self.genuine_bad_templates)
                        
                    # Genuine users review after receiving the item (e.g., 3 to 15 days delay)
                    review_delay = random.uniform(3, 15)
                    review_time = signup_time + timedelta(days=review_delay, 
                                                          hours=random.uniform(0, 24))
                    
                    reviews.append({
                        "review_id": review_id,
                        "account_id": account_id,
                        "product_id": product,
                        "seller_id": seller,
                        "rating": rating,
                        "review_time": review_time,
                        "review_text": text
                    })

        # --- 2. GENERATE ADVERSARIAL FAKE ACCOUNTS & REVIEWS ---
        # Fake accounts are created in "campaigns" targeting specific sellers.
        # We group fake accounts into clusters that operate together.
        num_campaigns = max(1, num_fake // 10)
        accounts_per_campaign = num_fake // num_campaigns
        
        fake_idx = 1
        for c in range(num_campaigns):
            # Pick a target seller and product for this campaign
            target_seller = random.choice(self.sellers)
            target_products = [p for p, s in self.product_to_seller.items() if s == target_seller]
            if not target_products:
                target_products = [random.choice(self.products)]
                
            # Type of campaign: 85% positive (boosting own store), 15% negative (attacking competitor)
            is_positive_campaign = random.random() < 0.85
            
            # Collusion pattern setup: Shared subnet and device clusters
            campaign_subnet = f"{random.randint(24, 220)}.{random.randint(10, 250)}.{random.randint(0, 254)}"
            
            # Group shares device_ids in batches of 3-4 accounts
            device_pool = [self._generate_device_id() for _ in range(max(1, accounts_per_campaign // 3))]
            
            # Campaign launch time (occurs at some burst point)
            campaign_start = base_time + timedelta(days=random.uniform(10, 80))
            
            for _ in range(accounts_per_campaign):
                account_id = f"USR-F{fake_idx:05d}"
                
                # Adversaries sign up very rapidly: within a few minutes/hours of each other
                signup_time = campaign_start + timedelta(minutes=random.uniform(0, 180))
                
                # Shared network and device characteristics
                ip = self._generate_ip(subnet=campaign_subnet)
                device = random.choice(device_pool)
                
                accounts.append({
                    "account_id": account_id,
                    "username": f"reviewer_{random.randint(100, 9999)}_{fake_idx}",
                    "signup_time": signup_time,
                    "signup_ip": ip,
                    "device_id": device,
                    "country": "US",  # often spoofed/focused on the target market
                    "is_fake": 1
                })
                
                # Fake accounts write reviews almost immediately and concentrate reviews
                # Let's say they review 1 to 3 items
                num_reviews = random.randint(1, 3)
                for r in range(num_reviews):
                    review_id = f"REV-F{fake_idx:05d}-{r}"
                    
                    # With high probability (attack severity), they review the target product/seller.
                    # Otherwise, they review a random product to "blend in"
                    if random.random() < attack_severity:
                        product = random.choice(target_products)
                        seller = target_seller
                        is_target = True
                    else:
                        product = random.choice(self.products)
                        seller = self.product_to_seller[product]
                        is_target = False
                        
                    # Ratings
                    if is_target:
                        rating = 5 if is_positive_campaign else 1
                        text = random.choice(self.fake_positive_templates if is_positive_campaign else self.fake_negative_templates)
                    else:
                        # Random filler review rating
                        rating = random.choices([1, 2, 3, 4, 5], weights=[0.1, 0.1, 0.2, 0.3, 0.3])[0]
                        text = random.choice(self.genuine_good_templates if rating >= 4 else (self.genuine_neutral_templates if rating == 3 else self.genuine_bad_templates))
                        
                    # VELOCITY anomaly: review written within minutes or hours of signing up (e.g. 5 min to 12 hours)
                    review_delay = random.uniform(5, 720) # in minutes
                    review_time = signup_time + timedelta(minutes=review_delay)
                    
                    reviews.append({
                        "review_id": review_id,
                        "account_id": account_id,
                        "product_id": product,
                        "seller_id": seller,
                        "rating": rating,
                        "review_time": review_time,
                        "review_text": text
                    })
                    
                fake_idx += 1
                
        df_accounts = pd.DataFrame(accounts)
        df_reviews = pd.DataFrame(reviews)
        
        return df_accounts, df_reviews

if __name__ == "__main__":
    generator = EcommerceDataGenerator()
    df_acc, df_rev = generator.generate_data(num_genuine=200, num_fake=20)
    print("Generated accounts:", len(df_acc))
    print("Fake accounts:", df_acc['is_fake'].sum())
    print("Generated reviews:", len(df_rev))
