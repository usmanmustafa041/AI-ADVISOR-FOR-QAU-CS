# QAU chatbot recovery — release remains blocked

The isolated replacement runs at <http://127.0.0.1:5180>. The interim `qwen3:8b` still produces unacceptable answers. No production cutover or legacy deletion is authorized. Engineering checks and successful HTTP responses do not establish factual accuracy.

The user confirmed a review export exists. Its local path has not been supplied, so no independently supplied references or grades have been imported or counted.

## Actual evidence

All thirty development questions were replayed before the recovery changes, then on the preserved old API and the replacement. Twenty separate student conversations completed 36 consecutive turns with real owner-bound server conversation IDs. Every raw answer, including failures, is retained.

| Run | HTTP completions | Median | p95 | Median first visible token |
| --- | ---: | ---: | ---: | ---: |
| Fresh replacement before recovery | 30/30 | 13.1 s | 58.2 s | 9.6 s |
| Preserved old chatbot | 30/30 | 17.0 s | 25.6 s | Not exposed by old JSON endpoint |
| Recovery replacement before extraction correction | 30/30 | 16.0 s | 61.5 s | 12.7 s |
| Twenty conversations before extraction correction | 36/36 turns | 18.7 s | 61.0 s | See individual traces |

These are transport measurements, not answer pass rates. They do not show a consistent latency improvement over the fresh pre-recovery run. Median interpretation took 7.35 s, generation 10.69 s, and retrieval 26 ms. Stage medians cannot be added to obtain the total median because the case sets and distributions differ. No reranker was selected. The parser migration ran briefly alongside part of the evaluation; these are development measurements, not isolated production throughput measurements.

- [Full paired old/new answers](../.runtime/chatbot-v3/evaluation/recovery-comparison.md).
- [All thirty engineering diagnoses](../.runtime/chatbot-v3/evaluation/recovery-failure-audit.md) and [pipeline inputs, evidence and raw responses](../.runtime/chatbot-v3/evaluation/recovery-failure-audit.json).
- [Twenty actual student conversations](../.runtime/chatbot-v3/evaluation/recovery-final-student-conversations.md).
- [Stage timing distributions](../.runtime/chatbot-v3/evaluation/recovery-stage-latencies.json).
- [Independent review workbench](../.runtime/chatbot-v3/evaluation/review.html).

The paired report records the selected case's code hash and parser version. Later affected-case replays supplement the complete thirty-case run. Earlier malformed-output, queue, timeout, incomplete-generation and unavailable-baseline trials remain available under `recovery-*`; they are not hidden by a later successful request.

## Repairs and practical limits

The replacement distinguishes scheme membership from prerequisites, explicit research interests from publications, and dated teaching assignments from historical teaching lists. Faculty retrieval uses individual official profile fields. A unique observed course identity resolves an alias such as `CS104`; multiple real identities remain ambiguous. Alias lookup excludes unverified workspace sources.

Structured lookup results now reach generation. Each requested fact has an evidence type; citations to a source of another type are rejected. Lecture/lab components and their calculated sum are supported separately. Uncited blocks cannot introduce unrelated course identifiers. These constraints do not prove that every sentence is entailed by a source or that a self-labelled “limitation” contains no factual claim.

The admissions replay exposed a concrete extraction failure: the BS heading was separated from its Mathematics/50% requirements. Parser `v3-pdfplumber-html-4` preserves the official site's nested degree card and FAQs. All 388 unique previously catalogued originals were checked and re-parsed into a 1,006-chunk checksummed E5 bundle. This does not claim recovery of earlier unparseable or uncrawled inputs. Publication changes only the preview pointer and retains the prior bundle.

An intact, warning-free official degree section can describe published eligibility/test requirements while extraction review is pending. This does not certify personal eligibility. Fees, registration, current dates, timetables, policies and OCR still require applicable reviewed evidence. No academic source approval was fabricated.

Native model timings now include prompt processing, generation, token counts and raw first token. Interpretation and generation have wall-time limits; tutoring uses a smaller output budget than full grounded lists. Language repair occurs after the original stream closes, in one batch bounded to 45 seconds, with identifier/number checks. Translation is not an independent truth audit. A failed repair remains a failed answer.

The browser replay exposed another concrete validation defect: a course-only list with unchanged official English titles was needlessly translated as wrong-language prose, then withheld. Only rows matching the cited source are now exempt from prose translation; altered rows and ordinary prose are not exempt. Urdu `۵۰ فیصد` and printed `50%` are also normalized to the same numerical value. Neither change assigns a factual-accuracy grade.

Completed, malformed and cancelled responses close their nested streams and release model admission capacity. Validation errors retain trace IDs. Diagnostic prompts are privacy-redacted. The interpreted programme reaches degree-specific tools while fee/service topic switches discard curriculum cohort filters.

For requests consisting entirely of university facts, zero eligible evidence now produces an explicit tool-gap message instead of model-generated factual prose. Diagnostics record that generation was skipped, with no claimed generator input. The final six-case replay completed in 5.0 s median / 9.7 s p95 with only interpretation calls, and the real CGPA clarification follow-up stopped inventing a repeat policy. This is a missing-tool boundary; answers with evidence still use the language model. Mixed and partially supported answers still need semantic review.

## Failures still blocking release

The full run still omitted whole-scheme lists, omitted a relevant NLP researcher, produced poor or wrong-script Roman Urdu, failed parts of mixed questions and overstated admissions evidence. One prerequisite replay invented `CSC-103` inside an uncited limitation; the subsequent identifier guard blocks that specific failure class, without proving all unsupported prerequisite wording detectable.

Real follow-ups also omitted semester courses and added unsupported elective commentary. The independent reviewer must assess every assertion, applicability, completeness, language, usefulness and actual citation support. Urdu eligibility wording still garbles qualification names even after percentage normalization. No self-assigned factual-accuracy percentage is reported.

## Models, acquisition and preservation

The measured machine is an Apple M1 Max with 64 GiB unified memory and Ollama 0.35.1. Only `qwen3:8b` among the three requested generator candidates is installed. One bounded 600-second attempt per Qwen 3.5 candidate ended with incomplete downloads of only a few percent. Partial downloads and logs remain resumable. No further unbounded retry or inferred larger-model winner was substituted for measurement.

[Current generator probes](../.runtime/chatbot-v3/evaluation/recovery-generation-benchmark-current.json) retain real outputs and failures. Unavailable candidates have null quality/latency. These probes supplement the actual API conversations; they do not certify grounded answers. Cached E5 and the multilingual MiniLM reranker load offline; the Qwen 0.6B encoder/reranker do not. Their comparison on independently reviewed retrieval cases remains unmeasured.

The bounded official crawl visited 18 URLs, discovered 150, parsed five, recorded ten failures and three missing pages, and retained 142 pending URLs. Its last request extended the nominal 300 seconds to about 305 seconds. The frontier now persists and supports `--resume`. New acquisitions remain staging data. This is partial university coverage.

The recovery backup is `.runtime/backups/chatbot-v3-recovery-20261011-195728/`; the earlier verified archive and PostgreSQL restore drill remain intact. All 425 original input assets retain their checksums. The inventory now also contains two replacement source files; the retained all-entry comparison separately records the authorized review-template edit instead of treating that code as an original university asset.

The workbench records language/helpfulness judgments and binds human grades to the exact paired-answer digest. Changed answers cannot inherit old grades. Checked source URLs for retrieval evaluation are separate from AI suggestions. Academic-source approval and benchmark-answer approval remain distinct.

The latest engineering checks passed forty-one backend checks and two frontend stream checks. The corrected Chromium run passed both tests, including the original course-list assertion, real captured-source retrieval, cancellation and mobile layout. The two earlier failed browser runs and their captured trace remain retained. The three-request capacity check returned 200/200/503 in 5.28 s / 10.33 s / 10 ms; a disconnected generation incremented cancellation, released the queue, and allowed the next request to finish. A separate temporary API with a genuinely missing local model returned HTTP 503 with `Retry-After: 5`, without an invented answer or stopping the user's Ollama service. These results validate runtime behavior, not student answer correctness. The final percentage normalization and no-evidence boundary were checked with focused live HTTP replays after that browser run.

The release gate remains false. Independently reviewed factual accuracy, citation support, completeness, abstention, language and helpfulness remain unmeasured. No cutover or retirement should be proposed until the remaining factual failures, model comparison, human review and deployment checks are complete.
