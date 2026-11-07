# MCP

This directory is an intentional boundary, not a pending phase. No governed MCP client, server or transport is implemented. Tool access goes through `apps/tool_gateway` with static registration and tenant allowlists only; network access, MCP negotiation and remote tool execution are explicit non-goals for this repository.
