---
name: Email templates are file-based in moso-configuration
description: Email templates live as .json + .content.htm files in moso-configuration, not in an admin panel — must create template files when adding new email templates
type: feedback
---

When creating or modifying email templates, always create/update files in `moso-configuration/src/main/resources/backups/Template/`.

Each template consists of two files:
- `<template_name>.json` — metadata: context vars, from, to, reply_to, title, labels, type
- `<template_name>.content.htm` — email body HTML

The template engine has access to `${Server.currentUser().*}` for the current user and `${root.$relation.field$}` for entity relations.

**Why:** Templates are deployed as file-based backups in `moso-configuration`, not managed through an admin panel at dev time. Creating Java code that references a template name without creating the corresponding template files will result in runtime errors.

**How to apply:** Whenever Java code uses `sendUsingTemplate("template_name", context)`, ensure the matching `.json` and `.content.htm` files exist in `moso-configuration/src/main/resources/backups/Template/`.
