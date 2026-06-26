"""Agentic tool-use loop (agent_mode="agentic").

Native AsyncAnthropic manual tool-use loop that coexists with the legacy PAE
graph behind the `agent_mode` flag. `runner.run_agentic` mirrors
`graph.run_agent`'s signature + 9-event SSE contract; the PAE path is untouched.
"""
