# Design: Personal Portfolio Website

**Date:** 2026-05-26
**Owner:** Lahari Karumanchi
**Status:** Draft — pending user review

---

## 1. Goal

A lean, minimal-academic personal site that funnels recruiters from a 10-second skim of the landing page into a deep read of at least one project case study. Optimized for the Summer 2026 ML/SWE internship recruiting cycle.

## 2. Audience

Primary: recruiters and hiring managers screening early-career ML/SWE candidates.
Secondary: future collaborators, professors, and people Lahari shares the link with directly.

The design optimizes for the primary audience. The blog and "about" sections serve the secondary audience without distracting the primary one.

## 3. Site architecture

```
   /                                  ← Landing (single scroll, recruiter funnel)
   ├── /projects/
   │     ├── data-analysis-agent      ← NEW project — featured prominently
   │     ├── document-qa-rag
   │     ├── multi-tool-agent
   │     ├── churn-prediction
   │     └── movie-recommender
   ├── /blog/
   │     ├── building-da-agent        ← launch post #1 (technical)
   │     └── why-evals-matter         ← launch post #2 (opinion)
   ├── /about
   └── /resume.pdf                    ← static file, no HTML wrapper
```

**Top-nav tabs:** `Projects · Blog · About · Résumé`

## 4. Landing page structure

A single scrolling page with five sections in this order:

| # | Section | Purpose | Content |
|---|---|---|---|
| 1 | **Hero** | Establish identity in one breath | Name, one-line bio, location, links (GitHub, LinkedIn, email). No photo for v1; can revisit. |
| 2 | **Featured project** | The hook | Large card for the **Data Analysis Agent** with benchmark number front-and-center, one-paragraph summary, links to GitHub + live demo + case study. |
| 3 | **Other projects** | Demonstrate breadth | Four smaller cards (Document Q&A RAG, Multi-Tool Agent, Churn Prediction, Movie Recommender) — title, one-line, tech stack tags, "View →" link to case study. |
| 4 | **Recent writing** | Signal depth | Two most-recent blog posts as cards. If no blog posts exist, this section is hidden (not shown empty). |
| 5 | **About + résumé CTA** | Closer | Two-paragraph bio (longer than the hero line, gives texture) + résumé download button + secondary contact. |

There is no separate `/` and home page — the landing page **is** the home page.

## 5. Project case-study template

Every project page (including the four legacy ones) uses the same template:

1. **One-line summary** — the elevator pitch, above the fold.
2. **Headline number** — the metric in large type (e.g., "0.83 ROC-AUC", "X% on DABench").
3. **Problem** — one paragraph: what was being solved and why it matters.
4. **Approach** — an architecture diagram (SVG) plus 2–3 paragraphs on the key technical decisions.
5. **Results** — a small table or chart with the actual measured outcome.
6. **What I'd do differently** — short, honest reflection. Signals self-awareness.
7. **Links** — GitHub repository; live demo if applicable; relevant references.

The template is a single MDX layout component reused for all projects. Adding a new project is a single MDX file in `src/content/projects/`.

## 6. Blog

- **Launch content:** two posts published on day one so the blog does not look abandoned:
  1. **"Building a Data Analysis Agent from Scratch"** — technical writeup of the new project. Includes the agent loop, the code-as-action design choice, and the eval methodology. Cross-links the project case study.
  2. **"Why I'm Obsessed with LLM Evaluations"** (working title) — short opinion piece, ~600 words, on the value of evaluations in agent work. Demonstrates thinking-out-loud beyond just shipping projects.
- **Format:** MDX, so future posts can embed code blocks, charts, and components.
- **No** comments, no newsletter signup, no related-posts widget, no tagging system. Minimal-academic means minimal.
- **Future cadence:** intentionally undefined. Empty or stale blogs hurt; better to publish two solid posts and pause than to commit to a schedule and miss it.

## 7. Visual design system

| Aspect | Choice | Rationale |
|---|---|---|
| Aesthetic | Minimal-academic (Karpathy, James H. Fisher) | Reads as "I'm here for the work" — strongest signal for ML/research-leaning roles. |
| Body type | System sans (`-apple-system, Inter, sans-serif`) | Universally legible, no webfont download. |
| Heading type | Serif (`Iowan Old Style, Georgia, serif`) | Subtle academic feel; system fonts only. |
| Palette | 3 colors — ink `#1a1a1a`, paper `#fafaf7`, link blue `#0a5dae` | Restraint; nothing flashy. |
| Layout | Single column, 680px max width for prose; wider only for project-card grids | Reads like a journal article. |
| Imagery | Hand-styled SVG diagrams; no stock photography | Reinforces the considered aesthetic. |
| Dark mode | Out of scope for v1 | Adds work; the light-mode look is the signature. Revisit after launch. |
| Animations | Only simple hover/transition states; no scroll-triggered effects | Discipline; visual restraint is part of the brand. |

## 8. Stack & hosting

| Choice | Value | Why |
|---|---|---|
| Framework | **Astro** | Best static-site DX for a content-heavy site; clean MDX support; minimal JS shipped to the client; doesn't require deep React knowledge. |
| Hosting | **Vercel** (or Cloudflare Pages if simpler) | Free tier handles a portfolio forever; git push → deploy in ~30s; preview deploys per PR. |
| Domain | `<username>.vercel.app` for v1 | Custom domain (`lahari.dev`, ~$10/year) deferred — explicitly chosen by user, easy to swap in later. |
| Analytics | None in v1 | Plausible (privacy-friendly) is an easy add-on if/when wanted. |

## 9. Performance & accessibility

Non-negotiable for a portfolio that signals technical seriousness:

- Lighthouse score **≥ 95** on Performance, Accessibility, Best Practices, and SEO.
- Semantic HTML; correct heading hierarchy on every page.
- `alt` text on every image; descriptive link text (no "click here").
- Keyboard-navigable nav and project cards.
- No JS on routes that don't need it (Astro defaults handle this).
- Font subsetting; no FOUT/FOIT.

## 10. Repository layout

```
src/
  pages/
    index.astro                   # landing
    about.astro
    blog/
      index.astro                 # blog index
      [...slug].astro             # individual post route
    projects/
      [...slug].astro             # individual project route
  layouts/
    BaseLayout.astro              # nav, footer, head
    ProjectLayout.astro           # case-study template
    BlogLayout.astro              # post template
  components/
    Hero.astro
    ProjectCard.astro
    PostCard.astro
  content/
    projects/
      data-analysis-agent.mdx
      document-qa-rag.mdx
      multi-tool-agent.mdx
      churn-prediction.mdx
      movie-recommender.mdx
    blog/
      building-da-agent.mdx
      why-evals-matter.mdx
  styles/
    global.css                    # design tokens, base styles
public/
  resume.pdf
  diagrams/                       # SVGs for projects
astro.config.mjs
package.json
README.md
```

## 11. Out of scope (deliberate)

- Authentication, user accounts, comments, server-side forms.
- A CMS — content lives in `.mdx` files in the repo and is edited by code.
- Dark mode (v1).
- Custom domain (v1 — explicit user decision).
- Internationalization.
- E-commerce, paywalls, gated content.
- A "press" or "speaking" page — premature for an undergraduate.

## 12. Open questions

- **Headshot or no headshot in hero?** Defaulting to no for v1; revisit once a strong photo exists.
- **Should the case-study pages embed the Streamlit demo via iframe, or just link out?** Lean toward link-out for performance and simplicity; revisit once the demo is live.
- **Light favicon, dark favicon, or both (theme-aware)?** Defer to implementation.

## 13. Success criteria

The portfolio is "done" when:

- All five project case-study pages exist with the full template filled in.
- The two launch blog posts are published.
- Lighthouse scores ≥ 95 across all four categories on the landing and a representative project page.
- The site is deployed and publicly accessible.
- The résumé PDF download works.
- The Data Analysis Agent project page links to the live demo and the GitHub repo.

## 14. Dependency on the Data Analysis Agent project

The portfolio's headline section is the Data Analysis Agent. The site can technically launch without the DA Agent (using a "coming soon" card for the featured slot), but the recommended sequence is:

1. Ship the DA Agent (or at least an MVP with a benchmark number).
2. Then launch the portfolio with the DA Agent as the centerpiece.

Implementation planning should respect this ordering.
