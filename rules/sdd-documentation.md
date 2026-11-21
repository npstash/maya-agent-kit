# SDD documentation

The SDD (SW Development Documents), their process and the variants of the process are in
[workflow.md](../tools/sdd-templates/workflow.md).

- Apply the workflow only to a project with an `sdd/` folder.
- In a project with `sdd/`, the decision log of the project is `sdd/ADL.md`.

## Templates

The templates of the SDD documents are in [templates](../tools/sdd-templates/templates/).

- Each document can only contain required sections of its template. Do not add, rename or move a section of the template.
- Do not copy the guidance of a template into a document, e.g. "How to write a requirement", the examples and the placeholders.
- You can add a subsection to a section of the template. It must add details or group the content of its parent, and stay in the scope of its parent.
- If content fits no section of the template, ask the user. Change the structure only with the explicit approval of the user.

## Target environment

- Write "target host", "target environment" or "target runtime" for the deployment target. Do not write a host name.
- Describe the target environment in the section "Deployment" of `DESIGN.md`: the current hardware, OS, container
  runtime and devices.
- For a measurement or a verification, give the hardware, not a host name.

## Behaviour in DESIGN.md

- Describe each behaviour at the API that shows it: section 6.1 for a container, section 6.2 for an internal API of a component.
- Describe a behaviour outside the API in one case only: an API of another design declares the operation, this implementation adds behaviour that it does not specify, and no internal API covers that behaviour.
- If a behaviour fits no API, consult user.
- When more than one implementation serves an API, define each behaviour that a client sees in the design of the API, also the failures. The design of each implementation refers to it and adds only what the API leaves open.
- Use a flow in section 7 for a behaviour that is complex, important or affects many API items. Describe it there in detail. The API items refer to the flow.

## Requirements and dependencies

- The project with the SRS is the root of the product requirements. Cover each requirement in its DESIGN.md or in an API of a direct dependency.
- Check that the APIs of the dependencies of a project give each behaviour that its own APIs need. Check the dependencies of each dependency in the same way.

## Test plan

- Keep `sdd/STP.md` in each project with an `sdd/` folder, in the full variant and in the service variant.
- List each test of the project in it, in the category of the test, with its description and the item that it verifies.
- Write in each description what the test does, what it checks and the expected behaviour. Read the code of the test for it. Do not repeat the name of the test.
- Write the full procedure of each manual test: the preconditions, the numbered steps and the expected result of each step.
- When you add, change or remove a test, update `STP.md` in the same commit.

## Values

- Write each value (a limit, a time, a default) as an uppercase name, e.g. `RETRY_COUNT`.
- Define each name with its default in the "Default values" section of one SDD document: the
  first document that uses the value.
- In other documents, use the same name. Do not define it again. Refer to the document that
  defines it.
- In the text, write the default and the unit in parentheses after the name, e.g.
  `RETRY_COUNT (3)`, `SOME_TIMEOUT (1000 ms)`. Do not do this in the "Default values" table
  and in code blocks.
- When a default changes, update each occurrence of the name.

## Components

This section applies only to a project that keeps its components in separate folders. If
the repository has a rule that defines components, use its definition.

- Do not apply the workflow to a component. Update the SDD of the parent project.
- Create an `sdd/` folder in a component only with the explicit confirmation of the user.
