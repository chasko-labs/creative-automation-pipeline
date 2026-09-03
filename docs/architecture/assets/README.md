# architecture diagram assets

pre-rendered PNGs of the mermaid diagrams in `../SYSTEM-OVERVIEW.md`, for viewers that do not render mermaid inline.

- the source of truth is the fenced ```mermaid blocks in `SYSTEM-OVERVIEW.md` — these PNGs are generated FROM that source, never edited by hand
- rendered via mermaid.js in headless chromium (playwright), deviceScaleFactor 2 for retina-legible text
- to regenerate after editing the doc: extract each mermaid block, render through mermaid.run(), screenshot the produced svg. mermaid-cli (mmdc) also works: `mmdc -i SYSTEM-OVERVIEW.md -o assets/diagram.png`

| file                    | diagram                                              |
| ----------------------- | ---------------------------------------------------- |
| 01-system-context.png   | level 0 system context — actors + external services  |
| 02-api-surface.png      | three FastAPI apps + endpoints                       |
| 03-data-schema-er.png   | DynamoDB tables + AssetRef + vector record ER        |
| 04-infra-deploy.png     | CloudFormation footprint                             |
| 05-security-posture.png | encryption, IAM, exposure, secrets, model governance |
| 06-cicd-flow.png        | CodeBuild fail-fast gate sequence                    |

each diagram is validated for syntax at render time — a mermaid parse error fails the render, so a committed PNG means the block parsed clean.
