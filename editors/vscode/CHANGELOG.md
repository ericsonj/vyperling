# Changelog

All notable changes to this extension are documented here. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/). Even minor versions are releases, odd minor versions are pre-releases.

## [0.1.0] - Pre-release

First release under the `ericsonjoseph` publisher.

### Added

- Test Explorer discovery of test files in `test_dir`, honoring `forge.yml` naming conventions (snake_case and Ceedling-style camelCase).
- Run a test unit with `vpl test --output json`: pass/fail gutter icons, inline failure messages at `file:line`, ignored tests shown as skipped.
- Debug a test unit: rebuild with `vpl test --debug` and launch the native binary under gdb through the C/C++ extension.
- Settings for the CLI path, default target, parallel jobs and the shell used to run `vpl`.
- Vyperling panel in the Activity Bar with shortcuts to run all tests, open the Test Explorer, show the output and open the settings.

### Fixed

- Debug resolves the target the same way as Run (`vyperling.defaultTarget`, then `forge.yml` `targets.default`), so a cross target is no longer launched under host gdb.
