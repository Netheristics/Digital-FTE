---
name: summarize-ticket
description: >-
  Turns one support ticket into a structured five-section handoff summary for
  tier-2 escalation or teammate review. Use this skill whenever the user asks
  for a handoff note, wants to TL;DR a thread, asks "what's the status and
  next step", requests a ticket summary for a colleague, or says variants like
  "give me the rundown on this ticket", "what do I need to pass this off",
  "condense this for the next agent", or "write up the current state for
  handoff". Fire on any request that wants one ticket's current state distilled
  into a short structured brief — even if the user never uses the word
  "summarize". Do NOT use this skill when the user is drafting a reply to a
  customer, triaging a batch of tickets, writing macros, or performing any task
  that is not specifically about condensing one ticket's state into a handoff.
---

# Summarize Ticket

You are turning one support ticket into a short, structured handoff summary. The
audience is a tier-2 agent or teammate who knows nothing about this ticket and
needs to pick it up cold. Write for someone scanning quickly, not reading deeply.

## Output format

ALWAYS use these five sections, in this order. If you don't have information for
a section, write "Not yet determined" or "No escalation needed" — never skip a
section.

### 1. Issue Summary
One or two sentences: what broke, what the customer wants, and the product area.
Lead with the symptom, not the history.

### 2. Customer Context
Who the customer is (name or org, plan/tier if relevant), how long they've been
waiting, and any urgency signals (deadline, revenue impact, multiple contacts).
Omit this section if the ticket has no customer-identifying information.

### 3. Current State
Where things stand right now. Is the issue reproduced? Is a fix deployed? Is
there a workaround in place? What was the last thing that happened?

### 4. Actions Taken
Numbered list of what has been tried or completed so far, with outcomes.
Include the agent names or team members involved if visible in the thread.
Keep it factual — outcomes, not intentions.

### 5. Recommended Next Step
One clear sentence on what the next agent should do first. If escalation is
needed, say where. If the ticket is blocked on the customer, say so. If there's
a known fix waiting for confirmation, say that.

## Tone and length

- Total length: 150–300 words. Shorter is better.
- Write in plain, direct language. No filler, no pleasantries, no "hope this
  helps".
- Use bullet points inside sections only when listing multiple items.
- Do not include a greeting, sign-off, or meta-commentary about the summary
  itself.

## Edge cases

- **Multiple issues in one ticket:** Pick the primary issue for the summary. If
  secondary issues are entangled, mention them briefly in Current State but
  don't let them dilute the handoff.
- **Ticket with no activity yet:** State that, in Current State. Fill in what
  you can from the customer's initial message.
- **Ticket already resolved:** Use Current State to note the resolution and
  Actions Taken to show the path. Recommended Next Step becomes "Confirm with
  customer" or "Close if no response within SLA".

## Example

**Input:** A customer reported that their webhook deliveries are failing with
502 errors since yesterday morning. They're on the Enterprise plan. An agent
checked the logs, found a DNS resolution timeout on the customer's endpoint, and
suggested they whitelist the webhook IP range. Customer hasn't responded in 18
hours.

**Output:**

### 1. Issue Summary
Webhook deliveries returning 502 due to DNS resolution timeout on the customer's
endpoint. Enterprise account.

### 2. Customer Context
Enterprise plan. Reported 18 hours ago. No response to suggested fix in 18
hours.

### 3. Current State
Issue reproduced. DNS timeout confirmed in delivery logs. Workaround suggested
(IP whitelisting) awaiting customer action.

### 4. Actions Taken
1. Agent checked delivery logs — DNS resolution timeout on customer endpoint.
2. Agent suggested whitelisting webhook IP range. Awaiting customer response.

### 5. Recommended Next Step
Follow up with customer on IP whitelisting. If no response in 24h total, flag
as at-risk for SLA breach.
