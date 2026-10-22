# CheckSense Annotation Guidelines & Labeling Contract

**Version:** 1.0  
**Status:** Canonical Reference for Human Annotation (Phase 3)  
**Specification Reference:** [docs/MASTER_SPEC.md](MASTER_SPEC.md) Section 2 & 4  
**Binding Governance:** [AGENTS.md](../AGENTS.md)

---

## 1. Core Principles & Governance Rules

1. **Rule 0 (Context Awareness):** Do not flag information as incomplete or ambiguous if that information is explicitly defined elsewhere in the same Software Requirements Specification (SRS) or system context.
2. **Human Authority:** AI and rule-generated suggestions are strictly drafts (`label_status='draft'`). A requirement or gap only achieves `label_status='verified'` when an authorized human annotator reviews, edits, and confirms it.
3. **Real Data Integrity:** Annotate only authentic requirements sampled from the PURE corpus. Never fabricate example requirements or synthesize mock data.
4. **Clean Requirements:** If a requirement is clear, verifiable, and complete, mark `has_gap=0` and `label_status='verified'`. Clean requirements are vital negative training examples.
5. **Exact Spans:** For `ambiguity` and `incompleteness`, the `span_text` must be an exact verbatim substring within the requirement text. For `implicit` gaps, the scope is the entire requirement.

---

## 2. Severity Rating Contract

Every identified defect must be assigned an ordinal severity level from 1 to 3:

| Severity | Tier Name | Criteria | Practical Impact |
|:---:|:---|:---|:---|
| **3** | **Critical Defect** | The requirement will likely cause developers to build the **wrong behavior**, create a **security vulnerability**, compromise **safety**, or violate **legal/compliance** constraints. | Production failure, data breach, safety hazard, major architectural rework. |
| **2** | **Moderate Defect** | The requirement is ambiguous or missing edge-case handling, leading to **differing developer interpretations** or likely rework during integration and acceptance testing. | Sprint rework, delayed feature delivery, conflicting test assertions. |
| **1** | **Minor Defect** | Minor stylistic ambiguity, harmless unattributed passive voice where the actor is obvious from context, or non-critical cosmetic phrasing. | Low friction, easily resolved in code review or backlog grooming. |

---

## 3. Gap Taxonomy: Definitions & Benchmark Examples

### 3.1 Class: Ambiguity
Ambiguity occurs when a requirement can be legitimately interpreted in multiple distinct ways by developers, testers, or stakeholders.

---

#### Subtype 1: `vague_term`
Subjective adjectives or adverbs that lack quantifiable, measurable acceptance criteria.

* **Positive Example 1:**
  * **Requirement:** *"The user interface shall be user-friendly and intuitive to operate."*
  * **Span:** `user-friendly and intuitive`
  * **Severity:** 2 (Moderate: different developers will implement drastically differing designs)
  * **Explanation:** Terms like 'user-friendly' and 'intuitive' are subjective and cannot be objectively verified by a test case.
  * **Question:** *"What specific usability metric, such as maximum task completion time or SUS score, defines usability acceptance?"*
  * **Stakeholder Answer:** *"First-time operators shall complete the primary checkout flow in under 90 seconds without assistance."*
  * **Refined Text:** *"First-time operators shall complete the primary checkout flow in under 90 seconds without assistance."*

* **Positive Example 2:**
  * **Requirement:** *"The notification service shall process outbound push alerts rapidly."*
  * **Span:** `rapidly`
  * **Severity:** 2 (Moderate: latency expectations undefined)
  * **Explanation:** 'Rapidly' is an unquantified adjective providing no latency threshold.
  * **Question:** *"What is the maximum allowable latency between alert generation and transmission?"*
  * **Stakeholder Answer:** *"Push alerts must be dispatched within 500 milliseconds of generation."*
  * **Refined Text:** *"The notification service shall dispatch outbound push alerts within 500 milliseconds of event generation."*

* **Negative Example 1 (Clean):**
  * **Requirement:** *"The database query engine shall return search results within 250 milliseconds under a 500 concurrent query load."*
  * **Why Clean:** Specific quantitative bound (`250 milliseconds`) under explicit operating load.

* **Negative Example 2 (Clean):**
  * **Requirement:** *"The web application shall conform to WCAG 2.1 Level AA accessibility guidelines."*
  * **Why Clean:** While 'accessible' alone is vague, referencing an explicit, testable industry standard (`WCAG 2.1 AA`) provides objective pass/fail criteria.

---

#### Subtype 2: `vague_quantifier`
Indefinite quantifiers, open-ended lists, or unbounded scopes (e.g., `several`, `some`, `etc.`, `and so on`).

* **Positive Example 1:**
  * **Requirement:** *"The storage manager shall preserve several backup copies of the configuration registry."*
  * **Span:** `several`
  * **Severity:** 2 (Moderate: backup redundancy number is unknown to infrastructure teams)
  * **Explanation:** 'Several' is indefinite, leaving the required number of backups unspecified.
  * **Question:** *"Exactly how many redundant backup copies of the configuration registry shall be preserved?"*
  * **Stakeholder Answer:** *"At least three redundant copies across two separate availability zones."*
  * **Refined Text:** *"The storage manager shall preserve at least three redundant backup copies of the configuration registry across two separate availability zones."*

* **Positive Example 2:**
  * **Requirement:** *"The audit log viewer shall display system warnings, connection drops, etc."*
  * **Span:** `etc.`
  * **Severity:** 2 (Moderate: open-ended list risks missing critical audit events)
  * **Explanation:** 'Etc.' introduces an unbounded enumeration, leaving the complete set of log events undefined.
  * **Question:** *"What complete set of security and system events shall the audit log viewer display?"*
  * **Stakeholder Answer:** *"It must display system warnings, connection drops, authentication failures, and privilege escalations."*
  * **Refined Text:** *"The audit log viewer shall display system warnings, connection drops, authentication failures, and privilege escalations."*

* **Negative Example 1 (Clean):**
  * **Requirement:** *"The cluster controller shall maintain a minimum of 3 and a maximum of 12 active worker nodes."*
  * **Why Clean:** Explicit integer minimum and maximum bounds.

* **Negative Example 2 (Clean):**
  * **Requirement:** *"The report generator shall export data in exactly one of the following formats: CSV, PDF, or XLSX."*
  * **Why Clean:** Closed, exhaustive enumeration without open-ended catch-alls.

---

#### Subtype 3: `anaphora`
Pronouns (e.g., `it`, `they`, `them`, `their`) whose antecedent reference is ambiguous or grammatically dangling.

* **Positive Example 1:**
  * **Requirement:** *"When the client issues a command to the proxy and it fails, it shall log the error code."*
  * **Span:** `it`
  * **Severity:** 2 (Moderate: unclear whether the client, proxy, or command failed, and who logs)
  * **Explanation:** The pronoun 'it' appears twice with ambiguous antecedents across client, proxy, and command.
  * **Question:** *"If the command fails, which component shall log the error code: the client or the proxy?"*
  * **Stakeholder Answer:** *"The proxy shall log the error code when command execution fails."*
  * **Refined Text:** *"When the client issues a command to the proxy and the command execution fails, the proxy shall log the error code."*

* **Positive Example 2:**
  * **Requirement:** *"The security monitors shall notify the site supervisors if they detect an unauthorized perimeter breach."*
  * **Span:** `they`
  * **Severity:** 1 (Minor: semantic context suggests the monitors detect, but phrasing is grammatically ambiguous)
  * **Explanation:** 'They' can grammatically refer to either monitors or supervisors.
  * **Question:** *"Does 'they' refer to the security monitors detecting the breach or the supervisors?"*
  * **Stakeholder Answer:** *"The security monitors detect the breach."*
  * **Refined Text:** *"The security monitors shall notify the site supervisors upon detecting an unauthorized perimeter breach."*

* **Negative Example 1 (Clean):**
  * **Requirement:** *"When the primary database fails, the replica database shall promote itself to primary within 5 seconds."*
  * **Why Clean:** Repeated, explicit noun phrases (`replica database`) prevent dangling reference.

* **Negative Example 2 (Clean):**
  * **Requirement:** *"If sensor temperature exceeds 100°C, the cooling fan shall run at maximum RPM."*
  * **Why Clean:** No ambiguous pronouns; subject and predicate are explicitly aligned.

---

#### Subtype 4: `coordination`
Ambiguous logical branching caused by unclear precedence of `and` / `or` connectives.

* **Positive Example 1:**
  * **Requirement:** *"The access gateway shall grant entry to users possessing a security badge and fingerprint scan or PIN code."*
  * **Span:** `and fingerprint scan or PIN code`
  * **Severity:** 3 (Critical: ambiguous security logic: `(Badge AND Fingerprint) OR PIN` vs `Badge AND (Fingerprint OR PIN)`)
  * **Explanation:** Unclear Boolean operator precedence creates a serious access control loophole.
  * **Question:** *"Does entry require a badge combined with either a fingerprint or PIN, or is a PIN alone sufficient?"*
  * **Stakeholder Answer:** *"A badge is always mandatory, accompanied by either a fingerprint scan or a PIN."*
  * **Refined Text:** *"The access gateway shall grant entry to users possessing a security badge accompanied by either a fingerprint scan or a PIN code."*

* **Positive Example 2:**
  * **Requirement:** *"The operator shall approve and archive or reject pending applications."*
  * **Span:** `and archive or reject`
  * **Severity:** 2 (Moderate: unclear whether rejection also requires archiving)
  * **Explanation:** Coordination ambiguity leaves the workflow for rejected applications unspecified.
  * **Question:** *"Shall rejected applications also be archived, or are only approved applications archived?"*
  * **Stakeholder Answer:** *"Approved applications are archived; rejected applications are marked rejected without archiving."*
  * **Refined Text:** *"The operator shall either approve and archive the pending application, or reject the pending application."*

* **Negative Example 1 (Clean):**
  * **Requirement:** *"The system shall require two-factor authentication consisting of a password combined with either an SMS OTP or an authenticator app token."*
  * **Why Clean:** Explicit grouping (`consisting of X combined with either Y or Z`) removes Boolean precedence ambiguity.

* **Negative Example 2 (Clean):**
  * **Requirement:** *"The admin may edit the profile, or the admin may delete the profile."*
  * **Why Clean:** Explicit separate clauses disambiguate disjoint alternatives.

---

### 3.2 Class: Incompleteness
Incompleteness occurs when mandatory functional elements—such as actors, preconditions, numeric boundaries, or failure handling—are omitted.

---

#### Subtype 5: `missing_actor`
Passive voice or impersonal statements where the responsible human role, system component, or external service is unstated.

* **Positive Example 1:**
  * **Requirement:** *"The customer session cryptographic keys shall be rotated every 24 hours."*
  * **Span:** `shall be rotated`
  * **Severity:** 2 (Moderate: architectural uncertainty as to which component owns key rotation)
  * **Explanation:** Passive voice omits the agent responsible for rotating keys.
  * **Question:** *"Which subsystem or service shall rotate the customer session cryptographic keys?"*
  * **Stakeholder Answer:** *"The Key Management Daemon (KMD) shall rotate session keys."*
  * **Refined Text:** *"The Key Management Daemon shall rotate customer session cryptographic keys every 24 hours."*

* **Positive Example 2:**
  * **Requirement:** *"Payment transaction logs shall be transmitted to the compliance vault at the end of each business day."*
  * **Span:** `shall be transmitted`
  * **Severity:** 2 (Moderate: responsible service omitted)
  * **Explanation:** The transmission agent is missing.
  * **Question:** *"What component shall transmit the payment transaction logs to the compliance vault?"*
  * **Stakeholder Answer:** *"The settlement processor service shall transmit transaction logs."*
  * **Refined Text:** *"The settlement processor service shall transmit payment transaction logs to the compliance vault at the end of each business day."*

* **Negative Example 1 (Clean):**
  * **Requirement:** *"The telemetry agent shall upload sensor readings to the cloud endpoint every 60 seconds."*
  * **Why Clean:** Explicit subject/actor (`The telemetry agent`).

* **Negative Example 2 (Clean):**
  * **Requirement:** *"Sensor readings shall be received by the telemetry agent over serial port COM1."*
  * **Why Clean:** Passive construction contains an explicit prepositional agent (`by the telemetry agent`).

---

#### Subtype 6: `missing_condition`
State-altering or critical actions lacking necessary triggering preconditions, or containing discretionary loophole clauses (e.g., `if applicable`, `as appropriate`).

* **Positive Example 1:**
  * **Requirement:** *"The document management system shall purge archived client records as appropriate."*
  * **Span:** `as appropriate`
  * **Severity:** 3 (Critical: discretionary phrase risks accidental deletion or non-compliance)
  * **Explanation:** 'As appropriate' introduces an unguided loophole without legal or operational retention conditions.
  * **Question:** *"Under what specific retention schedule or approval conditions shall archived client records be purged?"*
  * **Stakeholder Answer:** *"Records shall be purged only after 7 years from account closure upon legal compliance sign-off."*
  * **Refined Text:** *"The document management system shall purge archived client records after 7 years from account closure upon receipt of compliance authorization."*

* **Positive Example 2:**
  * **Requirement:** *"The cooling system shall switch to emergency auxiliary power."*
  * **Span:** `shall switch`
  * **Severity:** 3 (Critical: missing triggering criteria for emergency mode)
  * **Explanation:** The requirement mandates an emergency mode transition without defining the triggering condition.
  * **Question:** *"Under what condition shall the cooling system switch to emergency auxiliary power?"*
  * **Stakeholder Answer:** *"When primary grid voltage drops below 190V for more than 500 milliseconds."*
  * **Refined Text:** *"When primary grid voltage drops below 190V for more than 500 milliseconds, the cooling system shall switch to emergency auxiliary power."*

* **Negative Example 1 (Clean):**
  * **Requirement:** *"When the ambient light sensor detects less than 10 lux for 3 consecutive seconds, the headlights shall turn on."*
  * **Why Clean:** Explicit, quantifiable condition clause (`When the ambient light sensor...`).

* **Negative Example 2 (Clean):**
  * **Requirement:** *"Upon receiving a signed cancellation request from the policyholder, the insurer shall terminate the coverage."*
  * **Why Clean:** Explicit precondition and triggering event.

---

#### Subtype 7: `missing_threshold`
Qualitative descriptions modifying performance, capacity, or resource metrics without numeric bounds or units.

* **Positive Example 1:**
  * **Requirement:** *"The streaming server shall maintain low latency during peak traffic periods."*
  * **Span:** `low latency`
  * **Severity:** 2 (Moderate: engineering teams cannot verify compliance)
  * **Explanation:** 'Low latency' describes a quantitative performance metric without an upper numerical bound or unit.
  * **Question:** *"What is the maximum acceptable latency in milliseconds during peak traffic periods?"*
  * **Stakeholder Answer:** *"Latency must not exceed 200 ms for 99% of requests."*
  * **Refined Text:** *"The streaming server shall maintain latency below 200 milliseconds for 99% of requests during peak traffic periods."*

* **Positive Example 2:**
  * **Requirement:** *"The emergency braking actuator shall apply high pressure when an obstacle is detected."*
  * **Span:** `high pressure`
  * **Severity:** 3 (Critical: safety subsystem requires exact hydraulic pressure specifications)
  * **Explanation:** 'High pressure' is qualitative in a safety-critical mechanical system.
  * **Question:** *"What minimum hydraulic braking pressure in bars or psi shall the actuator apply?"*
  * **Stakeholder Answer:** *"At least 120 bars of hydraulic pressure within 100 milliseconds."*
  * **Refined Text:** *"The emergency braking actuator shall apply a minimum of 120 bars of hydraulic pressure within 100 milliseconds when an obstacle is detected."*

* **Negative Example 1 (Clean):**
  * **Requirement:** *"The database engine shall maintain CPU utilization below 75% under standard workload."*
  * **Why Clean:** Quantitative threshold (`75%`) with measurable metric (`CPU utilization`).

* **Negative Example 2 (Clean):**
  * **Requirement:** *"The backup battery shall supply at least 1500 Watts for a minimum duration of 30 minutes."*
  * **Why Clean:** Fully specified physical thresholds with standard engineering units (`Watts`, `minutes`).

---

#### Subtype 8: `missing_error_handling`
High-risk, state-altering, or network operations lacking fallback, recovery, retry, or exception behavior.

* **Positive Example 1:**
  * **Requirement:** *"The checkout service shall charge the customer's payment card for the order total."*
  * **Span:** `shall charge`
  * **Severity:** 3 (Critical: payment failure paths unhandled, leading to lost revenue or duplicate charges)
  * **Explanation:** The requirement describes the happy path but omits behavior when the charge is declined or times out.
  * **Question:** *"What action shall the checkout service take if the payment card charge is declined or the gateway times out?"*
  * **Stakeholder Answer:** *"If declined, display the specific reason and hold the order in pending status for 15 minutes."*
  * **Refined Text:** *"The checkout service shall charge the customer's payment card for the order total; if the charge is declined or times out, the service shall display an error to the user and hold the order in pending status for 15 minutes."*

* **Positive Example 2:**
  * **Requirement:** *"The synchronizer shall write updated client profiles to the central remote database."*
  * **Span:** `shall write`
  * **Severity:** 2 (Moderate: network disconnect behavior unhandled)
  * **Explanation:** Omits exception behavior if the remote database is unreachable.
  * **Question:** *"What shall the synchronizer do if the connection to the central remote database fails during a write?"*
  * **Stakeholder Answer:** *"Buffer changes locally and retry every 60 seconds until connection is restored."*
  * **Refined Text:** *"The synchronizer shall write updated client profiles to the central remote database; if unreachable, it shall buffer records locally and retry every 60 seconds."*

* **Negative Example 1 (Clean):**
  * **Requirement:** *"The file transfer service shall send daily reports to the FTP server; if connection fails, it shall retry 3 times at 5-minute intervals before alerting the administrator."*
  * **Why Clean:** Explicit retry count, backoff interval, and escalation path.

* **Negative Example 2 (Clean):**
  * **Requirement:** *"The authentication module shall lock user accounts for 30 minutes following 5 consecutive failed login attempts."*
  * **Why Clean:** Explicit edge-case defense and error recovery policy.

---

### 3.3 Class: Implicit
Implicit gaps occur when a requirement omits an essential, unstated domain constraint (such as security, privacy, regulatory compliance, or auditability) that industry standards demand for that domain action.

---

#### Subtype 9: `unstated_constraint`
Omission of implicit domain constraints (e.g. data encryption in transit for personal health data, atomic transactions for financial balances, or tamper-evident logging for access control).

* **Positive Example 1:**
  * **Requirement:** *"The patient portal shall transmit real-time heart rate and blood glucose telemetry to the physician dashboard."*
  * **Span:** *(Whole requirement / requirement-level)*
  * **Severity:** 3 (Critical: transmitting unencrypted Protected Health Information violates HIPAA and patient privacy)
  * **Explanation:** Transmitting personal health telemetry requires an unstated encryption in transit constraint.
  * **Question:** *"Shall the patient health telemetry be encrypted in transit using TLS 1.3 or higher?"*
  * **Stakeholder Answer:** *"Yes, end-to-end TLS 1.3 encryption with mutual certificate authentication is mandatory."*
  * **Refined Text:** *"The patient portal shall transmit real-time heart rate and blood glucose telemetry to the physician dashboard over an encrypted TLS 1.3 connection with mutual certificate authentication."*

* **Positive Example 2:**
  * **Requirement:** *"The banking application shall transfer money between customer accounts upon request."*
  * **Span:** *(Whole requirement / requirement-level)*
  * **Severity:** 3 (Critical: financial money transfer requires atomic execution and audit trail)
  * **Explanation:** Money transfer requires implicit ACID transactional atomicity and non-repudiation audit logging.
  * **Question:** *"Must the transfer execute as an atomic transaction with duplicate-prevention idempotency?"*
  * **Stakeholder Answer:** *"Transfers must be atomic and idempotent using a client-generated transaction UUID."*
  * **Refined Text:** *"The banking application shall transfer money between customer accounts as an atomic, idempotent transaction verified by a unique transaction UUID."*

* **Negative Example 1 (Clean):**
  * **Requirement:** *"The telemetry service shall store biometric user data in the database encrypted at rest using AES-256."*
  * **Why Clean:** Security and privacy constraints are explicitly incorporated into the specification.

* **Negative Example 2 (Clean):**
  * **Requirement:** *"The flight controller shall log sensor inputs to write-once, tamper-evident flash memory."*
  * **Why Clean:** Audit integrity constraints are explicitly stated.

---

## 4. Question Formulation Guidelines

Every clarification question written by annotators or generated by models must satisfy:
1. **Punctuation:** Must end with **exactly one** question mark (`?`).
2. **Length:** At most **30 words**.
3. **Neutrality:** Ask what the constraint or definition should be; **never invent answers or propose leading options**.
4. **Groundedness:** Must directly address the flagged span and identified defect type.

---

## 5. Refinement Formulation Guidelines

When authoring a refined requirement based on stakeholder answers:
1. **Preserve Scope:** Incorporate only the clarification provided in the answer; do not alter unaffected parts of the requirement.
2. **Numeric Integrity:** Retain all original numbers, dates, units, and identifiers verbatim unless explicitly corrected by the stakeholder.
3. **No Hallucination:** Do not introduce unverified assumptions or extra features not stated in the requirement or stakeholder answer.
