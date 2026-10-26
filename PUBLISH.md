# PUBLISH.md — release checklist

Everything a release must pass, in the order CI runs it
(`.github/workflows/ci.yml`). Nothing here needs G\*Power.

```console
$ pip install -e ".[mcp,agent,dev]"

$ python tools/compliance_check.py        # C-1..C-5: no binary, no decompiler output, one engine
$ python tools/make_vectors.py --check    # the 401 vectors are a function of the engine
$ gpower selftest                         # 401/401 exact N
$ python -m pytest -q                     # incl. every recorded G*Power reading
$ python tools/judge_cleanroom.py --strict
$ python tools/stamp_worksheet.py && python tools/harvest.py && python tools/rea_report.py
$ git diff --exit-code -- probes/         # the recorded evidence and its reports are current
```

If the engine changes in a way that affects a G\*Power reading,
`tests/test_gpower_observed.py` fails. That is the point: the readings are the
contract, and they are never edited to make a test pass.

To add readings, run G\*Power for macOS, grant Accessibility permission to the
terminal, and run `python tools/rea_campaign.py --set <set>`; records are
appended, never rewritten.

`tools/publish.ps1` is the Windows helper the first release was pushed with; it
refuses to push if the compliance gate fails.
