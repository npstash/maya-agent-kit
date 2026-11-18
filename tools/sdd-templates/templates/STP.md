# Software Test Plan (STP) — [system name]

The complete list of the tests of the project, grouped by category. Each test has a description and the item that it verifies. The description tells what the test does, what it checks, and the expected behaviour. Do not repeat the name of the test. The description has no length limit. The item that a test verifies is:

- Unit test and component test: the API, an operation of section 6.1 or an interface of section 6.2 of DESIGN.
- Functional test, integration test, QAS test and manual test: a requirement of SRS or a scenario of QAS.

Identify an automatic test by its path and its name, e.g. `components/api/tests/test_orders.py::test_order_is_saved`. Identify a manual test by an ID `M-[NN]`. Mark a test that is planned but not written with **MISSING:**. A project with no SRS has no functional test and no integration test.

## 1. Unit tests

Tests of one function or one class, with test doubles for each other part.

| Test | Description | API |
| --- | --- | --- |
| [test] | [description] | [operation or interface] |

## 2. Component tests

Tests of one component or one container through its API, with test doubles for its dependencies.

| Test | Description | API |
| --- | --- | --- |
| [test] | [description] | [operation or interface] |

## 3. Functional tests

Tests of a requirement through the interfaces of the system, with test doubles for the external systems.

| Test | Description | Requirement |
| --- | --- | --- |
| [test] | [description] | [REQ-NNN] |

## 4. Integration tests

Tests of the system with the real code or the real service of a direct dependency.

| Test | Description | Requirement or QAS |
| --- | --- | --- |
| [test] | [description] | [REQ-NNN or QAS-NNN] |

## 5. QAS tests

Tests of the response measure of a quality attribute scenario.

| Test | Description | QAS |
| --- | --- | --- |
| [test] | [description] | [QAS-NNN] |

## 6. Manual tests

Tests that a person does. Write the full procedure: the preconditions, then numbered steps. Give the expected result of each step.

| Test | Description | Requirement or QAS |
| --- | --- | --- |
| [M-01] | Preconditions: [state of the system]. 1. [action] Expected: [result]. 2. [action] Expected: [result]. | [REQ-NNN or QAS-NNN] |
