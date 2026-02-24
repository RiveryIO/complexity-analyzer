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
      --bg-deep: #0c0e12;
      --bg-card: #14171e;
      --bg-elevated: #1a1e28;
      --border: #2a303c;
      --text: #e8ecf2;
      --text-muted: #8892a0;
      --accent: #e8a838;
      --accent-dim: rgba(232, 168, 56, 0.12);
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
    h1 {{ font-family: 'Syne', sans-serif; font-size: 1.85rem; font-weight: 700; letter-spacing: -0.03em; margin: 0 0 0.4rem; }}
    .subtitle {{ font-size: 0.95rem; color: var(--text-muted); }}
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
    .chart-card:hover {{ box-shadow: 0 4px 20px rgba(0,0,0,0.25); }}
    .chart-card h3 {{ font-family: 'Syne', sans-serif; font-size: 0.95rem; font-weight: 600; margin: 0 0 0.25rem; }}
    .chart-card .sub {{ font-size: 0.8rem; color: var(--text-muted); margin-bottom: 0.75rem; }}
    .chart-container {{ width: 100%; height: 320px; }}
  </style>
</head>
<body>
  <div class="page">
    <header>
      <h1>Engineering Intelligence</h1>
      <p class="subtitle">Complexity Analyzer — Dynamic charts</p>
    </header>
    <div class="tabs" id="tabs"></div>
    <div id="panels"></div>
  </div>

  <script>
    const chartData = {chart_data_json};
    const tabOrder = ['basic', 'team', 'risk', 'fairness', 'advanced'];
    const tabLabels = {{ basic: 'Basic', team: 'Team', risk: 'Risk', fairness: 'Fairness', advanced: 'Advanced' }};

    const DARK_THEME = {{
      backgroundColor: 'transparent',
      textStyle: {{ color: '#8892a0', fontFamily: 'IBM Plex Sans' }},
      title: {{ textStyle: {{ color: '#e8ecf2' }}, subtextStyle: {{ color: '#8892a0' }} }},
      legend: {{ textStyle: {{ color: '#8892a0' }} }},
      axisLine: {{ lineStyle: {{ color: '#2a303c' }} }},
      axisLabel: {{ color: '#8892a0' }},
      splitLine: {{ lineStyle: {{ color: '#1a1e28' }} }},
    }};

    const COLORS = ['#e8a838', '#5cb8b2', '#c97dd5', '#6b9bd1', '#e89b6f', '#8bc98a', '#d47070', '#9b9b9b'];

    function renderBar(container, c) {{
      const opt = {{
        ...DARK_THEME,
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
        ...DARK_THEME,
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
        ...DARK_THEME,
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
      const series = (c.series || []).map((s, i) => ({{
        type: 'line', name: s.name, data: s.data, smooth: true, symbol: 'circle', symbolSize: 4,
        itemStyle: {{ color: COLORS[i % COLORS.length] }},
      }}));
      const opt = {{
        ...DARK_THEME,
        tooltip: {{ trigger: 'axis' }},
        legend: {{ type: 'scroll', bottom: 0 }},
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

    function renderStackedBar(container, c) {{
      const series = (c.series || []).map((s, i) => ({{
        type: 'bar', name: s.name, stack: 'total', data: s.data,
        barMinWidth: 12, barMaxWidth: 60,
        itemStyle: {{ color: COLORS[i % COLORS.length] }},
      }}));
      const opt = {{
        ...DARK_THEME,
        tooltip: {{ trigger: 'axis' }},
        legend: {{ type: 'scroll', bottom: 0 }},
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
        ...DARK_THEME,
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
        ...DARK_THEME,
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
        ...DARK_THEME,
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
        ...DARK_THEME,
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
        html += `<div class="chart-card"><h3>${{c.title}}</h3><div class="sub">${{c.subtitle || ''}}</div><div id="${{id}}" class="chart-container"></div></div>`;
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
  </script>
</body>
</html>
"""
