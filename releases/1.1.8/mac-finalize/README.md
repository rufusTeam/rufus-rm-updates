# Completed Mac 1.1.8 draft finalization

This one-use job is archived and disabled. Do not re-run the original document
finalizer or retag operation. The current eight assets and latest/draft state are
recorded in final-receipt.json and in rufusTeam/rrm release reports.

The initial guarded document update replaced only three documentation assets and
updated the notes, then stopped when GitHub returned its provisional draft tag.
The first read-only inspection lacked draft visibility (403); using the same
existing release-management job scope, a GET-only inspection verified the private
draft, all eight assets and protected latest v1.1.7. A single explicit tag PATCH
then restored intended v1.1.8 while keeping draft=true and make_latest=false.
Final run 44496544812 passed every readback, with no binary changes.

For the later Windows pass, use existing release ID 450687888. The five Mac
binary/blockmap/latest-mac assets must retain their IDs and bytes. Three current
document IDs supersede the initial receipt. Include tag_name=v1.1.8 explicitly
in any future release PATCH; the UI URL of a GitHub draft can use an untagged
placeholder. Keep the release draft until Windows acceptance; do not create a
second release or rerun the completed Mac transfers.

MCP was excluded by the owner because the plugin is unpublished and unused.
Its reader/core alignment remains required before plugin activation, outside
this release. Production web/core, classic Stage and both Mac S3 aliases are
1.1.8. Windows latest.exe and stable GitHub v1.1.7 remain protected until its pass.
