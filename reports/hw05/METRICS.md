## Part 5 agent evaluation

The agent loop uses execute_tool as its single tool entry point. The offline tests verified valid tool calls, invalid inputs, the safety block, unknown tools, and the max_steps stopping rule.

The four planned scenarios were apartment search, listing detail lookup, category summary, and a private-information request. Ollama was installed, but the local generation requests timed out. Therefore, the deterministic MockModel output was kept as the reproducible agent evidence. The private-information request was rejected by the safety rule instead of being executed.