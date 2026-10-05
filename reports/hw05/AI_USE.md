# AI use

1. I used an AI assistant to help break the HW5 instructions into smaller tasks, explain Python and Redux errors, and suggest a starting structure for the MCP servers and retry tests. I made the final project choices, ran the commands, checked the results, and captured the evidence myself.

2. One thing I independently checked was the retry experiment. A result that only showed a high success rate would not be enough, so I also checked the raw records and the SQL/tool response patterns to make sure the 0%, 20%, and 50% runs were actually present.

3. I checked the result by reading the generated JSON instead of relying only on the terminal summary. I verified that there were 150 records, 50 for each failure rate, and that a failed first attempt could be followed by a successful retry.

4. I kept the final implementation limited to the required tools and added an offline test runner. This makes the contract tests repeatable without an LLM, an external API, or a database connection.
