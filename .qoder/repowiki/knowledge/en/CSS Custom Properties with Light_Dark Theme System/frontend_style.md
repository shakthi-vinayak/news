## Styling Approach

This repository uses a **vanilla CSS architecture** built on CSS custom properties (CSS variables) for theming and design tokens. No CSS preprocessor, framework (Tailwind, Bootstrap), or component library is employed. The styling system is lightweight, dependency-free, and designed for a static documentation site.

### Core Design Decisions

1. **CSS Custom Properties as Design Tokens**: All colors, spacing, shadows, typography, and radii are defined as CSS custom properties in `:root`. This creates a single source of truth for the visual language.

2. **Dual-Theme Support via Data Attribute**: Dark mode is implemented by toggling `[data-theme="dark"]` on the `<html>` element. The theme toggle button persists user preference to `localStorage`, and the CSS cascade automatically swaps all token values when the attribute changes.

3. **No Build Step Required**: The CSS is authored as a single flat file (`style.css`) with no compilation, bundling, or post-processing. This aligns with the project's zero-build-step philosophy (also reflected in the vanilla JS app).

4. **BEM-Inspired Naming Convention**: Class names follow a modified BEM pattern with double underscores for elements (e.g., `.news-card__title`, `.job-card__header`). This provides clear scoping without requiring a CSS-in-JS or module system.

5. **Responsive Strategy**: A single mobile breakpoint at `600px` collapses the header layout, card grid to single column, and filter bar to vertical stacking. The card grid uses `auto-fill` with `minmax(340px, 1fr)` for fluid responsiveness above that threshold.

## Key Files

- **`docs/assets/style.css`** — The sole stylesheet (~260 lines). Contains:
  - CSS reset (box-sizing, margin/padding zeroing)
  - `:root` design token definitions (light theme defaults)
  - `[data-theme="dark"]` override block (dark theme tokens)
  - Component styles organized by section comments: Header, Tabs, Filters, Card Grid, News Card, Job Card, Pagination, Empty/Error States, Footer, Responsive
- **`docs/index.html`** — Static HTML structure referencing `style.css` and `app.js`. Uses semantic HTML5 elements (`<header>`, `<nav>`, `<section>`, `<article>`, `<footer>`) with ARIA roles for accessibility.
- **`docs/assets/app.js`** — Vanilla JavaScript handling theme toggle persistence, tab switching, data fetching, filtering, pagination, and dynamic card rendering. The JS generates HTML strings injected into the DOM; no client-side templating engine is used.

## Architecture & Conventions

### Design Token Structure

The `:root` block defines these token categories:

| Category | Tokens | Purpose |
|---|---|---|
| **Surfaces** | `--bg`, `--surface`, `--surface-alt` | Background layers |
| **Typography** | `--text`, `--text-muted`, `--font` | Text colors and font stack |
| **Interactive** | `--accent`, `--accent-hover` | Primary action color |
| **Semantic** | `--danger`, `--warn`, `--success` | Status indicators |
| **UI Elements** | `--tag-bg`, `--tag-text`, `--border` | Badge and border colors |
| **Metrics** | `--radius`, `--shadow`, `--shadow-md` | Spacing and elevation |

Dark mode overrides ~12 of these tokens while inheriting the rest (e.g., `--radius`, `--font` remain unchanged).

### Component Patterns

- **Cards** (`.news-card`, `.job-card`): Flexbox column layout with hover effects (`box-shadow` increase + `translateY(-2px)`). Titles use `-webkit-line-clamp` for multi-line truncation.
- **Badges** (`.source-badge`, `.location-badge`, `.salary-badge`, `.category-badge`, `.tag`): Inline-block elements with distinct color pairs per badge type. Each has its own light/dark color pair defined directly in the rule (not via tokens), which is a minor inconsistency.
- **Filters Bar**: Flex-wrap layout with consistent input/select styling. Focus states highlight with `--accent` border color.
- **Pagination**: Centered flex row with active page highlighted via `--accent` background.

### Accessibility Considerations

- ARIA roles (`tablist`, `tab`, `tabpanel`, `list`, `listitem`, `alert`) are applied in HTML.
- `aria-selected`, `aria-labelledby`, and `aria-live` attributes provide screen reader context.
- Theme toggle button includes `aria-label` and `title`.
- Color contrast ratios appear considered (e.g., dark mode uses lighter text on darker backgrounds).

## Rules Developers Should Follow

1. **Add new design tokens to `:root`**, not inline styles. If a new color/spacing value is needed, define it as a CSS custom property first.

2. **Mirror dark mode overrides**: When adding a new token that should change in dark mode, add the corresponding override in the `[data-theme="dark"]` block.

3. **Use existing badge patterns**: New badge types should follow the established pattern of separate light/dark color pairs defined directly in the selector (e.g., `.new-badge { background: #xxx; color: #yyy; } [data-theme="dark"] .new-badge { background: #aaa; color: #bbb; }`).

4. **Maintain BEM-style naming**: Use `component__element` for nested elements within cards or sections. Avoid deep nesting in selectors.

5. **Keep the single-breakpoint responsive strategy**: Additional breakpoints should only be added if there is clear evidence of layout issues at intermediate widths. The current approach prioritizes simplicity.

6. **No external dependencies**: Do not introduce CSS frameworks, icon libraries, or font CDNs. The project intentionally avoids build tooling and external runtime dependencies.

7. **Hover/transition consistency**: Interactive elements should use `transition` properties matching existing patterns (`.15s` for most interactions, `.2s` for body background/color transitions).

8. **Card hover effects**: New card components should replicate the `box-shadow` + `transform: translateY(-2px)` hover pattern for visual consistency.