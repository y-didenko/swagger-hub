Generate API test cases for the service described below.

## Service: {{service_name}}

## Spec Metadata

```json
{{spec_metadata}}
```

## Endpoints

```json
{{endpoint_summary}}
```

## Security Definitions

```json
{{security_summary}}
```

## Component Schema Names (reference only)

```json
{{schema_summary}}
```

{{chunk_context}}

## Output Constraints

{{output_constraints}}

## Coverage Requirements

Where applicable to the endpoints provided, generate test cases covering:

1. Happy path — successful request with valid inputs
2. Required field validation — missing or empty required fields
3. Invalid input — wrong types, formats, or values
4. Boundary conditions — min/max values, empty collections, max-length strings
5. Authentication / authorization — missing token, expired token, insufficient permissions
6. Response code validation — verify each documented status code is triggered
7. Schema / contract validation — response body matches declared schema
8. Error handling — verify error responses include correct codes and messages
9. Idempotency or duplication — where inferable from the operation semantics
10. Pagination, filtering, sorting — if query parameters suggest these capabilities
11. State transitions or dependencies — if the operation implies a prior or subsequent state

Mark any test case based on inference (not explicitly stated in the spec) with a `notes` field.
