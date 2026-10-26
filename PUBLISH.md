# PUBLISH.md — getting this repository onto GitHub

The deliverable is a GitHub repository link. Git is **not installed** on the
machine this was built on, so the publish step is the one thing left to run.
It takes about three minutes.

---

## Fast path (PowerShell)

```powershell
# 1. Install git and the GitHub CLI (once)
winget install --id Git.Git      --source winget --accept-package-agreements
winget install --id GitHub.cli   --source winget --accept-package-agreements
# close and reopen the terminal so PATH picks them up

# 2. Verify the repository still passes everything before publishing
cd "$env:USERPROFILE\OneDrive\Desktop\yazılımtest\gpower-rea"
python tools\compliance_check.py
python tools\make_vectors.py --check
python -m pytest -q
gpower selftest

# 3. Publish
.\tools\publish.ps1 -RepoName gpower-rea -Public
```

`tools/publish.ps1` runs the four checks again, refuses to continue if any
fails, then creates the commit and the GitHub repository. Pass `-Private`
instead of `-Public` if the course wants it private.

---

## Manual path

If you prefer to do it by hand, or `gh` is unavailable:

```powershell
cd "$env:USERPROFILE\OneDrive\Desktop\yazılımtest\gpower-rea"

git init -b main
git config user.name  "Your Name"
git config user.email "you@example.com"
git add -A
git status --short          # sanity check: no .exe, no __pycache__

git commit -m @'
gpower-rea: clean-room engine, CLI, MCP server and agent for the G*Power t-test family

Behavioural reverse engineering of the G*Power 3.1 "t tests" family:
12 findings in SPEC.md, one evidence file each, 36-row discriminating
probe worksheet. Clean-room engine with zero runtime dependencies,
401/401 exact sample-size agreement, independently re-derived with SciPy.
'@

# then, on github.com, create an EMPTY repository named gpower-rea and:
git remote add origin https://github.com/<your-user>/gpower-rea.git
git push -u origin main
```

Create the repository **empty** — no README, no .gitignore, no licence —
otherwise the first push is rejected as a non-fast-forward.

---

## After pushing

1. **Check Actions.** `.github/workflows/ci.yml` has four jobs:
   `bare-engine` (installs no extras and runs the gate),
   `compliance` (the submission rules), `tests` (Python 3.10–3.13), and
   `agent-static`. All four should be green within a few minutes. A green
   `bare-engine` is the single most useful thing a grader can see.

2. **Submit the link**, plus these three commands in the submission note so the
   grader can reproduce the claim in under a minute:

   ```console
   pip install -e .
   gpower selftest                      # 401/401 exact N matches
   gpower solve -t indep -a 0.05 -p 0.95 -e 0.5     # the canonical example
   ```

3. **Optional but worth it — close the two gaps** that are currently marked
   unsigned in [docs/SESSION-LOG.md](docs/SESSION-LOG.md):

   * **GUI probes** (~30 min, needs a G\*Power installation):
     `python tools/probe_plan.py`, fill the `observed` column of
     `probes/probe_worksheet.csv` from the GUI, `python tools/harvest.py`,
     commit. This converts 28 discriminating rows from `PENDING` to a stamped
     verdict and is what turns the `REA-BEHAVIOURAL` and `REA-OPEN` findings
     from falsifiable into tested.
   * **Two-session attestation** (~10 min, needs one extra agent session):
     follow [docs/CLEANROOM-PROTOCOL.md §6](docs/CLEANROOM-PROTOCOL.md) and
     fill in the table in `docs/SESSION-LOG.md`.

   Both are deliberately left as empty, named slots rather than filled in
   speculatively — see [docs/SESSION-LOG.md](docs/SESSION-LOG.md).

---

## What must never be committed

Enforced by `.gitignore` **and** by `python tools/compliance_check.py`, which
runs in CI:

* `GPower.exe` or any installer / executable artefact (rule C-1);
* decompiler or disassembler output of any kind (rule C-2).

If `compliance_check.py` ever prints `COMPLIANCE: FAIL`, stop and fix it
before pushing — it is the machine-checkable half of the submission rules.
