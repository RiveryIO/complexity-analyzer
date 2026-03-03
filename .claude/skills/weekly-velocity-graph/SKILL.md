---
name: weekly-velocity-graph
description: "DEPRECATED — use the generate-web-reports skill instead, which produces an interactive HTML dashboard with all charts (including velocity by week). This skill generated a static PNG bar chart and is no longer maintained."
---

# Weekly Velocity Graph (DEPRECATED)

**This skill is deprecated.** Use `generate-web-reports` instead, which produces an interactive HTML dashboard with tabbed charts, search, and developer filtering — including the velocity-by-week chart this skill used to generate.

```bash
# Instead of this:
# python scripts/velocity_by_week.py

# Use:
complexity-cli generate-reports -i complexity-report.csv -o reports
python -m http.server 8080 -d reports &
open http://localhost:8080
```
