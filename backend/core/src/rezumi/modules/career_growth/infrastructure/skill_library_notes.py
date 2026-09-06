"""Original readable study articles for each skill family.

These notes are self-authored teaching text. They are not transcripts or copies
of a paid course. Completion is not Career Record evidence.
"""

from __future__ import annotations

from rezumi.modules.career_growth.infrastructure.skill_library_packs import family_for_skill

_NOTE_MAX = 50_000


def study_articles(name: str, *, why: str, how_to_start: str) -> tuple[tuple[str, str], ...]:
    family = family_for_skill(name)
    why_line = why.strip() or (
        f"{name} is on this role path because teams expect you to use it under pressure."
    )
    start_line = how_to_start.strip() or (
        f"Write what you already know about {name}, then complete one small artifact this week."
    )
    concepts = _concepts(name, family, why_line)
    practice = _practice(name, family, start_line)
    field_notes = _field_notes(name, family, start_line)
    return (
        (f"{name}: what you actually need to know", concepts),
        (f"{name}: practice workbook", practice),
        (f"{name}: field notes and a four-week study plan", field_notes),
    )


def _concepts(name: str, family: str, why_line: str) -> str:
    body = _FAMILY_CONCEPTS.get(family, _FAMILY_CONCEPTS["product"])
    return _clip(
        f"{name}\n\n"
        "Read this as a study article, not a checklist. The goal is to explain the "
        "skill out loud, then prove it with a small artifact. This is original Rezumi "
        "teaching text. It is not a paid-course transcript and is not Career Record evidence.\n\n"
        f"Why this skill is on your path\n{why_line}\n\n"
        f"{body}\n\n"
        f"{_skill_lens(name, family)}\n\n"
        f"{_FAMILY_DEPTH.get(family, _FAMILY_DEPTH['product'])}\n\n"
        "How this shows up at work\n"
        "People will not ask you to recite a course title. They will ask you to choose "
        "a tool, defend a tradeoff, notice a failure mode, and write something another "
        "person can use. Keep a running page of: the decision, the alternative you rejected, "
        "the signal that would change your mind, and the evidence you still need in your "
        "Career Record.\n"
    )


def _practice(name: str, family: str, start_line: str) -> str:
    drills = _FAMILY_DRILLS.get(family, _FAMILY_DRILLS["product"])
    return _clip(
        f"{name} practice workbook\n\n"
        "Do the work in writing. If you cannot show an artifact, you have not practiced "
        "the skill yet.\n\n"
        f"This week\n1. {start_line}\n"
        "2. Watch one free course from the library and write a one-page explanation in "
        "your own words. Include one example, one failure mode, and one question you still have.\n"
        "3. Produce a small artifact you could attach later as Career Record evidence only "
        "after you actually did the work.\n\n"
        f"{drills}\n\n"
        "How to write the artifact\n"
        "Open a blank page. Title it with the skill. Write: the setup, the action, the "
        "observable result, and the failure you injected. If you used a tutorial, close it "
        "and redo the last step from memory. If you cannot, you were copying, not practicing.\n\n"
        "Self-check before you stop\n"
        "- Can you teach this to a teammate in ten minutes without slides?\n"
        "- Can you name a mistake you made while practicing and how you caught it?\n"
        "- Can you point to an artifact, not a feeling, that the skill improved?\n"
        "- Did you write the failure mode you hit, not only the happy path?\n"
    )


def _clip(value: str) -> str:
    text = value.strip()
    if len(text) > _NOTE_MAX:
        return text[: _NOTE_MAX - 1].rstrip() + "…"
    return text


def _skill_lens(name: str, family: str) -> str:
    return (
        f"How to study {name} specifically\n"
        f"{name} is not a generic {family.replace('_', ' ')} course title. Treat it as a "
        "job you will be asked to do with incomplete information. Before you watch another "
        "hour of video, write four sentences: what this skill produces, who consumes that "
        "output, what a cheap fake looks like, and what evidence would prove you can do it. "
        "Then pick resources that help you produce that artifact, not resources that merely "
        f"repeat the words {name}.\n\n"
        "A worked reading order\n"
        "1. Skim the official docs or primary reference until you can name the objects.\n"
        "2. Watch one full free course with a notebook: pause, restate, resume.\n"
        "3. Do the practice workbook drills in writing.\n"
        "4. Only then look at a paid course if a certificate or a tighter syllabus helps you "
        "finish. Paid does not mean more true.\n"
        "5. Teach the skill in a one-page note a teammate could use on Monday.\n"
    )


def _field_notes(name: str, family: str, start_line: str) -> str:
    depth = _FAMILY_DEPTH.get(family, _FAMILY_DEPTH["product"])
    return _clip(
        f"{name} field notes\n\n"
        "This is a readable study plan, not a Markdown dump and not a transcript of a paid "
        "course. Keep it next to the library links. Completion here is still not Career "
        "Record evidence until you actually did the work and can point to an artifact.\n\n"
        f"Week 1 — orientation\n{start_line} Copy the vocabulary from the concepts article "
        f"into your own words. Watch one free course about {name} and write a half page on "
        "what surprised you.\n\n"
        f"Week 2 — mechanics\nDo the first half of the practice workbook. Produce a small "
        f"{name} artifact: a diagram, a query, a spec, a test, a rec, a script, or a "
        "recorded explanation. Label what is still guesswork.\n\n"
        f"Week 3 — pressure\nAdd a failure mode. Break your artifact on purpose, then repair "
        "it. If this skill is used in interviews, answer one prompt out loud and record "
        "yourself. If it is used on a team, write the status update you would send.\n\n"
        "Week 4 — transfer\nUse a second resource from a different provider so you are not "
        "fluent in only one teacher's metaphors. Rewrite your one-pager. List evidence you "
        "still do not have the right to claim.\n\n"
        f"{depth}\n\n"
        "What to refuse\n"
        "Do not paste a certificate into Career Record as if it were a shipped result. Do "
        "not copy a vendor lab as your own accomplishment. Do not download notes as a "
        "substitute for reading them. The in-app articles are the notes; PDF is only for "
        "offline rereading.\n"
    )


_FAMILY_DEPTH: dict[str, str] = {
    "algorithms": (
        "Interview and on-the-job prompts\n"
        "Explain the invariant of your structure before code. Compare hash map vs sort plus "
        "two pointers for the same problem. Name when a graph is the wrong model. Estimate "
        "memory, not only time. If you cannot draw it, you do not know it yet."
    ),
    "git": (
        "Interview and on-the-job prompts\n"
        "Walk through a conflicted rebase. Explain force-with-lease. Recover a commit with "
        "reflog. Describe a branching rule you would actually enforce on a team of six."
    ),
    "testing": (
        "Interview and on-the-job prompts\n"
        "Given a flaky test, what do you delete vs quarantine vs rewrite. Where does a unit "
        "test stop and an integration test start. How do you test time, randomness, and I/O "
        "without lying to yourself."
    ),
    "system_design": (
        "Interview and on-the-job prompts\n"
        "State QPS, payload size, and retention before drawing boxes. What is cached, who "
        "invalidates, what is the stampede plan. What does the user see if the queue lags "
        "by ten minutes."
    ),
    "distributed": (
        "Interview and on-the-job prompts\n"
        "At-least-once vs at-most-once vs idempotent handlers. Dual-write failure. How you "
        "would page a human for poison messages. Clock skew in last-write-wins."
    ),
    "frontend": (
        "Interview and on-the-job prompts\n"
        "Rebuild a form with labels, errors, and focus. Explain flex vs grid for a real "
        "layout. Name the accessibility bug in a div that looks like a button."
    ),
    "javascript": (
        "Interview and on-the-job prompts\n"
        "Stale closure. Aborting fetch. Why TypeScript disappeared at runtime. How you "
        "would type a JSON boundary without any."
    ),
    "accessibility": (
        "Interview and on-the-job prompts\n"
        "Keyboard a modal. Name, role, value for a custom widget. Contrast vs color-only "
        "status. When ARIA makes things worse."
    ),
    "databases": (
        "Interview and on-the-job prompts\n"
        "Read an EXPLAIN plan. Choose a composite index. Transaction isolation for a "
        "decrement. Why OFFSET pagination falls over."
    ),
    "python": (
        "Interview and on-the-job prompts\n"
        "Mutable defaults. Virtualenv vs lockfile. When pandas is the wrong tool. How you "
        "test a script that reads a file."
    ),
    "ml": (
        "Interview and on-the-job prompts\n"
        "Leakage examples. Metric vs decision cost. Time split vs random split. What you "
        "log in production besides accuracy."
    ),
    "llm": (
        "Interview and on-the-job prompts\n"
        "How retrieval fails. How you evaluate without vibes. Cost of retries. What you "
        "refuse to store as Career Record evidence from a model."
    ),
    "data": (
        "Interview and on-the-job prompts\n"
        "State the grain. Define revenue with refunds. Freshness SLO. Why a join on names "
        "is a bug."
    ),
    "statistics": (
        "Interview and on-the-job prompts\n"
        "Peeking. Multiple comparisons. Effect size vs p-value. When an A/B test is the "
        "wrong instrument."
    ),
    "devops": (
        "Interview and on-the-job prompts\n"
        "Build once, promote the digest. Rollback in one paragraph. Alert that a human can "
        "action. Secret that leaked into logs."
    ),
    "linux": (
        "Interview and on-the-job prompts\n"
        "Service down: status, logs, disk, ports, recent change. Permissions that are not "
        "777. When strace is worth it."
    ),
    "cloud": (
        "Interview and on-the-job prompts\n"
        "Blast radius of one account. IAM least privilege for one action. A bill shock "
        "story and the alarm that would have caught it."
    ),
    "security": (
        "Interview and on-the-job prompts\n"
        "Threat model a search box. Injection vs XSS vs SSRF in one sentence each. What "
        "you do with a scanner finding you cannot explain."
    ),
    "product": (
        "Interview and on-the-job prompts\n"
        "Write non-goals. Kill metric. Stakeholder who disagrees. Why a roadmap is not a "
        "feature list."
    ),
    "design": (
        "Interview and on-the-job prompts\n"
        "Empty, loading, error, overflow. Tokens vs one-off values. How a critique changes "
        "the file, not the ego."
    ),
    "research": (
        "Interview and on-the-job prompts\n"
        "A non-leading question. n=5 vs market size. One disconfirming quote. Method "
        "matched to the decision."
    ),
    "qa": (
        "Interview and on-the-job prompts\n"
        "A bug report an exhausted engineer can use. Severity vs priority. What not to "
        "automate yet."
    ),
    "mobile": (
        "Interview and on-the-job prompts\n"
        "Offline write queue. Cold start budget. Store review surprise. Battery work you "
        "moved off the main thread."
    ),
    "management": (
        "Interview and on-the-job prompts\n"
        "A 1:1 agenda the other person wrote. SBI feedback. A growth plan with evidence "
        "dates. Hiring scorecard vs vibe."
    ),
    "business_analysis": (
        "Interview and on-the-job prompts\n"
        "As-is vs to-be. A testable requirement. A metric with source system. Where data "
        "is retyped."
    ),
    "writing": (
        "Interview and on-the-job prompts\n"
        "Error message rewrite. Audience and next action. Docs-as-code review. Tone that "
        "does not joke at the user."
    ),
    "project": (
        "Interview and on-the-job prompts\n"
        "Status as variance. A risk with trigger and owner. What you will descope. How you "
        "say red without theater."
    ),
    "agile": (
        "Interview and on-the-job prompts\n"
        "One retro change with an owner. WIP and cycle time. Impediment that is dated. "
        "Standup that is not status theater."
    ),
    "architecture": (
        "Interview and on-the-job prompts\n"
        "NFR turned into a test. Sync vs async integration. Versioning and deprecation. "
        "Failure sequence, not only happy path."
    ),
    "networking": (
        "Interview and on-the-job prompts\n"
        "Name the layer that failed. TCP vs TLS vs HTTP. Trust boundary drawing. Why "
        "overlapping subnets hurt."
    ),
    "support": (
        "Interview and on-the-job prompts\n"
        "Ticket a stranger can continue. Time-bound update under pressure. Recent-change "
        "question. When to escalate."
    ),
    "sales": (
        "Interview and on-the-job prompts\n"
        "Discovery before demo. Objection as information. POC success criteria. Forecast "
        "evidence vs hope."
    ),
    "marketing": (
        "Interview and on-the-job prompts\n"
        "One campaign, one metric, one kill date. Intent vs volume. Attribution bias you "
        "accept. Channel without a message."
    ),
    "finance": (
        "Interview and on-the-job prompts\n"
        "Bridge a variance. Driver vs total. Assumption you can change. Cash vs revenue "
        "this quarter."
    ),
    "accounting": (
        "Interview and on-the-job prompts\n"
        "Walk a bank rec. Cut-off example. Why suspense is a smell. Close checklist "
        "ownership."
    ),
    "hr": (
        "Interview and on-the-job prompts\n"
        "Document facts, not labels. Jurisdictional caution. Who can see which report. "
        "Inconsistent exception risk."
    ),
    "recruiting": (
        "Interview and on-the-job prompts\n"
        "Scorecard before sourcing. Candidate update that is honest. Bar that does not "
        "move after debrief. Role you can explain without faking."
    ),
    "operations": (
        "Interview and on-the-job prompts\n"
        "Service level vs inventory. Forecast error buffer. Vendor OTIF. Cost to serve "
        "vs unit cost."
    ),
}


_FAMILY_CONCEPTS: dict[str, str] = {
    "algorithms": (
        "Core ideas\n"
        "A data structure is a rule for storing values so that some operations are cheap "
        "and others are expensive. An algorithm is a procedure with a cost you can explain. "
        "Big-O is not a score. It is a claim about how work grows as input size grows. "
        "O(1) lookup on a hash map assumes a good hash and enough memory. O(n) scan of an "
        "array can beat a fancy structure on small n. Always state the operation: insert, "
        "lookup, delete, min, range, shortest path.\n\n"
        "Structures you must be able to draw\n"
        "Array and dynamic array: contiguous memory, index in O(1), insert in the middle is O(n). "
        "Hash map: expected O(1) lookup, fails when keys collide or when you need order. "
        "Stack and queue: LIFO and FIFO. Use them for DFS, BFS, undo, and scheduling. "
        "Binary search tree and heap: ordered vs priority. Heap gives you min or max quickly, "
        "not sorted iteration. Graph: adjacency list vs matrix. BFS for shortest unweighted "
        "path, Dijkstra for weighted nonnegative edges, union-find for connectivity.\n\n"
        "Worked example: two-sum\n"
        "Naive nested loops are O(n^2). A hash map of value to index is expected O(n) time "
        "and O(n) extra memory. If the interviewer asks for constant extra memory, sort then "
        "two-pointer, which is O(n log n). Say the tradeoff out loud before you code.\n\n"
        "Worked example: BFS\n"
        "Put the start node in a queue. Track visited so you do not loop. Each edge is seen "
        "a constant number of times, so time is O(V+E). If someone asks for shortest path in "
        "an unweighted graph, BFS is the default, not DFS.\n\n"
        "Common failure modes\n"
        "Memorizing solutions without the invariant. Off-by-one on binary search bounds. "
        "Mutating a collection while iterating. Using a recursive DFS on a deep graph until "
        "the stack blows. Claiming O(1) hash map time as a guarantee.\n"
    ),
    "git": (
        "Core ideas\n"
        "Git stores snapshots, not a list of file diffs you have to imagine. A commit is a "
        "snapshot plus parents plus a message. A branch is a movable pointer. HEAD is which "
        "commit your next commit will parent. Remote tracking branches are your last known "
        "view of someone else's pointers.\n\n"
        "The working loop\n"
        "status, diff, add, commit, push, pull --rebase or merge, open a review, address "
        "comments, squash or not according to the team's rule. Never force-push a shared "
        "branch unless the team has an explicit rule and you know who you will rewrite.\n\n"
        "Worked example\n"
        "You branched from main, main moved, your feature conflicts. Fetch. Rebase onto "
        "origin/main or merge origin/main. Resolve one file at a time. Run tests. Then push. "
        "If rebase rewrites commits already on the remote feature branch, you need a force "
        "with lease, not a blind force.\n\n"
        "Common failure modes\n"
        "Committing secrets. Giant commits that mix formatting and logic. Rewriting public "
        "history. Using reset --hard on uncommitted work. Ignoring the diff because the "
        "conflict markers look scary.\n"
    ),
    "testing": (
        "Core ideas\n"
        "A test is a contract: given this setup, this action, this observable result. Unit "
        "tests pin a function. Integration tests pin a boundary (database, HTTP, queue). "
        "End-to-end tests pin a user path. More end-to-end is not more safety if they are "
        "slow and flaky. Flaky tests train the team to ignore red builds.\n\n"
        "What to test first\n"
        "The branchy business rule, the parser, the authorization check, the retry, the "
        "timezone, the empty list. Do not test the framework. Do not assert on log wording "
        "unless the log is the product.\n\n"
        "Worked example\n"
        "A discount function: 0 items is 0, 1-9 items is full price, 10+ is 10% off, negative "
        "quantity is rejected. Write one test per rule before you cleverly combine them. "
        "Name the test after the rule, not after the method.\n\n"
        "Common failure modes\n"
        "Testing implementation details so refactors break tests. Shared mutable fixtures. "
        "Sleeping to wait for async work. Snapshot tests nobody reads. Coverage as a goal "
        "instead of a flashlight.\n"
    ),
    "system_design": (
        "Core ideas\n"
        "Start from the job: users, writes per second, reads per second, data size, latency "
        "budget, consistency need, failure story. Then pick storage, compute, and a way to "
        "split work. A box labeled 'cache' is not a design until you say what is cached, "
        "who invalidates it, and what happens on a miss.\n\n"
        "Building blocks\n"
        "Load balancer, stateless app, primary/replica database, object store, queue, cache, "
        "CDN, id generator, search index. CAP is a slogan; talk about what the user sees on "
        "partition. Idempotency keys for writes. Backpressure for queues. Timeouts and "
        "retries with jitter, not infinite retry storms.\n\n"
        "Worked example: URL shortener\n"
        "Write path: auth, rate limit, insert mapping, return slug. Read path: cache then "
        "database then 301. Unique slugs via hash or preallocated ranges. Analytics via "
        "async log, not on the redirect critical path.\n\n"
        "Common failure modes\n"
        "Jumping to Kubernetes before the data model. Single-region everything. Cache "
        "without TTL or stampede control. Chatty service meshes for a CRUD app.\n"
    ),
    "distributed": (
        "Core ideas\n"
        "The network is not a function call. Packets drop, clocks drift, nodes die and "
        "come back with old disks. At-least-once delivery is the default; exactly-once is "
        "an application invariant you design with idempotency, not a broker checkbox.\n\n"
        "Patterns\n"
        "Leader election, quorum, fencing tokens, outbox, saga, bulkhead, circuit breaker. "
        "Read the Google SRE book chapters on incidents after you can explain "
        "retry amplification.\n\n"
        "Worked example\n"
        "A worker crashes after sending an email but before marking the job done. The job "
        "runs twice. Fix: store a send id, make the email provider accept that id, and treat "
        "the second send as a no-op.\n\n"
        "Common failure modes\n"
        "Dual writes to database and queue. Using wall-clock for last-write-wins across "
        "regions. Ignoring poison messages.\n"
    ),
    "frontend": (
        "Core ideas\n"
        "HTML is the document. CSS is presentation. Accessibility and semantics are not a "
        "theme. A button that is a div with a click handler is already a bug for keyboard "
        "and screen-reader users. Layout: flow, flex, grid. Cascade and specificity beat "
        "random !important.\n\n"
        "Worked example\n"
        "A form with name, email, submit. Labels are associated with inputs. Errors are "
        "text, not color alone. Focus order matches visual order. Contrast meets a published "
        "ratio. The submit button is a real button.\n\n"
        "Common failure modes\n"
        "Div soup. Images without alt. Animations that ignore reduced-motion. 12-column "
        "grids used as a substitute for hierarchy.\n"
    ),
    "javascript": (
        "Core ideas\n"
        "Values vs references. Closures. Promises and the event loop. async/await is "
        "control flow over promises, not parallelism by itself. TypeScript is a contract "
        "the compiler checks; it disappears at runtime unless you add runtime validation.\n\n"
        "Components\n"
        "A component is a function of props and state to UI. Lift state only as far as "
        "siblings need it. Effects are sync with the outside world, not a second render "
        "lifecycle to dump logic into.\n\n"
        "Worked example\n"
        "Fetch on mount: ignore stale responses or abort. Put the result in state. Show "
        "loading, empty, error, success. Do not hide failure behind a spinner forever.\n\n"
        "Common failure modes\n"
        "Mutating props. Stale closures in effects. any everywhere. Fetching in render.\n"
    ),
    "accessibility": (
        "Core ideas\n"
        "Perceivable, operable, understandable, robust. Color is a hint, never the only "
        "channel. Keyboard must reach every action. Name, role, value must be exposed to "
        "assistive tech. ARIA is a last resort after native HTML fails.\n\n"
        "Worked example\n"
        "A modal: focus moves inside, tab cycles, escape closes, focus returns to the "
        "opener, background is inert. That is not a CSS overlay. That is a dialog pattern.\n\n"
        "Common failure modes\n"
        "Placeholder as label. Icon-only buttons with no accessible name. Autoplaying video "
        "with sound. Custom checkboxes that are not checkboxes.\n"
    ),
    "databases": (
        "Core ideas\n"
        "Tables, keys, joins, indexes, transactions. Third normal form is a default, not a "
        "religion: denormalize when a measured read path needs it. An index speeds lookup "
        "and slows writes. EXPLAIN is how you stop guessing.\n\n"
        "Worked example\n"
        "Find recent orders for a customer: index (customer_id, created_at desc). Select "
        "only needed columns. Avoid SELECT *. Pagination with a stable key, not OFFSET on "
        "huge tables.\n\n"
        "Common failure modes\n"
        "N+1 queries. Missing unique constraints. Using float for money. One giant JSON "
        "column because schema felt hard.\n"
    ),
    "python": (
        "Core ideas\n"
        "Names bind to objects. Mutable default arguments are a trap. Context managers "
        "close resources. Virtual environments pin dependencies. Typing is optional at "
        "runtime unless you validate.\n\n"
        "Worked example\n"
        "Read a CSV, compute a grouped mean, write a parquet or another CSV. Use pandas "
        "for tabular work you can name; use plain Python when the table is tiny and the "
        "logic is the point.\n\n"
        "Common failure modes\n"
        "Bare except. Mutable class attributes shared across instances. Notebooks as the "
        "only source of truth with no function you can test.\n"
    ),
    "ml": (
        "Core ideas\n"
        "A model maps features to a prediction. Split train/validation/test the way "
        "production will see data, not randomly if time matters. Leakage is the silent "
        "killer: using future information or the label itself. Metrics must match the "
        "decision: accuracy on a 1% fraud set is a vanity number.\n\n"
        "Worked example\n"
        "Binary classifier: report precision, recall, and a threshold chosen for the cost "
        "of false positives vs false negatives. Plot a calibration curve before you ship "
        "probabilities to a human.\n\n"
        "Common failure modes\n"
        "Tuning on the test set. Imputing with statistics computed on all data including "
        "test. Claiming causality from a correlational model.\n"
    ),
    "llm": (
        "Core ideas\n"
        "A prompt is not a program. Retrieval grounds generation in documents you chose. "
        "Evaluation needs labeled tasks, not vibes. Safety is refusal, red-teaming, and "
        "logging, not a system prompt that says 'be nice'. Cost is tokens times price "
        "times retries.\n\n"
        "Worked example\n"
        "RAG: chunk documents with citations, embed, retrieve top-k, generate only from "
        "those chunks, show sources. If the answer is not in the chunks, say so.\n\n"
        "Common failure modes\n"
        "Stuffing the whole corpus into context. No eval set. Treating model output as "
        "facts in a Career Record.\n"
    ),
    "data": (
        "Core ideas\n"
        "Raw, cleaned, modeled. ETL vs ELT is about where compute lives. A warehouse "
        "table without a grain is a fight waiting to happen. Data quality: completeness, "
        "freshness, uniqueness, validity. Observability is knowing the pipeline failed "
        "before a stakeholder does.\n\n"
        "Worked example\n"
        "Orders grain is one row per order_id. Revenue is sum of paid orders in the period "
        "in USD after refunds. Write that in the table description. Then build the dashboard.\n\n"
        "Common failure modes\n"
        "Joining on names. Timezones mixed naively. Metrics that change definition every "
        "quarter with no version.\n"
    ),
    "statistics": (
        "Core ideas\n"
        "Distribution, variance, bias, sampling. A p-value is not the probability the "
        "hypothesis is true. Confidence intervals and effect sizes beat star-gazing. "
        "A/B tests need a pre-registered metric, sample size, and stopping rule.\n\n"
        "Worked example\n"
        "Conversion 2.0% vs 2.2%. Is that noise? Compute the interval. If the experiment "
        "was peeked daily and stopped when it looked good, you inflated false positives.\n\n"
        "Common failure modes\n"
        "Multiple comparisons without correction. Segment hunting. Mixing correlation "
        "slides with causal language.\n"
    ),
    "devops": (
        "Core ideas\n"
        "Build once, promote the same artifact. Infrastructure as code is reviewable "
        "state, not a clickops memoir. CI runs tests and linters. CD is a boring path to "
        "production with a rollback. Observability: logs, metrics, traces, and an owner "
        "for the alert.\n\n"
        "Worked example\n"
        "A GitHub Action builds an image, tags it with the git sha, pushes, and a deploy "
        "job applies a manifest that pins that sha. Rollback is deploy the previous sha.\n\n"
        "Common failure modes\n"
        "Building on the production server. Secrets in logs. Alerts nobody can action. "
        "Snowflake servers named after pets.\n"
    ),
    "linux": (
        "Core ideas\n"
        "Processes, files, permissions, signals, networking stack. Everything is a file "
        "is a slogan; file descriptors and sockets are the useful version. systemd starts "
        "services. journalctl reads their logs. ip and ss replace much of ifconfig/netstat.\n\n"
        "Worked example\n"
        "Service is down: systemctl status, journalctl -u, disk space, file descriptors, "
        "listening ports, recent deploys. Write the timeline.\n\n"
        "Common failure modes\n"
        "chmod 777. Disabling SELinux because it was loud. Debugging production over SSH "
        "with no notes.\n"
    ),
    "cloud": (
        "Core ideas\n"
        "Regions, AZs, IAM, networking, managed data stores, object storage, accounts vs "
        "resources. The bill is an architecture artifact. Least privilege is a reviewable "
        "policy, not a feeling. Tag resources with owner and purpose.\n\n"
        "Worked example\n"
        "A web app: load balancer, autoscaling group or container service, managed "
        "postgres, object storage for uploads, secrets manager, alarms on 5xx and cost.\n\n"
        "Common failure modes\n"
        "One AWS account for everything. 0.0.0.0/0 security groups. Leaving unused NAT "
        "gateways running. No budget alarm.\n"
    ),
    "security": (
        "Core ideas\n"
        "Threats, assets, controls. OWASP classes: injection, broken auth, XSS, SSRF, "
        "insecure design, misconfig. Threat modeling asks what can go wrong before you "
        "write the feature. Secrets are not in git. Dependencies are in a bill of materials.\n\n"
        "Worked example\n"
        "A search box: parameterized queries, encoded output, rate limits, authz on the "
        "object id, not just on the page. Log the actor and object, not the password.\n\n"
        "Common failure modes\n"
        "Security theater checklists. Blocking a release for a scanner finding you cannot "
        "explain. Ignoring the actual data flow.\n"
    ),
    "product": (
        "Core ideas\n"
        "A spec is a decision record: who, problem, constraints, success metric, non-goals, "
        "rollout, risks. Prioritization is explicit tradeoffs, not a backlog sorted by "
        "who shouted last. Stakeholders need a cadence and a single source of status.\n\n"
        "Worked example\n"
        "Write a one-pager for a small feature. Include the metric that would kill it. "
        "Review it with engineering and design before tickets exist.\n\n"
        "Common failure modes\n"
        "Roadmaps that are feature lists. Success metrics that the product cannot move. "
        "Discovery theater with no decision.\n"
    ),
    "design": (
        "Core ideas\n"
        "Hierarchy, spacing, type, contrast, components. A design system is a language: "
        "tokens, components, usage rules, contribution path. Handoff is constraints and "
        "states (empty, loading, error, overflow), not a single pretty frame.\n\n"
        "Worked example\n"
        "Design a settings row: label, helper, control, error. Show 1x and 2x density. "
        "Document keyboard behavior.\n\n"
        "Common failure modes\n"
        "Unique snowflake components. Ignoring dark mode and overflow. Shipping color with "
        "no meaning.\n"
    ),
    "research": (
        "Core ideas\n"
        "Method matches the question. Interviews for why, surveys for how many, usability "
        "tests for can they, analytics for did they. Do not lead. Record what people did, "
        "not what you hoped they would say. Synthesis groups evidence, not opinions.\n\n"
        "Worked example\n"
        "Five interviews, affinity map, one opportunity question, two quotes, one "
        "disconfirming note. Present that, not a 40-slide deck of screenshots.\n\n"
        "Common failure modes\n"
        "Recruiting only fans of the product. Asking 'would you use this?'. Treating n=5 "
        "as a market size.\n"
    ),
    "qa": (
        "Core ideas\n"
        "A test case has preconditions, steps, expected result, and a priority. Bugs need "
        "repro, environment, expected vs actual, severity. Automation is for stable, "
        "valuable paths. Load testing has a hypothesis: which resource saturates first.\n\n"
        "Worked example\n"
        "File a bug as if the engineer is tired and the build is red. Include the exact "
        "URL, account state, and a HAR or log snippet.\n\n"
        "Common failure modes\n"
        "Steps that start at 'log in' with no user. Severity inflation. Automation of a "
        "flow that changes weekly.\n"
    ),
    "mobile": (
        "Core ideas\n"
        "Lifecycle, offline caches, background limits, store review rules, battery. Network "
        "is optional. Persist a queue of writes. Sync with conflict rules. Measure jank and "
        "startup, not only features.\n\n"
        "Worked example\n"
        "Compose a screen that loads cached data instantly, refreshes in the background, "
        "and shows a retry when the refresh fails.\n\n"
        "Common failure modes\n"
        "Assuming always-on Wi-Fi. Blocking the main thread. Ignoring store screenshot and "
        "privacy questionnaire requirements until submit day.\n"
    ),
    "management": (
        "Core ideas\n"
        "One-on-ones are the employee's meeting. Feedback is specific behavior plus impact "
        "plus request. Estimation is a range and a risk, not a hostage number. Hiring is a "
        "bar and a process, not a vibe.\n\n"
        "Worked example\n"
        "Write a growth plan with two skills, evidence of each, and a review date. Do not "
        "store it only in your head.\n\n"
        "Common failure modes\n"
        "Status-only 1:1s. Surprise performance reviews. Saying 'be more proactive' with "
        "no example.\n"
    ),
    "business_analysis": (
        "Core ideas\n"
        "Current state, future state, gap, process, data, decision. A requirement is "
        "testable. A process map has a start, actors, systems, and a handoff. Numbers "
        "need a definition and a source.\n\n"
        "Worked example\n"
        "Map invoice-to-cash in one page. Mark where data is retyped. That is the "
        "automation candidate.\n\n"
        "Common failure modes\n"
        "Solutioning in the problem statement. Requirements that say 'fast' with no number. "
        "Stakeholders who never signed the grain of the metric.\n"
    ),
    "writing": (
        "Core ideas\n"
        "Audience, job to be done, structure, examples, next action. Docs-as-code means "
        "PRs, review, and owners. Interface writing is UI, not a novel. Voice is a "
        "constraint list, not a mood board.\n\n"
        "Worked example\n"
        "Rewrite an error: what happened, what the user can do, where to get help. No "
        "blame. No error codes without a human sentence.\n\n"
        "Common failure modes\n"
        "Walls of text. Screenshots that rot. Tone that jokes while the user is stuck.\n"
    ),
    "project": (
        "Core ideas\n"
        "Scope, timeline, budget, risk, communication. A plan that cannot change is a "
        "wish. Risks have likelihood, impact, owner, and a trigger. Status is variance "
        "against the plan, not a diary.\n\n"
        "Worked example\n"
        "A weekly status: goal, done, next, risks, decisions needed. Send it even when "
        "nothing is on fire.\n\n"
        "Common failure modes\n"
        "Hidden buffers that explode. Risk logs nobody reads. Green status on a red "
        "critical path.\n"
    ),
    "agile": (
        "Core ideas\n"
        "Inspect and adapt. Scrum events have a purpose: plan, daily, review, retro. "
        "Flow metrics: throughput, cycle time, WIP. Facilitation is making the team "
        "decide, not deciding for them. Impediments are owned, dated, and visible.\n\n"
        "Worked example\n"
        "A retro with one change, an owner, and a check next sprint. Not twelve stickies "
        "and no difference.\n\n"
        "Common failure modes\n"
        "Standups as status theater. Story points as commitments to finance. Skipping "
        "review because the demo is embarrassing — that is the point.\n"
    ),
    "architecture": (
        "Core ideas\n"
        "Quality attributes drive structure: latency, durability, cost, operability, "
        "team boundaries. Integration: sync vs async, contracts, versioning, failure. "
        "NFRs are testable. Draw the sequence for the failure, not only the happy path.\n\n"
        "Worked example\n"
        "Translate 'must work if billing is down' into: queue payments, timeout, user "
        "messaging, replay, and a dashboard.\n\n"
        "Common failure modes\n"
        "Framework-first diagrams. Ignoring team ownership. Eternal compatibility with "
        "no deprecation policy.\n"
    ),
    "networking": (
        "Core ideas\n"
        "Layers: link, IP, transport, app. TCP is reliable ordered bytes; UDP is datagrams. "
        "Routing moves packets toward a prefix. DNS names to addresses. TLS authenticates "
        "and encrypts. Firewalls match 5-tuples. Observability is counters, flows, and "
        "packet captures when you must.\n\n"
        "Worked example\n"
        "User cannot reach an API: DNS, TCP handshake, TLS, HTTP status, path MTU, security "
        "group, NACLs, the app log. Write the layer that failed.\n\n"
        "Common failure modes\n"
        "Blaming the application for a TCP reset. Overlapping subnets. No diagram of "
        "trust boundaries.\n"
    ),
    "support": (
        "Core ideas\n"
        "Reproduce, isolate, document, communicate. A ticket is a record for the next "
        "human. Identity, device, recent change, error text. Under pressure, narrate what "
        "you know and what you will do next.\n\n"
        "Worked example\n"
        "Cannot print: local vs network, driver, queue, permissions, last working time. "
        "Give the user a time bound even if the bound is 'I will update in 30 minutes'.\n\n"
        "Common failure modes\n"
        "Closing with 'please reboot' and no note. Jargon to a scared customer. Skipping "
        "the recent-change question.\n"
    ),
    "sales": (
        "Core ideas\n"
        "Discovery before demo. Qualification is fit, urgency, authority, and a next "
        "step. Objections are information. A POC has success criteria written down. "
        "Forecast is evidence, not hope.\n\n"
        "Worked example\n"
        "A discovery call agenda: their workflow, current tool, cost of status quo, "
        "decision process, date. Demo only the two screens that match.\n\n"
        "Common failure modes\n"
        "Feature dump. Discounting before value. Pipeline that is actually a mailing list.\n"
    ),
    "marketing": (
        "Core ideas\n"
        "Audience, message, channel, offer, measurement. A campaign has a hypothesis. "
        "SEO is technical access plus content that matches intent plus earned links. "
        "Lifecycle is not one blast. Attribution is messy; pick a decision-grade model "
        "and know its bias.\n\n"
        "Worked example\n"
        "One landing page, one audience, one CTA, one primary metric, a kill date.\n\n"
        "Common failure modes\n"
        "Vanity traffic. Keyword stuffing. Channel tactics with no message.\n"
    ),
    "finance": (
        "Core ideas\n"
        "Statements: income, balance sheet, cash flow. Drivers vs totals. A model is "
        "assumptions you can change. Variance is actual minus plan, with a story. "
        "Partnering is translating a business question into a number and a decision.\n\n"
        "Worked example\n"
        "Gross margin dropped: price, mix, cost, returns. Show the bridge, not a red cell.\n\n"
        "Common failure modes\n"
        "Hockey-stick revenue with linear costs. Precision as a substitute for accuracy. "
        "Models nobody else can open.\n"
    ),
    "accounting": (
        "Core ideas\n"
        "Debits and credits, control accounts, reconciliations, close calendar, cut-off. "
        "A recon proves the subledger to the GL. Supporting docs beat memory. Standards "
        "tell you recognition, not just the spreadsheet layout.\n\n"
        "Worked example\n"
        "Bank rec: book balance, outstanding checks, deposits in transit, bank fees, "
        "true cash. Every plug has an owner.\n\n"
        "Common failure modes\n"
        "Force-balancing. Booking to suspense forever. Closing without a checklist.\n"
    ),
    "hr": (
        "Core ideas\n"
        "Employment law is jurisdiction-specific; do not improvise discipline. Employee "
        "relations is documentation plus fairness. Performance systems need calibrated "
        "expectations. HR data is sensitive: access, retention, purpose limitation.\n\n"
        "Worked example\n"
        "A performance note: observed behavior, date, impact, support offered, next review. "
        "No labels without examples.\n\n"
        "Common failure modes\n"
        "Slack advice as policy. Inconsistent exceptions. Reports with identifiable data "
        "in a shared drive.\n"
    ),
    "recruiting": (
        "Core ideas\n"
        "Role scorecard, sourcing channels, structured interviews, candidate experience, "
        "offer math. Time-to-fill without quality is a vanity metric. Technical literacy "
        "means you can explain the work to a candidate without faking it.\n\n"
        "Worked example\n"
        "A scorecard with four competencies, questions, and what good looks like. Every "
        "interviewer uses it.\n\n"
        "Common failure modes\n"
        "Ghosting. Moving the bar after the debrief. Selling a job the team does not have.\n"
    ),
    "operations": (
        "Core ideas\n"
        "Demand, supply, inventory, lead time, service level, cost to serve. Forecasts "
        "are wrong; the question is the buffer and the review cadence. Vendors have SLAs "
        "and exit plans. Process improvement needs a baseline.\n\n"
        "Worked example\n"
        "A SKU with rising stockouts: check forecast, supplier OTIF, safety stock, and "
        "whether the promo was in the plan.\n\n"
        "Common failure modes\n"
        "Excel as the system of record with no owner. Optimizing unit cost while freight "
        "explodes. KPI theater.\n"
    ),
}


_FAMILY_DRILLS: dict[str, str] = {
    "algorithms": (
        "Drills\n"
        "- Implement array list, hash map, and binary heap from scratch once.\n"
        "- Solve 15 problems: arrays, hashing, two pointers, trees, graphs, heaps. "
        "For each, write the invariant in one sentence before code.\n"
        "- Time yourself explaining Dijkstra to a rubber duck in five minutes.\n"
    ),
    "git": (
        "Drills\n"
        "- Clone, branch, commit, open a PR, address a review comment, squash, merge.\n"
        "- Practice rebase vs merge on a throwaway repo and write when you would use each.\n"
        "- Recover a deleted branch with reflog once so you are not afraid of it.\n"
    ),
    "testing": (
        "Drills\n"
        "- Add tests for one pure function including a failing case.\n"
        "- Write one integration test that hits a real test database or HTTP stub.\n"
        "- Quarantine or delete one flaky test instead of rerunning the pipeline.\n"
    ),
    "system_design": (
        "Drills\n"
        "- Sketch a product you use: clients, edge, app, data, async, ops.\n"
        "- Estimate storage and QPS on paper. Show units.\n"
        "- Write the failure mode if the cache is wrong for 10 minutes.\n"
    ),
    "distributed": (
        "Drills\n"
        "- Read one public incident report and name the amplification loop.\n"
        "- Design an idempotent webhook handler on paper.\n"
        "- List what 'at least once' means for your last project.\n"
    ),
    "frontend": (
        "Drills\n"
        "- Rebuild a simple landing page with semantic HTML and no framework.\n"
        "- Tab through it. Fix what you cannot reach.\n"
        "- Measure LCP on a slow 3G profile once.\n"
    ),
    "javascript": (
        "Drills\n"
        "- Write a typed function that fetches JSON and handles abort.\n"
        "- Build a list with loading, empty, error, and retry.\n"
        "- Remove one any and replace it with a real type plus a runtime check at the boundary.\n"
    ),
    "accessibility": (
        "Drills\n"
        "- Run a page with a keyboard only. Write every trap.\n"
        "- Check names of icon buttons.\n"
        "- Fix one contrast failure and one missing label.\n"
    ),
    "databases": (
        "Drills\n"
        "- Model a blog: users, posts, tags. Write the create SQL.\n"
        "- Add the index your list query needs and prove it with EXPLAIN.\n"
        "- Write a transaction that cannot double-spend a remaining quantity.\n"
    ),
    "python": (
        "Drills\n"
        "- Script that reads a file, transforms rows, writes output, exits nonzero on bad input.\n"
        "- Add pytest for the transform.\n"
        "- Pin dependencies and run it in a fresh venv.\n"
    ),
    "ml": (
        "Drills\n"
        "- Train a baseline (logistic regression or tree) before a neural net.\n"
        "- Make a leakage check: time split vs random split, compare metrics.\n"
        "- Write why the metric matches the decision.\n"
    ),
    "llm": (
        "Drills\n"
        "- Build a 20-example eval set with expected answers.\n"
        "- Compare with/without retrieval on those examples.\n"
        "- Log prompts and costs for one day of experiments.\n"
    ),
    "data": (
        "Drills\n"
        "- Define one metric with grain, filters, and owner.\n"
        "- Draw the pipeline from event to dashboard.\n"
        "- Add a freshness check that pages a human.\n"
    ),
    "statistics": (
        "Drills\n"
        "- Compute a confidence interval by hand once for a proportion.\n"
        "- Design an A/B test: metric, MDE, sample size, stop rule.\n"
        "- Find one chart in the wild that implies causality it does not have.\n"
    ),
    "devops": (
        "Drills\n"
        "- Dockerize a small app and run it locally.\n"
        "- Add a CI workflow that runs tests on pull request.\n"
        "- Write a rollback instruction in one paragraph.\n"
    ),
    "linux": (
        "Drills\n"
        "- Use journalctl, ss, df, top to inspect a machine.\n"
        "- Write a systemd unit for a toy process.\n"
        "- Trace a TCP connection with ss or tcpdump once.\n"
    ),
    "cloud": (
        "Drills\n"
        "- Draw your account/org structure and blast radius.\n"
        "- Enable a billing alarm.\n"
        "- Write an IAM policy that allows one action on one resource.\n"
    ),
    "security": (
        "Drills\n"
        "- Threat-model one feature: assets, actors, entry points, controls.\n"
        "- Find one dependency with a known CVE and decide patch vs accept.\n"
        "- Turn a password in config into a secret manager reference in a sample app.\n"
    ),
    "product": (
        "Drills\n"
        "- Write a one-page spec with non-goals and a kill metric.\n"
        "- Rank five ideas with one framework and show the discarded ones.\n"
        "- Run a 15-minute stakeholder update with a decision log.\n"
    ),
    "design": (
        "Drills\n"
        "- Rebuild a settings screen with a real component set.\n"
        "- Document empty, loading, error, and overflow.\n"
        "- Do a critique with two other people and list what changed.\n"
    ),
    "research": (
        "Drills\n"
        "- Write a discussion guide with no leading questions.\n"
        "- Interview one person and extract five observations, not solutions.\n"
        "- Cluster notes into opportunities with evidence tags.\n"
    ),
    "qa": (
        "Drills\n"
        "- Write 10 test cases for a login form including lockout.\n"
        "- File a bug with a reliable repro.\n"
        "- Script one happy-path browser test.\n"
    ),
    "mobile": (
        "Drills\n"
        "- Implement offline read cache for one screen.\n"
        "- Measure cold start.\n"
        "- Walk through store listing, privacy, and screenshot requirements on paper.\n"
    ),
    "management": (
        "Drills\n"
        "- Run a 1:1 with an agenda the other person wrote.\n"
        "- Give one piece of feedback using situation-behavior-impact.\n"
        "- Break a project into milestones with owners and dates.\n"
    ),
    "business_analysis": (
        "Drills\n"
        "- Interview an operator and draw the as-is process.\n"
        "- Write five testable requirements.\n"
        "- Define one KPI with formula and source system.\n"
    ),
    "writing": (
        "Drills\n"
        "- Rewrite a confusing error message.\n"
        "- Document a CLI or API endpoint with an example.\n"
        "- Get a review from someone who has never seen the product.\n"
    ),
    "project": (
        "Drills\n"
        "- Build a one-page plan with risks and owners.\n"
        "- Send a status that a skip-level could read.\n"
        "- Run a risk review and retire one stale risk.\n"
    ),
    "agile": (
        "Drills\n"
        "- Facilitate a retro that produces one change.\n"
        "- Chart cycle time for a week of work.\n"
        "- Make the impediment board visible and dated.\n"
    ),
    "architecture": (
        "Drills\n"
        "- Translate three NFRs into tests or alerts.\n"
        "- Draw a sequence diagram for timeout and retry.\n"
        "- Write a versioning policy for one API.\n"
    ),
    "networking": (
        "Drills\n"
        "- Explain a packet path from laptop to a public API.\n"
        "- Capture a failed TLS handshake once in a lab.\n"
        "- Draw trust boundaries for a simple VPC.\n"
    ),
    "support": (
        "Drills\n"
        "- Practice a ticket writeup from a messy chat transcript.\n"
        "- Time-box an investigation and update the user.\n"
        "- Build a personal runbook for the top three issues.\n"
    ),
    "sales": (
        "Drills\n"
        "- Write five discovery questions you will actually ask.\n"
        "- Role-play one objection: price, timing, competitor.\n"
        "- Score a pipeline of 10 deals with evidence, not hope.\n"
    ),
    "marketing": (
        "Drills\n"
        "- Write a campaign one-pager with one metric.\n"
        "- Do keyword intent mapping for five queries.\n"
        "- Kill or double down on a channel using last month's data.\n"
    ),
    "finance": (
        "Drills\n"
        "- Build a three-statement sketch for a simple business.\n"
        "- Write a variance narrative for one line item.\n"
        "- List the five drivers of cash this quarter.\n"
    ),
    "accounting": (
        "Drills\n"
        "- Record 10 sample journals and produce a trial balance.\n"
        "- Reconcile a fake bank statement.\n"
        "- Draft a close checklist with owners.\n"
    ),
    "hr": (
        "Drills\n"
        "- Rewrite a policy paragraph in plain language.\n"
        "- Practice documenting a conversation with facts only.\n"
        "- Map which HR reports contain identifiable data.\n"
    ),
    "recruiting": (
        "Drills\n"
        "- Write a scorecard for one role.\n"
        "- Source 10 profiles and record the channel.\n"
        "- Draft a candidate update email that is honest about timing.\n"
    ),
    "operations": (
        "Drills\n"
        "- Pick one SKU or vendor and write the service-level and cost-to-serve.\n"
        "- Chart stockouts vs inventory for a month.\n"
        "- Document a process with the actual systems, not the org chart.\n"
    ),
}
