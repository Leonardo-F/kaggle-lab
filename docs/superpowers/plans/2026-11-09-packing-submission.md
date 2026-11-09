# Square packing correctness and portable submission plan

Goal: audit the existing simulator, keep the organizer-described grid baseline,
make a complete submission the default export, and deliver an offline HTML.

Design: keep Canvas 2D and the existing layout. Extract the numerical/CSV logic
into a small dependency-free module shared by the browser and Node regression
tests. Build that module, app and CSS into one HTML. A framework or server adds
no useful capability to this task. Default preview is n=1000; the primary action
exports all n=1..1000. Do not auto-download on page load.

Constraints: preserve the quantum project; no runtime dependencies; exact
half-integer grid centers and angle=0; six official CSV columns; 500,500 rows.
The baseline is a feasible reference, not an optimal packing. Modified rotated
layouts are local estimates, not official interval certificates.

Review focus: sub-tolerance overlaps; malformed/empty numeric input; loss of
imported decimal precision; concurrent import/search/export; full-file export
and browser responsiveness.

- [x] Add regression cases for tiny overlaps, rotated contact uncertainty,
  invalid CSV, retained decimals and the complete submission schema.
- [x] Implement a pure geometry/CSV core; use exact decimal separation for
  zero-angle contact and conservatively reject ambiguous rotated contacts.
- [x] Make full export primary, show the baseline formula, prevent stale
  async operations, keep the camera scale fixed while dragging, and explain
  local validation accurately in Chinese.
- [x] Align the Python checker with the conservative contact policy; build
  the standalone HTML reproducibly. Verify the full generated CSV with both
  JavaScript and Python and exact grid invariants.
- [x] Independently review the changes; fix extreme-coordinate validation and
  preserve untouched decimal fields during single-field edits.
- [x] Run a DOM integration smoke check of the actual standalone scripts:
  full CSV download, import/export, busy lock, rotation, invalid export,
  atomic malformed import, and decimal preservation after a keyboard edit.
- [ ] Real-browser visual and local-file download checks: the cloud browser
  blocks file:// URLs. No browser rendering or official certification is claimed.

Validation: 10 JavaScript packing tests, 9 Python packing tests, and 4 unrelated
quantum tests pass. Complete exported CSV contains 1000 puzzles and 500,500
rows; computed baseline total is 28.93766991655058. Standalone has no external
script/style assets. Full CSV import parses synchronously and can pause the UI
for several seconds; controls are locked and progress text is shown beforehand.
