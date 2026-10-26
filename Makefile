# gpower-rea -- developer shortcuts.
#
# Everything here is also a plain command; see README.md.  `make check` is
# what CI runs.

PY ?= python

.PHONY: help install install-all test gate compliance vectors probes cleanroom check clean demo

help:
	@echo "install      editable install (engine + CLI, zero dependencies)"
	@echo "install-all  + mcp, agent and dev extras"
	@echo "test         full pytest suite (incl. the SciPy re-derivation)"
	@echo "gate         the conformance gate: 401 reference vectors"
	@echo "compliance   submission rules, as a machine check"
	@echo "vectors      regenerate src/gpower_rea/data/public_vectors.csv"
	@echo "probes       regenerate the GUI probe worksheet, then harvest"
	@echo "cleanroom    judge the 2nd implementation, then probe the spec gaps"
	@echo "check        compliance + vectors freshness + tests + gate  (= CI)"
	@echo "demo         run one example through all three interfaces"

install:
	$(PY) -m pip install -e .

install-all:
	$(PY) -m pip install -e ".[mcp,agent,dev]" mpmath

test:
	$(PY) -m pytest -q

gate:
	gpower selftest

compliance:
	$(PY) tools/compliance_check.py

vectors:
	$(PY) tools/make_vectors.py

probes:
	$(PY) tools/probe_plan.py
	$(PY) tools/harvest.py

cleanroom:
	$(PY) tools/judge_cleanroom.py
	$(PY) tools/probe_spec_gaps.py

check: compliance
	$(PY) tools/make_vectors.py --check
	$(PY) -m pytest -q
	gpower selftest

demo:
	@echo "--- engine (Python) ---"
	@$(PY) -c "from gpower_rea import solve; r = solve('ttest-indep-means', 'n', alpha=0.05, power_target=0.95, effect_size=0.5, tails=2); print(r.sample_size, round(r.power, 7))"
	@echo "--- CLI ---"
	@gpower solve -t indep -a 0.05 -p 0.95 -e 0.5 -f apa
	@echo "--- MCP server (tool list) ---"
	@$(PY) -c "import asyncio; from gpower_rea.mcp_server import mcp; print(', '.join(sorted(t.name for t in asyncio.run(mcp.list_tools()))))"
	@echo "--- agent (needs ANTHROPIC_API_KEY) ---"
	@echo "    python agent/agent.py \"how many participants for d=0.5 at 95% power?\""

clean:
	-$(PY) -c "import shutil,glob,os; [shutil.rmtree(p, ignore_errors=True) for p in glob.glob('**/__pycache__', recursive=True) + ['.pytest_cache', 'build', 'dist']]"
