# Changelog

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [1.4.0] - 2025-02-12
- add reordering event handling
## [1.3.8] - 2024-08-19
- remove grain (if we get banding on streams, we have to add it back)
- add slight motion blur
- when toggling ambient light, also inversely toggle atmosphere
- set worldEps for translucency pass to 0 for more sharpness with atmosphere visible
- switch to DLSS for better performance on high-res demo setups
- make sure 'Sun' feature is only listed under lights' section
## [1.3.7] - 2024-08-14
- improve zoom gesture when camera is very close to surface
## [1.3.6] - 2024-04-16
- improving zoom gesture
## [1.3.5] - 2024-03-18
- add globe rotation features (CTRL + R)
## [1.3.4] - 2024-03-15
- add refresh button to force shader graph rebuild; add UI toggling functionality
## [1.3.3] - 2024-03-15
- make sure time_coverage changes don't trigger shader graph recompilations
## [1.3.2] - 2024-03-14
- switch to viewport change update notification
## [1.3.1] - 2024-02-27
- add shader update functionality
## [1.3.0] - 2024-02-19
- fix zoom, wheel, and tumble issues
## [1.2.3] - 2024-02-16
- separate light and other features in UI
## [1.2.2] - 2024-02-15
- make atmos respect camera animations
## [1.2.1] - 2024-01-30
- update timeline ui
## [1.2.0] - 2024-01-25
- add button for feature properties window if extension is loaded
## [1.1.0] - 2024-01-18
- switching to global time management; adjusting timeline ui
## [1.0.3] - 2023-09-01
- version bump
## [1.0.2] - 2023-06-26
- moved default scenario into separate extension (gdn_demo_scenario)
## [1.0.1] - 2023-05-17
- bumping patch version to republish with updated kit version
## [1.0.0] - 2021-04-26
- Initial version of extension UI template with a window
