# How to publish this spec on GitHub

Step-by-step. Assumes you have the org `memarray` already created at https://github.com/memarray. Total time: ~30 minutes if you go in order.

---

## Before you start: things to verify, in writing

**Do these before publishing. Each one is a place where being sloppy costs the narrative.**

1. **Read the actual Mem0 paper.** Open https://arxiv.org/abs/2504.19413 and read the "Conclusions and Future Work" section yourself. The blueprint v2 attributes a specific quote to that paper about "human oversight" and "versioning system." I could not find that exact quote in the paper. I have written the spec to *not* depend on that quote — the argument is built from Mem0's actual API, which is verifiable. But if you find the quote and want to add it back as a citation, do so. If the quote is not there, you do not need it; the API-based argument is stronger anyway.

2. **Spin up Mem0 and test the history endpoint yourself.** Run `pip install mem0ai`, get an API key, do a few `add()` calls, then call `client.history(memory_id=...)`. Confirm the response shape matches what the spec says (`{old_memory, new_memory, event ∈ {ADD, UPDATE, DELETE}, created_at, updated_at}`). If it doesn't match, fix the spec before publishing. This takes 20 minutes and protects you from being publicly corrected.

3. **Verify Apache AGE versions.** The spec says AGE 1.6.0 ships on PG16 and AGE 1.7.0 on PG17. The blueprint has these dates but verify on https://age.apache.org/ before quoting them externally. If they're wrong, soften to "AGE supports PG16/17 as of [date you checked]."

4. **Decide on contact info.** The spec ends with "Reach me at [contact]." Decide: email, Twitter DM, or just the GitHub handle. Personally I'd put a real email — solo founder applications get traction from being personally reachable.

5. **Pick the dates.** Two `[DATE TO INSERT]` placeholders in the spec — the publication date (set to today when you push) and the v0.1 demo target date. The blueprint says v0.1 demo is targeted around Day 75–90, so somewhere in mid-to-late July 2026. Pick something realistic.

---

## Step 1 — Create the repo (5 minutes)

1. Go to https://github.com/orgs/memarray/repositories/new
2. **Repository name:** `influence-trace-spec`
3. **Description:** `A design specification for response-level influence tracing and operationally reversible memory in agent memory systems.`
4. **Visibility:** Public.
5. **Initialize:** Leave all checkboxes UNCHECKED. We are pushing files locally; we don't want GitHub to create a README/LICENSE that will conflict.
6. Click "Create repository."

---

## Step 2 — Push the files (10 minutes)

On your local machine:

```bash
# Pick a directory you'll keep this in long-term
mkdir -p ~/memarray && cd ~/memarray

# Copy the four files I generated into this directory:
#   SPEC.md
#   README.md
#   CONTRIBUTING.md
#   LICENSE

# Initialize and push
git init
git branch -M main
git add SPEC.md README.md CONTRIBUTING.md LICENSE
git commit -m "Initial draft: response-level influence tracing for agent memory"
git remote add origin git@github.com:memarray/influence-trace-spec.git
git push -u origin main
```

If you don't have SSH keys set up for GitHub, use the HTTPS URL: `https://github.com/memarray/influence-trace-spec.git` and authenticate with a personal access token when prompted.

---

## Step 3 — Configure the repo (5 minutes)

On the GitHub repo page:

1. **Topics** (right sidebar, gear icon next to "About"). Add: `agent-memory`, `llm-memory`, `voice-agents`, `memory-systems`, `event-sourcing`, `bi-temporal`, `ai-infra`, `apache-2`. Topics are how people find you in search.
2. **About** (same sidebar). Add the description: "Design spec for response-level influence tracing and operationally reversible memory." Add a website URL — leave blank for now if you don't have one.
3. **Issues** (Settings → General → Features). Make sure Issues are enabled.
4. **Discussions** (Settings → General → Features). Enable Discussions. This is where you want longer back-and-forth conversations to live.

---

## Step 4 — Add issue and PR templates (10 minutes)

These are the small details that signal "this is a real project, not a vibe."

Create these files locally and push:

```bash
mkdir -p .github/ISSUE_TEMPLATE
```

Create `.github/ISSUE_TEMPLATE/spec-feedback.md`:

```markdown
---
name: Spec feedback
about: Disagreement, edge case, or clarification request about the spec
title: ''
labels: spec-feedback
---

**Section of the spec you're commenting on:**
(Link to the heading or paste the relevant snippet)

**The feedback:**

**A concrete scenario or counterexample:**

**If you're proposing a change, what would it be:**
```

Create `.github/ISSUE_TEMPLATE/implementation-report.md`:

```markdown
---
name: Implementation report
about: You implemented something based on this spec — tell us what happened
title: ''
labels: implementation-report
---

**What you implemented:**

**Stack you implemented it on:**

**What worked as the spec described:**

**What didn't work or was unclear:**

**Suggested changes to the spec, if any:**
```

Create `.github/PULL_REQUEST_TEMPLATE.md`:

```markdown
**What this PR changes in the spec:**

**Why:**

**For substantive changes (anything that changes behaviour or semantics):**
- [ ] I opened an issue first and got rough agreement on the change
- [ ] OR this is a typo / clarification fix that doesn't need prior discussion
```

Commit and push:

```bash
git add .github
git commit -m "Add issue and PR templates"
git push
```

---

## Step 5 — The first social push (do this 24-48 hours AFTER pushing the repo, not immediately)

The repo needs to look "lived in" before you start drawing eyeballs. If you push the repo and immediately tweet it, the first impression people have is one commit with no engagement. If you let it sit for a day, then tweet, the repo has had time to get a few stars from people watching the org and looks more organic.

When you do push it socially:

**Twitter/X.** Pick a quiet weekday morning IST (Tuesday/Wednesday around 10am IST = 9:30pm Pacific the previous evening = good for India-and-late-US-coast). Thread of 4-6 tweets. First tweet has the most important sentence: "Every memory layer can tell you what's in memory. None can tell you which memories caused this specific response, or undo what they just did to your data. I wrote a spec for both. [link]"

**Hacker News.** Submit as a Show HN. Title: `Show HN: A spec for response-level influence tracing and reversible agent memory`. Submit Tuesday or Wednesday at 8:30–9:30am US Pacific (so 9–10pm IST). Stay online for 4–6 hours after submission to answer comments. Do not ask friends to upvote — HN detects this and will sink your post. Do ask 2-3 people to read and comment substantively in the first 30 minutes if they would naturally find this interesting.

**Reddit.** Cross-post to r/LocalLLaMA and r/AI_Agents. Title each one slightly differently — Reddit penalizes identical cross-posts.

**Discords.** LiveKit Agents, Vapi, Retell — drop a link in the appropriate channel with one sentence of context. Do this only after a month of being visibly helpful in those Discords (Phase 3 of the blueprint). If you're not at that point yet, hold the Discord drops.

---

## Step 6 — When you do the YC/EF/SPC application

The "project URL" field in each application is `https://github.com/memarray/influence-trace-spec`. The "video" link, when you have it, points to a separate URL — don't put a video link in the spec README until the video exists.

In the application's "what are you building" answer, mention the repo by name and link directly to it. In the YC video, show the GitHub page on screen for 3-5 seconds while you explain what the spec covers.

---

## What to do if Mem0 (or anyone) responds publicly

This will probably happen — that's good, not bad.

**If they engage substantively** (e.g. "this comparison is wrong because of X"): respond fast (within hours), thank them, fix the spec if they're right, push the fix as a commit, link to the commit in your reply. This makes you look like a serious person, not a defensive one.

**If they engage defensively** (e.g. "we have an audit trail!"): agree publicly that they have an audit trail, and clarify that the spec is about the operational layer above the audit trail. Do not get into a fight. Do not @ them aggressively. The spec already credits Mem0 in the prior-art section; lean on that.

**If they don't engage at all**: that's also fine. The spec stands on its own.

---

## Final checklist before you push

- [ ] Read the Mem0 paper's future-work section yourself
- [ ] Spun up Mem0 and confirmed the history endpoint shape
- [ ] Verified Apache AGE versions on age.apache.org
- [ ] Replaced both `[DATE TO INSERT]` placeholders in SPEC.md
- [ ] Replaced `[contact]` with real contact info in SPEC.md
- [ ] Spell-checked the spec (use a spellchecker, don't trust your eyes)
- [ ] One friend has read the spec and told you it makes sense
- [ ] You can summarize the spec out loud in 60 seconds without reading it
