# M2 — Semantic calibration results

Model: `sentence-transformers/all-MiniLM-L6-v2` (local, normalized embeddings, cosine similarity).
Thresholds under test (provisional): L = 0.30, U = 0.60.
Dataset: `calibration/semantic_pairs.json` (fictional). Regenerate with `python -m scripts.calibrate_semantic`.

Verdict rules: *strong* pairs should be strong (partial = borderline); *partial* pairs should be partial;
*unrelated* pairs should be none (partial = borderline); *related_different* and *keyword_trap* pairs must
not be strong.

## Per-pair results

| ID | Category | Expected | Requirement | Evidence | Cosine | Score | Result | Verdict |
|---|---|---|---|---|--:|--:|---|---|
| S1 | strong | strong | Previous e-commerce experience | We have developed six online retail platforms for European customers. | 0.504 | 0.68 | partial | borderline |
| S2 | strong | strong | Payment integration experience | We integrated Stripe, PayPal and Adyen into several online stores. | 0.507 | 0.69 | partial | borderline |
| S3 | strong | strong | Experience building mobile apps for iOS and Android | Our team has shipped more than twenty cross-platform smartphone applications to the App Store and Google Play. | 0.569 | 0.90 | partial | borderline |
| S4 | strong | strong | Experience with GDPR-compliant handling of personal data | All our projects follow EU data protection rules for storing and processing customer information. | 0.449 | 0.50 | partial | borderline |
| S5 | strong | strong | Automated testing and continuous integration | Every project runs automated unit and integration tests in a CI pipeline on each commit. | 0.660 | 1.00 | strong | ok |
| S6 | strong | strong | Post-launch maintenance and support | After go-live we provide twelve months of bug fixing, updates and technical support. | 0.499 | 0.66 | partial | borderline |
| S7 | strong | strong | Agile development with regular sprint demos | We work in two-week Scrum iterations and present the progress to the client at the end of each one. | 0.470 | 0.57 | partial | borderline |
| S8 | strong | strong | Accessibility compliance for users with disabilities | Our interfaces are audited against WCAG 2.1 AA so that people using screen readers can use them. | 0.378 | 0.26 | partial | borderline |
| S9 | strong | strong | Experience with warehouse and inventory management systems | We built stock tracking software for the distribution centres of a logistics company. | 0.543 | 0.81 | partial | borderline |
| P1 | partial | partial | Previous e-commerce experience | We built a booking platform for a hotel chain that accepts online payments. | 0.339 | 0.13 | partial | ok |
| P2 | partial | partial | Payment integration experience | Our apps handle user subscriptions and invoicing. | 0.401 | 0.34 | partial | ok |
| P3 | partial | partial | Experience with GDPR-compliant handling of personal data | We take security seriously and encrypt all data at rest. | 0.308 | 0.03 | partial | ok |
| P4 | partial | partial | Post-launch maintenance and support | We offer a 30-day warranty period after delivery. | 0.275 | 0.00 | none | borderline |
| P5 | partial | partial | Experience building mobile apps for iOS and Android | We developed a responsive web application that works well on smartphones. | 0.534 | 0.78 | partial | ok |
| P6 | partial | partial | Automated testing and continuous integration | Our QA engineers manually test every release before deployment. | 0.506 | 0.69 | partial | ok |
| P7 | partial | partial | Agile development with regular sprint demos | We send the client a weekly progress report by email. | 0.147 | 0.00 | none | borderline |
| U1 | unrelated | none | Previous e-commerce experience | Our office is located in a renovated factory building near the river. | 0.108 | 0.00 | none | ok |
| U2 | unrelated | none | Payment integration experience | The team enjoys hiking trips together every summer. | -0.035 | 0.00 | none | ok |
| U3 | unrelated | none | Accessibility compliance for users with disabilities | We developed firmware for industrial temperature sensors. | 0.016 | 0.00 | none | ok |
| U4 | unrelated | none | Post-launch maintenance and support | Our designers created the logo for a local bakery. | 0.034 | 0.00 | none | ok |
| U5 | unrelated | none | Experience with warehouse and inventory management systems | We recently won an award for our corporate photography. | 0.090 | 0.00 | none | ok |
| R1 | related_different | not strong | Payment integration experience | We built the product catalogue and search function for an online store. | 0.149 | 0.00 | none | ok |
| R2 | related_different | not strong | Previous e-commerce experience | We have built several mobile banking apps. | 0.285 | 0.00 | none | ok |
| R3 | related_different | not strong | Experience building mobile apps for iOS and Android | We develop backend REST APIs that are consumed by other services. | 0.197 | 0.00 | none | ok |
| R4 | related_different | not strong | Automated testing and continuous integration | We deploy applications to Kubernetes clusters on Google Cloud. | 0.184 | 0.00 | none | ok |
| R5 | related_different | not strong | Experience with GDPR-compliant handling of personal data | We have built analytics dashboards for marketing teams. | 0.200 | 0.00 | none | ok |
| R6 | related_different | not strong | Accessibility compliance for users with disabilities | We create pixel-perfect, visually striking user interfaces. | 0.173 | 0.00 | none | ok |
| K1 | keyword_trap | not strong | Previous e-commerce experience | We have no previous e-commerce experience, but we are eager to learn. | 0.690 | 1.00 | strong | wrong |
| K2 | keyword_trap | not strong | Payment integration experience | Payment for our services is due within 30 days of each invoice. | 0.406 | 0.35 | partial | ok |
| K3 | keyword_trap | not strong | Experience building mobile apps for iOS and Android | Our team members use iOS and Android phones to stay in touch with clients. | 0.570 | 0.90 | partial | ok |
| K4 | keyword_trap | not strong | Automated testing and continuous integration | The continuous integration of new employees into our culture matters, and we test every candidate carefully. | 0.478 | 0.59 | partial | ok |
| K5 | keyword_trap | not strong | Post-launch maintenance and support | We support local football clubs and sponsored the launch of a charity run. | 0.274 | 0.00 | none | ok |
| K6 | keyword_trap | not strong | Experience with warehouse and inventory management systems | Our warehouse-style office keeps an inventory of standing desks. | 0.474 | 0.58 | partial | ok |

## Per-category similarity

| Category | n | min | mean | max |
|---|--:|--:|--:|--:|
| strong | 9 | 0.378 | 0.509 | 0.660 |
| partial | 7 | 0.147 | 0.359 | 0.534 |
| unrelated | 5 | -0.035 | 0.043 | 0.108 |
| related_different | 6 | 0.149 | 0.198 | 0.285 |
| keyword_trap | 6 | 0.274 | 0.482 | 0.690 |

**Current thresholds:** 22 ok, 10 borderline, 1 wrong out of 33 pairs.

## Sensitivity (context only — thresholds were not tuned)

| L | U | ok | borderline | wrong |
|--:|--:|--:|--:|--:|
| 0.20 | 0.50 | 24 | 7 | 2 |
| 0.20 | 0.55 | 23 | 8 | 2 |
| 0.20 | 0.60 | 23 | 9 | 1 |
| 0.20 | 0.65 | 23 | 9 | 1 |
| 0.25 | 0.50 | 24 | 7 | 2 |
| 0.25 | 0.55 | 23 | 8 | 2 |
| 0.25 | 0.60 | 23 | 9 | 1 |
| 0.25 | 0.65 | 23 | 9 | 1 |
| 0.30 | 0.50 | 23 | 8 | 2 |
| 0.30 | 0.55 | 22 | 9 | 2 |
| 0.30 | 0.60 | 22 | 10 | 1 ← current |
| 0.30 | 0.65 | 22 | 10 | 1 |
| 0.35 | 0.50 | 21 | 10 | 2 |
| 0.35 | 0.55 | 20 | 11 | 2 |
| 0.35 | 0.60 | 20 | 12 | 1 |
| 0.35 | 0.65 | 20 | 12 | 1 |
