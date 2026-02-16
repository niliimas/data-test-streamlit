# app.py
# Streamlit app for the take-home test:
# 1) Data Overview & Validation
# 2) KPI Dashboard
# 3) Analysis & Insights
#
# Final version includes:
# - Upload-based data source
# - Cleaning toggles
# - Filters (date range, vendor, category)
# - Order definition toggle (Row-level vs Unique OrderKey)
# - KPIs + Monthly trends + Top vendors/categories
# - Task A (Customer behavior) + Task B (Vendor contribution)
# -  Business insights
# - Impact scenarios (Retention upside + Vendor dependency risk)
# - Exports (filtered dataset + key tables)

import streamlit as st
import pandas as pd
import numpy as np
import altair as alt


# -----------------------------
# Page configuration
# -----------------------------
st.set_page_config(
    page_title="Data Test — KPI Dashboard",
    page_icon="📊",
    layout="wide"
)

st.title(" Data Analysis Test — Streamlit App")
st.caption("Data Overview & Validation • KPI Dashboard • Analysis & Insights")


# -----------------------------
# Utilities
# -----------------------------
@st.cache_data(show_spinner=False)
def load_data(source) -> pd.DataFrame:
    """
    Reads Excel data from either:
    - an uploaded file (Streamlit UploadedFile), or
    - a file path (string).
    """
    df = pd.read_excel(source)

    # Normalize IDs
    for col in ["OrderKey", "CustomerKey", "VendorKey"]:
        if col in df.columns:
            df[col] = df[col].astype(str).str.strip()

    # Convert OrderDateKey -> datetime
    if "OrderDateKey" in df.columns:
        df["OrderDate"] = pd.to_datetime(
            df["OrderDateKey"].astype(str),
            format="%Y%m%d",
            errors="coerce"
        )

    # Force numeric columns
    for col in ["SoldCoupon", "GMV", "CategoryID", "OrderDateKey"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    return df


def data_quality_report(df: pd.DataFrame) -> dict:
    report = {
        "rows": int(len(df)),
        "cols": int(df.shape[1]),
        "duplicate_rows": int(df.duplicated().sum()),
        "missing_by_col": df.isna().sum().to_dict(),
    }

    # OrderKey uniqueness
    if "OrderKey" in df.columns:
        uniq = int(df["OrderKey"].nunique(dropna=True))
        report["orderkey_unique"] = uniq
        report["orderkey_duplicate_row_count"] = int(len(df) - uniq)
    else:
        report["orderkey_unique"] = None
        report["orderkey_duplicate_row_count"] = None

    # GMV <= 0
    if "GMV" in df.columns:
        report["gmv_le_zero"] = int((df["GMV"].fillna(0) <= 0).sum())
    else:
        report["gmv_le_zero"] = None

    # Date range
    if "OrderDate" in df.columns:
        report["min_date"] = df["OrderDate"].min()
        report["max_date"] = df["OrderDate"].max()
        report["bad_dates"] = int(df["OrderDate"].isna().sum())
    else:
        report["min_date"] = None
        report["max_date"] = None
        report["bad_dates"] = None

    return report


def clean_data(df: pd.DataFrame, drop_full_duplicates: bool, drop_gmv_le_zero: bool) -> pd.DataFrame:
    out = df.copy()
    if drop_full_duplicates:
        out = out.drop_duplicates()
    if drop_gmv_le_zero and "GMV" in out.columns:
        out = out[out["GMV"] > 0]
    return out


def apply_filters(
    df: pd.DataFrame,
    start_date,
    end_date,
    vendors: list,
    categories: list
) -> pd.DataFrame:
    out = df.copy()

    if "OrderDate" in out.columns and start_date and end_date:
        out = out[out["OrderDate"].between(pd.to_datetime(start_date), pd.to_datetime(end_date))]

    if vendors and "VendorKey" in out.columns:
        out = out[out["VendorKey"].isin(vendors)]

    if categories and "CategoryID" in out.columns:
        out = out[out["CategoryID"].isin(categories)]

    return out


def compute_kpis(df: pd.DataFrame, use_unique_orderkey: bool) -> dict:
    """
    - Orders (rows): number of rows in dataset (as per "each row is an order")
    - Orders (unique): distinct OrderKey count (useful when OrderKey duplicates exist)
    - Orders used: depends on the selected order definition
    """
    orders_rows = int(len(df))
    orders_unique = df["OrderKey"].nunique() if "OrderKey" in df.columns else np.nan
    orders_used = orders_unique if use_unique_orderkey else orders_rows

    customers_unique = df["CustomerKey"].nunique() if "CustomerKey" in df.columns else np.nan
    gmv_total = df["GMV"].sum() if "GMV" in df.columns else np.nan
    sold_coupon_total = df["SoldCoupon"].sum() if "SoldCoupon" in df.columns else np.nan

    avg_gmv_per_order = (gmv_total / orders_used) if (pd.notna(orders_used) and orders_used != 0) else np.nan
    avg_orders_per_customer = (orders_used / customers_unique) if (pd.notna(customers_unique) and customers_unique != 0) else np.nan

    return {
        "rows": int(len(df)),
        "orders_rows": orders_rows,
        "orders_unique": orders_unique,
        "orders_used": orders_used,
        "customers_unique": customers_unique,
        "gmv_total": gmv_total,
        "sold_coupon_total": sold_coupon_total,
        "avg_gmv_per_order": avg_gmv_per_order,
        "avg_orders_per_customer": avg_orders_per_customer,
    }


def month_trends(df: pd.DataFrame, use_unique_orderkey: bool) -> pd.DataFrame:
    if "OrderDate" not in df.columns:
        return pd.DataFrame()

    tmp = df.dropna(subset=["OrderDate"]).copy()
    if tmp.empty:
        return pd.DataFrame()

    tmp["YearMonth"] = tmp["OrderDate"].dt.to_period("M").astype(str)

    # Orders aggregation depends on chosen definition
    if use_unique_orderkey and "OrderKey" in tmp.columns:
        orders_agg = ("OrderKey", "nunique")
    else:
        # row-level: each row is an order
        orders_agg = ("OrderKey", "size")

    agg = tmp.groupby("YearMonth").agg(
        Orders=orders_agg,
        GMV=("GMV", "sum"),
        Rows=("OrderKey", "size")
    ).reset_index()

    agg["YearMonth_dt"] = pd.to_datetime(agg["YearMonth"] + "-01")
    agg = agg.sort_values("YearMonth_dt").drop(columns=["YearMonth_dt"])
    return agg


def top_n(df: pd.DataFrame, group_col: str, value_col: str, n: int = 10) -> pd.DataFrame:
    if group_col not in df.columns or value_col not in df.columns or df.empty:
        return pd.DataFrame()
    out = df.groupby(group_col, as_index=False)[value_col].sum()
    out = out.sort_values(value_col, ascending=False).head(n)
    return out


def customer_behavior(df: pd.DataFrame, use_unique_orderkey: bool) -> dict:
    """
    Task A:
    - One-time vs repeat customers based on the chosen order definition
    - Share of GMV from repeat customers
    """
    required = {"CustomerKey", "GMV"}
    if not required.issubset(set(df.columns)) or df.empty:
        return {}

    if use_unique_orderkey:
        if "OrderKey" not in df.columns:
            return {}
        cust_orders = df.groupby("CustomerKey")["OrderKey"].nunique()
    else:
        # row-level orders
        cust_orders = df.groupby("CustomerKey").size()

    total_customers = int(cust_orders.shape[0])
    one_time = int((cust_orders == 1).sum())
    repeat = int((cust_orders > 1).sum())

    repeat_customers = cust_orders[cust_orders > 1].index
    gmv_total = float(df["GMV"].sum()) if "GMV" in df.columns else 0.0
    gmv_repeat = float(df[df["CustomerKey"].isin(repeat_customers)]["GMV"].sum()) if gmv_total else 0.0

    repeat_pct = (repeat / total_customers) if total_customers else np.nan
    repeat_gmv_share = (gmv_repeat / gmv_total) if gmv_total else np.nan

    return {
        "total_customers": total_customers,
        "one_time_customers": one_time,
        "repeat_customers": repeat,
        "repeat_pct": repeat_pct,
        "gmv_total": gmv_total,
        "gmv_repeat": gmv_repeat,
        "repeat_gmv_share": repeat_gmv_share,
        "cust_orders_series": cust_orders
    }


def vendor_contribution(df: pd.DataFrame) -> dict:
    """
    Task B:
    - Top 5, Top 10 GMV share
    - Top 20% vendors share
    """
    required = {"VendorKey", "GMV"}
    if not required.issubset(set(df.columns)) or df.empty:
        return {}

    v = df.groupby("VendorKey", as_index=False)["GMV"].sum().sort_values("GMV", ascending=False)
    total_gmv = float(v["GMV"].sum())
    vendor_count = int(v.shape[0])

    top5_share = float(v.head(5)["GMV"].sum() / total_gmv) if total_gmv else np.nan
    top10_share = float(v.head(10)["GMV"].sum() / total_gmv) if total_gmv else np.nan

    top20pct_n = int(np.ceil(vendor_count * 0.2))
    top20pct_share = float(v.head(top20pct_n)["GMV"].sum() / total_gmv) if total_gmv else np.nan

    v["GMV_share"] = v["GMV"] / total_gmv if total_gmv else np.nan
    v["GMV_cum_share"] = v["GMV_share"].cumsum()

    return {
        "vendor_count": vendor_count,
        "total_gmv": total_gmv,
        "top5_share": top5_share,
        "top10_share": top10_share,
        "top20pct_n": top20pct_n,
        "top20pct_share": top20pct_share,
        "vendor_table": v
    }


# -----------------------------
# Impact Scenarios (Assumption-driven)
# -----------------------------
def retention_uplift_scenarios(cb: dict, conversion_rates=(0.02, 0.05, 0.10)) -> pd.DataFrame:
    """
    Estimate GMV uplift if a fraction of one-time customers become repeat customers.

    Assumption:
    Converted customers generate the same average GMV as current repeat customers.
    This is a directional estimate, not a precise forecast.
    """
    if not cb:
        return pd.DataFrame()

    one_time = cb.get("one_time_customers", 0)
    repeat = cb.get("repeat_customers", 0)
    gmv_repeat = cb.get("gmv_repeat", 0.0)

    if repeat <= 0 or one_time <= 0 or gmv_repeat <= 0:
        return pd.DataFrame()

    avg_gmv_per_repeat_customer = gmv_repeat / repeat

    rows = []
    for r in conversion_rates:
        converted = int(round(one_time * r))
        uplift_gmv = converted * avg_gmv_per_repeat_customer
        rows.append({
            "Scenario": f"Convert {int(r * 100)}% of one-time → repeat",
            "Converted customers": converted,
            "Avg GMV per repeat customer (assumption)": avg_gmv_per_repeat_customer,
            "Estimated GMV uplift": uplift_gmv
        })

    return pd.DataFrame(rows)


def vendor_loss_scenarios(vc: dict, top_list=(1, 3, 5, 10)) -> pd.DataFrame:
    """
    Estimate GMV at risk if top-N vendors are lost.

    Assumption:
    Losing the vendor implies losing their GMV contribution (no immediate substitution).
    This is a directional risk estimate, not a precise forecast.
    """
    if not vc or "vendor_table" not in vc:
        return pd.DataFrame()

    vtable = vc["vendor_table"].copy()
    if vtable.empty or "GMV" not in vtable.columns:
        return pd.DataFrame()

    total_gmv = float(vtable["GMV"].sum())
    if total_gmv <= 0:
        return pd.DataFrame()

    rows = []
    for n in top_list:
        at_risk = float(vtable.head(n)["GMV"].sum())
        rows.append({
            "Scenario": f"Lose Top {n} vendor(s)",
            "GMV at risk": at_risk,
            "GMV at risk (%)": at_risk / total_gmv
        })

    return pd.DataFrame(rows)


def fmt_int(x):
    if pd.isna(x):
        return "-"
    return f"{int(x):,}"


def fmt_money(x):
    if pd.isna(x):
        return "-"
    return f"{x:,.2f}"


def fmt_pct(x):
    if pd.isna(x):
        return "-"
    return f"{x * 100:.2f}%"


def safe_csv_download(df: pd.DataFrame, filename: str, label: str):
    if df is None or df.empty:
        st.info(f"{label}: nothing to download (empty result).")
        return
    st.download_button(
        label,
        data=df.to_csv(index=False).encode("utf-8"),
        file_name=filename,
        mime="text/csv"
    )


# -----------------------------
# Sidebar: Inputs
# -----------------------------
with st.sidebar:
    st.header(" Settings")

    st.subheader(" Data Source")
    uploaded_file = st.file_uploader("Upload Data.xlsx", type=["xlsx"])

    st.markdown("---")
    st.subheader(" Data Cleaning")
    drop_full_duplicates = st.checkbox("Drop fully duplicated rows", value=True)
    drop_gmv_le_zero = st.checkbox("Drop rows with GMV ≤ 0", value=True)

# Load (from uploader)
if uploaded_file is None:
    st.warning("Please upload the Excel file (Data.xlsx) to proceed.")
    st.stop()

try:
    df_raw = load_data(uploaded_file)
except Exception as e:
    st.error(f"Failed to read uploaded dataset: {e}")
    st.stop()

# Cleaned base dataset
df_base = clean_data(
    df_raw,
    drop_full_duplicates=drop_full_duplicates,
    drop_gmv_le_zero=drop_gmv_le_zero
)

# Sidebar: Order definition + Filters (based on cleaned/base dataset)
with st.sidebar:
    st.markdown("---")
    st.subheader(" Order Definition")

    order_def = st.radio(
        "How should we count orders?",
        ["Row-level (each row is an order)", "Unique OrderKey (deduplicate by OrderKey)"],
        index=0
    )
    use_unique_orderkey = (order_def == "Unique OrderKey (deduplicate by OrderKey)")

    st.markdown("---")
    st.subheader(" Filters")

    if "OrderDate" in df_base.columns and df_base["OrderDate"].notna().any():
        min_date = df_base["OrderDate"].min().date()
        max_date = df_base["OrderDate"].max().date()
        date_range = st.date_input(
            "Date range",
            value=(min_date, max_date),
            min_value=min_date,
            max_value=max_date
        )
        if isinstance(date_range, tuple) and len(date_range) == 2:
            start_date, end_date = date_range
        else:
            start_date, end_date = min_date, max_date
    else:
        start_date, end_date = None, None
        st.warning("No valid dates found (OrderDateKey → OrderDate conversion).")

    vendor_options = sorted(df_base["VendorKey"].dropna().unique().tolist()) if "VendorKey" in df_base.columns else []
    category_options = sorted(df_base["CategoryID"].dropna().unique().tolist()) if "CategoryID" in df_base.columns else []

    vendors_sel = st.multiselect("Vendor", options=vendor_options, default=[])
    categories_sel = st.multiselect("CategoryID", options=category_options, default=[])

    st.caption("All metrics and charts are computed on the cleaned + filtered dataset.")

# Apply filters
df = apply_filters(df_base, start_date, end_date, vendors_sel, categories_sel)

# -----------------------------
# Tabs
# -----------------------------
tab1, tab2, tab3 = st.tabs(["1) Data Overview & Validation", "2) KPI Dashboard", "3) Analysis & Insights"])


# -----------------------------
# Tab 1: Overview & Validation
# -----------------------------
with tab1:
    st.subheader(" Data Overview")

    rep_raw = data_quality_report(df_raw)
    rep_clean = data_quality_report(df_base)

    colA, colB, colC, colD = st.columns(4)
    with colA:
        st.metric("Rows (raw)", fmt_int(rep_raw["rows"]))
        st.metric("Rows (after cleaning)", fmt_int(rep_clean["rows"]))
    with colB:
        st.metric("Columns", fmt_int(rep_raw["cols"]))
        st.metric("Duplicate rows (raw)", fmt_int(rep_raw["duplicate_rows"]))
    with colC:
        st.metric("Unique OrderKey (raw)", fmt_int(rep_raw["orderkey_unique"]))
        st.metric("OrderKey duplicates (row count)", fmt_int(rep_raw["orderkey_duplicate_row_count"]))
    with colD:
        st.metric("GMV ≤ 0 rows (raw)", fmt_int(rep_raw["gmv_le_zero"]))
        if rep_raw["min_date"] is not None:
            st.metric("Date range (raw)", f"{rep_raw['min_date'].date()} → {rep_raw['max_date'].date()}")
        else:
            st.metric("Date range (raw)", "-")

    st.markdown("---")
    st.subheader(" Schema & Missing Values")

    schema_df = pd.DataFrame({
        "Column": df_raw.columns,
        "Dtype": [str(df_raw[c].dtype) for c in df_raw.columns],
        "Missing": [int(df_raw[c].isna().sum()) for c in df_raw.columns],
        "Unique": [int(df_raw[c].nunique(dropna=True)) for c in df_raw.columns],
    })
    st.dataframe(schema_df, use_container_width=True)

    st.markdown("---")
    st.subheader(" Data Issues (recommended to mention)")

    issues = []
    if rep_raw["orderkey_duplicate_row_count"] and rep_raw["orderkey_duplicate_row_count"] > 0:
        issues.append(
            f"- `OrderKey` is not unique: about **{rep_raw['orderkey_duplicate_row_count']:,}** rows are additional "
            f"(unique OrderKey = {rep_raw['orderkey_unique']:,} out of {rep_raw['rows']:,} rows). "
            "This suggests the dataset may not be strictly order-level, or it contains duplicated order records."
        )
    if rep_raw["duplicate_rows"] and rep_raw["duplicate_rows"] > 0:
        issues.append(f"- Fully duplicated rows exist: **{rep_raw['duplicate_rows']:,}** rows.")
    if rep_raw["gmv_le_zero"] and rep_raw["gmv_le_zero"] > 0:
        issues.append(
            f"- Rows with `GMV ≤ 0`: **{rep_raw['gmv_le_zero']:,}** rows "
            f"(could be refunds/cancellations or data issues)."
        )
    if rep_raw["bad_dates"] and rep_raw["bad_dates"] > 0:
        issues.append(f"- Invalid/unparsed dates: **{rep_raw['bad_dates']:,}** rows (OrderDateKey conversion failed).")

    if issues:
        st.markdown("\n".join(issues))
    else:
        st.success("No major issues detected.")

    st.markdown("---")
    st.subheader(" Exports")

    colE1, colE2, colE3 = st.columns(3)
    with colE1:
        safe_csv_download(df, "filtered_data.csv", "Download filtered dataset (cleaned + filtered)")
    with colE2:
        safe_csv_download(schema_df, "schema_summary.csv", "Download schema summary")
    with colE3:
        issues_df = pd.DataFrame({"Issue": issues}) if issues else pd.DataFrame({"Issue": ["No major issues detected."]})
        safe_csv_download(issues_df, "data_issues.csv", "Download issues list")

    with st.expander("Preview (first 50 rows of filtered data)"):
        st.dataframe(df.head(50), use_container_width=True)


# -----------------------------
# Tab 2: KPI Dashboard
# -----------------------------
with tab2:
    st.subheader(" KPI Dashboard")

    k = compute_kpis(df, use_unique_orderkey)

    # Show both order counts, plus the chosen one
    c1, c2, c3, c4, c5, c6 = st.columns(6)
    c1.metric("Orders (rows)", fmt_int(k["orders_rows"]))
    c2.metric("Orders (unique OrderKey)", fmt_int(k["orders_unique"]))
    c3.metric("Orders used (current definition)", fmt_int(k["orders_used"]))
    c4.metric("Customers", fmt_int(k["customers_unique"]))
    c5.metric("Total GMV", fmt_money(k["gmv_total"]))
    c6.metric("Avg GMV / Order (used)", fmt_money(k["avg_gmv_per_order"]))

    c7, c8, c9 = st.columns(3)
    c7.metric("SoldCoupon (sum)", fmt_money(k["sold_coupon_total"]) if pd.notna(k["sold_coupon_total"]) else "-")
    c8.metric("Avg Orders / Customer (used)", f"{k['avg_orders_per_customer']:.2f}" if pd.notna(k["avg_orders_per_customer"]) else "-")
    c9.metric("Rows (filtered)", fmt_int(k["rows"]))

    st.info(
        f"Current order definition: **{order_def}**. "
        "If the dataset is truly order-level, use row-level. If OrderKey duplicates reflect true duplicates or multi-line orders, "
        "Unique OrderKey can be more appropriate."
    )

    st.markdown("---")
    st.subheader("📈 Monthly Trends")

    tr = month_trends(df, use_unique_orderkey)
    if tr.empty:
        st.warning("Not enough valid date data for monthly trends.")
    else:
        colL, colR = st.columns(2)

        orders_chart = (
            alt.Chart(tr)
            .mark_line()
            .encode(
                x=alt.X("YearMonth:N", sort=None, title="Year-Month"),
                y=alt.Y("Orders:Q", title="Orders"),
                tooltip=["YearMonth", "Orders", alt.Tooltip("GMV:Q", format=",.2f")]
            )
            .properties(height=320)
        )

        gmv_chart = (
            alt.Chart(tr)
            .mark_line()
            .encode(
                x=alt.X("YearMonth:N", sort=None, title="Year-Month"),
                y=alt.Y("GMV:Q", title="GMV"),
                tooltip=["YearMonth", alt.Tooltip("GMV:Q", format=",.2f"), "Orders"]
            )
            .properties(height=320)
        )

        with colL:
            st.altair_chart(orders_chart, use_container_width=True)
        with colR:
            st.altair_chart(gmv_chart, use_container_width=True)

        st.caption("If the last month is partial, it may show a drop compared to full months.")
        safe_csv_download(tr, "monthly_trends.csv", "Download monthly trends (CSV)")

    st.markdown("---")
    st.subheader(" Breakdowns")

    left, right = st.columns(2)

    with left:
        st.markdown("### Top 10 Vendors by GMV")
        tv = top_n(df, "VendorKey", "GMV", n=10)
        if tv.empty:
            st.info("VendorKey/GMV missing or not enough data.")
        else:
            tv = tv.rename(columns={"VendorKey": "Vendor", "GMV": "GMV"})
            st.dataframe(tv, use_container_width=True)

            chart_v = (
                alt.Chart(tv)
                .mark_bar()
                .encode(
                    x=alt.X("GMV:Q", title="GMV"),
                    y=alt.Y("Vendor:N", sort="-x", title="Vendor"),
                    tooltip=["Vendor", alt.Tooltip("GMV:Q", format=",.2f")]
                )
                .properties(height=360)
            )
            st.altair_chart(chart_v, use_container_width=True)
            safe_csv_download(tv, "top10_vendors_by_gmv.csv", "Download Top 10 Vendors (CSV)")

    with right:
        st.markdown("### Top 10 Categories by GMV")
        tc = top_n(df, "CategoryID", "GMV", n=10)
        if tc.empty:
            st.info("CategoryID/GMV missing or not enough data.")
        else:
            st.dataframe(tc, use_container_width=True)

            chart_c = (
                alt.Chart(tc)
                .mark_bar()
                .encode(
                    x=alt.X("GMV:Q", title="GMV"),
                    y=alt.Y("CategoryID:N", sort="-x", title="CategoryID"),
                    tooltip=["CategoryID", alt.Tooltip("GMV:Q", format=",.2f")]
                )
                .properties(height=360)
            )
            st.altair_chart(chart_c, use_container_width=True)
            safe_csv_download(tc, "top10_categories_by_gmv.csv", "Download Top 10 Categories (CSV)")


# -----------------------------
# Tab 3: Analysis & Insights
# -----------------------------
with tab3:
    st.subheader(" Analysis & Insights")

    st.markdown("## Task A — Customer Behavior")
    cb = customer_behavior(df, use_unique_orderkey)

    if not cb:
        st.warning("Not enough data for Task A (requires CustomerKey + GMV, and OrderKey if using Unique OrderKey).")
    else:
        a1, a2, a3, a4 = st.columns(4)
        a1.metric("Total customers", fmt_int(cb["total_customers"]))
        a2.metric("One-time customers", fmt_int(cb["one_time_customers"]))
        a3.metric("Repeat customers", fmt_int(cb["repeat_customers"]))
        a4.metric("Repeat %", fmt_pct(cb["repeat_pct"]))

        st.write(
            f"Using **{order_def}**, repeat customers represent **{fmt_pct(cb['repeat_pct'])}** of customers "
            f"but generate **{fmt_pct(cb['repeat_gmv_share'])}** of GMV."
        )

        # Distribution chart: orders per customer (binned)
        cust_orders_series = cb["cust_orders_series"]
        cust_orders_df = cust_orders_series.reset_index()
        cust_orders_df.columns = ["CustomerKey", "OrdersPerCustomer"]

        cust_orders_df["Bin"] = pd.cut(
            cust_orders_df["OrdersPerCustomer"],
            bins=[0, 1, 2, 3, 5, 10, 999999],
            labels=["1", "2", "3", "4-5", "6-10", "11+"],
            include_lowest=True
        )
        dist = cust_orders_df.groupby("Bin", as_index=False).size().rename(columns={"size": "Customers"})

        dist_chart = (
            alt.Chart(dist)
            .mark_bar()
            .encode(
                x=alt.X("Bin:N", title="Orders per customer (binned)"),
                y=alt.Y("Customers:Q", title="Customers"),
                tooltip=["Bin", "Customers"]
            )
            .properties(height=300)
        )
        st.altair_chart(dist_chart, use_container_width=True)
        safe_csv_download(dist, "orders_per_customer_distribution.csv", "Download orders/customer distribution (CSV)")

        # -----------------------------
        # Impact Scenario: Retention Upside
        # -----------------------------
        st.markdown("---")
        st.markdown("###  Retention Upside (Impact Scenarios)")
        st.caption("Directional estimates under a simplifying assumption (not a precise forecast).")

        ret_df = retention_uplift_scenarios(cb, conversion_rates=(0.02, 0.05, 0.10))
        if ret_df.empty:
            st.info("Not enough data to estimate retention uplift scenarios.")
        else:
            ret_disp = ret_df.copy()
            ret_disp["Avg GMV per repeat customer (assumption)"] = ret_disp["Avg GMV per repeat customer (assumption)"].map(lambda x: f"{x:,.2f}")
            ret_disp["Estimated GMV uplift"] = ret_disp["Estimated GMV uplift"].map(lambda x: f"{x:,.2f}")
            st.dataframe(ret_disp, use_container_width=True)
            safe_csv_download(ret_df, "retention_uplift_scenarios.csv", "Download retention uplift scenarios (CSV)")

    st.markdown("---")
    st.markdown("## Task B — Vendor Contribution")
    vc = vendor_contribution(df)

    if not vc:
        st.warning("Not enough data for Task B (requires VendorKey and GMV).")
    else:
        b1, b2, b3, b4 = st.columns(4)
        b1.metric("Vendors", fmt_int(vc["vendor_count"]))
        b2.metric("Top 5 GMV share", fmt_pct(vc["top5_share"]))
        b3.metric("Top 10 GMV share", fmt_pct(vc["top10_share"]))
        b4.metric("Top 20% vendors share", fmt_pct(vc["top20pct_share"]))

        vtable = vc["vendor_table"].copy()
        st.dataframe(vtable.head(25), use_container_width=True)

        vtable2 = vtable.reset_index(drop=True).copy()
        vtable2["Rank"] = np.arange(1, len(vtable2) + 1)

        pareto = (
            alt.Chart(vtable2.head(300))
            .mark_line()
            .encode(
                x=alt.X("Rank:Q", title="Vendor rank (top 300)"),
                y=alt.Y("GMV_cum_share:Q", title="Cumulative GMV share"),
                tooltip=["Rank", alt.Tooltip("GMV_cum_share:Q", format=".2%")]
            )
            .properties(height=320)
        )
        st.altair_chart(pareto, use_container_width=True)
        st.caption("The curve shows how concentrated GMV is among top vendors (Pareto effect).")

        safe_csv_download(vtable, "vendor_contribution_table.csv", "Download vendor contribution table (CSV)")

        # -----------------------------
        # Impact Scenario: Vendor Dependency Risk
        # -----------------------------
        st.markdown("---")
        st.markdown("###  Vendor Dependency Risk (Impact Scenarios)")
        st.caption("Directional estimates under a simplifying assumption (not a precise forecast).")

        risk_df = vendor_loss_scenarios(vc, top_list=(1, 3, 5, 10))
        if risk_df.empty:
            st.info("Not enough data to estimate vendor dependency scenarios.")
        else:
            risk_disp = risk_df.copy()
            risk_disp["GMV at risk"] = risk_disp["GMV at risk"].map(lambda x: f"{x:,.2f}")
            risk_disp["GMV at risk (%)"] = risk_df["GMV at risk (%)"].map(lambda x: f"{x * 100:.2f}%")
            st.dataframe(risk_disp, use_container_width=True)
            safe_csv_download(risk_df, "vendor_dependency_risk_scenarios.csv", "Download vendor dependency scenarios (CSV)")

    # =========================================================
    #  Business Insights 
    # =========================================================
    st.markdown("---")
    st.markdown("##  Business Insights")

    rep_raw = data_quality_report(df_raw)

    # Helper computations for insights
    # Category dominance (Top 2 share + IDs)
    top2_cat_share = np.nan
    top2_cat_ids = []
    
    if "GMV" in df.columns and df["GMV"].notna().any() and "CategoryID" in df.columns:
        total_gmv_current = float(df["GMV"].sum())
        if total_gmv_current > 0:
            cat_tbl = (
                df.groupby("CategoryID", as_index=False)["GMV"]
                .sum()
                .sort_values("GMV", ascending=False)
                .head(2)
            )
            if not cat_tbl.empty:
                top2_cat_share = float(cat_tbl["GMV"].sum() / total_gmv_current)
                top2_cat_ids = cat_tbl["CategoryID"].astype(str).tolist()


    # Campaign-driven pattern (peak GMV month)
    peak_month = None
    tr_ins = month_trends(df, use_unique_orderkey)
    if not tr_ins.empty and "GMV" in tr_ins.columns and tr_ins["GMV"].notna().any():
        peak_row = tr_ins.loc[tr_ins["GMV"].idxmax()]
        peak_month = str(peak_row["YearMonth"])

    # Quantified retention impact from 5% scenario if available
    uplift_5pct = np.nan
    if "ret_df" in locals() and isinstance(ret_df, pd.DataFrame) and not ret_df.empty:
        match = ret_df[ret_df["Scenario"].str.contains("5%", regex=False)]
        if not match.empty:
            uplift_5pct = float(match.iloc[0]["Estimated GMV uplift"])

    insights = []
    
    # Helper: useful numbers for more "human" insights
    orders_rows = k.get("orders_rows", np.nan) if "k" in locals() else np.nan
    orders_unique = k.get("orders_unique", np.nan) if "k" in locals() else np.nan
    
    repeat_pct = cb.get("repeat_pct", np.nan) if cb else np.nan
    repeat_gmv_share = cb.get("repeat_gmv_share", np.nan) if cb else np.nan
    
    top10_share = vc.get("top10_share", np.nan) if vc else np.nan
    top20pct_share = vc.get("top20pct_share", np.nan) if vc else np.nan
    
    # 1) Data Grain Ambiguity
    if rep_raw.get("orderkey_duplicate_row_count") and rep_raw["orderkey_duplicate_row_count"] > 0:
        insights.append(
            f"1) Data Grain Ambiguity (Order definition matters): `OrderKey` is not unique — "
            f"there are ~{rep_raw['orderkey_duplicate_row_count']:,} extra rows beyond unique orders "
            f"(rows: {rep_raw['rows']:,} vs unique OrderKey: {rep_raw['orderkey_unique']:,}). "
            "This strongly suggests the dataset may not be strictly order-level (e.g., duplicated records or multi-line orders). "
            "So KPIs like Orders, AOV, and Orders/Customer can materially change depending on whether we count rows or unique OrderKey. "
            "That’s why the dashboard makes the order definition explicit and user-controlled."
        )
    
    # 2) Refund / Cancellation Handling
    if rep_raw.get("gmv_le_zero") and rep_raw["gmv_le_zero"] > 0:
        insights.append(
            f"2) Refund / Cancellation signals: {rep_raw['gmv_le_zero']:,} rows have `GMV ≤ 0`. "
            "In real commerce data this often indicates cancellations, refunds, chargebacks, or operational adjustments. "
            "If we mix these with positive GMV, revenue trends can be understated and vendor/customer performance can look worse than it is. "
            "Recommendation: keep these rows but flag them (Refund/Cancel indicator) and report Gross GMV vs Net GMV separately."
        )
    
    # 3) Customer Retention Opportunity
    if cb and pd.notna(repeat_pct) and pd.notna(repeat_gmv_share):
        insights.append(
            f"3) Customer Retention Opportunity (high leverage): Repeat customers are only {fmt_pct(repeat_pct)} of the customer base, "
            f"but they generate {fmt_pct(repeat_gmv_share)} of total GMV. "
            "This is a classic 'quality over quantity' signal: repeat buyers are materially more valuable than one-timers. "
            "Practical actions: lifecycle CRM (welcome → second purchase), personalized offers for second order, and win-back for lapsed users."
        )
    
    # 4) Quantified Retention Impact
    if pd.notna(uplift_5pct):
        insights.append(
            f"4) Quantified Retention Upside (directional): A simple scenario shows that converting just 5% of one-time customers into repeat "
            f"could add roughly {fmt_money(uplift_5pct)} GMV. "
            "These are directional impact estimates under a simplifying assumption, meant to quantify upside/risk — "
            "the goal is prioritization, not forecasting accuracy."
        )
    else:
        insights.append(
            "4) Quantified Retention Upside (directional): Even small improvements in repeat rate can create outsized GMV impact. "
            "The scenario table above provides directional impact estimates under a simplifying assumption, meant to quantify upside/risk."
        )
    
    # 5) Vendor Revenue Concentration
    if vc and pd.notna(top10_share):
        insights.append(
            f"5) Vendor Revenue Concentration (opportunity + dependency risk): The top 10 vendors contribute about {fmt_pct(top10_share)} of total GMV. "
            "This indicates meaningful dependency on a small supplier set. "
            "Opportunity: develop strategic partnerships (exclusive deals, better placements, joint campaigns) with top vendors. "
            "Risk: losing even 1–2 key vendors can create an immediate revenue shock — mitigation includes vendor retention programs and pipeline diversification."
        )
    
    # 6) Long-tail / 80-20 dynamic (Vendor portfolio)
    if vc and pd.notna(top20pct_share):
        insights.append(
            f"6) Long-tail economics (vendor portfolio): The top 20% of vendors generate ~{fmt_pct(top20pct_share)} of GMV, "
            "which means the remaining 80% contribute very little in aggregate. "
            "This raises an operational question: are we spending disproportionate support/ops cost on low-value tail vendors? "
            "Next step: segment vendors (top/mid/long tail) and align account management effort with revenue potential."
        )
    
    # 7) Category Dominance
    if pd.notna(top2_cat_share) and len(top2_cat_ids) == 2:
        insights.append(
            f"7) Category Dominance (product concentration): Categories {top2_cat_ids[0]} and {top2_cat_ids[1]} "
            f"together account for {fmt_pct(top2_cat_share)} of GMV. "
            "This indicates meaningful product mix concentration. "
            "If demand or supply in these categories shifts, overall revenue performance could be materially impacted. "
            "Recommendation: evaluate diversification and category-level growth experiments."
        )
    else:
        insights.append(
            "7) Category Dominance: GMV appears concentrated in a small number of categories. "
            "Quantifying top category shares can guide diversification strategy."
        )

            
    
    # 8) Campaign-driven month spike
    if peak_month:
        insights.append(
            f"8) Campaign/Event-driven growth signal: {peak_month} is the highest GMV month, and the charts show a visible spike in both Orders and GMV. "
            "This pattern is often campaign-driven rather than purely organic. "
            "Next step: validate by linking to campaign calendars/promotions and measuring incrementality (lift vs baseline)."
        )
    else:
        insights.append(
            "8) Campaign/Event-driven growth signal: Monthly trends show variability; identifying spike months helps separate campaign lift from baseline demand."
        )
    
    # 9) Structural Recommendation (Data Mart)
    insights.append(
        "9) Structural Recommendation (scalability + consistency): Build an analytics-ready data mart "
        "(FactOrders with DimDate/DimCustomer/DimVendor/DimCategory). "
        "This will standardize KPI definitions, resolve grain ambiguity, and improve dashboard performance. "
        "It also makes it easier to add advanced analyses later (cohorts, retention curves, attribution, and vendor/category segmentation)."
    )
    
    for it in insights:
        st.write(it)


    st.markdown("---")
    st.subheader("Submission Notes")
    st.markdown(
        """
- This app computes every metric on the **cleaned + filtered** dataset.
- The app also supports two order-counting approaches:
  - Row-level (matches the common assumption "each row is an order")
  - Unique OrderKey (useful when OrderKey duplicates exist)
- Recommended deliverables:
  - `app.py`
  - `requirements.txt`
  - `README.md` (how to run, KPI definitions, data issues found)
"""
    )

st.markdown("---")
st.caption("Built with Streamlit • KPI-driven analytics • Clean + Filter aware")
