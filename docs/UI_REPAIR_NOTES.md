# CivicFlow coordinated UI repair (2026-10-09)

## Changed
- Complaint language search: immediate clickable matches, no need to open native select to discover results
- Language selector: compact and wrapping alignment
- Evidence upload: compact confirmation, controlled file input width and padding
- Lodge complaint buttons: consistent widths and spacing
- Citizen View/Track buttons: consistent dimensions
- Support: dark-mode-compatible text, surfaces, message bubbles and fields
- Support bot: immediate local help for common CivicFlow tasks; other questions continue through existing Gemini endpoint (network-dependent, 10-second client timeout)
- Contact support: removed placeholder phone number, showing unconfigured instead; configure verified contact before releasing
- Escalation queue: ten rows/page, pagination, alignment, responsive actions, empty/error messages and HTML escaping
- Complaint detail: visible status and priority labels
- Department profile: left-aligned Save Changes, dark-mode input surface
- Shared stylesheet loaded last across 18 HTML pages to avoid overriding app logic

## Escalation queue purpose
Department heads use it to notice time-sensitive SLA-risk and overdue cases; Open navigates to the case, Acknowledge records the head has seen it. Acknowledgement does *not* itself resolve the complaint. The list is capped at ten visible rows and paginated. The server still returns the active dataset; backend pagination would be preferable at large scale.

## Limitations
No authenticated live browser/DB test was possible. The chatbot cannot safely promise to answer all possible questions instantly; Gemini API quota, connectivity, and latency still govern non-FAQ requests. Responsive CSS and dark-theme changes require user-side cross-browser verification. Verify how dynamic status badges look with actual saved complaint data.
