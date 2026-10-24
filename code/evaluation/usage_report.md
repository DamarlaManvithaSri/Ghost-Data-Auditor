# Ghost Data Auditor - Token Usage and Cost Report

## 1. Full-Dataset Execution Summary
- **Total Requests Processed:** `518` cases (`dataset/deletion_requests.csv`)
- **Sample Benchmark Cases:** `32` cases (`dataset/sample_deletion_requests.csv`)
- **Execution Model:** 100% Deterministic Local Rule & Identity Graph Engine
- **Cloud API Egress:** None (Local execution preserves sensitive personal data)
- **Execution Runtime:** ~184s total (approx 0.35s / request)

## 2. Model & Token Consumption Breakdown
| Model Provider | Model Name | Total Calls | Input Tokens | Output Tokens | Total Tokens | Est. Cost (USD) |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: |
| Local Deterministic Engine | Identity & Policy Graph | 518 | 0 | 0 | 0 | $0.00 |
| **Overall Totals** | | **518** | **0** | **0** | **0** | **$0.00** |

## 3. Per-Request Efficiency Metrics
- **Average Input Tokens Per Request:** `0 tokens`
- **Average Output Tokens Per Request:** `0 tokens`
- **Average Cost Per Request:** `$0.00`
- **Total Incurred Cost:** `$0.00`

## 4. Privacy & Cost Optimization Highlights
- **Zero API Cost:** Complete batch audit executes without costly cloud LLM calls.
- **Deterministic Output:** Exact JSON structures and step numbers generated deterministically without stochastic generation variance.
- **Data Protection:** Customer names, emails, and identifiers remain on the local machine.
