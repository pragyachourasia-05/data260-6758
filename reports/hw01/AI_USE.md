\# AI Use Disclosure



\## 1. What I used an AI assistant for



I used an AI assistant for troubleshooting commands, explaining AWS ECS and ECR deployment steps, reviewing errors, and helping organize the assignment deliverables.



I personally ran the commands, configured AWS, created the Docker image, deployed the ECS service, ran the 40 model experiments, created the token-accounting files, and verified the outputs.



\## 2. One unsuitable AI-produced result



One model output produced vague or awkward tags such as `appliances in-unit laundry` and `Downtown`. These tags were less clear than the original listing attributes.



\## 3. How I detected the problem



I reviewed the Planner, Reviewer, and Finalizer outputs across repeated runs and compared the results against the original rental title and description. I also counted distinct tag sets and summaries programmatically.



\## 4. What I changed and why



I added a Reviewer and Finalizer pipeline, enforced a fixed output schema, and measured repeated outputs at temperatures 0.7 and 0.0. This made the results easier to validate and showed that temperature 0.0 produced much more consistent summaries and tags.

