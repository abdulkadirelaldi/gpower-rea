# Live agent run — natural language → MCP → engine

| | |
|---|---|
| date | 2026-10-26 |
| model | `claude-opus-5-5` |
| harness | Claude Code 2.1.310, headless (`claude -p`) |
| tools the model could use | **only** the six `gpower` MCP tools (`--strict-mcp-config --allowedTools "mcp__gpower__*"`) — no shell, no files, no web |
| MCP server | `gpower-mcp` from this repository, engine 1.2.0, over stdio |
| turns / cost | 7 / $0.19 |

`agent/agent.py` (Anthropic SDK tool runner) could not be run on the build machine for lack of an API key. This run uses Claude Code as the agent harness instead; the server side, the tools and the engine are identical, and the property under test is the same: **every number in the answer comes from a tool call.**

## The question (verbatim)

> İki bağımsız grupla bir klinik çalışma planlıyorum. Kontrol grubunu tedavi grubunun iki katı büyüklükte tutmak istiyorum. Beklediğim etki büyüklüğü d=0.5, alfa 0.05, çift yönlü test, hedef güç 0.95. Her grupta kaç kişi gerekir ve gerçekleşen güç nedir? Sayıları yalnızca gpower araçlarından al.

## Tool calls, in order

| # | tool | input | engine returned |
|---|---|---|---|
| 1 | `describe_test` | `{"test": "ttest-independent"}` | error: unknown test 'ttest-independent'; known tests: ttest-generic, ttest-indep-means, ttest-one… |
| 2 | `power_analysis` | `{"test": "ttest-indep-means", "solve_for": "n", "effect_size": 0.5, "alpha": 0.05, "power": 0.95, "tails": 2, "allocation_ratio": 2}` | n1=79, n2=157, N=236, power=0.9505146 |
| 3 | `describe_test` | `{"test": "ttest-indep-means"}` | test description (ttest-indep-means) |
| 4 | `power_analysis` | `{"test": "ttest-indep-means", "solve_for": "power", "effect_size": 0.5, "alpha": 0.05, "tails": 2, "n1": 79, "n2": 158}` | n1=79, n2=158, N=237, power=0.9509116 |
| 5 | `power_analysis` | `{"test": "ttest-indep-means", "solve_for": "power", "effect_size": 0.5, "alpha": 0.05, "tails": 2, "n1": 78, "n2": 156}` | n1=78, n2=156, N=234, power=0.9485150 |

## The answer (verbatim)

> Tam olarak 2:1 oranı için **tedavi grubunda 79, kontrol grubunda 158 kişi (toplam 237)** gerekiyor. Bu tasarımda gerçekleşen güç **0.9509**. Bütün sayılar gpower aracından alındı (`ttest-indep-means`, d = 0.5, α = 0.05, çift yönlü).
>
> | Tasarım | Tedavi (n1) | Kontrol (n2) | Toplam | Oran | Gerçekleşen güç |
> |---|---|---|---|---|---|
> | A priori çözüm, oran = 2 | 79 | 157 | 236 | 1.987 | 0.9505 |
> | **Tam 2:1 (önerilen)** | **79** | **158** | **237** | **2.000** | **0.9509** |
> | Bir alt tam 2:1 tasarım | 78 | 156 | 234 | 2.000 | 0.9485 (yetersiz) |
>
> **Bir uyarı:** A priori hesapta araç oranı 2 olarak aldı ama "even-total" yuvarlama kuralı yüzünden kontrol grubunu 157'de bıraktı. Bu yüzden ortaya çıkan oran tam 2 değil, 1.987. Siz kontrolün tam iki katı olmasını istediğiniz için 79/158 tasarımını ayrıca hesaplattım. 0.95 hedefini geçen en küçük tam 2:1 tasarım bu. Bir alttaki 78/156 tasarımı 0.95'in altında kalıyor.
>
> **Çıktıyla ilgili bir not:** Post hoc hesabın `report_text` çıktısında "Allocation ratio N2/N1 = 1" yazıyor. Bu satır yanlış; gerçek oran 2.0 ve güç hesabı da 79 ile 158 kullanılarak yapılmış. Rapor metnini yöntem bölümüne aynen kopyalayacaksanız o satırı düzeltin.
>
> **Yöntem bölümü için örnek cümle:** Çift yönlü, bağımsız iki grup ortalama farkı t testi için yapılan a priori güç analizi (d = 0.5, α = 0.05, hedef güç = 0.95, N2/N1 = 2) sonucunda tedavi grubunda 79, kontrol grubunda 158 katılımcı (toplam N = 237) gerektiği belirlendi; bu örneklem büyüklüğünde gerçekleşen güç 0.951'dir.
>
> Bu sayılara olası kayıplar (dropout) dahil değil. Kayıp bekliyorsanız işe alım hedefini buna göre yükseltmeniz gerekir.

## Checking it through a different code path

```console
$ gpower solve -t indep -a 0.05 -p 0.95 -e 0.5 --ratio 2 --json      # call 2
  -> n1 = 79, n2 = 157, N = 236, power = 0.9505146   (= G*Power, probe P-09-c)
$ gpower solve -t indep -s power -a 0.05 -e 0.5 --n1 79 --n2 158 --json   # call 4
  -> n1 = 79, n2 = 158, N = 237, power = 0.9509116
$ gpower solve -t indep -s power -a 0.05 -e 0.5 --n1 78 --n2 156 --json   # call 5
  -> n1 = 78, n2 = 156, N = 234, power = 0.9485150
```

## What the run found

1. **A real defect in our output.** The agent noticed that the post-hoc `report_text` for `79 + 158` said *"Allocation ratio N2/N1 = 1"*. Every analysis except a priori is given the design itself, so the ratio must be `n2/n1`; the engine reported its default. Fixed in `engine._build_result`, locked by `tests/test_engine_invariants.py::test_an_explicit_design_reports_its_own_ratio_not_the_default`.
2. **A missing alias.** Its first guess, `ttest-independent`, was refused (the error listed the valid keys, and it recovered on the next call). The alias now resolves.
3. **The agent explained F-09 correctly from the tool output alone**: G\*Power's answer for ratio 2 is `79 / 157`, not an exact 2:1 split, and it said so instead of silently "fixing" it.

