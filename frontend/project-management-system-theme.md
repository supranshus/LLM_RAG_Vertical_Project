# Project Management System — Theme Guide

This guide lists the fonts, colors, sizes and component styles used in the Project Management System, so that every
screen looks the same. All values come from the original HTML designs (Create project, Generated documents).

---

## 1. Fonts

| Role | Font | Weights | Used for |
|---|---|---|---|
| Body | **IBM Plex Sans** | 400, 500, 600 | All normal text, inputs, buttons, labels |
| Display | **Space Grotesk** | 500, 600 | Page titles, section headings, card titles |
| Mono | **IBM Plex Mono** | 500 | Numbers, step badges, file names, chips, IDs, estimates |

Google Fonts link (one line, loads all three):

```html
<link href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@500;600&family=IBM+Plex+Sans:wght@400;500;600&family=IBM+Plex+Mono:wght@500&display=swap" rel="stylesheet">
```

Fallbacks: `'IBM Plex Sans', sans-serif` · `'Space Grotesk', sans-serif` · `'IBM Plex Mono', monospace`

### Type scale

| Element | Font | Size | Weight | Notes |
|---|---|---|---|---|
| Page title (e.g. "Set up a new project") | Space Grotesk | 33px | 600 | letter-spacing −0.015em |
| Viewer title (e.g. project name on documents page) | Space Grotesk | 29px | 600 | letter-spacing −0.015em |
| Section heading (h2) | Space Grotesk | 19px | 600 | |
| Document heading (h3) | Space Grotesk | 15.5px | 600 | |
| Card title (sprint, test case) | Space Grotesk | 15px | 600 | |
| Brand name in sidebar | Space Grotesk | 15px (14.5px on documents page) | 600 | letter-spacing −0.01em |
| Group title (task groups) | Space Grotesk | 14px | 600 | |
| Body text | IBM Plex Sans | 15px | 400 | line-height **1.55** everywhere |
| Document body text | IBM Plex Sans | 14.5px | 400 | |
| Sidebar item | IBM Plex Sans | 14px (13.5px on documents page) | 400 / 500 when active | |
| Buttons | IBM Plex Sans | 14px (13.5px in page headers) | 500 | |
| Notes, secondary text | IBM Plex Sans | 13.5px | 400 | |
| Form labels | IBM Plex Sans | 13px | 500 | color: text-secondary |
| Input text | IBM Plex Sans | 14px | 400 | |
| Hints, meta text | IBM Plex Sans | 12px | 400 | color: text-muted |
| Tags / badges | IBM Plex Sans | 11.5px | 500 | |
| Chips, IDs, step numbers, dates | IBM Plex Mono | 12–13px | 500 | |
| File names | IBM Plex Mono | 12.5px | 500 | |

**Mobile (≤ 860px):** page title 26px, viewer title 24px, sidebar labels 11px.

---

## 2. Colors

### Core palette

| Token | Hex | Used for |
|---|---|---|
| `--ink` | `#11201C` | Main text color |
| `--paper` | `#F1F4F0` | Page background |
| `--panel` | `#0E2B24` | Dark sidebar background |
| `--route` | `#33D2A0` | Bright highlight: active step, status dot, check marks, icons on primary buttons |
| `--accent` | `#1F6F58` | Primary buttons, focus borders, links |
| `--accent-dark` | `#175245` | Primary button hover, text on soft-green backgrounds |
| `--accent-soft` | `#E1F0E9` | Soft green backgrounds: chips, active toggle, avatars, focus ring |
| `--text-secondary` | `#57685F` | Labels, notes, secondary text |
| `--text-muted` | `#8B9A92` | Hints, meta text, placeholders, inactive icons |
| `--border` | `#DCE4DD` | All normal borders and dividers |
| `--border-strong` | `#C3CFC5` | Hover borders, dashed upload border |
| `--danger` | `#B3261E` | Delete / remove hover, errors |
| White | `#FFFFFF` | Cards, inputs, secondary buttons |

### Supporting surfaces

| Hex | Used for |
|---|---|
| `#E9F0E9` | Page header box (with a dot pattern: `radial-gradient(rgba(17,32,28,0.09) 1px, transparent 1px)`, size 15px) |
| `#FAFBF9` | Card toolbars, sprint cards (very light grey-green) |

### On the dark sidebar

| Value | Used for |
|---|---|
| `#FFFFFF` | Brand name, active item text |
| `rgba(255,255,255,0.85)` | Item text on hover |
| `rgba(255,255,255,0.75)` | Completed step label |
| `rgba(255,255,255,0.55)` / `0.5` | Normal item text |
| `rgba(255,255,255,0.45)` | Brand subtitle |
| `rgba(255,255,255,0.4)` | Inactive icons |
| `rgba(255,255,255,0.22)` | Step circle border |
| `rgba(255,255,255,0.12)` | Divider lines, step connector line |
| `rgba(255,255,255,0.06)` | Item hover background |
| `rgba(51,210,160,0.14)` | Active item / completed step background |

### Tags (background / text)

| Tag | Background | Text |
|---|---|---|
| Frontend | `#E1F0E9` | `#175245` |
| Backend | `#E7ECF3` | `#3A5A85` |
| QA | `#FBF0DE` | `#8A5A17` |
| Design | `#F3E9F1` | `#7A4368` |
| PM | `#EDEEEC` | `#57685F` |
| Must / Critical | `#FBEAEA` | `#A3372F` |
| Should / High | `#FDF3E3` | `#8A5A17` |
| Could / Medium | `#EDEEEC` | `#57685F` |

---

## 3. Shape (corner radius)

| Radius | Used for |
|---|---|
| 6px | Small ID badges (e.g. `TC-01`) |
| 8px | Inputs, selects, text areas, upload box, small square buttons |
| 10px | Sidebar items, task lists |
| 12px | Inner cards (sprint cards, test case cards) |
| 16px | Large panels: sidebar, page header, document cards |
| 999px (pill) | Buttons, chips, tags, toggles |
| 50% | Avatars, step circles, status dot |

---

## 4. Layout and spacing

| Item | Value |
|---|---|
| Page max width | 1080px, centered |
| Page padding | 48px top, 24px sides, 96px bottom |
| Columns | Sidebar **250px** + content **up to 700px**, gap **40px** |
| Sidebar | Sticky, 40px from top; padding 26px 22px |
| Page header box | Padding 40px 40px 34px; 40px below it |
| Sections | 38px padding top and bottom, 1px divider line between sections |
| Space between form fields | 20px |
| Gap between fields in a row | 16px |
| Card body padding | 30px 32px 34px |
| Card toolbar padding | 15px 24px |
| Action bar | 44px above, 24px padding top, divider line, buttons right-aligned, 10px apart |
| Mobile breakpoint | **860px**: sidebar moves above content, rows become single columns |

---

## 5. Components

**Primary button**: background `#1F6F58`, white text, 1px border same color, pill shape, padding 11px 22px,
14px / 500. Hover: `#175245`. Its icon uses `#33D2A0`.

**Secondary button**: white background, 1px `#DCE4DD` border, ink text, same size and shape. Hover: border `#C3CFC5`.

**Small outline button** (e.g. "Add member"): no fill, 1px `#DCE4DD` border, text `#175245`, 13px / 500,
padding 7px 16px 7px 12px. Hover: border `#1F6F58`.

**Icon-only square button** (e.g. remove): 34 × 34px, white, 1px border, 8px radius, muted icon.
Hover: icon and border `#B3261E`.

**Inputs / selects / text areas**: white, 1px `#DCE4DD` border, 8px radius, padding 10px 12px, 14px text.
Placeholder `#8B9A92`. Text areas are at least 76px tall.
**Focus:** border `#1F6F58` + ring `0 0 0 3px #E1F0E9`, no outline.

**Toggle (segmented)**: white pill with a 1px border and 4px padding. Options are 13px / 500, `#57685F`.
The selected option has a `#E1F0E9` background and `#175245` text.

**Upload box**: 1.5px dashed `#C3CFC5`, 8px radius, padding 14px 16px. Hover: border `#1F6F58`, background
`#E1F0E9`, text `#175245`.

**Stat chip**: mono 12px, text `#175245` on `#E1F0E9`, pill, padding 5px 12px.

**Status dot**: 8px circle `#33D2A0` with ring `0 0 0 3px rgba(51,210,160,0.18)`.

**Avatar**: circle, `#E1F0E9` background, `#175245` mono initials (600). 26px in stacks with a 2px white border and
−8px overlap. 22px in task rows.

**Sidebar steps**: 38px circles with a 1.5px border.
- Normal: border `rgba(255,255,255,0.22)`.
- Done: border `#33D2A0`, text `#33D2A0`, background `rgba(51,210,160,0.14)`.
- Active: filled `#33D2A0`, dark text, glow `0 0 0 5px rgba(51,210,160,0.16)`.
- A 2px line connects the circles.

**Document card**: white, 1px border, 16px radius. Toolbar on `#FAFBF9` with an icon, a mono file name and meta
text on the right.

---

## 6. Icons

- Line icons on a 24 × 24 grid, **stroke width 1.75** (2 for small check / plus / close).
- Round line caps and joins, no fill, drawn in the current text color.
- Sizes: 15–20px. Common sizes are 16px in toolbars and buttons, 17px in the sidebar and 20px for the brand pin.
- The brand mark is a **map pin** (location marker) in `#33D2A0`.

---

## 7. Motion

- Hover and focus changes: **0.15s ease** (step circles: 0.2s ease).
- No other animation.
- Users who turn on "reduce motion" get no transitions and no smooth scrolling.

---

## 8. Using it in a Streamlit app

Put this in `.streamlit/config.toml`:

```toml
[theme]
base = "light"
primaryColor = "#1F6F58"
backgroundColor = "#F1F4F0"
secondaryBackgroundColor = "#FFFFFF"
textColor = "#11201C"
linkColor = "#175245"
borderColor = "#DCE4DD"
showWidgetBorder = true
baseRadius = "8px"
buttonRadius = "999px"
baseFontSize = 15
font = "IBM Plex Sans:https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600&display=swap"
headingFont = "Space Grotesk:https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@500;600&display=swap"
codeFont = "IBM Plex Mono:https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@500&display=swap"
```

## 9. CSS variables (copy-paste)

```css
:root {
  --ink: #11201C;
  --paper: #F1F4F0;
  --panel: #0E2B24;
  --route: #33D2A0;
  --accent: #1F6F58;
  --accent-dark: #175245;
  --accent-soft: #E1F0E9;
  --text-secondary: #57685F;
  --text-muted: #8B9A92;
  --border: #DCE4DD;
  --border-strong: #C3CFC5;
  --danger: #B3261E;
  --radius: 8px;
  --font-body: 'IBM Plex Sans', sans-serif;
  --font-display: 'Space Grotesk', sans-serif;
  --font-mono: 'IBM Plex Mono', monospace;
}
```
