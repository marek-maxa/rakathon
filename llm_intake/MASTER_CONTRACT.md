# Zpráva → fakta → vazby na otázky

Samostatný modul pro MASTER QUESTION obsahuje datový kontrakt, katalog,
LLM extraktor, návrh kandidátních otázek a omezený interaktivní dialog.
Dosavadní `Intake` a export v2 zůstávají kompatibilní, navíc lze předat
zdrojové události. Tento jiný typ pipeline výstupu má vlastní verzi 1.
Bez nových závislostí, triáže, ukládání karty a časovače.

## Rozhraní

- [master_contract.py](master_contract.py): `MessageEvent`, `Fact`,
  `NumericRange`, `build_packet(message, facts) -> dict`.
- [question_catalog.py](question_catalog.py): `load_catalog()`,
  `load_topic_catalog()`, `resolve_topics(topic_ids) -> list[dict]`
  a kompatibilní `lookup_questions(concepts) -> dict`.
- [question_topics.json](question_topics.json): klíčová slova, aliasy a kontext
  pro každou otázku. Texty otázek a možnosti se načítají přímo ze zdroje.
- [master.py](master.py): `MasterExtractor(client)(message) -> list[Fact]`,
  `validate_facts(result, message)` a `analyze_message(message, extract) -> dict`.
- [dialogue.py](dialogue.py): `MasterDialogue`, interaktivní CLI a rozpočet kontaktu.
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
| `topic_ids` | Seznam přesných ID `dotaznik/otazka` podložených faktem; celý katalog tvoří enum modelového schématu. Pro nepokrytý pojem prázdný seznam |
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
se týká cílených odpovědí, samostatné fakty tím nepotvrzuje. Neplatná data vyvolají výjimku;
prázdný seznam faktů značí pouze prázdnou extrakci, nikoli dobrý zdravotní stav.
Typové kontroly a citace nedokazují správný význam, úplnost ani klinickou platnost.

## Použití bez sítě

```python
from llm_intake.master_contract import Fact, MessageEvent, NumericRange, build_packet
from llm_intake.question_catalog import lookup_questions

message = MessageEvent(
    id="synthetic-01",
    patient_id="synthetic-patient",
    text="Zvracel jsem pětkrát nebo šestkrát.",
    available_at="2026-10-16T10:00:00+02:00",
    source="master_question",
    author="patient",
    question="Jak se dnes cítíte?",
)
fact = Fact(
    concept="vomiting.episodes",
    presence="present",
    subject="patient",
    evidence="Zvracel jsem pětkrát nebo šestkrát",
    value=NumericRange(5, 6),
    unit="episodes",
    certainty="uncertain",
)
packet = build_packet(message, [fact])
links = lookup_questions(f["concept"] for f in packet["facts"])
```

Katalog načítá všech 49 otázek z
[definic](../rakathon_meddi_onco_data/docs/dotazniky_definice.json).
Klíčem je dvojice ID dotazníku a otázky. Zachovává text, typ a zdrojovou
`podminka`. Katalog používá stejný balíček `Question.specification()` jako
intake, včetně možností, návodu a směru škály, bez barev.
`load_topic_catalog()` přidá ke každé otázce klíčová slova, aliasy a `hint`.
Kontroluje přesnou shodu ID se zdrojem: 25 otázek nežádoucích účinků,
9 psychoonkologických, 5 analgetických a 10 ESAS. Chybějící i nadbytečná
položka znamená chybu, nikoli zúžení promptu. Toto není úplné klinické pokrytí.

`resolve_topics` převede přesná ID na aktuální balíčky ve zdrojovém pořadí.
U podmíněného popisu zahrne také rodiče (`krvaceni`, `nu`), organizační
rozcestníky při konkrétní potíži nepřidává. Větvení následně vyhodnocuje
[QuestionnaireFlow](../docs/llm-flow.md) podle potvrzených odpovědí.
Podobná témata v různých formulářích se nezaměňují: běžná slovní únava vede
na `nezadouci_ucinky/unava`, výslovná škála ESAS na `esas/unava`.
Nespavost se nepřevádí na denní ospalost. Kontext určují i celé možnosti,
nejen shodné slovo v názvu otázky.

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

message = MessageEvent(
    **json.loads(
        Path("llm_intake/master_input.example.json").read_text(encoding="utf-8")
    )
)
packet = analyze_message(message, MasterExtractor(Client.from_env()))
```

Extraktor používá stávající deployment a autentizaci; `Client.structured_payload`
a `Client.send` sdílejí sestavení striktního požadavku a HTTP transport s Intake.
Modelu posíláme text, skutečnou otázku a autora, pět příkladů a úplný katalog
všech 49 otázek s klíčovými slovy, kontextem a možnostmi odpovědí.
Klíčová slova pomáhají porozumění; nejde o doslovné filtrování ani top-k.
Model vrací všechna podložená `topic_ids` u jednotlivých faktů, schéma
dynamicky přidá enum všech ID. Kód ověřuje ID a páruje je mechanicky.
Katalog je statická část posledního uživatelského vstupu, před polem `message`.
Obsahuje celé texty a možnosti; mechanická metadata (`order`, `condition`,
duplicitní ID) zůstávají v aplikačním katalogu. Společný kontext formuláře
je jednou v `questionnaire_context`.
ID pacienta, systémový čas, barvy ani pravidla
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
- `unmapped_concepts`: sdělené pojmy bez odpovídající otázky. Obecné „jiné“
  nesmí zakrýt nepokrytý problém, například zmatenost.
- `unknown_subject_fact_indices`: fakta s neurčeným subjektem, která nelze
  automaticky použít k dotazování pacienta.

Kandidáty vytvářejí pouze fakty se subjektem `patient` a přítomností `present`
nebo `uncertain`. Popření a potíže pečujícího zůstávají ve `facts`, ale samy
nevyvolají dotaz pacientovi. Neznámá témata a neurčené subjekty jsou explicitní
mezery, nikoli důkaz normálního stavu. `question_answers` je zatím prázdný:
model nevybírá indexy možností a nic není automaticky potvrzené.
Vlastní extraktory mohou nadále vracet `Fact` bez `topic_ids`; pak kód použije
anglické aliasy z katalogu a tečkovaná pole dědí nejbližší známou vazbu.
Modelový výstup přes `MasterExtractor` musí pole vracet vždy.

Tyto kandidáty **nepokládat slepě jeden po druhém**. `MasterDialogue` nyní využívá
již sdělené hodnoty, nabídne jejich potvrzení, řídí podmíněné větve a rozpočet
kontaktu. Kandidát s úplným faktem nemusí potřebovat novou otázku. Historii,
naléhavost ani stáří údajů vůči klinickým pravidlům tato vrstva nevyhodnocuje.

## Omezený MASTER dialog

```text
uv run --locked --env-file llm_intake/.env python -m llm_intake.dialogue --debug --output .scratch/master-output.json
```

Výchozí MASTER zní „Jak se dnes cítíte?“. `--input soubor.json` ji nahradí
zaznamenanou zprávou. Parametr `--at` nastaví simulovaný čas; všechny nové
odpovědi CLI mají stejný čas dostupnosti v rámci tohoto kontaktu. S `--input`
se použije čas ze souboru. Pořadí rozlišují události a seznam `messages`.

`Intake.seed(messages)` předá existující `MessageEvent` bez změny původních
otázek (včetně null u spontánní zprávy). Úplný význam přejde k potvrzení,
neúplný k doptání. Nové odpovědi se předávají přes `submit_event(message)`.
`Client.extract_events` posílá k textům i jejich autory, bez ID a časů.
Původní `submit(text)` a tříargumentové extraktory zůstávají funkční.

Python:

```python
from llm_intake.client import Client
from llm_intake.dialogue import MasterDialogue
from llm_intake.master import MasterExtractor

client = Client.from_env()
contact = MasterDialogue(
    MasterExtractor(client),
    client,
    extract_with_events=client.extract_events,
    max_questions=6,
    max_clarifications=2,
)
packet = contact.start(message)  # MessageEvent z předchozího příkladu
# needs_confirmation: po výslovném souhlasu contact.confirm(), jinak contact.reject()
# needs_answer/needs_correction: MessageEvent s contact.active.next_question → contact.submit(event)
packet = contact.snapshot()
```

Každá slovní odpověď projde také obecnou extrakcí, aby se neztratilo nové téma.
Nové kandidáty přidá `QuestionnaireFlow.add_targets()` po ukončení aktivní
relace, se zachováním už potvrzených odpovědí. Při více tématech se nejprve
dokončí aktivní relace; řízení naléhavosti je nezávislý budoucí vstup.
Při chybě extrakce se odpověď nepotvrdí ani se nezmění na prázdný úspěch.
CLI skončí kódem 1 a může uložit dosud zpracovaný stav; nemá automatické resume.
I při selhání první extrakce uchová úvodní zprávu. `analysis_status` je při
`dialogue.reason=processing_error` rovněž `processing_error`, nikoli `no_facts`.
Chybu `content_filter` odlišujeme od chyby schématu; nelze ji počítat jako
úspěšně vyhodnocenou zprávu.

Rozpočet `max_questions` (výchozí 6) zahrnuje MASTER, vydané doptání, žádosti
o potvrzení i opravu. Texty možností nebo opakování po neplatném vstupu nejsou
nový dotaz. `max_clarifications` (výchozí 2) je zároveň limit doptání parametru.
Stav `complete` znamená dokončený sběr v tomto rozsahu, nikoli triáž. `limited`
znamená vyčerpaný rozpočet, `unresolved` nevyřešený dotaz, nepokryté téma nebo
neurčený subjekt; `cancelled` přerušení. CLI vrací 0 / 2 / 1 pro dokončení /
neúplné či přerušené zpracování / chybu. Nepotvrzené hodnoty se nevynucují.

JSON rozšiřuje původní paket o `messages` (zdrojové události celého kontaktu)
a `dialogue` (stav, důvod ukončení, počítadlo, limit a stavy větví).
`dialogue.pending_topic_ids` obsahuje připravené i blokované otázky, které ještě
zbývají. Limit nezkracuje seznam faktů nebo rozpoznaných kandidátů. `facts`
obsahuje fakta všech zpráv s jejich původními `source_message_id`;
`fact_indices` odkazují do tohoto spojeného seznamu. `question_answers`
obsahuje ukončené i případnou aktivní nepotvrzenou relaci. Její `turns` navíc
zachovává ID, čas dostupnosti a autora zdrojové události. Fakta zůstávají
nepotvrzenými návrhy; potvrzení se týká přesné hodnoty cílené odpovědi.
Pozdější protichůdné sdělení se uchová; jiná už potvrzená odpověď se automaticky
nepřepisuje. Řešení rozporů a časových epizod zůstává budoucí integrace.

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

## Regrese úplného katalogu

[53 syntetických případů](../tests/fixtures/master_topic_cases.json) pokrývá
všech 49 ID a navíc více témat, popření, pečujícího a nepokryté potíže.
Nejsou součástí in-context příkladů. Živý běh:

```text
uv run --locked --env-file llm_intake/.env python -m llm_intake.evaluate_topics --output .scratch/master-topics-evaluation.json
```

Report měří záchyt očekávaných témat přímo z modelových `topic_ids`, nikoli
z pozdějšího aliasového fallbacku. Chyby API a validace jsou nevyhodnocené
případy mimo jmenovatel `topic_recall`, běh s chybami přesto neprojde.
Témata navíc vypisuje zvlášť; nejde o přesnost
na klinicky anotovaném vzorku. `--case ID` lze opakovat pro vybrané scénáře.
Volitelné `allowed_topics` označuje úplný seznam povolených témat případu;
nepovolené přiřazení znamená neúspěch i při plném záchytu. `fact_checks`
ověřuje anotovaný subjekt, negaci nebo hodnotu. `topic_precision` se počítá
pouze nad takto označenými případy; `topic_recall` nad očekávanými tématy
všech validně vyhodnocených případů. `api_usage` zachovává měření z API
i u neúspěšné validace, pokud je brána vrátila. Bez údajů report vrací null.
Pro přesnost slouží další [syntetická sada](../tests/fixtures/master_precision_cases.json);
[příkaz a spotřeba](README.md#spotřeba-tokenů).
Strukturální testy garantují pokrytí promptu a mechanické směrování,
konečná syntetická sada nezaručuje zachycení každé budoucí formulace.

Ověření 16. 10. 2026: 53/53 případů splnilo kontrolu minimálního pokrytí,
55/55 očekávaných výskytů témat zachyceno. U 21 případů bylo nutné po HTTP 429
opakovat volání se souběhem 1; žádný případ s chybou se nepočítal jako úspěšný.
Model vrátil také 10 dalších přiřazení, včetně popřeného příznaku a souvisejících
otázek. Z toho neodvozujeme míru falešných přiřazení ani klinickou přesnost.

Ověření z kořene repa v Linuxu i PowerShellu:

```text
uv run --locked python -m pytest tests/test_master_contract.py tests/test_master_extraction.py tests/test_topic_catalog.py -q
```
