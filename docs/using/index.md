# Using Research Software Tools

The application turns one Research Software Management (RSM) JSON document into editable
metadata, individual generated files, or a complete repository.

## Workspaces

A workspace holds one RSM document. Create an empty workspace, or paste or upload existing RSM
JSON. Both produce a URL like `/w/{id}` that you can return to or share.

Workspaces are temporary: by default they expire 12 hours after the last activity, and reading,
editing, or generating from one restarts that clock. The URL is unguessable, but it is not an
authorization mechanism. Do not put secrets or directly identifying patient data in a workspace,
and download your RSM JSON before finishing.

## Editing metadata

The form is generated from the same RSM Schema the server validates. Edits save automatically a
moment after you stop typing; the indicator beside the title shows whether the current version has
reached the server.

- **Form** and **Raw JSON** are two views of the same document. Switching views carries edits
  across.
- **Fields** narrows the form to metadata used by one tool. Hidden metadata is not deleted.
- Search finds fields by their schema title and description.
- A validation notice links to the first affected field.

## Generating files and repositories

Tools are grouped by what they produce:

| Group | Produces |
| --- | --- |
| Entire repositories | A complete project scaffold as a ZIP, or created directly on GitHub |
| Metadata files | `rsm.json`, `codemeta.json`, `CITATION.cff`, `biotools.json`, and `.zenodo.json` |
| Documentation files | `README.md` plus separate overview, user, deployment, developer, reference, and legal Markdown pages |
| Community files | Repository policies and templates such as `LICENSE`, `CONTRIBUTING.md`, issue forms, and pull-request templates |

Open a tool's information button to see the metadata it reads and jump to a listed
field. Use search to filter the tool catalogue. Documentation pages are separate
Markdown downloads. Complete repository templates select pages and configure their
documentation builder.

Generated content uses the current RSM document. A tool's information panel lists
the fields used for its output.

Repository scaffolds are rendered with Copier from the configured revision of
[LUMC-DCC/rs-repo-templates](https://github.com/LUMC-DCC/rs-repo-templates). Choose the generic,
Python, or R scaffold for the repository. Generic is the default and provides a
language-neutral structure. The generated `.copier-answers.yml` records the answers
needed by Copier's update workflow. GitHub
publishing appears only when the deployment has configured it; see
[GitHub publishing](../deployment/github.md).

## Keep your result

Redis is temporary workspace storage, not a permanent database. Download `rsm.json`, generated
files, or the repository before the workspace expires. Creating a GitHub repository returns a
direct link to the result.
