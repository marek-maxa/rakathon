# LLM intake

Modul zpracovává slovní zprávy a odpovědi, navrhuje cílené otázky a řídí
potvrzení/opravy. Neurčuje triáž, nespravuje pacientskou kartu ani termíny.
Web ho propojuje se sdíleným backendem; [architektura](../docs/architecture.md).
Datové typy a výstupy jsou v [MASTER_CONTRACT.md](MASTER_CONTRACT.md).

## Konfigurace

Z kořene repozitáře, Python 3.12 + uv, stejné příkazy na Linuxu a PowerShellu:

```text
uv sync --locked
```

Zkopírujte [.env.example](.env.example) do `llm_intake/.env` a doplňte klíč.
CLI používá explicitní `--env-file`; web soubor načte automaticky. `.env`
nepatří do Gitu. Živá volání provádějte jen se syntetickými nebo schválenými daty.

| Proměnná | Význam |
| --- | --- |
| `MEDDI_LLM_API_KEY` | Povinný přístupový klíč |
| `MEDDI_LLM_BASE_URL` | HTTPS base URL brány; výchozí hodnota v `client.py` / `.env.example` |
| `MEDDI_LLM_MODEL` | Deployment, nikoli obecný název modelu; výchozí `gpt-6-1-sol-dz-eu` |
| `MEDDI_LLM_KEY_HEADER` | Výchozí `api-key`; klient podporuje také `Authorization` a `Ocp-Apim-Subscription-Key` pro jinou konfiguraci |

`Client` posílá `/chat/completions` s `response_format=json_schema`,
`strict=true`, bez nástrojů/streamování. Výstup validuje i lokálně a na volný
text při chybě nepřechází. Hlavička `Authorization` používá Bearer, ostatní
hlavičky samotný klíč. Přesměrování s klíčem klient nepovoluje.
Konfigurace brány a podporovaný deployment se ověřují u jejího provozovatele.

## MASTER a jedna cílená otázka

```text
uv run --locked --env-file llm_intake/.env python -m llm_intake.dialogue --debug --output .scratch/master-output.json
uv run --locked --env-file llm_intake/.env python -m llm_intake.dialogue --input llm_intake/master_input.example.json --debug
uv run --locked --env-file llm_intake/.env python -m llm_intake.master llm_intake/master_input.example.json
uv run --locked --env-file llm_intake/.env python -m llm_intake --question unava --debug
uv run --locked --env-file llm_intake/.env python -m llm_intake --questionnaire bolest_analgeticka_terapie --question sos
uv run --locked python -m llm_intake --list
```

`dialogue` vede MASTER a cílený rozhovor; `master` pouze extrahuje zprávu do
JSON; kořenové CLI řeší jednu otázku a po potvrzení zavolá sdílenou triáž.
Samotný modul nadále není bezpečnostní orchestrátor.

Pacient odpovídá vlastními slovy. Výchozí CLI vyžaduje `ano/ne` pro slovní
návrh, po odmítnutí přijme opravu. `/moznosti` ukáže texty možností bez LLM,
`/konec` ukončí kontakt. `--debug` zobrazí interní JSON, `--output` u MASTER
uloží výstup i do souboru. `.scratch/` Git ignoruje.

MASTER CLI má výchozí limit `--max-questions 6`, doptání parametru
`--max-clarifications 2`. Nevyřešené hodnoty se nevynucují. Čas MASTER CLI
je simulovaný (`--at`), během kontaktu se sám neposouvá; vstupní soubor dodá
vlastní čas. Nejde o pravidelné sledování pacienta.

Web používá `bulk_confirmation=True`, `review_sessions`, `revise(index)`
a `confirm_all()`: společná kontrola návrhů, oprava se zneplatněním podřízených
odpovědí a potvrzení jen vyřešených návrhů. Volba autora a personalizace jsou
teprve [požadovaná rozšíření](../docs/meddi-onco-plan.md#zpráva-pacienta-a-personalizace).

## Python API

```python
from llm_intake import Intake, load_question
from llm_intake.client import Client

session = Intake(load_question("nezadouci_ucinky", "unava"), Client.from_env())
session.submit("Odpočinek mi pomůže.")
summary = session.patient_summary()
# Až po skutečném souhlasu pacienta:
confirmed = session.confirm()
```

Pro testy nahraďte klienta funkcí bez sítě. Rozhraní extraktoru je
`extract(question, source_messages, source_questions) -> dict`;
`Client.extract_events` navíc předává autory z událostí. Používejte
`seed(messages)` / `submit_event(message)`, pokud znáte skutečné otázky,
autory a dostupnost. `submit(text)` tato metadata nevymýšlí.

`QuestionnaireFlow` řídí pořadí/podmínky celého formuláře nebo `targets`.
`find_question` / `create_targeted_session` umožňují cílený vstup; při
nejednoznačném ID je potřeba uvést dotazník. API a stavy jsou v kontraktu.

## Prompty a omezení

- [prompt.md](prompt.md) a [master_prompt.md](master_prompt.md) jsou runtime
  instrukce, nikoli vývojový deník. [examples.json](examples.json) a
  [master_examples.json](master_examples.json) jsou příklady pro model,
  nikoli nezávislá evaluace.
- Definice otázek a možností se načítají z originálu; barvy/triážní pravidla
  LLM nedostává. Katalog [question_topics.json](question_topics.json)
  obsahuje všechny otázky a jeho úplnost se kontroluje proti zdroji.
- MASTER zachovává všechny podložené pojmy včetně nepokrytých; cílený extraktor
  přiřazuje hodnotu jedné otázky. Obecná extrakce dalších odpovědí zachytí i nové
  potíže. Katalog není bezpečnostní filtr ani záruka klinické úplnosti.
- Cílený klient vybírá nejvýše tři relevantní příklady; katalog je před
  proměnlivou zprávou. Jeho přesun mezi rolemi požadavku vyžaduje regresi
  citlivých případů a chyb brány, nejen kontrolu tokenů.
- Chyba API, blokace `content_filter` a nevalidní výstup nejsou úspěšná prázdná
  extrakce. Stav a nevyřešené zdroje musí převzít volající; snapshot není resume.
- Zdrojové rozpory NRS a průjmu a limity klinického mapování jsou pouze
  v [backendu](../docs/backend.md#otevřené-klinické-otázky).

## Evaluace a metriky

Offline testy a náhrady transportu:

```text
uv run --locked python -m pytest tests/test_llm_intake.py tests/test_master_contract.py tests/test_master_dialogue.py tests/test_questionnaire_flow.py -q
```

Živé syntetické evaluace volají API:

```text
uv run --locked --env-file llm_intake/.env python -m llm_intake.evaluate_topics --output .scratch/master-topics-evaluation.json
uv run --locked --env-file llm_intake/.env python -m llm_intake.evaluate_topics --cases tests/fixtures/master_precision_cases.json --output .scratch/master-precision.json
```

`--case ID`, `--limit` a `--workers` omezí běh, `--cases` lze opakovat.
[Minimální pokrytí](../tests/fixtures/master_topic_cases.json) a
[přesnější anotace](../tests/fixtures/master_precision_cases.json) jsou
oddělené od promptových příkladů. `topic_recall` má jmenovatel očekávaných
výskytů u validních odpovědí; `topic_precision` jen u úplně anotovaných
povolených témat. Chyby API/validace jsou zvlášť a nepočítají se jako úspěch.
Negace, subjekt a hodnoty mají samostatné kontroly.

`Client(on_usage=callback)` předává tokeny, cache, reasoning a dobu bez textu
pacienta a klíče; chybějící měření je null, nikoli nula. Celý dialog navíc
vyžaduje nezávislou kontrolu správnosti potvrzené možnosti, zbytečných dotazů,
oprav a nevyřešených kontaktů. Schéma, citace ani pacientovo potvrzení samy
neprokazují přesnost; syntetická evaluační sada není klinická validace.

Web na main vybírá jen relevantní otázky, využívá sdělené údaje z MASTER
a doptává chybějící rozlišení. Limit kontaktu je opět 6; celé formuláře
se automaticky neotevírají. Historické zprávy podporuje
`meddi.messages`; CLI replay je zapíná explicitně přes `--with-messages`.
Konfigurace hesla a balení dema je pouze v [architektuře](../docs/architecture.md#heslo-dema-a-balení-pro-azure).
