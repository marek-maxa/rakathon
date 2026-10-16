# Zpráva → fakta → vazby na otázky

Samostatný modul pro MASTER QUESTION obsahuje datový kontrakt, katalog,
LLM extraktor a návrh kandidátních otázek. Automatické vedení celého rozhovoru
je další krok. Stávající
`Intake` a jeho export v2 se nemění. Tento jiný typ výstupu má vlastní verzi 1.
Bez nových závislostí, triáže, ukládání karty a časovače.

## Rozhraní

- [master_contract.py](master_contract.py): `MessageEvent`, `Fact`,
  `NumericRange`, `build_packet(message, facts) -> dict`.
- [question_catalog.py](question_catalog.py): `load_catalog()` a
  `lookup_questions(concepts) -> dict`.
- [master.py](master.py): `MasterExtractor(client)(message) -> list[Fact]`,
  `validate_facts(result, message)` a `analyze_message(message, extract) -> dict`.
- [master_prompt.md](master_prompt.md) a [master_schema.json](master_schema.json):
  samostatné instrukce a striktní výstupní schéma otevřené zprávy.
- [master_examples.json](master_examples.json): pět ručně sestavených syntetických
  příkladů požadovaného převodu. Nejde o výsledky LLM ani nezávislou evaluační sadu.
  Extraktor je posílá v kontextu každého volání; obálku tvoří aplikace.

`MessageEvent` uchovává `id`, `patient_id`, původní `text`, `available_at`
(ISO 8601 s časovým pásmem), `source`, `author` a skutečně položenou `question`.
Zdroje jsou `master_question`, `patient_message` a `targeted_answer`.
Spontánní zpráva nemusí mít otázku. Autor je `patient`, `caregiver`, `team`
nebo `unknown`; jeho identitu dodá aplikace, nikoli model.

| Pole faktu | Význam |
| --- | --- |
| `concept` | Pojem, např. `vomiting` nebo `vomiting.episodes`; lze zachovat i dosud nenamapovaný pojem |
| `presence` | `present`, `absent`, `uncertain`; absence zmínky nevytváří fakt |
| `subject` | `patient`, `caregiver`, `unknown`; pečující může popisovat i vlastní potíže |
| `value` | Číslo včetně nuly, text, `NumericRange` nebo null; u popření null |
| `unit` | Výslovná jednotka nebo null; nemění obecný pocit na číselné skóre |
| `time_text` | Doslovné časové vyjádření nebo null; „od včera“ není automaticky 24 hodin |
| `certainty` | `stated`, `approximate`, `uncertain`; charakter sdělení, nikoli pravděpodobnost správnosti modelu |
| `evidence` | Neprázdná doslovná citace ze zprávy |

Rozsah má `lower`, `upper` a `lower_inclusive` / `upper_inclusive`.
Jedna mez může být null; příslušná uzavřenost se pak neuplatní. Nepřevádíme
rozsah na jeho horší mez ani přibližný počet na přesnou hodnotu.
`presence=present` může označovat také přítomnost konkrétního měření: například
sdělené NRS 0 zůstane číselným faktem, ne diagnózou bolesti.

`build_packet` vrací `{schema_version: 1, message: {...}, facts: [...]}`.
Ověří vazbu citace i časového textu na zprávu a ke každému faktu připojí
`source_message_id` a vždy `confirmation="unconfirmed"`. Potvrzovací workflow
pro tyto fakta ještě neexistuje. Neplatná data vyvolají výjimku;
prázdný seznam faktů značí pouze prázdnou extrakci, nikoli dobrý zdravotní stav.
Typové kontroly a citace nedokazují správný význam, úplnost ani klinickou platnost.

## Použití bez sítě

```python
from llm_intake.master_contract import Fact, MessageEvent, NumericRange, build_packet
from llm_intake.question_catalog import lookup_questions

message = MessageEvent(
    id="synthetic-01", patient_id="synthetic-patient",
    text="Zvracel jsem pětkrát nebo šestkrát.",
    available_at="2026-10-16T10:00:00+02:00",
    source="master_question", author="patient", question="Jak se dnes cítíte?",
)
fact = Fact(
    concept="vomiting.episodes", presence="present", subject="patient",
    evidence="Zvracel jsem pětkrát nebo šestkrát",
    value=NumericRange(5, 6), unit="episodes", certainty="uncertain",
)
packet = build_packet(message, [fact])
links = lookup_questions(f["concept"] for f in packet["facts"])
```

Katalog načítá všech 49 otázek z
[definic](../rakathon_meddi_onco_data/docs/dotazniky_definice.json).
Klíčem je dvojice ID dotazníku a otázky. Zachovává text, typ a zdrojovou
`podminka`. Katalog nyní používá stejný balíček `Question.specification()` jako
intake, včetně možností, návodu a směru škály, bez barev. Samotné lookup větvení
nevyhodnocuje; to už umí samostatný [QuestionnaireFlow](../docs/llm-flow.md).
Počáteční vazby pokrývají jen témata `vomiting`, `diarrhea`, `fatigue`,
`temperature`, `breathlessness`, `bleeding` v dotazníku `nezadouci_ucinky`;
nejde o úplné klinické pokrytí. Tečkou oddělená pole dědí vazbu tématu.

`lookup_questions` vrací `questions` bez duplicit a `unmapped_concepts`.
Jde pouze o vazby: funkce nefiltruje autora, subjekt, popření, již známou hodnotu
ani podmínky větvení. Budoucí výběr musí použít celé fakty a kontext,
jinak by například kladl otázku pacientovi na únavu jeho pečujícího.
Neznámý pojem zůstává v paketu i seznamu nenamapovaných pojmů.

Pro ručně vybrané otázky již lze spojit fakta a výsledky intake přes
`build_pipeline_packet()`; [popis a syntetický výstup](../docs/llm-flow.md).
Katalog neobsahuje triážní pravidla. Ta a napojení na kartu zůstávají samostatná
práce ostatních částí systému; širší kontext je v [návrhu](../docs/master-question.md).

## Extraktor a návrh otázek

```python
import json
from pathlib import Path
from llm_intake.client import Client
from llm_intake.master import MasterExtractor, analyze_message
from llm_intake.master_contract import MessageEvent

message = MessageEvent(**json.loads(
    Path("llm_intake/master_input.example.json").read_text(encoding="utf-8")
))
packet = analyze_message(message, MasterExtractor(Client.from_env()))
```

Extraktor používá stávající deployment a autentizaci; `Client.structured_payload`
a `Client.send` sdílejí sestavení striktního požadavku a HTTP transport s Intake.
Modelu posíláme text, skutečnou otázku a autora, pět příkladů a balíčky otázek
pro šest namapovaných témat. ID pacienta, systémový čas, barvy ani pravidla
triáže neposíláme. Jiné potíže může model zachovat jako další pojmy.
Pole pojmu má anglický identifikátor, např. `vomiting.episodes`; počet stolic
nad obvyklý stav má odlišný pojem `diarrhea.increase_over_baseline`.

Lokální validace kontroluje všechny povinné klíče, hodnoty, uzavřenost mezí,
citace a časový text. Neplatný výstup nebo chyba API vyvolá výjimku,
nikoli úspěšný prázdný výsledek. Žádné částečné změny karty se zde nedělají.

`analyze_message` rozšiřuje pipeline paket `kind="llm_intake"` / v1 o:

- `analysis_status`: `extracted` nebo `no_facts`; nejde o vyhodnocení zdraví.
- `question_candidates`: seznam `{question: celý balíček, fact_indices: [...]}`,
  v pořadí definic, bez duplicit. Indexy odkazují do `facts`.
- `unmapped_concepts`: sdělené pojmy bez vazby v počátečním katalogu.
- `unknown_subject_fact_indices`: fakta s neurčeným subjektem, která nelze
  automaticky použít k dotazování pacienta.

Kandidáty vytvářejí pouze fakty se subjektem `patient` a přítomností `present`
nebo `uncertain`. Popření a potíže pečujícího zůstávají ve `facts`, ale samy
nevyvolají dotaz pacientovi. Neznámá témata a neurčené subjekty jsou explicitní
mezery, nikoli důkaz normálního stavu. `question_answers` je zatím prázdný:
model nevybírá indexy možností a nic není automaticky potvrzené.

Tyto kandidáty ještě **nepokládat slepě jeden po druhém**. Následný malý krok
má využít již sdělené hodnoty, nabídnout jejich potvrzení, řídit podmíněné
větve a rozpočet celého kontaktu. Kandidát s úplným faktem nemusí potřebovat
novou otázku. Historii, naléhavost ani stáří údajů tato funkce nevyhodnocuje.

## CLI nad zaznamenanou zprávou

Linux i PowerShell, z kořene repa; klíč je ve stávajícím ignorovaném `.env`:

```text
uv run --locked --env-file llm_intake/.env python -m llm_intake.master llm_intake/master_input.example.json
```

[Vstup](master_input.example.json) obsahuje syntetickou odpověď na MASTER QUESTION
a explicitní simulovaný čas dostupnosti. CLI vypíše pouze JSON pro další
zpracování; chyby jdou na stderr s kódem 1. Toto není pacientské UI a nevede
navazující rozhovor. Přijme stejný formát i pro spontánní zprávu či cílenou odpověď.
[Ukázkový výstup](master_output.example.json) pochází z živého volání nad tímto
syntetickým vstupem, nikoli z klinické reference.

Ověřeny tři živé syntetické scénáře: více témat s popřenou teplotou, pečující
s vlastním příznakem a přibližným počtem průjmů pacienta, nejistá horečka
s nenamapovanou nespavostí. Jde o základní kontrolu, nikoli benchmark přesnosti.
Technický podklad ke schématu: [OpenAI Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs?api-mode=chat),
ověřeno 16. 10. 2026. Schéma ani citace nedokazují úplnost a správný význam.

Ověření z kořene repa v Linuxu i PowerShellu:

```text
uv run --locked python -m pytest tests/test_master_contract.py tests/test_master_extraction.py -q
```
