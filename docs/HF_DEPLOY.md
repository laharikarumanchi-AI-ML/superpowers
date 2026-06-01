# Deploying the Streamlit demo to Hugging Face Spaces

The Streamlit demo (`demo/app.py`) runs the data-analysis agent against
the vetted CSVs in `demo/datasets/`. This guide walks through publishing
it as a public, free Hugging Face Space.

## Prerequisites

- A Hugging Face account at <https://huggingface.co>
- A write token from <https://huggingface.co/settings/tokens> (Type:
  Write, scope: Read + Write to your repos). Save it somewhere safe —
  HF won't show it again.

## One-time setup

### 1. Create the Space on Hugging Face

Go to <https://huggingface.co/new-space> and fill in:

| Field | Value |
|---|---|
| Owner | your HF username |
| Space name | `data-analysis-agent` |
| License | MIT (or whichever you prefer) |
| Space SDK | **Streamlit** |
| Space hardware | CPU basic (free) |
| Visibility | Public |

Click **Create Space**. HF will create an empty git repo at
`https://huggingface.co/spaces/<your-username>/data-analysis-agent`.

### 2. Add `GROQ_API_KEY` as a Space secret

In the Space's **Settings** tab → **Variables and secrets** →
**New secret**:

- Name: `GROQ_API_KEY`
- Value: your Groq key from <https://console.groq.com/keys>

This is what the deployed `demo/app.py` reads via `os.environ.get`.

### 3. Add the Space's git URL as a remote

```bash
cd /path/to/superpowers
git remote add hf "https://huggingface.co/spaces/<your-username>/data-analysis-agent"
```

You can keep `origin` (pointing at GitHub) and `hf` (pointing at HF
Spaces) as two separate remotes.

### 4. Generate the Space's README with HF frontmatter

HF Spaces needs YAML frontmatter at the top of its `README.md` to know
which SDK + entry file to use. We DON'T put this in the GitHub repo's
README (it would render as an ugly YAML table for recruiters).
Instead, generate a Space-specific README at deploy time.

Run this once before pushing:

```bash
# From the repo root
cat > /tmp/space_README.md <<'EOF'
---
title: Data Analysis Agent
emoji: 🤖
colorFrom: blue
colorTo: indigo
sdk: streamlit
sdk_version: 1.31.0
app_file: demo/app.py
pinned: false
short_description: Code-as-action agent for CSV analysis with sandboxed Jupyter execution
---

# Data Analysis Agent

A code-as-action data-analysis agent. Upload a CSV (or pick from the
vetted set: iris, tips, titanic) and ask questions in natural language;
the agent writes and executes Python in a sandboxed Jupyter kernel
to answer.

See the main repo for code and docs:
https://github.com/laharikarumanchi-AI-ML/superpowers
EOF
```

## Pushing the deploy

```bash
# 1. Make sure your working tree is clean
git status

# 2. Temporarily swap in the Space's README + push
cp README.md /tmp/github_README.md      # save the GitHub README
cp /tmp/space_README.md README.md
git add README.md requirements.txt
git commit -m "deploy: HF Spaces config"

# 3. Push to HF (your token authenticates this push)
git push hf deploy/hf-spaces:main

# 4. Restore the GitHub README
cp /tmp/github_README.md README.md
git add README.md
git commit -m "chore: restore GitHub README after HF push"
```

After `git push hf`, HF Spaces will:
1. Build the requirements.txt (~2-3 min on first deploy)
2. Boot the Streamlit app pointed at `demo/app.py`
3. The Space goes live at
   `https://huggingface.co/spaces/<your-username>/data-analysis-agent`

## Embedding in the portfolio

Once the Space is live, embed it in the portfolio's `data-analysis-agent`
project page by adding this MDX block:

```mdx
## Live demo

<iframe
  src="https://<your-username>-data-analysis-agent.hf.space"
  width="100%"
  height="700"
  style="border:1px solid var(--rule); border-radius: 4px; margin-block: 1.5rem;"
  loading="lazy"
></iframe>

[Open in a new tab →](https://huggingface.co/spaces/<your-username>/data-analysis-agent)
```

The HF Space URL `<username>-<spacename>.hf.space` is the iframe-friendly
embed URL (different from the canonical Space URL).

## Updating the Space

After the first deploy, updates are just `git push hf`:

```bash
# After making changes locally
git push hf main:main
```

HF Spaces auto-rebuilds on each push.

## Troubleshooting

- **Build fails with "no module named agent"** — make sure `requirements.txt`
  has the `-e .` line at the end, which installs the local package.
- **Streamlit shows "GROQ_API_KEY not set"** — re-check the secret name
  exactly matches `GROQ_API_KEY` in Space settings.
- **Demo crashes on a CSV upload** — the vetted-datasets-only mode
  should be the default; verify `demo/app.py` doesn't expose
  `st.file_uploader` for arbitrary uploads.
