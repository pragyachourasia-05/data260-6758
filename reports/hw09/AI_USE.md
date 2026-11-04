# AI use - HW9

## 1. What I used AI for and what I did myself

I used Claude to debug problems and understand the caching and evaluator parts. I gave it the HW9 brief and the two demo files and used it to help write the counter, the semantic cache, the sweep script, the Answering and Evaluator agents, the verify script and the report layout.

I ran everything on my laptop (Docker, Redis, MySQL and Ollama), checked the outputs and screenshots against the brief, and did the final Git push and tag myself.

## 2. Something the AI got wrong

- The first Evaluator rejected a correct answer. "$1950, and the property type..." failed because the number check treated the comma after the number as part of a bigger number.
- The first dataset script left listings 107-109 out of the reference data, so the Answering Agent was told those listings did not exist.
- The next Evaluator was too lenient. It passed answers with invented details such as "studio apartment" and flat claims such as "There is no gym", so training showed 16 out of 16 correct.
- One test value was wrong: 4 roommates splitting $3450 is $862.50, but the script rounded it to $862.

## 3. How the problems were found

- Reading the attempt trail in the output, where a correct answer was marked REVISE.
- A perfect training score looked wrong, so I read every answer in full and compared them with the records.
- Checking the expected values printed by the dataset script.

## 4. What was changed

- The number check now only rejects a comma when another digit follows it.
- Every listing a question names is now in the reference data.
- The Evaluator now rejects invented property details, flat yes or no claims on unsupported questions and answers that deny an existing listing.
- The roommate question now uses 3 people, which divides evenly.
- All of these were done before the final test run was used in the report. The first lesson also failed validation, so I revised it using the validation answers and ran the test again. The first test run is saved as `raw/part4_test_v1.json`.
