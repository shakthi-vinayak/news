## Frontend Styling Architecture

This repository uses a **vanilla CSS custom properties (CSS variables) system** for theming and styling, with no CSS framework, preprocessor, or build step. The entire frontend is a static site served from the `docs/` directory.

### Design Token System

The styling system is built around CSS custom properties defined in `:root` for light mode and `[data-theme="dark"]` for dark mode. These tokens control:

- **Color palette**: Backgrounds (`--bg`, `--surface`, `--surface-alt`), borders (`--border`), text (`--text`, `--text-muted`), accents (`--accent`, `--accent-hover`), semantic colors (`--danger`, `--warn`, `--success`), tag colors (`--tag-bg`, `--tag-text`)
- **Layout primitives**: Border radius (`--radius: 10px`), shadows (`--shadow`, `--shadow-md`)
- **Typography**: Font stack (`--font: system-ui, -apple-system, 'Segoe UI', sans-serif`)

Dark mode overrides approximately 12 of these tokens with darker values, maintaining consistent contrast ratios.

### Theme Toggle Implementation

Theme switching is handled via JavaScript that:
1. Reads saved preference from `localStorage.getItem('theme')`
2. Sets `data-theme` attribute on the `<html>` element
3. Toggles emoji icon (🌙/☀️) on the button
4. Persists user choice back to `localStorage`

The CSS transitions on `background` and `color` properties (`.2s` duration) provide smooth theme switching.

### Component Styling Patterns

Components follow a **BEM-like naming convention** with double underscores for elements:
- `.news-card`, `.news-card__title`, `.news-card__summary`, `.news-card__meta`, `.news-card__tags`
- `.job-card`, `.job-card__header`, `.job-card__title-block`, `.job-card__company`
- `.site-header`, `.header-inner`, `.brand`, `.brand-icon`, `.brand-name`
- `.tab-nav`, `.tab-btn`, `.tab-panel`
- `.filters-bar`, `.filter-input`, `.filter-select`, `.btn-secondary`
- `.pagination`, `.page-btn`

Badge components use inline styles with theme-aware dark mode overrides:
- `.source-badge`, `.location-badge`, `.salary-badge`, `.category-badge`, `.tag`

### Responsive Strategy

A single mobile breakpoint at `600px` handles responsive behavior:
- Header stacks vertically (`flex-direction: column`)
- Card grid collapses to single column (`grid-template-columns: 1fr`)
- Filters switch from horizontal flex to vertical stacking
- Inputs expand to full width

The card grid uses CSS Grid with `auto-fill` and `minmax(340px, 1fr)` for fluid column counts on larger screens.

### Key Architectural Decisions

1. **Zero dependencies**: No CSS framework, no build tool, no preprocessor
2. **Single stylesheet**: All styles in one file (`docs/assets/style.css`, 260 lines)
3. **CSS-only transitions**: Smooth theme switching without JavaScript animation libraries
4. **Semantic color tokens**: Named by purpose (not by color value) for maintainability
5. **Inline badge styling**: Some badges use hardcoded hex values with explicit `[data-theme="dark"]` overrides rather than tokens

### Developer Conventions

When extending the styling system:

1. **Use existing CSS custom properties** for colors, spacing, and effects — do not hardcode hex values unless creating a new token
2. **Follow BEM-like naming** for new components: `.component-name__element--modifier`
3. **Add dark mode support** by adding `[data-theme="dark"]` rules for any component with hardcoded colors
4. **Maintain the single-breakpoint approach** — add responsive rules inside the existing `@media (max-width: 600px)` block
5. **Keep transitions lightweight** — use the existing `.15s` / `.2s` durations for consistency
6. **Preserve accessibility** — ensure focus states, contrast ratios, and ARIA attributes remain intact when modifying components
7. **No CSS preprocessing** — write plain CSS; there is no Sass/Less/Tailwind compilation pipeline

### Files

- `docs/assets/style.css` — Complete stylesheet with design tokens, component styles, and responsive rules
- `docs/assets/app.js` — Theme toggle logic (lines 71-84) and DOM manipulation
- `docs/index.html` — HTML structure with `data-theme="light"` default on `<html>` element
