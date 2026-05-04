# Contributing

Thanks for considering a contribution. This repository hosts a design spec, not a codebase, so contributions look a bit different from a typical OSS project.

## What makes a good contribution

The spec is meant to be improved by people who have implemented something in this space, debugged a related problem in production, or have a principled disagreement with the design. Particularly valuable contributions:

- **Counter-examples.** "Here's a case where the grounding score formulation gives a wrong answer." File an issue with the case.
- **Implementation reports.** "I implemented `rollback` semantics on top of [X], here's what broke." File an issue or open a discussion.
- **Edge-case clarifications.** "What should happen when [obscure interaction]?" File an issue with a proposed answer.
- **Prior-art additions.** "This work in [paper / system] also covers this ground." PRs welcome on the prior-art section.
- **API ergonomics.** "This endpoint shape is awkward for [common case]." PRs against the API surface section welcome.

## What is out of scope for this repo

- Bug reports against the MemArray reference implementation. Those go to [memarray/memarray](https://github.com/memarray/memarray).
- Feature requests for the reference implementation that are not also spec changes. Same — those go to the implementation repo.
- Promotional content for other memory systems. The spec compares systems factually; we will not accept marketing PRs.

## How to file an issue

Use the issue templates. Include:

- The section of the spec you are commenting on (link to the line if possible).
- A concrete example or scenario, not just a theoretical concern.
- If you are proposing a change, the change you would make.

## How to open a PR

For typo fixes and clarifications, just open a PR.

For substantive changes (anything that changes behaviour or semantics), open an issue first to discuss. PRs that change the spec without prior discussion will likely be asked to convert to an issue.

## Code of conduct

Be excellent to each other. The full code of conduct is the [Contributor Covenant v2.1](https://www.contributor-covenant.org/version/2/1/code_of_conduct/).

## License

By contributing, you agree that your contributions will be licensed under Apache 2.0, the same license as the spec itself.
