"""
Retail Profitability & Inventory Health — Analysis Script
Dataset: Sample Superstore (Kaggle), 9,994 order-line rows, 2014-2017
Author: Afrin

Run: python3 analysis.py
Produces: cleaned_superstore.csv, kpis.json, insight.json (all consumed by dashboard.html)
"""
import pandas as pd
import numpy as np
import json
from scipy import stats

pd.set_option("display.width", 140)

# ---------------------------------------------------------------
# PHASE 2 — LOAD & CLEAN
# ---------------------------------------------------------------
xl = pd.ExcelFile("superstore_raw.xls")
df = xl.parse(xl.sheet_names[0])

# 1. Fix dtypes
df["Order Date"] = pd.to_datetime(df["Order Date"])
df["Ship Date"] = pd.to_datetime(df["Ship Date"])
df["Postal Code"] = df["Postal Code"].astype(str).str.zfill(5)  # postal codes are identifiers, not numbers

# 2. Real-world messy-quirk fix (non-hand-held step, documented explicitly):
#    A handful of Furniture "Tables" and "Bookcases" lines carry heavy negative-profit
#    outliers driven by deep discounting (Discount >= 0.5). These are real, not data errors,
#    but they skew a naive category-average margin badly enough to mislead a reader who
#    doesn't see the distribution. We keep every row (nothing is dropped — that would be
#    hiding the actual problem), but we flag them so the dashboard can show "underlying"
#    vs "discount-distorted" margin side by side instead of one misleading blended number.
df["Heavy_Discount_Flag"] = df["Discount"] >= 0.5

# 3. Remove exact duplicate rows / fully blank rows (none found here, but the check is real)
before = len(df)
df = df.drop_duplicates()
df = df.dropna(how="all")
dupes_removed = before - len(df)

# 4. Derived fields
df["Ship_Delay_Days"] = (df["Ship Date"] - df["Order Date"]).dt.days
df["Order_Month"] = df["Order Date"].dt.to_period("M").astype(str)
df["Order_Year"] = df["Order Date"].dt.year
df["Profit_Margin"] = df["Profit"] / df["Sales"]

df.to_csv("cleaned_superstore.csv", index=False)

# ---------------------------------------------------------------
# PHASE 3 — CORE KPIs
# ---------------------------------------------------------------
total_sales = df["Sales"].sum()
total_profit = df["Profit"].sum()
overall_margin = total_profit / total_sales

by_year = df.groupby("Order_Year").agg(Sales=("Sales", "sum"), Profit=("Profit", "sum")).reset_index()
by_year["Margin"] = by_year["Profit"] / by_year["Sales"]
by_year["YoY_Sales_Growth"] = by_year["Sales"].pct_change()

monthly = df.groupby("Order_Month").agg(Sales=("Sales", "sum"), Profit=("Profit", "sum")).reset_index()
monthly["Margin"] = monthly["Profit"] / monthly["Sales"]

# ---------------------------------------------------------------
# CATEGORY / SUB-CATEGORY DEEP DIVE
# ---------------------------------------------------------------
cat = df.groupby("Category").agg(
    Sales=("Sales", "sum"), Profit=("Profit", "sum"), Orders=("Order ID", "nunique"), Qty=("Quantity", "sum")
).reset_index()
cat["Margin"] = cat["Profit"] / cat["Sales"]

subcat = df.groupby(["Category", "Sub-Category"]).agg(
    Sales=("Sales", "sum"), Profit=("Profit", "sum"), Qty=("Quantity", "sum"), Orders=("Order ID", "nunique")
).reset_index()
subcat["Margin"] = subcat["Profit"] / subcat["Sales"]
subcat_sorted = subcat.sort_values("Margin")

# ---------------------------------------------------------------
# STOCKOUT-RISK PROXY (no real inventory data exists — documented explicitly)
# Proxy logic: sub-categories with HIGH order frequency (many distinct orders) but
# LOW average quantity per order line are the ones most likely to be sold through
# fast and restocked reactively -> higher real-world stockout risk.
# We rank by (order frequency rank) - (avg qty per line rank): high freq + low qty = high risk.
# ---------------------------------------------------------------
freq = df.groupby("Sub-Category").agg(
    Order_Lines=("Row ID", "count"),
    Avg_Qty_Per_Line=("Quantity", "mean"),
    Total_Qty=("Quantity", "sum"),
    Sales=("Sales", "sum"),
).reset_index()
freq["Freq_Rank"] = freq["Order_Lines"].rank(ascending=False)
freq["LowQty_Rank"] = freq["Avg_Qty_Per_Line"].rank(ascending=True)
freq["Stockout_Risk_Score"] = (freq["Freq_Rank"] + freq["LowQty_Rank"]) / 2
freq_sorted = freq.sort_values("Stockout_Risk_Score")

# ---------------------------------------------------------------
# REGIONAL MATRIX
# ---------------------------------------------------------------
region = df.groupby("Region").agg(Sales=("Sales", "sum"), Profit=("Profit", "sum")).reset_index()
region["Margin"] = region["Profit"] / region["Sales"]

region_cat = df.groupby(["Region", "Category"]).agg(Sales=("Sales", "sum"), Profit=("Profit", "sum")).reset_index()
region_cat["Margin"] = region_cat["Profit"] / region_cat["Sales"]

# ---------------------------------------------------------------
# PHASE 7 — COUNTER-INTUITIVE FINDING + STAT TEST
# Hypothesis to test in data: "Furniture" *looks* like a margin problem overall,
# but is the margin gap between Furniture and the best category (Technology) actually
# driven by a small number of heavily-discounted Tables/Bookcases lines, or is it
# a real, broad-based, statistically significant gap across ALL its lines?
# ---------------------------------------------------------------
furniture_margins = df.loc[df["Category"] == "Furniture", "Profit_Margin"]
technology_margins = df.loc[df["Category"] == "Technology", "Profit_Margin"]

t_stat, p_val = stats.ttest_ind(technology_margins, furniture_margins, equal_var=False, nan_policy="omit")

# Also check: if we exclude the heavily-discounted (>=50%) lines, does Furniture's
# margin problem disappear, or is it structural?
furn_no_heavy_discount = df[(df["Category"] == "Furniture") & (~df["Heavy_Discount_Flag"])]
furn_margin_all = df.loc[df["Category"] == "Furniture", "Profit"].sum() / df.loc[df["Category"] == "Furniture", "Sales"].sum()
furn_margin_ex_heavy = furn_no_heavy_discount["Profit"].sum() / furn_no_heavy_discount["Sales"].sum()

heavy_discount_lines = df["Heavy_Discount_Flag"].sum()
heavy_discount_furniture_lines = df[(df["Category"] == "Furniture") & (df["Heavy_Discount_Flag"])].shape[0]
heavy_discount_loss = df.loc[df["Heavy_Discount_Flag"], "Profit"].sum()

# Tables specifically (worst sub-category)
tables = subcat[subcat["Sub-Category"] == "Tables"].iloc[0]

# Bootcamp headline number: monthly loss run-rate from Tables' negative margin
tables_rows = df[df["Sub-Category"] == "Tables"]
tables_monthly_loss = tables_rows.groupby("Order_Month")["Profit"].sum()
avg_monthly_tables_loss = tables_monthly_loss[tables_monthly_loss < 0].mean()

print("=== OVERALL ===")
print(f"Total Sales: {total_sales:,.2f}")
print(f"Total Profit: {total_profit:,.2f}")
print(f"Overall Margin: {overall_margin:.2%}")
print()
print("=== BY YEAR ===")
print(by_year)
print()
print("=== CATEGORY ===")
print(cat)
print()
print("=== WORST SUBCATEGORIES BY MARGIN ===")
print(subcat_sorted.head(5)[["Category", "Sub-Category", "Sales", "Profit", "Margin"]])
print()
print("=== STOCKOUT RISK (top 5 highest risk) ===")
print(freq_sorted.head(5)[["Sub-Category", "Order_Lines", "Avg_Qty_Per_Line", "Stockout_Risk_Score"]])
print()
print("=== REGION ===")
print(region)
print()
print("=== STAT TEST: Technology vs Furniture margin (Welch t-test) ===")
print(f"t = {t_stat:.3f}, p = {p_val:.6f}")
print()
print("=== TABLES SUB-CATEGORY ===")
print(tables)
print(f"Avg monthly loss (loss months only): {avg_monthly_tables_loss:.2f}")
print()
print(f"Furniture margin (all lines): {furn_margin_all:.2%}")
print(f"Furniture margin (excl. >=50% discount lines): {furn_margin_ex_heavy:.2%}")
print(f"Heavy-discount (>=50%) lines: {heavy_discount_lines} total, {heavy_discount_furniture_lines} in Furniture")
print(f"Total profit lost on heavy-discount lines: {heavy_discount_loss:,.2f}")
print(f"Duplicate rows removed: {dupes_removed}")

# ---------------------------------------------------------------
# SAVE EVERYTHING THE DASHBOARD NEEDS
# ---------------------------------------------------------------
output = {
    "total_sales": round(total_sales, 2),
    "total_profit": round(total_profit, 2),
    "overall_margin": round(overall_margin, 4),
    "by_year": by_year.to_dict(orient="records"),
    "monthly": monthly.to_dict(orient="records"),
    "category": cat.to_dict(orient="records"),
    "subcategory": subcat.sort_values("Margin").to_dict(orient="records"),
    "stockout_risk": freq_sorted.to_dict(orient="records"),
    "region": region.to_dict(orient="records"),
    "region_category": region_cat.to_dict(orient="records"),
    "stat_test": {
        "t_stat": round(float(t_stat), 3),
        "p_value": float(p_val),
        "tech_mean_margin": round(float(technology_margins.mean()), 4),
        "furniture_mean_margin": round(float(furniture_margins.mean()), 4),
    },
    "insight": {
        "furniture_margin_all": round(furn_margin_all, 4),
        "furniture_margin_ex_heavy_discount": round(furn_margin_ex_heavy, 4),
        "heavy_discount_lines_total": int(heavy_discount_lines),
        "heavy_discount_lines_furniture": int(heavy_discount_furniture_lines),
        "heavy_discount_total_profit_lost": round(float(heavy_discount_loss), 2),
        "tables_sales": round(float(tables["Sales"]), 2),
        "tables_profit": round(float(tables["Profit"]), 2),
        "tables_margin": round(float(tables["Margin"]), 4),
        "avg_monthly_tables_loss": round(float(avg_monthly_tables_loss), 2),
    },
    "dupes_removed": int(dupes_removed),
    "row_count": int(len(df)),
}

with open("data.json", "w") as f:
    json.dump(output, f, indent=2, default=str)

print("\nSaved cleaned_superstore.csv and data.json")
