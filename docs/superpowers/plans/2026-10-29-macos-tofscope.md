# macOS ToFScope Implementation Plan

**Goal:** Give the first macOS user a guided uv installation from a locally supplied wheel.

**Architecture:** Keep the existing bundled Python application and document a separate user walkthrough and release preparation checklist. Verify the distribution using existing checks where the environment permits.

**Tech Stack:** macOS, uv, Python 3.11+, wheel.

**Spec:** Approved conversation design: guided local wheel installation, launch, update, removal, and ToFScope limitations.

## Tasks

- [x] Document setup, launching, saving, updates, removal, and troubleshooting for a macOS user.
- [x] Link the guide and document how to build and hand off the wheel.
- [ ] Build and exercise the wheel in an isolated environment; report any environment restrictions and unverified steps.
