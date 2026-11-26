# Archived macOS 1.1.10 publication

The guarded workflow at commit 7736e7a7956f73810d7f0f5482fc2307d07b6a37 completed successfully in run 45791070672. It added eight Mac assets to existing release 458713908, preserved all six Windows assets and v1.1.9, then verified anonymous downloads. The workflow is now disabled with read-only contents permission. Do not re-run a publication without checking current remote state.

`publication-plan.json` records the accepted source/body and exact artifact hashes. `publication-receipt.json` records the completed job and public downloads. The other text files match the public Mac assets. Binary installers live in the release, not Git source. Mac aliases in S3 were subsequently updated and independently verified; source/QA/S3 closure is recorded in the RRM release branches under docs/releases/1.1.10-mac-publication-20261126.md.
