"""Interactive HTML report - tabbed dashboard with dynamic ECharts (no PNGs)."""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd

from reports.chart_data import build_all_chart_data


def build_interactive_report(
    df: pd.DataFrame,
    output_dir: Path,
    generated_paths: Optional[List[str]] = None,
) -> str:
    """Build tabbed HTML dashboard with dynamic ECharts. Returns path to index.html."""
    output_dir = Path(output_dir)
    chart_data = build_all_chart_data(df)
    data_json = json.dumps(chart_data, default=str)

    out = output_dir / "index.html"
    html = _HTML_TEMPLATE.format(chart_data_json=data_json)
    out.write_text(html, encoding="utf-8")
    return str(out)


_HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Engineering Intelligence — Complexity Analyzer</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Syne:wght@400;500;600;700&family=IBM+Plex+Sans:wght@400;500&display=swap" rel="stylesheet">
  <script src="https://cdn.jsdelivr.net/npm/echarts@5.4.3/dist/echarts.min.js"></script>
  <style>
    :root {{
      --bg-deep: #f5f6f8;
      --bg-card: #ffffff;
      --bg-elevated: #f0f1f3;
      --border: #e2e4e8;
      --text: #1a1d24;
      --text-muted: #6b7280;
      --accent: #b45309;
      --accent-dim: rgba(180, 83, 9, 0.12);
    }}
    * {{ box-sizing: border-box; }}
    body {{
      font-family: 'IBM Plex Sans', system-ui, sans-serif;
      margin: 0;
      background: var(--bg-deep);
      color: var(--text);
      min-height: 100vh;
      line-height: 1.5;
    }}
    .page {{ max-width: 1440px; margin: 0 auto; padding: 2rem 2.5rem 4rem; }}
    header {{ margin-bottom: 2.5rem; padding-bottom: 1.5rem; border-bottom: 1px solid var(--border); }}
    .header-row {{ display: flex; align-items: flex-start; justify-content: space-between; gap: 1.5rem; }}
    .header-text {{ flex: 1; }}
    h1 {{ font-family: 'Syne', sans-serif; font-size: 1.85rem; font-weight: 700; letter-spacing: -0.03em; margin: 0 0 0.4rem; }}
    .subtitle {{ font-size: 0.95rem; color: var(--text-muted); }}
    .global-search {{
      position: relative;
      width: 280px;
      flex-shrink: 0;
      margin-top: 0.2rem;
    }}
    .global-search input {{
      width: 100%;
      padding: 0.55rem 0.75rem 0.55rem 2.2rem;
      font-family: 'IBM Plex Sans', system-ui, sans-serif;
      font-size: 0.85rem;
      border: 1.5px solid var(--border);
      border-radius: 9px;
      background: var(--bg-card);
      color: var(--text);
      outline: none;
      transition: border-color 0.2s, box-shadow 0.2s;
    }}
    .global-search input:focus {{
      border-color: var(--accent);
      box-shadow: 0 0 0 3px var(--accent-dim);
    }}
    .global-search input::placeholder {{ color: var(--text-muted); opacity: 0.6; }}
    .global-search svg {{
      position: absolute;
      left: 0.65rem;
      top: 50%;
      transform: translateY(-50%);
      width: 16px;
      height: 16px;
      color: var(--text-muted);
      pointer-events: none;
    }}
    .global-search .clear-btn {{
      position: absolute;
      right: 0.5rem;
      top: 50%;
      transform: translateY(-50%);
      width: 20px;
      height: 20px;
      border: none;
      background: var(--bg-elevated);
      border-radius: 50%;
      font-size: 0.7rem;
      color: var(--text-muted);
      cursor: pointer;
      display: none;
      align-items: center;
      justify-content: center;
      transition: background 0.15s, color 0.15s;
    }}
    .global-search .clear-btn:hover {{ background: var(--accent-dim); color: var(--accent); }}
    .global-search.has-value .clear-btn {{ display: flex; }}
    .search-count {{
      font-family: 'Syne', sans-serif;
      font-size: 0.8rem;
      font-weight: 500;
      color: var(--text-muted);
      padding: 0.6rem 0 0.2rem;
    }}
    .search-count span {{ color: var(--accent); font-weight: 600; }}
    #search-results {{ display: none; animation: fadeIn 0.25s ease; }}
    #search-results.active {{ display: block; }}
    #search-results .grid {{ grid-template-columns: repeat(auto-fill, minmax(480px, 1fr)); }}
    .tabs {{
      display: flex; gap: 0.2rem; margin-bottom: 2rem; padding: 0.3rem;
      background: var(--bg-card); border-radius: 10px; border: 1px solid var(--border); overflow-x: auto;
    }}
    .tab {{
      padding: 0.6rem 1.2rem; font-family: 'Syne', sans-serif; font-size: 0.9rem; font-weight: 500;
      background: transparent; color: var(--text-muted); border: none; border-radius: 8px;
      cursor: pointer; transition: color 0.2s, background 0.2s;
    }}
    .tab:hover {{ color: var(--text); background: var(--bg-elevated); }}
    .tab.active {{ color: var(--accent); background: var(--accent-dim); }}
    .panel {{ display: none; animation: fadeIn 0.25s ease; }}
    .panel.active {{ display: block; }}
    @keyframes fadeIn {{ from {{ opacity: 0; }} to {{ opacity: 1; }} }}
    .grid {{
      display: grid; grid-template-columns: repeat(auto-fill, minmax(480px, 1fr)); gap: 1.5rem;
    }}
    .chart-card {{
      background: var(--bg-card); border: 1px solid var(--border); border-radius: 10px;
      overflow: hidden; padding: 1rem; transition: box-shadow 0.2s;
    }}
    .chart-card:hover {{ box-shadow: 0 4px 20px rgba(0,0,0,0.08); }}
    .chart-card h3 {{ font-family: 'Syne', sans-serif; font-size: 0.95rem; font-weight: 600; margin: 0 0 0.25rem; }}
    .chart-card .sub {{ font-size: 0.8rem; color: var(--text-muted); margin-bottom: 0.75rem; }}
    .chart-container {{ width: 100%; height: 320px; }}

    /* Developer picker for multiLine charts */
    .chart-card.has-picker {{
      grid-column: 1 / -1;
      display: grid;
      grid-template-columns: 1fr 230px;
      grid-template-rows: auto auto 1fr;
      gap: 0;
    }}
    .chart-card.has-picker h3 {{ grid-column: 1 / -1; }}
    .chart-card.has-picker .sub {{ grid-column: 1 / -1; }}
    .chart-card.has-picker .chart-container {{ height: 420px; }}
    .picker-panel {{
      border-left: 1px solid var(--border);
      padding: 0.5rem;
      display: flex;
      flex-direction: column;
      gap: 0.4rem;
      min-height: 0;
    }}
    .picker-search {{
      width: 100%;
      padding: 0.4rem 0.6rem;
      border: 1px solid var(--border);
      border-radius: 6px;
      font-size: 0.78rem;
      font-family: 'IBM Plex Sans', system-ui, sans-serif;
      background: var(--bg-elevated);
      color: var(--text);
      outline: none;
      transition: border-color 0.2s;
    }}
    .picker-search:focus {{ border-color: var(--accent); }}
    .picker-search::placeholder {{ color: var(--text-muted); opacity: 0.7; }}
    .picker-actions {{
      display: flex;
      gap: 0.3rem;
      flex-wrap: wrap;
    }}
    .picker-actions button {{
      padding: 0.2rem 0.5rem;
      font-size: 0.68rem;
      font-family: 'Syne', sans-serif;
      font-weight: 500;
      border: 1px solid var(--border);
      border-radius: 5px;
      background: var(--bg-card);
      color: var(--text-muted);
      cursor: pointer;
      transition: all 0.15s;
      white-space: nowrap;
    }}
    .picker-actions button:hover {{ background: var(--accent-dim); color: var(--accent); border-color: var(--accent); }}
    .picker-actions button.active {{ background: var(--accent); color: #fff; border-color: var(--accent); }}
    .picker-list {{
      flex: 1;
      overflow-y: auto;
      min-height: 0;
    }}
    .picker-list::-webkit-scrollbar {{ width: 4px; }}
    .picker-list::-webkit-scrollbar-thumb {{ background: var(--border); border-radius: 2px; }}
    .picker-team-label {{
      font-family: 'Syne', sans-serif;
      font-size: 0.65rem;
      font-weight: 600;
      text-transform: uppercase;
      letter-spacing: 0.06em;
      color: var(--text-muted);
      padding: 0.4rem 0.3rem 0.15rem;
      margin-top: 0.1rem;
    }}
    .picker-item {{
      display: flex;
      align-items: center;
      gap: 0.4rem;
      padding: 0.25rem 0.3rem;
      border-radius: 5px;
      cursor: pointer;
      transition: background 0.12s;
      font-size: 0.76rem;
    }}
    .picker-item:hover {{ background: var(--bg-elevated); }}
    .picker-item.hidden {{ display: none; }}
    .picker-swatch {{
      width: 10px;
      height: 10px;
      border-radius: 3px;
      flex-shrink: 0;
      opacity: 0.3;
      transition: opacity 0.15s;
    }}
    .picker-item.selected .picker-swatch {{ opacity: 1; }}
    .picker-name {{
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
      color: var(--text-muted);
      transition: color 0.15s;
    }}
    .picker-item.selected .picker-name {{ color: var(--text); font-weight: 500; }}
  </style>
</head>
<body>
  <div class="page">
    <header>
      <div class="header-row">
        <div class="header-text">
          <h1>Engineering Intelligence</h1>
          <p class="subtitle">Complexity Analyzer — Dynamic charts</p>
        </div>
        <div class="global-search" id="global-search">
          <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
          <input type="text" id="chart-search" placeholder="Filter charts by title..." autocomplete="off" spellcheck="false">
          <button class="clear-btn" id="search-clear">&times;</button>
        </div>
      </div>
    </header>
    <div class="tabs" id="tabs"></div>
    <div id="panels"></div>
    <div id="search-results"></div>
  </div>

  <script>
    const chartData = {chart_data_json};
    const tabOrder = ['basic', 'team', 'risk', 'fairness', 'advanced'];
    const tabLabels = {{ basic: 'Basic', team: 'Team', risk: 'Risk', fairness: 'Fairness', advanced: 'Advanced' }};

    const CHART_THEME = {{
      backgroundColor: 'transparent',
      textStyle: {{ color: '#6b7280', fontFamily: 'IBM Plex Sans' }},
      title: {{ textStyle: {{ color: '#1a1d24' }}, subtextStyle: {{ color: '#6b7280' }} }},
      legend: {{ textStyle: {{ color: '#6b7280' }} }},
      axisLine: {{ lineStyle: {{ color: '#e2e4e8' }} }},
      axisLabel: {{ color: '#6b7280' }},
      splitLine: {{ lineStyle: {{ color: '#eef0f2' }} }},
    }};

    const COLORS = ['#b45309', '#0d9488', '#7c3aed', '#2563eb', '#ea580c', '#16a34a', '#dc2626', '#6b7280'];

    function renderBar(container, c) {{
      const opt = {{
        ...CHART_THEME,
        tooltip: {{ trigger: 'axis' }},
        grid: {{ left: 50, right: 30, top: 40, bottom: 60 }},
        xAxis: {{ type: 'category', data: c.x, axisLabel: {{ rotate: 45 }} }},
        yAxis: {{ type: 'value', minInterval: 0 }},
        series: [{{ type: 'bar', data: c.y, barWidth: '50%', barMinWidth: 20, barMaxWidth: 100, itemStyle: {{ color: COLORS[0] }} }}],
      }};
      const chart = echarts.init(container);
      chart.setOption(opt);
      window.addEventListener('resize', () => chart.resize());
      return chart;
    }}

    function renderLine(container, c) {{
      const opt = {{
        ...CHART_THEME,
        tooltip: {{ trigger: 'axis' }},
        grid: {{ left: 50, right: 30, top: 40, bottom: 60 }},
        xAxis: {{ type: 'category', data: c.x, axisLabel: {{ rotate: 45 }} }},
        yAxis: {{ type: 'value', minInterval: 0 }},
        series: [{{ type: 'line', data: c.y, smooth: true, symbol: 'circle', symbolSize: 6, itemStyle: {{ color: COLORS[0] }} }}],
      }};
      const chart = echarts.init(container);
      chart.setOption(opt);
      window.addEventListener('resize', () => chart.resize());
      return chart;
    }}

    function renderDualLine(container, c) {{
      const opt = {{
        ...CHART_THEME,
        tooltip: {{ trigger: 'axis' }},
        legend: {{ data: [c.y1Name, c.y2Name] }},
        grid: {{ left: 50, right: 50, top: 50, bottom: 60 }},
        xAxis: {{ type: 'category', data: c.x, axisLabel: {{ rotate: 45 }} }},
        yAxis: [
          {{ type: 'value', name: c.y1Name, position: 'left', axisLine: {{ show: true, lineStyle: {{ color: COLORS[0] }} }} }},
          {{ type: 'value', name: c.y2Name, position: 'right', axisLine: {{ show: true, lineStyle: {{ color: COLORS[1] }} }} }},
        ],
        series: [
          {{ type: 'line', name: c.y1Name, data: c.y1, smooth: true, yAxisIndex: 0, itemStyle: {{ color: COLORS[0] }} }},
          {{ type: 'line', name: c.y2Name, data: c.y2, smooth: true, yAxisIndex: 1, itemStyle: {{ color: COLORS[1] }} }},
        ],
      }};
      const chart = echarts.init(container);
      chart.setOption(opt);
      window.addEventListener('resize', () => chart.resize());
      return chart;
    }}

    function renderMultiLine(container, c) {{
      const hasPicker = c.hasPicker && c.series && c.series.length > 6;
      const allSeries = (c.series || []);
      const colorMap = {{}};
      allSeries.forEach((s, i) => {{ colorMap[s.name] = COLORS[i % COLORS.length]; }});

      const series = allSeries.map((s, i) => ({{
        type: 'line', name: s.name, data: s.data, smooth: true, symbol: 'circle', symbolSize: 4,
        itemStyle: {{ color: COLORS[i % COLORS.length] }},
      }}));

      const legendCfg = hasPicker
        ? {{ show: false }}
        : {{
            type: 'scroll', bottom: 0, selectedMode: 'single', selector: true,
            pageIconSize: 10, pageTextStyle: {{ fontSize: 10 }},
            pageFormatter: ({{ current, total }}) => `${{current}}/${{total}}`,
            pageButtonItemGap: 4, itemGap: 8, itemWidth: 14, itemHeight: 10, textStyle: {{ fontSize: 10 }},
          }};

      const opt = {{
        ...CHART_THEME,
        tooltip: {{ trigger: 'axis', confine: true,
          formatter: function(params) {{
            const active = params.filter(p => p.value != null && p.value !== 0);
            if (!active.length) return '';
            active.sort((a, b) => (b.value || 0) - (a.value || 0));
            let s = `<b>${{active[0].axisValue}}</b><br/>`;
            active.forEach(p => {{
              s += `${{p.marker}} ${{p.seriesName}}: <b>${{p.value}}</b><br/>`;
            }});
            return s;
          }}
        }},
        legend: legendCfg,
        grid: {{ left: 50, right: 20, top: 30, bottom: hasPicker ? 30 : 80 }},
        xAxis: {{ type: 'category', data: c.x, axisLabel: {{ rotate: 45 }} }},
        yAxis: {{ type: 'value', minInterval: 0 }},
        series,
      }};
      const chart = echarts.init(container);
      chart.setOption(opt);
      window.addEventListener('resize', () => chart.resize());

      if (hasPicker) {{
        const pickerId = container.id + '-picker';
        const pickerEl = document.getElementById(pickerId);
        if (pickerEl) buildPicker(pickerEl, chart, allSeries, colorMap);
      }}

      return chart;
    }}

    function buildPicker(pickerEl, chart, allSeries, colorMap) {{
      const teams = {{}};
      const noTeam = [];
      allSeries.forEach(s => {{
        const t = s.team || '';
        if (t) {{
          if (!teams[t]) teams[t] = [];
          teams[t].push(s.name);
        }} else {{
          noTeam.push(s.name);
        }}
      }});
      const teamOrder = Object.keys(teams).sort();
      const selected = new Set();
      if (allSeries.length > 0) selected.add(allSeries[0].name);

      const searchInput = document.createElement('input');
      searchInput.className = 'picker-search';
      searchInput.placeholder = 'Search developers...';
      pickerEl.appendChild(searchInput);

      const actionsDiv = document.createElement('div');
      actionsDiv.className = 'picker-actions';
      pickerEl.appendChild(actionsDiv);

      const listDiv = document.createElement('div');
      listDiv.className = 'picker-list';
      pickerEl.appendChild(listDiv);

      const itemEls = {{}};

      function addTeamSection(teamName, devs) {{
        const label = document.createElement('div');
        label.className = 'picker-team-label';
        label.textContent = teamName;
        label.dataset.teamlabel = teamName;
        listDiv.appendChild(label);
        devs.forEach(name => {{
          const item = document.createElement('div');
          item.className = 'picker-item' + (selected.has(name) ? ' selected' : '');
          item.dataset.name = name.toLowerCase();
          item.dataset.team = teamName;
          const swatch = document.createElement('span');
          swatch.className = 'picker-swatch';
          swatch.style.background = colorMap[name] || '#999';
          const nameEl = document.createElement('span');
          nameEl.className = 'picker-name';
          nameEl.textContent = name;
          nameEl.title = name;
          item.appendChild(swatch);
          item.appendChild(nameEl);
          item.addEventListener('click', () => toggleDev(name));
          listDiv.appendChild(item);
          itemEls[name] = item;
        }});
      }}

      teamOrder.forEach(t => addTeamSection(t, teams[t]));
      if (noTeam.length) addTeamSection('Other', noTeam);

      // team filter buttons
      const allBtn = document.createElement('button');
      allBtn.textContent = 'All';
      allBtn.addEventListener('click', () => {{
        selected.clear();
        allSeries.forEach(s => selected.add(s.name));
        syncChart();
      }});
      actionsDiv.appendChild(allBtn);

      const noneBtn = document.createElement('button');
      noneBtn.textContent = 'None';
      noneBtn.addEventListener('click', () => {{
        selected.clear();
        syncChart();
      }});
      actionsDiv.appendChild(noneBtn);

      teamOrder.forEach(t => {{
        const btn = document.createElement('button');
        btn.textContent = t;
        btn.addEventListener('click', () => {{
          selected.clear();
          teams[t].forEach(d => selected.add(d));
          syncChart();
        }});
        actionsDiv.appendChild(btn);
      }});

      searchInput.addEventListener('input', () => {{
        const q = searchInput.value.toLowerCase();
        const labels = listDiv.querySelectorAll('.picker-team-label');
        labels.forEach(l => {{ l.style.display = 'none'; }});
        const visibleTeams = new Set();
        Object.entries(itemEls).forEach(([name, el]) => {{
          const match = name.toLowerCase().includes(q);
          el.classList.toggle('hidden', !match);
          if (match) visibleTeams.add(el.dataset.team);
        }});
        labels.forEach(l => {{
          if (visibleTeams.has(l.dataset.teamlabel)) l.style.display = '';
        }});
      }});

      function toggleDev(name) {{
        if (selected.has(name)) selected.delete(name);
        else selected.add(name);
        syncChart();
      }}

      function syncChart() {{
        const legend = {{}};
        allSeries.forEach(s => {{ legend[s.name] = selected.has(s.name); }});
        chart.setOption({{ legend: {{ selected: legend }} }});
        Object.entries(itemEls).forEach(([name, el]) => {{
          el.classList.toggle('selected', selected.has(name));
        }});
      }}

      syncChart();
    }}

    function renderStackedBar(container, c) {{
      const series = (c.series || []).map((s, i) => ({{
        type: 'bar', name: s.name, stack: 'total', data: s.data,
        barMinWidth: 12, barMaxWidth: 60,
        itemStyle: {{ color: COLORS[i % COLORS.length] }},
      }}));
      const opt = {{
        ...CHART_THEME,
        tooltip: {{ trigger: 'axis' }},
        legend: {{
          type: 'scroll',
          bottom: 0,
          selectedMode: 'single',
          selector: true,
          pageIconSize: 10,
          pageTextStyle: {{ fontSize: 10 }},
          pageFormatter: ({{ current, total }}) => `${{current}}/${{total}}`,
          pageButtonItemGap: 4,
          itemGap: 8,
          itemWidth: 14,
          itemHeight: 10,
          textStyle: {{ fontSize: 10 }},
        }},
        grid: {{ left: 50, right: 30, top: 40, bottom: 80 }},
        xAxis: {{ type: 'category', data: c.x, axisLabel: {{ rotate: 45 }} }},
        yAxis: {{ type: 'value', minInterval: 0 }},
        series,
      }};
      const chart = echarts.init(container);
      chart.setOption(opt);
      window.addEventListener('resize', () => chart.resize());
      return chart;
    }}

    function renderScatter(container, c) {{
      const opt = {{
        ...CHART_THEME,
        tooltip: {{ trigger: 'item' }},
        grid: {{ left: 50, right: 30, top: 40, bottom: 60 }},
        xAxis: {{ type: 'value', name: c.xAxisName || 'X' }},
        yAxis: {{ type: 'value', name: c.yAxisName || 'Y' }},
        series: [{{ type: 'scatter', data: c.data, symbolSize: 8, itemStyle: {{ color: COLORS[0] }} }}],
      }};
      const chart = echarts.init(container);
      chart.setOption(opt);
      window.addEventListener('resize', () => chart.resize());
      return chart;
    }}

    function renderScatterLabel(container, c) {{
      const data = (c.data || []).map(d => ({{ name: d.name, value: d.value }}));
      const opt = {{
        ...CHART_THEME,
        tooltip: {{ trigger: 'item' }},
        grid: {{ left: 50, right: 30, top: 40, bottom: 60 }},
        xAxis: {{ type: 'value', name: c.xAxisName || 'PR Count' }},
        yAxis: {{ type: 'value', name: c.yAxisName || 'Y' }},
        series: [{{
          type: 'scatter', data, symbolSize: 12,
          itemStyle: {{ color: COLORS[0] }},
          label: {{ show: true, formatter: '{{b}}', position: 'right', fontSize: 10 }},
        }}],
      }};
      const chart = echarts.init(container);
      chart.setOption(opt);
      window.addEventListener('resize', () => chart.resize());
      return chart;
    }}

    function renderBoxplot(container, c) {{
      const opt = {{
        ...CHART_THEME,
        tooltip: {{ trigger: 'item' }},
        grid: {{ left: 50, right: 30, top: 40, bottom: 60 }},
        xAxis: {{ type: 'category', data: c.x, axisLabel: {{ rotate: 45 }} }},
        yAxis: {{ type: 'value', minInterval: 0 }},
        series: [{{ type: 'boxplot', data: c.data, boxWidth: '50%', itemStyle: {{ color: COLORS[0] }} }}],
      }};
      const chart = echarts.init(container);
      chart.setOption(opt);
      window.addEventListener('resize', () => chart.resize());
      return chart;
    }}

    function renderArea(container, c) {{
      const opt = {{
        ...CHART_THEME,
        tooltip: {{ trigger: 'axis' }},
        grid: {{ left: 50, right: 30, top: 40, bottom: 60 }},
        xAxis: {{ type: 'category', data: c.x, axisLabel: {{ rotate: 45 }} }},
        yAxis: {{ type: 'value', minInterval: 0 }},
        series: [{{ type: 'line', data: c.y, areaStyle: {{}}, smooth: true, itemStyle: {{ color: COLORS[0] }} }}],
      }};
      const chart = echarts.init(container);
      chart.setOption(opt);
      window.addEventListener('resize', () => chart.resize());
      return chart;
    }}

    function renderChart(container, c) {{
      const type = c.type || 'bar';
      if (type === 'bar') return renderBar(container, c);
      if (type === 'line') return renderLine(container, c);
      if (type === 'dualLine') return renderDualLine(container, c);
      if (type === 'multiLine') return renderMultiLine(container, c);
      if (type === 'stackedBar') return renderStackedBar(container, c);
      if (type === 'scatter') return renderScatter(container, c);
      if (type === 'scatterLabel') return renderScatterLabel(container, c);
      if (type === 'boxplot') return renderBoxplot(container, c);
      if (type === 'area') return renderArea(container, c);
      return renderBar(container, c);
    }}

    const tabsEl = document.getElementById('tabs');
    const panelsEl = document.getElementById('panels');

    const chartInstances = {{}};

    tabOrder.forEach((key, i) => {{
      const btn = document.createElement('button');
      btn.className = 'tab' + (i === 0 ? ' active' : '');
      btn.textContent = tabLabels[key];
      btn.dataset.tab = key;
      btn.onclick = () => {{
        document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
        document.querySelectorAll('.panel').forEach(p => p.classList.remove('active'));
        btn.classList.add('active');
        const panel = document.getElementById('panel-' + key);
        panel.classList.add('active');
        (chartInstances[key] || []).forEach(ch => ch.resize());
      }};
      tabsEl.appendChild(btn);
    }});

    tabOrder.forEach((key, i) => {{
      const panel = document.createElement('div');
      panel.id = 'panel-' + key;
      panel.className = 'panel' + (i === 0 ? ' active' : '');

      const charts = chartData[key] || [];
      let html = '<div class="grid">';
      charts.forEach((c, idx) => {{
        const id = 'chart-' + key + '-' + idx;
        const hasPicker = c.hasPicker && c.series && c.series.length > 6;
        const cardClass = hasPicker ? 'chart-card has-picker' : 'chart-card';
        const pickerHtml = hasPicker
          ? `<div class="picker-panel" id="${{id}}-picker"></div>`
          : '';
        const spanStyle = hasPicker ? ' style="grid-column:1/-1"' : '';
        html += `<div class="${{cardClass}}"><h3${{spanStyle}}>${{c.title}}</h3><div class="sub"${{spanStyle}}>${{c.subtitle || ''}}</div><div id="${{id}}" class="chart-container"></div>${{pickerHtml}}</div>`;
      }});
      html += '</div>';
      panel.innerHTML = html;
      panelsEl.appendChild(panel);

      chartInstances[key] = [];
      charts.forEach((c, idx) => {{
        const id = 'chart-' + key + '-' + idx;
        const el = document.getElementById(id);
        if (el) {{
          const ch = renderChart(el, c);
          if (ch) chartInstances[key].push(ch);
        }}
      }});
    }});

    requestAnimationFrame(() => {{
      (chartInstances['basic'] || []).forEach(ch => ch.resize());
    }});

    // Global chart search
    const searchEl = document.getElementById('chart-search');
    const searchWrap = document.getElementById('global-search');
    const clearBtn = document.getElementById('search-clear');
    const searchResultsEl = document.getElementById('search-results');
    const allChartEntries = [];

    tabOrder.forEach(key => {{
      (chartData[key] || []).forEach((c, idx) => {{
        allChartEntries.push({{ tab: key, idx, data: c, title: c.title || '', subtitle: c.subtitle || '' }});
      }});
    }});

    let searchChartInstances = [];

    function doSearch(query) {{
      const q = query.trim().toLowerCase();
      searchWrap.classList.toggle('has-value', q.length > 0);

      if (!q) {{
        tabsEl.style.display = '';
        panelsEl.style.display = '';
        searchResultsEl.classList.remove('active');
        searchChartInstances.forEach(ch => ch.dispose());
        searchChartInstances = [];
        searchResultsEl.innerHTML = '';
        const activeTab = document.querySelector('.tab.active');
        if (activeTab) {{
          const key = activeTab.dataset.tab;
          (chartInstances[key] || []).forEach(ch => ch.resize());
        }}
        return;
      }}

      tabsEl.style.display = 'none';
      panelsEl.style.display = 'none';
      searchResultsEl.classList.add('active');

      searchChartInstances.forEach(ch => ch.dispose());
      searchChartInstances = [];

      const matches = allChartEntries.filter(e =>
        e.title.toLowerCase().includes(q) || e.subtitle.toLowerCase().includes(q)
      );

      let html = `<div class="search-count"><span>${{matches.length}}</span> chart${{matches.length !== 1 ? 's' : ''}} matching "${{query.trim()}}"</div>`;
      html += '<div class="grid">';
      matches.forEach((m, i) => {{
        const id = 'search-chart-' + i;
        const hasPicker = m.data.hasPicker && m.data.series && m.data.series.length > 6;
        const cardClass = hasPicker ? 'chart-card has-picker' : 'chart-card';
        const pickerHtml = hasPicker ? `<div class="picker-panel" id="${{id}}-picker"></div>` : '';
        const spanStyle = hasPicker ? ' style="grid-column:1/-1"' : '';
        const tabBadge = `<span style="font-size:0.65rem;font-weight:500;color:var(--accent);background:var(--accent-dim);padding:0.15rem 0.45rem;border-radius:4px;margin-left:0.5rem;vertical-align:middle;text-transform:uppercase;letter-spacing:0.04em;">${{tabLabels[m.tab]}}</span>`;
        html += `<div class="${{cardClass}}"><h3${{spanStyle}}>${{m.data.title}}${{tabBadge}}</h3><div class="sub"${{spanStyle}}>${{m.data.subtitle || ''}}</div><div id="${{id}}" class="chart-container"></div>${{pickerHtml}}</div>`;
      }});
      html += '</div>';
      searchResultsEl.innerHTML = html;

      matches.forEach((m, i) => {{
        const id = 'search-chart-' + i;
        const el = document.getElementById(id);
        if (el) {{
          const ch = renderChart(el, m.data);
          if (ch) searchChartInstances.push(ch);
        }}
      }});
    }}

    searchEl.addEventListener('input', () => doSearch(searchEl.value));
    clearBtn.addEventListener('click', () => {{
      searchEl.value = '';
      doSearch('');
      searchEl.focus();
    }});
  </script>
</body>
</html>
"""
