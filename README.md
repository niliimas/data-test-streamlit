# Data Analysis Test — Streamlit KPI Dashboard

## Overview
This project is a Streamlit-based interactive dashboard built for a data analysis take-home test.

The application includes:

- Data Overview & Validation
- KPI Dashboard
- Customer Behavior Analysis
- Vendor Contribution Analysis
- Business Insights

The dashboard supports interactive filtering and two different order definitions:

- Row-level (each row is considered one order)
- Unique OrderKey (orders counted using distinct OrderKey values)

---

## Dataset Description

The dataset contains transactional data with the following fields:

- OrderKey
- CustomerKey
- VendorKey
- SoldCoupon
- GMV
- CategoryID
- OrderDateKey

`OrderDateKey` is converted into a proper datetime field (`OrderDate`) for time-based analysis.

---

## Data Validation & Quality Checks

The application performs the following validation steps:

- Total row and column count
- Data type inspection
- Missing value detection
- Duplicate row detection
- OrderKey uniqueness validation
- GMV ≤ 0 detection
- Date conversion validation

All detected issues are displayed in the **Data Overview** section.

---

## KPI Definitions

Orders can be calculated using two approaches:

### 1. Row-level definition
Each row is treated as one order.

### 2. Unique OrderKey definition
Orders are counted using distinct OrderKey values.

Main KPIs:

- Total Orders
- Total Customers (distinct CustomerKey)
- Total GMV (sum of GMV)
- Average GMV per Order
- Average Orders per Customer

All KPIs dynamically respond to:

- Selected filters
- Selected order definition
- Applied data cleaning options

---

## Dashboard Features

### Interactive Filters

- Date range
- Vendor
- Category
- Order definition toggle

All visualizations and KPIs update dynamically based on filter selection.

### Trend Analysis

- Monthly Orders
- Monthly GMV

### Breakdown Analysis

- Top 10 Vendors by GMV
- Top 10 Categories by GMV

---

## Analysis Section

### Task A — Customer Behavior

- Orders per customer
- One-time vs repeat customers
- Repeat customer percentage
- GMV share from repeat customers
- Orders per customer distribution (binned)
- Retention upside scenarios (directional impact estimates)

### Task B — Vendor Contribution

- GMV per vendor
- Vendor ranking by GMV
- Top 5 GMV share
- Top 10 GMV share
- Top 20% vendor GMV share
- Cumulative GMV curve (Pareto analysis)
- Vendor dependency risk scenarios (directional impact estimates)

---

## Business Insights

The application includes a structured **insight layer** that goes beyond descriptive metrics and connects findings to business implications.

Key analytical insights include:

- **Data Grain Ambiguity**  
  `OrderKey` is not fully unique, which may indicate non–order-level granularity or duplicated records. KPI definitions (e.g., Orders, AOV) can materially change depending on whether orders are counted at row-level or by unique `OrderKey`.

- **Refund / Cancellation Handling**  
  The presence of `GMV ≤ 0` rows suggests potential refunds, cancellations, or chargebacks. These should be explicitly flagged and separated (e.g., Gross GMV vs Net GMV) to avoid distorting revenue reporting.

- **Customer Retention Opportunity**  
  A relatively small share of repeat customers generates a disproportionately high share of GMV. This indicates strong retention leverage and highlights the financial importance of CRM and lifecycle initiatives.

- **Quantified Retention Impact (Directional Scenario)**  
  Under a simplifying assumption, even a small improvement in repeat rate (e.g., converting 5% of one-time customers) can generate a meaningful GMV uplift.  
  These are directional impact estimates meant to quantify upside, not precise forecasts.

- **Vendor Revenue Concentration Risk**  
  A small group of top vendors contributes a significant share of total GMV. This creates both strategic partnership opportunities and dependency risk in case of vendor churn.

- **Long-Tail Vendor Contribution (Pareto Structure)**  
  The vendor portfolio exhibits a Pareto-like structure where a minority of vendors drives most revenue. This raises operational questions around resource allocation and vendor segmentation strategy.

- **Category-Level Concentration (Product Mix Risk)**  
  A small number of top categories accounts for a substantial share of GMV, indicating product concentration. Diversifying the category mix may reduce structural revenue risk.

- **Campaign/Event-Driven Growth Pattern**  
  Monthly trends reveal peak periods with noticeable spikes in Orders and GMV, suggesting campaign-driven uplift rather than purely organic growth.  
  Campaign attribution analysis is recommended to validate incrementality.

- **Structural Recommendation (Analytics Data Mart)**  
  Build an analytics-ready data mart consisting of:
  - `FactOrders`
  - `DimDate`
  - `DimCustomer`
  - `DimVendor`
  - `DimCategory`

  This will standardize KPI definitions, resolve grain ambiguity, and improve BI scalability and performance.


---

## Assumptions & Limitations

- **OrderKey duplicates → Order definition toggle:**  
  Although the instructions state each row represents one order, duplicate `OrderKey` values were detected.  
  To keep the analysis transparent, the dashboard supports two order definitions (Row-level vs Unique `OrderKey`).

- **GMV ≤ 0 may reflect refunds/cancellations:**  
  Records with `GMV ≤ 0` may represent refunds, cancellations, or data-entry issues.  
  A cleaning toggle is provided to optionally exclude these records depending on reporting needs.

- **Impact scenarios are directional (assumption-driven):**  
  Retention and vendor-risk scenarios are simplified, directional estimates designed to quantify upside/risk under assumptions,  
  not precise forecasts.

---

## Summary (Why this aligns with the test goal)

This project focuses on analytical thinking and insight generation (not just charting), including:

- Data quality and integrity checks before KPI calculation
- Detecting potential grain ambiguity and making metric definitions explicit
- Translating metrics into business insights (retention opportunity, vendor concentration risk)
- Quantifying upside/risk with simple scenario modeling

---

## How to Run Locally

### 1. Install dependencies

```bash
pip install -r requirements.txt

```

### 2. Run the application

```bash
streamlit run app.py
```

### 3. Upload the dataset

After the app starts, upload the provided Excel file (`Data.xlsx`) using the file uploader inside the application.

---

## Project Structure

```
app.py
requirements.txt
README.md
```
---

## Notes

- All metrics are calculated on the cleaned and filtered dataset.
- Cleaning options include removing duplicate rows and excluding GMV ≤ 0 records.
- Order calculation logic is configurable to ensure analytical transparency.
