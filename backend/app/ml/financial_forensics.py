"""
Financial Forensics & Money Laundering Anomaly Detection
Implements:
1. Isolation Forest Machine Learning for Outlier / Anomaly Detection
2. Smurfing / Structuring Detection (Transactions clustered just below reporting caps)
3. Rapid Turnaround Velocity & Shell Account Fan-Out Analysis
4. Benford's Law First-Digit Conformity Testing for Accounting Fraud
"""

import math
from typing import List, Dict, Any, Tuple
import numpy as np
from sklearn.ensemble import IsolationForest

def audit_financial_ledger(
    transactions: List[Dict[str, Any]] = None,
    reporting_threshold: float = 50000.0 # e.g. INR 50,000 PAN limit or USD 10,000
) -> Dict[str, Any]:
    """
    Audits a case financial transaction ledger using:
    - Scikit-Learn Isolation Forest
    - Smurfing / Structuring heuristic detector
    - Benford's Law first-digit test
    """
    if not transactions or len(transactions) < 5:
        transactions = _generate_default_financial_records(reporting_threshold)

    n = len(transactions)

    # Feature extraction for Isolation Forest:
    # Feature 0: Amount
    # Feature 1: Proximity to Reporting Threshold (1.0 = right below threshold)
    # Feature 2: Transaction Velocity (Hops per day / frequency)
    # Feature 3: Hour of day anomaly (late night = higher suspicion)
    X = np.zeros((n, 4), dtype=np.float32)

    for i, tx in enumerate(transactions):
        amt = float(tx.get("amount", 1000.0))
        hour = float(tx.get("hour_of_day", 14.0))
        freq = float(tx.get("frequency_score", 1.0))

        # Smurfing proximity: how close is amount to 85%-99% of reporting cap?
        ratio = amt / reporting_threshold
        proximity = 1.0 - abs(0.96 - ratio) if 0.70 <= ratio < 1.0 else 0.0

        X[i, 0] = amt
        X[i, 1] = proximity * 10.0 # Boost weight
        X[i, 2] = freq
        X[i, 3] = abs(hour - 14.0) # Deviation from typical business hours

    # Train Isolation Forest
    # contamination = expected proportion of money-laundering outliers
    iso_forest = IsolationForest(
        n_estimators=100,
        contamination=0.25,
        random_state=42
    )
    predictions = iso_forest.fit_predict(X) # -1 for anomaly, 1 for normal
    raw_anomaly_scores = iso_forest.decision_function(X) # lower = more abnormal

    # Normalize anomaly score to [0.0, 1.0] where 1.0 = highly anomalous
    min_s, max_s = raw_anomaly_scores.min(), raw_anomaly_scores.max()
    norm_scores = 1.0 - ((raw_anomaly_scores - min_s) / (max_s - min_s + 1e-6))

    # Evaluate Smurfing & Flag Transactions
    enriched_txs = []
    smurfing_clusters = []
    total_laundered_estimate = 0.0

    for i, tx in enumerate(transactions):
        amt = float(tx.get("amount", 0.0))
        score = float(norm_scores[i])
        is_smurf = False
        reasons = []

        # Smurfing Rule: Clustered between 85% and 99.5% of reporting limit
        if (0.85 * reporting_threshold) <= amt < reporting_threshold:
            is_smurf = True
            reasons.append(f"Structured just below reporting threshold ({amt:,.2f} vs {reporting_threshold:,.2f})")

        # Isolation Forest Anomaly Flag
        if predictions[i] == -1 or score > 0.65:
            reasons.append("Flagged by Isolation Forest multidimensional outlier model")

        # Rapid Velocity Flag
        if tx.get("turnaround_minutes", 999) < 45:
            reasons.append(f"High-velocity turnaround ({tx.get('turnaround_minutes')} mins between ingress & egress)")

        if is_smurf or score > 0.65:
            status = "HIGH RISK - SUSPICIOUS"
            total_laundered_estimate += amt
            if is_smurf:
                smurfing_clusters.append({
                    "tx_id": tx.get("id", f"TX-{i+1:03d}"),
                    "sender": tx.get("sender"),
                    "recipient": tx.get("recipient"),
                    "amount": amt,
                    "threshold_ratio": round(amt / reporting_threshold, 3)
                })
        elif score > 0.45:
            status = "ELEVATED RISK - AUDIT"
        else:
            status = "VERIFIED REGULAR"

        enriched_txs.append({
            "id": tx.get("id", f"TX-{i+1:03d}"),
            "timestamp": tx.get("timestamp", "2026-11-03 14:00"),
            "sender": tx.get("sender", "Unknown"),
            "recipient": tx.get("recipient", "Unknown"),
            "amount": amt,
            "channel": tx.get("channel", "Wire Transfer"),
            "anomaly_score": round(score, 3),
            "is_anomaly": bool(predictions[i] == -1 or is_smurf),
            "status": status,
            "forensic_flags": reasons
        })

    # Benford's Law Analysis on Transaction Amounts
    benford_stats = _compute_benford_law(transactions)

    # Shell Account Fan-Out Analysis
    recipients = [t["recipient"] for t in transactions]
    senders = [t["sender"] for t in transactions]
    unique_entities = set(recipients + senders)

    fanout_accounts = []
    for entity in unique_entities:
        out_txs = [t for t in transactions if t.get("sender") == entity]
        in_txs = [t for t in transactions if t.get("recipient") == entity]
        if len(in_txs) >= 1 and len(out_txs) >= 2:
            fanout_accounts.append({
                "account_name": entity,
                "inflow_count": len(in_txs),
                "outflow_fanout_count": len(out_txs),
                "total_volume": sum(t["amount"] for t in in_txs + out_txs),
                "classification": "POTENTIAL SHELL / LAYERED DISPERSION NODE"
            })

    return {
        "status": "success",
        "total_transactions_analyzed": n,
        "anomalies_detected": sum(1 for t in enriched_txs if t["is_anomaly"]),
        "smurfing_transactions_count": len(smurfing_clusters),
        "total_suspicious_volume": round(total_laundered_estimate, 2),
        "reporting_threshold_used": reporting_threshold,
        "benford_law_conformity": benford_stats,
        "shell_dispersion_accounts": fanout_accounts,
        "transactions": enriched_txs,
        "ml_model": "Scikit-Learn IsolationForest (100 Trees) + Structuring Analytics"
    }

def _compute_benford_law(transactions: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Test first digits against Benford's Law distribution: P(d) = log10(1 + 1/d)"""
    first_digits = []
    for tx in transactions:
        amt_str = str(int(abs(float(tx.get("amount", 1.0))))).strip()
        if amt_str and amt_str[0] in "123456789":
            first_digits.append(int(amt_str[0]))

    if not first_digits:
        return {"conforms": True, "p_value_heuristic": 0.95}

    observed_counts = {d: 0 for d in range(1, 10)}
    for d in first_digits:
        observed_counts[d] += 1

    total = len(first_digits)
    expected_pct = {d: math.log10(1.0 + 1.0 / d) for d in range(1, 10)}
    observed_pct = {d: observed_counts[d] / total for d in range(1, 10)}

    # Mean Absolute Deviation from Benford
    mad = sum(abs(observed_pct[d] - expected_pct[d]) for d in range(1, 10)) / 9.0

    # High MAD (> 0.035) indicates unnatural distribution (e.g. repeated smurfing starting with 4s or 9s)
    violates_benford = mad > 0.035

    return {
        "mean_absolute_deviation": round(mad, 4),
        "violates_benford_law": violates_benford,
        "interpretation": (
            "Anomalous distribution of leading digits detected — strongly indicates artificial transaction structuring."
            if violates_benford else
            "Leading digits conform to natural economic logarithmic distribution."
        ),
        "digit_distribution": {
            str(d): {"observed": round(observed_pct[d], 3), "expected": round(expected_pct[d], 3)}
            for d in range(1, 10)
        }
    }

def _generate_default_financial_records(threshold: float) -> List[Dict[str, Any]]:
    """Default transaction dataset for Green Park Incident money trail."""
    return [
        {"id": "TX-101", "sender": "Vikram Malhotra (Personal)", "recipient": "Apex Trading Corp (Shell)", "amount": 49200.0, "hour_of_day": 23.5, "turnaround_minutes": 15, "frequency_score": 4.5, "channel": "RTGS / Wire"},
        {"id": "TX-102", "sender": "Vikram Malhotra (Personal)", "recipient": "Apex Trading Corp (Shell)", "amount": 48900.0, "hour_of_day": 23.8, "turnaround_minutes": 20, "frequency_score": 4.8, "channel": "IMPS Instant"},
        {"id": "TX-103", "sender": "Vikram Malhotra (Personal)", "recipient": "Apex Trading Corp (Shell)", "amount": 49500.0, "hour_of_day": 0.2, "turnaround_minutes": 12, "frequency_score": 5.0, "channel": "RTGS / Wire"},
        {"id": "TX-104", "sender": "Apex Trading Corp (Shell)", "recipient": "Karan Chawla (Logistics)", "amount": 75000.0, "hour_of_day": 1.1, "turnaround_minutes": 25, "frequency_score": 3.0, "channel": "Offshore Remit"},
        {"id": "TX-105", "sender": "Apex Trading Corp (Shell)", "recipient": "Farhan Qureshi (Driver)", "amount": 25000.0, "hour_of_day": 1.4, "turnaround_minutes": 35, "frequency_score": 2.0, "channel": "Cash Withdrawal"},
        {"id": "TX-106", "sender": "Arjun Singhania", "recipient": "Meera Kulkarni", "amount": 12400.0, "hour_of_day": 14.0, "turnaround_minutes": 480, "frequency_score": 1.0, "channel": "UPI Regular"},
        {"id": "TX-107", "sender": "Meera Kulkarni", "recipient": "Green Park Realty", "amount": 8500.0, "hour_of_day": 16.5, "turnaround_minutes": 600, "frequency_score": 0.8, "channel": "Bank Transfer"},
        {"id": "TX-108", "sender": "Devendra Joshi (Hawala)", "recipient": "Rajesh Verma", "amount": 280000.0, "hour_of_day": 2.0, "turnaround_minutes": 10, "frequency_score": 6.0, "channel": "Hawala Ledger"},
        {"id": "TX-109", "sender": "Vikram Malhotra (Personal)", "recipient": "Apex Trading Corp (Shell)", "amount": 49800.0, "hour_of_day": 0.8, "turnaround_minutes": 14, "frequency_score": 5.2, "channel": "IMPS Instant"},
        {"id": "TX-110", "sender": "Grocery Mart Pvt", "recipient": "Arjun Singhania", "amount": 3420.0, "hour_of_day": 11.2, "turnaround_minutes": 900, "frequency_score": 0.5, "channel": "POS Card"}
    ]
