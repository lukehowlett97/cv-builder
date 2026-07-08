
I need you to produce an `input.md` file for my local CV builder.

The file must be valid Markdown and must start with YAML front matter.

Required front matter fields:
- name
- headline
- location
- email

Optional front matter fields:
- linkedin
- website

The CV builder expects these main Markdown sections:
- ## Profile
- ## Professional experience
- ## Core capabilities
- ## Education

It can also include:
- ## Key Projects
- ## Additional information

Use this exact structure. Keep the output as raw Markdown only, with no explanation before or after it.

Template:

---
name: Full Name
headline: Short professional headline
location: City, Country
email: email@example.com
linkedin: "https://www.linkedin.com/in/example/"
website: "www.example.com"
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
Institution, YYYY-YYYY

## Additional information

- Extra relevant point.
- Extra relevant point.
```

Important detail: the builder requires the YAML block at the very top. The required fields are `name`, `headline`, `location`, and `email`; if any of those are missing, the tool will fail.
