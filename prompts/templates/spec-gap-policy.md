# Spec Gap Policy

When identifying spec gaps, only include gaps that **materially affect test coverage**.

## Include as a spec gap

- Missing or empty response schemas for status codes that the endpoint declares (especially 2xx and 4xx)
- Undocumented or implicit authentication requirements
- Parameters with no type, format, or constraint information where that information is needed to write a meaningful test
- Missing error response definitions (4xx / 5xx) for operations that can clearly fail
- No examples for complex or deeply nested request bodies
- Contradictory information between the path-level and operation-level definitions
- Missing `operationId` when it would be needed to link tests to code

## Do not flag as a spec gap

- Missing `description` for fields whose names are self-explanatory
- Stylistic or naming convention issues
- Missing `example` values for simple scalar fields (string, integer)
- Cosmetic or formatting inconsistencies
- Business logic that the spec is not expected to document

## Tone

State gaps factually and briefly. Do not suggest how to fix them unless the fix is directly relevant to the test case being written.
