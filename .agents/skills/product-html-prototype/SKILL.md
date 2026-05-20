---
name: product-html-prototype
description: create interactive single-file html product prototypes from prds, product requirements, design docs, user flows, wireframes, information architecture, component specs, or page descriptions. use when codex needs to turn product documents into clickable html prototypes with layouts, navigation, forms, modals, drawers, empty states, loading states, error states, success feedback, and multi-step flows. do not use for production frontend implementation unless the user explicitly asks for production code.
---

# Product HTML Prototype Skill

## Core behavior

When this skill is used, create an interactive product prototype from product requirements or design context.

Do not mechanically mirror the document structure. First infer:
1. target users
2. user goals
3. core jobs to be done
4. page list
5. information hierarchy
6. primary user path
7. secondary user paths
8. required components
9. required states
10. business rules and edge cases

Then generate a usable clickable prototype.

## Default output

Default to creating or updating:

prototype.html

The prototype must be:
- a single HTML file
- self-contained
- directly openable in a browser
- built with embedded CSS
- built with embedded JavaScript
- free of external CDN dependencies
- free of build steps
- free of framework requirements

Do not use React, Vue, Svelte, Tailwind CDN, Bootstrap CDN, icon CDNs, remote fonts, or external images unless the user explicitly asks.

Use semantic HTML, modern CSS, and plain JavaScript.

## Required design quality

The prototype should look like a mature product prototype, not a raw wireframe.

Default style:
- modern B2B SaaS
- clean layout
- restrained visual design
- neutral background
- clear typography
- card-based sections
- subtle borders
- light shadows
- rounded corners
- good spacing
- medium information density
- accessible contrast
- responsive layout

Prefer realistic product copy over lorem ipsum.

## Required interaction quality

Include meaningful interactions where relevant:
- page switching
- sidebar navigation
- tabs
- search
- filters
- table row selection
- detail drawer
- modal dialog
- form validation
- save success toast
- delete confirmation
- loading state
- empty state
- error state
- disabled state
- hover and focus states

For multi-page products, implement page switching inside the single HTML file using JavaScript, unless the user explicitly asks for multiple files.

## Workflow

Follow this workflow:

1. Locate and read the relevant product/design documents.
2. Summarize the product goal and user goal internally before coding.
3. Identify the minimum set of screens needed for a clickable prototype.
4. Identify the primary user path.
5. Identify required UI states.
6. Select an appropriate style preset from references/style-presets.md.
7. Select relevant component patterns from references/component-patterns.md.
8. Generate prototype.html.
9. Run scripts/validate_html.py against prototype.html.
10. If Playwright or browser tools are available, open the prototype and test the primary click path.
11. Fix any broken interactions, missing buttons, invalid selectors, or layout problems.
12. Report what was created, where it was saved, and what assumptions were made.

## Handling incomplete requirements

If the design document is incomplete:
- make reasonable product assumptions
- do not block unnecessarily
- include assumptions in comments at the top of prototype.html or in README.md
- preserve the core user goal
- prefer a coherent MVP flow over a broad but shallow prototype

## Handling conflicting requirements

If requirements conflict:
- choose the version most aligned with the primary user goal
- mention the conflict briefly
- encode the chosen assumption in README.md or comments
- do not stop unless the conflict makes generation impossible

## Modifying existing prototypes

When modifying an existing prototype.html:
1. create a backup first, named prototype.backup.html or prototype.<timestamp>.backup.html
2. preserve existing working interactions unless the user asks to replace them
3. update only the required parts when possible
4. re-run validation after modification

## Style control

If the user provides style guidance, obey it.

If the user does not provide style guidance, default to:
Modern B2B SaaS.

If the user references known visual styles such as Linear, Vercel, Stripe, Notion, Apple, or GitHub:
- use them only as broad visual inspiration
- do not copy logos
- do not copy brand assets
- do not copy proprietary layouts verbatim
- do not use trademarked content as page content

## Accessibility

The prototype should include:
- semantic landmarks where useful
- buttons for clickable actions
- labels for inputs
- visible focus states
- sufficient contrast
- keyboard-friendly modal close behavior where practical
- responsive behavior for smaller screens

## References

Load only the references needed for the current request:
- references/document-analysis.md for extracting goals, users, flows, entities, and states from documents.
- references/prototype-standards.md for the minimum quality bar.
- references/style-presets.md for choosing visual direction.
- references/component-patterns.md for selecting UI patterns.
- references/interaction-checklist.md before final validation.

## Before final response

Before responding to the user:
- confirm prototype.html exists
- confirm it has a title
- confirm it has viewport meta
- confirm it has embedded CSS
- confirm it has embedded JavaScript if interaction is required
- confirm primary buttons have click handlers
- confirm there is no external CDN unless explicitly requested
- confirm validation passed or explain any remaining limitation

## Final response format

Respond with:
1. Created/updated file path
2. Brief summary of screens
3. Brief summary of interactions
4. Assumptions made
5. How to open the prototype

Do not paste the full HTML into chat unless the user explicitly asks.
