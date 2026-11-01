# AI use - HW8

## 1. What I used AI for and what I did myself

I used Claude to debug problems and understand the Kafka parts. I gave it the HW8 brief and the two demo projects and used it to help write the listing worker and FastAPI wrapper, the Docker setup, the Planner, Writer and Reviewer, the failure tests, the verify script and the report layout.

I chose to continue in my rental listings repo, ran the system on my laptop (Docker and Ollama), checked the outputs and screenshots against the brief, and did the final Git push and tag myself.

## 2. Something the AI got wrong

- The first merged Part 1 log was out of order. The worker's "received" line appeared before the API's "sent" line, because the API only logged after Kafka acknowledged the send, and lines with the same millisecond were sorted by text.
- The first Part 2 screenshots were wrong. The Planner image showed the send_question window because the script captured the screen without bringing the Planner window to the front.

## 3. How the problems were found

- Reading the sequence log line by line: a message cannot be received before it is sent.
- Opening each screenshot and comparing the window title with the expected terminal.

## 4. What was changed

- The API and worker now log right before sending, timestamps use microseconds, and the merge sorts only on the timestamp. The sequence now reads send, receive, process, reply, client response.
- The screenshot script minimizes and restores each window before capturing it, and each window is maximized before it prints anything, so the output starts at the top.
