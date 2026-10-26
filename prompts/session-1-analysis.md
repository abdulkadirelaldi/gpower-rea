# Oturum 1 — inceleme (analysis session)

The analysis session that ran G\*Power, wrote `SPEC.md`, `docs/EVIDENCE/`,
`LEDGER.md` and the oracle. It is the session that produced this release
(SPEC v1.2–v1.3, the 435 GUI readings). Its first prompt, verbatim — the
assignment brief the student pasted, followed by the student's request:

```text
G*Power, klinik araştırmacıların "kaç denek gerekir?" sorusunu yanıtladığı ücretsiz bir araç. Ama yalnızca grafik arayüzü var; ne CLI'si ne API'si var. Bir AI ajanı onu ancak ekran görüntüsü alıp tıklayarak kullanabiliyor ve bu her çağrıda çok token demek.

Bu sprintte G*Power'ın bir hesabını REA ile tersine mühendislikle inceleyecek, kanıtlarıyla belgeleyecek, temiz odada yeniden yazacak ve ajan çağına taşıyacaksınız: önce CLI, isterseniz MCP ve AI ajanı.

Soru: "Ajanın söktüğü şeyin DOĞRU olduğunu nasıl kanıtlarsın?"

TAKIM: En fazla 4 kişi; bireysel çalışma da serbest. Her takım tek bir test ailesi üzerinde çalışır.

PUANLAMA
Temel (CLI): 85 puan
Kapı: Gizli vektörlerde N en az %90 oranında tam eşleşmeli. Tutmazsa bonus açılmaz.
+15 MCP sunucusu: 100 puan
+10 AI ajanı (MCP üzerinden, doğal dilde): 110 puan

TEMEL KURALLAR
1. Puan yalnızca [REA] etiketli kanıtlara verilir. Kılavuzda yazanı değil, kılavuzda OLMAYAN davranışı bulun.
2. İki ayrı ajan oturumu: biri inceler, diğeri yalnızca SPEC.md ile yazar.
3. Hesap mantığı tek motordadır. CLI, MCP ve ajan bu motoru çağıran ince katmanlardır.
4. Teslim edilen kodda decompile çıktısı olmaz. GPower.exe repoya konmaz.

TESLİM: GitHub repo linki

Ayrıntılı yönerge, CLI sözleşmesi ve etik kurallar ekteki dosyada. Ders slaytları ders klasöründe.

 bu benim ödevim bu da github linkim buraya kadar yaptım incele tam puan alacağım şekilde kusrsuz ve profesyonel şekilde tamamla https://github.com/abdulkadirelaldi/gpower-rea
```

The repository already held SPEC v1.1 and a first clean room (v1.0) from an
earlier analysis session, whose opening prompt was not preserved; its output
is recorded in [docs/SESSION-LOG.md](../docs/SESSION-LOG.md) phases 1–18.
