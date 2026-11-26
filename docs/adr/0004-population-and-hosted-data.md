---
status: proposed
date: 2026-11-26
decision-makers: Nick Christoforakis
---

# Generate 25,000 Dutch-locale patients over ten years, and host only the public layer

<!-- Drafted by the assistant from the owner's decision. Stays "proposed" until the owner has rewritten it in their own words. -->

## Context and Problem Statement

The generator needs a default population size, a Faker locale and a history window. The prediction model needs at least 100 hyperkalaemia events in its training set, and every drug start needs 180 days with no order and 365 days of baseline labs before it. The hosted app needs a hosted database, on a free tier. How large should the population be, where does it "live", over which years, and what goes to the hosted database?

## Decision Drivers

* Enough events for the model.
* Generation, load and build fast enough to run often, locally and in CI.
* Names, addresses and regions that fit an EU GDPR story.
* The hosted database should hold no more than the hosted app needs.

## Considered Options

* Size: (a) 5,000, (b) 25,000, (c) 100,000 patients
* Locale: one EU locale, `en_GB`, or a mix
* History: 10 years or 5 years
* Hosted database: everything, or `marts_public` only

## Decision Outcome

Chosen: **25,000 patients, locale `nl_NL`, history 2016-01-01 to 2025-12-31 with starts counted from 2017-01-01, and only `marts_public` in the hosted database**, because:

* A rough estimate (rates to be checked against sources) gives about 30 events for 5,000 patients and about 150 for 25,000, so about 100 in training.
* `nl_NL` is an EU locale, so the EU GDPR applies; `en_GB` would fall under the UK GDPR. One locale keeps one consistent list of regions. Faker's national ID generators stay unused.
* Ten years give more starts than five, and starting the count in 2017 leaves a full year of history before each start.
* The hosted app reads only `marts_public`, so keeping anything else on the hosted database would be data with no purpose (data minimisation, GDPR Art. 5(1)(c)).

### Consequences

* Good, because the model has enough events, if the estimate holds.
* Good, because the hosted database holds only suppressed aggregates: there is nothing more there to leak, and it stays far below free-tier storage limits.
* Bad, because 25,000 patients over ten years is an estimated few million rows, so CI may need a smaller population if the full run is slow there.
* Bad, because a publish script and its test are needed.

### Confirmation

* After the first generation, the number of hyperkalaemia events is counted; the population is raised if fewer than 100 fall in training.
* After publishing, a test lists every schema and table in the hosted database and fails if anything other than `marts_public` is there.

## Pros and Cons of the Options

### (a) 5,000 patients

* Good, because it is the fastest to generate and test.
* Bad, because the model would have about 30 events.

### (b) 25,000 patients

* Good, because it meets the event minimum under the estimate, and runs comfortably on a laptop.
* Bad, because CI may need a smaller size.

### (c) 100,000 patients

* Good, because it gives plenty of events and real performance practice.
* Bad, because it is slower everywhere.

### Everything in the hosted database

* Good, because there is no publish step.
* Bad, because the hosted database would hold identifiers and per-patient rows that the hosted app never reads.
