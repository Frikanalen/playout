# Changelog

## [2.1.0](https://github.com/Frikanalen/playout/compare/v2.0.1...v2.1.0) (2026-08-21)


### Features

* **loudness:** normalize playback level from R128 measurements ([#13](https://github.com/Frikanalen/playout/issues/13)) ([7eeec2b](https://github.com/Frikanalen/playout/commit/7eeec2b240dd24587a860b738a9fb39a47f00380))
* use a plain filler loop for gaps under 30 seconds ([#10](https://github.com/Frikanalen/playout/issues/10)) ([799a989](https://github.com/Frikanalen/playout/commit/799a989a9079edd8c81f5f9106819d482cac3579))


### Bug Fixes

* **build:** include generated client runtime dependency ([c5af3f0](https://github.com/Frikanalen/playout/commit/c5af3f063f68aea00247ab8dbb73f76acf408099))
* **build:** ship the generated API client and its deps in the wheel ([324eaf8](https://github.com/Frikanalen/playout/commit/324eaf82a8bf357fee888e297150dc5e51e63231))
* **ci:** build from the checkout, not a Git context ([e1e65ed](https://github.com/Frikanalen/playout/commit/e1e65ed590145222e350a1830f64aeb248d02c28))
* **ci:** let release-please read its config so the chart version tracks releases ([#7](https://github.com/Frikanalen/playout/issues/7)) ([6debe18](https://github.com/Frikanalen/playout/commit/6debe184f032f340c0623087a068de756c45649f))
* **codegen:** emit a flat client tree and wipe stale files first ([fec7b3b](https://github.com/Frikanalen/playout/commit/fec7b3b269aed03a0dacd79b80c355552b0e1b56))
* **docker:** install project with uv pip so local packages land in the image ([7770e05](https://github.com/Frikanalen/playout/commit/7770e058b4277e0bdb1e6fff466fac78d2fcf92e))
* **docker:** reinstall after copying app code to include local packages ([5bd1f6c](https://github.com/Frikanalen/playout/commit/5bd1f6c1af70de3e4a7053ab08f5e6d25aa2f8d8))
* **playout:** make graphics URL configurable ([#15](https://github.com/Frikanalen/playout/issues/15)) ([3c576aa](https://github.com/Frikanalen/playout/commit/3c576aa9c1f2ab4aaef57a4e5c3255fe533c0931))
* **playout:** use mounted media files in production ([#14](https://github.com/Frikanalen/playout/issues/14)) ([ef3f049](https://github.com/Frikanalen/playout/commit/ef3f04986731d23c1d08a6230ca6298631ad4e01))
* **schedule:** stop sending the literal 'today' as a date parameter ([01172d6](https://github.com/Frikanalen/playout/commit/01172d6fa95ef491da5974de2cfe8631414a1c66))

## [2.0.1](https://github.com/Frikanalen/playout/compare/v2.0.0...v2.0.1) (2026-01-10)


### Miscellaneous Chores

* release 2.0.1 ([bced9f2](https://github.com/Frikanalen/playout/commit/bced9f229790a9b9adfc3e12dd15795921f5acda))

## [2.0.0](https://github.com/Frikanalen/playout/compare/v1.0.2...v2.0.0) (2026-01-02)


### ⚠ BREAKING CHANGES

* Remove schedule-service dependency, improve logging ([#4](https://github.com/Frikanalen/playout/issues/4))

### Features

* Remove schedule-service dependency, improve logging ([#4](https://github.com/Frikanalen/playout/issues/4)) ([49807fe](https://github.com/Frikanalen/playout/commit/49807fe5e65cab3951bc5bff94a153ab57996cc2))

## [1.0.2](https://github.com/Frikanalen/playout/compare/v1.0.1...v1.0.2) (2025-12-18)


### Bug Fixes

* explicitly tag in workflow ([1ee60d0](https://github.com/Frikanalen/playout/commit/1ee60d0a43f6df3acae4ccc59848e1863f5ba42e))

## [1.0.1](https://github.com/Frikanalen/playout/compare/v1.0.0...v1.0.1) (2025-12-18)


### Bug Fixes

* GHA: remove redundant "ref" specifier ([742b149](https://github.com/Frikanalen/playout/commit/742b149bba4d9ec5ec3a8806c77348cb40094a44))

## 1.0.0 (2025-12-18)


### Bug Fixes

* Add some release-please files ([2852af0](https://github.com/Frikanalen/playout/commit/2852af037d327317912beadd987af244fc0d44f9))
* grant contents: write to workflow ([893a71b](https://github.com/Frikanalen/playout/commit/893a71b092de9ac7a06754c20481bc6ad50e29ac))


### Miscellaneous Chores

* release 1.0.0 ([877bdb2](https://github.com/Frikanalen/playout/commit/877bdb26cd9faf0c0a0fb06ad20e4ca79477b4ea))
