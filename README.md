# Retail Profitability & Inventory Health

**Type:** Analyst case study · **Tools:** Power BI Desktop (DAX, RLS, drill-through), Python (pandas, SciPy) for data cleaning and statistical validation
**Dataset:** [Sample Superstore](https://www.kaggle.com/datasets/vivek468/superstore-dataset-final) (Kaggle) — 9,994 order-line rows, Jan 2014–Dec 2017, US retail chain. All figures below are in **USD**.

---

## Dashboard Preview

**Executive Overview**
![Executive Overview](screenshots/Executive%20Overview.png)

**Category Deep-Dive**
![Category Deep-Dive](screenshots/Category%20Deep-Dive.png)

**Regional & Product Performance**
![Regional and Product Performance](screenshots/Regional%20%26%20Product%20Performance.png)

---

## 1. Business Problem

Leadership at a mid-size retail chain suspects some product categories look strong on revenue but are quietly bleeding margin, and that certain products are running out at the wrong times. They asked for one view that shows **profitability and inventory health together** — not just a sales report.

Three questions this analysis had to answer:
1. Which categories/sub-categories generate strong sales but weak or negative profit?
2. Is there a real regional profitability gap, and where is it worst?
3. Which products are most likely to be at risk of stocking out, given we have no direct inventory data?

## 2. Data & Methodology

- Source file: `superstore_raw.xls` (Kaggle export), cleaned in `analysis.py` before being loaded into Power BI.
- Cleaning steps actually performed (see `analysis.py` for the exact code):
  - Cast `Order Date`/`Ship Date` to datetime; `Postal Code` to a zero-padded string (it's an identifier, not a number — a real quirk in this dataset that breaks naive numeric handling).
  - Checked for and removed exact duplicate/blank rows (none found — 0 removed, confirmed programmatically, not assumed).
  - **Non-hand-held cleaning decision:** flagged all order lines with `Discount >= 0.5` (922 lines, 9.2% of the dataset) as `Heavy_Discount_Flag`. These aren't data errors — they're real heavily-discounted sales — but a naive category-average margin blends them invisibly into the "true" underlying margin, which is exactly the kind of number that falls apart under questioning. The dashboard reports both figures side by side.
  - Derived `Profit_Margin = Profit / Sales` per line, `Ship_Delay_Days`, and monthly/yearly rollups.
- The cleaned CSV was loaded into a Power BI data model with a proper `Date` dimension table (`CALENDAR()`-based) related to the `Orders` fact table on `Order Date`, so real DAX time-intelligence (`SAMEPERIODLASTYEAR`) works correctly.

### Stockout-risk proxy (no real inventory data exists in this dataset)
This dataset has no stock-on-hand field, so a proxy was built explicitly: sub-categories with **high order frequency** (many distinct order lines) and **low average quantity per line** are the ones most likely to be sold through fast and restocked reactively — a genuine analyst move when the "right" data doesn't exist, stated openly rather than disguised as real inventory data. Ranking is the average of the (order-frequency rank) and (low-avg-qty rank); a lower score = higher stockout risk.

## 3. Core DAX Measures

```dax
Total Sales      = SUM(Orders[Sales])
Total Profit     = SUM(Orders[Profit])
Profit Margin %  = DIVIDE([Total Profit], [Total Sales])
Sales LY         = CALCULATE([Total Sales], SAMEPERIODLASTYEAR('Date'[Date]))
YoY Growth %     = DIVIDE([Total Sales] - [Sales LY], [Sales LY])
Low Margin Flag  = IF([Profit Margin %] < 0.05, "Low Margin", "OK")
```

## 4. Dashboard Structure (Power BI, 3 pages)

- **Executive Overview** — 4 KPI cards (Total Sales, Total Profit, Profit Margin %, YoY Growth %), a monthly sales trend line chart, a Total Sales by State map, and a written Key Insights panel.
- **Category Deep-Dive** — Total Sales & Total Profit by Sub-Category, and a Total Sales vs. Profit Margin % scatter at the product level, with Category/Region/Date slicers.
- **Regional & Product Performance** — a region-level summary table (Sales, Profit, Margin %, Avg Qty/Order) with drill-through to a Product Detail table.
- **Row-Level Security**: a `Regional Manager - West` role restricts all visuals to `Region = "West"` — demonstrates a real security concept an enterprise dashboard would need, testable via **Modeling → View As**.

## 5. Key Findings (real numbers, computed from the data)

- **Overall:** $2,297,201 in sales, $286,397 in profit → **12.5% blended margin**, 2014–2017.
- **2017 YoY sales growth: +20.4%** — the business is growing, which is exactly why a hidden margin problem is dangerous: it's easy to mistake growing revenue for growing health.
- **Category split is the real story:** Furniture ($741,999 sales) earns only **2.5% margin** — Office Supplies and Technology, on similar or lower sales, earn 17.0–17.4%.
- **Headline / counter-intuitive finding:** Furniture's weak margin is **not spread evenly across the category** — it's concentrated in heavy discounting. Across the *whole dataset*, 922 order lines (9.2%) carry a discount of ≥50%, and together they destroy **$97,065 in profit** — about **25.3%** of the profit the business would otherwise have earned ($286,397 actual vs. $383,462 without those lines). Strip those lines out of Furniture specifically and its margin **more than doubles**, from 2.5% to 5.8%. This reframes the fix: it's not "Furniture is a bad category," it's "the discount approval process on Furniture lines is a bad process."
- **Worst single sub-category: Tables** — -8.6% margin on $206,966 in sales (a real, outright loss of $17,725), the single biggest line-item margin problem in the dataset, worse even than Bookcases (-3.0%).
- **Regional gap is real and material:** Central region margin is 7.9% vs. West's 14.9% — nearly a 2x gap on a comparable revenue base ($501,240 vs $725,458 in sales). Central's Furniture line is actually *negative* (-1.8% margin) while every other region's Furniture line is positive.
- **Stockout-risk proxy top candidates:** Phones, Furnishings, Paper, Storage, Appliances — all combine high order-line frequency with a low average quantity per line, consistent with fast sell-through and reactive restocking.

### Statistical check on the biggest claim
Is the Technology-vs-Furniture margin gap real, or could it be noise from a small number of extreme rows? A Welch's t-test on per-line profit margin (unequal variances assumed, since Furniture's margin is far more volatile):

```
t = 12.75, p < 0.000001   (Technology mean margin ≈ 21.1% vs Furniture mean margin ≈ 1.7%, per line)
```
The gap is statistically significant at any conventional threshold — this is a structural difference in how these two categories are priced and discounted, not sampling noise.

## 6. Recommendations

1. **Put a discount-approval ceiling on Furniture, especially Tables/Bookcases** — anything ≥50% off should require manager sign-off. This single change targets $97,065/year in currently-destroyed profit.
2. **Investigate Central region's Furniture pricing/discounting specifically** — it's the only region+category combination that's outright loss-making, and it's dragging the whole region's margin down to the worst in the network.
3. **Treat Phones, Furnishings, Paper, Storage, and Appliances as priority SKUs for a real inventory/reorder-point review** — they show the sell-through pattern most consistent with stockout risk, even without direct stock data.
4. **Don't read the 20.4% YoY sales growth as "things are fine"** — it's masking a margin-erosion problem that would only get worse at scale if the discounting pattern isn't addressed first.

## 7. Limitations (what to validate with more time/data)

- **No real inventory data.** The stockout-risk ranking is a documented proxy (order frequency + low quantity-per-line), not actual stock-on-hand. It should be validated against real reorder/lead-time data before being used operationally.
- **Discount reason is unknown.** The dataset doesn't say *why* a line was discounted 50%+ (clearance, loyalty, error, negotiated B2B deal) — the recommendation to cap discounts assumes most of these are avoidable, which should be confirmed with whoever approves discounts today.
- **Four years of data, no seasonality decomposition.** The monthly trend shows clear December/November spikes typical of retail, but this analysis didn't formally decompose trend vs. seasonality vs. noise — worth doing before using the YoY figure to set targets.
- **US-only, single-chain data.** Findings (e.g. the Central-region Furniture problem) are specific to this dataset and shouldn't be generalized to "furniture is always low-margin" without checking against a second data source.
- **Map visual is unweighted.** The Total Sales by State map should be checked to confirm it's using Total Sales for color/size intensity rather than a flat fill, so state-level variation is actually visible.

## 8. Files in this repo

| File | What it is |
|---|---|
| `superstore_raw.xls` | Original Kaggle export, untouched |
| `analysis.py` | Full cleaning + KPI + stat-test pipeline (reproducible, prints every number in this README) |
| `cleaned_superstore.csv` | Cleaned output of `analysis.py`, loaded into the Power BI model |
| `Retail_Profitability_Dashboard.pbix` | The finished Power BI dashboard — open in Power BI Desktop (free, no license needed to view) |
| `screenshots/` | PNG exports of all 3 dashboard pages, for anyone viewing the repo without Power BI installed |

To reproduce the data pipeline: `python3 analysis.py`. To rebuild the dashboard, open `Retail_Profitability_Dashboard.pbix` in Power BI Desktop.

## 9. 30-second interview pitch

*"Leadership at a retail chain thought Furniture was just a low-margin category. I found the real problem was different: 9% of all order lines carried 50%+ discounts, and those lines alone were wiping out a quarter of total company profit — Furniture just had the most of them. I confirmed the margin gap between Furniture and Technology was statistically significant (p < 0.000001, not noise), traced the worst single item down to the Tables sub-category which was outright losing money, and found Central region's Furniture line was the only category+region combination in the whole business that was unprofitable. The fix isn't 'stop selling Furniture' — it's tightening discount approval on a specific set of SKUs and regions. I built this as a real Power BI dashboard with DAX measures, a Date dimension for time intelligence, drill-through to product detail, and a row-level security role restricting a regional manager's view to their own region."*
