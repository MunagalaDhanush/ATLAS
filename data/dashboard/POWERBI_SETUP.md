# ATLAS — Power BI Dashboard Setup Guide

## Prerequisites
- Power BI Desktop (free, download from microsoft.com/en-us/power-bi/desktop)
- All 6 CSV files present in this folder (`data/dashboard/`)

---

## Step 1 — Import Each CSV File

In Power BI Desktop, repeat for each of the 6 files:

1. **Home** > **Get Data** > **Text/CSV**
2. Navigate to `data/dashboard/` and select the file
3. Power BI will preview the data. Confirm **delimiter = Comma** and **first row as headers = Yes**
4. Click **Load** (not Transform — data is already clean)

Import in this order:
| # | File | Table Name in Power BI |
|---|------|------------------------|
| 1 | `Friction Hotspots.csv` | `Friction Hotspots` |
| 2 | `KPI Weekly Trend.csv` | `KPI Weekly Trend` |
| 3 | `KPI Alerts.csv` | `KPI Alerts` |
| 4 | `LLM Theme Summary.csv` | `LLM Theme Summary` |
| 5 | `Customer Journeys.csv` | `Customer Journeys` |
| 6 | `Segment Cuts.csv` | `Segment Cuts` |

---

## Step 2 — Set Column Data Types

After importing, open **Power Query Editor** (Home > Transform Data) and verify:

**KPI Weekly Trend:**
- `Week` → Date

**Customer Journeys:**
- `Is Friction` → True/False
- `Resolved` → True/False
- `Friction Score` → Decimal Number
- `Duration Hours` → Decimal Number

**KPI Alerts:**
- `Alert Fired` → True/False
- `Current Value`, `Forecast Value`, `Change Pct` → Decimal Number

Click **Close & Apply** when done.

---

## Step 3 — Define Table Relationships

Go to **Model** view (left sidebar, third icon). Create these relationships by dragging:

| From Table | From Column | To Table | To Column | Cardinality |
|-----------|-------------|----------|-----------|-------------|
| `Customer Journeys` | `Product` | `Friction Hotspots` | `Product` | Many-to-Many |
| `KPI Weekly Trend` | `Week` (date) | — | — | (no direct join — use as standalone fact table) |
| `KPI Alerts` | `KPI` | — | — | (standalone lookup table for cards) |

> **Note on LLM Theme Summary:** There is no direct key join between `Customer Journeys` and `LLM Theme Summary`. The theme data was extracted from a 500-row sample. Use `LLM Theme Summary` as a standalone visual source (bar chart, table). Cross-filter is not reliable without an explicit join key.

> **Note on Segment Cuts:** Use `Segment Label` as a slicer to filter between the 3 pre-built segments. The table is denormalized and self-contained — no relationships needed.

---

## Step 4 — Apply Dashboard Color Theme

Go to **View** > **Themes** > **Customize current theme** and enter:

```
Background:  #0A0F1E
Font:        #F0F4FF
Accent:      #4DA6FF
Warning:     #F0A500
Critical:    #E05555
```

For a quick import: create a JSON file named `atlas_theme.json` with:
```json
{
  "name": "ATLAS Dark",
  "dataColors": ["#4DA6FF","#F0A500","#E05555","#00C49A","#9B59B6","#E67E22"],
  "background": "#0A0F1E",
  "foreground": "#F0F4FF",
  "tableAccent": "#4DA6FF"
}
```
Then **View** > **Themes** > **Browse for themes** and select the file.

---

## Step 5 — Build Each Visual

### Visual 1 — Priority Score by Product + Region (Clustered Bar Chart)

1. Insert > **Clustered Bar Chart**
2. Source table: `Friction Hotspots`
3. Y-axis: `Product` (drag in, then also drag `Region` beneath it for grouping)
4. X-axis: `Priority Score`
5. Values: `Priority Score` (set aggregation to **Sum** — each row is a unique segment)
6. Filter pane: Add `Priority Score` filter > Top N > **Top 10** > by `Priority Score`
7. Sort: Click the visual > **...** > Sort by **Priority Score** > Descending
8. Format > Data labels: On | Color: `#F0F4FF`
9. Title: `Friction Hotspot Priority — Top 10 Segments`

---

### Visual 2 — Friction Rate & NPS Over Time (Dual-Axis Line Chart)

1. Insert > **Line chart**
2. Source table: `KPI Weekly Trend`
3. X-axis: `Week`
4. Line Y-axis (primary): `Friction Rate`
5. Line Y-axis (secondary): `NPS Score`
   - To add secondary axis: Format > Y-axis > turn on **Secondary Y-axis** > assign `NPS Score` to it
6. Format > Colors: Friction Rate = `#E05555` | NPS Score = `#4DA6FF`
7. Title: `Weekly KPI Trend — Friction Rate vs NPS Score`
8. Add a **reference line** at Friction Rate = 0.025 (the designed baseline):
   Analytics pane > Constant Line > Value: 0.025 | Color: `#F0A500` | Dashed

---

### Visual 3 — KPI Summary Cards (4 Cards)

For each metric, insert a **Card** visual:

| Card | Table | Field | Aggregation | Format |
|------|-------|-------|-------------|--------|
| Friction Rate | `KPI Weekly Trend` | `Friction Rate` | Last value | 3 decimal places |
| NPS Score | `KPI Weekly Trend` | `NPS Score` | Last value | 1 decimal place |
| Escalation Rate | `KPI Weekly Trend` | `Escalation Rate` | Last value | 3 decimal places |
| Resolution Rate | `KPI Weekly Trend` | `Resolution Rate` | Last value | 3 decimal places |

> To get "last value" (most recent week): In Power Query, add a custom column or use a DAX measure:
> ```
> Latest Friction Rate = LASTNONBLANK('KPI Weekly Trend'[Friction Rate], 1)
> ```

Arrange all 4 cards in a row across the top of the page.

---

### Visual 4 — Top 10 Hotspots Table with Conditional Formatting

1. Insert > **Table**
2. Source: `Friction Hotspots`
3. Columns (in order): `Product`, `Region`, `Channel`, `Customers`, `Friction Score`, `Unresolved Rate`, `Avg Sentiment`, `Priority Score`
4. Filter: `Priority Score` Top 10
5. Sort by `Priority Score` Descending
6. **Conditional formatting on Priority Score:**
   - Select the `Priority Score` column
   - Format > Conditional formatting > **Background color**
   - Rules:
     - If value > 60 → Background `#E05555` (red), Font `#FFFFFF`
     - If value >= 40 AND <= 60 → Background `#F0A500` (amber), Font `#0A0F1E`
     - If value < 40 → Background `#00C49A` (green), Font `#0A0F1E`
7. Title: `Friction Hotspot Segments — Priority Ranked`

---

### Visual 5 — Theme Count with Avg Sentiment Overlay (Combo Chart)

1. Insert > **Line and clustered column chart**
2. Source: `LLM Theme Summary`
3. X-axis (Shared): `Theme`
4. Column Y-axis: `Count`
5. Line Y-axis: `Avg Sentiment`
6. Format > Column: Color `#4DA6FF`
7. Format > Line: Color `#E05555`
8. Add data labels to both series
9. Title: `LLM Theme Distribution — Event Count & Avg Sentiment`

---

## Step 6 — Add Slicers

On the right side of the dashboard, add:

1. **Product slicer** from `Customer Journeys` > `Product` (List style)
2. **Region slicer** from `Customer Journeys` > `Region` (List style)
3. **Segment Label slicer** from `Segment Cuts` > `Segment Label` (Dropdown)
4. **Alert Fired slicer** from `KPI Alerts` > `Alert Fired` (Checkbox: True only)

---

## Step 7 — Final Layout

Suggested 3-row layout:

```
Row 1: [Friction Rate Card] [NPS Card] [Escalation Card] [Resolution Card]
Row 2: [Priority Bar Chart - 60%] | [Dual-Axis Line Chart - 40%]
Row 3: [Hotspots Table - 50%] | [Theme Combo Chart - 50%]
Sidebar: Slicers (Product, Region, Segment Label)
```

---

## Publish (Optional)

1. **File** > **Publish** > **Publish to Power BI**
2. Sign in with your Microsoft account
3. Select your workspace
4. Once published, share the dashboard URL or embed it

---

*Generated by ATLAS Phase 6 — Power BI Export Preparation*
