"""Capture pipeline package — Playwright orchestrator + supporting hooks.

Modules:
- screen_capture: Python orchestrator that drives the Playwright spec.
- pre_commit_png_size: pre-commit hook rejecting PNGs > 500KB.
- determinism.ts / screen_capture.spec.ts: Playwright TypeScript pieces (loaded by
  the Node toolchain, not Python).

See `.specify/scripts/capture/screen_capture.py --help` and
`platforms/madruga-ai/epics/027-screen-flow-canvas/contracts/capture-script.contract.md`
for the public I/O contract.
"""
