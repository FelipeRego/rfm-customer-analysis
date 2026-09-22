Your customer data has two halves.

The numbers: when they last bought, how often, how much they spend.

And the words: what they actually wrote to you. Support tickets. Survey replies. The email to their account manager.

Almost all customer analytics uses the first half and quietly ignores the second.

This week I found out what that costs.

---

**The blind spot**

RFM analysis scores customers on Recency, Frequency and Monetary value, then sorts them into groups like Champions, At Risk and Lost. It is a good method. I use it constantly.

But it only reads behaviour.

Which means it cannot see a customer who has decided to leave and simply hasn't stopped buying yet.

That customer scores 5 out of 5 on everything. Right up until the day they are gone.

---

**What I added**

I used Jev, a model that reads text and answers specific questions with numbers rather than paragraphs.

For every customer message, it answered five:

→ Are they signalling they want to leave?
→ How serious is the problem they describe?
→ What is driving it — service, price, the product, a competitor?
→ Could we still keep them if we acted this fortnight?
→ Does this need a person, or will a campaign do?

No training data. No labelled examples. No model to retrain. You write the question in plain English and get a number back that your code can use.

---

**What it found**

5 customers who looked completely healthy on every purchase measure, while telling us they were unhappy.

8.5% of total portfolio value. Four of the five had an unresolved service complaint sitting there.

RFM ranked every one of them as safe. It had no way not to.

---

**The part I didn't expect**

"Angry" and "leaving" are not the same signal.

An unresolved service failure scored 0.90 on severity — and only 0.22 on intent to leave.

That is correct. A furious customer complaining TO you hasn't left. They are giving you a chance.

Meanwhile "please close my account" scored the exact inverse: 0.78 on leaving, 0.14 on severity. Calm, polite, and final.

Two different problems. Two different responses. Most churn scores blend them into one number and lose both.

---

**And it says when it isn't sure**

For 2 of 8 customer groups, several actions were equally defensible — so it said so, instead of picking one and sounding confident.

Those went to a person for review rather than onto a recommendation slide.

A model that admits uncertainty is far more useful than one that guesses well.

---

**The rule I held to throughout**

The model never touches a number.

Every score, every threshold, every dollar figure stays in ordinary code. The model reads meaning. The arithmetic stays where it can be checked, argued with, and corrected.

That is the whole idea. Not replacing the analysis — reading the half of your data the analysis was never able to see.

Code, charts and the full deck: https://github.com/FelipeRego/rfm-customer-analysis

(Demonstration dataset; the customer messages are synthetic.)

What is your customer base telling you in words that your dashboard cannot see?

#CustomerAnalytics #CustomerExperience #CustomerRetention #Churn #RFMAnalysis #CRM #MarketingAnalytics #VoiceOfCustomer
