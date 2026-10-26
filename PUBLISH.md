# PUBLISH.md — getting this repository onto GitHub

The deliverable is a GitHub repository link. **Almost everything is already
done**: git and the GitHub CLI are installed, the repository is initialised,
and the work is committed and tagged. What remains needs *your* GitHub
credentials, which is not something a tool can supply for you.

## Current state

| | |
|---|---|
| git | installed at `%LOCALAPPDATA%\Programs\MinGit` (portable, no admin needed) and added to your user `PATH` |
| GitHub CLI | installed at `%LOCALAPPDATA%\Programs\gh\bin`, also on your `PATH` |
| repository | initialised on branch `main`, 56 files committed |
| tag | `spec-frozen-v1.0` marks the clean-room handover point |
| identity | `user.name = "Abdulkadir Elaldi"`, `user.email = "elaldiabdulkadir1@gmail.com"` — change it with `git config user.name "..."` if the spelling is wrong **before** you push |
| remote | not set — this is the step below |

> If `git` is not found in a terminal that was already open, close and reopen
> it; `PATH` changes only reach new processes.

---

## The two commands that remain

```powershell
cd "$env:USERPROFILE\OneDrive\Desktop\yazılımtest\gpower-rea"

gh auth login                                  # opens a browser; pick HTTPS
.\tools\publish.ps1 -RepoName gpower-rea -Public
```

`tools/publish.ps1` re-runs the whole gate — compliance check, vector
freshness, the test suite, `gpower selftest` — and **refuses to publish if any
of them fails**. Then it creates the GitHub repository and pushes. Pass
`-Private` instead of `-Public` if the course wants it private.

---

## Manual path (no `gh`)

Create an **empty** repository named `gpower-rea` on github.com — no README,
no .gitignore, no licence, or the first push is rejected as a
non-fast-forward. Then:

```powershell
cd "$env:USERPROFILE\OneDrive\Desktop\yazılımtest\gpower-rea"
git remote add origin https://github.com/<your-user>/gpower-rea.git
git push -u origin main --follow-tags
```

Git will prompt for credentials on the first push. Use a
[personal access token](https://github.com/settings/tokens) as the password,
not your account password.

The commit already exists, so there is nothing else to do — `git log --oneline`
should show one commit tagged `spec-frozen-v1.0`.

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
