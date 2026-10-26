# The natural-language agent

A power-analysis consultant that talks to the same engine the CLI talks to.

```
you ──prose──► Claude Opus 5 ──MCP(stdio)──► gpower-mcp ──► engine.solve()
```

## Run it

```console
$ pip install -e ".[mcp,agent]"
$ export ANTHROPIC_API_KEY=...            # or: ant auth login

$ python agent/agent.py                   # interactive
$ python agent/agent.py "I have two groups of 40 and expect d=0.6 — what power do I have?"
$ python agent/agent.py --json -v "n for d=0.5, power .95"
```

| flag | effect |
|---|---|
| `--json` | emit `{prompt, answer, tool_calls}` instead of prose |
| `-v`, `--verbose` | log every tool call and its arguments to stderr |
| `--server CMD` | launch the MCP server differently (default: this interpreter running `gpower_rea.mcp_server`) |

The server is started as a subprocess over stdio, so there is nothing to
configure and no port to pick.

## The one design rule

**The agent does no arithmetic.** Its system prompt says so:

> *Never compute, estimate, or recall a sample size, power value, critical
> value, or noncentrality parameter yourself. Every number you state must come
> from a tool result in this conversation. If a tool fails, say so and say
> why — do not substitute a guess.*

and the build fails if it ever does:

```python
# tools/compliance_check.py, rule C-3
if marker.search(text) or re.search(r"\bmath\.sqrt\(", text):
    problems.append("C-3 the agent performs its own arithmetic")
```

Which is why its answers are auditable: anything it says can be reproduced by
a `gpower solve` command through a different code path.

## What the prompt makes it do

* **Name the design back to you.** "Two independent groups" vs "the same
  participants twice" is a substantive methodological choice, not a parameter;
  the agent states which one it picked and why.
* **Convert raw descriptives first.** Given means and SDs rather than a `d`, it
  calls `compute_effect_size` and shows the intermediate value — including
  which of the two pooling options it used
  ([F-11](../SPEC.md#f-11--the-effect-size-drawer-offers-two-pooled-sds-and-the-equal-n-one-is-an-rms)).
* **Declare its defaults.** `α = 0.05`, power `0.80`, two tails, allocation
  ratio 1 when you are silent — and it says which of those it defaulted.
* **Ask only when it matters.** A clarifying question when one- vs two-tailed
  or paired vs independent would change the answer; otherwise it proceeds under
  stated assumptions.
* **Report per-group *and* total, plus achieved power.** The achieved power
  always slightly exceeds the target because sample sizes are integers
  ([F-06](../SPEC.md#f-06--minimality-and-actual-power-is-recomputed)); the
  agent explains that rather than hiding it.
* **Answer in your language.** The tools are language-neutral; the prose is not.
* **Not claim to be G\*Power.** On "can I trust this?" it calls
  `engine_provenance` and answers from it.

## Tools it can reach

| tool | use |
|---|---|
| `list_tests` | when the described design is unclear |
| `describe_test` | parameters and exact menu title of one test |
| `power_analysis` | all five analysis types; returns numbers **plus** `report_text` and `apa_sentence` |
| `compute_effect_size` | raw descriptives → `d` / `dz` / `r` / `f²` |
| `power_curve` | the `N`-vs-power trade-off instead of a single number |
| `engine_provenance` | version, specification, and what the engine is *not* |

Errors come back as data (`{"ok": false, "error": {...}}`), never as
exceptions, so a bad parameter becomes a question to you rather than a crash.

## Model configuration

```python
MODEL        = "claude-opus-5"
max_tokens   = 16_000
thinking     = {"type": "adaptive"}
output_config = {"effort": "high"}
fallbacks    = "default"          # beta: server-side-fallback-2026-07-01
```

Server-side refusal fallbacks are requested when the installed SDK supports
them and skipped silently otherwise, and `stop_reason == "refusal"` is handled
explicitly rather than crashing on `content[0]`.

The tool loop uses the SDK's `client.beta.messages.tool_runner` with
`anthropic.lib.tools.mcp.async_mcp_tool`, mirroring the conversation history
between turns so that follow-up questions keep full context.

## Example session

```
you> Diyabet hastalarında yeni bir eğitim programını deniyorum. Müdahale ve
     kontrol grubu olacak, orta büyüklükte bir etki bekliyorum. Kaç hasta?

  · list_tests({})
  · power_analysis({"test": "ttest-indep-means", "solve_for": "n",
                    "alpha": 0.05, "power": 0.8, "effect_size": 0.5, "tails": 2})

Her gruba 64 hasta, toplam 128 hasta gerekiyor.

Tasarım: iki bağımsız grup (müdahale vs kontrol) için iki yönlü t testi.
Varsayımlarım — açıkça belirtiyorum: Cohen'in orta etki büyüklüğü d = 0.50,
α = 0.05, hedef güç 0.80, grup oranı 1:1. Bu üçü sizin belirtmediğiniz,
benim varsaydığım değerler.

Bu örneklem büyüklüğünde ulaşılan güç 0.8015 — hedefin biraz üzerinde, çünkü
örneklem büyüklüğü tam sayı olmak zorunda.

Metot bölümü için: "An a priori power analysis for a two-tailed independent
samples t test (d = 0.5, alpha = 0.05, target power = 0.80) indicated that
n1 = 64 and n2 = 64 (total N = 128) is required; the achieved power at that
sample size is 0.8015."

Etki büyüklüğünü literatürden bir ön çalışmanın ortalama ve standart
sapmalarıyla hesaplamak isterseniz, onları verin — doğru d'yi hesaplayıp
örneklemi güncellerim.
```

Verify it:

```console
$ gpower solve -t indep -a 0.05 -p 0.80 -e 0.5 --tails 2 --json
  "sample_size": { "n1": 64, "n2": 64, "total": 128, ... },
  "power": 0.8014596...
```

## What is tested, and what is not

Stated plainly, because an agent is the easiest component to claim works.

| | status |
|---|---|
| compiles, imports resolve (`anthropic`, `anthropic.lib.tools.mcp`, `mcp`) | tested, CI |
| contains no arithmetic | tested (`compliance_check.py` C-3 **and** `tests/test_agent_offline.py`) |
| system prompt states the no-arithmetic rule, the four defaults, and the "not G\*Power" clause | tested |
| tool-call extraction from a response | tested |
| conversation history mirrored between turns, so follow-ups keep context | tested |
| `stop_reason == "refusal"` reported rather than crashing on `content[0]` | tested |
| refusal-fallback beta unavailable → degrades, retries, and does not leave the failed turn in the history | tested |
| an unrelated API error is not swallowed by the degradation path | tested |
| the MCP transport it uses (server as a stdio subprocess) | tested (`tests/test_mcp_stdio_e2e.py`) |
| **run against the live Anthropic API** | **not verified** — the build machine has no credentials |

The 22 offline tests in `tests/test_agent_offline.py` drive `PowerAgent.ask()`
with a stub client, so everything except the model call itself is exercised.
What a test cannot check is the model's *judgement* — whether it picks the
right design from a vague description. That is governed by the system prompt,
and the honest claim is that the prompt says the right things, not that the
behaviour has been measured.

To run it for real:

```console
$ ant auth login          # or: export ANTHROPIC_API_KEY=...
$ python agent/agent.py -v "iki grubum var, her birinde 40 kişi, d=0.6, gücüm ne?"
```

and check the answer against the equivalent `gpower solve` command — which is
the point of the architecture.

## Cost

One typical question is 2–4 tool calls and a few thousand tokens. The tools
return compact JSON, and `engine_provenance` / `list_tests` are small enough
that the model can call them freely. Compare with the alternative this project
exists to replace: screenshotting a GUI, which costs thousands of image tokens
per interaction and gets the answer by reading pixels.
