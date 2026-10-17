# Kontrakt LLM intake

Rozlišujeme tři výstupy: zdrojové fakty `build_packet` / v1, export jedné
odpovědi `Intake.snapshot` / v2 a paket kontaktu `llm_intake` / v1.
Verze nejsou vzájemné náhrady. Konfigurace/CLI jsou v [README](README.md),
triážní adaptér v [backendu](../docs/backend.md).

## Zpráva a fakt

Webový portál může zahájit kontakt přímo odpovědí na sledovanou otázku:
`MasterDialogue(..., follow_up_topic="dotaznik/otazka")` validuje a přidá
jednu existující otázku, její běžné podmíněné větve a nové relevantní potíže.
První událost má skutečnou otázku a `source=targeted_answer`; počítá se do
rozpočtu. Validní cílená odpověď projde běžným potvrzením i při prázdné obecné
extrakci. Neodhadnutá odpověď, neznámé další pojmy a chyba dál zůstávají
nevyřešené; checkpoint se volá před cílenou extrakcí stejně jako u MASTER.

[master_contract.py](master_contract.py) poskytuje `MessageEvent`, `Fact`,
`NumericRange` a `build_packet(message, facts)`.

| MessageEvent | Význam |
| --- | --- |
| `id`, `patient_id` | Stabilní zdrojová událost a pacient |
| `text` | Doslovné původní sdělení |
| `available_at` | ISO 8601 s pásmem; čas dostupnosti |
| `source` | `master_question`, `patient_message`, `targeted_answer` |
| `author` | `patient`, `caregiver`, `team`, `unknown`; dodává aplikace |
| `question` | Skutečná otázka, povinná pro odpovědi; u spontánní zprávy může být null |

| Fact | Význam |
| --- | --- |
| `concept` | Anglický pojem; nenamapované pojmy zůstávají zachované |
| `topic_ids` | Přesná ID `dotaznik/otazka`; prázdné u nepokrytého pojmu |
| `presence` | `present`, `absent`, `uncertain`; absence zmínky nevytváří fakt |
| `subject` | `patient`, `caregiver`, `unknown`, nezávisle na autorovi |
| `value`, `unit` | Číslo včetně nuly, text, NumericRange nebo null; výslovná jednotka |
| `time_text` | Doslovný časový výraz nebo null; není normalizovaný čas pozorování |
| `certainty` | `stated`, `approximate`, `uncertain`, nikoli kalibrovaná jistota modelu |
| `evidence` | Neprázdná doslovná citace ze zprávy |

`NumericRange` má dolní/horní mez a jejich uzavřenost; jedna mez může chybět.
Interval se nepřevádí na přesnou horší hodnotu. Sdělená nula zůstává číslem,
nikoli automatickou negací. `build_packet` ověří citaci a časový výraz vůči
zprávě a přidá `source_message_id`, `confirmation=unconfirmed`.
Prázdná extrakce neznamená dobrý stav. Neplatný vstup vyvolá výjimku.

Offline příklad:

```python
from llm_intake import Fact, MessageEvent, NumericRange, build_packet

message = MessageEvent(
    id="synthetic-01", patient_id="synthetic-patient",
    text="Zvracel jsem pětkrát nebo šestkrát.",
    available_at="2026-10-17T10:00:00+02:00",
    source="master_question", author="patient", question="Jak se dnes cítíte?",
)
fact = Fact(
    concept="vomiting.episodes", presence="present", subject="patient",
    evidence="Zvracel jsem pětkrát nebo šestkrát", value=NumericRange(5, 6),
    unit="episodes", certainty="uncertain",
)
packet = build_packet(message, [fact])
```

Příklad nedokládá 24hodinové okno; backend ho nesmí doplnit odhadem.

## Extrakce a katalog

Volitelný `clinical_fields` dodává extraktoru názvy vstupů existujících
pravidel pro přesně sdělené údaje. Nemění schéma faktu ani nepovoluje LLM
určit triáž; historické zprávy jej používají pro kompatibilní mapování.

`MasterExtractor(client)(message)` vrací seznam faktů.
`analyze_message(message, extract)` přidá do paketu:

| Pole | Význam |
| --- | --- |
| `analysis_status` | `extracted` / `no_facts`, při chybě uloženého dialogu také `processing_error` |
| `question_candidates` | Balíček otázky a `fact_indices`, pořadí podle definic, bez duplicit |
| `unmapped_concepts` | Sdělené problémy bez odpovídající otázky |
| `unknown_subject_fact_indices` | Fakta s neurčeným subjektem |

Model dostává text, skutečnou otázku a autora, úplný katalog s možnostmi
a syntetické příklady. ID pacienta, systémový čas, barvy ani klinická pravidla
nejsou součástí modelového vstupu. Validační schéma omezuje vrácená topic ID.
Kandidáti vznikají z pacientových přítomných/nejistých faktů; popření a vlastní
potíže pečujícího zůstanou ve faktech, ale nevyvolají automaticky dotaz pacientovi.

`load_topic_catalog()` spojuje [question_topics.json](question_topics.json)
s [definicemi](../rakathon_meddi_onco_data/docs/dotazniky_definice.json) všech
49 otázek; chybějící/nadbytečné ID je chyba. `resolve_topics(topic_ids)` vrací
aktuální balíčky ve zdrojovém pořadí, pro podmíněný popis zahrne příslušného
rodiče. `lookup_questions(concepts)` je kompatibilní aliasové mapování;
nefiltrovalo by samo subjekt/negaci. U vlastních extraktorů bez `topic_ids`
se použije aliasový fallback, modelový výstup je musí vracet.

Katalog není klinické pokrytí. Kandidát není povinnost položit otázku;
již sdělený údaj se využije a nerozpoznaný problém se nezahodí.

## Intake a QuestionnaireFlow

`Intake(question, extract, max_clarifications=2, extract_with_events=None)`
spravuje jednu otázku. `submit(text)` zachová text, ale nedodá chybějící metadata.
`seed(messages)` a `submit_event(message)` zachovají skutečné zdrojové události.
`next_question` je aktuální text, `patient_summary()` slovní návrh.

| Stav | Další krok |
| --- | --- |
| `needs_answer` | Dodat odpověď na aktuální otázku |
| `needs_confirmation` | Po výslovném souhlasu `confirm()`, jinak `reject()` |
| `needs_correction` | Dodat slovní opravu |
| `confirmed` | Dokončená potvrzená hodnota |
| `unresolved` | Nevyřešeno, bez vynucené možnosti; důvod a zdroje zůstávají |

Extraktor jedné otázky vrací přesně `status`, `value`, `source_index`,
`evidence`, `follow_up`. `answered` má hodnotu a citaci, `follow_up=null`;
`unclear` má hodnotu/zdroj null a jednu cílenou otázku do 240 znaků.
Indexy možností jsou od nuly, u více možností seznam. Číslo/škála/text nejsou
index možnosti. Výlučné „žádné účinky“ nelze kombinovat s pozitivní volbou.

`Intake.snapshot()` / `confirm()` vrací `schema_version=2`, identifikaci otázky,
revizi/stav/potvrzení, `odpoved`, `odpoved_index`, `extraction`, chronologické
`source_messages`, `source_questions`, případné `source_events`,
`signaly_odpovedi`, `follow_up`, `unresolved_reason`, `metrics`.
`confirmed_data()` je jen pro potvrzený stav. Zdrojové barvy připojí kód z definic,
nikoli model; nejsou finální triáž.

`QuestionnaireFlow(questionnaire_id, targets=None)` řídí zdrojové pořadí
a `podminka`: `next_question()` → Intake → `record(session)`.
Cílený vstup nevyplní rodiče mimo rozsah; pokud rodič ve zvoleném rozsahu
větev vyloučí, cíl ji nepřebije. Nevyřešené závislosti jsou `blocked`.
`find_question(question_id, questionnaire_id=None)` odmítne nejednoznačné ID;
`create_targeted_session` připraví samostatný Intake s volitelným klientem.

## MASTER kontakt a paket pipeline

`MasterDialogue(extract_message, extract_answer, extract_with_events=None,
max_questions=6, max_clarifications=2, bulk_confirmation=False)` poskytuje:

- `start(message)`, `submit(message)`, `snapshot()` a `cancel(reason)`.
- Výchozí potvrzení `confirm()` / `reject()` pro aktivní otázku.
- Pro společné potvrzení: `review_sessions`, `revise(index)`, `confirm_all()`;
  oprava zneplatní závislé odpovědi, nepotvrdí nevyřešený návrh.

Web i CLI vybírají přes `targets` konkrétní relevantní otázky a jejich
podmíněné větve, nikoli celé formuláře. Existující zprávy využívá `seed`;
úplný údaj jde k potvrzení, chybějící rozlišení k doptání. Výchozí limit je 6.
`dialogue.mode=targeted_from_message` označuje cílený tok. Nenamapované
nálezy zůstávají v paketu i bez odpovídající otázky.

Pro celkový pocit bez přesné hodnoty se neprovádí `seed`, který by mohl
odhadnout ordinalitu z „dobrý“. Nabídne se původní škála 1–5. Přesná krátká
kladná odpověď na skutečnou MASTER otázku má při prázdné extrakci omezenou
zálohu v `analyze_message`: vznikne doložený slovní `overall_feeling`,
nikoli číslo nebo negace všech příznaků. Chyba extraktoru touto cestou nejde.
Potvrzenou navazující odpověď dokládá až backend v `clarified_facts`;
zdrojový fakt z intake nemizí. Obecné prázdné/nejasné odpovědi zůstávají
nevyřešené.

Každá slovní odpověď projde obecnou extrakcí; nové kandidáty přidá flow po
uzavření aktivní relace. Dialog spravuje rozpočet, nikoli naléhavost.
Výchozí režim započítává také vydané žádosti o potvrzení a opravy;
webová společná kontrola potvrzení neprovádí po každé otázce.
`complete` znamená hotový sběr v daném rozsahu, `limited` vyčerpaný rozpočet,
`unresolved` nevyřešený vstup, `cancelled` přerušení. Chyba není prázdný úspěch.

`start(message, checkpoint=None)` a `submit(message, checkpoint=None)` přijímají
volitelný keyword callback `checkpoint(packet) -> bool`. Volá se po obecné
extrakci a před cíleným seed/submit. Vrátí-li true, dialog zůstane `paused`
s důvodem `external_checkpoint`; zpráva a její fakta jsou zachované, cílená
extrakce ještě neproběhla. `resume()` dokončí odloženou práci bez opakování
obecné extrakce. Web tím před dalším LLM zobrazí naléhavou instrukci; samotný
dialog klinickou politiku nezná a callback si neukládá. Bez callbacku se tok
nemění. Pozastavení ani `resume()` neimplementují trvalou obnovu K2b.

`build_pipeline_packet(message, facts, sessions)` vrací `kind=llm_intake`,
`schema_version=1`, `message`, `facts`, `question_answers`. Každá odpověď má
balíček `question`, `state`, `confirmed`, `revision`, `value`, slovní `answer`,
`evidence` s indexem do `turns`, samotné tahy, `follow_up`, důvod a metriky.
Nepotvrzený návrh je odlišený, odmítnutý/nevyřešený nemá platnou hodnotu.

MASTER rozšíří paket o `messages`, analýzu a `dialogue`: stav/důvod, počet a
limit dotazů, stavy flow a `pending_topic_ids`. Fakta mají původní zdrojová ID,
`fact_indices` odkazují do společného seznamu. Tahy odpovědí zachovají známého
autora a čas. Potvrzení odpovědi nepotvrzuje samostatné fakty a pozdější
protichůdná zpráva sama nepřepíše jinou potvrzenou odpověď.

[Ukázka paketu](pipeline_example.json) a [vstup MASTER](master_input.example.json)
jsou syntetické. Limity nezkracují seznam rozpoznaných faktů/kandidátů.
Snapshot není serializované obnovení; bezpečnostní reakce, persistence,
aktuální epizody a plánování patří do [aplikačního toku](../docs/meddi-onco-plan.md).
Citace a striktní schéma neprokazují sémantickou ani klinickou správnost.
