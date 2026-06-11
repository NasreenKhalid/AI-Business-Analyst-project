import streamlit as st
import pandas as pd
import plotly.express as px

st.title("AI Business Analyst")

uploaded_file = st.file_uploader("Upload a CSV file", type=["csv"])

if uploaded_file is not None:
    # Auto-detect separator and handle index column
    import io
    raw = uploaded_file.read().decode('utf-8')
    uploaded_file.seek(0)

    first_line = raw.split('\n')[0]
    if ',' in first_line:
        sep = ','
    elif '\t' in first_line:
        sep = '\t'
    else:
        sep = r'\s+'

    df = pd.read_csv(io.StringIO(raw), sep=sep, engine='python')

    # Drop row-number index column if present (e.g. 0,1,2,3...)
    first_col = df.iloc[:, 0]
    try:
        if (pd.to_numeric(first_col, errors='coerce').notna().all() and
                list(first_col.astype(int)) == list(range(len(df)))):
            df = df.iloc[:, 1:]
    except Exception:
        pass

    # Clean column names (strip extra spaces)
    df.columns = df.columns.str.strip()

    # For any column that looks numeric but is stored as text, clean and convert
    for col in df.columns:
        if df[col].dtype == object:
            cleaned = df[col].astype(str).str.strip().str.replace(r'[\$,]', '', regex=True)
            converted = pd.to_numeric(cleaned, errors='coerce')
            # If 80%+ of values converted successfully, treat it as numeric
            if converted.notna().sum() / len(df) > 0.8:
                df[col] = converted

    st.write("### Dataset Preview")
    st.dataframe(df)

    # --- Column Detection ---
    numeric_cols = df.select_dtypes(include='number').columns.tolist()
    categorical_cols = df.select_dtypes(include='object').columns.tolist()

    date_cols = []
    for col in df.columns:
        if df[col].dtype == "object":
            try:
                converted = pd.to_datetime(df[col])
                if converted.notna().sum() / len(df) > 0.8:
                    date_cols.append(col)
                    df[col] = pd.to_datetime(df[col])  # convert in-place
            except Exception:
                pass

    # Remove detected date columns from categorical
    categorical_cols = [col for col in categorical_cols if col not in date_cols]

    with st.expander("Detected Columns"):
        st.write(f"**Numeric:** {numeric_cols}")
        st.write(f"**Categorical:** {categorical_cols}")
        st.write(f"**Date:** {date_cols}")

    # --- Auto-detect best metric and category columns ---
    metric_keywords = ["revenue", "sales", "amount", "profit", "income", "earnings", "price", "total", "cost"]

    metric_col = None
    for col in numeric_cols:
        if any(keyword in col.lower() for keyword in metric_keywords):
            metric_col = col
            break
    if metric_col is None and len(numeric_cols) > 0:
        metric_col = numeric_cols[0]

    category_col = None
    if len(categorical_cols) > 0:
        category_col = categorical_cols[0]

    date_col = date_cols[0] if date_cols else None

    # --- Guard: need at least a metric column to proceed ---
    if metric_col is None:
        st.warning("No numeric columns detected. Please upload a CSV with numeric data.")
        st.stop()

    st.write(f"**Metric Column:** `{metric_col}` | **Category Column:** `{category_col}` | **Date Column:** `{date_col}`")

    # --- KPI Metrics ---
    st.subheader("KPI Metrics")

    total_metric = df[metric_col].sum()
    total_orders = len(df)
    avg_metric = df[metric_col].mean()

    if category_col:
        num_categories = df[category_col].nunique()
        col1, col2, col3, col4 = st.columns(4)
        col4.metric(f"Unique {category_col}", num_categories)
    else:
        col1, col2, col3 = st.columns(3)

    col1.metric(f"Total {metric_col}", f"{total_metric:,.2f}")
    col2.metric("Total Rows", total_orders)
    col3.metric(f"Avg {metric_col}", f"{avg_metric:,.2f}")

    # --- AI Insights (Rule-Based, No API) ---
    st.subheader("🤖 AI Insights")

    insights = []

    if category_col:
        group = df.groupby(category_col)[metric_col].sum().sort_values(ascending=False)
        total = group.sum()
        avg_cat = group.mean()

        # 1. Top Performer
        top_name = group.index[0]
        top_val = group.iloc[0]
        top_pct = (top_val / total) * 100
        insights.append(("🏆 Top Performer", f"{top_name} is the highest performing {category_col} with {metric_col} of {top_val:,.2f}, contributing {top_pct:.1f}% of total revenue."))

        # 2. Lowest Performer
        low_name = group.index[-1]
        low_val = group.iloc[-1]
        low_pct = (low_val / total) * 100
        insights.append(("⚠️ Lowest Performer", f"{low_name} is the weakest {category_col} with only {low_val:,.2f} in {metric_col} ({low_pct:.1f}% of total). Consider investigating or reallocating resources."))

        # 3. Contribution %
        top3 = group.head(3)
        top3_pct = (top3.sum() / total) * 100
        top3_names = ", ".join(top3.index.tolist())
        insights.append(("📊 Contribution %", f"The top 3 {category_col}s ({top3_names}) account for {top3_pct:.1f}% of total {metric_col} ({top3.sum():,.2f} out of {total:,.2f})."))

        # 4. Above Average Categories
        above_avg = group[group > avg_cat]
        below_avg = group[group <= avg_cat]
        above_names = ", ".join(above_avg.index.tolist())
        insights.append(("📈 Above Average Categories", f"{len(above_avg)} out of {len(group)} {category_col}s are above average ({avg_cat:,.2f}): {above_names}. The remaining {len(below_avg)} are below average and may need attention."))

        # 5. Business Concentration
        top1_pct = (top_val / total) * 100
        if top1_pct > 40:
            concentration_msg = f"High concentration risk — {top_name} alone drives {top1_pct:.1f}% of total {metric_col}. Over-reliance on a single {category_col} is a business risk."
        elif top3_pct > 70:
            concentration_msg = f"Moderate concentration — top 3 {category_col}s generate {top3_pct:.1f}% of revenue. Business is somewhat dependent on a few key performers."
        else:
            concentration_msg = f"Revenue is well distributed across {category_col}s. No single {category_col} dominates, suggesting a healthy, diversified business."
        insights.append(("🎯 Business Concentration", concentration_msg))

    else:
        # No category column — show numeric summary insights
        insights.append(("📊 Total", f"Total {metric_col}: {total_metric:,.2f} across {len(df)} records."))
        insights.append(("📈 Average", f"Average {metric_col} per record: {avg_metric:,.2f}."))
        max_val = df[metric_col].max()
        min_val = df[metric_col].min()
        insights.append(("🏆 Range", f"{metric_col} ranges from {min_val:,.2f} (lowest) to {max_val:,.2f} (highest)."))

    # Render insights as styled cards
    for title, text in insights:
        st.markdown(
            f'''<div style="background:#f0f4ff;border-left:4px solid #4a6cf7;
            padding:14px 18px;border-radius:8px;margin-bottom:10px;line-height:1.7">
            <strong>{title}</strong><br>{text}
            </div>''',
            unsafe_allow_html=True
        )

    # --- Bar Chart: Metric by Category ---
    if category_col:
        st.subheader(f"{metric_col} by {category_col}")
        chart_data = (
            df.groupby(category_col)[metric_col]
            .sum()
            .reset_index()
            .sort_values(metric_col, ascending=False)
        )
        fig = px.bar(
            chart_data,
            x=category_col,
            y=metric_col,
            title=f"{metric_col} by {category_col}",
            color=metric_col,
            color_continuous_scale="Blues"
        )
        st.plotly_chart(fig, use_container_width=True)

        # Pie chart
        st.subheader(f"{metric_col} Share by {category_col}")
        fig_pie = px.pie(
            chart_data,
            names=category_col,
            values=metric_col,
            title=f"{metric_col} Share by {category_col}"
        )
        st.plotly_chart(fig_pie, use_container_width=True)
    else:
        st.info("No categorical column detected — skipping bar and pie charts.")

    # --- Time Trend Chart ---
    if date_col:
        st.subheader(f"{metric_col} Trend Over Time")
        trend_data = (
            df.groupby(date_col)[metric_col]
            .sum()
            .reset_index()
            .sort_values(date_col)
        )
        fig2 = px.line(
            trend_data,
            x=date_col,
            y=metric_col,
            title=f"{metric_col} Over Time",
            markers=True
        )
        st.plotly_chart(fig2, use_container_width=True)
    else:
        st.info("No date column detected — skipping time trend chart.")
