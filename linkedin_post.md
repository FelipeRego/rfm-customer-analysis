I rebuilt my RFM customer analysis this week.

The most useful thing that happened was discovering how much of it was wrong.

Three things I had shipped and believed:

**1. My Customer Lifetime Value formula was meaningless.**

I used the textbook one: average order value × frequency × lifespan × margin.

But average order value IS total spend divided by frequency. The frequency terms cancel. Every CLV I had calculated was just total spend × 0.6 — a rescaling of a column I already had.

A customer who spent $1,000 across ten orders scored identically to one who spent $1,000 once and never came back.

**2. My output file did not match my own code.**

20 of 100 customers were sitting in the wrong segment. Every chart and every slide downstream had been built on that file.

**3. My documentation described the segmentation as a table of rules.**

It is actually an ordered chain, where earlier rules silently override later ones. 13 of the 25 possible score combinations matched more than one "rule".

---

Then I added the thing RFM structurally cannot do.

RFM reads behaviour: how recently, how often, how much. Which means it is blind — by construction — to a customer who has decided to leave but has not stopped buying yet. They score 5/5/5 right up until they are gone.

So I had a model read what customers actually wrote, and score every message on five things: are they signalling they will leave, how serious is the problem, what is driving it, can we still save them, and does this need a person.

It surfaced 5 customers who looked perfectly healthy on every purchase measure while telling us they were unhappy. 8.5% of portfolio value.

---

And then it caught a mistake in MY logic.

It scored an unresolved service failure as HIGH severity (0.90) but LOW intent to leave (0.22).

I assumed that was a miss. It was not. A furious customer complaining TO you has not left — they are giving you a chance. Meanwhile "please close my account" scored the exact inverse: 0.78 intent, 0.14 severity.

But my scoring blended those two into a single risk number. Which filed a top-tier customer, sitting on an unresolved failure, as safe.

That is precisely the customer who leaves without warning.

**"Angry" and "leaving" are not the same signal. Average them and you hide both.**

---

What I keep relearning: the value is not in going faster.

It is in having something check the work you were too confident to check yourself.

Three of those four findings were bugs I wrote, shipped, and would never have gone looking for.

Code is public, including the charts and the deck: https://github.com/FelipeRego/rfm-customer-analysis

(Demonstration dataset, and the customer messages are synthetic — but every one of those bugs was real.)

What is sitting in your pipeline that you have never re-derived?

#CustomerAnalytics #RFMAnalysis #CustomerLifetimeValue #DataQuality #CustomerSegmentation #Churn #CRM #MarketingAnalytics #Analytics
