# Portfolio Website Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a lean, minimal-academic Astro portfolio that funnels recruiters from a 10-second skim of the landing page into a deep read of at least one project case study. Optimized for the Summer 2026 ML/SWE internship recruiting cycle.

**Architecture:** Astro static site, MDX content collections for projects + blog posts, three layouts (Base, Project, Blog), single design-tokens CSS file. Deploys to Vercel free tier. No client-side JavaScript by default.

**Tech Stack:** Astro 4+, MDX, system fonts (serif headers + sans body), Vercel hosting, optional `@astrojs/sitemap` integration.

**Spec reference:** [docs/superpowers/specs/2026-05-26-portfolio-website-design.md](../specs/2026-05-26-portfolio-website-design.md)

**Blocked on:** Per spec §14, the portfolio cannot launch publicly until the Data Analysis Agent has hit its MVP gate (working CLI + working demo + 80-task benchmark number). Implementation can begin in parallel, but the final deploy waits for the agent's MVP.

---

## Repository decision (decide before Task 1)

The agent project lives at `/Users/anilkumar/Lahari/` (currently pushed to `github.com/laharikarumanchi-AI-ML/superpowers`). The portfolio can go in one of two places:

| Option | Pro | Con |
|---|---|---|
| **Separate repo** (`lahari-portfolio`) — Recommended | Cleaner: distinct stack (Astro vs Python), distinct deploy (Vercel vs HF), distinct READMEs. Recruiters see one repo per project, not a sprawling monorepo. | Two repos to manage. |
| **Subdirectory of agent repo** (`portfolio/`) | Single repo to push. | Mixes two stacks; the GitHub repo page becomes confusing (which README is "the" one?). |

**Default in this plan: separate repo.** Create `/Users/anilkumar/portfolio/` locally, then push to a new GitHub repo named `portfolio` (or `lahari-karumanchi`).

If you'd rather use the subdirectory approach, the paths below need to be prefixed with `portfolio/` and the deploy task adjusted.

---

## File Structure (target)

```
portfolio/
  astro.config.mjs
  package.json
  tsconfig.json
  src/
    pages/
      index.astro                   # landing
      about.astro
      404.astro
      blog/
        index.astro                 # blog index
        [...slug].astro             # individual post route
      projects/
        [...slug].astro             # individual project route
    layouts/
      BaseLayout.astro              # nav, footer, head, OG meta
      ProjectLayout.astro           # case-study template
      BlogLayout.astro              # post template
    components/
      Hero.astro
      ProjectCard.astro
      PostCard.astro
      Nav.astro
      Footer.astro
    content/
      config.ts                     # zod schemas for content collections
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
    resume.pdf                      # static download (Lahari adds her latest)
    og-default.png                  # 1200x630 default social card
    favicon.svg
  README.md
```

---

## Conventions

- **No client-side JS** by default. Astro's static output is what makes Lighthouse Performance ≥ 95 trivial.
- **MDX, not HTML in components.** Content is data; components render it.
- **One CSS file** (`src/styles/global.css`) with custom properties for tokens. No frameworks (no Tailwind, no CSS-in-JS). Minimal-academic means restrained.
- **Frontmatter schemas via Zod** in `src/content/config.ts` — Astro will type-check every MDX file's frontmatter.
- **Commit per task** — TDD-discipline doesn't apply to mostly-presentational frontend, but small atomic commits do.

---

# Phase 1 — Scaffold

## Task 1: Create the Astro project

**Files:** entire `portfolio/` directory.

- [ ] **Step 1: Scaffold via `npm create astro`**

```bash
cd /Users/anilkumar/
npm create astro@latest portfolio -- --template minimal --typescript strict --no-install --no-git
cd portfolio
```

This creates a bare TypeScript-strict Astro project. The `--no-install` is so we can review `package.json` first; `--no-git` because we'll `git init` ourselves.

- [ ] **Step 2: Install + verify the dev server starts**

```bash
npm install
npm run dev
# In another terminal: curl -sI http://localhost:4321/ | head -2
# Expected: HTTP 200
# Then Ctrl-C the dev server.
```

- [ ] **Step 3: Add MDX + sitemap integrations**

```bash
npx astro add mdx --yes
npx astro add sitemap --yes
```

The MDX integration enables `.mdx` files in `src/content/`. The sitemap integration auto-generates `sitemap-index.xml` from your pages — needed for Lighthouse SEO ≥ 95.

- [ ] **Step 4: Set the site URL in `astro.config.mjs`**

Add `site: 'https://lahari-portfolio.vercel.app'` (or whatever the eventual Vercel URL will be — see Task 16). The sitemap integration needs this to emit absolute URLs.

- [ ] **Step 5: Init git, gitignore, first commit**

```bash
git init -b main
# .gitignore is already created by Astro template; verify it includes node_modules/, dist/, .astro/
git add .
git commit -m "chore: scaffold Astro portfolio with MDX + sitemap"
```

---

# Phase 2 — Content schemas + layouts

## Task 2: Content collection schemas

> **Note on Astro v6** (current as of this writing): the legacy `src/content/config.ts` + `type: 'content'` pattern was removed. Schemas now live at `src/content.config.ts` and each collection takes a `loader: glob(...)` pointing at the MDX directory. The `getCollection()` API used by downstream pages is unchanged. Code below uses the v6 shape.

**Files:** Create `src/content.config.ts` (NOT `src/content/config.ts`).

```typescript
import { defineCollection, z } from 'astro:content';
import { glob } from 'astro/loaders';

const projects = defineCollection({
  loader: glob({ pattern: '**/*.{md,mdx}', base: './src/content/projects' }),
  schema: z.object({
    title: z.string(),
    oneLiner: z.string(),           // appears on cards and at top of case study
    headlineNumber: z.string(),     // e.g. "0.83 ROC-AUC"
    techStack: z.array(z.string()),
    year: z.number(),
    githubUrl: z.string().url().optional(),
    demoUrl: z.string().url().optional(),
    featured: z.boolean().default(false),
    order: z.number(),              // for sorting cards on landing
  }),
});

const blog = defineCollection({
  loader: glob({ pattern: '**/*.{md,mdx}', base: './src/content/blog' }),
  schema: z.object({
    title: z.string(),
    description: z.string(),
    publishedAt: z.coerce.date(),
    draft: z.boolean().default(false),
  }),
});

export const collections = { projects, blog };
```

Commit:
```bash
git add src/content/config.ts
git commit -m "feat(content): zod schemas for projects + blog collections"
```

## Task 3: Design tokens + global styles

**Files:** Create `src/styles/global.css`.

```css
:root {
  --ink: #1a1a1a;
  --paper: #fafaf7;
  --link: #0a5dae;
  --muted: #555;
  --rule: #d8d8d3;

  --font-serif: 'Iowan Old Style', 'Charter', Georgia, serif;
  --font-sans: -apple-system, BlinkMacSystemFont, 'Inter', sans-serif;
  --font-mono: ui-monospace, 'SF Mono', Menlo, monospace;

  --content-width: 680px;
  --wide-width: 960px;

  --space-1: 0.5rem;
  --space-2: 1rem;
  --space-3: 1.5rem;
  --space-4: 2.5rem;
  --space-5: 4rem;
}

* { box-sizing: border-box; }

html {
  font-family: var(--font-sans);
  color: var(--ink);
  background: var(--paper);
  line-height: 1.65;
  -webkit-font-smoothing: antialiased;
}

body {
  margin: 0;
  padding: var(--space-2);
  max-width: var(--content-width);
  margin-inline: auto;
}

main.wide {
  max-width: var(--wide-width);
}

h1, h2, h3, h4 {
  font-family: var(--font-serif);
  font-weight: 600;
  line-height: 1.2;
  margin-block: var(--space-4) var(--space-2);
}

h1 { font-size: 2.25rem; }
h2 { font-size: 1.5rem; }
h3 { font-size: 1.2rem; }

a {
  color: var(--link);
  text-decoration: underline;
  text-underline-offset: 2px;
}
a:hover { text-decoration-thickness: 2px; }

code, pre {
  font-family: var(--font-mono);
  font-size: 0.9em;
}

pre {
  background: #f0f0eb;
  padding: var(--space-2);
  overflow-x: auto;
}

hr {
  border: none;
  border-top: 1px solid var(--rule);
  margin-block: var(--space-4);
}

img { max-width: 100%; height: auto; }
```

Commit:
```bash
git add src/styles/global.css
git commit -m "feat(styles): design tokens + minimal-academic base"
```

## Task 4: BaseLayout with SEO meta

**Files:** Create `src/layouts/BaseLayout.astro`.

```astro
---
import '../styles/global.css';
import Nav from '../components/Nav.astro';
import Footer from '../components/Footer.astro';

interface Props {
  title: string;
  description: string;
  ogImage?: string;
  wide?: boolean;
}

const { title, description, ogImage = '/og-default.png', wide = false } = Astro.props;
const canonical = new URL(Astro.url.pathname, Astro.site).toString();
---
<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>{title}</title>
    <meta name="description" content={description} />
    <link rel="canonical" href={canonical} />
    <link rel="icon" type="image/svg+xml" href="/favicon.svg" />

    <meta property="og:type" content="website" />
    <meta property="og:title" content={title} />
    <meta property="og:description" content={description} />
    <meta property="og:image" content={new URL(ogImage, Astro.site).toString()} />
    <meta property="og:url" content={canonical} />

    <meta name="twitter:card" content="summary_large_image" />
    <meta name="twitter:title" content={title} />
    <meta name="twitter:description" content={description} />
    <meta name="twitter:image" content={new URL(ogImage, Astro.site).toString()} />
  </head>
  <body>
    <Nav />
    <main class={wide ? 'wide' : ''}>
      <slot />
    </main>
    <Footer />
  </body>
</html>
```

## Task 5: Nav + Footer components

**Files:** `src/components/Nav.astro`, `src/components/Footer.astro`.

`Nav.astro`:
```astro
---
const pages = [
  { href: '/', label: 'Lahari Karumanchi' },
  { href: '/#projects', label: 'Projects' },
  { href: '/blog', label: 'Blog' },
  { href: '/about', label: 'About' },
  { href: '/resume.pdf', label: 'Résumé' },
];
---
<nav style="display:flex; gap:1.5rem; padding-block:1.5rem; font-family:var(--font-serif); border-bottom:1px solid var(--rule);">
  {pages.map((p, i) => (
    <a href={p.href} style={i === 0 ? 'font-weight:600; margin-right:auto;' : ''}>{p.label}</a>
  ))}
</nav>
```

`Footer.astro`:
```astro
<footer style="margin-top:5rem; padding-block:2rem; border-top:1px solid var(--rule); font-size:0.9em; color:var(--muted);">
  <p>© {new Date().getFullYear()} Lahari Karumanchi. <a href="https://github.com/laharikarumanchi-AI-ML">GitHub</a> · <a href="https://www.linkedin.com/in/...">LinkedIn</a> · <a href="mailto:lahari.karumanchi01@gmail.com">Email</a></p>
</footer>
```

(Replace the LinkedIn URL with your actual profile.)

Commit:
```bash
git add src/layouts/BaseLayout.astro src/components/Nav.astro src/components/Footer.astro
git commit -m "feat(layout): base layout with SEO meta + nav/footer"
```

---

# Phase 3 — Content

## Task 6: Write the 5 project MDX files

**Files:** five files under `src/content/projects/`.

For each, frontmatter follows the schema in Task 2. Body uses the case-study template from spec §5: one-line summary → headline number → problem → approach → results → "what I'd do differently" → links.

- [ ] **Step 1: Create skeletons**

```bash
mkdir -p src/content/projects
```

Then write each `.mdx` file. Example for the featured project:

`src/content/projects/data-analysis-agent.mdx`:
```mdx
---
title: "Data Analysis Agent"
oneLiner: "A code-as-action agent that answers questions about CSV data by writing and executing Python in a sandboxed Jupyter kernel."
headlineNumber: "X% ABQ on InfiAgent-DABench"
techStack: ["Python", "jupyter_client", "Groq/Llama-3.3", "Streamlit"]
year: 2026
githubUrl: "https://github.com/laharikarumanchi-AI-ML/superpowers"
demoUrl: "https://huggingface.co/spaces/laharikarumanchi-AI-ML/data-analysis-agent"
featured: true
order: 1
---

## Problem
[1 paragraph: why structured data Q&A is interesting; why prior tool-call agents fall short on it.]

## Approach
[2-3 paragraphs: code-as-action loop, sandboxed Jupyter, custom (no LangChain), why I made each tradeoff. Include the SVG architecture diagram.]

## Results
| Configuration                       | ABQ on DABench |
|-------------------------------------|----------------|
| Llama-3.3-70B + retry               | X%             |
| Llama-3.3-70B no retry              | Y%             |
| Gemini-2.0-Flash + retry            | Z%             |

## What I'd do differently
[Honest reflection — 1 paragraph. The "what failed" details from your eval results file are the raw material.]

## Links
- GitHub: <a href="https://github.com/laharikarumanchi-AI-ML/superpowers">repo</a>
- Live demo: <a href="https://huggingface.co/spaces/...">Hugging Face Space</a>
```

- [ ] **Step 2: Create the other four** (`document-qa-rag.mdx`, `multi-tool-agent.mdx`, `churn-prediction.mdx`, `movie-recommender.mdx`) using the same template. Pull content directly from your resume's existing bullet points, expanded into the case-study sections.

For each legacy project, you may use the "Project at a glance" bullet-list shortcut from spec §13 if you don't have time for full architecture diagrams.

- [ ] **Step 3: Commit**

```bash
git add src/content/projects/
git commit -m "content: five project case studies"
```

## Task 7: Write the two launch blog posts

**Files:** `src/content/blog/building-da-agent.mdx`, `src/content/blog/why-evals-matter.mdx`.

- [ ] **Step 1: `building-da-agent.mdx`** — a technical writeup of the agent. Sections suggested:
  - Why code-as-action over tool-calls
  - The Jupyter sandbox (and how a "sandbox" is harder than it sounds — Phase 0 lessons)
  - The eval methodology, with the actual subset → ablation → full pipeline
  - Surprises (e.g. matplotlib backend issue, scorer schema mismatch)
  - Closing: what this taught you about agent engineering

- [ ] **Step 2: `why-evals-matter.mdx`** — 500–800 words, opinion piece. Suggested angle: "I almost shipped a substring scorer. Here's why I'm glad I didn't." (the Path A vs B scorer decision from the agent's Phase 0.) Concrete, personal, demonstrates judgment.

- [ ] **Step 3: Commit**

```bash
git add src/content/blog/
git commit -m "content: two launch blog posts"
```

## Task 8: About page

**Files:** `src/pages/about.astro`.

```astro
---
import BaseLayout from '../layouts/BaseLayout.astro';
---
<BaseLayout title="About — Lahari Karumanchi"
            description="Third-year CS student at CVR College of Engineering. ML projects, agents, and the occasional opinion.">
  <h1>About</h1>
  <p>
    [2 paragraphs of bio. Who you are, what you care about, what you're recruiting for.
    Tell the human story your projects don't.]
  </p>
  <h2>Reach me</h2>
  <p>
    Email: <a href="mailto:lahari.karumanchi01@gmail.com">lahari.karumanchi01@gmail.com</a><br/>
    GitHub: <a href="https://github.com/laharikarumanchi-AI-ML">laharikarumanchi-AI-ML</a><br/>
    LinkedIn: [link]
  </p>
</BaseLayout>
```

Commit:
```bash
git add src/pages/about.astro
git commit -m "feat(page): about"
```

---

# Phase 4 — Pages

## Task 9: Landing page

**Files:** `src/pages/index.astro`, `src/components/Hero.astro`, `src/components/ProjectCard.astro`, `src/components/PostCard.astro`.

The landing is a single scrolling page with five sections (per spec §4).

- [ ] **Step 1: `Hero.astro`** — name, one-line bio, contact links. Restrained.

- [ ] **Step 2: `ProjectCard.astro`** — receives the parsed Astro content entry. Renders title, oneLiner, techStack tags, "View →" link to `/projects/<slug>`. The "featured" variant is larger (used once); the default variant is compact (used in the grid).

- [ ] **Step 3: `PostCard.astro`** — receives a blog entry. Renders title, description, date, link to `/blog/<slug>`.

- [ ] **Step 4: `index.astro`**:

```astro
---
import { getCollection } from 'astro:content';
import BaseLayout from '../layouts/BaseLayout.astro';
import Hero from '../components/Hero.astro';
import ProjectCard from '../components/ProjectCard.astro';
import PostCard from '../components/PostCard.astro';

const projects = (await getCollection('projects')).sort((a, b) => a.data.order - b.data.order);
const featured = projects.find(p => p.data.featured);
const others = projects.filter(p => !p.data.featured);

const posts = (await getCollection('blog', ({ data }) => !data.draft))
  .sort((a, b) => +b.data.publishedAt - +a.data.publishedAt)
  .slice(0, 2);
---
<BaseLayout title="Lahari Karumanchi — ML projects + agents"
            description="Third-year CS student. Code-as-action agents, RAG, classical ML. Recruiting for Summer 2026 ML/SWE internships.">
  <Hero />

  {featured && (
    <section id="projects">
      <h2>Featured</h2>
      <ProjectCard entry={featured} variant="featured" />

      <h2 style="margin-top:3rem;">More projects</h2>
      <div style="display:grid; grid-template-columns:1fr 1fr; gap:1.5rem;">
        {others.map(p => <ProjectCard entry={p} variant="compact" />)}
      </div>
    </section>
  )}

  {posts.length > 0 && (
    <section id="writing">
      <h2 style="margin-top:3rem;">Recent writing</h2>
      <div style="display:grid; gap:1.5rem;">
        {posts.map(p => <PostCard entry={p} />)}
      </div>
    </section>
  )}

  <section id="about" style="margin-top:3rem;">
    <h2>About</h2>
    <p>[1-2 paragraphs of bio]</p>
    <p><a href="/resume.pdf" style="display:inline-block; padding:0.5rem 1rem; border:1px solid var(--ink); text-decoration:none;">Download résumé →</a></p>
  </section>
</BaseLayout>
```

- [ ] **Step 5: Commit**

```bash
git add src/pages/index.astro src/components/Hero.astro src/components/ProjectCard.astro src/components/PostCard.astro
git commit -m "feat(page): landing with hero, featured, projects grid, writing"
```

## Task 10: ProjectLayout + projects/[...slug].astro

**Files:** `src/layouts/ProjectLayout.astro`, `src/pages/projects/[...slug].astro`.

`ProjectLayout.astro` — render the case-study template (one-liner, headline number, body, links).

`[...slug].astro`:
```astro
---
import { getCollection, type CollectionEntry } from 'astro:content';
import ProjectLayout from '../../layouts/ProjectLayout.astro';

export async function getStaticPaths() {
  const projects = await getCollection('projects');
  return projects.map(entry => ({ params: { slug: entry.slug }, props: { entry } }));
}

const { entry } = Astro.props as { entry: CollectionEntry<'projects'> };
const { Content } = await entry.render();
---
<ProjectLayout entry={entry}>
  <Content />
</ProjectLayout>
```

Commit:
```bash
git add src/layouts/ProjectLayout.astro src/pages/projects/
git commit -m "feat(page): project case-study route"
```

## Task 11: BlogLayout + blog routes

**Files:** `src/layouts/BlogLayout.astro`, `src/pages/blog/index.astro`, `src/pages/blog/[...slug].astro`.

Mirror Task 10's structure for blog posts. The blog index lists all non-draft posts sorted by `publishedAt` descending.

Commit:
```bash
git add src/layouts/BlogLayout.astro src/pages/blog/
git commit -m "feat(page): blog index and post route"
```

## Task 12: 404 page

**Files:** `src/pages/404.astro`.

```astro
---
import BaseLayout from '../layouts/BaseLayout.astro';
---
<BaseLayout title="Not found — Lahari Karumanchi"
            description="That page doesn't exist.">
  <h1>404</h1>
  <p>That page doesn't exist. <a href="/">Back home →</a></p>
</BaseLayout>
```

Commit:
```bash
git add src/pages/404.astro
git commit -m "feat(page): 404"
```

---

# Phase 5 — Static assets

## Task 13: Résumé, favicon, default OG image

**Files:** `public/resume.pdf`, `public/favicon.svg`, `public/og-default.png`.

- [ ] **Step 1: Convert and place your résumé**

Convert your latest `Lahari_Karumanchi_Resume.docx` to PDF (e.g., open in Pages/Word and export). Place at `public/resume.pdf`.

- [ ] **Step 2: Create a favicon**

Simplest acceptable: a 32×32 SVG with your initials in serif. Many free generators online; minimal-academic style means: black "LK" on paper background, serif. Save as `public/favicon.svg`.

- [ ] **Step 3: Create a default OG image (1200×630)**

The image LinkedIn/Twitter shows when someone pastes your URL. Suggested content: your name in serif, the one-line bio, on the paper-colored background. Tools: Figma, Canva, or [@vercel/og](https://vercel.com/docs/concepts/functions/edge-functions/og-image-generation) if you want it programmatic.

Save as `public/og-default.png`. Test by pasting your eventual URL into [opengraph.xyz](https://www.opengraph.xyz/) post-deploy.

- [ ] **Step 4: Commit**

```bash
git add public/
git commit -m "assets: resume, favicon, default OG image"
```

---

# Phase 6 — Build, audit, deploy

## Task 14: Local build + audit

- [ ] **Step 1: Build and serve the production output**

```bash
npm run build
npm run preview
# Open http://localhost:4321/ in a browser.
```

Click through every page. Verify:
- All five project cards link to their case studies.
- All blog cards link to their posts.
- The résumé download works.
- Nav links work (including the in-page anchor to `#projects`).
- 404 page renders for an unknown URL.

- [ ] **Step 2: Run Lighthouse locally**

In Chrome DevTools → Lighthouse panel, run an audit on the landing page AND one project page. Both should score ≥ 95 on Performance, Accessibility, Best Practices, SEO.

Common failures and fixes:
- **SEO 90s, not 95+**: usually a missing `<meta description>` or canonical. Verify BaseLayout is being used by every page.
- **Accessibility < 95**: most often color contrast on muted text. The `--muted: #555` token meets WCAG AA on `--paper`, but verify in DevTools.
- **Performance < 95**: usually means a too-large image. PNG OG image should be < 200 KB.

Fix any issues in additional commits.

## Task 15: Mobile review on a real device

Lighthouse mobile emulation is a poor proxy for real phone rendering. Open the site on your actual phone (use your laptop's IP from the dev server: `npm run preview -- --host 0.0.0.0`, then `http://<laptop-ip>:4321/` from the phone). Look for:

- Hero name not awkwardly wrapping.
- Project cards stacking cleanly (the `grid-template-columns:1fr 1fr` should drop to single-column on narrow screens — add a `@media` rule if it doesn't).
- Tap targets (links) at least 44px high.

Fix and commit any mobile-specific tweaks.

## Task 16: Deploy to Vercel

- [ ] **Step 1: Push the portfolio repo to GitHub**

Create a new GitHub repo named `portfolio` (or whatever you choose). Then:
```bash
git remote add origin https://github.com/laharikarumanchi-AI-ML/portfolio.git
git push -u origin main
```

- [ ] **Step 2: Import into Vercel**

- Sign up at https://vercel.com (free, supports GitHub login).
- Click "Add New Project" → import the `portfolio` repo.
- Astro is autodetected. Accept defaults.
- Click Deploy. First deploy takes ~30 seconds.

- [ ] **Step 3: Capture the URL and update `astro.config.mjs`**

Vercel assigns `<repo-name>-<hash>.vercel.app`. Set the `site:` field in `astro.config.mjs` to this URL so sitemap and canonical tags work. Commit + redeploy automatic.

- [ ] **Step 4: Verify the live site**

- `https://<your-url>.vercel.app/` loads.
- `https://<your-url>.vercel.app/sitemap-index.xml` returns the sitemap.
- `https://<your-url>.vercel.app/resume.pdf` downloads.
- Paste the URL into LinkedIn, Twitter, and Discord → OG card renders correctly in all three.

## Task 17: Pre-launch checklist walkthrough

From spec §13:

- [ ] All internal links resolve (no 404s) — click every link.
- [ ] All external links open in new tab where appropriate.
- [ ] Custom 404 page exists ✓ (Task 12).
- [ ] Social preview renders on LinkedIn, Twitter, chat ✓ (Task 16 step 4).
- [ ] Favicon shows in browser tab.
- [ ] Résumé PDF is the latest version.
- [ ] Analytics decision documented (default: none in v1; if you want Plausible, this is the moment to add it).
- [ ] Mobile layout verified on a real phone ✓ (Task 15).
- [ ] Spec's MVP-gate dependency met: agent's DABench number exists, demo is deployed, project page's headline number is filled in (not "X%").

When all boxes are checked, the portfolio is launched. Share the URL — that's the link that goes on every application, your résumé, your LinkedIn header, your email signature.

---

# Done criteria (per spec §13)

- [ ] All five project case-study pages exist with the full template filled in.
- [ ] The two launch blog posts are published.
- [ ] Lighthouse scores ≥ 95 across all four categories (landing + representative project page).
- [ ] Site deployed and publicly accessible.
- [ ] Résumé download works.
- [ ] DA Agent project page links to live demo + GitHub.
- [ ] Pre-launch checklist walked through end-to-end.
- [ ] Agent's MVP gate met (cannot launch publicly without this — see spec §14).
