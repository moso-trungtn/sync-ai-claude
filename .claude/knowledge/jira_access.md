---
name: Jira API Access via Curl
description: How to access Jira tickets using curl with API token authentication
type: reference
---

# Accessing Jira Tickets via Curl

## Method
Use curl with your Jira email and API token:

```bash
curl -s -u "$JIRA_EMAIL:$JIRA_API_TOKEN" "https://mosoteam.atlassian.net/rest/api/2/issue/MOSO-XXXXX"
```

## Environment Variables Needed
- `$JIRA_EMAIL` - Your Atlassian email (e.g., trung.thach@loanfactory.com)
- `$JIRA_API_TOKEN` - Your Atlassian API token

## Response
Returns JSON with full ticket details including:
- `summary` - Task title
- `description` - Full description (in Jira markup format)
- `status` - Current status
- `assignee` - Who it's assigned to
- `priority` - Task priority
- `fields.customfield_10021` - Sprint information
- `attachment` - Attached files/screenshots

## Example Parsing
The JSON response contains all task information. Can be parsed with `jq` for structured access.

## How I'll Use This
When you need to work on a Jira task, you can share the curl output and I'll:
1. Parse the JSON
2. Extract requirements
3. Create implementation plan
4. Help complete the task
