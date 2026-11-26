---
status: proposed
date: 2026-11-26
decision-makers: Nick Christoforakis
---

# Generate six chronic conditions and five drug–lab interactions

<!-- Drafted by the assistant from the owner's decision. Stays "proposed" until the owner has rewritten it in their own words. -->

## Context and Problem Statement

The generator must produce clinically plausible data, and the app and the prediction model need drug–lab interactions with a known true rate. Which conditions and interactions should the data contain, and how should the prediction model define a drug start and handle a missing follow-up potassium?

## Decision Drivers

* The conditions should share labs, so interactions arise from overlapping care rather than isolated rules.
* The interactions should cover different kinds of drug–lab problem, so the app shows variety.
* The prediction model needs enough starts and events (at least 100 events in training).
* Each rule must be testable against a configured rate.

## Considered Options

* (a) Six conditions (type 2 diabetes, hypertension, CKD, heart failure, atrial fibrillation, hyperlipidaemia) and five interactions
* (b) The four cardio-renal-metabolic conditions only, with three interactions
* (c) A changed list

## Decision Outcome

Chosen option: **(a)**, because the six conditions overlap the way they do in real patients, share potassium and creatinine, and give five kinds of drug–lab problem: high potassium, low potassium, kidney dosing, anticoagulation and liver.

Also decided:

* **Drug start:** an order with no order of the same class in the 180 days before. Chosen over 365 days to keep more starts for the model.
* **No potassium in the 30 days after a start:** the start is left out and counted. Chosen over "treat as normal", which would undercount events, and over "always measure", which is unrealistic. The generator plants follow-up testing at a configured rate below 100%.

### Consequences

* Good, because the app's interaction view and the model both have the data they need.
* Good, because the missing-follow-up rule teaches that missing data is not the same as normal.
* Bad, because there are more rules to write and test than with (b).

### Confirmation

* The planted-rate tests: each interaction's rate in the marts is within tolerance of its configured rate.
* The prediction model's results report the number of starts left out for a missing potassium.

## Pros and Cons of the Options

### (a) Six conditions, five interactions

* Good, because of the variety and realistic overlap.
* Bad, because of the extra work in weeks 2 and 5.

### (b) Four conditions, three interactions

* Good, because it is a tighter story and less work, and the model is unaffected.
* Bad, because all interactions are about potassium or the kidney.

### (c) A changed list

* Good, because it could use the owner's own clinical strengths.
* Bad, because new conditions must share labs with the others, or they become islands in the data.
