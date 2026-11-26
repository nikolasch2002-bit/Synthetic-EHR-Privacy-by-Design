---
status: accepted
date: 2026-11-26
decision-makers: Nick Christoforakis
---

# Build the app in Streamlit, with a public hosted mode and a local mode

<!-- Drafted by the assistant from the owner's decision; reviewed and accepted by the owner, 2026-11-26. -->

## Context and Problem Statement

The app must show cohorts, a patient visit timeline, drug–lab interactions and the prediction model's performance, and demonstrate that different roles see different data. It must also be reachable at a public URL. But the spec allows the public app only aggregates after small-cell suppression, so a public role switcher or patient timeline would break the project's own rule. Which framework, and how do the role demonstration and the public rule fit together?

## Decision Drivers

* The public deployment must be unable to show anything but suppressed aggregates, by construction rather than by care.
* The role demonstration must still be visible to a reviewer.
* Free hosting, and as little extra work as possible.

## Considered Options

* (a) Streamlit
* (b) FastAPI with token-scoped roles, plus a small front end
* (c) Both: FastAPI for the data, Streamlit as the front end

And for the role demonstration:

* A hosted/local split: hosted mode holds only the `public_app` login; the role switcher and timeline run locally
* A "showcase" exception: a few pseudonymous patients' timelines made public, recorded in the DPIA

## Decision Outcome

Chosen option: **(a) Streamlit, with the hosted/local split**, because it is one Python app with free hosting, and the hosted app cannot show more than `marts_public` even with a bug: it has no credentials that could read more.

### Consequences

* Good, because the public rule is enforced by what the hosted app is given, not by what its code chooses to show.
* Good, because local mode shows the full role demonstration, and the README records it.
* Bad, because reviewers who only click the public link do not see the role switcher; they see it in the README's screenshots and recording.
* Bad, because Streamlit shows less backend structure than an API would.

### Confirmation

* A test runs the app in hosted mode and checks that no role switcher or timeline appears.
* The role test checks that `public_app` can read only `marts_public`.

## Pros and Cons of the Options

### (a) Streamlit

* Good, because filters, charts and the timeline are quick to build in Python.
* Good, because Streamlit Community Cloud hosts it free (it sleeps after a while without visitors).
* Bad, because it is an app framework, not an API.

### (b) FastAPI with token-scoped roles

* Good, because it shows backend engineering and API access control.
* Bad, because it about doubles the work, needs a front end, and needs a server host whose free tiers usually sleep or have limits.

### (c) Both

* Good, because it is the most complete architecture.
* Bad, because it is the most work, likely adding a week or more.

### Showcase exception (instead of the split)

* Good, because recruiters could click through a timeline online.
* Bad, because it weakens the project's main claim that the public sees only suppressed aggregates.
