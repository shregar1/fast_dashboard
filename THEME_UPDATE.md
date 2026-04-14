# FastMVC Dashboards Theme Update Guide

## Overview

All dashboards need to be updated to use a consistent **monochrome flat dark/light theme** that matches:

- `static/launch.html`
- `static/swagger.html`
- `docs-site`

## CSS Variables Pattern

Replace existing CSS variables with:

```css
:root {
  --bg: #0a0a0b;
  --surface: #141416;
  --surface-raised: #1c1c1f;
  --border: #27272a;
  --border-hover: #3f3f46;
  --text: #fafafa;
  --text-secondary: #a1a1aa;
  --text-muted: #71717a;
  --accent: #e4e4e7;
  --success: #22c55e;
  --warning: #eab308;
  --error: #ef4444;
  --info: #3b82f6;
}

[data-theme="light"] {
  --bg: #fafafa;
  --surface: #ffffff;
  --surface-raised: #f4f4f5;
  --border: #e4e4e7;
  --border-hover: #d4d4d8;
  --text: #18181b;
  --text-secondary: #52525b;
  --text-muted: #a1a1aa;
  --accent: #18181b;
  --success: #16a34a;
  --warning: #ca8a04;
  --error: #dc2626;
  --info: #2563eb;
}
```

## Theme Toggle Button

Add this HTML to each dashboard header:

```html
<button class="theme-toggle" id="theme-toggle" aria-label="Toggle theme">
  <svg class="moon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
    <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/>
  </svg>
  <svg class="sun" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
    <circle cx="12" cy="12" r="5"/>
    <line x1="12" y1="1" x2="12" y2="3"/>
    <line x1="12" y1="21" x2="12" y2="23"/>
    <line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/>
    <line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/>
    <line x1="1" y1="12" x2="3" y2="12"/>
    <line x1="21" y1="12" x2="23" y2="12"/>
    <line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/>
    <line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/>
  </svg>
</button>
```

## Theme Toggle CSS

```css
.theme-toggle {
  background: var(--surface-raised);
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 8px;
  cursor: pointer;
  color: var(--text-muted);
  transition: all 0.2s;
  display: flex;
  align-items: center;
  justify-content: center;
}

.theme-toggle:hover {
  background: var(--border);
  border-color: var(--border-hover);
  color: var(--text);
}

.theme-toggle svg { width: 18px; height: 18px; }
.theme-toggle .sun { display: none; }
.theme-toggle .moon { display: block; }
[data-theme="light"] .theme-toggle .sun { display: block; }
[data-theme="light"] .theme-toggle .moon { display: none; }
```

## Theme Toggle JavaScript

Add before closing `</body>` tag:

```javascript
<script>
  const themeToggle = document.getElementById('theme-toggle');
  const html = document.documentElement;
  
  const savedTheme = localStorage.getItem('theme') || 'dark';
  html.setAttribute('data-theme', savedTheme);
  
  themeToggle.addEventListener('click', () => {
    const currentTheme = html.getAttribute('data-theme');
    const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
    html.setAttribute('data-theme', newTheme);
    localStorage.setItem('theme', newTheme);
  });
</script>
```

## Design Changes

### Remove

- Gradients (`background: linear-gradient(...)`)
- Glass effects (`backdrop-filter: blur(...)`)
- Glow shadows (`box-shadow: 0 0 40px...`)
- Radial gradient backgrounds

### Replace with

- Flat colors using CSS variables
- Subtle borders (`border: 1px solid var(--border)`)
- Simple hover states with border color changes
- Clean transitions (`transition: all 0.3s ease`)

## Files to Update

1. `/fast_dashboards/src/fast_dashboards/operations/api_dashboard/router.py` ✅
2. `/fast_dashboards/src/fast_dashboards/operations/health/dashboard.py`
3. `/fast_dashboards/src/fast_dashboards/operations/queues_dashboard/router.py`
4. `/fast_dashboards/src/fast_dashboards/operations/tenants_dashboard/router.py`
5. `/fast_dashboards/src/fast_dashboards/operations/secrets_dashboard/router.py`
6. `/fast_dashboards/src/fast_dashboards/operations/workflows_dashboard/router.py`

## Quick Apply Script

Use this sed/awk pattern to bulk update CSS variables (test first!):

```bash
# Backup files first
cp router.py router.py.bak

# Replace dark theme variables
sed -i 's/#0a0a0f/#0a0a0b/g' router.py
sed -i 's/#12121a/#141416/g' router.py
sed -i 's/#1a1a25/#1c1c1f/g' router.py
# ... etc
```

## Testing Checklist

- [ ] Dark mode renders correctly
- [ ] Light mode renders correctly
- [ ] Theme toggle switches between modes
- [ ] Theme preference persists in localStorage
- [ ] All functionality still works (buttons, forms, etc.)
- [ ] Responsive design works on mobile
- [ ] Scrollbars styled correctly
