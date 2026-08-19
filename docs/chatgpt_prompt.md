I need you to produce the complete contents of an `input.md` file for my
local CV builder.

Output raw Markdown only. Do not include an explanation, comments, or code
fences before or after the Markdown.

Front matter rules are strict: use exactly `---` (three hyphens) for both the
opening and closing delimiter. Keep all front matter values as plain text.
In particular, `email` must contain only an email address, not a Markdown link
or `mailto:` link. Put links in the `linkedin`, `website`, and `github` fields.

The file must begin with YAML front matter. These fields are required and
must not be omitted:

- `name`
- `headline`
- `location`
- `email`

These front matter fields are optional:

- `linkedin`
- `website`
- `github`

The CV should normally include these sections, using these canonical headings:

- `## Profile`
- `## Professional experience`
- `## Core capabilities`
- `## Education`

It may also include:

- `## Key Projects`
- `## Additional information`

The builder also accepts common alternatives such as `Summary` for `Profile`,
`Work experience` for `Professional experience`, `Skills` for `Core
capabilities`, and `Qualifications` for `Education`. Prefer the canonical
headings above for consistency.

The PDF template renders `github` and `website` as GitHub and Portfolio links
in the page footer. LinkedIn is rendered as a contact link in the header. Do
not repeat these links in `## Additional information` unless there is useful
context beyond the URL itself.

Optional layout front matter may be included when specifically requested:

```yaml
layout_keep_headings_with_content: true
layout_h2_needspace: 6
layout_h2_before_h3_needspace: 10
layout_h3_needspace: 8
```

The layout boolean must be `true` or `false`. Each numeric layout value must
be an integer from 1 to 30. Omit these fields unless there is a reason to tune
pagination.

Use this structure as a template, adapting the content to the candidate:

---
name: Full Name
headline: Short professional headline
location: City, Country
email: email@example.com
linkedin: "https://www.linkedin.com/in/example/"
website: "www.example.com"
github: "https://github.com/example"
---

## Profile

Short professional summary.

Second paragraph if useful.

## Professional experience

### Job Title
**Company Name** — Location / Remote
*YYYY – YYYY or Present*

- Achievement or responsibility.
- Achievement or responsibility.
- Achievement or responsibility.

### Previous Job Title
**Company Name** — Location
*YYYY – YYYY*

- Achievement or responsibility.
- Achievement or responsibility.
- Achievement or responsibility.

## Key Projects

### Project Name

- What was built or delivered.
- Technologies or systems involved.
- Outcome or business value.

## Core capabilities

### Category Name

- Skill or capability.
- Skill or capability.
- Skill or capability.

### Technical Systems

- Python, SQL, JavaScript / TypeScript
- AWS, Docker, Terraform
- PostgreSQL, APIs, dashboards

## Education

**Qualification**
Institution, YYYY–YYYY

## Additional information

- Extra relevant point.
- Extra relevant point.

Remember: the YAML front matter must be the first content in the file, and
the required fields are `name`, `headline`, `location`, and `email`.
