# Standards and guidance reference

**Important:** this repository uses these standards as process-design references. It does not claim
certification or full conformance. The project owner and organization must select applicable
requirements, risk levels, tailoring, evidence, and approval responsibilities for each target
project. Standards may be copyrighted; this file summarizes their purpose and links to official
publisher or steward pages rather than reproducing their text.

| Reference | How this framework uses it |
|---|---|
| ISO/IEC/IEEE 12207:2026 — Software life cycle processes | Overall lifecycle vocabulary and process structure across development, operation, maintenance and retirement. |
| ISO/IEC/IEEE 29148:2018 — Requirements engineering | Requirements elicitation, analysis, traceability, and requirements work products. Re-check its status before each major framework release. |
| ISO/IEC/IEEE 29119-1:2022 — Software testing concepts | Shared testing terminology and concepts. |
| ISO/IEC/IEEE 29119-2:2021 — Test processes | Test planning, monitoring, design/implementation, execution and completion process guidance. |
| ISO/IEC/IEEE 29119-3:2021 — Test documentation | Test plan, test case, test procedure, incident/defect and completion-report structures. |
| NIST SP 800-218 SSDF v1.1 (final) | Secure development practices integrated into planning, coding, review, build, release and vulnerability handling. |
| NIST SP 800-218 Rev. 1 / SSDF v1.2 (initial public draft, Dec 2025) | Monitor for updates; do not treat a draft as the final normative baseline. |
| OWASP ASVS 5.0.0 | Security verification requirements for web applications and services, selected according to application risk. |

## Tailoring rules

1. The BA/PO define business requirements and acceptance criteria; the architect records design decisions
   and technical constraints.
2. QA defines a risk-based test strategy and maps tests to requirement IDs and acceptance criteria.
3. Developers apply secure coding, dependency, secrets, review, and build-integrity controls.
4. The release approver reviews test evidence, known defects, exceptions, security findings, and rollback readiness.
5. The Scrum Master reports actual work and test evidence, not unsupported claims or model-generated status.

## Official references checked for this bootstrap (6 Nov 2026)

- [ISO/IEC/IEEE 12207:2026](https://www.iso.org/standard/90219.html) — published April 2026; replaces the 2017 edition.
- [ISO/IEC/IEEE 29148:2018](https://www.iso.org/standard/72089.html) — requirements engineering reference; ISO page states it was confirmed in 2024 and remains current, while a replacement is expected.
- [IEEE / ISO/IEC/IEEE 29119-2:2021](https://standards.ieee.org/ieee/29119-2/7498/) — active standard describing software testing processes.
- [IEEE / ISO/IEC/IEEE 29119-3:2021](https://standards.ieee.org/ieee/29119-3/7499/) — test documentation templates.
- [NIST SSDF publications](https://csrc.nist.gov/projects/ssdf/publications) — at the time checked, SP 800-218 v1.1 is final and Rev. 1 / v1.2 is listed as an initial public draft dated 17 December 2025.
- [OWASP ASVS 5.0.0](https://asvs.owasp.org/) — stable release published 30 May 2025.

This reference list must be reviewed periodically. The exact version and applicability should be
confirmed before describing a client project as aligned to a standard.
