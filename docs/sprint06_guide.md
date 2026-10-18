# Sprint 6 in simple English

## What we built

BLACKGRID can now **guess who will message whom next**. It looks only at the past and never peeks at the future.

It answers two questions:
1. **New connections:** which two people who have *never* messaged will message in the next 19 days?
2. **Repeat interactions:** which pairs who *have* messaged will message again?

## How it's kept honest

- **No peeking.** To guess the future, the system only uses messages sent before a chosen day. A test changes the
  future messages and checks that nothing used for the guess changes.
- **A sealed exam.** The data is split by time. Early periods are for learning, middle periods for choosing the best
  method, and the last two periods are the exam. The winner is picked and saved *before* the exam answers are opened.
- **Simple methods first.** "Friends in common", "popular people meet popular people", "who was active lately", "how
  recently they talked", and a small learning model. No fancy neural networks were needed.
- **Honest statements.** Every sentence the system writes is checked. It can't say "80% chance" (scores are rankings,
  not probabilities), can't claim causes, and can't claim to predict people it has never seen.

## What we found

- **New connections are hard to guess.** Only about 6 in 100,000 possible pairs actually start talking. The best
  method, "who was active lately", was about 40 times better than random, but still weak.
- **Repeat interactions are easier.** "How recently they talked" and the learning model found about 40% of the right
  pairs near the top (AP 0.40 in one test window).
- **Time helps.** In both tasks, methods that use recent activity beat methods that only use the network's shape.

## Where to see it

```bash
uv run --frozen blackgrid forecast configs/collegemsg_full.json --evaluation runs/sprint6-v1 --task new_pair
```

Open the console and choose **Forecast connections**. The ranked pairs stay on your computer.

## What it doesn't do (yet)

- It doesn't predict anything about brand-new people.
- It doesn't give probabilities.
- It hasn't been tested on other networks.
- The learning model for *new* connections was skipped. It would have needed more than 2 million training examples,
  above the safety limit set before starting.
