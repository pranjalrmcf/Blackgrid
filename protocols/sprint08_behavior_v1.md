# Sprint 8: observed messaging behavior, v1

Registered before execution on 2026-10-19. Exploratory, descriptive, transductive analysis of the already selected half-open observation window; no future prediction, causal inference or real anomaly labels. No new dataset, dependency or paid execution is required.

## Fixed contract

Preserve repeated directed events. Exclude self-messages from features and count exclusions; retain their nodes with zero features. Filter events to the recorded `[start, end)` and verify the resulting nodes and undirected projection against the investigation graph. Maximum 1,000 nodes, 10,000 pairs and 100,000 selected events. Refuse missing event provenance and incompatible graphs rather than inferring behavior from topology.

Use eight features, in order: log(1 + sent events), log(1 + received events), log(1 + distinct recipients), log(1 + distinct senders), fraction of seven equal-duration bins active, reciprocal-neighbor fraction, outgoing-event fraction, largest-bin fraction of incident events. Empty denominators give zero. Repeated events count in activity; reciprocal distinct neighbors count once. Include feature definitions, window, exclusions, input fingerprint, seed and library versions in artifacts. Node rows remain in local artifacts only; model evidence uses an explicit aggregate allowlist.

* **Behavioral clustering:** standardize each feature within the selected population, KMeans k=3, seed=8, n_init=10. Report cluster sizes, original-scale feature means, silhouette where defined, and inertia. Abstain below six nonzero profiles or fewer than three distinct nonzero profiles. Exclude zero profiles as unassigned. No k search or real-world group labels.
* **Similarity search:** cosine on the nonnegative feature vectors, L2 normalization, five nearest other nonzero profiles per node, ties by numeric node identifier. Zero profiles have no defined neighbors. Similarity includes activity volume and timing; it does not establish a relationship, identity, prediction or probability.
* **Anomaly detection:** largest absolute robust feature deviation. Center at population median; scale at max(1.4826 MAD, 0.1) for ratio features and max(1.4826 MAD, 1.0) for log-count features. Flag score >=3.5 as a heuristic candidate. Report count-only deviation as a transparent baseline and flag overlap. Abstain below 20 nonzero profiles or when all profiles are identical. Exclude zero profiles, report their count. These are unusual observed profiles, not verified malicious or abnormal people; no false-positive rate or calibrated significance is claimed.

## Acceptance and verification

Hand-calculated directed-event features, repeated-event preservation, end-boundary/future isolation, deterministic nearest-neighbor ordering without self matches, zero-profile handling, degenerate abstention, event/projection mismatch rejection, fixed-method argument rejection, and model-payload privacy. Test all three natural-language routes and a complete offline workflow against known inputs. Run the existing regression suite. Any real-data demonstration uses the existing approved CollegeMsg window, reports aggregate exploratory results separately from synthetic checks, and preserves failures. Do not tune these settings after observing demonstration outputs; revisions require a new protocol.

No synthetic detection accuracy or real-world clustering quality threshold is claimed by correctness tests. A later blinded benchmark with planted behavioral mechanisms and untouched evaluation seeds is required before performance claims.

## Development smoke check (registered before paid execution)

One real-LLM planner attempt on the existing CollegeMsg first window: “Find behavioral clusters, similar activity profiles and anomalous messaging behavior.” Require behavior family, all four tools, checked aggregate claims, complete report and no identifier rows in model evidence. This already-exposed wording is an integration check, not a held-out success-rate evaluation. Use the retained absolute USD 3 project ceiling (prior spend and reservations included), existing per-run cap at most USD 0.15, no retry or model-written interpretation. Preserve failure instead of tuning thresholds. Record actual cost, runtime and model in the local run receipt and publish aggregates only.
