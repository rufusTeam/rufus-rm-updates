# RRM 1.1.8 Mac draft preparation

This branch prepares only a private draft of the existing updates repository.
It does not publish a stable release, move installer aliases, deploy services,
replace prior assets, or prepare Windows.

The owner authorized preparing and uploading the signed Mac 1.1.8 artifacts to
S3 and Git. The browser has no active GitHub session and this connector has no
release-upload action. The branch-scoped GitHub Actions job uses its short-lived
repository token with contents:write only for release creation and uploads.
No PAT, persistent secret, OAuth grant or external credential is created or read.
Checkout is pinned to the official v7 SHA with credential persistence disabled.

Before the single create request, the job downloads all eight immutable public
S3 artifacts, verifies byte counts and SHA256, refuses an existing v1.1.8, and
captures the current v1.1.7 stable release and asset metadata. It creates draft=true,
make_latest=false; uploads only to that newly returned release ID; checks each
GitHub digest; then verifies the prior stable snapshot is unchanged. There are no
PATCH, DELETE, publish or old-asset upload operations. An uncertain/failed run must
be inspected rather than repeated blindly.

The script's final JSON receipt and job summary identify the actual draft and
asset IDs. No log or profile exports are included. The release must remain on
hold until independent MCP/core alignment and Windows packaging are accepted.
The earlier full backend suite has known baseline failures; focused 1.1.8 checks
pass and the source manifest states the limits.
