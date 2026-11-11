#!/usr/bin/env python3
"""
PSXpert - Local Web Database Explorer
Run: python web_viewer.py
Open: http://localhost:5000 in your browser
"""

import math
from flask import Flask, render_template_string, request, jsonify
from sqlalchemy import text
from src.database.connection import get_engine, is_postgres

app = Flask(__name__)
engine = get_engine()

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>PSXpert Database Explorer</title>
  <style>
    :root {
      --bg: #0f172a;
      --card: #1e293b;
      --border: #334155;
      --primary: #38bdf8;
      --text: #f8fafc;
      --text-muted: #94a3b8;
      --accent: #10b981;
    }
    body {
      margin: 0;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      background: var(--bg);
      color: var(--text);
      display: flex;
      height: 100vh;
      overflow: hidden;
    }
    aside {
      width: 280px;
      background: var(--card);
      border-right: 1px solid var(--border);
      padding: 20px;
      overflow-y: auto;
      display: flex;
      flex-direction: column;
      gap: 15px;
    }
    .brand {
      font-size: 1.3rem;
      font-weight: 700;
      color: var(--primary);
      display: flex;
      align-items: center;
      gap: 8px;
    }
    .badge {
      font-size: 0.75rem;
      background: #0369a1;
      padding: 2px 8px;
      border-radius: 12px;
      color: white;
    }
    .table-list {
      list-style: none;
      padding: 0;
      margin: 0;
      display: flex;
      flex-direction: column;
      gap: 4px;
    }
    .table-btn {
      width: 100%;
      text-align: left;
      background: transparent;
      border: 1px solid transparent;
      color: var(--text);
      padding: 10px 12px;
      border-radius: 6px;
      cursor: pointer;
      display: flex;
      justify-content: space-between;
      font-size: 0.88rem;
      transition: all 0.15s ease;
    }
    .table-btn:hover, .table-btn.active {
      background: #334155;
      border-color: var(--primary);
      color: var(--primary);
    }
    .count {
      color: var(--text-muted);
      font-size: 0.8rem;
    }
    main {
      flex: 1;
      display: flex;
      flex-direction: column;
      overflow: hidden;
    }
    header {
      padding: 16px 24px;
      border-bottom: 1px solid var(--border);
      display: flex;
      justify-content: space-between;
      align-items: center;
      background: #111827;
    }
    .search-box {
      background: #1e293b;
      border: 1px solid var(--border);
      color: white;
      padding: 8px 14px;
      border-radius: 6px;
      width: 320px;
      font-size: 0.9rem;
    }
    .content-area {
      flex: 1;
      overflow: auto;
      padding: 20px 24px;
    }
    table {
      width: 100%;
      border-collapse: collapse;
      font-size: 0.88rem;
    }
    th {
      background: #1e293b;
      position: sticky;
      top: 0;
      text-align: left;
      padding: 12px 14px;
      border-bottom: 2px solid var(--border);
      color: var(--primary);
      font-weight: 600;
      white-space: nowrap;
    }
    td {
      padding: 10px 14px;
      border-bottom: 1px solid #1e293b;
      color: #cbd5e1;
      white-space: nowrap;
    }
    tr:hover td {
      background: #1e293b80;
      color: white;
    }
    .pagination {
      display: flex;
      gap: 8px;
      align-items: center;
      padding: 12px 24px;
      border-top: 1px solid var(--border);
      background: #111827;
      font-size: 0.88rem;
    }
    .pg-btn {
      background: #1e293b;
      border: 1px solid var(--border);
      color: white;
      padding: 6px 12px;
      border-radius: 4px;
      cursor: pointer;
    }
    .pg-btn:disabled {
      opacity: 0.4;
      cursor: not-allowed;
    }
    .sql-box {
      width: 100%;
      background: #0f172a;
      border: 1px solid var(--border);
      color: #38bdf8;
      font-family: monospace;
      padding: 10px;
      border-radius: 6px;
      margin-bottom: 12px;
      resize: vertical;
      box-sizing: border-box;
    }
  </style>
</head>
<body>
  <aside>
    <div class="brand">
      <span>🇵🇰 PSXpert DB</span>
      <span class="badge">{{ dialect }}</span>
    </div>
    <div style="font-size: 0.8rem; color: var(--text-muted);">
      Connected: {{ conn_target }}
    </div>
    <hr style="border: 0; border-top: 1px solid var(--border); margin: 5px 0;">
    <ul class="table-list">
      {% for tbl, cnt in tables %}
      <li>
        <button class="table-btn {% if tbl == active_table %}active{% endif %}" onclick="selectTable('{{ tbl }}')">
          <span>{{ tbl }}</span>
          <span class="count">{{ "{:,}".format(cnt) }}</span>
        </button>
      </li>
      {% endfor %}
    </ul>
  </aside>

  <main>
    <header>
      <div>
        <h2 style="margin: 0; font-size: 1.2rem; font-weight: 600;">
          Table: <span style="color: var(--primary);">{{ active_table }}</span>
          <span style="font-size: 0.85rem; color: var(--text-muted); font-weight: normal; margin-left: 10px;">
            ({{ "{:,}".format(total_rows) }} records)
          </span>
        </h2>
      </div>
      <form method="GET" style="display: flex; gap: 8px;">
        <input type="hidden" name="table" value="{{ active_table }}">
        <input type="text" name="q" class="search-box" placeholder="Filter/Search (e.g. OGDC, CEMENT)..." value="{{ search_query }}">
        <button type="submit" class="pg-btn">Search</button>
        {% if search_query %}
          <a href="/?table={{ active_table }}" class="pg-btn" style="text-decoration: none;">Clear</a>
        {% endif %}
      </form>
    </header>

    <div class="content-area">
      {% if error %}
        <div style="padding: 16px; background: #ef444420; border: 1px solid #ef4444; border-radius: 6px; color: #fca5a5;">
          {{ error }}
        </div>
      {% elif rows %}
        <table>
          <thead>
            <tr>
              {% for col in columns %}
                <th>{{ col }}</th>
              {% endfor %}
            </tr>
          </thead>
          <tbody>
            {% for row in rows %}
              <tr>
                {% for col in columns %}
                  <td>{{ row[col] if row[col] is not none else '<span style="color:#64748b;">NULL</span>'|safe }}</td>
                {% endfor %}
              </tr>
            {% endfor %}
          </tbody>
        </table>
      {% else %}
        <div style="color: var(--text-muted); text-align: center; margin-top: 40px;">
          No matching records found.
        </div>
      {% endif %}
    </div>

    <div class="pagination">
      <span>Page {{ page }} of {{ max_pages }}</span>
      <div style="margin-left: auto; display: flex; gap: 6px;">
        <button class="pg-btn" {% if page <= 1 %}disabled{% endif %} onclick="goToPage({{ page - 1 }})">Previous</button>
        <button class="pg-btn" {% if page >= max_pages %}disabled{% endif %} onclick="goToPage({{ page + 1 }})">Next</button>
      </div>
    </div>
  </main>

  <script>
    function selectTable(tbl) {
      window.location.href = '/?table=' + tbl;
    }
    function goToPage(p) {
      const url = new URL(window.location.href);
      url.searchParams.set('page', p);
      window.location.href = url.toString();
    }
  </script>
</body>
</html>
"""

TABLES = [
    "companies",
    "stock_prices",
    "market_indices",
    "news_articles",
    "news_entities",
    "company_financials",
    "news_sentiment",
    "corporate_announcements",
    "corporate_payouts",
    "data_sources"
]

@app.route("/")
def index():
    active_table = request.args.get("table", "companies")
    if active_table not in TABLES:
        active_table = "companies"

    page = int(request.args.get("page", 1))
    page_size = 50
    search_query = request.args.get("q", "").strip()

    dialect = "PostgreSQL" if is_postgres() else "SQLite"
    conn_target = "localhost:5432/psxpert" if is_postgres() else "data/psxpert.db"

    table_counts = []
    columns = []
    rows = []
    total_rows = 0
    error = None

    try:
        with engine.connect() as conn:
            for tbl in TABLES:
                cnt = conn.execute(text(f"SELECT COUNT(*) FROM {tbl}")).scalar()
                table_counts.append((tbl, cnt))

            # Base query
            count_sql = f"SELECT COUNT(*) FROM {active_table}"
            data_sql = f"SELECT * FROM {active_table}"

            where_clauses = []
            params = {}

            if search_query:
                # Text matching on common searchable columns
                if active_table == "companies":
                    where_clauses.append("(symbol ILIKE :q OR company_name ILIKE :q OR sector ILIKE :q)")
                elif active_table == "stock_prices":
                    where_clauses.append("(symbol ILIKE :q OR trading_date::text ILIKE :q)")
                elif active_table in ("corporate_announcements", "corporate_payouts", "company_financials"):
                    where_clauses.append("symbol ILIKE :q")
                elif active_table == "news_articles":
                    where_clauses.append("(headline ILIKE :q OR publisher ILIKE :q)")
                elif active_table == "market_indices":
                    where_clauses.append("index_symbol ILIKE :q")
                params["q"] = f"%{search_query}%"

            if where_clauses:
                clause = " WHERE " + " AND ".join(where_clauses)
                count_sql += clause
                data_sql += clause

            total_rows = conn.execute(text(count_sql), params).scalar()

            # Sorting
            if active_table == "stock_prices":
                data_sql += " ORDER BY trading_date DESC"
            elif active_table == "news_articles":
                data_sql += " ORDER BY published_at DESC"
            elif active_table == "corporate_announcements":
                data_sql += " ORDER BY posting_date DESC"
            elif active_table == "corporate_payouts":
                data_sql += " ORDER BY announcement_date DESC"
            elif active_table == "company_financials":
                data_sql += " ORDER BY fiscal_year DESC, fiscal_period DESC"
            else:
                data_sql += " ORDER BY 1 ASC"

            # Pagination
            offset = (page - 1) * page_size
            data_sql += f" LIMIT {page_size} OFFSET {offset}"

            res = conn.execute(text(data_sql), params)
            columns = list(res.keys())
            rows = [dict(zip(columns, r)) for r in res.fetchall()]

    except Exception as e:
        error = str(e)

    max_pages = max(1, math.ceil(total_rows / page_size))

    return render_template_string(
        HTML_TEMPLATE,
        tables=table_counts,
        active_table=active_table,
        columns=columns,
        rows=rows,
        total_rows=total_rows,
        page=page,
        max_pages=max_pages,
        search_query=search_query,
        dialect=dialect,
        conn_target=conn_target,
        error=error
    )

if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("PSXPERT DATABASE EXPLORER SERVER STARTED")
    print("Open in your browser: http://localhost:5000")
    print("=" * 60 + "\n")
    app.run(host="localhost", port=5000, debug=False)
