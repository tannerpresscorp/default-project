# Contract tests

This directory is reserved for cross-process contracts that do not exist yet. The current platform verifies request/response schemas through unit tests, PostgreSQL integration tests in `tests/integration`, and the Temporal worker tests. Gateway and MCP wire contracts are explicit non-goals until a remote counterpart exists; do not add placeholder tests that imply one.
