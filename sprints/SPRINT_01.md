# BLACKGRID — Sprint 1

## Time and goal

This sprint covers 14 days from the agreed start date. Plan for 16–20 focused hours in total, usually 60–90 minutes per session with a longer session to put everything together. Adjust the amount of work to fit the time available.

Build one small workflow that runs on your computer and studies part of the CollegeMsg messaging network. It should choose an allowed experiment, run the calculations, check the evidence, and write a report. When the evidence is too weak, it must say “not enough evidence.”

Also check the calculations using small artificial networks where we know the answers. These are called **synthetic graphs**.

The main question is: **Does the messaging network show stronger group structure than a suitable randomized network? Does the answer change when some connections are removed?**

This is an early trial for research questions RQ1 and RQ2 in `PROJECT_CONTEXT.md`. It does not prove that BLACKGRID improves scientific research.

Start with **mock mode**: fixed example agent responses that need no paid AI service. A real LLM run is optional, needs separate permission, and is not required to finish the sprint. This plan alone does not authorize coding or spending; follow the user's instructions about which day to work on.

Leave graph machine learning, full Bayesian models, causal-effect estimates, custom model hosting, separate agent services, a user interface, and deployment for later. Their requirements remain in `PROJECT_CONTEXT.md`.

## Dataset and preparation rules

Use `data/CollegeMsg.txt/CollegeMsg.txt` in the repository. Its current full path is `C:\Blackgrid\data\CollegeMsg.txt\CollegeMsg.txt`.

The [SNAP dataset page](https://snap.stanford.edu/data/CollegeMsg.html) describes each row as a sender ID, receiver ID, and message time. The time is a Unix timestamp: seconds since the start of 1970 in UTC.

Record the source, citation, row-format checks, and decision about permitted use and redistribution. Calculate a **SHA-256 checksum**, a fingerprint that helps confirm that the input file has not changed. Follow any existing usage decision in `docs/decision_log.md`. If permitted use is still unresolved, mark the CollegeMsg run as blocked and continue with synthetic checks. Do not call the real-data work complete in that case.

Keep the raw file unchanged. Never send user IDs or message records to an external LLM or logging service.

### Choose a small time window

Follow the fixed rule in `PROJECT_CONTEXT.md`:

1. Start at the earliest valid message time and try the first 7 days.
2. If that includes more than 1,000 active users or 10,000 distinct connections, try the first 3 days, then 1 day, then 6 hours.
3. Use the first window that fits both limits. Include the start time and exclude messages exactly at the end time.
4. Choose using size counts only, before looking at experiment results. Keep the selected times and graph-building rules fixed afterward.
5. If none fits, or the selected network cannot support a valid experiment, stop with an explanation. Do not search for a window that gives an attractive result.

An active user sends or receives at least one message in the window.

### Turn messages into a network

Keep the selected message table, including direction, timestamps, and repeated messages. For the one group-finding experiment, make a simpler network:

- Each user becomes a node.
- Two users have one connection if either sent the other at least one message.
- Repeated messages and messages in both directions become one connection.
- All connections count equally. This experiment deliberately leaves out message direction and frequency.
- Leave out messages users send to themselves, but count and report them.
- Flag exact duplicate rows; do not silently delete them because they might be genuine events.

Record all checks, decisions, excluded records, counts before and after conversion, and the new graph's checksum. Conclusions apply only to this simplified network and time window.

CollegeMsg has no verified social-group labels or known causal effects. Keep its exploratory findings separate from synthetic test scores. Do not describe discovered groups as proven friendships or claim that a network feature causes an outcome.

## The experiment

Use the CollegeMsg network for the real-data demonstration. Use small synthetic networks with built-in groups, randomized connections, and uneven numbers of connections per node to check correctness.

Before running the experiment, choose one group-finding method and one score. Distinguish the groups built into synthetic data from the groups the method finds; they need not match exactly.

Compare the observed network with a **null model**: randomized networks representing a specific alternative explanation. Where practical, preserve each node's number of connections while shuffling which nodes connect. Document how to handle small or disconnected networks and failed shuffling attempts.

Use the same group-finding method, score calculation, random-seed rules, and amount of optimization on the observed network and every randomized network. A **random seed** is a recorded starting value that helps repeat a randomized calculation. Do not carefully optimize the observed grouping while giving the randomized networks less effort.

Choose and record a fixed number of randomized comparisons using synthetic development cases, within the tool's time limit. Do not change that number after seeing whether a result looks statistically significant.

Calculate the Monte Carlo p-value as:

`p = (1 + exceedances) / (1 + replicates)`

Here, `replicates` is the number of randomized comparisons, and `exceedances` counts comparisons whose score is at least as large as the observed score. Report the smallest possible p-value for that number of comparisons: `1 / (1 + replicates)`.

A small p-value does not measure the size of the difference or prove that real social groups exist. Report the observed score, a summary of randomized scores, the size of their difference, uncertainty, and limitations.

Also remove connections using a rule chosen in advance and check whether the conclusion changes. Call this a **sensitivity check**, not a Bayesian uncertainty estimate. Full Bayesian calculations come later.

If an experiment is invalid or has too little evidence, report a failure or “not enough evidence.” Keep synthetic answer keys available only to the evaluator, not to the agent, critic, or report writer.

## Daily plan

| Day | Hours | Work and how to check it |
|---|---:|---|
| 1 | 1 | Confirm the question, CollegeMsg source and usage terms, time-window rules, computer limits, and sprint scope. Write the experiment plan and start the decision log. No private data or paid service is needed. |
| 2 | 1 | Set up the small code repository and an environment with recorded dependency versions, after permission to implement. Define required fields and checks for graphs, experiments, results, claims, and run records. Document one command that works offline. |
| 3 | 1.5 | Build the CollegeMsg file reader. Check its checksum and row format, select the fixed time window, and build the simplified graph. Add tiny synthetic test networks with recorded seeds and checksums. Keep their answers away from the agent. |
| 4 | 1 | Create 8 small synthetic test cases across three network families and four task types. Include randomized networks, disconnected networks, missing connections, and invalid requests. Add file-reader and time-window tests. Reserve separate locations and IDs for future tests that must stay unseen during development. |
| 5 | 1.5 | Build the network summary and the single statistical experiment. Check the calculations using examples that can be worked out by hand or checked independently. |
| 6 | 1 | Add the planned missing-connection checks. Record where each graph came from and how it was built. Treat missing connections as unknown; keep guessed connections separate from observed ones. |
| 7 | 1 | Check experiment requests and allow only registered tools. Enforce resource limits. Reject arbitrary code, unsuitable methods, oversized inputs, and incorrectly formatted arguments. |
| 8 | 1.5 | Add one simple planner and controller using fixed mock responses. Optionally add a connection to an LLM provider. Check call, token, retry, revision, spending, and time limits before each action. |
| 9 | 1 | Add rule-based checks and a critic checklist. Check method requirements, statistical support, limitations, and links between claims and evidence. Reject unsupported claims about cause and effect. |
| 10 | 1 | Produce a readable CollegeMsg Markdown report and machine-readable run records. Explain the time-window limits and show synthetic results separately. Check that every reported number has evidence and that failures remain visible. |
| 11 | 1.5 | Compare tools alone with tools plus the validator and critic, using the same mock test cases. Check formats, workflow completion, supported claims, useful answers, and failures. Mock responses cannot show how well a real LLM works. |
| 12 | 1 | Test misleading instructions inside input text, attempts to read answer keys, blocked network access, timeouts, and spending limits. Confirm that restrictions actually work. Disable any execution path that cannot enforce them. |
| 13 | 2 | Repeat the complete offline workflow in a clean environment using the written instructions. Check the report, evidence, run records, and failure records. Fix problems that prevent completion. |
| 14 | 1.5 | Check every completion requirement. Write a local sprint report with limitations, actual time and cost, and a decision about the next step. Label early findings clearly; do not present them as confirmed research results. |

The plan totals **17.5 hours**, leaving about **2.5 hours** within the 20-hour limit for unexpected problems.

If time runs short, drop the optional live-LLM connection first. Then reduce the range of test cases if needed, recording what is no longer covered. Keep evidence links, separation of development and unseen tests, resource limits, and repeatable runs. Mark unfinished requirements honestly.

## What the sprint should produce

- One small command-line workflow that works offline, with a command and instructions for repeating it.
- Versioned CollegeMsg file-reading, time-window, and graph-building rules, plus source and usage records.
- Synthetic test-data settings and test cases.
- One experiment plan, repeatable calculation, comparison baseline, and critic checklist.
- A mock planner, a checked list of allowed tools, a controller with limits, and clear failure outcomes.
- A CollegeMsg example report and run record containing file and graph checksums, time bounds, validation counts, excluded-record counts, and logs without sensitive data. Synthetic results stay separate.
- Focused tests, a small comparison table, and an honest sprint report.

This is a plan, not proof that these items are complete. Check the actual files, test evidence, and decision log for current progress.

## When Sprint 1 is complete

1. The CollegeMsg workflow runs from the existing local file in a clean environment using the written instructions. It needs no secrets, downloads, or network calls, and the usage decision is recorded. If that decision is unresolved, this requirement stays blocked; synthetic-only work is partial completion.
2. Small known-answer and randomized test networks check the calculations and handling of invalid inputs. A network designed to contain groups does not have to produce statistical significance on every randomized run.
3. Every factual claim in the report links to saved evidence. Weak evidence leads to “not enough evidence,” and unsupported causal statements are rejected.
4. The agent, critic, and report writer cannot read synthetic answer keys or reserved test information. Include a test that tries to access them.
5. Run records correctly include settings, software versions, seeds, checksums, tool calls, failures, timings, and costs. Distinguish zero-cost mock runs from actual paid usage.
6. The workflow stops predictably when it runs out of budget, retries too often, exceeds time or size limits, receives a bad tool request, or attempts an unauthorized action. Save a failure record without sensitive data.
7. The comparison table shows unsupported claims and useful answers, including the total number assessed for each score. Mock results check the workflow only. Any real-LLM results are labeled as small early trials.
8. The report includes missing-connection checks and CollegeMsg's observation and graph-conversion limits. Synthetic scores remain separate. No proprietary ValueMatrix data, added identity details, or raw user/message records enter external prompts, logs, or published reports.
9. File-reader tests cover bad rows, repeated events, exact duplicates, self-messages, and timestamps. Tests confirm the fixed time-window rule and connection aggregation. Run records show counts before and after conversion. Results never influence window selection.

## Resource limits and stopping rules

Follow `PROJECT_CONTEXT.md`:

- Use the CPU first. Experimental graphs must have at most 1,000 active users and 10,000 distinct connections, selected using the CollegeMsg window rule.
- Run one worker, with at most 2 GB of memory and 60 seconds per tool call.
- Start smaller if randomized comparisons cannot finish within the limits, following the fixed window rule rather than choosing by results.
- Do not rent a cloud GPU, create infrastructure accounts, or run unattended paid loops.

Paid use needs separate permission. If approved, all these limits apply:

| Limit | Maximum |
|---|---:|
| Total sprint spending | USD 10 |
| Spending per investigation | USD 0.50 |
| LLM calls per investigation | 8 |
| Total input and output tokens per investigation | 20,000 |
| Retries per failed call | 1 |
| Revision rounds per investigation | 2 |

Tokens are the units an LLM uses to count input and output text. Retries and calls made inside other calls count toward the limits too.

Stop before the next action would exceed any limit. Record current provider prices and the estimated charge before each paid call. Disable paid calls if pricing is unknown. These amounts are spending ceilings, not estimates of provider prices.

## Review and next step

Move forward only when the calculations, evidence links, execution restrictions, and repeatable offline run work. Fix that foundation before adding more features.

If the critic does not improve results, record that finding. A simpler rule-based approach may be enough.

Next, write and freeze a small real-LLM trial plan and scoring checklist. Obtain any needed API permission, estimate result variability and cost, then choose the size of the larger study and the smallest useful improvement before looking at fresh test results.

Review whether the CollegeMsg window remains suitable and whether usage or redistribution questions remain before broader real-data work. Leave the other datasets for later. Graph ML, Bayesian models, causal inference, and faster model serving each need their own reason for inclusion and completion requirements.
