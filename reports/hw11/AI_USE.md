# AI use - HW11

## 1. What I used AI for and what I did myself

I used Claude to debug problems and understand the kit, to help write my test fixtures and the report layout, and to type my prompts into my Muse chat and take the screenshots. I chose the watchlist, reviewed the policy and the golden labels before the first run, decided which Muse steps to allow (I did not let Muse use GitHub), checked the results against the brief, and pushed the work myself.

## 2. Something the AI got wrong

- The first plan installed the kit on Muse by cloning my GitHub repo. I did not want Muse to use GitHub, but the clone had already started before I said so.
- The first live run used the kit's count of 5 filings per company; SEC rejects that with HTTP 400, so no 8-Ks were checked.
- The kit read Stooq's bot-check web page as "no big moves" instead of a failed source.

## 3. How the problems were found

- I told it to stop; Muse deleted the cloned folders and I switched to attaching the kit as a zip.
- The first live run said "0 new", which looked wrong, so I asked Muse for the run's trace and saw the 400 error.
- Testing the two URLs from my laptop showed the SEC count rule and the bot-check page.

## 4. What was changed

- The kit is installed from a zip; Muse confirmed both cloned folders were deleted.
- sources.json asks SEC for 10 filings per company.
- watch.py now raises an error when a price reply is not CSV, so a blocked price source shows up as a source error.
- policy.md got an "Old items" rule so the first live run did not alert on months-old filings.
